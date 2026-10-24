# Review checklist

For a human reviewing anything an assistant produced. Prompt 07 runs a pass of this first, which
makes the list shorter to work through — it does not make it optional, and an assistant's
"approve" verdict is one more input, not a signature.

A principle before the boxes: **evidence beats assertion.** "Ruff passes" is not evidence; the
pasted output of `ruff check .` is. A review that accepts claims instead of output is where
AI-assisted work goes wrong, because the claims are always fluent.

## Scenario completeness and traceability

- [ ] Every scenario traces to a rule in the feature brief, and no brief rule is uncovered.
- [ ] Every expected result could actually fail.
- [ ] No expected result was derived from the application's current behaviour.
- [ ] Inferences are labelled `[A]`, open questions `[?]`; neither is hiding in prose.
- [ ] Ids follow the scheme, are unique, and nothing was renumbered.
- [ ] `python -m ai_testing.validate_catalog` passes, with its real output shown — schema,
      lifecycle rules, id uniqueness and test mappings.
- [ ] Any new or changed catalog file sits in `apps/<app>/scenarios/`, with `meta.app` and
      `meta.feature` matching.
- [ ] Status is honest: nothing `APPROVED` that a human did not approve, nothing
      `ACTIVE_REGRESSION` without a deliberate decision. `review.approved_by` names a real
      person who really confirmed the expected results — the validator checks the field is
      filled, not that the review happened.
- [ ] `review.status_history` records the transition, with who and when.
- [ ] Volatile data (price, stock, promotion, product id, result count) is resolved at runtime,
      not hard-coded.
- [ ] `environment.side_effects` is accurate, with a cleanup answer where it is not `none`.
- [ ] `ci_eligible: false` on every live third-party target.

## Locator evidence

- [ ] Every selector has a comment citing the markup or observation that justifies it.
- [ ] No generated class name, positional `nth` selector, long descendant chain, or marketing
      string as a hook.
- [ ] Known-fragile selectors are labelled as such rather than quietly accepted.
- [ ] Selectors live in `apps/<app>/locators/`, not inline in a page object or test.

## Page-object boundaries

- [ ] No `assert` or `expect` in a page object.
- [ ] No URL or timeout literal: `self.config.base_url`, `self.config.action_timeout`.
- [ ] Only methods `BasePage` already provides, or a separately justified proposal to add one.
- [ ] Nothing app-specific added to `core/`.
- [ ] State exposed as a value or a `Locator` so the test can use auto-retrying `expect`.
- [ ] A component, if introduced, has a stated reason and is documented.
- [ ] `__init__.py` present for a new app package, matching every other app.

## Assertion quality

- [ ] Every approved expected result is asserted — the whole list, not the convenient half.
- [ ] No assertion that would pass on an error page, an empty state or a bot challenge.
- [ ] Exact strings only where the string is genuinely stable; a regex on a stable fragment
      otherwise.
- [ ] No assertion was weakened, deleted or `xfail`ed to get a green run.
- [ ] A test that only performs actions is rejected.

## Test isolation

- [ ] No dependence on another test's state or ordering.
- [ ] Fixture scopes no wider than needed; `app_config` is session-scoped by convention, browser
      state is not.
- [ ] State-mutating steps declare what is cleaned up and what is not.
- [ ] No `time.sleep`, no `wait_for_timeout`, no arbitrary timeout bump.
- [ ] Module basename is unique across `tests/` — a duplicate breaks collection for the whole
      suite.
- [ ] Markers correct: `ui`/`api` as applicable, `smoke` if it belongs in the gate, `production`
      on every live-site test. Markers select suites; folders do not.
- [ ] `@pytest.mark.scenario("<id>")` present and matching the catalog's `automation.test`,
      so the Allure `scenario` label traces a report row back to the catalog.

## Static checks

- [ ] `ruff check .` — real output pasted.
- [ ] `black --check .` — real output pasted.
- [ ] `mypy .` — real output pasted.
- [ ] No lint rule, type ignore or config loosened to pass.

## Browser execution

- [ ] `pytest --collect-only -q -m "not production"` shows live-site tests deselected.
- [ ] The non-production tests that were added actually ran, with real output.
- [ ] Any `production` test was **not** run in CI, and a local run (if any) is reported as a local
      observation, with its authorization noted.
- [ ] Reruns are reported, not silently absorbed: `--reruns 1` is global and an app's
      `retry_count` stacks on top, so "passed on rerun" is a finding.

## Failure classification

- [ ] Every failure is classified from real evidence (traceback, screenshot, trace, video, log) —
      not from a description of the failure.
- [ ] Application defect, automation defect, data/session, environment/network, access
      restriction, timing, or unknown — exactly one, with the evidence that decides it.
- [ ] An external-dependency failure is not reported as a defect in the code under test.
- [ ] "Unknown" names what evidence is missing instead of guessing.

## Production safety

- [ ] No checkout, payment, order-placement, authentication or account-creation code — including
      a file that merely exists for it.
- [ ] No bypass of a CAPTCHA, OTP or access control, in code, prompt or scenario.
- [ ] No loops, parallel sessions or repeated runs against a live site.
- [ ] `tests/test_ci_production_exclusion.py`, `pytest.ini`'s markers and the `-m "not
      production"` exclusions in [ci.yml](../../.github/workflows/ci.yml) are unchanged — or the
      change strengthens them, with a reason.
- [ ] No secret, cookie, token, `storage_state` or personal datum in the diff, an artifact, or
      anything pasted to an assistant. Config holds env-var *names* only.
- [ ] No new configuration key is presented as a safety control unless code enforces it.

## Human review

- [ ] A named person approved every expected result that became an assertion.
- [ ] Shared-framework changes (`core/`, root `conftest.py`, `pytest.ini`, CI workflow) are
      reviewed as their own change, each with a justification.
- [ ] No claim in a docstring, comment or report asserts verification that did not happen.
- [ ] The merge decision is a human's, and the assistant did not merge its own change.
