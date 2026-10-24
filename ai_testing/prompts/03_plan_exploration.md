# Prompt 03 — Plan browser exploration

All prompts inherit `ai_testing/README.md` § House rules.

## Purpose

Produce a short, bounded checklist for a supervised browser session whose only job is to gather
evidence: what the approved scenarios' steps actually look like in the application, and which
locators are defensible. Exploration answers "what does it do", never "what should it do".

## Required inputs

- Approved scenarios (`<work-item>/scenarios-reviewed.yaml`, status `APPROVED`).
- `<work-item>/repo-analysis.md`.
- The target named in each scenario's `environment.target`, and the recorded authorization for it.

## Instructions

1. Restate the target and the authorization in one line. If the target is a live production site
   and no authorization is on record, stop here and say so — the plan is not written.
2. For each approved scenario, list the smallest sequence of observations that would let someone
   implement it: which page, which control, which text or state proves the step happened.
3. For each control, ask for **two** candidate locators and a reason to prefer one: a role or
   accessible name, a stable user-visible attribute (a placeholder, a label), a documented
   public class. Note what makes each fragile — generated class names, positional indexes, text
   that is a marketing string.
4. Call out what must be read at runtime rather than recorded: prices, stock, promotions,
   product ids, result counts.
5. List the interstitials to expect (cookie or consent walls, promo modals, app-install
   banners) and note that `BasePage.dismiss_if_visible` exists for them, driven by a
   `consent_selector` in `extra` if one is needed (`apps/web_search/pages/home_page.py`).
6. Set explicit limits: how many page loads, how long, headed only, one browser, no repeated
   runs. Name the stop conditions — a CAPTCHA, an OTP prompt, an access-denied page, an
   unexpected interstitial, any login wall, anything resembling a checkout step.
7. Say which evidence file each observation lands in and in what form (a selector plus the
   markup it came from, a screenshot path, a copied text string).

## Output format

`<work-item>/exploration-plan.md`:

```
# Exploration plan — <app>, <date>
## Target and authorization
## Limits and stop conditions
## Per-scenario observation checklist
## Locator candidates to confirm
## Values that must be read at runtime
## Evidence to capture, and where it goes
```

## Acceptance criteria

- Every approved scenario has at least one observation entry.
- Every control has two candidate locators with a stated preference.
- Limits and stop conditions are concrete (counts, durations), not "be careful".
- Nothing in the plan would create, mutate or authenticate an account, or approach a checkout.

## Safety constraints

This prompt writes a plan; it does not browse. Execution is a human act: headed, supervised, on
an authorized target, and abandoned at the first stop condition. Never plan around a CAPTCHA,
OTP or access control — encountering one ends the session. Never plan load: no loops, no
parallel sessions, no repeated hammering of a live site.

## Human review

The person who will run the session reads the plan and confirms the target, the authorization and
the limits before opening a browser.

## Next step

`04_convert_codegen.md`, with the recording and notes from the session.
