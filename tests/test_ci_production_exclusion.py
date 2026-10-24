"""Guards the one control that actually keeps live-site tests out of CI.

`@pytest.mark.production` is a label, not an enforcement mechanism: what keeps a
test marked `production` from running in CI is the `-m` expression on each pytest
invocation in .github/workflows/ci.yml. Nothing else in the framework does -
conftest.py discovers a new application purely from its directory layout, so a
new tests/<app>/ folder joins the regression suite automatically.

Which applications are live-production targets is read from configuration, not
from a list of names kept here: an application declares itself with
`"production_target": true` in its own `apps/<app>/config/<environment>.json`.
A declaration that cannot be read - malformed JSON, a non-object document, a
value that is not a JSON boolean - is a failure, never a quiet omission, because
an application dropped from the set is an application nobody is checking.

The policy runs in both directions:

* a declared production application may not contain an unmarked test, or CI's
  exclusion will not deselect it;
* a production-marked test must belong to a declared production application -
  a stray marker means either the marker or the declaration is wrong.

Application ownership follows the same rule as the root conftest: the first path
segment under tests/ names the application, provided it is not a generic suite
directory and a matching apps/<name>/ package exists. A production marker on a
test outside any application is reported as exactly that, rather than being
blamed on a directory or a filename that was never an application.

These checks also fail if the exclusion is dropped from a workflow command or if
the marker stops being registered. Pure static analysis: no browser, no network,
no YAML dependency (the workflow and configs are read as text and JSON, and the
tests as an AST, so this adds nothing to the lock file).
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

from config.settings import BASE_DIR

WORKFLOW = BASE_DIR / ".github" / "workflows" / "ci.yml"
PYTEST_INI = BASE_DIR / "pytest.ini"

# An application declares itself a live-production target in its own config,
# `apps/<app>/config/<environment>.json`, with `"production_target": true`.
# Nothing here names an application: the framework layer should not know which
# app happens to be the pilot, and a new production app becomes visible to these
# checks by declaring itself rather than by someone remembering to edit a list.
#
# The flag is read straight from the JSON rather than through AppConfig, for two
# reasons: `load_app_config` resolves one environment (and an app that never runs
# in CI has no ci.json to resolve), and an unrecognised key would land silently in
# `AppConfig.extra`. A declaration that cannot be read is a failure here, not a
# skip - see test_production_app_declarations_are_valid.
PRODUCTION_FLAG = "production_target"

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


def production_apps(root: Path = BASE_DIR) -> tuple[set[str], list[str]]:
    """Applications declaring `production_target: true`, and any problems found.

    Every environment file of every application is read, so an app is a production
    target if *any* of its environments says so - an app that is live in one
    environment is not safe to collect in CI because another environment omits the
    flag. Problems are returned rather than raised so a single test can report all
    of them at once; nothing is skipped on their account.
    """
    declared: set[str] = set()
    problems: list[str] = []
    apps_dir = root / "apps"
    if not apps_dir.is_dir():
        return declared, [f"no applications directory at {apps_dir}"]

    for config_path in sorted(apps_dir.glob("*/config/*.json")):
        app = config_path.relative_to(apps_dir).parts[0]
        try:
            raw = json.loads(config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            problems.append(f"{config_path.relative_to(root)} is not valid JSON: {exc}")
            continue
        if not isinstance(raw, dict):
            problems.append(f"{config_path.relative_to(root)} is not a JSON object")
            continue
        if PRODUCTION_FLAG not in raw:
            continue
        value = raw[PRODUCTION_FLAG]
        if not isinstance(value, bool):
            problems.append(
                f"{config_path.relative_to(root)}: {PRODUCTION_FLAG!r} must be a JSON "
                f"boolean (true/false, unquoted), got {value!r}"
            )
            continue
        if value:
            declared.add(app)
    return declared, problems


# Mirrors `_GENERIC_SUITE_DIRS` in the root conftest.py: suite-type folders that
# hold tests not owned by any one application. Kept in step with it by
# test_the_application_ownership_rule_matches_conftest below.
GENERIC_SUITE_DIRS = frozenset({"smoke", "ui", "regression", "api", "tmp"})


def _owning_app(path: Path, root: Path) -> str | None:
    """The application a test file belongs to, or None if it belongs to none.

    The same rule as conftest.py's `_app_name_for_path`: the first segment under
    tests/ names the application when it is not a generic suite directory and
    apps/<name>/ exists. `tests/api/test_x.py` and `tests/test_x.py` therefore
    belong to no application, which is different from belonging to one that has
    not declared itself.
    """
    try:
        parts = path.relative_to(root / "tests").parts
    except ValueError:
        return None
    if not parts:
        return None
    app = parts[0]
    if app in GENERIC_SUITE_DIRS or not (root / "apps" / app).is_dir():
        return None
    return app


def _stray_production_tests(root: Path, declared: set[str]) -> list[str]:
    """Production-marked tests that no declared production application owns."""
    stray: list[str] = []
    for path in sorted((root / "tests").rglob("test_*.py")):
        app = _owning_app(path, root)
        for node in _test_functions(path):
            if "production" not in _marker_names(node):
                continue
            nodeid = f"{path.relative_to(root)}::{node.name}"
            if app is None:
                stray.append(
                    f"  {nodeid} is marked production but belongs to no application: a "
                    "production test lives in tests/<app>/ with a matching apps/<app>/"
                )
            elif app not in declared:
                stray.append(
                    f"  {nodeid} is marked production, but apps/{app} does not declare "
                    f"{PRODUCTION_FLAG}: true"
                )
    return stray


def _unmarked_tests_under(test_dir: Path, root: Path) -> list[str]:
    return [
        f"  {path.relative_to(root)}::{node.name}"
        for path in sorted(test_dir.rglob("test_*.py"))
        for node in _test_functions(path)
        if "production" not in _marker_names(node)
    ]


def test_production_app_declarations_are_valid():
    """A declaration that cannot be read must fail loudly. If an unreadable or
    malformed config quietly dropped an application from the set, these checks would
    pass while the application's tests were left unguarded."""
    _, problems = production_apps()
    assert not problems, (
        f"Application configuration declaring {PRODUCTION_FLAG!r} could not be read:\n  "
        + "\n  ".join(problems)
    )


def test_a_declared_production_app_has_tests_to_guard():
    """Also not a skip: an app that declares itself a production target but has no
    tests directory means either the declaration or the tests are in the wrong
    place, and the guard below would silently check nothing."""
    declared, _ = production_apps()
    missing = [
        f"  apps/{app} declares {PRODUCTION_FLAG}: true but tests/{app}/ has no tests"
        for app in sorted(declared)
        if not list((BASE_DIR / "tests" / app).rglob("test_*.py"))
    ]
    assert not missing, "\n".join(missing)


def test_every_test_in_a_production_app_carries_the_marker():
    declared, _ = production_apps()
    unmarked = [
        line
        for app in sorted(declared)
        for line in _unmarked_tests_under(BASE_DIR / "tests" / app, BASE_DIR)
    ]
    assert not unmarked, (
        "Every test under an application that declares itself a live-production target "
        "must carry @pytest.mark.production, or CI's exclusion will not deselect it:\n"
        + "\n".join(unmarked)
    )


def test_production_marked_tests_live_only_in_declared_apps():
    """The inverse direction, which the previous hard-coded list could not catch: a
    test marked `production` that no declared production application owns. Either
    the marker or the declaration is wrong, and both are worth knowing about."""
    declared, _ = production_apps()
    stray = _stray_production_tests(BASE_DIR, declared)
    assert not stray, (
        "Every production-marked test must belong to an application that declares "
        f"{PRODUCTION_FLAG}: true:\n" + "\n".join(stray)
    )


def _conftest_generic_suite_dirs(root: Path = BASE_DIR) -> frozenset[str] | None:
    """The root conftest's `_GENERIC_SUITE_DIRS`, read from its source.

    Deliberately not `import conftest`: five conftest.py files live in this
    repository, and under pytest's prepend import mode - xdist workers in
    particular - the name resolves to whichever one was imported first, which is
    usually one of the per-application ones. Reading the literal keeps this in the
    same static-analysis style as the rest of the module and cannot pick the wrong
    file.
    """
    tree = ast.parse((root / "conftest.py").read_text(encoding="utf-8"), filename="conftest.py")
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "_GENERIC_SUITE_DIRS":
                return frozenset(ast.literal_eval(node.value))
    return None


def test_the_application_ownership_rule_matches_conftest():
    """R2 only holds while the two agree on what an application is. If the root
    conftest gains or loses a generic suite directory, this fails rather than
    letting the policy quietly diverge from how tests are actually labelled."""
    from_conftest = _conftest_generic_suite_dirs()

    assert from_conftest is not None, (
        "conftest.py no longer defines _GENERIC_SUITE_DIRS - the ownership rule here "
        "mirrors it and must be re-checked against whatever replaced it"
    )
    assert GENERIC_SUITE_DIRS == from_conftest, (
        "GENERIC_SUITE_DIRS here has drifted from conftest.py's _GENERIC_SUITE_DIRS: "
        f"{sorted(GENERIC_SUITE_DIRS)} vs {sorted(from_conftest)}"
    )


# --------------------------------------------------------------------------- #
# Focused tests for the discovery itself, against throwaway repositories, so the
# rules hold for any application rather than only for whatever this repository
# happens to contain today.
# --------------------------------------------------------------------------- #


def _app(root: Path, name: str, config: str, environment: str = "local") -> None:
    """Write apps/<name>/config/<environment>.json verbatim (so a test can make it
    malformed) and give the app a tests/ directory."""
    config_dir = root / "apps" / name / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / f"{environment}.json").write_text(config, encoding="utf-8")
    (root / "tests" / name).mkdir(parents=True, exist_ok=True)


def test_discovery_finds_only_the_apps_that_declare_themselves(tmp_path):
    _app(tmp_path, "live_app", '{"base_url": "https://example.test", "production_target": true}')
    _app(
        tmp_path, "staging_app", '{"base_url": "https://example.test", "production_target": false}'
    )
    _app(tmp_path, "quiet_app", '{"base_url": "https://example.test"}')

    declared, problems = production_apps(tmp_path)

    assert declared == {"live_app"}
    assert problems == []


def test_discovery_reads_every_environment_of_an_app(tmp_path):
    """Declared in one environment is declared, full stop: an app that is live
    anywhere is not safe to collect in CI because another environment omits it."""
    _app(tmp_path, "mixed_app", '{"base_url": "https://example.test"}', environment="ci")
    _app(tmp_path, "mixed_app", '{"base_url": "https://example.test", "production_target": true}')

    declared, problems = production_apps(tmp_path)

    assert declared == {"mixed_app"}
    assert problems == []


def test_missing_applications_directory_is_a_problem_not_an_empty_result(tmp_path):
    declared, problems = production_apps(tmp_path)

    assert declared == set()
    assert len(problems) == 1 and "no applications directory" in problems[0]


def test_an_app_without_configuration_is_simply_not_declared(tmp_path):
    """A config-less directory is not an error - plenty of apps have no config in a
    given environment - but it must never count as a production target either."""
    (tmp_path / "apps" / "config_less_app").mkdir(parents=True)
    _app(tmp_path, "live_app", '{"production_target": true}')

    declared, problems = production_apps(tmp_path)

    assert declared == {"live_app"}
    assert problems == []


def test_malformed_json_is_reported_rather_than_skipped(tmp_path):
    _app(tmp_path, "broken_app", '{"production_target": true,}')

    declared, problems = production_apps(tmp_path)

    assert declared == set()
    assert len(problems) == 1
    assert "broken_app" in problems[0] and "not valid JSON" in problems[0]


def test_a_non_boolean_declaration_is_reported_rather_than_coerced(tmp_path):
    """`bool("false")` is True in Python: coercing here would flip a safety-relevant
    declaration to the opposite of what was written. The same reasoning as
    core/app_config.py applies to ignore_https_errors."""
    _app(tmp_path, "stringly_app", '{"production_target": "true"}')

    declared, problems = production_apps(tmp_path)

    assert declared == set()
    assert len(problems) == 1
    assert "must be a JSON boolean" in problems[0]


def test_a_json_document_that_is_not_an_object_is_reported(tmp_path):
    _app(tmp_path, "list_app", "[1, 2, 3]")

    declared, problems = production_apps(tmp_path)

    assert declared == set()
    assert len(problems) == 1 and "not a JSON object" in problems[0]


def test_unmarked_tests_are_found_under_a_declared_app(tmp_path):
    """The guard itself, exercised without depending on this repository's apps."""
    _app(tmp_path, "live_app", '{"production_target": true}')
    (tmp_path / "tests" / "live_app" / "test_marked.py").write_text(
        "import pytest\n\n\n@pytest.mark.production\ndef test_ok():\n    pass\n",
        encoding="utf-8",
    )
    (tmp_path / "tests" / "live_app" / "test_unmarked.py").write_text(
        "def test_forgotten():\n    pass\n", encoding="utf-8"
    )

    unmarked = _unmarked_tests_under(tmp_path / "tests" / "live_app", tmp_path)

    assert unmarked == ["  tests/live_app/test_unmarked.py::test_forgotten"]


def _test_file(root: Path, relative: str, *, marked: bool) -> Path:
    """Write a test module under tests/, with or without the production marker."""
    path = root / "tests" / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "import pytest\n\n\n"
    if marked:
        body += "@pytest.mark.production\n"
    body += f"def test_{path.stem}_case():\n    pass\n"
    path.write_text(body, encoding="utf-8")
    return path


def test_conflicting_declarations_across_environments_mean_production(tmp_path):
    """The documented safety rule, pinned: any `true` wins. An application that is
    live in one environment is not safe to collect in CI because another
    environment's file omits or disables the flag. Changing this should require
    changing this test."""
    _app(tmp_path, "mixed_app", '{"production_target": true}', environment="local")
    _app(tmp_path, "mixed_app", '{"production_target": false}', environment="ci")

    declared, problems = production_apps(tmp_path)

    assert declared == {"mixed_app"}
    assert problems == []


def test_a_declared_app_whose_tests_are_all_marked_is_clean(tmp_path):
    _app(tmp_path, "live_app", '{"production_target": true}')
    _test_file(tmp_path, "live_app/smoke/test_home.py", marked=True)
    _test_file(tmp_path, "live_app/ui/test_journey.py", marked=True)

    declared, problems = production_apps(tmp_path)

    assert declared == {"live_app"}
    assert problems == []
    assert _stray_production_tests(tmp_path, declared) == []
    assert _unmarked_tests_under(tmp_path / "tests" / "live_app", tmp_path) == []


def test_a_production_marked_test_in_an_undeclared_app_is_reported(tmp_path):
    _app(tmp_path, "undeclared_app", '{"base_url": "https://example.test"}')
    _test_file(tmp_path, "undeclared_app/smoke/test_home.py", marked=True)

    declared, _ = production_apps(tmp_path)
    stray = _stray_production_tests(tmp_path, declared)

    assert len(stray) == 1
    assert "tests/undeclared_app/smoke/test_home.py::test_test_home_case" in stray[0]
    assert "apps/undeclared_app does not declare production_target: true" in stray[0]


def test_a_production_marked_test_in_a_generic_suite_directory_is_an_ownership_error(tmp_path):
    """`tests/api/` is a suite directory, not an application. The diagnostic must say
    the test belongs to no application rather than inventing an app called "api"."""
    _app(tmp_path, "live_app", '{"production_target": true}')
    _test_file(tmp_path, "api/test_contract.py", marked=True)

    declared, _ = production_apps(tmp_path)
    stray = _stray_production_tests(tmp_path, declared)

    assert len(stray) == 1
    assert "tests/api/test_contract.py::test_test_contract_case" in stray[0]
    assert "belongs to no application" in stray[0]
    assert "apps/api" not in stray[0]


def test_a_root_level_production_marked_test_is_an_ownership_error(tmp_path):
    """A framework-level test file is not an application either, and must not be
    reported as an application named after the file."""
    _app(tmp_path, "live_app", '{"production_target": true}')
    _test_file(tmp_path, "test_logger.py", marked=True)

    declared, _ = production_apps(tmp_path)
    stray = _stray_production_tests(tmp_path, declared)

    assert len(stray) == 1
    assert "tests/test_logger.py::test_test_logger_case" in stray[0]
    assert "belongs to no application" in stray[0]
    assert "apps/test_logger.py" not in stray[0]


def test_a_declared_app_with_an_unmarked_test_is_reported(tmp_path):
    """The forward direction, through the same helpers the repository-level test
    uses, so it holds for any application rather than only for this repository."""
    _app(tmp_path, "live_app", '{"production_target": true}')
    _test_file(tmp_path, "live_app/smoke/test_marked.py", marked=True)
    _test_file(tmp_path, "live_app/smoke/test_forgotten.py", marked=False)

    declared, _ = production_apps(tmp_path)
    unmarked = [
        line
        for app in sorted(declared)
        for line in _unmarked_tests_under(tmp_path / "tests" / app, tmp_path)
    ]

    assert unmarked == ["  tests/live_app/smoke/test_forgotten.py::test_test_forgotten_case"]
    assert _stray_production_tests(tmp_path, declared) == []
