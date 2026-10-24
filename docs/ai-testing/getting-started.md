# Getting started

For an engineer who has the framework running and wants to use the AI-assisted process for the
first time. Framework setup itself is in [README.md § Installation](../../README.md#installation)
— this guide assumes `pytest tests/test_*.py -m "not production"` already passes for you.

## What you need

- The repository, and an assistant that can read it and run commands in it. No particular vendor
  is assumed; nothing here requires a plugin, an API key or a network service beyond the
  assistant you already use.
- No new test-runtime dependency. `requirements.in`/`requirements.txt` are untouched by this
  toolkit and must stay that way
  ([ai_testing/README.md § Dependencies](../../ai_testing/README.md#dependencies)). The catalog
  validator has two dependencies of its own, pinned separately: `pip install -r
  requirements-ai.txt` once, and `python -m ai_testing.validate_catalog` works. Without them
  the catalog self-tests skip, and CI validates the catalog in its own job.

## Your first pass, in order

1. **Make a work item directory.** `artifacts/ai-work/<YYYYMMDD>-<slug>/`. It is git-ignored, and
   it is where everything unreviewed lives — drafts, recordings, evidence, review notes. Nothing
   from it is ever imported by a test.
2. **Run prompt 00.** Paste [00_analyze_repository.md](../../ai_testing/prompts/00_analyze_repository.md)
   into your assistant and save the result as `repo-analysis.md`. Spot-check three of its
   citations. If one does not resolve, start over with a fresh context — an assistant that
   invented a citation will invent a method next.
3. **Write the feature brief yourself.** Copy
   [feature_brief.md](../../ai_testing/templates/feature_brief.md) and fill it in. This is the
   step with no shortcut: everything downstream treats it as the truth about expected behaviour,
   so a vague brief produces confidently wrong scenarios. "Unknown" is a valid answer and becomes
   a question later; a guess becomes a false assertion.
4. **Generate and review scenarios.** Prompt 01, then prompt 02 **in a fresh context** — a model
   reviewing its own output in the same conversation mostly agrees with itself. Then answer the
   decisions list and approve, in writing, in the scenario file.
5. **Explore, under supervision.** Prompt 03 produces a plan; you run the session, headed, within
   the stated limits, on a target you are authorized to touch. Stop at the first CAPTCHA, OTP,
   login wall or access-denied page.
6. **Convert evidence to code.** Prompt 04 (evidence), 05 (page objects and locators), 06 (tests).
   Each one's output is reviewed before the next runs.
7. **Review and validate.** Prompt 07 in a fresh context, then
   [review-checklist.md](review-checklist.md) yourself, then the real commands:

   ```bash
   ruff check . && black --check . && mypy .
   python -m ai_testing.validate_catalog          # catalog, lifecycle rules, test mappings
   pytest --collect-only -q -m "not production"
   pytest tests/<app> -m "not production" -q
   ```

8. **Merge as you would any change.** An assistant does not merge its own work.

Expect to go backwards. Exploration that finds the flow is not what the brief described sends you
to step 3, not step 6.

## The rules that matter most

Read [ai_testing/README.md § House rules](../../ai_testing/README.md#house-rules) once, properly.
If you remember only four:

- Nothing is verified unless a command ran and its real output was pasted.
- Never derive an expected business result from what the application currently does.
- Never weaken an assertion, add a sleep or add a rerun to make a failure go away.
- Live production sites are supervised, authorized, local-only, and never a CI gate.

## Where things end up

| Artifact | Location | Committed? |
|---|---|---|
| Drafts, recordings, evidence, review notes | `artifacts/ai-work/<work-item>/` | no — git-ignored |
| Prompts, templates, conventions | `ai_testing/` | yes |
| This guide | `docs/ai-testing/` | yes |
| Page objects, locators, config | `apps/<app>/` | yes |
| Tests | `tests/<app>/<suite>/` | yes |
| Scenario catalog | `apps/<app>/scenarios/<feature>.yaml` | yes — validated by `python -m ai_testing.validate_catalog` |
| Failure evidence from a run | `screenshots/`, `traces/`, `videos/`, `logs/`, `reports/` | no — git-ignored, written on failure only |

## If something looks wrong

The framework's own documentation wins over anything here, and the code wins over both. A
disagreement between [ai_testing/README.md § Verified framework facts](../../ai_testing/README.md#verified-framework-facts)
and the source is a bug in that table — fix it in the same change that found it.
