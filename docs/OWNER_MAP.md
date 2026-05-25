# Turf Intelligence Owner's Map

This is the plain-English version of how the app works.

It is written for someone who needs to **own** the product, not for someone trying to become a full-time ML engineer in a week.

The goal is:

- know what the important files do
- know what happens when a user asks a question
- know how to tell “the app is running” from “the app is healthy”
- know where to make safe changes

## The fastest mental model

Think of the app as five layers:

1. **The web app shell**
   - takes requests
   - manages sessions
   - returns JSON or HTML
2. **The answer router**
   - decides what kind of question this is
3. **The deterministic answer lanes**
   - verified product answers
   - turf science
   - diagnosis
   - general guidance
4. **The feedback and moderation loop**
   - stores what users liked or disliked
   - builds the review queue
5. **The validation board**
   - tests and evals that tell you if the build is still good

If you keep those five buckets in your head, the repo stops feeling like one giant blob.

## The main files that matter

### 1. [app.py](/Users/christiancrossmock/Desktop/turf-ai/app.py)

This is the main traffic cop.

It does things like:

- define routes like `/ask`, `/feedback`, `/admin`
- enforce CSRF and auth
- call the router
- call the answer lanes
- save the question/answer/feedback signal

If you only read one file first, read this one.

### 2. [verified_kb.py](/Users/christiancrossmock/Desktop/turf-ai/verified_kb.py)

This is the deterministic product-answer brain.

It handles questions like:

- `What diseases does Daconil control?`
- `What is the difference between prodiamine and dithiopyr?`
- `Can I overseed after Kerb SC?`
- `What is the annual max for Primo MAXX?`

If a product answer is wrong, stiff, or missing, this is one of the first places to check.

### 3. [expert_mode_router.py](/Users/christiancrossmock/Desktop/turf-ai/expert_mode_router.py)

This decides which answer lane should take the question.

It helps separate:

- product questions
- science questions
- diagnosis questions
- broad guidance questions

If the answer is landing in the wrong “mode,” this file matters.

### 4. [advanced_turf_science.py](/Users/christiancrossmock/Desktop/turf-ai/advanced_turf_science.py)

This handles the “why” questions.

Examples:

- `Why does Poa decline faster than bentgrass in summer?`
- `Why do warm nights hurt bentgrass more than hot days?`
- `How do bicarbonates affect micros?`

If the app sounds weak on turf physiology or mechanisms, this is a high-value file.

### 5. [advanced_diagnosis.py](/Users/christiancrossmock/Desktop/turf-ai/advanced_diagnosis.py)

This handles structured turf troubleshooting.

Examples:

- `How do I tell drought stress from disease stress?`
- `What does syringe relief tell you?`
- `How do you read Poa melting while bent hangs on?`

If the app is getting field triage wrong, start here.

### 6. [course_profile.py](/Users/christiancrossmock/Desktop/turf-ai/course_profile.py)

This shapes broad guidance using course context.

Examples:

- `What should I be watching on greens this week?`
- `How do I keep bentgrass alive in August?`

This is the “operator feel” file for broad management answers.

### 7. [feedback_system.py](/Users/christiancrossmock/Desktop/turf-ai/feedback_system.py)

This is the moderation and learning loop.

It handles:

- feedback records
- review queue
- priority queue
- duplicate collapse
- KB gaps
- training/example records

If the moderation queue feels wrong, this file matters.

### 8. [templates/admin.html](/Users/christiancrossmock/Desktop/turf-ai/templates/admin.html)

This is the admin UI.

If the backend is returning the right data but admin still feels awkward, this is where you look.

### 9. [templates/index.html](/Users/christiancrossmock/Desktop/turf-ai/templates/index.html)

This is the user chat UI.

It controls things like:

- feedback buttons
- message rendering
- image upload
- client-side request flow

If the frontend feels wrong but `/ask` itself is fine, check here.

## What happens when a user asks a question

Very simplified:

1. The browser sends the question to `/ask`
2. [app.py](/Users/christiancrossmock/Desktop/turf-ai/app.py) validates the request
3. The app loads session and course-profile context
4. The router decides what kind of question it is
5. One of the answer lanes handles it:
   - verified product
   - advanced turf science
   - advanced diagnosis
   - general turf guidance
   - fallback model path
6. The app saves the exchange and any review signal
7. The UI renders the answer and lets the user give feedback

That’s the main heartbeat of the product.

## The answer lanes in plain English

### Verified Product

Use this when the question is label/product specific.

Examples:

- rates
- REI
- retreat interval
- rainfast
- target support
- product comparisons

This is the safest and most deterministic lane.

### Advanced Turf Science

Use this for mechanism and physiology.

Examples:

- summer stress
- why one species declines faster
- soil / water / microclimate questions

### Advanced Diagnosis

Use this for turf troubleshooting and field interpretation.

Examples:

- drought vs disease
- what symptom patterns suggest
- what to check first

### General Turf Guidance

Use this for broad management questions.

Examples:

- what to watch this week
- how to manage through summer
- general priorities

## Run vs validate

This distinction matters.

### To start the app

```bash
python3 app.py
```

That means:

- “the app is running”

It does **not** mean:

- the product is healthy
- the evals are green

### To validate the build

```bash
python3 scripts/run_handoff_quality_suite.py
```

That means:

- “the important test/eval board is green”

This is the command you tell a receiving team to use when they want proof, not just a running server.

## The quickest health checks

### Operational health

- `/health`
- `/ready`

### Product-level confidence

```bash
python3 scripts/run_handoff_quality_suite.py
python3 scripts/smoke_check_simple_app.py
python3 scripts/run_demo_prompt_check.py
```

### Moderation/admin health

Check:

- `/admin`
- `/admin/review-queue`
- `/admin/feedback/all`
- `/admin/eval-dashboard`

## Safe changes vs risky changes

### Safer changes

- improving wording inside one deterministic answer lane
- adding one verified product field
- adding one new eval case
- fixing moderation UI behavior
- fixing a queue bug

### Riskier changes

- changing routing broadly
- changing auth/session behavior
- changing persistence behavior
- changing source policy
- changing multiple answer lanes at once without fresh tests

## If something goes wrong, where do I look?

### “The app is up, but product answers feel wrong”

Look at:

- [expert_mode_router.py](/Users/christiancrossmock/Desktop/turf-ai/expert_mode_router.py)
- [verified_kb.py](/Users/christiancrossmock/Desktop/turf-ai/verified_kb.py)
- [advanced_turf_science.py](/Users/christiancrossmock/Desktop/turf-ai/advanced_turf_science.py)
- [advanced_diagnosis.py](/Users/christiancrossmock/Desktop/turf-ai/advanced_diagnosis.py)
- [course_profile.py](/Users/christiancrossmock/Desktop/turf-ai/course_profile.py)

### “The moderation queue feels broken”

Look at:

- [feedback_system.py](/Users/christiancrossmock/Desktop/turf-ai/feedback_system.py)
- [templates/admin.html](/Users/christiancrossmock/Desktop/turf-ai/templates/admin.html)

### “Feedback is not sticking”

Look at:

- [templates/index.html](/Users/christiancrossmock/Desktop/turf-ai/templates/index.html)
- `/feedback` in [app.py](/Users/christiancrossmock/Desktop/turf-ai/app.py)
- [feedback_system.py](/Users/christiancrossmock/Desktop/turf-ai/feedback_system.py)

### “Auth tests are failing in a weird way”

First ask:

- were the auth-heavy suites run in parallel?

If yes, treat that result as suspicious.

This repo uses shared local account/reset files in tests, so auth-heavy validation should be treated as **serial**.

### “A local scripted check gets 400s from `/ask`”

First ask:

- did the script include a CSRF token/session?

The browser handles that naturally. A bare test client call does not.

If you want a ready-made local script that already does the right session/CSRF setup, use:

```bash
python3 scripts/run_demo_prompt_check.py
```

## What you do not need right now

You do **not** need to become an ML researcher to own this product.

You need to be able to:

- explain the lanes
- explain the key files
- run the validation board
- tell a running app from a healthy app
- make small safe edits without panic

That is real ownership.
