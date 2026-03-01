"""
Course Map & GIS Data Layer Module for Greenside AI.

Provides zone management (polygons), pin management (points of interest),
data layer overlays (heatmaps), and GeoJSON export for turfgrass course mapping.

Includes Shoelace formula for polygon area calculation and Haversine formula
for GPS distance calculations.

Database: Uses get_db() context manager from db.py (SQLite/PostgreSQL).
"""

import json
import math
import re
import logging
from datetime import datetime, timedelta

from db import get_db

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
VALID_ZONE_TYPES = (
    'green', 'fairway', 'tee', 'rough', 'bunker', 'pond',
    'practice', 'clubhouse', 'maintenance', 'other'
)

VALID_PIN_TYPES = (
    'issue', 'sample', 'equipment', 'irrigation', 'observation', 'custom'
)

VALID_PIN_STATUSES = ('active', 'resolved', 'archived')

VALID_LAYER_TYPES = (
    'soil_test', 'moisture', 'spray_coverage', 'disease_pressure',
    'traffic', 'elevation', 'custom'
)

# Default zone colors by type
ZONE_COLORS = {
    'green': '#2ecc71',
    'fairway': '#27ae60',
    'tee': '#3498db',
    'rough': '#8e9e3c',
    'bunker': '#f0d78c',
    'pond': '#2980b9',
    'practice': '#9b59b6',
    'clubhouse': '#7f8c8d',
    'maintenance': '#e67e22',
    'other': '#95a5a6',
}
# Earth radius in meters
EARTH_RADIUS_M = 6371000.0
# Meters to feet conversion
METERS_TO_FEET = 3.28084
# Degrees to radians
DEG_TO_RAD = math.pi / 180.0
# Approximate meters per degree of latitude
METERS_PER_DEG_LAT = 111320.0


# ---------------------------------------------------------------------------
# Geo / Math Utilities
# ---------------------------------------------------------------------------

def _haversine_ft(lat1, lng1, lat2, lng2):
    """Calculate distance in feet between two GPS coordinates using Haversine.

    Args:
        lat1, lng1: First point (decimal degrees).
        lat2, lng2: Second point (decimal degrees).

    Returns:
        Distance in feet (float).
    """
    rlat1 = lat1 * DEG_TO_RAD
    rlat2 = lat2 * DEG_TO_RAD
    dlat = (lat2 - lat1) * DEG_TO_RAD
    dlng = (lng2 - lng1) * DEG_TO_RAD
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(rlat1) * math.cos(rlat2) * math.sin(dlng / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return EARTH_RADIUS_M * c * METERS_TO_FEET


def calculate_zone_area(polygon_coords):
    """Calculate area of a polygon in square feet using the Shoelace formula.

    Converts lat/lng to approximate meter coordinates first, then applies
    the Shoelace formula, and converts the result to square feet.

    Args:
        polygon_coords: List of [lat, lng] pairs forming a closed polygon.
                        The last point does NOT need to duplicate the first.

    Returns:
        Area in square feet (float), or 0.0 if fewer than 3 points.
    """
    if not polygon_coords or len(polygon_coords) < 3:
        return 0.0

    coords = polygon_coords
    n = len(coords)

    # Use centroid as reference point for projection
    ref_lat = sum(c[0] for c in coords) / n
    ref_lng = sum(c[1] for c in coords) / n
    # At the reference latitude, 1 degree of longitude is shorter than at equator
    cos_ref = math.cos(ref_lat * DEG_TO_RAD)
    meters_per_deg_lng = METERS_PER_DEG_LAT * cos_ref

    # Project to local meter coordinates
    projected = []
    for lat, lng in coords:
        x = (lng - ref_lng) * meters_per_deg_lng
        y = (lat - ref_lat) * METERS_PER_DEG_LAT
        projected.append((x, y))

    # Shoelace formula
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += projected[i][0] * projected[j][1]
        area -= projected[j][0] * projected[i][1]
    area_sq_m = abs(area) / 2.0

    # Convert square meters to square feet
    area_sq_ft = area_sq_m * (METERS_TO_FEET ** 2)
    return round(area_sq_ft, 2)


def calculate_centroid(polygon_coords):
    """Calculate the centroid (center point) of a polygon.

    Args:
        polygon_coords: List of [lat, lng] pairs.

    Returns:
        (lat, lng) tuple, or (0.0, 0.0) if no coords.
    """
    if not polygon_coords:
        return (0.0, 0.0)

    n = len(polygon_coords)
    avg_lat = sum(c[0] for c in polygon_coords) / n
    avg_lng = sum(c[1] for c in polygon_coords) / n
    return (round(avg_lat, 8), round(avg_lng, 8))


def point_in_polygon(lat, lng, polygon_coords):
    """Check if a point is inside a polygon using ray-casting algorithm.

    Args:
        lat, lng: Point to test.
        polygon_coords: List of [lat, lng] pairs forming the polygon.

    Returns:
        True if point is inside the polygon.
    """
    if not polygon_coords or len(polygon_coords) < 3:
        return False

    n = len(polygon_coords)
    inside = False

    j = n - 1
    for i in range(n):
        yi, xi = polygon_coords[i][0], polygon_coords[i][1]
        yj, xj = polygon_coords[j][0], polygon_coords[j][1]
        if ((yi > lat) != (yj > lat)) and (lng < (xj - xi) * (lat - yi) / (yj - yi) + xi):
            inside = not inside
        j = i

    return inside


# ---------------------------------------------------------------------------
# GeoJSON Helpers
# ---------------------------------------------------------------------------

def point_to_geojson(lat, lng, properties=None):
    """Create a GeoJSON Feature with a Point geometry.

    Args:
        lat, lng: Coordinates.
        properties: Optional dict of properties.

    Returns:
        GeoJSON Feature dict.
    """
    return {
        'type': 'Feature',
        'geometry': {
            'type': 'Point',
            'coordinates': [lng, lat]  # GeoJSON uses [lng, lat]
        },
        'properties': properties or {}
    }

def polygon_to_geojson(coords, properties=None):
    """Create a GeoJSON Feature with a Polygon geometry.

    Args:
        coords: List of [lat, lng] pairs.
        properties: Optional dict of properties.

    Returns:
        GeoJSON Feature dict.
    """
    if not coords:
        return None

    # GeoJSON polygons use [lng, lat] and must be closed rings
    ring = [[c[1], c[0]] for c in coords]
    # Close the ring if not already closed
    if ring and ring[0] != ring[-1]:
        ring.append(ring[0])

    return {
        'type': 'Feature',
        'geometry': {
            'type': 'Polygon',
            'coordinates': [ring]
        },
        'properties': properties or {}
    }


def feature_collection(features):
    """Wrap a list of GeoJSON features into a FeatureCollection.
    Args:
        features: List of GeoJSON Feature dicts.

    Returns:
        GeoJSON FeatureCollection dict.
    """
    return {
        'type': 'FeatureCollection',
        'features': [f for f in features if f is not None]
    }


# ---------------------------------------------------------------------------
# Serialization Helpers
# ---------------------------------------------------------------------------

def _serialize_zone(row):
    """Convert a database row to a zone dict."""
    if row is None:
        return None
    keys = [
        'id', 'user_id', 'name', 'zone_type', 'hole_number',
        'polygon_coords', 'center_lat', 'center_lng', 'area_sqft',
        'color', 'notes', 'created_at', 'updated_at',
    ]
    result = {}
    for key in keys:
        try:
            val = row[key]
            result[key] = str(val) if isinstance(val, datetime) else val
        except (KeyError, IndexError):
            result[key] = None

    # Parse polygon_coords JSON string into list
    if isinstance(result.get('polygon_coords'), str):
        try:
            result['polygon_coords'] = json.loads(result['polygon_coords'])
        except (json.JSONDecodeError, TypeError):
            result['polygon_coords'] = []

    return result


def _serialize_pin(row):
    """Convert a database row to a pin dict."""
    if row is None:
        return None
    keys = [
        'id', 'user_id', 'zone_id', 'lat', 'lng', 'pin_type',
        'title', 'description', 'severity', 'photo_url',
        'linked_report_id', 'linked_equipment_id', 'status',
        'created_at', 'updated_at',
    ]
    result = {}
    for key in keys:
        try:
            val = row[key]
            result[key] = str(val) if isinstance(val, datetime) else val
        except (KeyError, IndexError):
            result[key] = None
    return result

def _serialize_layer(row):
    """Convert a database row to a layer dict."""
    if row is None:
        return None
    keys = [
        'id', 'user_id', 'name', 'layer_type', 'data_json',
        'visible', 'opacity', 'created_at', 'updated_at',
    ]
    result = {}
    for key in keys:
        try:
            val = row[key]
            result[key] = str(val) if isinstance(val, datetime) else val
        except (KeyError, IndexError):
            result[key] = None

    # Parse data_json
    if isinstance(result.get('data_json'), str):
        try:
            result['data_json'] = json.loads(result['data_json'])
        except (json.JSONDecodeError, TypeError):
            result['data_json'] = None

    # Normalize visible to boolean
    if result.get('visible') is not None:
        result['visible'] = bool(result['visible'])

    return result

# ---------------------------------------------------------------------------
# Table Initialization
# ---------------------------------------------------------------------------

def init_map_tables():
    """Create map_zones, map_pins, and map_layers tables."""
    with get_db() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS map_zones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                zone_type TEXT NOT NULL DEFAULT 'other',
                hole_number INTEGER,
                polygon_coords TEXT,
                center_lat REAL,
                center_lng REAL,
                area_sqft REAL,
                color TEXT,
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        ''')
        conn.execute(
            'CREATE INDEX IF NOT EXISTS idx_map_zones_user ON map_zones(user_id)'
        )
        conn.execute(
            'CREATE INDEX IF NOT EXISTS idx_map_zones_type ON map_zones(user_id, zone_type)'
        )
        conn.execute('''
            CREATE TABLE IF NOT EXISTS map_pins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                zone_id INTEGER,
                lat REAL NOT NULL,
                lng REAL NOT NULL,
                pin_type TEXT NOT NULL DEFAULT 'observation',
                title TEXT,
                description TEXT,
                severity INTEGER,
                photo_url TEXT,
                linked_report_id INTEGER,
                linked_equipment_id INTEGER,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (zone_id) REFERENCES map_zones(id) ON DELETE SET NULL
            )
        ''')
        conn.execute(
            'CREATE INDEX IF NOT EXISTS idx_map_pins_user ON map_pins(user_id)'
        )
        conn.execute(
            'CREATE INDEX IF NOT EXISTS idx_map_pins_type ON map_pins(user_id, pin_type)'
        )
        conn.execute(
            'CREATE INDEX IF NOT EXISTS idx_map_pins_zone ON map_pins(zone_id)'
        )
        conn.execute(
            'CREATE INDEX IF NOT EXISTS idx_map_pins_status ON map_pins(user_id, status)'
        )
        conn.execute('''
            CREATE TABLE IF NOT EXISTS map_layers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                layer_type TEXT NOT NULL DEFAULT 'custom',
                data_json TEXT,
                visible INTEGER NOT NULL DEFAULT 1,
                opacity REAL NOT NULL DEFAULT 0.6,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        ''')
        conn.execute(
            'CREATE INDEX IF NOT EXISTS idx_map_layers_user ON map_layers(user_id)'
        )

    logger.info("Map tables initialised successfully")


# ---------------------------------------------------------------------------
# Zone Management
# ---------------------------------------------------------------------------

def create_zone(user_id, data):
    """Create a new map zone (polygon area on the course).

    Args:
        user_id: Owner of the zone.
        data: dict with keys: name, zone_type, hole_number, polygon_coords,
              color, notes.

    Returns:
        dict of the newly created zone.

    Raises:
        ValueError: On invalid field values.
    """
    name = data.get('name', '').strip()
    if not name:
        raise ValueError("Zone name is required")

    zone_type = data.get('zone_type', 'other').lower()
    if zone_type not in VALID_ZONE_TYPES:
        raise ValueError(
            f"Invalid zone_type '{zone_type}'. Must be one of {VALID_ZONE_TYPES}"
        )

    polygon_coords = data.get('polygon_coords', [])
    if isinstance(polygon_coords, str):
        try:
            polygon_coords = json.loads(polygon_coords)
        except (json.JSONDecodeError, TypeError):
            polygon_coords = []

    # Calculate area and centroid from polygon
    area_sqft = calculate_zone_area(polygon_coords) if polygon_coords else 0.0
    center_lat, center_lng = calculate_centroid(polygon_coords) if polygon_coords else (0.0, 0.0)

    # Allow explicit override of center coordinates
    center_lat = data.get('center_lat', center_lat) or center_lat
    center_lng = data.get('center_lng', center_lng) or center_lng

    color = data.get('color') or ZONE_COLORS.get(zone_type, '#95a5a6')
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

    with get_db() as conn:
        cursor = conn.execute('''
            INSERT INTO map_zones (
                user_id, name, zone_type, hole_number, polygon_coords,
                center_lat, center_lng, area_sqft, color, notes,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_id, name, zone_type,
            data.get('hole_number'),
            json.dumps(polygon_coords),
            center_lat, center_lng, area_sqft, color,
            data.get('notes'),
            now, now,
        ))
        zone_id = cursor.lastrowid

    logger.info("Created map zone %s '%s' for user %s", zone_id, name, user_id)
    return get_zone_by_id(zone_id, user_id)

def update_zone(zone_id, user_id, data):
    """Update an existing map zone.

    Only fields present in data are updated. If polygon_coords changes,
    area and centroid are recalculated.

    Returns:
        Updated zone dict, or None if not found.
    """
    allowed_fields = {
        'name', 'zone_type', 'hole_number', 'polygon_coords',
        'center_lat', 'center_lng', 'color', 'notes',
    }

    updates = {k: v for k, v in data.items() if k in allowed_fields}
    if not updates:
        return get_zone_by_id(zone_id, user_id)

    # Validate zone_type if provided
    if 'zone_type' in updates:
        if updates['zone_type'].lower() not in VALID_ZONE_TYPES:
            raise ValueError(f"Invalid zone_type '{updates['zone_type']}'")
        updates['zone_type'] = updates['zone_type'].lower()

    # If polygon_coords changed, recalculate area and centroid
    if 'polygon_coords' in updates:
        coords = updates['polygon_coords']
        if isinstance(coords, str):
            try:
                coords = json.loads(coords)
            except (json.JSONDecodeError, TypeError):
                coords = []
        updates['polygon_coords'] = json.dumps(coords)
        updates['area_sqft'] = calculate_zone_area(coords)
        centroid = calculate_centroid(coords)
        if 'center_lat' not in updates:
            updates['center_lat'] = centroid[0]
        if 'center_lng' not in updates:
            updates['center_lng'] = centroid[1]

    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    updates['updated_at'] = now

    set_clause = ', '.join(f'{col} = ?' for col in updates)
    values = list(updates.values()) + [zone_id, user_id]

    with get_db() as conn:
        cursor = conn.execute(
            f'UPDATE map_zones SET {set_clause} WHERE id = ? AND user_id = ?',
            values,
        )
        if cursor.rowcount == 0:
            logger.warning("Zone %s not found for user %s", zone_id, user_id)
            return None

    logger.info("Updated map zone %s", zone_id)
    return get_zone_by_id(zone_id, user_id)

def delete_zone(zone_id, user_id):
    """Delete a map zone. Pins linked to this zone will have zone_id set to NULL.

    Returns:
        True if deleted, False if not found.
    """
    with get_db() as conn:
        # Unlink pins (ON DELETE SET NULL should handle this, but be explicit)
        conn.execute(
            'UPDATE map_pins SET zone_id = NULL WHERE zone_id = ? AND user_id = ?',
            (zone_id, user_id),
        )
        cursor = conn.execute(
            'DELETE FROM map_zones WHERE id = ? AND user_id = ?',
            (zone_id, user_id),
        )
        deleted = cursor.rowcount > 0

    if deleted:
        logger.info("Deleted map zone %s for user %s", zone_id, user_id)
    else:
        logger.warning("Zone %s not found for deletion (user %s)", zone_id, user_id)
    return deleted


def get_zones(user_id, zone_type=None):
    """Get all zones for a user, optionally filtered by zone_type.

    Args:
        user_id: Owner.
        zone_type: Optional filter (e.g., 'green', 'fairway').

    Returns:
        List of zone dicts.
    """
    query = 'SELECT * FROM map_zones WHERE user_id = ?'
    params = [user_id]

    if zone_type:
        if zone_type.lower() not in VALID_ZONE_TYPES:
            raise ValueError(f"Invalid zone_type '{zone_type}'")
        query += ' AND zone_type = ?'
        params.append(zone_type.lower())

    query += ' ORDER BY hole_number, name'

    with get_db() as conn:
        cursor = conn.execute(query, params)
        rows = cursor.fetchall()

    return [_serialize_zone(row) for row in rows]


def get_zone_by_id(zone_id, user_id):
    """Get a single zone by ID with ownership check.

    Returns:
        Zone dict, or None if not found.
    """
    with get_db() as conn:
        cursor = conn.execute(
            'SELECT * FROM map_zones WHERE id = ? AND user_id = ?',
            (zone_id, user_id),
        )
        row = cursor.fetchone()

    return _serialize_zone(row)


def get_zones_geojson(user_id):
    """Return all zones for a user as a GeoJSON FeatureCollection.

    Each zone polygon becomes a Feature with zone metadata as properties.

    Returns:
        GeoJSON FeatureCollection dict.
    """
    zones = get_zones(user_id)
    features = []

    for zone in zones:
        coords = zone.get('polygon_coords', [])
        if not coords:
            continue

        properties = {
            'id': zone['id'],
            'name': zone['name'],
            'zone_type': zone['zone_type'],
            'hole_number': zone['hole_number'],
            'area_sqft': zone['area_sqft'],
            'color': zone['color'],
            'notes': zone['notes'],
        }
        feat = polygon_to_geojson(coords, properties)
        if feat:
            features.append(feat)

    return feature_collection(features)


# ---------------------------------------------------------------------------
# Pin Management
# ---------------------------------------------------------------------------

def create_pin(user_id, data):
    """Create a new map pin (point of interest).

    Args:
        user_id: Owner.
        data: dict with keys: lat, lng, pin_type, zone_id, title, description,
              severity, photo_url, linked_report_id, linked_equipment_id, status.

    Returns:
        dict of the newly created pin.

    Raises:
        ValueError: On invalid field values.
    """
    lat = data.get('lat')
    lng = data.get('lng')
    if lat is None or lng is None:
        raise ValueError("lat and lng are required for a pin")

    try:
        lat = float(lat)
        lng = float(lng)
    except (TypeError, ValueError):
        raise ValueError("lat and lng must be numeric values")

    pin_type = data.get('pin_type', 'observation').lower()
    if pin_type not in VALID_PIN_TYPES:
        raise ValueError(
            f"Invalid pin_type '{pin_type}'. Must be one of {VALID_PIN_TYPES}"
        )

    status = data.get('status', 'active').lower()
    if status not in VALID_PIN_STATUSES:
        raise ValueError(
            f"Invalid status '{status}'. Must be one of {VALID_PIN_STATUSES}"
        )

    severity = data.get('severity')
    if severity is not None:
        severity = int(severity)
        if severity < 1 or severity > 5:
            raise ValueError("Severity must be between 1 and 5")

    # Auto-detect which zone the pin falls in
    zone_id = data.get('zone_id')
    if zone_id is None:
        zone_id = _detect_zone_for_point(user_id, lat, lng)

    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

    with get_db() as conn:
        cursor = conn.execute('''
            INSERT INTO map_pins (
                user_id, zone_id, lat, lng, pin_type, title, description,
                severity, photo_url, linked_report_id, linked_equipment_id,
                status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_id, zone_id, lat, lng, pin_type,
            data.get('title'),
            data.get('description'),
            severity,
            data.get('photo_url'),
            data.get('linked_report_id'),
            data.get('linked_equipment_id'),
            status,
            now, now,
        ))
        pin_id = cursor.lastrowid

    logger.info("Created map pin %s for user %s", pin_id, user_id)
    return get_pin_by_id(pin_id, user_id)

def update_pin(pin_id, user_id, data):
    """Update an existing map pin.

    Only fields present in data are updated.

    Returns:
        Updated pin dict, or None if not found.
    """
    allowed_fields = {
        'zone_id', 'lat', 'lng', 'pin_type', 'title', 'description',
        'severity', 'photo_url', 'linked_report_id', 'linked_equipment_id',
        'status',
    }

    updates = {k: v for k, v in data.items() if k in allowed_fields}
    if not updates:
        return get_pin_by_id(pin_id, user_id)

    # Validate mutable constraints
    if 'pin_type' in updates:
        if updates['pin_type'].lower() not in VALID_PIN_TYPES:
            raise ValueError(f"Invalid pin_type '{updates['pin_type']}'")
        updates['pin_type'] = updates['pin_type'].lower()

    if 'status' in updates:
        if updates['status'].lower() not in VALID_PIN_STATUSES:
            raise ValueError(f"Invalid status '{updates['status']}'")
        updates['status'] = updates['status'].lower()
    if 'severity' in updates and updates['severity'] is not None:
        updates['severity'] = int(updates['severity'])
        if updates['severity'] < 1 or updates['severity'] > 5:
            raise ValueError("Severity must be between 1 and 5")

    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    updates['updated_at'] = now

    set_clause = ', '.join(f'{col} = ?' for col in updates)
    values = list(updates.values()) + [pin_id, user_id]

    with get_db() as conn:
        cursor = conn.execute(
            f'UPDATE map_pins SET {set_clause} WHERE id = ? AND user_id = ?',
            values,
        )
        if cursor.rowcount == 0:
            logger.warning("Pin %s not found for user %s", pin_id, user_id)
            return None

    logger.info("Updated map pin %s", pin_id)
    return get_pin_by_id(pin_id, user_id)


def delete_pin(pin_id, user_id):
    """Delete a map pin.

    Returns:
        True if deleted, False if not found.
    """
    with get_db() as conn:
        cursor = conn.execute(
            'DELETE FROM map_pins WHERE id = ? AND user_id = ?',
            (pin_id, user_id),
        )
        deleted = cursor.rowcount > 0

    if deleted:
        logger.info("Deleted map pin %s for user %s", pin_id, user_id)
    else:
        logger.warning("Pin %s not found for deletion (user %s)", pin_id, user_id)
    return deleted


def get_pin_by_id(pin_id, user_id):
    """Get a single pin by ID with ownership check."""
    with get_db() as conn:
        cursor = conn.execute(
            'SELECT * FROM map_pins WHERE id = ? AND user_id = ?',
            (pin_id, user_id),
        )
        row = cursor.fetchone()

    return _serialize_pin(row)


def get_pins(user_id, pin_type=None, zone_id=None, status=None):
    """Get pins for a user with optional filters.

    Args:
        user_id: Owner.
        pin_type: Filter by pin type.
        zone_id: Filter by zone.
        status: Filter by status (active/resolved/archived).

    Returns:
        List of pin dicts.
    """
    query = 'SELECT * FROM map_pins WHERE user_id = ?'
    params = [user_id]

    if pin_type:
        if pin_type.lower() not in VALID_PIN_TYPES:
            raise ValueError(f"Invalid pin_type '{pin_type}'")
        query += ' AND pin_type = ?'
        params.append(pin_type.lower())

    if zone_id is not None:
        query += ' AND zone_id = ?'
        params.append(zone_id)

    if status:
        if status.lower() not in VALID_PIN_STATUSES:
            raise ValueError(f"Invalid status '{status}'")
        query += ' AND status = ?'
        params.append(status.lower())

    query += ' ORDER BY created_at DESC'

    with get_db() as conn:
        cursor = conn.execute(query, params)
        rows = cursor.fetchall()

    return [_serialize_pin(row) for row in rows]


def get_pins_geojson(user_id, pin_type=None):
    """Return pins as a GeoJSON FeatureCollection.

    Args:
        user_id: Owner.
        pin_type: Optional filter.

    Returns:
        GeoJSON FeatureCollection dict.
    """
    pins = get_pins(user_id, pin_type=pin_type)
    features = []

    for pin in pins:
        if pin.get('lat') is None or pin.get('lng') is None:
            continue

        properties = {
            'id': pin['id'],
            'pin_type': pin['pin_type'],
            'title': pin['title'],
            'description': pin['description'],
            'severity': pin['severity'],
            'status': pin['status'],
            'zone_id': pin['zone_id'],
            'photo_url': pin['photo_url'],
            'linked_report_id': pin['linked_report_id'],
        }
        feat = point_to_geojson(pin['lat'], pin['lng'], properties)
        features.append(feat)

    return feature_collection(features)


def get_nearby_pins(user_id, lat, lng, radius_ft=100):
    """Find pins within a given radius of a GPS point.

    Uses Haversine distance calculation. Fetches all active pins for the user
    and filters by distance in Python (suitable for typical course pin counts).

    Args:
        user_id: Owner.
        lat, lng: Center point (decimal degrees).
        radius_ft: Search radius in feet (default 100).

    Returns:
        List of pin dicts with an added 'distance_ft' field, sorted by distance.
    """
    all_pins = get_pins(user_id, status='active')
    nearby = []

    for pin in all_pins:
        if pin.get('lat') is None or pin.get('lng') is None:
            continue

        dist = _haversine_ft(lat, lng, pin['lat'], pin['lng'])
        if dist <= radius_ft:
            pin['distance_ft'] = round(dist, 1)
            nearby.append(pin)

    nearby.sort(key=lambda p: p['distance_ft'])
    return nearby


def _detect_zone_for_point(user_id, lat, lng):
    """Detect which zone a point falls in. Returns zone_id or None."""
    try:
        zones = get_zones(user_id)
        for zone in zones:
            coords = zone.get('polygon_coords', [])
            if coords and point_in_polygon(lat, lng, coords):
                return zone['id']
    except Exception as e:
        logger.debug("Zone detection failed for (%s, %s): %s", lat, lng, e)
    return None


# ---------------------------------------------------------------------------
# Layer Management
# ---------------------------------------------------------------------------

def create_layer(user_id, data):
    """Create a new data layer (heatmap/overlay).

    Args:
        user_id: Owner.
        data: dict with keys: name, layer_type, data_json, visible, opacity.
    Returns:
        dict of the newly created layer.

    Raises:
        ValueError: On invalid field values.
    """
    name = data.get('name', '').strip()
    if not name:
        raise ValueError("Layer name is required")

    layer_type = data.get('layer_type', 'custom').lower()
    if layer_type not in VALID_LAYER_TYPES:
        raise ValueError(
            f"Invalid layer_type '{layer_type}'. Must be one of {VALID_LAYER_TYPES}"
        )

    data_json = data.get('data_json')
    if data_json and not isinstance(data_json, str):
        data_json = json.dumps(data_json)

    visible = 1 if data.get('visible', True) else 0
    opacity = float(data.get('opacity', 0.6))
    if opacity < 0 or opacity > 1:
        raise ValueError("Opacity must be between 0 and 1")

    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

    with get_db() as conn:
        cursor = conn.execute('''
            INSERT INTO map_layers (
                user_id, name, layer_type, data_json, visible, opacity,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_id, name, layer_type, data_json, visible, opacity,
            now, now,
        ))
        layer_id = cursor.lastrowid

    logger.info("Created map layer %s '%s' for user %s", layer_id, name, user_id)
    return get_layer_by_id(layer_id, user_id)


def update_layer(layer_id, user_id, data):
    """Update an existing data layer.

    Returns:
        Updated layer dict, or None if not found.
    """
    allowed_fields = {'name', 'layer_type', 'data_json', 'visible', 'opacity'}

    updates = {k: v for k, v in data.items() if k in allowed_fields}
    if not updates:
        return get_layer_by_id(layer_id, user_id)

    if 'layer_type' in updates:
        if updates['layer_type'].lower() not in VALID_LAYER_TYPES:
            raise ValueError(f"Invalid layer_type '{updates['layer_type']}'")
        updates['layer_type'] = updates['layer_type'].lower()
    if 'data_json' in updates and updates['data_json'] is not None:
        if not isinstance(updates['data_json'], str):
            updates['data_json'] = json.dumps(updates['data_json'])

    if 'visible' in updates:
        updates['visible'] = 1 if updates['visible'] else 0

    if 'opacity' in updates:
        updates['opacity'] = float(updates['opacity'])
        if updates['opacity'] < 0 or updates['opacity'] > 1:
            raise ValueError("Opacity must be between 0 and 1")

    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    updates['updated_at'] = now

    set_clause = ', '.join(f'{col} = ?' for col in updates)
    values = list(updates.values()) + [layer_id, user_id]

    with get_db() as conn:
        cursor = conn.execute(
            f'UPDATE map_layers SET {set_clause} WHERE id = ? AND user_id = ?',
            values,
        )
        if cursor.rowcount == 0:
            logger.warning("Layer %s not found for user %s", layer_id, user_id)
            return None

    logger.info("Updated map layer %s", layer_id)
    return get_layer_by_id(layer_id, user_id)

def delete_layer(layer_id, user_id):
    """Delete a data layer.

    Returns:
        True if deleted, False if not found.
    """
    with get_db() as conn:
        cursor = conn.execute(
            'DELETE FROM map_layers WHERE id = ? AND user_id = ?',
            (layer_id, user_id),
        )
        deleted = cursor.rowcount > 0

    if deleted:
        logger.info("Deleted map layer %s for user %s", layer_id, user_id)
    else:
        logger.warning("Layer %s not found for deletion (user %s)", layer_id, user_id)
    return deleted


def get_layer_by_id(layer_id, user_id):
    """Get a single layer by ID with ownership check."""
    with get_db() as conn:
        cursor = conn.execute(
            'SELECT * FROM map_layers WHERE id = ? AND user_id = ?',
            (layer_id, user_id),
        )
        row = cursor.fetchone()

    return _serialize_layer(row)

def get_layers(user_id):
    """Get all layers for a user.

    Returns:
        List of layer dicts ordered by creation date.
    """
    with get_db() as conn:
        cursor = conn.execute(
            'SELECT * FROM map_layers WHERE user_id = ? ORDER BY created_at DESC',
            (user_id,),
        )
        rows = cursor.fetchall()

    return [_serialize_layer(row) for row in rows]


def get_layer_by_name(user_id, layer_name):
    """Get a layer by name (or ID if numeric)."""
    with get_db() as conn:
        # Try numeric ID first
        try:
            lid = int(layer_name)
            row = conn.execute(
                'SELECT * FROM map_layers WHERE id = ? AND user_id = ?',
                (lid, user_id),
            ).fetchone()
        except (ValueError, TypeError):
            row = conn.execute(
                'SELECT * FROM map_layers WHERE name = ? AND user_id = ?',
                (layer_name, user_id),
            ).fetchone()
    if not row:
        return {'error': f'Layer {layer_name} not found'}
    return _serialize_layer(row)


def toggle_layer_visibility(layer_id, user_id):
    """Toggle the visible flag on a layer.

    Returns:
        Updated layer dict, or None if not found.
    """
    with get_db() as conn:
        # Read current visibility
        cursor = conn.execute(
            'SELECT visible FROM map_layers WHERE id = ? AND user_id = ?',
            (layer_id, user_id),
        )
        row = cursor.fetchone()
        if row is None:
            logger.warning("Layer %s not found for toggle (user %s)", layer_id, user_id)
            return None

        new_visible = 0 if row['visible'] else 1
        now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        conn.execute(
            'UPDATE map_layers SET visible = ?, updated_at = ? WHERE id = ? AND user_id = ?',
            (new_visible, now, layer_id, user_id),
        )

    logger.info("Toggled layer %s visibility to %s", layer_id, bool(new_visible))
    return get_layer_by_id(layer_id, user_id)


# ---------------------------------------------------------------------------
# Data Overlay Generation
# ---------------------------------------------------------------------------

def generate_disease_pressure_layer(user_id):
    """Generate a disease pressure heatmap layer from scouting report data.

    Queries scouting_reports for disease/pest issues with GPS coordinates
    and builds a weighted heatmap based on severity and recency.

    Returns:
        The created/updated layer dict, or None if no data.
    """
    try:
        with get_db() as conn:
            cursor = conn.execute('''
                SELECT gps_lat, gps_lng, severity, issue_type, status, scout_date, area
                FROM scouting_reports
                WHERE user_id = ?
                  AND gps_lat IS NOT NULL
                  AND gps_lng IS NOT NULL
                  AND issue_type IN ('disease', 'pest')
                ORDER BY scout_date DESC
            ''', (user_id,))
            rows = cursor.fetchall()
    except Exception as e:
        logger.error("Failed to query scouting reports for disease layer: %s", e)
        return None

    if not rows:
        logger.info("No disease/pest scouting data for user %s", user_id)
        return None

    now = datetime.utcnow()
    heatmap_points = []

    for row in rows:
        lat = row['gps_lat']
        lng = row['gps_lng']
        severity = row['severity'] or 3

        # Weight by recency: reports within 14 days get full weight,
        # older reports decay linearly over 90 days
        try:
            report_date = datetime.strptime(str(row['scout_date']), '%Y-%m-%d')
            days_ago = (now - report_date).days
        except (ValueError, TypeError):
            days_ago = 30

        if days_ago <= 14:
            recency_weight = 1.0
        elif days_ago <= 90:
            recency_weight = max(0.1, 1.0 - (days_ago - 14) / 76.0)
        else:
            recency_weight = 0.1

        # Resolved issues have lower weight
        status_weight = 0.3 if row['status'] == 'resolved' else 1.0

        weight = round((severity / 5.0) * recency_weight * status_weight, 3)

        heatmap_points.append({
            'lat': lat,
            'lng': lng,
            'weight': weight,
            'issue_type': row['issue_type'],
            'area': row['area'],
            'severity': severity,
        })

    layer_data = {
        'type': 'heatmap',
        'points': heatmap_points,
        'generated_at': now.strftime('%Y-%m-%d %H:%M:%S'),
        'source': 'scouting_reports',
        'report_count': len(heatmap_points),
    }

    # Upsert: update existing disease_pressure layer or create new
    return _upsert_generated_layer(
        user_id,
        name='Disease Pressure',
        layer_type='disease_pressure',
        data=layer_data,
    )


def generate_spray_coverage_layer(user_id, days=30):
    """Generate a spray coverage overlay from spray application history.

    Shows which areas have been sprayed recently, with intensity based on
    how many applications occurred.

    Args:
        user_id: Owner.
        days: Look-back window in days (default 30).

    Returns:
        The created/updated layer dict, or None if no data.
    """
    cutoff = (datetime.utcnow() - timedelta(days=days)).strftime('%Y-%m-%d')

    try:
        with get_db() as conn:
            cursor = conn.execute('''
                SELECT area, date, product_name, product_category, area_acreage
                FROM spray_applications
                WHERE user_id = ? AND date >= ?
                ORDER BY date DESC
            ''', (user_id, cutoff))
            rows = cursor.fetchall()
    except Exception as e:
        logger.error("Failed to query spray applications for coverage layer: %s", e)
        return None

    if not rows:
        logger.info("No spray applications in last %d days for user %s", days, user_id)
        return None

    # Aggregate by area
    area_coverage = {}
    for row in rows:
        area_name = row['area']
        if area_name not in area_coverage:
            area_coverage[area_name] = {
                'application_count': 0,
                'products': [],
                'last_spray_date': None,
                'total_acreage': 0,
            }
        area_coverage[area_name]['application_count'] += 1
        area_coverage[area_name]['products'].append({
            'name': row['product_name'],
            'category': row['product_category'],
            'date': row['date'],
        })
        if (area_coverage[area_name]['last_spray_date'] is None or
                row['date'] > area_coverage[area_name]['last_spray_date']):
            area_coverage[area_name]['last_spray_date'] = row['date']
        if row['area_acreage']:
            area_coverage[area_name]['total_acreage'] = row['area_acreage']

    # Deduplicate product lists (keep last 10)
    for area_name in area_coverage:
        area_coverage[area_name]['products'] = area_coverage[area_name]['products'][:10]

    now = datetime.utcnow()
    layer_data = {
        'type': 'area_coverage',
        'areas': area_coverage,
        'generated_at': now.strftime('%Y-%m-%d %H:%M:%S'),
        'source': 'spray_applications',
        'days_window': days,
        'total_applications': len(rows),
    }

    return _upsert_generated_layer(
        user_id,
        name=f'Spray Coverage (Last {days} Days)',
        layer_type='spray_coverage',
        data=layer_data,
    )

def generate_soil_test_layer(user_id, parameter='ph'):
    """Generate a soil test data overlay from soil test pins/samples.

    Reads map_pins of type 'sample' that have descriptions containing
    soil test values, and creates a heatmap layer for the specified parameter.

    Args:
        user_id: Owner.
        parameter: Soil parameter to map (default 'ph'). Common values:
                   'ph', 'organic_matter', 'phosphorus', 'potassium',
                   'calcium', 'magnesium', 'cec'.

    Returns:
        The created/updated layer dict, or None if no data.
    """
    try:
        with get_db() as conn:
            cursor = conn.execute('''
                SELECT id, lat, lng, title, description, created_at
                FROM map_pins
                WHERE user_id = ? AND pin_type = 'sample'
                  AND lat IS NOT NULL AND lng IS NOT NULL
                ORDER BY created_at DESC
            ''', (user_id,))
            rows = cursor.fetchall()
    except Exception as e:
        logger.error("Failed to query sample pins for soil layer: %s", e)
        return None
    if not rows:
        logger.info("No soil sample pins for user %s", user_id)
        return None

    points = []
    for row in rows:
        # Try to extract parameter value from description JSON or text
        value = _extract_soil_value(row['description'], parameter)
        if value is not None:
            points.append({
                'lat': row['lat'],
                'lng': row['lng'],
                'value': value,
                'pin_id': row['id'],
                'title': row['title'],
                'sampled_at': row['created_at'],
            })

    if not points:
        logger.info("No '%s' values found in soil samples for user %s", parameter, user_id)
        return None

    now = datetime.utcnow()
    layer_data = {
        'type': 'value_map',
        'parameter': parameter,
        'points': points,
        'generated_at': now.strftime('%Y-%m-%d %H:%M:%S'),
        'source': 'map_pins_sample',
        'sample_count': len(points),
        'min_value': min(p['value'] for p in points),
        'max_value': max(p['value'] for p in points),
        'avg_value': round(sum(p['value'] for p in points) / len(points), 2),
    }

    return _upsert_generated_layer(
        user_id,
        name=f'Soil Test: {parameter.upper()}',
        layer_type='soil_test',
        data=layer_data,
    )


def generate_moisture_layer(user_id):
    """Generate a moisture data overlay from observation pins and scouting reports.

    Combines moisture-related pins and scouting report moisture_level data
    into a heatmap layer.

    Returns:
        The created/updated layer dict, or None if no data.
    """
    points = []

    # Source 1: Scouting reports with moisture data
    try:
        with get_db() as conn:
            cursor = conn.execute('''
                SELECT gps_lat, gps_lng, moisture_level, scout_date, area
                FROM scouting_reports
                WHERE user_id = ?
                  AND gps_lat IS NOT NULL
                  AND gps_lng IS NOT NULL
                  AND moisture_level IS NOT NULL
                ORDER BY scout_date DESC
                LIMIT 500
            ''', (user_id,))
            scouting_rows = cursor.fetchall()
    except Exception as e:
        logger.error("Failed to query scouting reports for moisture layer: %s", e)
        scouting_rows = []

    moisture_values = {
        'dry': 0.2,
        'adequate': 0.5,
        'wet': 0.8,
        'saturated': 1.0,
    }

    for row in scouting_rows:
        level = str(row['moisture_level']).lower()
        value = moisture_values.get(level, 0.5)
        points.append({
            'lat': row['gps_lat'],
            'lng': row['gps_lng'],
            'value': value,
            'label': level,
            'source': 'scouting',
            'date': row['scout_date'],
            'area': row['area'],
        })

    # Source 2: Observation pins with moisture in title/description
    try:
        with get_db() as conn:
            cursor = conn.execute('''
                SELECT lat, lng, title, description, created_at
                FROM map_pins
                WHERE user_id = ?
                  AND pin_type = 'observation'
                  AND lat IS NOT NULL AND lng IS NOT NULL
                ORDER BY created_at DESC
                LIMIT 500
            ''', (user_id,))
            pin_rows = cursor.fetchall()
    except Exception as e:
        logger.error("Failed to query observation pins for moisture layer: %s", e)
        pin_rows = []

    for row in pin_rows:
        title = str(row['title'] or '').lower()
        desc = str(row['description'] or '').lower()
        combined = title + ' ' + desc

        # Check if this pin is moisture-related
        if any(kw in combined for kw in ('moisture', 'dry', 'wet', 'saturated', 'wilt', 'ldr')):
            # Try to extract a numeric moisture reading
            value = _extract_numeric_value(combined)
            if value is None:
                # Infer from keywords
                if 'saturated' in combined:
                    value = 1.0
                elif 'wet' in combined:
                    value = 0.8
                elif 'dry' in combined or 'wilt' in combined:
                    value = 0.2
                else:
                    value = 0.5

            points.append({
                'lat': row['lat'],
                'lng': row['lng'],
                'value': value,
                'label': row['title'],
                'source': 'pin',
                'date': row['created_at'],
            })

    if not points:
        logger.info("No moisture data for user %s", user_id)
        return None

    now = datetime.utcnow()
    layer_data = {
        'type': 'heatmap',
        'parameter': 'moisture',
        'points': points,
        'generated_at': now.strftime('%Y-%m-%d %H:%M:%S'),
        'source': 'scouting_reports+map_pins',
        'point_count': len(points),
    }

    return _upsert_generated_layer(
        user_id,
        name='Moisture Map',
        layer_type='moisture',
        data=layer_data,
    )


# ---------------------------------------------------------------------------
# Internal Helpers
# ---------------------------------------------------------------------------

def _upsert_generated_layer(user_id, name, layer_type, data):
    """Create or update a generated layer. If a layer of the same type exists,
    update it; otherwise create a new one.

    Returns:
        Layer dict.
    """
    data_json = json.dumps(data)
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

    with get_db() as conn:
        # Check for existing layer of this type
        cursor = conn.execute(
            'SELECT id FROM map_layers WHERE user_id = ? AND layer_type = ?',
            (user_id, layer_type),
        )
        existing = cursor.fetchone()

        if existing:
            layer_id = existing['id']
            conn.execute(
                'UPDATE map_layers SET name = ?, data_json = ?, updated_at = ? '
                'WHERE id = ? AND user_id = ?',
                (name, data_json, now, layer_id, user_id),
            )
            logger.info("Updated generated layer %s (%s) for user %s", layer_id, layer_type, user_id)
        else:
            cursor = conn.execute('''
                INSERT INTO map_layers (
                    user_id, name, layer_type, data_json, visible, opacity,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, 1, 0.6, ?, ?)
            ''', (user_id, name, layer_type, data_json, now, now))
            layer_id = cursor.lastrowid
            logger.info("Created generated layer %s (%s) for user %s", layer_id, layer_type, user_id)

    return get_layer_by_id(layer_id, user_id)

def _extract_soil_value(description, parameter):
    """Extract a numeric soil test value for a parameter from pin description.

    Supports both JSON-formatted descriptions and plain text patterns
    like 'pH: 6.5' or 'phosphorus: 42 ppm'.

    Returns:
        float value or None.
    """
    if not description:
        return None

    # Try JSON first
    try:
        data = json.loads(description)
        if isinstance(data, dict):
            # Try exact key match, then case variants
            val = data.get(parameter) or data.get(parameter.lower()) or data.get(parameter.upper())
            if val is not None:
                return float(val)
    except (json.JSONDecodeError, TypeError, ValueError):
        pass

    # Try plain text pattern: "parameter: value" or "parameter = value"
    desc_lower = description.lower()
    param_lower = parameter.lower()

    patterns = [
        rf'{re.escape(param_lower)}\s*[:=]\s*([\d.]+)',
        rf'{re.escape(param_lower)}\s+([\d.]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, desc_lower)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                continue

    return None


def _extract_numeric_value(text):
    """Extract the first numeric value from text. Returns float or None."""
    if not text:
        return None

    match = re.search(r'(\d+\.?\d*)', text)
    if match:
        try:
            val = float(match.group(1))
            # Normalize to 0-1 range if it looks like a percentage or reading
            if val > 1:
                return min(val / 100.0, 1.0)
            return val
        except ValueError:
            pass
    return None