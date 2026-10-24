"""The consumer-project root, and the paths derived from it.

The framework must work when it is *not* at the root of the project using it:
artifacts belong to the consumer repository, `apps/` is the consumer's, and
importing a module must not create anything anywhere. These tests pin that
contract, including the precedence between the four ways a root can be decided
and the errors raised when none of them applies.

Everything here is deterministic: temporary directories, and subprocesses that
import the framework from this checkout with a different working directory. No
network, no browser.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from config import paths, settings
from config.paths import (
    PROJECT_MARKER,
    ROOT_ENV_VAR,
    ProjectRootError,
    find_project_root,
    project_root,
    set_project_root,
)

FRAMEWORK_ROOT = project_root()


@pytest.fixture(autouse=True)
def _restore_pinned_roots(monkeypatch):
    """Root pinning is process-global. Snapshot it, let a test move it, put it
    back - otherwise one test would quietly relocate every later one."""
    caller, session = paths._caller_root, paths._pytest_root
    monkeypatch.delenv(ROOT_ENV_VAR, raising=False)
    yield
    paths._caller_root, paths._pytest_root = caller, session


def _consumer(tmp_path: Path, name: str = "consumer", *, marker: bool = True) -> Path:
    """A minimal consumer project: a marker file, one application, one test."""
    root = tmp_path / name
    (root / "apps" / "demo_app" / "config").mkdir(parents=True)
    (root / "tests" / "demo_app").mkdir(parents=True)
    if marker:
        (root / PROJECT_MARKER).write_text("[pytest]\ntestpaths = tests\n", encoding="utf-8")
    (root / "apps" / "demo_app" / "config" / "local.json").write_text(
        '{"base_url": "https://consumer.test", "action_timeout": 1234}\n', encoding="utf-8"
    )
    return root


# --------------------------------------------------------------------------- #
# Root resolution
# --------------------------------------------------------------------------- #


def test_the_marker_in_the_current_directory_is_the_root(tmp_path, monkeypatch):
    root = _consumer(tmp_path)
    paths.clear_project_root()
    monkeypatch.chdir(root)

    assert project_root() == root.resolve()


def test_the_marker_in_an_ancestor_directory_is_found(tmp_path, monkeypatch):
    root = _consumer(tmp_path)
    nested = root / "tests" / "demo_app"
    paths.clear_project_root()
    monkeypatch.chdir(nested)

    assert project_root() == root.resolve()


def test_the_nearest_marker_wins_when_projects_are_nested(tmp_path, monkeypatch):
    outer = _consumer(tmp_path, "outer")
    inner = _consumer(outer / "vendor", "inner")
    paths.clear_project_root()
    monkeypatch.chdir(inner / "tests")

    assert project_root() == inner.resolve()


def test_the_environment_override_is_used_when_nothing_is_pinned(tmp_path, monkeypatch):
    root = _consumer(tmp_path)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    paths.clear_project_root()
    monkeypatch.chdir(elsewhere)
    monkeypatch.setenv(ROOT_ENV_VAR, str(root))

    assert project_root() == root.resolve()


def test_an_environment_override_that_does_not_exist_is_rejected(tmp_path, monkeypatch):
    paths.clear_project_root()
    monkeypatch.setenv(ROOT_ENV_VAR, str(tmp_path / "nowhere"))

    with pytest.raises(ProjectRootError) as excinfo:
        project_root()

    assert ROOT_ENV_VAR in str(excinfo.value)
    assert "does not exist" in str(excinfo.value)


def test_an_environment_override_without_the_marker_is_rejected(tmp_path, monkeypatch):
    """A blind override is validated: pointing it at a random directory would put
    artifacts somewhere surprising and look for apps/ where there are none."""
    unmarked = _consumer(tmp_path, marker=False)
    paths.clear_project_root()
    monkeypatch.setenv(ROOT_ENV_VAR, str(unmarked))

    with pytest.raises(ProjectRootError) as excinfo:
        project_root()

    assert PROJECT_MARKER in str(excinfo.value)


def test_no_resolvable_root_fails_with_an_actionable_message(tmp_path, monkeypatch):
    """And never silently falls back to the framework's own directory."""
    empty = tmp_path / "no-project"
    empty.mkdir()
    paths.clear_project_root()
    monkeypatch.chdir(empty)
    monkeypatch.setattr(paths, "find_project_root", lambda start=None: None)

    with pytest.raises(ProjectRootError) as excinfo:
        project_root()

    message = str(excinfo.value)
    assert ROOT_ENV_VAR in message
    assert "--root" in message
    assert str(FRAMEWORK_ROOT) not in message


def test_an_explicit_caller_root_outranks_everything_else(tmp_path, monkeypatch):
    explicit = _consumer(tmp_path, "explicit")
    other = _consumer(tmp_path, "other")
    cwd_project = _consumer(tmp_path, "cwd_project")
    monkeypatch.chdir(cwd_project)
    monkeypatch.setenv(ROOT_ENV_VAR, str(other))
    set_project_root(other, source="pytest")

    set_project_root(explicit, source="--root")

    assert project_root() == explicit.resolve()


def test_the_pytest_rootdir_outranks_the_environment_and_the_cwd(tmp_path, monkeypatch):
    session = _consumer(tmp_path, "session")
    other = _consumer(tmp_path, "other")
    cwd_project = _consumer(tmp_path, "cwd_project")
    paths.clear_project_root()
    monkeypatch.chdir(cwd_project)
    monkeypatch.setenv(ROOT_ENV_VAR, str(other))
    set_project_root(session, source="pytest")

    assert project_root() == session.resolve()


def test_this_session_resolves_to_pytests_own_rootpath(pytestconfig):
    """The live integration: inside a pytest run the root is whatever pytest
    decided, pinned by the root conftest's pytest_configure."""
    assert project_root() == Path(pytestconfig.rootpath).resolve()


def test_find_project_root_returns_none_when_there_is_no_marker(tmp_path):
    unmarked = tmp_path / "plain"
    unmarked.mkdir()

    assert find_project_root(unmarked) is None


# --------------------------------------------------------------------------- #
# Filesystem behaviour
# --------------------------------------------------------------------------- #


def test_artifact_directories_hang_off_the_resolved_root(tmp_path):
    root = _consumer(tmp_path)
    set_project_root(root, source="caller")

    assert settings.screenshot_dir() == root.resolve() / "screenshots"
    assert settings.report_dir() == root.resolve() / "reports"
    assert settings.log_dir() == root.resolve() / "logs"
    assert settings.trace_dir() == root.resolve() / "traces"
    assert settings.video_dir() == root.resolve() / "videos"
    assert settings.allure_results_dir() == root.resolve() / "reports" / "allure-results"


def test_asking_for_an_artifact_path_does_not_create_it(tmp_path):
    root = _consumer(tmp_path)
    set_project_root(root, source="caller")

    for accessor in (
        settings.screenshot_dir,
        settings.report_dir,
        settings.log_dir,
        settings.trace_dir,
        settings.video_dir,
    ):
        assert not accessor().exists(), f"{accessor.__name__}() created its directory"


def test_ensure_dir_creates_it_when_something_needs_it(tmp_path):
    root = _consumer(tmp_path)
    set_project_root(root, source="caller")

    created = settings.ensure_dir(settings.trace_dir() / "demo_app")

    assert created.is_dir()
    assert created == root.resolve() / "traces" / "demo_app"


def test_a_logger_built_before_the_root_is_pinned_writes_under_the_final_root(tmp_path):
    """The root conftest imports utils.logger before pytest_configure can pin
    pytest's rootdir, so a handler that resolved its directory at construction
    time would log to one root while every other artifact went to another. The
    file handler resolves on its first record instead."""
    from utils.logger import get_logger

    early = _consumer(tmp_path, "early")
    final = _consumer(tmp_path, "final")

    set_project_root(early, source="caller")
    logger = get_logger("tests.test_project_root.late_binding_case")
    set_project_root(final, source="caller")
    logger.info("written after the root moved")

    # Which worker subdirectory it lands in is not this test's business - and
    # cannot be assumed, since tests/test_logger.py reloads utils.logger with a
    # different PYTEST_XDIST_WORKER and leaves that module constant changed for
    # the rest of the session. What matters is the *root*.
    written = list((final.resolve() / "logs").rglob("framework.log"))
    assert written, f"nothing was logged under {final / 'logs'}"
    assert not (early.resolve() / "logs").exists()


def test_application_discovery_uses_the_resolved_root(tmp_path):
    from core.app_config import apps_dir

    root = _consumer(tmp_path)
    set_project_root(root, source="caller")

    assert apps_dir() == root.resolve() / "apps"


# --------------------------------------------------------------------------- #
# A separate consumer project, driven in subprocesses
# --------------------------------------------------------------------------- #


def _run(code_or_args: list[str], cwd: Path, **env_overrides) -> subprocess.CompletedProcess:
    # The consumer subprocess inherits neither the parent run's project root nor
    # its environment selection: on CI the workflow exports ENVIRONMENT=ci, which
    # would silently make a consumer look for apps/<app>/config/ci.json while the
    # fixture below writes local.json. A test must decide both for itself.
    inherited = {ROOT_ENV_VAR, "ENVIRONMENT"}
    env = {k: v for k, v in os.environ.items() if k not in inherited}
    env["PYTHONPATH"] = str(FRAMEWORK_ROOT)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.update(env_overrides)
    return subprocess.run(
        [sys.executable, *code_or_args], cwd=cwd, env=env, capture_output=True, text=True
    )


def _artifact_dirs(root: Path) -> set[str]:
    return {
        d for d in ("screenshots", "reports", "logs", "traces", "videos") if (root / d).is_dir()
    }


def test_importing_the_framework_from_a_consumer_creates_nothing_anywhere(tmp_path):
    """The acceptance criterion: no artifact directory appears in the consumer
    project *or* inside the framework's own tree merely because a module was
    imported."""
    root = _consumer(tmp_path)
    before = _artifact_dirs(FRAMEWORK_ROOT)

    result = _run(
        ["-c", "import config.settings, core.app_config, utils.logger; print('ok')"], root
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ok"
    assert _artifact_dirs(root) == set(), "importing created artifact directories in the consumer"
    assert (
        _artifact_dirs(FRAMEWORK_ROOT) == before
    ), "importing created directories in the framework"


def test_a_consumer_resolves_its_own_application_config(tmp_path):
    root = _consumer(tmp_path)

    result = _run(
        [
            "-c",
            "from core.app_config import load_app_config;"
            "c = load_app_config('demo_app');"
            "print(c.base_url, c.action_timeout)",
        ],
        root,
        # Stated rather than inherited: _consumer writes local.json, so this is
        # the environment whose file it should find.
        ENVIRONMENT="local",
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "https://consumer.test 1234"


def test_the_catalog_cli_validates_the_consumer_not_the_framework(tmp_path):
    pytest.importorskip("yaml", reason="requirements-ai.txt is not installed")
    pytest.importorskip("jsonschema", reason="requirements-ai.txt is not installed")
    root = _consumer(tmp_path)

    result = _run(["-m", "ai_testing.validate_catalog"], root)

    assert result.returncode == 0, result.stdout + result.stderr
    # The consumer has no catalogs of its own, and the framework's own Myntra
    # catalog must not be dragged in by the module's location.
    assert f"0 file(s) checked under {root.resolve()}" in result.stdout
    assert "myntra" not in result.stdout


def test_the_catalog_cli_honours_an_explicit_root(tmp_path):
    pytest.importorskip("yaml", reason="requirements-ai.txt is not installed")
    pytest.importorskip("jsonschema", reason="requirements-ai.txt is not installed")
    root = _consumer(tmp_path)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()

    result = _run(["-m", "ai_testing.validate_catalog", "--root", str(root)], elsewhere)

    assert result.returncode == 0, result.stdout + result.stderr
    assert f"checked under {root.resolve()}" in result.stdout


def test_the_catalog_cli_reports_an_unresolvable_root_instead_of_guessing(tmp_path):
    pytest.importorskip("yaml", reason="requirements-ai.txt is not installed")
    nowhere = tmp_path / "no-project"
    nowhere.mkdir()

    result = _run(["-m", "ai_testing.validate_catalog"], nowhere)

    assert result.returncode == 2, result.stdout + result.stderr
    assert ROOT_ENV_VAR in result.stderr
    assert "--root" in result.stderr


def test_the_environment_override_works_for_a_consumer_subprocess(tmp_path):
    root = _consumer(tmp_path)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()

    result = _run(
        ["-c", "from config.settings import log_dir; print(log_dir())"],
        elsewhere,
        **{ROOT_ENV_VAR: str(root)},
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(root.resolve() / "logs")


def test_logging_without_a_resolvable_root_neither_raises_nor_writes(tmp_path):
    """Logging must never be the thing that breaks a run - and it must never
    fall back to writing inside the framework's own directory."""
    nowhere = tmp_path / "no-project"
    nowhere.mkdir()
    before = _artifact_dirs(FRAMEWORK_ROOT)

    result = _run(
        [
            "-c",
            "import utils.logger as L;"
            "log = L.get_logger('probe.no_root');"
            "log.info('hello');"
            "print('ok')",
        ],
        nowhere,
    )

    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout
    assert _artifact_dirs(nowhere) == set()
    assert _artifact_dirs(FRAMEWORK_ROOT) == before
