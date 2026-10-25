"""Prove the framework works as an *installed distribution*, not a source tree.

Every earlier consumer test put this repository on PYTHONPATH and changed the
working directory. That exercises path resolution but proves nothing about
packaging: it cannot tell you whether the wheel contains the right modules,
whether pytest discovers the plugin through its entry point, or whether the
scenario schema survives installation.

So this builds a wheel, reads its archive manifest, installs it into a
throwaway virtual environment, creates a separate consumer project, and runs
everything from there with the framework source tree nowhere on the path. The
manifest checks are deliberately about the artifact rather than the
configuration that produced it: `include = ["pwpf*"]` *should* leave `apps/`
and `tests/` out of the wheel, but only the zip itself says whether it did.

    python scripts/verify_installed_package.py [--keep]

Exit status is 0 when every check passes and 1 otherwise; each check prints its
own line. No network beyond the wheel build, and no third-party website: the
consumer's test drives nothing but the framework itself.

The environment is a clean `python -m venv` with nothing inherited, and the
wheel is installed with its declared dependencies plus the `ai` extra - so this
also checks that the dependency metadata is sufficient to run the plugin and the
catalog CLI. Playwright's browser binaries are not installed: the consumer's test
deliberately needs no browser, which keeps the check fast and independent of any
site.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

CONSUMER_PYTEST_INI = """[pytest]
testpaths = tests
addopts = -ra --strict-markers
"""

CONSUMER_APP_CONFIG = """{
  "base_url": "https://consumer.test",
  "action_timeout": 4321
}
"""

CONSUMER_APP_CONFTEST = """import pytest

from pwpf.core.app_config import load_app_config


@pytest.fixture(scope="session")
def app_config():
    return load_app_config("demo_app")
"""

CONSUMER_TEST = '''import pytest

from pwpf.config.settings import log_dir, screenshot_dir


@pytest.mark.smoke
@pytest.mark.ui
@pytest.mark.scenario("DEMO-APP-001")
def test_the_installed_framework_serves_this_consumer(app_config):
    """Markers come from the plugin's entry point: this consumer's pytest.ini
    registers none, and --strict-markers would reject them otherwise."""
    assert app_config.base_url == "https://consumer.test"
    assert app_config.action_timeout == 4321

    root = log_dir().parent
    assert root.name == "consumer", f"artifacts resolved outside the consumer: {root}"
    assert screenshot_dir() == root / "screenshots"
'''

CONSUMER_CATALOG = """schema_version: "1.0"

meta:
  app: demo_app
  feature: demo_feature
  brief: null
  owner: "consumer team"
  updated: "2026-10-25"
  id_scheme: "DEMO-<AREA>-<NNN>"

scenarios:
  - id: DEMO-APP-001
    title: The installed framework serves this consumer project
    feature: demo_feature
    priority: P2
    risk: low
    status: NEEDS_HUMAN_REVIEW
    requirement: "FB-DEMO-01"
    preconditions:
      - The framework is installed from a wheel
    test_data:
      source: no test data required
    steps:
      - Run the consumer's own test suite
    expected_results:
      - The plugin's markers and fixtures are available without a conftest.py
    environment:
      target: local-fixture
      side_effects: none
      side_effects_note: null
      authorization_required: false
      ci_eligible: true
    automation:
      test: tests/demo_app/test_demo.py::test_the_installed_framework_serves_this_consumer
      markers: [smoke, ui]
      implemented: true
    evidence:
      locators: null
      exploration: null
    review:
      approved_by: null
      approved_date: null
      status_history:
        - status: NEEDS_HUMAN_REVIEW
          by: "consumer team"
          date: "2026-10-25"
"""

results: list[tuple[bool, str]] = []


def check(ok: bool, description: str, detail: str = "") -> bool:
    results.append((ok, description))
    print(f"  [{'PASS' if ok else 'FAIL'}] {description}")
    if detail and not ok:
        for line in detail.strip().splitlines()[:20]:
            print(f"         {line}")
    return ok


# Every subprocess is bounded: a hung pip or pytest should fail this check, not
# wedge it. Generous enough that a cold pip cache still fits.
INSTALL_TIMEOUT = 600
CONSUMER_TIMEOUT = 300


def run(
    argv: list[str], cwd: Path, env: dict[str, str], timeout: int = CONSUMER_TIMEOUT
) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            argv, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout
        )
    except subprocess.TimeoutExpired as expired:
        return subprocess.CompletedProcess(
            argv,
            returncode=124,
            stdout=expired.stdout or "",
            stderr=f"timed out after {timeout}s: {' '.join(str(a) for a in argv)}",
        )


def build_wheel(workdir: Path) -> Path:
    wheel_dir = workdir / "wheel"
    # What the source tree already had, so the cleanup below removes only what
    # this build adds and never a developer's pre-existing build output.
    pre_existing = {p for p in (REPO_ROOT / "build", *REPO_ROOT.glob("*.egg-info")) if p.exists()}
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--wheel-dir",
            str(wheel_dir),
            str(REPO_ROOT),
        ],
        capture_output=True,
        text=True,
        timeout=INSTALL_TIMEOUT,
    )
    if proc.returncode != 0:
        raise SystemExit(f"wheel build failed:\n{proc.stdout}\n{proc.stderr}")
    wheels = sorted(wheel_dir.glob("*.whl"))
    if not wheels:
        raise SystemExit("wheel build produced no .whl")
    # setuptools leaves build/ and *.egg-info in the source tree; they are
    # git-ignored but mypy and a reader would both trip over them. Only what
    # this build created is removed - anything that was already there stays.
    for leftover in (REPO_ROOT / "build", *REPO_ROOT.glob("*.egg-info")):
        if leftover.exists() and leftover not in pre_existing:
            shutil.rmtree(leftover, ignore_errors=True)
    return wheels[0]


# Artifact directories and repository-only trees that must never be shipped.
# `pwpf/ai_testing/` (the validator and its schema) is part of the framework;
# the top-level `ai_testing/` prompt library is documentation and is not.
FORBIDDEN_WHEEL_PATHS = (
    "apps/",
    "tests/",
    "docs/",
    "ai_testing/",
    "scripts/",
    "screenshots/",
    "reports/",
    "logs/",
    "traces/",
    "videos/",
    "conftest.py",
    "pytest.ini",
)


def declared_project_metadata() -> dict[str, str]:
    """Name, version, Python requirement and license, read from pyproject.toml so
    these checks follow a version bump instead of having to be edited after one."""
    with (REPO_ROOT / "pyproject.toml").open("rb") as handle:
        project = tomllib.load(handle)["project"]
    return {
        "Name": project["name"],
        "Version": project["version"],
        "Requires-Python": project["requires-python"],
        "License-Expression": project["license"],
    }


def source_package_members() -> set[str]:
    """Every module and data file the wheel is expected to carry, taken from the
    source tree rather than from a list that would go stale when a file is added.

    Data files count, not only modules: a new `.json` under `pwpf/` that nobody
    adds to `[tool.setuptools.package-data]` is silently absent from the wheel,
    and a check that only looked for `*.py` plus one known schema would still
    pass. Build output and editor droppings are not source, so bytecode,
    `__pycache__` and dotfiles are excluded.
    """
    return {
        path.relative_to(REPO_ROOT).as_posix()
        for path in (REPO_ROOT / "pwpf").rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix != ".pyc"
        and not path.name.startswith(".")
    }


def check_wheel_contents(wheel: Path) -> None:
    """Assert what the built wheel actually contains, from its own manifest.

    The source of truth here is the zip, not the packaging configuration: a
    `include`/`package-data` entry that silently stopped matching looks exactly
    like a correct one until something reads the archive. Nothing below depends
    on the wheel's filename or on the exact name of its .dist-info directory,
    so a version bump or a metadata revision does not break these checks.
    """
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        metadata_files = sorted(n for n in names if n.endswith(".dist-info/METADATA"))
        if not check(
            len(metadata_files) == 1,
            "the wheel carries exactly one .dist-info/METADATA",
            f"found: {metadata_files}",
        ):
            return
        dist_info = metadata_files[0][: -len("METADATA")]

        missing = sorted(source_package_members() - names)
        check(
            not missing,
            "every pwpf module in the source tree is in the wheel",
            "missing: " + ", ".join(missing),
        )
        check(
            "pwpf/ai_testing/schemas/scenario.schema.json" in names,
            "the scenario schema is in the wheel as package data",
            "\n".join(sorted(n for n in names if "schema" in n)),
        )

        metadata = archive.read(dist_info + "METADATA").decode("utf-8")
        declared = declared_project_metadata()
        core = {k: v for k, v in declared.items() if k != "License-Expression"}
        missing_fields = [f"{k}: {v}" for k, v in core.items() if f"{k}: {v}" not in metadata]
        check(
            not missing_fields,
            "the wheel's METADATA matches the declared name, version and Python requirement",
            "missing: " + ", ".join(missing_fields),
        )
        expression = declared["License-Expression"]
        check(
            f"License-Expression: {expression}" in metadata,
            "METADATA declares the license as an SPDX expression: " + expression,
            "\n".join(line for line in metadata.splitlines() if "icense" in line),
        )

        license_members = sorted(
            n
            for n in names
            if n.startswith(dist_info) and "LICENSE" in n.rsplit("/", 1)[-1].upper()
        )
        license_text = "".join(archive.read(n).decode("utf-8") for n in license_members)
        check(
            bool(license_members) and "MIT License" in license_text,
            "the MIT license file itself is in the wheel",
            f"license members: {license_members}",
        )
        check(
            license_text.strip() == (REPO_ROOT / "LICENSE").read_text(encoding="utf-8").strip(),
            "the shipped license is this repository's LICENSE, unaltered",
            f"license members: {license_members}",
        )

        entry_points_path = dist_info + "entry_points.txt"
        entry_points = (
            archive.read(entry_points_path).decode("utf-8") if entry_points_path in names else ""
        )
        # Whitespace-insensitive: setuptools writes `name = target`, but the
        # format allows `name=target`, and that difference is not a defect.
        compact = "".join(entry_points.split())
        check(
            "[pytest11]" in compact and "pwpf.plugin=pwpf.plugin" in compact,
            "the pytest11 entry point is recorded in the wheel's metadata",
            entry_points or f"no {entry_points_path} in the wheel",
        )
        check(
            "pwpf-validate-catalog=pwpf.ai_testing.validate_catalog:main" in compact,
            "the catalog console script is recorded in the wheel's metadata",
            entry_points,
        )

        # One rule, stated two ways: nothing outside pwpf/ and the .dist-info
        # belongs in the wheel, and these specific trees least of all.
        strays = sorted(
            n for n in names if not n.startswith("pwpf/") and not n.startswith(dist_info)
        )
        check(
            not strays,
            "the wheel contains nothing beyond the pwpf package and its metadata",
            "unexpected: " + ", ".join(strays),
        )
        leaked = sorted(
            n for n in names for bad in FORBIDDEN_WHEEL_PATHS if n == bad or n.startswith(bad)
        )
        check(
            not leaked,
            "application code, tests, docs, the prompt library and artifacts are excluded",
            "leaked: " + ", ".join(leaked),
        )
        check(
            not [n for n in names if n.endswith(".pyc") or "__pycache__" in n],
            "no compiled bytecode is shipped in the wheel",
            "\n".join(sorted(n for n in names if n.endswith(".pyc"))),
        )


def make_venv(workdir: Path, wheel: Path) -> Path:
    venv_dir = workdir / "venv"
    # A clean environment: nothing from the surrounding interpreter is visible,
    # so the only way the consumer can import pwpf is the wheel, and the only
    # way it gets pytest is the distribution's own dependency metadata.
    subprocess.run(
        [sys.executable, "-m", "venv", str(venv_dir)], check=True, timeout=INSTALL_TIMEOUT
    )
    python = venv_dir / "bin" / "python"
    proc = subprocess.run(
        [str(python), "-m", "pip", "install", "--quiet", f"{wheel}[ai]"],
        capture_output=True,
        text=True,
        timeout=INSTALL_TIMEOUT,
    )
    if proc.returncode != 0:
        raise SystemExit(f"wheel install failed:\n{proc.stdout}\n{proc.stderr}")
    return venv_dir


def make_consumer(workdir: Path) -> Path:
    consumer = workdir / "consumer"
    (consumer / "apps" / "demo_app" / "config").mkdir(parents=True)
    (consumer / "apps" / "demo_app" / "scenarios").mkdir(parents=True)
    (consumer / "tests" / "demo_app").mkdir(parents=True)
    (consumer / "pytest.ini").write_text(CONSUMER_PYTEST_INI, encoding="utf-8")
    (consumer / "apps" / "demo_app" / "config" / "local.json").write_text(
        CONSUMER_APP_CONFIG, encoding="utf-8"
    )
    (consumer / "apps" / "demo_app" / "scenarios" / "demo_feature.yaml").write_text(
        CONSUMER_CATALOG, encoding="utf-8"
    )
    (consumer / "tests" / "demo_app" / "conftest.py").write_text(
        CONSUMER_APP_CONFTEST, encoding="utf-8"
    )
    (consumer / "tests" / "demo_app" / "test_demo.py").write_text(CONSUMER_TEST, encoding="utf-8")
    return consumer


def artifact_dirs(root: Path) -> set[str]:
    return {
        d for d in ("screenshots", "reports", "logs", "traces", "videos") if (root / d).is_dir()
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep", action="store_true", help="keep the temporary workspace")
    args = parser.parse_args(argv)

    workdir = Path(tempfile.mkdtemp(prefix="pwpf-install-check-"))
    print(f"workspace: {workdir}")
    try:
        wheel = build_wheel(workdir)
        print(f"built:     {wheel.name}")
        venv_dir = make_venv(workdir, wheel)
        python = venv_dir / "bin" / "python"
        consumer = make_consumer(workdir)
        site_packages = next((venv_dir / "lib").glob("python*/site-packages"))
        installed_pwpf = site_packages / "pwpf"

        env = {
            k: v
            for k, v in os.environ.items()
            if k not in {"PYTHONPATH", "PWPF_ROOT", "ENVIRONMENT"}
        }
        env["PYTHONDONTWRITEBYTECODE"] = "1"

        print("\nchecks:")

        # 0. The wheel itself, before anything is installed from it.
        check_wheel_contents(wheel)

        # 1. The framework really is imported from the installed distribution.
        proc = run([str(python), "-c", "import pwpf; print(pwpf.__file__)"], consumer, env)
        imported_from = proc.stdout.strip()
        check(
            proc.returncode == 0 and imported_from.startswith(str(site_packages)),
            "pwpf is imported from the installed wheel, not the source tree",
            f"{imported_from}\n{proc.stderr}",
        )
        check(
            str(REPO_ROOT) not in imported_from,
            "the framework source tree is not on the consumer's import path",
            imported_from,
        )

        # 2. The schema survives installation and is readable as package data.
        proc = run(
            [
                str(python),
                "-c",
                "import json;"
                "from pwpf.ai_testing.validate_catalog import schema_text;"
                "print(json.loads(schema_text())['title'])",
            ],
            consumer,
            env,
        )
        check(
            proc.returncode == 0 and "schema version 1.0" in proc.stdout,
            "the scenario schema is available from the installed distribution",
            proc.stdout + proc.stderr,
        )

        # 3. pytest discovers the plugin through its entry point.
        proc = run([str(python), "-m", "pytest", "--co", "-q", "-m", "smoke"], consumer, env)
        check(
            proc.returncode == 0 and "1 test" in proc.stdout,
            "pytest collects the consumer's test with the plugin's markers (--strict-markers)",
            proc.stdout + proc.stderr,
        )
        proc = run([str(python), "-m", "pytest", "--fixtures", "-q"], consumer, env)
        check(
            all(name in proc.stdout for name in ("browser_context_args", "playwright_context")),
            "the plugin's fixtures are registered without any consumer conftest.py",
            proc.stdout[-400:] + proc.stderr,
        )

        # 4. A real run: application discovery and artifact locations.
        before_package = artifact_dirs(installed_pwpf) | artifact_dirs(site_packages)
        proc = run([str(python), "-m", "pytest", "-q"], consumer, env)
        check(
            proc.returncode == 0 and "1 passed" in proc.stdout,
            "the consumer's suite passes, resolving its own application config",
            proc.stdout + proc.stderr,
        )
        logs = sorted((consumer / "logs").rglob("framework.log"))
        check(bool(logs), "framework artifacts are written under the consumer root", str(consumer))
        check(
            artifact_dirs(installed_pwpf) | artifact_dirs(site_packages) == before_package,
            "no artifacts are written into the installed package directory",
            str(sorted(artifact_dirs(installed_pwpf) | artifact_dirs(site_packages))),
        )
        check(
            artifact_dirs(REPO_ROOT / "pwpf") == set(),
            "no artifacts are written into the framework source package either",
        )

        # 5. The console script validates the consumer's own catalog.
        cli = venv_dir / "bin" / "pwpf-validate-catalog"
        check(cli.is_file(), "the catalog console script is installed", str(cli))
        proc = run([str(cli)], consumer, env)
        check(
            proc.returncode == 0 and f"1 file(s) checked under {consumer.resolve()}" in proc.stdout,
            "the installed CLI validates the consumer's catalog, not the framework's",
            proc.stdout + proc.stderr,
        )
        proc = run([str(python), "-m", "pwpf.ai_testing.validate_catalog"], consumer, env)
        check(
            proc.returncode == 0 and "1 file(s) checked" in proc.stdout,
            "python -m pwpf.ai_testing.validate_catalog works from the consumer too",
            proc.stdout + proc.stderr,
        )

        failed = [description for ok, description in results if not ok]
        print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
        if failed:
            for description in failed:
                print(f"  failed: {description}")
            return 1
        return 0
    finally:
        if args.keep:
            print(f"\nkept workspace: {workdir}")
        else:
            shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
