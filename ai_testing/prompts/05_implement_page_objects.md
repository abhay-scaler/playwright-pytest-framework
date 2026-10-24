# Prompt 05 — Implement page objects

All prompts inherit `ai_testing/README.md` § House rules.

## Purpose

Turn reviewed locator evidence into the application layer: locators as data, page objects that
act and expose state, and a fixture only if the application genuinely needs one. No assertions
live here.

## Required inputs

- `<work-item>/action-map.md` and `<work-item>/locator-evidence.md`, both reviewed.
- Approved scenarios.
- `<work-item>/repo-analysis.md`, and the existing app you are extending.

## Instructions

1. Re-read the closest existing example before writing anything: `apps/web_search/` for a
   network-driven app, `apps/uitesting_playground/` for several page objects in one app. Match
   their structure, naming and `allure.step` usage rather than introducing a style.
2. Put selectors in `apps/<app>/locators/<page>_locators.py` as plain class attributes, with a
   comment per selector citing the evidence that justifies it. A selector with no evidence does
   not get written.
3. Put interactions in `apps/<app>/pages/<page>.py`, subclassing `BasePage`, constructed
   `(page, config)`, redeclaring `config: AppConfig` so it is non-optional. Read timeouts from
   `self.config.action_timeout` and URLs from `self.config.base_url` — never a literal.
4. Use only the methods `BasePage` already provides (`ai_testing/README.md` § Verified framework
   facts). If something is genuinely missing, stop and propose adding it to `pwpf/core/base_page.py`
   as a separate, justified shared-framework change — do not add a private helper that
   duplicates it in the app layer, and do not reach for `self.page` to work around it unless the
   existing code already does so for that case.
5. Expose state as a method returning a value or a `Locator`, so the test can assert with
   Playwright's auto-retrying `expect(...)` — see `SampleAppPage.message_locator`
   (`apps/sample_app/pages/sample_app_page.py`). Page objects contain no `assert`.
6. No fixed waits. Wait for state with `is_visible`, `wait_for_url` or an `expect` in the test.
7. Add a component under `apps/<app>/components/` **only** with a stated reason: the same
   repeated element appears on several pages and needs its own scoped behaviour. Note that no
   existing app has one, that `BasePage` takes a `Page` rather than a scoped `Locator`, and that
   introducing the directory means documenting it in `DESIGN.md` §2. A page object is the default.
8. Add the package `__init__.py` files (`apps/<app>/`, `pages/`, `locators/`) if the app is new —
   every other app has them (`DESIGN.md` § Adding a New Application, step 3).
9. Configuration: use only the recognised keys, and add `apps/<app>/config/<env>.json` only for
   an environment the app will actually run in. Unknown keys are silently swallowed into
   `extra`, so check any new key against `_KNOWN_KEYS`. Secrets are env-var *names*, never values.
10. The app's own `tests/<app>/conftest.py` binds `app_config` with `load_app_config("<app>")`
    and nothing else, unless the application needs a fixture of its own — in which case it goes
    there, not in the root conftest.

## Output format

Real files in the repository, listed in your reply as a table `path | new/modified | why`, plus
the actual output of:

```
ruff check apps/<app> tests/<app>
black --check apps/<app> tests/<app>
mypy .
```

## Acceptance criteria

- Every selector cites evidence; nothing invented.
- No assertion, no fixed wait, no hard-coded URL or timeout in a page object.
- Only existing `BasePage` methods are used, or a shared change is proposed separately.
- `pwpf/`, `pytest.ini` and the CI workflow are untouched.
- Ruff, Black and mypy pass, with their real output shown.

## Safety constraints

No test is executed against a live production site in this step. No checkout, payment,
order-placement, login or account-creation page object is written, even speculatively — the file
existing is itself a statement of intent.

## Human review

A reviewer checks the locator comments against the evidence file and that the page object holds
no expectations. Shared-framework proposals are reviewed as their own change.

## Next step

`06_generate_tests.md`.
