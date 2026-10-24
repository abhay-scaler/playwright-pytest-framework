# The workflow

Twelve stages from a feature idea to a maintained test. Each has inputs, outputs, an owner and a
completion criterion, because the common failure of AI-assisted testing is not a bad suggestion —
it is a stage that was skipped, so the next one had nothing real to stand on.

"Assistant" means a coding assistant driven by a prompt from
[ai_testing/](../../ai_testing/README.md). "Human" means a named person who is accountable for
the decision. Where both appear, the assistant drafts and the human decides.

## Stages

| # | Stage | Owner | Inputs | Outputs | Done when |
|---|---|---|---|---|---|
| 1 | Repository analysis | assistant (prompt 00) | the repository | `repo-analysis.md` | citations spot-checked and resolving; absences listed |
| 2 | Feature brief | **human** | the requirement, the business rules | `feature-brief.md` | every section answered or explicitly "unknown"; scope and target stated |
| 3 | Scenario generation | assistant (01) | brief, repo analysis | `scenarios-draft.yaml` + rationale | every scenario traces to a brief rule; inferences labelled `[A]`; status `DRAFT` |
| 4 | Independent scenario review | assistant (02), fresh context | brief, draft | `scenario-review.md`, `scenarios-reviewed.yaml` | findings each name an id and an action; decisions list is answerable; status `AI_REVIEWED` |
| 5 | Human approval | **human** | review + draft | approved scenarios | every expected result confirmed by a person; `[?]` resolved or scenario parked; `APPROVED` recorded with name and date |
| 6 | Browser exploration | assistant plans (03), **human runs** | approved scenarios | `exploration-plan.md`, recording, notes, screenshots | plan's observations captured, or the session's stop reason recorded |
| 7 | Codegen evidence analysis | assistant (04) | recording and notes | `action-map.md`, `locator-evidence.md` | every recorded line classified; missing assertions and unverified steps listed; locators carry quoted evidence |
| 8 | Page-object and component design | assistant (05) | evidence, approved scenarios | locators, page objects, fixtures, config | selectors cite evidence; no assertion or literal in a page object; Ruff/Black/mypy clean with real output |
| 9 | Pytest implementation | assistant (06) | page objects, scenarios | tests under `tests/<app>/` | one test per scenario asserting every expected result; markers correct; unique module basename; collection output shown |
| 10 | Static and runtime validation | assistant runs, **human reads** | the diff | command output | the commands below actually ran, output pasted, failures included |
| 11 | Human review and merge | **human** (assistant pre-reviews with 07) | diff, evidence, output | merged change | checklist passed; blockers resolved; no safety control weakened |
| 12 | Failure analysis and maintenance | assistant (08, 09), **human** decides | failure evidence, change notes | `failure-analysis.md`, `impact-analysis.md`, patch | failure classified from real evidence; expectation changes approved by a human; coverage effect stated |

Stages 3–4 and 7–9 are where an assistant adds most. Stages 2, 5 and 11 are where a human cannot
be replaced: they are the stages that decide what "correct" means and what enters the repository.

## Deterministic checks versus judgments

Keep these apart when reading any assistant output. One kind can be trusted because a machine
produced it; the other is an opinion, however fluent.

**Deterministic** — reproducible, pass/fail, the same for everyone:

- `ruff check .`, `black --check .`, `mypy .`
- `pytest --collect-only` (what is collected, what a `-m` expression deselects)
- a real test run, and the screenshot, trace and video it captures on failure
- `tests/test_ci_production_exclusion.py` — the CI exclusion, the marker registration, and that
  every test in a production-only app carries the marker
- marker registration under `--strict-markers`

**Judgment** — an assistant's proposal, requiring a human:

- whether a scenario set covers the risk
- whether an expected result is right (only the brief's author can say)
- whether a locator is stable enough
- whether a failure is an application defect or an automation defect
- whether a test is worth its maintenance cost

The rule that follows: a judgment may never be reported as a verified fact, and a deterministic
result may never be reported without having run the command. See
[ai_testing/README.md § House rules](../../ai_testing/README.md#house-rules), rules 2 and 4.

## Validation commands

What stage 10 means, concretely. These are the framework's own commands; nothing here adds any.

```bash
ruff check . && black --check . && mypy .          # quality gates, also CI's first job
pytest tests/test_*.py -m "not production" -q      # framework self-tests, no browser
pytest --collect-only -q -m "not production"       # confirm live-site tests are deselected
pytest -m "smoke and not production" -n auto -q    # what the PR gate runs
pytest -m "not production" -n auto -q              # what the regression job runs
```

A `production`-marked test is not part of validation. It runs locally, headed, supervised, on an
authorized machine, and its result is reported as what it is: a local observation, not a gate.

## Where an assistant may not go

- It does not approve a business expectation (stage 5).
- It does not merge its own change (stage 11).
- It does not promote a scenario to `ACTIVE_REGRESSION` — in this framework, collected tests run
  automatically in CI, so that promotion decides what can block a release.
- It does not authorize or initiate a run against a live production site.
- It does not edit `core/`, the root `conftest.py`, `pytest.ini`, the CI workflow or
  `tests/test_ci_production_exclusion.py` as a side effect of adding a test. Shared-framework
  changes are proposed separately, with a reason.
- It does not weaken an assertion, add a sleep, raise a timeout or add a rerun to turn a failure
  green.

## When orchestration would be justified

A CLI that chains these prompts, calls an LLM provider and files the artifacts is a plausible
PR 5. It is deliberately not built yet, because its value depends on facts this team does not
have: whether the manual process produces work worth repeating. Build it only with evidence from
the pilot on each of these:

1. **Measured effort.** Hours from brief to approved scenarios, and from approved scenario to
   merged test, over at least a handful of real features — compared against a baseline measured
   the same way. Without a baseline, any improvement is a feeling.
2. **Artifact quality.** What share of generated scenarios survived review unchanged; what share
   of generated tests merged with only minor edits. A low share means orchestrating the process
   would mostly automate rework.
3. **Repeatability.** Whether a second engineer, following only the committed docs and prompts,
   reaches a comparable result. If the process needs its author present, automating it hides the
   dependency rather than removing it.
4. **Failure recovery.** Whether failures were classified correctly from evidence, and how often
   a proposed fix was accepted. An orchestrator that loops on bad diagnoses is worse than no
   orchestrator.
5. **Maintenance overhead.** What a UI change actually cost in engineering time, and whether
   prompt revisions kept their quality — prompts drift, and a drifted prompt inside an automated
   loop is a quiet quality regression.

Two constraints apply whenever it is built: its dependencies stay out of
`requirements.in`/`requirements.txt`, which every CI job installs, and no configuration key in it
may be presented as a safety control unless executable code enforces that key. A YAML file
containing `allow_order_placement: false` that nothing reads is documentation; treating it as
protection is worse than having nothing, because reviewers will cite it.

Metrics that need run history — first-run success rate, flaky rate, mean time to diagnose — need
somewhere to keep that history first. CI uploads JUnit XML and Allure results per run as
artifacts, but nothing retains or renders them over time
([README.md § Known Limitations](../../README.md#known-limitations)), so those three cannot be
measured today.
