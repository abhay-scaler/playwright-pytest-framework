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
  objects, and locators; the framework layer (`pwpf/`) is entirely application-agnostic.
- **Page Object Model** with a thin shared `BasePage` — page objects expose actions and locators
  only; assertions stay in the tests, not in page objects.
- **API testing with no second HTTP client** — `pwpf/core/api_client.py` wraps Playwright's own
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

The **Owner** column says who declares each tool: the framework distribution (`pyproject.toml`), or
this consumer project (`requirements.in`, `pytest.ini`, `.pre-commit-config.yaml`). It is the
boundary a future extraction cuts along, and it is already load-bearing — a consumer that installs
the framework gets the first group automatically and must choose the second for itself.

| Category | Tool | Owner |
|---|---|---|
| Browser automation | [Playwright](https://playwright.dev/python/) (sync API) — Chromium, Firefox, WebKit | framework |
| Test runner | [Pytest](https://docs.pytest.org/) | framework |
| Retries | [pytest-rerunfailures](https://github.com/pytest-dev/pytest-rerunfailures) | framework — the plugin applies `flaky` when an app sets `retry_count` |
| Test reporting | [Allure](https://allurereport.org/) (`allure-pytest`) | framework |
| HTML reporting | [pytest-html](https://pytest-html.readthedocs.io/) | framework, optional — the `[report]` extra, for the failure-screenshot embedding |
| API testing | Playwright's own `APIRequestContext` (no separate HTTP client) | framework |
| Parallel execution | [pytest-xdist](https://pytest-xdist.readthedocs.io/) | **consumer** — nothing in `pwpf/` needs it; `-n auto` is a choice about how a suite is run |
| Linting | [Ruff](https://docs.astral.sh/ruff/) | both — each repository lints its own code |
| Formatting | [Black](https://black.readthedocs.io/) | both |
| Static typing | [mypy](https://mypy-lang.org/) (incremental, non-strict) | both |
| Secret scanning | [detect-secrets](https://github.com/Yelp/detect-secrets) | consumer — this repository's pre-commit hook |
| CI/CD | GitHub Actions | both — [the seven jobs and their owners](#continuous-integration) |
| Language / runtime | Python 3.12 | framework — `requires-python = ">=3.12"` |

## Project Structure

Two trees: the installable framework, and this repository's own project that consumes it. The
boundary is where a future extraction would cut
([docs/documentation-split-plan.md](docs/documentation-split-plan.md)).

**The framework** (`playwright-pytest-framework`, importable as `pwpf`) — application-neutral:

```
pwpf/                       # the installable package (pip install .)
  plugin.py                  #   the pytest plugin: fixtures, markers, artifacts, root
  config/{paths,settings}.py #   consumer-root resolution and artifact locations
  core/                      #   base_page, app_config, api_client
  utils/                     #   logger, helpers, report_embedder, allure_cleanup
  ai_testing/                #   catalog validator + the scenario JSON Schema (package data)

pyproject.toml              # distribution metadata and dependencies, plus Ruff/Black/mypy config
LICENSE                     # MIT, shipped in the wheel
scripts/verify_installed_package.py   # builds the wheel and proves it installs and works
```

**The consumer project** — these applications, their tests, and this repository's policy:

```
apps/<app_name>/            # everything specific to one application
  config/{local,ci}.json     #   base_url, timeouts, retry policy, secret references
  pages/                     #   page objects — actions and state queries only, no assertions
  locators/                  #   selectors as plain data, isolated from page-object logic
  testdata/                  #   static fixtures, where an app needs one
  scenarios/                 #   approved scenario catalog (YAML), validated in CI

tests/
  <app_name>/{smoke,ui}/      # tests owned by one application
    conftest.py                #   binds the app_config fixture to this app's name
  api/                         # application-agnostic API tests
  tmp/                         # a deliberately skipped manual-only diagnostic check
  test_*.py                    # mostly tests of the framework itself; the two policy guards
                               #   (production exclusion, quarantine) are this repository's

conftest.py                   # one line: loads pwpf.plugin from this source tree
pytest.ini                    # test discovery, markers, default CLI options
requirements.in / .txt        # loose source and fully-pinned lock file
requirements-ai.in / .txt     # scenario-validator deps only, kept out of the test runtime
.github/workflows/ci.yml      # the seven CI jobs and their owners — see below
DESIGN.md                     # full architecture, execution flow, and onboarding walkthrough
docs/                         # this repository's documentation, incl. the AI-testing workflow
ai_testing/                   # its prompt library and templates (no code, no dependencies)
scripts/extraction_dry_run.py # proves this project runs against the installed framework
scripts/check_doc_links.py    # the documentation link and fragment gate
```

Generated at runtime (all git-ignored): `reports/` (HTML + Allure results), `screenshots/`,
`traces/`, `videos/` (failure artifacts, namespaced per application), `logs/` (per-worker log
files). They are created when something is actually written, under the **project root** — not
under the framework's own directory, and never as a side effect of importing a module. Under
pytest the root is pytest's own `rootdir`; elsewhere set `PWPF_ROOT`, pass `--root` where a
command supports it, or run from a directory at or below the one holding `pytest.ini`. The
full precedence is in `pwpf/config/paths.py` and [DESIGN.md](DESIGN.md) §6.

## Using the framework in another project

The framework is an installable distribution with a pytest plugin entry point, so a
consumer project needs no `conftest.py` to get the fixtures, the markers or the artifact
handling:

```bash
pip install playwright-pytest-framework              # from a wheel, index or path
pip install "playwright-pytest-framework[report]"    # plus the pytest-html report integration
pip install "playwright-pytest-framework[ai]"        # plus the scenario-catalog validator
python -m playwright install chromium                # browsers, once
```

Two things the base install deliberately leaves out, because the framework runs without them:

- **`[report]`** — `pytest-html`. The plugin embeds each run's failure screenshots into the HTML
  report named by `--html`; without the extra that step finds no report and says so, and nothing
  else changes. A `pytest.ini` that passes `--html` needs the extra, since pytest rejects an
  option no installed plugin defines before it collects anything.
- **`pytest-xdist`** — the consumer's own dependency, not an extra here. Nothing in the framework
  requires it; `-n auto` is a choice about how you run your suite, and the framework's
  xdist-master guards behave the same whether it is installed or not.

The consumer keeps its own layout — `pytest.ini`, `apps/<app>/`, `tests/<app>/` — and pytest
discovers the plugin automatically through the `pytest11` entry point. Everything is resolved
against *that* project: its applications, and its `screenshots/`, `reports/`, `logs/`,
`traces/` and `videos/`, never the installed package's directory. The catalog validator is
available as `pwpf-validate-catalog` or `python -m pwpf.ai_testing.validate_catalog`.

`scripts/verify_installed_package.py` builds a wheel, installs it into a throwaway virtual
environment and runs a generated consumer project against it, asserting exactly that.

## Prerequisites

- **Python 3.12+** — the framework declares `requires-python = ">=3.12"`, so pip will refuse to
  install it on anything older. CI runs 3.12, and 3.12 is the only version this suite has run on.
- pip

## Installation

Two different things, and only the second is about this repository:

- **Using the framework in another project** — `pip install playwright-pytest-framework`, plus the
  extras you need. See [Using the framework in another project](#using-the-framework-in-another-project).
- **Developing *this* project** — the rest of this section. It installs the pinned lock file, which
  includes the framework's own dependencies plus this repository's tooling (xdist, detect-secrets,
  the linters).

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
| `PWPF_ROOT` | Project root, for entry points that are neither pytest nor able to pass one | unset |
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
  key against `_KNOWN_KEYS` in `pwpf/core/app_config.py` before relying on it;
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
gates, run in a non-blocking job), and an auto-applied `app(name)` marker `pwpf/plugin.py` assigns
based on each test's file path.

## Reporting and Failure Diagnostics

| Artifact | Location | When |
|---|---|---|
| HTML report | `reports/pytest_report.html` | every run; failure screenshots embedded automatically |
| Allure results | `reports/allure-results/` | every run; `application`/`browser`/`environment` labels on every test; Allure's own stale results from previous runs cleared automatically, other files in that directory left alone |
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
application, lives in [DESIGN.md](DESIGN.md). Summary of the fixture chain (all in `pwpf/plugin.py`
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

`.github/workflows/ci.yml` runs as seven jobs rather than one, so a pull request gets fast
feedback without giving up full-suite and cross-browser coverage. The tag on each says which half
of the repository it serves — framework, consumer, or both — and nothing about how it runs:

1. **Lint & Type Check** — *both* — Ruff, Black, mypy, and the documentation link checker. Every
   trigger, before any job installs a browser.
2. **Scenario Catalog** — *consumer* — `python -m pwpf.ai_testing.validate_catalog`. Every
   trigger; static analysis, no pytest and no browser.
3. **Installed Package** — *framework* — `python scripts/verify_installed_package.py`. Every
   trigger; builds a real wheel, installs it into a clean virtualenv and runs a generated
   consumer project from there, so the packaging guarantees are enforced rather than assumed.
4. **PR Smoke** — *consumer* — framework self-tests plus `-m "smoke and not production"`,
   Chromium only. Pull requests only, kept deliberately fast.
5. **Regression** — *consumer* — the full suite, Chromium, `-n auto`. Push to `main`/`dev`,
   nightly schedule, and manual dispatch.
6. **Cross-Browser** — *consumer* — the full suite against Firefox and WebKit. Nightly, or on
   demand via `workflow_dispatch` — not on every PR, since it roughly triples runtime.
7. **Quarantined (non-blocking)** — *consumer* — `-m "quarantined and not production"` with
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

Each entry is tagged with where the behaviour lives — **framework** if it is the plugin's doing and
would follow the distribution into any consumer project, **consumer** if it is about this
repository's own configuration.

**"Playwright browser could not be launched" (test skipped, not failed)** — *framework* — the
browser binary isn't installed yet:

```bash
python -m playwright install chromium
```

**Browser launch fails even after installing** — *framework* — check the exact error Playwright
prints. A
common cause is an unsupported host OS/browser-build combination (for example, an older macOS
version than Playwright's currently-pinned Chromium build supports). See
[Local-Only Overrides](#local-only-overrides) for how to work around this on your own machine
without changing the framework's shared, default behavior.

**A test fails only in CI, not locally (or vice versa)** — *both* — check `ENVIRONMENT` first
(the framework reads it; which files it selects, `apps/<app>/config/*.json`, is the consumer's),
then `HEADLESS`/`BROWSER`. Confirm your installed versions match `requirements.txt` exactly
(`pip install -r requirements.txt` from a clean virtualenv) rather than whatever was already
installed — that lock file is this repository's.

**A parallel-only failure (`pytest -n auto` fails, `pytest` alone passes)** — *both* — running
in parallel is this repository's choice (xdist is the consumer's dependency), while the per-worker
log it leaves behind is the framework's: check `logs/gw*/framework.log` for that worker's output.

## Known Limitations

Honestly documented rather than hidden — these are deliberate absences, not oversights, and each
has a clear extension path. Tagged by owner, because an absence in the framework is a different
conversation from one in this project.

**The framework's**

- **No authentication/session infrastructure.** No current application needs a login, so none
  exists. The intended shape (API-login, `storage_state`, cached per `pytest-xdist` worker) is
  documented in [DESIGN.md](DESIGN.md), ready to build against the first application that needs it.
- **No test-data factories.** No current application mutates server-side state. A worker-id- and
  UUID-keyed factory convention is documented in `DESIGN.md` for when one does.
- **Not published to a package index.** The distribution is real — `pyproject.toml` has its
  `[project]` table, `pip install -e .` works, and CI builds the wheel and proves it installs and
  runs in a clean virtualenv on every trigger ([Installed Package](#continuous-integration)) — but
  it is consumed from a path or a Git reference, not from an index. The options and the
  recommendation are in
  [docs/framework-extraction-readiness.md](docs/framework-extraction-readiness.md) §4.
- **Single browser engine per run.** `BROWSER` selects one engine for the whole run; the
  cross-browser CI job achieves coverage via separate full-suite runs per engine, not multiple
  engines interleaved within one invocation.

**This project's**

- **Allure results are generated and uploaded, but not rendered or published in CI.** Viewing a
  report requires `allure serve`/`allure generate` run locally against the downloaded results.
- **Ruff's rule set is intentionally narrow** (`E`, `F`, `I` — style and import order), not
  `B`/`UP`/security-oriented rules. A framework repository would choose its own.
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

None of the above are correctness bugs in what's implemented — they're scope boundaries, each with
a known, documented path forward if a real requirement arrives.
