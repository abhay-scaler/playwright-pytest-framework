# Stage 4 and extraction: proposal and prerequisites

Preparation, not extraction. Nothing here moves, renames or deletes a file, creates a repository,
creates or pushes a tag, publishes an artifact, changes package metadata or dependency behaviour,
rewrites the nine toolkit links or touches CI. What it does is turn the two remaining pieces of
[framework-extraction-readiness.md](framework-extraction-readiness.md) §6 — Stage 4 of
[documentation-split-plan.md](documentation-split-plan.md), and the switchover itself — into an
ordered, reviewable sequence with acceptance criteria, and surface the decisions that block it.

Measured on `dev` at `abdeb066` (PR #19's merge commit), working tree clean.

Legend: **[V]** verified by a command here · **[R]** recommended, reasons given · **[?]** needs a
human decision before extraction can start.

## 0. Why this document exists rather than an edit to the plan

[documentation-split-plan.md](documentation-split-plan.md) §8 states that it moves nothing and
tags nothing, and its §6 hands Stage 4 and the extraction to "the extraction PR". Editing it to
carry an extraction sequence would contradict its own scope. The two corrections this review owes
those documents are recorded in §7 below and assigned to the stage that rewrites the owning
section, the same convention the plan itself uses.

## 1. Where `dev` stands [V]

| Check | Result |
|---|---|
| PR #19 | **merged** at 2026-10-25T10:14:19Z; merge commit `abdeb066`, parents `6942a8f` + `3d84df0` |
| `dev` tip | `abdeb066` — `git merge-base --is-ancestor 3d84df0 origin/dev` → true |
| Merge-push CI | run `40183941517`, event `push`, sha `abdeb066`, **completed / success** |
| Jobs | Lint & Type Check, Scenario Catalog, Installed Package, Quarantined, **Regression Suite (Chromium) success**; PR Smoke and Cross-Browser skipped by event condition |
| Regression tally | **173 passed, 5 skipped** |
| Working tree | clean |

No merge was attempted: the PR was already merged, so this is verification, not a second merge.

## 2. Framework repository and release identity

### 2.1 A name collision blocks the pinned URL **[?]**

`origin` is `abhay-scaler/playwright-pytest-framework` [V] — and that is **this** repository, the
consumer. The distribution built from it is also named `playwright-pytest-framework`
([pyproject.toml](../pyproject.toml), `name`) [V]. GitHub will not host two repositories of one
name under one owner, so the framework repository cannot simply take it.

This makes the URL already written into
[framework-extraction-readiness.md](framework-extraction-readiness.md) §4 —
`git+https://github.com/abhay-scaler/playwright-pytest-framework@v0.1.0` — point at the consumer
repository, not the framework, under every option below. It is a recommendation written before the
collision was noticed, not a decision. **No requirement line can be written until this is
settled**, and this document deliberately invents no URL.

| Option | What it costs | What it buys |
|---|---|---|
| **A. Rename this repository** (it is the consumer: e.g. a suite/automation name), freeing `playwright-pytest-framework` for the framework **[R]** | one rename; GitHub redirects the old URL, so the five PR links in these documents keep resolving; every clone's `origin` needs updating | repository name == distribution name == what the pinned requirement shows a reader |
| **B. Give the framework repository a different name** (e.g. `pwpf`) | the pinned URL and the package name disagree, which every new reader has to reconcile | nothing to rename |
| **C. Put the framework under a different owner or organisation** | an org to create and administer | separates ownership cleanly, if that is wanted for other reasons |

A is recommended because the distribution name is the thing already published in metadata and in
the draft's install instructions, and it is the name that cannot change cheaply later. B is a
legitimate fallback and costs nothing technically.

### 2.2 What `v0.1.0` should identify **[R]**

Readiness §6 asks for `v0.1.0` in *this* repository at step 1 and again in the framework
repository at step 3. Two different objects under one name, in two repositories, is an ambiguity
worth removing before either exists:

- **This repository** gets a freeze tag that says what it is — a pre-extraction baseline of the
  combined tree, not a framework release. It is what the rollback table restores from, and it is
  never what a consumer pins.
- **The framework repository** gets `v0.1.0`, on the commit whose tree produces the 0.1.0
  distribution. That is the tag a consumer pins, and the only one that needs to match the package
  version.

A tag is mutable; the lock file is not (§3.2). So the tag is for humans and the recorded commit is
the reproducibility guarantee.

### 2.3 The release artifact reproduces from the current source [V]

Built from `abdeb066` with `pip wheel --no-deps`, reading the wheel's own metadata rather than the
build log:

```
playwright_pytest_framework-0.1.0-py3-none-any.whl
  Name: playwright-pytest-framework
  Version: 0.1.0
  Requires-Python: >=3.12
  License-Expression: MIT
  [pytest11]        pwpf.plugin = pwpf.plugin
  [console_scripts] pwpf-validate-catalog = pwpf.ai_testing.validate_catalog:main
```

So the version a `v0.1.0` tag would claim is the version the source actually produces, and the
entry point that makes the plugin discoverable is in the artifact. The build's `build/` and
`*.egg-info` droppings were removed; the tree is clean [V]. **No tag was created** —
`git tag --list` and `git ls-remote --tags origin` are both empty [V], which also means nothing in
either repository currently pins anything.

## 3. Consumer dependency

### 3.1 What the consumer depends on today [V]

[requirements.in](../requirements.in) lists the framework's *own* dependencies as if they were the
consumer's — `pytest`, `playwright`, `allure-pytest`, `pytest-rerunfailures` — alongside the two
that genuinely are (`pytest-html`, `pytest-xdist`) and the lint toolchain. The framework itself is
not a dependency at all: it is on `sys.path` because it is in the working directory, and
[conftest.py](../conftest.py) loads `pwpf.plugin` from the source tree. That is the implicit
dependency extraction has to make explicit.

### 3.2 Pinning mechanism — rehearsed, not assumed [V]

The recommendation in readiness §4 (a git URL pinned to an immutable tag, no index on day one)
survives review, and its reproducibility claim is now measured rather than argued. Rehearsed
against a throwaway bare clone of this repository with a rehearsal tag — no URL invented, nothing
published:

- `pip install "playwright-pytest-framework @ git+file://<clone>@<tag>"` → exit 0.
- `direct_url.json` records `commit_id: abdeb06611338c42076ac36c181c79af4428105f`,
  `requested_revision: <tag>`.
- `pip freeze` emits the requirement **re-pinned to the commit**, not the tag — so a lock file
  generated after install pins the SHA even when the input named a tag. This is precisely the
  "a tag can be moved, a SHA cannot" guarantee §4 claims, and it is what makes a tag acceptable as
  the input.
- From outside the checkout, `import pwpf.plugin` resolves to the venv's `site-packages`, and the
  `pytest11` entry point `pwpf.plugin` is visible to `importlib.metadata` [V].

One measurement artifact worth recording, because it is the trap the dry run exists to catch: the
same import run with the repository as the working directory resolved to the *checkout*, since `''`
precedes `site-packages` on `sys.path`. Re-run with `-I` and from another directory, it resolves to
`site-packages` [V]. Any verification of "it came from the install" must control the working
directory — the dry run already does, by running the consumer from its own temporary directory.

### 3.3 What the consumer must end up with **[R]**

1. `requirements.in` keeps only what the consumer owns — `pytest-xdist`, `pytest-html` (for its
   `pytest.ini`'s `--html`, or as the framework's `[report]` extra), the lint toolchain — plus one
   direct reference to the framework at a tag, with extras: `playwright-pytest-framework[ai,report]
   @ git+<framework URL>@v0.1.0`. The framework's own dependencies leave `requirements.in` and
   arrive transitively, pinned by the lock.
2. `requirements.txt` is regenerated so the lock records the resolved framework commit and the
   transitive pins. **Prerequisite:** confirm the lock tool keeps the direct reference and the
   resolved SHA; `pip freeze` does [V], the project's compiler is untested against a VCS
   requirement **[?]**.
3. **No editable install and no local wheel in CI.** `pip install -e ../playwright-pytest-framework`
   stays a developer convenience and must appear in no workflow; the dry run's locally built wheel
   stays available behind an explicit flag (§5.1) but is not what CI validates.

### 3.4 Index or not **[R]**

No package index for the initial extraction, as readiness §4 concludes — one consumer, no
credentials to plumb, no release automation to build, and migration later is one requirement line
plus a publish job. This document adds no new mechanism and names no index.

## 4. Stage 4: link migration

### 4.1 The nine framework-pointing links, as they stand [V]

`grep` over `ai_testing/` and `docs/`, exactly the nine the plan's §2.2 predicted:

| # | Source | Target | Disposition **[R]** |
|---|---|---|---|
| 1 | [ai_testing/README.md](../ai_testing/README.md):42 | `../pwpf/ai_testing/schemas/scenario.schema.json` | **pinned-tag URL** — readers open the schema to author catalogs |
| 2 | ai_testing/README.md:43 | `../pwpf/ai_testing/validate_catalog.py` | **pinned-tag URL** — readers follow it to understand a rule code |
| 3 | ai_testing/README.md:98 | `../pwpf/plugin.py` | prose: name the module, drop the link |
| 4 | ai_testing/README.md:104 | `../pwpf/core/base_page.py` | prose |
| 5 | ai_testing/README.md:112 | `../pwpf/core/app_config.py` | prose |
| 6 | ai_testing/README.md:121 | `../pwpf/core/api_client.py` | prose |
| 7 | ai_testing/README.md:124 | `../pwpf/utils/helpers.py` | prose |
| 8 | ai_testing/README.md:125 | `../pwpf/utils/logger.py` | prose |
| 9 | [docs/ai-testing/scenario-authoring.md](ai-testing/scenario-authoring.md):8 | `../../pwpf/ai_testing/schemas/scenario.schema.json` | **pinned-tag URL** — same schema, same reason |

Three become version-pinned URLs, six become prose. The split follows what a reader does with
them: the schema and the validator are artifacts people read to get their own work right, while
the other six are citations that say *where behaviour lives* — a sentence naming the module serves
that, and a URL into a moving target does not. Pinning to the tag rather than a branch matters
here: unpinned source links rot silently as the framework changes, which is the failure mode this
whole exercise is trying not to reproduce.

**Blocked on §2.1 and §2.2**: three of the nine need a repository URL and a tag that do not yet
exist. The six prose rewrites are not blocked, but splitting the stage across two PRs to land them
early buys nothing — the stage is nine lines in two files.

### 4.2 The draft's `> **Draft.**` block [V]

[framework-readme-draft.md](framework-readme-draft.md) lines 11–18 are a block quote holding the
only three links in the file that point into this repository:
`documentation-split-plan.md`, `../DESIGN.md`, `../README.md`.

**Disposition [R]:** the block is deleted whole when the file becomes the framework repository's
`README.md`, which removes all three links in one edit and leaves nothing in the file pointing at
the consumer — the property the block itself asserts, and the reason it was written as one
contiguous block rather than as footnotes. The extraction PR verifies it by running the link
checker in the framework repository: with no `DESIGN.md`, no `README.md` beside it and no split
plan, any surviving reference fails there, so the check is not a matter of inspection.

The copy in this repository is **deleted** at the same time. Keeping it would leave a third copy of
the framework contracts in the consumer, which is what decision 1 forbids, and the file's own
header says it exists only until the extraction.

### 4.3 Deleting the draft breaks an inbound link [V]

[documentation-split-plan.md](documentation-split-plan.md):223 links to the draft, and §6's Stage 3
entry names the path in prose (line 314). When the draft leaves, line 223 breaks and the checker
fails — which is the checker working.

**Disposition [R]:** in the extraction PR, line 223 becomes prose, or a pinned-tag URL to the
framework repository's `README.md` under the same rule as §4.1. The prose mention at line 314 needs
no change: it names a path in a record of what Stage 3 did, which stays true.

### 4.4 `documentation-split-plan.md` must not travel **[R]**

It describes *this* repository's migration: section ownership of `DESIGN.md` and `README.md`, the
consumer's link inventory, five stages of consumer edits. In the framework repository it would
document a split that repository never performed.

- It stays here, unmoved, as the record of how the consumer got its shape. Five links from four documents
  point at it from here [V] — [README.md](../README.md):99, [DESIGN.md](../DESIGN.md):44 and :449,
  [framework-extraction-readiness.md](framework-extraction-readiness.md):223,
  [docs/ai-testing/scenario-authoring.md](ai-testing/scenario-authoring.md):143 — all consumer-side
  and all unaffected.
- The extraction PR must copy **no** `docs/` page into the framework repository. The framework
  repository's documentation is the draft, as `README.md`, and nothing else (plan §4.2, decision 5).
- `framework-extraction-readiness.md` is consumer-owned for the same reason (readiness §3.4 already
  assigns `scripts/extraction_dry_run.py` to the consumer on that logic).

### 4.5 What stays, and keeps working

18 links point at `DESIGN.md` and 18 at `README.md` [V]. Both filenames survive in the consumer
(plan §4.2, decision 6), so those 36 links keep resolving; what the extraction changes is their
*content*, and the anchors among them are plan §2.4's business, not Stage 4's. The six
consumer-targeted boundary crossings of plan §2.2 (`../pytest.ini`, `../requirements-ai.*`,
`../../tests/test_ci_production_exclusion.py`, `../../apps/myntra/scenarios/shopping_journey.yaml`,
`../../pytest.ini`) are untouched: the AI toolkit and the consumer stay together.

## 5. Extraction readiness

### 5.1 Validating against an installed, pinned artifact [V] → **[R]**

[scripts/verify_installed_package.py](../scripts/verify_installed_package.py) needs **no change**:
it builds and interrogates the framework's own wheel from its own repository root (`REPO_ROOT`,
`build_wheel` at lines 166–197, `source_package_members` at 232, globbing `REPO_ROOT/pwpf` at 244), and
it moves to the framework repository with the Installed Package job. Building from source is the
right question *there* — the artifact is that repository's output.

[scripts/extraction_dry_run.py](../scripts/extraction_dry_run.py) is the one that must change,
because its question is the consumer's: it currently builds the wheel it then installs
(`build_wheel`, lines 119–137; called at line 231), which after extraction would be building an
artifact this repository no longer owns. The exact changes:

| Where | Change |
|---|---|
| `main()`, lines 217–233 | add `--framework <requirement>`: a PEP 508 requirement to install instead of building. Default keeps today's behaviour (build from `REPO_ROOT`), so the script stays usable in this repository until `pwpf/` leaves and in developer loops afterwards |
| `make_venv()`, line 156 | `requirement = f"{wheel}[{extras}]"` becomes a helper that formats both forms: a wheel path with extras, or `playwright-pytest-framework[ai,report] @ <url>` — extras go on the *name*, before the `@`, for a direct reference |
| line 437 | the base-install venv takes the same requirement, so "a base install is rejected by this consumer's `pytest.ini`" still tests the pinned artifact rather than a local build |
| lines 285–292 | the check reads "imported from the installed wheel, not this checkout"; with a pinned artifact there is no checkout, so the wording and the `REPO_ROOT` comparison become "not this project". The assertion itself — `pwpf.__file__` under the venv's `site-packages` — stays exactly as load-bearing (§3.2's cwd artifact is why) |
| lines 409–414 | "no artifacts appeared in the framework checkout" compares `artifact_dirs(REPO_ROOT / "pwpf")` to the empty set. `artifact_dirs` tests `is_dir()` [V], so after extraction the `pwpf/` half is vacuously true rather than broken; the meaningful half is `artifact_dirs(REPO_ROOT) == before_checkout`, and the check should be reduced to that rather than left looking stronger than it is |
| `make_consumer()`, lines 168–183 | unchanged. It copies `apps/`, the six consumer test suites and `pytest.ini` [V]; the "no `pwpf/`, no root `conftest.py`" check becomes an invariant of the repository instead of of the copy, which is a strengthening, not a loss |

**Acceptance:** `python scripts/extraction_dry_run.py --framework "<pinned requirement>"` reports
18/18 with the framework installed from the pinned ref, the four smoke tests **executing** (not
skipping), and the selection invariants intact: production 1, quarantined 0, blocking smoke 4.

### 5.2 Scenario-catalog test ownership [V]

Re-measured on `abdeb066`, confirming plan decision 4: **22 collected**; **20 take `tmp_path`** and
validate the validator against synthetic repositories → **framework**; **2 take no arguments** →
[tests/test_scenario_catalog.py](../tests/test_scenario_catalog.py):383
`test_the_committed_catalog_is_valid` and :389
`test_no_committed_scenario_lets_a_live_site_gate_ci`.

- The 20 move with `pwpf/ai_testing/validate_catalog.py`.
- :383 duplicates the Scenario Catalog CI job and may go either way.
- **:389 must stay with the consumer.** It asserts that no committed scenario lets a live site gate
  CI — a policy about *these* applications that the CI job does not cover. If the file moves
  wholesale, this test leaves silently and the policy stops being enforced.

**Acceptance:** after extraction, `-m "not production and not quarantined"` in this repository
still collects `test_no_committed_scenario_lets_a_live_site_gate_ci`, and its sibling
`tests/test_ci_production_exclusion.py` still passes — it resolves `pwpf/plugin.py` through
`find_spec` since #14, so it reads the installed module (readiness §5.4) [V].

### 5.3 Root `conftest.py` [V]

[conftest.py](../conftest.py) is a docstring and one line, `pytest_plugins = ["pwpf.plugin"]`. It
is **deleted** at extraction: the entry point supplies the plugin, and the dry run's consumer has
no conftest and still receives every fixture and marker (readiness §5.6) [V]. It is also the first
rollback lever in readiness §6 — restoring it loads the plugin directly — so it is deleted in the
switchover commit, not before, and the rollback note should say that recovering it means
`git revert`, not `git checkout` of a file that still exists.

### 5.4 Browser installation for the resolved version [V]

Every browser job resolves the Playwright version by grepping the lock:
`grep -oP '(?<=^playwright==)[0-9.]+' requirements.txt`
([.github/workflows/ci.yml](../.github/workflows/ci.yml), the "Resolve pinned Playwright version"
step, repeated in PR Smoke, Regression, Cross-Browser and Quarantined), and keys the browser cache
on it [V]. Today `requirements.txt` pins `playwright==1.62.0` directly [V].

After extraction Playwright arrives *transitively*, via the framework. The grep keeps working only
if the regenerated lock still contains a top-level `playwright==` line — likely, since lock files
flatten transitives, but **unverified until the lock is regenerated against a real pinned ref
[?]**.

**Recommendation [R]:** stop inferring the version from a file and read it from the environment
that will run the browser, after installing requirements:
`python -c "import importlib.metadata as m; print(m.version('playwright'))"`. It is correct whether
the pin is direct, transitive or resolved from a range, it cannot silently disagree with what is
installed, and it keeps the cache key honest. This is a CI change and belongs to the extraction's
step 5, not here.

### 5.5 Remaining blockers

| Blocker | Evidence | Clears when |
|---|---|---|
| No repository name decided | §2.1: `origin` already holds the distribution's name [V] | the user picks A, B or C |
| No URL, therefore no pinned requirement and no pinned doc links | §2.1, §4.1 — three of the nine links need it | the repository exists |
| No tag anywhere | `git tag --list` and `git ls-remote --tags origin` both empty [V] | the freeze tag and `v0.1.0` are created, in that order |
| Lock-tool behaviour against a VCS requirement unverified | §3.3, §5.4 — `pip freeze` re-pins to the SHA [V], the project's compiler untested | the lock is regenerated against a real ref |
| Python support range unverified | §6 | a matrix runs |

None is architectural. Readiness §1's conclusion — "what remains is mechanical" — still holds; the
mechanical parts just have an order, below.

## 6. Python compatibility

[pyproject.toml](../pyproject.toml) declares `requires-python = ">=3.12"` [V], and the wheel
carries `Requires-Python: >=3.12` [V]. **Only 3.12 has been exercised.** Every one of the seven CI
jobs pins `python-version: "3.12"` [V], the only classifier is
`Programming Language :: Python :: 3.12` [V], and this machine's development virtualenv is 3.12 [V].
So `>=3.12` is an **unverified compatibility range**, not a tested one: 3.13 and 3.14 are promised
to installers and have never been run.

Two honest ways to close the gap; the first is recommended, and neither belongs to this task:

1. **Test the range [R].** In the framework repository, run its self-tests and the Installed
   Package job across `3.12` and `3.13` — `3.13` is where the promise is most likely to be tested
   by a real user, and the framework's dependency set (pytest, playwright, allure-pytest,
   pytest-rerunfailures) is the thing to watch. Add `3.14` when those four resolve on it. The
   browser-dependent test (`tests/test_console_logging.py`) needs a Playwright install in whichever
   job runs it. The consumer keeps a single pinned interpreter: it is an application, not a library,
   and a matrix there buys nothing.
2. **Narrow the declaration** to an upper bound until a matrix exists. Cheaper, and it makes the
   metadata true, but an upper bound on `requires-python` is a blunt instrument that blocks
   installs on interpreters that may work.

Classifiers follow whatever is tested, and only what is tested. **Not done here:** this proposal
changes no metadata and adds no job.

## 7. Two corrections owed to the existing documents

Recorded, with evidence, and assigned — not fixed here, following the plan's own convention of
letting the stage that rewrites a section carry its corrections.

| Document | Claim | Measured | Assigned to |
|---|---|---|---|
| [framework-extraction-readiness.md](framework-extraction-readiness.md) §6, step 6 | the pre-extraction regression baseline is "**136 passed, 5 skipped** in CI on `dev`" | **173 passed, 5 skipped** on `abdeb066` [V] — the suite has grown by 37 tests since that sentence | the extraction PR, which must compare against a baseline measured on the commit it extracts from |
| [documentation-split-plan.md](documentation-split-plan.md) §4.2, decision 5 | the draft carries the framework sections "in **303 lines**" | **304** [V] | the extraction PR, where that sentence becomes past tense |

The baseline figure is the one that matters: readiness §7's exit criterion compares post-extraction
counts against it, and an exit criterion measured against a stale number either passes wrongly or
blocks wrongly.

## 8. Proposed order

Stage 4 is **not** first. Three of its nine links need a URL and a tag, so the plan's own note —
"blocked on the extraction's Step 1" — means the documentation stage lands inside the extraction
sequence, not before it.

| # | Step | Depends on | Acceptance | Rollback |
|---|---|---|---|---|
| 1 | Decide the repository name and ownership (§2.1) | — | a name exists; no code change | — |
| 2 | Freeze this repository: a pre-extraction baseline tag on `dev`, and the regression baseline re-measured on that commit (§7) | 1 | tag resolves; counts recorded in the extraction PR | delete the tag |
| 3 | Create the framework repository; move §3.1 of readiness into it; its CI = lint/type + self-tests (with a browser) + Installed Package | 1, 2 | `verify_installed_package.py` 24/24 **in that repository** | abandon the repository; this one is untouched |
| 4 | Tag `v0.1.0` there, on the commit whose tree builds 0.1.0 (§2.3) | 3 | the built wheel's `Version` matches the tag | move or delete the tag before anyone pins it |
| 5 | **Stage 4 of the split plan**: rewrite the nine links (§4.1) | 4 | `grep -r '\.\./pwpf/\|\.\./\.\./pwpf/' ai_testing/ docs/ai-testing/` empty; link checker exit 0 | revert the commit |
| 6 | Teach the dry run to take a pinned requirement (§5.1) | 4 | `--framework "<ref>"` → 18/18, smoke executing, selections 1/0/4 | revert; the default path still builds locally |
| 7 | Switch the consumer: pinned requirement in `requirements.in`, lock regenerated, delete `pwpf/`, root `conftest.py`, the packaging half of `pyproject.toml`, the 9 migrated self-tests and the 20 catalog rule tests; keep `test_no_committed_scenario_lets_a_live_site_gate_ci` (§5.2) | 5, 6 | step 6's dry run green against the pinned ref; `pwpf` imports from `site-packages` | revert the switchover commit; `pwpf/` is in history and at the step-2 tag |
| 8 | Update consumer CI: install from the pinned ref, resolve the Playwright version from the environment (§5.4), every selection expression unchanged | 7 | all seven jobs green; `-m "not production and not quarantined"` matches the step-2 baseline | revert the workflow commit |
| 9 | Delete the draft from this repository and re-point the plan's line 223 (§4.2, §4.3) | 3, 7 | link checker exit 0 here and in the framework repository | revert |
| 10 | Rehearse the rollback once, from the step-2 tag, and record it | 7, 8 | a rehearsal is described in the PR, not merely offered | — |

Steps 1–4 touch this repository only at step 2 (a tag), so the consumer keeps working until step 7
— the same property readiness §6 was designed around.

## 9. Acceptance criteria for the extraction milestone

Readiness §7's five criteria stand. This review makes three of them measurable and adds two:

1. `extraction_dry_run.py` passes **against the pinned ref**, 18/18, smoke executing — §5.1.
2. Consumer regression matches the baseline **measured at step 2**, not the stale 136 — §7.
3. Framework CI green in its own repository, Installed Package included — step 3.
4. Link checker exit 0 in **both** repositories, and no `../pwpf/` link anywhere — §4.1, §4.2.
5. A rollback from the step-2 tag has been rehearsed — step 10.
6. **New:** `test_no_committed_scenario_lets_a_live_site_gate_ci` still collected here — §5.2.
7. **New:** the Python support range is either tested or narrowed — §6.

## 10. What this document does not do

No repository created. No tag created or pushed. No framework file moved, renamed or deleted. No
package metadata or dependency behaviour changed. None of the nine links rewritten. No CI workflow
or application code touched. Nothing merged automatically. The pinning rehearsal of §3.2 used a
throwaway local clone and a temporary virtualenv, both removed; it published nothing and invented
no URL.
