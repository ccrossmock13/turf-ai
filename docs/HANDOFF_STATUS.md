# Turf Intelligence Handoff Status

Last updated: `2026-05-17 09:06:00 PDT`

This file is the short version of repo readiness for the receiving team.

## Current state

- handoff checklist completed
- no critical handoff blockers currently open
- core user-facing chatbot lanes are validated
- admin and eval surfaces are loading and visible
- source policy is stable and implemented
- moderation queue now returns multiple distinct items instead of collapsing duplicate clusters into a single visible card
- feedback is tied to the specific answer card the user rated, not a shared page-level feedback state

## Latest validation snapshot

Latest successful checks:

- `python3 scripts/run_handoff_quality_suite.py`
  - passed
- `python3 scripts/run_demo_prompt_check.py`
  - passed
- `python3 -m unittest test_feedback_runtime.py test_operational_route.py test_verified_kb.py test_knowledge_base.py test_expert_mode_router.py`
  - `321` passed
- `python3 scripts/smoke_check_simple_app.py`
  - passed
- `GET /admin/eval-dashboard?refresh=true`
  - `200`
  - `9` eval families visible
- `python3 scripts/run_image_eval.py`
  - passed in deterministic handoff mode
- `python3 scripts/run_product_label_eval.py`
  - `124/124` passed
- `python3 scripts/run_general_turf_eval.py`
  - `27/27` passed
- `python3 scripts/run_no_account_turf_eval.py`
  - `39/39` passed
- `python3 scripts/run_anti_slop_eval.py`
  - `37/37` passed

Latest moderation checks:

- `get_review_queue(limit=20, queue_type='all')`
  - returns multiple distinct moderation items
- `get_priority_review_queue(limit=20)`
  - returns multiple distinct priority items
- duplicate clusters remain visible through `duplicate_count`
  - they no longer swallow the entire visible queue

Latest demo-path spot checks through `/ask`:

- `What diseases does Daconil control?`
  - `verified_product` / `Verified Supported Targets`
- `What fungicides control dollar spot?`
  - `verified_product` / `Verified Target Options`
- `What is the difference between prodiamine and dithiopyr?`
  - `verified_product` / `Verified Product Comparison`
- `What is the difference between Secure and Medallion?`
  - `verified_product` / `Verified Product Comparison`
- `What controls annual bluegrass weevil?`
  - `verified_product` / `Verified Target Options`
- `What should I spray on bermuda fairways for goosegrass?`
  - `verified_product` / `Verified Surface-Target Options`
- `Why does Poa annua decline faster than bentgrass in summer?`
  - `advanced_turf_science` / `Advanced Turf Science`
- `What should I be watching on greens this week?`
  - `general_turf_guidance` / `General Turf Guidance`
- `What is Headway used for?`
  - `verified_product` / `Verified Supported Targets`
- `What is Lexicon used for?`
  - `verified_product` / `Verified Supported Targets`
- `What is PoaCure used for?`
  - `verified_product` / `Verified Supported Targets`
- `What should I use for roughstalk bluegrass on greens?`
  - `verified_product` / `Verified Surface-Target Options`
- `What is Briskway used for?`
  - `verified_product` / `Verified Supported Targets`
- `What is Kerb SC used for?`
  - `verified_product` / `Verified Supported Targets`
- `Can I overseed after Kerb SC?`
  - `verified_product` / `Verified Overseeding Interval`
- `What is Posterity used for?`
  - `verified_product` / `Verified Supported Targets`
- `How soon can I spray Posterity again?`
  - `verified_product` / `Verified Re-Treatment Interval`

## Eval families currently surfaced in admin

- `general_turf`
- `anti_slop`
- `ambiguity`
- `comprehensive_100`
- `no_account`
- `context_switch`
- `phd_turf`
- `product_label`
- `image`

## Handoff posture

This repo should be treated as:

- a stable handoff build
- safe for bug-fix-only changes
- not a candidate for broad behavior churn without new eval coverage
- image eval is deterministic by default for handoff validation; use `--live` only when you want a real vendor-path spot check
- auth-heavy suites should be run serially in this repo because they share file-backed account/reset stores during tests

## Current source posture

- `static/product-labels`
  - publicly viewable
  - surfaced through `/product-labels/<filename>`
  - listed in `/resources` and `/api/resources`
- `static/epa_labels`, `static/solution-sheets`, `static/spray-programs`, `static/ntep-pdfs`
  - not publicly viewable
  - routes return `404`
  - not listed in public resources
- Pinecone metadata
  - does not store raw chunk text for newly indexed documents
  - search/reranking reconstruct chunk text locally when needed

## Current KB depth snapshot

Latest structured KB audit:

- `64` products
- `293` label PDFs
- `0` structured warnings
- field coverage now includes:
  - `irrigation_guidance`: `64/64`
  - `application_window_notes`: `64/64`
  - `max_rate_per_app`: `64/64`
  - `max_apps_per_year`: `64/64`
  - `reseeding_interval`: `64/64`
  - `overseeding_interval`: `64/64`
  - `retreatment_interval`: `64/64`

## First commands for the receiving team

```bash
python3 scripts/run_handoff_quality_suite.py
python3 scripts/smoke_check_simple_app.py
```
