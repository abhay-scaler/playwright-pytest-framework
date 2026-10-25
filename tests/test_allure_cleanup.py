"""Clearing stale Allure results: which directory, and what inside it.

Three layers, tested separately.

`clean_allure_results()` removes Allure's own artefacts from the directory it is
handed - allure-pytest never clears its own output, so without this every run
adds another UUID-named result to the same folder forever. It removes *only*
those artefacts: a consumer may point `--alluredir` at a directory it shares
with other files, and `environment.properties`, `executor.json`,
`categories.json` and `history/` are inputs to `allure generate` that a project
places deliberately.

The plugin decides *which* directory. allure-pytest resolves `--alluredir` with
`os.path.abspath` (`allure_pytest/plugin.py`) - against the working directory,
with no `~` and no `$VAR` expansion - so that is how it is resolved here.
Expanding `~` instead pointed the cleanup at `$HOME/<dir>`, a real directory
outside the project that Allure never writes to; the subprocess test below is
that reproduction, with `HOME` redirected into a temporary directory.

The plugin also refuses to clean a directory that is, or contains, the project
root or the invocation directory, however the option was spelled.

The subprocess tests establish real pytest and allure-pytest behaviour rather
than asserting against a mock of it, in temporary projects with a temporary
HOME, no network and no browser.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from pwpf.config import paths
from pwpf.config.paths import PROJECT_MARKER, ROOT_ENV_VAR, project_root, set_project_root
from pwpf.config.settings import allure_results_dir
from pwpf.plugin import _allure_results_dir, _unsafe_to_clean
from pwpf.utils import allure_cleanup
from pwpf.utils.allure_cleanup import clean_allure_results

FRAMEWORK_ROOT = project_root()
FRAMEWORK_PACKAGE = FRAMEWORK_ROOT / "pwpf"


@pytest.fixture(autouse=True)
def _restore_pinned_roots():
    """Root pinning is process-global; put it back so one test cannot relocate
    every later one."""
    caller, session = paths._caller_root, paths._pytest_root
    yield
    paths._caller_root, paths._pytest_root = caller, session


@pytest.fixture
def cleanup_log():
    """The cleanup module's own log records. Its logger does not propagate, so
    `caplog` sees nothing - a handler of our own is the way to read it."""
    messages: list[str] = []

    class Collect(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            messages.append(record.getMessage())

    logger = logging.getLogger(allure_cleanup.__name__)
    handler = Collect()
    logger.addHandler(handler)
    yield messages
    logger.removeHandler(handler)


def _require_symlinks(tmp_path: Path) -> None:
    probe = tmp_path / "symlink-probe"
    try:
        probe.symlink_to(tmp_path)
    except (OSError, NotImplementedError) as error:
        pytest.skip(f"symlinks cannot be created here: {error}")
    probe.unlink()


def _artifact(directory: Path, kind: str = "result.json") -> Path:
    """A file named the way allure-pytest names its own output."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{uuid.uuid4()}-{kind}"
    path.write_text('{"stale": true}', encoding="utf-8")
    return path


# --------------------------------------------------------------------------- #
# What the cleanup removes, and what it must not
# --------------------------------------------------------------------------- #


def test_allures_own_artifacts_are_removed(tmp_path):
    results_dir = tmp_path / "allure-results"
    artifacts = [
        _artifact(results_dir, kind)
        for kind in ("result.json", "container.json", "globals.json", "attachment.png")
    ]

    removed = clean_allure_results(results_dir)

    assert removed == 4
    assert not [a for a in artifacts if a.exists()]
    assert list(results_dir.iterdir()) == []


def test_report_inputs_and_unrelated_files_survive(tmp_path):
    """The reason the cleanup is pattern-based: these belong to the project, not
    to allure-pytest, and three of them are inputs `allure generate` reads."""
    results_dir = tmp_path / "allure-results"
    results_dir.mkdir()
    keepers = []
    for name in (
        "environment.properties",
        "executor.json",
        "categories.json",
        "notes.txt",
        "my-result.json",
    ):
        keeper = results_dir / name
        keeper.write_text("keep", encoding="utf-8")
        keepers.append(keeper)
    stale = _artifact(results_dir)

    removed = clean_allure_results(results_dir)

    assert removed == 1
    assert not stale.exists()
    assert [k for k in keepers if k.is_file()] == keepers


def test_no_directory_is_ever_removed(tmp_path):
    """allure-pytest writes no subdirectories, so the cleanup has no business
    deleting one - `history/` in particular is how trend data survives."""
    results_dir = tmp_path / "allure-results"
    history = results_dir / "history"
    history.mkdir(parents=True)
    (history / "history.json").write_text("[]", encoding="utf-8")
    nested = results_dir / "someones-data" / "deeper"
    nested.mkdir(parents=True)
    (nested / "keep.txt").write_text("keep", encoding="utf-8")
    stale = _artifact(results_dir)

    removed = clean_allure_results(results_dir)

    assert removed == 1
    assert not stale.exists()
    assert (history / "history.json").is_file()
    assert (nested / "keep.txt").is_file()


def test_clean_allure_results_is_a_noop_when_directory_is_absent(tmp_path):
    missing_dir = tmp_path / "does-not-exist"

    removed = clean_allure_results(missing_dir)

    assert removed == 0
    assert not missing_dir.exists()


def test_clean_allure_results_touches_nothing_outside_the_directory_it_is_given(tmp_path):
    results_dir = tmp_path / "allure-results"
    stale = _artifact(results_dir)
    sibling = tmp_path / "allure-results-from-another-run"
    kept_sibling = _artifact(sibling)
    loose_file = tmp_path / "keep.txt"
    loose_file.write_text("keep", encoding="utf-8")

    removed = clean_allure_results(results_dir)

    assert removed == 1
    assert not stale.exists()
    assert kept_sibling.is_file()
    assert loose_file.is_file()


def test_a_deletion_that_fails_is_reported_and_the_rest_still_proceeds(
    tmp_path, monkeypatch, cleanup_log
):
    """Housekeeping must not end a run: one artefact that cannot be removed is
    logged and skipped, and the others are still cleared. The failure is
    injected rather than staged with permission bits, which prove nothing when
    the tests run as root."""
    results_dir = tmp_path / "allure-results"
    doomed = _artifact(results_dir, "result.json")
    removable = _artifact(results_dir, "container.json")
    real_unlink = Path.unlink

    def unlink(self, *args, **kwargs):
        if self.name == doomed.name:
            raise PermissionError(13, "Permission denied")
        return real_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", unlink)

    removed = clean_allure_results(results_dir)

    assert removed == 1
    assert doomed.is_file(), "the undeletable artefact should simply be left alone"
    assert not removable.exists(), "a later artefact was skipped after the failure"
    assert [m for m in cleanup_log if "Could not remove the stale Allure result" in m]
    assert [m for m in cleanup_log if "could not be removed" in m]


def test_a_results_directory_that_cannot_be_read_is_reported_not_raised(
    tmp_path, monkeypatch, cleanup_log
):
    results_dir = tmp_path / "allure-results"
    results_dir.mkdir()

    def iterdir(self):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(Path, "iterdir", iterdir)

    assert clean_allure_results(results_dir) == 0
    assert [m for m in cleanup_log if "Could not read the Allure results directory" in m]


def test_called_without_a_directory_it_uses_the_project_root_convention(tmp_path):
    """The documented default for a deliberate call. The plugin does not rely on
    it - it passes the directory the run is configured to write to."""
    root = tmp_path / "consumer"
    root.mkdir()
    set_project_root(root, source="caller")
    stale = _artifact(allure_results_dir())

    removed = clean_allure_results()

    assert removed == 1
    assert not stale.exists()
    assert allure_results_dir() == root.resolve() / "reports" / "allure-results"


# --------------------------------------------------------------------------- #
# Which directory the plugin cleans
# --------------------------------------------------------------------------- #


def _config(alluredir: str | None, invocation_dir: Path, rootpath: Path | None = None):
    """The three things the resolution and the guard read off a real pytest
    Config. `--alluredir` stores to allure-pytest's own dest, `allure_report_dir`."""
    return cast(
        pytest.Config,
        SimpleNamespace(
            getoption=lambda name, default=None: (
                alluredir if name == "allure_report_dir" else default
            ),
            invocation_params=SimpleNamespace(dir=invocation_dir),
            rootpath=rootpath if rootpath is not None else invocation_dir,
        ),
    )


def test_the_configured_relative_default_resolves_under_the_project_root(tmp_path):
    """The ordinary invocation - pytest started at the project root, as
    pytest.ini's `--alluredir=reports/allure-results` assumes. This is the case
    that must not change: it is exactly `allure_results_dir()`."""
    root = tmp_path / "consumer"
    root.mkdir()
    set_project_root(root, source="caller")

    resolved = _allure_results_dir(_config("reports/allure-results", root))

    assert resolved == root / "reports" / "allure-results"
    assert resolved == allure_results_dir()


def test_a_relative_alluredir_from_a_subdirectory_resolves_under_that_subdirectory(tmp_path):
    """allure-pytest writes beside the invocation directory, so that is the
    directory to clear - not the project root's."""
    root = tmp_path / "consumer"
    subdirectory = root / "tests"
    subdirectory.mkdir(parents=True)
    set_project_root(root, source="caller")

    resolved = _allure_results_dir(_config("reports/allure-results", subdirectory))

    assert resolved == subdirectory / "reports" / "allure-results"
    assert resolved != allure_results_dir()


def test_an_absolute_alluredir_is_taken_as_given(tmp_path):
    elsewhere = tmp_path / "somewhere" / "allure"

    assert _allure_results_dir(_config(str(elsewhere), tmp_path)) == elsewhere


def test_an_alternative_relative_alluredir_is_honoured(tmp_path):
    """A consumer is free to put results anywhere; the cleanup follows the
    option rather than assuming a directory name."""
    root = tmp_path / "consumer"
    root.mkdir()
    set_project_root(root, source="caller")

    resolved = _allure_results_dir(_config("build/allure", root))

    assert resolved == root / "build" / "allure"


def test_a_tilde_is_not_expanded_because_allure_does_not_expand_it(tmp_path):
    """The destructive bug, at unit level: allure-pytest's `os.path.abspath`
    leaves `~` alone, making it a literal directory name under the invocation
    directory. Expanding it here pointed the cleanup at the real home."""
    invocation = tmp_path / "consumer"
    invocation.mkdir()

    resolved = _allure_results_dir(_config("~/allure-out", invocation))

    assert resolved == invocation / "~" / "allure-out"
    assert resolved != Path.home() / "allure-out"
    assert str(Path.home()) not in str(resolved)


def test_parent_segments_are_normalised_the_way_allure_normalises_them(tmp_path):
    invocation = tmp_path / "consumer" / "tests"
    invocation.mkdir(parents=True)

    resolved = _allure_results_dir(_config("../out", invocation))

    assert resolved == tmp_path / "consumer" / "out"
    assert ".." not in str(resolved)


def test_without_the_option_there_is_no_cleanup_target(tmp_path):
    """No `--alluredir` (or no allure-pytest): nothing is written this run, so
    there is nothing to clear. Deliberately *not* falling back to
    `allure_results_dir()` - that would delete a previous run's results which
    this run is not going to replace."""
    root = tmp_path / "consumer"
    root.mkdir()
    set_project_root(root, source="caller")

    assert _allure_results_dir(_config(None, root)) is None
    assert _allure_results_dir(_config("", root)) is None


# --------------------------------------------------------------------------- #
# The directories the plugin refuses to clean
# --------------------------------------------------------------------------- #


def test_a_dedicated_results_directory_is_safe_to_clean(tmp_path):
    root = tmp_path / "consumer"
    results = root / "reports" / "allure-results"
    results.mkdir(parents=True)

    assert _unsafe_to_clean(results, _config(None, root, rootpath=root)) is None


def test_the_invocation_directory_is_refused(tmp_path):
    """`--alluredir=.` - the cleanup would be operating in the middle of the
    project's own files."""
    root = tmp_path / "consumer"
    root.mkdir()

    reason = _unsafe_to_clean(root, _config(".", root, rootpath=root))

    assert reason is not None
    assert "invoked from" in reason or "project root" in reason


def test_a_directory_above_the_project_is_refused(tmp_path):
    """`--alluredir=..` and anything else that would reach over the project."""
    root = tmp_path / "consumer"
    (root / "tests").mkdir(parents=True)

    reason = _unsafe_to_clean(tmp_path, _config("..", root / "tests", rootpath=root))

    assert reason is not None
    assert "contains" in reason


def test_a_symlink_to_the_project_root_is_refused(tmp_path):
    """`--alluredir=link` with `link -> .`: `os.path.abspath` normalises `..`
    but not symlinks, so the apparent path looked like a dedicated
    subdirectory while being the project root itself."""
    _require_symlinks(tmp_path)
    root = tmp_path / "consumer"
    root.mkdir()
    (root / "selflink").symlink_to(root)

    reason = _unsafe_to_clean(root / "selflink", _config("selflink", root, rootpath=root))

    assert reason is not None, "a symlink to the project root slipped past the boundary check"


def test_a_real_subdirectory_reached_through_a_symlink_is_still_safe(tmp_path):
    """The other side of resolving: a genuine results directory that happens to
    be reached through a link is a dedicated directory, and stays cleanable."""
    _require_symlinks(tmp_path)
    root = tmp_path / "consumer"
    (root / "reports" / "allure-results").mkdir(parents=True)
    (root / "link").symlink_to(root / "reports")

    reason = _unsafe_to_clean(
        root / "link" / "allure-results", _config("link/allure-results", root, rootpath=root)
    )

    assert reason is None


def test_the_project_root_is_refused_even_from_a_subdirectory(tmp_path):
    root = tmp_path / "consumer"
    subdirectory = root / "tests"
    subdirectory.mkdir(parents=True)

    reason = _unsafe_to_clean(root, _config("..", subdirectory, rootpath=root))

    assert reason is not None


# --------------------------------------------------------------------------- #
# End to end: real pytest, real allure-pytest, temporary HOME
# --------------------------------------------------------------------------- #


CONSUMER_CONFTEST = 'pytest_plugins = ["pwpf.plugin"]\n'
CONSUMER_TEST = "def test_ok():\n    assert True\n"


def _consumer(tmp_path: Path, addopts: str) -> Path:
    root = tmp_path / "consumer"
    (root / "tests" / "demo_app").mkdir(parents=True)
    (root / PROJECT_MARKER).write_text(
        f"[pytest]\ntestpaths = tests\naddopts = {addopts}\n", encoding="utf-8"
    )
    (root / "conftest.py").write_text(CONSUMER_CONFTEST, encoding="utf-8")
    (root / "tests" / "demo_app" / "test_demo.py").write_text(CONSUMER_TEST, encoding="utf-8")
    return root


def _run_from(
    directory: Path,
    *,
    home: Path,
    decoy_root: Path | None = None,
) -> subprocess.CompletedProcess:
    """Real pytest in a subprocess, with HOME redirected into the test's own
    temporary directory so nothing here can reach a real home directory."""
    home.mkdir(parents=True, exist_ok=True)
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": str(home),
        "PYTHONPATH": str(FRAMEWORK_ROOT),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    if decoy_root is not None:
        # A root that disagrees with pytest's: pytest's rootdir must win, and
        # nothing here may be cleaned on its account.
        env[ROOT_ENV_VAR] = str(decoy_root)
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
        cwd=directory,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )


def _framework_log(root: Path) -> str:
    """The framework's own log from a consumer run. The plugin's diagnostics are
    emitted during `pytest_configure`, while pytest's output capture is in
    place, so the log file is where they reliably land."""
    return "".join(
        log.read_text(encoding="utf-8") for log in (root / "logs").rglob("framework.log")
    )


def test_a_run_from_a_subdirectory_clears_the_results_it_actually_writes(tmp_path):
    """Fails against the implementation that cleaned the project root's
    directory while allure-pytest wrote to the invocation directory's."""
    pytest.importorskip("allure_pytest", reason="allure-pytest is not installed")
    root = _consumer(tmp_path, "--alluredir=reports/allure-results")
    written_dir = root / "tests" / "reports" / "allure-results"
    stale_in_written = _artifact(written_dir)
    stale_at_root = _artifact(root / "reports" / "allure-results")
    decoy_root = tmp_path / "decoy"
    stale_in_decoy = _artifact(decoy_root / "reports" / "allure-results")

    result = _run_from(root / "tests", home=tmp_path / "home", decoy_root=decoy_root)

    assert result.returncode == 0, result.stdout + result.stderr
    # This run's results are there, and the previous run's are gone - which is
    # the whole point of the cleanup.
    assert not stale_in_written.exists(), (
        "the directory allure-pytest wrote to was not cleared, so results accumulate: "
        f"{sorted(p.name for p in written_dir.iterdir())}"
    )
    written = sorted(written_dir.glob("*-result.json"))
    assert written, f"allure-pytest wrote no result file into {written_dir}\n{result.stdout}"
    # Nothing writes to these, so nothing may be deleted from them either.
    assert stale_at_root.is_file(), "a directory this run never writes to was cleared"
    assert stale_in_decoy.is_file(), f"{ROOT_ENV_VAR} was followed instead of pytest's rootdir"
    # Consumer isolation: the framework's own package stays clean.
    assert not (FRAMEWORK_PACKAGE / "reports").exists()
    assert not list(FRAMEWORK_PACKAGE.rglob("allure-results"))


def test_a_tilde_alluredir_leaves_the_home_directory_alone(tmp_path):
    """The reproduction of the destructive defect, made permanent. Against the
    expanding implementation this fails: `$HOME/allure-out` is emptied while
    allure-pytest writes into a literal `~` directory under the project."""
    pytest.importorskip("allure_pytest", reason="allure-pytest is not installed")
    root = _consumer(tmp_path, "--alluredir=~/allure-out")
    home = tmp_path / "home"
    in_home = _artifact(home / "allure-out")

    result = _run_from(root, home=home)

    assert result.returncode == 0, result.stdout + result.stderr
    assert in_home.is_file(), (
        "a file in $HOME was deleted: the configured ~ was expanded, but allure-pytest "
        "treats it as a literal directory name"
    )
    literal = root / "~" / "allure-out"
    written = sorted(literal.glob("*-result.json"))
    assert written, f"allure-pytest wrote no result into {literal}\n{result.stdout}"


def test_an_alluredir_of_the_invocation_directory_is_refused_with_a_diagnostic(tmp_path):
    """`--alluredir=.`: nothing is deleted, and the run says why rather than
    silently doing nothing."""
    pytest.importorskip("allure_pytest", reason="allure-pytest is not installed")
    root = _consumer(tmp_path, "--alluredir=.")
    stale_shaped_like_allure = _artifact(root)
    unrelated = root / "keep.txt"
    unrelated.write_text("keep", encoding="utf-8")

    result = _run_from(root, home=tmp_path / "home")

    assert result.returncode == 0, result.stdout + result.stderr
    assert stale_shaped_like_allure.is_file(), "the invocation directory was cleaned anyway"
    assert unrelated.is_file()
    assert (root / PROJECT_MARKER).is_file()
    logs = _framework_log(root)
    diagnostics = logs + result.stdout + result.stderr
    refusal = re.search(r"Not clearing stale Allure results", diagnostics)
    assert refusal, f"no diagnostic explaining the refusal\n{diagnostics}"
    assert "it is the project root" in logs or "invoked from" in logs, logs


def test_a_symlinked_alluredir_cannot_clean_the_project_root(tmp_path):
    """The boundary check through a real run: `--alluredir=selflink` where the
    link points at the project root. Against the string-only comparison this
    deleted an Allure-shaped file from the root without a word."""
    pytest.importorskip("allure_pytest", reason="allure-pytest is not installed")
    _require_symlinks(tmp_path)
    root = _consumer(tmp_path, "--alluredir=selflink")
    (root / "selflink").symlink_to(root)
    protected = _artifact(root)
    unrelated = root / "keep.txt"
    unrelated.write_text("keep", encoding="utf-8")

    result = _run_from(root, home=tmp_path / "home")

    assert result.returncode == 0, result.stdout + result.stderr
    assert protected.is_file(), (
        "an Allure-shaped file in the project root was deleted through a symlinked "
        "--alluredir, which the boundary check exists to prevent"
    )
    assert unrelated.is_file()
    assert (root / PROJECT_MARKER).is_file()
    logs = _framework_log(root)
    assert "Not clearing stale Allure results" in logs, logs
    assert "it is the project root" in logs, logs


def test_a_cleanup_failure_does_not_stop_collection_or_execution(tmp_path):
    """The cleanup runs in `pytest_configure`, so an unhandled filesystem error
    there killed the session with an INTERNALERROR before a single test was
    collected. The failure is injected in the consumer's own conftest - a
    deterministic fault, not permission bits that root would ignore."""
    pytest.importorskip("allure_pytest", reason="allure-pytest is not installed")
    root = _consumer(tmp_path, "--alluredir=results")
    # Fails only for the files the cleanup is allowed to touch, so nothing else
    # in the subprocess is affected.
    (root / "conftest.py").write_text(
        "import pathlib\n"
        "\n"
        "_real_unlink = pathlib.Path.unlink\n"
        "\n"
        "\n"
        "def _unlink(self, *args, **kwargs):\n"
        '    if self.name.endswith(("-result.json", "-container.json")):\n'
        '        raise PermissionError(13, "injected failure")\n'
        "    return _real_unlink(self, *args, **kwargs)\n"
        "\n"
        "\n"
        "pathlib.Path.unlink = _unlink\n"
        "\n"
        'pytest_plugins = ["pwpf.plugin"]\n',
        encoding="utf-8",
    )
    undeletable = _artifact(root / "results")

    result = _run_from(root, home=tmp_path / "home")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "INTERNALERROR" not in result.stdout + result.stderr
    assert "1 passed" in result.stdout, result.stdout
    assert undeletable.is_file(), "the injected failure should have left the file in place"
    logs = _framework_log(root)
    assert "Could not remove the stale Allure result" in logs, logs


def test_a_run_without_alluredir_clears_nothing(tmp_path):
    """With no `--alluredir`, allure-pytest writes nothing, so a previous run's
    results are left where they are instead of being deleted by a cleanup that
    has no output directory to clean."""
    root = _consumer(tmp_path, "-ra")
    stale = _artifact(root / "reports" / "allure-results")

    result = _run_from(root, home=tmp_path / "home")

    assert result.returncode == 0, result.stdout + result.stderr
    assert stale.is_file(), "results were deleted for a run that writes none"
