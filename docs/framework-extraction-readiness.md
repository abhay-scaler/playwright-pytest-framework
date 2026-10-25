# Framework extraction readiness

Preparation, not the extraction. Nothing here moves a file, creates a repository, publishes a
package or changes where this project gets its framework from. What it does is settle three
questions with evidence: **what belongs where**, **how the consumer would depend on the
framework**, and **whether the split actually works** — the last one answered by a script you can
run.

Legend: **[V]** verified by a command in this repository · **[P]** proposal, decided but not done
· **[?]** open, needs a decision.

## 1. Where this stands

Three prerequisites are done and on `dev`:

| Milestone | What it established |
|---|---|
| [#6](https://github.com/abhay-scaler/playwright-pytest-framework/pull/6) | Production-test discovery is configuration-driven, not a list of application names in the framework |
| [#7](https://github.com/abhay-scaler/playwright-pytest-framework/pull/7) | Every path resolves from the *consumer's* project root — never from the framework's own location ([DESIGN.md](../DESIGN.md) §6) |
| [#8](https://github.com/abhay-scaler/playwright-pytest-framework/pull/8), [#9](https://github.com/abhay-scaler/playwright-pytest-framework/pull/9) | The framework is a distribution, `playwright-pytest-framework`, importable as `pwpf`, with a `pytest11` entry point, a validated wheel manifest and safe artifact handling (§12) |
| [#10](https://github.com/abhay-scaler/playwright-pytest-framework/pull/10) | CI runs `scripts/verify_installed_package.py` on every trigger, so the packaging guarantees are a gate |

What remains before extraction is mechanical rather than architectural — which is what the dry run
below is for.

## 2. The dry run

```bash
python scripts/extraction_dry_run.py          # add --keep to inspect the workspace afterwards
python scripts/extraction_dry_run.py --no-browser   # skip the Chromium download; collection only
```

`verify_installed_package.py` asks whether the wheel works for a *synthetic* consumer it generates
itself. This script asks the question extraction actually turns on: can **this repository's own**
consumer code — `apps/` and `tests/<app>/` — run against the installed distribution with the
framework checkout nowhere in sight? It builds a wheel, installs it into a clean virtual
environment, copies the consumer-owned half of the repository into a temporary project **without**
`pwpf/`, **without** the root `conftest.py` and **without** the framework's self-tests, and runs
that project from there.

**Result: 16/16 checks, exit 0** [V]

```
  [PASS] the consumer project contains no pwpf/ and no root conftest.py
  [PASS] the framework's own self-tests were not copied into the consumer
  [PASS] pwpf is imported from the installed wheel, not this checkout
  [PASS] the framework checkout is on neither sys.path nor PYTHONPATH
  [PASS] the plugin's markers are registered with no consumer conftest.py
  [PASS] the plugin's fixture chain is available to the consumer's tests
  [PASS] selection -m "production" collects 1
  [PASS] selection -m "quarantined" collects 0
  [PASS] selection -m "smoke and not production and not quarantined" collects 4
  [PASS] the consumer's blocking smoke selection runs and passes against the installed plugin
         (smoke tally: {'deselected': 9, 'passed': 4})
  [PASS] application config is resolved from the consumer's own apps/
  [PASS] artifacts are written under the consumer project root
  [PASS] Allure results are written to the consumer's reports/allure-results
  [PASS] no artifacts are written into the installed package
  [PASS] no artifacts appeared in the framework checkout
  [PASS] scenario-catalog validation passes in the consumer context
```

The four smoke tests **executed**, they did not skip: the run installs Chromium for the Playwright
version that was actually resolved. Selection expressions are the repository's own, `production`
excluded, so no live-site test runs. The only writes are to a temporary directory, removed on exit.

**It fails loudly rather than quietly.** `pwpf.__file__` must start with the throwaway
`site-packages`; the checkout must appear in neither `sys.path` nor `PYTHONPATH` (both are
inspected inside the consumer process, not assumed); and the consumer directory must contain no
`pwpf/` and no root `conftest.py`, so plugin discovery can only come from the entry point.

## 3. Ownership inventory

Classified by tracing imports and responsibilities, not by directory name. Counts are tracked
files.

### 3.1 Framework — moves to the new repository [P]

| Current path | Destination | Why | Dependencies / import changes | Tests & CI affected | Risk / rollback |
|---|---|---|---|---|---|
| `pwpf/` (17) | framework repo, unchanged | Imports nothing from `apps/` or `tests/` [V]; every path resolves from the consumer root | None — the package is already self-contained | Framework CI runs its self-tests | Low. The wheel is the interface; roll back by reinstalling the previous version |
| `tests/test_app_config.py`, `test_browser_config.py`, `test_framework_config.py`, `test_logger.py`, `test_report_embedder.py`, `test_report_path.py`, `test_allure_cleanup.py`, `test_project_root.py`, `test_wheel_contents.py` (9) | framework repo | Import only `pwpf.*`; their `apps/`, `pytest.ini` and consumer references are **synthetic fixtures** built in `tmp_path`, not this repository's files [V] | None | These leave the consumer's suite: its self-test count drops from 150 to ~16 | Low. They never touched application code |
| `tests/test_console_logging.py` (1) | framework repo | Tests the plugin's console/page-error listeners through the `page` fixture | Needs a browser, so the framework repo needs a Playwright install in CI | Framework CI gains a browser job | Low, but see finding 5.3 |
| `pyproject.toml`, `LICENSE` | framework repo | Distribution metadata and the licence it ships | The consumer gets its own `pyproject.toml`/requirements for *its* dependencies | Installed Package CI job | Low |
| `scripts/verify_installed_package.py` | framework repo | Verifies the framework's own artifact; reads `pyproject.toml`, `pwpf/`, `LICENSE` at its repo root | None | Moves with the Installed Package job | Low |
| CI: **Installed Package** job | framework repo | Gates the distribution | — | — | Low |
| `DESIGN.md` §§1–7, 9–12 (framework design, packaging, reporting internals) | framework repo, split out | Describes framework internals | Links must be re-pointed — see finding 5.5 | None | Medium: documentation is the most entangled asset here |

### 3.2 Consumer — stays in this repository [P]

| Current path | Why it stays | Changes needed at extraction | Risk |
|---|---|---|---|
| `apps/` (33: 4 applications) | The applications under test, their config, pages, locators, test data and scenarios | None | — |
| `tests/api/`, `tests/myntra/`, `tests/sample_app/`, `tests/uitesting_playground/`, `tests/web_search/`, `tests/tmp/` (13) | Consumer-owned tests, including the four `tests/<app>/conftest.py` that bind `app_config` | None — the dry run runs exactly these [V] | — |
| `pytest.ini` | Selection policy, markers and reporting flags are the consumer's | Must declare `pytest-html`/`pytest-xdist` itself — finding 5.1 | Medium until that is decided |
| `conftest.py` (root, one line) | Exists only to load the plugin from the source tree | **Delete.** The entry point supplies it; the dry run's consumer has no conftest and still gets fixtures and markers [V] | Low |
| `requirements.in` / `requirements.txt`, `requirements-ai.in` / `requirements-ai.txt` | The test-runtime lock for *this* project | Replace the implicit framework-from-checkout with an explicit pinned dependency (§4) | Medium — this is the actual switchover |
| `tests/test_ci_production_exclusion.py`, `tests/test_quarantine_policy.py` (2) | Read **this repository's** `.github/workflows/ci.yml` and `pytest.ini` [V] — they police consumer policy, not framework code | `_plugin_generic_suite_dirs()` reads `pwpf/plugin.py` by path; after extraction it must read the **installed** module's source instead | Medium: a real code change, named here so it is not a surprise |
| CI: PR Smoke, Regression, Cross-Browser, Quarantined | Run consumer tests | Add `playwright install` for the resolved version (finding 5.2) and install the framework from its pinned source | Medium |
| `.pre-commit-config.yaml`, `.secrets.baseline`, `.gitignore` | Repository hygiene | Each repo keeps its own | Low |

### 3.3 AI scenario-authoring toolkit — split, deliberately [P]

| Component | Owner | Why |
|---|---|---|
| `ai_testing/README.md`, `ai_testing/prompts/` (10), `ai_testing/templates/` (2) | **Consumer** | Prompts and briefs are about *these* applications and this team's review process; they are documentation, not code, and are excluded from the wheel already [V] |
| `docs/ai-testing/` (7 documents) | **Consumer** | The workflow, review checklist, scenario-authoring rules and lifecycle are the consumer's governance |
| `apps/*/scenarios/*.yaml`, the approval lifecycle | **Consumer** | Scenario expectations belong to whoever owns the application |
| `pwpf/ai_testing/validate_catalog.py` + `schemas/scenario.schema.json` | **Framework** | Generic code operating on consumer data: it reads the consumer's `pytest.ini`, `apps/*/scenarios/` and `tests/` from the resolved project root [V] (`validate_catalog.py:312`). Ships as package data behind the `ai` extra |
| CI: Scenario Catalog job | **Consumer** | Validates the consumer's catalogs; installs the framework's `ai` extra to get the validator |
| `tests/test_scenario_catalog.py` | **[?] Split** | It is two tests in one file: the validator's rule behaviour (framework) and "this repository's catalog is valid" (consumer, and already covered by the Scenario Catalog job). Decide at extraction; the cheap answer is to move the rule tests and let the CI job carry the repository-specific assertion |

### 3.4 Staying where it is

- **`scripts/extraction_dry_run.py`** — a *consumer-side* tool. It proves this repository can
  consume the wheel, so it belongs to the repository doing the consuming, and it keeps working
  after extraction with the wheel coming from a release instead of a local build.
- **`.github/workflows/ci.yml`** — not moved; split. Both repositories need a lint/type job; the
  rest divides as in the tables above.
- **`README.md`** — stays, but shrinks: its framework-architecture sections follow `DESIGN.md`
  into the new repository.

## 4. How the consumer should depend on the framework

| | Git URL pinned to a tag/commit | Private package index | Local wheel artifact |
|---|---|---|---|
| **Reproducibility** | Exact with a commit SHA; a tag can be moved, a SHA cannot | Exact, immutable once published; hashes pinnable | Exact for the build that produced it, and nothing records where it came from |
| **Auth / secrets** | None for a public repo; a deploy key or PAT for a private one, in CI secrets | A token in CI and in every developer's `pip.conf` | None |
| **CI complexity** | One `pip install` line | Index URL plus credential plumbing | A build step, or an artifact passed between jobs |
| **Developer experience** | `pip install -e ../playwright-pytest-framework` for local work, pinned ref otherwise | Familiar `pip install playwright-pytest-framework==0.1.0` | Awkward: everyone needs the artifact |
| **Versioning / release** | Tag the framework repo; no publish step | Needs a release workflow and a version bump policy | None, which is also the problem |
| **Rollback** | Change one ref back; the old SHA always exists | Pin the previous version | Keep old artifacts somewhere |
| **Maintenance** | No infrastructure | An index to run or pay for, tokens to rotate | Grows unmanageable |

**Recommendation: a Git URL pinned to an immutable tag for the initial extraction** [P] —
`playwright-pytest-framework @ git+https://github.com/abhay-scaler/playwright-pytest-framework@v0.1.0`
in the consumer's requirements, with the resolved commit hash recorded in the lock file.

Why: it needs no index, no credentials and no release automation on day one, while still being
reproducible, because pip records the resolved commit. The framework is one consumer's dependency
today, so an index would be infrastructure bought ahead of need. Rollback is a one-line revert to
the previous tag. The local wheel stays useful for development (`pip install dist/*.whl`) and is
what the dry run already exercises, and the migration to a private index later is a change of one
requirement line plus a publish job — nothing in the framework needs to know which path is in use,
since `pip wheel` and `python -m build` are already proven to work from the source tree [V].

## 5. Boundary findings, all verified

**5.1 The consumer owns two dependencies the framework does not declare.** `pytest.ini`'s
`addopts` ask for `--html` and the repository runs `-n auto`, but `pytest-html` and
`pytest-xdist` live in the framework's `dev` extra — development tooling, not something every
consumer needs. The dry run had to install them explicitly for this repository's `pytest.ini` to
work at all [V]. Decide at extraction: either the consumer declares them (correct, and the dry
run documents it) or the framework grows a `report` extra for them. **[?]**

**5.2 Playwright's browser build follows the resolved Playwright version.** The framework's floor
is `playwright>=1.48.0`, so a consumer can resolve a version whose browser build is not what the
machine has cached; the first dry-run attempt skipped all four smoke tests until Chromium was
installed for the resolved version [V]. Consumer CI must run `python -m playwright install` after
installing the framework, keyed on the version pip actually resolved — the existing jobs do this
from `requirements.txt`'s pin, which will no longer be where the Playwright version comes from.

**5.3 `tests/test_console_logging.py` names a logger that no longer exists.** Lines 8 and 23 pass
`logger="conftest"` to `caplog.at_level`; the plugin's logger has been `pwpf.plugin` since #8. The
three tests pass [V], so the records are reaching `caplog` somehow — but a logger configured the way
`pwpf.utils.logger` configures them (`propagate = False`) is *not* visible to `caplog` in isolation
[V], so the capture may be incidental rather than what the test intends. Worth resolving before the
file moves to the framework repository; not a breakage, and out of scope here. **[?]**

**5.4 The policy guards read framework source by path.** `tests/test_ci_production_exclusion.py`
parses `pwpf/plugin.py` as text to keep `GENERIC_SUITE_DIRS` in step with the plugin's own
constant. After extraction that file is in site-packages, so the guard must locate the installed
module (`importlib.util.find_spec`) instead of a repository-relative path. Named in §3.2 as a
required change.

**5.5 Documentation is the most entangled asset.** 79 relative links resolve today [V]; of those,
**9 cross from the AI-toolkit documents into framework paths**, **7 point into consumer paths**, and
**15 point at `DESIGN.md`/`README.md`**, which themselves describe both halves (1029 and 487 lines).
Splitting the prose is the largest single piece of extraction work and the easiest to get wrong —
a broken link check is the cheapest guard and already exists as a one-file script pattern in this
repository's review history.

**5.6 The root `conftest.py` becomes unnecessary.** It exists so the source tree can develop the
plugin. The dry run's consumer has none and still receives every fixture and marker [V], so it is
deleted at extraction rather than carried.

## 6. Migration sequence [P]

Nothing below has been performed.

1. **Freeze a reference.** Tag the current `dev` as `v0.1.0` in this repository *before* anything
   moves, so the pre-extraction framework is addressable.
2. **Create the framework repository** and move §3.1 into it, history included where practical.
   Its CI: lint/type, its self-tests (with a browser for `test_console_logging.py`), and the
   Installed Package job.
3. **Make the artifact available.** Tag `v0.1.0` there too; no publishing step under the
   recommendation in §4.
4. **Switch the consumer.** Add the pinned requirement, delete `pwpf/`, `conftest.py`,
   `pyproject.toml`'s packaging sections and the migrated self-tests. Fix finding 5.4. Run
   `scripts/extraction_dry_run.py` against the *installed* framework rather than a local build.
5. **Update consumer CI.** Install the framework from the pinned ref, add `playwright install` for
   the resolved version, keep every existing selection expression and exclusion unchanged.
6. **Run the full consumer regression** (`-m "not production and not quarantined"`) on the merge
   push, and compare the counts against the pre-extraction baseline — today **136 passed, 5
   skipped** in CI on `dev` [V].
7. **Confirm both CIs independently**, then tag the consumer repository so the switchover commit is
   addressable.

### Rollback

Each step is reversible on its own, and the order above is chosen so the consumer keeps working
until step 4:

| If this fails | Restore by |
|---|---|
| Installation (bad ref, resolution conflict) | Reverting the requirements line to the previous ref; nothing else has changed yet |
| Plugin discovery (markers or fixtures missing) | Restoring the one-line root `conftest.py`, which loads `pwpf.plugin` directly and works whether or not the distribution is installed |
| Package resources (schema missing) | Pinning the previous framework tag; the Installed Package job in the framework repository is what should have caught it first |
| Consumer tests (counts differ from the baseline) | Reverting the switchover commit as a whole — the pre-extraction tree is tagged in step 1 and `pwpf/` is still in its history |
| Anything after the framework repository exists | Re-adding `pwpf/` from the tag in step 1; the framework repository can be abandoned without touching this one |

The irreversible part is social, not technical: once the framework has its own repository and
other consumers start using it, the API is public and `0.1.0` stops being a number nobody depends
on.

## 7. Exit criteria for the extraction milestone

- `scripts/extraction_dry_run.py` passes against an **installed, pinned** framework rather than a
  locally built wheel.
- Consumer regression counts match the pre-extraction baseline, exclusions intact: production 1,
  quarantined 0, blocking smoke 4.
- Framework CI is green on its own repository, Installed Package job included.
- Every documentation link resolves in both repositories.
- A rollback to the step-1 tag has been rehearsed at least once.
