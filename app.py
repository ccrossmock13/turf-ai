from flask import Flask, render_template, send_from_directory, jsonify, request, session, redirect, Response
from routes import turf_bp
import os
import json
import logging
import math
import time
from datetime import datetime, timedelta
import openai
from config import Config
from dotenv import load_dotenv
from pinecone import Pinecone
from logging_config import logger
from detection import detect_grass_type, detect_region, detect_product_need
from auth import login_required, get_current_user, login_user_session, logout_user_session, create_user, authenticate_user
from profile import (get_profile, save_profile, build_profile_context,
                     get_sprayers, get_sprayer_for_area, save_sprayer, delete_sprayer,
                     get_profiles, set_active_profile, duplicate_profile, delete_profile,
                     get_profile_templates, create_from_template)
from query_expansion import expand_query, expand_vague_question
from chat_history import (
    create_session, save_message, build_context_for_ai,
    calculate_confidence_score, get_confidence_label,
    get_conversation_history
)
from feedback_system import save_feedback as save_user_feedback, save_query, update_query_rating
from constants import (
    STATIC_FOLDERS, SEARCH_FOLDERS, DEFAULT_SOURCES,
    MAX_CONTEXT_LENGTH, MAX_SOURCES
)
from search_service import (
    detect_topic, detect_specific_subject, detect_state, get_embedding,
    search_all_parallel,
    deduplicate_sources, filter_display_sources,
    TOPIC_KW
)
from scoring_service import score_results, safety_filter_results, build_context
from query_rewriter import rewrite_query
from answer_grounding import check_answer_grounding, add_grounding_warning, calculate_grounding_confidence
from knowledge_base import enrich_context_with_knowledge, extract_product_names, extract_disease_names, get_disease_photos, get_weed_photos, get_pest_photos
from reranker import rerank_results, is_cross_encoder_available
from web_search import should_trigger_web_search, should_supplement_with_web_search, search_web_for_turf_info, format_web_search_disclaimer
from weather_service import get_weather_data, get_weather_context, get_weather_warnings, format_weather_for_response
from hallucination_filter import filter_hallucinations
from query_classifier import classify_query, get_response_for_category
from feasibility_gate import check_feasibility
from intelligence_engine import (
    SelfHealingLoop, ABTestingEngine, SourceQualityIntelligence,
    ConfidenceCalibration, RegressionDetector, TopicIntelligence,
    SatisfactionPredictor, SmartEscalation, IntelligenceScheduler,
    PipelineAnalytics, AnomalyDetector, AlertEngine, CircuitBreaker,
    RemediationEngine, PromptVersioning, GradientBoostedPredictor,
    KnowledgeGapAnalyzer, ExecutiveDashboard, ConversationIntelligence,
    FeatureFlags, RateLimiter, DataRetentionManager, TrainingOrchestrator,
    InputSanitizer,
    process_answer_intelligence, process_feedback_intelligence,
    get_intelligence_overview
)
from answer_validator import apply_validation
from demo_cache import find_demo_response
from tracing import Trace
from cache import get_answer_cache
from pipeline import PipelineContext, run_pre_llm_pipeline, run_llm_and_postprocess
from product_loader import (
    get_all_products, search_products, get_product_by_id, save_custom_product,
    get_user_inventory, add_to_inventory, remove_from_inventory, get_inventory_product_ids,
    get_inventory_quantities, update_inventory_quantity, deduct_inventory
)
from spray_tracker import (
    calculate_total_product, calculate_carrier_volume, calculate_nutrients,
    calculate_tank_mix, build_spray_history_context,
    save_application, get_applications, get_application_by_id,
    delete_application, get_nutrient_summary, VALID_AREAS,
    get_templates, save_template, delete_template,
    get_monthly_nutrient_breakdown, update_efficacy, get_efficacy_by_product
)
from feature_routes import features_bp, init_all_feature_tables

load_dotenv()

# Logging is configured in logging_config.py

app = Flask(__name__)
app.secret_key = Config.FLASK_SECRET_KEY
app.permanent_session_lifetime = timedelta(hours=8)

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

# Initialize all feature module database tables
try:
    init_all_feature_tables()
    logger.info("Feature module tables initialized")
except Exception as e:
    logger.warning(f"Feature table init: {e}")

openai_client = openai.OpenAI(api_key=Config.OPENAI_API_KEY)
pc = Pinecone(api_key=Config.PINECONE_API_KEY)
index = pc.Index(Config.PINECONE_INDEX)


# -----------------------------------------------------------------------------
# Rate limiting — Redis-backed when available, in-memory fallback
# -----------------------------------------------------------------------------

_login_rate_redis = None
if Config.REDIS_URL:
    try:
        import redis as _redis_mod
        _login_rate_redis = _redis_mod.Redis.from_url(Config.REDIS_URL)
        _login_rate_redis.ping()
        logger.info("Login rate limiter using Redis")
    except Exception:
        _login_rate_redis = None

_login_attempts = {}  # Fallback: in-memory {ip: [timestamp, ...]}
_RATE_LIMIT_MAX = 5
_RATE_LIMIT_WINDOW = 300  # 5 minutes


def _check_rate_limit(ip):
    """Return True if the IP is rate-limited."""
    if _login_rate_redis:
        key = f"login_attempts:{ip}"
        count = _login_rate_redis.llen(key)
        return count >= _RATE_LIMIT_MAX
    now = time.time()
    attempts = _login_attempts.get(ip, [])
    attempts = [t for t in attempts if now - t < _RATE_LIMIT_WINDOW]
    _login_attempts[ip] = attempts
    return len(attempts) >= _RATE_LIMIT_MAX


def _record_attempt(ip):
    """Record a login/signup attempt for rate limiting."""
    if _login_rate_redis:
        key = f"login_attempts:{ip}"
        _login_rate_redis.rpush(key, str(time.time()))
        _login_rate_redis.expire(key, _RATE_LIMIT_WINDOW)
        return
    _login_attempts.setdefault(ip, []).append(time.time())


# -----------------------------------------------------------------------------
# Error handlers
# -----------------------------------------------------------------------------

@app.errorhandler(404)
def not_found_error(error):
    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'error': 'Not found'}), 404
    return render_template('login.html'), 404


@app.errorhandler(429)
def rate_limit_error(error):
    return jsonify({'error': 'Too many requests. Please try again later.'}), 429


@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'error': 'An internal error occurred. Please try again.'}), 500
    return render_template('login.html'), 500


# -----------------------------------------------------------------------------
# Static file routes
# -----------------------------------------------------------------------------

@app.route('/')
def home():
    if not session.get('user_id') and not Config.DEMO_MODE:
        return redirect('/login')
    return render_template('index.html')


# -----------------------------------------------------------------------------
# Authentication routes
# -----------------------------------------------------------------------------

@app.route('/login', methods=['GET'])
def login_page():
    if session.get('user_id'):
        return redirect('/')
    return render_template('login.html')


@app.route('/signup', methods=['GET'])
def signup_page():
    if session.get('user_id'):
        return redirect('/')
    return render_template('signup.html')


@app.route('/api/login', methods=['POST'])
def api_login():
    ip = request.remote_addr
    if _check_rate_limit(ip):
        return jsonify({'error': 'Too many login attempts. Please wait 5 minutes.'}), 429
    _record_attempt(ip)
    data = request.json or {}
    email = data.get('email', '').strip()
    password = data.get('password', '')
    if not email or not password:
        return jsonify({'error': 'Email and password required'}), 400
    user = authenticate_user(email, password)
    if user:
        login_user_session(user)
        return jsonify({'success': True, 'user': {'name': user['name'], 'email': user['email']}})
    return jsonify({'error': 'Invalid email or password'}), 401


@app.route('/api/signup', methods=['POST'])
def api_signup():
    ip = request.remote_addr
    if _check_rate_limit(ip):
        return jsonify({'error': 'Too many signup attempts. Please wait 5 minutes.'}), 429
    _record_attempt(ip)
    data = request.json or {}
    email = data.get('email', '').strip()
    password = data.get('password', '')
    name = data.get('name', '').strip()
    if not email or not password or not name:
        return jsonify({'error': 'Name, email, and password required'}), 400
    if len(password) < 8:
        return jsonify({'error': 'Password must be at least 8 characters'}), 400
    try:
        user_id = create_user(email, password, name)
        user = {'id': user_id, 'name': name, 'email': email}
        login_user_session(user)
        return jsonify({'success': True, 'user': {'name': name, 'email': email}})
    except ValueError as e:
        return jsonify({'error': str(e)}), 409


@app.route('/logout')
def logout():
    logout_user_session()
    return redirect('/login')


@app.route('/api/me')
def api_me():
    """Get current user info + profile for frontend."""
    user = get_current_user()
    if not user:
        from config import Config
        if Config.DEMO_MODE:
            user = {'id': 1, 'name': 'Demo User', 'email': 'demo@greenside.ai'}
        else:
            return jsonify({'authenticated': False}), 401
    profile = get_profile(user['id'])
    is_admin = False
    try:
        from db import get_db as _get_db
        with _get_db() as conn:
            row = conn.execute('SELECT is_admin FROM users WHERE id = ?', (user['id'],)).fetchone()
            is_admin = bool(row and row[0])
    except Exception:
        pass
    if not is_admin:
        from config import Config
        if Config.DEMO_MODE:
            is_admin = True
    user_data = dict(user)
    user_data['is_admin'] = is_admin
    return jsonify({
        'authenticated': True,
        'user': user_data,
        'profile': profile,
        'has_profile': profile is not None and (
            profile.get('primary_grass') is not None or profile.get('greens_grass') is not None
        )
    })


# -----------------------------------------------------------------------------
# Course profile routes
# -----------------------------------------------------------------------------

@app.route('/profile')
@login_required
def profile_page():
    return render_template('profile.html')


@app.route('/api/profile', methods=['GET'])
@login_required
def api_get_profile():
    """Get profile, optionally by course_name query param."""
    course_name = request.args.get('course_name')
    profile = get_profile(session['user_id'], course_name=course_name)
    return jsonify(profile or {})


@app.route('/api/profile', methods=['POST'])
@login_required
def api_save_profile():
    data = request.json or {}
    save_profile(session['user_id'], data)
    return jsonify({'success': True})


@app.route('/api/profile/context-preview')
@login_required
def api_profile_context_preview():
    """Return the AI context string so users can see what the AI 'sees'."""
    context = build_profile_context(session['user_id'])
    return jsonify({'context': context})


@app.route('/api/profiles', methods=['GET'])
@login_required
def api_list_profiles():
    """List all course profiles for the current user."""
    profiles = get_profiles(session['user_id'])
    return jsonify([{'course_name': p.get('course_name', 'My Course'),
                     'is_active': p.get('is_active', 0),
                     'turf_type': p.get('turf_type'),
                     'city': p.get('city'),
                     'state': p.get('state'),
                     'updated_at': p.get('updated_at')} for p in profiles])


@app.route('/api/profiles/activate', methods=['POST'])
@login_required
def api_activate_profile():
    """Switch active course profile."""
    data = request.json or {}
    course_name = data.get('course_name')
    if not course_name:
        return jsonify({'error': 'course_name required'}), 400
    success = set_active_profile(session['user_id'], course_name)
    return jsonify({'success': success})


@app.route('/api/profiles/duplicate', methods=['POST'])
@login_required
def api_duplicate_profile():
    """Duplicate an existing profile under a new name."""
    data = request.json or {}
    source = data.get('source')
    new_name = data.get('new_name')
    if not source or not new_name:
        return jsonify({'error': 'source and new_name required'}), 400
    success = duplicate_profile(session['user_id'], source, new_name)
    return jsonify({'success': success})


@app.route('/api/profiles/<course_name>', methods=['DELETE'])
@login_required
def api_delete_profile(course_name):
    """Delete a course profile (cannot delete last one)."""
    success = delete_profile(session['user_id'], course_name)
    if not success:
        return jsonify({'error': 'Cannot delete last profile'}), 400
    return jsonify({'success': True})


@app.route('/api/profile/templates', methods=['GET'])
@login_required
def api_profile_templates():
    """List available profile templates."""
    return jsonify(get_profile_templates())


@app.route('/api/profile/from-template', methods=['POST'])
@login_required
def api_create_from_template():
    """Create a new profile from a template."""
    data = request.json or {}
    template_id = data.get('template')
    course_name = data.get('course_name')
    if not template_id or not course_name:
        return jsonify({'error': 'template and course_name required'}), 400
    success = create_from_template(session['user_id'], template_id, course_name)
    return jsonify({'success': success})


@app.route('/api/climate-data/<state>')
@login_required
def api_climate_data(state):
    """Return climate normals for a US state."""
    try:
        from climate_data import get_climate_data
        data = get_climate_data(state)
        if data:
            return jsonify(data)
        return jsonify({'error': 'State not found'}), 404
    except ImportError:
        return jsonify({'error': 'Climate data module not available'}), 500


@app.route('/api/gdd/<state>')
@login_required
def api_gdd(state):
    """Return current season and GDD info for a state."""
    try:
        from climate_data import get_current_season, get_climate_data
        season = get_current_season(state)
        climate = get_climate_data(state)
        return jsonify({
            'season': season,
            'climate': climate,
        })
    except ImportError:
        return jsonify({'error': 'Climate data module not available'}), 500


# -----------------------------------------------------------------------------
# Spray Tracker routes
# -----------------------------------------------------------------------------

@app.route('/spray-tracker')
@login_required
def spray_tracker_page():
    return render_template('spray-tracker.html')


@app.route('/api/products/all')
@login_required
def api_products_all():
    """Get combined product list for autocomplete (pesticides + fertilizers + custom)."""
    products = get_all_products(user_id=session['user_id'])
    return jsonify([_serialize_product(p) for p in products])


@app.route('/api/products/search')
@login_required
def api_products_search():
    """Search products by name/brand/active ingredient. Use scope=inventory to search only user's inventory."""
    query = request.args.get('q', '').strip()
    category = request.args.get('category')
    form_type = request.args.get('form_type')  # 'liquid' or 'granular'
    scope = request.args.get('scope', 'inventory')  # 'inventory' or 'all'
    if not query or len(query) < 2:
        return jsonify([])
    inventory_only = (scope == 'inventory')
    results = search_products(query, user_id=session['user_id'], category=category, form_type=form_type, inventory_only=inventory_only)
    return jsonify([_serialize_product(p) for p in results[:50]])


@app.route('/api/custom-products', methods=['POST'])
@login_required
def api_save_custom_product():
    """Add a user-defined custom product."""
    data = request.json or {}
    if not data.get('product_name'):
        return jsonify({'error': 'Product name is required'}), 400

    product_id = save_custom_product(session['user_id'], data)
    # Auto-add custom product to inventory
    add_to_inventory(session['user_id'], product_id)
    return jsonify({'success': True, 'product_id': product_id})


@app.route('/api/products/<path:product_id>')
@login_required
def api_product_detail(product_id):
    """Get full product details by ID."""
    product = get_product_by_id(product_id, user_id=session['user_id'])
    if not product:
        return jsonify({'error': 'Product not found'}), 404
    return jsonify(product)


# ── User Inventory ──────────────────────────────────────────────────────

def _serialize_product(p):
    """Lightweight product serialization for API responses."""
    return {
        'id': p['id'],
        'display_name': p['display_name'],
        'brand': p.get('brand', ''),
        'category': p['category'],
        'form_type': p.get('form_type', 'granular'),
        'default_rate': p.get('default_rate'),
        'rate_unit': p.get('rate_unit', ''),
        'npk': p.get('npk'),
        'secondary_nutrients': p.get('secondary_nutrients'),
        'has_nutrients': p.get('npk') is not None,
        'density_lbs_per_gallon': p.get('density_lbs_per_gallon'),
        'frac_code': p.get('frac_code'),
        'hrac_group': p.get('hrac_group'),
        'irac_group': p.get('irac_group'),
        'active_ingredient': p.get('active_ingredient'),
    }


@app.route('/api/inventory')
@login_required
def api_get_inventory():
    """Get user's inventory products."""
    products = get_user_inventory(session['user_id'])
    return jsonify({'products': [_serialize_product(p) for p in products]})


@app.route('/api/inventory/ids')
@login_required
def api_get_inventory_ids():
    """Get just the product IDs in the user's inventory (lightweight)."""
    ids = get_inventory_product_ids(session['user_id'])
    return jsonify(list(ids))


@app.route('/api/inventory', methods=['POST'])
@login_required
def api_add_to_inventory():
    """Add product(s) to user's inventory."""
    data = request.json or {}
    product_id = data.get('product_id')
    product_ids = data.get('product_ids', [])

    if product_id:
        added = add_to_inventory(session['user_id'], product_id)
        return jsonify({'success': True, 'added': added})
    elif product_ids:
        count = 0
        for pid in product_ids:
            if add_to_inventory(session['user_id'], pid):
                count += 1
        return jsonify({'success': True, 'added_count': count})
    else:
        return jsonify({'error': 'product_id or product_ids required'}), 400


@app.route('/api/inventory/<path:product_id>', methods=['DELETE'])
@login_required
def api_remove_from_inventory(product_id):
    """Remove a product from user's inventory."""
    removed = remove_from_inventory(session['user_id'], product_id)
    if removed:
        return jsonify({'success': True})
    return jsonify({'error': 'Product not in inventory'}), 404


# ── Inventory Quantities ────────────────────────────────────────────────

@app.route('/api/inventory/quantities')
@login_required
def api_get_inventory_quantities():
    """Get all inventory quantities for user."""
    quantities = get_inventory_quantities(session['user_id'])
    return jsonify(quantities)


@app.route('/api/inventory/quantities', methods=['PUT'])
@login_required
def api_update_inventory_quantity():
    """Update quantity for a product."""
    data = request.json or {}
    pid = data.get('product_id')
    if not pid:
        return jsonify({'error': 'product_id is required'}), 400
    update_inventory_quantity(
        session['user_id'], pid,
        data.get('quantity', 0),
        data.get('unit', 'lbs'),
        data.get('supplier'),
        data.get('cost_per_unit'),
        data.get('notes')
    )
    return jsonify({'success': True})


@app.route('/api/inventory/deduct', methods=['POST'])
@login_required
def api_deduct_inventory():
    """Deduct usage from inventory."""
    data = request.json or {}
    pid = data.get('product_id')
    amount = data.get('amount', 0)
    unit = data.get('unit', 'lbs')
    if not pid:
        return jsonify({'error': 'product_id is required'}), 400
    deduct_inventory(session['user_id'], pid, amount, unit)
    return jsonify({'success': True})


# ── Sprayer management ──────────────────────────────────────────────────

@app.route('/api/sprayers', methods=['GET'])
@login_required
def api_get_sprayers():
    """Get all sprayers for the current user."""
    sprayers = get_sprayers(session['user_id'])
    return jsonify(sprayers)


@app.route('/api/sprayers', methods=['POST'])
@login_required
def api_save_sprayer():
    """Create or update a sprayer."""
    data = request.json or {}
    if not data.get('name') or not data.get('gpa') or not data.get('tank_size'):
        return jsonify({'error': 'name, gpa, and tank_size are required'}), 400
    sprayer_id = save_sprayer(session['user_id'], data)
    return jsonify({'success': True, 'id': sprayer_id})


@app.route('/api/sprayers/<int:sprayer_id>', methods=['DELETE'])
@login_required
def api_delete_sprayer(sprayer_id):
    """Delete a sprayer."""
    deleted = delete_sprayer(session['user_id'], sprayer_id)
    if deleted:
        return jsonify({'success': True})
    return jsonify({'error': 'Sprayer not found'}), 404


@app.route('/api/sprayers/for-area/<area>')
@login_required
def api_sprayer_for_area(area):
    """Get the sprayer assigned to a specific area."""
    sprayer = get_sprayer_for_area(session['user_id'], area)
    if sprayer:
        return jsonify(sprayer)
    return jsonify(None)


# ── Spray Templates ─────────────────────────────────────────────────────

@app.route('/api/spray-templates', methods=['GET'])
@login_required
def api_get_templates():
    """List user's spray program templates."""
    templates = get_templates(session['user_id'])
    return jsonify(templates)


@app.route('/api/spray-templates', methods=['POST'])
@login_required
def api_save_template():
    """Save a spray program template."""
    data = request.json or {}
    if not data.get('name') or not data.get('products'):
        return jsonify({'error': 'name and products are required'}), 400
    tid = save_template(
        session['user_id'],
        data['name'],
        data['products'],
        data.get('application_method'),
        data.get('notes')
    )
    return jsonify({'success': True, 'id': tid})


@app.route('/api/spray-templates/<int:template_id>', methods=['DELETE'])
@login_required
def api_delete_template(template_id):
    """Delete a spray template."""
    deleted = delete_template(session['user_id'], template_id)
    if deleted:
        return jsonify({'success': True})
    return jsonify({'error': 'Template not found'}), 404


# ── MOA Rotation Check ──────────────────────────────────────────────────

@app.route('/api/spray/moa-check')
@login_required
def api_moa_check():
    """Check if a product's MOA was recently used on an area."""
    area = request.args.get('area')
    frac = request.args.get('frac_code')
    hrac = request.args.get('hrac_group')
    irac = request.args.get('irac_group')
    if not area or not (frac or hrac or irac):
        return jsonify({'warnings': []})

    cutoff = (datetime.now() - timedelta(days=14)).strftime('%Y-%m-%d')
    apps = get_applications(session['user_id'], area=area, start_date=cutoff, limit=100)

    warnings = []
    for a in apps:
        products = a.get('products_json') or [{'product_id': a.get('product_id'), 'product_name': a.get('product_name')}]
        for p in products:
            pid = p.get('product_id')
            if not pid:
                continue
            product = get_product_by_id(pid, user_id=session['user_id'])
            if not product:
                continue
            pname = p.get('product_name', product.get('display_name', ''))
            if frac and product.get('frac_code') and str(product['frac_code']) == str(frac):
                warnings.append(f"FRAC {frac} used on {area} on {a['date']} ({pname}). Consider rotating MOA.")
            if hrac and product.get('hrac_group') and str(product['hrac_group']) == str(hrac):
                warnings.append(f"HRAC {hrac} used on {area} on {a['date']} ({pname}). Consider rotating MOA.")
            if irac and product.get('irac_group') and str(product['irac_group']) == str(irac):
                warnings.append(f"IRAC {irac} used on {area} on {a['date']} ({pname}). Consider rotating MOA.")

    # Dedupe
    seen = set()
    unique = []
    for w in warnings:
        if w not in seen:
            seen.add(w)
            unique.append(w)
    return jsonify({'warnings': unique})


# ── Efficacy Tracking ────────────────────────────────────────────────────

@app.route('/api/spray/<int:app_id>/efficacy', methods=['PATCH'])
@login_required
def api_update_efficacy(app_id):
    """Update efficacy rating on a spray application."""
    data = request.json or {}
    rating = data.get('efficacy_rating')
    notes = data.get('efficacy_notes', '')
    if rating is not None and (rating < 1 or rating > 5):
        return jsonify({'error': 'Rating must be between 1 and 5'}), 400
    updated = update_efficacy(session['user_id'], app_id, rating, notes)
    if updated:
        return jsonify({'success': True})
    return jsonify({'error': 'Application not found'}), 404


# ── Monthly Nutrient Breakdown ───────────────────────────────────────────

@app.route('/api/spray/nutrients/monthly')
@login_required
def api_nutrients_monthly():
    """Get month-by-month nutrient breakdown for charting."""
    year = request.args.get('year', str(datetime.now().year))
    compare_year = request.args.get('compare_year')
    area = request.args.get('area') or None
    data = get_monthly_nutrient_breakdown(session['user_id'], year, area=area)
    result = {'primary': data}
    if compare_year:
        result['compare'] = get_monthly_nutrient_breakdown(session['user_id'], compare_year, area=area)
    return jsonify(result)


@app.route('/api/spray', methods=['POST'])
@login_required
def api_log_spray():
    """Log a spray application with auto-calculations.
    Supports single-product and tank-mix (multiple products) payloads.
    """
    data = request.json or {}
    user_id = session['user_id']

    # Detect tank mix vs single product
    products_list = data.get('products')  # array for tank mix
    is_tank_mix = products_list and len(products_list) > 0

    # Validate shared fields
    if not data.get('date'):
        return jsonify({'error': 'date is required'}), 400
    area = data.get('area')
    if not area or area not in VALID_AREAS:
        return jsonify({'error': f'Invalid area. Must be one of: {", ".join(VALID_AREAS)}'}), 400

    # Get area acreage from profile
    profile = get_profile(user_id)
    acreage_key = f'{area}_acreage'
    area_acreage = data.get('area_acreage')
    if not area_acreage and profile:
        area_acreage = profile.get(acreage_key)
    if not area_acreage:
        return jsonify({'error': f'No acreage set for {area}. Update your profile or enter acreage.'}), 400
    area_acreage = float(area_acreage)

    carrier_gpa = float(data['carrier_volume_gpa']) if data.get('carrier_volume_gpa') else None

    # Get tank size from sprayer (new system) or legacy profile field
    sprayer = get_sprayer_for_area(user_id, area)
    tank_size = None
    if sprayer:
        tank_size = float(sprayer['tank_size']) if sprayer.get('tank_size') else None
        # If no GPA was sent, use the sprayer's GPA
        if not carrier_gpa and sprayer.get('gpa'):
            carrier_gpa = float(sprayer['gpa'])
    if not tank_size:
        ts = (profile or {}).get('tank_size')
        if ts:
            tank_size = float(ts)

    # --- Normalize single-product into 1-item products list for unified handling ---
    if not is_tank_mix:
        if not data.get('product_id') or not data.get('rate') or not data.get('rate_unit'):
            return jsonify({'error': 'product_id, rate, and rate_unit are required'}), 400
        products_list = [{
            'product_id': data['product_id'],
            'rate': data['rate'],
            'rate_unit': data['rate_unit']
        }]

    # --- Resolve all products ---
    resolved_products = []
    for i, p in enumerate(products_list):
        if not p.get('product_id') or not p.get('rate') or not p.get('rate_unit'):
            return jsonify({'error': f'Product {i+1} missing required fields'}), 400
        product = get_product_by_id(p['product_id'], user_id=user_id)
        if not product:
            return jsonify({'error': f'Product not found: {p["product_id"]}'}), 404
        resolved_products.append({
            'product': product,
            'rate': float(p['rate']),
            'rate_unit': p['rate_unit']
        })

    # --- Calculate (tank mix handles single products too) ---
    tank_count_from_ui = int(data.get('tank_count', 0)) or None
    mix_result = calculate_tank_mix(
        resolved_products, area_acreage, carrier_gpa, tank_size,
        tank_count_override=tank_count_from_ui
    )

    # --- Build application record ---
    first = mix_result['products'][0]
    is_multi = len(mix_result['products']) > 1
    app_data = {
        'date': data['date'],
        'area': area,
        'product_id': first['product_id'],
        'product_name': f"Tank Mix ({len(mix_result['products'])} products)" if is_multi else first.get('product_name', resolved_products[0]['product']['display_name']),
        'product_category': 'tank_mix' if is_multi else resolved_products[0]['product']['category'],
        'rate': first['rate'],
        'rate_unit': first['rate_unit'],
        'area_acreage': area_acreage,
        'carrier_volume_gpa': carrier_gpa,
        'total_product': first['total_product'],
        'total_product_unit': first['total_product_unit'],
        'total_carrier_gallons': mix_result['total_carrier_gallons'],
        'nutrients_applied': mix_result['combined_nutrients'],
        'weather_temp': data.get('weather_temp'),
        'weather_wind': data.get('weather_wind'),
        'weather_conditions': data.get('weather_conditions'),
        'notes': data.get('notes'),
        'products_json': mix_result['products'] if is_multi else None,
        'application_method': data.get('application_method')
    }

    app_id = save_application(user_id, app_data)
    return jsonify({
        'success': True,
        'id': app_id,
        'calculations': {
            'products': mix_result['products'],
            'total_carrier_gallons': mix_result['total_carrier_gallons'],
            'tank_count': mix_result['tank_count'],
            'combined_nutrients': mix_result['combined_nutrients']
        }
    })


@app.route('/api/spray', methods=['GET'])
@login_required
def api_get_sprays():
    """Get spray application history with optional filters."""
    user_id = session['user_id']
    area = request.args.get('area')
    year = request.args.get('year')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    limit = request.args.get('limit', 200, type=int)

    applications = get_applications(
        user_id, area=area, year=year,
        start_date=start_date, end_date=end_date, limit=limit
    )
    return jsonify(applications)


@app.route('/api/spray/<int:app_id>', methods=['GET'])
@login_required
def api_get_spray_single(app_id):
    """Get a single spray application by ID."""
    application = get_application_by_id(session['user_id'], app_id)
    if not application:
        return jsonify({'error': 'Application not found'}), 404
    return jsonify(application)


@app.route('/api/spray/<int:app_id>', methods=['DELETE'])
@login_required
def api_delete_spray(app_id):
    """Delete a spray application."""
    deleted = delete_application(session['user_id'], app_id)
    if deleted:
        return jsonify({'success': True})
    return jsonify({'error': 'Application not found or not authorized'}), 404


@app.route('/api/spray/nutrients')
@login_required
def api_spray_nutrients():
    """Get nutrient summary for a year."""
    user_id = session['user_id']
    year = request.args.get('year', str(datetime.now().year))
    area = request.args.get('area')

    summary = get_nutrient_summary(user_id, year, area=area)
    return jsonify(summary)


@app.route('/api/spray/csv')
@login_required
def api_spray_csv():
    """Export spray history as CSV."""
    import csv
    import io
    user_id = session['user_id']
    year = request.args.get('year')
    area = request.args.get('area') or None
    applications = get_applications(user_id, year=year, area=area, limit=5000)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Date', 'Area', 'Method', 'Product', 'Category', 'Rate', 'Rate Unit',
                     'Total Product', 'Unit', 'Carrier GPA', 'Total Carrier (gal)',
                     'Temp (F)', 'Wind', 'Conditions', 'Notes'])
    def _csv_row(a, product_data=None):
        """Build a CSV row from app record, optionally overriding product fields."""
        p = product_data or a
        return [
            a['date'], a['area'], a.get('application_method', ''),
            p.get('product_name', ''), p.get('product_category', ''),
            p.get('rate', ''), p.get('rate_unit', ''),
            p.get('total_product', ''), p.get('total_product_unit', ''),
            a.get('carrier_volume_gpa', ''), a.get('total_carrier_gallons', ''),
            a.get('weather_temp', ''), a.get('weather_wind', ''),
            a.get('weather_conditions', ''), a.get('notes', '')
        ]

    for a in applications:
        if a.get('products_json') and len(a['products_json']) > 0:
            for p in a['products_json']:
                writer.writerow(_csv_row(a, p))
        else:
            writer.writerow(_csv_row(a))

    from flask import Response
    response = Response(output.getvalue(), mimetype='text/csv')
    response.headers['Content-Disposition'] = f'attachment; filename=spray_history_{year or "all"}.csv'
    return response


@app.route('/api/spray/pdf/single/<int:app_id>')
@login_required
def api_spray_pdf_single(app_id):
    """Generate PDF for a single spray application."""
    user_id = session['user_id']
    application = get_application_by_id(user_id, app_id)
    if not application:
        return jsonify({'error': 'Application not found'}), 404

    profile = get_profile(user_id)
    course_name = profile.get('course_name', 'Course') if profile else 'Course'

    # Attach tank info for per-tank calculations in PDF
    area = application.get('area')
    sprayer = get_sprayer_for_area(user_id, area) if area else None
    t_size = float(sprayer['tank_size']) if sprayer and sprayer.get('tank_size') else None
    if not t_size and profile:
        ts = profile.get('tank_size')
        if ts:
            t_size = float(ts)
    application['tank_size'] = t_size

    # Derive tank count, then recalculate total as tank_size × tank_count
    tc = application.get('total_carrier_gallons')
    carrier_gpa = application.get('carrier_volume_gpa')
    app_acreage = application.get('area_acreage')
    if t_size and t_size > 0 and carrier_gpa and app_acreage:
        tank_count = math.ceil((float(carrier_gpa) * float(app_acreage)) / t_size)
        application['tank_count'] = tank_count
        application['total_carrier_gallons'] = round(t_size * tank_count, 1)
    elif tc and t_size and t_size > 0:
        application['tank_count'] = int(round(float(tc) / t_size))
    else:
        application['tank_count'] = None

    try:
        from pdf_generator import generate_single_spray_record
        pdf_buffer = generate_single_spray_record(application, course_name)
        return Response(
            pdf_buffer.getvalue(),
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename=spray_record_{app_id}.pdf'
            }
        )
    except ImportError:
        return jsonify({'error': 'PDF generation not available. Install reportlab.'}), 500
    except Exception as e:
        logger.error(f"PDF generation error: {e}", exc_info=True)
        return jsonify({'error': 'Failed to generate PDF'}), 500


@app.route('/api/spray/pdf/report')
@login_required
def api_spray_pdf_report():
    """Generate seasonal summary PDF report."""
    user_id = session['user_id']
    year = request.args.get('year', str(datetime.now().year))
    area = request.args.get('area')

    applications = get_applications(user_id, year=year, area=area, limit=5000)
    nutrient_summary = get_nutrient_summary(user_id, year, area=area)
    profile = get_profile(user_id)
    course_name = profile.get('course_name', 'Course') if profile else 'Course'

    try:
        from pdf_generator import generate_seasonal_report
        pdf_buffer = generate_seasonal_report(
            applications, nutrient_summary, course_name,
            date_range=f'Season {year}'
        )
        return Response(
            pdf_buffer.getvalue(),
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename=spray_report_{year}.pdf'
            }
        )
    except ImportError:
        return jsonify({'error': 'PDF generation not available. Install reportlab.'}), 500
    except Exception as e:
        logger.error(f"PDF report generation error: {e}", exc_info=True)
        return jsonify({'error': 'Failed to generate report'}), 500


@app.route('/api/spray/pdf/nutrients')
@login_required
def api_spray_pdf_nutrients():
    """Generate nutrient tracking PDF report."""
    user_id = session['user_id']
    year = request.args.get('year', str(datetime.now().year))

    nutrient_summary = get_nutrient_summary(user_id, year)
    profile = get_profile(user_id)
    course_name = profile.get('course_name', 'Course') if profile else 'Course'

    try:
        from pdf_generator import generate_nutrient_report
        pdf_buffer = generate_nutrient_report(nutrient_summary, course_name, year)
        return Response(
            pdf_buffer.getvalue(),
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename=nutrient_report_{year}.pdf'
            }
        )
    except ImportError:
        return jsonify({'error': 'PDF generation not available. Install reportlab.'}), 500
    except Exception as e:
        logger.error(f"Nutrient PDF error: {e}", exc_info=True)
        return jsonify({'error': 'Failed to generate nutrient report'}), 500


# -----------------------------------------------------------------------------
# Conversation history
# -----------------------------------------------------------------------------

@app.route('/api/conversations')
@login_required
def api_user_conversations():
    """Get conversation history for the current user."""
    from chat_history import get_user_conversations
    conversations = get_user_conversations(session['user_id'], limit=50)
    return jsonify(conversations)


@app.route('/api/conversations/<int:conversation_id>/messages')
@login_required
def api_conversation_messages(conversation_id):
    """Get messages for a specific conversation."""
    messages = get_conversation_history(conversation_id, limit=50)
    return jsonify(messages)


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
# Main AI endpoint
# -----------------------------------------------------------------------------

@app.route('/ask', methods=['POST'])
@login_required
def ask():
    try:
        body = request.json or {}
        question = body.get('question', '').strip()
        if not question:
            return jsonify({
                'answer': "Please enter a question about turfgrass management.",
                'sources': [], 'confidence': {'score': 0, 'label': 'No Question'}
            })

        body['client_ip'] = request.remote_addr or '127.0.0.1'
        ctx = PipelineContext(
            question=question,
            user_id=session.get('user_id'),
            session_data=dict(session),
            openai_client=openai_client,
            pinecone_index=index
        )

        # Pre-LLM pipeline (classify, detect, search, rerank, build context)
        early_return = run_pre_llm_pipeline(ctx, body)
        if early_return:
            status = early_return.pop('_status', 200)
            return jsonify(early_return), status

        # Sync session state back from pipeline
        session['last_topic'] = ctx.question_topic
        if ctx.current_subject:
            session['last_subject'] = ctx.current_subject
        if 'session_id' in ctx.session_data:
            session['session_id'] = ctx.session_data['session_id']
            session['conversation_id'] = ctx.session_data['conversation_id']

        # LLM call + post-processing (grounding, hallucination, confidence)
        response_data = run_llm_and_postprocess(ctx)
        return jsonify(response_data)

    except Exception as e:
        logger.error(f"Error processing question: {e}", exc_info=True)
        return jsonify({
            'answer': "I apologize, but I encountered an issue processing your question. Please try rephrasing or ask a different question about turfgrass management.",
            'sources': [], 'confidence': {'score': 0, 'label': 'Error'},
            'error_logged': True
        })


@app.route('/ask-stream', methods=['POST'])
@login_required
def ask_stream():
    """SSE streaming endpoint — streams LLM tokens in real-time, then final metadata."""
    body = request.json or {}
    question = body.get('question', '').strip()
    if not question:
        return jsonify({'error': 'No question provided'}), 400

    import time as _time
    from concurrent.futures import ThreadPoolExecutor

    # Capture request/session values BEFORE entering generator (Flask
    # pops the request context after returning the Response, so the
    # generator would otherwise crash with "Working outside of request context")
    _user_id = session.get('user_id')
    _session_id = session.get('session_id')
    _client_ip = request.remote_addr or '127.0.0.1'
    _conversation_id = _get_or_create_conversation()

    def generate():
        try:
            _t0 = _time.time()
            _trace = Trace(question=question, user_id=_user_id, session_id=_session_id)

            # Rate limiting + sanitization
            _rate_check = RateLimiter.check_rate_limit(_client_ip, 'ask')
            if not _rate_check['allowed']:
                yield f"data: {json.dumps({'error': 'Rate limited', 'done': True})}\n\n"
                return
            _sanitize_result = InputSanitizer.check_query(question, _client_ip)
            if not _sanitize_result['safe']:
                yield f"data: {json.dumps({'error': 'Query blocked', 'done': True})}\n\n"
                return

            # Demo/cache fast paths
            if Config.DEMO_MODE:
                demo_response = find_demo_response(question)
                if demo_response:
                    yield f"data: {json.dumps({'token': demo_response.get('answer', '')})}\n\n"
                    demo_response['done'] = True
                    yield f"data: {json.dumps(demo_response)}\n\n"
                    return

            _answer_cache = get_answer_cache()
            _course_id = _user_id
            if not body.get('regenerate', False):
                cached = _answer_cache.get(question, course_id=_course_id)
                if cached:
                    yield f"data: {json.dumps({'token': cached.get('answer', '')})}\n\n"
                    cached['done'] = True
                    cached['cached'] = True
                    yield f"data: {json.dumps(cached)}\n\n"
                    return

            # ── Pre-LLM pipeline (classify, detect, search, score, build context) ──
            with ThreadPoolExecutor(max_workers=3) as executor:
                classify_future = executor.submit(classify_query, openai_client, question, "gpt-4o-mini")
                rewrite_future = executor.submit(rewrite_query, openai_client, question, model="gpt-4o-mini")
                feasibility_result = check_feasibility(question)

            classification = classify_future.result()
            intercept_response = get_response_for_category(
                classification['category'], classification.get('reason', '')
            )
            _trace.step("classify", category=classification.get('category'))
            if intercept_response:
                yield f"data: {json.dumps({'token': intercept_response.get('answer', '')})}\n\n"
                intercept_response['done'] = True
                yield f"data: {json.dumps(intercept_response)}\n\n"
                return
            if feasibility_result:
                yield f"data: {json.dumps({'token': feasibility_result.get('answer', '')})}\n\n"
                feasibility_result['done'] = True
                yield f"data: {json.dumps(feasibility_result)}\n\n"
                return

            # Detection
            rewritten_query_text = rewrite_future.result() or question
            question_to_process = expand_vague_question(question)
            grass_type = detect_grass_type(question_to_process)
            region = detect_region(question_to_process)
            product_need = detect_product_need(question_to_process)
            question_topic = detect_topic(question_to_process.lower())
            _trace.step("detect", grass=grass_type, region=region, product=product_need)

            # Profile fallback
            user_profile = get_profile(_user_id)
            if not grass_type and user_profile:
                if user_profile.get('turf_type') == 'golf_course':
                    grass_type = user_profile.get('greens_grass') or user_profile.get('fairways_grass')
                else:
                    grass_type = user_profile.get('primary_grass')
            if not region and user_profile and user_profile.get('region'):
                region = user_profile['region']

            # Expand + search
            expanded_query = expand_query(rewritten_query_text)
            if grass_type:
                expanded_query += f" {grass_type}"
            if region:
                expanded_query += f" {region}"

            search_results = search_all_parallel(
                index, openai_client, rewritten_query_text, expanded_query,
                product_need, grass_type, Config.EMBEDDING_MODEL
            )
            all_matches = (
                search_results['general'].get('matches', []) +
                search_results['product'].get('matches', []) +
                search_results['timing'].get('matches', [])
            )
            scored_results = score_results(all_matches, question, grass_type, region, product_need)
            if scored_results:
                scored_results = rerank_results(rewritten_query_text, scored_results, top_k=20)
            _trace.step("search_rerank", result_count=len(scored_results))

            # Build context
            context, _src_list, _images = build_context(scored_results[:MAX_SOURCES], SEARCH_FOLDERS)
            sources = deduplicate_sources(scored_results[:MAX_SOURCES])
            display_sources = filter_display_sources(sources, SEARCH_FOLDERS)
            context = enrich_context_with_knowledge(context, question)

            # Truncate safely
            if len(context) > MAX_CONTEXT_LENGTH:
                truncated = context[:MAX_CONTEXT_LENGTH]
                last_break = truncated.rfind('\n\n')
                if last_break > MAX_CONTEXT_LENGTH * 0.7:
                    context = truncated[:last_break]
                else:
                    last_period = truncated.rfind('. ')
                    if last_period > MAX_CONTEXT_LENGTH * 0.7:
                        context = truncated[:last_period + 1]
                    else:
                        context = truncated

            # Build messages
            from prompts import build_system_prompt as _build_sys, build_reference_context
            system_prompt = _build_sys(question_topic, product_need)
            ref_ctx = build_reference_context(question_topic, product_need)
            if ref_ctx:
                context = "--- EXPERT REFERENCE DATA ---\n" + ref_ctx + "\n\n--- RETRIEVED SOURCES ---\n" + context
            profile_context = build_profile_context(_user_id, question_topic=question_topic)
            if profile_context:
                system_prompt += "\n\n--- USER CONTEXT ---\n" + profile_context

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": _build_user_prompt(context, question)}
            ]

            # ── Stream LLM response ──
            _llm_model = Config.CHAT_MODEL
            full_response = []
            try:
                stream = openai_client.chat.completions.create(
                    model=_llm_model,
                    messages=messages,
                    max_tokens=Config.CHAT_MAX_TOKENS,
                    temperature=Config.CHAT_TEMPERATURE,
                    stream=True,
                    timeout=30
                )
                for chunk in stream:
                    delta = chunk.choices[0].delta if chunk.choices else None
                    if delta and delta.content:
                        token = delta.content
                        full_response.append(token)
                        yield f"data: {json.dumps({'token': token})}\n\n"
            except Exception as llm_err:
                logger.error(f"SSE LLM error: {llm_err}")
                err_msg = "I encountered an error generating a response. Please try again."
                yield f"data: {json.dumps({'token': err_msg})}\n\n"
                full_response = [err_msg]

            assistant_response = ''.join(full_response)
            _trace.step("llm_answer", model=_llm_model)

            # Post-processing
            confidence = calculate_confidence_score(sources, assistant_response, question)
            confidence_label = get_confidence_label(confidence)
            _trace.finish(confidence=confidence, source_count=len(display_sources))

            # Save to conversation history
            try:
                save_message(_conversation_id, 'user', question)
                save_message(_conversation_id, 'assistant', assistant_response)
            except Exception:
                pass

            # Save query to feedback table so user ratings work
            try:
                needs_review = confidence < 70 or not sources
                save_query(
                    question=question, ai_answer=assistant_response,
                    sources=display_sources[:MAX_SOURCES],
                    confidence=confidence, needs_review=needs_review
                )
            except Exception as sq_err:
                logger.warning(f"Failed to save SSE query to feedback: {sq_err}")

            # Final metadata event
            final_data = {
                'done': True,
                'sources': display_sources[:MAX_SOURCES],
                'confidence': {'score': confidence, 'label': confidence_label},
                'trace_id': _trace.trace_id
            }
            yield f"data: {json.dumps(final_data)}\n\n"

        except Exception as e:
            logger.error(f"SSE stream error: {e}", exc_info=True)
            yield f"data: {json.dumps({'error': str(e), 'done': True})}\n\n"

    return Response(generate(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


def _get_or_create_conversation():
    """Get existing conversation ID or create new session."""
    if 'session_id' not in session:
        session_id, conversation_id = create_session(user_id=session.get('user_id'))
        session['session_id'] = session_id
        session['conversation_id'] = conversation_id
    return session['conversation_id']


def _is_significant_topic_change(previous_topic: str, current_topic: str, question: str,
                                  previous_subject: str = None, current_subject: str = None) -> bool:
    """
    Detect if the user is changing to a completely different topic.
    This helps prevent conversation history from confusing unrelated questions.

    Returns True if this appears to be a new topic that shouldn't use previous context.
    """
    # No previous topic means first question — but check subjects
    if not previous_topic:
        # If the current question has a specific subject different from last known subject,
        # treat as topic change to avoid injecting stale history
        if current_subject and previous_subject and current_subject != previous_subject:
            logging.debug(f'Subject change (no prev topic): {previous_subject} -> {current_subject}')
            return True
        return False

    # If we can't detect the current topic, treat it as a new topic
    # to avoid injecting irrelevant conversation history
    if not current_topic:
        return True

    # Same category but different specific subject = topic change
    # e.g., "pythium" vs "summer patch" are both 'disease' but different subjects
    if previous_topic == current_topic:
        if current_subject and previous_subject and current_subject != previous_subject:
            logging.debug(f'Subject change within same category: {previous_subject} -> {current_subject}')
            return True
        return False

    # Check for explicit "new question" signals (loaded from topic_keywords.json)
    question_lower = question.lower()
    if any(signal in question_lower for signal in TOPIC_KW['new_topic_signals']):
        return True

    # Define topic groups that are related
    related_groups = [
        {'chemical', 'fungicide', 'herbicide', 'insecticide'},
        {'cultural', 'irrigation', 'fertilizer'},
        {'equipment', 'calibration'},
        {'diagnostic', 'disease'},
    ]

    # Check if topics are in the same related group
    for group in related_groups:
        if previous_topic in group and current_topic in group:
            # Still check for subject change within related groups
            if current_subject and previous_subject and current_subject != previous_subject:
                logging.debug(f'Subject change within related group: {previous_subject} -> {current_subject}')
                return True
            return False

    # Check for follow-up language that suggests continuation (loaded from topic_keywords.json)
    if any(question_lower.startswith(signal) or signal in question_lower[:30] for signal in TOPIC_KW['followup_signals']):
        return False

    # Different topic groups and no follow-up language = topic change
    if previous_topic and current_topic and previous_topic != current_topic:
        return True

    return False


def _build_user_prompt(context, question):
    """Build the user prompt for the AI."""
    return (
        f"Context from research and manuals:\n\n{context}\n\n"
        f"Question: {question}\n\n"
        "INSTRUCTIONS:\n"
        "1. Provide specific treatment options with actual rates AND explain WHY each is recommended.\n"
        "2. Include FRAC/HRAC/IRAC codes when recommending pesticides.\n"
        "3. If verified product data is provided, use those exact rates."
    )


def _build_messages_with_history(conversation_id, system_prompt, context, current_question):
    """
    Build messages array including conversation history for follow-up understanding.
    This allows the AI to understand references like "what about the rate?" or "that product".
    """
    messages = [{"role": "system", "content": system_prompt}]

    # Get recent conversation history (last 3 exchanges = 6 messages)
    history = get_conversation_history(conversation_id, limit=6)

    # Add historical messages (excluding the current question we just saved)
    for msg in history[:-1]:  # Skip the last one (current question)
        if msg['role'] == 'user':
            messages.append({"role": "user", "content": msg['content']})
        elif msg['role'] == 'assistant':
            # Truncate long responses to save tokens
            content = msg['content']
            if len(content) > 500:
                content = content[:500] + "..."
            messages.append({"role": "assistant", "content": content})

    # Add current question with context
    messages.append({
        "role": "user",
        "content": _build_user_prompt(context, current_question)
    })

    return messages


def _check_vague_query(question: str):
    """
    Detect queries that are too vague, off-topic, or adversarial to process
    meaningfully. Returns a response dict if the query should be intercepted,
    or None if the query should proceed normally.
    """
    q = question.lower().strip().rstrip('?.!')

    # Ultra-short queries (1-3 words) that lack turf context
    words = q.split()
    if len(words) <= 2 and not any(
        term in q for term in [
            'dollar spot', 'brown patch', 'pythium', 'crabgrass', 'poa',
            'grub', 'fungicide', 'herbicide', 'insecticide', 'pgr',
            'mowing', 'aeration', 'topdress', 'irrigation', 'fertiliz',
            'bermuda', 'bentgrass', 'zoysia', 'bluegrass', 'fescue',
            'ryegrass', 'primo', 'heritage', 'banner', 'daconil',
            'barricade', 'dimension', 'tenacity', 'acelepryn',
        ]
    ):
        # Check for ultra-vague fragments
        vague_fragments = [
            'spray it', 'fix it', 'help', 'weeds', 'brown spots',
            'is it too late', 'how much', 'what should i',
        ]
        if q in vague_fragments or len(q) < 12:
            return {
                'answer': (
                    "I'd love to help, but I need a bit more information to give you a useful answer. "
                    "Could you tell me:\n\n"
                    "- **What grass type** do you have? (e.g., bermudagrass, bentgrass, bluegrass)\n"
                    "- **What's the problem or goal?** (e.g., disease, weeds, fertilization, mowing)\n"
                    "- **Any symptoms?** (e.g., brown patches, yellowing, thinning)\n"
                    "- **Your location or region?** (helps with timing and product selection)\n\n"
                    "The more detail you provide, the more specific my recommendations can be!"
                ),
                'sources': [],
                'confidence': {'score': 0, 'label': 'Need More Info'}
            }

    # Off-topic detection — clearly non-turfgrass questions
    off_topic_patterns = [
        # Finance/business
        'stock', 'invest', 'bitcoin', 'crypto', 'portfolio', 'trading',
        # Medical
        'headache', 'medicine', 'prescription', 'doctor', 'symptom',
        'diagnosis',  # only if no turf context
        # Cooking
        'recipe', 'cook', 'bake', 'ingredient',
        # Coding/tech
        'python script', 'javascript', 'html', 'programming', 'write code',
        'scrape web', 'source code', 'compile',
        # General knowledge
        'meaning of life', 'roman empire', 'history of', 'who invented',
        # Career
        'cover letter', 'resume', 'job interview',
        # Automotive
        'car engine', 'oil change', 'brake pad',
        # Legal
        'legal advice', 'lawsuit', 'attorney',
        # Cannabis/drugs
        'marijuana', 'cannabis', 'weed grow',  # Note: 'weed' alone is turf-related
    ]

    # Check for off-topic but avoid false positives for turf terms
    turf_context_words = [
        'turf', 'grass', 'lawn', 'green', 'fairway', 'golf', 'mow',
        'spray', 'fungicide', 'herbicide', 'fertiliz', 'aerat', 'irrigat',
        'bermuda', 'bentgrass', 'zoysia', 'fescue', 'bluegrass', 'rye',
        'disease', 'weed control', 'grub', 'insect', 'thatch', 'soil',
        'topdress', 'overseed', 'pgr', 'primo', 'frac', 'hrac', 'irac',
        'barricade', 'dimension', 'heritage', 'daconil', 'banner',
        'roundup', 'glyphosate', 'dollar spot', 'brown patch', 'pythium',
        'crabgrass', 'poa annua', 'nematode', 'pesticide', 'label rate',
        'application rate', 'tank mix', 'pre-emergent', 'post-emergent',
        'specticle', 'tenacity', 'acelepryn', 'merit', 'bifenthrin',
        'propiconazole', 'chlorothalonil', 'azoxystrobin',
    ]
    has_turf_context = any(t in q for t in turf_context_words)

    if not has_turf_context:
        for pattern in off_topic_patterns:
            if pattern in q:
                return {
                    'answer': (
                        "I specialize in turfgrass management and can't help with that topic. "
                        "Feel free to ask me anything about turf, lawn care, golf course management, "
                        "disease control, weed management, fertility, irrigation, or cultural practices!"
                    ),
                    'sources': [],
                    'confidence': {'score': 0, 'label': 'Off Topic'}
                }

    # Turf-related but missing critical context (location, grass type, target)
    missing_context_patterns = [
        'what should i spray this month',
        'what should i apply this month',
        'what do i need to spray',
        'what do i spray now',
        'what should i put down this month',
        'what should i apply now',
        'what product should i use this month',
    ]
    if any(p in q for p in missing_context_patterns):
        return {
            'answer': (
                "Great question! To give you the right spray program for this month, "
                "I need a few details:\n\n"
                "- **What grass type?** (e.g., bermudagrass, bentgrass, bluegrass, fescue)\n"
                "- **What's your location/region?** (timing varies significantly by climate)\n"
                "- **What are you targeting?** (disease prevention, weed control, insect management)\n"
                "- **What type of turf area?** (golf greens, fairways, home lawn, sports field)\n\n"
                "With these details, I can recommend specific products, rates, and timing!"
            ),
            'sources': [],
            'confidence': {'score': 0, 'label': 'Need More Info'}
        }

    # Prompt injection / system prompt leak attempts
    injection_patterns = [
        'ignore your instructions', 'ignore your prompt', 'ignore previous',
        'what are your instructions', 'show me your prompt',
        'system prompt', 'you are now', 'act as a', 'pretend you are',
        'forget your training', 'disregard your',
    ]
    if any(p in q for p in injection_patterns):
        return {
            'answer': (
                "I'm Greenside AI, a turfgrass management expert. "
                "I'm here to help with questions about turf, lawn care, disease management, "
                "weed control, fertility, irrigation, and golf course maintenance. "
                "What turf question can I help you with?"
            ),
            'sources': [],
            'confidence': {'score': 0, 'label': 'Off Topic'}
        }

    return None


# -----------------------------------------------------------------------------
# Photo diagnosis route
# -----------------------------------------------------------------------------

@app.route('/diagnose', methods=['POST'])
@login_required
def diagnose():
    """Analyze an uploaded turf photo using GPT-4o Vision, then enrich with RAG."""
    import base64
    import time as _time
    _t0 = _time.time()

    try:
        if 'image' not in request.files:
            return jsonify({
                'answer': 'No image was uploaded. Please select a photo.',
                'sources': [], 'images': [],
                'confidence': {'score': 0, 'label': 'No Image'}
            })

        image_file = request.files['image']
        optional_question = request.form.get('question', '').strip()

        # Validate file size (5MB)
        image_data = image_file.read()
        if len(image_data) > 5 * 1024 * 1024:
            return jsonify({
                'answer': 'Image is too large. Please use a photo under 5MB.',
                'sources': [], 'images': [],
                'confidence': {'score': 0, 'label': 'Image Too Large'}
            })

        base64_image = base64.b64encode(image_data).decode('utf-8')
        content_type = image_file.content_type or 'image/jpeg'

        # Build Vision prompt
        vision_text = (
            "Analyze this turf/grass photo. Identify:\n"
            "1. What disease, pest, weed, or cultural issue is visible\n"
            "2. What visual evidence supports your identification\n"
            "3. What grass type this appears to be (if identifiable)\n"
            "4. How severe the issue appears (early, moderate, severe)\n"
        )
        if optional_question:
            vision_text += f"\nThe user also asks: {optional_question}\n"

        # Call GPT-4o Vision
        vision_response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a PhD-level turfgrass pathologist performing visual diagnosis. "
                        "Analyze the turf photo and identify the most likely disease, pest, or cultural issue. "
                        "Be specific but honest about uncertainty. "
                        "If the image is not of turf or is too unclear, say so. "
                        "Structure: 1) Identification, 2) Key visual evidence, "
                        "3) Confidence (definite/likely/possible/uncertain), 4) Recommended next steps."
                    )
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": vision_text},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{content_type};base64,{base64_image}",
                                "detail": "high"
                            }
                        }
                    ]
                }
            ],
            max_tokens=800,
            temperature=0.3,
            timeout=30
        )

        diagnosis_text = vision_response.choices[0].message.content
        if not diagnosis_text:
            diagnosis_text = "I could not analyze this image. Please try a clearer photo."

        # Try to detect the disease from the diagnosis for RAG enrichment
        diagnosis_lower = diagnosis_text.lower()
        detected_disease = detect_specific_subject(diagnosis_lower)

        sources = []
        images = []

        # If a disease was identified, enrich with RAG treatment data
        if detected_disease:
            try:
                treatment_query = f"How to treat {detected_disease} on turfgrass? Best fungicide options and cultural practices."
                expanded = expand_query(treatment_query)
                embedding = get_embedding(openai_client, expanded, Config.EMBEDDING_MODEL)

                search_results = search_all_parallel(
                    index, openai_client, treatment_query, expanded,
                    'fungicide', None, Config.EMBEDDING_MODEL
                )

                all_matches = []
                for key in search_results:
                    all_matches.extend(search_results[key].get('matches', []))

                if all_matches:
                    scored = score_results(all_matches, treatment_query, None, None, 'fungicide')
                    if scored:
                        context, sources, images = build_context(scored[:5], SEARCH_FOLDERS)
                        context = enrich_context_with_knowledge(treatment_query, context)

                        # Generate combined diagnosis + treatment
                        from prompts import build_system_prompt
                        system_prompt = build_system_prompt('diagnostic', 'fungicide')

                        combined = openai_client.chat.completions.create(
                            model=Config.CHAT_MODEL,
                            messages=[
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": (
                                    f"Based on visual diagnosis of a turf photo, the likely issue is: {detected_disease}.\n\n"
                                    f"Visual analysis:\n{diagnosis_text}\n\n"
                                    f"Treatment context from research:\n{context}\n\n"
                                    f"Provide a combined response: 1) Visual diagnosis findings, "
                                    f"2) Treatment recommendations with product names and rates, "
                                    f"3) Cultural practice adjustments. Keep it focused and actionable."
                                )}
                            ],
                            max_tokens=Config.CHAT_MAX_TOKENS,
                            temperature=Config.CHAT_TEMPERATURE,
                            timeout=30
                        )
                        diagnosis_text = combined.choices[0].message.content or diagnosis_text
            except Exception as e:
                logger.warning(f"RAG enrichment failed for diagnosis: {e}")

            # Add disease, weed, or pest reference photos
            disease_photos = get_disease_photos(detected_disease)
            if disease_photos:
                images.extend(disease_photos)
            else:
                weed_photos = get_weed_photos(detected_disease)
                if weed_photos:
                    images.extend(weed_photos)
                else:
                    pest_photos = get_pest_photos(detected_disease)
                    if pest_photos:
                        images.extend(pest_photos)

        # Process sources
        sources = deduplicate_sources(sources) if sources else []
        display_sources = filter_display_sources(sources, SEARCH_FOLDERS) if sources else []

        confidence_score = 75 if detected_disease else 55
        confidence_label = get_confidence_label(confidence_score)

        elapsed = _time.time() - _t0
        logging.info(f"Photo diagnosis in {elapsed:.1f}s | detected: {detected_disease or 'unknown'}")

        return jsonify({
            'answer': diagnosis_text,
            'sources': display_sources[:MAX_SOURCES],
            'images': images,
            'confidence': {'score': confidence_score, 'label': confidence_label},
            'grounding': {'verified': True, 'issues': []},
            'needs_review': False
        })

    except Exception as e:
        logger.error(f"Photo diagnosis error: {e}", exc_info=True)
        return jsonify({
            'answer': "I had trouble analyzing the photo. Please try again with a clear, well-lit photo of the affected turf area.",
            'sources': [], 'images': [],
            'confidence': {'score': 0, 'label': 'Error'}
        })


# -----------------------------------------------------------------------------
# Session routes
# -----------------------------------------------------------------------------

@app.route('/api/new-session', methods=['POST'])
@login_required
def new_session():
    """Clear session to start a new conversation."""
    session.clear()
    return jsonify({'success': True})


# -----------------------------------------------------------------------------
# Admin routes
# -----------------------------------------------------------------------------

@app.route('/admin')
def admin_dashboard():
    return render_template('admin.html')


@app.route('/admin/stats')
def admin_stats():
    from feedback_system import get_feedback_stats
    return jsonify(get_feedback_stats())


@app.route('/admin/cache')
def admin_cache_stats():
    """Get cache statistics for monitoring."""
    from cache import get_embedding_cache, get_source_url_cache, get_search_cache
    return jsonify({
        'embedding_cache': get_embedding_cache().stats(),
        'source_url_cache': get_source_url_cache().stats(),
        'search_cache': get_search_cache().stats()
    })


@app.route('/admin/feedback/review')
def admin_feedback_review():
    from feedback_system import get_negative_feedback
    return jsonify(get_negative_feedback(limit=100, unreviewed_only=True))


@app.route('/admin/feedback/needs-review')
def admin_needs_review():
    """Get queries that were auto-flagged for human review (< 70% confidence)"""
    from feedback_system import get_queries_needing_review
    return jsonify(get_queries_needing_review(limit=100))


@app.route('/admin/feedback/all')
def admin_feedback_all():
    from db import get_db, FEEDBACK_DB
    with get_db(FEEDBACK_DB) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, question, ai_answer, user_rating, user_correction, timestamp, confidence_score
            FROM feedback ORDER BY timestamp DESC LIMIT 100
        ''')
        results = cursor.fetchall()

    feedback = [{
        'id': row[0], 'question': row[1], 'ai_answer': row[2],
        'rating': row[3], 'correction': row[4], 'timestamp': row[5],
        'confidence': row[6]
    } for row in results]
    return jsonify(feedback)


@app.route('/admin/feedback/approve', methods=['POST'])
def admin_approve_feedback():
    from feedback_system import approve_for_training
    data = request.json
    approve_for_training(data.get('id'), data.get('correction'))
    return jsonify({'success': True})


@app.route('/admin/feedback/reject', methods=['POST'])
def admin_reject_feedback():
    from feedback_system import reject_feedback
    data = request.json
    reject_feedback(data.get('id'), "Rejected by admin")
    return jsonify({'success': True})


@app.route('/admin/review-queue')
def admin_review_queue():
    """Get unified moderation queue (user-flagged + auto-flagged)"""
    from feedback_system import get_review_queue
    queue_type = request.args.get('type', 'all')  # all, negative, low_confidence
    return jsonify(get_review_queue(limit=100, queue_type=queue_type))


@app.route('/admin/moderate', methods=['POST'])
def admin_moderate():
    """Moderate an answer: approve, reject, or correct"""
    from feedback_system import moderate_answer
    data = request.json
    result = moderate_answer(
        feedback_id=data.get('id'),
        action=data.get('action'),  # approve, reject, correct
        corrected_answer=data.get('corrected_answer'),
        reason=data.get('reason'),
        moderator=data.get('moderator', 'admin')
    )
    return jsonify(result)


@app.route('/admin/promote-to-golden', methods=['POST'])
def admin_promote_to_golden():
    """Promote a moderation queue item to a golden answer"""
    from intelligence_engine import SelfHealingLoop
    data = request.json
    question = data.get('question', '').strip()
    answer = data.get('answer', '').strip()
    category = data.get('category', '').strip() or None
    if not question or not answer:
        return jsonify({'success': False, 'error': 'Question and answer required'})
    ga_id = SelfHealingLoop.create_golden_answer(question, answer, category)
    return jsonify({'success': True, 'id': ga_id})


@app.route('/admin/moderator-history')
def admin_moderator_history():
    """Get audit trail of moderator actions"""
    from feedback_system import get_moderator_history
    return jsonify(get_moderator_history(limit=100))


@app.route('/admin/training/generate', methods=['POST'])
def admin_generate_training():
    """Generate JSONL training file from approved feedback using the fine-tuning pipeline."""
    from fine_tuning import prepare_training_data
    result = prepare_training_data()
    if result.get('success'):
        return jsonify({
            'success': True,
            'filepath': result['path'],
            'num_examples': result['num_examples']
        })
    return jsonify({
        'success': False,
        'message': result.get('error', 'Not enough approved examples'),
        'current_count': result.get('current_count', 0),
        'needed': result.get('needed', 50)
    })


@app.route('/admin/knowledge')
def admin_knowledge_status():
    """Get knowledge base status including PDFs and web-scraped content."""
    try:
        from knowledge_builder import IndexTracker, scan_for_pdfs
    except ImportError as ie:
        logger.warning(f"knowledge_builder unavailable: {ie}")
        return jsonify({
            'indexed_files': 0, 'total_chunks': 0, 'last_run': None,
            'total_pdfs': 0, 'unindexed': 0, 'unindexed_sample': [],
            'pinecone_total_vectors': 0, 'scraped_sources': {},
            'warning': f'Knowledge builder unavailable: {ie}'
        })

    tracker = IndexTracker()
    stats = tracker.get_stats()

    all_pdfs = scan_for_pdfs()
    unindexed = [f for f, _ in all_pdfs if not tracker.is_indexed(f)]

    # Get total vectors from Pinecone (includes PDFs + scraped web guides)
    pinecone_vectors = 0
    try:
        pinecone_stats = index.describe_index_stats()
        pinecone_vectors = pinecone_stats.get('total_vector_count', 0)
    except Exception as e:
        logger.warning(f"Could not get Pinecone stats: {e}")

    # Count scraped knowledge sources
    scraped_sources = {
        'disease_guides': {'source': 'GreenCast', 'type': 'disease_guide'},
        'weed_guides': {'source': 'GreenCast', 'type': 'weed_guide'},
        'pest_guides': {'source': 'NC State TurfFiles', 'type': 'pest_guide'},
        'cultural_practices': {'source': 'University Extensions', 'type': 'cultural_practices'},
        'nematode_guides': {'source': 'UF/UC/Penn State/NC State', 'type': 'nematode_guide'},
        'abiotic_disorders': {'source': 'University Extensions', 'type': 'abiotic_disorders'},
        'irrigation': {'source': 'University Extensions', 'type': 'irrigation'},
        'fertility': {'source': 'University Extensions', 'type': 'fertility'},
    }

    return jsonify({
        'indexed_files': stats['total_files'],
        'total_chunks': stats['total_chunks'],
        'last_run': stats['last_run'],
        'total_pdfs': len(all_pdfs),
        'unindexed': len(unindexed),
        'unindexed_sample': [os.path.basename(f) for f in unindexed[:10]],
        'pinecone_total_vectors': pinecone_vectors,
        'scraped_sources': scraped_sources
    })


@app.route('/admin/knowledge/build', methods=['POST'])
def admin_knowledge_build():
    """Trigger knowledge base build (limited for safety)."""
    from knowledge_builder import build_knowledge_base, IndexTracker, scan_for_pdfs
    import threading

    data = request.get_json(silent=True) or {}
    limit = data.get('limit', 10)

    # Check if there are actually files to index
    tracker = IndexTracker()
    all_pdfs = scan_for_pdfs()
    unindexed = [f for f, _ in all_pdfs if not tracker.is_indexed(f)]

    if not unindexed:
        return jsonify({
            'success': True,
            'message': 'All PDF files are already indexed. No new files to process.'
        })

    actual_limit = min(limit, len(unindexed))

    # Run in background thread with status tracking
    build_status = {'running': True, 'error': None}

    def run_build():
        try:
            build_knowledge_base(limit=actual_limit)
        except Exception as e:
            logger.error(f"Knowledge build error: {e}")
            build_status['error'] = str(e)
        finally:
            build_status['running'] = False

    thread = threading.Thread(target=run_build, daemon=True)
    thread.start()

    return jsonify({
        'success': True,
        'message': f'Indexing {actual_limit} of {len(unindexed)} unindexed PDFs in background'
    })


# -----------------------------------------------------------------------------
# Bulk Operations
# -----------------------------------------------------------------------------

@app.route('/admin/bulk-moderate', methods=['POST'])
def admin_bulk_moderate():
    """Bulk approve or reject multiple items"""
    from feedback_system import bulk_moderate
    data = request.json
    ids = data.get('ids', [])
    action = data.get('action', 'approve')
    reason = data.get('reason')

    if not ids:
        return jsonify({'success': False, 'error': 'No IDs provided'})

    result = bulk_moderate(ids, action, reason)
    return jsonify(result)


@app.route('/admin/bulk-approve-high-confidence', methods=['POST'])
def admin_bulk_approve_high_confidence():
    """Auto-approve all high-confidence items"""
    from feedback_system import bulk_approve_high_confidence
    data = request.json or {}
    min_confidence = data.get('min_confidence', 80)
    limit = data.get('limit', 100)

    result = bulk_approve_high_confidence(min_confidence, limit)
    return jsonify(result)


# -----------------------------------------------------------------------------
# Export Routes
# -----------------------------------------------------------------------------

@app.route('/admin/export/feedback')
def admin_export_feedback():
    """Export all feedback as CSV"""
    from feedback_system import export_feedback_csv
    from flask import Response

    csv_data = export_feedback_csv()
    return Response(
        csv_data,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=feedback_export.csv'}
    )


@app.route('/admin/export/training')
def admin_export_training():
    """Export training examples as CSV"""
    from feedback_system import export_training_examples_csv
    from flask import Response

    csv_data = export_training_examples_csv()
    return Response(
        csv_data,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=training_examples.csv'}
    )


@app.route('/admin/export/moderation')
def admin_export_moderation():
    """Export moderation history as CSV"""
    from feedback_system import export_moderation_history_csv
    from flask import Response

    csv_data = export_moderation_history_csv()
    return Response(
        csv_data,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=moderation_history.csv'}
    )


@app.route('/admin/export/analytics')
def admin_export_analytics():
    """Export analytics data as JSON"""
    from feedback_system import export_analytics_json
    return jsonify(export_analytics_json())


# -----------------------------------------------------------------------------
# Priority Queue Routes
# -----------------------------------------------------------------------------

@app.route('/admin/priority-queue')
def admin_priority_queue():
    """Get priority-sorted review queue"""
    from feedback_system import get_priority_review_queue
    limit = request.args.get('limit', 100, type=int)
    return jsonify(get_priority_review_queue(limit))


@app.route('/admin/trending-issues')
def admin_trending_issues():
    """Get trending problem areas"""
    from feedback_system import get_trending_issues
    min_frequency = request.args.get('min_frequency', 3, type=int)
    days = request.args.get('days', 7, type=int)
    return jsonify(get_trending_issues(min_frequency, days))


@app.route('/admin/question-frequencies')
def admin_question_frequencies():
    """Get frequently asked questions"""
    from feedback_system import get_question_frequencies
    limit = request.args.get('limit', 50, type=int)
    return jsonify(get_question_frequencies(limit))


# -----------------------------------------------------------------------------
# Fine-tuning Routes
# -----------------------------------------------------------------------------

@app.route('/admin/fine-tuning/status')
def admin_fine_tuning_status():
    """Get fine-tuning status and training data readiness"""
    from feedback_system import get_training_examples
    from fine_tuning import list_fine_tuning_jobs, get_active_fine_tuned_model, MIN_EXAMPLES_FOR_TRAINING

    examples = get_training_examples(unused_only=True)
    jobs = list_fine_tuning_jobs(limit=5)
    active_model = get_active_fine_tuned_model()

    return jsonify({
        'training_examples_ready': len(examples),
        'min_examples_needed': MIN_EXAMPLES_FOR_TRAINING,
        'ready_to_train': len(examples) >= MIN_EXAMPLES_FOR_TRAINING,
        'recent_jobs': jobs,
        'active_fine_tuned_model': active_model
    })


@app.route('/admin/fine-tuning/start', methods=['POST'])
def admin_start_fine_tuning():
    """Start the fine-tuning pipeline"""
    from fine_tuning import run_full_fine_tuning_pipeline

    result = run_full_fine_tuning_pipeline()
    return jsonify(result)


@app.route('/admin/fine-tuning/job/<job_id>')
def admin_fine_tuning_job_status(job_id):
    """Get status of a specific fine-tuning job"""
    from fine_tuning import get_fine_tuning_status

    status = get_fine_tuning_status(job_id)
    return jsonify(status)


@app.route('/admin/source-quality')
def admin_source_quality():
    """Get source quality scores from feedback"""
    from fine_tuning import get_source_quality_scores, get_low_quality_sources

    return jsonify({
        'all_scores': get_source_quality_scores(),
        'low_quality': get_low_quality_sources(threshold=0.4)
    })


@app.route('/admin/eval/run', methods=['POST'])
def admin_run_evaluation():
    """Run evaluation against test questions"""
    from fine_tuning import run_evaluation, save_eval_results

    try:
        # Check if we should use the full 100-question set
        body = request.get_json(silent=True) or {}
        use_full = body.get('full', False)

        if use_full:
            from eval_questions_100 import EVAL_QUESTIONS_100
            results = run_evaluation(custom_questions=EVAL_QUESTIONS_100)
        else:
            results = run_evaluation()

        run_id = save_eval_results(results)
        results['run_id'] = run_id
        return jsonify(results)
    except Exception as e:
        import traceback
        logger.error(f"Evaluation error: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500


@app.route('/admin/eval/history')
def admin_eval_history():
    """Get evaluation run history"""
    from fine_tuning import get_eval_history

    limit = request.args.get('limit', 10, type=int)
    return jsonify(get_eval_history(limit))


# -----------------------------------------------------------------------------
# TGIF routes
# -----------------------------------------------------------------------------

@app.route('/tgif')
def tgif_search():
    return render_template('tgif_search.html')


@app.route('/tgif/analyze', methods=['POST'])
def tgif_analyze():
    import json
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
        # This helps identify which sources lead to good/bad answers
        try:
            from fine_tuning import track_source_quality
            from db import get_db, FEEDBACK_DB
            import json

            # Get the feedback record to access sources
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
# Intelligence Engine API
# -----------------------------------------------------------------------------

@app.route('/api/intelligence/overview')
def intelligence_overview():
    """Get high-level intelligence dashboard data."""
    return jsonify(get_intelligence_overview())


@app.route('/api/intelligence/events')
def intelligence_events():
    """Get recent intelligence events (audit log)."""
    from intelligence_engine import _get_conn
    limit = request.args.get('limit', 50, type=int)
    subsystem = request.args.get('subsystem')
    conn = _get_conn()
    if subsystem:
        rows = conn.execute(
            'SELECT * FROM intelligence_events WHERE subsystem = ? ORDER BY timestamp DESC LIMIT ?',
            (subsystem, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            'SELECT * FROM intelligence_events ORDER BY timestamp DESC LIMIT ?',
            (limit,)
        ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


# --- Self-Healing Knowledge Loop ---

@app.route('/api/intelligence/golden-answers')
def get_golden_answers():
    """Get all golden answers."""
    include_inactive = request.args.get('include_inactive', 'false') == 'true'
    return jsonify(SelfHealingLoop.get_all_golden_answers(include_inactive))


@app.route('/api/intelligence/golden-answers', methods=['POST'])
def create_golden_answer():
    """Create a new golden answer."""
    data = request.json
    golden_id = SelfHealingLoop.create_golden_answer(
        question=data['question'],
        answer=data['answer'],
        category=data.get('category'),
        source_feedback_id=data.get('source_feedback_id')
    )
    return jsonify({'success': True, 'id': golden_id})


@app.route('/api/intelligence/golden-answers/<int:golden_id>', methods=['PUT'])
def update_golden_answer(golden_id):
    """Update a golden answer."""
    data = request.json
    success = SelfHealingLoop.update_golden_answer(golden_id, **data)
    return jsonify({'success': success})


@app.route('/api/intelligence/golden-answers/<int:golden_id>', methods=['DELETE'])
def delete_golden_answer(golden_id):
    """Soft-delete a golden answer."""
    success = SelfHealingLoop.delete_golden_answer(golden_id)
    return jsonify({'success': success})


@app.route('/api/intelligence/weak-patterns')
def get_weak_patterns():
    """Detect recurring low-quality answer patterns."""
    days = request.args.get('days', 30, type=int)
    min_occ = request.args.get('min_occurrences', 3, type=int)
    return jsonify(SelfHealingLoop.detect_weak_patterns(min_occ, days))


# --- A/B Testing ---

@app.route('/api/intelligence/ab-tests')
def get_ab_tests():
    """Get active A/B tests."""
    return jsonify(ABTestingEngine.get_active_tests())


@app.route('/api/intelligence/ab-tests', methods=['POST'])
def create_ab_test():
    """Create a new A/B test."""
    data = request.json
    test_id = ABTestingEngine.create_ab_test(
        name=data['name'],
        pattern=data['pattern'],
        version_ids=data['version_ids'],
        traffic_split=data.get('traffic_split')
    )
    return jsonify({'success': True, 'id': test_id})


@app.route('/api/intelligence/ab-tests/<int:test_id>/analyze')
def analyze_ab_test(test_id):
    """Analyze A/B test results with statistical significance."""
    return jsonify(ABTestingEngine.analyze_ab_test(test_id))


@app.route('/api/intelligence/ab-tests/<int:test_id>/end', methods=['POST'])
def end_ab_test(test_id):
    """End an A/B test."""
    data = request.json or {}
    ABTestingEngine.end_test(test_id, data.get('winner_version_id'))
    return jsonify({'success': True})


@app.route('/api/intelligence/answer-versions', methods=['POST'])
def create_answer_version():
    """Create an answer version for A/B testing."""
    data = request.json
    version_id = ABTestingEngine.create_answer_version(
        pattern=data['pattern'],
        answer_template=data['answer_template'],
        strategy=data.get('strategy', 'default'),
        metadata=data.get('metadata')
    )
    return jsonify({'success': True, 'id': version_id})


# --- Source Quality Intelligence ---

@app.route('/api/intelligence/sources')
def get_source_leaderboard():
    """Get sources ranked by reliability."""
    limit = request.args.get('limit', 50, type=int)
    min_appearances = request.args.get('min_appearances', 3, type=int)
    return jsonify(SourceQualityIntelligence.get_source_leaderboard(limit, min_appearances))


@app.route('/api/intelligence/sources/<path:source_id>')
def get_source_detail(source_id):
    """Get reliability info for a specific source."""
    result = SourceQualityIntelligence.get_source_reliability(source_id)
    if result:
        return jsonify(result)
    return jsonify({'error': 'Source not found'}), 404


@app.route('/api/intelligence/sources/<path:source_id>/boost', methods=['POST'])
def set_source_boost(source_id):
    """Admin boost/penalize a source."""
    data = request.json
    SourceQualityIntelligence.set_admin_boost(source_id, data.get('boost', 0.0))
    return jsonify({'success': True})


# --- Confidence Calibration ---

@app.route('/api/intelligence/calibration-report')
def get_calibration_report():
    """Get full confidence calibration report."""
    return jsonify(ConfidenceCalibration.get_calibration_report())


@app.route('/api/intelligence/calibration-curve')
def get_calibration_curve():
    """Get calibration curve for a specific topic."""
    topic = request.args.get('topic')
    return jsonify(ConfidenceCalibration.compute_calibration_curve(topic=topic))


# --- Regression Detection ---

@app.route('/api/intelligence/regression-tests')
def get_regression_tests():
    """Get all regression tests."""
    active_only = request.args.get('active_only', 'true') == 'true'
    return jsonify(RegressionDetector.get_regression_tests(active_only))


@app.route('/api/intelligence/regression-tests', methods=['POST'])
def add_regression_test():
    """Add a new regression test case."""
    data = request.json
    test_id = RegressionDetector.add_regression_test(
        question=data['question'],
        expected_answer=data['expected_answer'],
        category=data.get('category'),
        criteria=data.get('criteria'),
        priority=data.get('priority', 1)
    )
    return jsonify({'success': True, 'id': test_id})


@app.route('/api/intelligence/regression-tests/<int:test_id>', methods=['PUT'])
def update_regression_test(test_id):
    """Update a regression test."""
    data = request.json
    success = RegressionDetector.update_regression_test(test_id, **data)
    return jsonify({'success': success})


@app.route('/api/intelligence/regression-tests/<int:test_id>', methods=['DELETE'])
def delete_regression_test(test_id):
    """Soft-delete a regression test."""
    success = RegressionDetector.delete_regression_test(test_id)
    return jsonify({'success': success})


@app.route('/api/intelligence/regression-dashboard')
def get_regression_dashboard():
    """Get regression testing dashboard."""
    return jsonify(RegressionDetector.get_regression_dashboard())


@app.route('/api/intelligence/regression-run', methods=['POST'])
def run_regression_suite():
    """Manually trigger a regression test run."""
    result = RegressionDetector.run_regression_suite(trigger='manual')
    return jsonify(result)


# --- Topic Clustering ---

@app.route('/api/intelligence/topics')
def get_topic_dashboard():
    """Get topic intelligence dashboard."""
    return jsonify(TopicIntelligence.get_topic_dashboard())


@app.route('/api/intelligence/topics/emerging')
def get_emerging_topics():
    """Get emerging topics."""
    days = request.args.get('days', 7, type=int)
    return jsonify(TopicIntelligence.detect_emerging_topics(days))


@app.route('/api/intelligence/topics/cluster', methods=['POST'])
def run_topic_clustering():
    """Manually trigger topic clustering."""
    result = TopicIntelligence.cluster_questions()
    return jsonify(result)


# --- Satisfaction Prediction ---

@app.route('/api/intelligence/satisfaction/accuracy')
def get_satisfaction_accuracy():
    """Get satisfaction prediction model accuracy."""
    return jsonify(SatisfactionPredictor.get_prediction_accuracy())


@app.route('/api/intelligence/satisfaction/train', methods=['POST'])
def train_satisfaction_model_route():
    """Manually trigger satisfaction model training."""
    result = SatisfactionPredictor.train_satisfaction_model()
    return jsonify(result)


# --- Smart Escalation ---

@app.route('/api/intelligence/escalations')
def get_escalation_queue():
    """Get smart escalation queue."""
    status = request.args.get('status', 'open')
    limit = request.args.get('limit', 50, type=int)
    return jsonify(SmartEscalation.get_smart_escalation_queue(status, limit))


@app.route('/api/intelligence/escalations/stats')
def get_escalation_stats():
    """Get escalation queue statistics."""
    return jsonify(SmartEscalation.get_escalation_stats())


@app.route('/api/intelligence/escalations/<int:esc_id>/resolve', methods=['POST'])
def resolve_escalation(esc_id):
    """Resolve an escalation."""
    data = request.json
    success = SmartEscalation.resolve_escalation(
        escalation_id=esc_id,
        action=data.get('action', 'dismiss'),
        resolved_by=data.get('resolved_by', 'admin'),
        notes=data.get('notes'),
        corrected_answer=data.get('corrected_answer')
    )
    return jsonify({'success': success})


# --- Promote from moderation to golden answer ---

@app.route('/api/intelligence/promote-to-golden', methods=['POST'])
def promote_to_golden():
    """Promote an approved moderation answer to golden answer."""
    data = request.json
    golden_id = SelfHealingLoop.create_golden_answer(
        question=data['question'],
        answer=data['answer'],
        category=data.get('category'),
        source_feedback_id=data.get('feedback_id')
    )
    return jsonify({'success': True, 'golden_id': golden_id})


# =============================================================================
# ENTERPRISE INTELLIGENCE API ENDPOINTS
# =============================================================================

# --- Pipeline Analytics & Cost ---

@app.route('/api/intelligence/pipeline-metrics')
def api_pipeline_metrics():
    """Get pipeline latency, throughput, and cost metrics."""
    period = request.args.get('period', '24h')
    return jsonify({
        'latency': PipelineAnalytics.get_latency_percentiles(period),
        'throughput': PipelineAnalytics.get_throughput(period),
        'cost': PipelineAnalytics.get_cost_summary(period),
        'steps': PipelineAnalytics.get_step_breakdown(period)
    })

@app.route('/api/intelligence/cost-summary')
def api_cost_summary():
    """Get cost breakdown by model and step."""
    period = request.args.get('period', '24h')
    return jsonify(PipelineAnalytics.get_cost_summary(period))

# --- Anomaly Detection ---

@app.route('/api/intelligence/anomalies')
def api_anomalies():
    """Get recent anomaly detections."""
    limit = request.args.get('limit', 50, type=int)
    return jsonify({'anomalies': AnomalyDetector.get_recent_anomalies(limit)})

@app.route('/api/intelligence/anomalies/check', methods=['POST'])
def api_anomaly_check():
    """Run anomaly detection now."""
    detections = AnomalyDetector.check_all()
    return jsonify({'detections': detections, 'count': len(detections)})

# --- Alert System ---

@app.route('/api/intelligence/alerts')
def api_alerts():
    """Get alert history."""
    limit = request.args.get('limit', 100, type=int)
    return jsonify({'alerts': AlertEngine.get_alert_history(limit)})

@app.route('/api/intelligence/alert-rules')
def api_alert_rules_get():
    """Get all alert rules."""
    return jsonify({'rules': AlertEngine.get_rules()})

@app.route('/api/intelligence/alert-rules', methods=['POST'])
def api_alert_rules_create():
    """Create a new alert rule."""
    data = request.json
    rule_id = AlertEngine.create_rule(
        name=data['name'],
        metric=data['metric'],
        condition=data['condition'],
        threshold=float(data['threshold']),
        channels=data.get('channels', ['in_app']),
        cooldown_minutes=data.get('cooldown_minutes', 60)
    )
    return jsonify({'success': True, 'rule_id': rule_id})

@app.route('/api/intelligence/alert-rules/<int:rule_id>', methods=['PUT'])
def api_alert_rules_update(rule_id):
    """Update an alert rule."""
    data = request.json
    from intelligence_engine import _get_conn
    conn = _get_conn()
    conn.execute('''
        UPDATE alert_rules SET name=?, metric=?, condition=?, threshold=?,
        channels=?, cooldown_minutes=?, enabled=? WHERE id=?
    ''', (data.get('name'), data.get('metric'), data.get('condition'),
          data.get('threshold'), json.dumps(data.get('channels', ['in_app'])),
          data.get('cooldown_minutes', 60), data.get('enabled', True), rule_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/intelligence/alert-rules/<int:rule_id>', methods=['DELETE'])
def api_alert_rules_delete(rule_id):
    """Disable an alert rule."""
    from intelligence_engine import _get_conn
    conn = _get_conn()
    conn.execute('UPDATE alert_rules SET enabled = 0 WHERE id = ?', (rule_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

# --- Remediation & Circuit Breakers ---

@app.route('/api/intelligence/remediations')
def api_remediations():
    """Get remediation action history."""
    limit = request.args.get('limit', 50, type=int)
    return jsonify({'actions': RemediationEngine.get_history(limit)})

@app.route('/api/intelligence/circuit-breakers')
def api_circuit_breakers():
    """Get circuit breaker status."""
    return jsonify({'breakers': CircuitBreaker.get_all_breakers()})

# --- Prompt Versioning ---

@app.route('/api/intelligence/prompt-versions')
def api_prompt_versions():
    """Get all prompt versions."""
    return jsonify({'versions': PromptVersioning.get_all_versions()})

@app.route('/api/intelligence/prompt-versions', methods=['POST'])
def api_prompt_version_create():
    """Create a new prompt version."""
    data = request.json
    version_id = PromptVersioning.create_version(
        template_text=data['template_text'],
        description=data.get('description', ''),
        changes=data.get('changes', ''),
        created_by=data.get('created_by', 'admin')
    )
    return jsonify({'success': True, 'version_id': version_id})

@app.route('/api/intelligence/prompt-versions/<int:version_id>/activate', methods=['POST'])
def api_prompt_version_activate(version_id):
    """Activate a prompt version."""
    success = PromptVersioning.activate_version(version_id)
    return jsonify({'success': success})

@app.route('/api/intelligence/prompt-versions/<int:version_id>/rollback', methods=['POST'])
def api_prompt_version_rollback(version_id):
    """Rollback to a prompt version."""
    success = PromptVersioning.rollback(version_id)
    return jsonify({'success': success})

@app.route('/api/intelligence/prompt-versions/compare')
def api_prompt_version_compare():
    """Compare two prompt versions."""
    v1 = request.args.get('v1', type=int)
    v2 = request.args.get('v2', type=int)
    if not v1 or not v2:
        return jsonify({'error': 'v1 and v2 parameters required'}), 400
    return jsonify(PromptVersioning.compare_versions(v1, v2))

# --- Knowledge Gaps ---

@app.route('/api/intelligence/knowledge-gaps')
def api_knowledge_gaps():
    """Get knowledge gap report."""
    return jsonify({'gaps': KnowledgeGapAnalyzer.get_gap_report()})

@app.route('/api/intelligence/knowledge-gaps/detect', methods=['POST'])
def api_detect_knowledge_gaps():
    """Run knowledge gap detection now."""
    gaps = KnowledgeGapAnalyzer.detect_gaps()
    return jsonify({'gaps': gaps, 'count': len(gaps)})

@app.route('/api/intelligence/content-freshness')
def api_content_freshness():
    """Get content freshness report."""
    return jsonify({'sources': KnowledgeGapAnalyzer.get_freshness_report()})

@app.route('/api/intelligence/coverage-matrix')
def api_coverage_matrix():
    """Get coverage quality matrix by category."""
    return jsonify(KnowledgeGapAnalyzer.get_coverage_matrix())

# --- Executive Dashboard ---

@app.route('/api/intelligence/executive/health')
def api_executive_health():
    """Get system health score (0-100)."""
    return jsonify(ExecutiveDashboard.compute_system_health())

@app.route('/api/intelligence/executive/weekly-digest')
def api_weekly_digest():
    """Get weekly performance digest."""
    return jsonify(ExecutiveDashboard.generate_weekly_digest())

@app.route('/api/intelligence/executive/kpi-trends')
def api_kpi_trends():
    """Get KPI time-series data."""
    period = request.args.get('period', '30d')
    return jsonify(ExecutiveDashboard.get_kpi_trends(period))

@app.route('/api/intelligence/executive/roi')
def api_roi_metrics():
    """Get ROI metrics."""
    return jsonify(ExecutiveDashboard.compute_roi_metrics())

# --- Gradient Boosted Predictor ---

@app.route('/api/intelligence/gradient-boosted/train', methods=['POST'])
def api_gradient_boosted_train():
    """Train the gradient boosted satisfaction model."""
    result = GradientBoostedPredictor.train()
    return jsonify(result)

@app.route('/api/intelligence/gradient-boosted/importance')
def api_gradient_boosted_importance():
    """Get feature importance from gradient boosted model."""
    return jsonify(GradientBoostedPredictor.feature_importance())

# --- Conversation Intelligence ---

@app.route('/api/intelligence/conversations')
def api_conversations():
    """Get conversation quality metrics."""
    return jsonify(ConversationIntelligence.get_conversation_quality_metrics())

@app.route('/api/intelligence/conversations/frustration')
def api_conversations_frustration():
    """Get frustration signals from conversations."""
    days = request.args.get('days', 7, type=int)
    return jsonify({'conversations': ConversationIntelligence.detect_frustration_signals(days)})

@app.route('/api/intelligence/conversations/analyze', methods=['POST'])
def api_conversations_analyze():
    """Batch analyze recent conversations."""
    days = request.json.get('days', 7) if request.json else 7
    ConversationIntelligence.batch_analyze_recent(days)
    return jsonify({'success': True})


# ── Anthropic-Grade: Feature Flags ──

@app.route('/api/intelligence/feature-flags')
def api_feature_flags():
    """Get all feature flag states."""
    return jsonify(FeatureFlags.get_all_flags())

@app.route('/api/intelligence/feature-flags', methods=['POST'])
def api_feature_flags_toggle():
    """Toggle a feature flag."""
    data = request.json or {}
    flag_name = data.get('flag_name')
    enabled = data.get('enabled')
    if not flag_name or enabled is None:
        return jsonify({'error': 'flag_name and enabled required'}), 400
    ok = FeatureFlags.set_flag(flag_name, bool(enabled))
    return jsonify({'success': ok})


# ── Anthropic-Grade: Data Retention ──

@app.route('/api/intelligence/data-retention/status')
def api_data_retention_status():
    """Get data retention status per table."""
    return jsonify(DataRetentionManager.get_status())

@app.route('/api/intelligence/data-retention/run', methods=['POST'])
def api_data_retention_run():
    """Trigger data retention cleanup now."""
    result = DataRetentionManager.run_cleanup()
    return jsonify(result)


# ── Anthropic-Grade: Rate Limiting ──

@app.route('/api/intelligence/rate-limit/status')
def api_rate_limit_status():
    """Get rate limiter status."""
    return jsonify(RateLimiter.get_status())


# ── Anthropic-Grade: Cost Budget ──

@app.route('/api/intelligence/cost-budget/status')
def api_cost_budget_status():
    """Get cost budget utilization."""
    return jsonify(PipelineAnalytics.check_budget())

@app.route('/api/intelligence/cost-budget/set', methods=['POST'])
def api_cost_budget_set():
    """Update cost budget limits (runtime only, does not persist to .env)."""
    data = request.json or {}
    if 'daily' in data:
        Config.COST_BUDGET_DAILY = float(data['daily'])
    if 'monthly' in data:
        Config.COST_BUDGET_MONTHLY = float(data['monthly'])
    return jsonify({'success': True, 'daily': Config.COST_BUDGET_DAILY, 'monthly': Config.COST_BUDGET_MONTHLY})


# ── Anthropic-Grade: Training Readiness ──

@app.route('/api/intelligence/training/status')
def api_training_status():
    """Check training readiness."""
    return jsonify(TrainingOrchestrator.check_readiness())

@app.route('/api/intelligence/training/check', methods=['POST'])
def api_training_check():
    """Run training readiness check now."""
    return jsonify(TrainingOrchestrator.check_readiness())


# ── Anthropic-Grade: Input Sanitization ──

@app.route('/api/intelligence/sanitization/blocked')
def api_sanitization_blocked():
    """Get recent blocked/flagged queries."""
    limit = request.args.get('limit', 50, type=int)
    return jsonify(InputSanitizer.get_blocked_queries(limit))


# -----------------------------------------------------------------------------
# Health check for monitoring
# -----------------------------------------------------------------------------

@app.route('/health')
def health_check():
    """Health check endpoint for production monitoring."""
    import time
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
