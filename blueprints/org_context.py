"""Organization context middleware and helpers for multi-tenancy."""

from functools import wraps
from flask import session, jsonify, g
import logging

logger = logging.getLogger(__name__)


def get_org_id():
    """Get the current organization ID from the session.

    Returns None if no organization is selected (single-user / legacy mode).
    """
    return session.get('org_id')


def org_required(f):
    """Decorator that requires an active organization in the session.

    Use on routes that need org-scoped data access.
    Falls back gracefully: if no org is set, returns user-scoped data.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        g.org_id = session.get('org_id')
        return f(*args, **kwargs)
    return decorated


def init_org_tables():
    """Create organizations and org_members tables if they don't exist."""
    from db import get_db

    with get_db() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS organizations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                slug TEXT UNIQUE NOT NULL,
                course_name TEXT,
                address TEXT,
                city TEXT,
                state TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active INTEGER DEFAULT 1
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS org_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                org_id INTEGER NOT NULL REFERENCES organizations(id),
                user_id INTEGER NOT NULL REFERENCES users(id),
                role TEXT DEFAULT 'member',
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(org_id, user_id)
            )
        ''')
    logger.info("Organization tables initialized")


def get_user_orgs(user_id):
    """Get all organizations a user belongs to."""
    from db import get_db

    with get_db() as conn:
        rows = conn.execute('''
            SELECT o.id, o.name, o.slug, o.course_name, o.city, o.state,
                   om.role, o.is_active
            FROM organizations o
            JOIN org_members om ON om.org_id = o.id
            WHERE om.user_id = ? AND o.is_active = 1
            ORDER BY o.name
        ''', (user_id,)).fetchall()
    return [dict(r) for r in rows]


def create_org(name, slug, user_id, course_name=None, city=None, state=None):
    """Create a new organization and make the creator an owner."""
    from db import get_db

    with get_db() as conn:
        cursor = conn.execute(
            '''INSERT INTO organizations (name, slug, course_name, city, state)
               VALUES (?, ?, ?, ?, ?)''',
            (name, slug, course_name, city, state)
        )
        org_id = cursor.lastrowid
        conn.execute(
            '''INSERT INTO org_members (org_id, user_id, role)
               VALUES (?, ?, 'owner')''',
            (org_id, user_id)
        )
    return org_id


def add_org_member(org_id, user_id, role='member'):
    """Add a user to an organization."""
    from db import get_db

    with get_db() as conn:
        conn.execute(
            '''INSERT OR IGNORE INTO org_members (org_id, user_id, role)
               VALUES (?, ?, ?)''',
            (org_id, user_id, role)
        )
    return True


def get_org_member_role(org_id, user_id):
    """Get a user's role in an organization. Returns None if not a member."""
    from db import get_db

    with get_db() as conn:
        row = conn.execute(
            'SELECT role FROM org_members WHERE org_id = ? AND user_id = ?',
            (org_id, user_id)
        ).fetchone()
    return row['role'] if row else None
