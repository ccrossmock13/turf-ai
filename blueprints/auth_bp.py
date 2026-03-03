"""Authentication blueprint — extracted from app.py."""

import time
from flask import Blueprint, render_template, jsonify, request, session, redirect
from config import Config
from logging_config import logger
from auth import (
    login_required, get_current_user, login_user_session,
    logout_user_session, create_user, authenticate_user
)
from profile import get_profile

auth = Blueprint('auth', __name__)

# -----------------------------------------------------------------------------
# Rate limiting — Redis-backed when available, in-memory fallback
# -----------------------------------------------------------------------------

_login_rate_redis = None
if Config.REDIS_URL:
    try:
        import redis as _redis_mod
        _login_rate_redis = _redis_mod.Redis.from_url(Config.REDIS_URL)
        _login_rate_redis.ping()
        logger.info("Login rate limiter using Redis")
    except Exception:
        _login_rate_redis = None

_login_attempts = {}  # Fallback: in-memory {ip: [timestamp, ...]}
_RATE_LIMIT_MAX = 5
_RATE_LIMIT_WINDOW = 300  # 5 minutes


def _check_rate_limit(ip):
    """Return True if the IP is rate-limited."""
    if _login_rate_redis:
        key = f"login_attempts:{ip}"
        count = _login_rate_redis.llen(key)
        return count >= _RATE_LIMIT_MAX
    now = time.time()
    attempts = _login_attempts.get(ip, [])
    attempts = [t for t in attempts if now - t < _RATE_LIMIT_WINDOW]
    _login_attempts[ip] = attempts
    return len(attempts) >= _RATE_LIMIT_MAX


def _record_attempt(ip):
    """Record a login/signup attempt for rate limiting."""
    if _login_rate_redis:
        key = f"login_attempts:{ip}"
        _login_rate_redis.rpush(key, str(time.time()))
        _login_rate_redis.expire(key, _RATE_LIMIT_WINDOW)
        return
    _login_attempts.setdefault(ip, []).append(time.time())


# -----------------------------------------------------------------------------
# Authentication routes
# -----------------------------------------------------------------------------

@auth.route('/login', methods=['GET'])
def login_page():
    if session.get('user_id'):
        return redirect('/')
    return render_template('login.html')


@auth.route('/signup', methods=['GET'])
def signup_page():
    if session.get('user_id'):
        return redirect('/')
    return render_template('signup.html')


@auth.route('/api/login', methods=['POST'])
def api_login():
    ip = request.remote_addr
    if _check_rate_limit(ip):
        return jsonify({'error': 'Too many login attempts. Please wait 5 minutes.'}), 429
    _record_attempt(ip)
    data = request.json or {}
    email = data.get('email', '').strip()
    password = data.get('password', '')
    if not email or not password:
        return jsonify({'error': 'Email and password required'}), 400
    user = authenticate_user(email, password)
    if user:
        login_user_session(user)
        return jsonify({'success': True, 'user': {'name': user['name'], 'email': user['email']}})
    return jsonify({'error': 'Invalid email or password'}), 401


@auth.route('/api/signup', methods=['POST'])
def api_signup():
    ip = request.remote_addr
    if _check_rate_limit(ip):
        return jsonify({'error': 'Too many signup attempts. Please wait 5 minutes.'}), 429
    _record_attempt(ip)
    data = request.json or {}
    email = data.get('email', '').strip()
    password = data.get('password', '')
    name = data.get('name', '').strip()
    if not email or not password or not name:
        return jsonify({'error': 'Name, email, and password required'}), 400
    if len(password) < 8:
        return jsonify({'error': 'Password must be at least 8 characters'}), 400
    try:
        user_id = create_user(email, password, name)
        user = {'id': user_id, 'name': name, 'email': email}
        login_user_session(user)
        return jsonify({'success': True, 'user': {'name': name, 'email': email}})
    except ValueError as e:
        return jsonify({'error': str(e)}), 409


@auth.route('/logout')
def logout():
    logout_user_session()
    return redirect('/login')


@auth.route('/api/register-push-token', methods=['POST'])
@login_required
def register_push_token():
    """Store device push notification token for Capacitor iOS app."""
    data = request.json or {}
    token = data.get('token')
    platform = data.get('platform', 'ios')
    if not token:
        return jsonify({'error': 'No token provided'}), 400

    user_id = session['user_id']
    try:
        from db import get_db as _get_db, add_column
        with _get_db() as conn:
            add_column(conn, 'users', 'push_token', 'TEXT')
            add_column(conn, 'users', 'push_platform', 'TEXT DEFAULT "ios"')
            conn.execute(
                'UPDATE users SET push_token = ?, push_platform = ? WHERE id = ?',
                (token, platform, user_id)
            )
        return jsonify({'status': 'registered'})
    except Exception as e:
        logger.error(f"Push token registration failed: {e}")
        return jsonify({'error': 'Registration failed'}), 500


@auth.route('/api/me')
def api_me():
    """Get current user info + profile for frontend."""
    user = get_current_user()
    if not user:
        from config import Config
        if Config.DEMO_MODE:
            user = {'id': 1, 'name': 'Demo User', 'email': 'demo@greenside.ai'}
        else:
            return jsonify({'authenticated': False}), 401
    profile = get_profile(user['id'])
    is_admin = False
    try:
        from db import get_db as _get_db
        with _get_db() as conn:
            row = conn.execute('SELECT is_admin FROM users WHERE id = ?', (user['id'],)).fetchone()
            is_admin = bool(row and row[0])
    except Exception:
        pass
    if not is_admin:
        from config import Config
        if Config.DEMO_MODE:
            is_admin = True
    user_data = dict(user)
    user_data['is_admin'] = is_admin
    return jsonify({
        'authenticated': True,
        'user': user_data,
        'profile': profile,
        'has_profile': profile is not None and (
            profile.get('primary_grass') is not None or profile.get('greens_grass') is not None
        )
    })
