# From a recording to maintainable automation

Playwright Codegen (`playwright codegen <url>`) records what a person did. That is evidence about
the application, and it is useful exactly once. It is never the test: a recording is a flat
script of selectors and clicks with no business intent, no assertions worth the name, and
selectors chosen by a tool that cannot know which are stable.

Six stages, mirroring prompts 03–07.

## 1. Record a small, intentional journey

Work from an [exploration plan](../../ai_testing/prompts/03_plan_exploration.md) covering approved
scenarios only. Headed, supervised, within the plan's stated limits, on an authorized target.

Keep it short — one journey, not an exploratory wander: every extra click is noise you will have
to classify later. Save the script and any screenshots into the work item directory
(`artifacts/ai-work/<work-item>/`, git-ignored).

Stop immediately at a CAPTCHA, an OTP prompt, a login wall or an access-denied page, and record
that you stopped and where. Never automate around one.

## 2. Capture the evidence, not just the script

For every control the journey touches, write down the markup it came from alongside the selector
Codegen chose. A selector without the markup that justifies it cannot be reviewed, and in six
months nobody will remember why `.desktop-searchBar` was acceptable.

Also capture what the journey *showed*: the text that proved a step worked, the URL after
navigation, the state that changed. That is what the assertions will be built from.

## 3. Separate business intent from incidental interaction

Classify every recorded line (prompt 04 does this as a table):

- **Business intent** — a step an approved scenario names. This becomes a page-object method.
- **Navigation** — becomes `goto` or `wait_for_url`.
- **State query** — becomes a page-object method returning a value or a `Locator`.
- **Interstitial handling** — a cookie wall or promo modal. `BasePage.dismiss_if_visible` exists
  for this, driven by a selector in `AppConfig.extra` where one is needed
  (`apps/web_search/pages/home_page.py`).
- **Incidental** — stray clicks, scrolls, a mis-click corrected later. Deleted, not translated.

Anything that maps to no scenario step is either incidental or a step the scenario is missing —
decide which, explicitly. The reverse matters more: a scenario step with no recorded action is
unverified, and a test that skips it is lying by omission.

## 4. Find the missing assertions

This is the step people skip, and the reason Codegen output makes bad tests. A recording contains
almost no assertions: it proves the person could click, not that the application was correct.

List every approved expected result the recording does not check, then build the test around that
list. An assertion that could pass on an error page, an empty state or a bot-challenge page is
not an assertion — "the page has a title" passes on all three.

## 5. Transform into the existing layers

Nothing here invents an API. The surface you build on is listed in
[ai_testing/README.md § Verified framework facts](../../ai_testing/README.md#verified-framework-facts),
and the authoritative reference is [DESIGN.md](../../DESIGN.md) plus the closest existing app —
`apps/web_search/` for a network app, `apps/uitesting_playground/` for several pages in one app.

| Recording contains | Where it goes |
|---|---|
| a selector | `apps/<app>/locators/<page>_locators.py`, with the evidence in a comment |
| a user action | a method on a `BasePage` subclass in `apps/<app>/pages/` |
| a state read | a page-object method returning a value or `Locator` |
| an expectation | an `assert`/`expect` in the test — never in a page object |
| a URL or timeout literal | `AppConfig.base_url` / `AppConfig.action_timeout` |
| setup repeated across tests | a fixture in `tests/<app>/conftest.py` |
| `wait_for_timeout`, `sleep` | deleted; wait for the state instead (`is_visible`, `wait_for_url`, `expect`) |

Two judgment calls:

**Fragile selectors.** Prefer a role or accessible name, then a stable user-visible attribute (a
placeholder, a label), then a documented public class. Reject generated class names, positional
`nth` selectors, long descendant chains, and text that reads like marketing copy. Where only a
fragile option exists, say so in the locator comment — a known-fragile selector with a note is
maintainable; a silent one is a mystery failure later.

**Components.** `apps/<app>/components/` is justified only when the same element recurs across
pages and needs its own scoped behaviour. No existing app has one; `BasePage` takes a `Page`
rather than a scoped `Locator`, so a component is plain app-local code, and introducing the
directory means documenting it in [DESIGN.md](../../DESIGN.md) §2. A page object is the default,
and five components for a five-page app is a smell.

## 6. Validate, then discard the recording

Run the real commands and paste the real output:

```bash
ruff check . && black --check . && mypy .
pytest --collect-only -q tests/<app>
pytest tests/<app> -m "not production" -q
```

A `production`-marked test is run locally, headed and supervised, only with authorization — and
its result is reported as a local observation.

Then delete the recording. It is evidence, not a runtime dependency: keeping it invites someone to
"fix" the test by re-recording instead of understanding it. Keep the sanitized evidence files
(`locator-evidence.md`, `action-map.md`) only while they are useful for review, and never keep a
recording that contains a cookie, a token or personal data — redact first, and note that you did.
