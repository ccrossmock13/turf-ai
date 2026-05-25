# Project-Based Course: Build Turf Intelligence

This course teaches someone how to build a real app like this one by rebuilding it in stages.

It is not a theory-first course.

Each module ends with a working product milestone, a concrete deliverable, and a review checklist.

## Course outcome

By the end, the student will be able to build a production-minded Flask AI application with:

- a chat-style web UI
- an authenticated account system
- persistent chat history
- a structured knowledge layer
- retrieval and reranking
- deterministic answer lanes for high-trust questions
- feedback and admin review workflows
- deployment and readiness checks

## Who this is for

- junior-to-mid developers who know basic Python and HTML/CSS
- builders who have used an API before but have not shipped an AI product
- founders or operators who want to understand how an app like this is actually assembled

## What the student will build

They will build a simplified Turf Intelligence clone in 8 projects:

1. A Flask shell with a chat interface
2. A working `/ask` route backed by an LLM
3. Memory, sessions, and saved chat history
4. Retrieval over turf documents and structured knowledge
5. Deterministic product-answer workflows
6. Course-profile context and operational guidance
7. Feedback, moderation, and admin tooling
8. Production hardening, evals, and deployment

## Teaching format

Recommended pacing:

- 8 weeks part time, 2 projects per week for an intensive cohort
- or 8 modules over 8 to 10 weeks for a guided bootcamp

Every module should include:

- one build session
- one code reading session using this repo
- one debugging lab
- one reflection/demo checkpoint

## Core repo references

Students should read these files repeatedly during the course:

- [app.py](/Users/christiancrossmock/Desktop/turf-ai/app.py)
- [templates/index.html](/Users/christiancrossmock/Desktop/turf-ai/templates/index.html)
- [verified_kb.py](/Users/christiancrossmock/Desktop/turf-ai/verified_kb.py)
- [advanced_turf_science.py](/Users/christiancrossmock/Desktop/turf-ai/advanced_turf_science.py)
- [advanced_diagnosis.py](/Users/christiancrossmock/Desktop/turf-ai/advanced_diagnosis.py)
- [expert_mode_router.py](/Users/christiancrossmock/Desktop/turf-ai/expert_mode_router.py)
- [course_profile.py](/Users/christiancrossmock/Desktop/turf-ai/course_profile.py)
- [feedback_system.py](/Users/christiancrossmock/Desktop/turf-ai/feedback_system.py)
- [config.py](/Users/christiancrossmock/Desktop/turf-ai/config.py)
- [README.md](/Users/christiancrossmock/Desktop/turf-ai/README.md)
- [docs/OWNER_MAP.md](/Users/christiancrossmock/Desktop/turf-ai/docs/OWNER_MAP.md)

## Module 1: Build the app shell

Goal:
Create the first usable version of the product with Flask, templates, and a simple chat layout.

Build:

- initialize Flask
- add `index.html`
- render a chat page with a message input and response area
- create health routes like `/health`

Concepts:

- Flask app structure
- request/response lifecycle
- server-rendered templates
- keeping the first version thin

Repo references:

- [app.py](/Users/christiancrossmock/Desktop/turf-ai/app.py)
- [routes.py](/Users/christiancrossmock/Desktop/turf-ai/routes.py)
- [templates/index.html](/Users/christiancrossmock/Desktop/turf-ai/templates/index.html)

Deliverable:
A local app that runs and shows a clean chat interface.

Acceptance check:

- `python app.py` starts successfully
- the homepage loads
- the UI is usable on desktop and mobile

## Module 2: Add the first AI answer path

Goal:
Turn the shell into a real AI app with a POST `/ask` endpoint and LLM-backed responses.

Build:

- connect the OpenAI client
- create a request payload
- return JSON answers
- wire the frontend to submit prompts asynchronously

Concepts:

- prompt construction
- API key management
- request validation
- graceful failure when the model is unavailable

Repo references:

- [app.py](/Users/christiancrossmock/Desktop/turf-ai/app.py)
- [config.py](/Users/christiancrossmock/Desktop/turf-ai/config.py)
- [demo_cache.py](/Users/christiancrossmock/Desktop/turf-ai/demo_cache.py)
- [templates/index.html](/Users/christiancrossmock/Desktop/turf-ai/templates/index.html)

Deliverable:
A chat app that accepts a question and returns an AI answer.

Acceptance check:

- `/ask` returns valid JSON
- the UI displays loading, success, and error states
- the app can fall back cleanly if the network is down

## Module 3: Sessions, auth, and persistence

Goal:
Teach students how to move from demo to product by adding accounts, sessions, and saved history.

Build:

- add registration and login
- persist users safely
- attach chats to users
- create account pages for export and deletion

Concepts:

- sessions and cookies
- hashed passwords
- CSRF protection
- file-backed persistence vs managed storage

Repo references:

- [auth_store.py](/Users/christiancrossmock/Desktop/turf-ai/auth_store.py)
- [chat_history.py](/Users/christiancrossmock/Desktop/turf-ai/chat_history.py)
- [templates/login.html](/Users/christiancrossmock/Desktop/turf-ai/templates/login.html)
- [templates/register.html](/Users/christiancrossmock/Desktop/turf-ai/templates/register.html)
- [templates/account.html](/Users/christiancrossmock/Desktop/turf-ai/templates/account.html)

Deliverable:
Users can create accounts, log in, and keep their own conversation history.

Acceptance check:

- user A cannot see user B's history
- account export works
- account deletion removes related chat data

## Module 4: Retrieval and knowledge grounding

Goal:
Show how a serious AI app gets beyond raw prompting by layering search and structured context.

Build:

- store turf knowledge in JSON and document folders
- create retrieval helpers
- score and rerank search results
- assemble context before generation

Concepts:

- embeddings
- vector search and keyword search
- reranking
- grounding and hallucination control

Repo references:

- [search_service.py](/Users/christiancrossmock/Desktop/turf-ai/search_service.py)
- [scoring_service.py](/Users/christiancrossmock/Desktop/turf-ai/scoring_service.py)
- [reranker.py](/Users/christiancrossmock/Desktop/turf-ai/reranker.py)
- [knowledge_base.py](/Users/christiancrossmock/Desktop/turf-ai/knowledge_base.py)
- [verified_kb.py](/Users/christiancrossmock/Desktop/turf-ai/verified_kb.py)
- [knowledge/](/Users/christiancrossmock/Desktop/turf-ai/knowledge)

Deliverable:
The app answers with retrieved support instead of pure freeform generation.

Acceptance check:

- answers cite or reflect retrieved context
- irrelevant search results are filtered
- obvious unsupported claims are reduced

## Module 5: Build deterministic answer lanes

Goal:
Teach students that high-trust apps should not send every question through one generic model path.

Build:

- classify incoming questions
- create specialized answer lanes
- build a deterministic verified-product workflow
- separate general guidance from diagnosis and science

Concepts:

- routing architecture
- narrow domain logic
- deterministic vs generative answers
- trust-aware product design

Repo references:

- [expert_mode_router.py](/Users/christiancrossmock/Desktop/turf-ai/expert_mode_router.py)
- [query_classifier.py](/Users/christiancrossmock/Desktop/turf-ai/query_classifier.py)
- [verified_kb.py](/Users/christiancrossmock/Desktop/turf-ai/verified_kb.py)
- [advanced_turf_science.py](/Users/christiancrossmock/Desktop/turf-ai/advanced_turf_science.py)
- [advanced_diagnosis.py](/Users/christiancrossmock/Desktop/turf-ai/advanced_diagnosis.py)

Deliverable:
The app chooses different answering strategies based on the question type.

Acceptance check:

- label questions hit the verified path
- diagnosis questions hit the diagnosis path
- broad management questions avoid brittle product logic

## Module 6: Add course memory and operator context

Goal:
Teach how personalization improves usefulness without pretending the app knows more than it does.

Build:

- create a course profile model
- store surface, soil, and mowing details
- inject profile context into answers
- build profile-aware operational guidance

Concepts:

- scoped memory
- structured context injection
- safe profile updates
- personalization with boundaries

Repo references:

- [course_profile.py](/Users/christiancrossmock/Desktop/turf-ai/course_profile.py)
- [test_course_profile.py](/Users/christiancrossmock/Desktop/turf-ai/test_course_profile.py)
- [app.py](/Users/christiancrossmock/Desktop/turf-ai/app.py)

Deliverable:
The app gives different answers based on the stored course context.

Acceptance check:

- profile updates persist correctly
- guidance changes when regional and surface inputs change
- the app does not invent missing profile details

## Module 7: Close the loop with feedback and admin tools

Goal:
Turn the app into an improvable product by capturing quality signals and surfacing review work.

Build:

- collect thumbs-up/thumbs-down or rating feedback
- save user queries for review
- build an admin dashboard
- add KB gap workflows and moderation actions

Concepts:

- human-in-the-loop review
- product telemetry
- operational tooling
- quality improvement loops

Repo references:

- [feedback_system.py](/Users/christiancrossmock/Desktop/turf-ai/feedback_system.py)
- [templates/admin.html](/Users/christiancrossmock/Desktop/turf-ai/templates/admin.html)
- [app.py](/Users/christiancrossmock/Desktop/turf-ai/app.py)
- [test_feedback_runtime.py](/Users/christiancrossmock/Desktop/turf-ai/test_feedback_runtime.py)

Deliverable:
An admin can review weak answers, identify gaps, and prioritize improvements.

Acceptance check:

- feedback records are stored
- admin routes are protected
- review queues help identify repeated failures

## Module 8: Production hardening and release readiness

Goal:
Teach students how to take a promising prototype and make it dependable.

Build:

- add rate limiting
- add readiness checks
- configure environment-based settings
- run automated tests and eval suites
- prepare deployment targets

Concepts:

- deployment safety
- readiness vs health
- persistence strategy
- eval-driven release decisions

Repo references:

- [rate_limit_store.py](/Users/christiancrossmock/Desktop/turf-ai/rate_limit_store.py)
- [persistence_backend.py](/Users/christiancrossmock/Desktop/turf-ai/persistence_backend.py)
- [scripts/run_handoff_quality_suite.py](/Users/christiancrossmock/Desktop/turf-ai/scripts/run_handoff_quality_suite.py)
- [docs/RELEASE_CHECKLIST.md](/Users/christiancrossmock/Desktop/turf-ai/docs/RELEASE_CHECKLIST.md)
- [docs/AWS_LAMBDA_READINESS.md](/Users/christiancrossmock/Desktop/turf-ai/docs/AWS_LAMBDA_READINESS.md)

Deliverable:
A version of the app that is safer to demo, pilot, and hand off.

Acceptance check:

- `/health` and `/ready` are meaningful
- tests pass locally
- deployment assumptions are documented

## Capstone

Final project:
Build a domain-specific AI assistant modeled on Turf Intelligence, but for a different niche.

Examples:

- vineyard operations
- golf fitness coaching
- sports field maintenance
- greenhouse disease triage
- landscape chemical planning

Required capstone features:

- authenticated user accounts
- chat history
- at least two answer lanes
- one deterministic knowledge-backed flow
- one admin review surface
- health and readiness endpoints

## Instructor notes

Strong teaching rhythm:

- students build a thin version first
- then compare their implementation to this repo
- then refactor toward the production pattern

That sequencing matters.

If students read this repo too early, they may copy complexity before they understand why it exists.

## Suggested grading rubric

- 20% app shell and UX
- 20% AI request/response flow
- 20% retrieval and answer quality
- 15% auth and persistence
- 15% admin and feedback loop
- 10% production readiness

## Recommended reading order inside this repo

1. [README.md](/Users/christiancrossmock/Desktop/turf-ai/README.md)
2. [docs/OWNER_MAP.md](/Users/christiancrossmock/Desktop/turf-ai/docs/OWNER_MAP.md)
3. [app.py](/Users/christiancrossmock/Desktop/turf-ai/app.py)
4. [templates/index.html](/Users/christiancrossmock/Desktop/turf-ai/templates/index.html)
5. [verified_kb.py](/Users/christiancrossmock/Desktop/turf-ai/verified_kb.py)
6. [course_profile.py](/Users/christiancrossmock/Desktop/turf-ai/course_profile.py)
7. [feedback_system.py](/Users/christiancrossmock/Desktop/turf-ai/feedback_system.py)
8. [docs/RELEASE_CHECKLIST.md](/Users/christiancrossmock/Desktop/turf-ai/docs/RELEASE_CHECKLIST.md)

## Optional advanced extensions

- image diagnosis workflows using [image_diagnosis.py](/Users/christiancrossmock/Desktop/turf-ai/image_diagnosis.py)
- weather-aware answers using [weather_service.py](/Users/christiancrossmock/Desktop/turf-ai/weather_service.py)
- DynamoDB persistence via [persistence_backend.py](/Users/christiancrossmock/Desktop/turf-ai/persistence_backend.py)
- serverless deployment via [aws_lambda.py](/Users/christiancrossmock/Desktop/turf-ai/aws_lambda.py) and [function_app.py](/Users/christiancrossmock/Desktop/turf-ai/function_app.py)

## Short version

If you want the cleanest summary:

- start with Flask and a chat UI
- add one trustworthy AI endpoint
- persist users and conversations
- add retrieval and structured knowledge
- split the app into answer lanes
- add personalization
- add admin review loops
- harden it for production
