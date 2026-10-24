# Prompt 07 — Review the automation

All prompts inherit `ai_testing/README.md` § House rules.

## Purpose

Independently review generated page objects and tests before a human spends time on them, with
the same bar a human-written change would face. Run in a fresh context from prompts 05–06.

## Required inputs

- The diff under review (`git diff` or `git diff --cached`).
- Approved scenarios.
- `<work-item>/locator-evidence.md` and `<work-item>/action-map.md`.
- `<work-item>/repo-analysis.md`.

## Instructions

Review for, in this order:

1. **Assertion quality** — does each test assert the scenario's expected results, or merely that
   actions completed? Could any assertion pass on an error page, an empty state or a bot
   challenge? Name the case.
2. **Locator evidence** — does every selector trace to the evidence file? Any generated class
   name, positional index or marketing string?
3. **Layer boundaries** — assertions only in tests, selectors only in locators, no raw Playwright
   in tests, no URL or timeout literal in a page object, nothing app-specific added to `pwpf/core/`.
4. **Framework reuse** — any reimplementation of something `BasePage`, a fixture, `AppConfig` or
   `pwpf/utils/` already provides? Any component introduced without a stated reason?
5. **Markers and placement** — `production` on every live-site test; `smoke` actually present on
   anything in a `smoke/` folder meant for the gate; module basenames unique across `tests/`.
6. **Determinism** — fixed waits, hard-coded volatile data, ordering assumptions, dependence on
   another test's state, fixture scope wider than it should be.
7. **Isolation and cleanup** — what state does the test leave behind, and is that declared?
8. **Shared-framework blast radius** — does the diff touch `pwpf/`, `pytest.ini`,
   `.github/workflows/ci.yml` or `tests/test_ci_production_exclusion.py`? Each such change needs
   its own justification, and weakening the production exclusion is never acceptable.
9. **Validation evidence** — did the author show real command output? Anything claimed but not
   run is a finding in itself.
10. **Honesty of docstrings and comments** — does any comment claim verification that did not
    happen?

## Output format

`<work-item>/automation-review.md`:

```
# Automation review — <date>, <revision>
## Verdict: approve | changes requested | blocked
## Findings            (table: severity | file:line | finding | proposed fix)
## Validation evidence (commands and whether real output was shown)
## Decisions needed from a human
```

Severities: **blocker** (wrong, unsafe, or hides a failure), **major** (works but violates a
convention or will be flaky), **minor** (style, naming, clarity).

## Acceptance criteria

- Every finding cites `file:line` and names a concrete fix.
- The verdict is one of the three, with no hedging.
- No finding proposes weakening an assertion or a safety control.
- Clean code is said to be clean; manufactured findings waste the reviewer's time as surely as
  missed ones.

## Safety constraints

Review only — change no file. Do not run a `production`-marked test to "check" a finding.

## Human review

The human reviewer owns the merge decision and re-checks any blocker. A finding list is input to
that decision, not a substitute for it.

## Next step

Human review and merge. After a failure in CI or a local run, `08_analyze_failures.md`.
