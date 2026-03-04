"""Audit trail for compliance-critical operations (spray records, EPA)."""

import json
import logging

from flask import session

from db import get_db

logger = logging.getLogger(__name__)


def init_audit_tables():
    """Create the audit_log table if it doesn't exist."""
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                org_id INTEGER,
                user_id INTEGER,
                user_name TEXT,
                action TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id TEXT,
                details TEXT,
                ip_address TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    logger.info("Audit tables initialized")


def log_action(action, entity_type, entity_id=None, details=None, user_id=None):
    """Log an auditable action.

    Args:
        action: 'create', 'update', 'delete', 'export', 'approve'
        entity_type: 'spray_record', 'equipment', 'crew_member', etc.
        entity_id: ID of the affected entity
        details: dict with change details (old/new values)
        user_id: override user_id (defaults to session user)
    """
    try:
        from flask import request

        _user_id = user_id or session.get("user_id")
        _user_name = session.get("user_name", "System")
        _org_id = session.get("org_id")
        _ip = request.remote_addr if request else None
    except RuntimeError:
        _user_id = user_id
        _user_name = "System"
        _org_id = None
        _ip = None

    details_json = json.dumps(details) if details else None

    try:
        with get_db() as conn:
            conn.execute(
                """
                INSERT INTO audit_log
                    (org_id, user_id, user_name, action, entity_type, entity_id, details, ip_address)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    _org_id,
                    _user_id,
                    _user_name,
                    action,
                    entity_type,
                    str(entity_id) if entity_id else None,
                    details_json,
                    _ip,
                ),
            )
    except Exception as e:
        logger.warning(f"Audit log failed: {e}")


def get_audit_trail(entity_type=None, entity_id=None, user_id=None, start_date=None, end_date=None, limit=100):
    """Query the audit trail with optional filters.

    Returns:
        list of audit log entries (newest first)
    """
    query = "SELECT * FROM audit_log WHERE 1=1"
    params = []

    if entity_type:
        query += " AND entity_type = ?"
        params.append(entity_type)
    if entity_id:
        query += " AND entity_id = ?"
        params.append(str(entity_id))
    if user_id:
        query += " AND user_id = ?"
        params.append(user_id)
    if start_date:
        query += " AND created_at >= ?"
        params.append(start_date)
    if end_date:
        query += " AND created_at <= ?"
        params.append(end_date)

    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    with get_db() as conn:
        rows = conn.execute(query, params).fetchall()

    results = []
    for row in rows:
        entry = dict(row)
        if entry.get("details"):
            try:
                entry["details"] = json.loads(entry["details"])
            except (json.JSONDecodeError, TypeError):
                pass
        results.append(entry)
    return results
