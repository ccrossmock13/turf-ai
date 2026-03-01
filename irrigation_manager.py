"""
Irrigation management module for Greenside AI.
Handles irrigation zones, scheduling, soil moisture tracking, ET calculations,
water usage monitoring, and drought protocol recommendations.
"""

import math
import logging
from datetime import datetime, timedelta

from db import get_db, add_column

logger = logging.getLogger(__name__)
# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_AREAS = ['greens', 'fairways', 'tees', 'rough', 'practice']
VALID_SPRINKLER_TYPES = ['rotor', 'spray', 'drip']
VALID_SOIL_TYPES = ['sand', 'sandy_loam', 'loam', 'clay_loam', 'clay']
VALID_RUN_TYPES = ['scheduled', 'manual', 'syringe', 'fertigation']
VALID_MOISTURE_METHODS = ['tdr', 'tensiometer', 'visual', 'feel']
VALID_ET_SOURCES = ['manual', 'weather_api']

# Crop coefficients by turf area (Kc values for well-maintained turf)
DEFAULT_CROP_COEFFICIENTS = {
    'greens': 0.85,
    'fairways': 0.80,
    'tees': 0.80,
    'rough': 0.70,
    'practice': 0.75,
}

# Soil available water capacity (inches of water per inch of soil depth)
SOIL_AWC = {
    'sand': 0.06,
    'sandy_loam': 0.12,
    'loam': 0.17,
    'clay_loam': 0.18,
    'clay': 0.15,
}

# Typical infiltration rates (inches/hour) by soil type
SOIL_INFILTRATION_RATES = {
    'sand': 2.0,
    'sandy_loam': 1.0,
    'loam': 0.5,
    'clay_loam': 0.3,
    'clay': 0.15,
}


# ---------------------------------------------------------------------------
# Database Initialization
# ---------------------------------------------------------------------------

def init_irrigation_tables():
    """Initialize all irrigation-related database tables.
    Works with both SQLite and PostgreSQL via the db.py conversion layer.
    """
    with get_db() as conn:
        cursor = conn.cursor()

        # Irrigation zones
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS irrigation_zones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                area TEXT NOT NULL,
                zone_number INTEGER,
                sprinkler_type TEXT,
                heads_count INTEGER,
                gpm_per_head REAL,
                precipitation_rate REAL,
                area_sqft REAL,
                soil_type TEXT,
                root_depth REAL,
                allowable_depletion REAL,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        # Irrigation runs
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS irrigation_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                zone_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                run_date TEXT NOT NULL,
                start_time TEXT,
                duration_minutes REAL,
                gallons_applied REAL,
                inches_applied REAL,
                run_type TEXT DEFAULT 'scheduled',
                weather_conditions TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (zone_id) REFERENCES irrigation_zones(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        # Soil moisture readings
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS soil_moisture_readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                zone_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                reading_date TEXT NOT NULL,
                moisture_pct REAL,
                reading_depth REAL,
                method TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (zone_id) REFERENCES irrigation_zones(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        # ET (evapotranspiration) data
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS et_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                et0 REAL,
                rainfall REAL,
                high_temp REAL,
                low_temp REAL,
                humidity REAL,
                wind_speed REAL,
                solar_radiation REAL,
                source TEXT DEFAULT 'manual',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        # Water usage tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS water_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                total_gallons REAL,
                meter_reading REAL,
                cost REAL,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        # Indexes for performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_irr_zones_user ON irrigation_zones(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_irr_zones_area ON irrigation_zones(user_id, area)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_irr_runs_zone ON irrigation_runs(zone_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_irr_runs_user ON irrigation_runs(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_irr_runs_date ON irrigation_runs(user_id, run_date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_moisture_zone ON soil_moisture_readings(zone_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_moisture_user ON soil_moisture_readings(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_moisture_date ON soil_moisture_readings(user_id, reading_date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_et_user_date ON et_data(user_id, date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_water_usage_user ON water_usage(user_id, date)')

    logger.info("Irrigation tables initialized")


# ---------------------------------------------------------------------------
# Zone Management
# ---------------------------------------------------------------------------

def add_zone(user_id, data):
    """Add an irrigation zone.

    Args:
        user_id: Owner user ID.
        data: dict with zone fields (name, area, zone_number, sprinkler_type,
              heads_count, gpm_per_head, precipitation_rate, area_sqft,
              soil_type, root_depth, allowable_depletion, notes).

    Returns:
        New zone ID (int).
    """
    area = data.get('area', '')
    if area not in VALID_AREAS:
        raise ValueError(f"Invalid area '{area}'. Must be one of {VALID_AREAS}")

    sprinkler_type = data.get('sprinkler_type')
    if sprinkler_type and sprinkler_type not in VALID_SPRINKLER_TYPES:
        raise ValueError(f"Invalid sprinkler_type '{sprinkler_type}'. Must be one of {VALID_SPRINKLER_TYPES}")

    soil_type = data.get('soil_type')
    if soil_type and soil_type not in VALID_SOIL_TYPES:
        raise ValueError(f"Invalid soil_type '{soil_type}'. Must be one of {VALID_SOIL_TYPES}")
    allowable_depletion = data.get('allowable_depletion')
    if allowable_depletion is not None and not (0 <= allowable_depletion <= 1):
        raise ValueError("allowable_depletion must be between 0 and 1")

    # Auto-calculate precipitation rate if heads_count, gpm_per_head, and area_sqft provided
    precipitation_rate = data.get('precipitation_rate')
    if precipitation_rate is None:
        heads = data.get('heads_count')
        gpm = data.get('gpm_per_head')
        sqft = data.get('area_sqft')
        if heads and gpm and sqft and sqft > 0:
            # precipitation_rate (in/hr) = (96.25 * total_gpm) / area_sqft
            precipitation_rate = round((96.25 * heads * gpm) / sqft, 3)

    with get_db() as conn:
        cursor = conn.execute('''
            INSERT INTO irrigation_zones (
                user_id, name, area, zone_number, sprinkler_type,
                heads_count, gpm_per_head, precipitation_rate, area_sqft,
                soil_type, root_depth, allowable_depletion, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_id,
            data.get('name', 'Unnamed Zone'),
            area,
            data.get('zone_number'),
            sprinkler_type,
            data.get('heads_count'),
            data.get('gpm_per_head'),
            precipitation_rate,
            data.get('area_sqft'),
            soil_type,
            data.get('root_depth'),
            allowable_depletion,
            data.get('notes'),
        ))
        zone_id = cursor.lastrowid

    logger.info(f"Irrigation zone created: {zone_id} ('{data.get('name')}') for user {user_id}")
    return zone_id

def update_zone(zone_id, user_id, data):
    """Update an irrigation zone.

    Args:
        zone_id: Zone ID to update.
        user_id: Owner user ID (ownership check).
        data: dict of fields to update.

    Returns:
        True if updated, False if zone not found or not owned by user.
    """
    allowed_fields = [
        'name', 'area', 'zone_number', 'sprinkler_type', 'heads_count',
        'gpm_per_head', 'precipitation_rate', 'area_sqft', 'soil_type',
        'root_depth', 'allowable_depletion', 'notes',
    ]

    updates = []
    params = []
    for field in allowed_fields:
        if field in data:
            updates.append(f'{field} = ?')
            params.append(data[field])

    if not updates:
        return False

    # Validate constraints on provided fields
    if 'area' in data and data['area'] not in VALID_AREAS:
        raise ValueError(f"Invalid area '{data['area']}'. Must be one of {VALID_AREAS}")
    if 'sprinkler_type' in data and data['sprinkler_type'] and data['sprinkler_type'] not in VALID_SPRINKLER_TYPES:
        raise ValueError(f"Invalid sprinkler_type. Must be one of {VALID_SPRINKLER_TYPES}")
    if 'soil_type' in data and data['soil_type'] and data['soil_type'] not in VALID_SOIL_TYPES:
        raise ValueError(f"Invalid soil_type. Must be one of {VALID_SOIL_TYPES}")
    if 'allowable_depletion' in data and data['allowable_depletion'] is not None:
        if not (0 <= data['allowable_depletion'] <= 1):
            raise ValueError("allowable_depletion must be between 0 and 1")
    updates.append('updated_at = CURRENT_TIMESTAMP')
    params.extend([zone_id, user_id])

    query = f"UPDATE irrigation_zones SET {', '.join(updates)} WHERE id = ? AND user_id = ?"

    with get_db() as conn:
        cursor = conn.execute(query, params)
        updated = cursor.rowcount > 0

    if updated:
        logger.info(f"Irrigation zone {zone_id} updated for user {user_id}")
    return updated


def delete_zone(zone_id, user_id):
    """Delete an irrigation zone (with ownership check).

    Returns:
        True if deleted, False if not found or not owned.
    """
    with get_db() as conn:
        cursor = conn.execute(
            'DELETE FROM irrigation_zones WHERE id = ? AND user_id = ?',
            (zone_id, user_id)
        )
        deleted = cursor.rowcount > 0

    if deleted:
        logger.info(f"Irrigation zone {zone_id} deleted for user {user_id}")
    return deleted

def get_zones(user_id, area=None):
    """Get all irrigation zones for a user, optionally filtered by area.

    Returns:
        List of zone dicts.
    """
    query = 'SELECT * FROM irrigation_zones WHERE user_id = ?'
    params = [user_id]

    if area and area in VALID_AREAS:
        query += ' AND area = ?'
        params.append(area)

    query += ' ORDER BY area, zone_number'

    with get_db() as conn:
        cursor = conn.execute(query, params)
        rows = cursor.fetchall()

    return [dict(row) for row in rows]


def get_zone_by_id(zone_id, user_id):
    """Get a single irrigation zone by ID (with ownership check).

    Returns:
        Zone dict or None.
    """
    with get_db() as conn:
        cursor = conn.execute(
            'SELECT * FROM irrigation_zones WHERE id = ? AND user_id = ?',
            (zone_id, user_id)
        )
        row = cursor.fetchone()

    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Irrigation Scheduling & Calculations
# ---------------------------------------------------------------------------

def calculate_et_irrigation(zone_id, user_id, et0, crop_coefficient=0.8):
    """Calculate irrigation runtime needed to replace ET losses for a zone.

    Uses the equation:
        ETc = ET0 * Kc  (crop evapotranspiration)
        Runtime (min) = (ETc / precipitation_rate) * 60

    Args:
        zone_id: Irrigation zone ID.
        user_id: Owner user ID.
        et0: Reference evapotranspiration (inches/day).
        crop_coefficient: Kc value (default 0.8 for cool-season turf).

    Returns:
        dict with etc, runtime_minutes, gallons_needed, precipitation_rate,
        or None if zone not found.
    """
    zone = get_zone_by_id(zone_id, user_id)
    if not zone:
        logger.warning(f"Zone {zone_id} not found for user {user_id}")
        return None

    precip_rate = zone.get('precipitation_rate')
    if not precip_rate or precip_rate <= 0:
        logger.warning(f"Zone {zone_id} has no precipitation rate configured")
        return None
    etc = et0 * crop_coefficient
    runtime_minutes = (etc / precip_rate) * 60.0

    # Calculate gallons if area is known
    gallons_needed = None
    area_sqft = zone.get('area_sqft')
    if area_sqft and area_sqft > 0:
        # gallons = inches * sqft * 0.623 (conversion factor)
        gallons_needed = round(etc * area_sqft * 0.623, 1)

    # Check if runtime exceeds soil infiltration capacity
    soil_type = zone.get('soil_type', 'loam')
    infiltration_rate = SOIL_INFILTRATION_RATES.get(soil_type, 0.5)
    cycle_soak = None
    if precip_rate > infiltration_rate:
        # Need cycle-soak: run in shorter cycles to prevent runoff
        max_run_minutes = (infiltration_rate / precip_rate) * 60.0 * 0.8  # 80% safety factor
        if runtime_minutes > max_run_minutes:
            num_cycles = math.ceil(runtime_minutes / max_run_minutes)
            cycle_soak = {
                'recommended': True,
                'cycles': num_cycles,
                'run_minutes': round(max_run_minutes, 1),
                'soak_minutes': round(max_run_minutes * 0.5, 1),
                'total_minutes': round(runtime_minutes, 1),
            }

    return {
        'zone_id': zone_id,
        'zone_name': zone.get('name'),
        'et0': et0,
        'crop_coefficient': crop_coefficient,
        'etc': round(etc, 4),
        'precipitation_rate': precip_rate,
        'runtime_minutes': round(runtime_minutes, 1),
        'gallons_needed': gallons_needed,
        'cycle_soak': cycle_soak,
    }

def calculate_deficit(zone_id, user_id, days=7):
    """Calculate water balance deficit for a zone over recent days.

    Deficit = sum(ETc) - sum(rainfall) - sum(irrigation applied)
    Positive deficit = zone needs water.

    Args:
        zone_id: Irrigation zone ID.
        user_id: Owner user ID.
        days: Number of days to look back (default 7).

    Returns:
        dict with total_et, total_rainfall, total_irrigation, deficit_inches,
        or None if zone not found.
    """
    zone = get_zone_by_id(zone_id, user_id)
    if not zone:
        return None

    area = zone.get('area', 'fairways')
    kc = DEFAULT_CROP_COEFFICIENTS.get(area, 0.80)
    cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

    # Sum ET data
    with get_db() as conn:
        cursor = conn.execute(
            'SELECT COALESCE(SUM(et0), 0) as total_et0, COALESCE(SUM(rainfall), 0) as total_rain '
            'FROM et_data WHERE user_id = ? AND date >= ?',
            (user_id, cutoff)
        )
        et_row = cursor.fetchone()
    total_et0 = float(et_row['total_et0']) if et_row else 0.0
    total_rainfall = float(et_row['total_rain']) if et_row else 0.0
    total_etc = total_et0 * kc

    # Sum irrigation applied to this zone
    with get_db() as conn:
        cursor = conn.execute(
            'SELECT COALESCE(SUM(inches_applied), 0) as total_irr '
            'FROM irrigation_runs WHERE zone_id = ? AND user_id = ? AND run_date >= ?',
            (zone_id, user_id, cutoff)
        )
        irr_row = cursor.fetchone()

    total_irrigation = float(irr_row['total_irr']) if irr_row else 0.0

    deficit = total_etc - total_rainfall - total_irrigation

    # Calculate soil moisture available water
    # Use `or` fallback because .get() returns None when the DB value is NULL
    soil_type = zone.get('soil_type') or 'loam'
    root_depth = zone.get('root_depth') or 6.0
    allowable_depletion = zone.get('allowable_depletion') or 0.5
    awc = SOIL_AWC.get(soil_type, 0.17)
    total_available_water = awc * root_depth
    management_allowed_deficit = total_available_water * allowable_depletion

    return {
        'zone_id': zone_id,
        'zone_name': zone.get('name'),
        'days': days,
        'crop_coefficient': kc,
        'total_et0': round(total_et0, 3),
        'total_etc': round(total_etc, 3),
        'total_rainfall': round(total_rainfall, 3),
        'total_irrigation': round(total_irrigation, 3),
        'deficit_inches': round(max(0, deficit), 3),
        'surplus_inches': round(abs(min(0, deficit)), 3),
        'management_allowed_deficit': round(management_allowed_deficit, 3),
        'needs_water': deficit > (management_allowed_deficit * 0.5),
    }

def get_irrigation_recommendation(user_id, zone_id=None):
    """Generate irrigation recommendations for a user's zones.

    Analyzes recent ET data, rainfall, irrigation history, and soil moisture
    to produce actionable recommendations.

    Args:
        user_id: Owner user ID.
        zone_id: Optional specific zone ID. If None, recommends for all zones.

    Returns:
        dict with recommendations per zone.
    """
    if zone_id:
        zones = [get_zone_by_id(zone_id, user_id)]
        zones = [z for z in zones if z]
    else:
        zones = get_zones(user_id)

    if not zones:
        return {'recommendations': [], 'summary': 'No irrigation zones configured.'}

    # Get latest ET data
    with get_db() as conn:
        cursor = conn.execute(
            'SELECT * FROM et_data WHERE user_id = ? ORDER BY date DESC LIMIT 1',
            (user_id,)
        )
        latest_et = cursor.fetchone()

    latest_et0 = float(latest_et['et0']) if latest_et else None
    recommendations = []
    for zone in zones:
        zid = zone['id']
        area = zone.get('area', 'fairways')
        zone_name = zone.get('name', f"Zone {zone.get('zone_number', '?')}")
        kc = DEFAULT_CROP_COEFFICIENTS.get(area, 0.80)

        # Calculate deficit
        deficit_data = calculate_deficit(zid, user_id, days=7)

        # Get latest moisture reading
        with get_db() as conn:
            cursor = conn.execute(
                'SELECT * FROM soil_moisture_readings WHERE zone_id = ? AND user_id = ? '
                'ORDER BY reading_date DESC LIMIT 1',
                (zid, user_id)
            )
            latest_moisture = cursor.fetchone()

        moisture_pct = float(latest_moisture['moisture_pct']) if latest_moisture else None

        # Build recommendation
        rec = {
            'zone_id': zid,
            'zone_name': zone_name,
            'area': area,
            'deficit': deficit_data,
            'latest_moisture_pct': moisture_pct,
            'latest_et0': latest_et0,
            'action': 'monitor',
            'priority': 'low',
            'message': '',
        }
        if deficit_data and deficit_data.get('needs_water'):
            deficit_in = deficit_data['deficit_inches']

            if deficit_in > 0.5:
                rec['action'] = 'irrigate'
                rec['priority'] = 'high'
                rec['message'] = (
                    f"{zone_name} has a {deficit_in:.2f}\" water deficit over the last 7 days. "
                    f"Irrigate to apply approximately {deficit_in:.2f}\" of water."
                )
            elif deficit_in > 0.2:
                rec['action'] = 'irrigate'
                rec['priority'] = 'medium'
                rec['message'] = (
                    f"{zone_name} is approaching a water deficit ({deficit_in:.2f}\"). "
                    f"Schedule irrigation within the next 24-48 hours."
                )
            else:
                rec['action'] = 'monitor'
                rec['priority'] = 'low'
                rec['message'] = (
                    f"{zone_name} water balance is adequate. "
                    f"Small deficit of {deficit_in:.2f}\" — continue monitoring."
                )

            # Add runtime recommendation if ET data is available
            if latest_et0 and zone.get('precipitation_rate'):
                et_calc = calculate_et_irrigation(zid, user_id, latest_et0, kc)
                if et_calc:
                    rec['suggested_runtime_minutes'] = et_calc['runtime_minutes']
                    rec['cycle_soak'] = et_calc.get('cycle_soak')
        else:
            rec['message'] = f"{zone_name} has adequate moisture. No irrigation needed."
        # Factor in soil moisture reading if available
        if moisture_pct is not None:
            if moisture_pct < 15:
                rec['priority'] = 'high'
                rec['action'] = 'irrigate'
                rec['message'] += f" Soil moisture is critically low ({moisture_pct:.1f}%)."
            elif moisture_pct < 25:
                if rec['priority'] == 'low':
                    rec['priority'] = 'medium'
                rec['message'] += f" Soil moisture is declining ({moisture_pct:.1f}%)."

        recommendations.append(rec)

    # Sort by priority
    priority_order = {'high': 0, 'medium': 1, 'low': 2}
    recommendations.sort(key=lambda r: priority_order.get(r['priority'], 3))

    # Summary
    high_count = sum(1 for r in recommendations if r['priority'] == 'high')
    medium_count = sum(1 for r in recommendations if r['priority'] == 'medium')

    if high_count:
        summary = f"{high_count} zone(s) need immediate irrigation."
    elif medium_count:
        summary = f"{medium_count} zone(s) should be irrigated within 24-48 hours."
    else:
        summary = "All zones have adequate moisture levels."

    return {
        'recommendations': recommendations,
        'summary': summary,
        'generated_at': datetime.now().isoformat(),
    }

def log_irrigation_run(user_id, data):
    """Log an irrigation run.

    Args:
        user_id: Owner user ID.
        data: dict with zone_id, run_date, start_time, duration_minutes,
              gallons_applied, inches_applied, run_type, weather_conditions, notes.

    Returns:
        New run ID (int).
    """
    zone_id = data.get('zone_id')
    if not zone_id:
        raise ValueError("zone_id is required")

    run_type = data.get('run_type', 'scheduled')
    if run_type not in VALID_RUN_TYPES:
        raise ValueError(f"Invalid run_type '{run_type}'. Must be one of {VALID_RUN_TYPES}")

    # Auto-calculate inches_applied if duration and precipitation_rate known
    inches_applied = data.get('inches_applied')
    zone = None
    if inches_applied is None and data.get('duration_minutes'):
        zone = get_zone_by_id(zone_id, user_id)
        if zone and zone.get('precipitation_rate'):
            inches_applied = round(
                (data['duration_minutes'] / 60.0) * zone['precipitation_rate'], 3
            )
    # Auto-calculate gallons_applied if inches and area known
    gallons_applied = data.get('gallons_applied')
    if gallons_applied is None and inches_applied:
        if zone is None:
            zone = get_zone_by_id(zone_id, user_id)
        if zone and zone.get('area_sqft'):
            gallons_applied = round(inches_applied * zone['area_sqft'] * 0.623, 1)

    with get_db() as conn:
        cursor = conn.execute('''
            INSERT INTO irrigation_runs (
                zone_id, user_id, run_date, start_time, duration_minutes,
                gallons_applied, inches_applied, run_type, weather_conditions, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            zone_id,
            user_id,
            data.get('run_date', datetime.now().strftime('%Y-%m-%d')),
            data.get('start_time'),
            data.get('duration_minutes'),
            gallons_applied,
            inches_applied,
            run_type,
            data.get('weather_conditions'),
            data.get('notes'),
        ))
        run_id = cursor.lastrowid

    logger.info(f"Irrigation run logged: {run_id} for zone {zone_id}, user {user_id}")
    return run_id

def get_irrigation_history(user_id, zone_id=None, start_date=None, end_date=None):
    """Get irrigation run history with optional filters.

    Returns:
        List of irrigation run dicts.
    """
    query = 'SELECT r.*, z.name as zone_name, z.area as zone_area FROM irrigation_runs r '
    query += 'LEFT JOIN irrigation_zones z ON r.zone_id = z.id '
    query += 'WHERE r.user_id = ?'
    params = [user_id]

    if zone_id:
        query += ' AND r.zone_id = ?'
        params.append(zone_id)

    if start_date:
        query += ' AND r.run_date >= ?'
        params.append(start_date)

    if end_date:
        query += ' AND r.run_date <= ?'
        params.append(end_date)

    query += ' ORDER BY r.run_date DESC, r.start_time DESC'

    with get_db() as conn:
        cursor = conn.execute(query, params)
        rows = cursor.fetchall()

    return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# Soil Moisture
# ---------------------------------------------------------------------------

def log_moisture_reading(user_id, data):
    """Log a soil moisture reading.

    Args:
        user_id: Owner user ID.
        data: dict with zone_id, reading_date, moisture_pct, reading_depth,
              method, notes.

    Returns:
        New reading ID (int).
    """
    zone_id = data.get('zone_id')
    if not zone_id:
        raise ValueError("zone_id is required")

    method = data.get('method')
    if method and method not in VALID_MOISTURE_METHODS:
        raise ValueError(f"Invalid method '{method}'. Must be one of {VALID_MOISTURE_METHODS}")

    with get_db() as conn:
        cursor = conn.execute('''
            INSERT INTO soil_moisture_readings (
                zone_id, user_id, reading_date, moisture_pct, reading_depth,
                method, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            zone_id,
            user_id,
            data.get('reading_date', datetime.now().strftime('%Y-%m-%d')),
            data.get('moisture_pct'),
            data.get('reading_depth'),
            method,
            data.get('notes'),
        ))
        reading_id = cursor.lastrowid

    logger.info(f"Moisture reading logged: {reading_id} for zone {zone_id}, user {user_id}")
    return reading_id

def get_moisture_readings(user_id, zone_id=None, start_date=None, end_date=None):
    """Get soil moisture readings with optional filters.

    Returns:
        List of reading dicts.
    """
    query = 'SELECT m.*, z.name as zone_name, z.area as zone_area FROM soil_moisture_readings m '
    query += 'LEFT JOIN irrigation_zones z ON m.zone_id = z.id '
    query += 'WHERE m.user_id = ?'
    params = [user_id]

    if zone_id:
        query += ' AND m.zone_id = ?'
        params.append(zone_id)

    if start_date:
        query += ' AND m.reading_date >= ?'
        params.append(start_date)

    if end_date:
        query += ' AND m.reading_date <= ?'
        params.append(end_date)

    query += ' ORDER BY m.reading_date DESC'

    with get_db() as conn:
        cursor = conn.execute(query, params)
        rows = cursor.fetchall()

    return [dict(row) for row in rows]

def get_moisture_trend(zone_id, user_id, days=30):
    """Get moisture trend data for charting.

    Args:
        zone_id: Irrigation zone ID.
        user_id: Owner user ID.
        days: Number of days of data to include (default 30).

    Returns:
        dict with data points for charting (date, moisture_pct, method).
    """
    cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

    with get_db() as conn:
        cursor = conn.execute(
            'SELECT reading_date, moisture_pct, reading_depth, method '
            'FROM soil_moisture_readings '
            'WHERE zone_id = ? AND user_id = ? AND reading_date >= ? '
            'ORDER BY reading_date ASC',
            (zone_id, user_id, cutoff)
        )
        rows = cursor.fetchall()

    data_points = [dict(row) for row in rows]

    # Calculate trend statistics
    if data_points:
        values = [dp['moisture_pct'] for dp in data_points if dp.get('moisture_pct') is not None]
        if values:
            avg = sum(values) / len(values)
            min_val = min(values)
            max_val = max(values)
            # Simple trend: compare first half average to second half average
            mid = len(values) // 2
            if mid > 0:
                first_half_avg = sum(values[:mid]) / mid
                second_half_avg = sum(values[mid:]) / (len(values) - mid)
                trend_direction = 'increasing' if second_half_avg > first_half_avg + 1 else (
                    'decreasing' if second_half_avg < first_half_avg - 1 else 'stable'
                )
            else:
                trend_direction = 'insufficient_data'

            return {
                'zone_id': zone_id,
                'days': days,
                'data_points': data_points,
                'statistics': {
                    'average': round(avg, 1),
                    'min': round(min_val, 1),
                    'max': round(max_val, 1),
                    'readings_count': len(values),
                    'trend': trend_direction,
                },
            }

    return {
        'zone_id': zone_id,
        'days': days,
        'data_points': data_points,
        'statistics': None,
    }


# ---------------------------------------------------------------------------
# ET and Water Balance
# ---------------------------------------------------------------------------

def log_et_data(user_id, data):
    """Log evapotranspiration and weather data for a day.

    Args:
        user_id: Owner user ID.
        data: dict with date, et0, rainfall, high_temp, low_temp, humidity,
              wind_speed, solar_radiation, source.

    Returns:
        New ET data record ID (int).
    """
    source = data.get('source', 'manual')
    if source not in VALID_ET_SOURCES:
        raise ValueError(f"Invalid source '{source}'. Must be one of {VALID_ET_SOURCES}")

    # Auto-calculate ET0 from temperature if not provided
    et0 = data.get('et0')
    if et0 is None and data.get('high_temp') is not None and data.get('low_temp') is not None:
        day_of_year = datetime.strptime(
            data.get('date', datetime.now().strftime('%Y-%m-%d')), '%Y-%m-%d'
        ).timetuple().tm_yday
        et0 = calculate_hargreaves_et0(
            data['high_temp'], data['low_temp'],
            latitude=35.0,  # Default mid-latitude; provide ET0 directly for accuracy
            day_of_year=day_of_year
        )
    with get_db() as conn:
        cursor = conn.execute('''
            INSERT INTO et_data (
                user_id, date, et0, rainfall, high_temp, low_temp,
                humidity, wind_speed, solar_radiation, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_id,
            data.get('date', datetime.now().strftime('%Y-%m-%d')),
            et0,
            data.get('rainfall', 0),
            data.get('high_temp'),
            data.get('low_temp'),
            data.get('humidity'),
            data.get('wind_speed'),
            data.get('solar_radiation'),
            source,
        ))
        record_id = cursor.lastrowid

    logger.info(f"ET data logged for {data.get('date')}, user {user_id} (ET0={et0})")
    return record_id

def calculate_hargreaves_et0(tmax, tmin, latitude, day_of_year):
    """Estimate reference ET0 using the Hargreaves-Samani equation.

    ET0 = 0.0023 * (Tmean + 17.8) * (Tmax - Tmin)^0.5 * Ra

    where Ra is extraterrestrial radiation estimated from latitude and
    day of year.

    All temperatures in Fahrenheit (converted to Celsius internally).
    Returns ET0 in inches/day.

    Args:
        tmax: Maximum daily temperature (Fahrenheit).
        tmin: Minimum daily temperature (Fahrenheit).
        latitude: Site latitude in decimal degrees.
        day_of_year: Julian day (1-366).

    Returns:
        ET0 in inches/day (float).
    """
    # Convert Fahrenheit to Celsius
    tmax_c = (tmax - 32.0) * 5.0 / 9.0
    tmin_c = (tmin - 32.0) * 5.0 / 9.0
    tmean_c = (tmax_c + tmin_c) / 2.0

    # Guard against negative temperature range
    temp_range = max(0, tmax_c - tmin_c)

    # Calculate extraterrestrial radiation (Ra) in MJ/m2/day
    ra = _calculate_extraterrestrial_radiation(latitude, day_of_year)
    # Hargreaves equation: ET0 in mm/day
    et0_mm = 0.0023 * (tmean_c + 17.8) * math.sqrt(temp_range) * ra

    # Ensure non-negative
    et0_mm = max(0.0, et0_mm)

    # Convert mm to inches
    et0_inches = et0_mm / 25.4

    return round(et0_inches, 4)


def _calculate_extraterrestrial_radiation(latitude, day_of_year):
    """Calculate extraterrestrial radiation (Ra) in MJ/m2/day.

    Based on FAO-56 equations for solar radiation at the top of the atmosphere.

    Args:
        latitude: Decimal degrees.
        day_of_year: Julian day (1-366).

    Returns:
        Ra in MJ/m2/day.
    """
    # Solar constant
    gsc = 0.0820  # MJ/m2/min

    # Convert latitude to radians
    phi = math.radians(latitude)
    # Inverse relative distance Earth-Sun
    dr = 1 + 0.033 * math.cos(2 * math.pi * day_of_year / 365)

    # Solar declination (radians)
    delta = 0.409 * math.sin(2 * math.pi * day_of_year / 365 - 1.39)

    # Sunset hour angle (radians)
    ws_arg = -math.tan(phi) * math.tan(delta)
    # Clamp to [-1, 1] for arccos domain
    ws_arg = max(-1.0, min(1.0, ws_arg))
    ws = math.acos(ws_arg)

    # Extraterrestrial radiation
    ra = (24 * 60 / math.pi) * gsc * dr * (
        ws * math.sin(phi) * math.sin(delta) +
        math.cos(phi) * math.cos(delta) * math.sin(ws)
    )

    return max(0.0, ra)

def get_water_balance(user_id, zone_id, days=14):
    """Get daily water balance data for charting.

    Returns daily breakdown of ET, rainfall, and irrigation for a zone.

    Args:
        user_id: Owner user ID.
        zone_id: Irrigation zone ID.
        days: Number of days to include (default 14).

    Returns:
        dict with daily data and running balance.
    """
    zone = get_zone_by_id(zone_id, user_id)
    if not zone:
        return None

    area = zone.get('area', 'fairways')
    kc = DEFAULT_CROP_COEFFICIENTS.get(area, 0.80)
    cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

    # Get ET data for the period
    with get_db() as conn:
        cursor = conn.execute(
            'SELECT date, et0, rainfall FROM et_data '
            'WHERE user_id = ? AND date >= ? ORDER BY date ASC',
            (user_id, cutoff)
        )
        et_rows = cursor.fetchall()
    # Get irrigation runs for this zone
    with get_db() as conn:
        cursor = conn.execute(
            'SELECT run_date, COALESCE(SUM(inches_applied), 0) as total_inches '
            'FROM irrigation_runs '
            'WHERE zone_id = ? AND user_id = ? AND run_date >= ? '
            'GROUP BY run_date ORDER BY run_date ASC',
            (zone_id, user_id, cutoff)
        )
        irr_rows = cursor.fetchall()

    # Build lookup dicts
    et_by_date = {}
    for row in et_rows:
        et_by_date[row['date']] = {
            'et0': float(row['et0']) if row['et0'] else 0,
            'rainfall': float(row['rainfall']) if row['rainfall'] else 0,
        }

    irr_by_date = {}
    for row in irr_rows:
        irr_by_date[row['run_date']] = float(row['total_inches'])
    # Build daily balance
    daily_data = []
    running_balance = 0.0
    current_date = datetime.now() - timedelta(days=days)

    for i in range(days + 1):
        date_str = current_date.strftime('%Y-%m-%d')
        et_info = et_by_date.get(date_str, {'et0': 0, 'rainfall': 0})
        etc = et_info['et0'] * kc
        rainfall = et_info['rainfall']
        irrigation = irr_by_date.get(date_str, 0)

        daily_net = rainfall + irrigation - etc
        running_balance += daily_net

        daily_data.append({
            'date': date_str,
            'et0': round(et_info['et0'], 4),
            'etc': round(etc, 4),
            'rainfall': round(rainfall, 3),
            'irrigation': round(irrigation, 3),
            'daily_net': round(daily_net, 3),
            'running_balance': round(running_balance, 3),
        })

        current_date += timedelta(days=1)

    return {
        'zone_id': zone_id,
        'zone_name': zone.get('name'),
        'crop_coefficient': kc,
        'days': days,
        'daily_data': daily_data,
        'total_et': round(sum(d['etc'] for d in daily_data), 3),
        'total_rainfall': round(sum(d['rainfall'] for d in daily_data), 3),
        'total_irrigation': round(sum(d['irrigation'] for d in daily_data), 3),
        'net_balance': round(running_balance, 3),
    }

def get_weekly_water_report(user_id):
    """Generate a weekly summary of water usage across all zones.

    Returns:
        dict with per-zone and aggregate water usage data for the past 7 days.
    """
    cutoff = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    zones = get_zones(user_id)

    zone_reports = []
    total_gallons = 0.0
    total_inches_all = 0.0

    for zone in zones:
        zid = zone['id']

        with get_db() as conn:
            cursor = conn.execute(
                'SELECT COUNT(*) as run_count, '
                'COALESCE(SUM(duration_minutes), 0) as total_minutes, '
                'COALESCE(SUM(gallons_applied), 0) as total_gallons, '
                'COALESCE(SUM(inches_applied), 0) as total_inches '
                'FROM irrigation_runs '
                'WHERE zone_id = ? AND user_id = ? AND run_date >= ?',
                (zid, user_id, cutoff)
            )
            row = cursor.fetchone()
        run_count = int(row['run_count']) if row else 0
        zone_gallons = float(row['total_gallons']) if row else 0
        zone_inches = float(row['total_inches']) if row else 0
        zone_minutes = float(row['total_minutes']) if row else 0

        total_gallons += zone_gallons
        total_inches_all += zone_inches

        zone_reports.append({
            'zone_id': zid,
            'zone_name': zone.get('name'),
            'area': zone.get('area'),
            'run_count': run_count,
            'total_minutes': round(zone_minutes, 1),
            'total_gallons': round(zone_gallons, 1),
            'total_inches': round(zone_inches, 3),
        })

    # Get ET and rainfall totals for the week
    with get_db() as conn:
        cursor = conn.execute(
            'SELECT COALESCE(SUM(et0), 0) as total_et0, '
            'COALESCE(SUM(rainfall), 0) as total_rain '
            'FROM et_data WHERE user_id = ? AND date >= ?',
            (user_id, cutoff)
        )
        et_row = cursor.fetchone()

    total_et0 = float(et_row['total_et0']) if et_row else 0.0
    total_rainfall = float(et_row['total_rain']) if et_row else 0.0
    # Get water meter usage for the week
    with get_db() as conn:
        cursor = conn.execute(
            'SELECT COALESCE(SUM(total_gallons), 0) as metered_gallons, '
            'COALESCE(SUM(cost), 0) as total_cost '
            'FROM water_usage WHERE user_id = ? AND date >= ?',
            (user_id, cutoff)
        )
        usage_row = cursor.fetchone()

    metered_gallons = float(usage_row['metered_gallons']) if usage_row else 0.0
    water_cost = float(usage_row['total_cost']) if usage_row else 0.0

    return {
        'period': f"{cutoff} to {datetime.now().strftime('%Y-%m-%d')}",
        'zones': zone_reports,
        'totals': {
            'irrigation_gallons': round(total_gallons, 1),
            'metered_gallons': round(metered_gallons, 1),
            'water_cost': round(water_cost, 2),
            'et0_inches': round(total_et0, 3),
            'rainfall_inches': round(total_rainfall, 3),
        },
        'generated_at': datetime.now().isoformat(),
    }


# ---------------------------------------------------------------------------
# Water Usage Tracking
# ---------------------------------------------------------------------------

def log_water_usage(user_id, data):
    """Log a water usage meter reading or daily total.

    Args:
        user_id: Owner user ID.
        data: dict with date, total_gallons, meter_reading, cost, notes.

    Returns:
        New record ID (int).
    """
    with get_db() as conn:
        cursor = conn.execute('''
            INSERT INTO water_usage (
                user_id, date, total_gallons, meter_reading, cost, notes
            ) VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            user_id,
            data.get('date', datetime.now().strftime('%Y-%m-%d')),
            data.get('total_gallons'),
            data.get('meter_reading'),
            data.get('cost'),
            data.get('notes'),
        ))
        record_id = cursor.lastrowid

    logger.info(f"Water usage logged for {data.get('date')}, user {user_id}")
    return record_id

def get_water_usage(user_id, start_date=None, end_date=None):
    """Get water usage records with optional date filters.

    Returns:
        List of water usage dicts.
    """
    query = 'SELECT * FROM water_usage WHERE user_id = ?'
    params = [user_id]

    if start_date:
        query += ' AND date >= ?'
        params.append(start_date)

    if end_date:
        query += ' AND date <= ?'
        params.append(end_date)

    query += ' ORDER BY date DESC'

    with get_db() as conn:
        cursor = conn.execute(query, params)
        rows = cursor.fetchall()

    return [dict(row) for row in rows]

def get_water_cost_summary(user_id, year=None):
    """Get monthly water cost breakdown for a year.

    Args:
        user_id: Owner user ID.
        year: Year to summarize (default: current year).

    Returns:
        dict with monthly cost and usage totals.
    """
    if year is None:
        year = datetime.now().year

    start = f'{year}-01-01'
    end = f'{year}-12-31'

    records = get_water_usage(user_id, start_date=start, end_date=end)

    monthly = {}
    for rec in records:
        try:
            month = int(rec['date'].split('-')[1])
        except (IndexError, ValueError, TypeError):
            continue

        if month not in monthly:
            monthly[month] = {'gallons': 0.0, 'cost': 0.0, 'readings': 0}

        monthly[month]['gallons'] += float(rec.get('total_gallons') or 0)
        monthly[month]['cost'] += float(rec.get('cost') or 0)
        monthly[month]['readings'] += 1
    # Round values
    for m in monthly:
        monthly[m]['gallons'] = round(monthly[m]['gallons'], 1)
        monthly[m]['cost'] = round(monthly[m]['cost'], 2)

    total_gallons = sum(m['gallons'] for m in monthly.values())
    total_cost = sum(m['cost'] for m in monthly.values())

    return {
        'year': year,
        'monthly': monthly,
        'annual_total_gallons': round(total_gallons, 1),
        'annual_total_cost': round(total_cost, 2),
        'cost_per_1000_gallons': round(
            (total_cost / total_gallons) * 1000, 2
        ) if total_gallons > 0 else 0,
    }

def get_gallons_per_acre(user_id, start_date, end_date):
    """Calculate water usage efficiency (gallons per acre) for a period.

    Combines metered water usage with irrigated acreage from zone data.

    Args:
        user_id: Owner user ID.
        start_date: Period start (YYYY-MM-DD).
        end_date: Period end (YYYY-MM-DD).

    Returns:
        dict with gallons_per_acre and breakdown.
    """
    # Total water usage for the period
    usage_records = get_water_usage(user_id, start_date=start_date, end_date=end_date)
    total_gallons = sum(float(r.get('total_gallons') or 0) for r in usage_records)

    # Total irrigated acreage from zones
    zones = get_zones(user_id)
    total_sqft = sum(float(z.get('area_sqft') or 0) for z in zones)
    total_acres = total_sqft / 43560.0 if total_sqft > 0 else 0

    gallons_per_acre = round(total_gallons / total_acres, 1) if total_acres > 0 else 0

    return {
        'start_date': start_date,
        'end_date': end_date,
        'total_gallons': round(total_gallons, 1),
        'total_acres': round(total_acres, 2),
        'gallons_per_acre': gallons_per_acre,
        'zone_count': len(zones),
    }


# ---------------------------------------------------------------------------
# Drought Protocols
# ---------------------------------------------------------------------------

def get_drought_status(user_id):
    """Assess current drought status based on water deficit data.

    Analyzes the past 14 days of ET, rainfall, and irrigation to determine
    the overall moisture status and drought severity level.

    Returns:
        dict with drought level, deficit data, and status description.
    """
    zones = get_zones(user_id)
    if not zones:
        return {
            'level': 'unknown',
            'message': 'No irrigation zones configured. Add zones to track drought status.',
        }

    # Aggregate deficits across all zones
    deficits = []
    for zone in zones:
        deficit_data = calculate_deficit(zone['id'], user_id, days=14)
        if deficit_data:
            deficits.append(deficit_data)

    if not deficits:
        return {
            'level': 'unknown',
            'message': 'Insufficient data to assess drought status. Log ET data and irrigation runs.',
        }
    # Average deficit across zones
    avg_deficit = sum(d['deficit_inches'] for d in deficits) / len(deficits)
    max_deficit = max(d['deficit_inches'] for d in deficits)
    total_et = sum(d['total_etc'] for d in deficits) / len(deficits)
    total_rain = sum(d['total_rainfall'] for d in deficits) / len(deficits)

    # Calculate deficit as percentage of ET demand
    deficit_pct = (avg_deficit / total_et * 100) if total_et > 0 else 0

    # Determine drought level
    if deficit_pct < 10:
        level = 'none'
        description = 'Adequate moisture. Water balance is healthy.'
    elif deficit_pct < 25:
        level = 'watch'
        description = 'Mild moisture deficit. Monitor conditions and consider supplemental irrigation.'
    elif deficit_pct < 50:
        level = 'moderate'
        description = 'Moderate drought stress. Increase irrigation frequency and prioritize high-value areas.'
    elif deficit_pct < 75:
        level = 'severe'
        description = 'Severe drought conditions. Implement water conservation protocols immediately.'
    else:
        level = 'extreme'
        description = 'Extreme drought. Triage irrigation to protect greens and critical areas only.'
    # Find most stressed zones
    zones_needing_water = [d for d in deficits if d.get('needs_water')]
    zones_needing_water.sort(key=lambda d: d['deficit_inches'], reverse=True)

    return {
        'level': level,
        'deficit_pct': round(deficit_pct, 1),
        'avg_deficit_inches': round(avg_deficit, 3),
        'max_deficit_inches': round(max_deficit, 3),
        'avg_et_14day': round(total_et, 3),
        'avg_rainfall_14day': round(total_rain, 3),
        'zones_assessed': len(deficits),
        'zones_needing_water': len(zones_needing_water),
        'most_stressed_zones': [
            {'zone_id': d['zone_id'], 'zone_name': d['zone_name'], 'deficit': d['deficit_inches']}
            for d in zones_needing_water[:5]
        ],
        'description': description,
        'recommendations': get_drought_protocol_recommendations(deficit_pct),
    }

def get_drought_protocol_recommendations(deficit_pct):
    """Get recommended actions based on drought severity.

    Args:
        deficit_pct: Water deficit as a percentage of ET demand.

    Returns:
        list of recommendation strings.
    """
    if deficit_pct < 10:
        return [
            'Continue normal irrigation scheduling.',
            'Monitor weather forecasts for upcoming dry periods.',
            'Consider banking soil moisture if rain is forecast.',
        ]
    elif deficit_pct < 25:
        return [
            'Increase irrigation cycle frequency by 10-15%.',
            'Apply wetting agents to improve water infiltration.',
            'Raise mowing heights by 0.5-1mm on greens, 0.25" on fairways.',
            'Monitor soil moisture more frequently (daily on greens).',
            'Reduce nitrogen applications to slow growth and water demand.',
        ]
    elif deficit_pct < 50:
        return [
            'Prioritize irrigation: greens > tees > fairways > rough.',
            'Implement syringing on greens during peak heat (11am-2pm).',
            'Raise mowing heights across all areas.',
            'Apply wetting agents on a tighter schedule.',
            'Suspend topdressing and aerification to reduce stress.',
            'Reduce foot traffic on stressed areas where possible.',
            'Hand-water hot spots and slopes.',
            'Consider reducing irrigation on rough areas by 30-50%.',
        ]
    elif deficit_pct < 75:
        return [
            'SEVERE: Focus all available water on greens and tees.',
            'Syringe greens 2-3 times daily during extreme heat.',
            'Cease irrigation on rough areas entirely if needed.',
            'Reduce fairway irrigation to 50% of ET replacement.',
            'Raise all mowing heights to maximum acceptable levels.',
            'Suspend all cultural practices that stress turf.',
            'Apply pigments or colorants to dormant rough areas.',
            'Communicate with membership about turf conditions.',
            'Install temporary shade on most vulnerable greens.',
        ]
    else:
        return [
            'EXTREME: Emergency triage — water greens only if supply is critical.',
            'Syringe greens continuously during peak heat.',
            'Allow fairways and rough to go dormant.',
            'Apply colorants to maintain appearance on dormant areas.',
            'Maximize all mowing heights.',
            'Consider emergency water sourcing (tanker trucks, temporary wells).',
            'Communicate drought plan to all stakeholders.',
            'Document conditions with photos for insurance records.',
            'Plan for recovery program once water restrictions ease.',
            'Consult with local extension office for additional guidance.',
        ]


def delete_irrigation_run(run_id, user_id):
    """Delete an irrigation run record."""
    with get_db() as conn:
        conn.execute(
            '''DELETE FROM irrigation_runs WHERE id = ? AND zone_id IN
               (SELECT id FROM irrigation_zones WHERE user_id = ?)''',
            (run_id, user_id)
        )
    return {'deleted': True}


def delete_moisture_reading(reading_id, user_id):
    """Delete a moisture reading."""
    with get_db() as conn:
        conn.execute(
            '''DELETE FROM soil_moisture_readings WHERE id = ? AND zone_id IN
               (SELECT id FROM irrigation_zones WHERE user_id = ?)''',
            (reading_id, user_id)
        )
    return {'deleted': True}


def delete_water_usage(usage_id, user_id):
    """Delete a water usage record."""
    with get_db() as conn:
        conn.execute(
            'DELETE FROM water_usage WHERE id = ? AND user_id = ?',
            (usage_id, user_id)
        )
    return {'deleted': True}


def get_et_data(user_id, start_date=None, end_date=None):
    """Get ET data entries for a user."""
    with get_db() as conn:
        query = 'SELECT * FROM et_data WHERE user_id = ?'
        params = [user_id]
        if start_date:
            query += ' AND date >= ?'
            params.append(start_date)
        if end_date:
            query += ' AND date <= ?'
            params.append(end_date)
        query += ' ORDER BY date DESC'
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]