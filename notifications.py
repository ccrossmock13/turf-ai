"""
Notification system for Greenside AI.

Provides a complete notification lifecycle: creation, delivery, preferences,
rule-based automation, and built-in generators for weather, GDD, spray,
maintenance, budget, inventory, and task alerts.

Uses the shared db layer (get_db context manager) which supports both
SQLite and PostgreSQL transparently.
"""

import json
import logging
from datetime import datetime, timedelta

from db import get_db

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_NOTIFICATION_TYPES = (
    'weather_alert',
    'gdd_threshold',
    'spray_reminder',
    'maintenance_due',
    'budget_warning',
    'calibration_due',
    'disease_alert',
    'task_overdue',
    'inventory_low',
    'custom',
)

VALID_SEVERITIES = ('info', 'warning', 'critical')

VALID_RULE_TYPES = (
    'gdd_threshold',
    'temperature',
    'wind_speed',
    'rain_forecast',
    'budget_pct',
    'inventory_qty',
    'spray_interval',
)

# Default severity labels used in morning briefings
_SEVERITY_EMOJI = {
    'critical': '[CRITICAL]',
    'warning': '[WARNING]',
    'info': '[INFO]',
}

# ---------------------------------------------------------------------------
# Table initialisation
# ---------------------------------------------------------------------------

def init_notification_tables():
    """Create the notification tables if they do not already exist.

    Safe to call multiple times -- uses IF NOT EXISTS.
    """
    with get_db() as conn:
        # -- notifications -------------------------------------------------
        conn.execute('''
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                notification_type TEXT NOT NULL,
                severity TEXT NOT NULL DEFAULT 'info',
                read INTEGER NOT NULL DEFAULT 0,
                dismissed INTEGER NOT NULL DEFAULT 0,
                action_url TEXT,
                related_id INTEGER,
                related_type TEXT,
                expires_at TIMESTAMP,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # -- notification_preferences --------------------------------------
        conn.execute('''
            CREATE TABLE IF NOT EXISTS notification_preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                notification_type TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                email_enabled INTEGER NOT NULL DEFAULT 0,
                push_enabled INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # -- notification_rules --------------------------------------------
        conn.execute('''
            CREATE TABLE IF NOT EXISTS notification_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                rule_type TEXT NOT NULL,
                condition_json TEXT NOT NULL,
                message_template TEXT NOT NULL,
                severity TEXT NOT NULL DEFAULT 'info',
                is_active INTEGER NOT NULL DEFAULT 1,
                last_triggered TIMESTAMP,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        ''')
    logger.info("Notification tables initialised")


# ---------------------------------------------------------------------------
# Notification CRUD
# ---------------------------------------------------------------------------

def create_notification(
    user_id,
    title,
    message,
    notification_type,
    severity='info',
    action_url=None,
    related_id=None,
    related_type=None,
    expires_at=None,
):
    """Insert a new notification and return its id.

    Before inserting, checks the user's preferences to see whether this
    notification type is enabled.  If it is disabled the call is a no-op
    and returns ``None``.
    """
    if notification_type not in VALID_NOTIFICATION_TYPES:
        logger.warning("Invalid notification_type %r -- skipping", notification_type)
        return None
    if severity not in VALID_SEVERITIES:
        severity = 'info'

    # Respect user preferences
    prefs = get_preferences(user_id)
    pref = prefs.get(notification_type)
    if pref and not pref.get('enabled', True):
        logger.debug(
            "Notification type %r disabled for user %s -- skipping",
            notification_type,
            user_id,
        )
        return None

    try:
        with get_db() as conn:
            cursor = conn.execute(
                '''INSERT INTO notifications
                   (user_id, title, message, notification_type, severity,
                    action_url, related_id, related_type, expires_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (
                    user_id,
                    title,
                    message,
                    notification_type,
                    severity,
                    action_url,
                    related_id,
                    related_type,
                    expires_at,
                ),
            )
            notification_id = cursor.lastrowid
            logger.info(
                "Created notification %s for user %s: %s",
                notification_id,
                user_id,
                title,
            )
            return notification_id
    except Exception:
        logger.exception("Failed to create notification for user %s", user_id)
        return None

def get_notifications(user_id, unread_only=False, limit=50):
    """Return a list of notifications for *user_id*.

    Args:
        user_id: Owner of the notifications.
        unread_only: When ``True`` only return notifications that have not
            been read or dismissed.
        limit: Maximum number of rows to return (default 50).

    Returns:
        list[dict]
    """
    try:
        with get_db() as conn:
            if unread_only:
                cursor = conn.execute(
                    '''SELECT * FROM notifications
                       WHERE user_id = ? AND read = 0 AND dismissed = 0
                       ORDER BY created_at DESC
                       LIMIT ?''',
                    (user_id, limit),
                )
            else:
                cursor = conn.execute(
                    '''SELECT * FROM notifications
                       WHERE user_id = ? AND dismissed = 0
                       ORDER BY created_at DESC
                       LIMIT ?''',
                    (user_id, limit),
                )
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
    except Exception:
        logger.exception("Failed to fetch notifications for user %s", user_id)
        return []


def mark_read(notification_id, user_id):
    """Mark a single notification as read.  Returns ``True`` on success."""
    try:
        with get_db() as conn:
            cursor = conn.execute(
                '''UPDATE notifications SET read = 1
                   WHERE id = ? AND user_id = ?''',
                (notification_id, user_id),
            )
            return cursor.rowcount > 0
    except Exception:
        logger.exception("Failed to mark notification %s read", notification_id)
        return False


def mark_all_read(user_id):
    """Mark every unread notification for *user_id* as read.

    Returns the number of rows affected.
    """
    try:
        with get_db() as conn:
            cursor = conn.execute(
                '''UPDATE notifications SET read = 1
                   WHERE user_id = ? AND read = 0''',
                (user_id,),
            )
            count = cursor.rowcount
            logger.info("Marked %d notifications read for user %s", count, user_id)
            return count
    except Exception:
        logger.exception("Failed to mark all read for user %s", user_id)
        return 0


def dismiss_notification(notification_id, user_id):
    """Dismiss (soft-delete) a notification.  Returns ``True`` on success."""
    try:
        with get_db() as conn:
            cursor = conn.execute(
                '''UPDATE notifications SET dismissed = 1
                   WHERE id = ? AND user_id = ?''',
                (notification_id, user_id),
            )
            return cursor.rowcount > 0
    except Exception:
        logger.exception("Failed to dismiss notification %s", notification_id)
        return False

def get_unread_count(user_id):
    """Return the number of unread, non-dismissed notifications."""
    try:
        with get_db() as conn:
            cursor = conn.execute(
                '''SELECT COUNT(*) FROM notifications
                   WHERE user_id = ? AND read = 0 AND dismissed = 0''',
                (user_id,),
            )
            row = cursor.fetchone()
            return row[0] if row else 0
    except Exception:
        logger.exception("Failed to get unread count for user %s", user_id)
        return 0


def cleanup_expired(user_id=None):
    """Delete notifications whose *expires_at* is in the past.

    If *user_id* is provided the cleanup is scoped to that user; otherwise
    all expired notifications across all users are removed.

    Returns the number of deleted rows.
    """
    try:
        with get_db() as conn:
            if user_id:
                cursor = conn.execute(
                    '''DELETE FROM notifications
                       WHERE user_id = ? AND expires_at IS NOT NULL
                         AND expires_at < CURRENT_TIMESTAMP''',
                    (user_id,),
                )
            else:
                cursor = conn.execute(
                    '''DELETE FROM notifications
                       WHERE expires_at IS NOT NULL
                         AND expires_at < CURRENT_TIMESTAMP'''
                )
            count = cursor.rowcount
            if count:
                logger.info("Cleaned up %d expired notifications", count)
            return count
    except Exception:
        logger.exception("Failed to clean up expired notifications")
        return 0

# ---------------------------------------------------------------------------
# Preference management
# ---------------------------------------------------------------------------

def get_preferences(user_id):
    """Return a dict keyed by notification_type with preference details.

    Example return value::

        {
            'weather_alert': {
                'enabled': True,
                'email_enabled': False,
                'push_enabled': True
            },
            ...
        }
    """
    try:
        with get_db() as conn:
            cursor = conn.execute(
                '''SELECT notification_type, enabled, email_enabled, push_enabled
                   FROM notification_preferences
                   WHERE user_id = ?''',
                (user_id,),
            )
            rows = cursor.fetchall()
            result = {}
            for row in rows:
                result[row['notification_type']] = {
                    'enabled': bool(row['enabled']),
                    'email_enabled': bool(row['email_enabled']),
                    'push_enabled': bool(row['push_enabled']),
                }
            return result
    except Exception:
        logger.exception("Failed to load preferences for user %s", user_id)
        return {}


def update_preference(user_id, notification_type, enabled=None, email_enabled=None, push_enabled=None):
    """Update one or more fields on an existing preference row.

    If the row does not exist it is created with the supplied values (and
    defaults for any omitted fields).

    Returns ``True`` on success.
    """
    if notification_type not in VALID_NOTIFICATION_TYPES:
        logger.warning("Invalid notification_type %r in update_preference", notification_type)
        return False

    try:
        with get_db() as conn:
            # Check if the row already exists
            cursor = conn.execute(
                '''SELECT id, enabled, email_enabled, push_enabled
                   FROM notification_preferences
                   WHERE user_id = ? AND notification_type = ?''',
                (user_id, notification_type),
            )
            existing = cursor.fetchone()

            if existing:
                new_enabled = int(enabled) if enabled is not None else existing['enabled']
                new_email = int(email_enabled) if email_enabled is not None else existing['email_enabled']
                new_push = int(push_enabled) if push_enabled is not None else existing['push_enabled']

                conn.execute(
                    '''UPDATE notification_preferences
                       SET enabled = ?, email_enabled = ?, push_enabled = ?,
                           updated_at = CURRENT_TIMESTAMP
                       WHERE id = ?''',
                    (new_enabled, new_email, new_push, existing['id']),
                )
            else:
                conn.execute(
                    '''INSERT INTO notification_preferences
                       (user_id, notification_type, enabled, email_enabled, push_enabled)
                       VALUES (?, ?, ?, ?, ?)''',
                    (
                        user_id,
                        notification_type,
                        int(enabled) if enabled is not None else 1,
                        int(email_enabled) if email_enabled is not None else 0,
                        int(push_enabled) if push_enabled is not None else 1,
                    ),
                )
            return True
    except Exception:
        logger.exception("Failed to update preference for user %s", user_id)
        return False


def init_default_preferences(user_id):
    """Seed default preference rows for every notification type.

    Existing rows are left untouched -- only missing types are inserted.
    """
    existing = get_preferences(user_id)
    try:
        with get_db() as conn:
            for ntype in VALID_NOTIFICATION_TYPES:
                if ntype not in existing:
                    conn.execute(
                        '''INSERT INTO notification_preferences
                           (user_id, notification_type, enabled, email_enabled, push_enabled)
                           VALUES (?, ?, 1, 0, 1)''',
                        (user_id, ntype),
                    )
        logger.info("Default notification preferences initialised for user %s", user_id)
    except Exception:
        logger.exception("Failed to init default preferences for user %s", user_id)

# ---------------------------------------------------------------------------
# Rule-based notifications
# ---------------------------------------------------------------------------

def create_rule(user_id, data):
    """Create a notification rule.

    *data* is a dict with keys: ``name``, ``rule_type``, ``condition_json``
    (dict or JSON string), ``message_template``, and optionally ``severity``.

    Returns the new rule id or ``None`` on failure.
    """
    name = data.get('name', 'Untitled Rule')
    rule_type = data.get('rule_type')
    condition = data.get('condition_json', '{}')
    template = data.get('message_template', '')
    severity = data.get('severity', 'info')

    if rule_type not in VALID_RULE_TYPES:
        logger.warning("Invalid rule_type %r", rule_type)
        return None

    if severity not in VALID_SEVERITIES:
        severity = 'info'

    # Accept a dict and serialise it
    if isinstance(condition, dict):
        condition = json.dumps(condition)
    try:
        with get_db() as conn:
            cursor = conn.execute(
                '''INSERT INTO notification_rules
                   (user_id, name, rule_type, condition_json,
                    message_template, severity)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (user_id, name, rule_type, condition, template, severity),
            )
            rule_id = cursor.lastrowid
            logger.info("Created notification rule %s for user %s", rule_id, user_id)
            return rule_id
    except Exception:
        logger.exception("Failed to create rule for user %s", user_id)
        return None


def get_rules(user_id):
    """Return all notification rules for *user_id*."""
    try:
        with get_db() as conn:
            cursor = conn.execute(
                '''SELECT * FROM notification_rules
                   WHERE user_id = ?
                   ORDER BY created_at DESC''',
                (user_id,),
            )
            rows = cursor.fetchall()
            results = []
            for row in rows:
                item = dict(row)
                # Parse condition_json for convenience
                try:
                    item['condition'] = json.loads(item.get('condition_json', '{}'))
                except (json.JSONDecodeError, TypeError):
                    item['condition'] = {}
                results.append(item)
            return results
    except Exception:
        logger.exception("Failed to fetch rules for user %s", user_id)
        return []


def update_rule(rule_id, user_id, data):
    """Update fields on an existing rule.

    *data* may contain any of: ``name``, ``rule_type``, ``condition_json``,
    ``message_template``, ``severity``, ``is_active``.

    Returns ``True`` on success.
    """
    allowed_fields = {
        'name', 'rule_type', 'condition_json', 'message_template',
        'severity', 'is_active',
    }
    updates = []
    params = []
    for key, value in data.items():
        if key not in allowed_fields:
            continue
        if key == 'condition_json' and isinstance(value, dict):
            value = json.dumps(value)
        if key == 'rule_type' and value not in VALID_RULE_TYPES:
            logger.warning("Skipping invalid rule_type %r in update", value)
            continue
        if key == 'severity' and value not in VALID_SEVERITIES:
            value = 'info'
        updates.append(f"{key} = ?")
        params.append(value)

    if not updates:
        return False

    params.extend([rule_id, user_id])
    set_clause = ', '.join(updates)

    try:
        with get_db() as conn:
            cursor = conn.execute(
                f'''UPDATE notification_rules
                    SET {set_clause}
                    WHERE id = ? AND user_id = ?''',
                tuple(params),
            )
            return cursor.rowcount > 0
    except Exception:
        logger.exception("Failed to update rule %s", rule_id)
        return False


def delete_rule(rule_id, user_id):
    """Delete a notification rule.  Returns ``True`` if a row was removed."""
    try:
        with get_db() as conn:
            cursor = conn.execute(
                '''DELETE FROM notification_rules
                   WHERE id = ? AND user_id = ?''',
                (rule_id, user_id),
            )
            return cursor.rowcount > 0
    except Exception:
        logger.exception("Failed to delete rule %s", rule_id)
        return False


def evaluate_rules(user_id, context_data):
    """Evaluate all active rules against *context_data* and fire matching
    notifications.

    *context_data* is a dict that should contain keys matching the
    ``rule_type`` values the user has configured.  For example::

        {
            'gdd_threshold': 450,
            'temperature': 92,
            'wind_speed': 18,
            'rain_forecast': 0.8,
            'budget_pct': 85,
            'inventory_qty': {'Primo Maxx': 2},
            'spray_interval': {'Primo Maxx': 21},
        }

    Each rule's ``condition_json`` should contain ``operator`` and
    ``value`` keys.  Supported operators: ``>``, ``>=``, ``<``, ``<=``,
    ``==``, ``!=``.

    Returns the number of notifications created.
    """
    rules = get_rules(user_id)
    created_count = 0

    operator_map = {
        '>': lambda a, b: a > b,
        '>=': lambda a, b: a >= b,
        '<': lambda a, b: a < b,
        '<=': lambda a, b: a <= b,
        '==': lambda a, b: a == b,
        '!=': lambda a, b: a != b,
    }

    for rule in rules:
        if not rule.get('is_active', 1):
            continue
        rule_type = rule.get('rule_type')
        condition = rule.get('condition', {})
        operator = condition.get('operator', '>=')
        threshold = condition.get('value')

        if threshold is None:
            continue

        # Get the current value from context_data
        current_value = context_data.get(rule_type)
        if current_value is None:
            continue

        # For dict-valued context entries (e.g. per-product inventory)
        # the condition may include a ``key`` to look up.
        if isinstance(current_value, dict):
            key = condition.get('key')
            if key is None:
                continue
            current_value = current_value.get(key)
            if current_value is None:
                continue

        op_fn = operator_map.get(operator)
        if op_fn is None:
            logger.warning("Unknown operator %r in rule %s", operator, rule.get('id'))
            continue
        try:
            if not op_fn(float(current_value), float(threshold)):
                continue
        except (ValueError, TypeError):
            logger.debug(
                "Could not compare %r with %r for rule %s",
                current_value, threshold, rule.get('id'),
            )
            continue

        # Build the notification message from the template
        template = rule.get('message_template', '')
        message = template.replace('{value}', str(current_value))
        message = message.replace('{threshold}', str(threshold))
        message = message.replace('{name}', rule.get('name', ''))

        nid = create_notification(
            user_id=user_id,
            title=rule.get('name', 'Rule Alert'),
            message=message,
            notification_type=_rule_type_to_notification_type(rule_type),
            severity=rule.get('severity', 'info'),
        )

        if nid:
            created_count += 1
            # Record when this rule last fired
            try:
                with get_db() as conn:
                    conn.execute(
                        '''UPDATE notification_rules
                           SET last_triggered = CURRENT_TIMESTAMP
                           WHERE id = ?''',
                        (rule['id'],),
                    )
            except Exception:
                logger.debug("Could not update last_triggered for rule %s", rule['id'])

    if created_count:
        logger.info(
            "Rule evaluation created %d notification(s) for user %s",
            created_count,
            user_id,
        )
    return created_count


def _rule_type_to_notification_type(rule_type):
    """Map a rule_type to its matching notification_type."""
    mapping = {
        'gdd_threshold': 'gdd_threshold',
        'temperature': 'weather_alert',
        'wind_speed': 'weather_alert',
        'rain_forecast': 'weather_alert',
        'budget_pct': 'budget_warning',
        'inventory_qty': 'inventory_low',
        'spray_interval': 'spray_reminder',
    }
    return mapping.get(rule_type, 'custom')

# ---------------------------------------------------------------------------
# Built-in notification generators
# ---------------------------------------------------------------------------

def notify_weather_alert(user_id, alert_type, details):
    """Create a weather-triggered notification.

    Args:
        user_id: Target user.
        alert_type: Short label, e.g. ``'heat_advisory'``, ``'frost_warning'``.
        details: Human-readable description of the alert.
    """
    severity = 'critical' if 'warning' in alert_type.lower() or 'frost' in alert_type.lower() else 'warning'
    return create_notification(
        user_id=user_id,
        title=f"Weather Alert: {alert_type.replace('_', ' ').title()}",
        message=details,
        notification_type='weather_alert',
        severity=severity,
        action_url='/weather',
    )


def notify_gdd_threshold(user_id, current_gdd, threshold, action):
    """Notify when a GDD milestone has been reached.

    Args:
        user_id: Target user.
        current_gdd: The current accumulated GDD value.
        threshold: The threshold that was crossed.
        action: Recommended action string.
    """
    return create_notification(
        user_id=user_id,
        title=f"GDD Threshold Reached: {threshold}",
        message=(
            f"Accumulated GDD has reached {current_gdd:.0f} "
            f"(threshold: {threshold}). Recommended action: {action}"
        ),
        notification_type='gdd_threshold',
        severity='info',
        action_url='/gdd',
    )


def notify_spray_reminder(user_id, product_name, area, last_applied, interval_days):
    """Remind the user to re-apply a spray product.

    Args:
        user_id: Target user.
        product_name: Name of the product.
        area: Turf area (e.g. ``'greens'``).
        last_applied: Date string of the most recent application.
        interval_days: Re-application interval in days.
    """
    return create_notification(
        user_id=user_id,
        title=f"Spray Reminder: {product_name}",
        message=(
            f"{product_name} on {area} was last applied on {last_applied}. "
            f"The {interval_days}-day re-application interval is approaching."
        ),
        notification_type='spray_reminder',
        severity='warning',
        action_url='/spray-tracker',
        related_type='spray_log',
    )


def notify_maintenance_due(user_id, equipment_name, maintenance_type, due_date):
    """Notify about upcoming equipment maintenance.

    Args:
        user_id: Target user.
        equipment_name: Name of the equipment.
        maintenance_type: Type of maintenance (e.g. ``'oil_change'``).
        due_date: When the maintenance is due (date string).
    """
    severity = 'warning'
    try:
        due_dt = datetime.strptime(str(due_date), '%Y-%m-%d')
        if due_dt.date() <= datetime.now().date():
            severity = 'critical'
    except (ValueError, TypeError):
        pass
    return create_notification(
        user_id=user_id,
        title=f"Maintenance Due: {equipment_name}",
        message=(
            f"{maintenance_type.replace('_', ' ').title()} is due for "
            f"{equipment_name} on {due_date}."
        ),
        notification_type='maintenance_due',
        severity=severity,
        action_url='/equipment',
    )


def notify_budget_warning(user_id, category, pct_used, budget_amount):
    """Warn when budget spend exceeds a threshold.

    Args:
        user_id: Target user.
        category: Budget category name.
        pct_used: Percentage of budget already consumed (0-100+).
        budget_amount: Total budget amount for context.
    """
    if pct_used >= 100:
        severity = 'critical'
        label = 'exceeded'
    elif pct_used >= 90:
        severity = 'critical'
        label = 'nearly exhausted'
    elif pct_used >= 75:
        severity = 'warning'
        label = 'reaching limit'
    else:
        severity = 'info'
        label = 'update'

    return create_notification(
        user_id=user_id,
        title=f"Budget {label.title()}: {category}",
        message=(
            f"The {category} budget is at {pct_used:.0f}% "
            f"(${budget_amount:,.2f} total). {label.capitalize()}."
        ),
        notification_type='budget_warning',
        severity=severity,
        action_url='/budget',
    )


def notify_inventory_low(user_id, product_name, current_qty, min_qty):
    """Alert when inventory drops below the minimum threshold.

    Args:
        user_id: Target user.
        product_name: Name of the product.
        current_qty: Current quantity in stock.
        min_qty: Minimum acceptable quantity.
    """
    severity = 'critical' if current_qty == 0 else 'warning'
    return create_notification(
        user_id=user_id,
        title=f"Low Inventory: {product_name}",
        message=(
            f"{product_name} stock is at {current_qty} "
            f"(minimum: {min_qty}). Please reorder."
        ),
        notification_type='inventory_low',
        severity=severity,
        action_url='/inventory',
    )


def notify_task_overdue(user_id, task_title, due_date):
    """Alert when a task or work order is past its due date.

    Args:
        user_id: Target user.
        task_title: Title of the overdue task.
        due_date: Original due date (date string).
    """
    return create_notification(
        user_id=user_id,
        title=f"Task Overdue: {task_title}",
        message=(
            f'"{task_title}" was due on {due_date} and has not been completed.'
        ),
        notification_type='task_overdue',
        severity='warning',
        action_url='/tasks',
    )

# ---------------------------------------------------------------------------
# Batch processing
# ---------------------------------------------------------------------------

def run_daily_checks(user_id):
    """Run all active notification rules against current data and perform
    housekeeping tasks.

    This is intended to be called once per day (e.g. via a scheduler or
    cron job).  It:

    1. Cleans up expired notifications.
    2. Gathers context data from the database (spray intervals, budgets,
       etc.) where available.
    3. Evaluates all user rules against that context.

    Returns a summary dict.
    """
    summary = {
        'expired_cleaned': 0,
        'rules_evaluated': 0,
        'notifications_created': 0,
    }

    # Step 1 -- housekeeping
    summary['expired_cleaned'] = cleanup_expired(user_id)

    # Step 2 -- gather context from database where possible
    context_data = _gather_context(user_id)
    # Step 3 -- evaluate rules
    if context_data:
        rules = get_rules(user_id)
        summary['rules_evaluated'] = len(rules)
        summary['notifications_created'] = evaluate_rules(user_id, context_data)

    logger.info("Daily checks for user %s: %s", user_id, summary)
    return summary


def _gather_context(user_id):
    """Best-effort collection of current data for rule evaluation.

    Pulls from spray_log, budgets, and inventory tables when they exist.
    Returns a dict suitable for ``evaluate_rules``.
    """
    context = {}

    try:
        with get_db() as conn:
            # --- Spray intervals: days since last application per product ---
            try:
                cursor = conn.execute(
                    '''SELECT product_name,
                              MAX(date_applied) as last_applied
                       FROM spray_log
                       WHERE user_id = ?
                       GROUP BY product_name''',
                    (user_id,),
                )
                spray_intervals = {}
                for row in cursor.fetchall():
                    try:
                        last = datetime.strptime(row['last_applied'], '%Y-%m-%d')
                        days_since = (datetime.now() - last).days
                        spray_intervals[row['product_name']] = days_since
                    except (ValueError, TypeError):
                        pass
                if spray_intervals:
                    context['spray_interval'] = spray_intervals
            except Exception:
                logger.debug("spray_log table not available for context gathering")

            # --- Budget percentages per category ---
            try:
                cursor = conn.execute(
                    '''SELECT category, budget_amount, spent_amount
                       FROM budgets
                       WHERE user_id = ?''',
                    (user_id,),
                )
                budget_pcts = {}
                for row in cursor.fetchall():
                    budget = float(row['budget_amount'] or 0)
                    spent = float(row['spent_amount'] or 0)
                    if budget > 0:
                        budget_pcts[row['category']] = round((spent / budget) * 100, 1)
                if budget_pcts:
                    context['budget_pct'] = budget_pcts
            except Exception:
                logger.debug("budgets table not available for context gathering")

            # --- Inventory quantities per product ---
            try:
                cursor = conn.execute(
                    '''SELECT product_name, quantity
                       FROM inventory
                       WHERE user_id = ?''',
                    (user_id,),
                )
                inv_qtys = {}
                for row in cursor.fetchall():
                    inv_qtys[row['product_name']] = float(row['quantity'] or 0)
                if inv_qtys:
                    context['inventory_qty'] = inv_qtys
            except Exception:
                logger.debug("inventory table not available for context gathering")

    except Exception:
        logger.exception("Failed to gather context for user %s", user_id)

    return context


def generate_morning_briefing(user_id):
    """Create a summary notification that aggregates today's key information.

    The briefing includes:
    - Unread critical/warning notification count
    - Any weather alerts from the last 24 hours
    - Upcoming spray reminders
    - Overdue tasks

    Returns the notification id of the briefing, or ``None``.
    """
    sections = []
    now = datetime.now()

    try:
        with get_db() as conn:
            # -- Unread counts by severity --
            cursor = conn.execute(
                '''SELECT severity, COUNT(*) as cnt
                   FROM notifications
                   WHERE user_id = ? AND read = 0 AND dismissed = 0
                   GROUP BY severity''',
                (user_id,),
            )
            severity_counts = {}
            for row in cursor.fetchall():
                severity_counts[row['severity']] = row['cnt']
            total_unread = sum(severity_counts.values())
            if severity_counts:
                parts = []
                for sev in ('critical', 'warning', 'info'):
                    cnt = severity_counts.get(sev, 0)
                    if cnt:
                        parts.append(f"{cnt} {sev}")
                sections.append(f"Unread alerts: {', '.join(parts)} ({total_unread} total)")

            # -- Recent weather alerts (last 24h) --
            cursor = conn.execute(
                '''SELECT title FROM notifications
                   WHERE user_id = ? AND notification_type = 'weather_alert'
                     AND dismissed = 0
                     AND created_at >= DATE('now', '-1 days')
                   ORDER BY created_at DESC
                   LIMIT 3''',
                (user_id,),
            )
            weather_rows = cursor.fetchall()
            if weather_rows:
                titles = [r['title'] for r in weather_rows]
                sections.append("Weather: " + '; '.join(titles))
            else:
                sections.append("Weather: No active alerts")

            # -- Upcoming spray reminders --
            cursor = conn.execute(
                '''SELECT title FROM notifications
                   WHERE user_id = ? AND notification_type = 'spray_reminder'
                     AND dismissed = 0 AND read = 0
                   ORDER BY created_at DESC
                   LIMIT 3''',
                (user_id,),
            )
            spray_rows = cursor.fetchall()
            if spray_rows:
                titles = [r['title'] for r in spray_rows]
                sections.append("Spray reminders: " + '; '.join(titles))

            # -- Overdue tasks --
            cursor = conn.execute(
                '''SELECT title FROM notifications
                   WHERE user_id = ? AND notification_type = 'task_overdue'
                     AND dismissed = 0 AND read = 0
                   ORDER BY created_at DESC
                   LIMIT 3''',
                (user_id,),
            )
            task_rows = cursor.fetchall()
            if task_rows:
                titles = [r['title'] for r in task_rows]
                sections.append("Overdue tasks: " + '; '.join(titles))

    except Exception:
        logger.exception("Error building morning briefing for user %s", user_id)
        sections.append("Could not load all briefing data.")
    if not sections:
        sections.append("No pending alerts. Have a great day on the course!")

    date_label = now.strftime('%A, %B %d')
    message = '\n'.join(f"- {s}" for s in sections)

    return create_notification(
        user_id=user_id,
        title=f"Morning Briefing - {date_label}",
        message=message,
        notification_type='custom',
        severity='info',
        expires_at=(now + timedelta(hours=18)).strftime('%Y-%m-%d %H:%M:%S'),
    )