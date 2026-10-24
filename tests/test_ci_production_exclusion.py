"""Guards the one control that actually keeps live-site tests out of CI.

`@pytest.mark.production` is a label, not an enforcement mechanism: what keeps a
test marked `production` from running in CI is the `-m` expression on each pytest
invocation in .github/workflows/ci.yml. Nothing else in the framework does -
conftest.py discovers a new application purely from its directory layout, so a
new tests/<app>/ folder joins the regression suite automatically.

These checks fail if that exclusion is dropped from a workflow command, if the
marker stops being registered, or if a test in a production-only application
forgets the marker. Pure static analysis: no browser, no network, no YAML
dependency (the workflow is read as text, so this adds nothing to the lock file).
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from config.settings import BASE_DIR

WORKFLOW = BASE_DIR / ".github" / "workflows" / "ci.yml"
PYTEST_INI = BASE_DIR / "pytest.ini"

# Applications whose tests drive a live third-party production site and must
# therefore never be collected by CI. Add a directory here when a new such
# application arrives - and only then.
PRODUCTION_APP_TEST_DIRS = [BASE_DIR / "tests" / "myntra"]

# A pytest invocation, as opposed to a mention of the word in a comment, a job
# name or a path such as reports/pytest_report.html.
_PYTEST_COMMAND = re.compile(r"(?:^|[\s:|&;(])pytest(?:\s|$)")
# -m <expr>, quoted or bare.
_MARKER_OPTION = re.compile(r"-m\s+(?:\"([^\"]*)\"|'([^']*)'|(\S+))")


def _pytest_command_lines() -> list[tuple[int, str]]:
    """Every line of the workflow that invokes pytest, with its 1-based number."""
    lines = WORKFLOW.read_text(encoding="utf-8").splitlines()
    found = []
    for number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if _PYTEST_COMMAND.search(stripped):
            found.append((number, stripped))
    return found


def test_workflow_exists_and_invokes_pytest():
    """If this fails, the check below would pass vacuously."""
    assert WORKFLOW.is_file(), f"{WORKFLOW} is missing"
    assert _pytest_command_lines(), f"No pytest invocation found in {WORKFLOW}"


def test_every_ci_pytest_invocation_excludes_production_tests():
    offenders = []
    for number, command in _pytest_command_lines():
        match = _MARKER_OPTION.search(command)
        expression = next((g for g in match.groups() if g is not None), "") if match else ""
        if "not production" not in expression:
            offenders.append(f"  ci.yml:{number}: {command}")
    assert not offenders, (
        "Every pytest invocation in .github/workflows/ci.yml must exclude production-marked "
        'tests with -m "not production" (combine it, e.g. -m "smoke and not production"). '
        "These do not:\n" + "\n".join(offenders)
    )


def test_production_marker_is_registered():
    markers = PYTEST_INI.read_text(encoding="utf-8")
    assert re.search(r"^\s+production:", markers, re.MULTILINE), (
        "The 'production' marker must stay registered in pytest.ini - with --strict-markers "
        "in addopts, an unregistered marker is an error, and the CI exclusion relies on it."
    )


def _test_functions(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith(
            "test_"
        ):
            yield node


def _marker_names(node) -> set[str]:
    names = set()
    for decorator in node.decorator_list:
        # @pytest.mark.foo and @pytest.mark.foo(...) alike.
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Attribute):
            if target.value.attr == "mark":
                names.add(target.attr)
    return names


@pytest.mark.parametrize("test_dir", PRODUCTION_APP_TEST_DIRS, ids=lambda p: p.name)
def test_every_test_in_a_production_app_carries_the_marker(test_dir: Path):
    if not test_dir.is_dir():
        pytest.skip(f"{test_dir} does not exist")
    unmarked = [
        f"  {path.relative_to(BASE_DIR)}::{node.name}"
        for path in sorted(test_dir.rglob("test_*.py"))
        for node in _test_functions(path)
        if "production" not in _marker_names(node)
    ]
    assert not unmarked, (
        f"Every test under {test_dir.relative_to(BASE_DIR)} drives a live production site and "
        "must carry @pytest.mark.production, or CI's exclusion will not deselect it:\n"
        + "\n".join(unmarked)
    )
