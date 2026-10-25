# Scenario authoring and governance

A scenario is a design record: the agreed description of one behaviour, stable enough to point at
in a review and in a report. It is not executable. The executable truth is always the Pytest test
named in the scenario's `automation.test` field.

Template: [ai_testing/templates/scenario_template.yaml](../../ai_testing/templates/scenario_template.yaml).
Schema: [pwpf/ai_testing/schemas/scenario.schema.json](../../pwpf/ai_testing/schemas/scenario.schema.json).
Every value in the template is illustrative, and its example scenarios are not verified Myntra
behaviour.

## Where scenarios live

`apps/<app>/scenarios/<feature>.yaml` — inside the application package, so an application stays
self-contained and deleting it deletes its catalog, consistent with
[DESIGN.md](../../DESIGN.md) §1. There is deliberately no top-level catalog tree: it would rot
independently of the app it describes.

One file covers one feature, and its `meta.feature` must match every scenario's `feature`.
`meta.app` must match the `apps/<app>/` package the file sits in. Drafts still being written
belong in a work item directory under `artifacts/ai-work/`; a file committed under
`apps/*/scenarios/` is validated on every CI run, so committing it is itself a small
commitment.

Today's catalog: [apps/myntra/scenarios/shopping_journey.yaml](../../apps/myntra/scenarios/shopping_journey.yaml)
— one scenario describing the committed homepage test and awaiting human review, plus three
explicitly illustrative drafts.

## Identifiers

`<APP>-<AREA>-<NNN>` — for example `MNY-SRCH-001`, `MNY-BAG-002`.

- Assigned once and **never** reused or renumbered. A reordered catalog with stable ids is
  readable history; renumbering silently breaks every reference to it.
- `AREA` is a short functional area (`SRCH`, `PDP`, `BAG`), not a page name — pages get redesigned.
- The id travels with the test as a marker, and the catalog points back at the test:

  ```python
  @pytest.mark.smoke
  @pytest.mark.ui
  @pytest.mark.production
  @pytest.mark.scenario("MNY-HOME-001")
  def test_home_page_loads_successfully(page, app_config):
      ...
  ```

  `scenario(id)` is registered in [pytest.ini](../../pytest.ini) (so `--strict-markers` accepts
  it) and `pwpf/plugin.py` attaches each id as an Allure label named `scenario`, beside
  the existing `application`, `browser` and `environment` labels — de-duplicated, because one
  test may legitimately carry the marker more than once. A report row can therefore be traced
  to the scenario it implements, and `python -m pwpf.ai_testing.validate_catalog` fails if the
  marker and the catalog disagree.
- A scenario is implemented by **exactly one** test. One test may cover several scenarios (one
  marker per id); two tests claiming the same id is an error.
- `automation.test` is a node id without parameters:
  `tests/<app>/<suite>/<module>.py::<function>`.

## Fields that are usually got wrong

- **`title`** names the outcome, not the clicks. "A product added to the bag appears in the bag"
  — not "click add to bag".
- **`expected_results`** must be able to fail. "The page loads" cannot. Each entry traces to a
  rule in the brief; anything inferred is labelled `[A]` and needs a human before it becomes an
  assertion.
- **`test_data`** names its source, and anything inventory-, price-, promotion- or time-dependent
  is resolved at runtime rather than written down. A hard-coded product id is a scheduled failure.
- **`environment.side_effects`** is where honesty costs something. Adding an item to a bag mutates
  session state on a live site; saying `none` because cleanup is inconvenient is how a suite
  starts corrupting its own preconditions.
- **`environment.ci_eligible`** is `false` for any live third-party target, always
  ([DESIGN.md](../../DESIGN.md) §8).
- **`risk`** is business impact if the behaviour breaks — not how hard the test is to write.

## Statuses

| Status | Meaning |
|---|---|
| `DRAFT` | written, by a human or an assistant; nothing confirmed |
| `AI_REVIEWED` | an independent assistant pass found no blocking issue. **Not approval** |
| `NEEDS_HUMAN_REVIEW` | ready for a person, and waiting on one |
| `NEEDS_CLARIFICATION` | a question must be answered before the expectation can be trusted |
| `APPROVED` | a human confirmed the expected results. Implementation may start |
| `IMPLEMENTED` | a test exists and `automation.test` names it |
| `VALIDATED` | that test ran and its real result was recorded |
| `ACTIVE_REGRESSION` | it is part of the suite that gates changes |
| `BLOCKED` | it cannot be verified today: access restriction, missing environment, absent capability |
| `QUARANTINED` | known unstable; excluded from gating until diagnosed, with the instability documented |
| `DEPRECATED` | no longer applicable; kept for history, with the reason |

## Transitions

```
DRAFT ──> AI_REVIEWED ──> NEEDS_HUMAN_REVIEW ──> APPROVED ──> IMPLEMENTED ──> VALIDATED ──> ACTIVE_REGRESSION
  │            │                   │                                              │               │
  └────────────┴───────────────────┴──> NEEDS_CLARIFICATION ──> (answered) ──> DRAFT             │
                                   └──> BLOCKED ──> (unblocked) ──> APPROVED                      │
                                                                      QUARANTINED <───────────────┤
                                                                      DEPRECATED  <───────────────┘
```

| Transition | Who | Note |
|---|---|---|
| `DRAFT` → `AI_REVIEWED` | assistant | mechanical: the review pass ran and found nothing blocking |
| `AI_REVIEWED` → `NEEDS_HUMAN_REVIEW` | assistant | queueing, not judging |
| anything → `NEEDS_CLARIFICATION` | either | an assistant **must** use this instead of guessing |
| `NEEDS_HUMAN_REVIEW` → **`APPROVED`** | **human** | the expectations become binding here. Name and date recorded |
| `APPROVED` → `IMPLEMENTED` | assistant | `automation.test` names a real test that collects |
| `IMPLEMENTED` → `VALIDATED` | assistant, human reads | requires real output; a `production` test's local run is a local observation, not a gate result |
| `VALIDATED` → **`ACTIVE_REGRESSION`** | **human** | see below |
| anything → `BLOCKED` / `QUARANTINED` / `DEPRECATED` | **human** | each with a reason and a date |
| `QUARANTINED` → `ACTIVE_REGRESSION` | **human** | only after the instability is explained, never after a passing rerun |

Two transitions are consequential enough to call out:

**`APPROVED`** is where an opinion becomes a requirement. Everything downstream — assertions,
failure classifications, impact analyses — treats approved expected results as correct. An
assistant may never set it.

**`ACTIVE_REGRESSION`** is consequential because of how this framework works: application
membership is inferred from a test's path and every collected test runs in CI's regression and
nightly cross-browser jobs (`pwpf/plugin.py:86`, [DESIGN.md](../../DESIGN.md) §8). So promoting a
scenario decides that its test can block a release and will run on three browser engines nightly.
A live-site scenario is never promoted — `-m "not production"` excludes it from every CI
invocation by design.

## Validation

```bash
pip install -r requirements-ai.txt        # once: PyYAML + jsonschema, pinned apart from the
                                          # test-runtime lock that every CI test job installs
python -m pwpf.ai_testing.validate_catalog     # every catalog under apps/*/scenarios/
python -m pwpf.ai_testing.validate_catalog --root .
```

Static analysis only: it parses YAML, validates against the JSON Schema, applies the
cross-field rules below, and reads `tests/` as an AST. It never imports a test, starts a
browser or opens a socket, and it never executes a scenario. CI runs it in its own
`Scenario Catalog` job, which installs `requirements-ai.txt` and nothing else; the self-tests
in [tests/test_scenario_catalog.py](../../tests/test_scenario_catalog.py) skip when those two
packages are absent.

**Two things are documented in this one section, and they belong to different halves of the
repository** ([docs/documentation-split-plan.md](../documentation-split-plan.md) §4.1, decision 4).
The rule table immediately below describes **framework behaviour**: the codes come from
`pwpf/ai_testing/validate_catalog.py`, they change when that validator changes, and they would
follow it into a framework repository. Everything else in this document — the statuses, the
transition table, who may set `APPROVED`, what a catalog must record — is **this project's
governance**, and stays here whatever happens to the framework. The table is reproduced rather
than owned: the validator is authoritative, and a disagreement between the two is a bug in this
page.

Each finding names the rule it broke, the file and — where it can be identified — the scenario:

| Rule | Fails when |
|---|---|
| `E-YAML` | the file is not valid YAML, or is empty |
| `E-SCHEMA` | a schema violation: missing field, wrong type, bad enum, or an **unknown key** (the schema sets `additionalProperties: false`, so a misspelling fails instead of being ignored) |
| `E-VERSION` | `schema_version` is not a supported version (today: `1.0`) |
| `E-APP` | `meta.app` does not match the owning `apps/<app>/` package, or that package does not exist |
| `E-FEATURE` | a scenario's `feature` does not match `meta.feature` |
| `E-DUPLICATE` | a scenario id appears more than once, in any catalog in the repository |
| `E-MAPPING` | `automation.implemented` and `automation.test` disagree |
| `E-LIFECYCLE` | `IMPLEMENTED`, `VALIDATED` or `ACTIVE_REGRESSION` without an implementing test |
| `E-APPROVAL` | `APPROVED` or later without `review.approved_by` **and** `review.approved_date` |
| `E-HISTORY` | the last `status_history` entry does not record the current status |
| `E-MARKER` | `automation.markers` names a marker that `pytest.ini` does not register |
| `E-PRODUCTION` | a `live-production` scenario is `ci_eligible`, lacks `authorization_required`, omits the `production` marker, or its test lacks `@pytest.mark.production` |
| `E-REGRESSION` | `ACTIVE_REGRESSION` without `ci_eligible: true`, or on a production-marked scenario (which CI excludes by design) |
| `E-TRACE` | `automation.test` names no real test function, the test lacks the matching `scenario` marker, two tests claim one scenario, or the two sides name different tests |
| `E-ORPHAN` | a test is marked with a scenario id no catalog defines |

`DRAFT`, `AI_REVIEWED`, `NEEDS_HUMAN_REVIEW`, `NEEDS_CLARIFICATION` and `BLOCKED` scenarios are
not required to have a test, by design: the catalog is where coverage is planned, not only
recorded.

**What this does and does not enforce** — and the line here is the same ownership line. The
validator (framework) checks that the record is *consistent*; whether the record is *true* is this
project's governance, which no amount of framework code can settle. It enforces consistency: a status that claims approval
must carry an approval record, a mapping must point at a real marked test, a live-site scenario
cannot claim CI eligibility. It cannot enforce that the recorded approval is genuine — a name
and a date in YAML are only as true as the review that produced them, and anyone with commit
access can type them. That part stays human, and the check exists to make skipping it visible
rather than impossible.

## Keeping the catalog honest

- A scenario whose test was deleted goes back to `APPROVED`, not left as `IMPLEMENTED`.
- A scenario whose expected result changed is revised and re-approved — never silently edited to
  match what the test now does.
- A scenario that can no longer be verified becomes `BLOCKED` or `DEPRECATED`. A test that passes
  while asserting less than the scenario claims is worse than a missing test, because the report
  says "green".
- Review the catalog when the requirement changes, not when a test fails.
