# Feature brief: <feature name>

A feature brief is the **source of truth for expected behaviour**. An assistant may draft
scenarios from it, but may never invent what this file leaves unanswered — anything missing comes
back as a question, not a guess. Copy this file into your work item directory
(`artifacts/ai-work/<YYYYMMDD>-<slug>/feature-brief.md`) and fill it in before running
`ai_testing/prompts/01_generate_scenarios.md`.

Delete the guidance in parentheses as you go. Leave a heading in place with "unknown" rather than
removing it: an empty section is information.

- **Application**: <the `apps/<app>/` package this belongs to>
- **Author**: <who owns the expectations in this document>
- **Date**: <YYYY-MM-DD>
- **Status**: draft | reviewed

## Objective

(One or two sentences on the business outcome being verified. Not a list of UI steps.)

## In scope

(The user-visible capabilities this brief covers, as bullets.)

## Out of scope

(What a reader might reasonably assume is included but is not — be explicit. For the current
pilot this always includes checkout, payment, order placement and account creation.)

## Business rules and expected behaviour

(The rules a test can assert against, each one checkable. "Searching for a term shows products
whose title or brand matches it" is a rule; "search works" is not. Where a rule is a guess rather
than a stated requirement, mark it `[A]` so review can catch it.)

## Test data

(What the test needs, and where it comes from: a fixture file, a factory, a constant, a value
read at runtime. Say which values are safe to hard-code and which are inventory-, price- or
promotion-dependent and therefore must not be.)

## Environment and execution constraints

- **Target**: (local fixture app | sanctioned practice site | live production site)
- **Side effects**: (does any step change server-side or session state? Adding an item to a bag
  does.)
- **Authorization**: (who approved running this against the named target, and when)
- **CI eligibility**: (may this become a CI gate? A live third-party site may not — see
  [DESIGN.md](../../DESIGN.md) §8.)

## Acceptance criteria

(How we will know the feature is adequately covered: which scenarios must exist and pass, which
evidence must accompany them.)

## Known risks

(Flakiness sources, access restrictions, anti-automation defences, data dependencies, timing.)

## Open questions

(Each one blocking or non-blocking, and who can answer it. These become `NEEDS_CLARIFICATION`
scenarios rather than assumptions baked into an assertion.)
