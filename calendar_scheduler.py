"""
Calendar & Task Scheduling module for Greenside AI.
Handles maintenance calendars, GDD-triggered events, spray windows,
recurring tasks, and built-in turfgrass management templates.
"""

import json
import logging
from datetime import datetime, timedelta, date

from db import get_db

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_EVENT_TYPES = ['maintenance', 'spray', 'cultural', 'meeting', 'reminder', 'custom']
VALID_AREAS = ['greens', 'fairways', 'tees', 'rough', 'all']
VALID_PRIORITIES = ['low', 'medium', 'high', 'critical']
VALID_RECURRENCES = ['none', 'daily', 'weekly', 'biweekly', 'monthly', 'yearly']
VALID_SEASONS = ['spring', 'summer', 'fall', 'winter', 'year-round']


def _serialize_date(obj):
    """JSON-safe date serializer."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    return obj


def _row_to_dict(row):
    """Convert a database row to a plain dict with JSON-parsed fields."""
    if row is None:
        return None
    d = dict(row)
    for key in ('events_json',):
        if key in d and isinstance(d[key], str):
            try:
                d[key] = json.loads(d[key])
            except (json.JSONDecodeError, TypeError):
                pass
    return d


def _event_row_to_dict(row):
    """Convert an event row, coercing booleans and dates for JSON output."""
    if row is None:
        return None
    d = dict(row)
    for flag in ('all_day', 'completed', 'weather_dependent'):
        if flag in d and d[flag] is not None:
            d[flag] = bool(d[flag])
    return d


# ---------------------------------------------------------------------------
# Table Initialization
# ---------------------------------------------------------------------------

def init_calendar_tables():
    """Create calendar_events and calendar_templates tables.

    Uses SQLite syntax with ? placeholders and INTEGER PRIMARY KEY AUTOINCREMENT;
    the db.py layer auto-converts for PostgreSQL.
    """
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS calendar_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                event_type TEXT NOT NULL DEFAULT 'maintenance',
                area TEXT DEFAULT 'all',
                start_date TEXT NOT NULL,
                end_date TEXT,
                all_day INTEGER DEFAULT 1,
                recurrence TEXT DEFAULT 'none',
                recurrence_end_date TEXT,
                completed INTEGER DEFAULT 0,
                completed_at TEXT,
                priority TEXT DEFAULT 'medium',
                color TEXT,
                linked_spray_id INTEGER,
                linked_equipment_id INTEGER,
                gdd_trigger REAL,
                weather_dependent INTEGER DEFAULT 0,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS calendar_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                name TEXT NOT NULL,
                description TEXT,
                events_json TEXT,
                season TEXT DEFAULT 'year-round',
                region TEXT,
                grass_type TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

    logger.info("Calendar tables initialized")


# ---------------------------------------------------------------------------
# CRUD -- Events
# ---------------------------------------------------------------------------

def create_event(user_id, data):
    """Create a new calendar event.

    Args:
        user_id: Owner user ID.
        data: dict with event fields (title required, rest optional).

    Returns:
        int -- new event ID.
    """
    title = data.get('title')
    if not title:
        raise ValueError("Event title is required")

    event_type = data.get('event_type', 'maintenance')
    if event_type not in VALID_EVENT_TYPES:
        raise ValueError(f"Invalid event_type: {event_type}")

    area = data.get('area', 'all')
    if area not in VALID_AREAS:
        raise ValueError(f"Invalid area: {area}")
    priority = data.get('priority', 'medium')
    if priority not in VALID_PRIORITIES:
        raise ValueError(f"Invalid priority: {priority}")

    recurrence = data.get('recurrence', 'none')
    if recurrence not in VALID_RECURRENCES:
        raise ValueError(f"Invalid recurrence: {recurrence}")

    start_date = data.get('start_date')
    if not start_date:
        raise ValueError("start_date is required")

    now = datetime.utcnow().isoformat()

    with get_db() as conn:
        cursor = conn.execute('''
            INSERT INTO calendar_events (
                user_id, title, description, event_type, area,
                start_date, end_date, all_day, recurrence, recurrence_end_date,
                completed, completed_at, priority, color,
                linked_spray_id, linked_equipment_id,
                gdd_trigger, weather_dependent, notes,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_id,
            title,
            data.get('description'),
            event_type,
            area,
            start_date,
            data.get('end_date'),
            1 if data.get('all_day', True) else 0,
            recurrence,
            data.get('recurrence_end_date'),
            0,
            None,
            priority,
            data.get('color'),
            data.get('linked_spray_id'),
            data.get('linked_equipment_id'),
            data.get('gdd_trigger'),
            1 if data.get('weather_dependent', False) else 0,
            data.get('notes'),
            now,
            now,
        ))
        event_id = cursor.lastrowid

    logger.info(f"Calendar event created: {event_id} '{title}' for user {user_id}")
    return event_id


def update_event(event_id, user_id, data):
    """Update an existing calendar event.

    Only fields present in *data* are updated; others are left unchanged.

    Args:
        event_id: Event to update.
        user_id: Must match event owner.
        data: dict of fields to update.

    Returns:
        bool -- True if a row was updated.
    """
    allowed = {
        'title', 'description', 'event_type', 'area',
        'start_date', 'end_date', 'all_day', 'recurrence', 'recurrence_end_date',
        'priority', 'color', 'linked_spray_id', 'linked_equipment_id',
        'gdd_trigger', 'weather_dependent', 'notes',
    }
    sets = []
    params = []
    for key, value in data.items():
        if key not in allowed:
            continue
        if key == 'event_type' and value not in VALID_EVENT_TYPES:
            raise ValueError(f"Invalid event_type: {value}")
        if key == 'area' and value not in VALID_AREAS:
            raise ValueError(f"Invalid area: {value}")
        if key == 'priority' and value not in VALID_PRIORITIES:
            raise ValueError(f"Invalid priority: {value}")
        if key == 'recurrence' and value not in VALID_RECURRENCES:
            raise ValueError(f"Invalid recurrence: {value}")
        # Coerce booleans to int for SQLite
        if key in ('all_day', 'weather_dependent'):
            value = 1 if value else 0
        sets.append(f"{key} = ?")
        params.append(value)

    if not sets:
        return False

    sets.append("updated_at = ?")
    params.append(datetime.utcnow().isoformat())
    params.extend([event_id, user_id])

    sql = f"UPDATE calendar_events SET {', '.join(sets)} WHERE id = ? AND user_id = ?"
    with get_db() as conn:
        cursor = conn.execute(sql, tuple(params))
        updated = cursor.rowcount > 0

    if updated:
        logger.info(f"Calendar event {event_id} updated by user {user_id}")
    return updated


def delete_event(event_id, user_id):
    """Delete a calendar event (ownership-checked).

    Returns:
        bool -- True if a row was deleted.
    """
    with get_db() as conn:
        cursor = conn.execute(
            'DELETE FROM calendar_events WHERE id = ? AND user_id = ?',
            (event_id, user_id)
        )
        deleted = cursor.rowcount > 0

    if deleted:
        logger.info(f"Calendar event {event_id} deleted by user {user_id}")
    return deleted


def get_events(user_id, start_date, end_date, area=None, event_type=None):
    """Get events in a date range with optional filters.

    Args:
        user_id: Owner.
        start_date: Inclusive start (YYYY-MM-DD string).
        end_date: Inclusive end (YYYY-MM-DD string).
        area: Optional area filter.
        event_type: Optional event-type filter.
    Returns:
        list of event dicts.
    """
    query = '''
        SELECT * FROM calendar_events
        WHERE user_id = ? AND start_date <= ? AND (end_date >= ? OR end_date IS NULL)
    '''
    params = [user_id, end_date, start_date]

    if area and area in VALID_AREAS:
        query += ' AND area = ?'
        params.append(area)

    if event_type and event_type in VALID_EVENT_TYPES:
        query += ' AND event_type = ?'
        params.append(event_type)

    query += ' ORDER BY start_date ASC'

    with get_db() as conn:
        cursor = conn.execute(query, tuple(params))
        rows = cursor.fetchall()

    return [_event_row_to_dict(r) for r in rows]


def get_event_by_id(event_id, user_id):
    """Get a single event by ID (ownership-checked).

    Returns:
        dict or None.
    """
    with get_db() as conn:
        cursor = conn.execute(
            'SELECT * FROM calendar_events WHERE id = ? AND user_id = ?',
            (event_id, user_id)
        )
        row = cursor.fetchone()

    return _event_row_to_dict(row)


def complete_event(event_id, user_id):
    """Mark an event as completed with a timestamp.

    Returns:
        bool -- True if updated.
    """
    now = datetime.utcnow().isoformat()
    with get_db() as conn:
        cursor = conn.execute('''
            UPDATE calendar_events
            SET completed = 1, completed_at = ?, updated_at = ?
            WHERE id = ? AND user_id = ? AND completed = 0
        ''', (now, now, event_id, user_id))
        updated = cursor.rowcount > 0

    if updated:
        logger.info(f"Calendar event {event_id} completed by user {user_id}")
    return updated


def get_upcoming_events(user_id, days=7):
    """Get events in the next N days that are not yet completed.

    Args:
        user_id: Owner.
        days: Lookahead window (default 7).

    Returns:
        list of event dicts.
    """
    today = date.today().isoformat()
    future = (date.today() + timedelta(days=days)).isoformat()

    with get_db() as conn:
        cursor = conn.execute('''
            SELECT * FROM calendar_events
            WHERE user_id = ?
              AND completed = 0
              AND start_date >= ?
              AND start_date <= ?
            ORDER BY start_date ASC
        ''', (user_id, today, future))
        rows = cursor.fetchall()

    return [_event_row_to_dict(r) for r in rows]


def get_overdue_events(user_id):
    """Get past events that have not been completed.

    Returns:
        list of event dicts ordered oldest first.
    """
    today = date.today().isoformat()

    with get_db() as conn:
        cursor = conn.execute('''
            SELECT * FROM calendar_events
            WHERE user_id = ?
              AND completed = 0
              AND start_date < ?
            ORDER BY start_date ASC
        ''', (user_id, today))
        rows = cursor.fetchall()

    return [_event_row_to_dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

def get_calendar_templates(user_id):
    """List all calendar templates owned by a user.

    Returns:
        list of template dicts.
    """
    with get_db() as conn:
        cursor = conn.execute(
            'SELECT * FROM calendar_templates WHERE user_id = ? ORDER BY name',
            (user_id,)
        )
        rows = cursor.fetchall()

    return [_row_to_dict(r) for r in rows]


def save_calendar_template(user_id, data):
    """Save a new calendar template.

    Args:
        user_id: Owner.
        data: dict with name, description, events_json (list), season, region, grass_type.
    Returns:
        int -- new template ID.
    """
    name = data.get('name')
    if not name:
        raise ValueError("Template name is required")

    events_json = data.get('events_json', [])
    if isinstance(events_json, (list, dict)):
        events_json = json.dumps(events_json, default=_serialize_date)

    season = data.get('season', 'year-round')
    if season not in VALID_SEASONS:
        raise ValueError(f"Invalid season: {season}")

    with get_db() as conn:
        cursor = conn.execute('''
            INSERT INTO calendar_templates (
                user_id, name, description, events_json,
                season, region, grass_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_id,
            name,
            data.get('description'),
            events_json,
            season,
            data.get('region'),
            data.get('grass_type'),
        ))
        template_id = cursor.lastrowid

    logger.info(f"Calendar template saved: {template_id} '{name}' for user {user_id}")
    return template_id


def apply_template(user_id, template_id, start_date):
    """Apply a calendar template, creating events relative to *start_date*.

    Each event in the template's events_json must have at least:
        - title
        - day_offset (int): days from start_date
    Optionally: end_day_offset, event_type, area, priority, recurrence, etc.

    Args:
        user_id: Owner.
        template_id: Template to apply.
        start_date: Reference date (YYYY-MM-DD string).

    Returns:
        list of created event IDs.
    """
    # Fetch template -- could be user-owned or built-in (user_id IS NULL)
    with get_db() as conn:
        cursor = conn.execute(
            'SELECT * FROM calendar_templates WHERE id = ? AND (user_id = ? OR user_id IS NULL)',
            (template_id, user_id)
        )
        row = cursor.fetchone()
    if not row:
        raise ValueError(f"Template {template_id} not found")

    template = _row_to_dict(row)
    events_def = template.get('events_json', [])
    if isinstance(events_def, str):
        events_def = json.loads(events_def)

    try:
        base = datetime.strptime(start_date, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        raise ValueError(f"Invalid start_date format: {start_date}. Expected YYYY-MM-DD.")

    created_ids = []
    for ev in events_def:
        offset_days = ev.get('day_offset', 0)
        ev_start = (base + timedelta(days=offset_days)).isoformat()
        end_offset = ev.get('end_day_offset')
        ev_end = (base + timedelta(days=end_offset)).isoformat() if end_offset is not None else None

        event_data = {
            'title': ev.get('title', 'Untitled'),
            'description': ev.get('description'),
            'event_type': ev.get('event_type', 'maintenance'),
            'area': ev.get('area', 'all'),
            'start_date': ev_start,
            'end_date': ev_end,
            'all_day': ev.get('all_day', True),
            'recurrence': ev.get('recurrence', 'none'),
            'recurrence_end_date': ev.get('recurrence_end_date'),
            'priority': ev.get('priority', 'medium'),
            'color': ev.get('color'),
            'gdd_trigger': ev.get('gdd_trigger'),
            'weather_dependent': ev.get('weather_dependent', False),
            'notes': ev.get('notes'),
        }
        eid = create_event(user_id, event_data)
        created_ids.append(eid)

    logger.info(
        f"Template {template_id} applied for user {user_id}: "
        f"{len(created_ids)} events created starting {start_date}"
    )
    return created_ids


# ---------------------------------------------------------------------------
# Built-in Templates
# ---------------------------------------------------------------------------

def get_builtin_templates():
    """Return hardcoded maintenance program templates.

    These are not stored in the DB -- they are returned as dicts so the
    frontend can display them and the user can apply them via apply_template()
    after they have been inserted into calendar_templates with user_id=NULL.

    Returns:
        list of template dicts.
    """
    return [
        {
            'id': 'builtin_cool_season',
            'name': 'Cool-Season Annual Program',
            'description': (
                'Full-year maintenance calendar for bentgrass and bluegrass '
                'in the Northeast and Transition Zone. Covers fertilization, '
                'fungicide rotations, PGR, and cultural practices.'
            ),
            'season': 'year-round',
            'region': 'Northeast / Transition Zone',
            'grass_type': 'Bentgrass / Kentucky Bluegrass',
            'events_json': [
                # --- Early Spring (March) ---
                {'day_offset': 0, 'title': 'Early spring soil test',
                 'event_type': 'maintenance', 'area': 'all', 'priority': 'high',
                 'description': 'Pull soil cores from greens, fairways, tees. Send to lab.'},
                {'day_offset': 14, 'title': 'Pre-emergent herbicide app #1 (Prodiamine)',
                 'event_type': 'spray', 'area': 'fairways', 'priority': 'critical',
                 'description': 'Apply prodiamine 0.65 oz ai/A when 5-day avg soil temp hits 50-55F.',
                 'weather_dependent': True, 'gdd_trigger': 150.0},
                {'day_offset': 14, 'title': 'Pre-emergent herbicide app #1 (Prodiamine)',
                 'event_type': 'spray', 'area': 'tees', 'priority': 'critical',
                 'description': 'Apply prodiamine 0.65 oz ai/A when 5-day avg soil temp hits 50-55F.',
                 'weather_dependent': True, 'gdd_trigger': 150.0},
                {'day_offset': 21, 'title': 'First fertilizer app -- light N',
                 'event_type': 'spray', 'area': 'greens', 'priority': 'high',
                 'description': '0.25 lb N/1000 sq ft spoon-feed.'},
                # --- Spring (April) ---
                {'day_offset': 30, 'title': 'Spring core aeration -- greens',
                 'event_type': 'cultural', 'area': 'greens', 'priority': 'high',
                 'description': '5/8" tines, 2x2 spacing. Follow with heavy topdress.'},
                {'day_offset': 35, 'title': 'Topdress greens post-aeration',
                 'event_type': 'cultural', 'area': 'greens', 'priority': 'high',
                 'description': 'USGA-spec sand, work into holes. Drag mat.'},
                {'day_offset': 42, 'title': 'PGR -- Primo Maxx cycle start',
                 'event_type': 'spray', 'area': 'greens', 'priority': 'medium',
                 'recurrence': 'biweekly',
                 'description': 'Trinexapac-ethyl 0.125 oz/1000 sq ft. 14-day reapply via GDD.',
                 'gdd_trigger': 200.0},
                # --- Late Spring (May) ---
                {'day_offset': 60, 'title': 'Dollar spot preventive -- first rotation',
                 'event_type': 'spray', 'area': 'greens', 'priority': 'high',
                 'description': 'Chlorothalonil or propiconazole at label rate.',
                 'weather_dependent': True},
                {'day_offset': 60, 'title': 'Fertilizer -- fairways granular',
                 'event_type': 'spray', 'area': 'fairways', 'priority': 'medium',
                 'description': '1 lb N/1000 sq ft slow-release (MESA or polymer-coated urea).'},
                # --- Summer (June-August) ---
                {'day_offset': 90, 'title': 'Brown patch / Pythium watch',
                 'event_type': 'spray', 'area': 'greens', 'priority': 'critical',
                 'description': 'Azoxystrobin + mefenoxam rotation. Night temps > 65F trigger.',
                 'weather_dependent': True},
                {'day_offset': 105, 'title': 'Topdress greens -- light',
                 'event_type': 'cultural', 'area': 'greens', 'priority': 'medium',
                 'recurrence': 'biweekly',
                 'description': 'Light sand topdress every 2 weeks through summer.'},
                {'day_offset': 120, 'title': 'Mid-summer foliar feed -- greens',
                 'event_type': 'spray', 'area': 'greens', 'priority': 'medium',
                 'description': '0.1 lb N/1000 sq ft foliar + chelated Fe + Mn.'},
                {'day_offset': 150, 'title': 'Summer stress -- raise HOC, reduce N',
                 'event_type': 'reminder', 'area': 'greens', 'priority': 'high',
                 'description': 'Raise height of cut 0.010". Reduce N inputs. Syringe as needed.'},
                # --- Fall (September) ---
                {'day_offset': 180, 'title': 'Fall core aeration -- greens',
                 'event_type': 'cultural', 'area': 'greens', 'priority': 'high',
                 'description': '1/2" tines. Primary recovery aeration. Heavy topdress.'},
                {'day_offset': 180, 'title': 'Fall core aeration -- fairways',
                 'event_type': 'cultural', 'area': 'fairways', 'priority': 'high',
                 'description': '3/4" tines. Deep-tine if compaction present.'},
                {'day_offset': 185, 'title': 'Overseed tees and thin fairway areas',
                 'event_type': 'cultural', 'area': 'tees', 'priority': 'medium',
                 'description': 'Perennial ryegrass or bluegrass blend at 3-5 lb/1000 sq ft.'},
                {'day_offset': 195, 'title': 'Fall fertilizer -- heavy N push',
                 'event_type': 'spray', 'area': 'fairways', 'priority': 'high',
                 'description': '1-1.5 lb N/1000 sq ft. Drives fall root growth and carb storage.'},
                # --- Late Fall (October-November) ---
                {'day_offset': 225, 'title': 'Snow mold preventive (if applicable)',
                 'event_type': 'spray', 'area': 'greens', 'priority': 'high',
                 'description': 'Chlorothalonil + propiconazole tank mix before dormancy.',
                 'weather_dependent': True},
                {'day_offset': 240, 'title': 'Winterizer fertilizer -- greens/tees',
                 'event_type': 'spray', 'area': 'greens', 'priority': 'medium',
                 'description': '0.5 lb N/1000 sq ft. Last app before freeze-up.'},
                {'day_offset': 250, 'title': 'End-of-season equipment winterization',
                 'event_type': 'maintenance', 'area': 'all', 'priority': 'medium',
                 'description': 'Drain sprayers, sharpen reels, winterize irrigation.'},
            ],
        },
        {
            'id': 'builtin_warm_season',
            'name': 'Warm-Season Annual Program',
            'description': (
                'Full-year maintenance calendar for bermudagrass and zoysiagrass '
                'in the Southeast and Southwest. Covers fertility, weed control, '
                'scalping, and cultural practices.'
            ),
            'season': 'year-round',
            'region': 'Southeast / Southwest',
            'grass_type': 'Bermudagrass / Zoysiagrass',
            'events_json': [
                # --- Late Winter (February) ---
                {'day_offset': 0, 'title': 'Pre-emergent #1 -- prodiamine',
                 'event_type': 'spray', 'area': 'fairways', 'priority': 'critical',
                 'description': 'Split app prodiamine when soil temps approach 55F.',
                 'weather_dependent': True, 'gdd_trigger': 100.0},
                # --- Spring Green-up (March-April) ---
                {'day_offset': 30, 'title': 'Scalp bermuda -- remove dormant thatch',
                 'event_type': 'cultural', 'area': 'fairways', 'priority': 'high',
                 'description': 'Lower HOC to remove dormant top growth. Bag clippings.'},
                {'day_offset': 30, 'title': 'Scalp bermuda -- tees',
                 'event_type': 'cultural', 'area': 'tees', 'priority': 'high',
                 'description': 'Lower HOC to remove dormant top growth.'},
                {'day_offset': 45, 'title': 'Pre-emergent #2 -- split application',
                 'event_type': 'spray', 'area': 'fairways', 'priority': 'critical',
                 'description': 'Second split of prodiamine 60-90 days after first.',
                 'gdd_trigger': 350.0},
                {'day_offset': 45, 'title': 'First N application -- green-up',
                 'event_type': 'spray', 'area': 'greens', 'priority': 'high',
                 'description': '0.5 lb N/1000 sq ft soluble after full green-up.'},
                # --- Spring (May) ---
                {'day_offset': 75, 'title': 'Spring verticutting -- greens',
                 'event_type': 'cultural', 'area': 'greens', 'priority': 'high',
                 'description': 'Verticut in 2 directions. Topdress and roll.'},
                {'day_offset': 75, 'title': 'PGR -- Primo Maxx cycle start',
                 'event_type': 'spray', 'area': 'greens', 'priority': 'medium',
                 'recurrence': 'biweekly',
                 'description': 'Trinexapac-ethyl 0.125 oz/1000. Track GDD for reapply.',
                 'gdd_trigger': 200.0},
                # --- Summer (June-August) ---
                {'day_offset': 105, 'title': 'Summer fertility -- spoon-feed N',
                 'event_type': 'spray', 'area': 'greens', 'priority': 'medium',
                 'recurrence': 'biweekly',
                 'description': '0.1-0.2 lb N/1000 sq ft foliar every 2 weeks.'},
                {'day_offset': 120, 'title': 'Summer fertility -- fairways granular',
                 'event_type': 'spray', 'area': 'fairways', 'priority': 'medium',
                 'description': '1 lb N/1000 sq ft slow-release.'},
                {'day_offset': 135, 'title': 'Dollar spot / brown patch fungicide rotation',
                 'event_type': 'spray', 'area': 'greens', 'priority': 'high',
                 'description': 'Rotate MOA: DMI, SDHI, strobilurin. 14-21 day interval.',
                 'weather_dependent': True},
                {'day_offset': 150, 'title': 'Core aeration -- greens (summer)',
                 'event_type': 'cultural', 'area': 'greens', 'priority': 'high',
                 'description': 'Bayonet or small tine. Bermuda recovers fast in heat.'},
                {'day_offset': 165, 'title': 'Topdress greens -- mid-summer',
                 'event_type': 'cultural', 'area': 'greens', 'priority': 'medium',
                 'description': 'Light sand application. Drag and irrigate.'},
                # --- Fall (September-October) ---
                {'day_offset': 210, 'title': 'Fall pre-emergent for winter annuals (Poa annua)',
                 'event_type': 'spray', 'area': 'fairways', 'priority': 'critical',
                 'description': 'Prodiamine or dithiopyr before soil temps drop below 70F.',
                 'weather_dependent': True},
                {'day_offset': 225, 'title': 'Last fertilizer before dormancy',
                 'event_type': 'spray', 'area': 'fairways', 'priority': 'medium',
                 'description': '0.5 lb N/1000 sq ft + potassium for winter hardiness.'},
                {'day_offset': 240, 'title': 'Overseed with ryegrass (optional)',
                 'event_type': 'cultural', 'area': 'fairways', 'priority': 'low',
                 'description': 'Perennial ryegrass 8-10 lb/1000 for winter color.'},
                # --- Winter ---
                {'day_offset': 300, 'title': 'Winter cultural -- avoid traffic on dormant turf',
                 'event_type': 'reminder', 'area': 'all', 'priority': 'low',
                 'description': 'Minimize equipment traffic. Repair divots. Plan next season.'},
            ],
        },
        {
            'id': 'builtin_preemergent',
            'name': 'Pre-Emergent Schedule',
            'description': (
                'Prodiamine and dithiopyr timing by region. '
                'Split applications for season-long crabgrass and goosegrass control.'
            ),
            'season': 'spring',
            'region': 'All regions (adjust by soil temp)',
            'grass_type': 'All',
            'events_json': [
                # Northeast / Transition Zone
                {'day_offset': 0, 'title': 'Pre-emergent #1 -- Northeast/Transition',
                 'event_type': 'spray', 'area': 'fairways', 'priority': 'critical',
                 'description': 'Prodiamine 65 WDG at 0.65 oz ai/A. Soil temp 50-55F.',
                 'gdd_trigger': 150.0, 'weather_dependent': True,
                 'notes': 'Forsythia bloom = crabgrass germination approaching.'},
                {'day_offset': 60, 'title': 'Pre-emergent #2 -- Northeast/Transition',
                 'event_type': 'spray', 'area': 'fairways', 'priority': 'high',
                 'description': 'Dithiopyr (Dimension) at label rate. Covers late germinators.',
                 'gdd_trigger': 500.0, 'weather_dependent': True},
                # Southeast
                {'day_offset': -30, 'title': 'Pre-emergent #1 -- Southeast',
                 'event_type': 'spray', 'area': 'fairways', 'priority': 'critical',
                 'description': 'Prodiamine early (Feb). Soil temps hit 50F earlier in south.',
                 'gdd_trigger': 100.0, 'weather_dependent': True},
                {'day_offset': 30, 'title': 'Pre-emergent #2 -- Southeast',
                 'event_type': 'spray', 'area': 'fairways', 'priority': 'high',
                 'description': 'Dithiopyr split app 60-90 days later.',
                 'gdd_trigger': 400.0, 'weather_dependent': True},
                # Fall pre-emergent (Poa annua)
                {'day_offset': 180, 'title': 'Fall pre-emergent -- Poa annua (all regions)',
                 'event_type': 'spray', 'area': 'fairways', 'priority': 'high',
                 'description': 'Prodiamine or dithiopyr when soil temp drops below 70F.',
                 'weather_dependent': True,
                 'notes': 'Critical for warm-season turf. 4-week window.'},
            ],
        },
        {
            'id': 'builtin_aerification',
            'name': 'Aerification & Topdressing',
            'description': (
                'Spring and fall core aeration plus regular topdressing program '
                'for greens, tees, and fairways.'
            ),
            'season': 'year-round',
            'region': 'All',
            'grass_type': 'All',
            'events_json': [
                # --- Spring Aeration ---
                {'day_offset': 0, 'title': 'Spring core aeration -- greens',
                 'event_type': 'cultural', 'area': 'greens', 'priority': 'high',
                 'description': '5/8" hollow tines, 2x2 spacing. Heavy topdress after.'},
                {'day_offset': 1, 'title': 'Spring topdress -- greens (post-aeration)',
                 'event_type': 'cultural', 'area': 'greens', 'priority': 'high',
                 'description': 'USGA-spec sand. Fill holes, drag, irrigate.'},
                {'day_offset': 7, 'title': 'Spring core aeration -- tees',
                 'event_type': 'cultural', 'area': 'tees', 'priority': 'medium',
                 'description': '3/4" tines. Overseed thin areas after.'},
                {'day_offset': 14, 'title': 'Spring core aeration -- fairways',
                 'event_type': 'cultural', 'area': 'fairways', 'priority': 'medium',
                 'description': '3/4" tines. Deep-tine compacted areas.'},
                # --- Regular Topdressing (summer) ---
                {'day_offset': 30, 'title': 'Light topdress -- greens (bi-weekly start)',
                 'event_type': 'cultural', 'area': 'greens', 'priority': 'medium',
                 'recurrence': 'biweekly',
                 'description': 'Light sand application, brush in. Manage thatch.'},
                # --- Fall Aeration ---
                {'day_offset': 150, 'title': 'Fall core aeration -- greens',
                 'event_type': 'cultural', 'area': 'greens', 'priority': 'high',
                 'description': 'Primary recovery aeration. Heavy topdress. Seed thin spots.'},
                {'day_offset': 151, 'title': 'Fall topdress -- greens (post-aeration)',
                 'event_type': 'cultural', 'area': 'greens', 'priority': 'high',
                 'description': 'Heavy topdress into aeration holes. Mat in.'},
                {'day_offset': 157, 'title': 'Fall core aeration -- tees',
                 'event_type': 'cultural', 'area': 'tees', 'priority': 'medium',
                 'description': '3/4" tines. Overseed.'},
                {'day_offset': 164, 'title': 'Fall core aeration -- fairways',
                 'event_type': 'cultural', 'area': 'fairways', 'priority': 'medium',
                 'description': '3/4" tines. Deep-tine traffic areas.'},
                {'day_offset': 170, 'title': 'Fall deep-tine aeration -- greens (optional)',
                 'event_type': 'cultural', 'area': 'greens', 'priority': 'low',
                 'description': 'Solid tines, 8-10" depth. Address deep compaction.'},
            ],
        },
        {
            'id': 'builtin_pgr',
            'name': 'PGR Program',
            'description': (
                'Primo Maxx (trinexapac-ethyl) 14-day cycle with GDD tracking. '
                'Greens application from spring green-up through late fall.'
            ),
            'season': 'year-round',
            'region': 'All',
            'grass_type': 'All managed turf',
            'events_json': [
                {'day_offset': 0, 'title': 'PGR -- Primo Maxx app #1 (season start)',
                 'event_type': 'spray', 'area': 'greens', 'priority': 'high',
                 'description': (
                     'Trinexapac-ethyl at 0.125 fl oz/1000 sq ft. Begin when turf '
                     'is actively growing. Track GDD base-32 for reapplication.'
                 ),
                 'gdd_trigger': 200.0, 'weather_dependent': True},
                {'day_offset': 14, 'title': 'PGR -- Primo Maxx app #2',
                 'event_type': 'spray', 'area': 'greens', 'priority': 'high',
                 'description': 'Reapply at 200 GDD (base 32F) or 14 days.',
                 'gdd_trigger': 200.0},
                {'day_offset': 28, 'title': 'PGR -- Primo Maxx app #3',
                 'event_type': 'spray', 'area': 'greens', 'priority': 'high',
                 'description': 'Continue 14-day / 200 GDD cycle.',
                 'gdd_trigger': 200.0},
                {'day_offset': 42, 'title': 'PGR -- Primo Maxx app #4',
                 'event_type': 'spray', 'area': 'greens', 'priority': 'high',
                 'description': 'Maintain cycle. Reduce rate in heat stress (>90F).',
                 'gdd_trigger': 200.0, 'weather_dependent': True},
                {'day_offset': 56, 'title': 'PGR -- Primo Maxx app #5',
                 'event_type': 'spray', 'area': 'greens', 'priority': 'high',
                 'description': 'Continue cycle. Consider adding Fe for color.',
                 'gdd_trigger': 200.0},
                {'day_offset': 70, 'title': 'PGR -- Primo Maxx app #6',
                 'event_type': 'spray', 'area': 'greens', 'priority': 'high',
                 'description': 'Continue cycle.',
                 'gdd_trigger': 200.0},
                {'day_offset': 84, 'title': 'PGR -- Primo Maxx app #7',
                 'event_type': 'spray', 'area': 'greens', 'priority': 'medium',
                 'description': 'Mid-season check -- adjust rate for growth response.',
                 'gdd_trigger': 200.0},
                {'day_offset': 98, 'title': 'PGR -- Primo Maxx app #8',
                 'event_type': 'spray', 'area': 'greens', 'priority': 'medium',
                 'description': 'Continue cycle.',
                 'gdd_trigger': 200.0},
                {'day_offset': 112, 'title': 'PGR -- Primo Maxx app #9',
                 'event_type': 'spray', 'area': 'greens', 'priority': 'medium',
                 'description': 'Late-season -- may widen interval if growth slows.',
                 'gdd_trigger': 200.0},
                {'day_offset': 126, 'title': 'PGR -- Primo Maxx app #10',
                 'event_type': 'spray', 'area': 'greens', 'priority': 'medium',
                 'description': 'Continue or taper. Monitor GDD accumulation.',
                 'gdd_trigger': 200.0},
                {'day_offset': 140, 'title': 'PGR -- Primo Maxx app #11',
                 'event_type': 'spray', 'area': 'greens', 'priority': 'low',
                 'description': 'Taper as growth slows. Last app ~4 weeks before dormancy.',
                 'gdd_trigger': 200.0},
                {'day_offset': 154, 'title': 'PGR season wrap-up assessment',
                 'event_type': 'reminder', 'area': 'greens', 'priority': 'low',
                 'description': (
                     'Review season GDD log. Note total apps and rate adjustments '
                     'for next year planning.'
                 )},
            ],
        },
    ]


def install_builtin_templates():
    """Insert built-in templates into the database with user_id=NULL so any user
    can apply them. Safe to call multiple times (skips if name already exists).

    Returns:
        int -- number of templates inserted.
    """
    builtins = get_builtin_templates()
    inserted = 0

    with get_db() as conn:
        for tmpl in builtins:
            # Check if already exists
            cursor = conn.execute(
                'SELECT id FROM calendar_templates WHERE name = ? AND user_id IS NULL',
                (tmpl['name'],)
            )
            if cursor.fetchone():
                continue

            events_json = json.dumps(tmpl['events_json'], default=_serialize_date)
            conn.execute('''
                INSERT INTO calendar_templates (
                    user_id, name, description, events_json,
                    season, region, grass_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                None,
                tmpl['name'],
                tmpl['description'],
                events_json,
                tmpl['season'],
                tmpl.get('region'),
                tmpl.get('grass_type'),
            ))
            inserted += 1

    logger.info(f"Installed {inserted} built-in calendar templates")
    return inserted


# ---------------------------------------------------------------------------
# GDD / Weather Integration
# ---------------------------------------------------------------------------

def check_gdd_triggers(user_id, current_gdd):
    """Check which upcoming events should trigger based on accumulated GDD.

    Scans incomplete events that have a gdd_trigger value. Returns events
    whose threshold has been met or exceeded by *current_gdd*.

    Args:
        user_id: Owner.
        current_gdd: Current growing degree day accumulation (float).

    Returns:
        list of event dicts that are triggered.
    """
    if current_gdd is None:
        return []

    with get_db() as conn:
        cursor = conn.execute('''
            SELECT * FROM calendar_events
            WHERE user_id = ?
              AND completed = 0
              AND gdd_trigger IS NOT NULL
              AND gdd_trigger <= ?
            ORDER BY gdd_trigger ASC
        ''', (user_id, current_gdd))
        rows = cursor.fetchall()

    triggered = [_event_row_to_dict(r) for r in rows]
    if triggered:
        logger.info(
            f"GDD trigger check for user {user_id}: "
            f"{len(triggered)} events triggered at GDD={current_gdd}"
        )
    return triggered


def get_spray_window_events(user_id, weather_data):
    """Filter upcoming weather-dependent spray events by weather suitability.

    Checks wind, rain probability, and temperature against reasonable
    spray windows.

    Args:
        user_id: Owner.
        weather_data: dict with keys:
            - wind_mph (float): current or forecast wind speed
            - rain_chance (float): 0-100 probability of rain
            - temp_f (float): temperature in Fahrenheit
            - max_wind_mph (float, optional): threshold, default 10
            - max_rain_chance (float, optional): threshold, default 40
            - min_temp_f (float, optional): threshold, default 40
            - max_temp_f (float, optional): threshold, default 95

    Returns:
        dict with 'suitable' and 'unsuitable' lists of event dicts,
        each annotated with a 'weather_reason' field.
    """
    # Thresholds
    max_wind = weather_data.get('max_wind_mph', 10.0)
    max_rain = weather_data.get('max_rain_chance', 40.0)
    min_temp = weather_data.get('min_temp_f', 40.0)
    max_temp = weather_data.get('max_temp_f', 95.0)

    wind = weather_data.get('wind_mph', 0)
    rain_chance = weather_data.get('rain_chance', 0)
    temp = weather_data.get('temp_f', 70)

    # Get upcoming incomplete weather-dependent events
    today = date.today().isoformat()
    future = (date.today() + timedelta(days=3)).isoformat()

    with get_db() as conn:
        cursor = conn.execute('''
            SELECT * FROM calendar_events
            WHERE user_id = ?
              AND completed = 0
              AND weather_dependent = 1
              AND start_date >= ?
              AND start_date <= ?
            ORDER BY start_date ASC
        ''', (user_id, today, future))
        rows = cursor.fetchall()

    suitable = []
    unsuitable = []

    for row in rows:
        event = _event_row_to_dict(row)
        reasons = []

        if wind > max_wind:
            reasons.append(f"Wind too high ({wind} mph, max {max_wind})")
        if rain_chance > max_rain:
            reasons.append(f"Rain probability too high ({rain_chance}%, max {max_rain}%)")
        if temp < min_temp:
            reasons.append(f"Temperature too low ({temp}F, min {min_temp}F)")
        if temp > max_temp:
            reasons.append(f"Temperature too high ({temp}F, max {max_temp}F)")

        if reasons:
            event['weather_reason'] = '; '.join(reasons)
            event['spray_window_ok'] = False
            unsuitable.append(event)
        else:
            event['weather_reason'] = 'Conditions suitable'
            event['spray_window_ok'] = True
            suitable.append(event)

    return {
        'suitable': suitable,
        'unsuitable': unsuitable,
        'weather_summary': {
            'wind_mph': wind,
            'rain_chance': rain_chance,
            'temp_f': temp,
        },
    }