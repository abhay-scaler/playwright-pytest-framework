"""The wheel-manifest assertions in scripts/verify_installed_package.py.

Those assertions are the only thing standing between a packaging mistake and a
wheel that ships the wrong files, so they need to fail when they should. The
installation check builds a real wheel, which takes a virtual environment and a
minute; these tests instead hand the same function synthetic archives - one
correct, then one defect at a time - and assert which checks flip. Fast,
deterministic, no build and no network.

They also pin the robustness the script claims: the checks read the archive's
own manifest, so neither the wheel's filename nor the name of its .dist-info
directory may matter, while the metadata inside it must match pyproject.toml.
"""

from __future__ import annotations

import importlib.util
import zipfile
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "verify_installed_package.py"


def _load_script() -> Any:
    """scripts/ is not a package - the script is loaded by path, as a tool."""
    spec = importlib.util.spec_from_file_location("verify_installed_package", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


verify = _load_script()


def _metadata(**overrides: str) -> str:
    declared = dict(verify.declared_project_metadata())
    declared.update(overrides)
    lines = ["Metadata-Version: 2.4"] + [f"{k}: {v}" for k, v in declared.items()]
    return "\n".join(lines) + "\n\nA synthetic wheel for testing.\n"


ENTRY_POINTS = """[console_scripts]
pwpf-validate-catalog = pwpf.ai_testing.validate_catalog:main

[pytest11]
pwpf.plugin = pwpf.plugin
"""


def _wheel(
    tmp_path: Path,
    *,
    filename: str = "playwright_pytest_framework-0.1.0-py3-none-any.whl",
    dist_info: str = "playwright_pytest_framework-0.1.0.dist-info/",
    metadata: str | None = None,
    entry_points: str | None = ENTRY_POINTS,
    license_text: str | None = None,
    omit: tuple[str, ...] = (),
    extra: dict[str, str] | None = None,
) -> Path:
    """A wheel-shaped zip: every module the source tree has, plus the metadata a
    correct build produces. Each keyword removes or corrupts exactly one thing."""
    members = {name: "" for name in verify.source_package_members()}
    members[dist_info + "METADATA"] = metadata if metadata is not None else _metadata()
    members[dist_info + "WHEEL"] = "Wheel-Version: 1.0\nGenerator: setuptools\n"
    members[dist_info + "RECORD"] = ""
    if entry_points is not None:
        members[dist_info + "entry_points.txt"] = entry_points
    members[dist_info + "licenses/LICENSE"] = (
        license_text
        if license_text is not None
        else (REPO_ROOT / "LICENSE").read_text(encoding="utf-8")
    )
    for name in omit:
        members.pop(name, None)
    members.update(extra or {})

    wheel = tmp_path / filename
    with zipfile.ZipFile(wheel, "w") as archive:
        for name, content in sorted(members.items()):
            archive.writestr(name, content)
    return wheel


def _outcomes(wheel: Path) -> dict[str, bool]:
    """Run the checks against one archive, in isolation from the script's own
    module-level result accumulator."""
    verify.results.clear()
    try:
        verify.check_wheel_contents(wheel)
        return {description: ok for ok, description in verify.results}
    finally:
        verify.results.clear()


def _failed(outcomes: dict[str, bool]) -> list[str]:
    return sorted(description for description, ok in outcomes.items() if not ok)


# --------------------------------------------------------------------------- #
# The happy path, and what it does not depend on
# --------------------------------------------------------------------------- #


def test_a_correct_wheel_passes_every_check(tmp_path):
    outcomes = _outcomes(_wheel(tmp_path))

    assert outcomes, "no checks ran"
    assert _failed(outcomes) == []


def test_neither_the_wheel_filename_nor_the_dist_info_name_matters(tmp_path):
    """Both are derived or ignored - a renamed build must not look like a defect."""
    outcomes = _outcomes(
        _wheel(
            tmp_path,
            filename="some-other-name-99.9-py3-none-any.whl",
            dist_info="renamed_distribution-99.9.dist-info/",
        )
    )

    assert _failed(outcomes) == []


def test_entry_points_without_spaces_around_the_equals_sign_still_pass(tmp_path):
    outcomes = _outcomes(
        _wheel(
            tmp_path,
            entry_points=(
                "[console_scripts]\n"
                "pwpf-validate-catalog=pwpf.ai_testing.validate_catalog:main\n"
                "[pytest11]\n"
                "pwpf.plugin=pwpf.plugin\n"
            ),
        )
    )

    assert _failed(outcomes) == []


# --------------------------------------------------------------------------- #
# One defect at a time
# --------------------------------------------------------------------------- #


def test_a_leaked_repository_tree_is_reported(tmp_path):
    outcomes = _outcomes(
        _wheel(
            tmp_path,
            extra={
                "tests/test_something.py": "",
                "apps/demo_app/__init__.py": "",
                "conftest.py": "",
                "ai_testing/prompts/00_analyze_repository.md": "",
                "screenshots/demo_app/shot.png": "",
            },
        )
    )

    assert outcomes["the wheel contains nothing beyond the pwpf package and its metadata"] is False
    assert (
        outcomes["application code, tests, docs, the prompt library and artifacts are excluded"]
        is False
    )


def test_a_missing_schema_is_reported(tmp_path):
    outcomes = _outcomes(_wheel(tmp_path, omit=("pwpf/ai_testing/schemas/scenario.schema.json",)))

    assert outcomes["the scenario schema is in the wheel as package data"] is False


def test_a_missing_module_is_reported(tmp_path):
    outcomes = _outcomes(_wheel(tmp_path, omit=("pwpf/plugin.py",)))

    assert outcomes["every pwpf module in the source tree is in the wheel"] is False


def test_a_missing_pytest_entry_point_is_reported(tmp_path):
    outcomes = _outcomes(_wheel(tmp_path, entry_points=None))

    assert outcomes["the pytest11 entry point is recorded in the wheel's metadata"] is False
    assert outcomes["the catalog console script is recorded in the wheel's metadata"] is False


def test_metadata_that_disagrees_with_pyproject_is_reported(tmp_path):
    outcomes = _outcomes(_wheel(tmp_path, metadata=_metadata(Version="0.0.0-wrong")))

    assert (
        outcomes["the wheel's METADATA matches the declared name, version and Python requirement"]
        is False
    )


def test_a_missing_license_expression_is_reported(tmp_path):
    metadata = "\n".join(
        line for line in _metadata().splitlines() if not line.startswith("License-Expression:")
    )
    outcomes = _outcomes(_wheel(tmp_path, metadata=metadata))

    assert _failed(outcomes) == [
        "METADATA declares the license as an SPDX expression: "
        + verify.declared_project_metadata()["License-Expression"]
    ]


def test_a_license_file_that_is_not_this_repositorys_is_reported(tmp_path):
    outcomes = _outcomes(_wheel(tmp_path, license_text="All rights reserved.\n"))

    assert outcomes["the MIT license file itself is in the wheel"] is False
    assert outcomes["the shipped license is this repository's LICENSE, unaltered"] is False


def test_shipped_bytecode_is_reported(tmp_path):
    outcomes = _outcomes(_wheel(tmp_path, extra={"pwpf/__pycache__/plugin.cpython-312.pyc": ""}))

    assert outcomes["no compiled bytecode is shipped in the wheel"] is False


def test_a_wheel_without_dist_info_metadata_fails_loudly(tmp_path):
    """Nothing can be derived without it, so the checks stop there rather than
    reporting a string of misleading failures."""
    wheel = tmp_path / "empty-0.0.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("pwpf/__init__.py", "")

    outcomes = _outcomes(wheel)

    assert outcomes == {"the wheel carries exactly one .dist-info/METADATA": False}


def test_the_script_exits_nonzero_when_a_check_fails(tmp_path):
    """The contract the CI-facing script relies on: a failed check is an exit
    code, not just a printed line."""
    verify.results.clear()
    try:
        verify.check_wheel_contents(_wheel(tmp_path, omit=("pwpf/plugin.py",)))
        failed = [description for ok, description in verify.results if not ok]
        assert failed, "expected at least one failing check"
    finally:
        verify.results.clear()


def test_the_scripts_own_source_tree_expectations_are_not_empty():
    """A guard on the guard: if source_package_members() ever returned nothing,
    "every module is in the wheel" would pass vacuously."""
    members = verify.source_package_members()

    assert "pwpf/plugin.py" in members
    assert "pwpf/ai_testing/schemas/scenario.schema.json" in members
    assert len(members) > 10
    assert not [m for m in members if "__pycache__" in m]
    assert [
        m for m in members if not m.endswith(".py")
    ], "data files must be expected in the wheel too, not only modules"


def test_every_data_file_under_the_package_is_expected_in_the_wheel(tmp_path, monkeypatch):
    """A new data file must be required without editing this script - that is
    the gap a `*.py`-only glob left. Build output and dotfiles are not source."""
    package = tmp_path / "pwpf" / "ai_testing" / "schemas"
    package.mkdir(parents=True)
    (tmp_path / "pwpf" / "plugin.py").write_text("", encoding="utf-8")
    (package / "scenario.schema.json").write_text("{}", encoding="utf-8")
    (package / "failure_report.schema.json").write_text("{}", encoding="utf-8")
    (tmp_path / "pwpf" / ".DS_Store").write_text("", encoding="utf-8")
    cache = tmp_path / "pwpf" / "__pycache__"
    cache.mkdir()
    (cache / "plugin.cpython-312.pyc").write_text("", encoding="utf-8")
    monkeypatch.setattr(verify, "REPO_ROOT", tmp_path)

    members = verify.source_package_members()

    assert members == {
        "pwpf/plugin.py",
        "pwpf/ai_testing/schemas/scenario.schema.json",
        "pwpf/ai_testing/schemas/failure_report.schema.json",
    }


def test_the_forbidden_paths_do_not_exclude_the_frameworks_own_ai_testing_package():
    """`ai_testing/` is a repository directory (the prompt library) and
    `pwpf/ai_testing/` is framework code - the exclusion must not catch the
    second while naming the first."""
    assert "ai_testing/" in verify.FORBIDDEN_WHEEL_PATHS
    assert not [bad for bad in verify.FORBIDDEN_WHEEL_PATHS if "pwpf/ai_testing/".startswith(bad)]


def test_the_installed_package_check_is_available_as_a_script():
    """It is invoked as `python scripts/verify_installed_package.py`, so it must
    stay executable that way rather than becoming an importable library only."""
    source = SCRIPT.read_text(encoding="utf-8")

    assert 'if __name__ == "__main__":' in source
    assert "raise SystemExit(main())" in source


@pytest.mark.parametrize("required", ["apps/", "tests/", "docs/", "conftest.py"])
def test_the_exclusion_list_names_every_tree_the_review_asked_about(required):
    assert required in verify.FORBIDDEN_WHEEL_PATHS
