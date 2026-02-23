"""
Course profile module for Greenside AI.
Handles course profile CRUD and builds AI context strings from profile data.
"""

import json
import sqlite3
import os
import logging

logger = logging.getLogger(__name__)

DATA_DIR = os.environ.get('DATA_DIR', 'data' if os.path.exists('data') else '.')
DB_PATH = os.path.join(DATA_DIR, 'greenside_conversations.db')


# ---------------------------------------------------------------------------
# Validation lists
# ---------------------------------------------------------------------------

VALID_GRASS_TYPES = [
    'bentgrass', 'hybrid bermudagrass', 'bermudagrass', 'poa annua',
    'kentucky bluegrass', 'tall fescue', 'perennial ryegrass', 'zoysiagrass',
    'st. augustinegrass', 'centipedegrass', 'bahiagrass', 'paspalum',
    'fine fescue', 'buffalograss'
]

VALID_TURF_TYPES = ['golf_course', 'sports_field', 'lawn_care', 'municipal', 'other']

VALID_ROLES = [
    'superintendent', 'assistant_superintendent', 'spray_tech',
    'grounds_manager', 'lawn_care_operator', 'student', 'other'
]

# State-to-region mapping (mirrors detection.py regions)
STATE_TO_REGION = {}
_region_map = {
    'northeast': [
        'massachusetts', 'connecticut', 'rhode island', 'vermont',
        'new hampshire', 'maine', 'new york', 'pennsylvania', 'new jersey',
        'delaware', 'maryland'
    ],
    'southeast': [
        'florida', 'georgia', 'alabama', 'south carolina', 'north carolina',
        'virginia', 'tennessee', 'mississippi', 'louisiana', 'arkansas',
        'kentucky', 'west virginia'
    ],
    'midwest': [
        'illinois', 'indiana', 'ohio', 'michigan', 'wisconsin', 'minnesota',
        'iowa', 'missouri', 'kansas', 'nebraska', 'north dakota', 'south dakota'
    ],
    'southwest': ['texas', 'oklahoma', 'arizona', 'new mexico'],
    'west': [
        'california', 'oregon', 'washington', 'nevada', 'colorado',
        'utah', 'idaho', 'montana', 'wyoming', 'hawaii', 'alaska'
    ],
}
for region, states in _region_map.items():
    for state in states:
        STATE_TO_REGION[state] = region

# US states for dropdowns
US_STATES = [
    'Alabama', 'Alaska', 'Arizona', 'Arkansas', 'California', 'Colorado',
    'Connecticut', 'Delaware', 'Florida', 'Georgia', 'Hawaii', 'Idaho',
    'Illinois', 'Indiana', 'Iowa', 'Kansas', 'Kentucky', 'Louisiana',
    'Maine', 'Maryland', 'Massachusetts', 'Michigan', 'Minnesota',
    'Mississippi', 'Missouri', 'Montana', 'Nebraska', 'Nevada',
    'New Hampshire', 'New Jersey', 'New Mexico', 'New York',
    'North Carolina', 'North Dakota', 'Ohio', 'Oklahoma', 'Oregon',
    'Pennsylvania', 'Rhode Island', 'South Carolina', 'South Dakota',
    'Tennessee', 'Texas', 'Utah', 'Vermont', 'Virginia', 'Washington',
    'West Virginia', 'Wisconsin', 'Wyoming'
]


# ---------------------------------------------------------------------------
# Profile CRUD
# ---------------------------------------------------------------------------

def save_profile(user_id, profile_data):
    """Create or update a course profile. Uses UPSERT pattern."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Auto-derive region from state
    state = (profile_data.get('state') or '').lower().strip()
    region = STATE_TO_REGION.get(state, profile_data.get('region'))

    # Build cultivar info as JSON-like string for storage
    cultivar_data = {}
    for key in ['primary_grass_cultivar', 'greens_grass_cultivar', 'fairways_grass_cultivar',
                'rough_grass_cultivar', 'tees_grass_cultivar']:
        val = (profile_data.get(key) or '').strip()
        if val:
            cultivar_data[key.replace('_cultivar', '')] = val
    cultivar_str = json.dumps(cultivar_data) if cultivar_data else None

    # Parse acreage values (convert to float or None)
    def _parse_acreage(val):
        try:
            v = float(val)
            return v if v > 0 else None
        except (TypeError, ValueError):
            return None

    cursor.execute('''
        INSERT INTO course_profiles (
            user_id, course_name, city, state, region,
            primary_grass, secondary_grasses, turf_type, role,
            greens_grass, fairways_grass, rough_grass, tees_grass,
            soil_type, irrigation_source, mowing_heights,
            annual_n_budget, notes, cultivars,
            greens_acreage, fairways_acreage, rough_acreage, tees_acreage,
            default_gpa, tank_size,
            updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id) DO UPDATE SET
            course_name=excluded.course_name, city=excluded.city,
            state=excluded.state, region=excluded.region,
            primary_grass=excluded.primary_grass,
            secondary_grasses=excluded.secondary_grasses,
            turf_type=excluded.turf_type, role=excluded.role,
            greens_grass=excluded.greens_grass,
            fairways_grass=excluded.fairways_grass,
            rough_grass=excluded.rough_grass,
            tees_grass=excluded.tees_grass,
            soil_type=excluded.soil_type,
            irrigation_source=excluded.irrigation_source,
            mowing_heights=excluded.mowing_heights,
            annual_n_budget=excluded.annual_n_budget,
            notes=excluded.notes,
            cultivars=excluded.cultivars,
            greens_acreage=excluded.greens_acreage,
            fairways_acreage=excluded.fairways_acreage,
            rough_acreage=excluded.rough_acreage,
            tees_acreage=excluded.tees_acreage,
            default_gpa=excluded.default_gpa,
            tank_size=excluded.tank_size,
            updated_at=CURRENT_TIMESTAMP
    ''', (
        user_id,
        profile_data.get('course_name'),
        profile_data.get('city'),
        profile_data.get('state'),
        region,
        profile_data.get('primary_grass'),
        profile_data.get('secondary_grasses'),
        profile_data.get('turf_type'),
        profile_data.get('role'),
        profile_data.get('greens_grass'),
        profile_data.get('fairways_grass'),
        profile_data.get('rough_grass'),
        profile_data.get('tees_grass'),
        profile_data.get('soil_type'),
        profile_data.get('irrigation_source'),
        profile_data.get('mowing_heights'),
        profile_data.get('annual_n_budget'),
        profile_data.get('notes'),
        cultivar_str,
        _parse_acreage(profile_data.get('greens_acreage')),
        _parse_acreage(profile_data.get('fairways_acreage')),
        _parse_acreage(profile_data.get('rough_acreage')),
        _parse_acreage(profile_data.get('tees_acreage')),
        _parse_acreage(profile_data.get('default_gpa')),
        _parse_acreage(profile_data.get('tank_size'))
    ))

    conn.commit()
    conn.close()
    logger.info(f"Profile saved for user {user_id}")


def get_profile(user_id):
    """Get the course profile for a user. Returns dict or None.
    Unpacks cultivar JSON into individual _cultivar keys for frontend use.
    """
    if not user_id:
        return None
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM course_profiles WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        result = dict(row)
        # Unpack cultivar JSON into individual keys
        cultivar_str = result.get('cultivars')
        if cultivar_str:
            try:
                cultivar_data = json.loads(cultivar_str)
                for area, cultivar in cultivar_data.items():
                    result[f'{area}_cultivar'] = cultivar
            except (json.JSONDecodeError, TypeError):
                pass
        return result
    return None


# ---------------------------------------------------------------------------
# AI context builder
# ---------------------------------------------------------------------------

def build_profile_context(user_id):
    """
    Build a context string from user profile for injection into AI prompts.

    Returns a string like:
        USER PROFILE: Superintendent at Pine Valley CC, New Jersey (northeast).
        Primary grass: bentgrass. Greens: bentgrass, Fairways: kentucky bluegrass.
        Soil: USGA sand-based.

    Returns empty string if no profile or user_id is None.
    """
    profile = get_profile(user_id)
    if not profile:
        return ''

    parts = []

    # Role + course + location
    header_parts = []
    if profile.get('role'):
        header_parts.append(profile['role'].replace('_', ' ').title())
    if profile.get('course_name'):
        header_parts.append(f"at {profile['course_name']}")
    location_bits = []
    if profile.get('city'):
        location_bits.append(profile['city'])
    if profile.get('state'):
        location_bits.append(profile['state'])
    if location_bits:
        header_parts.append(', '.join(location_bits))
    if profile.get('region'):
        header_parts.append(f"({profile['region']} region)")

    if header_parts:
        parts.append('USER PROFILE: ' + ' '.join(header_parts))

    # Grass types (with optional cultivar details)
    cultivar_data = {}
    if profile.get('cultivars'):
        try:
            cultivar_data = json.loads(profile['cultivars'])
        except (json.JSONDecodeError, TypeError):
            pass

    def grass_str(area_key, label):
        grass = profile.get(area_key)
        if not grass:
            return None
        cultivar = cultivar_data.get(area_key, '')
        if cultivar:
            return f"{label}: {grass} ({cultivar})"
        return f"{label}: {grass}"

    grass_bits = []
    if profile.get('turf_type') == 'golf_course':
        # Golf courses use per-area grasses
        for key, label in [('greens_grass', 'Greens'), ('fairways_grass', 'Fairways'),
                           ('rough_grass', 'Rough'), ('tees_grass', 'Tees')]:
            s = grass_str(key, label)
            if s:
                grass_bits.append(s)
    else:
        s = grass_str('primary_grass', 'Primary grass')
        if s:
            grass_bits.append(s)
    if grass_bits:
        parts.append('. '.join(grass_bits))

    # Acreage info
    acreage_bits = []
    for key, label in [('greens_acreage', 'Greens'), ('fairways_acreage', 'Fairways'),
                       ('tees_acreage', 'Tees'), ('rough_acreage', 'Rough')]:
        val = profile.get(key)
        if val:
            acreage_bits.append(f"{label}: {val} acres")
    if acreage_bits:
        parts.append('Acreage: ' + ', '.join(acreage_bits))

    # Sprayer config — pull from sprayers table
    sprayers = get_sprayers(user_id)
    if sprayers:
        sprayer_lines = []
        for s in sprayers:
            areas = json.loads(s['areas']) if isinstance(s['areas'], str) else s['areas']
            area_str = ', '.join(a.title() for a in areas) if areas else 'All areas'
            sprayer_lines.append(f"{s['name']}: {s['gpa']} GPA, {s['tank_size']} gal tank ({area_str})")
        parts.append('Sprayers: ' + '; '.join(sprayer_lines))
    elif profile.get('default_gpa') or profile.get('tank_size'):
        # Fallback to legacy single sprayer fields
        sprayer_bits = []
        if profile.get('default_gpa'):
            sprayer_bits.append(f"{profile['default_gpa']} GPA")
        if profile.get('tank_size'):
            sprayer_bits.append(f"{profile['tank_size']} gal tank")
        if sprayer_bits:
            parts.append('Sprayer: ' + ', '.join(sprayer_bits))

    # Other details
    detail_bits = []
    if profile.get('soil_type'):
        detail_bits.append(f"Soil: {profile['soil_type']}")
    if profile.get('irrigation_source'):
        detail_bits.append(f"Water source: {profile['irrigation_source']}")
    if detail_bits:
        parts.append('. '.join(detail_bits))

    return '\n'.join(parts)


# ---------------------------------------------------------------------------
# Sprayer CRUD
# ---------------------------------------------------------------------------

def get_sprayers(user_id):
    """Get all sprayers for a user. Returns list of dicts."""
    if not user_id:
        return []
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM sprayers WHERE user_id = ? ORDER BY is_default DESC, name', (user_id,))
    rows = cursor.fetchall()
    conn.close()
    results = []
    for row in rows:
        r = dict(row)
        # Parse areas JSON
        if isinstance(r.get('areas'), str):
            try:
                r['areas'] = json.loads(r['areas'])
            except (json.JSONDecodeError, TypeError):
                r['areas'] = []
        results.append(r)
    return results


def get_sprayer_for_area(user_id, area):
    """Get the sprayer assigned to a specific area. Returns dict or None.
    Falls back to default sprayer, then legacy profile fields.
    """
    sprayers = get_sprayers(user_id)
    if not sprayers:
        # Fallback to legacy profile fields
        profile = get_profile(user_id)
        if profile and (profile.get('default_gpa') or profile.get('tank_size')):
            return {
                'id': None,
                'name': 'Default Sprayer',
                'gpa': profile.get('default_gpa'),
                'tank_size': profile.get('tank_size'),
                'nozzle_type': None,
                'areas': [],
                'is_default': 1
            }
        return None

    # Find sprayer assigned to this area
    for s in sprayers:
        areas = s.get('areas', [])
        if area in areas:
            return s

    # Fallback to default sprayer
    for s in sprayers:
        if s.get('is_default'):
            return s

    # Fallback to first sprayer
    return sprayers[0] if sprayers else None


def save_sprayer(user_id, data):
    """Create or update a sprayer. Returns the sprayer ID."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    areas_str = json.dumps(data.get('areas', []))
    sprayer_id = data.get('id')

    if sprayer_id:
        # Update existing
        cursor.execute('''
            UPDATE sprayers SET name=?, gpa=?, tank_size=?, nozzle_type=?, areas=?, is_default=?
            WHERE id=? AND user_id=?
        ''', (
            data['name'],
            float(data['gpa']),
            float(data['tank_size']),
            data.get('nozzle_type'),
            areas_str,
            1 if data.get('is_default') else 0,
            sprayer_id,
            user_id
        ))
    else:
        # Insert new
        cursor.execute('''
            INSERT INTO sprayers (user_id, name, gpa, tank_size, nozzle_type, areas, is_default)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_id,
            data['name'],
            float(data['gpa']),
            float(data['tank_size']),
            data.get('nozzle_type'),
            areas_str,
            1 if data.get('is_default') else 0
        ))
        sprayer_id = cursor.lastrowid

    # If this sprayer is default, unset other defaults
    if data.get('is_default'):
        cursor.execute(
            'UPDATE sprayers SET is_default=0 WHERE user_id=? AND id!=?',
            (user_id, sprayer_id)
        )

    conn.commit()
    conn.close()
    logger.info(f"Sprayer saved: {sprayer_id} for user {user_id}")
    return sprayer_id


def delete_sprayer(user_id, sprayer_id):
    """Delete a sprayer. Returns True if deleted."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM sprayers WHERE id=? AND user_id=?', (sprayer_id, user_id))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted
