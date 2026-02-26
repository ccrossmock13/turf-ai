"""
Course profile module for Greenside AI.
Handles course profile CRUD and builds AI context strings from profile data.
"""

import json
import os
import logging

from db import get_db, is_postgres, CONVERSATIONS_DB

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

# USDA Hardiness Zone defaults per state (representative zones)
STATE_TO_CLIMATE_ZONE = {
    'alabama': '7b-8a', 'alaska': '4a-7b', 'arizona': '9a-10b',
    'arkansas': '7a-8a', 'california': '8a-10b', 'colorado': '5a-6b',
    'connecticut': '6a-6b', 'delaware': '7a-7b', 'florida': '9a-10b',
    'georgia': '7b-9a', 'hawaii': '10b-12a', 'idaho': '5a-6b',
    'illinois': '5b-6b', 'indiana': '5b-6b', 'iowa': '5a-5b',
    'kansas': '5b-6b', 'kentucky': '6a-7a', 'louisiana': '8a-9a',
    'maine': '4a-5b', 'maryland': '6b-7b', 'massachusetts': '5b-6b',
    'michigan': '5a-6a', 'minnesota': '3b-4b', 'mississippi': '7b-8b',
    'missouri': '5b-7a', 'montana': '4a-5b', 'nebraska': '4b-5b',
    'nevada': '6a-9b', 'new hampshire': '4b-5b', 'new jersey': '6b-7a',
    'new mexico': '6a-8b', 'new york': '4b-7a', 'north carolina': '7a-8a',
    'north dakota': '3b-4b', 'ohio': '5b-6b', 'oklahoma': '6b-7b',
    'oregon': '6a-9b', 'pennsylvania': '5b-7a', 'rhode island': '6a-6b',
    'south carolina': '7b-8b', 'south dakota': '4a-5a', 'tennessee': '6b-7b',
    'texas': '7a-9b', 'utah': '5a-7b', 'vermont': '4a-5a',
    'virginia': '6a-7b', 'washington': '5b-8b', 'west virginia': '5b-6b',
    'wisconsin': '4a-5b', 'wyoming': '4a-5b'
}

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
    """Create or update a course profile. Uses UPSERT on (user_id, course_name)."""
    with get_db() as conn:
        cursor = conn.cursor()

        # Auto-derive region and climate zone from state
        state = (profile_data.get('state') or '').lower().strip()
        region = STATE_TO_REGION.get(state, profile_data.get('region'))
        climate_zone = profile_data.get('climate_zone') or STATE_TO_CLIMATE_ZONE.get(state)

        # Build cultivar info as JSON-like string for storage
        cultivar_data = {}
        for key in ['primary_grass_cultivar', 'greens_grass_cultivar', 'fairways_grass_cultivar',
                    'rough_grass_cultivar', 'tees_grass_cultivar']:
            val = (profile_data.get(key) or '').strip()
            if val:
                cultivar_data[key.replace('_cultivar', '')] = val
        cultivar_str = json.dumps(cultivar_data) if cultivar_data else None

        # Parse acreage values (convert to float or None)
        def _parse_float(val):
            try:
                v = float(val)
                return v if v > 0 else None
            except (TypeError, ValueError):
                return None

        # Serialize JSON fields
        def _json_str(val):
            """Convert lists/dicts to JSON string, pass through existing strings."""
            if val is None:
                return None
            if isinstance(val, (list, dict)):
                return json.dumps(val)
            if isinstance(val, str):
                return val if val.strip() else None
            return None

        course_name = profile_data.get('course_name') or 'My Course'

        cursor.execute('''
            INSERT INTO course_profiles (
                user_id, course_name, is_active, city, state, region,
                primary_grass, secondary_grasses, turf_type, role,
                greens_grass, fairways_grass, rough_grass, tees_grass,
                soil_type, irrigation_source, mowing_heights,
                annual_n_budget, notes, cultivars,
                greens_acreage, fairways_acreage, rough_acreage, tees_acreage,
                default_gpa, tank_size,
                soil_ph, soil_om, water_ph, water_ec,
                green_speed_target, budget_tier, climate_zone,
                common_problems, preferred_products, overseeding_program,
                irrigation_schedule, aerification_program,
                topdressing_program, pgr_program,
                wetting_agent_program, maintenance_calendar, bunker_sand,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, course_name) DO UPDATE SET
                is_active=excluded.is_active,
                city=excluded.city, state=excluded.state, region=excluded.region,
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
                soil_ph=excluded.soil_ph,
                soil_om=excluded.soil_om,
                water_ph=excluded.water_ph,
                water_ec=excluded.water_ec,
                green_speed_target=excluded.green_speed_target,
                budget_tier=excluded.budget_tier,
                climate_zone=excluded.climate_zone,
                common_problems=excluded.common_problems,
                preferred_products=excluded.preferred_products,
                overseeding_program=excluded.overseeding_program,
                irrigation_schedule=excluded.irrigation_schedule,
                aerification_program=excluded.aerification_program,
                topdressing_program=excluded.topdressing_program,
                pgr_program=excluded.pgr_program,
                wetting_agent_program=excluded.wetting_agent_program,
                maintenance_calendar=excluded.maintenance_calendar,
                bunker_sand=excluded.bunker_sand,
                updated_at=CURRENT_TIMESTAMP
        ''', (
            user_id,
            course_name,
            1 if profile_data.get('is_active', True) else 0,
            profile_data.get('city'),
            profile_data.get('state'),
            region,
            profile_data.get('primary_grass'),
            _json_str(profile_data.get('secondary_grasses')),
            profile_data.get('turf_type'),
            profile_data.get('role'),
            profile_data.get('greens_grass'),
            profile_data.get('fairways_grass'),
            profile_data.get('rough_grass'),
            profile_data.get('tees_grass'),
            profile_data.get('soil_type'),
            profile_data.get('irrigation_source'),
            _json_str(profile_data.get('mowing_heights')),
            _json_str(profile_data.get('annual_n_budget')),
            profile_data.get('notes'),
            cultivar_str,
            _parse_float(profile_data.get('greens_acreage')),
            _parse_float(profile_data.get('fairways_acreage')),
            _parse_float(profile_data.get('rough_acreage')),
            _parse_float(profile_data.get('tees_acreage')),
            _parse_float(profile_data.get('default_gpa')),
            _parse_float(profile_data.get('tank_size')),
            _parse_float(profile_data.get('soil_ph')),
            _parse_float(profile_data.get('soil_om')),
            _parse_float(profile_data.get('water_ph')),
            _parse_float(profile_data.get('water_ec')),
            _parse_float(profile_data.get('green_speed_target')),
            profile_data.get('budget_tier'),
            climate_zone,
            _json_str(profile_data.get('common_problems')),
            _json_str(profile_data.get('preferred_products')),
            _json_str(profile_data.get('overseeding_program')),
            _json_str(profile_data.get('irrigation_schedule')),
            _json_str(profile_data.get('aerification_program')),
            _json_str(profile_data.get('topdressing_program')),
            _json_str(profile_data.get('pgr_program')),
            _json_str(profile_data.get('wetting_agent_program')),
            _json_str(profile_data.get('maintenance_calendar')),
            _json_str(profile_data.get('bunker_sand'))
        ))

    logger.info(f"Profile saved for user {user_id} course '{course_name}'")


def _unpack_profile(row):
    """Unpack a profile row into a dict with parsed JSON fields."""
    if not row:
        return None
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
    # Unpack JSON fields into native Python types
    for json_field in ['common_problems', 'preferred_products',
                       'overseeding_program', 'mowing_heights', 'annual_n_budget',
                       'secondary_grasses', 'irrigation_schedule', 'aerification_program',
                       'topdressing_program', 'pgr_program', 'wetting_agent_program',
                       'maintenance_calendar', 'bunker_sand']:
        raw = result.get(json_field)
        if raw and isinstance(raw, str):
            try:
                result[json_field] = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                pass
    return result


def get_profile(user_id, course_name=None):
    """Get a course profile for a user. Returns dict or None.
    If course_name is None, returns the active profile (is_active=1).
    Falls back to any profile if no active profile is set.
    """
    if not user_id:
        return None
    with get_db() as conn:
        cursor = conn.cursor()
        if course_name:
            cursor.execute('SELECT * FROM course_profiles WHERE user_id = ? AND course_name = ?',
                           (user_id, course_name))
        else:
            cursor.execute('SELECT * FROM course_profiles WHERE user_id = ? ORDER BY is_active DESC, updated_at DESC LIMIT 1',
                           (user_id,))
        row = cursor.fetchone()
    return _unpack_profile(row)


def get_profiles(user_id):
    """Get all course profiles for a user. Returns list of dicts."""
    if not user_id:
        return []
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM course_profiles WHERE user_id = ? ORDER BY is_active DESC, course_name',
                       (user_id,))
        rows = cursor.fetchall()
    return [_unpack_profile(row) for row in rows]


def set_active_profile(user_id, course_name):
    """Set a specific course as the active profile. Deactivates others."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE course_profiles SET is_active = 0 WHERE user_id = ?', (user_id,))
        cursor.execute('UPDATE course_profiles SET is_active = 1 WHERE user_id = ? AND course_name = ?',
                       (user_id, course_name))
        updated = cursor.rowcount > 0
    return updated


def duplicate_profile(user_id, source_name, new_name):
    """Duplicate a profile under a new course name. Returns True if successful."""
    source = get_profile(user_id, source_name)
    if not source:
        return False
    # Remove identity fields and set new name
    source.pop('id', None)
    source.pop('updated_at', None)
    source['course_name'] = new_name
    source['is_active'] = False
    save_profile(user_id, source)
    return True


def delete_profile(user_id, course_name):
    """Delete a course profile. Prevents deleting the last profile."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM course_profiles WHERE user_id = ?', (user_id,))
        count = cursor.fetchone()[0]
        if count <= 1:
            return False
        cursor.execute('DELETE FROM course_profiles WHERE user_id = ? AND course_name = ?',
                       (user_id, course_name))
        deleted = cursor.rowcount > 0
        # If we deleted the active profile, activate another one
        if deleted:
            cursor.execute('SELECT id FROM course_profiles WHERE user_id = ? AND is_active = 1', (user_id,))
            if not cursor.fetchone():
                # PostgreSQL doesn't support UPDATE LIMIT — use subquery
                if is_postgres():
                    cursor.execute('''
                        UPDATE course_profiles SET is_active = 1
                        WHERE id = (SELECT id FROM course_profiles WHERE user_id = ? LIMIT 1)
                    ''', (user_id,))
                else:
                    cursor.execute('UPDATE course_profiles SET is_active = 1 WHERE user_id = ? LIMIT 1', (user_id,))
    return deleted


# ---------------------------------------------------------------------------
# Profile templates
# ---------------------------------------------------------------------------

PROFILE_TEMPLATES = {
    'golf_18': {
        'label': '18-Hole Golf Course',
        'description': 'Full 18-hole golf course with greens, fairways, tees, and rough',
        'data': {
            'turf_type': 'golf_course',
            'greens_grass': 'bentgrass',
            'fairways_grass': 'kentucky bluegrass',
            'rough_grass': 'tall fescue',
            'tees_grass': 'kentucky bluegrass',
            'greens_acreage': 3.5,
            'fairways_acreage': 30,
            'tees_acreage': 4,
            'rough_acreage': 50,
            'mowing_heights': {'greens': '0.125', 'fairways': '0.625', 'rough': '2.5', 'tees': '0.5'},
            'green_speed_target': 10.5,
            'budget_tier': 'moderate',
        }
    },
    'golf_9': {
        'label': '9-Hole Golf Course',
        'description': 'Compact 9-hole course',
        'data': {
            'turf_type': 'golf_course',
            'greens_grass': 'bentgrass',
            'fairways_grass': 'kentucky bluegrass',
            'rough_grass': 'tall fescue',
            'tees_grass': 'kentucky bluegrass',
            'greens_acreage': 1.75,
            'fairways_acreage': 15,
            'tees_acreage': 2,
            'rough_acreage': 25,
            'mowing_heights': {'greens': '0.135', 'fairways': '0.75', 'rough': '3.0', 'tees': '0.5'},
            'green_speed_target': 9.5,
            'budget_tier': 'budget',
        }
    },
    'sports_field': {
        'label': 'Sports Field',
        'description': 'Athletic field (football, soccer, baseball, multi-use)',
        'data': {
            'turf_type': 'sports_field',
            'primary_grass': 'kentucky bluegrass',
            'mowing_heights': {'primary': '2.0'},
            'budget_tier': 'moderate',
        }
    },
    'lawn_residential': {
        'label': 'Residential Lawn Care',
        'description': 'Residential properties for lawn care operators',
        'data': {
            'turf_type': 'lawn_care',
            'primary_grass': 'kentucky bluegrass',
            'mowing_heights': {'primary': '3.0'},
            'budget_tier': 'budget',
        }
    },
    'lawn_commercial': {
        'label': 'Commercial Lawn Care',
        'description': 'Commercial properties and HOAs',
        'data': {
            'turf_type': 'lawn_care',
            'primary_grass': 'tall fescue',
            'mowing_heights': {'primary': '3.5'},
            'budget_tier': 'moderate',
        }
    },
}


def get_profile_templates():
    """Return available profile templates as list of {id, label, description}."""
    return [{'id': k, 'label': v['label'], 'description': v['description']}
            for k, v in PROFILE_TEMPLATES.items()]


def create_from_template(user_id, template_id, course_name):
    """Create a new profile from a template. Returns True if successful."""
    template = PROFILE_TEMPLATES.get(template_id)
    if not template:
        return False
    data = dict(template['data'])
    data['course_name'] = course_name
    data['is_active'] = False
    save_profile(user_id, data)
    return True


# ---------------------------------------------------------------------------
# AI context builder
# ---------------------------------------------------------------------------

def build_profile_context(user_id, question_topic=None):
    """
    Build a context string from user profile for injection into AI prompts.
    Uses topic-aware filtering to only include sections relevant to the question.
    """
    profile = get_profile(user_id)
    if not profile:
        return ''

    # Topic-aware section relevance
    TOPIC_SECTIONS = {
        'chemical': {'sprayers', 'problems', 'products', 'overseeding', 'budget', 'mowing', 'pgr'},
        'fungicide': {'sprayers', 'problems', 'products', 'budget', 'mowing', 'green_speed'},
        'herbicide': {'sprayers', 'problems', 'products', 'overseeding', 'budget'},
        'insecticide': {'sprayers', 'problems', 'products', 'budget'},
        'fertilizer': {'n_budget', 'soil_water', 'mowing', 'budget', 'acreage'},
        'cultural': {'mowing', 'green_speed', 'overseeding', 'acreage', 'cultural_practices', 'calendar'},
        'disease': {'problems', 'mowing', 'soil_water', 'green_speed'},
        'irrigation': {'soil_water', 'acreage', 'irrigation_detail'},
        'diagnostic': {'problems', 'mowing', 'soil_water'},
        'equipment': {'sprayers', 'acreage'},
        'pgr': {'pgr', 'mowing', 'green_speed', 'budget'},
        'topdressing': {'cultural_practices', 'soil_water', 'calendar'},
        'aerification': {'cultural_practices', 'calendar', 'soil_water'},
        'wetting_agent': {'soil_water', 'irrigation_detail', 'budget'},
        'calendar': {'calendar', 'cultural_practices', 'overseeding'},
    }

    def _include(section):
        if not question_topic:
            return True
        relevant = TOPIC_SECTIONS.get(question_topic, set())
        return section in relevant

    parts = []

    # ── Always included: identity + location + climate ──
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
    if profile.get('climate_zone'):
        header_parts.append(f"[Zone {profile['climate_zone']}]")

    if header_parts:
        parts.append('USER PROFILE: ' + ' '.join(header_parts))

    # ── Always included: grass types ──
    cultivar_data = {}
    if profile.get('cultivars'):
        try:
            cultivar_data = json.loads(profile['cultivars']) if isinstance(profile['cultivars'], str) else profile.get('cultivars', {})
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

    secondary = profile.get('secondary_grasses')
    if isinstance(secondary, str):
        try:
            secondary = json.loads(secondary)
        except (json.JSONDecodeError, TypeError):
            secondary = {}
    if not isinstance(secondary, dict):
        secondary = {}

    grass_bits = []
    if profile.get('turf_type') == 'golf_course':
        for key, label in [('greens_grass', 'Greens'), ('fairways_grass', 'Fairways'),
                           ('rough_grass', 'Rough'), ('tees_grass', 'Tees')]:
            s = grass_str(key, label)
            if s:
                area = key.replace('_grass', '')
                sec_grass = secondary.get(area)
                if sec_grass:
                    s += f" (overseeded/mixed: {sec_grass})"
                grass_bits.append(s)
    else:
        s = grass_str('primary_grass', 'Primary grass')
        if s:
            grass_bits.append(s)
    if grass_bits:
        parts.append('. '.join(grass_bits))

    # ── Conditional: acreage ──
    if _include('acreage'):
        acreage_bits = []
        for key, label in [('greens_acreage', 'Greens'), ('fairways_acreage', 'Fairways'),
                           ('tees_acreage', 'Tees'), ('rough_acreage', 'Rough')]:
            val = profile.get(key)
            if val:
                acreage_bits.append(f"{label}: {val} acres")
        if acreage_bits:
            parts.append('Acreage: ' + ', '.join(acreage_bits))

    # ── Conditional: mowing heights ──
    if _include('mowing') and profile.get('mowing_heights'):
        mh = profile['mowing_heights']
        if isinstance(mh, str):
            try:
                mh = json.loads(mh)
            except (json.JSONDecodeError, TypeError):
                mh = None
        if isinstance(mh, dict):
            mh_bits = [f"{area.title()}: {height}\"" for area, height in mh.items() if height]
            if mh_bits:
                parts.append('Mowing heights: ' + ', '.join(mh_bits))

    # ── Conditional: green speed ──
    if _include('green_speed') and profile.get('green_speed_target'):
        parts.append(f"Green speed target: {profile['green_speed_target']} ft (Stimpmeter)")

    # ── Conditional: sprayers ──
    if _include('sprayers'):
        sprayers = get_sprayers(user_id)
        if sprayers:
            sprayer_lines = []
            for s in sprayers:
                areas = json.loads(s['areas']) if isinstance(s['areas'], str) else s['areas']
                area_str = ', '.join(a.title() for a in areas) if areas else 'All areas'
                sprayer_lines.append(f"{s['name']}: {s['gpa']} GPA, {s['tank_size']} gal tank ({area_str})")
            parts.append('Sprayers: ' + '; '.join(sprayer_lines))
        elif profile.get('default_gpa') or profile.get('tank_size'):
            sprayer_bits = []
            if profile.get('default_gpa'):
                sprayer_bits.append(f"{profile['default_gpa']} GPA")
            if profile.get('tank_size'):
                sprayer_bits.append(f"{profile['tank_size']} gal tank")
            if sprayer_bits:
                parts.append('Sprayer: ' + ', '.join(sprayer_bits))

    # ── Conditional: N budget ──
    if _include('n_budget') and profile.get('annual_n_budget'):
        nb = profile['annual_n_budget']
        if isinstance(nb, str):
            try:
                nb = json.loads(nb)
            except (json.JSONDecodeError, TypeError):
                nb = None
        if isinstance(nb, dict):
            nb_bits = [f"{area.title()}: {val} lbs N/1000" for area, val in nb.items() if val]
            if nb_bits:
                parts.append('Annual N budget: ' + ', '.join(nb_bits))

    # ── Conditional: soil & water ──
    if _include('soil_water'):
        detail_bits = []
        if profile.get('soil_type'):
            detail_bits.append(f"Soil: {profile['soil_type']}")
        if profile.get('irrigation_source'):
            detail_bits.append(f"Water source: {profile['irrigation_source']}")
        if detail_bits:
            parts.append('. '.join(detail_bits))

        quality_bits = []
        if profile.get('soil_ph'):
            quality_bits.append(f"Soil pH: {profile['soil_ph']}")
        if profile.get('soil_om'):
            quality_bits.append(f"Organic matter: {profile['soil_om']}%")
        if profile.get('water_ph'):
            quality_bits.append(f"Water pH: {profile['water_ph']}")
        if profile.get('water_ec'):
            quality_bits.append(f"Water EC: {profile['water_ec']} dS/m")
        if quality_bits:
            parts.append('Lab data: ' + ', '.join(quality_bits))
    else:
        if profile.get('soil_type'):
            parts.append(f"Soil: {profile['soil_type']}")

    # ── Conditional: budget tier ──
    if _include('budget') and profile.get('budget_tier'):
        tier = profile['budget_tier']
        if tier == 'budget':
            parts.append(
                'PRODUCT GUIDANCE: Budget-conscious — suggest generic/commodity products first '
                '(e.g., generic propiconazole over Banner Maxx). Mention cost-saving alternatives.'
            )
        elif tier == 'premium':
            parts.append(
                'PRODUCT GUIDANCE: Premium budget — recommend best-in-class products for highest efficacy. '
                'Brand names are fine. Do not prioritize cost over performance.'
            )
        else:
            parts.append('Budget: Moderate (balance of cost and performance)')

    # ── Conditional: overseeding ──
    if _include('overseeding') and profile.get('overseeding_program'):
        os_data = profile['overseeding_program']
        if isinstance(os_data, str):
            try:
                os_data = json.loads(os_data)
            except (json.JSONDecodeError, TypeError):
                os_data = None
        if isinstance(os_data, dict) and (os_data.get('grass') or os_data.get('date')):
            os_parts = []
            if os_data.get('grass'):
                os_parts.append(os_data['grass'])
            if os_data.get('date'):
                os_parts.append(f"around {os_data['date']}")
            if os_data.get('rate'):
                os_parts.append(f"at {os_data['rate']} lbs/1000")
            parts.append('Overseeding: ' + ', '.join(os_parts))
            if os_data.get('date') and question_topic in ('chemical', 'herbicide'):
                parts.append(
                    f"HERBICIDE TIMING NOTE: User overseeds around {os_data['date']}. "
                    'Pre-emergent timing must avoid interfering with overseeding germination.'
                )

    # ── Conditional: common problems ──
    if _include('problems') and profile.get('common_problems'):
        problems = profile['common_problems']
        if isinstance(problems, str):
            try:
                problems = json.loads(problems)
            except (json.JSONDecodeError, TypeError):
                problems = []
        if isinstance(problems, list) and problems:
            problem_names = ', '.join(p.replace('_', ' ').title() for p in problems)
            parts.append(f"Common problems: {problem_names}")
            parts.append(
                f"PROACTIVE NOTE: This user commonly deals with {problem_names}. "
                'When relevant, mention preventive strategies or upcoming seasonal pressure.'
            )

    # ── Conditional: preferred products ──
    if _include('products') and profile.get('preferred_products'):
        prods = profile['preferred_products']
        if isinstance(prods, str):
            try:
                prods = json.loads(prods)
            except (json.JSONDecodeError, TypeError):
                prods = []
        if isinstance(prods, list) and prods:
            parts.append('Preferred products/brands: ' + ', '.join(prods))

    # ── Conditional: irrigation schedule ──
    if _include('irrigation_detail') and profile.get('irrigation_schedule'):
        irr = profile['irrigation_schedule']
        if isinstance(irr, str):
            try:
                irr = json.loads(irr)
            except (json.JSONDecodeError, TypeError):
                irr = None
        if isinstance(irr, dict):
            irr_bits = []
            if irr.get('system_type'):
                irr_bits.append(f"System: {irr['system_type']}")
            if irr.get('run_times'):
                irr_bits.append(f"Run times: {irr['run_times']}")
            if irr.get('zones'):
                irr_bits.append(f"Zones: {irr['zones']}")
            if irr_bits:
                parts.append('Irrigation: ' + ', '.join(irr_bits))

    # ── Conditional: cultural practices ──
    if _include('cultural_practices'):
        if profile.get('aerification_program'):
            aer = profile['aerification_program']
            if isinstance(aer, str):
                try:
                    aer = json.loads(aer)
                except (json.JSONDecodeError, TypeError):
                    aer = None
            if isinstance(aer, dict):
                aer_bits = []
                if aer.get('dates'):
                    aer_bits.append(f"dates: {aer['dates']}")
                if aer.get('tine_type'):
                    aer_bits.append(f"tines: {aer['tine_type']}")
                if aer.get('depth'):
                    aer_bits.append(f"depth: {aer['depth']}")
                if aer_bits:
                    parts.append('Aerification: ' + ', '.join(aer_bits))

        if profile.get('topdressing_program'):
            td = profile['topdressing_program']
            if isinstance(td, str):
                try:
                    td = json.loads(td)
                except (json.JSONDecodeError, TypeError):
                    td = None
            if isinstance(td, dict):
                td_bits = []
                if td.get('material'):
                    td_bits.append(td['material'])
                if td.get('rate'):
                    td_bits.append(f"rate: {td['rate']}")
                if td.get('frequency'):
                    td_bits.append(f"frequency: {td['frequency']}")
                if td_bits:
                    parts.append('Topdressing: ' + ', '.join(td_bits))

        if profile.get('bunker_sand'):
            bs = profile['bunker_sand']
            if isinstance(bs, str):
                try:
                    bs = json.loads(bs)
                except (json.JSONDecodeError, TypeError):
                    bs = None
            if isinstance(bs, dict) and bs.get('type'):
                parts.append(f"Bunker sand: {bs['type']}")

    # ── Conditional: PGR program ──
    if _include('pgr') and profile.get('pgr_program'):
        pgr = profile['pgr_program']
        if isinstance(pgr, str):
            try:
                pgr = json.loads(pgr)
            except (json.JSONDecodeError, TypeError):
                pgr = None
        if isinstance(pgr, dict):
            pgr_bits = []
            if pgr.get('product'):
                pgr_bits.append(pgr['product'])
            if pgr.get('rate'):
                pgr_bits.append(f"at {pgr['rate']}")
            if pgr.get('interval'):
                pgr_bits.append(f"every {pgr['interval']}")
            if pgr_bits:
                parts.append('PGR program: ' + ', '.join(pgr_bits))

    # ── Conditional: wetting agent ──
    if _include('irrigation_detail') or _include('soil_water'):
        if profile.get('wetting_agent_program'):
            wa = profile['wetting_agent_program']
            if isinstance(wa, str):
                try:
                    wa = json.loads(wa)
                except (json.JSONDecodeError, TypeError):
                    wa = None
            if isinstance(wa, dict) and wa.get('product'):
                wa_bits = [wa['product']]
                if wa.get('rate'):
                    wa_bits.append(f"at {wa['rate']}")
                if wa.get('interval'):
                    wa_bits.append(f"every {wa['interval']}")
                parts.append('Wetting agent: ' + ', '.join(wa_bits))

    # ── Conditional: maintenance calendar ──
    if _include('calendar') and profile.get('maintenance_calendar'):
        cal = profile['maintenance_calendar']
        if isinstance(cal, str):
            try:
                cal = json.loads(cal)
            except (json.JSONDecodeError, TypeError):
                cal = None
        if isinstance(cal, dict):
            from datetime import datetime as _dt
            current_month = _dt.now().strftime('%b').lower()
            month_tasks = cal.get(current_month)
            if month_tasks:
                parts.append(f"This month's planned tasks: {month_tasks}")

    # ── Seasonal awareness ──
    try:
        from climate_data import get_current_season
        state_name = (profile.get('state') or '').strip()
        if state_name:
            season_info = get_current_season(state_name)
            if season_info:
                parts.append(f"SEASON: {season_info['season'].replace('_', ' ').title()} — {season_info['description']}")
    except ImportError:
        pass

    # ── Weather context (auto-inject if profile has location) ──
    if profile.get('city') and profile.get('state'):
        try:
            from weather_service import get_weather_context
            weather_ctx = get_weather_context()
            if weather_ctx:
                parts.append(f"CURRENT WEATHER: {weather_ctx}")
        except Exception:
            pass

    # ── Spray history for chemical topics ──
    if question_topic in ('chemical', 'fungicide', 'herbicide', 'insecticide', 'pgr'):
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT date, product_name, product_category, rate, rate_unit, area
                    FROM spray_applications
                    WHERE user_id = ? AND date >= date('now', '-30 days')
                    ORDER BY date DESC LIMIT 10
                ''', (user_id,))
                recent_sprays = cursor.fetchall()
            if recent_sprays:
                spray_lines = []
                for s in recent_sprays:
                    spray_lines.append(f"{s[0]}: {s[1]} ({s[2]}) at {s[3]} {s[4]} on {s[5]}")
                parts.append('RECENT APPLICATIONS (last 30 days):\n' + '\n'.join(spray_lines))
        except Exception:
            pass

    # ── Always included: role-based tone ──
    role = profile.get('role', '')
    if role == 'superintendent':
        parts.append(
            'TONE: This user is an experienced superintendent. Be concise and direct. '
            'Lead with specific products, rates, and timing. Skip basic explanations '
            'they already know. Focus on actionable steps and decision rationale.'
        )
    elif role == 'assistant_superintendent':
        parts.append(
            'TONE: This user is an assistant superintendent. Provide detailed recommendations '
            'with rates and products. Include brief scientific reasoning to support '
            'their decision-making and communication to their superintendent.'
        )
    elif role == 'spray_tech':
        parts.append(
            'TONE: This user is a spray technician. Emphasize application details: '
            'exact rates, carrier volumes, nozzle tips, spray timing, tank mix order, '
            'and REI/PHI restrictions. Keep agronomic theory brief.'
        )
    elif role == 'lawn_care_operator':
        parts.append(
            'TONE: This user is a lawn care professional. Use consumer-grade product names '
            'alongside active ingredients. Include per-1000-sqft rates. Mention cost-effective '
            'options and practical scheduling for multiple properties.'
        )
    elif role == 'student':
        parts.append(
            'TONE: This user is a turfgrass student. Explain the WHY behind every recommendation. '
            'Include scientific mechanisms, pathogen biology, and agronomic principles. '
            'Use this as a teaching opportunity while still giving practical answers.'
        )
    elif role == 'grounds_manager':
        parts.append(
            'TONE: This user manages grounds (non-golf). Provide practical recommendations '
            'suitable for sports fields or municipal turf. Focus on durability, recovery, '
            'and budget-conscious options.'
        )

    return '\n'.join(parts)


# ---------------------------------------------------------------------------
# Sprayer CRUD
# ---------------------------------------------------------------------------

def get_sprayers(user_id):
    """Get all sprayers for a user. Returns list of dicts."""
    if not user_id:
        return []
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM sprayers WHERE user_id = ? ORDER BY is_default DESC, name', (user_id,))
        rows = cursor.fetchall()
    results = []
    for row in rows:
        r = dict(row)
        if isinstance(r.get('areas'), str):
            try:
                r['areas'] = json.loads(r['areas'])
            except (json.JSONDecodeError, TypeError):
                r['areas'] = []
        results.append(r)
    return results


def get_sprayer_for_area(user_id, area):
    """Get the sprayer assigned to a specific area. Returns dict or None."""
    sprayers = get_sprayers(user_id)
    if not sprayers:
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

    for s in sprayers:
        areas = s.get('areas', [])
        if area in areas:
            return s

    for s in sprayers:
        if s.get('is_default'):
            return s

    return sprayers[0] if sprayers else None


def save_sprayer(user_id, data):
    """Create or update a sprayer. Returns the sprayer ID."""
    with get_db() as conn:
        cursor = conn.cursor()

        areas_str = json.dumps(data.get('areas', []))
        sprayer_id = data.get('id')

        if sprayer_id:
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

        if data.get('is_default'):
            cursor.execute(
                'UPDATE sprayers SET is_default=0 WHERE user_id=? AND id!=?',
                (user_id, sprayer_id)
            )

    logger.info(f"Sprayer saved: {sprayer_id} for user {user_id}")
    return sprayer_id


def delete_sprayer(user_id, sprayer_id):
    """Delete a sprayer. Returns True if deleted."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM sprayers WHERE id=? AND user_id=?', (sprayer_id, user_id))
        deleted = cursor.rowcount > 0
    return deleted
