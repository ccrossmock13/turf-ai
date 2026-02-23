"""
Product loader for spray tracker.
Merges pesticides (products.json), fertilizers (fertilizers.json),
20+ brand-specific product catalogs, and user custom products
into a unified product interface.

Supports ~1,100+ professional turf products across all major brands.
"""

import json
import os
import re
import sqlite3
import logging

logger = logging.getLogger(__name__)

DATA_DIR = os.environ.get('DATA_DIR', 'data' if os.path.exists('data') else '.')
DB_PATH = os.path.join(DATA_DIR, 'greenside_conversations.db')
KNOWLEDGE_DIR = os.path.join(os.path.dirname(__file__), 'knowledge')

# Module-level caches
_pesticide_cache = None
_fertilizer_cache = None
_brand_cache = None

# ---------------------------------------------------------------------------
# Brand file configuration
# Each tuple: (filename, schema_type, brand_prefix)
#   schema_type: 'flat' = fertilizer-style flat dict
#                'nested' = pesticide-style nested by category
#                'mixed' = LESCO-style (flat sections + pesticide sections)
# ---------------------------------------------------------------------------

BRAND_FILES = [
    # Pesticide-schema files (nested by category → active_ingredient → product)
    ('syngenta_products.json', 'nested', 'syngenta'),
    ('envu_products.json', 'nested', 'envu'),
    ('nufarm_products.json', 'nested', 'nufarm'),
    ('basf_turf_products.json', 'nested', 'basf'),
    ('fmc_products.json', 'nested', 'fmc'),
    ('corteva_products.json', 'nested', 'corteva'),
    ('atticus_turf_products.json', 'nested', 'atticus'),
    ('quali_pro_products.json', 'nested', 'qualipro'),
    ('pbi_gordon_products.json', 'nested', 'pbigordon'),

    # Fertilizer-schema files (flat product dicts, skip 'metadata')
    ('floratine_products.json', 'flat', 'floratine'),
    ('pfc_products.json', 'flat', 'pfc'),
    ('grigg_brothers_products.json', 'flat', 'grigg'),
    ('foliarpak_products.json', 'flat', 'foliarpak'),
    ('andersons_products.json', 'flat', 'andersons'),
    ('harrells_products.json', 'flat', 'harrells'),
    ('lebanon_products.json', 'flat', 'lebanon'),
    ('mitchell_products.json', 'flat', 'mitchell'),
    ('aquatrols_products.json', 'flat', 'aquatrols'),
    ('aquaaid_products.json', 'flat', 'aquaaid'),
    ('simplot_products.json', 'flat', 'simplot'),
    ('plant_marvel_products.json', 'flat', 'plantmarvel'),

    # Mixed schema (LESCO: all sections use flat product dicts)
    ('lesco_products.json', 'mixed', 'lesco'),
]

# Category keys that indicate pesticide-nested sections
PESTICIDE_CATEGORIES = {
    'fungicides': 'fungicide',
    'herbicides': 'herbicide',
    'insecticides': 'insecticide',
    'pgrs': 'pgr',
    'pgr_growth_regulators': 'pgr',
    'nematicides': 'nematicide',
    'adjuvants': 'adjuvant',
    'combination_products': 'combination',
    'specialty_iron_products': 'specialty',
}

# All known brand prefixes (for get_product_by_id routing)
BRAND_PREFIXES = {entry[2] for entry in BRAND_FILES}


# ---------------------------------------------------------------------------
# Data loading (cached)
# ---------------------------------------------------------------------------

def _load_pesticides():
    """Load and normalize pesticides from products.json (original database)."""
    global _pesticide_cache
    if _pesticide_cache is not None:
        return _pesticide_cache

    path = os.path.join(KNOWLEDGE_DIR, 'products.json')
    try:
        with open(path) as f:
            data = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load products.json: {e}")
        _pesticide_cache = {}
        return _pesticide_cache

    products = {}
    category_map = {
        'fungicides': 'fungicide',
        'herbicides': 'herbicide',
        'insecticides': 'insecticide',
        'pgrs': 'pgr'
    }

    for category_key, category_name in category_map.items():
        cat_data = data.get(category_key, {})
        for active_ingredient, info in cat_data.items():
            pid = f"pesticide:{category_key}:{active_ingredient}"
            # Parse rate from string like "0.2-0.4 oz/1000 sq ft"
            default_rate, rate_unit = _parse_rate_string(info.get('rates', {}))
            trade_names = info.get('trade_names', [])
            display_name = trade_names[0] if trade_names else active_ingredient.replace('_', ' ').title()

            # Normalize oz → fl oz for liquid pesticides
            final_rate_unit = rate_unit or 'fl oz/1000 sq ft'
            if final_rate_unit and 'oz' in final_rate_unit and 'fl oz' not in final_rate_unit:
                final_rate_unit = final_rate_unit.replace('oz', 'fl oz')

            products[pid] = {
                'id': pid,
                'display_name': display_name,
                'brand': info.get('manufacturer', ''),
                'category': category_name,
                'active_ingredient': active_ingredient.replace('_', ' '),
                'form_type': 'liquid',  # Most pesticides are liquid sprays
                'npk': None,
                'secondary_nutrients': None,
                'default_rate': default_rate,
                'rate_unit': final_rate_unit,
                'density_lbs_per_gallon': None,
                'trade_names': trade_names,
                'frac_code': info.get('frac_code'),
                'hrac_group': info.get('hrac_group'),
                'irac_group': info.get('irac_group'),
                'targets': info.get('diseases') or info.get('target_weeds') or info.get('target_pests') or [],
                'notes': info.get('note', '')
            }

    _pesticide_cache = products
    logger.info(f"Loaded {len(products)} pesticide products from products.json")
    return products


def _parse_rate_string(rates_dict):
    """Parse rate info from products.json format.
    Input: {"foliar": "0.2-0.4 oz/1000 sq ft"} or {"standard": "3.5-5 fl oz/1000 sq ft"}
    Returns: (default_rate_float, rate_unit_string)
    """
    if not rates_dict:
        return None, None

    # Prefer 'standard' key, then first available
    rate_str = rates_dict.get('standard') or next(iter(rates_dict.values()), '')
    if not rate_str:
        return None, None

    # Extract number(s) and unit
    # Match patterns like "0.2-0.4 oz/1000 sq ft" or "3.5 fl oz/1000 sq ft"
    match = re.match(r'([\d.]+)(?:-([\d.]+))?\s*(.+)', str(rate_str))
    if not match:
        return None, str(rate_str)

    low = float(match.group(1))
    high = float(match.group(2)) if match.group(2) else low
    unit = match.group(3).strip()

    # Use midpoint of range as default
    default_rate = round((low + high) / 2, 2)
    return default_rate, unit


def _load_fertilizers():
    """Load fertilizers from fertilizers.json (original database)."""
    global _fertilizer_cache
    if _fertilizer_cache is not None:
        return _fertilizer_cache

    path = os.path.join(KNOWLEDGE_DIR, 'fertilizers.json')
    try:
        with open(path) as f:
            data = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load fertilizers.json: {e}")
        _fertilizer_cache = {}
        return _fertilizer_cache

    products = {}
    for fert_id, info in data.get('fertilizers', {}).items():
        pid = f"fertilizer:{fert_id}"
        brand = info.get('brand', '')
        product_name = info.get('product_name', fert_id.replace('_', ' ').title())
        products[pid] = {
            'id': pid,
            'display_name': _make_display_name(brand, product_name),
            'brand': info.get('brand', ''),
            'category': info.get('category', 'fertilizer'),
            'active_ingredient': None,
            'form_type': info.get('type', 'granular'),
            'npk': info.get('npk'),
            'secondary_nutrients': info.get('secondary_nutrients'),
            'default_rate': info.get('default_rate'),
            'rate_unit': info.get('rate_unit', 'lbs/1000 sq ft'),
            'density_lbs_per_gallon': info.get('density_lbs_per_gallon'),
            'trade_names': [],
            'frac_code': None,
            'hrac_group': None,
            'irac_group': None,
            'targets': [],
            'notes': info.get('application_notes', '')
        }

    _fertilizer_cache = products
    logger.info(f"Loaded {len(products)} fertilizer products from fertilizers.json")
    return products


def _load_brand_files():
    """Load all brand-specific product catalogs from knowledge/ directory.
    Handles three schema types: flat (fertilizer), nested (pesticide), and mixed.
    Returns dict of product_id -> product_dict.
    """
    global _brand_cache
    if _brand_cache is not None:
        return _brand_cache

    all_products = {}
    total_loaded = 0

    for filename, schema_type, prefix in BRAND_FILES:
        path = os.path.join(KNOWLEDGE_DIR, filename)
        if not os.path.exists(path):
            logger.warning(f"Brand file not found: {filename}")
            continue

        try:
            with open(path) as f:
                data = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load {filename}: {e}")
            continue

        count_before = len(all_products)

        if schema_type == 'flat':
            _load_flat_brand(data, prefix, all_products)
        elif schema_type == 'nested':
            _load_nested_brand(data, prefix, all_products)
        elif schema_type == 'mixed':
            _load_mixed_brand(data, prefix, all_products)

        count_after = len(all_products)
        brand_count = count_after - count_before
        total_loaded += brand_count
        logger.info(f"Loaded {brand_count} products from {filename}")

    _brand_cache = all_products
    logger.info(f"Total brand products loaded: {total_loaded} from {len(BRAND_FILES)} files")
    return all_products


def _make_display_name(brand, product_name):
    """Build display name, avoiding duplication like 'LESCO LESCO 46-0-0'."""
    if not brand:
        return product_name
    # If product_name already starts with the brand, don't double it
    if product_name.lower().startswith(brand.lower()):
        return product_name
    return f"{brand} {product_name}"


def _load_flat_brand(data, prefix, products):
    """Load a flat fertilizer-schema brand file.
    Structure: { "metadata": {...}, "product_key": { "brand", "product_name", "npk", ... }, ... }
    """
    for product_key, info in data.items():
        # Skip metadata and non-dict entries
        if product_key == 'metadata' or not isinstance(info, dict):
            continue
        # Skip if it looks like a nested category (contains sub-dicts with trade_names)
        if 'product_name' not in info and 'brand' not in info:
            continue

        pid = f"{prefix}:{product_key}"
        brand = info.get('brand', prefix.title())
        product_name = info.get('product_name', product_key.replace('_', ' ').title())

        products[pid] = {
            'id': pid,
            'display_name': _make_display_name(brand, product_name),
            'brand': brand,
            'category': info.get('category', 'fertilizer'),
            'active_ingredient': info.get('active_ingredient') or info.get('active_components'),
            'form_type': info.get('type', 'granular'),
            'npk': info.get('npk'),
            'secondary_nutrients': info.get('secondary_nutrients'),
            'default_rate': info.get('default_rate'),
            'rate_unit': info.get('rate_unit', 'lbs/1000 sq ft'),
            'density_lbs_per_gallon': info.get('density_lbs_per_gallon'),
            'trade_names': [],
            'frac_code': None,
            'hrac_group': None,
            'irac_group': None,
            'targets': [],
            'notes': info.get('application_notes', '') or info.get('notes', ''),
            'sgn': info.get('sgn'),
        }


def _load_nested_brand(data, prefix, products):
    """Load a nested pesticide-schema brand file.
    Structure: { "metadata": {...}, "fungicides": { "active_key": { "trade_names", ... } }, ... }
    """
    for category_key, cat_data in data.items():
        if category_key == 'metadata' or not isinstance(cat_data, dict):
            continue
        # Skip cross-reference / non-product sections
        if 'cross_reference' in category_key or 'reference' in category_key:
            continue

        # Determine category name
        category_name = PESTICIDE_CATEGORIES.get(category_key, category_key.rstrip('s'))

        for active_key, info in cat_data.items():
            if not isinstance(info, dict):
                continue

            pid = f"{prefix}:{category_key}:{active_key}"
            trade_names = info.get('trade_names', [])
            manufacturer = info.get('manufacturer', prefix.replace('_', ' ').title())

            # Build display name from first trade name or active ingredient
            if trade_names:
                display_name = trade_names[0]
            else:
                display_name = active_key.replace('_', ' ').title()

            # Parse rates
            default_rate, rate_unit = _parse_rate_string(info.get('rates', {}))

            # Determine form type from formulations or rates
            form_type = _detect_form_type(info)

            # Extract active ingredients as string
            ai = info.get('active_ingredients', {})
            if isinstance(ai, dict):
                ai_str = ', '.join(ai.keys()).replace('_', ' ')
            elif isinstance(ai, str):
                ai_str = ai
            else:
                ai_str = active_key.replace('_', ' ')

            # Normalize oz → fl oz for liquid products
            final_rate_unit = rate_unit or 'fl oz/1000 sq ft'
            if form_type == 'liquid' and final_rate_unit and 'oz' in final_rate_unit and 'fl oz' not in final_rate_unit:
                final_rate_unit = final_rate_unit.replace('oz', 'fl oz')

            products[pid] = {
                'id': pid,
                'display_name': display_name,
                'brand': manufacturer,
                'category': category_name,
                'active_ingredient': ai_str,
                'form_type': form_type,
                'npk': None,
                'secondary_nutrients': None,
                'default_rate': default_rate,
                'rate_unit': final_rate_unit,
                'density_lbs_per_gallon': None,
                'trade_names': trade_names,
                'frac_code': info.get('frac_code'),
                'hrac_group': info.get('hrac_group'),
                'irac_group': info.get('irac_group') or info.get('irac_class'),
                'targets': (info.get('diseases') or info.get('target_weeds')
                           or info.get('target_pests') or []),
                'notes': info.get('note', '') or info.get('notes', ''),
            }


def _load_mixed_brand(data, prefix, products):
    """Load a mixed-schema brand file (like LESCO).
    All sections use flat product dicts regardless of category.
    Structure: { "metadata": {...}, "granular_fertilizers": { flat... }, "herbicides": { flat... }, ... }
    """
    for section_key, section_data in data.items():
        if section_key == 'metadata' or not isinstance(section_data, dict):
            continue

        # All LESCO sections use the flat fertilizer schema with brand/product_name
        for product_key, info in section_data.items():
            if not isinstance(info, dict):
                continue

            pid = f"{prefix}:{product_key}"
            brand = info.get('brand', prefix.upper())
            product_name = info.get('product_name', product_key.replace('_', ' ').title())

            products[pid] = {
                'id': pid,
                'display_name': _make_display_name(brand, product_name),
                'brand': brand,
                'category': info.get('category', 'fertilizer'),
                'active_ingredient': info.get('active_ingredient'),
                'form_type': info.get('type', 'granular'),
                'npk': info.get('npk'),
                'secondary_nutrients': info.get('secondary_nutrients'),
                'default_rate': info.get('default_rate'),
                'rate_unit': info.get('rate_unit', 'lbs/1000 sq ft'),
                'density_lbs_per_gallon': info.get('density_lbs_per_gallon'),
                'trade_names': [],
                'frac_code': None,
                'hrac_group': None,
                'irac_group': None,
                'targets': [],
                'notes': info.get('application_notes', '') or info.get('notes', ''),
                'sgn': info.get('sgn'),
            }


def _detect_form_type(info):
    """Detect form type (liquid/granular) from nested pesticide product info.
    Default to liquid unless the product is ONLY granular.
    """
    formulations = info.get('formulations', {})
    if formulations:
        form_keys = set(k.lower() for k in formulations.keys())
        has_liquid = any(k in form_keys for k in ('sc', 'ec', 'tl', 'se', 'sl', 'wg',
                                                    'liquid', 'emulsion_in_water'))
        has_granular = 'g' in form_keys or 'granular' in form_keys
        # If ONLY granular formulation(s), it's granular
        if has_granular and not has_liquid:
            return 'granular'
        # If has any liquid formulation, default to liquid
        if has_liquid:
            return 'liquid'
    # Check rates for granular-only indicators
    rates = info.get('rates', {})
    all_granular = True
    for v in rates.values():
        v_str = str(v).lower()
        if 'fl oz' in v_str or 'ml' in v_str:
            return 'liquid'
        if 'lb' in v_str and '/1000' in v_str:
            pass  # could be granular
        else:
            all_granular = False
    if all_granular and rates:
        return 'granular'
    return 'liquid'


def _load_custom_products(user_id):
    """Load user's custom products from database."""
    if not user_id:
        return {}

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM custom_products WHERE user_id = ?', (user_id,))
        rows = cursor.fetchall()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to load custom products: {e}")
        return {}

    products = {}
    for row in rows:
        r = dict(row)
        pid = f"custom:{r['id']}"
        npk = None
        secondary = None
        try:
            if r.get('npk'):
                npk = json.loads(r['npk'])
            if r.get('secondary_nutrients'):
                secondary = json.loads(r['secondary_nutrients'])
        except (json.JSONDecodeError, TypeError):
            pass

        products[pid] = {
            'id': pid,
            'display_name': f"{r.get('brand', '')} {r['product_name']}".strip(),
            'brand': r.get('brand', ''),
            'category': r.get('product_type', 'fertilizer'),
            'active_ingredient': None,
            'form_type': r.get('form_type', 'granular'),
            'npk': npk,
            'secondary_nutrients': secondary,
            'default_rate': r.get('default_rate'),
            'rate_unit': r.get('rate_unit', 'lbs/1000 sq ft'),
            'density_lbs_per_gallon': r.get('density_lbs_per_gallon'),
            'trade_names': [],
            'frac_code': None,
            'hrac_group': None,
            'irac_group': None,
            'targets': [],
            'notes': r.get('notes', '')
        }

    return products


def _product_priority(pid):
    """Return priority for dedup: lower = keep. Custom > brand > generic."""
    if pid.startswith('custom:'):
        return 0
    if pid.startswith('pesticide:') or pid.startswith('fertilizer:'):
        return 2  # generic
    return 1  # brand-specific


# Suffixes to strip when comparing display names for dedup
_NAME_SUFFIXES = [
    ' broadleaf herbicide for turf', ' broadleaf herbicide',
    ' turf herbicide', ' for turf',
    ' fungicide', ' herbicide', ' insecticide',
    ' plant growth regulator',
]


def _normalize_display_name(name):
    """Normalize a display name for dedup matching."""
    n = name.lower().strip()
    for suffix in _NAME_SUFFIXES:
        if n.endswith(suffix):
            n = n[:-len(suffix)].strip()
    return n


def _get_all_products_dict(user_id=None):
    """Internal: merge all product sources into a single dict.
    Deduplicates in two passes:
      1. Same active-ingredient key in same category → drop generic pesticide entries
      2. Same normalized display name → drop lower-priority entry
    """
    all_products = {}
    all_products.update(_load_pesticides())
    all_products.update(_load_fertilizers())
    all_products.update(_load_brand_files())
    if user_id:
        all_products.update(_load_custom_products(user_id))

    to_remove = set()

    # --- Pass 1: drop generic entries when brand entry has same AI key + category ---
    brand_ai_keys = set()
    for pid, p in all_products.items():
        if pid.startswith('pesticide:') or pid.startswith('fertilizer:'):
            continue
        ai = (p.get('active_ingredient') or '').lower().replace(' ', '_').replace(',', '')
        if ai:
            brand_ai_keys.add((p['category'], ai))

    for pid in list(all_products.keys()):
        if not pid.startswith('pesticide:'):
            continue
        parts = pid.split(':')
        if len(parts) >= 3:
            cat_key = parts[1]
            ai_key = ':'.join(parts[2:])
            category = PESTICIDE_CATEGORIES.get(cat_key, cat_key.rstrip('s'))
            if (category, ai_key) in brand_ai_keys:
                to_remove.add(pid)

    # --- Pass 2: normalized display name dedup (keeps highest priority) ---
    seen_names = {}  # normalized_name -> (pid, priority)
    for pid, p in all_products.items():
        if pid in to_remove:
            continue
        norm = _normalize_display_name(p['display_name'])
        priority = _product_priority(pid)
        if norm in seen_names:
            existing_pid, existing_priority = seen_names[norm]
            if priority < existing_priority:
                to_remove.add(existing_pid)
                seen_names[norm] = (pid, priority)
            else:
                to_remove.add(pid)
        else:
            seen_names[norm] = (pid, priority)

    for pid in to_remove:
        del all_products[pid]

    if to_remove:
        logger.info(f"Deduplication removed {len(to_remove)} duplicate products")

    return all_products


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_all_products(user_id=None):
    """Get combined list of all products (pesticides + fertilizers + brands + custom).
    Returns list of product dicts sorted by category then display_name.
    """
    return sorted(
        _get_all_products_dict(user_id).values(),
        key=lambda p: (p['category'], p['display_name'])
    )


def search_products(query, user_id=None, category=None, form_type=None, inventory_only=False):
    """Search products by name, brand, trade names, or active ingredient.
    Optional filters: category (e.g. 'fungicide'), form_type (e.g. 'liquid', 'granular').
    If inventory_only=True, searches only the user's inventory (falls back to all if empty).
    Returns list of matching product dicts sorted by relevance.
    """
    if not query or len(query) < 2:
        return []

    all_dict = _get_all_products_dict(user_id)

    # Filter to inventory if requested
    if inventory_only and user_id:
        inv_ids = get_inventory_product_ids(user_id)
        if inv_ids:
            pool = {k: v for k, v in all_dict.items() if k in inv_ids}
        else:
            pool = all_dict  # Empty inventory → fall back to all
    else:
        pool = all_dict

    query_lower = query.lower().strip()
    query_words = query_lower.split()
    scored_results = []

    for product in pool.values():
        if category and product['category'] != category:
            continue
        if form_type and product.get('form_type') != form_type:
            continue

        display = (product.get('display_name') or '').lower()
        brand = (product.get('brand') or '').lower()
        ai = (product.get('active_ingredient') or '').lower()
        trade_names = [t.lower() for t in product.get('trade_names', []) if t]
        notes = (product.get('notes') or '').lower()
        searchable = f'{display} {brand} {ai} {" ".join(trade_names)} {notes}'

        # Score: lower = better
        score = None

        # Exact matches (full query as one string)
        if display == query_lower:
            score = 0  # Exact display name match
        elif any(t == query_lower for t in trade_names):
            score = 1  # Exact trade name match
        elif display.startswith(query_lower):
            score = 2  # Display name starts with query
        elif any(t.startswith(query_lower) for t in trade_names):
            score = 3  # Trade name starts with query
        elif query_lower in display:
            score = 4  # Query substring in display name
        elif any(query_lower in t for t in trade_names):
            score = 5  # Query substring in trade names
        elif query_lower in brand:
            score = 6  # Query substring in brand
        elif query_lower in ai:
            score = 7  # Query substring in active ingredient

        # Multi-word: all query words must appear somewhere in the product
        if score is None and len(query_words) > 1:
            if all(w in searchable for w in query_words):
                # Bonus if all words in display name
                if all(w in display for w in query_words):
                    score = 5
                else:
                    score = 8

        # Partial word matching: each query word starts a word in the product
        if score is None:
            searchable_words = searchable.split()
            if all(
                any(sw.startswith(qw) for sw in searchable_words)
                for qw in query_words
            ):
                # Better score if matching in display name
                display_words = display.split()
                if all(any(dw.startswith(qw) for dw in display_words) for qw in query_words):
                    score = 6
                else:
                    score = 9

        if score is not None:
            scored_results.append((score, product))

    scored_results.sort(key=lambda x: (x[0], x[1]['display_name']))
    return [p for _, p in scored_results]


def get_product_by_id(product_id, user_id=None):
    """Look up a single product by its ID.
    Returns product dict or None.
    """
    if not product_id:
        return None

    # Route to the right cache based on ID prefix
    if product_id.startswith('pesticide:'):
        return _load_pesticides().get(product_id)
    elif product_id.startswith('fertilizer:'):
        return _load_fertilizers().get(product_id)
    elif product_id.startswith('custom:'):
        return _load_custom_products(user_id).get(product_id)
    else:
        # Check if it matches any brand prefix
        prefix = product_id.split(':')[0] if ':' in product_id else ''
        if prefix in BRAND_PREFIXES:
            return _load_brand_files().get(product_id)
        # Fallback: search all brand products
        return _load_brand_files().get(product_id)


def save_custom_product(user_id, data):
    """Save a user-defined custom product. Returns the new product ID."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    npk_str = json.dumps(data.get('npk')) if data.get('npk') else None
    secondary_str = json.dumps(data.get('secondary_nutrients')) if data.get('secondary_nutrients') else None

    cursor.execute('''
        INSERT INTO custom_products (
            user_id, product_name, brand, product_type,
            npk, secondary_nutrients, form_type,
            density_lbs_per_gallon, sgn,
            default_rate, rate_unit, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        user_id,
        data.get('product_name', 'Custom Product'),
        data.get('brand', ''),
        data.get('product_type', 'fertilizer'),
        npk_str,
        secondary_str,
        data.get('form_type', 'granular'),
        data.get('density_lbs_per_gallon'),
        data.get('sgn'),
        data.get('default_rate'),
        data.get('rate_unit', 'lbs/1000 sq ft'),
        data.get('notes', '')
    ))

    product_id = cursor.lastrowid
    conn.commit()
    conn.close()

    logger.info(f"Custom product saved: {product_id} for user {user_id}")
    return f"custom:{product_id}"


# ---------------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------------

def get_inventory_product_ids(user_id):
    """Get set of product IDs in user's inventory."""
    if not user_id:
        return set()
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT product_id FROM user_inventory WHERE user_id = ?', (user_id,))
        ids = {row[0] for row in cursor.fetchall()}
        conn.close()
        return ids
    except Exception as e:
        logger.error(f"Failed to load inventory IDs: {e}")
        return set()


def get_user_inventory(user_id):
    """Get all products in the user's inventory as a list of product dicts."""
    if not user_id:
        return []
    inv_ids = get_inventory_product_ids(user_id)
    products = []
    for pid in inv_ids:
        p = get_product_by_id(pid, user_id=user_id)
        if p:
            products.append(p)
    return sorted(products, key=lambda p: (p['category'], p['display_name']))


def add_to_inventory(user_id, product_id):
    """Add a product to the user's inventory. Returns True if added."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(
            'INSERT OR IGNORE INTO user_inventory (user_id, product_id) VALUES (?, ?)',
            (user_id, product_id)
        )
        added = cursor.rowcount > 0
        conn.commit()
        return added
    finally:
        conn.close()


def remove_from_inventory(user_id, product_id):
    """Remove a product from the user's inventory. Returns True if removed."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        'DELETE FROM user_inventory WHERE user_id = ? AND product_id = ?',
        (user_id, product_id)
    )
    removed = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return removed


# ---------------------------------------------------------------------------
# Inventory Quantity Tracking
# ---------------------------------------------------------------------------

def get_inventory_quantities(user_id):
    """Get all inventory quantities for a user. Returns dict of product_id -> {quantity, unit, ...}."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM inventory_quantities WHERE user_id = ?', (user_id,))
    rows = {r['product_id']: dict(r) for r in cursor.fetchall()}
    conn.close()
    return rows


def update_inventory_quantity(user_id, product_id, quantity, unit='lbs', supplier=None, cost_per_unit=None, notes=None):
    """Update or insert inventory quantity for a product."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO inventory_quantities (user_id, product_id, quantity, unit, supplier, cost_per_unit, notes, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id, product_id) DO UPDATE SET
            quantity = excluded.quantity,
            unit = excluded.unit,
            supplier = COALESCE(excluded.supplier, supplier),
            cost_per_unit = COALESCE(excluded.cost_per_unit, cost_per_unit),
            notes = COALESCE(excluded.notes, notes),
            updated_at = CURRENT_TIMESTAMP
    ''', (user_id, product_id, quantity, unit, supplier, cost_per_unit, notes))
    conn.commit()
    conn.close()
    return True


def deduct_inventory(user_id, product_id, amount, unit):
    """Deduct usage amount from inventory quantity."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE inventory_quantities SET quantity = MAX(0, quantity - ?), updated_at = CURRENT_TIMESTAMP
        WHERE user_id = ? AND product_id = ? AND unit = ?
    ''', (amount, user_id, product_id, unit))
    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return updated


def clear_cache():
    """Clear all product caches. Call after adding new brand files or data changes."""
    global _pesticide_cache, _fertilizer_cache, _brand_cache
    _pesticide_cache = None
    _fertilizer_cache = None
    _brand_cache = None
    logger.info("Product caches cleared")
