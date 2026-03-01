"""
Authentication module for Greenside AI.
Handles user registration, login, session management, and route protection.
"""

import os
import logging
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from flask import session, redirect, url_for, request, jsonify
from db import get_db, get_integrity_error

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# User CRUD
# ---------------------------------------------------------------------------

def create_user(email, password, name):
    """Create a new user. Returns user_id or raises ValueError."""
    IntegrityError = get_integrity_error()
    try:
        password_hash = generate_password_hash(password)
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO users (email, password_hash, name) VALUES (?, ?, ?)',
                (email.lower().strip(), password_hash, name.strip())
            )
            user_id = cursor.lastrowid
            return user_id
    except IntegrityError:
        raise ValueError("Email already registered")


def authenticate_user(email, password):
    """Verify credentials. Returns user dict or None."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT id, email, password_hash, name FROM users WHERE email = ? AND is_active = 1',
            (email.lower().strip(),)
        )
        row = cursor.fetchone()

        if row and check_password_hash(row[2], password):
            # Update last_login within the same connection
            try:
                conn.execute('UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?', (row[0],))
            except Exception as e:
                logger.warning(f"Failed to update last_login: {e}")
            return {'id': row[0], 'email': row[1], 'name': row[3]}
        return None


def get_user_by_id(user_id):
    """Get user by ID. Returns user dict or None."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT id, email, name, created_at, last_login FROM users WHERE id = ?',
            (user_id,)
        )
        row = cursor.fetchone()
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
            # Allow demo mode without login — set user_id so routes
            # that access session['user_id'] directly don't crash
            from config import Config
            if Config.DEMO_MODE:
                session['user_id'] = 1
                return f(*args, **kwargs)
            # AJAX requests get JSON 401
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': 'Authentication required', 'redirect': '/login'}), 401
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Decorator for admin-only routes. Checks is_admin column on users table.
    In demo mode, user_id=1 is always treated as admin."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from config import Config
        user_id = session.get('user_id')
        if not user_id:
            if Config.DEMO_MODE:
                return f(*args, **kwargs)  # Demo mode: allow all admin access
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': 'Authentication required'}), 401
            return redirect('/login')
        with get_db() as conn:
            row = conn.execute('SELECT is_admin FROM users WHERE id = ?', (user_id,)).fetchone()
            if not row or not row[0]:
                if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'error': 'Admin access required'}), 403
                return redirect('/')
        return f(*args, **kwargs)
    return decorated_function
