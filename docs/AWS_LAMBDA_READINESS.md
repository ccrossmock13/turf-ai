# Greenside AI AWS Lambda Readiness

This document is deliberately separate from the main release checklist.

Why:
- **release readiness** asks whether we can launch safely for real users
- **AWS Lambda readiness** asks whether the app is a good fit for a Lambda-first runtime

Those are not the same question.

Current honest answer:

- **Managed beta release readiness:** close
- **AWS Lambda architecture readiness:** not ready yet

Update:

- an optional DynamoDB-backed runtime path now exists for:
  - accounts
  - account tokens
  - course profiles
  - chat history
  - rate limiting
  - core feedback/query records
  - expert router events
  - expert router work items
- this is a meaningful replatforming step
- it does **not** finish the full Lambda migration because feedback/admin/training state still uses local SQLite
- a DynamoDB bootstrap script now exists at [create_dynamodb_tables.py](/Users/christiancrossmock/Desktop/turf-ai/scripts/create_dynamodb_tables.py)
- `/ready` now checks for required DynamoDB tables when `PERSISTENCE_BACKEND=dynamodb`

## What Exists Today

The repo already has Lambda and cloud entrypoints:

- [aws_lambda.py](/Users/christiancrossmock/Desktop/turf-ai/aws_lambda.py)
- [function_app.py](/Users/christiancrossmock/Desktop/turf-ai/function_app.py)
- [wsgi.py](/Users/christiancrossmock/Desktop/turf-ai/wsgi.py)

That means the app can be *wrapped* for Lambda.

It does **not** yet mean the app is Lambda-native in how it stores state or scales.

## Why Lambda Is Not A Clean Fit Yet

The current launch model is explicitly:

- one app instance
- persistent writable `DATA_DIR`
- file-backed accounts and course profiles
- local SQLite for app state

That works for a managed beta.

It clashes with Lambda because Lambda is best when the app is mostly stateless and durable state lives in managed services.

## Current Lambda Gaps

### 1. File-backed accounts are not Lambda-native

Current state:
- accounts live in [auth_store.py](/Users/christiancrossmock/Desktop/turf-ai/auth_store.py)
- stored in `DATA_DIR/accounts/users.json`

Why this is a problem:
- Lambda local storage is ephemeral
- concurrent writes to one JSON file are fragile
- sharing that file safely across many Lambda invocations is not a strong production model

Lambda-ready options:
- move accounts to DynamoDB
- or move accounts to another managed auth/store layer

Status:
- **partially addressed**
- an optional DynamoDB backend now exists for accounts

Release-now status:
- acceptable for single-node managed beta
- **not** acceptable as a Lambda-first long-term architecture

### 2. Course profiles are file-based

Current state:
- profiles live in [course_profile.py](/Users/christiancrossmock/Desktop/turf-ai/course_profile.py)
- stored per account in `DATA_DIR/course_profiles/*.json`

Why this is a problem:
- same persistence/concurrency issue as accounts
- profile writes depend on writable shared disk

Lambda-ready options:
- DynamoDB table keyed by account id
- or another managed document store

Status:
- **partially addressed**
- an optional DynamoDB backend now exists for course profiles

### 3. Chat history uses local SQLite

Current state:
- chat state lives in [chat_history.py](/Users/christiancrossmock/Desktop/turf-ai/chat_history.py)
- stored in `greenside_conversations.db`

Why this is a problem:
- SQLite is fine on one node
- it is a poor shared-state model for Lambda concurrency
- Lambda instances do not share local disk

Lambda-ready options:
- DynamoDB for session/conversation/message storage
- or RDS/Aurora Serverless if relational querying is required

Status:
- **partially addressed**
- an optional DynamoDB backend now exists for chat history

### 4. Feedback and moderation state uses local SQLite

Current state:
- moderation/feedback/admin state lives in [feedback_system.py](/Users/christiancrossmock/Desktop/turf-ai/feedback_system.py)
- stored in `greenside_feedback.db`

Why this is a problem:
- same shared-state issue as chat history
- admin actions need durable centralized state

Lambda-ready options:
- move structured ops/admin state to managed storage

Status:
- **partially addressed**
- the runtime feedback/query path plus router review/work-item state can now use DynamoDB
- KB candidate review, moderator actions, and training/audit history are still local SQLite

### 5. Rate limiting is single-node persistent, not distributed

Current state:
- rate limiting lives in [rate_limit_store.py](/Users/christiancrossmock/Desktop/turf-ai/rate_limit_store.py)
- stored in local SQLite

Why this is a problem:
- Lambda needs a shared external limiter
- otherwise each execution environment sees a different picture

Lambda-ready options:
- API Gateway / WAF throttling
- Redis / ElastiCache
- DynamoDB-backed limiter

Status:
- **partially addressed**
- an optional DynamoDB backend now exists for rate limiting

### 6. Cold-start import cost is higher than ideal

Current state:
- the app creates the OpenAI and Pinecone clients at import time in [app.py](/Users/christiancrossmock/Desktop/turf-ai/app.py)
- the app imports a large amount of turf logic and admin machinery on startup

Why this matters:
- cold starts will be slower than they need to be
- Lambda punishes heavy import-time setup more than a long-lived server does

Lambda-ready options:
- lazy-init external clients
- reduce import-time work
- split admin-heavy surfaces from user runtime if needed

### 7. Local eval/admin caches assume writable local state

Current state:
- eval dashboard cache and runtime files are written into `DATA_DIR`

Why this matters:
- Lambda local writes are not reliable as shared persistent state

Lambda-ready options:
- move caches to managed storage
- or make them strictly best-effort and disposable

### 8. Large/complex request paths are better suited to container or VM first

Current state:
- image diagnosis
- admin dashboards
- eval runners
- moderation workflows

Why this matters:
- these are not impossible on Lambda
- but they are not the easiest place to start if the goal is a calm first release

## What Can Stay For A Managed Beta

These are okay **for now** if we launch as a small managed beta on a single persistent host:

- file-backed accounts
- file-backed course profiles
- local SQLite app state
- current persistent rate limiting
- current readiness model

That is the right reason not to force Lambda too early.

## What Must Change Before A Serious Lambda Deployment

These are the remaining Lambda blockers:

1. **Turn on and validate the DynamoDB runtime path in a real AWS environment**
2. **Move feedback/admin/training state off SQLite**
   - runtime feedback/router review is now covered
   - deeper KB candidate / training / moderator history is still pending
3. **Move any remaining document uploads/runtime cache/state to managed durable storage**
4. **Reduce import-time client setup**

If those are not done, Lambda is still a wrapper, not a good runtime fit.

## Recommended Path

### Phase 1: Release without forcing Lambda

Ship as:
- single instance
- persistent disk
- managed beta / paid pilot

This is the fastest path to real users.

### Phase 2: Make state Lambda-safe

Replatform, in this order:

1. accounts
2. course profiles
3. chat history
4. feedback/admin state
5. rate limiting

Do not start with the adapter. Start with the state model.

### Phase 3: Re-test readiness under Lambda constraints

Once state is externalized:
- re-run readiness
- re-run load probe against hosted environment
- test cold starts
- test concurrent writes

## Practical Conclusion

If the question is:

**“Can we release this app soon?”**

Answer: **yes, as a managed beta, nearly.**

If the question is:

**“Should AWS Lambda be the primary launch architecture right now?”**

Answer: **no, not until persistence is reworked.**

That is not failure. It is just the honest sequencing.
