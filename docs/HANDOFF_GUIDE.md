# Turf Intelligence Handoff Guide

This repo is a turfgrass-focused AI application with four main strengths:

- deterministic label-backed product answers
- advanced turf science and diagnosis modes
- eval-driven quality control
- admin moderation / feedback / KB improvement tools

## What matters most

If someone new is opening this repo, the highest-signal files are:

- [app.py](/Users/christiancrossmock/Desktop/turf-ai/app.py): main Flask application and routing
- [verified_kb.py](/Users/christiancrossmock/Desktop/turf-ai/verified_kb.py): deterministic label/product answer layer
- [advanced_turf_science.py](/Users/christiancrossmock/Desktop/turf-ai/advanced_turf_science.py): science explainer mode
- [advanced_diagnosis.py](/Users/christiancrossmock/Desktop/turf-ai/advanced_diagnosis.py): diagnosis mode
- [expert_mode_router.py](/Users/christiancrossmock/Desktop/turf-ai/expert_mode_router.py): routing among expert lanes
- [feedback_system.py](/Users/christiancrossmock/Desktop/turf-ai/feedback_system.py): feedback, moderation, KB gaps, router review flow
- [templates/admin.html](/Users/christiancrossmock/Desktop/turf-ai/templates/admin.html): admin console

## Core route map

If a new engineer wants to understand the app by user-facing surface first, start here:

- `/`
  - main chatbot interface
- `/ask`
  - primary question-answer route for chat, verified KB answers, science, diagnosis, and image analysis
- `/feedback`
  - user feedback intake path
- `/admin`
  - admin landing page and navigation shell
- `/admin/eval-dashboard`
  - aggregated eval-family health view
- `/admin/feedback/all`
  - raw feedback / query stream
- `/admin/review-queue`
  - moderation and training review queue
- `/admin/course-profile`
  - profile testing and saved course-context management
- `/health` and `/ready`
  - operational liveness / readiness checks

## Core subsystem map

These are the main modules by responsibility:

- [app.py](/Users/christiancrossmock/Desktop/turf-ai/app.py)
  - Flask routes, request flow, answer-lane orchestration, admin endpoints
- [verified_kb.py](/Users/christiancrossmock/Desktop/turf-ai/verified_kb.py)
  - deterministic product / label / comparison / target-matching answers
- [expert_mode_router.py](/Users/christiancrossmock/Desktop/turf-ai/expert_mode_router.py)
  - intent routing among science, diagnosis, general guidance, and verified product lanes
- [advanced_turf_science.py](/Users/christiancrossmock/Desktop/turf-ai/advanced_turf_science.py)
  - deterministic science and mechanism explainers
- [advanced_diagnosis.py](/Users/christiancrossmock/Desktop/turf-ai/advanced_diagnosis.py)
  - deterministic diagnostic differentials and field-triage structure
- [course_profile.py](/Users/christiancrossmock/Desktop/turf-ai/course_profile.py)
  - optional course-context shaping and general turf guidance responses
- [feedback_system.py](/Users/christiancrossmock/Desktop/turf-ai/feedback_system.py)
  - feedback ingestion, moderation, KB gaps, review queue, training records
- [auth_store.py](/Users/christiancrossmock/Desktop/turf-ai/auth_store.py)
  - account, password-reset, and verification persistence
- [chat_history.py](/Users/christiancrossmock/Desktop/turf-ai/chat_history.py)
  - conversation persistence, export, delete
- [rate_limit_store.py](/Users/christiancrossmock/Desktop/turf-ai/rate_limit_store.py)
  - request throttling

## One-command quality check

Run this before or after moving the repo:

```bash
python3 scripts/run_handoff_quality_suite.py
```

That runs:

- auth / route / KB tests
- comprehensive 100-question eval
- anti-slop eval
- no-account eval
- context-switch eval
- image eval
- smoke check

## Current eval families

- [run_anti_slop_eval.py](/Users/christiancrossmock/Desktop/turf-ai/scripts/run_anti_slop_eval.py)
- [run_ambiguity_eval.py](/Users/christiancrossmock/Desktop/turf-ai/scripts/run_ambiguity_eval.py)
- [run_comprehensive_100_eval.py](/Users/christiancrossmock/Desktop/turf-ai/scripts/run_comprehensive_100_eval.py)
- [run_product_label_eval.py](/Users/christiancrossmock/Desktop/turf-ai/scripts/run_product_label_eval.py)
- [run_no_account_turf_eval.py](/Users/christiancrossmock/Desktop/turf-ai/scripts/run_no_account_turf_eval.py)
- [run_context_switch_eval.py](/Users/christiancrossmock/Desktop/turf-ai/scripts/run_context_switch_eval.py)
- [run_image_eval.py](/Users/christiancrossmock/Desktop/turf-ai/scripts/run_image_eval.py)
- [run_phd_turf_eval.py](/Users/christiancrossmock/Desktop/turf-ai/scripts/run_phd_turf_eval.py)

## Answer paths

The product uses a few different answer lanes:

- `verified_product`
  - deterministic structured-KB answers for product labels, rates, intervals, targets, comparisons, and target-to-product matching
- `advanced_turf_science`
  - deterministic turf science explainers for mechanism, physiology, soils, water, and superintendent-style “why” questions
- `advanced_diagnosis`
  - deterministic diagnosis framework answers for field troubleshooting and differential diagnosis
- `general_turf_guidance`
  - deterministic broad agronomy guidance for “how do I keep…” and “what should I know…” questions
- general LLM-backed answer path
  - used only when the deterministic layers do not have a stronger fit

The important handoff truth is that this is **not** just a generic chat wrapper. The strongest and safest product behavior lives in the deterministic lanes above.

## Handoff-day shortcut

If you need the short version on the day itself, use:

- [Handoff-Day Cheat Sheet](/Users/christiancrossmock/Desktop/turf-ai/docs/HANDOFF_DAY_CHEAT_SHEET.md)

## Admin and eval usage

The admin surface is meant to answer three questions:

- what is the app seeing from users?
- where are the KB / moderation / training gaps?
- are the eval suites still green?

The main admin areas worth checking:

- `/admin`
  - dashboard and navigation
- `/admin/eval-dashboard`
  - eval family results and cached history
- `/admin/feedback/all`
  - feedback stream
- `/admin/review-queue`
  - moderation / training review queue
- `/admin/course-profile`
  - stored course context view and testing surface

For a repeatable local demo-path spot check, run:

```bash
python3 scripts/run_demo_prompt_check.py
```

That script uses the same session/CSRF shape the browser does, so it is a better local smoke tool than a bare `/ask` test-client call.

`/admin` stays closed by default now. If you intentionally set `ALLOW_PUBLIC_ADMIN=true`
for a short-lived local dev session, `/admin` can be opened without login.
That is convenience mode only and should not be used for release.

## Product truth

At its core, this is:

- a turfgrass chatbot
- that reads structured product-label knowledge
- and answers with or without course context

Course context should sharpen answers, not be the price of admission.

## Source policy

The current source posture is intentionally mixed, not all-or-nothing:

- `static/product-labels`
  - publicly viewable through the app
  - exposed through `/product-labels/<filename>`
  - included in `/resources` and `/api/resources`
- other local document buckets
  - not publicly viewable through the app
  - `/epa_labels/*`, `/solution-sheets/*`, `/spray-programs/*`, and `/ntep-pdfs/*` return `404`
  - those folders are not listed in the public resources endpoints
- Pinecone metadata
  - does **not** store raw chunk text for newly indexed documents
  - runtime retrieval reconstructs chunk text locally from the private file path when needed
- verified product answers
  - use the structured KB as the primary user-facing authority layer
  - may include clickable product-label links when the product record points at `static/product-labels`

The important handoff truth is:

- product labels are the only local third-party source documents intentionally surfaced to users right now
- all other local document corpora are private/internal only

## Known posture

Strong:

- verified label/product questions
- product-target and target-product matching
- comparison questions on major turf product pairs
- diagnosis and science routing
- no-account experience

Still expandable:

- more comparison pairs
- more label-field completeness on lower-traffic products
- more superintendent-style everyday phrasing
- deeper agronomy / pathology / soils coverage

## Repo readiness notes

- `/admin` is closed by default
- setting `ALLOW_PUBLIC_ADMIN=true` intentionally opens it without login
- release environments should keep `ALLOW_PUBLIC_ADMIN=false`
- the main release/planning docs are:
  - [README.md](/Users/christiancrossmock/Desktop/turf-ai/README.md)
  - [HANDOFF_STATUS.md](/Users/christiancrossmock/Desktop/turf-ai/docs/HANDOFF_STATUS.md)
  - [HANDOFF_14_DAY_PLAN.md](/Users/christiancrossmock/Desktop/turf-ai/docs/HANDOFF_14_DAY_PLAN.md)
  - [RELEASE_CHECKLIST.md](/Users/christiancrossmock/Desktop/turf-ai/docs/RELEASE_CHECKLIST.md)
  - [AWS_LAMBDA_READINESS.md](/Users/christiancrossmock/Desktop/turf-ai/docs/AWS_LAMBDA_READINESS.md)
  - [HANDOFF_30_DAY_CHECKLIST.md](/Users/christiancrossmock/Desktop/turf-ai/docs/HANDOFF_30_DAY_CHECKLIST.md)
  - [KNOWN_ISSUES.md](/Users/christiancrossmock/Desktop/turf-ai/docs/KNOWN_ISSUES.md)
