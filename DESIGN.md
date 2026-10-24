# Framework Design

This document describes the architecture, execution flow, and design decisions behind this
Playwright + Pytest test automation framework, including its multi-application support. Read top
to bottom and you should understand how the framework works, why it's built this way, and how to
extend it.

## 1. Architecture Overview

The framework has two halves that are deliberately kept separate:

- **The framework layer** (`core/`, `conftest.py`, `utils/`, `config/`) — shared machinery that
  knows nothing about any specific application. Browser lifecycle, failure-artifact capture,
  logging, and the config-loading mechanism all live here.
- **The application layer** (`apps/<app_name>/`) — everything specific to *one* application under
  test: its base URL, its page objects, its locators, its test data. Each application is a
  self-contained package. Adding a new one never requires editing an existing one, and never
  requires editing the framework layer.

```
tests/<app>/<suite>/   <- what to verify, for this application
       |
apps/<app>/pages/      <- how to interact with this application's screens
       |
apps/<app>/locators/   <- where things are on this application's screens
       |
core/base_page.py      <- shared page-object behavior (framework layer, app-agnostic)
       |
apps/<app>/config/     <- this application's base_url / timeouts / secrets, per environment
       |
conftest.py             <- browser/context/page fixtures, failure-artifact capture (framework layer)
```

Tests never touch Playwright's `Page` API or raw selectors directly — they call methods on page
objects, which call methods on `BasePage`, which drives Playwright. Page objects never hardcode a
URL or a timeout — they read it from the `AppConfig` handed to them by their app's fixture. This
is what makes multiple applications able to coexist: nothing in the framework layer needs to know
how many applications exist or what any of them are called.

## 2. Directory Structure

```
apps/
  sample_app/                 # a static local HTML app (demonstrates a file-based app)
    config/
      local.json
      ci.json
    pages/
      sample_app_page.py
    locators/
      sample_app_locators.py
    testdata/
      sample_app.html
  web_search/                  # a real network app (demonstrates a base_url-driven app)
    config/
      local.json
      ci.json
    pages/
      home_page.py
    locators/
      home_page_locators.py
  uitesting_playground/        # a multi-page app (demonstrates >1 page object per app)
    config/
      local.json
      ci.json
    pages/
      home_page.py
      dynamic_id_page.py
    locators/
      home_page_locators.py
      dynamic_id_page_locators.py
  myntra/                      # live production site - exploration target, never a CI gate
    config/
      local.json               #   local only: deliberately no ci.json (see §8)
    pages/
      home_page.py
    locators/
      home_page_locators.py
    scenarios/
      shopping_journey.yaml    #   scenario catalog, schema-validated in CI (§11)

core/
  base_page.py                 # shared Playwright actions used by every page object
  app_config.py                # loads apps/<app>/config/<environment>.json -> AppConfig
  api_client.py                 # thin APIRequestContext wrapper for API-level tests

config/
  settings.py                  # framework-wide env-var settings (browser, headless, etc.)

utils/
  logger.py                    # worker-aware file+console logger
  helpers.py                    # small stateless helpers (e.g. screenshot naming)
  report_embedder.py            # post-processes the HTML report to embed failure screenshots

tests/
  sample_app/, web_search/, uitesting_playground/
    conftest.py                 # binds the generic app_config fixture to this app's name
    smoke/, ui/
  api/, tmp/                    # framework-level tests not owned by one application
  test_*.py                     # tests of the framework itself (config, logging, report embedding)

conftest.py                    # session/test fixtures + failure-artifact hooks (framework layer)
pytest.ini                     # test discovery, markers, default CLI options
pyproject.toml                 # Ruff/Black/mypy config
requirements.in                # loose, human-maintained dependency source
requirements.txt               # generated, fully-pinned lock file - install from this
requirements-ai.in / .txt      # scenario-validator deps only, outside the test runtime (§11)
.pre-commit-config.yaml        # ruff, black, mypy, detect-secrets
.secrets.baseline              # detect-secrets baseline (known-safe matches, e.g. docs examples)
.github/workflows/ci.yml       # CI pipeline: lint/type-check, PR smoke, regression, cross-browser
```

## 3. Execution Flow

A single test run goes through these stages:

1. **Collection** — Pytest discovers tests under `tests/`. A `pytest_collection_modifyitems` hook
   in the root `conftest.py` inspects each test's file path, infers which application it belongs
   to (the first path segment under `tests/`, if a matching `apps/<name>/` package exists), and:
   - tags it with `pytest.mark.app("<name>")` (or `"framework"` for app-agnostic tests), used later
     for Allure/report labeling;
   - if that application's config declares a non-default `retry_count`, applies a
     `pytest.mark.flaky(reruns=N)` override for that test.

   This inference is purely structural — onboarding a new application never requires editing this
   hook.

2. **Session setup** — `playwright_context` (session-scoped) starts the Playwright driver once;
   `browser` (session-scoped) launches a single browser instance shared by every test in the run,
   using the engine named by the `BROWSER` env var.

3. **Per-test setup** — Only for tests that actually declare a `page` parameter:
   - `browser_context_args` reads which app the test belongs to and resolves that app's
     `ignore_https_errors` setting (default `True`, unchanged for every existing app) before
     `context` is created.
   - `context` creates a fresh, isolated `BrowserContext` with video recording pointed at
     `videos/<app_name>/`.
   - `page` starts a Playwright trace on that context, then opens a new `Page`, then registers two
     passive listeners on it: `page.on("console", ...)` logs any console message whose `type` is
     `"error"`, and `page.on("pageerror", ...)` logs any uncaught browser-side JavaScript
     exception. Both are diagnostic only — they write through the same worker-aware framework
     logger as everything else in this file and never affect the test's pass/fail outcome.
   - The app's own `tests/<app>/conftest.py` supplies `app_config` (a session-scoped `AppConfig`
     for that one app), which the test passes into its page objects.

   Logging is worker-aware throughout: `utils.get_logger()` writes to
   `logs/<PYTEST_XDIST_WORKER>/framework.log` (`logs/main/` when running serially), so parallel
   runs never interleave one worker's output into another's log file with no way to attribute it.

   Tests that don't request `page` (API tests, config unit tests) never trigger browser/context
   creation at all — see the Known Issues section in the previous revision of this document for
   why that matters; it's now fixed (details in §9).

4. **Test body** — the test constructs a page object with `PageClass(page, app_config)`, then
   calls business-level methods on it.

5. **Failure capture** — still inside the `page` fixture's own teardown (not a separate fixture —
   see §5 for why), once the test's pass/fail outcome is known:
   - **On failure**: a full-page screenshot, the complete Playwright trace covering the whole
     test, and the video are all saved under `screenshots|traces|videos/<app_name>/<test_name>`.
   - **On success**: the trace is stopped and discarded (no file written) and the video is
     deleted — only failures are worth the disk space.

6. **Reporting** — an autouse `_tag_allure_application` fixture labels every test in Allure with
   its application name, plus the run's `browser` (from `BROWSER_NAME`) and `environment` (from
   `ENVIRONMENT`), so a nightly cross-browser failure is identifiable from the Allure result
   itself rather than requiring someone to infer it from the CI job name. At the start of the
   session, a `pytest_configure` hook clears `reports/allure-results/` of any results left over
   from a previous run — allure-pytest never does this itself, so without it every run's results
   would accumulate in that directory forever. At the end of the session, `pytest_terminal_summary`
   post-processes `reports/pytest_report.html`, embedding any failure screenshots from *this* run
   directly into the file — recursively, so per-app subdirectories are found, and namespaced
   (`<app>__<test>.png`) so two apps' identically-named screenshots never collide. A `since=`
   timestamp (recorded when `conftest.py` is imported, before any test in the run can have written
   anything) excludes screenshots left over from a previous run rather than silently re-embedding
   stale evidence. Both the Allure-results cleanup and the screenshot-embedding step are guarded to
   run only in the xdist master process (`config.workerinput is None`) — under `pytest -n auto`
   this hook fires once per worker as well as in the master, so without the guard every worker
   would redundantly re-scan and rewrite the same shared files, and a worker could race to clear
   results another worker had already started writing.

7. **Teardown** — `page` and `context` close per test; `browser` closes once at the end of the
   session.

## 4. Major Components

- **`core/app_config.py`** — `load_app_config(app_name, environment=None)` reads
  `apps/<app_name>/config/<environment>.json` (defaulting to the global `ENVIRONMENT` env var) and
  returns a frozen `AppConfig` (`base_url`, `action_timeout`, `retry_count`, resolved `secrets`,
  and a passthrough `extra` dict for anything app-specific). Results are cached per
  `(app_name, environment)`. This is the one piece of machinery every application relies on, and
  the only file a new application's tests import from the framework layer besides `BasePage`.

- **`core/base_page.py`** — the class every page object inherits from. Constructor is
  `BasePage(page, config=None)`; page objects use `self.config.base_url` /
  `self.config.action_timeout` instead of hardcoding either. An app whose page objects can't
  function without a config (most of them) narrows this at the subclass level — see
  `apps/web_search/pages/home_page.py`'s `config: AppConfig` class-level redeclaration, which is
  what actually makes mypy treat `self.config` as non-optional inside that class.

- **`core/api_client.py`** — `api_request_context(base_url="", timeout=None, config=None)`, a thin
  context manager around Playwright's own `APIRequestContext` (`sync_playwright().request`), used
  in preference to a second HTTP library. Pass `config` for an app-owned API (reads its
  `base_url`/`action_timeout`); pass an explicit `base_url` for a standalone check not tied to any
  application, like `tests/api/test_json_placeholder.py`.

- **`config/settings.py`** — framework-wide settings only: `BROWSER`, `HEADLESS`, `ENVIRONMENT`,
  and the output directories (`screenshots/`, `reports/`, `logs/`, `traces/`, `videos/`). Nothing
  application-specific lives here anymore — `BASE_URL` remains for backward compatibility but is a
  legacy fallback that no page object reads; applications own their own `base_url`.

- **`apps/<app_name>/`** — one package per application: `config/` (JSON per environment),
  `pages/`, `locators/`, and optionally `testdata/` for apps that ship their own static fixtures.

- **`conftest.py`** — owns the real fixture chain (`playwright_context` → `browser` → `context` →
  `page`), the failure-artifact capture, the app-inference hook, and Allure labeling. This is the
  single source of truth for browser lifecycle.

## 5. Fixture Strategy

| Fixture | Scope | Owner | Purpose |
|---|---|---|---|
| `playwright_context` | session | framework (`conftest.py`) | One Playwright driver instance for the whole run |
| `browser` | session | framework | One browser process shared by all tests |
| `browser_context_args` | function | framework | Context options (viewport, `ignore_https_errors`) — function-scoped specifically so it can read the current test's app and apply that app's own `ignore_https_errors` setting |
| `context` | function | framework | Fresh, isolated browser context per test, video pointed at this test's app folder |
| `page` | function | framework | Fresh page per test; owns the entire trace/screenshot/video capture lifecycle in its own teardown |
| `app_config` | session | **each app's** `tests/<app>/conftest.py` | The one fixture an application must define — binds the generic loader to its own name |

Two design choices worth calling out:

- **Failure-artifact capture lives inside the `page` fixture itself, not a separate autouse
  fixture.** An earlier draft of this framework used a standalone `attach_test_artifacts`
  fixture that declared `page`/`context` as parameters purely to force Pytest's teardown
  ordering (screenshot/trace capture needs the page and context still open). That forced *every*
  test in the suite — including pure API and config tests — to trigger a full browser launch,
  which is wasteful and, in this repo, caused every single test to skip in any environment without
  a browser binary installed. Moving the capture logic into `page`'s own teardown fixes both
  problems at once: it only runs for tests that actually requested a page, and Pytest's normal
  fixture-teardown ordering guarantees `context` is still open when it runs.
- **`app_config` is the only fixture a new application must write.** Everything else
  (`page`, `context`, `browser`) is shared framework machinery. This is a deliberate minimal
  surface area for onboarding.

## 6. Test Data & Configuration Approach

- **Framework-wide configuration** is environment-variable driven (`BROWSER`, `HEADLESS`,
  `ENVIRONMENT`), applies to the whole run, and changes how tests execute, not what they test.
- **Application configuration** is per-app, per-environment JSON
  (`apps/<app>/config/<environment>.json`), resolved via `ENVIRONMENT` (default `local`, `ci` used
  in CI). It defines what the application *is*: its base URL, its timeouts, its secret
  references.
- **Secrets are never stored as values.** A config file's `secrets` map is `{logical_name:
  "ENV_VAR_NAME"}` — the JSON only ever names an environment variable; `AppConfig.secret(name)`
  resolves the actual value from the environment at runtime. Neither demo application needs real
  secrets today, so both `secrets` maps are empty — see §7 in "Adding a New Application" for how a
  new app that does need one would use this.
- **`ignore_https_errors`** defaults to `True` for every app (unchanged behavior). A future app
  whose environment has a real certificate worth validating sets
  `"ignore_https_errors": false` in its own config JSON — nothing else changes, and every existing
  app's config simply omits the key.
- **Unknown keys are stored, not validated.** `load_app_config` keeps only the five keys in
  `_KNOWN_KEYS` (`base_url`, `action_timeout`, `retry_count`, `ignore_https_errors`,
  `secrets`) as typed fields and sweeps everything else into `AppConfig.extra`. That is what
  makes an app-specific setting like `consent_selector` possible without a framework change,
  but it also means a misspelled or invented key (`timeout_ms` instead of `action_timeout`,
  say) is accepted in silence and simply never takes effect. Check a new key against
  `_KNOWN_KEYS` before relying on it. `ignore_https_errors` is the one key that raises on a
  wrong type, because silently coercing it would flip a security-relevant setting.
- **One config file per environment an app actually runs in.** `myntra` ships `local.json`
  only: its tests are `production`-marked and never execute in CI, so a `ci.json` would be
  dead weight that implies the opposite. Its `retry_count` is `0` on purpose - `pytest.ini`
  already applies `--reruns 1` to the whole run, and a per-app `retry_count` stacks a second,
  independent rerun layer on top of it (§3, step 1), which is how real instability on a live
  site gets hidden rather than reported.
- **Test data**: `sample_app` ships a static local HTML fixture inside its own `testdata/`
  folder, loaded via `file://` with zero network dependency. `web_search` needs no static test
  data — it drives a real external site (`playwright.dev`'s own docs search).
- **Why `web_search` targets `playwright.dev` and not `google.com`**: an earlier version of this
  demo app pointed at live Google Search, which failed intermittently in CI — GitHub-hosted
  runners aren't guaranteed to be in the US, and Google serves a GDPR consent interstitial to
  EU/UK-region traffic that hides the search box, on top of general anti-automation defenses a
  test suite has no control over. Testing against a real third party's production site that
  actively defends against automated traffic is a poor foundation for a CI gate — the failure has
  nothing to do with the code under test. `playwright.dev` is maintained by the Playwright team
  itself for their own docs, has no consent wall, and is exactly the kind of stable target an
  application's smoke tests should point at when there's a choice.

### Authentication (future — documented, not built)

No current app needs a login, so there's deliberately no authentication code in this framework
yet — building one against nothing real to authenticate would be speculative infrastructure. When
the first authenticated app arrives, the intended shape is:

```
Authentication API  ->  storage_state  ->  role-based session  ->  worker-isolated browser contexts
```

Concretely, layered onto what already exists without forking any shared fixture:

- Authenticate **via API, not UI** (`core/api_client.py`'s `api_request_context`, or the app's own
  auth endpoint) — a login form is exactly the kind of shared UI most likely to have its own
  transient issues unrelated to what's actually under test, and per-test UI login is the single
  largest avoidable source of both slowness and flakiness at scale.
- Save the result via `context.storage_state(path=...)` and add a session-scoped fixture per role
  (`admin_storage_state`, `standard_user_storage_state`) in that app's own
  `tests/<app>/conftest.py` — matching the existing one-fixture-per-app-concern convention exactly.
- Pass `storage_state=path` into that app's own context-creation step, keyed on the xdist worker id
  (`PYTEST_XDIST_WORKER`) so parallel workers don't all hit the login endpoint simultaneously and
  each pays the login cost once per worker, not once per test.

### Test Data (future — documented, not built)

None of the three current apps mutate server-side state, so there's no factory/cleanup system
yet either. The intended convention for the first app that does:

```
apps/<app>/data/
    factories.py
```

Plain functions returning dicts/dataclasses (no ORM needed at this scale), with two rules that
matter once tests run under `pytest -n auto`:

- **Uniqueness is derived from the xdist worker id plus a UUID**, e.g.
  `f"user-{worker_id}-{uuid4().hex[:8]}@example.test"`, so two parallel workers creating "a user"
  can never collide on a unique constraint.
- **Cleanup is a fixture-level teardown** (create via API in setup, delete via API in teardown)
  scoped to the test that created the data — never a shared/global cleanup step, which is itself a
  common source of cross-test flakiness when it runs at the wrong time relative to a parallel
  neighbor.

## 7. Reporting

Two reporting outputs are generated per run, both aware of which application each test belongs
to:

- **pytest-html** (`reports/pytest_report.html`) — the primary human-readable report; failure
  screenshots are embedded directly into the file. Test node IDs already show the owning
  application (`tests/sample_app/...`).
- **Allure results** (`reports/allure-results/`) — every test carries an `application` label
  (`sample_app`, `web_search`, `uitesting_playground`, or `framework` for app-agnostic tests), a
  `browser` label (`BROWSER_NAME`), and an `environment` label (`ENVIRONMENT`), all settable via
  Allure's built-in filtering/grouping in a generated Allure report. The directory is cleared of
  stale results from previous runs at the start of every session (master-only under xdist — see
  §3), so `allure serve`/`allure generate` only ever reflects the current run.
- **JUnit XML** (`reports/junit*.xml`, generated in CI via `--junitxml=`) — for CI systems that
  consume it natively (Jenkins, Azure DevOps, GitLab, or GitHub Actions annotation actions). Not
  enabled by default locally (it's a CI-consumption format, not something a developer needs on
  every local run) — passed explicitly as a CLI flag in each CI job rather than added to
  `pytest.ini`'s `addopts`.

Independently of both reports, the `page` fixture registers passive `console`/`pageerror`
listeners on every page it opens (see §3): browser console messages of type `error` and any
uncaught page-side JavaScript exception are written through the same worker-aware logger as the
rest of the framework (`logs/<worker>/framework.log`). This is diagnostic capture only — it never
fails a test or otherwise changes its outcome, and it does not capture non-error console output
(log/info/warn) or attach anything to the HTML/Allure report.

Artifacts on failure only, namespaced per application:
- Screenshot → `screenshots/<app_name>/<test_name>.png`
- Full trace of the failing test → `traces/<app_name>/<test_name>.zip`
- Video → `videos/<app_name>/<test_name>.webm`

Logger names also carry the application implicitly: a page object under `apps/sample_app/pages/`
logs as `apps.sample_app.pages.sample_app_page`. Log *files* additionally carry the
`pytest-xdist` worker: `logs/<worker>/framework.log` (`logs/main/` when running serially), so a
parallel run's output for two different workers is never interleaved into one file with no way to
tell which worker produced which line.

## 8. CI/CD Flow

GitHub Actions (`.github/workflows/ci.yml`) runs as six jobs rather than one, so a PR gets fast
feedback without giving up full-suite and cross-browser coverage:

1. **Lint & Type Check** — `ruff check .`, `black --check .`, `mypy .`. Runs on every trigger
   (push, PR, schedule, manual dispatch), before any job installs a browser, so a lint/type error
   fails in seconds rather than after a multi-minute Playwright install.
2. **Scenario Catalog** — `python -m ai_testing.validate_catalog`, installing only
   `requirements-ai.txt` (PyYAML + jsonschema). Every trigger. No pytest, no browser, no
   network, so it needs no Playwright install and finishes in seconds; it is also the only job
   that installs anything outside the test-runtime lock (§11).
3. **PR Smoke** (`pull_request` only) — the framework's own tests (`tests/test_*.py`, fast, no
   browser) plus `-m "smoke and not production"`, Chromium only. Deliberately narrow: full
   regression coverage belongs to the jobs below, not to every PR.
4. **Regression** (push to `main`/`dev`, nightly, manual dispatch) — the full suite, Chromium,
   `pytest -m "not production" -n auto`.
5. **Cross-Browser** (nightly, or manual dispatch with the `cross_browser` input) — the full suite
   against Firefox and WebKit, as a matrix. Not run on every PR — it roughly triples runtime for
   coverage most changes don't need.
6. **Quarantined (non-blocking)** — `pytest -m "quarantined and not production"`, with
   `continue-on-error: true`, so known-unstable tests still run and still report without
   gating anything. See "Quarantined tests" below.

Each browser-driving job:
- Installs Python dependencies from the pinned `requirements.txt` (cached via
  `actions/setup-python`'s `cache: pip`, keyed on the file's hash).
- Resolves the exact pinned Playwright version from `requirements.txt` and uses it as a cache key
  for `~/.cache/ms-playwright` — a version bump always misses the cache and installs fresh, so a
  stale cache can never silently serve an incompatible browser binary.
- Emits a JUnit XML report alongside the HTML/Allure output.
- Uploads `reports/`, `screenshots/`, `traces/`, `videos/` unconditionally (`if: always()`), under
  a job-specific artifact name (required since `upload-artifact@v4` needs unique names across a
  workflow run when multiple jobs upload).

Because `testpaths = tests` in `pytest.ini` is recursive and application membership is inferred
from the path, **onboarding a new application requires no CI changes** for its tests to run — they
are auto-discovered the moment `tests/<new_app>/` exists. That convenience cuts both ways, and
the subsection below is the counterweight. The `apps/<app>/` boundary this
framework already uses is also what a future CI matrix would shard on (one job per app) if the
suite ever grows large enough to need it — no new tooling required to get there, just a matrix
entry keyed on `tests/<app>` when that day comes. Not done today because three demo applications
don't justify the added CI complexity.

### Production-site applications and the CI exclusion

Auto-discovery means a new `tests/<app>/` folder joins the regression suite and the nightly
cross-browser sweep by itself, with nobody deciding that it should. For an application that
drives someone else's live production site, that default is wrong: §6 already records why this
framework moved `web_search` off `google.com` — a third party's production site that actively
defends against automated traffic is a poor foundation for a blocking CI gate, because the
failure has nothing to do with the code under test.

So such tests are labelled and excluded:

- **`@pytest.mark.production`** (registered in `pytest.ini`) marks every test that drives a
  live third-party site. `myntra` is the only such application today.
- **Every pytest invocation in `.github/workflows/ci.yml` carries `-m "not production"`** — all
  four of them: framework self-tests, PR smoke (`"smoke and not production"`), regression, and
  each cross-browser matrix leg. The marker is a label; these four commands are the control.
- **`tests/test_ci_production_exclusion.py`** fails if any pytest invocation in the workflow
  loses the exclusion, if the marker stops being registered, or if a test under a
  production-only application forgets the marker. It is static analysis — it reads the workflow
  as text and the tests as an AST, so it needs no browser, no network, and no YAML dependency.
- **Running them is a deliberate, local act**: `HEADLESS=false pytest -m production`, supervised,
  on a machine where that is authorized. Checkout, payment, order placement and account
  creation are out of scope for this phase, so no page object or test for them exists.

A CI-gated end-to-end pilot therefore needs a *sanctioned* target — a local fixture app in the
shape of `sample_app`, or a site published for automation practice. That choice is still open
and is tracked as an open item for the AI test-engineering work; until it is made, no
live-site test is a CI gate.

One policy note, since it is easy to get backwards: a safety control like this exclusion **is**
an authorized change to the shared framework layer, and an AI-assisted workflow that forbade
shared-framework edits outright would have blocked the one change that makes production
exploration safe. The bar is justification, not prohibition — unrelated framework changes still
need a reason, and a configuration flag that no code reads (`allow_order_placement: false` in a
YAML file, say) is documentation, never enforcement.

### Quarantined tests

A `quarantined` test is known-unstable and excluded from every blocking gate, while still
running in the non-blocking `Quarantined` job so its outcome stays visible. The marker is
additive: the test keeps its `smoke`/`ui` markers and `pytest -m quarantined` (or naming the
file) still runs it locally. `tests/test_quarantine_policy.py` pins the exact set, requires
each entry to explain itself and to be recorded here, and fails if a blocking job stops
excluding the marker or if the non-blocking job stops running it.

Quarantine is a holding state with an exit criterion, not a bin. It is never the fix for a
failure, and a fixed sleep, a longer timeout or an extra rerun is never the fix either — those
change the report, not the behaviour.

**`tests/web_search/smoke/test_web_search.py::test_web_search` — quarantined 2026-10-24.**

- **Symptom**: `Locator.wait_for: Timeout 15000ms exceeded` waiting for
  `.DocSearch-Modal input[type='search']` to be visible, after `HomePage.search` clicks the
  header search button. Intermittent: it passed at 11:01 and failed on every run afterwards.
- **Cause (evidence-based, not assumed)**: a hydration race in the test, not a site outage and
  not a stale selector. `HomePage.open` waits only for `domcontentloaded`, so the click lands
  on playwright.dev's server-rendered search button before Algolia DocSearch has attached its
  handler; nothing opens, and the subsequent wait times out. A probe against the live site
  confirmed the modal and its input are present and visible when the search control is clicked
  after the page settles (`.DocSearch-Modal`, `input.DocSearch-Input[type=search]`,
  `placeholder="Search docs"`), so the selectors in
  `apps/web_search/locators/home_page_locators.py` are current. Clicking immediately after
  `domcontentloaded` failed 3/3; clicking after a short settle opened the modal 3/3.
- **Reproduced on a pristine baseline**: the same failure occurs on commit `36aac2f` in a
  separate worktree, so it predates the AI test-engineering work and is not a regression from
  it. It fails on a developer machine as readily as in CI.
- **Exit criteria** — all three, then the marker comes off and the entry is removed from
  `QUARANTINED` in `tests/test_quarantine_policy.py`:
  1. The race is fixed in the application layer, without a fixed wait: click the search
     control and wait for the modal to actually open, retrying the click if it does not (the
     button itself advertises a keyboard shortcut via `aria-keyshortcuts`, which is another
     way in). Whatever the shape, it must wait for state, not for time — this framework has
     no `time.sleep` anywhere, and this is not where that starts.
  2. Ten consecutive green runs locally on a cold cache, plus a green non-blocking CI job.
  3. The fix is reviewed like any other change; `pytest -m "smoke and not production"` stays
     green afterwards.
- **Owner**: unassigned — the repository has no `CODEOWNERS`. Whoever takes it has the
  diagnosis above and needs an hour, not an investigation.
- **Open question worth holding onto**: this test gates PRs against a third party's live site,
  which §6 already argues against. Fixing the race removes the symptom; whether a docs search
  on someone else's site belongs in the PR gate at all is a separate decision, tied to the
  sanctioned-target question in "Production-site applications and the CI exclusion" above.

## 9. Design Principles

- **One direction of dependency**: tests → pages → core/locators → fixtures/config. Nothing
  downstream ever reaches back up. Applications never depend on each other.
- **Applications are structural, not configured.** Which application a test belongs to is
  inferred from where the test file lives, not from an environment variable a developer could
  forget to set or set inconsistently with the folder they're running.
- **Selectors are data, not logic**: isolated in `locators/` so UI changes don't ripple into
  test/page code.
- **No secret ever lives in a config file** — only the name of the environment variable that
  holds it.
- **Fail loud, capture evidence**: any UI test failure automatically produces a screenshot, a
  complete trace, and a video, and surfaces the screenshot directly in the HTML report.
- **Environment parity over environment-specific code**: the same test code runs locally and in
  CI for every application; only `ENVIRONMENT` and the per-app JSON it selects change.
- **Keep it simple**: no service locators, no dependency-injection frameworks, no per-app plugin
  registry. Pytest fixtures already provide dependency injection; a new application's tests get
  its config through one small `conftest.py`, matching the same pattern every other app uses.
- **Reproducible installs, not just reproducible code**: `requirements.txt` is a generated, fully
  pinned lock file (via `pip-compile`), not hand-edited loose constraints — the same install
  command produces the same exact dependency versions on every machine and in CI, instead of
  silently drifting to whatever the latest compatible version happens to resolve to on a given
  day. `requirements.in` stays the human-edited source of intent.

## 10. Fixed Since the Last Review

The previous review of this framework flagged several concrete bugs; these are now fixed as part
of adding multi-application support (since the same code paths needed touching either way):

- **Tracing previously started after the test had already failed**, producing an empty, useless
  trace file. Tracing now starts when the page is created and is stopped (and saved) only on
  failure, discarded otherwise.
- **The saved video path never matched Playwright's actual output file.** Video is now correctly
  retrieved via `page.video.path()` after the page closes, renamed to a predictable path on
  failure, and deleted on success (previously kept for every test, unbounded).
- **A scratch test that always failed by design sat in the default collection path**
  (`tests/tmp/test_failure_artifacts.py`), breaking any real CI run. It's now explicitly skipped
  with a clear reason, kept only for manual verification.
- **A dead, unregistered fixture file** (`fixtures/browser.py`) duplicated `conftest.py` without
  ever being imported. Deleted.
- **A half-wired global environment-config system** (`config/environments/*.json`, loaded into
  `ENV_CONFIG` but never read anywhere) has been replaced by the per-application config described
  above, which is actually consumed.
- **Found while validating this change**: the autouse artifact-capture fixture forced every test
  — including pure API and config unit tests — to launch a browser, since it declared `page`/
  `context` as parameters purely to control teardown order. This made the entire suite depend on a
  browser binary being installed, even for tests that never touch one. Fixed by moving capture
  logic into `page`'s own teardown (§5).
- **Found on the first real CI run**: `google_search`'s test (the network-app demo, at the time
  pointed at live `google.com`) failed intermittently with a timeout waiting for the search box.
  Root cause: Google serves a GDPR consent interstitial to traffic it geolocates to the EU/UK,
  which GitHub-hosted runners aren't guaranteed to avoid, on top of general anti-automation
  defenses outside this framework's control. Fixed two ways: the app was renamed `web_search` and
  repointed at `playwright.dev`'s own docs search (a target with no consent wall and no incentive
  to block Playwright-based automation — see §6), and `BasePage` gained a reusable
  `dismiss_if_visible(selector)` helper any application can wire through its config's
  `consent_selector` (or similarly-named `extra` key) for the case of a genuinely consent-walled
  target — see "Adding a New Application," step 2.

- **Found on the second real CI run**: after the `web_search` swap, the test still failed, but
  differently — `results_visible()` returned `False` instead of timing out. Confirmed directly
  against the live DOM (via a real browser, not Playwright's) that `.DocSearch-Hits` was the
  correct selector and genuinely became visible after a search — the actual bug was
  `Locator.is_visible(timeout=...)` itself: despite the parameter name, Playwright's `is_visible()`
  does **not** poll/retry until the timeout elapses, it's a single instantaneous check. It was
  called immediately after `fill()`, before DocSearch's async Algolia search-as-you-type request
  had time to resolve and render — a pure timing race, unrelated to the selector. This was latent
  in `BasePage.is_visible` itself (not just this one call site), silently non-functional for
  anyone who used it expecting wait-and-retry semantics; the original `google_search`/`HomePage`
  never surfaced it because a full-page navigation (Google's `Enter`-triggered results page load)
  happened to finish before the check ran, masking the race by coincidence rather than by
  correctness. Fixed at the source: `BasePage.is_visible` now uses `Locator.wait_for(state=
  "visible")`, which does retry, and `HomePage.results_visible()` now calls `self.is_visible(...)`
  instead of bypassing `BasePage` with a raw Playwright call.

**Deliberately not done in that pass** (real, but independent of multi-app support): a shared API
client abstraction for `tests/api/`, and placeholder test cleanup (`test_ui_sample.py`,
`test_api_placeholder`). Both were addressed in the hardening pass below.

### Hardening pass (following a full architecture audit)

A subsequent audit (scored 6.4/10, "Intermediate") surfaced several concrete issues, fixed on a
dedicated branch without changing the architecture described above:

- **Screenshot embedding was confirmed broken** — `report_embedder.py`'s glob was non-recursive
  and never found the per-app-namespaced screenshot subdirectories introduced by multi-app
  support. Fixed (§7), with an added `since=` filter so a stale screenshot from a previous run
  can't be silently re-embedded into a new report, and asset-name namespacing so two apps'
  identically-named screenshots can't collide once copied into one flat `assets/` folder. Covered
  by `tests/test_report_embedder.py`.
- **Logging was not xdist-safe** — every worker wrote to one shared, unattributed log file. Fixed
  by making `utils/logger.py` worker-aware (§3/§7), covered by `tests/test_logger.py`.
- **No dependency lock file** — `requirements.txt` was loose lower-bound constraints only.
  Replaced with a `pip-compile`-generated lock (§9), verified to install cleanly in a completely
  fresh environment.
- **`ignore_https_errors` was a single global, unscoped `True`** — now a per-app `AppConfig` field
  (default `True`, preserving every existing app's behavior), covered by `tests/test_app_config.py`.
- **Mixed assertion idioms** — `sample_app`'s tests used plain `assert` against a value returned by
  `BasePage.get_text()`, which (unlike the already-fixed `is_visible()`) is still a single
  non-retrying read. Migrated those two tests to `expect(locator).to_have_text(...)`, via a new
  `SampleAppPage.message_locator()` returning the `Locator` itself rather than an extracted string
  — keeping the same Page Object → state query / Test → assertion boundary, not moving assertions
  into the page object. `web_search`'s test was left as-is: it already goes through the fixed,
  retry-safe `is_visible()`, so there was no further reliability gap to close there.
- **Three zero-value placeholder tests removed** (`test_ui_sample.py`, `test_api_placeholder`,
  `test_regression_sample.py`) — each asserted something that could never fail
  (`assert True`, `assert 2 + 2 == 4`), inflating the passing-test count without contributing real
  coverage. The `regression` marker remains registered for real future use; it's simply unused
  today rather than backed by a fake placeholder.
- **The one real API test moved off `requests`** and onto `core/api_client.py`, a thin wrapper
  around Playwright's own `APIRequestContext` (§4) — `requests` was used nowhere else, so this
  removed a dependency rather than adding one.
- **Static type checking added** (mypy, non-strict, incremental — see `pyproject.toml`), which
  caught two real gaps while being introduced: `BasePage.goto()`'s `wait_until` accepted any `str`
  instead of Playwright's actual `Literal` union, and `web_search`/`uitesting_playground`'s page
  objects accessed `self.config` as if it were never `None` despite `BasePage` typing it
  `Optional` — both fixed at the type level, not suppressed.
- **Secret scanning added** (`detect-secrets` pre-commit hook + `.secrets.baseline`) as an
  automated guardrail behind the existing secrets-by-reference convention (§6), which previously
  relied on the convention alone.
- **Ruff's config was on a deprecated path** (top-level `select` instead of `[tool.ruff.lint]`),
  nagging on every invocation. Fixed with no behavior change.
- **CI restructured** into lint/type-check, PR-smoke, regression, and cross-browser jobs (§8),
  with dependency and browser-binary caching and JUnit XML output added — previously a single job
  ran the entire suite, uncached, on every push.

### Follow-on hardening pass (commit `04f214f`)

A further, smaller batch of fixes landed after the pass above, once the framework was already
running under real `pytest -n auto` load:

- **The report-embedding hook ran once per xdist worker plus once in the master** — `pytest
  -n auto` fires `pytest_terminal_summary` in every worker process as well as the master, so
  without a guard, each worker redundantly re-scanned and rewrote the same
  `reports/pytest_report.html`. Fixed with a one-line `config.workerinput is None` guard so only
  the master embeds (§3/§7). Confirmed under real `-n auto` execution: exactly one embed
  invocation instead of N+1.
- **No browser console/page-error visibility** — the `page` fixture now registers passive
  `page.on("console", ...)`/`page.on("pageerror", ...)` listeners, logging error-level console
  messages and uncaught JS exceptions through the existing worker-aware logger (§3/§7). Diagnostic
  only; never fails a test.
- **Allure results carried no browser/environment context** — the existing
  `_tag_allure_application` fixture now also labels every test with `browser` and `environment`
  (§3/§7), so a nightly cross-browser failure is identifiable from the Allure result itself.
- **No negative-path API coverage** — `tests/api/test_json_placeholder.py` gained a test asserting
  the real, verified contract for a nonexistent resource (`GET /posts/999999` → `status=404`,
  `ok=False`, no exception raised — `core/api_client.py` is a thin passthrough to Playwright's own
  `APIRequestContext`, which does not raise on a non-2xx response).
- **`reports/allure-results/` accumulated forever** — allure-pytest never clears its own output
  directory, so every run added another UUID-named result per test with nothing ever removing old
  ones. Fixed with a `pytest_configure` hook (`utils/allure_cleanup.py`, same xdist-master guard as
  above) that clears the directory once at the start of each run.

---

## 11. AI-Assisted Test Engineering (Optional)

An optional way of working, not a part of the framework: a version-controlled set of prompts,
templates and conventions for using a coding assistant to help design and implement tests here.
Nothing in it is imported, installed or executed by a test run, it adds no dependency to
`requirements.in`/`requirements.txt`, and deleting both directories would leave every test
behaving identically.

- **[docs/ai-testing/](docs/ai-testing/README.md)** — the entry point: the twelve-stage workflow
  (inputs, outputs, owner and completion criterion per stage), scenario authoring and governance,
  the Codegen-to-page-object standards, a review checklist and evidence-based troubleshooting.
- **[ai_testing/](ai_testing/README.md)** — the prompt library (ten prompts, each with purpose,
  inputs, instructions, output format, acceptance criteria, safety constraints and human-review
  requirements), the feature-brief and scenario templates, and the house rules every prompt
  inherits.

Three constraints shape it, and they are the parts worth knowing even if you never use the
process:

- **The brief and the approved scenarios are the source of truth for expected behaviour**; the
  application is the source of truth only for what it currently does. An expectation derived
  from observed behaviour produces a test that agrees with the bug.
- **An assistant proposes, a human approves and merges.** No assistant approves a business
  expectation, authorizes a run against a live site, promotes a scenario to active regression,
  or merges its own change — and shared-framework changes (`core/`, the root `conftest.py`,
  `pytest.ini`, the CI workflow) are proposed separately, with a reason, never as a side effect
  of adding a test.
- **Prompt text enforces nothing.** What enforces anything here is executable: Ruff, Black and
  mypy; `--strict-markers`; the `-m "not production"` exclusion on every pytest invocation in
  CI, guarded by `tests/test_ci_production_exclusion.py` (§8); and human review. A YAML flag that
  no code reads is documentation, never a safety control.

Work in progress — drafts, recordings, exploration evidence — lives in `artifacts/ai-work/`,
which is git-ignored.

### The scenario catalog

Approved scenarios are committed per application, at `apps/<app>/scenarios/<feature>.yaml`, so an
application stays self-contained (§1) — there is deliberately no top-level catalog tree. They
are a design and traceability record: nothing in the test runtime reads them, and the executable
truth is always the test named in a scenario's `automation.test`.

- **Schema**: `ai_testing/schemas/scenario.schema.json`, JSON Schema 2020-12, versioned
  (`schema_version: "1.0"`). Unknown keys are rejected, so a misspelled field fails instead of
  being silently ignored — the same failure mode `AppConfig.extra` has for configuration (§6),
  avoided here deliberately.
- **Validation**: `python -m ai_testing.validate_catalog` — schema, id uniqueness across every
  catalog, the lifecycle rules, and the scenario-to-test mappings in both directions. Static
  analysis: it parses YAML and reads `tests/` as an AST, never importing a test, starting a
  browser or opening a socket. CI runs it in its own `Scenario Catalog` job (§8).
- **Traceability**: the implementing test carries `@pytest.mark.scenario("<id>")` — registered
  in `pytest.ini` like every other marker — and the root `conftest.py` attaches each id as an
  Allure label named `scenario`, beside `application`, `browser` and `environment`. One scenario
  is implemented by exactly one test; one test may cover several scenarios.
- **Dependencies**: the validator needs PyYAML and jsonschema, pinned in `requirements-ai.txt`
  and deliberately **not** in the test-runtime lock that every test job installs. It imports
  them lazily, and `tests/test_scenario_catalog.py` skips when they are absent.
- **What it cannot enforce**: that a recorded approval is genuine. `review.approved_by` plus
  `approved_date` are required from `APPROVED` onwards, and `ACTIVE_REGRESSION` additionally
  requires `ci_eligible: true` and no `production` marker — but a name and a date in YAML are
  only as true as the review behind them. The checks make skipping review visible, not
  impossible; that part stays human, as does merging.

A CLI or LLM orchestration is still **not implemented** and remains a separate, later decision;
`docs/ai-testing/README.md` records what is built and what is not.

## Adding a New Application

Follow these steps to onboard a new application, e.g. `checkout_app`. Nothing here requires
editing another application's files or the framework layer.

### 1. Create the application's configuration

```
apps/checkout_app/config/local.json
apps/checkout_app/config/ci.json
```

One JSON file per environment you need (matches whatever `ENVIRONMENT` values your team uses —
`local`/`ci` today, add `staging`/`prod` the same way if needed).

### 2. Define URLs, credentials, browser settings, timeouts, environment-specific values

Inside each environment's JSON:

```json
{
  "base_url": "https://checkout.staging.example.com",
  "action_timeout": 12000,
  "retry_count": 1,
  "ignore_https_errors": false,
  "secrets": {
    "api_key": "CHECKOUT_APP_API_KEY"
  }
}
```

- `base_url` — read by page objects as `self.config.base_url`. Omit/leave empty for a
  file-based app with no real URL (see `sample_app`).
- `action_timeout` — available as `self.config.action_timeout` for any explicit
  timeout in a page object.
- `retry_count` — auto-applied as a `pytest.mark.flaky(reruns=N)` override for every test under
  `tests/checkout_app/` (falls back to the global `--reruns` default in `pytest.ini` if omitted).
- `secrets` — **never put an actual secret value here.** Map a logical name to the *name* of an
  environment variable, then set that environment variable locally (`.env`, shell export) or as a
  CI secret. Read it in a page object/test via `app_config.secret("api_key")`. If the environment
  variable isn't set, `.secret()` raises a clear error naming exactly which file to fix. A
  `detect-secrets` pre-commit hook (`.secrets.baseline`) is a backstop against an actual secret
  value landing here by mistake — it isn't a substitute for following the convention.
- `ignore_https_errors` — optional, defaults to `true` (omit the key entirely for that). Set to
  `false` only if this app's environment has a real certificate worth validating.
- Browser engine and headless mode are **framework-wide**, not per-app (`BROWSER`/`HEADLESS` env
  vars) — every application in a given run shares one browser process for launch efficiency. If an
  application genuinely needs a different browser engine than the rest of the suite, that's a real
  architectural change (a per-test browser fixture instead of session-scoped) — flag it rather
  than working around it, since it changes the performance characteristics of the whole suite.
- **Optional app-specific keys** — anything in the JSON beyond `base_url`/`action_timeout`/
  `retry_count`/`secrets` lands in `app_config.extra`. `web_search` uses this for a
  `consent_selector` key: if the target site shows a cookie/consent banner, set
  `"consent_selector": "text=Accept all"` (or whatever selector matches) and call
  `self.dismiss_if_visible(self.config.extra["consent_selector"])` early in the page object's
  `open()` — it's a no-op if the banner never appears, so it's safe to call unconditionally.
  `web_search`'s own config leaves this `null` since `playwright.dev` has no such banner.

### 3. Where application-specific page objects/components go

```
apps/checkout_app/pages/checkout_page.py
apps/checkout_app/locators/checkout_locators.py
```

```python
# apps/checkout_app/locators/checkout_locators.py
class CheckoutLocators:
    PAY_BUTTON = "#pay"

# apps/checkout_app/pages/checkout_page.py
from core.base_page import BasePage
from apps.checkout_app.locators.checkout_locators import CheckoutLocators

class CheckoutPage(BasePage):
    def open(self) -> None:
        self.goto(self.config.base_url)

    def pay(self) -> None:
        self.click(CheckoutLocators.PAY_BUTTON)
```

Don't forget `apps/checkout_app/__init__.py`, `apps/checkout_app/pages/__init__.py`, and
`apps/checkout_app/locators/__init__.py` (empty files — they make the folders importable
packages, matching every other app).

### 4. Create the fixtures the application needs

Exactly one file, one fixture:

```python
# tests/checkout_app/conftest.py
import pytest
from core.app_config import load_app_config

@pytest.fixture(scope="session")
def app_config():
    return load_app_config("checkout_app")
```

If the application needs extra fixtures beyond `app_config` (e.g. a logged-in session), add them
to this same `conftest.py` — they'll only be visible to `checkout_app`'s own tests, never leaking
into other applications.

### 5. Where application-specific test data lives

```
apps/checkout_app/testdata/
```

Only needed for static fixtures (sample HTML, JSON payloads, seed files) the app's own tests load
directly — mirrors `apps/sample_app/testdata/`.

### 6. Create the first smoke test

```
tests/checkout_app/smoke/test_checkout_smoke.py
```

```python
import pytest
from apps.checkout_app.pages.checkout_page import CheckoutPage

@pytest.mark.smoke
def test_checkout_page_loads(page, app_config):
    checkout_page = CheckoutPage(page, app_config)
    checkout_page.open()
    assert checkout_page.page.title() != ""
```

The `app_config` fixture comes from the `conftest.py` created in step 4 — Pytest resolves it
automatically because the test lives under `tests/checkout_app/`.

### 7. Execute tests for a specific application and environment

```bash
# local environment (default)
pytest tests/checkout_app

# a specific environment
ENVIRONMENT=ci pytest tests/checkout_app

# just this app's smoke suite
pytest tests/checkout_app/smoke

# this app's smoke tests, headed, against a non-default browser
BROWSER=firefox HEADLESS=false pytest tests/checkout_app/smoke
```

### 8. Integrate into CI/CD

**Nothing to change for basic execution** — the Regression job already runs `pytest -n auto` over
all of `tests/`, so `tests/checkout_app/` is picked up automatically. If any of its tests carry
`@pytest.mark.smoke`, they're automatically included in the PR Smoke job too.

If the new application needs a secret in CI, add it as a GitHub Actions secret and expose it as an
env var in the workflow's `env:` block, using the same variable name referenced in
`apps/checkout_app/config/ci.json`'s `secrets` map — nothing else changes.

Only add a dedicated CI job/matrix entry for this application if you have a real reason to isolate
it (separate schedule, separate secret scope, much longer runtime) — not by default.

### 9. How reporting, screenshots, traces, and logs identify the application

All automatic — no extra code needed once the app follows the `tests/checkout_app/...`
convention:

- Screenshots/traces/videos on failure land under `screenshots|traces|videos/checkout_app/`.
- Allure results carry an `application: checkout_app` label on every test.
- Logger names inside `apps/checkout_app/...` files read as
  `apps.checkout_app.pages.checkout_page` in `logs/<worker>/framework.log`.
- Test node IDs in the HTML report already read `tests/checkout_app/...`.

### 10. Files a developer needs to modify when adding a new application

**New files only — nothing existing needs to change:**

- `apps/checkout_app/__init__.py`, `pages/__init__.py`, `locators/__init__.py`
- `apps/checkout_app/config/local.json` (+ `ci.json`, etc.)
- `apps/checkout_app/pages/*.py`, `apps/checkout_app/locators/*.py`
- `apps/checkout_app/testdata/*` (if needed)
- `tests/checkout_app/conftest.py`
- `tests/checkout_app/<suite>/test_*.py`

The only case that touches a shared file is a **new secret in CI** (adding a GitHub Actions
secret + one `env:` line in `ci.yml`) — and even that never requires editing another
application's tests or the framework layer (`core/`, root `conftest.py`, `config/settings.py`).
