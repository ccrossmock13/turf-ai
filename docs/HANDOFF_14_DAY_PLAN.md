# Turf Intelligence 14-Day Handoff Plan

This is the final two-week runway before handoff.

The goal now is not to add broad new behavior. The goal is:

- protect the working build
- catch real bugs with live pressure-testing
- keep docs aligned with reality
- make the receiving team's first week easy

## Operating rule

For the next two weeks, change only:

- real bugs
- real wrong answers
- real handoff blockers
- documentation gaps that would confuse the receiving team

Avoid:

- speculative refactors
- new subsystems
- broad copy churn
- risky behavior changes without new regression coverage

## Week 1: Pressure-Test and Tighten

Focus:

- use the real app like a superintendent would
- keep moderation/admin honest
- fix only concrete misses

Definition of done:

- the live demo paths still feel sharp
- moderation queue is usable and feedback signal is visible
- every fix is covered by tests or evals

Checklist:

- [x] run `python3 scripts/run_handoff_quality_suite.py`
- [x] run `python3 -m unittest test_feedback_runtime.py test_operational_route.py test_verified_kb.py test_knowledge_base.py test_expert_mode_router.py`
- [x] pressure-test 20 to 30 real prompts through `/ask`
- [x] pressure-test `/admin/review-queue`, `/admin/feedback/all`, and `/admin/eval-dashboard`
- [x] fix any real misses before moving on
- [x] update `HANDOFF_STATUS.md` if the validation snapshot changes

## Week 2: Freeze and Package

Focus:

- stop churn
- rerun validation
- make the handoff package calm and obvious

Definition of done:

- the receiving team can run, test, and understand the app without tribal memory
- no critical blockers remain open

Checklist:

- [x] rerun `python3 scripts/run_handoff_quality_suite.py` serially
- [x] rerun `python3 scripts/smoke_check_simple_app.py`
- [x] spot-check the core demo prompts one final time
- [x] confirm docs still match the actual source policy and admin behavior
- [x] confirm `KNOWN_ISSUES.md` is short and honest
- [ ] freeze behavior unless a real blocker appears

## Final demo prompt set

Use these before handoff because they represent the strongest product lanes:

- `What diseases does Daconil control?`
- `What fungicides control dollar spot?`
- `What is the difference between prodiamine and dithiopyr?`
- `What controls annual bluegrass weevil?`
- `What should I spray on bermuda fairways for goosegrass?`
- `Why does Poa annua decline faster than bentgrass in summer?`
- `How do I tell drought stress from disease stress?`
- `What should I be watching on greens this week?`
- `What is Headway used for?`
- `Can I overseed after Kerb SC?`

## Validation note

Auth-heavy suites should be treated as serial checks in this repo because they share file-backed account and password-reset stores during tests.

That is a test-runner constraint, not a product bug.

## Stopping point

The stopping point is not “no possible future improvements.”

It is:

- the app is stable
- the important demos work
- the validation board is green
- the receiving team can inherit the repo without guesswork
