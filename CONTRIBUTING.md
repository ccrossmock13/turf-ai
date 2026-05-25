# Contributing

This repo is in a late-stage handoff / stabilization phase.

## Working rules

- prefer narrow fixes over broad refactors
- protect passing evals and route tests
- update docs when behavior changes
- treat auth-heavy validation as serial, not parallel

## First commands to know

Run the full confidence board:

```bash
python3 scripts/run_handoff_quality_suite.py
```

Run the app locally:

```bash
python3 app.py
```

Run the core demo-path check:

```bash
python3 scripts/run_demo_prompt_check.py
```

## Main files

- [app.py](/Users/christiancrossmock/Desktop/turf-ai/app.py)
  - main Flask app and route orchestration
- [verified_kb.py](/Users/christiancrossmock/Desktop/turf-ai/verified_kb.py)
  - deterministic product and label-backed answer layer
- [feedback_system.py](/Users/christiancrossmock/Desktop/turf-ai/feedback_system.py)
  - moderation, feedback, and KB-gap workflow
- [course_profile.py](/Users/christiancrossmock/Desktop/turf-ai/course_profile.py)
  - general turf guidance and course-context shaping

## Quality expectations

Before shipping a meaningful behavior change:

1. run the relevant focused tests
2. rerun the handoff suite if the change touches core behavior
3. keep docs and admin behavior aligned with reality

## More context

- [Owner's Map](/Users/christiancrossmock/Desktop/turf-ai/docs/OWNER_MAP.md)
- [Handoff-Day Cheat Sheet](/Users/christiancrossmock/Desktop/turf-ai/docs/HANDOFF_DAY_CHEAT_SHEET.md)
- [Final-Stretch Decision Guide](/Users/christiancrossmock/Desktop/turf-ai/docs/FINAL_STRETCH_DECISION_GUIDE.md)

