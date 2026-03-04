from flask import Flask, render_template, send_from_directory, jsonify, request, session, redirect
from routes import turf_bp
import os
import json
import logging
import secrets
import time
from datetime import timedelta
import openai
from config import Config
from dotenv import load_dotenv
from pinecone import Pinecone
from logging_config import logger
from auth import login_required
from feedback_system import update_query_rating
from constants import STATIC_FOLDERS
from intelligence_engine import (
    IntelligenceScheduler, process_feedback_intelligence
)
from cache import get_answer_cache
from feature_routes import features_bp, init_all_feature_tables
from blueprints import register_blueprints
from weather_service import get_weather_data, get_weather_warnings, format_weather_for_response

load_dotenv()

# Logging is configured in logging_config.py

app = Flask(__name__)
app.secret_key = Config.FLASK_SECRET_KEY
app.permanent_session_lifetime = timedelta(hours=8)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
if not Config.DEBUG:
    app.config['SESSION_COOKIE_SECURE'] = True

# --- Capacitor / mobile app CORS support ---
@app.after_request
def add_capacitor_cors(response):
    origin = request.headers.get('Origin', '')
    if origin.startswith('capacitor://') or origin.startswith('ionic://'):
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    return response

# --- CSRF Protection ---
@app.before_request
def csrf_protect():
    """Generate CSRF token and validate on state-changing requests."""
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)
    if request.method in ('POST', 'PUT', 'DELETE'):
        # Exempt paths that don't need CSRF (login, signup, health, webhooks)
        exempt = ('/api/login', '/api/signup', '/health', '/api/webhook', '/api/me')
        if request.path in exempt:
            return
        # Also exempt SSE streaming and file uploads (which use FormData)
        if request.path in ('/ask-stream', '/diagnose'):
            return
        token = request.headers.get('X-CSRF-Token') or request.form.get('csrf_token')
        if not token or token != session.get('csrf_token'):
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': {'code': 'CSRF_INVALID', 'message': 'Invalid or missing CSRF token'}}), 403

# --- Security Headers ---
@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    if not Config.DEBUG:
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' cdn.jsdelivr.net cdnjs.cloudflare.com; "
            "style-src 'self' 'unsafe-inline' cdn.jsdelivr.net cdnjs.cloudflare.com; "
            "img-src 'self' data: blob: *.openweathermap.org; "
            "connect-src 'self'; "
            "font-src 'self' cdn.jsdelivr.net cdnjs.cloudflare.com; "
            "frame-ancestors 'none'"
        )
    return response

# --- Server-side sessions via Redis (when available) ---
if Config.REDIS_URL:
    try:
        from flask_session import Session
        app.config['SESSION_TYPE'] = 'redis'
        app.config['SESSION_PERMANENT'] = True
        app.config['SESSION_KEY_PREFIX'] = 'greenside:'
        import redis as _redis_mod
        app.config['SESSION_REDIS'] = _redis_mod.Redis.from_url(Config.REDIS_URL)
        Session(app)
        logger.info("Flask-Session initialized with Redis backend")
    except ImportError:
        logger.warning("flask_session or redis not installed, using default cookie sessions")
else:
    logger.info("No REDIS_URL set, using default cookie sessions")

app.register_blueprint(turf_bp)
app.register_blueprint(features_bp)
register_blueprints(app)

# --- Swagger / OpenAPI documentation ---
try:
    from flasgger import Swagger
    from swagger_config import SWAGGER_CONFIG, SWAGGER_TEMPLATE
    swagger = Swagger(app, config=SWAGGER_CONFIG, template=SWAGGER_TEMPLATE)
    logger.info("Swagger UI available at /api/docs")
except ImportError:
    logger.warning("flasgger not installed, Swagger UI disabled")

# Initialize all feature module database tables
try:
    init_all_feature_tables()
    logger.info("Feature module tables initialized")
except Exception as e:
    logger.warning(f"Feature table init: {e}")

# Initialize audit trail tables
try:
    from audit import init_audit_tables
    init_audit_tables()
except Exception as e:
    logger.warning(f"Audit table init: {e}")

openai_client = openai.OpenAI(api_key=Config.OPENAI_API_KEY)
pc = Pinecone(api_key=Config.PINECONE_API_KEY)
index = pc.Index(Config.PINECONE_INDEX)


# -----------------------------------------------------------------------------
# Error handlers
# -----------------------------------------------------------------------------

def api_error(message, code, status):
    """Return a structured API error response."""
    body = {'error': {'code': code, 'message': message}}
    if status == 429:
        body['error']['retry_after'] = 60
    return jsonify(body), status


@app.errorhandler(404)
def not_found_error(error):
    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return api_error('Not found', 'NOT_FOUND', 404)
    return render_template('login.html'), 404


@app.errorhandler(429)
def rate_limit_error(error):
    return api_error('Too many requests. Please try again later.', 'RATE_LIMITED', 429)


@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return api_error('An internal error occurred. Please try again.', 'INTERNAL_ERROR', 500)
    return render_template('login.html'), 500


# -----------------------------------------------------------------------------
# Home route
# -----------------------------------------------------------------------------

@app.route('/')
def home():
    if not session.get('user_id') and not Config.DEMO_MODE:
        return redirect('/login')
    return render_template('index.html')


# -----------------------------------------------------------------------------
# Static file routes
# -----------------------------------------------------------------------------

@app.route('/epa_labels/<path:filename>')
def serve_epa_label(filename):
    return send_from_directory('static/epa_labels', filename)


@app.route('/product-labels/<path:filename>')
def serve_product_label(filename):
    return send_from_directory('static/product-labels', filename)


@app.route('/solution-sheets/<path:filename>')
def serve_solution_sheet(filename):
    return send_from_directory('static/solution-sheets', filename)


@app.route('/spray-programs/<path:filename>')
def serve_spray_program(filename):
    return send_from_directory('static/spray-programs', filename)


@app.route('/ntep-pdfs/<path:filename>')
def serve_ntep(filename):
    return send_from_directory('static/ntep-pdfs', filename)


@app.route('/disease-photos/<path:filename>')
def serve_disease_photo(filename):
    return send_from_directory('static/disease-photos', filename)

@app.route('/weed-photos/<path:filename>')
def serve_weed_photo(filename):
    return send_from_directory('static/weed-photos', filename)

@app.route('/pest-photos/<path:filename>')
def serve_pest_photo(filename):
    return send_from_directory('static/pest-photos', filename)


@app.route('/resources')
def resources():
    return render_template('resources.html')


@app.route('/api/resources')
def get_resources():
    resources_list = []
    try:
        for folder, category in STATIC_FOLDERS.items():
            folder_path = f'static/{folder}'
            if os.path.exists(folder_path):
                for root, dirs, files in os.walk(folder_path):
                    for filename in files:
                        if filename.lower().endswith('.pdf') and not filename.startswith('.'):
                            full_path = os.path.join(root, filename)
                            relative_path = full_path.replace('static/', '')
                            resources_list.append({
                                'filename': filename,
                                'url': f'/static/{relative_path}',
                                'category': category
                            })
        resources_list.sort(key=lambda x: x['filename'])
    except Exception as e:
        logger.error(f"Error reading PDF folders: {e}")
        return jsonify({'error': str(e)}), 500
    return jsonify(resources_list)


# -----------------------------------------------------------------------------
# TGIF routes
# -----------------------------------------------------------------------------

@app.route('/tgif')
def tgif_search():
    return render_template('tgif_search.html')


@app.route('/tgif/analyze', methods=['POST'])
def tgif_analyze():
    try:
        data = request.json
        question = data.get('question')
        results = data.get('results')

        analysis_prompt = f"""You are analyzing turfgrass research results from the TGIF database.

User's question: {question}

Research results from TGIF:
{results}

Your task:
1. Provide a 2-3 sentence executive summary answering the user's question based on the research
2. Extract the top 5 most relevant findings with titles and brief summaries

Respond in JSON format:
{{
  "summary": "Executive summary here",
  "findings": [
    {{"title": "Study title", "summary": "Key finding"}},
    ...
  ]
}}
"""
        response = openai_client.chat.completions.create(
            model=Config.CHAT_MODEL,
            messages=[
                {"role": "system", "content": "You are a turfgrass research expert analyzing scientific literature."},
                {"role": "user", "content": analysis_prompt}
            ],
            temperature=0.3,
            max_tokens=1500
        )
        analysis = json.loads(response.choices[0].message.content)
        return jsonify(analysis)
    except Exception as e:
        logger.error(f"Error analyzing TGIF results: {e}")
        return jsonify({'error': str(e)}), 500


# -----------------------------------------------------------------------------
# Feedback routes
# -----------------------------------------------------------------------------

@app.route('/feedback', methods=['POST'])
def submit_feedback():
    try:
        data = request.json
        question = data.get('question')
        rating = data.get('rating')
        correction = data.get('correction', '')
        categories = data.get('categories', [])

        # Combine categories with correction text
        if categories:
            category_text = '[' + ', '.join(categories) + ']'
            correction = (category_text + ' ' + (correction or '')).strip()

        # Update the existing query with the user's rating
        update_query_rating(
            question=question,
            rating=rating,
            correction=correction or None
        )

        # Track source quality based on feedback
        try:
            from fine_tuning import track_source_quality
            from db import get_db, FEEDBACK_DB

            with get_db(FEEDBACK_DB) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, sources FROM feedback
                    WHERE question = ?
                    ORDER BY timestamp DESC LIMIT 1
                ''', (question,))
                row = cursor.fetchone()

            if row and row[1]:
                sources = json.loads(row[1])
                track_source_quality(question, sources, rating, row[0])
                logger.debug(f"Tracked source quality for {len(sources)} sources")
        except Exception as sq_error:
            logger.warning(f"Source quality tracking failed: {sq_error}")

        # Intelligence: Update calibration, source reliability, prediction accuracy
        try:
            from db import get_db as _get_db, FEEDBACK_DB as _fb_db
            with _get_db(_fb_db) as _conn:
                _row = _conn.execute(
                    'SELECT id, confidence_score, sources FROM feedback WHERE question = ? ORDER BY timestamp DESC LIMIT 1',
                    (question,)
                ).fetchone()
            if _row:
                _sources = json.loads(_row[2]) if _row[2] else []
                process_feedback_intelligence(
                    query_id=_row[0], question=question, rating=rating,
                    confidence=_row[1] or 50, sources=_sources,
                    correction=correction
                )
        except Exception as _intel_err:
            logger.warning(f"Feedback intelligence failed: {_intel_err}")

        # Bust answer cache on negative feedback so re-asks get fresh answers
        if rating and str(rating) in ('-1', '0', 'bad', 'negative') and question:
            try:
                get_answer_cache().invalidate(question)
                logger.debug(f"Cache invalidated for question after negative feedback")
            except Exception as cache_err:
                logger.warning(f"Cache invalidation failed: {cache_err}")

        # Community knowledge loop — log corrections and knowledge gaps
        try:
            from turf_intelligence import process_community_feedback, log_knowledge_gap
            feedback_result = process_community_feedback(
                question=question, rating=rating,
                correction=correction, sources=_sources if '_sources' in dir() else None
            )
            if feedback_result and feedback_result.get('knowledge_gap'):
                log_knowledge_gap(feedback_result['knowledge_gap'])
        except Exception as comm_err:
            logger.warning(f"Community feedback loop failed: {comm_err}")

        return jsonify({'success': True, 'message': 'Feedback saved'})
    except Exception as e:
        logger.error(f"Error saving feedback: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# -----------------------------------------------------------------------------
# Health check for monitoring
# -----------------------------------------------------------------------------

@app.route('/health')
def health_check():
    """Health check endpoint for production monitoring."""
    start = time.time()

    status = {
        'status': 'healthy',
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime()),
        'services': {}
    }

    # Check Pinecone
    try:
        stats = index.describe_index_stats()
        status['services']['pinecone'] = {
            'status': 'connected',
            'vectors': stats.get('total_vector_count', 0)
        }
    except Exception as e:
        status['services']['pinecone'] = {'status': 'error', 'message': str(e)[:100]}
        status['status'] = 'degraded'

    # Check OpenAI key configured
    try:
        if Config.OPENAI_API_KEY and len(Config.OPENAI_API_KEY) > 10:
            status['services']['openai'] = {'status': 'configured'}
        else:
            status['services']['openai'] = {'status': 'not configured'}
            status['status'] = 'degraded'
    except Exception:
        status['services']['openai'] = {'status': 'error'}
        status['status'] = 'degraded'

    # Check database
    try:
        from db import get_db, is_postgres
        with get_db() as conn:
            conn.execute('SELECT 1')
        status['services']['database'] = {
            'status': 'connected',
            'backend': 'postgresql' if is_postgres() else 'sqlite'
        }
    except Exception as e:
        status['services']['database'] = {'status': 'error', 'message': str(e)[:100]}
        status['status'] = 'degraded'

    # Check Redis (if configured)
    if Config.REDIS_URL:
        try:
            import redis as _redis_check
            r = _redis_check.Redis.from_url(Config.REDIS_URL)
            r.ping()
            status['services']['redis'] = {'status': 'connected'}
        except Exception as e:
            status['services']['redis'] = {'status': 'error', 'message': str(e)[:100]}
            status['status'] = 'degraded'

    status['response_time_ms'] = round((time.time() - start) * 1000, 2)

    http_status = 200 if status['status'] == 'healthy' else 503
    return jsonify(status), http_status


# -----------------------------------------------------------------------------
# Weather routes
# -----------------------------------------------------------------------------

@app.route('/api/weather', methods=['GET', 'POST'])
def get_weather():
    """Get weather data for a location."""
    if request.method == 'POST':
        data = request.json or {}
    else:
        data = request.args

    lat = data.get('lat', type=float) if request.method == 'GET' else data.get('lat')
    lon = data.get('lon', type=float) if request.method == 'GET' else data.get('lon')
    city = data.get('city')
    state = data.get('state')

    if not ((lat and lon) or city):
        return jsonify({'error': 'Provide lat/lon or city'}), 400

    weather_data = get_weather_data(lat=lat, lon=lon, city=city, state=state)
    if not weather_data:
        return jsonify({'error': 'Could not fetch weather data'}), 500

    return jsonify({
        'location': weather_data.get('location'),
        'current': weather_data.get('current'),
        'forecast': weather_data.get('forecast'),
        'warnings': get_weather_warnings(weather_data),
        'summary': format_weather_for_response(weather_data)
    })


if __name__ == '__main__':
    # Start the intelligence engine background scheduler
    try:
        IntelligenceScheduler.start()
        logger.info("Intelligence scheduler started")
    except Exception as e:
        logger.warning(f"Intelligence scheduler failed to start: {e}")

    app.run(debug=Config.DEBUG, port=Config.PORT)
