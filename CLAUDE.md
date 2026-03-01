# CLAUDE.md — Greenside AI (Turf-AI)

## Project Overview
Greenside AI is a full-stack turfgrass management platform for golf course superintendents. It combines a RAG-powered AI chatbot (Pinecone + GPT-4o) with 13 operational tools (equipment tracking, irrigation, crew scheduling, etc.) and an admin moderation panel. The app runs on Flask with SSE streaming and supports both SQLite (dev) and PostgreSQL (prod).

## Tech Stack
- **Backend:** Python 3 / Flask 3.1, Gunicorn + gevent (prod)
- **AI/ML:** OpenAI GPT-4o (chat), text-embedding-3-small (embeddings), Pinecone (vector DB)
- **Database:** SQLite with WAL mode (dev) / PostgreSQL with connection pooling (prod)
- **Frontend:** Vanilla JS, server-rendered Jinja2 templates, custom CSS per page
- **Deployment:** Docker, Railway (railway.json), nginx reverse proxy
- **Monitoring:** Sentry, structured logging, intelligence analytics

## Quick Start
```bash
# Install dependencies
pip install -r requirements.txt

# Set required env vars (see .env.example or config.py)
export OPENAI_API_KEY=...
export PINECONE_API_KEY=...

# Run the dev server
python3 app.py
# → http://localhost:5001
```

## Project Structure

### Core Application
| File | Purpose |
|------|---------|
| `app.py` (~3200 lines) | Main Flask app — all routes including SSE chat streaming, admin panel, auth endpoints |
| `feature_routes.py` (~3400 lines) | `features_bp` Blueprint — API routes for all 13 feature modules |
| `config.py` | `Config` class — all env vars (API keys, model settings, rate limits, cost budgets) |
| `db.py` | Database abstraction — `get_db()` context manager, SQLite↔PostgreSQL auto-conversion |
| `auth.py` | `@login_required`, `@admin_required` decorators, session management, user CRUD |
| `constants.py` | Product lists, topic keywords, search folders, scoring weights |

### AI / RAG Pipeline
| File | Purpose |
|------|---------|
| `pipeline.py` | Synchronous query pipeline (non-streaming path) |
| `search_service.py` | Pinecone vector search, topic detection, source deduplication, `filter_display_sources()` |
| `scoring_service.py` | Result scoring/ranking, `build_context()`, safety filtering |
| `query_expansion.py` | Query expansion for vague questions |
| `query_rewriter.py` | Query rewriting for better retrieval |
| `query_classifier.py` | Intent classification |
| `reranker.py` | Cross-encoder reranking of search results |
| `answer_grounding.py` | Hallucination detection — checks answer grounding against sources |
| `answer_validator.py` | Answer quality validation |
| `hallucination_filter.py` | Filters hallucinated content from responses |
| `prompts.py` | System prompts and prompt templates |
| `knowledge_base.py` | Enriches context with scraped knowledge (diseases, weeds, pests, products) |
| `knowledge_builder.py` | PDF indexing into Pinecone (requires PyPDF2) |

### Feature Modules (each has matching template + CSS)
| Module | Template | Description |
|--------|----------|-------------|
| `equipment_manager.py` | `equipment.html` | Equipment inventory, maintenance scheduling |
| `irrigation_manager.py` | `irrigation.html` | Zone management, drought monitoring, water usage |
| `crew_management.py` | `crew.html` | Staff scheduling, certifications, time tracking |
| `budget_tracker.py` | `budget.html` | Budget categories, expense tracking, forecasting |
| `calendar_scheduler.py` | `calendar.html` | Course maintenance calendar |
| `scouting_log.py` | `scouting.html` | Field scouting reports with photo upload |
| `soil_testing.py` | `soil.html` | Soil test results, amendment recommendations |
| `spray_tracker.py` | `spray-tracker.html` | Spray application records, REI/PHI tracking |
| `community.py` | `community.html` | Forum posts, comments |
| `cultivar_tool.py` | `cultivars.html` | NTEP trial data, cultivar comparisons |
| `reporting.py` | `reports.html` | PDF report generation (uses ReportLab) |
| `course_map.py` | `course-map.html` | Course zones visualization |
| `unit_converter.py` | `calculator.html` | Turf math — area, volume, application rate conversions |

### Intelligence Engine (`/intelligence/`)
21-module enterprise subsystem for self-improving AI:
| Module | Purpose |
|--------|---------|
| `orchestrator.py` | Coordinates all intelligence modules |
| `analytics.py` | Query analytics and usage patterns |
| `anomaly.py` | Anomaly detection in query patterns |
| `ab_testing.py` | A/B testing for prompt variants |
| `alerts.py` | Webhook/email alerting (Slack, Teams, Discord) |
| `circuit_breaker.py` | Failure circuit breaker for external APIs |
| `confidence_calibration.py` | Calibrates confidence scores against user feedback |
| `conversation.py` | Multi-turn conversation context |
| `escalation.py` | Routes low-confidence queries for human review |
| `knowledge_gaps.py` | Identifies topics with poor coverage |
| `prompt_versioning.py` | Prompt version management |
| `regression.py` | Detects answer quality regressions |
| `satisfaction.py` | User satisfaction tracking |
| `self_healing.py` | Auto-recovery from failure states |
| `source_quality.py` | Tracks reliability of knowledge sources |
| `topic_intelligence.py` | Topic-level performance tracking |
| `training.py` | Fine-tuning data collection |

### Frontend
- **Templates:** `templates/*.html` — 20 Jinja2 templates
- **CSS:** `static/css/*.css` — 19 per-page stylesheets + `shared.css`
- **JS:** `static/js/index.js` (chatbot), `admin.js`, `profile.js`, `resources.js`, `spray-tracker.js`
- Other tool pages use inline `<script>` blocks in their templates

### Data & Knowledge
- `data/` — scraped JSON data, seed data
- `knowledge/` — PDF knowledge base files
- `static/product-labels/`, `static/epa_labels/`, `static/solution-sheets/` — PDF resources indexed in Pinecone
- `*.json` (root) — scraped disease, weed, pest, cultural practice data

## Key Architecture Patterns

### Database Access
Always use the `get_db()` context manager from `db.py`:
```python
from db import get_db

with get_db() as conn:
    conn.execute('INSERT INTO table (col) VALUES (?)', (value,))
    rows = conn.execute('SELECT * FROM table').fetchall()
```
SQL is written in SQLite syntax — `db.py` auto-converts `?` → `%s`, `AUTOINCREMENT` → `SERIAL`, date functions, etc. for PostgreSQL.

### Adding a Column (Migration)
Use `add_column()` from `db.py` — it's idempotent and works on both backends:
```python
from db import add_column
add_column(conn, 'table_name', 'new_col', 'TEXT DEFAULT ""')
```

### Auth Decorators
```python
from auth import login_required, admin_required

@app.route('/protected')
@login_required
def protected_page():
    user_id = session['user_id']  # guaranteed to exist
    ...

@app.route('/admin/something')
@admin_required
def admin_page():
    ...
```
`@login_required` redirects unauthenticated users to `/login`. In DEMO_MODE, it auto-sets `session['user_id'] = 1`.

### SSE Streaming (Chatbot)
The `/ask` endpoint streams tokens via Server-Sent Events. Critical pattern — capture Flask request context *before* the generator:
```python
# BEFORE generator — Flask context is still active
_user_id = session.get('user_id')
_session_id = session.get('session_id')
_client_ip = request.remote_addr

def generate():
    # INSIDE generator — Flask context is GONE
    # Use _user_id, _session_id, _client_ip (pre-captured)
    ...
```

### Search & Scoring Pipeline
1. `expand_query()` → expands vague questions
2. `search_all_parallel()` → Pinecone vector search across folders
3. `score_results()` → hybrid scoring (vector 70% + keyword 30%)
4. `build_context()` → assembles context string from top results (returns tuple: `context, sources, images`)
5. `filter_display_sources()` → filters sources for user display
6. `calculate_confidence_score(sources, answer_text, question)` → confidence percentage

### Feature Route Pattern
All feature API routes live in `feature_routes.py` on the `features_bp` Blueprint. Routes follow REST patterns:
```
GET  /api/feature/items      → list
POST /api/feature/items      → create
PUT  /api/feature/items/<id> → update
DELETE /api/feature/items/<id> → delete
```

## Environment Variables
See `config.py` for the full list. Required:
- `OPENAI_API_KEY` — OpenAI API access
- `PINECONE_API_KEY` — Pinecone vector DB access

Optional but recommended:
- `FLASK_SECRET_KEY` — session encryption (has default, change in prod)
- `DATABASE_URL` — PostgreSQL connection string (omit for SQLite)
- `REDIS_URL` — Redis for sessions/cache (omit for in-memory)
- `TAVILY_API_KEY` — web search fallback
- `OPENWEATHER_API_KEY` — weather data
- `SENTRY_DSN` — error tracking
- `DEMO_MODE=true` — cached responses, zero API cost
- `ALERT_WEBHOOK_URL` — Slack/Teams/Discord alerting

## Testing
```bash
# Run unit tests
pytest tests/

# Run AI accuracy evals
python evals/run_evals.py
```
Test files cover: search service, scoring, confidence, detection, query expansion, hallucination filtering, reranking, tracing, profile, context truncation.

## Common Tasks

### Add a new feature module
1. Create `new_feature.py` with DB init and API functions
2. Add template `templates/new-feature.html` and CSS `static/css/new-feature.css`
3. Register routes in `feature_routes.py` on `features_bp`
4. Add nav link to all templates

### Add a new knowledge source to Pinecone
```bash
# Use the knowledge builder scripts
python scripts/setup_pinecone.py          # initial index setup
python knowledge_builder.py               # index PDFs
python scripts/upload_*.py                # upload scraped data
```

### Modify the system prompt
Edit `prompts.py` — the main system prompt template is there. It gets augmented with profile context from `profile.py`.

## Gotchas
- `build_context()` returns a **tuple** `(context, sources, images)` — always unpack all three
- `filter_display_sources(sources, allowed_folders)` requires **two** arguments
- `calculate_confidence_score(sources, answer_text, question)` — argument order matters
- Some source dicts use `'source'` key instead of `'url'` — always use `.get('url') or .get('source')`
- `irrigation_manager.py` zone fields can be `None` even with `.get(key, default)` when the key exists with a NULL value — use `or` fallback: `zone.get('root_depth') or 6.0`
- `knowledge_builder.py` requires PyPDF2 — import is wrapped in try/except in app.py
- SSE generators run **after** Flask pops request context — pre-capture all session/request values
- The community API returns `{posts: [...]}` not a bare array
