# Turf Intelligence Final-Stretch Decision Guide

Use this when you are under time pressure and wondering:

- should we change this?
- should we leave it alone?
- should we document it instead of touching code?

This is the “don’t get cute in the last two weeks” guide.

## The three buckets

When something comes up, sort it into one of these:

### 1. Fix now

This means:

- it is a real bug
- it changes user-facing behavior in a bad way
- it breaks admin/moderation/validation
- it undermines trust in the demo

Examples:

- a verified product answer is wrong
- moderation queue hides real items
- admin route fails to load
- handoff suite turns red
- demo prompt now routes into the wrong lane

If it is in this bucket:

- fix it
- add proof
- rerun the relevant checks

### 2. Leave it alone

This means:

- it is not broken
- it is tempting to improve
- changing it now adds risk without clear handoff value

Examples:

- broad routing cleanup because “it could be smarter”
- answer style rewrites across the whole app
- moving lots of files around again
- changing source policy just because you might want to
- refactoring auth/session behavior without a real bug

If it is in this bucket:

- do not touch it

### 3. Document it, don’t rebuild it

This means:

- the behavior is acceptable
- the receiving team still needs to know about it
- changing it now is not worth the risk

Examples:

- auth-heavy tests should run serially
- product labels are public but other local document buckets are private
- some lower-traffic products still have less depth than top-tier products
- local scripted `/ask` checks need CSRF/session setup

If it is in this bucket:

- put it in docs
- make the behavior explicit
- move on

## The 30-second decision filter

Before touching code, ask:

1. Is this actually broken?
2. Will a user or receiving engineer notice it in a bad way?
3. Can I prove the fix with a test, eval, or smoke check?
4. Is this a narrow change, or am I about to disturb a big system?

If the answers are:

- **yes / yes / yes / narrow**
  - fix it

- **no / maybe / no / broad**
  - leave it alone

- **not broken / but worth explaining**
  - document it

## Good late-stage changes

These are usually worth doing:

- bug fixes
- deterministic answer fixes
- moderation/admin usability fixes
- validation tooling
- small documentation corrections
- small operator-quality improvements with direct proof

## Bad late-stage changes

These are usually not worth doing now:

- large refactors
- new persistence ideas
- broad auth/session changes
- new product features
- large UI redesigns
- answer-lane rewrites without fresh eval coverage

## What “proof” should look like

Try to leave every meaningful fix with at least one of these:

- unit test
- eval pass
- smoke check
- demo prompt check

Examples:

- product answer fix -> `run_product_label_eval.py`
- chatbot feel/routing fix -> `run_anti_slop_eval.py`
- moderation fix -> `test_feedback_runtime.py`
- app path fix -> `smoke_check_simple_app.py`
- broad confidence check -> `run_handoff_quality_suite.py`

## The safest default

If you are unsure, prefer:

- the smaller change
- the deterministic change
- the documented truth
- the green board

That is the right final-stretch instinct.

## The owner’s sentence

When you are unsure what to do, use this sentence:

**“Does this make the handoff safer, or does it just make the code feel more finished to me?”**

If it only makes the code *feel* more finished, it is probably not the right move this late.
