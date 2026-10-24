"""Guards the quarantine mechanism: what is in it, and what that implies in CI.

Quarantine is meant to be a narrow, visible, temporary state. The risk it
introduces is the opposite: a marker that quietly grows until a whole area of
the suite is "known unstable" and nothing gates anything. So these checks pin
the exact set of quarantined tests, require each one to be documented with its
exit criteria, and verify that the blocking CI jobs exclude exactly that marker
while the non-blocking job still runs it.

Static analysis only - the workflow is read as text and the tests as an AST, so
this needs no browser, no network and no YAML dependency. The production
exclusion is checked separately by tests/test_ci_production_exclusion.py, which
this deliberately does not duplicate.
"""

from __future__ import annotations

import ast
import re

from pwpf.config.paths import project_root

BASE_DIR = project_root()
WORKFLOW = BASE_DIR / ".github" / "workflows" / "ci.yml"
PYTEST_INI = BASE_DIR / "pytest.ini"
DESIGN = BASE_DIR / "DESIGN.md"
TESTS_DIR = BASE_DIR / "tests"

# The complete quarantine list, currently empty: the one test that was in it had
# its hydration race fixed and is back in the blocking smoke gate. The mechanism
# stays, because the next unstable test should be held here deliberately rather
# than tolerated. Adding an entry is a deliberate act: these checks fail until the
# node id is listed here AND documented in DESIGN.md with its evidence and its
# exit criteria.
QUARANTINED: frozenset[str] = frozenset()

_PYTEST_COMMAND = re.compile(r"(?:^|[\s:|&;(])pytest(?:\s|$)")
_MARKER_OPTION = re.compile(r"-m\s+(?:\"([^\"]*)\"|'([^']*)'|(\S+))")
_JOB_HEADER = re.compile(r"^  ([a-z][a-z0-9-]*):\s*$")


def _jobs_with_pytest() -> list[tuple[str, bool, str]]:
    """(job name, is non-blocking, pytest command) for every pytest invocation."""
    lines = WORKFLOW.read_text(encoding="utf-8").splitlines()

    # Which job each line belongs to, and whether that job is continue-on-error.
    job_of_line: list[str] = []
    current = ""
    non_blocking: set[str] = set()
    for line in lines:
        header = _JOB_HEADER.match(line)
        if header:
            current = header.group(1)
        if current and line.strip() == "continue-on-error: true":
            non_blocking.add(current)
        job_of_line.append(current)

    found = []
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("#") or not _PYTEST_COMMAND.search(stripped):
            continue
        job = job_of_line[index]
        found.append((job, job in non_blocking, stripped))
    return found


def _marker_expression(command: str) -> str:
    match = _MARKER_OPTION.search(command)
    if not match:
        return ""
    return next((group for group in match.groups() if group is not None), "")


def _quarantined_tests() -> dict[str, tuple[str | None, frozenset[str]]]:
    """Node id -> (docstring, markers), for every @pytest.mark.quarantined test."""
    found: dict[str, tuple[str | None, frozenset[str]]] = {}
    for path in sorted(TESTS_DIR.rglob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not node.name.startswith("test_"):
                continue
            markers = set()
            for decorator in node.decorator_list:
                target = decorator.func if isinstance(decorator, ast.Call) else decorator
                if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Attribute):
                    if target.value.attr == "mark":
                        markers.add(target.attr)
            if "quarantined" in markers:
                nodeid = f"{path.relative_to(BASE_DIR).as_posix()}::{node.name}"
                found[nodeid] = (ast.get_docstring(node), frozenset(markers))
    return found


def test_the_quarantined_marker_is_registered():
    assert re.search(r"^\s+quarantined:", PYTEST_INI.read_text(encoding="utf-8"), re.MULTILINE), (
        "The 'quarantined' marker must stay registered in pytest.ini - with --strict-markers, "
        "an unregistered marker is an error, and the CI exclusions rely on it."
    )


def test_only_the_recorded_tests_are_quarantined():
    actual = set(_quarantined_tests())
    assert actual == set(QUARANTINED), (
        "The quarantine list changed. Quarantine is a holding state with an exit criterion, "
        "not a way to silence a failure: add the test here and document it in DESIGN.md "
        "(section 8, 'Quarantined tests') with its evidence and what must happen before it "
        f"returns to the blocking gates.\n  added: {sorted(actual - set(QUARANTINED))}\n"
        f"  removed: {sorted(set(QUARANTINED) - actual)}"
    )


def test_every_quarantined_test_explains_itself():
    undocumented = [
        nodeid for nodeid, (docstring, _) in _quarantined_tests().items() if not docstring
    ]
    assert not undocumented, (
        "A quarantined test must say in its docstring why it is quarantined and how it gets "
        f"out: {undocumented}"
    )


def test_every_quarantined_test_is_recorded_in_design():
    design = DESIGN.read_text(encoding="utf-8")
    missing = [nodeid for nodeid in QUARANTINED if nodeid.split("::")[0] not in design]
    assert not missing, (
        "DESIGN.md must record each quarantined test with its evidence, owner and exit "
        f"criteria: {missing}"
    )


def test_blocking_ci_jobs_exclude_quarantined_tests():
    offenders = [
        f"  {job}: {command}"
        for job, is_non_blocking, command in _jobs_with_pytest()
        if not is_non_blocking and "not quarantined" not in _marker_expression(command)
    ]
    assert not offenders, (
        'Every blocking pytest invocation must exclude quarantined tests with -m "... and '
        'not quarantined". These do not:\n' + "\n".join(offenders)
    )


def test_a_non_blocking_job_still_runs_the_quarantined_tests():
    """Quarantine must not mean invisibility: the outcome still has to be reported
    somewhere, or a quarantined test rots until nobody knows what it does."""
    selecting = [
        command
        for _, is_non_blocking, command in _jobs_with_pytest()
        if is_non_blocking and "quarantined" in _marker_expression(command)
    ]
    assert selecting, (
        "No non-blocking CI job runs the quarantined tests. One job with "
        "continue-on-error: true must select them, so their failures stay visible without "
        "gating anything."
    )


def test_the_quarantine_job_does_not_relax_the_production_policy():
    for _, is_non_blocking, command in _jobs_with_pytest():
        if is_non_blocking:
            assert "not production" in _marker_expression(command), (
                "The non-blocking job must still exclude production tests: quarantine is "
                "not a route to running live-site tests in CI."
            )


def test_quarantine_does_not_remove_a_test_from_its_suite():
    """The marker is additive: a quarantined test keeps the suite markers it had, so
    `pytest -m smoke` locally still runs it and it stays explicitly runnable. Checked
    against whatever is quarantined rather than one hard-coded node id, so it keeps
    working as the list changes - and passes vacuously while the list is empty."""
    suite_markers = {"smoke", "ui", "api", "regression"}
    stripped = sorted(
        nodeid
        for nodeid, (_, markers) in _quarantined_tests().items()
        if not markers & suite_markers
    )
    assert not stripped, (
        "A quarantined test must keep its suite markers - quarantine excludes it from the "
        f"blocking gates, it does not take it out of its suite: {stripped}"
    )
