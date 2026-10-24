# Troubleshooting

Evidence-based diagnosis. The framework captures a screenshot, a trace and a video for every
failed UI test, automatically and only on failure (`conftest.py`), under `screenshots/<app>/`,
`traces/<app>/` and `videos/<app>/`, with the screenshot embedded in
`reports/pytest_report.html` and per-worker logs under `logs/`. Open the trace before theorising:

```bash
playwright show-trace traces/<app>/<test_name>.zip
```

Classify before fixing — the categories are in
[08_analyze_failures.md](../../ai_testing/prompts/08_analyze_failures.md), and the one rule that
matters is that a fix which makes the failure disappear without explaining it is not a fix.

## Framework and workflow problems

**A new application's tests are not collected.** Membership is structural: the first path segment
under `tests/` must match an existing `apps/<name>/` directory (`conftest.py:44`). Check the
directory names match exactly, and that `apps/<app>/__init__.py` and the `pages/`/`locators/`
`__init__.py` files exist.

**"Import file mismatch" or a collection error naming an unrelated test.** Two test modules share
a basename. `tests/` has no `__init__.py`, so `tests/a/smoke/test_homepage.py` and
`tests/b/smoke/test_homepage.py` collide and **whole-suite collection fails** — a problem that
does not show up when you run one directory. Give each module a unique, app-prefixed name.

**A test in `smoke/` never runs in the smoke gate.** Markers select suites, folders do not. Add
`@pytest.mark.smoke`. Confirm with `pytest --collect-only -q -m "smoke and not production"`.

**`Unknown pytest.mark.<x>`** — `--strict-markers` is on; register the marker in `pytest.ini`.
That is a shared-framework change: justify it rather than slipping it in.

**A config value has no effect.** Only `base_url`, `action_timeout`, `retry_count`,
`ignore_https_errors` and `secrets` are recognised; everything else is swept into `AppConfig.extra`
**silently** (`core/app_config.py:12`). A misspelling never errors — check `_KNOWN_KEYS`.

**`No config found for app '<app>' in environment '<env>'`** — `ENVIRONMENT` (default `local`)
selects `apps/<app>/config/<ENVIRONMENT>.json`. `myntra` deliberately ships `local.json` only,
because its tests never run in CI.

**`AppConfig.secret(...)` raises `KeyError`.** The config maps a logical name to an environment
variable *name*; the variable itself must be set in your shell. A secret value never goes in the
file.

**A test passes locally and fails in CI, or the reverse.** `HEADLESS` defaults to `false` locally
and `true` when `CI` is set; `ENVIRONMENT=ci` in CI selects a different config file. Reproduce
with `CI=true HEADLESS=true ENVIRONMENT=ci pytest <test>`.

**"It passed on the second attempt."** That is a finding, not a pass. `pytest.ini` applies
`--reruns 1` to every run and a non-zero app `retry_count` adds another layer
(`conftest.py:78`). Report the rerun and investigate the instability.

**A live-site test ran in CI.** It should be impossible: every pytest invocation in the workflow
carries `-m "not production"`, and `tests/test_ci_production_exclusion.py` fails if one loses it.
If it happens anyway, the test is missing `@pytest.mark.production` — that guard test checks for
exactly this, so run it and read what it says.

## Application-facing failures

**`Locator.wait_for: Timeout ... exceeded`.** Four different causes, distinguishable from the
trace: the element never appeared (wrong selector, or a page that rendered something else); it
appeared later than the timeout (`action_timeout` is per app); it is behind an interstitial (use
`BasePage.dismiss_if_visible`); or the page is an error or challenge page. Look at the screenshot
first — it usually answers this in one glance. Do not raise the timeout until you know which.

**An external site fails intermittently.** A third-party production site is outside your control.
This has happened before in this repo: `tests/web_search` drives live `playwright.dev`, and
[DESIGN.md](../../DESIGN.md) §6 records why that app was moved off `google.com` after exactly this
class of failure. Classify it as an environment failure, and do not "fix" it by weakening the
test. If a test like this gates PRs, that is worth raising as its own decision.

**A bot challenge, CAPTCHA, OTP or access-denied page.** Stop. This is an access restriction, not
a defect and not a puzzle: record what you saw, and either seek authorization or move the scenario
to a sanctioned target. Never attempt a bypass, and never retry in a loop — that is load on
someone else's site.

**An assertion on an exact title or price starts failing.** Expected: marketing copy, pricing and
promotions change without the feature breaking. Assert a stable fragment (a regex) or a structural
fact (a control is present) instead, and read the title change as evidence that the expectation
was too tight — not as an application defect.

**The bag, cart or session behaves oddly across runs.** A state-mutating step left something
behind. Each such step needs a declared cleanup; on a live site where cleanup is impossible, the
scenario needs explicit authorization or a different target.

## Assistant-output problems

**A citation does not resolve.** Discard the output and start with a fresh context. One invented
`path:line` means the rest cannot be trusted, and patching it teaches nothing.

**A command result is claimed but no output is shown.** Treat it as not run. Ask for the real
output, including failures; "not run" is an acceptable answer and a fabricated pass is not.

**The review pass agrees with everything.** It was probably run in the same context that produced
the work. Run prompt 07 in a fresh context with only the diff and the approved scenarios.

**Proposed code uses a method that does not exist.** Check it against
[ai_testing/README.md § Verified framework facts](../../ai_testing/README.md#verified-framework-facts).
If something genuinely missing is needed, that is a shared-framework proposal for a human — not a
private helper in the app layer and not a workaround through `self.page`.

**A fix arrives as a longer timeout, an extra rerun, a `time.sleep` or a removed assertion.**
Reject it. The failure is still there; only the report changed.
