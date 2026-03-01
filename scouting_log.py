"""
Scouting Log Module for Greenside AI.

Photo scouting and field log system for turfgrass management.
Supports report CRUD, photo attachments, scouting templates,
analytics, and weekly report generation.

Database: Uses get_db() context manager from db.py (SQLite/PostgreSQL).
"""

import json
import logging
from datetime import datetime, timedelta

from db import get_db

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_AREAS = ('greens', 'fairways', 'tees', 'rough', 'bunkers', 'practice')
VALID_ISSUE_TYPES = ('disease', 'pest', 'weed', 'drought', 'mechanical', 'nutrient', 'other')
VALID_SEVERITIES = (1, 2, 3, 4, 5)
VALID_MOISTURE_LEVELS = ('dry', 'adequate', 'wet', 'saturated')
VALID_STATUSES = ('open', 'monitoring', 'treated', 'resolved')
VALID_PHOTO_TYPES = ('initial', 'progress', 'resolved')
VALID_FREQUENCIES = ('daily', 'weekly', 'biweekly', 'monthly')


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------

def _serialize_report(row):
    """Convert a database row to a JSON-serializable dict."""
    if row is None:
        return None
    keys = [
        'id', 'user_id', 'scout_date', 'area', 'hole_number',
        'location_description', 'gps_lat', 'gps_lng', 'issue_type',
        'severity', 'diagnosis', 'diagnosis_confidence',
        'weather_conditions', 'soil_temp', 'air_temp', 'moisture_level',
        'treatment_applied', 'treatment_product', 'treatment_date',
        'follow_up_date', 'status', 'notes', 'created_at', 'updated_at',
    ]
    result = {}
    for key in keys:
        try:
            val = row[key]
            result[key] = str(val) if isinstance(val, (datetime,)) else val
        except (KeyError, IndexError):
            result[key] = None
    return result


def _serialize_photo(row):
    """Convert a photo row to a JSON-serializable dict."""
    if row is None:
        return None
    keys = ['id', 'report_id', 'photo_url', 'photo_type', 'caption', 'taken_at', 'created_at']
    result = {}
    for key in keys:
        try:
            val = row[key]
            result[key] = str(val) if isinstance(val, (datetime,)) else val
        except (KeyError, IndexError):
            result[key] = None
    # Template uses .type shorthand; also expose photo_url as .data
    result['type'] = result.get('photo_type')
    result['data'] = result.get('photo_url')
    return result


def _serialize_template(row):
    """Convert a template row to a JSON-serializable dict."""
    if row is None:
        return None
    result = {}
    for key in ['id', 'user_id', 'name', 'checklist_json', 'area', 'frequency', 'created_at']:
        try:
            val = row[key]
            result[key] = str(val) if isinstance(val, (datetime,)) else val
        except (KeyError, IndexError):
            result[key] = None
    # Parse checklist_json into a list if it is a string
    if isinstance(result.get('checklist_json'), str):
        try:
            result['checklist_json'] = json.loads(result['checklist_json'])
        except (json.JSONDecodeError, TypeError):
            pass
    return result


# ---------------------------------------------------------------------------
# Table initialisation
# ---------------------------------------------------------------------------

def init_scouting_tables():
    """Create scouting_reports, scouting_photos, and scouting_templates tables."""
    with get_db() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS scouting_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                scout_date TEXT NOT NULL,
                area TEXT NOT NULL,
                hole_number INTEGER,
                location_description TEXT,
                gps_lat REAL,
                gps_lng REAL,
                issue_type TEXT NOT NULL,
                severity INTEGER NOT NULL DEFAULT 3,
                diagnosis TEXT,
                diagnosis_confidence REAL,
                weather_conditions TEXT,
                soil_temp REAL,
                air_temp REAL,
                moisture_level TEXT,
                treatment_applied TEXT,
                treatment_product TEXT,
                treatment_date TEXT,
                follow_up_date TEXT,
                status TEXT NOT NULL DEFAULT 'open',
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        ''')

        conn.execute('''
            CREATE TABLE IF NOT EXISTS scouting_photos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_id INTEGER NOT NULL,
                photo_url TEXT NOT NULL,
                photo_type TEXT NOT NULL DEFAULT 'initial',
                caption TEXT,
                taken_at TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (report_id) REFERENCES scouting_reports(id) ON DELETE CASCADE
            )
        ''')

        conn.execute('''
            CREATE TABLE IF NOT EXISTS scouting_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                checklist_json TEXT NOT NULL,
                area TEXT,
                frequency TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        ''')

    logger.info("Scouting tables initialised successfully")


# ---------------------------------------------------------------------------
# Report CRUD
# ---------------------------------------------------------------------------

def create_report(user_id, data):
    """
    Create a new scouting report.

    Args:
        user_id: Owner of the report.
        data: dict with report fields (area, issue_type, severity, etc.).

    Returns:
        dict of the newly created report.

    Raises:
        ValueError: On invalid field values.
    """
    area = data.get('area', '').lower()
    if area not in VALID_AREAS:
        raise ValueError(f"Invalid area '{area}'. Must be one of {VALID_AREAS}")

    issue_type = data.get('issue_type', '').lower()
    if issue_type not in VALID_ISSUE_TYPES:
        raise ValueError(f"Invalid issue_type '{issue_type}'. Must be one of {VALID_ISSUE_TYPES}")

    severity = int(data.get('severity', 3))
    if severity not in VALID_SEVERITIES:
        raise ValueError(f"Severity must be 1-5, got {severity}")

    moisture_level = data.get('moisture_level')
    if moisture_level and moisture_level.lower() not in VALID_MOISTURE_LEVELS:
        raise ValueError(f"Invalid moisture_level '{moisture_level}'")

    status = data.get('status', 'open').lower()
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status '{status}'")

    diagnosis_confidence = data.get('diagnosis_confidence')
    if diagnosis_confidence is not None:
        diagnosis_confidence = float(diagnosis_confidence)
        if not 0 <= diagnosis_confidence <= 1:
            raise ValueError("diagnosis_confidence must be between 0 and 1")

    scout_date = data.get('scout_date', datetime.utcnow().strftime('%Y-%m-%d'))
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

    with get_db() as conn:
        cursor = conn.execute('''
            INSERT INTO scouting_reports (
                user_id, scout_date, area, hole_number, location_description,
                gps_lat, gps_lng, issue_type, severity, diagnosis,
                diagnosis_confidence, weather_conditions, soil_temp, air_temp,
                moisture_level, treatment_applied, treatment_product,
                treatment_date, follow_up_date, status, notes,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_id, scout_date, area,
            data.get('hole_number'),
            data.get('location_description'),
            data.get('gps_lat'),
            data.get('gps_lng'),
            issue_type, severity,
            data.get('diagnosis'),
            diagnosis_confidence,
            data.get('weather_conditions'),
            data.get('soil_temp'),
            data.get('air_temp'),
            moisture_level.lower() if moisture_level else None,
            data.get('treatment_applied'),
            data.get('treatment_product'),
            data.get('treatment_date'),
            data.get('follow_up_date'),
            status,
            data.get('notes'),
            now, now,
        ))
        report_id = cursor.lastrowid

    logger.info("Created scouting report %s for user %s", report_id, user_id)
    return get_report_by_id(report_id, user_id)


def update_report(report_id, user_id, data):
    """
    Update an existing scouting report.

    Only fields present in *data* are updated.

    Returns:
        Updated report dict, or None if not found.
    """
    allowed_fields = {
        'scout_date', 'area', 'hole_number', 'location_description',
        'gps_lat', 'gps_lng', 'issue_type', 'severity', 'diagnosis',
        'diagnosis_confidence', 'weather_conditions', 'soil_temp', 'air_temp',
        'moisture_level', 'treatment_applied', 'treatment_product',
        'treatment_date', 'follow_up_date', 'status', 'notes',
    }

    updates = {k: v for k, v in data.items() if k in allowed_fields}
    if not updates:
        return get_report_by_id(report_id, user_id)

    # Validate mutable constraints
    if 'area' in updates and updates['area'].lower() not in VALID_AREAS:
        raise ValueError(f"Invalid area '{updates['area']}'")
    if 'issue_type' in updates and updates['issue_type'].lower() not in VALID_ISSUE_TYPES:
        raise ValueError(f"Invalid issue_type '{updates['issue_type']}'")
    if 'severity' in updates:
        updates['severity'] = int(updates['severity'])
        if updates['severity'] not in VALID_SEVERITIES:
            raise ValueError("Severity must be 1-5")
    if 'moisture_level' in updates and updates['moisture_level']:
        if updates['moisture_level'].lower() not in VALID_MOISTURE_LEVELS:
            raise ValueError(f"Invalid moisture_level '{updates['moisture_level']}'")
    if 'status' in updates and updates['status'].lower() not in VALID_STATUSES:
        raise ValueError(f"Invalid status '{updates['status']}'")
    if 'diagnosis_confidence' in updates and updates['diagnosis_confidence'] is not None:
        dc = float(updates['diagnosis_confidence'])
        if not 0 <= dc <= 1:
            raise ValueError("diagnosis_confidence must be between 0 and 1")
        updates['diagnosis_confidence'] = dc

    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    updates['updated_at'] = now

    set_clause = ', '.join(f'{col} = ?' for col in updates)
    values = list(updates.values()) + [report_id, user_id]

    with get_db() as conn:
        cursor = conn.execute(
            f'UPDATE scouting_reports SET {set_clause} WHERE id = ? AND user_id = ?',
            values,
        )
        if cursor.rowcount == 0:
            logger.warning("Report %s not found for user %s", report_id, user_id)
            return None

    logger.info("Updated scouting report %s", report_id)
    return get_report_by_id(report_id, user_id)


def delete_report(report_id, user_id):
    """
    Delete a scouting report and its associated photos.

    Returns:
        True if deleted, False if not found.
    """
    with get_db() as conn:
        # Delete photos first (cascade may not be on for SQLite by default)
        conn.execute(
            'DELETE FROM scouting_photos WHERE report_id = ?', (report_id,)
        )
        cursor = conn.execute(
            'DELETE FROM scouting_reports WHERE id = ? AND user_id = ?',
            (report_id, user_id),
        )
        deleted = cursor.rowcount > 0

    if deleted:
        logger.info("Deleted scouting report %s for user %s", report_id, user_id)
    else:
        logger.warning("Report %s not found for deletion (user %s)", report_id, user_id)
    return deleted


def get_reports(user_id, start_date=None, end_date=None, area=None,
                issue_type=None, status=None):
    """
    Return filtered list of scouting reports for a user.

    All filter parameters are optional.
    """
    query = 'SELECT * FROM scouting_reports WHERE user_id = ?'
    params = [user_id]

    if start_date:
        query += ' AND scout_date >= ?'
        params.append(start_date)
    if end_date:
        query += ' AND scout_date <= ?'
        params.append(end_date)
    if area:
        query += ' AND area = ?'
        params.append(area.lower())
    if issue_type:
        query += ' AND issue_type = ?'
        params.append(issue_type.lower())
    if status:
        query += ' AND status = ?'
        params.append(status.lower())

    query += ' ORDER BY scout_date DESC, created_at DESC'

    with get_db() as conn:
        rows = conn.execute(query, params).fetchall()
    return [_serialize_report(r) for r in rows]


def get_report_by_id(report_id, user_id):
    """
    Return a single scouting report with its photos attached.

    Returns:
        dict with report fields and a 'photos' list, or None.
    """
    with get_db() as conn:
        row = conn.execute(
            'SELECT * FROM scouting_reports WHERE id = ? AND user_id = ?',
            (report_id, user_id),
        ).fetchone()
        if row is None:
            return None
        report = _serialize_report(row)

        photos = conn.execute(
            'SELECT * FROM scouting_photos WHERE report_id = ? ORDER BY created_at ASC',
            (report_id,),
        ).fetchall()
        report['photos'] = [_serialize_photo(p) for p in photos]
    return report


def update_report_status(report_id, user_id, status):
    """
    Change the status of a scouting report.

    Returns:
        Updated report dict, or None if not found.
    """
    status = status.lower()
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status '{status}'. Must be one of {VALID_STATUSES}")

    return update_report(report_id, user_id, {'status': status})


def get_open_issues(user_id):
    """Return all non-resolved reports for a user."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM scouting_reports WHERE user_id = ? AND status != 'resolved' "
            "ORDER BY severity DESC, scout_date DESC",
            (user_id,),
        ).fetchall()
    return [_serialize_report(r) for r in rows]


# ---------------------------------------------------------------------------
# Photo management
# ---------------------------------------------------------------------------

def add_photo(report_id, user_id, photo_data, photo_type='initial', caption=''):
    """
    Attach a photo (base64 data or URL) to a scouting report.

    Args:
        report_id: The parent report.
        user_id: Must own the parent report.
        photo_data: base64 string or file path.
        photo_type: 'initial', 'progress', or 'resolved'.
        caption: Optional description.

    Returns:
        dict of the created photo record.

    Raises:
        ValueError: If the report does not belong to the user or photo_type is invalid.
    """
    if photo_type not in VALID_PHOTO_TYPES:
        raise ValueError(f"Invalid photo_type '{photo_type}'. Must be one of {VALID_PHOTO_TYPES}")

    # Verify report ownership
    with get_db() as conn:
        owner_check = conn.execute(
            'SELECT id FROM scouting_reports WHERE id = ? AND user_id = ?',
            (report_id, user_id),
        ).fetchone()
        if owner_check is None:
            raise ValueError(f"Report {report_id} not found for user {user_id}")

        now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        cursor = conn.execute('''
            INSERT INTO scouting_photos (report_id, photo_url, photo_type, caption, taken_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (report_id, photo_data, photo_type, caption, now, now))
        photo_id = cursor.lastrowid

        row = conn.execute(
            'SELECT * FROM scouting_photos WHERE id = ?', (photo_id,)
        ).fetchone()

    logger.info("Added photo %s to report %s", photo_id, report_id)
    return _serialize_photo(row)


def get_photos(report_id):
    """Return all photos attached to a report."""
    with get_db() as conn:
        rows = conn.execute(
            'SELECT * FROM scouting_photos WHERE report_id = ? ORDER BY created_at ASC',
            (report_id,),
        ).fetchall()
    return [_serialize_photo(r) for r in rows]


def delete_photo(photo_id, user_id):
    """
    Delete a photo. The user must own the parent report.

    Returns:
        True if deleted, False if not found or not authorised.
    """
    with get_db() as conn:
        # Verify ownership via the parent report
        row = conn.execute('''
            SELECT sp.id FROM scouting_photos sp
            JOIN scouting_reports sr ON sp.report_id = sr.id
            WHERE sp.id = ? AND sr.user_id = ?
        ''', (photo_id, user_id)).fetchone()
        if row is None:
            logger.warning("Photo %s not found or not owned by user %s", photo_id, user_id)
            return False

        conn.execute('DELETE FROM scouting_photos WHERE id = ?', (photo_id,))

    logger.info("Deleted photo %s (user %s)", photo_id, user_id)
    return True


# ---------------------------------------------------------------------------
# Scouting templates
# ---------------------------------------------------------------------------

def get_scouting_templates(user_id):
    """Return all scouting templates for a user."""
    with get_db() as conn:
        rows = conn.execute(
            'SELECT * FROM scouting_templates WHERE user_id = ? ORDER BY name ASC',
            (user_id,),
        ).fetchall()
    return [_serialize_template(r) for r in rows]


def save_scouting_template(user_id, data):
    """
    Create or update a scouting template.

    If a template with the same name already exists for the user, it is updated.
    Otherwise a new template is created.

    Args:
        user_id: Owner.
        data: dict with 'name', 'checklist_json', and optional 'area', 'frequency'.

    Returns:
        dict of the saved template.
    """
    name = data.get('name')
    if not name:
        raise ValueError("Template name is required")

    checklist = data.get('checklist_json')
    if checklist is None:
        raise ValueError("checklist_json is required")
    if isinstance(checklist, (list, dict)):
        checklist_str = json.dumps(checklist)
    else:
        # Validate it is parseable JSON
        try:
            json.loads(checklist)
        except (json.JSONDecodeError, TypeError):
            raise ValueError("checklist_json must be valid JSON")
        checklist_str = checklist

    area = data.get('area')
    if area and area.lower() not in VALID_AREAS:
        raise ValueError(f"Invalid area '{area}'")

    frequency = data.get('frequency')
    if frequency and frequency.lower() not in VALID_FREQUENCIES:
        raise ValueError(f"Invalid frequency '{frequency}'")

    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

    with get_db() as conn:
        # Check if template with same name exists for this user
        existing = conn.execute(
            'SELECT id FROM scouting_templates WHERE user_id = ? AND name = ?',
            (user_id, name),
        ).fetchone()

        if existing:
            conn.execute('''
                UPDATE scouting_templates
                SET checklist_json = ?, area = ?, frequency = ?
                WHERE id = ? AND user_id = ?
            ''', (
                checklist_str,
                area.lower() if area else None,
                frequency.lower() if frequency else None,
                existing['id'], user_id,
            ))
            template_id = existing['id']
            logger.info("Updated scouting template %s for user %s", template_id, user_id)
        else:
            cursor = conn.execute('''
                INSERT INTO scouting_templates (user_id, name, checklist_json, area, frequency, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                user_id, name, checklist_str,
                area.lower() if area else None,
                frequency.lower() if frequency else None,
                now,
            ))
            template_id = cursor.lastrowid
            logger.info("Created scouting template %s for user %s", template_id, user_id)

        row = conn.execute(
            'SELECT * FROM scouting_templates WHERE id = ?', (template_id,)
        ).fetchone()

    return _serialize_template(row)


def get_scouting_template_by_id(template_id, user_id):
    """Get a single scouting template by ID."""
    with get_db() as conn:
        row = conn.execute(
            'SELECT * FROM scouting_templates WHERE id = ? AND user_id = ?',
            (template_id, user_id),
        ).fetchone()
    if not row:
        raise ValueError(f"Template {template_id} not found")
    return _serialize_template(row)


def delete_scouting_template(template_id, user_id):
    """
    Delete a scouting template.

    Returns:
        True if deleted, False if not found.
    """
    with get_db() as conn:
        cursor = conn.execute(
            'DELETE FROM scouting_templates WHERE id = ? AND user_id = ?',
            (template_id, user_id),
        )
        deleted = cursor.rowcount > 0

    if deleted:
        logger.info("Deleted scouting template %s (user %s)", template_id, user_id)
    return deleted


def get_default_checklists():
    """
    Return built-in scouting checklists for common inspection scenarios.

    Returns:
        list of dicts, each with 'name', 'area', 'frequency', and 'checklist_json'.
    """
    return [
        {
            'name': 'Morning Greens Inspection',
            'area': 'greens',
            'frequency': 'daily',
            'checklist_json': [
                {'item': 'Surface firmness', 'type': 'rating', 'scale': '1-10'},
                {'item': 'Green speed (stimpmeter)', 'type': 'number', 'unit': 'feet'},
                {'item': 'Turf color uniformity', 'type': 'rating', 'scale': '1-10'},
                {'item': 'Disease signs (dollar spot, brown patch, pythium)',
                 'type': 'checkbox',
                 'options': ['none', 'dollar spot', 'brown patch', 'pythium', 'other']},
                {'item': 'Soil moisture level', 'type': 'select',
                 'options': ['dry', 'adequate', 'wet', 'saturated']},
                {'item': 'Dew presence', 'type': 'checkbox',
                 'options': ['heavy', 'light', 'none']},
                {'item': 'Mowing quality', 'type': 'rating', 'scale': '1-10'},
                {'item': 'Ball mark damage', 'type': 'select',
                 'options': ['none', 'light', 'moderate', 'heavy']},
                {'item': 'Notes', 'type': 'text'},
            ],
        },
        {
            'name': 'Weekly Full Course Scout',
            'area': None,
            'frequency': 'weekly',
            'checklist_json': [
                {'section': 'Greens', 'items': [
                    {'item': 'Disease presence', 'type': 'checkbox',
                     'options': ['none', 'dollar spot', 'brown patch',
                                 'anthracnose', 'pythium', 'other']},
                    {'item': 'Pest activity', 'type': 'checkbox',
                     'options': ['none', 'grubs', 'cutworms',
                                 'armyworms', 'mites', 'other']},
                    {'item': 'Weed pressure', 'type': 'checkbox',
                     'options': ['none', 'poa annua', 'clover',
                                 'crabgrass', 'goosegrass', 'other']},
                    {'item': 'Overall turf quality', 'type': 'rating', 'scale': '1-10'},
                ]},
                {'section': 'Fairways', 'items': [
                    {'item': 'Disease presence', 'type': 'checkbox',
                     'options': ['none', 'dollar spot', 'brown patch', 'rust', 'other']},
                    {'item': 'Pest activity', 'type': 'checkbox',
                     'options': ['none', 'grubs', 'chinch bugs', 'billbugs', 'other']},
                    {'item': 'Weed pressure', 'type': 'checkbox',
                     'options': ['none', 'crabgrass', 'goosegrass',
                                 'dandelion', 'clover', 'other']},
                    {'item': 'Overall turf quality', 'type': 'rating', 'scale': '1-10'},
                ]},
                {'section': 'Tees', 'items': [
                    {'item': 'Disease presence', 'type': 'checkbox',
                     'options': ['none', 'other']},
                    {'item': 'Pest activity', 'type': 'checkbox',
                     'options': ['none', 'other']},
                    {'item': 'Weed pressure', 'type': 'checkbox',
                     'options': ['none', 'other']},
                    {'item': 'Overall turf quality', 'type': 'rating', 'scale': '1-10'},
                    {'item': 'Divot recovery', 'type': 'select',
                     'options': ['excellent', 'good', 'fair', 'poor']},
                ]},
                {'section': 'Rough', 'items': [
                    {'item': 'Disease presence', 'type': 'checkbox',
                     'options': ['none', 'other']},
                    {'item': 'Pest activity', 'type': 'checkbox',
                     'options': ['none', 'other']},
                    {'item': 'Weed pressure', 'type': 'checkbox',
                     'options': ['none', 'other']},
                    {'item': 'Overall turf quality', 'type': 'rating', 'scale': '1-10'},
                ]},
                {'section': 'Bunkers', 'items': [
                    {'item': 'Sand depth adequate', 'type': 'checkbox',
                     'options': ['yes', 'no']},
                    {'item': 'Edge maintenance', 'type': 'select',
                     'options': ['excellent', 'good', 'fair', 'poor']},
                    {'item': 'Drainage issues', 'type': 'checkbox',
                     'options': ['none', 'minor', 'major']},
                    {'item': 'Contamination (weeds, debris)', 'type': 'select',
                     'options': ['none', 'light', 'moderate', 'heavy']},
                ]},
            ],
        },
        {
            'name': 'Post-Application Check',
            'area': None,
            'frequency': 'weekly',
            'checklist_json': [
                {'item': 'Application target area', 'type': 'text'},
                {'item': 'Product applied', 'type': 'text'},
                {'item': 'Days since application', 'type': 'number'},
                {'item': 'Efficacy rating', 'type': 'rating', 'scale': '1-10'},
                {'item': 'Phytotoxicity observed', 'type': 'select',
                 'options': ['none', 'slight tip burn',
                             'moderate discoloration', 'severe damage']},
                {'item': 'Coverage uniformity', 'type': 'select',
                 'options': ['excellent', 'good', 'fair', 'poor']},
                {'item': 'Re-application needed', 'type': 'checkbox',
                 'options': ['yes', 'no']},
                {'item': 'Notes on turf response', 'type': 'text'},
            ],
        },
        {
            'name': 'Pre-Tournament Inspection',
            'area': None,
            'frequency': 'monthly',
            'checklist_json': [
                {'section': 'Greens', 'items': [
                    {'item': 'Green speed (stimpmeter)', 'type': 'number', 'unit': 'feet'},
                    {'item': 'Speed consistency across holes', 'type': 'rating',
                     'scale': '1-10'},
                    {'item': 'Surface uniformity', 'type': 'rating', 'scale': '1-10'},
                    {'item': 'Pin placement conditions', 'type': 'select',
                     'options': ['excellent', 'good', 'fair', 'poor']},
                    {'item': 'Disease or stress visible', 'type': 'checkbox',
                     'options': ['yes', 'no']},
                ]},
                {'section': 'Fairways', 'items': [
                    {'item': 'Mowing pattern quality', 'type': 'rating', 'scale': '1-10'},
                    {'item': 'Lie consistency', 'type': 'select',
                     'options': ['excellent', 'good', 'fair', 'poor']},
                    {'item': 'Divot fill level', 'type': 'select',
                     'options': ['full', 'adequate', 'needs attention']},
                ]},
                {'section': 'Bunkers', 'items': [
                    {'item': 'Sand condition', 'type': 'rating', 'scale': '1-10'},
                    {'item': 'Rake availability', 'type': 'checkbox',
                     'options': ['all present', 'some missing']},
                    {'item': 'Edge definition', 'type': 'select',
                     'options': ['sharp', 'acceptable', 'needs work']},
                ]},
                {'section': 'Hazard Areas', 'items': [
                    {'item': 'Penalty area markings correct', 'type': 'checkbox',
                     'options': ['yes', 'no']},
                    {'item': 'OB stakes visible', 'type': 'checkbox',
                     'options': ['yes', 'no']},
                    {'item': 'Cart path conditions', 'type': 'select',
                     'options': ['excellent', 'good', 'fair', 'poor']},
                    {'item': 'Spectator areas prepared', 'type': 'checkbox',
                     'options': ['yes', 'no']},
                ]},
                {'section': 'General', 'items': [
                    {'item': 'Overall course presentation', 'type': 'rating',
                     'scale': '1-10'},
                    {'item': 'Signage in place', 'type': 'checkbox',
                     'options': ['yes', 'no']},
                    {'item': 'Practice area ready', 'type': 'checkbox',
                     'options': ['yes', 'no']},
                    {'item': 'Notes / concerns', 'type': 'text'},
                ]},
            ],
        },
    ]


# ---------------------------------------------------------------------------
# Analytics and reporting
# ---------------------------------------------------------------------------

def get_issue_summary(user_id, days=30):
    """
    Summarise scouting issues for the past *days*.

    Returns:
        dict with 'by_type', 'by_area', 'by_severity', and 'total' counts.
    """
    cutoff = (datetime.utcnow() - timedelta(days=days)).strftime('%Y-%m-%d')

    with get_db() as conn:
        by_type = conn.execute(
            'SELECT issue_type, COUNT(*) as cnt FROM scouting_reports '
            'WHERE user_id = ? AND scout_date >= ? '
            'GROUP BY issue_type ORDER BY cnt DESC',
            (user_id, cutoff),
        ).fetchall()

        by_area = conn.execute(
            'SELECT area, COUNT(*) as cnt FROM scouting_reports '
            'WHERE user_id = ? AND scout_date >= ? '
            'GROUP BY area ORDER BY cnt DESC',
            (user_id, cutoff),
        ).fetchall()

        by_severity = conn.execute(
            'SELECT severity, COUNT(*) as cnt FROM scouting_reports '
            'WHERE user_id = ? AND scout_date >= ? '
            'GROUP BY severity ORDER BY severity DESC',
            (user_id, cutoff),
        ).fetchall()

        total_row = conn.execute(
            'SELECT COUNT(*) as cnt FROM scouting_reports '
            'WHERE user_id = ? AND scout_date >= ?',
            (user_id, cutoff),
        ).fetchone()

    return {
        'days': days,
        'total': total_row['cnt'] if total_row else 0,
        'by_type': [{'issue_type': r['issue_type'], 'count': r['cnt']} for r in by_type],
        'by_area': [{'area': r['area'], 'count': r['cnt']} for r in by_area],
        'by_severity': [{'severity': r['severity'], 'count': r['cnt']} for r in by_severity],
    }


def get_disease_pressure_map(user_id):
    """
    Return currently open disease issues grouped by area.

    Returns:
        dict mapping area name to list of open disease report summaries.
    """
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM scouting_reports "
            "WHERE user_id = ? AND issue_type = 'disease' AND status != 'resolved' "
            "ORDER BY area, severity DESC",
            (user_id,),
        ).fetchall()

    pressure_map = {}
    for r in rows:
        report = _serialize_report(r)
        area = report['area']
        if area not in pressure_map:
            pressure_map[area] = []
        pressure_map[area].append({
            'id': report['id'],
            'diagnosis': report['diagnosis'],
            'severity': report['severity'],
            'status': report['status'],
            'scout_date': report['scout_date'],
            'hole_number': report['hole_number'],
            'location_description': report['location_description'],
            'gps_lat': report['gps_lat'],
            'gps_lng': report['gps_lng'],
        })

    return pressure_map


def get_treatment_history(user_id, issue_type=None):
    """
    Return reports that have treatment information, optionally filtered by issue type.

    Returns:
        list of dicts with treatment details.
    """
    query = (
        'SELECT * FROM scouting_reports '
        'WHERE user_id = ? AND treatment_applied IS NOT NULL'
    )
    params = [user_id]

    if issue_type:
        query += ' AND issue_type = ?'
        params.append(issue_type.lower())

    query += ' ORDER BY treatment_date DESC, scout_date DESC'

    with get_db() as conn:
        rows = conn.execute(query, params).fetchall()

    results = []
    for r in rows:
        report = _serialize_report(r)
        results.append({
            'id': report['id'],
            'scout_date': report['scout_date'],
            'area': report['area'],
            'hole_number': report['hole_number'],
            'issue_type': report['issue_type'],
            'diagnosis': report['diagnosis'],
            'severity': report['severity'],
            'treatment_applied': report['treatment_applied'],
            'treatment_product': report['treatment_product'],
            'treatment_date': report['treatment_date'],
            'status': report['status'],
        })
    return results


def generate_weekly_report(user_id):
    """
    Auto-generate a summary of the past 7 days of scouting activity.

    Returns:
        dict with sections: overview, new_issues, resolved, active, high_priority,
        treatments_applied, and areas_scouted.
    """
    today = datetime.utcnow()
    week_ago = (today - timedelta(days=7)).strftime('%Y-%m-%d')
    today_str = today.strftime('%Y-%m-%d')

    with get_db() as conn:
        # New reports this week
        new_reports = conn.execute(
            'SELECT * FROM scouting_reports '
            'WHERE user_id = ? AND scout_date >= ? AND scout_date <= ? '
            'ORDER BY scout_date DESC',
            (user_id, week_ago, today_str),
        ).fetchall()

        # Resolved this week
        resolved = conn.execute(
            "SELECT * FROM scouting_reports "
            "WHERE user_id = ? AND status = 'resolved' AND updated_at >= ? "
            "ORDER BY updated_at DESC",
            (user_id, week_ago),
        ).fetchall()

        # Currently active (non-resolved)
        active = conn.execute(
            "SELECT * FROM scouting_reports "
            "WHERE user_id = ? AND status != 'resolved' "
            "ORDER BY severity DESC",
            (user_id,),
        ).fetchall()

        # High-priority (severity >= 4 and not resolved)
        high_priority = conn.execute(
            "SELECT * FROM scouting_reports "
            "WHERE user_id = ? AND severity >= 4 AND status != 'resolved' "
            "ORDER BY severity DESC, scout_date DESC",
            (user_id,),
        ).fetchall()

    # Build area summary from new reports
    areas_scouted = {}
    treatments_applied = []
    for r in new_reports:
        report = _serialize_report(r)
        area = report['area']
        if area not in areas_scouted:
            areas_scouted[area] = {'count': 0, 'issues': []}
        areas_scouted[area]['count'] += 1
        areas_scouted[area]['issues'].append(report['issue_type'])

        if report.get('treatment_applied'):
            treatments_applied.append({
                'area': area,
                'issue_type': report['issue_type'],
                'treatment': report['treatment_applied'],
                'product': report['treatment_product'],
                'date': report['treatment_date'],
            })

    return {
        'report_period': {
            'start': week_ago,
            'end': today_str,
        },
        'overview': {
            'new_reports': len(new_reports),
            'resolved_count': len(resolved),
            'active_count': len(active),
            'high_priority_count': len(high_priority),
        },
        'new_issues': [_serialize_report(r) for r in new_reports],
        'resolved': [_serialize_report(r) for r in resolved],
        'active': [_serialize_report(r) for r in active],
        'high_priority': [_serialize_report(r) for r in high_priority],
        'treatments_applied': treatments_applied,
        'areas_scouted': areas_scouted,
    }
