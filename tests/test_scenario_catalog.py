"""Self-tests for the scenario catalog validator.

Every case builds a throwaway repository under `tmp_path` and runs
`validate_catalog` against it, so nothing here touches the committed catalog,
the browser or the network. Two cases at the end do look at the real catalog -
read-only, asserting it is valid and that no scenario claims a live production
site may gate CI.

The module skips entirely when `requirements-ai.txt` is not installed: PyYAML
and jsonschema are deliberately absent from the test-runtime lock, and CI
validates the catalog in its own job instead (see .github/workflows/ci.yml).
"""

from __future__ import annotations

import pytest

from pwpf.ai_testing.validate_catalog import discover_catalogs, validate_catalog
from pwpf.config.paths import project_root

yaml = pytest.importorskip("yaml", reason="requirements-ai.txt is not installed")
pytest.importorskip("jsonschema", reason="requirements-ai.txt is not installed")

PYTEST_INI = """[pytest]
testpaths = tests
markers =
    smoke: quick smoke tests
    ui: browser UI tests
    api: API-oriented tests
    regression: regression coverage
    production: drives a live third-party production site
    scenario(id): catalog scenario this test implements
"""

TEST_MODULE = """import pytest


@pytest.mark.ui
@pytest.mark.production
@pytest.mark.scenario("MNY-HOME-001")
def test_home_page_loads_successfully(page, app_config):
    pass
"""


def _scenario(**overrides):
    """A scenario that validates cleanly; override one field per case."""
    scenario = {
        "id": "MNY-HOME-001",
        "title": "The homepage renders its own header search bar",
        "feature": "shopping_journey",
        "priority": "P1",
        "risk": "high",
        "status": "DRAFT",
        "requirement": "FB-SHOP-00",
        "preconditions": ["The site is reachable"],
        "test_data": {"source": "no test data required"},
        "steps": ["Open the homepage"],
        "expected_results": ["The header search bar is present"],
        "environment": {
            "target": "live-production",
            "side_effects": "none",
            "authorization_required": True,
            "ci_eligible": False,
        },
        "automation": {"test": None, "markers": ["ui", "production"], "implemented": False},
        "review": {
            "approved_by": None,
            "approved_date": None,
            "status_history": [{"status": "DRAFT", "by": "assistant", "date": "2026-10-24"}],
        },
    }
    scenario.update(overrides)
    return scenario


def _document(*scenarios, app="myntra", feature="shopping_journey"):
    return {
        "schema_version": "1.0",
        "meta": {
            "app": app,
            "feature": feature,
            "owner": "QA automation",
            "updated": "2026-10-24",
        },
        "scenarios": list(scenarios),
    }


def _repo(tmp_path, catalogs=None, raw_catalogs=None, tests=None, app="myntra"):
    """A minimal repository: pytest.ini, an app package, catalogs and tests.

    `catalogs` maps a file name to a document that is dumped as YAML;
    `raw_catalogs` maps a file name to literal text (for malformed YAML);
    `tests` maps a path under tests/ to module source.
    """
    (tmp_path / "pytest.ini").write_text(PYTEST_INI, encoding="utf-8")
    app_dir = tmp_path / "apps" / app
    (app_dir / "scenarios").mkdir(parents=True)
    (app_dir / "__init__.py").write_text("", encoding="utf-8")

    for name, document in (catalogs or {}).items():
        (app_dir / "scenarios" / name).write_text(yaml.safe_dump(document), encoding="utf-8")
    for name, text in (raw_catalogs or {}).items():
        (app_dir / "scenarios" / name).write_text(text, encoding="utf-8")
    for relative, source in (tests or {}).items():
        path = tmp_path / "tests" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
    return tmp_path


def _rules(findings):
    return sorted({finding.rule for finding in findings})


def _messages(findings):
    return "\n".join(str(finding) for finding in findings)


def test_a_valid_catalog_produces_no_findings(tmp_path):
    findings = validate_catalog(_repo(tmp_path, catalogs={"shopping.yaml": _document(_scenario())}))
    assert findings == [], _messages(findings)


def test_a_missing_required_field_is_rejected(tmp_path):
    scenario = _scenario()
    del scenario["risk"]
    findings = validate_catalog(_repo(tmp_path, catalogs={"shopping.yaml": _document(scenario)}))
    assert _rules(findings) == ["E-SCHEMA"], _messages(findings)
    assert "risk" in _messages(findings)
    assert findings[0].scenario_id == "MNY-HOME-001"


def test_an_unknown_field_is_rejected(tmp_path):
    # A misspelling must fail rather than being silently ignored - the whole
    # reason the schema sets additionalProperties: false.
    findings = validate_catalog(
        _repo(tmp_path, catalogs={"shopping.yaml": _document(_scenario(priorty="P1"))})
    )
    assert _rules(findings) == ["E-SCHEMA"], _messages(findings)
    assert "priorty" in _messages(findings)


def test_malformed_yaml_is_reported_with_the_path(tmp_path):
    findings = validate_catalog(
        _repo(tmp_path, raw_catalogs={"broken.yaml": "scenarios:\n  - id: [unclosed\n"})
    )
    assert _rules(findings) == ["E-YAML"], _messages(findings)
    assert findings[0].path == "apps/myntra/scenarios/broken.yaml"


def test_an_empty_catalog_file_is_reported(tmp_path):
    findings = validate_catalog(_repo(tmp_path, raw_catalogs={"empty.yaml": "\n"}))
    assert _rules(findings) == ["E-YAML"], _messages(findings)


def test_duplicate_scenario_ids_are_rejected_across_files(tmp_path):
    findings = validate_catalog(
        _repo(
            tmp_path,
            catalogs={
                "shopping.yaml": _document(_scenario()),
                "other.yaml": _document(_scenario(), feature="shopping_journey"),
            },
        )
    )
    assert "E-DUPLICATE" in _rules(findings), _messages(findings)
    assert "MNY-HOME-001" in _messages(findings)


def test_an_invalid_lifecycle_status_is_rejected(tmp_path):
    findings = validate_catalog(
        _repo(
            tmp_path,
            catalogs={"shopping.yaml": _document(_scenario(status="ALMOST_APPROVED"))},
        )
    )
    assert "E-SCHEMA" in _rules(findings), _messages(findings)
    assert "ALMOST_APPROVED" in _messages(findings)


def test_approved_status_requires_a_human_approval_record(tmp_path):
    approved = _scenario(
        status="APPROVED",
        review={
            "approved_by": None,
            "approved_date": None,
            "status_history": [{"status": "APPROVED", "by": "assistant", "date": "2026-10-24"}],
        },
    )
    findings = validate_catalog(_repo(tmp_path, catalogs={"shopping.yaml": _document(approved)}))
    assert "E-APPROVAL" in _rules(findings), _messages(findings)


def test_an_implemented_status_without_a_test_mapping_is_rejected(tmp_path):
    implemented = _scenario(
        status="IMPLEMENTED",
        review={
            "approved_by": "A Reviewer",
            "approved_date": "2026-10-24",
            "status_history": [{"status": "IMPLEMENTED", "by": "A Reviewer", "date": "2026-10-24"}],
        },
    )
    findings = validate_catalog(_repo(tmp_path, catalogs={"shopping.yaml": _document(implemented)}))
    assert "E-LIFECYCLE" in _rules(findings), _messages(findings)


def test_a_mapping_to_a_nonexistent_test_is_rejected(tmp_path):
    mapped = _scenario(
        automation={
            "test": "tests/myntra/smoke/test_missing.py::test_nothing",
            "markers": ["ui", "production"],
            "implemented": True,
        }
    )
    findings = validate_catalog(_repo(tmp_path, catalogs={"shopping.yaml": _document(mapped)}))
    assert "E-TRACE" in _rules(findings), _messages(findings)
    assert "does not match any collected test" in _messages(findings)


def test_a_mapped_test_must_carry_the_scenario_marker(tmp_path):
    mapped = _scenario(
        automation={
            "test": "tests/myntra/smoke/test_home.py::test_home_page_loads_successfully",
            "markers": ["ui", "production"],
            "implemented": True,
        }
    )
    unmarked = TEST_MODULE.replace('@pytest.mark.scenario("MNY-HOME-001")\n', "")
    findings = validate_catalog(
        _repo(
            tmp_path,
            catalogs={"shopping.yaml": _document(mapped)},
            tests={"myntra/smoke/test_home.py": unmarked},
        )
    )
    assert "E-TRACE" in _rules(findings), _messages(findings)
    assert "pytest.mark.scenario" in _messages(findings)


def test_a_complete_mapping_validates(tmp_path):
    mapped = _scenario(
        automation={
            "test": "tests/myntra/smoke/test_home.py::test_home_page_loads_successfully",
            "markers": ["ui", "production"],
            "implemented": True,
        }
    )
    findings = validate_catalog(
        _repo(
            tmp_path,
            catalogs={"shopping.yaml": _document(mapped)},
            tests={"myntra/smoke/test_home.py": TEST_MODULE},
        )
    )
    assert findings == [], _messages(findings)


def test_two_tests_claiming_one_scenario_are_rejected(tmp_path):
    mapped = _scenario(
        automation={
            "test": "tests/myntra/smoke/test_home.py::test_home_page_loads_successfully",
            "markers": ["ui", "production"],
            "implemented": True,
        }
    )
    findings = validate_catalog(
        _repo(
            tmp_path,
            catalogs={"shopping.yaml": _document(mapped)},
            tests={
                "myntra/smoke/test_home.py": TEST_MODULE,
                "myntra/ui/test_home_again.py": TEST_MODULE,
            },
        )
    )
    assert "E-TRACE" in _rules(findings), _messages(findings)
    assert "more than one test" in _messages(findings)


def test_a_marker_for_an_unknown_scenario_is_rejected(tmp_path):
    findings = validate_catalog(
        _repo(
            tmp_path,
            catalogs={"shopping.yaml": _document(_scenario(id="MNY-SRCH-001"))},
            tests={"myntra/smoke/test_home.py": TEST_MODULE},
        )
    )
    assert "E-ORPHAN" in _rules(findings), _messages(findings)


def test_unapproved_scenarios_do_not_need_tests(tmp_path):
    drafts = [
        _scenario(id="MNY-SRCH-001", status="DRAFT"),
        _scenario(id="MNY-SRCH-002", status="AI_REVIEWED"),
        _scenario(id="MNY-SRCH-003", status="NEEDS_HUMAN_REVIEW"),
        _scenario(id="MNY-SRCH-004", status="NEEDS_CLARIFICATION"),
        _scenario(id="MNY-SRCH-005", status="BLOCKED"),
    ]
    for scenario in drafts:
        scenario["review"]["status_history"] = [
            {"status": scenario["status"], "by": "assistant", "date": "2026-10-24"}
        ]
    findings = validate_catalog(_repo(tmp_path, catalogs={"shopping.yaml": _document(*drafts)}))
    assert findings == [], _messages(findings)


def test_a_live_production_scenario_cannot_be_declared_ci_eligible(tmp_path):
    eligible = _scenario(
        environment={
            "target": "live-production",
            "side_effects": "none",
            "authorization_required": True,
            "ci_eligible": True,
        }
    )
    findings = validate_catalog(_repo(tmp_path, catalogs={"shopping.yaml": _document(eligible)}))
    assert "E-PRODUCTION" in _rules(findings), _messages(findings)


def test_a_production_scenario_cannot_be_active_regression(tmp_path):
    promoted = _scenario(
        status="ACTIVE_REGRESSION",
        automation={
            "test": "tests/myntra/smoke/test_home.py::test_home_page_loads_successfully",
            "markers": ["ui", "production"],
            "implemented": True,
        },
        review={
            "approved_by": "A Reviewer",
            "approved_date": "2026-10-24",
            "status_history": [
                {"status": "ACTIVE_REGRESSION", "by": "A Reviewer", "date": "2026-10-24"}
            ],
        },
    )
    findings = validate_catalog(
        _repo(
            tmp_path,
            catalogs={"shopping.yaml": _document(promoted)},
            tests={"myntra/smoke/test_home.py": TEST_MODULE},
        )
    )
    assert "E-REGRESSION" in _rules(findings), _messages(findings)


def test_an_unregistered_marker_is_rejected(tmp_path):
    findings = validate_catalog(
        _repo(
            tmp_path,
            catalogs={
                "shopping.yaml": _document(
                    _scenario(
                        automation={
                            "test": None,
                            "markers": ["ui", "production", "nightly"],
                            "implemented": False,
                        }
                    )
                )
            },
        )
    )
    assert "E-MARKER" in _rules(findings), _messages(findings)


def test_meta_app_must_match_the_owning_package(tmp_path):
    findings = validate_catalog(
        _repo(tmp_path, catalogs={"shopping.yaml": _document(_scenario(), app="other_app")})
    )
    assert "E-APP" in _rules(findings), _messages(findings)


def test_an_unsupported_schema_version_is_rejected(tmp_path):
    document = _document(_scenario())
    document["schema_version"] = "2.0"
    findings = validate_catalog(_repo(tmp_path, catalogs={"shopping.yaml": document}))
    assert "E-SCHEMA" in _rules(findings), _messages(findings)
    assert "E-VERSION" in _rules(findings), _messages(findings)


def test_the_committed_catalog_is_valid():
    findings = validate_catalog(project_root())
    assert findings == [], _messages(findings)
    assert discover_catalogs(project_root()), "no catalog files were discovered"


def test_no_committed_scenario_lets_a_live_site_gate_ci():
    """The catalog-side half of the production-exclusion policy. The CI half -
    that every pytest invocation carries -m "not production" - is checked by
    tests/test_ci_production_exclusion.py, which this does not duplicate."""
    for path in discover_catalogs(project_root()):
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        for scenario in document["scenarios"]:
            environment = scenario["environment"]
            if environment["target"] == "live-production":
                assert environment["ci_eligible"] is False, scenario["id"]
                assert scenario["status"] != "ACTIVE_REGRESSION", scenario["id"]
                assert "production" in scenario["automation"]["markers"], scenario["id"]
