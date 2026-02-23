from flask import Flask, render_template, send_from_directory, jsonify, request, session, redirect, Response
from routes import turf_bp
import os
import json
import logging
from datetime import datetime, timedelta
import openai
from config import Config
from dotenv import load_dotenv
from pinecone import Pinecone
from logging_config import logger
from detection import detect_grass_type, detect_region, detect_product_need
from auth import login_required, get_current_user, login_user_session, logout_user_session, create_user, authenticate_user
from profile import get_profile, save_profile, build_profile_context, get_sprayers, get_sprayer_for_area, save_sprayer, delete_sprayer
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
    deduplicate_sources, filter_display_sources
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
from answer_validator import apply_validation
from demo_cache import find_demo_response
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

load_dotenv()

# Logging is configured in logging_config.py

app = Flask(__name__)
app.secret_key = Config.FLASK_SECRET_KEY
app.register_blueprint(turf_bp)

openai_client = openai.OpenAI(api_key=Config.OPENAI_API_KEY)
pc = Pinecone(api_key=Config.PINECONE_API_KEY)
index = pc.Index(Config.PINECONE_INDEX)


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
        return jsonify({'authenticated': False}), 401
    profile = get_profile(user['id'])
    return jsonify({
        'authenticated': True,
        'user': user,
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
    profile = get_profile(session['user_id'])
    return jsonify(profile or {})


@app.route('/api/profile', methods=['POST'])
@login_required
def api_save_profile():
    data = request.json or {}
    save_profile(session['user_id'], data)
    return jsonify({'success': True})


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

    if is_tank_mix:
        # --- Tank mix path ---
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

        tank_count_from_ui = int(data.get('tank_count', 0)) or None
        mix_result = calculate_tank_mix(resolved_products, area_acreage, carrier_gpa, tank_size, tank_count_override=tank_count_from_ui)

        # Use first product for legacy columns
        first = mix_result['products'][0]
        app_data = {
            'date': data['date'],
            'area': area,
            'product_id': first['product_id'],
            'product_name': f"Tank Mix ({len(mix_result['products'])} products)",
            'product_category': 'tank_mix',
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
            'products_json': mix_result['products'],
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

    else:
        # --- Single product path ---
        if not data.get('product_id') or not data.get('rate') or not data.get('rate_unit'):
            return jsonify({'error': 'product_id, rate, and rate_unit are required'}), 400

        product = get_product_by_id(data['product_id'], user_id=user_id)
        if not product:
            return jsonify({'error': 'Product not found'}), 404

        rate = float(data['rate'])
        rate_unit = data['rate_unit']

        total_result = calculate_total_product(rate, rate_unit, area_acreage)
        total_carrier = None
        tank_count_calc = int(data.get('tank_count', 0)) or 0
        if not tank_count_calc and tank_size and tank_size > 0 and carrier_gpa and area_acreage:
            tank_count_calc = __import__('math').ceil((carrier_gpa * area_acreage) / tank_size)
        if tank_count_calc > 0 and tank_size and tank_size > 0:
            total_carrier = round(tank_size * tank_count_calc, 1)

        nutrients = calculate_nutrients(product, rate, rate_unit, area_acreage)

        app_data = {
            'date': data['date'],
            'area': area,
            'product_id': data['product_id'],
            'product_name': product['display_name'],
            'product_category': product['category'],
            'rate': rate,
            'rate_unit': rate_unit,
            'area_acreage': area_acreage,
            'carrier_volume_gpa': carrier_gpa,
            'total_product': total_result['total'],
            'total_product_unit': total_result['unit'],
            'total_carrier_gallons': total_carrier,
            'nutrients_applied': nutrients,
            'weather_temp': data.get('weather_temp'),
            'weather_wind': data.get('weather_wind'),
            'weather_conditions': data.get('weather_conditions'),
            'notes': data.get('notes'),
            'application_method': data.get('application_method')
        }

        app_id = save_application(user_id, app_data)

        return jsonify({
            'success': True,
            'id': app_id,
            'calculations': {
                'total_product': total_result['total'],
                'total_product_unit': total_result['unit'],
                'total_product_base': total_result.get('total_base'),
                'total_product_unit_base': total_result.get('unit_base'),
                'area_1000sqft': total_result['area_1000sqft'],
                'total_carrier_gallons': total_carrier,
                'tank_count': (
                    int(total_carrier / tank_size)
                    if total_carrier and tank_size else None
                ),
                'nutrients': nutrients
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
    year = request.args.get('year', str(__import__('datetime').datetime.now().year))
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
    for a in applications:
        if a.get('products_json') and len(a['products_json']) > 0:
            for p in a['products_json']:
                writer.writerow([a['date'], a['area'], a.get('application_method', ''),
                    p.get('product_name', ''), p.get('product_category', ''),
                    p.get('rate', ''), p.get('rate_unit', ''),
                    p.get('total_product', ''), p.get('total_product_unit', ''),
                    a.get('carrier_volume_gpa', ''), a.get('total_carrier_gallons', ''),
                    a.get('weather_temp', ''), a.get('weather_wind', ''),
                    a.get('weather_conditions', ''), a.get('notes', '')])
        else:
            writer.writerow([a['date'], a['area'], a.get('application_method', ''),
                a.get('product_name', ''), a.get('product_category', ''),
                a.get('rate', ''), a.get('rate_unit', ''),
                a.get('total_product', ''), a.get('total_product_unit', ''),
                a.get('carrier_volume_gpa', ''), a.get('total_carrier_gallons', ''),
                a.get('weather_temp', ''), a.get('weather_wind', ''),
                a.get('weather_conditions', ''), a.get('notes', '')])

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
        tank_count = __import__('math').ceil((float(carrier_gpa) * float(app_acreage)) / t_size)
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
    year = request.args.get('year', str(__import__('datetime').datetime.now().year))
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
    year = request.args.get('year', str(__import__('datetime').datetime.now().year))

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
        logging.debug('Received a question request.')
        body = request.json or {}
        question = body.get('question', '').strip()
        if not question:
            return jsonify({
                'answer': "Please enter a question about turfgrass management.",
                'sources': [],
                'confidence': {'score': 0, 'label': 'No Question'}
            })
        logging.debug(f'Question: {question}')
        import time as _time
        _t0 = _time.time()
        _timings = {}

        # Demo mode: return cached golden responses (zero API cost, instant)
        if Config.DEMO_MODE:
            demo_response = find_demo_response(question)
            if demo_response:
                return jsonify(demo_response)

        # ── PARALLEL: classify + feasibility (classify is LLM, feasibility is local) ──
        from concurrent.futures import ThreadPoolExecutor, as_completed
        classify_future = None
        with ThreadPoolExecutor(max_workers=2) as executor:
            classify_future = executor.submit(classify_query, openai_client, question, "gpt-4o-mini")
            feasibility_result = check_feasibility(question)

        classification = classify_future.result()
        intercept_response = get_response_for_category(
            classification['category'], classification.get('reason', '')
        )
        _timings['1_classify'] = _time.time() - _t0
        if intercept_response:
            logging.debug(f"Query intercepted: {classification['category']} - {classification.get('reason', '')}")
            return jsonify(intercept_response)

        if feasibility_result:
            logging.debug(f"Feasibility gate triggered: {feasibility_result.get('feasibility_issues', [])}")
            return jsonify(feasibility_result)

        # Get optional location for weather (can be passed from frontend)
        user_location = body.get('location', {})
        lat = user_location.get('lat')
        lon = user_location.get('lon')
        city = user_location.get('city')
        state = user_location.get('state')

        # Session management
        conversation_id = _get_or_create_conversation()

        # Detect if this is a topic change - if so, don't use conversation history
        question_lower = question.lower()
        current_topic = detect_topic(question_lower)
        current_subject = detect_specific_subject(question_lower)
        previous_topic = session.get('last_topic')
        previous_subject = session.get('last_subject')
        is_topic_change = _is_significant_topic_change(
            previous_topic, current_topic, question,
            previous_subject=previous_subject, current_subject=current_subject
        )

        # Always save the message
        save_message(conversation_id, 'user', question)

        if is_topic_change:
            logging.debug(f'Topic change detected: {previous_topic}({previous_subject}) -> {current_topic}({current_subject})')
            contextual_question = question
            question_to_process = expand_vague_question(question)
        else:
            contextual_question = build_context_for_ai(conversation_id, question)
            question_to_process = expand_vague_question(contextual_question)

        session['last_topic'] = current_topic
        if current_subject:
            session['last_subject'] = current_subject

        _timings['2_feasibility'] = _time.time() - _t0
        # LLM-based query rewriting for better retrieval
        rewritten_query = rewrite_query(openai_client, question_to_process, model="gpt-4o-mini")
        logging.debug(f'Rewritten query: {rewritten_query[:100]}')

        _timings['3_rewrite'] = _time.time() - _t0
        # Detect context from original question
        grass_type = detect_grass_type(question_to_process)
        region = detect_region(question_to_process)
        product_need = detect_product_need(question_to_process)
        question_topic = detect_topic(question_to_process.lower())

        # Profile-based fallback — if question doesn't specify, use profile
        user_profile = get_profile(session.get('user_id'))
        if not grass_type and user_profile:
            # For golf courses, use greens grass as primary reference
            if user_profile.get('turf_type') == 'golf_course':
                grass_type = user_profile.get('greens_grass') or user_profile.get('fairways_grass')
            else:
                grass_type = user_profile.get('primary_grass')
        if not region and user_profile and user_profile.get('region'):
            region = user_profile['region']
        if product_need and not question_topic:
            question_topic = 'chemical'

        # Build expanded query using rewritten version
        expanded_query = expand_query(rewritten_query)
        if grass_type:
            expanded_query += f" {grass_type}"
        if region:
            expanded_query += f" {region}"

        # Search (parallel execution for better performance)
        search_results = search_all_parallel(
            index, openai_client, rewritten_query, expanded_query,
            product_need, grass_type, Config.EMBEDDING_MODEL
        )

        _timings['4_search'] = _time.time() - _t0
        # Combine and score results first to check if we have anything
        all_matches = (
            search_results['general'].get('matches', []) +
            search_results['product'].get('matches', []) +
            search_results['timing'].get('matches', [])
        )
        scored_results = score_results(all_matches, question, grass_type, region, product_need)

        # Apply cross-encoder reranking for better relevance (if available)
        if scored_results:
            scored_results = rerank_results(rewritten_query, scored_results, top_k=20)

        _timings['5_rerank'] = _time.time() - _t0
        # Filter and build context
        filtered_results = safety_filter_results(scored_results, question_topic, product_need)
        context, sources, images = build_context(filtered_results, SEARCH_FOLDERS)

        # Calculate preliminary confidence to decide on web search
        prelim_confidence = len(filtered_results) * 10 if filtered_results else 0
        if filtered_results:
            avg_score = sum(r.get('score', 0) for r in filtered_results[:5]) / min(5, len(filtered_results))
            prelim_confidence = min(100, avg_score * 100)

        # Check if web search is needed
        used_web_search = False
        web_search_result = None
        supplement_mode = False

        if should_trigger_web_search(search_results):
            # No results at all - full web search fallback
            logging.debug('No Pinecone results found - triggering web search fallback')
            web_search_result = search_web_for_turf_info(openai_client, question, supplement_mode=False)
            if web_search_result:
                used_web_search = True
                context = web_search_result['context']
                sources = web_search_result['sources']
                images = []
                logging.debug('Web search fallback returned results')
        elif should_supplement_with_web_search(prelim_confidence):
            # Have some results but low confidence - supplement with web search
            logging.debug(f'Low confidence ({prelim_confidence:.0f}%) - supplementing with web search')
            web_search_result = search_web_for_turf_info(openai_client, question, supplement_mode=True)
            if web_search_result:
                used_web_search = True
                supplement_mode = True
                # Append web search context to existing context
                context = context + "\n\n" + web_search_result['context']
                sources = sources + web_search_result['sources']
                logging.debug('Web search supplement added')

        # Enrich context with structured knowledge base data
        if not used_web_search or supplement_mode:
            context = enrich_context_with_knowledge(question, context)

        # Add disease, weed, or pest reference photos if a specific subject was detected
        if current_subject:
            disease_photos = get_disease_photos(current_subject)
            if disease_photos:
                images.extend(disease_photos)
            else:
                weed_photos = get_weed_photos(current_subject)
                if weed_photos:
                    images.extend(weed_photos)
                else:
                    pest_photos = get_pest_photos(current_subject)
                    if pest_photos:
                        images.extend(pest_photos)

        # Add weather context if location provided and topic is relevant
        weather_data = None
        weather_topics = {'chemical', 'fungicide', 'herbicide', 'insecticide', 'irrigation', 'cultural', 'diagnostic', 'disease'}
        if (lat and lon) or city:
            if question_topic in weather_topics or product_need:
                weather_data = get_weather_data(lat=lat, lon=lon, city=city, state=state)
                if weather_data:
                    weather_context = get_weather_context(weather_data)
                    context = context + "\n\n" + weather_context
                    logging.debug(f"Added weather context for {weather_data.get('location', 'unknown')}")

        context = context[:MAX_CONTEXT_LENGTH]

        # Process sources
        sources = [s for s in sources if s.get('url') is not None or s.get('note')]  # Allow web search sources
        sources = deduplicate_sources(sources)

        # For supplement mode, filter DB sources but keep web sources
        if supplement_mode:
            db_sources = [s for s in sources if not s.get('note', '').startswith('Web search')]
            web_sources = [s for s in sources if s.get('note', '').startswith('Web search')]
            display_sources = filter_display_sources(db_sources, SEARCH_FOLDERS) + web_sources
        elif used_web_search:
            display_sources = sources  # All web sources
        else:
            display_sources = filter_display_sources(sources, SEARCH_FOLDERS)
        all_sources_for_confidence = sources

        if not display_sources:
            display_sources = DEFAULT_SOURCES.copy()

        # Generate AI response with topic-specific prompt and conversation history
        from prompts import build_system_prompt
        system_prompt = build_system_prompt(question_topic, product_need)

        # Inject user profile context into system prompt
        profile_context = build_profile_context(session.get('user_id'))
        if profile_context:
            system_prompt += (
                "\n\n--- USER CONTEXT ---\n" + profile_context +
                "\nUse this profile to tailor your recommendations. "
                "If the user's question specifies different grass/location, use theirs."
            )

        # Inject spray history context for resistance rotation awareness
        try:
            spray_context = build_spray_history_context(session.get('user_id'))
            if spray_context:
                system_prompt += (
                    "\n\n--- SPRAY HISTORY ---\n" + spray_context +
                    "\nIMPORTANT: When recommending pesticides, check the spray history "
                    "above. Do NOT recommend the same FRAC/HRAC/IRAC group that was "
                    "recently used on the same area. Suggest rotation to a different "
                    "mode of action group. If the user asks 'what should I spray next', "
                    "explicitly reference what they sprayed recently and suggest the "
                    "next rotation partner."
                )
        except Exception as e:
            logger.warning(f"Failed to build spray history context: {e}")

        # Build messages array - skip history if topic changed
        if is_topic_change:
            # Fresh start - no conversation history
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": _build_user_prompt(context, question)}
            ]
        else:
            # Include conversation history for follow-up understanding
            messages = _build_messages_with_history(
                conversation_id, system_prompt, context, question
            )

        _timings['6_pre_llm'] = _time.time() - _t0
        answer = openai_client.chat.completions.create(
            model=Config.CHAT_MODEL,
            messages=messages,
            max_tokens=Config.CHAT_MAX_TOKENS,
            temperature=Config.CHAT_TEMPERATURE,
            timeout=30  # Don't hang longer than 30s during a live demo
        )
        assistant_response = answer.choices[0].message.content
        if not assistant_response:
            assistant_response = "I wasn't able to generate a response. Please try rephrasing your question."
        _timings['7_llm_answer'] = _time.time() - _t0

        # ── PARALLEL: grounding check (API) + hallucination filter + validation (local) ──
        # Grounding is a GPT-4o-mini call (~3-4s). Hallucination filter and validation
        # are local checks (~0s). Run grounding in background while local checks proceed.
        with ThreadPoolExecutor(max_workers=2) as executor:
            grounding_future = executor.submit(
                check_answer_grounding, openai_client, assistant_response, context, question, "gpt-4o-mini"
            )

            # Run local checks while grounding API call is in flight
            hallucination_result = filter_hallucinations(
                answer=assistant_response,
                question=question,
                context=context,
                sources=sources,
                openai_client=openai_client
            )
            if hallucination_result['was_modified']:
                assistant_response = hallucination_result['filtered_answer']
                logging.info(f"Hallucination filter: {len(hallucination_result['issues_found'])} issues found")

            # Knowledge base validation
            assistant_response, validation_result = apply_validation(assistant_response, question)
            if not validation_result['valid']:
                logging.info(f"KB validation: {len(validation_result['issues'])} issues found")

            # Wait for grounding result
            grounding_result = grounding_future.result()

        # Add warning if answer has grounding issues
        assistant_response = add_grounding_warning(assistant_response, grounding_result)

        _timings['8_grounding+checks'] = _time.time() - _t0
        # Calculate confidence with grounding + hallucination filter + validation adjustments
        base_confidence = calculate_confidence_score(all_sources_for_confidence, assistant_response, question)
        confidence = calculate_grounding_confidence(grounding_result, base_confidence)
        # Apply hallucination filter penalty
        confidence -= hallucination_result.get('confidence_penalty', 0)
        # Apply knowledge base validation penalty
        confidence -= validation_result.get('confidence_penalty', 0)
        confidence = max(0, confidence)
        confidence_label = get_confidence_label(confidence)

        # Save response to conversation history
        save_message(
            conversation_id, 'assistant', assistant_response,
            sources=display_sources[:MAX_SOURCES],
            confidence_score=confidence
        )

        # Determine if human review is needed (below 70% threshold)
        needs_review = (
            confidence < 70 or
            not grounding_result.get('grounded', True) or
            len(grounding_result.get('unsupported_claims', [])) > 1 or
            not sources  # No sources found
        )

        # Save query to admin dashboard (all queries, not just rated ones)
        save_query(
            question=question,
            ai_answer=assistant_response,
            sources=display_sources[:MAX_SOURCES],
            confidence=confidence,
            needs_review=needs_review
        )

        response_data = {
            'answer': assistant_response,
            'sources': display_sources[:MAX_SOURCES],
            'images': images,
            'confidence': {'score': confidence, 'label': confidence_label},
            'grounding': {
                'verified': grounding_result.get('grounded', True),
                'issues': grounding_result.get('unsupported_claims', [])
            },
            'needs_review': needs_review
        }

        # Scan AI response for product recommendations
        try:
            mentioned_names = extract_product_names(assistant_response)
            if mentioned_names:
                rec_products = []
                seen_ids = set()
                for name in mentioned_names[:8]:
                    matches = search_products(name, category=None, form_type=None)
                    if matches:
                        p = matches[0]
                        pid = p.get('id', p.get('product_id', ''))
                        if pid and pid not in seen_ids:
                            seen_ids.add(pid)
                            rec_products.append({'id': pid, 'name': p.get('display_name', p.get('name', name))})
                if rec_products:
                    response_data['recommended_products'] = rec_products[:5]
        except Exception:
            pass  # Never break the response pipeline for this

        # Add web search indicator if used
        if used_web_search:
            response_data['web_search_used'] = True
            response_data['web_search_disclaimer'] = format_web_search_disclaimer()

        # Add weather info if available
        if weather_data:
            response_data['weather'] = {
                'location': weather_data.get('location'),
                'summary': format_weather_for_response(weather_data),
                'warnings': get_weather_warnings(weather_data)
            }

        _timings['10_total'] = _time.time() - _t0
        # Log timing breakdown
        prev = 0
        timing_parts = []
        for key in sorted(_timings.keys()):
            elapsed = _timings[key]
            delta = elapsed - prev
            timing_parts.append(f"{key}={delta:.1f}s")
            prev = elapsed
        logging.info(f"⏱️ PIPELINE TIMING [{_timings['10_total']:.1f}s total]: {' | '.join(timing_parts)}")

        return jsonify(response_data)

    except Exception as e:
        # Log the error but never crash - always return something useful
        logger.error(f"Error processing question: {e}", exc_info=True)

        # Return a graceful fallback response
        return jsonify({
            'answer': "I apologize, but I encountered an issue processing your question. Please try rephrasing or ask a different question about turfgrass management.",
            'sources': [],
            'confidence': {'score': 0, 'label': 'Error'},
            'error_logged': True
        })


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

    # Check for explicit "new question" signals
    new_topic_signals = [
        'different question',
        'new question',
        'unrelated',
        'switching topic',
        'change of topic',
        'another question',
        'also wondering',
    ]
    question_lower = question.lower()
    if any(signal in question_lower for signal in new_topic_signals):
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

    # Check for follow-up language that suggests continuation
    followup_signals = [
        'what about',
        'how about',
        'and ',
        'also ',
        'what if',
        'same ',
        'that ',
        'the rate',
        'the product',
        'this disease',
        'those ',
    ]
    if any(question_lower.startswith(signal) or signal in question_lower[:30] for signal in followup_signals):
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
    import sqlite3
    from feedback_system import DB_PATH
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, question, ai_answer, user_rating, user_correction, timestamp, confidence_score
        FROM feedback ORDER BY timestamp DESC LIMIT 100
    ''')
    results = cursor.fetchall()
    conn.close()

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
    from knowledge_builder import IndexTracker, scan_for_pdfs
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
        correction = data.get('correction')

        # Update the existing query with the user's rating
        update_query_rating(
            question=question,
            rating=rating,
            correction=correction
        )

        # Track source quality based on feedback
        # This helps identify which sources lead to good/bad answers
        try:
            from fine_tuning import track_source_quality
            import sqlite3
            from feedback_system import DB_PATH
            import json

            # Get the feedback record to access sources
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, sources FROM feedback
                WHERE question = ?
                ORDER BY timestamp DESC LIMIT 1
            ''', (question,))
            row = cursor.fetchone()
            conn.close()

            if row and row[1]:
                sources = json.loads(row[1])
                track_source_quality(question, sources, rating, row[0])
                logger.debug(f"Tracked source quality for {len(sources)} sources")
        except Exception as sq_error:
            logger.warning(f"Source quality tracking failed: {sq_error}")

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
        from feedback_system import get_feedback_stats
        stats = get_feedback_stats()
        status['services']['database'] = {
            'status': 'connected',
            'total_queries': stats.get('total_feedback', 0)
        }
    except Exception as e:
        status['services']['database'] = {'status': 'error', 'message': str(e)[:100]}
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
    app.run(debug=Config.DEBUG, port=Config.PORT)
