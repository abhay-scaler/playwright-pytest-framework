# Prompt 04 — Analyze Codegen evidence

All prompts inherit `ai_testing/README.md` § House rules.

## Purpose

Turn a raw recording of a supervised session into two reviewable artifacts: a map from recorded
actions to approved scenario steps, and locator evidence with a recommendation per control. The
recording is evidence and stays temporary; it never becomes the test.

## Required inputs

- The recorded script and any notes or screenshots from the session, under
  `<work-item>/` (git-ignored).
- `<work-item>/exploration-plan.md` and the approved scenarios.
- `<work-item>/repo-analysis.md`.

## Instructions

1. Walk the recording line by line and classify every action: **business intent** (a step a
   scenario names), **navigation**, **state query**, **assertion**, **incidental** (a stray
   click, a scroll, a mis-click corrected later), or **interstitial handling**.
2. Map business-intent actions onto scenario step ids. Report any recorded action that maps to
   nothing — it is either incidental or a missing scenario step, and you must say which.
3. Report every scenario step with no recorded action: that step is unverified.
4. List every assertion the recording contains, and — more importantly — every expected result
   from the scenarios that the recording does **not** check. Codegen records actions, not
   expectations; this list is the main reason this prompt exists.
5. For each control, give: the recorded selector, the markup it came from, one or two
   alternatives, your recommendation, and the risk of each. Prefer role or accessible name, then
   a stable user-visible attribute, then a documented class. Reject generated class names,
   `nth`-style positional selectors, long CSS descendant chains and text that reads like
   marketing copy.
6. Flag every fixed wait, `wait_for_timeout`, `sleep` or arbitrary timeout for deletion, and name
   the state the code should wait for instead (an element visible, a URL, a text change) using
   only methods `BasePage` already has.
7. Flag every value the recording hard-codes that must be read at runtime instead (prices,
   counts, product ids, stock, promotions).
8. Propose, but do not implement, the split: which actions belong in a page object, which in a
   fixture, which stay in the test, and whether an application-local component is justified —
   and if so, why a page object would not do.

## Output format

- `<work-item>/action-map.md`: a table `recorded action | classification | scenario step | note`,
  followed by **Unmapped actions**, **Unverified steps** and **Missing assertions**.
- `<work-item>/locator-evidence.md`: per control, a table `candidate | evidence (markup) |
  stability risk | recommended?`.

## Acceptance criteria

- Every recorded line is classified.
- Every missing assertion is listed explicitly.
- Every recommended locator has evidence quoted from the recording or the page, not a guess.
- Every fixed wait is flagged with the state to wait for instead.
- No code is written in this step.

## Safety constraints

Work only from the captured evidence; do not open a browser to fill a gap — record the gap. Never
copy a cookie, token, `storage_state` or personal data out of the recording into an artifact:
redact it and note that you did. Discard the raw recording once the evidence files are reviewed;
it is not a runtime dependency.

## Human review

A reviewer checks two locator recommendations against the quoted evidence, and confirms the
missing-assertion list is complete enough to implement against.

## Next step

`05_implement_page_objects.md`.
