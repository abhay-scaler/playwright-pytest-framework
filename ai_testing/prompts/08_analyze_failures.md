# Prompt 08 — Analyze a failure

All prompts inherit `ai_testing/README.md` § House rules.

## Purpose

Classify a failure from its evidence and propose the smallest correct next action, without
guessing and without making the failure disappear.

## Required inputs

- The failing test's name and the real command that produced the failure.
- Actual output: the traceback, the assertion message, the Pytest summary.
- The captured evidence: `screenshots/<app>/<test>.png`, `traces/<app>/<test>.zip`,
  `videos/<app>/<test>.webm`, `logs/`, and `reports/pytest_report.html` — all written
  automatically on failure only (`pwpf/plugin.py`).
- The scenario the test implements, and the page objects involved.

## Instructions

1. Quote the actual error first — exception type, message, and the line it came from. If you do
   not have real output, say so and stop; a diagnosis from a described failure is a guess.
2. Classify into exactly one, with the evidence that decides it:
   - **Application defect** — the app behaved differently from an approved expectation.
   - **Automation defect** — selector, waiting, page-object or test logic.
   - **Test-data or session-state issue** — data changed, stock ran out, session carried over.
   - **Environment or network failure** — DNS, TLS, timeout against an external dependency.
   - **Access restriction** — bot challenge, CAPTCHA, OTP, geo or login wall.
   - **Timing or synchronization** — a race the test should wait on properly.
   - **Unknown** — insufficient evidence; name exactly what is missing.
3. State your confidence and what would raise it (open the trace, re-run once headed, check the
   same step in another test).
4. Check whether the test passed before: this framework applies `--reruns 1` globally and an
   app's `retry_count` adds another layer, so a pass on rerun is itself a finding — report it
   rather than treating the run as green.
5. Distinguish an external-dependency failure from a defect in the code under test. A live
   third-party site timing out is the former; `tests/web_search` against `playwright.dev` has
   failed this way before, which is on record in `DESIGN.md` §6.
6. Propose the smallest fix that addresses the cause, and say what evidence would confirm it
   worked. If the cause is an access restriction, the only acceptable proposals are: stop, seek
   authorization, or move the scenario to a sanctioned target. Never a bypass.
7. If the fix would change what the test expects, that is a scenario change needing human
   approval, not a code edit.

## Output format

`<work-item>/failure-analysis.md`:

```
# Failure analysis — <test>, <date>
## Command and actual output
## Classification and confidence
## Evidence used            (each file consulted and what it showed)
## Root cause (or what is missing)
## Proposed action          (smallest first) + how to confirm
## Human decisions needed
```

## Acceptance criteria

- Real output is quoted; nothing is inferred from a paraphrase.
- Exactly one classification, with evidence.
- Reruns and prior passes are reported, not hidden.
- No proposal weakens an assertion, raises a timeout to mask a race, adds a rerun, or bypasses an
  access control.

## Safety constraints

Diagnosis is read-only. Do not re-run a `production`-marked test to reproduce without explicit
authorization, and never repeatedly — a loop of retries against a live site is load.

## Human review

A human accepts the classification before any fix lands, and owns any decision that changes an
expected result or authorizes a production re-run.

## Next step

`09_maintenance.md` for a UI change, or back to `05`/`06` for an automation defect — then `07`.
