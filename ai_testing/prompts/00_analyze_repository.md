# Prompt 00 — Analyze the repository

All prompts inherit `ai_testing/README.md` § House rules. Read them first; they are not repeated
here.

## Purpose

Establish what this framework actually provides before anything is written against it, so later
stages extend real conventions instead of inventing plausible ones. Run this once per assistant
session that will touch code, and again after any change to `pwpf/`, `pytest.ini` or the CI
workflow.

## Required inputs

- Read access to the repository.
- The application you will be working on (`apps/<app>/`), if one exists yet.

## Instructions

1. Read, in this order: `README.md`, `DESIGN.md` §§1–9, `pytest.ini`, `pwpf/plugin.py`,
   `pwpf/core/app_config.py`, `pwpf/core/base_page.py`, `pwpf/config/settings.py`,
   `.github/workflows/ci.yml`.
2. Read one complete existing application end to end — `apps/web_search/` plus
   `tests/web_search/` is the smallest real-network example; `apps/uitesting_playground/` shows
   more than one page object per app.
3. Reconcile what you read with `ai_testing/README.md` § Verified framework facts. Report any
   disagreement explicitly: the code is authoritative and that table is then wrong.
4. Record, with `path:line` citations: the fixtures available to a test; every method `BasePage`
   provides; the recognised configuration keys and how an environment is selected; the registered
   markers and how application membership is inferred; how failure evidence is captured; the
   commands that constitute validation.
5. Record what the framework deliberately does **not** have — authentication, test-data
   factories, a scenario interpreter, an installable package root — from `README.md § Known
   Limitations` and `DESIGN.md` §6, rather than assuming absence means an oversight.
6. For the application in question, state whether it already exists, what page objects and
   locators it has, which environments it has config for, and whether its tests are
   `production`-marked.
7. List what you would need in order to add a test, and flag anything missing as `[?]`.

## Output format

Markdown, saved as `<work-item>/repo-analysis.md`:

```
# Repository analysis — <date>, revision <git rev-parse --short HEAD>
## Fixtures available to a test
## BasePage surface
## Configuration model
## Markers and application discovery
## Failure evidence and reporting
## Validation commands
## Deliberate absences
## Target application: <app>
## Assumptions [A] and open questions [?]
## Disagreements with ai_testing/README.md § Verified framework facts
```

Every factual line carries a `path:line` citation or an `[A]`/`[?]` label.

## Acceptance criteria

- Every claim is citable, and the citations resolve.
- No method, fixture, key or command appears that is not in the source.
- The absences section is present and not empty.
- The revision the analysis was taken at is recorded.

## Safety constraints

Read-only. Change no file, run no browser, start no network test. Do not read or echo `.env`
files, secrets or anything under `artifacts/ai-work/` belonging to another work item.

## Human review

A reviewer spot-checks three citations. If one does not resolve, the analysis is rejected rather
than patched — a single invented citation means the rest cannot be trusted.

## Next step

`01_generate_scenarios.md`, once a feature brief exists.
