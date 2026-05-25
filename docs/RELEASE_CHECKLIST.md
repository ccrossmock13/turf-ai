# Greenside AI Release Checklist

This is the release gate for Greenside AI.

The goal is to stop expanding scope forever and answer one question clearly:

**Can we release this version with a straight face?**

If an item in **Must Ship** is not done, we are not ready.

## Release Target

Current honest target:

- `Managed pilot / paid beta`: close
- `Broad self-serve SaaS`: not ready yet

This checklist is written so we can get to a releaseable managed beta first,
then decide whether to harden further for self-serve SaaS.

## Must Ship

### 1. Remove machine-specific paths

Status: `Open`

Why it matters:
- The app still contains hardcoded local absolute paths.
- That means evals and some admin quality features can silently break anywhere except this machine.

Done means:
- No `/Users/christiancrossmock/...` paths remain in app code, tests, or eval fixtures.
- Eval case files use repo-relative paths.
- Admin eval dashboard resolves case files from the repo, not one laptop.

Known hotspots:
- [app.py](/Users/christiancrossmock/Desktop/turf-ai/app.py#L595)
- [test_knowledge_base.py](/Users/christiancrossmock/Desktop/turf-ai/test_knowledge_base.py#L82)
- [image_eval_cases.json](/Users/christiancrossmock/Desktop/turf-ai/scripts/image_eval_cases.json)

Owner: `Engineering`

### 2. Stop shipping runtime data in the repo

Status: `Open`

Why it matters:
- The workspace currently contains runtime account files, password reset data, SQLite DBs, and many saved course profiles.
- That is a privacy, compliance, and operational hygiene problem.

Done means:
- `data/` runtime state is excluded from git by policy unless explicitly required fixture data is separated.
- Existing runtime/account/profile DB artifacts are removed from the tracked release artifact.
- We have a clean split between:
  - product code
  - test fixtures
  - runtime state

Known hotspots:
- [`.gitignore`](/Users/christiancrossmock/Desktop/turf-ai/.gitignore#L1)
- [auth_store.py](/Users/christiancrossmock/Desktop/turf-ai/auth_store.py#L24)
- [course_profile.py](/Users/christiancrossmock/Desktop/turf-ai/course_profile.py#L101)
- [chat_history.py](/Users/christiancrossmock/Desktop/turf-ai/chat_history.py#L15)

Owner: `Engineering`

### 3. Lock one supported deployment model

Status: `Open`

Why it matters:
- The app currently mixes file-backed auth, file-backed course profiles, and SQLite chat/feedback storage.
- That can work, but only for certain hosting shapes.

We need to choose one launch model:
- `Option A`: single-instance or managed deployment with persistent mounted storage
- `Option B`: replatform persistence before launch

Done means:
- The supported deployment architecture is explicitly documented.
- It is tested in an environment that matches production.
- `DATA_DIR` persistence is guaranteed.
- Backup/restore expectations are documented.

Known hotspots:
- [README.md](/Users/christiancrossmock/Desktop/turf-ai/README.md#L64)
- [auth_store.py](/Users/christiancrossmock/Desktop/turf-ai/auth_store.py#L24)
- [course_profile.py](/Users/christiancrossmock/Desktop/turf-ai/course_profile.py#L38)
- [chat_history.py](/Users/christiancrossmock/Desktop/turf-ai/chat_history.py#L14)
- [feedback_system.py](/Users/christiancrossmock/Desktop/turf-ai/feedback_system.py#L17)

Owner: `Engineering + Ops`

### 4. Make readiness a real release gate

Status: `Open`

Why it matters:
- The app has a real readiness probe, but local smoke currently accepts `503`.
- That is fine for development, but not as a release signal.

Done means:
- Staging `/ready` returns `200`.
- CI or pre-release checks fail if `/ready` is not healthy.
- Missing production requirements are treated as blockers, not warnings we ignore.

Known hotspots:
- [app.py](/Users/christiancrossmock/Desktop/turf-ai/app.py#L3054)
- [smoke_check_simple_app.py](/Users/christiancrossmock/Desktop/turf-ai/scripts/smoke_check_simple_app.py#L64)

Owner: `Engineering + Ops`

### 5. Replace in-memory rate limiting

Status: `Open`

Why it matters:
- Rate limiting is currently process-local.
- It will reset on restart and will not protect correctly across multiple workers or instances.

Done means:
- Rate limiting is moved to a shared layer:
  - reverse proxy / WAF / API gateway / Redis-backed app limit
- Limits are documented by route class:
  - auth
  - ask
  - admin

Known hotspot:
- [app.py](/Users/christiancrossmock/Desktop/turf-ai/app.py#L116)

Owner: `Engineering + Ops`

### 6. Finish production security posture

Status: `Open`

Why it matters:
- Basic CSRF and auth checks are in place.
- Production transport and browser hardening are still incomplete.

Done means:
- HTTPS is mandatory in production.
- HSTS is enabled.
- CSP is defined and tested.
- Cookie/session settings are reviewed in the real deployment.
- Reverse proxy config matches the actual production host, not just local nginx sample assumptions.

Known hotspots:
- [app.py](/Users/christiancrossmock/Desktop/turf-ai/app.py#L94)
- [app.py](/Users/christiancrossmock/Desktop/turf-ai/app.py#L307)
- [nginx.conf](/Users/christiancrossmock/Desktop/turf-ai/nginx.conf#L42)

Owner: `Engineering + Ops`

### 7. Add a product/label eval suite

Status: `Open`

Why it matters:
- The highest-risk mistakes in this product are product, rate, interval, REI, tank mix, and label-use mistakes.
- Current eval dashboard covers:
  - general turf
  - ambiguity
  - image
- That is not enough for release confidence.

Done means:
- A dedicated product/label eval suite exists.
- It covers:
  - rates
  - REI
  - retreat intervals
  - irrigation guidance
  - rainfast
  - reseeding/overseeding intervals
  - tank mix
  - unsupported label questions
- Results show in admin eval dashboard.
- A minimum launch pass threshold is set and met.

Known hotspot:
- [app.py](/Users/christiancrossmock/Desktop/turf-ai/app.py#L587)

Owner: `Engineering + KB`

### 8. Define and hit KB trust thresholds

Status: `Open`

Why it matters:
- The KB is strong, but release confidence needs a measurable bar.
- We should not release based on “feels good.”

Done means:
- We define launch thresholds for product trust, for example:
  - top launch products human-reviewed
  - top launch label fields human-reviewed
  - unsupported fields never surfaced as verified
- The KB Quality Dashboard reports these thresholds clearly.
- Launch scope is trimmed if coverage is not there.

Known references:
- [README.md](/Users/christiancrossmock/Desktop/turf-ai/README.md#L52)
- [products.json](/Users/christiancrossmock/Desktop/turf-ai/knowledge/products.json)
- [admin.html](/Users/christiancrossmock/Desktop/turf-ai/templates/admin.html)

Owner: `KB + Product`

### 9. Close account/data lifecycle gaps

Status: `Open`

Why it matters:
- Paid customers will eventually ask:
  - how do I delete my account?
  - how do I delete my data?
  - how long do you keep it?
  - how do you restore from failure?

Done means:
- We have a real answer for:
  - account deletion or deactivation
  - data retention
  - backup/restore
  - support access to user data
- Either implemented in product or handled with documented ops workflow.

Known gap:
- no clear delete/retention/restore workflow found in:
  - [app.py](/Users/christiancrossmock/Desktop/turf-ai/app.py)
  - [auth_store.py](/Users/christiancrossmock/Desktop/turf-ai/auth_store.py)
  - [README.md](/Users/christiancrossmock/Desktop/turf-ai/README.md)

Owner: `Product + Ops`

### 10. Decide whether email verification is required for launch

Status: `Open`

Why it matters:
- There is password reset, but no email verification flow.
- For managed beta this may be okay.
- For self-serve SaaS this is usually expected.

Done means:
- We explicitly choose one:
  - `Managed beta`: no email verification, admin-controlled onboarding
  - `Self-serve`: email verification implemented before launch

Known gap:
- no email verification flow found in:
  - [app.py](/Users/christiancrossmock/Desktop/turf-ai/app.py)
  - [auth_store.py](/Users/christiancrossmock/Desktop/turf-ai/auth_store.py)

Owner: `Product`

### 11. Make external dependency behavior explicit

Status: `Open`

Why it matters:
- OpenAI and Pinecone clients are created at import time.
- That increases fragility and makes deployment failures harsher than they need to be.

Done means:
- We choose one policy:
  - lazy-init with graceful errors
  - or explicit hard fail at startup with documented infra requirements
- Health and readiness reflect that policy clearly.

Known hotspot:
- [app.py](/Users/christiancrossmock/Desktop/turf-ai/app.py#L103)

Owner: `Engineering`

## Should Ship If Time Allows

These are important, but they do not need to block a managed beta if the Must Ship section is done.

### 12. Break up oversized files

Why it matters:
- Some core files are now very large:
  - [app.py](/Users/christiancrossmock/Desktop/turf-ai/app.py)
  - [admin.html](/Users/christiancrossmock/Desktop/turf-ai/templates/admin.html)
  - [feedback_system.py](/Users/christiancrossmock/Desktop/turf-ai/feedback_system.py)
- That will slow future development and increase release risk over time.

Done means:
- App routes are grouped by responsibility.
- Admin JS/UI is split into manageable sections.
- Feedback/KB/admin work items are separated into clearer modules.

### 13. Add stronger observability

Why it matters:
- We need to know what happens after launch, not just before it.

Done means:
- Capture and review:
  - answer mode mix
  - fallback rate
  - safety-block rate
  - eval trends
  - KB gap trends
  - major error categories

### 14. Add admin-visible launch KPIs

Why it matters:
- The admin already has quality tooling.
- It should also show release health at a glance.

Done means:
- Dashboard includes:
  - `/ready` summary
  - eval pass rates
  - high-risk KB coverage
  - recent safety blocks
  - active review queues

## Can Defer Until After First Release

These are good improvements, but they are not reasons to delay a managed release.

- more KB depth
- more image eval coverage
- more admin polish
- more UX polish on non-critical flows
- broader fine-tuning workflow
- full billing/subscription implementation if launch is founder-led
- major architectural cleanup purely for elegance

## Launch Decision Table

Use this table when we want to decide “release” vs “not yet.”

| Area | Release rule |
| --- | --- |
| Deployment | One supported production architecture is chosen and tested |
| Secrets | Production secrets configured and `/ready` returns `200` |
| Storage | Persistent `DATA_DIR` and backup plan are documented |
| Security | TLS, session, CSRF, and rate-limit strategy are production-ready |
| Product safety | Product/label eval suite exists and passes launch threshold |
| KB trust | Launch KB review threshold is defined and met |
| Privacy/data | No runtime customer data ships in repo or artifacts |
| Supportability | Restore, retention, and admin support posture are documented |

## Recommendation

Recommended path:

1. Release as a **managed pilot / paid beta**
2. Do **not** call it broad self-serve SaaS yet
3. Finish every item in **Must Ship**
4. Freeze scope after that and launch

## Working Rule

Until this checklist is green:

- do not add more random KB depth
- do not keep polishing admin forever
- do not treat “tests pass locally” as release readiness

Work the blockers in order, then ship.
