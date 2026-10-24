# Scenario authoring and governance

A scenario is a design record: the agreed description of one behaviour, stable enough to point at
in a review and in a report. It is not executable. The executable truth is always the Pytest test
named in the scenario's `automation.test` field.

Template: [ai_testing/templates/scenario_template.yaml](../../ai_testing/templates/scenario_template.yaml).
Every value in it is illustrative, and the two example scenarios are not verified Myntra
behaviour.

## Where scenarios will live

`apps/<app>/scenarios/<feature>.yaml` — inside the application package, so an application stays
self-contained and deleting it deletes its catalog, consistent with
[DESIGN.md](../../DESIGN.md) §1. A separate top-level catalog tree is not the plan: it would rot
independently of the app it describes.

**The directory does not exist yet.** Introducing it, with a JSON Schema and validation, is PR 2.
Until then scenarios live in a work item directory under `artifacts/ai-work/`, and the only thing
checking them is a reviewer.

## Identifiers

`<APP>-<AREA>-<NNN>` — for example `MNY-SRCH-001`, `MNY-BAG-002`.

- Assigned once and **never** reused or renumbered. A reordered catalog with stable ids is
  readable history; renumbering silently breaks every reference to it.
- `AREA` is a short functional area (`SRCH`, `PDP`, `BAG`), not a page name — pages get redesigned.
- The id belongs in the test's docstring, so a failure in a report can be traced back by anyone
  reading it. A registered `scenario(id)` marker and a matching Allure label would make that
  traceability machine-checkable; that is **PR 2 work and is not implemented** — today the
  docstring and the `automation.test` field are the whole mechanism, and they go stale unless
  review catches it.

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
nightly cross-browser jobs (`conftest.py:44`, [DESIGN.md](../../DESIGN.md) §8). So promoting a
scenario decides that its test can block a release and will run on three browser engines nightly.
A live-site scenario is never promoted — `-m "not production"` excludes it from every CI
invocation by design.

## Keeping the catalog honest

- A scenario whose test was deleted goes back to `APPROVED`, not left as `IMPLEMENTED`.
- A scenario whose expected result changed is revised and re-approved — never silently edited to
  match what the test now does.
- A scenario that can no longer be verified becomes `BLOCKED` or `DEPRECATED`. A test that passes
  while asserting less than the scenario claims is worse than a missing test, because the report
  says "green".
- Review the catalog when the requirement changes, not when a test fails.
