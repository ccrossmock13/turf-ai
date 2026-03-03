"""Spray tracker blueprint — extracted from app.py."""

import math
from datetime import datetime, timedelta
from flask import Blueprint, render_template, jsonify, request, session, Response
from logging_config import logger
from auth import login_required
from profile import get_profile, get_sprayer_for_area
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

spray = Blueprint('spray', __name__)

# -----------------------------------------------------------------------------
# Spray Tracker routes
# -----------------------------------------------------------------------------

@spray.route('/spray-tracker')
@login_required
def spray_tracker_page():
    return render_template('spray-tracker.html')


@spray.route('/api/products/all')
@login_required
def api_products_all():
    """Get combined product list for autocomplete (pesticides + fertilizers + custom)."""
    products = get_all_products(user_id=session['user_id'])
    return jsonify([_serialize_product(p) for p in products])


@spray.route('/api/products/search')
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


@spray.route('/api/custom-products', methods=['POST'])
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


@spray.route('/api/products/<path:product_id>')
@login_required
def api_product_detail(product_id):
    """Get full product details by ID."""
    product = get_product_by_id(product_id, user_id=session['user_id'])
    if not product:
        return jsonify({'error': 'Product not found'}), 404
    return jsonify(product)


# -- User Inventory -----------------------------------------------------------

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


@spray.route('/api/inventory')
@login_required
def api_get_inventory():
    """Get user's inventory products."""
    products = get_user_inventory(session['user_id'])
    return jsonify({'products': [_serialize_product(p) for p in products]})


@spray.route('/api/inventory/ids')
@login_required
def api_get_inventory_ids():
    """Get just the product IDs in the user's inventory (lightweight)."""
    ids = get_inventory_product_ids(session['user_id'])
    return jsonify(list(ids))


@spray.route('/api/inventory', methods=['POST'])
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


@spray.route('/api/inventory/<path:product_id>', methods=['DELETE'])
@login_required
def api_remove_from_inventory(product_id):
    """Remove a product from user's inventory."""
    removed = remove_from_inventory(session['user_id'], product_id)
    if removed:
        return jsonify({'success': True})
    return jsonify({'error': 'Product not in inventory'}), 404


# -- Inventory Quantities -----------------------------------------------------

@spray.route('/api/inventory/quantities')
@login_required
def api_get_inventory_quantities():
    """Get all inventory quantities for user."""
    quantities = get_inventory_quantities(session['user_id'])
    return jsonify(quantities)


@spray.route('/api/inventory/quantities', methods=['PUT'])
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


@spray.route('/api/inventory/deduct', methods=['POST'])
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


# -- Sprayer management -------------------------------------------------------

@spray.route('/api/sprayers', methods=['GET'])
@login_required
def api_get_sprayers():
    """Get all sprayers for the current user."""
    from profile import get_sprayers
    sprayers = get_sprayers(session['user_id'])
    return jsonify(sprayers)


@spray.route('/api/sprayers', methods=['POST'])
@login_required
def api_save_sprayer():
    """Create or update a sprayer."""
    from profile import save_sprayer
    data = request.json or {}
    if not data.get('name') or not data.get('gpa') or not data.get('tank_size'):
        return jsonify({'error': 'name, gpa, and tank_size are required'}), 400
    sprayer_id = save_sprayer(session['user_id'], data)
    return jsonify({'success': True, 'id': sprayer_id})


@spray.route('/api/sprayers/<int:sprayer_id>', methods=['DELETE'])
@login_required
def api_delete_sprayer(sprayer_id):
    """Delete a sprayer."""
    from profile import delete_sprayer
    deleted = delete_sprayer(session['user_id'], sprayer_id)
    if deleted:
        return jsonify({'success': True})
    return jsonify({'error': 'Sprayer not found'}), 404


@spray.route('/api/sprayers/for-area/<area>')
@login_required
def api_sprayer_for_area(area):
    """Get the sprayer assigned to a specific area."""
    sprayer = get_sprayer_for_area(session['user_id'], area)
    if sprayer:
        return jsonify(sprayer)
    return jsonify(None)


# -- Spray Templates ----------------------------------------------------------

@spray.route('/api/spray-templates', methods=['GET'])
@login_required
def api_get_templates():
    """List user's spray program templates."""
    templates = get_templates(session['user_id'])
    return jsonify(templates)


@spray.route('/api/spray-templates', methods=['POST'])
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


@spray.route('/api/spray-templates/<int:template_id>', methods=['DELETE'])
@login_required
def api_delete_template(template_id):
    """Delete a spray template."""
    deleted = delete_template(session['user_id'], template_id)
    if deleted:
        return jsonify({'success': True})
    return jsonify({'error': 'Template not found'}), 404


# -- MOA Rotation Check -------------------------------------------------------

@spray.route('/api/spray/moa-check')
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


# -- Efficacy Tracking --------------------------------------------------------

@spray.route('/api/spray/<int:app_id>/efficacy', methods=['PATCH'])
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


# -- Monthly Nutrient Breakdown -----------------------------------------------

@spray.route('/api/spray/nutrients/monthly')
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


@spray.route('/api/spray', methods=['POST'])
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

    # Audit trail logging
    try:
        from audit import log_action
        log_action('create', 'spray_record', app_id, {
            'date': data['date'],
            'area': area,
            'product_name': app_data['product_name'],
            'product_category': app_data['product_category'],
            'rate': first['rate'],
            'rate_unit': first['rate_unit'],
            'area_acreage': area_acreage,
            'is_tank_mix': is_multi,
            'product_count': len(mix_result['products']),
        }, user_id=user_id)
    except Exception as e:
        logger.warning(f"Audit log failed for spray create: {e}")

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


@spray.route('/api/spray', methods=['GET'])
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


@spray.route('/api/spray/<int:app_id>', methods=['GET'])
@login_required
def api_get_spray_single(app_id):
    """Get a single spray application by ID."""
    application = get_application_by_id(session['user_id'], app_id)
    if not application:
        return jsonify({'error': 'Application not found'}), 404
    return jsonify(application)


@spray.route('/api/spray/<int:app_id>', methods=['DELETE'])
@login_required
def api_delete_spray(app_id):
    """Delete a spray application."""
    deleted = delete_application(session['user_id'], app_id)
    if deleted:
        # Audit trail logging
        try:
            from audit import log_action
            log_action('delete', 'spray_record', app_id, user_id=session['user_id'])
        except Exception as e:
            logger.warning(f"Audit log failed for spray delete: {e}")
        return jsonify({'success': True})
    return jsonify({'error': 'Application not found or not authorized'}), 404


@spray.route('/api/spray/nutrients')
@login_required
def api_spray_nutrients():
    """Get nutrient summary for a year."""
    user_id = session['user_id']
    year = request.args.get('year', str(datetime.now().year))
    area = request.args.get('area')

    summary = get_nutrient_summary(user_id, year, area=area)
    return jsonify(summary)


@spray.route('/api/spray/csv')
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

    response = Response(output.getvalue(), mimetype='text/csv')
    response.headers['Content-Disposition'] = f'attachment; filename=spray_history_{year or "all"}.csv'
    return response


@spray.route('/api/spray/pdf/single/<int:app_id>')
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

    # Derive tank count, then recalculate total as tank_size * tank_count
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


@spray.route('/api/spray/pdf/report')
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


@spray.route('/api/spray/pdf/nutrients')
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


@spray.route('/api/spray/audit-trail', methods=['GET'])
@login_required
def spray_audit_trail():
    """Get audit trail for spray operations.
    ---
    tags:
      - Spray
    parameters:
      - name: start_date
        in: query
        type: string
        format: date
      - name: end_date
        in: query
        type: string
        format: date
      - name: limit
        in: query
        type: integer
        default: 100
    responses:
      200:
        description: List of audit log entries
    """
    from blueprints.helpers import _user_id
    user_id = _user_id()
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    limit = request.args.get('limit', 100, type=int)
    try:
        from audit import get_audit_trail
        entries = get_audit_trail(
            entity_type='spray_record',
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )
        return jsonify(entries)
    except Exception as e:
        logger.error(f"Error getting spray audit trail: {e}")
        return jsonify({'error': str(e)}), 500


@spray.route('/api/spray/export', methods=['GET'])
@login_required
def export_spray():
    """Export spray application records as CSV or PDF.
    ---
    tags:
      - Spray
    parameters:
      - name: format
        in: query
        type: string
        enum: [csv, pdf]
        default: csv
      - name: year
        in: query
        type: integer
    responses:
      200:
        description: File download
    """
    from blueprints.helpers import _user_id
    user_id = _user_id()
    fmt = request.args.get('format', 'csv').lower()
    year = request.args.get('year', type=int)
    try:
        applications = get_applications(user_id, year=year)
        columns = [
            ('date', 'Date'),
            ('area', 'Area'),
            ('product_name', 'Product'),
            ('rate', 'Rate'),
            ('rate_unit', 'Rate Unit'),
            ('area_acreage', 'Acreage'),
            ('weather_temp', 'Temp (F)'),
            ('weather_wind', 'Wind'),
            ('weather_conditions', 'Conditions'),
            ('notes', 'Notes'),
        ]
        from datetime import datetime as _dt
        date_str = _dt.now().strftime('%Y-%m-%d')
        if fmt == 'pdf':
            from export_service import export_pdf
            return export_pdf(applications, 'Spray Application Records', columns, f'spray_records_{date_str}.pdf')
        from export_service import export_csv
        return export_csv(applications, columns, f'spray_records_{date_str}.csv')
    except Exception as e:
        logger.error(f"Error exporting spray records: {e}")
        return jsonify({'error': str(e)}), 500
