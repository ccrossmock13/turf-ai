# Handoff-Day Cheat Sheet

This is the short version to keep in front of you on handoff day.

## The 3-command confidence loop

Run these before the meeting:

```bash
python3 scripts/run_handoff_quality_suite.py
python3 scripts/smoke_check_simple_app.py
python3 scripts/run_demo_prompt_check.py
```

What they mean:

- `run_handoff_quality_suite.py`
  - the full board is green
  - tests, evals, and smoke all pass together
- `smoke_check_simple_app.py`
  - the app surface and key routes are alive
- `run_demo_prompt_check.py`
  - the core chatbot demo prompts still land correctly

## Important distinction

- `python3 app.py`
  - starts the app
- `python3 scripts/run_handoff_quality_suite.py`
  - proves the build is healthy

Running is not the same thing as validating.

## Core demo prompts

These are safe, useful prompts to use in a live demo:

1. `What should I be watching on greens this week?`
   - expected lane: `General Turf Guidance`

2. `What is the difference between prodiamine and dithiopyr?`
   - expected lane: `Verified Product Comparison`

3. `What controls annual bluegrass weevil?`
   - expected lane: verified target-to-product support

4. `What diseases does Daconil control?`
   - expected lane: verified product support

5. `We syringe and it helps for an hour. What does that tell you?`
   - expected lane: `Clarifying Diagnosis`

6. `Why does Poa annua decline faster than bentgrass in summer?`
   - expected lane: `Advanced Turf Science`

## If something looks off

### The app starts, but you are not confident

Run:

```bash
python3 scripts/run_handoff_quality_suite.py
```

Ask yourself:

- did we validate it?
- or did we only start it?

### A local `/ask` check fails in a weird way

First thought:

- do not panic
- make sure it used the real session / CSRF flow

Use:

```bash
python3 scripts/run_demo_prompt_check.py
```

instead of treating a bare scripted `/ask` call as truth.

### Auth-heavy tests fail in a strange way

First thought:

- were they run in parallel?

For this repo, auth-heavy validation should be treated as **serial** because the tests share local file-backed account and reset stores.

### Moderation looks thin or strange

First places to look:

- [feedback_system.py](/Users/christiancrossmock/Desktop/turf-ai/feedback_system.py)
- [templates/admin.html](/Users/christiancrossmock/Desktop/turf-ai/templates/admin.html)

### A verified product answer looks wrong

First places to look:

- [verified_kb.py](/Users/christiancrossmock/Desktop/turf-ai/verified_kb.py)
- [products.json](/Users/christiancrossmock/Desktop/turf-ai/knowledge/products.json)

### A broad turf answer feels generic

First places to look:

- [course_profile.py](/Users/christiancrossmock/Desktop/turf-ai/course_profile.py)
- [advanced_diagnosis.py](/Users/christiancrossmock/Desktop/turf-ai/advanced_diagnosis.py)
- [advanced_turf_science.py](/Users/christiancrossmock/Desktop/turf-ai/advanced_turf_science.py)

## Final-stretch rule

Ask:

- is it broken?
- will someone notice in a bad way?
- can I prove the fix?

If not, leave it alone.

Do not make last-minute changes just because the code feels unfinished.

## Best fallback sentence

If you need one calm sentence in the room:

> The app is running, the validation suite is green, and the core demo prompts are passing. If something looks unusual, I know which layer to check first.

## Where to go next

- [Owner's Map](/Users/christiancrossmock/Desktop/turf-ai/docs/OWNER_MAP.md)
- [Final-Stretch Decision Guide](/Users/christiancrossmock/Desktop/turf-ai/docs/FINAL_STRETCH_DECISION_GUIDE.md)
- [Handoff Guide](/Users/christiancrossmock/Desktop/turf-ai/docs/HANDOFF_GUIDE.md)
