"""
Spray tracker module for Greenside AI.
Handles spray application logging, rate calculations, nutrient tracking, and CRUD.
"""

import json
import math
import sqlite3
import os
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

DATA_DIR = os.environ.get('DATA_DIR', 'data' if os.path.exists('data') else '.')
DB_PATH = os.path.join(DATA_DIR, 'greenside_conversations.db')

# Constants
ACRE_TO_1000SQFT = 43.56
FL_OZ_PER_GALLON = 128.0
OZ_PER_LB = 16.0
VALID_AREAS = ['greens', 'fairways', 'tees', 'rough']

# Default N budgets (lbs N per 1000 sq ft per year) if not set in profile
DEFAULT_N_BUDGETS = {
    'greens': 4.0,
    'fairways': 3.0,
    'tees': 3.5,
    'rough': 2.0
}

# Nutrient keys tracked (NPK only)
NUTRIENT_KEYS = ['N', 'P2O5', 'K2O']


# ---------------------------------------------------------------------------
# Calculation engine
# ---------------------------------------------------------------------------

def calculate_total_product(rate, rate_unit, area_acreage):
    """Calculate total product needed for an area.

    Args:
        rate: Application rate (number)
        rate_unit: Rate unit string (e.g., "fl oz/1000 sq ft", "lbs/acre")
        area_acreage: Area in acres

    Returns:
        dict with 'total', 'unit', 'area_1000sqft'
    """
    area_1000sqft = area_acreage * ACRE_TO_1000SQFT

    if '/1000' in rate_unit:
        total = rate * area_1000sqft
    elif '/acre' in rate_unit:
        total = rate * area_acreage
    else:
        total = rate * area_1000sqft  # Default to per 1000

    # Determine base unit
    if 'fl oz' in rate_unit:
        unit = 'fl oz'
        # Convert to gallons if large
        if total > 256:  # 2+ gallons
            return {'total': round(total / FL_OZ_PER_GALLON, 2), 'unit': 'gallons',
                    'total_base': round(total, 2), 'unit_base': 'fl oz',
                    'area_1000sqft': round(area_1000sqft, 2)}
    elif 'oz' in rate_unit and 'fl' not in rate_unit:
        unit = 'oz'
        # Convert to lbs if large
        if total > 32:  # 2+ lbs
            return {'total': round(total / OZ_PER_LB, 2), 'unit': 'lbs',
                    'total_base': round(total, 2), 'unit_base': 'oz',
                    'area_1000sqft': round(area_1000sqft, 2)}
    elif 'lbs' in rate_unit or 'lb' in rate_unit:
        unit = 'lbs'
    else:
        unit = rate_unit.split('/')[0].strip()

    return {'total': round(total, 2), 'unit': unit,
            'total_base': round(total, 2), 'unit_base': unit,
            'area_1000sqft': round(area_1000sqft, 2)}


def calculate_carrier_volume(gpa, area_acreage):
    """Calculate total carrier (water) volume.

    Args:
        gpa: Gallons per acre
        area_acreage: Area in acres

    Returns:
        Total gallons (float)
    """
    if not gpa or not area_acreage:
        return None
    return round(gpa * area_acreage, 1)


def calculate_nutrients(product, rate, rate_unit, area_acreage):
    """Calculate nutrients applied from a fertilizer application.

    Args:
        product: Product dict from product_loader (must have 'npk', 'secondary_nutrients')
        rate: Application rate
        rate_unit: Rate unit string
        area_acreage: Area in acres

    Returns:
        dict with per_1000 and total for each nutrient, or None if not a fertilizer
    """
    npk = product.get('npk')
    if not npk:
        return None

    area_1000sqft = area_acreage * ACRE_TO_1000SQFT

    # Step 1: Convert rate to lbs product per 1000 sq ft
    if product.get('form_type') == 'liquid':
        density = product.get('density_lbs_per_gallon')
        if not density:
            density = 10.0  # Reasonable default for liquid fertilizers

        # Convert rate to gallons, then to lbs via density
        if 'gal' in rate_unit:
            rate_gal = rate
        elif 'fl oz' in rate_unit:
            rate_gal = rate / FL_OZ_PER_GALLON
        elif 'oz' in rate_unit:
            # Weight oz ≈ volume oz for liquid products
            rate_gal = rate / FL_OZ_PER_GALLON
        else:
            rate_gal = rate / FL_OZ_PER_GALLON

        if '/1000' in rate_unit:
            lbs_per_1000 = rate_gal * density
        elif '/acre' in rate_unit:
            lbs_per_1000 = (rate_gal * density) / ACRE_TO_1000SQFT
        else:
            lbs_per_1000 = rate_gal * density
    else:
        # Granular: rate is in lbs (or oz)
        if 'oz' in rate_unit and 'fl' not in rate_unit:
            rate_lbs = rate / OZ_PER_LB
        else:
            rate_lbs = rate

        if '/1000' in rate_unit:
            lbs_per_1000 = rate_lbs
        elif '/acre' in rate_unit:
            lbs_per_1000 = rate_lbs / ACRE_TO_1000SQFT
        else:
            lbs_per_1000 = rate_lbs

    # Step 2: Calculate nutrient amounts (N, P, K only)
    nutrients = {}
    nutrient_map = {
        'N': npk[0] if len(npk) > 0 else 0,
        'P2O5': npk[1] if len(npk) > 1 else 0,
        'K2O': npk[2] if len(npk) > 2 else 0,
    }

    for nutrient, pct in nutrient_map.items():
        per_1000 = lbs_per_1000 * (pct / 100.0)
        total = per_1000 * area_1000sqft
        nutrients[nutrient] = {
            'per_1000': round(per_1000, 4),
            'total': round(total, 2),
            'pct': pct
        }

    return nutrients


def calculate_tank_mix(products_data, area_acreage, carrier_gpa, tank_size=None, tank_count_override=None):
    """Calculate totals for a tank mix (multiple products applied together).

    Args:
        products_data: list of dicts, each with:
            - product: product dict from product_loader
            - rate: application rate
            - rate_unit: rate unit string
        area_acreage: area in acres
        carrier_gpa: gallons per acre (shared across all products)
        tank_size: optional tank size in gallons for tank count calc
        tank_count_override: optional tank count from frontend (takes priority)

    Returns:
        dict with per-product calculations + shared carrier + tank count
    """
    results = []
    combined_nutrients = {k: {'per_1000': 0.0, 'total': 0.0} for k in NUTRIENT_KEYS}
    has_nutrients = False

    for pd in products_data:
        product = pd['product']
        rate = pd['rate']
        rate_unit = pd['rate_unit']

        total_result = calculate_total_product(rate, rate_unit, area_acreage)
        nutrients = calculate_nutrients(product, rate, rate_unit, area_acreage)

        # Accumulate nutrients
        if nutrients:
            has_nutrients = True
            for key in NUTRIENT_KEYS:
                if key in nutrients:
                    combined_nutrients[key]['per_1000'] += nutrients[key]['per_1000']
                    combined_nutrients[key]['total'] += nutrients[key]['total']

        results.append({
            'product_id': product['id'],
            'product_name': product['display_name'],
            'product_category': product['category'],
            'rate': rate,
            'rate_unit': rate_unit,
            'total_product': total_result['total'],
            'total_product_unit': total_result['unit'],
            'nutrients_applied': nutrients
        })

    # Total amount = tank size × number of tanks
    tank_count = tank_count_override or None
    if not tank_count and tank_size and tank_size > 0 and carrier_gpa and area_acreage:
        tank_count = math.ceil((carrier_gpa * area_acreage) / tank_size)
    total_carrier = None
    if tank_count and tank_size and tank_size > 0:
        total_carrier = round(tank_size * tank_count, 1)

    # Round combined nutrients
    if has_nutrients:
        for key in NUTRIENT_KEYS:
            combined_nutrients[key]['per_1000'] = round(combined_nutrients[key]['per_1000'], 4)
            combined_nutrients[key]['total'] = round(combined_nutrients[key]['total'], 2)
    else:
        combined_nutrients = None

    return {
        'products': results,
        'total_carrier_gallons': total_carrier,
        'tank_count': tank_count,
        'combined_nutrients': combined_nutrients
    }


# ---------------------------------------------------------------------------
# CRUD operations
# ---------------------------------------------------------------------------

def save_application(user_id, data):
    """Save a spray application record. Returns the new record ID.
    Supports both single-product and tank-mix (products_json) records.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    nutrients_str = json.dumps(data.get('nutrients_applied')) if data.get('nutrients_applied') else None
    products_json_str = json.dumps(data.get('products_json')) if data.get('products_json') else None

    cursor.execute('''
        INSERT INTO spray_applications (
            user_id, date, area, product_id, product_name, product_category,
            rate, rate_unit, area_acreage,
            carrier_volume_gpa, total_product, total_product_unit,
            total_carrier_gallons, nutrients_applied,
            weather_temp, weather_wind, weather_conditions, notes,
            products_json, application_method
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        user_id,
        data['date'],
        data['area'],
        data['product_id'],
        data['product_name'],
        data['product_category'],
        data['rate'],
        data['rate_unit'],
        data['area_acreage'],
        data.get('carrier_volume_gpa'),
        data.get('total_product'),
        data.get('total_product_unit'),
        data.get('total_carrier_gallons'),
        nutrients_str,
        data.get('weather_temp'),
        data.get('weather_wind'),
        data.get('weather_conditions'),
        data.get('notes'),
        products_json_str,
        data.get('application_method')
    ))

    app_id = cursor.lastrowid
    conn.commit()
    conn.close()
    logger.info(f"Spray application saved: {app_id} for user {user_id}")
    return app_id


def get_applications(user_id, area=None, year=None, start_date=None, end_date=None, limit=200):
    """Get spray applications with optional filters."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = 'SELECT * FROM spray_applications WHERE user_id = ?'
    params = [user_id]

    if area and area in VALID_AREAS:
        query += ' AND area = ?'
        params.append(area)

    if year:
        query += ' AND date LIKE ?'
        params.append(f'{year}-%')

    if start_date:
        query += ' AND date >= ?'
        params.append(start_date)

    if end_date:
        query += ' AND date <= ?'
        params.append(end_date)

    query += ' ORDER BY date DESC LIMIT ?'
    params.append(limit)

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    results = []
    for row in rows:
        r = dict(row)
        # Parse nutrients JSON
        if r.get('nutrients_applied'):
            try:
                r['nutrients_applied'] = json.loads(r['nutrients_applied'])
            except (json.JSONDecodeError, TypeError):
                r['nutrients_applied'] = None
        # Parse products_json for tank mixes
        if r.get('products_json'):
            try:
                r['products_json'] = json.loads(r['products_json'])
            except (json.JSONDecodeError, TypeError):
                r['products_json'] = None
        results.append(r)

    return results


def get_application_by_id(user_id, app_id):
    """Get a single application by ID (with ownership check)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        'SELECT * FROM spray_applications WHERE id = ? AND user_id = ?',
        (app_id, user_id)
    )
    row = cursor.fetchone()
    conn.close()

    if row:
        r = dict(row)
        if r.get('nutrients_applied'):
            try:
                r['nutrients_applied'] = json.loads(r['nutrients_applied'])
            except (json.JSONDecodeError, TypeError):
                r['nutrients_applied'] = None
        if r.get('products_json'):
            try:
                r['products_json'] = json.loads(r['products_json'])
            except (json.JSONDecodeError, TypeError):
                r['products_json'] = None
        return r
    return None


def delete_application(user_id, app_id):
    """Delete a spray application (with ownership check). Returns True if deleted."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        'DELETE FROM spray_applications WHERE id = ? AND user_id = ?',
        (app_id, user_id)
    )
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def get_nutrient_summary(user_id, year, area=None):
    """Get aggregated nutrient totals per area for a year.

    Returns dict with per-area nutrient totals, per-1000 rates, and N budget tracking.
    """
    from profile import get_profile

    profile = get_profile(user_id)
    applications = get_applications(user_id, area=area, year=year, limit=5000)

    areas_data = {}
    for area_name in VALID_AREAS:
        if area and area_name != area:
            continue

        # Get acreage from profile
        acreage_key = f'{area_name}_acreage'
        acreage = (profile or {}).get(acreage_key) if profile else None

        # Filter applications for this area
        area_apps = [a for a in applications if a['area'] == area_name]

        # Aggregate nutrients (handles both single-product and tank-mix records)
        totals = {k: 0.0 for k in NUTRIENT_KEYS}
        for app in area_apps:
            # For tank mixes, use products_json nutrients if available
            if app.get('products_json') and isinstance(app['products_json'], list):
                for mix_product in app['products_json']:
                    p_nutrients = mix_product.get('nutrients_applied')
                    if p_nutrients:
                        for key in NUTRIENT_KEYS:
                            n_data = p_nutrients.get(key)
                            if isinstance(n_data, dict):
                                totals[key] += n_data.get('total', 0)
                            elif isinstance(n_data, (int, float)):
                                totals[key] += n_data
            else:
                # Single-product record — use top-level nutrients_applied
                nutrients = app.get('nutrients_applied')
                if nutrients:
                    for key in NUTRIENT_KEYS:
                        n_data = nutrients.get(key)
                        if isinstance(n_data, dict):
                            totals[key] += n_data.get('total', 0)
                        elif isinstance(n_data, (int, float)):
                            totals[key] += n_data

        # Calculate per-1000 rates
        per_1000 = {}
        if acreage and acreage > 0:
            area_1000sqft = acreage * ACRE_TO_1000SQFT
            for key in NUTRIENT_KEYS:
                per_1000[key] = round(totals[key] / area_1000sqft, 3) if area_1000sqft > 0 else 0
        else:
            per_1000 = {k: 0 for k in NUTRIENT_KEYS}

        # N budget tracking
        n_target = DEFAULT_N_BUDGETS.get(area_name, 3.0)
        # Could be overridden by profile's annual_n_budget
        if profile and profile.get('annual_n_budget'):
            try:
                budget_data = json.loads(profile['annual_n_budget'])
                if isinstance(budget_data, dict) and area_name in budget_data:
                    n_target = float(budget_data[area_name])
            except (json.JSONDecodeError, TypeError, ValueError):
                pass

        n_applied = per_1000.get('N', 0)
        n_pct = round((n_applied / n_target) * 100, 1) if n_target > 0 else 0

        areas_data[area_name] = {
            'acreage': acreage,
            'applications_count': len(area_apps),
            'totals': {k: round(v, 2) for k, v in totals.items()},
            'per_1000': per_1000,
            'n_budget': {
                'target': n_target,
                'applied': round(n_applied, 3),
                'remaining': round(max(0, n_target - n_applied), 3),
                'pct': n_pct
            }
        }

    return {
        'year': year,
        'areas': areas_data
    }


# ---------------------------------------------------------------------------
# AI Context Builder
# ---------------------------------------------------------------------------

def build_spray_history_context(user_id, days_back=90):
    """Build a context string of recent spray applications for AI prompt injection.

    Returns a string summarizing recent spray history with MOA rotation guidance.
    Returns empty string if no spray history exists.
    """
    from product_loader import get_product_by_id

    cutoff = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
    applications = get_applications(user_id, start_date=cutoff, limit=500)

    if not applications:
        return ''

    # Group by area
    by_area = {}
    for app in applications:
        area = app['area']
        if area not in by_area:
            by_area[area] = []
        by_area[area].append(app)

    parts = [f'RECENT SPRAY HISTORY (last {days_back} days):']

    # Track MOA codes used per area for rotation advice
    moa_by_area = {}  # area -> [{code, date, product_name}, ...]

    for area in VALID_AREAS:
        area_apps = by_area.get(area, [])
        if not area_apps:
            continue

        parts.append(f'\n{area.title()}:')
        moa_by_area[area] = []

        for app in area_apps[:15]:  # Limit to 15 most recent per area
            # Handle tank mix records
            if app.get('products_json') and isinstance(app['products_json'], list):
                mix_names = [p.get('product_name', '?') for p in app['products_json']]
                line = f"- {app['date']}: Tank Mix ({', '.join(mix_names)})"
                parts.append(line)

                # Extract MOA codes from each product in the mix
                for mp in app['products_json']:
                    product = get_product_by_id(mp.get('product_id'))
                    if product:
                        _extract_moa(product, app['date'], mp.get('product_name', ''), moa_by_area[area])
            else:
                # Single product record
                product = get_product_by_id(app['product_id'])
                line_parts = [f"- {app['date']}: {app['product_name']}"]

                if product:
                    ai = product.get('active_ingredient')
                    if ai:
                        moa_str = _get_moa_string(product)
                        if moa_str:
                            line_parts.append(f"({ai}, {moa_str})")
                        else:
                            line_parts.append(f"({ai})")
                        _extract_moa(product, app['date'], app['product_name'], moa_by_area[area])

                line_parts.append(f"at {app['rate']} {app['rate_unit']}")
                parts.append(' '.join(line_parts))

    # Add rotation advice
    rotation_notes = []
    for area, moas in moa_by_area.items():
        if not moas:
            continue
        # Find most recently used codes (deduplicated)
        recent_codes = []
        seen = set()
        for m in moas:
            if m['code'] not in seen:
                seen.add(m['code'])
                recent_codes.append(m)
            if len(recent_codes) >= 3:
                break

        for m in recent_codes:
            rotation_notes.append(
                f"- {m['code']} used on {area} on {m['date']} ({m['name']}). "
                f"Avoid recommending {m['code']} products for {area} — suggest rotation."
            )

    if rotation_notes:
        parts.append('\nRESISTANCE ROTATION GUIDANCE:')
        parts.extend(rotation_notes)
        parts.append(
            'When recommending fungicides/herbicides/insecticides, '
            'rotate to a DIFFERENT mode of action group than what was '
            'recently used on that area.'
        )

    # Add nutrient summary if any fertilizers were applied
    fert_apps = [a for a in applications if a.get('nutrients_applied')]
    if fert_apps:
        parts.append('\nRECENT NUTRIENT APPLICATIONS:')
        for area in VALID_AREAS:
            area_ferts = [a for a in fert_apps if a['area'] == area]
            if area_ferts:
                total_n = 0
                for a in area_ferts:
                    nutrients = a['nutrients_applied']
                    if isinstance(nutrients, str):
                        try:
                            nutrients = json.loads(nutrients)
                        except Exception:
                            continue
                    n_data = nutrients.get('N', {})
                    if isinstance(n_data, dict):
                        total_n += n_data.get('per_1000', 0)
                if total_n > 0:
                    parts.append(
                        f"- {area.title()}: {total_n:.3f} lbs N/1000 sq ft "
                        f"applied in last {days_back} days"
                    )

    return '\n'.join(parts)


def _get_moa_string(product):
    """Get the MOA code string for a product (FRAC, HRAC, or IRAC)."""
    frac = product.get('frac_code')
    hrac = product.get('hrac_group')
    irac = product.get('irac_group')
    if frac:
        return f"FRAC {frac}"
    elif hrac:
        return f"HRAC {hrac}"
    elif irac:
        return f"IRAC {irac}"
    return None


def _extract_moa(product, date, name, moa_list):
    """Extract MOA code from a product and add to the tracking list."""
    moa_str = _get_moa_string(product)
    if moa_str:
        # Handle combo MOA codes like "FRAC 11 + 3"
        if '+' in str(product.get('frac_code', '')):
            for code in str(product['frac_code']).split('+'):
                moa_list.append({'code': f'FRAC {code.strip()}', 'date': date, 'name': name})
        elif '+' in str(product.get('hrac_group', '')):
            for code in str(product['hrac_group']).split('+'):
                moa_list.append({'code': f'HRAC {code.strip()}', 'date': date, 'name': name})
        elif '+' in str(product.get('irac_group', '')):
            for code in str(product['irac_group']).split('+'):
                moa_list.append({'code': f'IRAC {code.strip()}', 'date': date, 'name': name})
        else:
            moa_list.append({'code': moa_str, 'date': date, 'name': name})
