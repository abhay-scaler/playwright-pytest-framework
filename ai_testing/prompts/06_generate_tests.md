# Prompt 06 — Generate Pytest tests

All prompts inherit `ai_testing/README.md` § House rules.

## Purpose

Implement approved scenarios as Pytest tests that read as business intent, assert the scenario's
expected results, and carry the markers that decide where they run.

## Required inputs

- Approved scenarios, with their ids.
- The page objects from prompt 05.
- `<work-item>/action-map.md` (particularly its missing-assertion list).

## Instructions

1. One test per scenario, named for the outcome:
   `test_search_returns_products_matching_the_term`, not `test_search_1`. The test body reads as
   the scenario's steps, with no selector and no raw Playwright call in sight.
2. File goes in `tests/<app>/<suite>/test_<something>.py`, where `<suite>` is `smoke` or `ui`
   following the existing apps. **Give the module a unique basename across the whole repo** —
   `tests/` has no `__init__.py`, so two `test_homepage.py` files break collection for the entire
   suite. Prefix with the app name when in doubt.
3. Request the `page` and `app_config` fixtures; construct the page object as
   `Page(page, app_config)`. Do not create a browser, context or config yourself.
4. Markers: `ui` for anything browser-driven, `smoke` if it belongs in the fast gate, `api` for
   API-level tests, `production` for **every** test that touches a live third-party site, and
   `scenario("<id>")` naming the catalog scenario the test implements — one marker per scenario
   covered. Then fill that scenario's `automation.test`, `markers` and `implemented: true` in
   `apps/<app>/scenarios/<feature>.yaml`, and run `python -m ai_testing.validate_catalog`: it
   fails if the mapping, the marker or the lifecycle status disagree.
   Markers select suites — the folder does not — so a test in `smoke/` without
   `@pytest.mark.smoke` silently never runs in the smoke gate. All markers must be registered in
   `pytest.ini` (`--strict-markers`).
5. Assert the scenario's expected results, all of them, preferring Playwright's auto-retrying
   `expect(...)` on a `Locator` from the page object over a snapshot read. Add the assertions
   prompt 04 found missing; a test that only performs actions verifies nothing.
6. Avoid brittle expectations: no exact page title where a regex on a stable fragment will do, no
   hard-coded price, stock level, product id or result count, no dependence on promotions or
   ordering unless the brief makes it a rule. Where the outcome can only be checked loosely,
   assert the loose thing and say so in the docstring.
7. Give each test a docstring naming the scenario id, what it proves, and — for a
   `production`-marked test — that it is local-and-authorized only, plus any limitation (for
   example that the assertion was derived from served markup rather than a live browser run).
8. No `time.sleep`, no `wait_for_timeout`, no added reruns, no `xfail` to paper over a real
   failure, no `try/except` that swallows a failed expectation.
9. State-mutating steps need a teardown decision in the test or a fixture: say explicitly what is
   cleaned up and what is not. If nothing can be cleaned up on a live site, the scenario needs
   human authorization, not a quiet test.
10. Use `allure.step` for the assertion blocks, as the existing tests do, so the report reads
    like the scenario.

## Output format

Real test files, listed as `path | scenario ids | markers`, plus the actual output of:

```
ruff check . && black --check . && mypy .
python -m ai_testing.validate_catalog
pytest --collect-only -q tests/<app>
pytest --collect-only -q -m "not production"      # confirm live-site tests are deselected
pytest <the non-production tests you added> -q    # real run, real output
```

A `production`-marked test is **not** executed here. Say so; do not imply it passed.

## Acceptance criteria

- One test per approved scenario, each asserting every expected result.
- Unique module basename; correct markers; `production` on every live-site test.
- No sleeps, no weakened assertions, no swallowed failures.
- Collection output shows live-site tests deselected by `-m "not production"`.
- Every command shown was actually run, with its real output, failures included.

## Safety constraints

Nothing here authorizes a live run. Checkout, payment, order placement and account creation stay
out of scope. Do not modify `pytest.ini`, the CI workflow or
`tests/test_ci_production_exclusion.py` to make a new test fit — if a test does not fit the
existing markers, that is a finding for a human.

## Human review

A reviewer confirms each assertion matches the approved expected result, and that markers put the
test where it belongs. Only a human may later promote a scenario to `ACTIVE_REGRESSION`.

## Next step

`07_review_automation.md`, run in a fresh context.
