"""
Equipment and Fleet Management module for Greenside AI.
Handles equipment inventory, maintenance tracking, hour logging,
calibration records, and fleet analytics for turfgrass operations.
"""

import json
import logging
from datetime import datetime, timedelta

from db import get_db, add_column

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_EQUIPMENT_TYPES = [
    'mower_reel', 'mower_rotary', 'sprayer', 'aerifier', 'topdresser',
    'utility_vehicle', 'roller', 'verticutter', 'blower', 'chainsaw', 'other'
]

VALID_STATUSES = ['active', 'maintenance', 'repair', 'retired']

VALID_AREAS = ['greens', 'fairways', 'tees', 'rough', 'all']

VALID_FUEL_TYPES = ['gas', 'diesel', 'electric', 'manual']

VALID_MAINTENANCE_TYPES = ['routine', 'repair', 'inspection', 'calibration']

VALID_CALIBRATION_TYPES = ['sprayer_output', 'mower_hoc', 'spreader_rate', 'other']

VALID_PRIORITIES = ['low', 'medium', 'high']


# ---------------------------------------------------------------------------
# Table initialization
# ---------------------------------------------------------------------------

def init_equipment_tables():
    """Initialize all equipment management tables. Safe to call multiple times."""
    with get_db() as conn:
        cursor = conn.cursor()

        # Equipment inventory
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS equipment (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                equipment_type TEXT NOT NULL DEFAULT 'other',
                make TEXT,
                model TEXT,
                year INTEGER,
                serial_number TEXT,
                purchase_date TEXT,
                purchase_price REAL,
                current_hours REAL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'active',
                area_assigned TEXT DEFAULT 'all',
                fuel_type TEXT DEFAULT 'gas',
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Maintenance logs
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS maintenance_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                equipment_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                maintenance_type TEXT NOT NULL DEFAULT 'routine',
                description TEXT,
                parts_used TEXT,
                parts_cost REAL DEFAULT 0,
                labor_hours REAL DEFAULT 0,
                labor_cost REAL DEFAULT 0,
                performed_by TEXT,
                performed_date TEXT NOT NULL,
                next_due_date TEXT,
                next_due_hours REAL,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (equipment_id) REFERENCES equipment (id)
            )
        ''')

        # Equipment hours log
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS equipment_hours (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                equipment_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                hours_used REAL NOT NULL,
                area TEXT,
                operator TEXT,
                fuel_added REAL,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (equipment_id) REFERENCES equipment (id)
            )
        ''')

        # Calibration records
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS calibration_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                equipment_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                calibration_date TEXT NOT NULL,
                calibration_type TEXT NOT NULL DEFAULT 'other',
                settings_json TEXT,
                results_json TEXT,
                pass_fail TEXT,
                technician TEXT,
                next_calibration_date TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (equipment_id) REFERENCES equipment (id)
            )
        ''')

        # Maintenance schedules (recurring tasks)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS maintenance_schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                equipment_id INTEGER NOT NULL,
                task_description TEXT NOT NULL,
                interval_hours REAL,
                interval_days INTEGER,
                last_completed TEXT,
                next_due_hours REAL,
                next_due_date TEXT,
                priority TEXT NOT NULL DEFAULT 'medium',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (equipment_id) REFERENCES equipment (id)
            )
        ''')

    logger.info("Equipment management tables initialized")


# ---------------------------------------------------------------------------
# Equipment CRUD
# ---------------------------------------------------------------------------

def add_equipment(user_id, data):
    """Add a new piece of equipment. Returns the new equipment ID.

    Args:
        user_id: Owner user ID.
        data: dict with keys matching the equipment table columns.

    Returns:
        int: New equipment row ID.
    """
    equipment_type = data.get('equipment_type', 'other')
    if equipment_type not in VALID_EQUIPMENT_TYPES:
        equipment_type = 'other'

    status = data.get('status', 'active')
    if status not in VALID_STATUSES:
        status = 'active'

    area_assigned = data.get('area_assigned', 'all')
    if area_assigned not in VALID_AREAS:
        area_assigned = 'all'

    fuel_type = data.get('fuel_type', 'gas')
    if fuel_type not in VALID_FUEL_TYPES:
        fuel_type = 'gas'

    with get_db() as conn:
        cursor = conn.execute('''
            INSERT INTO equipment (
                user_id, name, equipment_type, make, model, year,
                serial_number, purchase_date, purchase_price,
                current_hours, status, area_assigned, fuel_type, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_id,
            data['name'],
            equipment_type,
            data.get('make'),
            data.get('model'),
            data.get('year'),
            data.get('serial_number'),
            data.get('purchase_date'),
            data.get('purchase_price'),
            data.get('current_hours', 0),
            status,
            area_assigned,
            fuel_type,
            data.get('notes')
        ))
        equip_id = cursor.lastrowid

    logger.info(f"Equipment added: id={equip_id} name={data['name']} user={user_id}")
    return equip_id


def update_equipment(equip_id, user_id, data):
    """Update equipment details. Only updates fields present in data.

    Args:
        equip_id: Equipment ID to update.
        user_id: Owner user ID (ownership check).
        data: dict of fields to update.

    Returns:
        bool: True if the row was updated.
    """
    allowed_fields = [
        'name', 'equipment_type', 'make', 'model', 'year',
        'serial_number', 'purchase_date', 'purchase_price',
        'current_hours', 'status', 'area_assigned', 'fuel_type', 'notes'
    ]

    # Validate enum fields if present
    if 'equipment_type' in data and data['equipment_type'] not in VALID_EQUIPMENT_TYPES:
        data['equipment_type'] = 'other'
    if 'status' in data and data['status'] not in VALID_STATUSES:
        data['status'] = 'active'
    if 'area_assigned' in data and data['area_assigned'] not in VALID_AREAS:
        data['area_assigned'] = 'all'
    if 'fuel_type' in data and data['fuel_type'] not in VALID_FUEL_TYPES:
        data['fuel_type'] = 'gas'

    set_clauses = []
    params = []
    for field in allowed_fields:
        if field in data:
            set_clauses.append(f'{field} = ?')
            params.append(data[field])

    if not set_clauses:
        return False

    set_clauses.append('updated_at = CURRENT_TIMESTAMP')
    params.extend([equip_id, user_id])

    query = f"UPDATE equipment SET {', '.join(set_clauses)} WHERE id = ? AND user_id = ?"

    with get_db() as conn:
        cursor = conn.execute(query, params)
        updated = cursor.rowcount > 0

    if updated:
        logger.info(f"Equipment updated: id={equip_id} user={user_id}")
    return updated


def retire_equipment(equip_id, user_id):
    """Mark equipment as retired.

    Args:
        equip_id: Equipment ID.
        user_id: Owner user ID.

    Returns:
        bool: True if the status was changed.
    """
    with get_db() as conn:
        cursor = conn.execute(
            "UPDATE equipment SET status = 'retired', updated_at = CURRENT_TIMESTAMP "
            "WHERE id = ? AND user_id = ?",
            (equip_id, user_id)
        )
        retired = cursor.rowcount > 0

    if retired:
        logger.info(f"Equipment retired: id={equip_id} user={user_id}")
    return retired


def delete_equipment(equip_id, user_id):
    """Permanently delete equipment and all related records.

    Args:
        equip_id: Equipment ID.
        user_id: Owner user ID.

    Returns:
        bool: True if the equipment was deleted.
    """
    with get_db() as conn:
        # Verify ownership first
        row = conn.execute(
            "SELECT id FROM equipment WHERE id = ? AND user_id = ?",
            (equip_id, user_id)
        ).fetchone()
        if not row:
            return False

        # Cascade delete related records
        conn.execute("DELETE FROM maintenance_schedules WHERE equipment_id = ?", (equip_id,))
        conn.execute("DELETE FROM maintenance_logs WHERE equipment_id = ?", (equip_id,))
        conn.execute("DELETE FROM equipment_hours WHERE equipment_id = ?", (equip_id,))
        conn.execute("DELETE FROM calibration_records WHERE equipment_id = ?", (equip_id,))
        conn.execute("DELETE FROM equipment WHERE id = ? AND user_id = ?", (equip_id, user_id))

    logger.info(f"Equipment deleted: id={equip_id} user={user_id}")
    return True


def get_equipment(user_id, equipment_type=None, status=None):
    """Get all equipment for a user with optional filters.

    Args:
        user_id: Owner user ID.
        equipment_type: Optional filter by equipment type.
        status: Optional filter by status.

    Returns:
        list[dict]: Equipment records.
    """
    query = 'SELECT * FROM equipment WHERE user_id = ?'
    params = [user_id]

    if equipment_type and equipment_type in VALID_EQUIPMENT_TYPES:
        query += ' AND equipment_type = ?'
        params.append(equipment_type)

    if status and status in VALID_STATUSES:
        query += ' AND status = ?'
        params.append(status)

    query += ' ORDER BY name ASC'

    with get_db() as conn:
        cursor = conn.execute(query, params)
        rows = cursor.fetchall()

    return [dict(row) for row in rows]


def get_equipment_by_id(equip_id, user_id):
    """Get a single piece of equipment by ID with ownership check.

    Args:
        equip_id: Equipment ID.
        user_id: Owner user ID.

    Returns:
        dict or None: Equipment record.
    """
    with get_db() as conn:
        cursor = conn.execute(
            'SELECT * FROM equipment WHERE id = ? AND user_id = ?',
            (equip_id, user_id)
        )
        row = cursor.fetchone()

    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Maintenance logging
# ---------------------------------------------------------------------------

def log_maintenance(user_id, data):
    """Log a maintenance event for a piece of equipment.

    Args:
        user_id: Owner user ID.
        data: dict with equipment_id, maintenance_type, description, etc.

    Returns:
        int: New maintenance log ID, or None on ownership failure.
    """
    equip_id = data.get('equipment_id')
    if not equip_id:
        logger.warning("log_maintenance called without equipment_id")
        return None

    maintenance_type = data.get('maintenance_type', 'routine')
    if maintenance_type not in VALID_MAINTENANCE_TYPES:
        maintenance_type = 'routine'

    with get_db() as conn:
        # Verify ownership
        cursor = conn.execute(
            'SELECT id FROM equipment WHERE id = ? AND user_id = ?',
            (equip_id, user_id)
        )
        if not cursor.fetchone():
            logger.warning(f"Maintenance log denied: equipment {equip_id} not owned by user {user_id}")
            return None

        cursor = conn.execute('''
            INSERT INTO maintenance_logs (
                equipment_id, user_id, maintenance_type, description,
                parts_used, parts_cost, labor_hours, labor_cost,
                performed_by, performed_date, next_due_date,
                next_due_hours, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            equip_id,
            user_id,
            maintenance_type,
            data.get('description'),
            data.get('parts_used'),
            data.get('parts_cost', 0),
            data.get('labor_hours', 0),
            data.get('labor_cost', 0),
            data.get('performed_by'),
            data.get('performed_date', datetime.now().strftime('%Y-%m-%d')),
            data.get('next_due_date'),
            data.get('next_due_hours'),
            data.get('notes')
        ))
        log_id = cursor.lastrowid

        # If maintenance changes equipment status, update it
        if data.get('set_status') and data['set_status'] in VALID_STATUSES:
            conn.execute(
                "UPDATE equipment SET status = ?, updated_at = CURRENT_TIMESTAMP "
                "WHERE id = ? AND user_id = ?",
                (data['set_status'], equip_id, user_id)
            )

    logger.info(f"Maintenance logged: id={log_id} equipment={equip_id} type={maintenance_type}")
    return log_id


def get_maintenance_history(equip_id, user_id):
    """Get full maintenance history for a piece of equipment.

    Args:
        equip_id: Equipment ID.
        user_id: Owner user ID.

    Returns:
        list[dict]: Maintenance log records ordered newest first.
    """
    with get_db() as conn:
        # Verify ownership
        cursor = conn.execute(
            'SELECT id FROM equipment WHERE id = ? AND user_id = ?',
            (equip_id, user_id)
        )
        if not cursor.fetchone():
            return []

        cursor = conn.execute('''
            SELECT ml.*, e.name AS equipment_name
            FROM maintenance_logs ml
            JOIN equipment e ON e.id = ml.equipment_id
            WHERE ml.equipment_id = ? AND ml.user_id = ?
            ORDER BY ml.performed_date DESC, ml.created_at DESC
        ''', (equip_id, user_id))
        rows = cursor.fetchall()

    return [dict(row) for row in rows]


def get_upcoming_maintenance(user_id, days=30):
    """Get maintenance tasks due within the next N days.

    Checks maintenance_schedules for upcoming due dates and hour thresholds.

    Args:
        user_id: Owner user ID.
        days: Number of days to look ahead (default 30).

    Returns:
        list[dict]: Upcoming maintenance items with equipment info.
    """
    results = []

    with get_db() as conn:
        # From maintenance schedules
        cursor = conn.execute('''
            SELECT ms.*, e.name AS equipment_name, e.equipment_type, e.current_hours
            FROM maintenance_schedules ms
            JOIN equipment e ON e.id = ms.equipment_id
            WHERE e.user_id = ?
              AND e.status != 'retired'
              AND (
                  (ms.next_due_date IS NOT NULL
                   AND ms.next_due_date <= DATE('now', ? || ' days')
                   AND ms.next_due_date >= DATE('now'))
                  OR
                  (ms.next_due_hours IS NOT NULL
                   AND ms.next_due_hours <= e.current_hours + 50)
              )
            ORDER BY ms.next_due_date ASC
        ''', (user_id, str(days)))
        rows = cursor.fetchall()

        for row in rows:
            r = dict(row)
            r['source'] = 'schedule'
            results.append(r)

    return results


def get_overdue_maintenance(user_id):
    """Get maintenance items that are past due.

    Args:
        user_id: Owner user ID.

    Returns:
        list[dict]: Overdue maintenance items with equipment info.
    """
    results = []

    with get_db() as conn:
        # Overdue schedules by date or hours
        cursor = conn.execute('''
            SELECT ms.*, e.name AS equipment_name, e.equipment_type, e.current_hours
            FROM maintenance_schedules ms
            JOIN equipment e ON e.id = ms.equipment_id
            WHERE e.user_id = ?
              AND e.status != 'retired'
              AND (
                  (ms.next_due_date IS NOT NULL AND ms.next_due_date < DATE('now'))
                  OR
                  (ms.next_due_hours IS NOT NULL AND ms.next_due_hours <= e.current_hours)
              )
            ORDER BY ms.next_due_date ASC
        ''', (user_id,))
        rows = cursor.fetchall()

        for row in rows:
            r = dict(row)
            r['source'] = 'schedule'
            results.append(r)

    return results


def create_maintenance_schedule(user_id, data):
    """Create a recurring maintenance schedule for equipment.

    Args:
        user_id: Owner user ID.
        data: dict with equipment_id, task_description, interval_hours/interval_days, etc.

    Returns:
        int: New schedule ID, or None on ownership failure.
    """
    equip_id = data.get('equipment_id')
    if not equip_id:
        logger.warning("create_maintenance_schedule called without equipment_id")
        return None

    priority = data.get('priority', 'medium')
    if priority not in VALID_PRIORITIES:
        priority = 'medium'

    with get_db() as conn:
        # Verify ownership
        cursor = conn.execute(
            'SELECT id, current_hours FROM equipment WHERE id = ? AND user_id = ?',
            (equip_id, user_id)
        )
        equip_row = cursor.fetchone()
        if not equip_row:
            logger.warning(f"Schedule creation denied: equipment {equip_id} not owned by user {user_id}")
            return None

        current_hours = equip_row['current_hours'] or 0

        # Calculate next due
        interval_hours = data.get('interval_hours')
        interval_days = data.get('interval_days')
        next_due_hours = None
        next_due_date = None

        if interval_hours:
            next_due_hours = current_hours + float(interval_hours)

        if interval_days:
            next_due_date = (datetime.now() + timedelta(days=int(interval_days))).strftime('%Y-%m-%d')

        cursor = conn.execute('''
            INSERT INTO maintenance_schedules (
                equipment_id, task_description, interval_hours, interval_days,
                last_completed, next_due_hours, next_due_date, priority
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            equip_id,
            data['task_description'],
            interval_hours,
            interval_days,
            data.get('last_completed'),
            next_due_hours,
            next_due_date,
            priority
        ))
        schedule_id = cursor.lastrowid

    logger.info(f"Maintenance schedule created: id={schedule_id} equipment={equip_id}")
    return schedule_id


def get_maintenance_cost_summary(user_id, start_date=None, end_date=None):
    """Get maintenance cost summary grouped by equipment.

    Args:
        user_id: Owner user ID.
        start_date: Optional start date filter (YYYY-MM-DD).
        end_date: Optional end date filter (YYYY-MM-DD).

    Returns:
        list[dict]: Cost breakdown per equipment with totals.
    """
    query = '''
        SELECT
            e.id AS equipment_id,
            e.name AS equipment_name,
            e.equipment_type,
            COUNT(ml.id) AS maintenance_count,
            COALESCE(SUM(ml.parts_cost), 0) AS total_parts_cost,
            COALESCE(SUM(ml.labor_cost), 0) AS total_labor_cost,
            COALESCE(SUM(ml.parts_cost), 0) + COALESCE(SUM(ml.labor_cost), 0) AS total_cost,
            COALESCE(SUM(ml.labor_hours), 0) AS total_labor_hours
        FROM equipment e
        LEFT JOIN maintenance_logs ml ON ml.equipment_id = e.id
    '''
    conditions = ['e.user_id = ?']
    params = [user_id]

    if start_date:
        conditions.append('ml.performed_date >= ?')
        params.append(start_date)

    if end_date:
        conditions.append('ml.performed_date <= ?')
        params.append(end_date)

    query += ' WHERE ' + ' AND '.join(conditions)
    query += ' GROUP BY e.id, e.name, e.equipment_type ORDER BY total_cost DESC'

    with get_db() as conn:
        cursor = conn.execute(query, params)
        rows = cursor.fetchall()

    return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# Hour tracking
# ---------------------------------------------------------------------------

def log_hours(user_id, data):
    """Log equipment usage hours.

    Args:
        user_id: Owner user ID.
        data: dict with equipment_id, date, hours_used, area, operator, fuel_added, notes.

    Returns:
        int: New hours log ID, or None on ownership failure.
    """
    equip_id = data.get('equipment_id')
    if not equip_id:
        logger.warning("log_hours called without equipment_id")
        return None

    with get_db() as conn:
        # Verify ownership
        cursor = conn.execute(
            'SELECT id FROM equipment WHERE id = ? AND user_id = ?',
            (equip_id, user_id)
        )
        if not cursor.fetchone():
            logger.warning(f"Hours log denied: equipment {equip_id} not owned by user {user_id}")
            return None

        cursor = conn.execute('''
            INSERT INTO equipment_hours (
                equipment_id, date, hours_used, area, operator, fuel_added, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            equip_id,
            data.get('date', datetime.now().strftime('%Y-%m-%d')),
            data['hours_used'],
            data.get('area'),
            data.get('operator'),
            data.get('fuel_added'),
            data.get('notes')
        ))
        log_id = cursor.lastrowid

        # Update cumulative hours on equipment
        _recalculate_equipment_hours(conn, equip_id)

    logger.info(f"Hours logged: id={log_id} equipment={equip_id} hours={data['hours_used']}")
    return log_id


def get_hours_log(equip_id, user_id, start_date=None, end_date=None):
    """Get hours log entries for a piece of equipment.

    Args:
        equip_id: Equipment ID.
        user_id: Owner user ID.
        start_date: Optional start date (YYYY-MM-DD).
        end_date: Optional end date (YYYY-MM-DD).

    Returns:
        list[dict]: Hour log records.
    """
    with get_db() as conn:
        # Verify ownership
        cursor = conn.execute(
            'SELECT id FROM equipment WHERE id = ? AND user_id = ?',
            (equip_id, user_id)
        )
        if not cursor.fetchone():
            return []

        query = 'SELECT * FROM equipment_hours WHERE equipment_id = ?'
        params = [equip_id]

        if start_date:
            query += ' AND date >= ?'
            params.append(start_date)

        if end_date:
            query += ' AND date <= ?'
            params.append(end_date)

        query += ' ORDER BY date DESC'

        cursor = conn.execute(query, params)
        rows = cursor.fetchall()

    return [dict(row) for row in rows]


def get_fleet_utilization(user_id, start_date, end_date):
    """Get fleet utilization report grouped by equipment type.

    Args:
        user_id: Owner user ID.
        start_date: Start date (YYYY-MM-DD).
        end_date: End date (YYYY-MM-DD).

    Returns:
        list[dict]: Utilization by equipment type with total hours, avg per unit, etc.
    """
    with get_db() as conn:
        cursor = conn.execute('''
            SELECT
                e.equipment_type,
                COUNT(DISTINCT e.id) AS equipment_count,
                COALESCE(SUM(eh.hours_used), 0) AS total_hours,
                COALESCE(AVG(eh.hours_used), 0) AS avg_hours_per_entry,
                COUNT(eh.id) AS log_entries
            FROM equipment e
            LEFT JOIN equipment_hours eh ON eh.equipment_id = e.id
                AND eh.date >= ? AND eh.date <= ?
            WHERE e.user_id = ? AND e.status != 'retired'
            GROUP BY e.equipment_type
            ORDER BY total_hours DESC
        ''', (start_date, end_date, user_id))
        rows = cursor.fetchall()

    results = []
    for row in rows:
        r = dict(row)
        count = r['equipment_count']
        r['avg_hours_per_unit'] = round(r['total_hours'] / count, 1) if count else 0
        results.append(r)

    return results


def update_equipment_hours(equip_id, user_id):
    """Recalculate total hours on an equipment record from the hours log.

    Args:
        equip_id: Equipment ID.
        user_id: Owner user ID.

    Returns:
        float: New total hours, or None on ownership failure.
    """
    with get_db() as conn:
        # Verify ownership
        cursor = conn.execute(
            'SELECT id FROM equipment WHERE id = ? AND user_id = ?',
            (equip_id, user_id)
        )
        if not cursor.fetchone():
            return None

        new_total = _recalculate_equipment_hours(conn, equip_id)

    logger.info(f"Equipment hours recalculated: id={equip_id} total={new_total}")
    return new_total


def _recalculate_equipment_hours(conn, equip_id):
    """Internal: recalculate and update current_hours from logs.

    Args:
        conn: Active database connection.
        equip_id: Equipment ID.

    Returns:
        float: Updated total hours.
    """
    cursor = conn.execute(
        'SELECT COALESCE(SUM(hours_used), 0) AS total FROM equipment_hours WHERE equipment_id = ?',
        (equip_id,)
    )
    row = cursor.fetchone()
    total = float(row['total']) if row else 0.0

    conn.execute(
        'UPDATE equipment SET current_hours = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
        (total, equip_id)
    )
    return total


# ---------------------------------------------------------------------------
# Calibration records
# ---------------------------------------------------------------------------

def log_calibration(user_id, data):
    """Log a calibration record for equipment.

    Args:
        user_id: Owner user ID.
        data: dict with equipment_id, calibration_date, calibration_type,
              settings_json, results_json, pass_fail, technician,
              next_calibration_date, notes.

    Returns:
        int: New calibration record ID, or None on ownership failure.
    """
    equip_id = data.get('equipment_id')
    if not equip_id:
        logger.warning("log_calibration called without equipment_id")
        return None

    calibration_type = data.get('calibration_type', 'other')
    if calibration_type not in VALID_CALIBRATION_TYPES:
        calibration_type = 'other'

    # Serialize JSON fields if they are dicts/lists
    settings_json = data.get('settings_json')
    if settings_json and not isinstance(settings_json, str):
        settings_json = json.dumps(settings_json)

    results_json = data.get('results_json')
    if results_json and not isinstance(results_json, str):
        results_json = json.dumps(results_json)

    with get_db() as conn:
        # Verify ownership
        cursor = conn.execute(
            'SELECT id FROM equipment WHERE id = ? AND user_id = ?',
            (equip_id, user_id)
        )
        if not cursor.fetchone():
            logger.warning(f"Calibration log denied: equipment {equip_id} not owned by user {user_id}")
            return None

        cursor = conn.execute('''
            INSERT INTO calibration_records (
                equipment_id, user_id, calibration_date, calibration_type,
                settings_json, results_json, pass_fail, technician,
                next_calibration_date, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            equip_id,
            user_id,
            data.get('calibration_date', datetime.now().strftime('%Y-%m-%d')),
            calibration_type,
            settings_json,
            results_json,
            data.get('pass_fail'),
            data.get('technician'),
            data.get('next_calibration_date'),
            data.get('notes')
        ))
        cal_id = cursor.lastrowid

    logger.info(f"Calibration logged: id={cal_id} equipment={equip_id} type={calibration_type}")
    return cal_id


def get_calibration_history(equip_id, user_id):
    """Get calibration history for a piece of equipment.

    Args:
        equip_id: Equipment ID.
        user_id: Owner user ID.

    Returns:
        list[dict]: Calibration records with parsed JSON fields.
    """
    with get_db() as conn:
        # Verify ownership
        cursor = conn.execute(
            'SELECT id FROM equipment WHERE id = ? AND user_id = ?',
            (equip_id, user_id)
        )
        if not cursor.fetchone():
            return []

        cursor = conn.execute('''
            SELECT cr.*, e.name AS equipment_name
            FROM calibration_records cr
            JOIN equipment e ON e.id = cr.equipment_id
            WHERE cr.equipment_id = ? AND cr.user_id = ?
            ORDER BY cr.calibration_date DESC, cr.created_at DESC
        ''', (equip_id, user_id))
        rows = cursor.fetchall()

    results = []
    for row in rows:
        r = dict(row)
        # Parse JSON fields
        if r.get('settings_json'):
            try:
                r['settings_json'] = json.loads(r['settings_json'])
            except (json.JSONDecodeError, TypeError):
                pass
        if r.get('results_json'):
            try:
                r['results_json'] = json.loads(r['results_json'])
            except (json.JSONDecodeError, TypeError):
                pass
        results.append(r)

    return results


def get_calibrations_due(user_id):
    """Get calibrations that are upcoming or overdue.

    Returns the most recent calibration record per equipment/type
    where next_calibration_date is within 30 days or already past.

    Args:
        user_id: Owner user ID.

    Returns:
        list[dict]: Due/overdue calibration items with equipment info.
    """
    with get_db() as conn:
        cursor = conn.execute('''
            SELECT cr.*, e.name AS equipment_name, e.equipment_type
            FROM calibration_records cr
            JOIN equipment e ON e.id = cr.equipment_id
            WHERE cr.user_id = ?
              AND e.status != 'retired'
              AND cr.next_calibration_date IS NOT NULL
              AND cr.next_calibration_date <= DATE('now', '30 days')
              AND cr.id = (
                  SELECT cr2.id FROM calibration_records cr2
                  WHERE cr2.equipment_id = cr.equipment_id
                    AND cr2.calibration_type = cr.calibration_type
                  ORDER BY cr2.calibration_date DESC
                  LIMIT 1
              )
            ORDER BY cr.next_calibration_date ASC
        ''', (user_id,))
        rows = cursor.fetchall()

    results = []
    for row in rows:
        r = dict(row)
        r['is_overdue'] = (
            r.get('next_calibration_date', '') < datetime.now().strftime('%Y-%m-%d')
        )
        # Parse JSON fields
        if r.get('settings_json'):
            try:
                r['settings_json'] = json.loads(r['settings_json'])
            except (json.JSONDecodeError, TypeError):
                pass
        if r.get('results_json'):
            try:
                r['results_json'] = json.loads(r['results_json'])
            except (json.JSONDecodeError, TypeError):
                pass
        results.append(r)

    return results


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

def get_fleet_summary(user_id):
    """Get summary of the fleet: counts by type and status.

    Args:
        user_id: Owner user ID.

    Returns:
        dict with 'total', 'by_type', 'by_status', 'by_area'.
    """
    with get_db() as conn:
        # Count by type
        cursor = conn.execute('''
            SELECT equipment_type, COUNT(*) AS count
            FROM equipment WHERE user_id = ?
            GROUP BY equipment_type ORDER BY count DESC
        ''', (user_id,))
        by_type = {row['equipment_type']: row['count'] for row in cursor.fetchall()}

        # Count by status
        cursor = conn.execute('''
            SELECT status, COUNT(*) AS count
            FROM equipment WHERE user_id = ?
            GROUP BY status ORDER BY count DESC
        ''', (user_id,))
        by_status = {row['status']: row['count'] for row in cursor.fetchall()}

        # Count by area assigned
        cursor = conn.execute('''
            SELECT area_assigned, COUNT(*) AS count
            FROM equipment WHERE user_id = ?
            GROUP BY area_assigned ORDER BY count DESC
        ''', (user_id,))
        by_area = {row['area_assigned']: row['count'] for row in cursor.fetchall()}

        # Total
        cursor = conn.execute(
            'SELECT COUNT(*) AS total FROM equipment WHERE user_id = ?',
            (user_id,)
        )
        total_row = cursor.fetchone()
        total = total_row['total'] if total_row else 0

    return {
        'total': total,
        'by_type': by_type,
        'by_status': by_status,
        'by_area': by_area
    }


def get_maintenance_forecast(user_id):
    """Predict upcoming maintenance needs based on schedules and usage patterns.

    Analyzes maintenance schedules and current equipment hours to forecast
    what maintenance will be needed in the next 7, 30, and 90 days.

    Args:
        user_id: Owner user ID.

    Returns:
        dict with 'next_7_days', 'next_30_days', 'next_90_days', 'overdue' lists.
    """
    now = datetime.now()
    now_str = now.strftime('%Y-%m-%d')
    d7 = (now + timedelta(days=7)).strftime('%Y-%m-%d')
    d30 = (now + timedelta(days=30)).strftime('%Y-%m-%d')
    d90 = (now + timedelta(days=90)).strftime('%Y-%m-%d')

    forecast = {
        'overdue': [],
        'next_7_days': [],
        'next_30_days': [],
        'next_90_days': []
    }

    with get_db() as conn:
        cursor = conn.execute('''
            SELECT ms.*, e.name AS equipment_name, e.equipment_type,
                   e.current_hours, e.status
            FROM maintenance_schedules ms
            JOIN equipment e ON e.id = ms.equipment_id
            WHERE e.user_id = ? AND e.status != 'retired'
            ORDER BY ms.next_due_date ASC
        ''', (user_id,))
        rows = cursor.fetchall()

    for row in rows:
        r = dict(row)
        due_date = r.get('next_due_date')
        due_hours = r.get('next_due_hours')
        current_hours = r.get('current_hours') or 0

        is_overdue_date = due_date and due_date < now_str
        is_overdue_hours = due_hours is not None and due_hours <= current_hours

        if is_overdue_date or is_overdue_hours:
            r['overdue_reason'] = []
            if is_overdue_date:
                r['overdue_reason'].append(f'date ({due_date})')
            if is_overdue_hours:
                r['overdue_reason'].append(f'hours ({due_hours} due, {current_hours} current)')
            forecast['overdue'].append(r)
        elif due_date:
            if due_date <= d7:
                forecast['next_7_days'].append(r)
            elif due_date <= d30:
                forecast['next_30_days'].append(r)
            elif due_date <= d90:
                forecast['next_90_days'].append(r)
        elif due_hours is not None:
            # Estimate urgency based on remaining hours
            hours_remaining = due_hours - current_hours
            if hours_remaining <= 10:
                forecast['next_7_days'].append(r)
            elif hours_remaining <= 50:
                forecast['next_30_days'].append(r)
            elif hours_remaining <= 150:
                forecast['next_90_days'].append(r)

    return forecast


def get_cost_of_ownership(equip_id, user_id):
    """Calculate total cost of ownership for a piece of equipment.

    Includes purchase price, all maintenance costs, and fuel usage totals.

    Args:
        equip_id: Equipment ID.
        user_id: Owner user ID.

    Returns:
        dict with cost breakdown, or None if equipment not found.
    """
    with get_db() as conn:
        # Get equipment details
        cursor = conn.execute(
            'SELECT * FROM equipment WHERE id = ? AND user_id = ?',
            (equip_id, user_id)
        )
        equip = cursor.fetchone()
        if not equip:
            return None
        equip = dict(equip)

        # Maintenance costs
        cursor = conn.execute('''
            SELECT
                COUNT(*) AS maintenance_events,
                COALESCE(SUM(parts_cost), 0) AS total_parts_cost,
                COALESCE(SUM(labor_cost), 0) AS total_labor_cost,
                COALESCE(SUM(labor_hours), 0) AS total_labor_hours
            FROM maintenance_logs
            WHERE equipment_id = ? AND user_id = ?
        ''', (equip_id, user_id))
        maint = dict(cursor.fetchone())

        # Fuel usage from hours log
        cursor = conn.execute('''
            SELECT
                COALESCE(SUM(fuel_added), 0) AS total_fuel,
                COALESCE(SUM(hours_used), 0) AS total_hours_logged
            FROM equipment_hours
            WHERE equipment_id = ?
        ''', (equip_id,))
        fuel = dict(cursor.fetchone())

    purchase_price = equip.get('purchase_price') or 0
    total_maintenance = maint['total_parts_cost'] + maint['total_labor_cost']
    total_hours = equip.get('current_hours') or 0

    cost_per_hour = 0
    if total_hours > 0:
        cost_per_hour = round((purchase_price + total_maintenance) / total_hours, 2)

    return {
        'equipment_id': equip_id,
        'equipment_name': equip.get('name'),
        'equipment_type': equip.get('equipment_type'),
        'purchase_price': purchase_price,
        'purchase_date': equip.get('purchase_date'),
        'current_hours': total_hours,
        'maintenance_events': maint['maintenance_events'],
        'total_parts_cost': maint['total_parts_cost'],
        'total_labor_cost': maint['total_labor_cost'],
        'total_maintenance_cost': total_maintenance,
        'total_labor_hours': maint['total_labor_hours'],
        'total_fuel_gallons': fuel['total_fuel'],
        'total_cost': purchase_price + total_maintenance,
        'cost_per_hour': cost_per_hour
    }


def get_fuel_usage_report(user_id, start_date, end_date):
    """Get fuel usage report grouped by equipment for a date range.

    Args:
        user_id: Owner user ID.
        start_date: Start date (YYYY-MM-DD).
        end_date: End date (YYYY-MM-DD).

    Returns:
        list[dict]: Fuel usage per equipment with hours and efficiency.
    """
    with get_db() as conn:
        cursor = conn.execute('''
            SELECT
                e.id AS equipment_id,
                e.name AS equipment_name,
                e.equipment_type,
                e.fuel_type,
                COALESCE(SUM(eh.fuel_added), 0) AS total_fuel,
                COALESCE(SUM(eh.hours_used), 0) AS total_hours,
                COUNT(eh.id) AS log_entries
            FROM equipment e
            LEFT JOIN equipment_hours eh ON eh.equipment_id = e.id
                AND eh.date >= ? AND eh.date <= ?
            WHERE e.user_id = ?
              AND e.status != 'retired'
              AND e.fuel_type != 'manual'
              AND e.fuel_type != 'electric'
            GROUP BY e.id, e.name, e.equipment_type, e.fuel_type
            HAVING total_fuel > 0 OR total_hours > 0
            ORDER BY total_fuel DESC
        ''', (start_date, end_date, user_id))
        rows = cursor.fetchall()

    results = []
    for row in rows:
        r = dict(row)
        total_fuel = r['total_fuel']
        total_hours = r['total_hours']
        r['gallons_per_hour'] = round(total_fuel / total_hours, 2) if total_hours > 0 else 0
        results.append(r)

    return results


def get_all_maintenance(user_id):
    """Get ALL maintenance records for a user (across all equipment)."""
    with get_db() as conn:
        rows = conn.execute(
            '''SELECT m.*, e.name as equipment_name, e.equipment_type
               FROM maintenance_logs m
               JOIN equipment e ON m.equipment_id = e.id
               WHERE e.user_id = ?
               ORDER BY m.performed_date DESC''',
            (user_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_all_hours(user_id):
    """Get ALL hours log entries for a user (across all equipment)."""
    with get_db() as conn:
        rows = conn.execute(
            '''SELECT h.*, e.name as equipment_name, e.equipment_type
               FROM equipment_hours h
               JOIN equipment e ON h.equipment_id = e.id
               WHERE e.user_id = ?
               ORDER BY h.date DESC''',
            (user_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_all_calibration(user_id):
    """Get ALL calibration records for a user (across all equipment)."""
    with get_db() as conn:
        rows = conn.execute(
            '''SELECT c.*, e.name as equipment_name, e.equipment_type
               FROM calibration_records c
               JOIN equipment e ON c.equipment_id = e.id
               WHERE e.user_id = ?
               ORDER BY c.calibration_date DESC''',
            (user_id,)
        ).fetchall()
    return [dict(r) for r in rows]
