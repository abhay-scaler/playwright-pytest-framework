# playwright-pytest-framework

A Playwright + pytest framework that knows nothing about your applications. Install it, and a
pytest run in your project gets the browser lifecycle, per-application configuration, failure
artifacts, logging and Allure labelling — with every path resolved against *your* project, never
against wherever the framework happens to be installed.

It is a pytest plugin, registered through a `pytest11` entry point, so there is no `conftest.py` to
copy and no framework directory to vendor.

## Requirements

- **Python 3.12 or newer.** The distribution declares `requires-python = ">=3.12"`, so pip refuses
  older interpreters. CI runs the suite, and the installed-package verification, on **3.12 and
  3.13**; later versions are allowed by that declaration and are not yet exercised.
- A Playwright browser build, installed once per machine: `python -m playwright install chromium`
  (add `firefox webkit` if you run those engines).

## Install

```bash
pip install playwright-pytest-framework              # the plugin and its fixtures
pip install "playwright-pytest-framework[report]"    # plus the pytest-html report integration
pip install "playwright-pytest-framework[ai]"        # plus the scenario-catalog validator
python -m playwright install chromium
```

| What you get | Comes from |
|---|---|
| `pytest`, `playwright`, `allure-pytest`, `pytest-rerunfailures` | the base install — what the plugin itself imports |
| `pytest-html` | the **`report`** extra, for embedding failure screenshots into an HTML report |
| `pyyaml`, `jsonschema` | the **`ai`** extra, for the scenario-catalog validator |
| `pytest-xdist` | **nothing here** — parallel execution is your choice, so it is your dependency |

Two deliberate omissions, both load-bearing:

- **`[report]`.** The plugin embeds each run's failure screenshots into the report named by
  `--html`. Without the extra that step finds no report and says so; nothing else changes. But a
  `pytest.ini` that *passes* `--html` needs it, because pytest rejects an option no installed
  plugin defines before it collects anything.
- **`pytest-xdist`.** Nothing in the package requires it. The xdist-master guards behave the same
  whether it is installed or not, so `-n auto` is a decision about how you run your suite.

## Quickstart

A consumer project needs three things: a `pytest.ini` (which also marks the project root), one
configuration file per application and environment, and a fixture binding each application's name.

```
your-project/
  pytest.ini
  apps/
    checkout_app/
      config/local.json
      pages/
      locators/
  tests/
    checkout_app/
      conftest.py
      smoke/test_checkout.py
```

```ini
# pytest.ini
[pytest]
testpaths = tests
addopts = -ra --strict-markers
```

```json
// apps/checkout_app/config/local.json
{
  "base_url": "https://checkout.example.test",
  "action_timeout": 10000
}
```

```python
# tests/checkout_app/conftest.py — the one fixture an application must define
import pytest

from pwpf.core.app_config import load_app_config


@pytest.fixture(scope="session")
def app_config():
    return load_app_config("checkout_app")
```

```python
# tests/checkout_app/smoke/test_checkout.py
import pytest
from playwright.sync_api import expect


@pytest.mark.smoke
@pytest.mark.ui
def test_the_cart_page_loads(page, app_config):
    page.goto(f"{app_config.base_url}/cart")
    expect(page).to_have_title("Cart")
```

```bash
pytest -m smoke
```

That is the whole integration. The plugin supplies `page`; `app_config` is yours, because the
framework must not hold a list of your application names.

## What the plugin provides

**Fixtures.** The chain is lazy: a test that never asks for `page` never starts a browser.

| Fixture | Scope | What it is |
|---|---|---|
| `playwright_context` | session | the Playwright driver, started once per session |
| `browser` | session | one launched browser; skips the test with a clear message if the binary is missing |
| `browser_context_args` | function | the context arguments, including the current application's `ignore_https_errors` |
| `context` | function | a browser context with video recording enabled |
| `page` | function | a page with console- and page-error listeners attached, and failure artifacts on the way out |

**Markers**, all registered by the plugin, so `--strict-markers` works in a project that declares
none of them:

| Marker | Meaning |
|---|---|
| `smoke` | quick smoke tests |
| `ui` | browser UI tests |
| `regression` | regression coverage |
| `api` | API-oriented tests |
| `app(name)` | applied automatically from the test's path — see below |
| `production` | drives a live third-party production site; exclude it from CI with `-m "not production"` |
| `scenario(id)` | the catalog scenario a test implements; also attached as an Allure label |
| `quarantined` | known-unstable; keep it out of blocking gates |

**Application inference.** A test's application is its first path segment under `tests/`, provided
a matching `apps/<name>/` directory exists; anything else is labelled `framework`. There is no
registry to edit — a new `tests/<app>/` plus `apps/<app>/` is picked up on the next run. The
inferred name drives the `app(name)` marker, the Allure `application` label and the per-application
artifact directories.

## Application configuration

One JSON file per application per environment, at
`apps/<app>/config/<environment>.json`. `ENVIRONMENT` selects which one (default `local`), and
`load_app_config("<app>")` returns a frozen `AppConfig`.

| Key | Type | Default | Meaning |
|---|---|---|---|
| `base_url` | string | required | the application's base URL |
| `action_timeout` | int (ms) | `ACTION_TIMEOUT`, else 10000 | per-action timeout |
| `retry_count` | int | `RETRY_COUNT`, else 0 | when non-zero, the plugin applies `flaky(reruns=N)` to that application's tests |
| `ignore_https_errors` | bool | `true` | passed to the browser context |
| `secrets` | object | `{}` | maps a secret *name* to the **name of an environment variable** |

Anything else lands in `AppConfig.extra` rather than being rejected, so an application can carry
its own settings. A misspelled known key therefore ends up in `extra` and silently stops taking
effect — worth a validation check in your own project if that matters to you.

`config.secret("name")` reads the environment variable named by `secrets["name"]`, so a secret's
*value* never appears in a configuration file. A missing entry raises with the file and key to fix.

**Environment variables** the framework reads: `ENVIRONMENT` (which config file), `BROWSER`
(`chromium` by default), `HEADLESS` (defaults to true in CI, detected from `CI`), `ACTION_TIMEOUT`,
`RETRY_COUNT`, `BASE_URL` (a legacy global fallback) and `PWPF_ROOT` (below).

## Where files go

Every path resolves from **your** project root, never from the installed package. The order, first
match winning:

1. an explicit root from the caller — `pwpf-validate-catalog --root`, or
   `set_project_root(..., source="caller")`;
2. the active pytest session's `rootdir`, which the plugin pins in `pytest_configure`;
3. `PWPF_ROOT`, for code running outside pytest;
4. the nearest `pytest.ini` at or above the working directory.

If none applies, a `ProjectRootError` says how to supply one. The framework's own location is never
a fallback — guessing it is the bug this ordering exists to prevent.

Artifact directories are created when something is first written to them, never on import:
`screenshots/`, `traces/`, `videos/` (each namespaced per application), `reports/` (and
`reports/allure-results/`), and `logs/<worker>/framework.log`.

## Reporting and failure diagnostics

- **On failure only**: a full-page screenshot, a Playwright trace and the recorded video are kept,
  under the failing test's application. On a passing test the trace is discarded and the video
  deleted, so a green run leaves no debris.
- **HTML report**: with the `report` extra and an `--html` path, this run's failure screenshots are
  embedded into that report — recursively, and namespaced so two applications' identically named
  screenshots cannot collide. Which file is read comes from the `--html` option itself, resolved the
  way pytest-html resolves it.
- **Allure**: every test carries `application`, `browser` and `environment` labels, plus a
  `scenario` label for each `scenario(id)` marker. Stale results from the previous run are cleared
  at session start — only Allure's own artefacts, only in the directory `--alluredir` names, and
  never a directory that is, or contains, your project root.
- **Logging**: one log file per xdist worker, so parallel output stays attributable.
- **Console and page errors**: `error`-level console messages and uncaught page exceptions are
  logged, and never fail a test by themselves.

Under `pytest -n auto` the report embedding and the Allure cleanup run in the master process only.

## Conventions a consumer project must follow

The framework imposes exactly as much structure as it needs to infer application ownership, and no
more:

1. **`tests/<app>/` and `apps/<app>/` share a name.** That pairing is what the `app(name)` marker,
   the Allure labels and the artifact namespacing are derived from.
2. **One `app_config` fixture per application**, session-scoped, calling
   `load_app_config("<app>")` — in `tests/<app>/conftest.py`, which keeps it invisible to every
   other application's tests.
3. **Page objects act; tests assert.** `pwpf.core.base_page.BasePage` offers the shared Playwright
   actions and returns `Locator`s so tests can use auto-retrying `expect`. Keep selectors out of
   page-object logic and assertions out of page objects.
4. **A live-site test carries `production`**, and every CI invocation carries
   `-m "not production"`. The marker is a label; the exclusion in the command is what enforces it,
   so a check that fails when an invocation loses the exclusion is worth owning.
5. **`pytest.ini` marks the root.** Keep one at the project root, and the framework's artifacts and
   application lookup follow it.
6. **API tests** can use `pwpf.core.api_client`, a thin wrapper over Playwright's
   `APIRequestContext`, instead of adding an HTTP client.

Nothing above requires editing the framework, and onboarding a second application requires editing
nothing of the first.

## The scenario-catalog validator (optional)

With the `ai` extra:

```bash
pwpf-validate-catalog                 # every catalog under apps/*/scenarios/
pwpf-validate-catalog --root /path    # or against another project
python -m pwpf.ai_testing.validate_catalog
```

Static analysis only: it parses YAML, validates against a JSON Schema shipped with the package,
applies cross-field rules, and reads `tests/` as an AST. It never imports a test, starts a browser
or opens a socket. The rule codes it reports are framework behaviour; the lifecycle and approval
policy a catalog describes are a project's own governance, and the framework has no opinion on
them.

## Verifying an installation

```bash
python scripts/verify_installed_package.py
```

It builds a wheel, reads the archive manifest, installs it with its declared dependencies into a
clean virtual environment, generates a throwaway consumer project and runs that project with the
source tree nowhere on the path — checking plugin discovery, marker registration under
`--strict-markers`, application config resolution, artifact locations, the console script and the
packaged schema. Twenty-four checks, and a non-zero exit if any fails.

## Design principles

- **The framework never knows an application's name.** Ownership is inferred from the layout;
  anything else is configuration the consumer supplies.
- **Nothing resolves against the installed package.** Artifacts, applications and catalogs belong
  to the project under test (see *Where files go*).
- **Importing a module writes nothing.** Directories appear when an artifact is actually written.
- **Fail loudly, degrade quietly in the right places.** A missing browser skips with a reason; an
  unresolvable project root raises; housekeeping that cannot run says so instead of ending a run.
- **A marker is a label, not an enforcement mechanism.** What a command selects is what runs.

## Project layout

```
pwpf/
  plugin.py                    # the pytest plugin: fixtures, markers, hooks, artifacts
  config/
    paths.py                   # consumer-project root resolution
    settings.py                # artifact locations and env-var settings
  core/
    base_page.py               # shared Playwright actions for page objects
    app_config.py              # loads apps/<app>/config/<environment>.json -> AppConfig
    api_client.py              # thin APIRequestContext wrapper
  utils/
    logger.py                  # worker-aware file + console logger
    helpers.py                 # small stateless helpers
    report_embedder.py         # embeds failure screenshots into the HTML report
    allure_cleanup.py          # clears the run's own stale Allure results
  ai_testing/
    validate_catalog.py        # the catalog validator (console script + python -m)
    schemas/scenario.schema.json

pyproject.toml                 # distribution metadata, dependencies, lint/type configuration
LICENSE                        # MIT
scripts/verify_installed_package.py
tests/                         # the framework's own tests
```

## License

MIT.
