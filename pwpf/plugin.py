"""The reusable pytest plugin: browser lifecycle, artifacts, markers, root.

Registered through the `pytest11` entry point, so installing the
distribution is enough - a consumer project needs no conftest.py of its own
to get the fixtures, the markers or the artifact handling. Everything here
is application-neutral: which application a test belongs to is inferred from
the consumer's own tests/<app>/ and apps/<app>/ layout, never from a list of
names kept in the framework.

This repository loads the same module through `pytest_plugins` in its root
conftest.py, so it runs against the source tree exactly as a consumer runs
it against the installed wheel. Both routes name it `pwpf.plugin` - the entry
point shares the module's name deliberately - so pytest finds that name
already registered and skips the second import. Registering one module under
two names is an error, which is why the two names must stay in step.
"""

import os
import time
from pathlib import Path

import allure
import pytest
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from pwpf.config.paths import project_root, set_project_root
from pwpf.config.settings import (
    BROWSER_NAME,
    ENVIRONMENT,
    HEADLESS,
    ensure_dir,
    report_dir,
    screenshot_dir,
    trace_dir,
    video_dir,
)
from pwpf.core.app_config import apps_dir, load_app_config
from pwpf.utils.allure_cleanup import clean_allure_results
from pwpf.utils.logger import get_logger
from pwpf.utils.report_embedder import embed_failure_screenshots

LOGGER = get_logger(__name__)

# Recorded at process import time (i.e. before this session's own tests can
# have written anything) so embed_failure_screenshots' `since=` filter can
# exclude screenshots left over from a previous run.
_SESSION_START = time.time()

# Suite-type folders that hold tests not owned by a specific application.
_GENERIC_SUITE_DIRS = {"smoke", "ui", "regression", "api", "tmp"}

# Registered by the plugin so an installed consumer inherits them without
# copying a markers block into its own pytest.ini. This repository also lists
# them in its pytest.ini - the policy guards in tests/ read that file - and
# registering the same marker twice is harmless.
MARKERS = (
    "smoke: quick smoke tests",
    "ui: browser UI tests",
    "regression: regression coverage",
    "api: API-oriented tests",
    "app(name): application under test, applied automatically from the test's path",
    "production: drives a live third-party production site; excluded from every CI run, "
    "opt in locally with -m production",
    'scenario(id): catalog scenario this test implements, e.g. scenario("MNY-HOME-001"); '
    "also attached as an Allure label",
    "quarantined: known-unstable test, excluded from the blocking CI gates and run in a "
    "separate non-blocking job",
)


def _configured_path(config: pytest.Config, option: str, *, expand: bool = False) -> Path | None:
    """A path pytest was configured with, resolved as its owning plugin resolves it.

    Both plugins turn a relative value into an absolute one against the
    directory pytest was invoked from - `os.path.abspath(report_dir)` in
    `allure_pytest/plugin.py`, `Path.cwd() / ...` in
    `pytest_html/basereport.py` - and *not* against rootdir. So that, not the
    project root, is where the files of a run started from a subdirectory land.

    `expand` is where they differ, and it is not cosmetic. pytest-html applies
    `os.path.expandvars` and `expanduser`; allure-pytest applies neither, so
    `--alluredir=~/out` means a literal `./~/out` directory to it. Expanding it
    anyway pointed this framework's cleanup at `$HOME/out` - a real directory,
    outside the project, that Allure never writes to. Reading the wrong path
    finds nothing; deleting from it loses someone's files, so the expansion
    policy follows the plugin that owns the option, never the other one.

    Returns None when the option was not given, or when the plugin that defines
    it is not installed.
    """
    value = config.getoption(option, default=None)
    if not value:
        return None
    text = os.path.expandvars(str(value)) if expand else str(value)
    path = Path(text).expanduser() if expand else Path(text)
    if not path.is_absolute():
        path = Path(config.invocation_params.dir) / path
    # abspath, not resolve(): it normalises `..` the way both plugins do without
    # following symlinks, so the comparisons in _unsafe_to_clean see the same
    # directory the artefacts are written to.
    return Path(os.path.abspath(path))


def _allure_results_dir(config: pytest.Config) -> Path | None:
    """The directory allure-pytest will write this run's results to, or None.

    No expansion (see above), and no fallback to the framework's own
    `allure_results_dir()` either, unlike the report path below: this directory
    is deleted from, and with no `--alluredir` nothing is written this run, so a
    guessed directory would delete a previous run's results that nothing is
    going to replace.
    """
    return _configured_path(config, "allure_report_dir")


def _resolved(path: Path | str) -> Path:
    """The real directory a path names, symlinks and all.

    `resolve()` rather than `os.path.abspath`, and only for the comparisons
    below: abspath normalises `..` but not symlinks, so `--alluredir=link` with
    `link -> .` looked like a dedicated subdirectory while being the project
    root. Non-strict, because the results directory often does not exist yet -
    the existing ancestors resolve and the rest is appended.
    """
    return Path(path).resolve()


def _unsafe_to_clean(results_dir: Path, config: pytest.Config) -> str | None:
    """Why this directory must not be cleaned automatically, or None if it may be.

    `clean_allure_results` only ever removes Allure's own artefacts, so even
    `--alluredir=.` cannot empty a working tree. These boundaries are the second
    line: a results directory that *is* the project root or the invocation
    directory, or that contains either, is being shared with the project's own
    files, and no unattended cleanup belongs there - however the path is
    spelled, which is why both sides are resolved before being compared.
    """
    target = _resolved(results_dir)
    boundaries = (
        ("the project root", _resolved(config.rootpath)),
        ("the directory pytest was invoked from", _resolved(config.invocation_params.dir)),
    )
    for name, boundary in boundaries:
        if target == boundary:
            return f"it is {name}"
        if boundary.is_relative_to(target):
            return f"it contains {name}"
    return None


def pytest_configure(config: pytest.Config) -> None:
    for marker in MARKERS:
        config.addinivalue_line("markers", marker)

    # pytest's rootdir is the authoritative answer to "which project is this?",
    # and it is pinned here - before the xdist guard below - so every process,
    # master and worker alike, resolves artifact and application paths against
    # the consumer project rather than wherever this framework is installed.
    set_project_root(config.rootpath, source="pytest")

    # Same xdist-master guard as pytest_terminal_summary below: the master's
    # own pytest_configure runs before any worker is spawned, so clearing
    # here can never race with a worker that has already started writing.
    if getattr(config, "workerinput", None) is not None:
        return
    allure_dir = _allure_results_dir(config)
    if allure_dir is None:
        return
    unsafe = _unsafe_to_clean(allure_dir, config)
    if unsafe is not None:
        LOGGER.warning(
            "Not clearing stale Allure results in %s: %s. Point --alluredir at a "
            "directory of its own, or clear it yourself.",
            allure_dir,
            unsafe,
        )
        return
    clean_allure_results(allure_dir)


def _app_name_for_path(path: Path) -> str:
    """Infer the owning application from a test's location under tests/.

    Tests live at tests/<app_name>/<suite_type>/... . Anything outside that shape
    (framework-level sanity tests, generic API/regression checks) is labelled
    "framework" rather than forced into an app it doesn't belong to. A new app
    is picked up automatically as soon as its tests/<app_name>/ folder and
    matching apps/<app_name>/ package both exist — no registry to edit here.
    """
    try:
        rel_parts = path.resolve().relative_to(project_root() / "tests").parts
    except ValueError:
        return "framework"
    if (
        rel_parts
        and rel_parts[0] not in _GENERIC_SUITE_DIRS
        and (apps_dir() / rel_parts[0]).is_dir()
    ):
        return rel_parts[0]
    return "framework"


def _app_name(request) -> str:
    return _app_name_for_path(request.node.path)


def pytest_collection_modifyitems(config, items):
    for item in items:
        app_name = _app_name_for_path(item.path)
        item.add_marker(pytest.mark.app(app_name))

        if app_name == "framework":
            continue
        try:
            app_cfg = load_app_config(app_name)
        except FileNotFoundError:
            continue
        if app_cfg.retry_count:
            item.add_marker(pytest.mark.flaky(reruns=app_cfg.retry_count))


@pytest.fixture(scope="session")
def playwright_context():
    with sync_playwright() as pw:
        yield pw


@pytest.fixture(scope="session")
def browser(playwright_context):
    launch_kwargs = {"headless": HEADLESS, "args": ["--disable-dev-shm-usage"]}
    try:
        browser_launcher = getattr(playwright_context, BROWSER_NAME, None)
        if browser_launcher is None:
            raise AttributeError(f"Unsupported browser: {BROWSER_NAME}")
        browser = browser_launcher.launch(**launch_kwargs)
    except Exception as exc:
        pytest.skip(f"Playwright browser could not be launched: {exc}")
    yield browser
    browser.close()


@pytest.fixture
def browser_context_args(request):
    # Function-scoped (not session-scoped) so it can read which app the
    # current test belongs to and use that app's own ignore_https_errors
    # setting - every existing app's config omits the field and gets True,
    # unchanged from before.
    ignore_https_errors = True
    app_name = _app_name(request)
    if app_name != "framework":
        try:
            ignore_https_errors = load_app_config(app_name).ignore_https_errors
        except FileNotFoundError:
            pass
    return {
        "viewport": {"width": 1440, "height": 900},
        "ignore_https_errors": ignore_https_errors,
    }


@pytest.fixture
def context(browser, browser_context_args, request):
    app_video_dir = ensure_dir(video_dir() / _app_name(request))
    ctx = browser.new_context(
        **browser_context_args,
        record_video_dir=str(app_video_dir),
        record_video_size={"width": 1280, "height": 720},
    )
    yield ctx
    ctx.close()


def _save_failure_screenshot(page, app_name: str, test_name: str, node) -> None:
    app_screenshot_dir = ensure_dir(screenshot_dir() / app_name)
    path = app_screenshot_dir / f"{test_name}.png"
    try:
        page.screenshot(path=str(path), full_page=True)
        setattr(node, "screenshot_path", str(path))
        LOGGER.warning("Saved failure screenshot: %s", path)
    except PlaywrightError as exc:
        LOGGER.warning("Unable to save screenshot: %s", exc)


def _save_failure_trace(context, app_name: str, test_name: str, node) -> None:
    app_trace_dir = ensure_dir(trace_dir() / app_name)
    path = app_trace_dir / f"{test_name}.zip"
    try:
        context.tracing.stop(path=str(path))
        setattr(node, "trace_path", str(path))
        LOGGER.warning("Saved failure trace: %s", path)
    except PlaywrightError as exc:
        LOGGER.warning("Unable to save trace: %s", exc)


def _save_failure_video(video, app_name: str, test_name: str, node) -> None:
    app_video_dir = ensure_dir(video_dir() / app_name)
    dest = app_video_dir / f"{test_name}.webm"
    try:
        saved_path = Path(video.path()).replace(dest)
        setattr(node, "video_path", str(saved_path))
        LOGGER.warning("Saved failure video: %s", saved_path)
    except PlaywrightError as exc:
        LOGGER.warning("Unable to save video: %s", exc)


def _log_console_error(page, msg) -> None:
    # Passive observability only - only error-level console messages are
    # logged (not log/warning/info noise), and this never affects the test
    # outcome.
    if msg.type == "error":
        LOGGER.error("Browser console error on %s: %s", page.url, msg.text)


def _log_page_error(page, error) -> None:
    # A page-side uncaught JS exception - always worth surfacing, but still
    # passive: it does not fail the test.
    LOGGER.error("Uncaught page error on %s: %s", page.url, error)


@pytest.fixture
def page(context, request):
    # Trace lifecycle is owned entirely by this fixture (start here, stop below)
    # so it is guaranteed to wrap the actual test execution, and to run only for
    # tests that actually requested a page — non-UI tests never pay for a browser.
    context.tracing.start(screenshots=True, snapshots=True)
    p = context.new_page()
    p.on("console", lambda msg: _log_console_error(p, msg))
    p.on("pageerror", lambda error: _log_page_error(p, error))
    yield p

    failed = bool(getattr(request.node, "rep_call", None) and request.node.rep_call.failed)
    app_name = _app_name(request)
    test_name = request.node.name

    if failed:
        _save_failure_screenshot(p, app_name, test_name, request.node)
        _save_failure_trace(context, app_name, test_name, request.node)
    else:
        try:
            context.tracing.stop()  # discard: no path means nothing is written
        except PlaywrightError:
            pass

    video = p.video
    p.close()
    if video is None:
        return
    if failed:
        _save_failure_video(video, app_name, test_name, request.node)
    else:
        try:
            Path(video.path()).unlink(missing_ok=True)
        except PlaywrightError:
            pass


@pytest.fixture(autouse=True)
def _tag_allure_application(request):
    allure.dynamic.label("application", _app_name(request))
    allure.dynamic.label("browser", BROWSER_NAME)
    allure.dynamic.label("environment", ENVIRONMENT)
    # Catalog scenario ids, from @pytest.mark.scenario("<id>"), as a label so a
    # report row can be traced back to the scenario it implements. De-duplicated
    # because a test may carry the marker more than once (one test may cover
    # several scenarios) and Allure would otherwise show the same label twice.
    seen = set()
    for marker in request.node.iter_markers("scenario"):
        for scenario_id in marker.args:
            if scenario_id not in seen:
                seen.add(scenario_id)
                allure.dynamic.label("scenario", scenario_id)
    yield


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    setattr(item, "rep_" + rep.when, rep)

    if rep.when == "call" and getattr(item, "screenshot_path", None) and rep.failed:
        rep.screenshot_path = item.screenshot_path

    return rep


def _html_report_path(config: pytest.Config) -> Path:
    """Where this run's pytest-html report actually is, as an absolute path.

    pytest-html owns `--html`. Reading the option back from the config is what
    keeps this in step with wherever the report was actually written; the
    hardcoded `"reports/pytest_report.html"` this replaces was right for one
    `--html` value and silently embedded nothing for any other.

    `expand=True` matches pytest-html, which runs the value through
    `os.path.expandvars` and `expanduser` (`pytest_html/basereport.py`), so a
    `--html=$OUT/report.html` points both of us at the same file.

    With no `--html` (pytest-html absent, or no report asked for) the
    framework's own convention stands in: `report_dir()`, which is anchored to
    the consumer project's root like every other artifact directory and never
    to wherever the framework itself is installed. Embedding only ever reads,
    so a fallback here costs nothing worse than "report not found". Both halves
    are pinned by tests/test_report_path.py.
    """
    return _configured_path(config, "htmlpath", expand=True) or report_dir() / "pytest_report.html"


@pytest.hookimpl(trylast=True)
def pytest_terminal_summary(terminalreporter, exitstatus, config):
    # Under pytest-xdist, this hook fires in every worker process as well as
    # the master - `workerinput` is only set on a worker's `config`. Without
    # this guard, N workers + the master each redundantly re-scan and
    # rewrite the same report.
    if getattr(config, "workerinput", None) is not None:
        return
    embed_failure_screenshots(_html_report_path(config), since=_SESSION_START)
