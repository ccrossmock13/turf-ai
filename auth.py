"""
Authentication module for Greenside AI.
Handles user registration, login, session management, and route protection.
"""

import sqlite3
import os
import logging
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from flask import session, redirect, url_for, request, jsonify

logger = logging.getLogger(__name__)

DATA_DIR = os.environ.get('DATA_DIR', 'data' if os.path.exists('data') else '.')
DB_PATH = os.path.join(DATA_DIR, 'greenside_conversations.db')


# ---------------------------------------------------------------------------
# User CRUD
# ---------------------------------------------------------------------------

def create_user(email, password, name):
    """Create a new user. Returns user_id or raises ValueError."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        password_hash = generate_password_hash(password)
        cursor.execute(
            'INSERT INTO users (email, password_hash, name) VALUES (?, ?, ?)',
            (email.lower().strip(), password_hash, name.strip())
        )
        user_id = cursor.lastrowid
        conn.commit()
        return user_id
    except sqlite3.IntegrityError:
        raise ValueError("Email already registered")
    finally:
        conn.close()


def authenticate_user(email, password):
    """Verify credentials. Returns user dict or None."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        'SELECT id, email, password_hash, name FROM users WHERE email = ? AND is_active = 1',
        (email.lower().strip(),)
    )
    row = cursor.fetchone()
    conn.close()

    if row and check_password_hash(row[2], password):
        # Update last_login
        try:
            conn2 = sqlite3.connect(DB_PATH)
            conn2.execute('UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?', (row[0],))
            conn2.commit()
            conn2.close()
        except Exception as e:
            logger.warning(f"Failed to update last_login: {e}")
        return {'id': row[0], 'email': row[1], 'name': row[3]}
    return None


def get_user_by_id(user_id):
    """Get user by ID. Returns user dict or None."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        'SELECT id, email, name, created_at, last_login FROM users WHERE id = ?',
        (user_id,)
    )
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            'id': row[0], 'email': row[1], 'name': row[2],
            'created_at': row[3], 'last_login': row[4]
        }
    return None


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------

def login_user_session(user):
    """Set session after successful auth. Expires after 8 hours."""
    session.permanent = True
    session['user_id'] = user['id']
    session['user_name'] = user['name']
    session['user_email'] = user['email']


def logout_user_session():
    """Clear all session data."""
    session.pop('user_id', None)
    session.pop('user_name', None)
    session.pop('user_email', None)
    session.pop('session_id', None)
    session.pop('conversation_id', None)
    session.pop('last_topic', None)
    session.pop('last_subject', None)


def get_current_user():
    """Get current logged-in user from session. Returns dict or None."""
    user_id = session.get('user_id')
    if user_id:
        return {
            'id': user_id,
            'name': session.get('user_name'),
            'email': session.get('user_email')
        }
    return None


# ---------------------------------------------------------------------------
# Route protection
# ---------------------------------------------------------------------------

def login_required(f):
    """Decorator for routes that require authentication.
    - AJAX/JSON requests get 401 JSON response
    - Page requests get redirected to /login
    - Bypassed when DEMO_MODE is enabled
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            # Allow demo mode without login
            from config import Config
            if Config.DEMO_MODE:
                return f(*args, **kwargs)
            # AJAX requests get JSON 401
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': 'Authentication required', 'redirect': '/login'}), 401
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated_function
