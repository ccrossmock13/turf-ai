"""
Crew and labor management module for Greenside AI.
Handles crew member CRUD, work orders, time tracking, daily assignments,
and labor analytics for golf course maintenance operations.
"""

import json
import logging
from datetime import datetime, date, timedelta

from db import get_db, is_postgres, add_column

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_ROLES = [
    'superintendent', 'assistant_super', 'spray_tech', 'mechanic',
    'crew_leader', 'crew_member', 'intern'
]

VALID_AREAS = [
    'greens', 'fairways', 'tees', 'rough', 'bunkers',
    'practice', 'clubhouse', 'all'
]

VALID_TASK_TYPES = [
    'mowing', 'spraying', 'aerification', 'topdressing',
    'irrigation', 'bunker', 'cleanup', 'setup', 'other'
]

VALID_PRIORITIES = ['low', 'medium', 'high', 'urgent']

VALID_STATUSES = ['pending', 'assigned', 'in_progress', 'completed', 'cancelled']

VALID_RECURRENCES = ['none', 'daily', 'weekly', 'monthly']

STANDARD_WORK_HOURS_PER_WEEK = 40.0


# ---------------------------------------------------------------------------
# Table initialization
# ---------------------------------------------------------------------------

def init_crew_tables():
    """Initialize all crew management tables. Safe to call multiple times."""
    with get_db() as conn:
        cursor = conn.cursor()

        # Crew members table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS crew_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'crew_member',
                email TEXT,
                phone TEXT,
                certifications TEXT,
                hire_date TEXT,
                hourly_rate REAL,
                is_active INTEGER DEFAULT 1,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # Work orders table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS work_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                area TEXT DEFAULT 'all',
                task_type TEXT DEFAULT 'other',
                priority TEXT DEFAULT 'medium',
                status TEXT DEFAULT 'pending',
                assigned_to INTEGER,
                due_date TEXT,
                completed_at TIMESTAMP,
                estimated_hours REAL,
                actual_hours REAL,
                notes TEXT,
                recurrence TEXT DEFAULT 'none',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (assigned_to) REFERENCES crew_members (id)
            )
        ''')
        # Time entries table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS time_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                crew_member_id INTEGER NOT NULL,
                work_order_id INTEGER,
                date TEXT NOT NULL,
                start_time TEXT,
                end_time TEXT,
                hours REAL NOT NULL,
                area TEXT,
                task_type TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (crew_member_id) REFERENCES crew_members (id),
                FOREIGN KEY (work_order_id) REFERENCES work_orders (id)
            )
        ''')
        # Daily assignments table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                crew_member_id INTEGER NOT NULL,
                area TEXT,
                task_description TEXT NOT NULL,
                equipment_needed TEXT,
                start_time TEXT,
                completed INTEGER DEFAULT 0,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (crew_member_id) REFERENCES crew_members (id)
            )
        ''')

    logger.info("Crew management tables initialized")


# ---------------------------------------------------------------------------
# Crew Member CRUD
# ---------------------------------------------------------------------------

def add_crew_member(user_id, data):
    """Add a new crew member.

    Args:
        user_id: The superintendent/manager user ID.
        data: Dict with keys: name (required), role, email, phone,
              certifications, hire_date, hourly_rate, notes.

    Returns:
        dict with 'id' and 'name' on success, or dict with 'error'.
    """
    name = data.get('name', '').strip()
    if not name:
        return {'error': 'Crew member name is required'}

    role = data.get('role', 'crew_member')
    if role not in VALID_ROLES:
        return {'error': f'Invalid role. Must be one of: {", ".join(VALID_ROLES)}'}
    certifications = data.get('certifications')
    if certifications and isinstance(certifications, (list, dict)):
        certifications = json.dumps(certifications)

    try:
        with get_db() as conn:
            cursor = conn.execute('''
                INSERT INTO crew_members
                (user_id, name, role, email, phone, certifications,
                 hire_date, hourly_rate, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id, name, role,
                data.get('email', '').strip() or None,
                data.get('phone', '').strip() or None,
                certifications,
                data.get('hire_date') or None,
                data.get('hourly_rate') or None,
                data.get('notes', '').strip() or None
            ))
            member_id = cursor.lastrowid
        logger.info(f"Added crew member '{name}' (id={member_id}) for user {user_id}")
        return {'id': member_id, 'name': name}
    except Exception as e:
        logger.error(f"Error adding crew member: {e}")
        return {'error': str(e)}

def update_crew_member(member_id, user_id, data):
    """Update an existing crew member.

    Args:
        member_id: Crew member ID.
        user_id: Owner user ID (for authorization).
        data: Dict of fields to update.

    Returns:
        dict with 'success' or 'error'.
    """
    if 'role' in data and data['role'] not in VALID_ROLES:
        return {'error': f'Invalid role. Must be one of: {", ".join(VALID_ROLES)}'}

    allowed_fields = [
        'name', 'role', 'email', 'phone', 'certifications',
        'hire_date', 'hourly_rate', 'is_active', 'notes'
    ]

    updates = []
    params = []
    for field in allowed_fields:
        if field in data:
            value = data[field]
            if field == 'certifications' and isinstance(value, (list, dict)):
                value = json.dumps(value)
            updates.append(f"{field} = ?")
            params.append(value)
    if not updates:
        return {'error': 'No valid fields to update'}

    updates.append("updated_at = CURRENT_TIMESTAMP")
    params.extend([member_id, user_id])

    try:
        with get_db() as conn:
            cursor = conn.execute(f'''
                UPDATE crew_members
                SET {", ".join(updates)}
                WHERE id = ? AND user_id = ?
            ''', params)
            if cursor.rowcount == 0:
                return {'error': 'Crew member not found or access denied'}
        logger.info(f"Updated crew member {member_id} for user {user_id}")
        return {'success': True}
    except Exception as e:
        logger.error(f"Error updating crew member {member_id}: {e}")
        return {'error': str(e)}

def deactivate_crew_member(member_id, user_id):
    """Soft-delete a crew member by setting is_active = 0.

    Args:
        member_id: Crew member ID.
        user_id: Owner user ID.

    Returns:
        dict with 'success' or 'error'.
    """
    try:
        with get_db() as conn:
            cursor = conn.execute('''
                UPDATE crew_members
                SET is_active = 0, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND user_id = ?
            ''', (member_id, user_id))
            if cursor.rowcount == 0:
                return {'error': 'Crew member not found or access denied'}
        logger.info(f"Deactivated crew member {member_id} for user {user_id}")
        return {'success': True}
    except Exception as e:
        logger.error(f"Error deactivating crew member {member_id}: {e}")
        return {'error': str(e)}

def delete_crew_member_permanent(member_id, user_id):
    """Permanently delete a crew member and all related records."""
    try:
        with get_db() as conn:
            row = conn.execute(
                'SELECT id FROM crew_members WHERE id = ? AND user_id = ?',
                (member_id, user_id)
            ).fetchone()
            if not row:
                return {'error': 'Crew member not found or access denied'}
            conn.execute('DELETE FROM daily_assignments WHERE crew_member_id = ? AND user_id = ?', (member_id, user_id))
            conn.execute('DELETE FROM time_entries WHERE crew_member_id = ?', (member_id,))
            conn.execute('UPDATE work_orders SET assigned_to = NULL WHERE assigned_to = ? AND user_id = ?', (member_id, user_id))
            conn.execute('DELETE FROM crew_members WHERE id = ? AND user_id = ?', (member_id, user_id))
        logger.info(f"Permanently deleted crew member {member_id} for user {user_id}")
        return {'success': True}
    except Exception as e:
        logger.error(f"Error deleting crew member {member_id}: {e}")
        return {'error': str(e)}


def get_crew_members(user_id, role=None, active_only=True):
    """Get all crew members for a user.

    Args:
        user_id: Owner user ID.
        role: Optional role filter.
        active_only: If True, only return active members.

    Returns:
        List of crew member dicts.
    """
    try:
        with get_db() as conn:
            sql = 'SELECT * FROM crew_members WHERE user_id = ?'
            params = [user_id]

            if active_only:
                sql += ' AND is_active = 1'

            if role:
                if role not in VALID_ROLES:
                    return []
                sql += ' AND role = ?'
                params.append(role)

            sql += ' ORDER BY name ASC'
            rows = conn.execute(sql, params).fetchall()

        members = []
        for row in rows:
            member = _row_to_crew_member(row)
            members.append(member)
        return members
    except Exception as e:
        logger.error(f"Error fetching crew members for user {user_id}: {e}")
        return []

def get_crew_member_by_id(member_id, user_id):
    """Get a single crew member by ID.

    Args:
        member_id: Crew member ID.
        user_id: Owner user ID.

    Returns:
        Crew member dict or None.
    """
    try:
        with get_db() as conn:
            row = conn.execute('''
                SELECT * FROM crew_members
                WHERE id = ? AND user_id = ?
            ''', (member_id, user_id)).fetchone()

        if not row:
            return None
        return _row_to_crew_member(row)
    except Exception as e:
        logger.error(f"Error fetching crew member {member_id}: {e}")
        return None

def _row_to_crew_member(row):
    """Convert a database row to a crew member dict."""
    certs = row['certifications']
    if certs:
        try:
            certs = json.loads(certs)
        except (json.JSONDecodeError, TypeError):
            pass

    return {
        'id': row['id'],
        'user_id': row['user_id'],
        'name': row['name'],
        'role': row['role'],
        'email': row['email'],
        'phone': row['phone'],
        'certifications': certs,
        'hire_date': row['hire_date'],
        'hourly_rate': row['hourly_rate'],
        'is_active': bool(row['is_active']),
        'notes': row['notes'],
        'created_at': row['created_at'],
        'updated_at': row['updated_at'],
    }


# ---------------------------------------------------------------------------
# Work Order CRUD
# ---------------------------------------------------------------------------

def create_work_order(user_id, data):
    """Create a new work order.

    Args:
        user_id: Owner user ID.
        data: Dict with keys: title (required), description, area, task_type,
              priority, assigned_to, due_date, estimated_hours, notes, recurrence.

    Returns:
        dict with 'id' and 'title' on success, or dict with 'error'.
    """
    title = data.get('title', '').strip()
    if not title:
        return {'error': 'Work order title is required'}

    area = data.get('area', 'all')
    if area not in VALID_AREAS:
        return {'error': f'Invalid area. Must be one of: {", ".join(VALID_AREAS)}'}

    task_type = data.get('task_type', 'other')
    if task_type not in VALID_TASK_TYPES:
        return {'error': f'Invalid task type. Must be one of: {", ".join(VALID_TASK_TYPES)}'}
    priority = data.get('priority', 'medium')
    if priority not in VALID_PRIORITIES:
        return {'error': f'Invalid priority. Must be one of: {", ".join(VALID_PRIORITIES)}'}

    recurrence = data.get('recurrence', 'none')
    if recurrence not in VALID_RECURRENCES:
        return {'error': f'Invalid recurrence. Must be one of: {", ".join(VALID_RECURRENCES)}'}

    status = 'assigned' if data.get('assigned_to') else 'pending'

    try:
        with get_db() as conn:
            cursor = conn.execute('''
                INSERT INTO work_orders
                (user_id, title, description, area, task_type, priority, status,
                 assigned_to, due_date, estimated_hours, notes, recurrence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id, title,
                data.get('description', '').strip() or None,
                area, task_type, priority, status,
                data.get('assigned_to') or None,
                data.get('due_date') or None,
                data.get('estimated_hours') or None,
                data.get('notes', '').strip() or None,
                recurrence
            ))
            wo_id = cursor.lastrowid
        logger.info(f"Created work order '{title}' (id={wo_id}) for user {user_id}")
        return {'id': wo_id, 'title': title}
    except Exception as e:
        logger.error(f"Error creating work order: {e}")
        return {'error': str(e)}

def update_work_order(wo_id, user_id, data):
    """Update an existing work order.

    Args:
        wo_id: Work order ID.
        user_id: Owner user ID.
        data: Dict of fields to update.

    Returns:
        dict with 'success' or 'error'.
    """
    if 'area' in data and data['area'] not in VALID_AREAS:
        return {'error': f'Invalid area. Must be one of: {", ".join(VALID_AREAS)}'}
    if 'task_type' in data and data['task_type'] not in VALID_TASK_TYPES:
        return {'error': f'Invalid task type. Must be one of: {", ".join(VALID_TASK_TYPES)}'}
    if 'priority' in data and data['priority'] not in VALID_PRIORITIES:
        return {'error': f'Invalid priority. Must be one of: {", ".join(VALID_PRIORITIES)}'}
    if 'status' in data and data['status'] not in VALID_STATUSES:
        return {'error': f'Invalid status. Must be one of: {", ".join(VALID_STATUSES)}'}
    if 'recurrence' in data and data['recurrence'] not in VALID_RECURRENCES:
        return {'error': f'Invalid recurrence. Must be one of: {", ".join(VALID_RECURRENCES)}'}
    allowed_fields = [
        'title', 'description', 'area', 'task_type', 'priority', 'status',
        'assigned_to', 'due_date', 'estimated_hours', 'actual_hours',
        'notes', 'recurrence'
    ]

    updates = []
    params = []
    for field in allowed_fields:
        if field in data:
            updates.append(f"{field} = ?")
            params.append(data[field])

    if not updates:
        return {'error': 'No valid fields to update'}

    updates.append("updated_at = CURRENT_TIMESTAMP")
    params.extend([wo_id, user_id])

    try:
        with get_db() as conn:
            cursor = conn.execute(f'''
                UPDATE work_orders
                SET {", ".join(updates)}
                WHERE id = ? AND user_id = ?
            ''', params)
            if cursor.rowcount == 0:
                return {'error': 'Work order not found or access denied'}
        logger.info(f"Updated work order {wo_id} for user {user_id}")
        return {'success': True}
    except Exception as e:
        logger.error(f"Error updating work order {wo_id}: {e}")
        return {'error': str(e)}

def assign_work_order(wo_id, user_id, crew_member_id):
    """Assign a work order to a crew member.

    Args:
        wo_id: Work order ID.
        user_id: Owner user ID.
        crew_member_id: ID of the crew member to assign.

    Returns:
        dict with 'success' or 'error'.
    """
    try:
        with get_db() as conn:
            # Verify crew member belongs to this user and is active
            member = conn.execute('''
                SELECT id, name FROM crew_members
                WHERE id = ? AND user_id = ? AND is_active = 1
            ''', (crew_member_id, user_id)).fetchone()

            if not member:
                return {'error': 'Crew member not found, inactive, or access denied'}

            cursor = conn.execute('''
                UPDATE work_orders
                SET assigned_to = ?, status = 'assigned',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND user_id = ?
            ''', (crew_member_id, wo_id, user_id))
            if cursor.rowcount == 0:
                return {'error': 'Work order not found or access denied'}

        logger.info(
            f"Assigned work order {wo_id} to crew member "
            f"{crew_member_id} for user {user_id}"
        )
        return {'success': True, 'assigned_to_name': member['name']}
    except Exception as e:
        logger.error(f"Error assigning work order {wo_id}: {e}")
        return {'error': str(e)}

def complete_work_order(wo_id, user_id, actual_hours=None):
    """Mark a work order as completed.

    Args:
        wo_id: Work order ID.
        user_id: Owner user ID.
        actual_hours: Optional actual hours spent.

    Returns:
        dict with 'success' or 'error'.
    """
    try:
        with get_db() as conn:
            if actual_hours is not None:
                cursor = conn.execute('''
                    UPDATE work_orders
                    SET status = 'completed', completed_at = CURRENT_TIMESTAMP,
                        actual_hours = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND user_id = ?
                ''', (actual_hours, wo_id, user_id))
            else:
                cursor = conn.execute('''
                    UPDATE work_orders
                    SET status = 'completed', completed_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND user_id = ?
                ''', (wo_id, user_id))

            if cursor.rowcount == 0:
                return {'error': 'Work order not found or access denied'}
        logger.info(f"Completed work order {wo_id} for user {user_id}")
        return {'success': True}
    except Exception as e:
        logger.error(f"Error completing work order {wo_id}: {e}")
        return {'error': str(e)}

def get_work_orders(user_id, status=None, area=None, assigned_to=None,
                    date_range=None):
    """Get work orders with optional filters.

    Args:
        user_id: Owner user ID.
        status: Optional status filter.
        area: Optional area filter.
        assigned_to: Optional crew member ID filter.
        date_range: Optional tuple of (start_date, end_date) strings for due_date.

    Returns:
        List of work order dicts.
    """
    try:
        with get_db() as conn:
            sql = '''
                SELECT wo.*, cm.name AS assigned_name
                FROM work_orders wo
                LEFT JOIN crew_members cm ON wo.assigned_to = cm.id
                WHERE wo.user_id = ?
            '''
            params = [user_id]

            if status:
                sql += ' AND wo.status = ?'
                params.append(status)
            if area:
                sql += ' AND wo.area = ?'
                params.append(area)

            if assigned_to:
                sql += ' AND wo.assigned_to = ?'
                params.append(assigned_to)

            if date_range and len(date_range) == 2:
                start_dt, end_dt = date_range
                if start_dt:
                    sql += ' AND wo.due_date >= ?'
                    params.append(start_dt)
                if end_dt:
                    sql += ' AND wo.due_date <= ?'
                    params.append(end_dt)

            sql += ' ORDER BY wo.due_date ASC, wo.priority DESC'
            rows = conn.execute(sql, params).fetchall()

        orders = []
        for row in rows:
            orders.append(_row_to_work_order(row))
        return orders
    except Exception as e:
        logger.error(f"Error fetching work orders for user {user_id}: {e}")
        return []

def get_work_order_by_id(wo_id, user_id):
    """Get a single work order by ID.

    Args:
        wo_id: Work order ID.
        user_id: Owner user ID.

    Returns:
        Work order dict or None.
    """
    try:
        with get_db() as conn:
            row = conn.execute('''
                SELECT wo.*, cm.name AS assigned_name
                FROM work_orders wo
                LEFT JOIN crew_members cm ON wo.assigned_to = cm.id
                WHERE wo.id = ? AND wo.user_id = ?
            ''', (wo_id, user_id)).fetchone()

        if not row:
            return None
        return _row_to_work_order(row)
    except Exception as e:
        logger.error(f"Error fetching work order {wo_id}: {e}")
        return None

def get_daily_work_orders(user_id, date=None):
    """Get work orders due on a specific date (defaults to today).

    Args:
        user_id: Owner user ID.
        date: Date string (YYYY-MM-DD). Defaults to today.

    Returns:
        List of work order dicts.
    """
    if date is None:
        date = _today_str()

    try:
        with get_db() as conn:
            rows = conn.execute('''
                SELECT wo.*, cm.name AS assigned_name
                FROM work_orders wo
                LEFT JOIN crew_members cm ON wo.assigned_to = cm.id
                WHERE wo.user_id = ? AND wo.due_date = ?
                    AND wo.status != 'cancelled'
                ORDER BY
                    CASE wo.priority
                        WHEN 'urgent' THEN 0
                        WHEN 'high' THEN 1
                        WHEN 'medium' THEN 2
                        WHEN 'low' THEN 3
                    END,
                    wo.created_at ASC
            ''', (user_id, date)).fetchall()
        orders = []
        for row in rows:
            orders.append(_row_to_work_order(row))
        return orders
    except Exception as e:
        logger.error(f"Error fetching daily work orders for user {user_id}: {e}")
        return []

def _row_to_work_order(row):
    """Convert a database row to a work order dict."""
    return {
        'id': row['id'],
        'user_id': row['user_id'],
        'title': row['title'],
        'description': row['description'],
        'area': row['area'],
        'task_type': row['task_type'],
        'priority': row['priority'],
        'status': row['status'],
        'assigned_to': row['assigned_to'],
        'assigned_name': row.get('assigned_name'),
        'due_date': row['due_date'],
        'completed_at': row['completed_at'],
        'estimated_hours': row['estimated_hours'],
        'actual_hours': row['actual_hours'],
        'notes': row['notes'],
        'recurrence': row['recurrence'],
        'created_at': row['created_at'],
        'updated_at': row['updated_at'],
    }


# ---------------------------------------------------------------------------
# Time Tracking
# ---------------------------------------------------------------------------

def log_time(user_id, data):
    """Log a time entry for a crew member.

    Args:
        user_id: Owner user ID (used to verify crew member ownership).
        data: Dict with keys: crew_member_id (required), date (required),
              hours (required), work_order_id, start_time, end_time,
              area, task_type, notes.

    Returns:
        dict with 'id' on success, or dict with 'error'.
    """
    crew_member_id = data.get('crew_member_id')
    entry_date = data.get('date')
    hours = data.get('hours')

    if not crew_member_id:
        return {'error': 'crew_member_id is required'}
    if not entry_date:
        return {'error': 'date is required'}
    if hours is None or hours <= 0:
        return {'error': 'hours must be a positive number'}
    area = data.get('area')
    if area and area not in VALID_AREAS:
        return {'error': f'Invalid area. Must be one of: {", ".join(VALID_AREAS)}'}

    task_type = data.get('task_type')
    if task_type and task_type not in VALID_TASK_TYPES:
        return {'error': f'Invalid task type. Must be one of: {", ".join(VALID_TASK_TYPES)}'}

    try:
        with get_db() as conn:
            # Verify crew member belongs to this user
            member = conn.execute('''
                SELECT id FROM crew_members
                WHERE id = ? AND user_id = ?
            ''', (crew_member_id, user_id)).fetchone()

            if not member:
                return {'error': 'Crew member not found or access denied'}

            cursor = conn.execute('''
                INSERT INTO time_entries
                (crew_member_id, work_order_id, date, start_time, end_time,
                 hours, area, task_type, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                crew_member_id,
                data.get('work_order_id') or None,
                entry_date,
                data.get('start_time') or None,
                data.get('end_time') or None,                hours,
                area,
                task_type,
                data.get('notes', '').strip() or None
            ))
            entry_id = cursor.lastrowid

        logger.info(
            f"Logged {hours}h for crew member {crew_member_id} "
            f"on {entry_date} (entry={entry_id})"
        )
        return {'id': entry_id}
    except Exception as e:
        logger.error(f"Error logging time: {e}")
        return {'error': str(e)}

def get_time_entries(user_id, crew_member_id=None, start_date=None,
                     end_date=None):
    """Get time entries for a user's crew.

    Args:
        user_id: Owner user ID.
        crew_member_id: Optional filter by specific crew member.
        start_date: Optional start date (YYYY-MM-DD).
        end_date: Optional end date (YYYY-MM-DD).

    Returns:
        List of time entry dicts.
    """
    try:
        with get_db() as conn:
            sql = '''
                SELECT te.*, cm.name AS crew_member_name
                FROM time_entries te
                JOIN crew_members cm ON te.crew_member_id = cm.id
                WHERE cm.user_id = ?
            '''
            params = [user_id]

            if crew_member_id:
                sql += ' AND te.crew_member_id = ?'
                params.append(crew_member_id)

            if start_date:
                sql += ' AND te.date >= ?'
                params.append(start_date)
            if end_date:
                sql += ' AND te.date <= ?'
                params.append(end_date)

            sql += ' ORDER BY te.date DESC, te.start_time DESC'
            rows = conn.execute(sql, params).fetchall()

        entries = []
        for row in rows:
            entries.append({
                'id': row['id'],
                'crew_member_id': row['crew_member_id'],
                'crew_member_name': row['crew_member_name'],
                'work_order_id': row['work_order_id'],
                'date': row['date'],
                'start_time': row['start_time'],
                'end_time': row['end_time'],
                'hours': row['hours'],
                'area': row['area'],
                'task_type': row['task_type'],
                'notes': row['notes'],
                'created_at': row['created_at'],
            })
        return entries
    except Exception as e:
        logger.error(f"Error fetching time entries for user {user_id}: {e}")
        return []

def get_labor_summary(user_id, start_date, end_date):
    """Get a summary of labor hours broken down by area, task type, and crew member.

    Args:
        user_id: Owner user ID.
        start_date: Start date (YYYY-MM-DD).
        end_date: End date (YYYY-MM-DD).

    Returns:
        dict with 'by_area', 'by_task_type', 'by_crew_member', 'total_hours'.
    """
    try:
        with get_db() as conn:
            params = [user_id, start_date, end_date]

            # Hours by area
            area_rows = conn.execute('''
                SELECT te.area, SUM(te.hours) AS total_hours,
                       COUNT(*) AS entry_count
                FROM time_entries te
                JOIN crew_members cm ON te.crew_member_id = cm.id
                WHERE cm.user_id = ? AND te.date >= ? AND te.date <= ?
                    AND te.area IS NOT NULL
                GROUP BY te.area
                ORDER BY total_hours DESC
            ''', params).fetchall()
            # Hours by task type
            task_rows = conn.execute('''
                SELECT te.task_type, SUM(te.hours) AS total_hours,
                       COUNT(*) AS entry_count
                FROM time_entries te
                JOIN crew_members cm ON te.crew_member_id = cm.id
                WHERE cm.user_id = ? AND te.date >= ? AND te.date <= ?
                    AND te.task_type IS NOT NULL
                GROUP BY te.task_type
                ORDER BY total_hours DESC
            ''', params).fetchall()

            # Hours by crew member
            member_rows = conn.execute('''
                SELECT cm.id, cm.name, SUM(te.hours) AS total_hours,
                       COUNT(*) AS entry_count
                FROM time_entries te
                JOIN crew_members cm ON te.crew_member_id = cm.id
                WHERE cm.user_id = ? AND te.date >= ? AND te.date <= ?
                GROUP BY cm.id, cm.name
                ORDER BY total_hours DESC
            ''', params).fetchall()
            # Total hours
            total_row = conn.execute('''
                SELECT SUM(te.hours) AS total_hours
                FROM time_entries te
                JOIN crew_members cm ON te.crew_member_id = cm.id
                WHERE cm.user_id = ? AND te.date >= ? AND te.date <= ?
            ''', params).fetchone()

        by_area = [
            {'area': r['area'], 'hours': round(r['total_hours'], 2),
             'entries': r['entry_count']}
            for r in area_rows
        ]
        by_task_type = [
            {'task_type': r['task_type'], 'hours': round(r['total_hours'], 2),
             'entries': r['entry_count']}
            for r in task_rows
        ]
        by_crew_member = [
            {'id': r['id'], 'name': r['name'],
             'hours': round(r['total_hours'], 2), 'entries': r['entry_count']}
            for r in member_rows
        ]
        total_hours = round(total_row['total_hours'], 2) if total_row and total_row['total_hours'] else 0.0
        return {
            'by_area': by_area,
            'by_task_type': by_task_type,
            'by_crew_member': by_crew_member,
            'total_hours': total_hours,
            'start_date': start_date,
            'end_date': end_date,
        }
    except Exception as e:
        logger.error(f"Error generating labor summary for user {user_id}: {e}")
        return {
            'by_area': [], 'by_task_type': [], 'by_crew_member': [],
            'total_hours': 0.0, 'start_date': start_date, 'end_date': end_date,
        }

def get_labor_cost(user_id, start_date, end_date):
    """Get labor cost breakdown by crew member and area.

    Args:
        user_id: Owner user ID.
        start_date: Start date (YYYY-MM-DD).
        end_date: End date (YYYY-MM-DD).

    Returns:
        dict with 'by_crew_member', 'by_area', 'total_cost', 'total_hours'.
    """
    try:
        with get_db() as conn:
            params = [user_id, start_date, end_date]

            # Cost by crew member
            member_rows = conn.execute('''
                SELECT cm.id, cm.name, cm.hourly_rate,
                       SUM(te.hours) AS total_hours
                FROM time_entries te
                JOIN crew_members cm ON te.crew_member_id = cm.id
                WHERE cm.user_id = ? AND te.date >= ? AND te.date <= ?
                GROUP BY cm.id, cm.name, cm.hourly_rate
                ORDER BY total_hours DESC
            ''', params).fetchall()
            # Cost by area
            area_rows = conn.execute('''
                SELECT te.area, SUM(te.hours) AS total_hours,
                       SUM(te.hours * COALESCE(cm.hourly_rate, 0)) AS total_cost
                FROM time_entries te
                JOIN crew_members cm ON te.crew_member_id = cm.id
                WHERE cm.user_id = ? AND te.date >= ? AND te.date <= ?
                    AND te.area IS NOT NULL
                GROUP BY te.area
                ORDER BY total_cost DESC
            ''', params).fetchall()

        by_member = []
        total_cost = 0.0
        total_hours = 0.0
        for r in member_rows:
            rate = r['hourly_rate'] or 0.0
            hours = r['total_hours'] or 0.0
            cost = round(rate * hours, 2)
            total_cost += cost
            total_hours += hours
            by_member.append({
                'id': r['id'],
                'name': r['name'],
                'hourly_rate': rate,
                'hours': round(hours, 2),
                'cost': cost,
            })
        by_area = [
            {'area': r['area'], 'hours': round(r['total_hours'] or 0, 2),
             'cost': round(r['total_cost'] or 0, 2)}
            for r in area_rows
        ]

        return {
            'by_crew_member': by_member,
            'by_area': by_area,
            'total_cost': round(total_cost, 2),
            'total_hours': round(total_hours, 2),
            'start_date': start_date,
            'end_date': end_date,
        }
    except Exception as e:
        logger.error(f"Error generating labor cost for user {user_id}: {e}")
        return {
            'by_crew_member': [], 'by_area': [],
            'total_cost': 0.0, 'total_hours': 0.0,
            'start_date': start_date, 'end_date': end_date,
        }


# ---------------------------------------------------------------------------
# Daily Assignments
# ---------------------------------------------------------------------------

def create_daily_assignments(user_id, date, assignments):
    """Batch-create daily assignments.

    Args:
        user_id: Owner user ID.
        date: Date string (YYYY-MM-DD).
        assignments: List of dicts, each with: crew_member_id (required),
                     task_description (required), area, equipment_needed,
                     start_time, notes.

    Returns:
        dict with 'created' count and 'ids', or dict with 'error'.
    """
    if not assignments or not isinstance(assignments, list):
        return {'error': 'assignments must be a non-empty list'}

    if not date:
        return {'error': 'date is required'}

    created_ids = []
    errors = []
    try:
        with get_db() as conn:
            # Pre-validate all crew member IDs belong to this user
            member_ids = set(
                a.get('crew_member_id') for a in assignments
                if a.get('crew_member_id')
            )
            if member_ids:
                placeholders = ', '.join(['?' for _ in member_ids])
                valid_rows = conn.execute(f'''
                    SELECT id FROM crew_members
                    WHERE user_id = ? AND id IN ({placeholders})
                ''', [user_id] + list(member_ids)).fetchall()
                valid_ids = set(r['id'] for r in valid_rows)
            else:
                valid_ids = set()

            for i, assignment in enumerate(assignments):
                cm_id = assignment.get('crew_member_id')
                task_desc = assignment.get('task_description', '').strip()

                if not cm_id:
                    errors.append(f"Assignment {i}: crew_member_id is required")
                    continue
                if cm_id not in valid_ids:
                    errors.append(
                        f"Assignment {i}: crew member {cm_id} not found or access denied"
                    )
                    continue
                if not task_desc:
                    errors.append(f"Assignment {i}: task_description is required")
                    continue
                area = assignment.get('area')
                if area and area not in VALID_AREAS:
                    errors.append(f"Assignment {i}: invalid area '{area}'")
                    continue

                cursor = conn.execute('''
                    INSERT INTO daily_assignments
                    (user_id, date, crew_member_id, area, task_description,
                     equipment_needed, start_time, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    user_id, date, cm_id, area, task_desc,
                    assignment.get('equipment_needed', '').strip() or None,
                    assignment.get('start_time') or None,
                    assignment.get('notes', '').strip() or None
                ))
                created_ids.append(cursor.lastrowid)

        result = {'created': len(created_ids), 'ids': created_ids}
        if errors:
            result['errors'] = errors
        logger.info(
            f"Created {len(created_ids)} daily assignments for "
            f"user {user_id} on {date}"
        )
        return result
    except Exception as e:
        logger.error(f"Error creating daily assignments: {e}")
        return {'error': str(e)}

def get_daily_assignments(user_id, date=None):
    """Get daily assignments for a given date (defaults to today).

    Args:
        user_id: Owner user ID.
        date: Date string (YYYY-MM-DD). Defaults to today.

    Returns:
        List of assignment dicts.
    """
    if date is None:
        date = _today_str()

    try:
        with get_db() as conn:
            rows = conn.execute('''
                SELECT da.*, cm.name AS crew_member_name,
                       cm.role AS crew_member_role
                FROM daily_assignments da
                JOIN crew_members cm ON da.crew_member_id = cm.id
                WHERE da.user_id = ? AND da.date = ?
                ORDER BY da.start_time ASC, cm.name ASC
            ''', (user_id, date)).fetchall()

        assignments = []
        for row in rows:
            assignments.append({
                'id': row['id'],
                'user_id': row['user_id'],                'date': row['date'],
                'crew_member_id': row['crew_member_id'],
                'crew_member_name': row['crew_member_name'],
                'crew_member_role': row['crew_member_role'],
                'area': row['area'],
                'task_description': row['task_description'],
                'equipment_needed': row['equipment_needed'],
                'start_time': row['start_time'],
                'completed': bool(row['completed']),
                'notes': row['notes'],
                'created_at': row['created_at'],
            })
        return assignments
    except Exception as e:
        logger.error(f"Error fetching daily assignments for user {user_id}: {e}")
        return []

def complete_assignment(assignment_id, user_id):
    """Mark a daily assignment as completed.

    Args:
        assignment_id: Assignment ID.
        user_id: Owner user ID.

    Returns:
        dict with 'success' or 'error'.
    """
    try:
        with get_db() as conn:
            cursor = conn.execute('''
                UPDATE daily_assignments
                SET completed = 1
                WHERE id = ? AND user_id = ?
            ''', (assignment_id, user_id))
            if cursor.rowcount == 0:
                return {'error': 'Assignment not found or access denied'}
        logger.info(f"Completed assignment {assignment_id} for user {user_id}")
        return {'success': True}
    except Exception as e:
        logger.error(f"Error completing assignment {assignment_id}: {e}")
        return {'error': str(e)}

def generate_daily_sheet(user_id, date=None):
    """Generate a formatted daily work sheet for printing or display.

    Args:
        user_id: Owner user ID.
        date: Date string (YYYY-MM-DD). Defaults to today.

    Returns:
        dict with 'date', 'assignments_by_member', 'work_orders', 'summary'.
    """
    if date is None:
        date = _today_str()

    assignments = get_daily_assignments(user_id, date)
    work_orders = get_daily_work_orders(user_id, date)

    # Group assignments by crew member
    by_member = {}
    for a in assignments:
        name = a['crew_member_name']
        if name not in by_member:
            by_member[name] = {
                'crew_member_id': a['crew_member_id'],
                'role': a['crew_member_role'],
                'tasks': [],
            }
        by_member[name]['tasks'].append({
            'id': a['id'],
            'area': a['area'],            'task': a['task_description'],
            'equipment': a['equipment_needed'],
            'start_time': a['start_time'],
            'completed': a['completed'],
            'notes': a['notes'],
        })

    # Summary counts
    total_tasks = len(assignments)
    completed_tasks = sum(1 for a in assignments if a['completed'])
    pending_wo = sum(1 for wo in work_orders if wo['status'] != 'completed')

    return {
        'date': date,
        'assignments_by_member': by_member,
        'work_orders': work_orders,
        'summary': {
            'total_crew': len(by_member),
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks,
            'pending_work_orders': pending_wo,
        },
    }


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

def get_productivity_report(user_id, start_date, end_date):
    """Generate a productivity report: hours per area and estimated vs actual.

    Args:
        user_id: Owner user ID.
        start_date: Start date (YYYY-MM-DD).
        end_date: End date (YYYY-MM-DD).

    Returns:
        dict with 'hours_by_area', 'efficiency', 'daily_breakdown'.
    """
    try:
        with get_db() as conn:
            params = [user_id, start_date, end_date]

            # Hours by area
            area_rows = conn.execute('''
                SELECT te.area, SUM(te.hours) AS total_hours,
                       COUNT(DISTINCT te.date) AS days_worked
                FROM time_entries te
                JOIN crew_members cm ON te.crew_member_id = cm.id
                WHERE cm.user_id = ? AND te.date >= ? AND te.date <= ?
                    AND te.area IS NOT NULL
                GROUP BY te.area
                ORDER BY total_hours DESC
            ''', params).fetchall()
            # Efficiency: estimated vs actual hours on completed work orders
            efficiency_rows = conn.execute('''
                SELECT wo.area, wo.task_type,
                       SUM(wo.estimated_hours) AS est_total,
                       SUM(wo.actual_hours) AS act_total,
                       COUNT(*) AS order_count
                FROM work_orders wo
                WHERE wo.user_id = ? AND wo.status = 'completed'
                    AND wo.completed_at >= ? AND wo.completed_at <= ?
                    AND wo.estimated_hours IS NOT NULL
                    AND wo.actual_hours IS NOT NULL
                GROUP BY wo.area, wo.task_type
                ORDER BY wo.area, wo.task_type
            ''', params).fetchall()

            # Daily total hours
            daily_rows = conn.execute('''
                SELECT te.date, SUM(te.hours) AS total_hours,
                       COUNT(DISTINCT te.crew_member_id) AS crew_count
                FROM time_entries te
                JOIN crew_members cm ON te.crew_member_id = cm.id
                WHERE cm.user_id = ? AND te.date >= ? AND te.date <= ?
                GROUP BY te.date
                ORDER BY te.date ASC
            ''', params).fetchall()
        hours_by_area = [
            {'area': r['area'], 'hours': round(r['total_hours'], 2),
             'days_worked': r['days_worked'],
             'avg_hours_per_day': round(
                 r['total_hours'] / max(r['days_worked'], 1), 2
             )}
            for r in area_rows
        ]

        efficiency = []
        for r in efficiency_rows:
            est = r['est_total'] or 0
            act = r['act_total'] or 0
            pct = round((est / act * 100), 1) if act > 0 else None
            efficiency.append({
                'area': r['area'],
                'task_type': r['task_type'],
                'estimated_hours': round(est, 2),
                'actual_hours': round(act, 2),
                'efficiency_pct': pct,
                'order_count': r['order_count'],
            })

        daily_breakdown = [
            {'date': r['date'], 'hours': round(r['total_hours'], 2),
             'crew_count': r['crew_count']}
            for r in daily_rows
        ]
        return {
            'hours_by_area': hours_by_area,
            'efficiency': efficiency,
            'daily_breakdown': daily_breakdown,
            'start_date': start_date,
            'end_date': end_date,
        }
    except Exception as e:
        logger.error(f"Error generating productivity report for user {user_id}: {e}")
        return {
            'hours_by_area': [], 'efficiency': [], 'daily_breakdown': [],
            'start_date': start_date, 'end_date': end_date,
        }

def get_crew_utilization(user_id, start_date, end_date):
    """Calculate crew utilization: percentage of available hours used.

    Assumes each active crew member is available for STANDARD_WORK_HOURS_PER_WEEK
    hours per week.

    Args:
        user_id: Owner user ID.
        start_date: Start date (YYYY-MM-DD).
        end_date: End date (YYYY-MM-DD).

    Returns:
        dict with 'by_crew_member', 'overall_utilization_pct',
        'total_available', 'total_worked'.
    """
    try:
        # Calculate number of work weeks in range
        start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()
        total_days = (end_dt - start_dt).days + 1
        total_weeks = max(total_days / 7.0, 0.0)

        with get_db() as conn:
            # Get active crew members and their logged hours
            rows = conn.execute('''
                SELECT cm.id, cm.name, cm.role,
                       COALESCE(SUM(te.hours), 0) AS total_hours
                FROM crew_members cm
                LEFT JOIN time_entries te
                    ON te.crew_member_id = cm.id
                    AND te.date >= ? AND te.date <= ?                WHERE cm.user_id = ? AND cm.is_active = 1
                GROUP BY cm.id, cm.name, cm.role
                ORDER BY cm.name ASC
            ''', (start_date, end_date, user_id)).fetchall()

        by_member = []
        total_available = 0.0
        total_worked = 0.0

        for r in rows:
            available = round(STANDARD_WORK_HOURS_PER_WEEK * total_weeks, 2)
            worked = round(r['total_hours'], 2)
            utilization = (
                round((worked / available * 100), 1) if available > 0 else 0.0
            )
            total_available += available
            total_worked += worked
            by_member.append({
                'id': r['id'],
                'name': r['name'],
                'role': r['role'],
                'available_hours': available,
                'worked_hours': worked,
                'utilization_pct': utilization,
            })
        overall = (
            round((total_worked / total_available * 100), 1)
            if total_available > 0 else 0.0
        )

        return {
            'by_crew_member': by_member,
            'overall_utilization_pct': overall,
            'total_available_hours': round(total_available, 2),
            'total_worked_hours': round(total_worked, 2),
            'weeks_in_range': round(total_weeks, 2),
            'start_date': start_date,
            'end_date': end_date,
        }
    except Exception as e:
        logger.error(f"Error generating crew utilization for user {user_id}: {e}")
        return {
            'by_crew_member': [], 'overall_utilization_pct': 0.0,
            'total_available_hours': 0.0, 'total_worked_hours': 0.0,
            'weeks_in_range': 0.0,
            'start_date': start_date, 'end_date': end_date,
        }

def get_overtime_report(user_id, start_date, end_date):
    """Generate an overtime report showing hours over 40 per week per member.

    Args:
        user_id: Owner user ID.
        start_date: Start date (YYYY-MM-DD).
        end_date: End date (YYYY-MM-DD).

    Returns:
        dict with 'by_crew_member' (each with weekly breakdown),
        'total_overtime_hours', 'total_overtime_cost'.
    """
    try:
        start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()

        with get_db() as conn:
            # Get all time entries in range for this user's crew
            rows = conn.execute('''
                SELECT te.crew_member_id, cm.name, cm.hourly_rate,
                       te.date, te.hours
                FROM time_entries te
                JOIN crew_members cm ON te.crew_member_id = cm.id
                WHERE cm.user_id = ? AND te.date >= ? AND te.date <= ?
                ORDER BY te.crew_member_id, te.date
            ''', (user_id, start_date, end_date)).fetchall()
        # Build weekly totals per crew member
        # Week key = ISO year-week
        member_weeks = {}

        for r in rows:
            mid = r['crew_member_id']
            if mid not in member_weeks:
                member_weeks[mid] = {
                    'name': r['name'],
                    'hourly_rate': r['hourly_rate'] or 0.0,
                    'weeks': {},
                }

            try:
                entry_date = datetime.strptime(r['date'], '%Y-%m-%d').date()
            except (ValueError, TypeError):
                continue

            iso_year, iso_week, _ = entry_date.isocalendar()
            week_key = f"{iso_year}-W{iso_week:02d}"

            member_weeks[mid]['weeks'][week_key] = (
                member_weeks[mid]['weeks'].get(week_key, 0.0)
                + (r['hours'] or 0.0)
            )
        # Calculate overtime
        by_member = []
        total_overtime_hours = 0.0
        total_overtime_cost = 0.0

        for mid, info in member_weeks.items():
            member_ot_hours = 0.0
            weekly_detail = []

            for week_key in sorted(info['weeks'].keys()):
                weekly_hours = info['weeks'][week_key]
                ot = max(0.0, weekly_hours - STANDARD_WORK_HOURS_PER_WEEK)
                member_ot_hours += ot
                weekly_detail.append({
                    'week': week_key,
                    'total_hours': round(weekly_hours, 2),
                    'overtime_hours': round(ot, 2),
                })

            # Overtime cost at 1.5x rate
            ot_cost = round(member_ot_hours * info['hourly_rate'] * 1.5, 2)
            total_overtime_hours += member_ot_hours
            total_overtime_cost += ot_cost

            by_member.append({
                'id': mid,
                'name': info['name'],
                'hourly_rate': info['hourly_rate'],
                'total_overtime_hours': round(member_ot_hours, 2),
                'overtime_cost': ot_cost,
                'weekly_detail': weekly_detail,
            })
        # Sort by most overtime first
        by_member.sort(key=lambda x: x['total_overtime_hours'], reverse=True)

        return {
            'by_crew_member': by_member,
            'total_overtime_hours': round(total_overtime_hours, 2),
            'total_overtime_cost': round(total_overtime_cost, 2),
            'start_date': start_date,
            'end_date': end_date,
        }
    except Exception as e:
        logger.error(f"Error generating overtime report for user {user_id}: {e}")
        return {
            'by_crew_member': [],
            'total_overtime_hours': 0.0,
            'total_overtime_cost': 0.0,
            'start_date': start_date,
            'end_date': end_date,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _today_str():
    """Return today's date as YYYY-MM-DD string."""
    return date.today().isoformat()


def update_assignment(assignment_id, user_id, data):
    """Update a daily assignment."""
    with get_db() as conn:
        assignment = conn.execute(
            'SELECT id FROM daily_assignments WHERE id = ? AND user_id = ?',
            (assignment_id, user_id)
        ).fetchone()
        if not assignment:
            raise ValueError(f"Assignment {assignment_id} not found")
        sets = []
        vals = []
        for key in ('crew_member_id', 'area', 'task', 'priority', 'notes', 'completed'):
            if key in data:
                sets.append(f'{key} = ?')
                vals.append(data[key])
        if sets:
            vals.extend([assignment_id, user_id])
            conn.execute(
                f'UPDATE daily_assignments SET {", ".join(sets)} WHERE id = ? AND user_id = ?',
                vals
            )
    return {'id': assignment_id, 'updated': True}


def delete_assignment(assignment_id, user_id):
    """Delete a daily assignment."""
    with get_db() as conn:
        conn.execute(
            'DELETE FROM daily_assignments WHERE id = ? AND user_id = ?',
            (assignment_id, user_id)
        )
    return {'deleted': True}
