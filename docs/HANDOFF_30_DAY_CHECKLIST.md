# Turf Intelligence 30-Day Handoff Checklist

This is the handoff-month plan for transferring the product and repo cleanly.

The goal for this month is not endless improvement. The goal is:

- stabilize the product
- make the repo easy to inherit
- make validation easy to run
- document what is true, what is supported, and what still has limits

## Operating rule

From this point on, only change:

- real bugs
- real wrong answers
- real handoff blockers
- documentation gaps that would confuse the new owner

Avoid:

- speculative refactors
- risky architecture churn
- cosmetic rewrites that touch core behavior without a clear handoff benefit

## Week 1: Stabilize

Focus:

- fix clear user-facing bugs
- fix clear admin / feedback / eval bugs
- stop adding broad new behavior unless it closes a real gap

Definition of done:

- core question classes remain green
- handoff suite passes
- no known “AI slop” answers remain in the main demo paths

Checklist:

- [x] run `python3 scripts/run_handoff_quality_suite.py`
- [x] run `python3 scripts/run_comprehensive_100_eval.py`
- [x] run `python3 scripts/run_anti_slop_eval.py`
- [x] run `python3 scripts/run_no_account_turf_eval.py`
- [x] fix any failures before changing anything else
- [x] keep a short list of known issues instead of burying them

## Week 2: Document

Focus:

- make the repo understandable without tribal memory

Definition of done:

- a new engineer can understand what the app is, how it runs, and how to validate it

Checklist:

- [x] confirm `README.md` setup steps are current
- [x] confirm `HANDOFF_GUIDE.md` still points to the right high-signal files
- [x] document required env vars clearly
- [x] document the current deployment model clearly
- [x] document which answer paths are deterministic vs LLM-backed
- [x] document admin/eval usage at a practical level
- [x] document known limits honestly

## Week 3: Inheritance

Focus:

- make the codebase easier for the receiving team to take over

Definition of done:

- someone new can locate core logic without a guided tour from the original author

Checklist:

- [x] confirm the major routes and subsystems are named clearly
- [x] add short comments only where they reduce real confusion
- [x] make sure scripts in `scripts/` have obvious names and purposes
- [x] make sure the eval families have a short description in docs
- [x] make sure the admin surface reflects the current eval families
- [x] confirm public-admin behavior is intentional and documented for development only

## Week 4: Final validation

Focus:

- prove the build is stable enough to hand off

Definition of done:

- the repo passes the agreed validation suite
- the remaining known issues are explicit
- no critical handoff blockers remain

Checklist:

- [x] run `python3 scripts/run_handoff_quality_suite.py`
- [x] run smoke check one more time
- [x] spot-check the key demo prompts through `/ask`
- [x] confirm admin loads and evals are visible
- [x] confirm handoff docs are still accurate
- [x] write a short final known-issues list

## Core demo prompts

These are the prompts worth checking before handoff because they represent the strongest product paths:

- `What diseases does Daconil control?`
- `What fungicides control dollar spot?`
- `What is the difference between prodiamine and dithiopyr?`
- `What is the difference between Secure and Medallion?`
- `What controls annual bluegrass weevil?`
- `What should I spray on bermuda fairways for goosegrass?`
- `Why does Poa annua decline faster than bentgrass in summer?`
- `Why do warm nights hurt bentgrass more than hot days?`
- `How do I keep bentgrass alive through humid nights?`
- `What should I be watching on greens this week?`

## Handoff standard

The handoff standard is not “perfect forever.”

It is:

- the app works reliably in its main lanes
- the risky answer classes are guarded
- the validation story is real
- the receiving team can run, test, and understand the repo

That is the stopping point.
