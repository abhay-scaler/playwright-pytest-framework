# Playwright + Pytest Test Automation Framework

A multi-application UI and API test automation framework built with **Playwright** and
**Pytest**. It supports several independent applications under test from one shared codebase —
each application owns its own configuration, page objects, and locators, while a common framework
layer handles browser lifecycle, failure diagnostics, logging, and reporting without knowing
anything about any specific application.

The project currently automates three sample applications end-to-end (a static local HTML form,
a real documentation-search widget, and a multi-page public demo site) plus one API test against
a public REST API, as a working demonstration of the architecture — not because the framework is
limited to three apps. Onboarding a new application is an additive process (see
[Adding a New Application](DESIGN.md#adding-a-new-application)) that requires no changes to
existing application code or to the framework layer; this was proven in practice when the third
sample app was added with zero edits to the other two.

## Table of Contents

- [Key Features](#key-features)
- [Technology Stack](#technology-stack)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running Tests](#running-tests)
- [Reporting and Failure Diagnostics](#reporting-and-failure-diagnostics)
- [Architecture and Fixture Strategy](#architecture-and-fixture-strategy)
- [Code Quality](#code-quality)
- [Continuous Integration](#continuous-integration)
- [Local-Only Overrides](#local-only-overrides)
- [Troubleshooting](#troubleshooting)
- [Known Limitations](#known-limitations)

## Key Features

- **Multi-application architecture** — `apps/<app_name>/` owns its own configuration, page
  objects, and locators; the framework layer (`core/`, `conftest.py`, `utils/`) is entirely
  application-agnostic.
- **Page Object Model** with a thin shared `BasePage` — page objects expose actions and locators
  only; assertions stay in the tests, not in page objects.
- **API testing with no second HTTP client** — `core/api_client.py` wraps Playwright's own
  `APIRequestContext`, so API tests share the same driver/dependency as UI tests instead of adding
  `requests` or similar as a separate dependency. No browser is launched for API tests.
- **Automatic failure diagnostics** — on a UI test failure, a full-page screenshot, the complete
  Playwright trace, and a video are captured automatically, namespaced per application; all three
  are discarded on success so only failures cost disk space.
- **Passive browser error capture** — every page is watched for console errors (`type == "error"`)
  and uncaught JavaScript exceptions via `page.on("console", ...)`/`page.on("pageerror", ...)`;
  both are written to the framework logs and never affect a test's pass/fail outcome.
- **Worker-aware logging** — under parallel execution (`pytest-xdist`), each worker writes to its
  own log file (`logs/<worker>/framework.log`) instead of one interleaved, unattributable file.
- **Allure reporting** with `application`, `browser`, and `environment` labels on every test, plus
  automatic cleanup of stale results from previous runs at the start of each session (so `allure
  serve` always reflects only the current run).
- **Allure step reporting** on the reusable page-object action primitives (navigation, click,
  fill, screenshot, title verification) — business-visible actions show up as readable steps,
  nested under each page-object method that calls them; low-level reads/checks are deliberately
  left uninstrumented to keep the report readable.
- **No hard waits and no fragile selectors** — zero use of `time.sleep()` anywhere in the
  codebase; all waits are Playwright's own auto-retrying locators. Locator strategy is chosen
  deliberately per application (stable CSS ids for a static fixture, a third party's documented
  public CSS theming API, accessible-role locators elsewhere) rather than one default applied
  blindly everywhere.
- **Dependency locking** — `requirements.in` (loose, human-maintained) compiles to a fully-pinned
  `requirements.txt`, so installs are reproducible across every machine and in CI instead of
  silently drifting.
- **Static analysis and secret scanning** — Ruff, Black, and mypy are configured and wired into
  pre-commit and CI; `detect-secrets` runs as a pre-commit guardrail behind the framework's
  secrets-by-reference configuration convention (see [Configuration](#configuration)).
- **CI/CD** — a four-job GitHub Actions pipeline (lint/type-check, PR smoke, full regression,
  nightly cross-browser) with both pip and the Playwright browser binary cached.

## Technology Stack

| Category | Tool |
|---|---|
| Browser automation | [Playwright](https://playwright.dev/python/) (sync API) — Chromium, Firefox, WebKit |
| Test runner | [Pytest](https://docs.pytest.org/) |
| Parallel execution | [pytest-xdist](https://pytest-xdist.readthedocs.io/) |
| Retries | [pytest-rerunfailures](https://github.com/pytest-dev/pytest-rerunfailures) |
| HTML reporting | [pytest-html](https://pytest-html.readthedocs.io/) |
| Test reporting | [Allure](https://allurereport.org/) (`allure-pytest`) |
| API testing | Playwright's own `APIRequestContext` (no separate HTTP client) |
| Linting | [Ruff](https://docs.astral.sh/ruff/) |
| Formatting | [Black](https://black.readthedocs.io/) |
| Static typing | [mypy](https://mypy-lang.org/) (incremental, non-strict) |
| Secret scanning | [detect-secrets](https://github.com/Yelp/detect-secrets) |
| CI/CD | GitHub Actions |
| Language / runtime | Python 3.12 |

## Project Structure

```
apps/<app_name>/            # everything specific to one application
  config/{local,ci}.json     #   base_url, timeouts, retry policy, secret references
  pages/                     #   page objects — actions and state queries only, no assertions
  locators/                  #   selectors as plain data, isolated from page-object logic
  testdata/                  #   static fixtures, where an app needs one
  scenarios/                 #   approved scenario catalog (YAML), validated in CI

core/
  base_page.py               # shared Playwright actions every page object inherits
  app_config.py               # loads apps/<app>/config/<environment>.json -> AppConfig
  api_client.py                # thin wrapper around Playwright's APIRequestContext

config/
  settings.py                 # framework-wide settings from environment variables

utils/
  logger.py                   # worker-aware file + console logger
  report_embedder.py           # embeds failure screenshots into the HTML report (xdist-safe)
  allure_cleanup.py            # clears stale Allure results at the start of each run (xdist-safe)
  helpers.py

tests/
  <app_name>/{smoke,ui}/      # tests owned by one application
    conftest.py                #   binds the app_config fixture to this app's name
  api/                         # application-agnostic API tests
  tmp/                         # a deliberately skipped manual-only diagnostic check
  test_*.py                    # tests of the framework itself (config, logging, report embedding)

conftest.py                   # browser/context/page fixtures, failure capture, Allure labeling
pytest.ini                    # test discovery, markers, default CLI options
pyproject.toml                # Ruff / Black / mypy configuration
requirements.in / .txt        # loose source and fully-pinned lock file
requirements-ai.in / .txt     # scenario-validator deps only, kept out of the test runtime
.github/workflows/ci.yml      # CI pipeline
DESIGN.md                     # full architecture, execution flow, and onboarding walkthrough
docs/ai-testing/              # optional AI-assisted test engineering workflow (documentation)
ai_testing/                   # its prompt library and templates (no code, no dependencies)
```

Generated at runtime (all git-ignored): `reports/` (HTML + Allure results), `screenshots/`,
`traces/`, `videos/` (failure artifacts, namespaced per application), `logs/` (per-worker log
files).

## Prerequisites

- Python 3.10+ (CI runs 3.12)
- pip

## Installation

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
python -m playwright install chromium
```

`requirements.txt` is a generated, fully-pinned lock file — install from it, don't hand-edit it.
To change a dependency, edit `requirements.in` (the loose, human-maintained source) and
regenerate:

```bash
pip install pip-tools
pip-compile requirements.in --output-file requirements.txt
```

Commit both files together so installs stay reproducible across every machine and in CI.

To install other browser engines (used by the nightly cross-browser CI job, or on demand
locally):

```bash
python -m playwright install firefox webkit
```

## Configuration

Two layers of configuration exist.

**Framework-wide**, via environment variables (apply to every application/run):

| Variable | Purpose | Default |
|---|---|---|
| `BROWSER` | Browser engine: `chromium`, `firefox`, `webkit` | `chromium` |
| `HEADLESS` | Run headless (`true`/`false`) | `false` locally, `true` when `CI` is set |
| `ENVIRONMENT` | Selects `apps/<app>/config/<ENVIRONMENT>.json` | `local` |
| `CI` | Auto-forces headless when set | unset |
| `ACTION_TIMEOUT` | Framework-wide default action timeout (ms) | `10000` |
| `RETRY_COUNT` | Framework-wide default rerun count | `0` |

**Per-application**, via `apps/<app_name>/config/<environment>.json`:

```json
{
  "base_url": "https://example.test",
  "action_timeout": 15000,
  "retry_count": 1,
  "ignore_https_errors": false,
  "secrets": {
    "api_key": "MY_APP_API_KEY"
  }
}
```

- `base_url`, `action_timeout`, `retry_count` — self-explanatory; `retry_count` becomes a
  `pytest.mark.flaky(reruns=N)` override for that application's tests, applied automatically
  based on the test's file location.
- `ignore_https_errors` — optional, defaults to `true`; set `false` only if the application's
  environment has a real certificate worth validating.
- `secrets` — **never put an actual secret value here.** Map a logical name to the *name* of an
  environment variable; the real value is read from the environment at runtime via
  `AppConfig.secret("api_key")`. No app currently declares any secrets — none of the sample
  applications require credentials.
- `production_target` — optional, defaults to absent. `true` declares that this application
  drives a live third-party production site: every test under it must carry
  `@pytest.mark.production`, and a production-marked test that no declared application owns
  is equally an error. Nothing in the framework names an application; a new production app
  becomes visible to the guard by declaring itself.
  **It is not an `AppConfig` field.** `tests/test_ci_production_exclusion.py` reads it
  straight from the JSON — every environment file, so a `true` anywhere counts — because
  `load_app_config` resolves only one environment and would sweep an unrecognised key into
  `extra` unvalidated. The policy check validates it instead: a malformed file or a
  non-boolean value fails the check rather than quietly dropping the application from it.
- Any other key lands in `AppConfig.extra` for app-specific use (for example, an optional
  `consent_selector` a site's cookie banner can be dismissed with). **Unknown keys are
  accepted silently, not rejected** — a misspelling, or an invented key such as `timeout_ms`
  instead of `action_timeout`, lands in `extra` and simply never takes effect. Check a new
  key against `_KNOWN_KEYS` in `core/app_config.py` before relying on it;
  `ignore_https_errors` is the only key that fails loudly on a wrong type.

Example combining both layers:

```bash
BROWSER=firefox HEADLESS=true ENVIRONMENT=ci pytest tests/web_search
```

## Running Tests

```bash
# Full suite
pytest -q

# Headed / headless explicitly
HEADLESS=false pytest -q
HEADLESS=true pytest -q

# One application, any environment
pytest tests/sample_app -q
ENVIRONMENT=ci pytest tests/web_search -q

# One specific test file or test case
pytest tests/sample_app/ui/test_sample_app_form.py -q
pytest tests/api/test_json_placeholder.py::test_json_placeholder_nonexistent_post_returns_404 -q

# By marker
pytest -m smoke -q
pytest -m ui -q
pytest -m api -q

# Known-unstable tests: excluded from the blocking gates, still runnable
pytest -m quarantined -q                        # currently empty; DESIGN.md section 8 keeps the record

# Production-site tests (opt-in, local only - excluded from every CI job)
HEADLESS=false pytest -m production -q          # headed and supervised: the intended way
pytest tests/myntra -m production -q            # one production application
pytest -m "not production" -q                   # what CI runs: everything else

# In parallel
pytest -n auto -q

# Re-run only what failed last time
pytest --lf

# Framework self-tests only (fast; most need no browser)
pytest tests/test_*.py -q
```

Registered markers (`pytest.ini`): `smoke`, `ui`, `api`, `regression` (reserved for future use —
currently no test carries it), `production` (drives a live third-party site; excluded from every
CI job, opt in locally as above), `scenario(id)` (the catalog scenario a test implements, also
attached as an Allure label), `quarantined` (known-unstable; excluded from the blocking CI
gates, run in a non-blocking job), and an auto-applied `app(name)` marker `conftest.py` assigns
based on each test's file path.

## Reporting and Failure Diagnostics

| Artifact | Location | When |
|---|---|---|
| HTML report | `reports/pytest_report.html` | every run; failure screenshots embedded automatically |
| Allure results | `reports/allure-results/` | every run; `application`/`browser`/`environment` labels on every test; stale results from previous runs cleared automatically |
| Screenshot | `screenshots/<app_name>/<test_name>.png` | UI test failure only |
| Trace | `traces/<app_name>/<test_name>.zip` | UI test failure only |
| Video | `videos/<app_name>/<test_name>.webm` | UI test failure only |
| Logs | `logs/<worker>/framework.log` (`logs/main/` when serial) | every run |

View the Allure report locally:

```bash
pip install allure-commandline    # or: brew install allure
allure serve reports/allure-results
```

Open a saved trace:

```bash
playwright show-trace traces/<app_name>/<test_name>.zip
```

Debugging a failure: start with the HTML report (embedded screenshot), open the trace for full
DOM/network/console detail, check the video for the visual sequence, and grep
`logs/<worker>/framework.log` for the test or application name — including any browser console
error / page error lines captured passively during the run.

## Architecture and Fixture Strategy

Full detail, including the execution flow and the step-by-step guide for onboarding a new
application, lives in [DESIGN.md](DESIGN.md). Summary of the fixture chain (all in `conftest.py`
unless noted):

| Fixture | Scope | Purpose |
|---|---|---|
| `playwright_context` | session | One Playwright driver per worker process |
| `browser` | session | One browser process per worker, shared across its tests for launch speed |
| `context` | function | A fresh, isolated `BrowserContext` per test — this is where test isolation lives |
| `page` | function | A fresh `Page` per test; owns the entire trace/screenshot/video capture lifecycle in its own teardown |
| `app_config` | session (per-app `tests/<app>/conftest.py`) | The one fixture a new application must define |

This chain is intentionally short: one browser launch per worker (not per test, for speed), but a
fresh context per test (so isolation doesn't depend on re-launching the browser). Under parallel
execution, each `pytest-xdist` worker is a separate OS process with its own `browser` instance —
there is no shared browser, context, or global mutable state between workers. The two places that
*do* touch a file shared across workers (embedding failure screenshots into the HTML report, and
clearing stale Allure results) are explicitly guarded to run only in the xdist master process,
to avoid redundant work and a write race if every worker did it independently.

Artifact paths are namespaced by `<application>/<test_name>`, and Allure results are
independently UUID-named per test, so two tests — even across different workers — can never
collide on a file path.

## Code Quality

```bash
ruff check .
black --check .
mypy .
pre-commit install          # once per clone
pre-commit run --all-files
```

`detect-secrets` runs as part of the pre-commit hooks, checked against the baseline at
`.secrets.baseline`. If it flags something new, verify it's genuinely not a secret, then update
the baseline:

```bash
detect-secrets scan --baseline .secrets.baseline
```

## Continuous Integration

`.github/workflows/ci.yml` runs as six jobs rather than one, so a pull request gets fast feedback
without giving up full-suite and cross-browser coverage:

1. **Lint & Type Check** — Ruff, Black, mypy. Every trigger, before any job installs a browser.
2. **Scenario Catalog** — `python -m ai_testing.validate_catalog`. Every trigger; static
   analysis, no pytest and no browser.
3. **PR Smoke** — framework self-tests plus `-m "smoke and not production"`, Chromium only.
   Pull requests only, kept deliberately fast.
4. **Regression** — the full suite, Chromium, `-n auto`. Push to `main`/`dev`, nightly schedule,
   and manual dispatch.
5. **Cross-Browser** — the full suite against Firefox and WebKit. Nightly, or on demand via
   `workflow_dispatch` — not on every PR, since it roughly triples runtime.
6. **Quarantined (non-blocking)** — `-m "quarantined and not production"` with
   `continue-on-error: true`: known-unstable tests still run and report, but gate nothing.

Every pytest invocation in the workflow carries `-m "not production"`, so tests that drive a
live third-party site are never collected in CI; `tests/test_ci_production_exclusion.py` fails
if any invocation loses the exclusion. Every **blocking** invocation also excludes
`quarantined`, which the non-blocking job runs instead;
`tests/test_quarantine_policy.py` pins which tests those are. See [DESIGN.md](DESIGN.md) §8.

Both pip and the Playwright browser binary are cached, the latter keyed on the exact pinned
Playwright version so a dependency bump always installs fresh rather than risking a stale,
incompatible cache. Every job uploads its `reports/`, `screenshots/`, `traces/`, and `videos/` as
a build artifact unconditionally (`if: always()`), and emits a JUnit XML report alongside the
HTML/Allure output for CI platforms that consume it natively.

## Local-Only Overrides

A contributor's machine may need a tweak the rest of the team doesn't — an unsupported browser
build for their OS version, a different local port, and so on. The supported way to do this is to
edit a tracked file (`conftest.py`, `pytest.ini`, etc.) locally and simply **not commit** that
edit — `git status`/`git diff` will show it as an uncommitted local change.

- Prefer an environment variable or a per-app `config/*.json` entry over editing a shared file,
  whenever the override can be expressed that way.
- Keep a genuinely necessary tracked-file edit small and easy to spot in a diff.
- Never commit it, and don't let it change the framework's *default* behavior for anyone who
  hasn't made the same local edit.
- If more than one contributor needs the same workaround, that's a signal it should become a
  real, documented, opt-in feature instead of everyone independently carrying the same local
  diff.

## Troubleshooting

**"Playwright browser could not be launched" (test skipped, not failed)** — the browser binary
isn't installed yet:

```bash
python -m playwright install chromium
```

**Browser launch fails even after installing** — check the exact error Playwright prints. A
common cause is an unsupported host OS/browser-build combination (for example, an older macOS
version than Playwright's currently-pinned Chromium build supports). See
[Local-Only Overrides](#local-only-overrides) for how to work around this on your own machine
without changing the framework's shared, default behavior.

**A test fails only in CI, not locally (or vice versa)** — check `ENVIRONMENT` first (`local` vs
`ci` selects a different `apps/<app>/config/*.json`), then `HEADLESS`/`BROWSER`. Confirm your
installed versions match `requirements.txt` exactly (`pip install -r requirements.txt` from a
clean virtualenv) rather than whatever was already installed.

**A parallel-only failure (`pytest -n auto` fails, `pytest` alone passes)** — check
`logs/gw*/framework.log` for that worker's output.

## Known Limitations

Honestly documented rather than hidden — these are deliberate absences for the framework's
current scope, not oversights, and each has a clear extension path:

- **No authentication/session infrastructure.** No current application needs a login, so none
  exists. The intended shape (API-login, `storage_state`, cached per `pytest-xdist` worker) is
  documented in [DESIGN.md](DESIGN.md), ready to build against the first application that needs it.
- **No test-data factories.** No current application mutates server-side state. A worker-id- and
  UUID-keyed factory convention is documented in `DESIGN.md` for when one does.
- **No installable package root.** `pyproject.toml` has no `[project]` table — the project isn't
  `pip install -e .`-able. Imports work via Pytest's rootdir insertion, which is sufficient for
  running the test suite itself.
- **Allure results are generated and uploaded, but not rendered or published in CI.** Viewing a
  report requires `allure serve`/`allure generate` run locally against the downloaded results.
- **Ruff's rule set is intentionally narrow** (`E`, `F`, `I` — style and import order), not
  `B`/`UP`/security-oriented rules.
- **No accessibility testing** (no `axe`-style integration) and **no containerized CI** — neither
  has been a concrete requirement for the current applications.
- **Two locator modules share the same class name** (`HomePageLocators`, in two different
  applications) — harmless since imports are fully qualified, but worth knowing if you're
  searching the codebase by class name.
- **One live-site test still gates pull requests.** `tests/web_search` drives `playwright.dev`,
  a third party's production site, in the smoke gate. Its hydration race is fixed and the
  interaction contract is covered locally by `tests/web_search/ui/test_search_hydration.py`, but
  whether a docs search on someone else's site belongs in a blocking gate at all is still an open
  decision — see [DESIGN.md](DESIGN.md) §8.
- **Single browser engine per run.** `BROWSER` selects one engine for the whole run; the
  cross-browser CI job achieves coverage via separate full-suite runs per engine, not multiple
  engines interleaved within one invocation.

None of the above are correctness bugs in what's implemented — they're scope boundaries, each with
a known, documented path forward if a real requirement arrives.
