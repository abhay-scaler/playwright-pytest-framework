# AI test engineering toolkit

Version-controlled prompts, templates and conventions for using a coding assistant to help
design and implement tests in this framework. Everything here is **plain Markdown and YAML**:
there is no CLI, no runtime, no LLM dependency, and nothing in this directory is imported by a
test. Deleting it would not change how a single test runs.

Start with [docs/ai-testing/README.md](../docs/ai-testing/README.md) for the workflow these
prompts implement. This file is the contract every prompt inherits — the house rules, the
verified framework facts, and where work in progress is allowed to live.

## How to use a prompt

1. Open a work item directory: `artifacts/ai-work/<YYYYMMDD>-<slug>/` (git-ignored — see
   [.gitignore](../.gitignore)). Everything the assistant produces that is not yet reviewed
   lives there.
2. Paste the prompt file's contents into a coding assistant that can read this repository, and
   supply the inputs its **Required inputs** section names.
3. Save its output into the work item directory under the filename the prompt's **Output
   format** section specifies.
4. Do the **Human review** step. Only then move to the prompt named under **Next step**.

Prompts are ordered but not a pipeline: any stage can send you back one. Running a later prompt
without the earlier one's reviewed output is the main way this process produces plausible
nonsense.

| # | Prompt | Produces | Next |
|---|---|---|---|
| 00 | [analyze_repository](prompts/00_analyze_repository.md) | `repo-analysis.md` — verified conventions | 01 |
| 01 | [generate_scenarios](prompts/01_generate_scenarios.md) | `scenarios-draft.yaml` (`DRAFT`) | 02 |
| 02 | [review_scenarios](prompts/02_review_scenarios.md) | `scenario-review.md` + revised draft (`AI_REVIEWED`) | human approval |
| 03 | [plan_exploration](prompts/03_plan_exploration.md) | `exploration-plan.md` | 04 |
| 04 | [convert_codegen](prompts/04_convert_codegen.md) | `action-map.md` + `locator-evidence.md` | 05 |
| 05 | [implement_page_objects](prompts/05_implement_page_objects.md) | page objects, locators, fixtures | 06 |
| 06 | [generate_tests](prompts/06_generate_tests.md) | Pytest tests | 07 |
| 07 | [review_automation](prompts/07_review_automation.md) | `automation-review.md` | human review |
| 08 | [analyze_failures](prompts/08_analyze_failures.md) | `failure-analysis.md` | 09 or a fix |
| 09 | [maintenance](prompts/09_maintenance.md) | `impact-analysis.md` + patch | 07 |

Templates: [feature_brief.md](templates/feature_brief.md),
[scenario_template.yaml](templates/scenario_template.yaml). Schema:
[schemas/scenario.schema.json](schemas/scenario.schema.json), validated by
[validate_catalog.py](validate_catalog.py):

```bash
pip install -r ../requirements-ai.txt     # once; kept out of the test-runtime lock
python -m ai_testing.validate_catalog     # schema, lifecycle rules, scenario-to-test mappings
```

Approved scenarios are committed to `apps/<app>/scenarios/<feature>.yaml` and the implementing
test carries `@pytest.mark.scenario("<id>")`; the rules are documented in
[docs/ai-testing/scenario-authoring.md § Validation](../docs/ai-testing/scenario-authoring.md#validation).

## House rules

Every prompt inherits these. They are repeated in no prompt; prompts reference
"`ai_testing/README.md` § House rules" instead.

1. **Read before writing.** Open the actual source file before describing or extending it.
   Cite what you relied on as `path:line`.
2. **Label every claim.** `[V]` verified by reading a file or observing output in this session,
   `[A]` assumption, `[?]` open question. An unlabelled claim is read as `[V]`, so do not leave
   assumptions unlabelled. Keep `[A]`/`[?]` items in a dedicated section rather than scattering
   them.
3. **Invent nothing.** No framework method, fixture, marker, configuration key, directory or
   command that is not in § Verified framework facts or in the source you cited. If something
   needed is missing, say so as `[?]` and stop — do not improvise an abstraction.
4. **Never claim an unrun command.** Do not report a test as passing, a lint check as clean or a
   locator as working unless the command ran in this session; paste the real output, including
   failures. "Not run" is an acceptable answer; a fabricated result is not.
5. **Never weaken a check to get green.** No deleted assertion, loosened matcher, added
   `time.sleep`, raised timeout or extra rerun as a way of making a failure disappear. A failing
   test that reflects reality is the useful outcome.
6. **Separate observation from expectation.** What the application *does* comes from the browser,
   the DOM or a response. What it *should* do comes from the feature brief or a human. Never
   derive an expected business result from the application's current behaviour alone.
7. **Respect the layers.** `tests/<app>/` asserts, `apps/<app>/pages/` acts,
   `apps/<app>/locators/` holds selectors as data, `core/` is shared and app-agnostic. Changes
   to `core/`, the root `conftest.py`, `pytest.ini` or the CI workflow are shared-framework
   changes: propose them separately, with a reason, and never as a side effect of adding a test.
8. **Production safety.** The live production target (`myntra`) is for supervised, explicitly
   authorized local exploration only. Never write or run checkout, payment, order-placement or
   account-creation steps; never bypass a CAPTCHA, OTP or access control; never generate load or
   hammer a live site; never run a `production`-marked test in CI. See
   [docs/ai-testing/README.md § Production safety](../docs/ai-testing/README.md#production-safety).
9. **No secrets in a prompt.** Never paste credentials, cookies, `storage_state`, tokens, `.env`
   contents or personal data into an assistant, and never put a secret value in a config file —
   only the *name* of an environment variable (`core/app_config.py:62`).
10. **Humans approve.** An assistant may propose scenarios, code and diagnoses. A human approves
    business expectations, authorizes production execution, and merges. No assistant decides that
    a scenario is `APPROVED` or `ACTIVE_REGRESSION`.

## Verified framework facts

Read from the source on this branch. If one of these disagrees with the code, the code wins and
this table needs fixing.

**Fixtures** — root [conftest.py](../conftest.py): `playwright_context` (session), `browser`
(session), `browser_context_args` (function), `context` (function), `page` (function), plus an
autouse Allure labeller. Per application: `app_config` (session), defined in
`tests/<app>/conftest.py` as `load_app_config("<app>")` and nowhere else. A test that needs a
browser requests `page`; one that does not never starts a browser.

**`BasePage`** — [core/base_page.py](../core/base_page.py), the only shared page-object base:
`goto(url, wait_until="load")`, `wait_for_url(url, timeout)`, `click(selector, timeout)`,
`click_role_link(name, timeout)`, `click_role_button(name, timeout)`, `fill(selector, value)`,
`get_text(selector)`, `is_visible(selector, timeout)` (polls until visible, unlike Playwright's
own `is_visible`), `take_screenshot(name)`, `expect_title(title, timeout)`,
`dismiss_if_visible(selector, timeout)`. It is constructed as `BasePage(page, config)`; `page`
objects for real applications redeclare `config: AppConfig` to make it non-optional.

**`AppConfig`** — [core/app_config.py](../core/app_config.py): fields `app_name`, `environment`,
`base_url`, `action_timeout`, `retry_count`, `ignore_https_errors`, `secrets`, `extra`, and the
method `secret(name)`. Loaded from `apps/<app>/config/<ENVIRONMENT>.json`, `ENVIRONMENT`
defaulting to `local`. **Only** `base_url`, `action_timeout`, `retry_count`,
`ignore_https_errors` and `secrets` are recognised keys; anything else is swept into
`extra` **silently**, so a misspelled or invented key never takes effect and never errors. Check
a new key against `_KNOWN_KEYS` (`core/app_config.py:12`).

**API calls** — `api_request_context(base_url, timeout, config)`, a context manager in
[core/api_client.py](../core/api_client.py). It shares no cookies with the browser fixtures.

**Helpers** — `take_screenshot(page, name)` and `read_text_file(path)` in
[utils/helpers.py](../utils/helpers.py); `get_logger(__name__)` in
[utils/logger.py](../utils/logger.py).

**Markers** — registered in [pytest.ini](../pytest.ini): `smoke`, `ui`, `api`, `regression`,
`production`, `scenario(id)`, and `app(name)` which the root conftest applies automatically from
the test's path. `--strict-markers` is on, so an unregistered marker is an error. Each
`scenario(id)` is also attached as an Allure label named `scenario` by the autouse fixture in
the root `conftest.py`, beside `application`, `browser` and `environment`.

**Application discovery is structural.** A test belongs to the application named by its first
path segment under `tests/`, provided `apps/<that name>/` exists (`conftest.py:44`). There is no
registry to edit — and therefore a new `tests/<app>/` folder joins the regression suite by
itself, which is why live-site tests must carry `@pytest.mark.production`.

**Retries** — `pytest.ini` applies `--reruns 1` to every run, and a non-zero `retry_count` in an
app's config adds a second, independent `flaky(reruns=N)` layer on top (`conftest.py:78`). Two
layers hide instability; leave `retry_count` at `0` unless there is a reason on record.

**Failure evidence**, captured automatically and only on failure: screenshot, trace and video
under `screenshots/<app>/`, `traces/<app>/`, `videos/<app>/`, with the screenshot embedded into
`reports/pytest_report.html`. Allure results land in `reports/allure-results`. All of these
directories are git-ignored.

**Commands** that count as validation: `ruff check .`, `black --check .`, `mypy .`,
`pytest tests/test_*.py -m "not production"` (framework self-tests, no browser),
`pytest -m "smoke and not production"`, `pytest -m "not production" -n auto` (what CI runs), and
`HEADLESS=false pytest -m production` (local, supervised, authorized only). Full reference:
[README.md § Running Tests](../README.md#running-tests).

## Dependencies

Nothing here may add a dependency to the **test runtime**. `requirements.in` is the human-edited
source and `requirements.txt` the pinned lock that every CI test job installs, so anything added
there is installed by the lint job and the nightly cross-browser sweep alike.

The catalog validator's own two dependencies (PyYAML, jsonschema) therefore live in
[requirements-ai.in](../requirements-ai.in) and the pinned
[requirements-ai.txt](../requirements-ai.txt), installed only by CI's `Scenario Catalog` job
and by developers who run the validator. The validator imports them lazily, the catalog
self-tests skip without them, and no test needs them to run. If automated
orchestration is ever justified (see
[docs/ai-testing/workflow.md § When orchestration would be justified](../docs/ai-testing/workflow.md#when-orchestration-would-be-justified)),
its dependencies belong in a separate file resolved separately, and that is an architecture
decision to take deliberately — not a side effect of a feature.
