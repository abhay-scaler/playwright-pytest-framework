# AI-assisted test engineering

How to use a coding assistant to help design and implement tests in this framework, without
giving up the controls that make the suite trustworthy. It is an **optional** way of working:
the framework, its tests and its CI pipeline neither know nor care whether this process was
used, and nothing here is installed, imported or executed by a test run.

Read [DESIGN.md](../../DESIGN.md) and [README.md](../../README.md) first — they are authoritative
for the framework itself, and this guide links to them rather than restating them.

## What is here

| Document | Read it when |
|---|---|
| [getting-started.md](getting-started.md) | you have never used this process before |
| [workflow.md](workflow.md) | you want the stage-by-stage contract: inputs, outputs, owners, done |
| [scenario-authoring.md](scenario-authoring.md) | you are writing or reviewing scenarios, or need the catalog's schema, rules and validation command |
| [codegen-to-page-objects.md](codegen-to-page-objects.md) | you have a recording and need maintainable code |
| [review-checklist.md](review-checklist.md) | you are reviewing anything an assistant produced |
| [troubleshooting.md](troubleshooting.md) | something failed and you need to classify it |
| [../../ai_testing/README.md](../../ai_testing/README.md) | the prompt library, house rules and verified framework facts |

## The shape of it

```
feature brief (human)  ->  scenarios (assistant)  ->  review (assistant)  ->  APPROVED (human)
                                                                                   |
                    exploration plan  ->  supervised browser session (human)  <----+
                                                   |
                                      evidence  ->  page objects  ->  tests (assistant)
                                                                           |
                                            review (assistant, then human) |
                                                                           v
                                              validation  ->  merge (human)  ->  maintenance
```

Three properties hold at every stage, and everything else here follows from them:

- **The brief and the approved scenarios are the source of truth for expected behaviour.** The
  application is the source of truth for what it currently *does*. An assistant that derives an
  expectation from observed behaviour has written a test that can only ever agree with the bug.
- **An assistant proposes; a human approves and merges.** Specifically: no assistant approves a
  business expectation, authorizes a run against a live site, promotes a scenario to
  `ACTIVE_REGRESSION`, or merges its own change.
- **Prompt text is not an enforcement mechanism.** The things that actually enforce anything in
  this repository are executable: Ruff, Black and mypy; `--strict-markers`; the `-m "not
  production"` exclusion on every pytest invocation in CI, guarded by
  [tests/test_ci_production_exclusion.py](../../tests/test_ci_production_exclusion.py);
  `python -m pwpf.ai_testing.validate_catalog`, which refuses a catalog whose statuses, approval
  records and test mappings do not line up; and human review. A rule that lives only in a
  prompt is a convention, and conventions are broken by accident.

## Production safety

The pilot application `myntra` drives a **live third-party production site**. It exists for
supervised exploration and explicitly authorized local runs, and for nothing else.

Prohibited throughout this workflow, in prompts, scenarios, page objects and tests alike:

- Checkout, payment or order placement.
- Account creation, authentication, or any other unauthorized mutation of someone's data.
- Bypassing a CAPTCHA, OTP, geo restriction or any other access control. Encountering one ends
  the session; it is never an obstacle to work around.
- Load: loops, parallel sessions, repeated runs or anything that sends a live site more traffic
  than a person clicking through it once, under supervision.
- Sharing secrets, cookies, `storage_state`, tokens or personal data with an LLM provider, or
  committing them anywhere.

What enforces the CI side of this is not the above paragraph but the `production` marker plus the
exclusion on all four pytest invocations in [ci.yml](../../.github/workflows/ci.yml) — see
[DESIGN.md §8](../../DESIGN.md) "Production-site applications and the CI exclusion". Running
these tests locally is deliberate: `HEADLESS=false pytest -m production`, supervised, on an
authorized machine.

The one Myntra test that exists today asserts a title pattern and the presence of the header
search bar. Its locators were read from the HTML the site served on 2026-10-24; **it has not been
executed against a live browser session**, and nothing here should be read as saying it has.

## Open decisions

These are genuinely undecided. Do not let an assistant close one by picking a default.

1. **The sanctioned CI pilot target.** A live third-party site cannot be a blocking CI gate
   ([DESIGN.md](../../DESIGN.md) §6 records why). The end-to-end pilot therefore needs either a
   local fixture application in the shape of `apps/sample_app/`, or a site published for
   automation practice. Until this is chosen, no live-site test is a gate.
2. **Whether an external test-management system should stay authoritative** instead of the
   in-repository catalog. The catalog now lives at `apps/<app>/scenarios/<feature>.yaml`,
   inside the application package so an app stays self-contained; if the organization already
   has a system of record, this becomes a mirror of it rather than the source of truth.
3. **Which assistants are approved** for use with this repository, and what data may be sent to
   them.
4. **Whether orchestration is worth building** — see
   [workflow.md § When orchestration would be justified](workflow.md#when-orchestration-would-be-justified).
5. **Who owns the prompt library and the catalog** once more than one person uses them. There is
   no `CODEOWNERS` file today.

## Deliberately not built yet

| Thing | Status |
|---|---|
| Validation tooling for work-item artifacts and failure reports | planned, PR 4 |
| Validation tooling and artifact organization | planned, PR 4 |
| CLI, LLM provider interface, orchestration | planned at the earliest, PR 5, and only against the evidence listed in `workflow.md` |
| Authentication, test-data factories | framework-level absences, documented in [README.md § Known Limitations](../../README.md#known-limitations) |

Nothing in that table is implemented. If a document, prompt or scenario implies otherwise, the
document is wrong.
