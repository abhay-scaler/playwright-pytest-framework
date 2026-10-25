"""Where the plugin looks for the pytest-html report it embeds screenshots into.

The report is the one artifact the framework does not place itself: pytest-html
owns `--html` and resolves a relative path against the directory pytest was
invoked from. The embed step used to pass the literal
`"reports/pytest_report.html"`, which is only ever the right file for a project
that passes exactly that `--html` value - any other report name or directory,
or an absolute path, and the step looked somewhere nothing had been written,
logged "Report not found" and embedded nothing, however many screenshots the
run had produced. (A relative literal and pytest-html's own relative
resolution do agree when both see the same working directory, which is why
running from a subdirectory alone did not expose it - measured, not assumed.)

Reading the option back from the config fixes that for any path a consumer
passes, and when there is no option the framework's own project-root
convention stands in. These tests pin both halves, that the `$VAR` and `~`
expansion pytest-html performs is matched here (and nowhere near the Allure
path, which allure-pytest does not expand and which is deleted from), and that
neither branch can land inside the installed framework. Deterministic throughout - temporary
directories and one subprocess, no network and no browser.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from pwpf.config import paths
from pwpf.config.paths import PROJECT_MARKER, ROOT_ENV_VAR, project_root, set_project_root
from pwpf.config.settings import report_dir
from pwpf.plugin import _html_report_path

FRAMEWORK_ROOT = project_root()
FRAMEWORK_PACKAGE = Path(__file__).resolve().parent.parent / "pwpf"


@pytest.fixture(autouse=True)
def _restore_pinned_roots():
    """Root pinning is process-global; put it back so one test cannot relocate
    every later one."""
    caller, session = paths._caller_root, paths._pytest_root
    yield
    paths._caller_root, paths._pytest_root = caller, session


def _config(html_path: str | None, invocation_dir: Path) -> pytest.Config:
    """The two things `_html_report_path` reads off a real pytest Config."""
    return cast(
        pytest.Config,
        SimpleNamespace(
            getoption=lambda name, default=None: html_path if name == "htmlpath" else default,
            invocation_params=SimpleNamespace(dir=invocation_dir),
        ),
    )


# --------------------------------------------------------------------------- #
# Resolution
# --------------------------------------------------------------------------- #


def test_a_relative_html_option_resolves_against_the_invocation_directory(tmp_path):
    """The regression: pytest-html wrote the report next to where pytest was
    started, so that is where it has to be looked for."""
    subdirectory = tmp_path / "project" / "tests"
    subdirectory.mkdir(parents=True)

    resolved = _html_report_path(_config("reports/pytest_report.html", subdirectory))

    assert resolved == subdirectory / "reports" / "pytest_report.html"


def test_an_absolute_html_option_is_taken_as_given(tmp_path):
    report = tmp_path / "elsewhere" / "report.html"

    assert _html_report_path(_config(str(report), tmp_path)) == report


def test_an_environment_variable_in_the_html_path_is_expanded(tmp_path, monkeypatch):
    """pytest-html runs the value through `os.path.expandvars`
    (`pytest_html/basereport.py`), so `--html=$OUT/report.html` has to be read
    the same way here or the embed step looks for a literal `$OUT` directory.
    The Allure path deliberately does *not* do this - allure-pytest does not
    either, and that path is the one that gets deleted from."""
    monkeypatch.setenv("PWPF_TEST_OUT", str(tmp_path / "out"))

    resolved = _html_report_path(_config("$PWPF_TEST_OUT/report.html", tmp_path))

    assert resolved == tmp_path / "out" / "report.html"


def test_a_tilde_in_the_html_path_is_expanded(tmp_path, monkeypatch):
    """Also pytest-html's behaviour (`expanduser`). Harmless here because
    embedding only reads - and the opposite of what the Allure path must do."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))

    resolved = _html_report_path(_config("~/report.html", tmp_path))

    assert resolved == tmp_path / "home" / "report.html"


def test_without_the_html_option_the_report_falls_under_the_project_root(tmp_path):
    """No `--html` (pytest-html absent, or no report requested): the framework's
    own convention applies, anchored to the consumer project."""
    root = tmp_path / "consumer"
    root.mkdir()
    set_project_root(root, source="caller")

    resolved = _html_report_path(_config(None, tmp_path / "somewhere" / "else"))

    assert resolved == root.resolve() / "reports" / "pytest_report.html"
    assert resolved == report_dir() / "pytest_report.html"


def test_the_report_is_never_resolved_inside_the_framework_package(tmp_path):
    """The failure this whole path contract exists to prevent: an installed
    framework must not collect artifacts beside its own code."""
    root = tmp_path / "consumer"
    root.mkdir()
    set_project_root(root, source="caller")

    for html_option in (None, "reports/pytest_report.html"):
        resolved = _html_report_path(_config(html_option, root / "tests"))

        assert FRAMEWORK_PACKAGE not in resolved.parents, resolved
        assert str(resolved).startswith(str(root.resolve())), resolved


# --------------------------------------------------------------------------- #
# End to end, from a subdirectory
# --------------------------------------------------------------------------- #


# A report path of the consumer's own choosing - which is the point: the old
# hardcoded literal matched one value only, and this is not it.
CONSUMER_PYTEST_INI = """[pytest]
testpaths = tests
addopts = --html=artifacts/run-report.html
"""

# The plugin is not installed as a distribution here, so this consumer loads it
# the same way this repository does while developing it. What matters for this
# test is only that the plugin is active; how it was loaded is not the subject.
CONSUMER_CONFTEST = 'pytest_plugins = ["pwpf.plugin"]\n'

# Writes its screenshot the way the framework does - through the settings
# helpers, so the file lands under the consumer's own root - and does it during
# the run, so the embed step's `since=` filter accepts it.
CONSUMER_TEST = """import pytest

from pwpf.config.settings import ensure_dir, screenshot_dir


@pytest.mark.smoke
def test_leaves_a_screenshot_behind():
    shot = ensure_dir(screenshot_dir() / "demo_app") / "test_leaves_a_screenshot_behind.png"
    shot.write_bytes(b"not a real png, but a real file")
    assert shot.is_file()
"""


def _consumer(tmp_path: Path) -> Path:
    root = tmp_path / "consumer"
    (root / "tests" / "demo_app").mkdir(parents=True)
    (root / PROJECT_MARKER).write_text(CONSUMER_PYTEST_INI, encoding="utf-8")
    (root / "conftest.py").write_text(CONSUMER_CONFTEST, encoding="utf-8")
    (root / "tests" / "demo_app" / "test_demo.py").write_text(CONSUMER_TEST, encoding="utf-8")
    return root


def test_a_run_from_a_subdirectory_embeds_into_the_report_pytest_html_wrote(tmp_path):
    """The whole chain, in one subprocess: pytest started from `tests/`, the
    report written where this consumer asked for it, the screenshot written
    under the project root, and the embed step finding both."""
    pytest.importorskip("pytest_html", reason="pytest-html is not installed")
    root = _consumer(tmp_path)

    env = {k: v for k, v in os.environ.items() if k not in {ROOT_ENV_VAR, "ENVIRONMENT"}}
    env["PYTHONPATH"] = str(FRAMEWORK_ROOT)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
        cwd=root / "tests",
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    report = root / "tests" / "artifacts" / "run-report.html"
    assert report.is_file(), f"pytest-html wrote no report at {report}\n{result.stdout}"
    assert "Failure Screenshot" in report.read_text(encoding="utf-8"), (
        "the screenshot under the project root was not embedded into the report this "
        f"consumer asked for\n{result.stdout}"
    )
    assert "Report not found" not in result.stdout + result.stderr
    # Nothing was written to the path the old literal pointed at, in either
    # the invocation directory or the project root.
    assert not (root / "tests" / "reports").exists()
    assert not (root / "reports").exists()
    # The screenshot itself stays anchored to the project root, as before.
    assert (root / "screenshots" / "demo_app").is_dir()
