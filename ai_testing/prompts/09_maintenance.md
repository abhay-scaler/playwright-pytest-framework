# Prompt 09 — Assess a change and propose a repair

All prompts inherit `ai_testing/README.md` § House rules.

## Purpose

When the application or the framework changes, work out what it breaks and propose the smallest
patch, with the scenario catalog kept honest about what is still covered.

## Required inputs

- What changed: a release note, a diff, a redesigned page, or a framework change.
- The affected tests, page objects and locators.
- The scenarios those tests implement.
- Any failure analysis from prompt 08.

## Instructions

1. Establish the scope of the change from evidence, not from the symptom. A changed header
   affects every page object that touches it.
2. Produce an impact list: for each affected file, what breaks and why — selector gone, flow
   reordered, state no longer observable, expectation no longer true.
3. Separate two questions, and never merge them: *does the automation need updating* (ours to
   fix), and *has the expected behaviour changed* (a human's to decide). A changed expectation is
   a scenario revision needing approval, never a quietly edited assertion.
4. Propose the patch at the lowest layer that fixes it: a locator change where the DOM moved, a
   page-object change where the flow changed, a test change only where the user-visible outcome
   changed. New evidence is required for any new selector — if there is none, the next step is
   exploration (prompt 03), not a guess.
5. Check whether coverage shrank. If a scenario can no longer be verified, propose
   `BLOCKED` or `DEPRECATED` with a reason instead of leaving a test that passes while asserting
   less.
6. For a genuinely unstable test, propose `QUARANTINED` with the instability documented — never
   an extra rerun, a longer timeout or a removed assertion as a stabilization strategy.
7. If the change is in the framework layer, say what every application must do, and keep the
   framework change and the application fixes reviewable separately.
8. Update the scenario catalog in the same patch: `automation.test` references, `status`, and a
   `review.status_history` entry recording what changed and why.

## Output format

- `<work-item>/impact-analysis.md`:

```
# Impact analysis — <change>, <date>
## What changed, and the evidence for it
## Affected files            (table: path | breaks how | layer to fix)
## Automation fixes (ours)
## Expectation changes (human decision required)
## Coverage effect           (scenarios blocked, deprecated, quarantined)
## Proposed patch            (smallest first)
```

- The patch itself, as repository changes, with the real output of `ruff check .`,
  `black --check .`, `mypy .` and the relevant non-production Pytest run.

## Acceptance criteria

- Every affected file is named, with the layer that should absorb the change.
- Expectation changes are listed separately and left for a human.
- No new selector without evidence; no stabilization by retry, sleep or removed assertion.
- Coverage changes are stated, including what is no longer verified.
- Command output is real.

## Safety constraints

No live-site run without authorization. Do not touch the production exclusion or its regression
test to make a change fit. Framework-layer edits need their own justification (House rule 7).

## Human review

A human approves any expectation change and any scenario status change, and merges. Quarantine
and deprecation are human decisions with a date and a reason.

## Next step

`07_review_automation.md` on the resulting diff.
