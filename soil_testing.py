"""
Soil Testing Integration Module for Greenside AI.

Complete soil test management including:
- Soil test CRUD with full nutrient panels
- Amendment recommendations (lime, sulfur, gypsum, fertilizer)
- Trend analysis and nutrient comparisons
- Water quality testing and SAR calculations
- Hardcoded agronomic optimal ranges by grass type and area

Uses the shared db.py layer (SQLite/PostgreSQL dual-backend).
"""

import math
import logging
from datetime import datetime

from db import get_db, is_postgres, add_column

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_AREAS = ['greens', 'fairways', 'tees', 'rough']

VALID_AMENDMENT_TYPES = [
    'lime', 'sulfur', 'gypsum', 'fertilizer', 'organic', 'other',
]

VALID_WATER_SOURCES = ['well', 'municipal', 'pond', 'reclaimed']

# Soil types and their lime/sulfur requirement factors
SOIL_TYPE_FACTORS = {
    'sand': 0.6,
    'sandy_loam': 0.8,
    'loam': 1.0,
    'silt_loam': 1.1,
    'clay_loam': 1.2,
    'clay': 1.4,
}

# SMP buffer pH lime requirement factors
# (lbs CaCO3 per 1000 sqft per 0.1 pH unit)
SMP_LIME_FACTORS = {
    6.0: 3.4,
    6.2: 3.8,
    6.5: 4.5,
    6.8: 5.2,
    7.0: 5.8,
}


# ---------------------------------------------------------------------------
# Optimal Ranges by Grass Type and Area
# ---------------------------------------------------------------------------

OPTIMAL_RANGES = {
    'bentgrass_greens': {
        'ph': (5.8, 6.5),
        'organic_matter': (2.0, 4.0),
        'cec': (8.0, 20.0),
        'phosphorus_ppm': (25.0, 50.0),
        'potassium_ppm': (80.0, 150.0),
        'calcium_ppm': (600.0, 1200.0),
        'magnesium_ppm': (80.0, 200.0),
        'sulfur_ppm': (15.0, 40.0),
        'iron_ppm': (50.0, 200.0),
        'manganese_ppm': (10.0, 80.0),
        'zinc_ppm': (2.0, 10.0),
        'copper_ppm': (1.0, 5.0),
        'boron_ppm': (0.5, 2.0),
        'base_saturation_ca': (55.0, 70.0),
        'base_saturation_mg': (10.0, 20.0),
        'base_saturation_k': (3.0, 7.0),
        'base_saturation_na': (0.0, 3.0),
        'sand_pct': (85.0, 98.0),
        'ec': (0.0, 1.5),
    },
    'bermudagrass_fairways': {
        'ph': (6.0, 7.0),
        'organic_matter': (1.0, 3.0),
        'cec': (8.0, 25.0),
        'phosphorus_ppm': (30.0, 60.0),
        'potassium_ppm': (100.0, 200.0),
        'calcium_ppm': (800.0, 1500.0),
        'magnesium_ppm': (100.0, 300.0),
        'sulfur_ppm': (15.0, 50.0),
        'iron_ppm': (50.0, 250.0),
        'manganese_ppm': (15.0, 100.0),
        'zinc_ppm': (2.0, 15.0),
        'copper_ppm': (1.0, 8.0),
        'boron_ppm': (0.5, 2.5),
        'base_saturation_ca': (60.0, 75.0),
        'base_saturation_mg': (10.0, 20.0),
        'base_saturation_k': (3.0, 7.0),
        'base_saturation_na': (0.0, 3.0),
        'sand_pct': (40.0, 80.0),
        'ec': (0.0, 2.0),
    },
    'bermudagrass_tees': {
        'ph': (6.0, 7.0),
        'organic_matter': (1.0, 3.5),
        'cec': (8.0, 25.0),
        'phosphorus_ppm': (30.0, 60.0),
        'potassium_ppm': (100.0, 200.0),
        'calcium_ppm': (800.0, 1500.0),
        'magnesium_ppm': (100.0, 300.0),
        'sulfur_ppm': (15.0, 50.0),
        'iron_ppm': (50.0, 250.0),
        'manganese_ppm': (15.0, 100.0),
        'zinc_ppm': (2.0, 15.0),
        'copper_ppm': (1.0, 8.0),
        'boron_ppm': (0.5, 2.5),
        'base_saturation_ca': (60.0, 75.0),
        'base_saturation_mg': (10.0, 20.0),
        'base_saturation_k': (3.0, 7.0),
        'base_saturation_na': (0.0, 3.0),
        'sand_pct': (60.0, 90.0),
        'ec': (0.0, 2.0),
    },
    'kentucky_bluegrass_fairways': {
        'ph': (6.0, 7.0),
        'organic_matter': (2.0, 5.0),
        'cec': (10.0, 25.0),
        'phosphorus_ppm': (30.0, 60.0),
        'potassium_ppm': (100.0, 200.0),
        'calcium_ppm': (800.0, 1500.0),
        'magnesium_ppm': (100.0, 300.0),
        'sulfur_ppm': (15.0, 50.0),
        'iron_ppm': (50.0, 250.0),
        'manganese_ppm': (15.0, 100.0),
        'zinc_ppm': (2.0, 15.0),
        'copper_ppm': (1.0, 8.0),
        'boron_ppm': (0.5, 2.5),
        'base_saturation_ca': (60.0, 75.0),
        'base_saturation_mg': (10.0, 20.0),
        'base_saturation_k': (3.0, 7.0),
        'base_saturation_na': (0.0, 3.0),
        'sand_pct': (30.0, 70.0),
        'ec': (0.0, 2.0),
    },
    'general_turfgrass': {
        'ph': (6.0, 7.0),
        'organic_matter': (2.0, 5.0),
        'cec': (10.0, 25.0),
        'phosphorus_ppm': (25.0, 60.0),
        'potassium_ppm': (80.0, 200.0),
        'calcium_ppm': (700.0, 1500.0),
        'magnesium_ppm': (80.0, 300.0),
        'sulfur_ppm': (15.0, 50.0),
        'iron_ppm': (50.0, 250.0),
        'manganese_ppm': (10.0, 100.0),
        'zinc_ppm': (2.0, 15.0),
        'copper_ppm': (1.0, 8.0),
        'boron_ppm': (0.5, 2.5),
        'base_saturation_ca': (60.0, 75.0),
        'base_saturation_mg': (10.0, 20.0),
        'base_saturation_k': (3.0, 7.0),
        'base_saturation_na': (0.0, 3.0),
        'sand_pct': (30.0, 80.0),
        'ec': (0.0, 2.0),
    },
}

# Water quality optimal ranges
WATER_QUALITY_RANGES = {
    'ph': (6.0, 8.0),
    'ec': (0.0, 1.5),
    'tds_ppm': (0.0, 960.0),
    'sodium_ppm': (0.0, 70.0),
    'chloride_ppm': (0.0, 100.0),
    'bicarbonate_ppm': (0.0, 120.0),
    'calcium_ppm': (40.0, 120.0),
    'magnesium_ppm': (6.0, 25.0),
    'sar': (0.0, 6.0),
    'hardness_ppm': (50.0, 200.0),
    'iron_ppm': (0.0, 0.3),
}


# ---------------------------------------------------------------------------
# Database Initialization
# ---------------------------------------------------------------------------

def init_soil_tables():
    """Initialize soil testing database tables.
    Works with both SQLite and PostgreSQL."""
    with get_db() as conn:
        cursor = conn.cursor()

        # Soil tests table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS soil_tests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                test_date TEXT NOT NULL,
                lab_name TEXT,
                lab_report_id TEXT,
                area TEXT NOT NULL,
                zone_name TEXT,
                sample_depth REAL,
                ph REAL,
                buffer_ph REAL,
                organic_matter REAL,
                cec REAL,
                base_saturation_ca REAL,
                base_saturation_mg REAL,
                base_saturation_k REAL,
                base_saturation_na REAL,
                nitrogen_ppm REAL,
                phosphorus_ppm REAL,
                potassium_ppm REAL,
                calcium_ppm REAL,
                magnesium_ppm REAL,
                sulfur_ppm REAL,
                iron_ppm REAL,
                manganese_ppm REAL,
                zinc_ppm REAL,
                copper_ppm REAL,
                boron_ppm REAL,
                sodium_ppm REAL,
                chloride_ppm REAL,
                sand_pct REAL,
                silt_pct REAL,
                clay_pct REAL,
                ec REAL,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Soil amendments table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS soil_amendments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                soil_test_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                amendment_type TEXT NOT NULL,
                product_name TEXT,
                rate_per_1000sqft REAL,
                rate_unit TEXT,
                total_needed REAL,
                applied INTEGER DEFAULT 0,
                applied_date TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (soil_test_id) REFERENCES soil_tests (id)
            )
        ''')

        # Water tests table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS water_tests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                test_date TEXT NOT NULL,
                source TEXT,
                ph REAL,
                ec REAL,
                tds_ppm REAL,
                sodium_ppm REAL,
                chloride_ppm REAL,
                bicarbonate_ppm REAL,
                calcium_ppm REAL,
                magnesium_ppm REAL,
                sar REAL,
                hardness_ppm REAL,
                iron_ppm REAL,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        logger.info("Soil testing tables initialized successfully")


# ---------------------------------------------------------------------------
# Soil Test CRUD
# ---------------------------------------------------------------------------

def add_soil_test(user_id, data):
    """Add a new soil test record.

    Args:
        user_id: User ID (integer).
        data: Dict with soil test fields. Required: test_date, area, ph.

    Returns:
        The new soil test ID, or None on error.
    """
    required = ['test_date', 'area', 'ph']
    for field in required:
        if field not in data or data[field] is None:
            logger.error(f"Missing required field for soil test: {field}")
            return None

    area = data['area'].lower()
    if area not in VALID_AREAS:
        logger.error(f"Invalid area '{area}'. Must be one of {VALID_AREAS}")
        return None

    try:
        with get_db() as conn:
            cursor = conn.execute('''
                INSERT INTO soil_tests (
                    user_id, test_date, lab_name, lab_report_id, area,
                    zone_name, sample_depth, ph, buffer_ph, organic_matter,
                    cec, base_saturation_ca, base_saturation_mg,
                    base_saturation_k, base_saturation_na,
                    nitrogen_ppm, phosphorus_ppm, potassium_ppm,
                    calcium_ppm, magnesium_ppm, sulfur_ppm,
                    iron_ppm, manganese_ppm, zinc_ppm, copper_ppm,
                    boron_ppm, sodium_ppm, chloride_ppm,
                    sand_pct, silt_pct, clay_pct, ec, notes
                ) VALUES (
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?,
                    ?, ?,
                    ?, ?, ?,
                    ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?,
                    ?, ?, ?, ?, ?
                )
            ''', (
                user_id,
                data['test_date'],
                data.get('lab_name'),
                data.get('lab_report_id'),
                area,
                data.get('zone_name'),
                data.get('sample_depth'),
                data['ph'],
                data.get('buffer_ph'),
                data.get('organic_matter'),
                data.get('cec'),
                data.get('base_saturation_ca'),
                data.get('base_saturation_mg'),
                data.get('base_saturation_k'),
                data.get('base_saturation_na'),
                data.get('nitrogen_ppm'),
                data.get('phosphorus_ppm'),
                data.get('potassium_ppm'),
                data.get('calcium_ppm'),
                data.get('magnesium_ppm'),
                data.get('sulfur_ppm'),
                data.get('iron_ppm'),
                data.get('manganese_ppm'),
                data.get('zinc_ppm'),
                data.get('copper_ppm'),
                data.get('boron_ppm'),
                data.get('sodium_ppm'),
                data.get('chloride_ppm'),
                data.get('sand_pct'),
                data.get('silt_pct'),
                data.get('clay_pct'),
                data.get('ec'),
                data.get('notes'),
            ))
            test_id = cursor.lastrowid
            logger.info(f"Added soil test {test_id} for user {user_id}, area={area}")
            return test_id
    except Exception as e:
        logger.error(f"Error adding soil test: {e}")
        return None

def update_soil_test(test_id, user_id, data):
    """Update an existing soil test record.

    Args:
        test_id: Soil test ID.
        user_id: User ID (for ownership check).
        data: Dict with fields to update.

    Returns:
        True on success, False on error.
    """
    allowed_fields = [
        'test_date', 'lab_name', 'lab_report_id', 'area', 'zone_name',
        'sample_depth', 'ph', 'buffer_ph', 'organic_matter', 'cec',
        'base_saturation_ca', 'base_saturation_mg',
        'base_saturation_k', 'base_saturation_na',
        'nitrogen_ppm', 'phosphorus_ppm', 'potassium_ppm',
        'calcium_ppm', 'magnesium_ppm', 'sulfur_ppm',
        'iron_ppm', 'manganese_ppm', 'zinc_ppm', 'copper_ppm',
        'boron_ppm', 'sodium_ppm', 'chloride_ppm',
        'sand_pct', 'silt_pct', 'clay_pct', 'ec', 'notes',
    ]

    updates = []
    params = []
    for field in allowed_fields:
        if field in data:
            updates.append(f"{field} = ?")
            params.append(data[field])

    if not updates:
        logger.warning("No valid fields to update for soil test")
        return False

    updates.append("updated_at = CURRENT_TIMESTAMP")
    params.extend([test_id, user_id])

    try:
        with get_db() as conn:
            cursor = conn.execute(
                f"UPDATE soil_tests SET {', '.join(updates)} "
                f"WHERE id = ? AND user_id = ?",
                params
            )
            if cursor.rowcount == 0:
                logger.warning(
                    f"Soil test {test_id} not found or not owned "
                    f"by user {user_id}"
                )
                return False
            logger.info(f"Updated soil test {test_id} for user {user_id}")
            return True
    except Exception as e:
        logger.error(f"Error updating soil test {test_id}: {e}")
        return False


def delete_soil_test(test_id, user_id):
    """Delete a soil test and its associated amendments.

    Args:
        test_id: Soil test ID.
        user_id: User ID (for ownership check).

    Returns:
        True on success, False on error.
    """
    try:
        with get_db() as conn:
            # Delete associated amendments first
            conn.execute(
                "DELETE FROM soil_amendments "
                "WHERE soil_test_id = ? AND user_id = ?",
                (test_id, user_id)
            )
            cursor = conn.execute(
                "DELETE FROM soil_tests WHERE id = ? AND user_id = ?",
                (test_id, user_id)
            )
            if cursor.rowcount == 0:
                logger.warning(
                    f"Soil test {test_id} not found or not owned "
                    f"by user {user_id}"
                )
                return False
            logger.info(
                f"Deleted soil test {test_id} and amendments "
                f"for user {user_id}"
            )
            return True
    except Exception as e:
        logger.error(f"Error deleting soil test {test_id}: {e}")
        return False

def get_soil_tests(user_id, area=None, start_date=None, end_date=None):
    """Get soil tests for a user with optional filters.

    Args:
        user_id: User ID.
        area: Optional area filter (greens/fairways/tees/rough).
        start_date: Optional start date string (YYYY-MM-DD).
        end_date: Optional end date string (YYYY-MM-DD).

    Returns:
        List of soil test dicts, or empty list on error.
    """
    try:
        with get_db() as conn:
            sql = "SELECT * FROM soil_tests WHERE user_id = ?"
            params = [user_id]

            if area:
                sql += " AND area = ?"
                params.append(area.lower())
            if start_date:
                sql += " AND test_date >= ?"
                params.append(start_date)
            if end_date:
                sql += " AND test_date <= ?"
                params.append(end_date)

            sql += " ORDER BY test_date DESC"

            cursor = conn.execute(sql, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error fetching soil tests for user {user_id}: {e}")
        return []


def get_soil_test_by_id(test_id, user_id):
    """Get a single soil test by ID.

    Args:
        test_id: Soil test ID.
        user_id: User ID (for ownership check).

    Returns:
        Soil test dict, or None if not found.
    """
    try:
        with get_db() as conn:
            cursor = conn.execute(
                "SELECT * FROM soil_tests WHERE id = ? AND user_id = ?",
                (test_id, user_id)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
    except Exception as e:
        logger.error(f"Error fetching soil test {test_id}: {e}")
        return None


def get_latest_soil_test(user_id, area):
    """Get the most recent soil test for a specific area.

    Args:
        user_id: User ID.
        area: Area name (greens/fairways/tees/rough).

    Returns:
        Soil test dict, or None if not found.
    """
    area = area.lower()
    if area not in VALID_AREAS:
        logger.error(f"Invalid area '{area}'. Must be one of {VALID_AREAS}")
        return None

    try:
        with get_db() as conn:
            cursor = conn.execute(
                "SELECT * FROM soil_tests "
                "WHERE user_id = ? AND area = ? "
                "ORDER BY test_date DESC LIMIT 1",
                (user_id, area)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
    except Exception as e:
        logger.error(
            f"Error fetching latest soil test for user {user_id}, "
            f"area={area}: {e}"
        )
        return None


# ---------------------------------------------------------------------------
# Amendment Calculations
# ---------------------------------------------------------------------------

def calculate_lime_need(current_ph, target_ph, buffer_ph, cec,
                        soil_type='loam'):
    """Calculate lime requirement using SMP buffer pH method.

    Based on the SMP buffer pH method:
    - If buffer pH >= 6.6: no lime needed
    - Lime (lbs CaCO3/1000 sqft) = (7.0 - buffer_pH) * factor

    The factor varies by target pH and is adjusted by soil type and CEC.

    Args:
        current_ph: Current soil pH.
        target_ph: Target soil pH (typically 6.0-7.0).
        buffer_ph: SMP buffer pH from lab.
        cec: Cation Exchange Capacity (meq/100g).
        soil_type: Soil texture class (sand, loam, clay, etc.).

    Returns:
        Lime requirement in lbs CaCO3 per 1000 sqft, or 0.0 if none needed.
    """
    if current_ph >= target_ph:
        return 0.0

    if buffer_ph is None:
        # Fallback estimation without buffer pH: use CEC-based method
        if cec is None:
            cec = 12.0  # Default mid-range CEC
        soil_factor = SOIL_TYPE_FACTORS.get(soil_type, 1.0)
        lime_lbs = (target_ph - current_ph) * cec * 3.3 * soil_factor
        return round(max(0.0, lime_lbs), 1)

    # SMP buffer pH method
    if buffer_ph >= 6.6:
        return 0.0

    # Select the closest target pH factor
    target_keys = sorted(SMP_LIME_FACTORS.keys())
    closest_target = min(target_keys, key=lambda x: abs(x - target_ph))
    factor = SMP_LIME_FACTORS[closest_target]

    # Base lime requirement
    lime_lbs = (7.0 - buffer_ph) * factor

    # Adjust by soil type
    soil_factor = SOIL_TYPE_FACTORS.get(soil_type, 1.0)
    lime_lbs *= soil_factor

    # Adjust by CEC if provided (heavier soils need more lime)
    if cec and cec > 0:
        cec_factor = cec / 15.0  # Normalize to a CEC of 15
        lime_lbs *= max(0.5, min(cec_factor, 2.0))  # Clamp 0.5x-2x

    return round(max(0.0, lime_lbs), 1)

def calculate_sulfur_need(current_ph, target_ph, soil_type='loam',
                          om_pct=None):
    """Calculate elemental sulfur requirement to lower soil pH.

    Based on general turfgrass agronomic recommendations:
    - Sandy soils: ~5 lbs S/1000 sqft per 0.5 pH unit reduction
    - Loam soils: ~8 lbs S/1000 sqft per 0.5 pH unit reduction
    - Clay soils: ~12 lbs S/1000 sqft per 0.5 pH unit reduction

    Higher organic matter increases buffering and raises the requirement.

    Args:
        current_ph: Current soil pH.
        target_ph: Target soil pH (lower than current).
        soil_type: Soil texture class.
        om_pct: Organic matter percentage (optional).

    Returns:
        Sulfur requirement in lbs elemental S per 1000 sqft, or 0.0.
    """
    if current_ph <= target_ph:
        return 0.0

    ph_change = current_ph - target_ph

    # Base rate per 0.5 pH unit reduction by soil type
    base_rates = {
        'sand': 5.0,
        'sandy_loam': 6.5,
        'loam': 8.0,
        'silt_loam': 9.0,
        'clay_loam': 10.5,
        'clay': 12.0,
    }

    base_rate = base_rates.get(soil_type, 8.0)
    sulfur_lbs = (ph_change / 0.5) * base_rate

    # Adjust for organic matter (higher OM = more buffering)
    if om_pct and om_pct > 0:
        if om_pct > 5.0:
            sulfur_lbs *= 1.3
        elif om_pct > 3.0:
            sulfur_lbs *= 1.1

    return round(max(0.0, sulfur_lbs), 1)


def calculate_gypsum_need(sodium_ppm, cec, target_na_pct=3.0):
    """Calculate gypsum requirement for sodium remediation.

    Gypsum (CaSO4) displaces sodium from the exchange complex.
    Goal: reduce Na base saturation to target level (typically 3%).

    Formula:
        Na meq/100g = sodium_ppm / 230
        Current Na% = (Na meq / CEC) * 100
        Excess Na meq = CEC * (current_na_pct - target_na_pct) / 100
        Gypsum lbs/1000sqft = excess_na_meq * 8.86

    Args:
        sodium_ppm: Current sodium in ppm (Mehlich-3 or equivalent).
        cec: Cation Exchange Capacity (meq/100g).
        target_na_pct: Target sodium base saturation % (default 3.0).

    Returns:
        Gypsum requirement in lbs per 1000 sqft, or 0.0 if none needed.
    """
    if not sodium_ppm or not cec or cec <= 0:
        return 0.0

    # Convert sodium ppm to meq/100g (Na atomic weight ~23, valence 1)
    na_meq = sodium_ppm / 230.0
    current_na_pct = (na_meq / cec) * 100.0

    if current_na_pct <= target_na_pct:
        return 0.0

    # Excess sodium in meq/100g
    excess_na_meq = cec * (current_na_pct - target_na_pct) / 100.0

    # Gypsum needed: ~386 lbs per acre-6inches per meq Na/100g
    # Converted to per 1000 sqft: 386 / 43.56 = ~8.86
    gypsum_lbs = excess_na_meq * 8.86

    return round(max(0.0, gypsum_lbs), 1)

def generate_amendment_recommendations(test_id, user_id, target_ph=None):
    """Generate a full set of amendment recommendations based on a soil test.

    Analyzes the soil test results and generates recommendations for:
    - Lime (if pH too low)
    - Sulfur (if pH too high)
    - Gypsum (if sodium is elevated)
    - Phosphorus fertilizer (if P is deficient)
    - Potassium fertilizer (if K is deficient)

    Saves recommendations to the soil_amendments table.

    Args:
        test_id: Soil test ID.
        user_id: User ID (for ownership check).
        target_ph: Optional target pH override. If None, uses area-based optimal.

    Returns:
        List of amendment recommendation dicts, or empty list on error.
    """
    test = get_soil_test_by_id(test_id, user_id)
    if not test:
        logger.error(f"Soil test {test_id} not found for user {user_id}")
        return []

    area = test.get('area', 'fairways')
    ranges = get_optimal_ranges(None, area)
    recommendations = []

    # Determine target pH
    if target_ph is None:
        ph_range = ranges.get('ph', (6.0, 7.0))
        target_ph = (ph_range[0] + ph_range[1]) / 2.0

    current_ph = test.get('ph')
    buffer_ph = test.get('buffer_ph')
    cec = test.get('cec')
    om_pct = test.get('organic_matter')

    # --- pH Amendments ---
    if current_ph is not None and current_ph < target_ph - 0.2:
        # Need lime
        lime_lbs = calculate_lime_need(
            current_ph, target_ph, buffer_ph, cec, soil_type='loam'
        )
        if lime_lbs > 0:
            recommendations.append({
                'amendment_type': 'lime',
                'product_name': 'Calcitic Limestone (CaCO3)',
                'rate_per_1000sqft': lime_lbs,
                'rate_unit': 'lbs/1000sqft',
                'total_needed': None,
                'notes': (
                    f"Raise pH from {current_ph} to {target_ph:.1f}. "
                    f"Buffer pH: {buffer_ph or 'N/A'}. "
                    f"Apply max 50 lbs/1000sqft per application; "
                    f"split if higher."
                ),
            })

    elif current_ph is not None and current_ph > target_ph + 0.3:
        # Need sulfur
        sulfur_lbs = calculate_sulfur_need(
            current_ph, target_ph, soil_type='loam', om_pct=om_pct
        )
        if sulfur_lbs > 0:
            recommendations.append({
                'amendment_type': 'sulfur',
                'product_name': 'Elemental Sulfur (90%)',
                'rate_per_1000sqft': sulfur_lbs,
                'rate_unit': 'lbs/1000sqft',
                'total_needed': None,
                'notes': (
                    f"Lower pH from {current_ph} to {target_ph:.1f}. "
                    f"Apply max 5 lbs/1000sqft per application on "
                    f"established turf. Space applications 6-8 weeks apart."
                ),
            })

    # --- Sodium / Gypsum ---
    sodium_ppm = test.get('sodium_ppm')
    na_pct = test.get('base_saturation_na')
    if (na_pct and na_pct > 3.0) or (
        sodium_ppm and cec and cec > 0
        and (sodium_ppm / 230.0 / cec * 100) > 3.0
    ):
        gypsum_lbs = calculate_gypsum_need(
            sodium_ppm, cec, target_na_pct=3.0
        )
        if gypsum_lbs > 0:
            recommendations.append({
                'amendment_type': 'gypsum',
                'product_name': 'Gypsum (CaSO4 dihydrate)',
                'rate_per_1000sqft': gypsum_lbs,
                'rate_unit': 'lbs/1000sqft',
                'total_needed': None,
                'notes': (
                    f"Reduce sodium from {sodium_ppm or 'N/A'} ppm "
                    f"(Na sat: {na_pct or 'N/A'}%). "
                    f"Apply max 40 lbs/1000sqft per application; "
                    f"irrigate after."
                ),
            })

    # --- Phosphorus ---
    p_ppm = test.get('phosphorus_ppm')
    p_range = ranges.get('phosphorus_ppm', (25.0, 60.0))
    if p_ppm is not None and p_ppm < p_range[0]:
        deficiency = p_range[0] - p_ppm
        # Rough rule: 1 lb P2O5/1000sqft raises Mehlich-3 P by ~2-4 ppm
        p2o5_needed = deficiency / 3.0
        recommendations.append({
            'amendment_type': 'fertilizer',
            'product_name': 'Superphosphate (0-46-0) or equivalent P source',
            'rate_per_1000sqft': round(p2o5_needed, 1),
            'rate_unit': 'lbs P2O5/1000sqft',
            'total_needed': None,
            'notes': (
                f"Phosphorus at {p_ppm} ppm, target range "
                f"{p_range[0]}-{p_range[1]} ppm. "
                f"Consider split applications."
            ),
        })

    # --- Potassium ---
    k_ppm = test.get('potassium_ppm')
    k_range = ranges.get('potassium_ppm', (80.0, 200.0))
    if k_ppm is not None and k_ppm < k_range[0]:
        deficiency = k_range[0] - k_ppm
        # Rough rule: 1 lb K2O/1000sqft raises Mehlich-3 K by ~3-5 ppm
        k2o_needed = deficiency / 4.0
        recommendations.append({
            'amendment_type': 'fertilizer',
            'product_name': (
                'Sulfate of Potash (0-0-50) or equivalent K source'
            ),
            'rate_per_1000sqft': round(k2o_needed, 1),
            'rate_unit': 'lbs K2O/1000sqft',
            'total_needed': None,
            'notes': (
                f"Potassium at {k_ppm} ppm, target range "
                f"{k_range[0]}-{k_range[1]} ppm. "
                f"Split into multiple applications through the season."
            ),
        })

    # --- Calcium (low base saturation) ---
    ca_pct = test.get('base_saturation_ca')
    ca_range = ranges.get('base_saturation_ca', (60.0, 75.0))
    if (ca_pct is not None and ca_pct < ca_range[0]
            and current_ph and current_ph >= target_ph - 0.2):
        # Calcium is low but pH is fine -- use gypsum, not lime
        ca_deficit_pct = ca_range[0] - ca_pct
        gypsum_rate = round(ca_deficit_pct * 2.0, 1)
        recommendations.append({
            'amendment_type': 'gypsum',
            'product_name': (
                'Gypsum (CaSO4) for calcium without pH change'
            ),
            'rate_per_1000sqft': gypsum_rate,
            'rate_unit': 'lbs/1000sqft',
            'total_needed': None,
            'notes': (
                f"Calcium base saturation at {ca_pct}%, target "
                f"{ca_range[0]}-{ca_range[1]}%. "
                f"pH is acceptable so using gypsum instead of lime."
            ),
        })

    # --- Magnesium ---
    mg_ppm = test.get('magnesium_ppm')
    mg_range = ranges.get('magnesium_ppm', (80.0, 300.0))
    if mg_ppm is not None and mg_ppm < mg_range[0]:
        recommendations.append({
            'amendment_type': 'fertilizer',
            'product_name': 'Epsom Salt (MgSO4) or Dolomitic Lime',
            'rate_per_1000sqft': round(
                (mg_range[0] - mg_ppm) / 20.0, 1
            ),
            'rate_unit': 'lbs/1000sqft',
            'total_needed': None,
            'notes': (
                f"Magnesium at {mg_ppm} ppm, target "
                f"{mg_range[0]}-{mg_range[1]} ppm. "
                f"Use dolomitic lime if pH also needs raising; "
                f"otherwise use Epsom salt."
            ),
        })

    # Save recommendations to database
    try:
        with get_db() as conn:
            # Remove previous recommendations for this test
            conn.execute(
                "DELETE FROM soil_amendments "
                "WHERE soil_test_id = ? AND user_id = ?",
                (test_id, user_id)
            )
            for rec in recommendations:
                conn.execute('''
                    INSERT INTO soil_amendments (
                        soil_test_id, user_id, amendment_type,
                        product_name, rate_per_1000sqft, rate_unit,
                        total_needed, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    test_id, user_id,
                    rec['amendment_type'],
                    rec['product_name'],
                    rec['rate_per_1000sqft'],
                    rec['rate_unit'],
                    rec.get('total_needed'),
                    rec.get('notes'),
                ))
        logger.info(
            f"Generated {len(recommendations)} amendment recommendations "
            f"for test {test_id}, user {user_id}"
        )
    except Exception as e:
        logger.error(f"Error saving amendment recommendations: {e}")

    return recommendations


def get_amendments(test_id, user_id):
    """Get saved amendment recommendations for a soil test.

    Args:
        test_id: Soil test ID.
        user_id: User ID (for ownership check).

    Returns:
        List of amendment dicts, or empty list on error.
    """
    try:
        with get_db() as conn:
            cursor = conn.execute(
                "SELECT * FROM soil_amendments "
                "WHERE soil_test_id = ? AND user_id = ? ORDER BY id",
                (test_id, user_id)
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(
            f"Error fetching amendments for test {test_id}: {e}"
        )
        return []


# ---------------------------------------------------------------------------
# Trend Analysis
# ---------------------------------------------------------------------------

def get_soil_trend(user_id, area, parameter, years=5):
    """Get historical trend for a soil parameter in a specific area.

    Args:
        user_id: User ID.
        area: Area name (greens/fairways/tees/rough).
        parameter: Column name to trend (e.g. 'ph', 'phosphorus_ppm').
        years: Number of years of history to include (default 5).

    Returns:
        List of dicts with 'test_date', 'value', and 'id' keys,
        ordered by date ascending. Empty list on error or no data.
    """
    area = area.lower()
    if area not in VALID_AREAS:
        logger.error(f"Invalid area '{area}' for trend query")
        return []

    # Whitelist allowed column names to prevent SQL injection
    allowed_params = [
        'ph', 'buffer_ph', 'organic_matter', 'cec',
        'base_saturation_ca', 'base_saturation_mg',
        'base_saturation_k', 'base_saturation_na',
        'nitrogen_ppm', 'phosphorus_ppm', 'potassium_ppm',
        'calcium_ppm', 'magnesium_ppm', 'sulfur_ppm',
        'iron_ppm', 'manganese_ppm', 'zinc_ppm', 'copper_ppm',
        'boron_ppm', 'sodium_ppm', 'chloride_ppm',
        'sand_pct', 'silt_pct', 'clay_pct', 'ec',
    ]

    if parameter not in allowed_params:
        logger.error(f"Invalid parameter '{parameter}' for trend query")
        return []

    try:
        with get_db() as conn:
            cutoff_days = years * 365
            cursor = conn.execute(
                f"SELECT id, test_date, {parameter} as value "
                f"FROM soil_tests "
                f"WHERE user_id = ? AND area = ? "
                f"AND {parameter} IS NOT NULL "
                f"AND test_date >= DATE('now', '-{cutoff_days} days') "
                f"ORDER BY test_date ASC",
                (user_id, area)
            )
            rows = cursor.fetchall()
            return [
                {
                    'id': row['id'],
                    'test_date': row['test_date'],
                    'value': row['value'],
                }
                for row in rows
            ]
    except Exception as e:
        logger.error(
            f"Error fetching soil trend for user {user_id}, "
            f"{area}/{parameter}: {e}"
        )
        return []

def get_nutrient_comparison(user_id):
    """Get the latest soil test values vs. optimal ranges for each area.

    Returns a dict keyed by area, each containing the latest test values
    and the optimal range for each parameter.

    Args:
        user_id: User ID.

    Returns:
        Dict: {area: {'test': {...}, 'comparisons': {param: {...}}}}
    """
    result = {}
    compare_params = [
        'ph', 'organic_matter', 'cec',
        'phosphorus_ppm', 'potassium_ppm', 'calcium_ppm',
        'magnesium_ppm', 'sulfur_ppm', 'iron_ppm',
        'manganese_ppm', 'zinc_ppm',
        'base_saturation_ca', 'base_saturation_mg',
        'base_saturation_k', 'base_saturation_na',
        'ec',
    ]

    for area in VALID_AREAS:
        test = get_latest_soil_test(user_id, area)
        if not test:
            continue

        ranges = get_optimal_ranges(None, area)
        comparisons = {}

        for param in compare_params:
            value = test.get(param)
            if value is None:
                continue
            rng = ranges.get(param)
            if not rng:
                comparisons[param] = {
                    'value': value,
                    'low': None,
                    'high': None,
                    'status': 'unknown',
                }
                continue

            low, high = rng
            if value < low:
                status = 'low'
            elif value > high:
                status = 'high'
            else:
                status = 'optimal'

            comparisons[param] = {
                'value': value,
                'low': low,
                'high': high,
                'status': status,
            }

        result[area] = {
            'test': test,
            'comparisons': comparisons,
        }

    return result


def get_optimal_ranges(grass_type, area):
    """Get optimal nutrient ranges for a grass type and area.

    Tries to find a specific match (e.g., 'bentgrass_greens'), then
    falls back to 'general_turfgrass'.

    Args:
        grass_type: Grass type string (e.g., 'bentgrass', 'bermudagrass')
                    or None for general defaults.
        area: Area name (greens/fairways/tees/rough).

    Returns:
        Dict of parameter: (low, high) tuples.
    """
    area = area.lower() if area else 'fairways'

    # Try specific grass+area combo first
    if grass_type:
        key = f"{grass_type.lower()}_{area}"
        if key in OPTIMAL_RANGES:
            return OPTIMAL_RANGES[key]

    # Try just the area with common grass types
    for prefix in ['bentgrass', 'bermudagrass', 'kentucky_bluegrass']:
        key = f"{prefix}_{area}"
        if key in OPTIMAL_RANGES:
            return OPTIMAL_RANGES[key]

    # Fallback to general turfgrass
    return OPTIMAL_RANGES.get('general_turfgrass', {})


# ---------------------------------------------------------------------------
# Water Testing
# ---------------------------------------------------------------------------

def add_water_test(user_id, data):
    """Add a new water quality test record.

    Args:
        user_id: User ID.
        data: Dict with water test fields. Required: test_date.

    Returns:
        The new water test ID, or None on error.
    """
    if 'test_date' not in data or data['test_date'] is None:
        logger.error("Missing required field 'test_date' for water test")
        return None

    source = (
        data.get('source', '').lower() if data.get('source') else None
    )
    if source and source not in VALID_WATER_SOURCES:
        logger.warning(
            f"Unrecognized water source '{source}', saving anyway"
        )

    # Auto-calculate SAR if sodium, calcium, magnesium are provided
    sar = data.get('sar')
    if (sar is None and data.get('sodium_ppm')
            and data.get('calcium_ppm')
            and data.get('magnesium_ppm')):
        sar = calculate_sar(
            data['sodium_ppm'],
            data['calcium_ppm'],
            data['magnesium_ppm'],
        )

    try:
        with get_db() as conn:
            cursor = conn.execute('''
                INSERT INTO water_tests (
                    user_id, test_date, source, ph, ec, tds_ppm,
                    sodium_ppm, chloride_ppm, bicarbonate_ppm,
                    calcium_ppm, magnesium_ppm,
                    sar, hardness_ppm, iron_ppm, notes
                ) VALUES (
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?,
                    ?, ?,
                    ?, ?, ?, ?
                )
            ''', (
                user_id,
                data['test_date'],
                source,
                data.get('ph'),
                data.get('ec'),
                data.get('tds_ppm'),
                data.get('sodium_ppm'),
                data.get('chloride_ppm'),
                data.get('bicarbonate_ppm'),
                data.get('calcium_ppm'),
                data.get('magnesium_ppm'),
                sar,
                data.get('hardness_ppm'),
                data.get('iron_ppm'),
                data.get('notes'),
            ))
            test_id = cursor.lastrowid
            logger.info(f"Added water test {test_id} for user {user_id}")
            return test_id
    except Exception as e:
        logger.error(f"Error adding water test: {e}")
        return None


def get_water_tests(user_id):
    """Get all water tests for a user, ordered by date descending.

    Args:
        user_id: User ID.

    Returns:
        List of water test dicts, or empty list on error.
    """
    try:
        with get_db() as conn:
            cursor = conn.execute(
                "SELECT * FROM water_tests WHERE user_id = ? "
                "ORDER BY test_date DESC",
                (user_id,)
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(
            f"Error fetching water tests for user {user_id}: {e}"
        )
        return []

def get_water_test_by_id(test_id, user_id):
    """Get a single water test by ID."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM water_tests WHERE id = ? AND user_id = ?",
            (test_id, user_id)
        ).fetchone()
    if row is None:
        raise ValueError(f"Water test {test_id} not found")
    return dict(row)


def calculate_sar(sodium, calcium, magnesium):
    """Calculate the Sodium Adsorption Ratio (SAR).

    SAR = Na / sqrt((Ca + Mg) / 2)
    where all concentrations are in meq/L.

    Converts from ppm to meq/L internally:
    - Na: ppm / 23.0
    - Ca: ppm / 20.04
    - Mg: ppm / 12.15

    Args:
        sodium: Sodium in ppm.
        calcium: Calcium in ppm.
        magnesium: Magnesium in ppm.

    Returns:
        SAR value (float), or None if inputs are invalid.
    """
    if not sodium or not calcium or not magnesium:
        return None

    try:
        na_meq = sodium / 23.0
        ca_meq = calcium / 20.04
        mg_meq = magnesium / 12.15

        denominator = (ca_meq + mg_meq) / 2.0
        if denominator <= 0:
            return None

        sar = na_meq / math.sqrt(denominator)
        return round(sar, 2)
    except (ValueError, ZeroDivisionError):
        return None

def get_water_quality_assessment(test_id, user_id):
    """Generate a qualitative assessment of water quality from a test.

    Evaluates each parameter against standard irrigation water quality
    guidelines and returns a summary with ratings.

    Args:
        test_id: Water test ID.
        user_id: User ID (for ownership check).

    Returns:
        Dict with 'overall_rating', 'parameters', 'concerns',
        'recommendations', or None if test not found.
    """
    try:
        with get_db() as conn:
            cursor = conn.execute(
                "SELECT * FROM water_tests "
                "WHERE id = ? AND user_id = ?",
                (test_id, user_id)
            )
            row = cursor.fetchone()
            if not row:
                logger.warning(
                    f"Water test {test_id} not found for user {user_id}"
                )
                return None
            test = dict(row)
    except Exception as e:
        logger.error(f"Error fetching water test {test_id}: {e}")
        return None

    concerns = []
    recommendations = []
    parameter_ratings = {}
    severity_scores = []

    # Assess each parameter
    assessment_params = [
        ('ph', 'pH'),
        ('ec', 'Electrical Conductivity (dS/m)'),
        ('tds_ppm', 'Total Dissolved Solids (ppm)'),
        ('sodium_ppm', 'Sodium (ppm)'),
        ('chloride_ppm', 'Chloride (ppm)'),
        ('bicarbonate_ppm', 'Bicarbonate (ppm)'),
        ('calcium_ppm', 'Calcium (ppm)'),
        ('magnesium_ppm', 'Magnesium (ppm)'),
        ('sar', 'Sodium Adsorption Ratio'),
        ('hardness_ppm', 'Hardness (ppm)'),
        ('iron_ppm', 'Iron (ppm)'),
    ]

    for param_key, param_label in assessment_params:
        value = test.get(param_key)
        if value is None:
            continue

        rng = WATER_QUALITY_RANGES.get(param_key)
        if not rng:
            continue

        low, high = rng
        rating = 'acceptable'
        severity = 0

        # pH is special: both too high and too low are concerns
        if param_key == 'ph':
            if value < low:
                rating = 'low'
                severity = 1 if value >= low - 0.5 else 2
                concerns.append(
                    f"Low {param_label}: {value} "
                    f"(target {low}-{high})"
                )
                recommendations.append(
                    "Consider acid injection or blending water "
                    "sources to raise pH"
                )
            elif value > high:
                rating = 'high'
                severity = 1 if value <= high + 0.5 else 2
                concerns.append(
                    f"High {param_label}: {value} "
                    f"(target {low}-{high})"
                )
                recommendations.append(
                    "Acidify irrigation water with sulfuric "
                    "or phosphoric acid"
                )
        elif param_key in (
            'calcium_ppm', 'magnesium_ppm', 'hardness_ppm'
        ):
            # These have meaningful low values
            if value < low:
                rating = 'low'
                severity = 1
                concerns.append(
                    f"Low {param_label}: {value} "
                    f"(target {low}-{high})"
                )
            elif value > high:
                rating = 'high'
                severity = 1 if value <= high * 1.5 else 2
                concerns.append(
                    f"High {param_label}: {value} "
                    f"(target {low}-{high})"
                )
        else:
            # Most parameters: only high is a concern
            if value > high:
                rating = 'high'
                severity = 1 if value <= high * 1.5 else 2
                concerns.append(
                    f"Elevated {param_label}: {value} "
                    f"(max recommended: {high})"
                )

        severity_scores.append(severity)
        parameter_ratings[param_key] = {
            'value': value,
            'low': low,
            'high': high,
            'rating': rating,
            'severity': severity,
        }

    # SAR-specific recommendations
    sar = test.get('sar')
    if sar is not None:
        if sar > 9.0:
            recommendations.append(
                "SAR is very high. Severe sodium risk -- apply gypsum "
                "to soil, improve drainage, and consider alternative "
                "water source."
            )
        elif sar > 6.0:
            recommendations.append(
                "SAR is moderately high. Apply gypsum to offset "
                "sodium loading and monitor soil sodium levels."
            )

    # Bicarbonate recommendations
    bicarb = test.get('bicarbonate_ppm')
    if bicarb and bicarb > 120:
        recommendations.append(
            "Elevated bicarbonate can raise soil pH and cause lime "
            "deposits. Acidify irrigation water to neutralize "
            "bicarbonate."
        )

    # Chloride recommendations
    chloride = test.get('chloride_ppm')
    if chloride and chloride > 100:
        recommendations.append(
            "High chloride may cause leaf burn on sensitive grasses. "
            "Increase leaching fraction and monitor soil chloride."
        )

    # Iron recommendations
    iron = test.get('iron_ppm')
    if iron and iron > 0.3:
        recommendations.append(
            "Elevated iron can cause staining on surfaces and "
            "irrigation equipment. Consider iron filtration or "
            "settling tanks."
        )

    # Overall rating
    if not severity_scores:
        overall = 'insufficient_data'
    elif max(severity_scores) == 0:
        overall = 'excellent'
    elif (max(severity_scores) == 1
          and sum(s > 0 for s in severity_scores) <= 2):
        overall = 'good'
    elif max(severity_scores) == 1:
        overall = 'fair'
    elif sum(s == 2 for s in severity_scores) <= 1:
        overall = 'marginal'
    else:
        overall = 'poor'

    return {
        'test_id': test_id,
        'test_date': test.get('test_date'),
        'source': test.get('source'),
        'overall_rating': overall,
        'parameters': parameter_ratings,
        'concerns': concerns,
        'recommendations': recommendations,
    }


def get_all_amendments(user_id, area=None):
    """Get all amendment recommendations across all soil tests for a user."""
    with get_db() as conn:
        query = '''SELECT a.*, s.area, s.test_date
                   FROM soil_amendments a
                   JOIN soil_tests s ON a.soil_test_id = s.id
                   WHERE a.user_id = ?'''
        params = [user_id]
        if area:
            query += ' AND s.area = ?'
            params.append(area)
        query += ' ORDER BY a.id DESC'
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def apply_amendment(amendment_id, user_id):
    """Mark an amendment recommendation as applied."""
    with get_db() as conn:
        conn.execute(
            '''UPDATE soil_amendments SET applied = 1, applied_date = date('now')
               WHERE id = ? AND user_id = ?''',
            (amendment_id, user_id)
        )
    return {'applied': True}


def delete_water_test(test_id, user_id):
    """Delete a water quality test."""
    with get_db() as conn:
        conn.execute(
            'DELETE FROM water_tests WHERE id = ? AND user_id = ?',
            (test_id, user_id)
        )
    return {'deleted': True}
