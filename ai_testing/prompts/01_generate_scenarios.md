# Prompt 01 — Generate scenarios

All prompts inherit `ai_testing/README.md` § House rules.

## Purpose

Turn a human-written feature brief into a draft scenario catalog: risk-ordered, reviewable, and
explicit about what is assumed. This produces a design artifact, not tests, and not approval.

## Required inputs

- `<work-item>/feature-brief.md`, filled in from `ai_testing/templates/feature_brief.md`.
- `<work-item>/repo-analysis.md` from prompt 00.
- `ai_testing/templates/scenario_template.yaml` for the shape and the ID scheme.

## Instructions

1. Derive scenarios **only** from the brief. Where the brief is silent, raise a
   `blocking_questions` entry and set that scenario's `status` to `NEEDS_CLARIFICATION` — never
   fill the gap from the application's current behaviour or from general knowledge of how such
   sites usually work.
2. Order by risk: what would hurt the business most if it broke, not what is easiest to automate.
   Cover the primary happy path first, then the variations the brief names, then boundaries and
   negative cases the brief's rules imply.
3. For each scenario give: a stable `id` following `meta.id_scheme`, a title naming the outcome
   (not the clicks), `priority`, `risk`, `preconditions`, `test_data` with its source, `steps` as
   user intent, `expected_results` that are checkable, and the `requirement` it traces to.
4. Mark every expected result you inferred rather than read in the brief with `[A]`.
5. Fill `environment` honestly: `target`, whether a step has `side_effects`, whether
   authorization is required, and `ci_eligible: false` for any live third-party target.
6. Set `automation.test: null` and `implemented: false`. You are not writing tests here.
7. Set every `status` to `DRAFT` (or `NEEDS_CLARIFICATION`). Do not use `AI_REVIEWED`, which
   prompt 02 assigns, and never `APPROVED`.
8. Stop at the coverage the brief justifies. Twelve thin scenarios are worse than four that
   assert something a human agreed to.

## Output format

Valid YAML in the template's shape (and the schema's: `pwpf/ai_testing/schemas/scenario.schema.json`,
`schema_version: "1.0"`), saved as `<work-item>/scenarios-draft.yaml` — a draft stays in the
work item directory, not under `apps/*/scenarios/`, until a human approves it. Plus a short
Markdown note `<work-item>/scenarios-rationale.md` covering: risk ordering, what you chose not to
cover and why, and every `[A]`/`[?]` in one list.

## Acceptance criteria

- The YAML parses and every scenario has every field the template shows.
- IDs are unique, follow the scheme, and nothing is renumbered from a previous draft.
- Each `expected_results` entry is checkable by a person reading it, and traces to a brief
  heading.
- No scenario describes checkout, payment, order placement or account creation.
- No scenario is `APPROVED` or `ACTIVE_REGRESSION`.

## Safety constraints

No browser, no network, no code. Do not open the application to "check" an expectation — that
inverts the source of truth (House rule 6).

## Human review

The brief's author confirms each expected result, resolves `[?]` items, and either approves or
sends scenarios back. Approval is a human act recorded in `review.status_history`.

## Next step

`02_review_scenarios.md` — review by a separate pass, before any human approval.
