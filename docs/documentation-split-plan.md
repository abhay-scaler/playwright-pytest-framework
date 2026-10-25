# Documentation split: inventory and staged plan

Planning only. Nothing here has been moved, renamed, rewritten or deleted, no CI was touched, and
the link checker this plan proposes has deliberately **not** been implemented — that is Stage 0's
job. This is the §5.5 half of
[framework-extraction-readiness.md](framework-extraction-readiness.md): the last large piece of
extraction work, and the one most likely to go wrong, because prose has no test suite.

Measured on `dev` at `7bcc4b4`.

Legend: **[V]** measured in this repository · **[R]** recommended, follows a stated default ·
**[?]** unresolved, needs human judgement.

## 1. Counting method

Stated first, because every number below depends on it and an unstated method is how a figure like
"79 links" survives three PRs.

- **Scope:** `*.md` at the repository root, `docs/**/*.md`, `ai_testing/**/*.md` — **13 tracked
  files**, plus this plan while it is untracked.
- **Pattern:** Markdown inline links — square-bracketed text followed by a parenthesised
  target. `http://`, `https://` and `mailto:` targets are excluded; reference-style links and bare
  URLs do not occur in these files. (This bullet deliberately avoids writing the pattern out:
  prose that quotes link syntax is itself read as a link by a naive checker, which is how the
  requirement below was found.)
- **Three classes**, counted separately because they fail differently:
  - **file** — `path`, no fragment. Breaks when the file moves. **66** [V]
  - **file+anchor** — `path#fragment`. Breaks when the file moves *or* when the heading is renamed
    or moves to the other repository, and a file-existence check cannot see the second case. **15** [V]
  - **in-page anchor** — `#fragment` only, almost all of them the README table of contents. Breaks
    when a heading in the same document is renamed. **16** [V]
- **"Relative links"** in the figures below means file + file+anchor: **81** [V], **0 broken** [V].
  Including this plan's own single link, 82. The readiness document's §5.5 says 79 — it was written
  before its own links existed; Stage 0 owns that correction and no other stage touches it.
- **Ownership** is assigned per path, not per directory: `pwpf/`, `scripts/verify_installed_package.py`,
  `pyproject.toml`, `LICENSE` → framework. `apps/`, `tests/<app>/`, `tests/test_ci_production_exclusion.py`,
  `tests/test_quarantine_policy.py`, `pytest.ini`, `conftest.py`, `requirements*`, `.github/`,
  `scripts/extraction_dry_run.py`, `docs/framework-extraction-readiness.md` → consumer.
  `ai_testing/**`, `docs/ai-testing/**` → AI toolkit (consumer-side). `DESIGN.md`, `README.md` →
  **mixed**, which is what this plan exists to resolve.

## 2. Link inventory

### 2.1 Totals

| Class | Count [V] | Breaks on |
|---|---|---|
| file | 66 | the target file moving |
| file+anchor | 15 | the file moving, or the heading being renamed/moved |
| in-page anchor | 16 | a heading in the same document being renamed |
| **relative (file + file+anchor)** | **81**, 0 broken | — |

### 2.2 Direct framework/consumer boundary crossings — **15** [V]

Source and target under different owners, target framework- or consumer-owned, **source not one of
the two mixed documents** (a link out of a mixed document is not yet a crossing: it becomes one, or
stops being one, depending on which half its source section lands in).

| Source | Target | Target owner |
|---|---|---|
| `ai_testing/README.md:42` | `../pwpf/ai_testing/schemas/scenario.schema.json` | framework |
| `ai_testing/README.md:43` | `../pwpf/ai_testing/validate_catalog.py` | framework |
| `ai_testing/README.md:98` | `../pwpf/plugin.py` | framework |
| `ai_testing/README.md:104` | `../pwpf/core/base_page.py` | framework |
| `ai_testing/README.md:112` | `../pwpf/core/app_config.py` | framework |
| `ai_testing/README.md:121` | `../pwpf/core/api_client.py` | framework |
| `ai_testing/README.md:124` | `../pwpf/utils/helpers.py` | framework |
| `ai_testing/README.md:125` | `../pwpf/utils/logger.py` | framework |
| `docs/ai-testing/scenario-authoring.md:8` | `../../pwpf/ai_testing/schemas/scenario.schema.json` | framework |
| `ai_testing/README.md:127` | `../pytest.ini` | consumer |
| `ai_testing/README.md:160` | `../requirements-ai.in` | consumer |
| `ai_testing/README.md:161` | `../requirements-ai.txt` | consumer |
| `docs/ai-testing/README.md:48` | `../../tests/test_ci_production_exclusion.py` | consumer |
| `docs/ai-testing/scenario-authoring.md:25` | `../../apps/myntra/scenarios/shopping_journey.yaml` | consumer |
| `docs/ai-testing/scenario-authoring.md:47` | `../../pytest.ini` | consumer |

**Correction to the earlier figure.** The readiness document and the first draft of this plan said
16. The 16th was `README.md:473 → docs/framework-extraction-readiness.md`, a link *from* a mixed
document, which this plan now classifies separately for the reason above. So: **15 crossings from
non-mixed sources + 1 from a mixed source = the 16 previously quoted** [V]. Only the nine
framework-targeted ones break at extraction; the six consumer-targeted ones are unaffected, because
the AI toolkit and the consumer stay together.

### 2.3 Links targeting the mixed root documents — **22** [V]

Ownership of each of these is **decided by §3**, not by the link: when its target section goes to
the framework repository the link becomes a cross-repository reference; when the section stays, it
stays a local link.

`README.md` → `DESIGN.md` ×6 (13, 145, 354, 419, 473, 492) · `ai_testing/README.md:151` →
`README.md#running-tests` · `ai_testing/templates/feature_brief.md:49` → `DESIGN.md` ·
`docs/ai-testing/README.md` ×5 (8 ×2, 71, 84, 105) · `docs/ai-testing/codegen-to-page-objects.md`
×2 (60, 84) · `docs/ai-testing/getting-started.md:4` → `README.md#installation` ·
`docs/ai-testing/scenario-authoring.md` ×3 (16, 71, 121) · `docs/ai-testing/troubleshooting.md:69` ·
`docs/ai-testing/workflow.md:124` → `README.md#known-limitations` ·
`docs/framework-extraction-readiness.md:19` → `../DESIGN.md`

### 2.4 Anchor links — **5** fragments in mixed documents, **4** genuinely endangered [V]

The first draft said "four anchor cases" and was right by accident. There are **five**
`file+anchor` links whose fragment lives in a mixed root document — the draft missed the most
exposed of them — and **four** of those five can actually break, because the fifth points at a
section that stays with the consumer:

| Source | Target fragment | Exposure |
|---|---|---|
| `README.md:13` | `DESIGN.md#adding-a-new-application` | **mixed → mixed today**, cross-repository after the split: README's framework half leaves while "Adding a New Application" is consumer-owned (§3.2) |
| `ai_testing/README.md:151` | `README.md#running-tests` | **not endangered:** "Running Tests" is consumer-owned and the AI toolkit stays with the consumer. Listed because its fragment lives in a document being split |
| `docs/ai-testing/getting-started.md:4` | `README.md#installation` | "Installation" is a **split** section — the fragment may cease to exist |
| `docs/ai-testing/README.md:105` | `README.md#known-limitations` | "Known Limitations" is a **split** section |
| `docs/ai-testing/workflow.md:124` | `README.md#known-limitations` | same |

A further **10** `file+anchor` links point within the AI toolkit (`ai_testing/README.md#house-rules`,
`#verified-framework-facts`, `#dependencies`, `docs/ai-testing/workflow.md#when-orchestration-would-be-justified`,
`scenario-authoring.md#validation`, `docs/ai-testing/README.md#production-safety`), and **16**
in-page anchors live in the README table of contents [V]. None of those cross the boundary, but all
31 fragments break silently under heading edits, which is the case for validating fragments rather
than file existence alone.

## 3. Section ownership

Line counts are section start to the line before the next `## ` heading [V].

### 3.1 `DESIGN.md` — 1,035 lines, 13 sections, 7-line preamble [V]

| § | Lines | Section | Owner | Note |
|---|---|---|---|---|
| 1 | 32 | Architecture Overview | framework | the layer diagram; `apps/<app>/` appears as a consumer-shaped hole |
| 2 | 83 | Directory Structure | **split** | one tree spanning `apps/`, `tests/`, `pwpf/`, `docs/`, `ai_testing/` |
| 3 | 96 | Execution Flow | framework | fixture chain, artifact capture, hooks, xdist guards |
| 4 | 34 | Major Components | framework | one `apps/<app_name>/` bullet moves |
| 5 | 26 | Fixture Strategy | framework | |
| 6 | 104 | Test Data & Configuration | framework (authoritative) | §4.1 decision 1 |
| 7 | 38 | Reporting | framework | |
| 8 | 154 | CI/CD Flow | **split** | Lint and Installed Package are framework-shaped; PR Smoke, Regression, Cross-Browser, Quarantined, Scenario Catalog are the consumer's; the production-exclusion subsection is consumer policy |
| 9 | 24 | Design Principles | framework | |
| 10 | 136 | Fixed Since the Last Review | **stays whole, consumer** | §4.1 decision 3 |
| 11 | 65 | AI-Assisted Test Engineering | consumer / AI toolkit | pointer section into `docs/ai-testing/` |
| 12 | 49 | Packaging and the pytest plugin | framework | its extraction note becomes history in the consumer |
| — | 187 | Adding a New Application | **split** | §4.1 decision 2 |

Totals [V], three buckets that do not overlap: **403** framework outright (§§1, 3–7, 9, 12) ·
**424** to be split line by line (§2 83 + §8 154 + "Adding a New Application" 187) · **201**
staying whole with the consumer (§10 136 + §11 65). 403 + 424 + 201 = 1,028, plus the 7-line
preamble = 1,035 ✓.

### 3.2 `README.md` — 498 lines, 16 sections, 16-line preamble [V]

| Lines | Section | Owner | Note |
|---|---|---|---|
| 17 | Table of Contents | each repository regenerates its own | 16 in-page anchors live here |
| 38 | Key Features | framework | |
| 18 | Technology Stack | **split** | the table mixes framework dependencies with the consumer's xdist/pytest-html — ownership already settled by readiness §5.1 |
| 57 | Project Structure | **split** | the same tree problem as DESIGN §2 |
| 32 | Using the framework in another project | **framework** | this is the framework README's front page, currently in the wrong repository |
| 5 + 28 | Prerequisites, Installation | **split** | framework install vs this repository's dev setup; `#installation` is an anchor target (§2.4) |
| 62 | Configuration | framework (authoritative) | §4.1 decision 1 |
| 48 | Running Tests | consumer | anchor target `#running-tests` |
| 29 | Reporting and Failure Diagnostics | framework | |
| 26 | Architecture and Fixture Strategy | framework | summary pointing at DESIGN |
| 18 | Code Quality | each repository keeps its own | |
| 32 | Continuous Integration | **split** | as DESIGN §8 |
| 16 | Local-Only Overrides | consumer | |
| 23 | Troubleshooting | **split** | browser-launch and `ENVIRONMENT` entries framework; parallel-only and CI-only entries consumer |
| 33 | Known Limitations | **split** | framework absences vs consumer ones; anchor target `#known-limitations` ×2 |

Totals [V]: framework outright **155** (Key Features, Configuration, Reporting, Architecture) +
**32** that move (Using the framework) · consumer outright **64** (Running Tests, Local-Only) ·
duplicated per repository **35** (ToC, Code Quality) · split line by line **196**. 155 + 32 + 64 +
35 + 196 = 482, plus the 16-line preamble = 498 ✓.

## 4. The four ownership decisions

### 4.1 Decisions

**1. The `AppConfig` contract — framework-authoritative, consumer links to it. [R]**
The mechanism is `pwpf/core/app_config.py` and its `_KNOWN_KEYS` validation [V]; the data is the
consumer's `apps/<app>/config/<environment>.json`. DESIGN §6 and README "Configuration" keep the
authoritative key table in the framework documentation; the consumer keeps **one** minimal example
config and a link. Two independently maintained copies of a key list is how a framework and its
consumer start disagreeing about what `action_timeout` means.

**2. "Adding a New Application" — split into two guides. [R]**
187 lines today, written in terms of framework conventions but walking through *this* repository.
It becomes a framework guide ("the conventions a consumer project must follow: the
`tests/<app>/`+`apps/<app>/` pairing, the one `app_config` fixture, the config keys") and a
consumer guide ("onboarding an application here", with the Myntra/sample_app specifics), each
cross-linking the other. The framework half also replaces README "Using the framework in another
project" as that repository's front page. Nothing is discarded: every step in the current guide
lands in one of the two.

**3. DESIGN §10 "Fixed Since the Last Review" — stays whole, with the consumer. [R]**
24 entries [V], mixed: framework defects (tracing started after failure, video paths, xdist-unsafe
logging, non-recursive screenshot embedding, Allure accumulation) and consumer ones (the
`google_search`→`web_search` swap, placeholder-test removal, the Myntra pilot cleanup). The
trade-off: splitting it gives each repository a tidy record but destroys the chronology, and
several entries explain *each other* — the CI restructuring entry only makes sense beside the
report-embedding one. Keeping it whole costs the framework repository its early history, which the
framework's own CHANGELOG can start fresh from `v0.1.0`. Provenance beats tidiness here, and this
is a planning decision that can be revisited at extraction without rework, since the section is not
being edited either way.

**4. `tests/test_scenario_catalog.py` — split 20/2, and the documentation follows. [V]**
Verified against the file and the workflow:

- **22 collected tests** [V] (`def test_home_page_loads_successfully` at line 41 is inside a
  template string the helper writes into throwaway repositories, not a test).
- **20 take `tmp_path`** and validate the validator's rules against synthetic repositories [V] →
  **framework**, with `pwpf/ai_testing/validate_catalog.py`.
- **2 take no arguments** and assert things about *this* repository [V]: `test_the_committed_catalog_is_valid`
  (line 383), which duplicates the **Scenario Catalog** CI job (`python -m pwpf.ai_testing.validate_catalog`)
  [V], and `test_no_committed_scenario_lets_a_live_site_gate_ci` (line 389), a consumer policy
  assertion the CI job does **not** cover → **consumer**, and the second one must survive the split.

Documentation consequence: the rule-code table in `docs/ai-testing/scenario-authoring.md`
("Validation", 15 rule codes) documents framework behaviour and belongs with the framework (or is
linked from there); the lifecycle, statuses and approval governance in the same document are
consumer policy and stay. That is a **split within one document**, scheduled in Stage 2.

### 4.2 Still unresolved

- **[?]** Whether the framework repository publishes documentation at all beyond its README, or
  keeps DESIGN-style internals in-repo only. This decides whether §§3–7 and 9 become one
  `DESIGN.md` there or get folded into the README.
- **[?]** Whether the consumer repository keeps a trimmed `DESIGN.md` at all once §§1, 3–7, 9 and
  12 leave, or whether its remaining content (§2 consumer half, §8 consumer jobs, §10, §11, the
  consumer onboarding guide) is better served as `docs/` pages.

Both are editorial, both can be decided at Stage 3 when the framework draft exists and the shape is
visible, and neither blocks Stages 0–2.

## 5. Two stale facts, re-confirmed on `dev` at `7bcc4b4`

| Claim | Status | Evidence |
|---|---|---|
| `README.md:476-478` — "**No installable package root.** `pyproject.toml` has no `[project]` table — the project isn't `pip install -e .`-able." | **False** since #8 | `grep -c '^\[project\]$' pyproject.toml` → 1; `[build-system]` present with `setuptools>=77`; CI's Installed Package job builds, installs and verifies the wheel on every run (24/24 on `7bcc4b4`) [V] |
| `DESIGN.md:84-87` — a top-level `core/` block listing `base_page.py`, `app_config.py`, `api_client.py`, sitting immediately above the `pwpf/` block in the §2 tree | **Stale** since #8 | `core/` does not exist on disk; the three modules are `pwpf/core/*` [V]. The tree documents them twice, once at a path that is gone |

Both corrections are assigned to the stage that rewrites the owning section — **Stage 2** for the
README limitation, **Stage 1** for the DESIGN tree — so each is reviewed with its surrounding text
rather than as a drive-by edit.

## 6. Staged migration

Five stages. Each is a documentation-only commit on its own branch, each leaves both documents
coherent, and none moves `pwpf/` or creates a repository.

### Stage 0 — make links and anchors checkable

- **Scope:** add a link checker; correct one stale number. **Proposed here, implemented in the
  stage, not by this plan.**
- **Files:** new `scripts/check_doc_links.py`; `.github/workflows/ci.yml` (one step in the existing
  Lint & Type Check job); `docs/framework-extraction-readiness.md` §5.5 (79 → 81, the only edit any
  stage makes to that document).
- **Validation:** the checker resolves every relative target **and** every fragment — the 15
  `file+anchor` and 16 in-page anchors of §2.1, 31 fragments in total, all resolving today [V] —
  and reports the counts of §2.1 so a drift in them is visible. It must **ignore inline code spans
  and fenced blocks**: documentation that quotes link syntax or shows an example path is not a
  link, and a checker without that rule reports a false positive on this plan itself [V]. It must
  fail on a deliberately broken file link and on a deliberately broken anchor, then pass on `dev`.
- **Acceptance:** 81 relative links in the tracked documents, 0 broken, 31 fragments resolved,
  exit 0 — and no false positive from prose that quotes link syntax; the Lint job green; the two
  deliberate breakages shown failing in the PR description.
- **Rollback:** revert the commit — one script, one workflow step, one number.
- **Useful without extraction:** **yes**, and most of all. 31 fragments already depend on
  headings that nothing checks, five of them in documents this plan splits.

### Stage 1 — split the trees, label the CI jobs

- **Scope:** rewrite the two directory trees and annotate job ownership. No section moves.
- **Files:** `DESIGN.md` §2 (83 lines) and §8 (154); `README.md` "Project Structure" (57) and
  "Continuous Integration" (32). Fixes the `core/` duplication of §5.
- **Validation:** Stage 0's checker; `tests/test_ci_production_exclusion.py` and
  `tests/test_quarantine_policy.py` still pass (they read the workflow, not the prose, but both
  documents quote the job names and the marker policy).
- **Acceptance:** each tree is two labelled halves, framework and consumer; each of the seven CI
  jobs carries its owner; no top-level `core/` entry remains; links and anchors unchanged in count.
- **Rollback:** revert; nothing else referenced the new labels.
- **Useful without extraction:** **yes** — the tree is wrong today, and the job list gains the
  ownership note a reader currently has to infer.

### Stage 2 — separate the mixed prose in place

- **Scope:** label framework vs consumer content inside the sections that mix them. Still one file
  each, nothing moved.
- **Files:** `README.md` Technology Stack (18), Prerequisites/Installation (33), Troubleshooting
  (23), Known Limitations (33) — fixing the `[project]` falsehood of §5 here;
  `docs/ai-testing/scenario-authoring.md` "Validation" (the rule-code table, per decision 4).
  DESIGN §10 is **not** touched, per decision 3.
- **Validation:** Stage 0's checker, with attention to the three anchor targets in these sections
  (`#installation`, `#known-limitations` ×2); `python -m pwpf.ai_testing.validate_catalog` still
  clean, since the rule table is documentation of its behaviour.
- **Acceptance:** every bullet in the four README sections is attributable to one repository; the
  `[project]` claim is gone; the rule-code table states that it documents framework behaviour; the
  three anchors still resolve.
- **Rollback:** revert; no structural change to undo.
- **Useful without extraction:** **partly** — fixing the `[project]` falsehood and clarifying the
  rule table are worth having regardless; the labelling is preparation.

### Stage 3 — stand up the framework-facing draft

- **Scope:** assemble the framework-owned content as a **new** file. Nothing deleted.
- **Files:** new `docs/framework-readme-draft.md` carrying README "Using the framework in another
  project" (32), Key Features (38), Configuration (62), Reporting (29), Architecture & Fixture
  Strategy (26), DESIGN §§1, 3–7, 9, 12 (403) and the framework half of decision 2's guide.
- **Validation:** Stage 0's checker over the draft; a heading diff proving every framework-owned
  section appears **exactly once** across the draft and the originals (the draft quotes, it does
  not yet delete, so this check is what stops silent divergence).
- **Acceptance:** the draft reads as a standalone framework document; no consumer-specific path,
  application name or CI job appears in it; the two **[?]** questions of §4.2 are answered in the PR
  description.
- **Rollback:** delete the draft; the originals are untouched by this stage.
- **Useful without extraction:** **no** — this stage only pays off if the split happens. It is also
  where the split becomes real work, and the right place to stop if the plan is abandoned.

### Stage 4 — rewrite the nine framework-pointing toolkit links

- **Scope:** the nine links of §2.2 that target `pwpf/`. The six consumer-targeted crossings are
  left alone.
- **Files:** `ai_testing/README.md` (8 links), `docs/ai-testing/scenario-authoring.md` (1).
- **Change:** prose plus a pinned-tag URL into the framework repository for the two that readers
  actually follow (the scenario schema and the validator); prose only for the six source-file
  citations, which exist to say where behaviour lives. **[R]**
- **Validation:** Stage 0's checker; `grep -r '\.\./pwpf/\|\.\./\.\./pwpf/' ai_testing/ docs/ai-testing/`
  returns nothing.
- **Acceptance:** no relative link into `pwpf/` remains from toolkit documentation; every replaced
  reference still tells the reader where the behaviour is defined.
- **Rollback:** revert; the links were valid before and would be valid again until `pwpf/` moves.
- **Useful without extraction:** **no**, and it should be done last — until the framework
  repository exists there is no tag to point at, so this stage is blocked on the extraction's
  Step 1 (tag `v0.1.0`).

### Then, at extraction — not in this plan

The draft becomes the framework repository's `README.md`/`DESIGN.md`, the framework-owned sections
are deleted from this repository's copies, and the anchors of §2.4 are re-pointed. That belongs to
the extraction PR.

## 7. Risks and rollback

- **Prose has no test suite.** A checker catches broken targets and fragments; it cannot catch a
  paragraph that is now in the wrong repository. Each stage is sized to be read, which is the
  substitute.
- **Duplication drift** — mitigated by decision 1 (one authoritative copy plus a link) and by
  Stage 3's exactly-once heading diff.
- **Anchors are load-bearing** — five cross-document fragments plus 26 more, none checked today.
  Stage 0 exists for this and is the one stage worth doing even if everything else is dropped.
- **Stage 4 is blocked** on the framework repository existing, so the plan cannot be completed
  before the extraction starts — by design.
- **Rollback** is `git revert` of a documentation-only commit at every stage. Stage 0 is the only
  one that touches CI (one job step). Nothing is deleted before the extraction PR, so until then
  the originals remain authoritative and the draft can simply be abandoned.

## 8. What this plan does not do

No file moved, renamed, rewritten or deleted. No CI change. No link checker implemented. No
framework extraction, no repository created, no release tagged. The two stale facts of §5 are
reported with their evidence and assigned to stages, not fixed here.
