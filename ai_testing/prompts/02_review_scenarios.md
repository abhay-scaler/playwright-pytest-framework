# Prompt 02 — Review scenarios

All prompts inherit `ai_testing/README.md` § House rules.

## Purpose

Independently critique a scenario draft for completeness, testability and honesty, and hand a
human a short list of decisions rather than a wall of YAML. This is a second pass, not a
rubber stamp: run it in a fresh context from prompt 01's, with the brief and the draft as the
only inputs.

## Required inputs

- `<work-item>/feature-brief.md`.
- `<work-item>/scenarios-draft.yaml`.
- `<work-item>/scenarios-rationale.md`.

## Instructions

Review against these questions and report findings, not rewrites, first:

1. **Traceability** — does every scenario trace to a brief rule? Is any brief rule uncovered?
2. **Testability** — can each expected result fail? An expectation nothing could violate
   ("the page loads") is not a test.
3. **Evidence boundary** — is any expected result actually derived from how the site behaves
   rather than from the brief? Flag it.
4. **Data realism** — are any hard-coded values inventory-, price-, promotion- or
   time-dependent? Those must be resolved at runtime or moved to a fixture.
5. **Side effects** — is every state-mutating step declared, with a cleanup answer?
6. **Scope** — does anything stray into checkout, payment, order placement, authentication or
   account creation?
7. **Marker correctness** — does every live-target scenario carry `production` in
   `automation.markers` and `ci_eligible: false`?
8. **Duplication and overlap** — would two scenarios fail for the same reason? Merge them.
9. **Priority sanity** — is the risk rating about business impact rather than effort?
10. **Honesty** — is every inference labelled `[A]`, every unknown `[?]`?

Then, and only then, produce a revised draft applying the findings that need no human decision
(wording, duplication, markers, labelling). Leave anything that changes an expected business
result as a question — you may not decide it.

## Output format

- `<work-item>/scenario-review.md`: a findings table (`id | severity | finding | proposed
  action`), then **Decisions needed from a human** as a numbered list, each answerable yes/no or
  with one value.
- `<work-item>/scenarios-reviewed.yaml`: the revised draft, statuses moved `DRAFT` →
  `AI_REVIEWED`, except scenarios with open blocking questions, which become
  `NEEDS_CLARIFICATION`.

## Acceptance criteria

- The revised YAML would pass `python -m ai_testing.validate_catalog` once committed: schema,
  id uniqueness, matching `meta.feature`, and no status claiming an approval it does not have.
  Check it by placing the file under `apps/<app>/scenarios/` locally and running the validator;
  if it does not pass, it is not ready for a human.
- Every finding names a scenario `id` and a concrete action.
- No expected business result was changed without a human decision; such changes appear only as
  questions.
- The revised YAML parses, and no ID changed.
- `AI_REVIEWED` is the highest status assigned.

## Safety constraints

No browser, no network, no code, no file outside the work item directory.

## Human review

Mandatory and blocking. A human answers the decisions list, then sets `APPROVED` (or
`NEEDS_CLARIFICATION`/`BLOCKED`) in `review.status_history` with their name and the date.
`AI_REVIEWED` is not approval and never authorizes implementation.

## Next step

`03_plan_exploration.md`, once at least one scenario is `APPROVED`.
