"""Clearing stale Allure results, and choosing which directory to clear.

Two layers, tested separately. `clean_allure_results()` empties the directory it
is handed - allure-pytest never clears its own output, so without this every run
adds another UUID-named result to the same folder forever. The plugin decides
*which* directory that is, and that decision is the part that was wrong:
allure-pytest resolves `--alluredir` with `os.path.abspath`
(`allure_pytest/plugin.py`), i.e. against the directory pytest was invoked from,
while the plugin cleaned `allure_results_dir()` under the project root. Run from
a subdirectory, the two were different folders: the results that were written
accumulated, and a previous run's results elsewhere were deleted instead.

The subprocess tests here are the reproduction, made permanent. They establish
real pytest and allure-pytest behaviour rather than asserting against a mock of
it, in temporary projects, with no network and no browser.
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
from pwpf.config.settings import allure_results_dir
from pwpf.plugin import _allure_results_dir
from pwpf.utils.allure_cleanup import clean_allure_results

FRAMEWORK_ROOT = project_root()
FRAMEWORK_PACKAGE = FRAMEWORK_ROOT / "pwpf"


# --------------------------------------------------------------------------- #
# The cleanup itself
# --------------------------------------------------------------------------- #


def test_clean_allure_results_removes_stale_files(tmp_path):
    results_dir = tmp_path / "allure-results"
    results_dir.mkdir()
    (results_dir / "stale-result.json").write_text("{}", encoding="utf-8")
    stale_attachment_dir = results_dir / "stale-attachment-dir"
    stale_attachment_dir.mkdir()
    (stale_attachment_dir / "stale.txt").write_text("stale", encoding="utf-8")

    removed = clean_allure_results(results_dir)

    assert removed == 2
    assert list(results_dir.iterdir()) == []


def test_clean_allure_results_is_a_noop_when_directory_is_absent(tmp_path):
    missing_dir = tmp_path / "does-not-exist"

    removed = clean_allure_results(missing_dir)

    assert removed == 0
    assert not missing_dir.exists()


def test_clean_allure_results_touches_nothing_outside_the_directory_it_is_given(tmp_path):
    results_dir = tmp_path / "allure-results"
    results_dir.mkdir()
    (results_dir / "stale-result.json").write_text("{}", encoding="utf-8")
    sibling = tmp_path / "allure-results-from-another-run"
    sibling.mkdir()
    (sibling / "keep-result.json").write_text("{}", encoding="utf-8")
    loose_file = tmp_path / "keep.txt"
    loose_file.write_text("keep", encoding="utf-8")

    removed = clean_allure_results(results_dir)

    assert removed == 1
    assert list(results_dir.iterdir()) == []
    assert (sibling / "keep-result.json").is_file()
    assert loose_file.is_file()


# --------------------------------------------------------------------------- #
# Which directory the plugin cleans
# --------------------------------------------------------------------------- #


@pytest.fixture(autouse=True)
def _restore_pinned_roots():
    """Root pinning is process-global; put it back so one test cannot relocate
    every later one."""
    caller, session = paths._caller_root, paths._pytest_root
    yield
    paths._caller_root, paths._pytest_root = caller, session


def _config(alluredir: str | None, invocation_dir: Path) -> pytest.Config:
    """The two things the resolution reads off a real pytest Config. The option's
    dest is allure-pytest's own: `--alluredir` stores to `allure_report_dir`."""
    return cast(
        pytest.Config,
        SimpleNamespace(
            getoption=lambda name, default=None: (
                alluredir if name == "allure_report_dir" else default
            ),
            invocation_params=SimpleNamespace(dir=invocation_dir),
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
    """The regression: allure-pytest writes beside the invocation directory, so
    that is the directory to clear - not the project root's."""
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
# End to end: real pytest, real allure-pytest
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


def _stale(directory: Path, name: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    stale = directory / name
    stale.write_text('{"stale": true}', encoding="utf-8")
    return stale


def _run_from(directory: Path, *, decoy_root: Path | None = None) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k not in {ROOT_ENV_VAR, "ENVIRONMENT"}}
    env["PYTHONPATH"] = str(FRAMEWORK_ROOT)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
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


def test_a_run_from_a_subdirectory_clears_the_results_it_actually_writes(tmp_path):
    """The reproduction, made permanent. Fails against the old implementation,
    which cleared the project root's directory while allure-pytest wrote to the
    invocation directory's."""
    pytest.importorskip("allure_pytest", reason="allure-pytest is not installed")
    root = _consumer(tmp_path, "--alluredir=reports/allure-results")
    written_dir = root / "tests" / "reports" / "allure-results"
    project_root_dir = root / "reports" / "allure-results"
    stale_in_written = _stale(written_dir, "stale-subdir-result.json")
    stale_at_root = _stale(project_root_dir, "stale-root-result.json")
    decoy_root = tmp_path / "decoy"
    stale_in_decoy = _stale(decoy_root / "reports" / "allure-results", "decoy-result.json")

    result = _run_from(root / "tests", decoy_root=decoy_root)

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


def test_a_run_without_alluredir_clears_nothing(tmp_path):
    """The one behaviour this fix changes: with no `--alluredir`, allure-pytest
    writes nothing, so a previous run's results are left where they are instead
    of being deleted by a cleanup that has no output directory to clean."""
    root = _consumer(tmp_path, "-ra")
    stale = _stale(root / "reports" / "allure-results", "previous-run-result.json")

    result = _run_from(root / "tests")

    assert result.returncode == 0, result.stdout + result.stderr
    assert stale.is_file(), "results were deleted for a run that writes none"
