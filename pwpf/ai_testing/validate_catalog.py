"""Deterministic validation of the scenario catalogs under `apps/*/scenarios/`.

Run it directly:

    python -m pwpf.ai_testing.validate_catalog          # the whole project
    pwpf-validate-catalog --root /path/to/project       # installed console script

It is static analysis and nothing else: it parses YAML, validates it against
`ai_testing/schemas/scenario.schema.json`, applies the cross-field lifecycle
rules, and reads `tests/` as an abstract syntax tree to check scenario-to-test
mappings. It never imports a test, starts a browser, opens a socket or executes
a scenario, so it is safe to run anywhere and needs no browser install.

Its two dependencies (PyYAML, jsonschema) are pinned in `requirements-ai.txt`,
deliberately apart from the test-runtime lock that every test job installs. The
catalog self-tests in `tests/test_scenario_catalog.py` skip when they are
absent; CI runs this command in its own job instead.

Exit status is 0 when the catalogs are clean and 1 when any rule is violated.
Each finding names the rule it broke, the file, and the scenario id where one
can be identified.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import dataclass, replace
from importlib import resources
from pathlib import Path
from typing import Any, Iterator, Sequence

from pwpf.config.paths import ProjectRootError, project_root, set_project_root

# The schema ships with the framework, so it is read as package data rather than
# from a path next to this file: once installed, "next to this file" is inside
# site-packages, and a zipped distribution has no such path at all. The catalogs
# are the opposite - they belong to whichever project is being validated, which
# is why every entry point below resolves a consumer project root.
SCHEMA_RESOURCE = "schemas/scenario.schema.json"


def schema_text() -> str:
    """The scenario schema, from the installed distribution."""
    package = resources.files(__package__)
    return (package / SCHEMA_RESOURCE).read_text(encoding="utf-8")


# A backwards-incompatible schema change adds a new file and a new entry here,
# so catalogs on the old version keep validating until they are migrated.
SUPPORTED_SCHEMA_VERSIONS = ("1.0",)

# Statuses that assert a human has signed off on the expected results, and
# those that additionally assert an implementing test exists.
APPROVED_ONWARDS = frozenset({"APPROVED", "IMPLEMENTED", "VALIDATED", "ACTIVE_REGRESSION"})
REQUIRES_IMPLEMENTATION = frozenset({"IMPLEMENTED", "VALIDATED", "ACTIVE_REGRESSION"})

_MARKER_LINE = re.compile(r"^\s{4}([a-z_]+)\s*(?:\(|:)")


@dataclass(frozen=True)
class Finding:
    """One rule violation. `rule` is the identifier documented in
    docs/ai-testing/scenario-authoring.md, so a failure can be looked up."""

    rule: str
    path: str
    scenario_id: str | None
    message: str

    def __str__(self) -> str:
        where = f"{self.path}" + (f" [{self.scenario_id}]" if self.scenario_id else "")
        return f"{self.rule}  {where}: {self.message}"


# --------------------------------------------------------------------------- #
# Discovery and loading
# --------------------------------------------------------------------------- #


def discover_catalogs(root: Path) -> list[Path]:
    """Every committed catalog file, in a stable order.

    The catalog's home is the application package (`apps/<app>/scenarios/`) so
    an application stays self-contained; there is deliberately no parallel
    top-level catalog tree to search.
    """
    apps_dir = root / "apps"
    if not apps_dir.is_dir():
        return []
    found = [
        path
        for app in sorted(p for p in apps_dir.iterdir() if p.is_dir())
        for pattern in ("*.yaml", "*.yml")
        for path in sorted((app / "scenarios").glob(pattern))
    ]
    return found


def _load_yaml(path: Path) -> tuple[Any, Finding | None]:
    import yaml  # imported here so --help works without the tooling installed

    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")), None
    except yaml.YAMLError as exc:
        detail = str(exc).replace("\n", " ")
        return None, Finding("E-YAML", str(path), None, f"file is not valid YAML: {detail}")


def _scenario_id_at(document: Any, json_path: Sequence[Any]) -> str | None:
    """Best-effort: map a schema error's path back to the scenario it is in."""
    if len(json_path) >= 2 and json_path[0] == "scenarios" and isinstance(json_path[1], int):
        try:
            scenario = document["scenarios"][json_path[1]]
        except (KeyError, IndexError, TypeError):
            return None
        if isinstance(scenario, dict):
            found = scenario.get("id")
            return found if isinstance(found, str) else None
    return None


# --------------------------------------------------------------------------- #
# Schema and cross-field rules
# --------------------------------------------------------------------------- #


def schema_findings(path: Path, document: Any) -> list[Finding]:
    from jsonschema import Draft202012Validator

    schema = json.loads(schema_text())
    validator = Draft202012Validator(schema)
    findings = []
    for error in sorted(validator.iter_errors(document), key=lambda e: list(e.absolute_path)):
        location = "/".join(str(part) for part in error.absolute_path) or "<document root>"
        findings.append(
            Finding(
                "E-SCHEMA",
                str(path),
                _scenario_id_at(document, list(error.absolute_path)),
                f"{location}: {error.message}",
            )
        )
    return findings


def _app_of(path: Path, root: Path) -> str:
    # apps/<app>/scenarios/<feature>.yaml
    return path.relative_to(root / "apps").parts[0]


def lifecycle_findings(path: Path, document: Any, root: Path, markers: set[str]) -> list[Finding]:
    """The cross-field rules. These are what make a status mean something: a
    YAML field cannot enforce anything by itself, but a check that refuses to
    pass until the field is consistent with the rest of the file can."""
    findings: list[Finding] = []
    if not isinstance(document, dict):
        return findings

    version = document.get("schema_version")
    if version not in SUPPORTED_SCHEMA_VERSIONS:
        findings.append(
            Finding(
                "E-VERSION",
                str(path),
                None,
                f"schema_version {version!r} is not supported "
                f"(supported: {', '.join(SUPPORTED_SCHEMA_VERSIONS)})",
            )
        )

    raw_meta = document.get("meta")
    meta: dict[str, Any] = raw_meta if isinstance(raw_meta, dict) else {}
    owning_app = _app_of(path, root)
    if meta.get("app") != owning_app:
        findings.append(
            Finding(
                "E-APP",
                str(path),
                None,
                f"meta.app is {meta.get('app')!r} but the catalog lives in apps/{owning_app}/",
            )
        )
    if not (root / "apps" / owning_app).is_dir():
        findings.append(
            Finding("E-APP", str(path), None, f"no such application package: apps/{owning_app}/")
        )

    scenarios = document.get("scenarios")
    if not isinstance(scenarios, list):
        return findings

    for scenario in scenarios:
        if not isinstance(scenario, dict):
            continue
        findings.extend(_scenario_rules(path, scenario, meta, markers))
    return findings


def _scenario_rules(
    path: Path, scenario: dict[str, Any], meta: dict[str, Any], markers: set[str]
) -> Iterator[Finding]:
    sid = scenario.get("id") if isinstance(scenario.get("id"), str) else None
    status = scenario.get("status")
    environment = scenario.get("environment") or {}
    automation = scenario.get("automation") or {}
    review = scenario.get("review") or {}
    test = automation.get("test")
    implemented = automation.get("implemented")
    declared_markers = automation.get("markers") or []

    def finding(rule: str, message: str) -> Finding:
        return Finding(rule, str(path), sid, message)

    if meta.get("feature") and scenario.get("feature") != meta.get("feature"):
        yield finding(
            "E-FEATURE",
            f"feature {scenario.get('feature')!r} does not match meta.feature "
            f"{meta.get('feature')!r} - one catalog file covers one feature",
        )

    if implemented is True and not test:
        yield finding("E-MAPPING", "automation.implemented is true but automation.test is null")
    if implemented is False and test:
        yield finding("E-MAPPING", f"automation.test is set to {test!r} but implemented is false")

    if status in REQUIRES_IMPLEMENTATION and not test:
        yield finding("E-LIFECYCLE", f"status {status} requires an implementing test")

    approved_record = review.get("approved_by") and review.get("approved_date")
    if status in APPROVED_ONWARDS and not approved_record:
        yield finding(
            "E-APPROVAL",
            f"status {status} requires review.approved_by and review.approved_date - "
            "approving expected results is a human act and cannot be self-assigned",
        )

    if environment.get("target") == "live-production":
        if environment.get("ci_eligible") is not False:
            yield finding(
                "E-PRODUCTION",
                "a live-production target must set ci_eligible: false - a live third-party "
                "site can never be a blocking CI gate",
            )
        if environment.get("authorization_required") is not True:
            yield finding(
                "E-PRODUCTION",
                "a live-production target must set authorization_required: true",
            )
        if "production" not in declared_markers:
            yield finding(
                "E-PRODUCTION",
                "a live-production scenario must declare the `production` marker, which is "
                'what excludes it from every CI run (-m "not production")',
            )

    if status == "ACTIVE_REGRESSION":
        if environment.get("ci_eligible") is not True:
            yield finding(
                "E-REGRESSION",
                "ACTIVE_REGRESSION requires ci_eligible: true - the status means this test "
                "gates changes, and every collected test runs in CI",
            )
        if "production" in declared_markers:
            yield finding(
                "E-REGRESSION",
                "a production-marked scenario cannot be ACTIVE_REGRESSION: it is excluded "
                "from every CI invocation by design",
            )

    history = review.get("status_history") or []
    if isinstance(history, list) and history:
        last = history[-1]
        if isinstance(last, dict) and last.get("status") != status:
            yield finding(
                "E-HISTORY",
                f"status is {status} but the last status_history entry is "
                f"{last.get('status')} - the history must record the current status",
            )

    for marker in declared_markers:
        if markers and marker not in markers:
            yield finding(
                "E-MARKER",
                f"marker {marker!r} is not registered in pytest.ini, and --strict-markers "
                "would reject it",
            )


def duplicate_id_findings(by_id: dict[str, list[tuple[Path, str]]]) -> list[Finding]:
    """Ids are unique across every catalog in the repository, not just within a
    file: an id is the one stable handle a report, a test and a review share."""
    findings = []
    for sid, occurrences in sorted(by_id.items()):
        if len(occurrences) > 1:
            where = ", ".join(str(path) for path, _ in occurrences)
            findings.append(
                Finding("E-DUPLICATE", where, sid, f"scenario id appears {len(occurrences)} times")
            )
    return findings


# --------------------------------------------------------------------------- #
# Traceability: catalog <-> tests, by AST
# --------------------------------------------------------------------------- #


def registered_markers(root: Path) -> set[str]:
    ini = root / "pytest.ini"
    if not ini.is_file():
        return set()
    return {
        match.group(1)
        for line in ini.read_text(encoding="utf-8").splitlines()
        if (match := _MARKER_LINE.match(line))
    }


def _marker_names_and_args(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> tuple[set[str], list[str]]:
    names: set[str] = set()
    scenario_ids: list[str] = []
    for decorator in node.decorator_list:
        call = decorator if isinstance(decorator, ast.Call) else None
        target = call.func if call else decorator
        if not (isinstance(target, ast.Attribute) and isinstance(target.value, ast.Attribute)):
            continue
        if target.value.attr != "mark":
            continue
        names.add(target.attr)
        if target.attr == "scenario" and call:
            scenario_ids.extend(
                arg.value
                for arg in call.args
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
            )
    return names, scenario_ids


@dataclass(frozen=True)
class TestFunction:
    nodeid: str
    markers: frozenset[str]
    scenario_ids: tuple[str, ...]


def collect_test_functions(root: Path) -> dict[str, TestFunction]:
    """Every test function under tests/, keyed by `<path>::<name>` node id.

    AST only - importing the modules would pull in Playwright and the root
    conftest, and a validator has no business doing that.
    """
    tests_dir = root / "tests"
    if not tests_dir.is_dir():
        return {}
    found: dict[str, TestFunction] = {}
    for path in sorted(tests_dir.rglob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not node.name.startswith("test_"):
                continue
            markers, scenario_ids = _marker_names_and_args(node)
            nodeid = f"{path.relative_to(root).as_posix()}::{node.name}"
            found[nodeid] = TestFunction(nodeid, frozenset(markers), tuple(scenario_ids))
    return found


def traceability_findings(
    scenarios: dict[str, tuple[Path, dict[str, Any]]], tests: dict[str, TestFunction]
) -> list[Finding]:
    findings: list[Finding] = []

    # Which test(s) claim each scenario id, from the test side.
    claimed: dict[str, list[str]] = {}
    for test in tests.values():
        for sid in test.scenario_ids:
            claimed.setdefault(sid, []).append(test.nodeid)

    for sid, (path, scenario) in sorted(scenarios.items()):
        automation = scenario.get("automation") or {}
        environment = scenario.get("environment") or {}
        nodeid = automation.get("test")
        if not nodeid:
            # DRAFT, AI_REVIEWED, NEEDS_* and BLOCKED scenarios are not
            # required to have a test; the lifecycle rules cover the statuses
            # that are.
            continue
        mapped = tests.get(nodeid)
        if mapped is None:
            findings.append(
                Finding(
                    "E-TRACE",
                    str(path),
                    sid,
                    f"automation.test {nodeid!r} does not match any collected test function "
                    "(check the path and the function name; parameters are not part of the "
                    "reference)",
                )
            )
            continue
        if sid not in mapped.scenario_ids:
            findings.append(
                Finding(
                    "E-TRACE",
                    str(path),
                    sid,
                    f'{nodeid} does not carry @pytest.mark.scenario("{sid}"), so the '
                    "mapping exists in the catalog only and nothing in a report links them",
                )
            )
        target_is_live = environment.get("target") == "live-production"
        if target_is_live and "production" not in mapped.markers:
            findings.append(
                Finding(
                    "E-PRODUCTION",
                    str(path),
                    sid,
                    f"{nodeid} drives a live-production scenario but lacks "
                    "@pytest.mark.production",
                )
            )

    for sid, nodeids in sorted(claimed.items()):
        if sid not in scenarios:
            findings.append(
                Finding(
                    "E-ORPHAN",
                    ", ".join(nodeids),
                    sid,
                    "test is marked with a scenario id that no catalog defines",
                )
            )
            continue
        if len(nodeids) > 1:
            findings.append(
                Finding(
                    "E-TRACE",
                    str(scenarios[sid][0]),
                    sid,
                    "mapped to more than one test "
                    f"({', '.join(nodeids)}); one scenario is implemented by exactly one test, "
                    "though one test may cover several scenarios",
                )
            )
            continue
        declared = (scenarios[sid][1].get("automation") or {}).get("test")
        if declared and declared != nodeids[0]:
            findings.append(
                Finding(
                    "E-TRACE",
                    str(scenarios[sid][0]),
                    sid,
                    f"catalog maps this scenario to {declared!r} but {nodeids[0]} claims it",
                )
            )

    return findings


# --------------------------------------------------------------------------- #
# Entry points
# --------------------------------------------------------------------------- #


def validate_catalog(root: Path | None = None) -> list[Finding]:
    """Every finding for every catalog under `root`. Empty means valid."""
    root = root if root is not None else project_root()
    findings: list[Finding] = []
    markers = registered_markers(root)
    by_id: dict[str, list[tuple[Path, str]]] = {}
    scenarios: dict[str, tuple[Path, dict[str, Any]]] = {}

    for path in discover_catalogs(root):
        document, yaml_finding = _load_yaml(path)
        if yaml_finding is not None:
            findings.append(yaml_finding)
            continue
        if document is None:
            findings.append(Finding("E-YAML", str(path), None, "file is empty"))
            continue

        schema_errors = schema_findings(path, document)
        findings.extend(schema_errors)
        findings.extend(lifecycle_findings(path, document, root, markers))

        if isinstance(document, dict) and isinstance(document.get("scenarios"), list):
            for scenario in document["scenarios"]:
                if not isinstance(scenario, dict):
                    continue
                sid = scenario.get("id")
                if not isinstance(sid, str):
                    continue
                by_id.setdefault(sid, []).append((path, sid))
                scenarios.setdefault(sid, (path, scenario))

    findings.extend(duplicate_id_findings(by_id))
    findings.extend(traceability_findings(scenarios, collect_test_functions(root)))
    # Findings are built with absolute paths (several helpers never see `root`);
    # reporting them repository-relative keeps output diffable across machines.
    prefix = f"{root}/"
    return [replace(f, path=f.path.replace(prefix, "")) for f in findings]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pwpf-validate-catalog",
        description="Validate the scenario catalogs and their test mappings. Static analysis "
        "only: no browser, no network, no scenario execution.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="project root to validate (default: the resolved project root - see "
        "pwpf/config/paths.py for the precedence)",
    )
    args = parser.parse_args(argv)
    try:
        root = set_project_root(args.root, source="--root") if args.root else project_root()
    except ProjectRootError as exc:
        print(f"{exc}", file=sys.stderr)
        return 2

    catalogs = discover_catalogs(root)
    findings = validate_catalog(root)

    for finding in findings:
        print(finding, file=sys.stderr)

    if findings:
        print(
            f"\n{len(findings)} finding(s) in {len(catalogs)} catalog file(s). "
            "Rules are documented in docs/ai-testing/scenario-authoring.md.",
            file=sys.stderr,
        )
        return 1
    print(f"Scenario catalogs valid: {len(catalogs)} file(s) checked under {root}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
