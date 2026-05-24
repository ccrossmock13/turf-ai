# Turf Intelligence

Turf Intelligence is a Flask-based turf management assistant focused on practical, superintendent-grade answers for diagnosis, product guidance, weather-aware recommendations, and course-specific context.

It combines:

- structured and verified product knowledge
- retrieval across a broader turf knowledge library
- domain-tuned prompts and topic routing
- feedback, admin review, and quality gates
- account-aware chat history and course profiles

## What This App Does

Core capabilities in the current app:

- answer turf management questions through `/ask`
- handle disease, fertility, irrigation, weed, and product-support questions
- use verified KB flows for higher-confidence product answers
- fall back to retrieval, scoring, reranking, and validation for broader questions
- support image-assisted diagnosis
- store user accounts, chat history, and course profiles
- expose admin and feedback workflows for improving the system over time

## Project Shape

High-level structure:

- [app.py](/Users/christiancrossmock/Desktop/turf-ai/app.py): main Flask app, runtime orchestration, request handling
- [routes.py](/Users/christiancrossmock/Desktop/turf-ai/routes.py): page and resource routes
- [config.py](/Users/christiancrossmock/Desktop/turf-ai/config.py): environment-driven configuration
- [prompts.py](/Users/christiancrossmock/Desktop/turf-ai/prompts.py): system prompt building blocks and topic-specific prompt modules
- [knowledge](/Users/christiancrossmock/Desktop/turf-ai/knowledge): structured turf knowledge files
- [templates](/Users/christiancrossmock/Desktop/turf-ai/templates): HTML templates
- [scripts](/Users/christiancrossmock/Desktop/turf-ai/scripts): eval, maintenance, and operational scripts
- root-level `test_*.py`: active unittest-based regression suite
- [docs](/Users/christiancrossmock/Desktop/turf-ai/docs): handoff, release, and operational documentation

## Request Flow

At a high level, the app works like this:

1. A user submits a turf question or image.
2. The app classifies the request and gathers context.
3. Verified KB logic answers directly when possible.
4. Otherwise the app builds retrieval context from the broader knowledge stack.
5. The LLM is prompted with domain instructions plus contextual evidence.
6. Post-processing layers apply grounding, safety, validation, and response shaping.
7. Feedback and chat history can be stored for future improvement.

## Local Setup

1. Copy the example environment file:

```bash
cp .env.example .env
```

2. Fill in the values you need in `.env`.

Recommended minimum local variables:

```env
FLASK_SECRET_KEY=change-me
APP_ENV=development
OPENAI_API_KEY=your-openai-key
PINECONE_API_KEY=your-pinecone-key
PINECONE_INDEX=turf-research
```

Optional integrations already supported:

- `TAVILY_API_KEY` for web-search fallback
- `OPENWEATHER_API_KEY` for weather-aware answers
- SMTP settings for password reset / verification
- `DEMO_MODE=true` if you want admin available locally without an account

Environment notes:

- `APP_ENV` is the primary runtime environment setting
- `FLASK_ENV` is still accepted as a compatibility alias when `APP_ENV` is not set

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Run the app:

```bash
python app.py
```

Default local port is controlled by `FLASK_PORT` in [config.py](/Users/christiancrossmock/Desktop/turf-ai/config.py).

## Testing And Quality Checks

Useful local checks:

```bash
python -m unittest test_auth_flow.py
python -m unittest test_operational_route.py
python scripts/run_demo_prompt_check.py
python scripts/run_handoff_quality_suite.py
```

Quality coverage in this repo includes:

- root-level regression tests
- demo prompt checks
- eval runners for ambiguity, anti-slop, image, context-switch, and broader turf quality

See [tests/README.md](/Users/christiancrossmock/Desktop/turf-ai/tests/README.md) and [scripts](/Users/christiancrossmock/Desktop/turf-ai/scripts) for the current testing layout.

## Prompt System

The prompt layer is currently centered in [prompts.py](/Users/christiancrossmock/Desktop/turf-ai/prompts.py).

Important pieces:

- `BASE_PROMPT`: role, response standards, safety rules
- `KNOWLEDGE_SUPPLEMENT`: core turf-science facts
- `FEW_SHOT_EXAMPLES`: example reasoning patterns
- topic prompts such as disease, herbicide, irrigation, fertilizer, and diagnostics
- `build_system_prompt(...)`: combines the relevant prompt parts for each request

If you want to improve functionality through prompt work, start with:

- [docs/PROMPT_STRUCTURE.md](/Users/christiancrossmock/Desktop/turf-ai/docs/PROMPT_STRUCTURE.md)

That guide covers how to change prompts without accidentally weakening grounding, safety, or answer quality.

## How To Improve This App Safely

When adding or improving functionality, use this order:

1. Define the user-facing behavior you want to improve.
2. Decide which layer should change:
   - UI/template
   - route/controller logic
   - retrieval/search/reranking
   - verified KB / structured knowledge
   - prompt structure
   - safety/validation/grounding
3. Make the smallest change at the correct layer.
4. Add or run the nearest regression test or eval.
5. Test at least one success case and one failure/edge case.

Good examples of targeted improvements:

- improve diagnosis quality by adding missing retrieval evidence
- improve product answers by extending verified KB coverage
- improve answer shape by tightening prompt instructions
- improve trust by expanding validation or hallucination checks
- improve onboarding by clarifying UI or account flows

Avoid using prompt changes as the first fix for:

- missing source data
- routing bugs
- incorrect product facts
- broken state handling
- poor retrieval quality

## Persistence And Deployment Notes

Current supported launch model:

- one app instance
- persistent writable `DATA_DIR`
- file-backed or DynamoDB-backed runtime persistence, depending on configuration

Relevant entrypoints:

- [wsgi.py](/Users/christiancrossmock/Desktop/turf-ai/wsgi.py)
- [aws_lambda.py](/Users/christiancrossmock/Desktop/turf-ai/aws_lambda.py)
- [function_app.py](/Users/christiancrossmock/Desktop/turf-ai/function_app.py)

For production, review:

- [docs/RELEASE_CHECKLIST.md](/Users/christiancrossmock/Desktop/turf-ai/docs/RELEASE_CHECKLIST.md)
- [docs/AWS_LAMBDA_READINESS.md](/Users/christiancrossmock/Desktop/turf-ai/docs/AWS_LAMBDA_READINESS.md)
- [docs/KNOWN_ISSUES.md](/Users/christiancrossmock/Desktop/turf-ai/docs/KNOWN_ISSUES.md)

## Contributor Docs

Useful starting points:

- [CONTRIBUTING.md](/Users/christiancrossmock/Desktop/turf-ai/CONTRIBUTING.md)
- [docs/README.md](/Users/christiancrossmock/Desktop/turf-ai/docs/README.md)
- [docs/PROJECT_BASED_BUILD_COURSE.md](/Users/christiancrossmock/Desktop/turf-ai/docs/PROJECT_BASED_BUILD_COURSE.md)
- [docs/HANDOFF_GUIDE.md](/Users/christiancrossmock/Desktop/turf-ai/docs/HANDOFF_GUIDE.md)

## Legal Note

This product is decision support, not a replacement for pesticide labels, local regulations, or site-specific professional judgment. Label instructions and local requirements always win.
