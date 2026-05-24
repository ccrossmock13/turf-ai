from flask import Flask, render_template, jsonify, request, session, redirect, url_for, flash, abort, send_from_directory
from routes import turf_bp
import json
import os
import logging
import openai
import secrets
import shutil
import socket
import smtplib
import subprocess
import time
from datetime import datetime, timezone
from email.message import EmailMessage
from functools import wraps
from pathlib import Path
from typing import Any
from config import Config
from dotenv import load_dotenv
from pinecone import Pinecone
from logging_config import logger
from detection import detect_grass_type, detect_region, detect_product_need
from query_expansion import expand_query, expand_vague_question
from chat_history import (
    create_session, save_message, build_context_for_ai,
    calculate_confidence_score, get_confidence_label,
    get_conversation_history, set_conversation_account,
    export_account_conversations, delete_account_conversations,
)
from feedback_system import (
    retire_matching_open_kb_gaps,
    save_feedback as save_user_feedback,
    save_query,
    save_kb_gap,
    save_expert_router_event,
    update_query_rating,
)
from constants import (
    STATIC_FOLDERS, SEARCH_FOLDERS, DEFAULT_SOURCES,
    MAX_CONTEXT_LENGTH, MAX_SOURCES
)
from search_service import (
    detect_topic, detect_specific_subject, detect_state, get_embedding,
    search_all_parallel,
    deduplicate_sources, filter_display_sources
)
from scoring_service import score_results, safety_filter_results, build_context
from source_policy import public_product_label_resources, safe_public_resources
from query_rewriter import rewrite_query
from answer_grounding import check_answer_grounding, add_grounding_warning, calculate_grounding_confidence
from knowledge_base import enrich_context_with_knowledge, extract_product_names, extract_disease_names, load_products
from reranker import rerank_results, is_cross_encoder_available
from web_search import should_trigger_web_search, should_supplement_with_web_search, search_web_for_turf_info, format_web_search_disclaimer
from weather_service import get_weather_data, get_weather_context, get_weather_warnings, format_weather_for_response
from hallucination_filter import filter_hallucinations
from query_classifier import classify_query, get_response_for_category
from feasibility_gate import check_feasibility
from answer_validator import apply_validation
from demo_cache import find_demo_response
from advanced_diagnosis import answer_advanced_diagnosis
from advanced_turf_science import answer_advanced_turf_science
from expert_mode_router import route_expert_mode
from image_diagnosis import answer_image_diagnosis, validate_image_attachment
from safety_gate import apply_post_llm_safety_gate, get_pre_llm_safety_response
from verified_kb import (
    answer_from_verified_kb,
    answer_product_context_needed,
    recommend_verified_products_for_target,
    recommend_verified_products_for_surface_target,
)
from auth_store import (
    consume_email_verification_token,
    consume_password_reset_token,
    create_account,
    create_email_verification_token,
    create_password_reset_token,
    delete_account,
    get_account_by_email,
    get_account_by_id,
    get_email_verification_account,
    get_password_reset_account,
    update_account,
    verify_credentials,
)
from rate_limit_store import RATE_LIMIT_BUCKETS
from persistence_backend import dynamodb_table_exists
from course_profile import (
    apply_course_profile_updates,
    build_course_profile_kb_hint,
    build_current_management_snapshot,
    build_general_turf_guidance_response,
    build_operational_guidance_response,
    delete_course_profile,
    format_current_management_snapshot,
    format_course_profile_for_prompt,
    infer_regional_management_context,
    is_course_profile_only_update,
    load_course_profile,
    summarize_known_profile_for_questions,
    update_course_profile,
)

load_dotenv()

# Logging is configured in logging_config.py

app = Flask(__name__)
app.secret_key = Config.FLASK_SECRET_KEY
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=Config.APP_ENV == 'production',
    SESSION_COOKIE_NAME=Config.SESSION_COOKIE_NAME,
    PERMANENT_SESSION_LIFETIME=Config.session_lifetime(),
    MAX_CONTENT_LENGTH=max(10 * 1024 * 1024, Config.MAX_IMAGE_UPLOAD_BYTES * 2),
)
app.register_blueprint(turf_bp)
Config.validate_runtime()

_openai_client = None
_pinecone_client = None
_pinecone_index = None
_pinecone_unavailable_until = 0.0
_openai_unavailable_until = 0.0


def get_openai_client():
    global _openai_client
    if _openai_client is None:
        _openai_client = openai.OpenAI(api_key=Config.OPENAI_API_KEY)
    return _openai_client


def get_pinecone_client():
    global _pinecone_client
    if _pinecone_client is None:
        _pinecone_client = Pinecone(api_key=Config.PINECONE_API_KEY)
    return _pinecone_client


def get_pinecone_index():
    global _pinecone_index
    if _pinecone_index is None:
        _pinecone_index = get_pinecone_client().Index(Config.PINECONE_INDEX)
    return _pinecone_index


def get_pinecone_index_safe():
    """Return the Pinecone index when available, otherwise None for graceful degradation."""
    global _pinecone_unavailable_until, _pinecone_index
    now = time.time()
    if _pinecone_unavailable_until and now < _pinecone_unavailable_until:
        return None
    try:
        return get_pinecone_index()
    except Exception as exc:
        _pinecone_index = None
        _pinecone_unavailable_until = now + 60
        logger.warning("Pinecone unavailable; using degraded retrieval path for 60s: %s", exc)
        return None


def openai_requests_available() -> bool:
    """Return True when OpenAI DNS/network looks reachable, with a short outage cache."""
    global _openai_unavailable_until
    now = time.time()
    if _openai_unavailable_until and now < _openai_unavailable_until:
        return False
    try:
        socket.getaddrinfo("api.openai.com", 443)
        return True
    except OSError as exc:
        _openai_unavailable_until = now + 60
        logger.warning("OpenAI unavailable; using deterministic fallback path for 60s: %s", exc)
        return False


AUTH_SESSION_KEYS = {
    'account_id',
    'account_email',
    'account_role',
    'account_name',
    'account_org',
}
CSRF_SESSION_KEY = "_csrf_token"


def _get_csrf_token() -> str:
    token = session.get(CSRF_SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        session[CSRF_SESSION_KEY] = token
    return token


def _rotate_csrf_token() -> str:
    token = secrets.token_urlsafe(32)
    session[CSRF_SESSION_KEY] = token
    return token


def _is_safe_method() -> bool:
    return request.method in {"GET", "HEAD", "OPTIONS", "TRACE"}


def _should_enforce_csrf() -> bool:
    if _is_safe_method():
        return False
    if request.path in {"/health", "/ready"}:
        return False
    return True


def _rate_limit_key(scope: str) -> str:
    account = _current_account()
    identity = account.get("id") if account else request.headers.get("X-Forwarded-For", request.remote_addr or "anon")
    return f"{scope}:{identity}"


def _is_rate_limited(scope: str, *, limit: int, window_seconds: int) -> tuple[bool, int]:
    key = _rate_limit_key(scope)
    return RATE_LIMIT_BUCKETS.consume(scope, key, limit=limit, window_seconds=window_seconds)


def _rate_limit_response(scope: str, *, limit: int, window_seconds: int, html_template: str | None = None, template_context: dict | None = None):
    limited, retry_after = _is_rate_limited(scope, limit=limit, window_seconds=window_seconds)
    if not limited:
        return None
    message = f"Too many requests right now. Please wait about {retry_after} seconds and try again."
    if request.is_json or _is_json_request():
        response = jsonify({"success": False, "error": message, "retry_after": retry_after})
        response.status_code = 429
        response.headers["Retry-After"] = str(retry_after)
        return response
    flash(message, "error")
    response = render_template(html_template or "login.html", **(template_context or {}))
    return response, 429


def _local_sendmail_path() -> str | None:
    return shutil.which("sendmail")


def _mail_delivery_available() -> bool:
    if not Config.MAIL_FROM:
        return False
    return bool(Config.SMTP_HOST or _local_sendmail_path())


def _deliver_transactional_email(message: EmailMessage) -> bool:
    try:
        if Config.SMTP_HOST:
            with smtplib.SMTP(Config.SMTP_HOST, Config.SMTP_PORT, timeout=10) as smtp:
                if Config.SMTP_USE_TLS:
                    smtp.starttls()
                if Config.SMTP_USERNAME:
                    smtp.login(Config.SMTP_USERNAME, Config.SMTP_PASSWORD or "")
                smtp.send_message(message)
        else:
            sendmail_path = _local_sendmail_path()
            if not sendmail_path:
                return False
            subprocess.run(
                [sendmail_path, "-t", "-oi"],
                input=message.as_bytes(),
                capture_output=True,
                check=True,
            )
        return True
    except subprocess.CalledProcessError as exc:
        logger.warning(
            "Transactional email sendmail fallback failed with exit status %s.",
            exc.returncode,
        )
        return False
    except Exception:
        logger.exception("Failed to deliver transactional email.")
        return False


def _send_password_reset_email(email: str, reset_url: str) -> bool:
    if not _mail_delivery_available():
        return False
    message = EmailMessage()
    message["Subject"] = "Reset your Turf Management Intelligence password"
    message["From"] = Config.MAIL_FROM
    message["To"] = email
    message.set_content(
        "We received a request to reset your Turf Management Intelligence password.\n\n"
        f"Use this secure link to choose a new password:\n{reset_url}\n\n"
        "If you did not request this, you can ignore this email."
    )
    return _deliver_transactional_email(message)


def _send_email_verification_email(email: str, verify_url: str) -> bool:
    if not _mail_delivery_available():
        return False
    message = EmailMessage()
    message["Subject"] = "Verify your Turf Management Intelligence email"
    message["From"] = Config.MAIL_FROM
    message["To"] = email
    message.set_content(
        "Welcome.\n\n"
        f"Use this secure link to verify your email address:\n{verify_url}\n\n"
        "If you did not create this account, you can ignore this email."
    )
    return _deliver_transactional_email(message)


def _current_account():
    account_id = session.get('account_id')
    if not account_id:
        return None
    account = get_account_by_id(account_id)
    if not account:
        for key in AUTH_SESSION_KEYS:
            session.pop(key, None)
        return None
    return account


def _moderator_identity() -> str:
    account = _current_account() or {}
    return (
        account.get('email')
        or account.get('name')
        or account.get('id')
        or 'admin'
    )


def _login_account(account: dict):
    preserved = {
        key: session.get(key)
        for key in ('session_id', 'conversation_id', 'last_topic', 'last_subject')
        if session.get(key) is not None
    }
    session.clear()
    session.update(preserved)
    _rotate_csrf_token()
    session.permanent = True
    session['account_id'] = account['id']
    session['account_email'] = account['email']
    session['account_role'] = account.get('role', 'user')
    session['account_name'] = account.get('name', '')
    session['account_org'] = account.get('organization', '')


def _logout_account():
    for key in AUTH_SESSION_KEYS:
        session.pop(key, None)
    _rotate_csrf_token()


def _is_json_request() -> bool:
    return request.path.startswith('/admin/') or request.is_json or request.accept_mimetypes.best == 'application/json'


def _allow_public_admin_access() -> bool:
    return bool(Config.ALLOW_PUBLIC_ADMIN or Config.DEMO_MODE)


def login_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        account = _current_account()
        if account:
            if Config.REQUIRE_EMAIL_VERIFICATION and not account.get('email_verified_at'):
                _logout_account()
                if _is_json_request():
                    return jsonify({'error': 'Verify your email before signing in.'}), 403
                flash('Verify your email before signing in.', 'error')
                return redirect(url_for('login', next=request.path))
            return view_func(*args, **kwargs)
        if _is_json_request():
            return jsonify({'error': 'Authentication required.'}), 401
        return redirect(url_for('login', next=request.path))
    return wrapper


def admin_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if _allow_public_admin_access():
            return view_func(*args, **kwargs)
        account = _current_account()
        if not account:
            if _is_json_request():
                return jsonify({'error': 'Authentication required.'}), 401
            return redirect(url_for('login', next=request.path))
        if Config.REQUIRE_EMAIL_VERIFICATION and not account.get('email_verified_at'):
            if _is_json_request():
                return jsonify({'error': 'Verify your email before accessing admin tools.'}), 403
            flash('Verify your email before accessing admin tools.', 'error')
            return redirect(url_for('login', next=request.path))
        if account.get('role') != 'admin':
            if _is_json_request():
                return jsonify({'error': 'Admin access required.'}), 403
            return redirect(url_for('home'))
        return view_func(*args, **kwargs)
    return wrapper


@app.context_processor
def inject_auth_context():
    account = _current_account()
    public_admin = _allow_public_admin_access()
    return {
        'current_account': account,
        'is_admin': bool((account and account.get('role') == 'admin') or public_admin),
        'admin_readonly_mode': bool(public_admin and not account),
        'csrf_token': _get_csrf_token(),
    }


@app.before_request
def protect_admin_routes():
    if not request.path.startswith('/admin'):
        return None
    if _allow_public_admin_access():
        return None
    account = _current_account()
    if not account:
        if _is_json_request():
            return jsonify({'error': 'Authentication required.'}), 401
        return redirect(url_for('login', next=request.path))
    if Config.REQUIRE_EMAIL_VERIFICATION and not account.get('email_verified_at'):
        if _is_json_request():
            return jsonify({'error': 'Verify your email before accessing admin tools.'}), 403
        flash('Verify your email before accessing admin tools.', 'error')
        return redirect(url_for('login', next=request.path))
    if account.get('role') != 'admin':
        if _is_json_request():
            return jsonify({'error': 'Admin access required.'}), 403
        return redirect(url_for('home'))
    return None


@app.before_request
def protect_csrf():
    if not _should_enforce_csrf():
        return None

    request_token = (
        request.headers.get("X-CSRF-Token")
        or request.form.get("_csrf_token")
        or (request.get_json(silent=True) or {}).get("csrf_token")
    )
    if request_token and request_token == session.get(CSRF_SESSION_KEY):
        return None

    message = "Your session security check failed. Refresh the page and try again."
    if request.is_json or _is_json_request():
        return jsonify({"success": False, "error": message}), 400
    return message, 400


@app.after_request
def add_security_headers(response):
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
    response.headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")
    response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; img-src 'self' data: https:; style-src 'self' 'unsafe-inline'; "
        "script-src 'self' 'unsafe-inline'; connect-src 'self' https:; frame-ancestors 'none'; base-uri 'self'"
    )
    if request.path.startswith('/login') or request.path.startswith('/register') or request.path.startswith('/account') or request.path.startswith('/admin'):
        response.headers.setdefault("Cache-Control", "no-store")
    if Config.APP_ENV == "production":
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


def _request_json():
    """Return a safe JSON object for old admin/chat endpoints.

    Some older routes expect a dict-like payload and call ``.get(...)`` on it
    immediately. If a client sends a JSON array/string/number instead, we keep
    the app on the safe path by treating that as an empty object rather than
    letting the route blow up with an attribute error.
    """
    payload = request.get_json(silent=True)
    return payload if isinstance(payload, dict) else {}


def _normalize_id_list(value):
    """Return a cleaned list of string ids from a JSON payload value."""
    if not isinstance(value, list):
        return []
    normalized = []
    for item in value:
        if isinstance(item, (str, int)):
            cleaned = str(item).strip()
            if cleaned:
                normalized.append(cleaned)
    return normalized


def _coerce_int(value, default, *, minimum=None, maximum=None):
    try:
        coerced = int(value)
    except (TypeError, ValueError):
        coerced = default
    if minimum is not None:
        coerced = max(minimum, coerced)
    if maximum is not None:
        coerced = min(maximum, coerced)
    return coerced


def _format_profile_update_response(updates):
    """Build a short response when the user is only teaching course context."""
    labels = {
        'surfaces.greens': 'greens',
        'surfaces.tees': 'tees',
        'surfaces.fairways': 'fairways',
        'surfaces.rough': 'rough',
        'mowing_heights.greens': 'greens mowing height',
        'mowing_heights.tees': 'tees mowing height',
        'mowing_heights.fairways': 'fairways mowing height',
        'mowing_heights.rough': 'rough mowing height',
        'region': 'region',
        'soil': 'soil',
        'course_name': 'course',
        'preferred_products': 'preferred products',
        'products_to_avoid': 'products to avoid',
        'notes': 'notes',
    }
    parts = []
    for key, value in updates.items():
        label = labels.get(key, key)
        if isinstance(value, list):
            value = ', '.join(value)
        parts.append(f"{label}: {value}")
    return "Got it — I'll remember this for your course profile: " + "; ".join(parts) + "."


def _augment_course_profile(profile: dict | None = None) -> dict:
    """Attach inferred and date-aware management context to a saved profile."""
    base = dict(profile or {})
    base['inferred_context'] = infer_regional_management_context(base)
    base['current_management'] = build_current_management_snapshot(base)
    return base


def _course_profile_health(profile: dict | None = None) -> dict:
    profile = dict(profile or {})
    surfaces = dict(profile.get('surfaces') or {})
    mowing = dict(profile.get('mowing_heights') or {})

    checks = [
        bool(profile.get('region')),
        bool(profile.get('soil')),
        bool(surfaces.get('greens')),
        bool(surfaces.get('fairways')),
        bool(surfaces.get('tees') or surfaces.get('rough')),
        bool(mowing.get('greens')),
        bool(profile.get('notes')),
        bool(profile.get('preferred_products') or profile.get('products_to_avoid')),
    ]
    labels = [
        'Add a region.',
        'Add a soil/rootzone note.',
        'Add the greens surface.',
        'Add the fairways surface.',
        'Add tees or rough details.',
        'Add greens mowing height.',
        'Add at least one course note.',
        'Add product preferences or avoidances.',
    ]
    completed = sum(1 for item in checks if item)
    score = round((completed / len(checks)) * 100)
    if score >= 80:
        summary = 'Strong course context'
    elif score >= 50:
        summary = 'Usable but still thin'
    else:
        summary = 'Thin course context'
    missing = [label for ok, label in zip(checks, labels) if not ok]
    return {
        'score': score,
        'summary': summary,
        'completed': completed,
        'total': len(checks),
        'missing': missing[:5],
    }


def _kb_quality_dashboard_payload() -> dict:
    from feedback_system import (
        LABEL_REVIEWED_STATUSES,
        get_expert_router_stats,
        get_kb_candidates,
        get_kb_gap_stats,
        get_kb_gaps,
        get_kb_regression_tests,
    )
    from scripts.audit_structured_kb import EXPANDED_LABEL_FIELDS, run_audit

    audit = run_audit()
    summary = audit.get('summary', {})
    records = audit.get('records', [])
    products = load_products()
    regression_tests = get_kb_regression_tests(status='all', limit=250)
    gap_stats = get_kb_gap_stats()
    router_stats = get_expert_router_stats()
    open_gaps = get_kb_gaps(status='open', limit=200)
    candidates = get_kb_candidates(limit=250)

    product_total = sum(len(items) for items in products.values())
    review_status_counts = {}
    verification_counts = {}
    human_reviewed_records = 0
    machine_reviewed_records = 0
    for category_items in products.values():
        for info in category_items.values():
            review_status = info.get('label_review_status') or 'unknown'
            verification_status = info.get('verification_status') or 'unknown'
            review_status_counts[review_status] = review_status_counts.get(review_status, 0) + 1
            verification_counts[verification_status] = verification_counts.get(verification_status, 0) + 1
            if review_status in LABEL_REVIEWED_STATUSES:
                human_reviewed_records += 1
            if review_status.startswith('machine_'):
                machine_reviewed_records += 1

    field_coverage = summary.get('expanded_field_coverage', {})
    weak_fields = []
    for field in EXPANDED_LABEL_FIELDS:
        field_info = field_coverage.get(field, {})
        records_with_value = int(field_info.get('records_with_value', 0) or 0)
        pct = round((records_with_value / product_total) * 100, 1) if product_total else 0.0
        weak_fields.append({
            'field': field,
            'records_with_value': records_with_value,
            'coverage_percent': pct,
        })
    weak_fields.sort(key=lambda item: (item['coverage_percent'], item['field']))

    regression_total = len(regression_tests)
    regression_with_results = [item for item in regression_tests if item.get('last_result')]
    regression_pass = [
        item for item in regression_with_results
        if item['last_result'].get('matches_expected_verdict') is True
    ]
    regression_fail = [
        item for item in regression_with_results
        if item['last_result'].get('matches_expected_verdict') is False
    ]
    regression_never_run = [item for item in regression_tests if not item.get('last_result')]
    deduped_regression_fail = _dedupe_regression_items([
        {
            'id': item.get('id'),
            'question': item.get('question'),
            'expected_kb_verdict': item.get('expected_kb_verdict'),
            'actual_kb_verdict': (item.get('last_result') or {}).get('actual_kb_verdict'),
            'last_run_at': item.get('last_run_at'),
        }
        for item in regression_fail
    ])
    deduped_regression_never_run = _dedupe_regression_items([
        {
            'id': item.get('id'),
            'question': item.get('question'),
            'expected_kb_verdict': item.get('expected_kb_verdict'),
            'actual_kb_verdict': None,
        }
        for item in regression_never_run
    ])

    stale_open_gaps = []
    actionable_open_gaps = []
    for gap in open_gaps:
        current_verdict = _current_kb_verdict_for_question(gap.get('question') or '')
        gap['current_kb_verdict'] = current_verdict
        if current_verdict and current_verdict != gap.get('kb_verdict'):
            stale_open_gaps.append(gap)
            continue
        actionable_open_gaps.append(gap)

    def _counts_toward_trust_gate(gap: dict) -> bool:
        notes = str(gap.get('notes') or '').lower()
        if 'synthetic open kb gap' in notes:
            return False
        gap_type = gap.get('gap_type') or ''
        current_verdict = gap.get('current_kb_verdict') or gap.get('kb_verdict')
        if gap_type == 'surface_restriction' and current_verdict == 'surface_restricted':
            return False
        if gap_type == 'product_target_not_verified' and current_verdict == 'not_verified':
            return False
        return True

    trust_blocking_open_gaps = [gap for gap in actionable_open_gaps if _counts_toward_trust_gate(gap)]

    stale_open_gaps = sorted(
        stale_open_gaps,
        key=lambda item: item.get('created_at') or '',
        reverse=True,
    )

    top_open_gaps = sorted(
        actionable_open_gaps,
        key=lambda item: (
            0 if (item.get('kb_verdict') or '').startswith('not_verified') else 1,
            0 if item.get('gap_type') == 'surface_target_product' else 1,
            item.get('created_at') or '',
        ),
        reverse=True,
    )[:8]

    risky_records = [
        {
            'category': record.get('category'),
            'active_ingredient': record.get('active_ingredient'),
            'trade_names': record.get('trade_names', []),
            'warnings': record.get('warnings', []),
            'label_candidate': record.get('label_candidate'),
        }
        for record in records
        if record.get('warnings')
    ][:8]

    candidate_status_counts = {}
    for candidate in candidates:
        status = candidate.get('status') or 'unknown'
        candidate_status_counts[status] = candidate_status_counts.get(status, 0) + 1

    return {
        'summary': {
            'products': product_total,
            'human_reviewed_products': human_reviewed_records,
            'machine_reviewed_products': machine_reviewed_records,
            'human_review_coverage_percent': round((human_reviewed_records / product_total) * 100, 1) if product_total else 0.0,
            'records_with_no_warnings': summary.get('records_with_no_warnings', 0),
            'warning_records': sum(1 for record in records if record.get('warnings')),
            'open_kb_gaps': len(actionable_open_gaps),
            'trust_blocking_open_kb_gaps': len(trust_blocking_open_gaps),
            'stale_open_kb_gaps': len(stale_open_gaps),
            'router_needs_review': router_stats.get('needs_review', 0),
            'regression_total': regression_total,
            'regression_passed': len(regression_pass),
            'regression_failed': len(deduped_regression_fail),
            'regression_never_run': len(deduped_regression_never_run),
        },
        'review_status_counts': review_status_counts,
        'verification_counts': verification_counts,
        'candidate_status_counts': candidate_status_counts,
        'all_fields': weak_fields,
        'weak_fields': weak_fields[:6],
        'top_warning_counts': [
            {'warning': key, 'count': count}
            for key, count in sorted((summary.get('warnings') or {}).items(), key=lambda item: (-item[1], item[0]))
        ],
        'top_open_gaps': top_open_gaps,
        'risky_records': risky_records,
        'stale_open_gaps': [
            {
                'id': item.get('id'),
                'question': item.get('question'),
                'kb_verdict': item.get('kb_verdict'),
                'current_kb_verdict': item.get('current_kb_verdict'),
            }
            for item in stale_open_gaps[:8]
        ],
        'failing_regressions': deduped_regression_fail[:8],
        'never_run_regressions': deduped_regression_never_run[:8],
    }


def _kb_trust_gate_payload(kb_quality: dict | None = None) -> dict:
    kb_quality = kb_quality or _kb_quality_dashboard_payload()
    summary = kb_quality.get('summary', {})
    field_coverage_map = {
        item.get('field'): float(item.get('coverage_percent') or 0.0)
        for item in kb_quality.get('weak_fields', [])
    }
    if not field_coverage_map:
        field_coverage_map = {}
    for item in kb_quality.get('all_fields', []):
        field_coverage_map[item.get('field')] = float(item.get('coverage_percent') or 0.0)

    thresholds = {
        'human_review_coverage_percent': Config.KB_TRUST_MIN_HUMAN_REVIEW_PERCENT,
        'rei_coverage_percent': Config.KB_TRUST_MIN_REI_COVERAGE_PERCENT,
        'irrigation_guidance_coverage_percent': Config.KB_TRUST_MIN_IRRIGATION_COVERAGE_PERCENT,
        'tank_mix_guidance_coverage_percent': Config.KB_TRUST_MIN_TANK_MIX_COVERAGE_PERCENT,
        'max_rate_per_app_coverage_percent': Config.KB_TRUST_MIN_MAX_RATE_COVERAGE_PERCENT,
        'warning_records_max': 0,
        'open_kb_gaps_max': 0,
    }
    actuals = {
        'human_review_coverage_percent': float(summary.get('human_review_coverage_percent') or 0.0),
        'rei_coverage_percent': field_coverage_map.get('rei', 0.0),
        'irrigation_guidance_coverage_percent': field_coverage_map.get('irrigation_guidance', 0.0),
        'tank_mix_guidance_coverage_percent': field_coverage_map.get('tank_mix_guidance', 0.0),
        'max_rate_per_app_coverage_percent': field_coverage_map.get('max_rate_per_app', 0.0),
        'warning_records': int(summary.get('warning_records') or 0),
        'open_kb_gaps': int(
            summary['trust_blocking_open_kb_gaps']
            if 'trust_blocking_open_kb_gaps' in summary
            else summary.get('open_kb_gaps') or 0
        ),
    }

    checks = [
        {
            'key': 'human_review_coverage_percent',
            'label': 'Human-reviewed product coverage',
            'actual': actuals['human_review_coverage_percent'],
            'threshold': thresholds['human_review_coverage_percent'],
            'passed': actuals['human_review_coverage_percent'] >= thresholds['human_review_coverage_percent'],
        },
        {
            'key': 'rei_coverage_percent',
            'label': 'REI coverage',
            'actual': actuals['rei_coverage_percent'],
            'threshold': thresholds['rei_coverage_percent'],
            'passed': actuals['rei_coverage_percent'] >= thresholds['rei_coverage_percent'],
        },
        {
            'key': 'irrigation_guidance_coverage_percent',
            'label': 'Irrigation guidance coverage',
            'actual': actuals['irrigation_guidance_coverage_percent'],
            'threshold': thresholds['irrigation_guidance_coverage_percent'],
            'passed': actuals['irrigation_guidance_coverage_percent'] >= thresholds['irrigation_guidance_coverage_percent'],
        },
        {
            'key': 'tank_mix_guidance_coverage_percent',
            'label': 'Tank-mix guidance coverage',
            'actual': actuals['tank_mix_guidance_coverage_percent'],
            'threshold': thresholds['tank_mix_guidance_coverage_percent'],
            'passed': actuals['tank_mix_guidance_coverage_percent'] >= thresholds['tank_mix_guidance_coverage_percent'],
        },
        {
            'key': 'max_rate_per_app_coverage_percent',
            'label': 'Max rate per application coverage',
            'actual': actuals['max_rate_per_app_coverage_percent'],
            'threshold': thresholds['max_rate_per_app_coverage_percent'],
            'passed': actuals['max_rate_per_app_coverage_percent'] >= thresholds['max_rate_per_app_coverage_percent'],
        },
        {
            'key': 'warning_records',
            'label': 'Structured KB warning records',
            'actual': actuals['warning_records'],
            'threshold': thresholds['warning_records_max'],
            'passed': actuals['warning_records'] <= thresholds['warning_records_max'],
        },
        {
            'key': 'open_kb_gaps',
            'label': 'Open KB gaps',
            'actual': actuals['open_kb_gaps'],
            'threshold': thresholds['open_kb_gaps_max'],
            'passed': actuals['open_kb_gaps'] <= thresholds['open_kb_gaps_max'],
        },
    ]
    failed_checks = [item for item in checks if not item['passed']]
    return {
        'status': 'pass' if not failed_checks else 'fail',
        'enforced': Config.ENFORCE_KB_TRUST_GATE,
        'checks': checks,
        'failed_checks': failed_checks,
        'summary': {
            'passed_checks': len(checks) - len(failed_checks),
            'total_checks': len(checks),
            'human_review_coverage_percent': actuals['human_review_coverage_percent'],
        },
    }


APP_ROOT = Path(__file__).resolve().parent
EVAL_CACHE_PATH = Path(Config.DATA_DIR) / "eval_dashboard_cache.json"
EVAL_CACHE_TTL_SECONDS = 300
EVAL_HISTORY_LIMIT = 12


def _read_eval_dashboard_cache() -> dict:
    try:
        if not EVAL_CACHE_PATH.exists():
            return {}
        return json.loads(EVAL_CACHE_PATH.read_text(encoding='utf-8'))
    except Exception:
        return {}


def _write_eval_dashboard_cache(payload: dict) -> None:
    try:
        EVAL_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        EVAL_CACHE_PATH.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    except Exception as exc:
        logger.warning(f"Could not persist eval dashboard cache: {exc}")


def _run_eval_suite(module_name: str, case_path: str) -> dict:
    if module_name == 'scripts.run_general_turf_eval':
        from scripts.run_general_turf_eval import load_cases, run_eval
    elif module_name == 'scripts.run_anti_slop_eval':
        from scripts.run_anti_slop_eval import load_cases, run_eval
    elif module_name == 'scripts.run_ambiguity_eval':
        from scripts.run_ambiguity_eval import load_cases, run_eval
    elif module_name == 'scripts.run_comprehensive_100_eval':
        from scripts.run_comprehensive_100_eval import load_cases, run_eval
    elif module_name == 'scripts.run_no_account_turf_eval':
        from scripts.run_no_account_turf_eval import load_cases, run_eval
    elif module_name == 'scripts.run_context_switch_eval':
        from scripts.run_context_switch_eval import load_cases, run_eval
    elif module_name == 'scripts.run_phd_turf_eval':
        from scripts.run_phd_turf_eval import load_cases, run_eval
    elif module_name == 'scripts.run_product_label_eval':
        from scripts.run_product_label_eval import load_cases, run_eval
    else:
        from scripts.run_image_eval import load_cases, run_eval
    if module_name == 'scripts.run_comprehensive_100_eval':
        return run_eval(load_cases())
    return run_eval(load_cases(Path(case_path)))


def _fresh_eval_dashboard_payload() -> dict:
    """Run the curated eval suites and summarize current quality health."""
    suite_reports = []
    failing_cases = []
    total_cases = 0
    total_passed = 0
    total_failed = 0

    # Keep the admin dashboard aligned with the handoff quality story: one broad
    # regression sweep, plus the narrower families that catch specific behavior drift.
    suites = [
        ('general_turf', 'General Turf', 'scripts.run_general_turf_eval', APP_ROOT / 'scripts' / 'general_turf_eval_cases.json'),
        ('anti_slop', 'Anti-Slop', 'scripts.run_anti_slop_eval', APP_ROOT / 'scripts' / 'anti_slop_eval_cases.json'),
        ('ambiguity', 'Ambiguity', 'scripts.run_ambiguity_eval', APP_ROOT / 'scripts' / 'ambiguity_eval_cases.json'),
        ('comprehensive_100', 'Comprehensive 100', 'scripts.run_comprehensive_100_eval', APP_ROOT / 'scripts' / 'run_comprehensive_100_eval.py'),
        ('no_account', 'No-Account', 'scripts.run_no_account_turf_eval', APP_ROOT / 'scripts' / 'no_account_turf_eval_cases.json'),
        ('context_switch', 'Context Switch', 'scripts.run_context_switch_eval', APP_ROOT / 'scripts' / 'context_switch_eval_cases.json'),
        ('phd_turf', 'PhD Turf', 'scripts.run_phd_turf_eval', APP_ROOT / 'scripts' / 'phd_turf_eval_cases.json'),
        ('product_label', 'Product / Label', 'scripts.run_product_label_eval', APP_ROOT / 'scripts' / 'product_label_eval_cases.json'),
        ('image', 'Image', 'scripts.run_image_eval', APP_ROOT / 'scripts' / 'image_eval_cases.json'),
    ]

    for key, label, module_name, case_path in suites:
        try:
            report = _run_eval_suite(module_name, str(case_path))
            summary = report.get('summary') or report
            cases = int(summary.get('cases', 0) or 0)
            passed = int(summary.get('passed', 0) or 0)
            failed = int(summary.get('failed', 0) or 0)
            pass_rate = round((passed / cases) * 100, 1) if cases else 0.0

            suite_failures = []
            for item in report.get('results', []):
                if item.get('passed'):
                    continue
                failure_messages = item.get('failures') or item.get('reasons') or []
                failure_entry = {
                    'suite': label,
                    'id': item.get('id'),
                    'question': item.get('question'),
                    'kb_verdict': item.get('kb_verdict'),
                    'selected_mode': item.get('selected_mode') or item.get('mode'),
                    'confidence_label': item.get('confidence_label') or item.get('confidence'),
                    'failures': failure_messages,
                }
                suite_failures.append(failure_entry)
                failing_cases.append(failure_entry)

            suite_reports.append({
                'key': key,
                'label': label,
                'cases': cases,
                'passed': passed,
                'failed': failed,
                'pass_rate': pass_rate,
                'failing_cases': suite_failures,
            })
            total_cases += cases
            total_passed += passed
            total_failed += failed
        except Exception as exc:
            error_text = str(exc)
            suite_reports.append({
                'key': key,
                'label': label,
                'cases': 0,
                'passed': 0,
                'failed': 0,
                'pass_rate': 0.0,
                'error': error_text,
                'failing_cases': [],
            })
            failing_cases.append({
                'suite': label,
                'id': f'{key}_eval_error',
                'question': 'Eval suite failed to run',
                'kb_verdict': None,
                'selected_mode': None,
                'confidence_label': None,
                'failures': [error_text],
            })

    run_at = datetime.now(timezone.utc).isoformat()
    return {
        'summary': {
            'suite_count': len(suite_reports),
            'cases': total_cases,
            'passed': total_passed,
            'failed': total_failed,
            'pass_rate': round((total_passed / total_cases) * 100, 1) if total_cases else 0.0,
            'run_at': run_at,
            'cached': False,
        },
        'suites': suite_reports,
        'failing_cases': failing_cases[:12],
    }


def _eval_dashboard_payload(force_refresh: bool = False) -> dict:
    """Return cached eval summaries when fresh, else rerun and persist a short history."""
    now = time.time()
    cache_payload = _read_eval_dashboard_cache()
    history = cache_payload.get('history', []) if isinstance(cache_payload, dict) else []
    latest = cache_payload.get('latest', {}) if isinstance(cache_payload, dict) else {}

    latest_run_at = latest.get('summary', {}).get('run_at') if isinstance(latest, dict) else None
    if latest_run_at and not force_refresh:
        try:
            last_ts = datetime.fromisoformat(latest_run_at).timestamp()
            if (now - last_ts) < EVAL_CACHE_TTL_SECONDS:
                cached = dict(latest)
                cached_summary = dict(cached.get('summary', {}))
                cached_summary['cached'] = True
                cached_summary['age_seconds'] = round(now - last_ts, 1)
                cached['summary'] = cached_summary
                cached['history'] = history[:EVAL_HISTORY_LIMIT]
                return cached
        except Exception:
            pass

    fresh = _fresh_eval_dashboard_payload()
    history_entry = {
        'run_at': fresh['summary'].get('run_at'),
        'suite_count': fresh['summary'].get('suite_count', 0),
        'cases': fresh['summary'].get('cases', 0),
        'passed': fresh['summary'].get('passed', 0),
        'failed': fresh['summary'].get('failed', 0),
        'pass_rate': fresh['summary'].get('pass_rate', 0.0),
    }
    next_history = [history_entry, *history][:EVAL_HISTORY_LIMIT]
    cache_to_write = {
        'latest': fresh,
        'history': next_history,
    }
    _write_eval_dashboard_cache(cache_to_write)
    fresh['history'] = next_history
    return fresh

def _text_list_from_value(value, *, separator_pattern=r',|;'):
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if value is None:
        return []
    import re
    return [item.strip() for item in re.split(separator_pattern, str(value)) if item.strip()]


def _account_course_profile_payload(payload) -> dict:
    return {
        'region': payload.get('region', ''),
        'soil': payload.get('soil', ''),
        'surfaces': {
            'greens': payload.get('greens_surface', ''),
            'fairways': payload.get('fairways_surface', ''),
            'tees': payload.get('tees_surface', ''),
            'rough': payload.get('rough_surface', ''),
        },
        'mowing_heights': {
            'greens': payload.get('greens_mowing_height', ''),
        },
        'preferred_products': _text_list_from_value(payload.get('preferred_products')),
        'products_to_avoid': _text_list_from_value(payload.get('products_to_avoid')),
        'notes': _text_list_from_value(payload.get('course_notes')),
    }


def _current_account_profile() -> dict:
    return _augment_course_profile(load_course_profile(_get_profile_key()))


def _account_export_payload(account: dict) -> dict:
    profile = _current_account_profile()
    conversations = export_account_conversations(account["id"])
    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "account": account,
        "course_profile": profile,
        "profile_health": _course_profile_health(profile),
        "conversations": conversations,
        "summary": {
            "conversation_count": len(conversations),
            "message_count": sum(len(item.get("messages", [])) for item in conversations),
        },
    }


def _record_kb_gap_if_needed(question: str, response: dict, feedback_id=None):
    """Turn unsupported/restricted KB verdicts into admin work items."""
    verdict = response.get('kb_verdict')
    gap_verdicts = {'not_verified', 'surface_restricted', 'no_verified_recommendation'}
    if verdict not in gap_verdicts:
        if verdict in {'known_no_verified_selective_control', 'needs_more_context', 'verified_surface_target_options'}:
            retire_matching_open_kb_gaps(
                question,
                notes='Retired automatically after deterministic handling replaced this as an active KB gap.',
            )
        return None
    return save_kb_gap(
        feedback_id=feedback_id,
        question=question,
        ai_answer=response.get('answer'),
        kb_verdict=verdict,
        product=response.get('product'),
        target=response.get('target'),
        surface=response.get('surface'),
        turf=response.get('turf'),
        notes='Auto-created from deterministic KB guardrail.',
    )


def _current_kb_verdict_for_question(question: str) -> str | None:
    course_profile = {}
    course_profile_context = format_course_profile_for_prompt(profile=course_profile)

    for responder in (
        lambda: answer_from_verified_kb(question, course_profile_context),
        lambda: recommend_verified_products_for_surface_target(question, course_profile),
        lambda: answer_product_context_needed(question, course_profile),
        lambda: answer_advanced_diagnosis(question, course_profile),
        lambda: answer_advanced_turf_science(question, course_profile),
    ):
        response = responder()
        if response and response.get('kb_verdict'):
            return response.get('kb_verdict')
    return None


def _dedupe_regression_items(items: list[dict]) -> list[dict]:
    seen = set()
    deduped = []
    for item in items:
        key = (
            item.get('question'),
            item.get('expected_kb_verdict'),
            item.get('actual_kb_verdict'),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _feedback_attachment_payload(image_attachment: dict | None) -> dict | None:
    if not image_attachment:
        return None
    data_url = str(image_attachment.get('data_url') or '').strip()
    if not data_url.startswith('data:image/'):
        return None
    return {
        'kind': 'uploaded_image',
        'name': image_attachment.get('name') or 'turf-image',
        'mime_type': image_attachment.get('mime_type') or '',
        'size_bytes': image_attachment.get('size_bytes'),
        'data_url': data_url,
    }


def _attach_feedback_id(response: dict | None, feedback_id: int | str | None) -> dict | None:
    """Thread the saved feedback row id back to the chat client."""
    if isinstance(response, dict) and feedback_id is not None:
        response['feedback_id'] = feedback_id
    return response


def _save_expert_response(conversation_id: str, question: str, response: dict, attachment: dict | None = None) -> int | None:
    """Persist deterministic expert responses consistently."""
    save_message(conversation_id, 'user', question)
    save_message(
        conversation_id,
        'assistant',
        response['answer'],
        sources=response.get('sources'),
        confidence_score=response.get('confidence', {}).get('score'),
    )
    return save_query(
        question=question,
        ai_answer=response['answer'],
        sources=response.get('sources', []),
        confidence=response.get('confidence', {}).get('score', 0),
        needs_review=response.get('needs_review', False),
        attachment=attachment,
    )


def _log_expert_router_event(question: str, router_decision: dict | None, resolved_mode: str, response: dict | None = None):
    """Persist router telemetry for expert/admin review."""
    if not router_decision:
        return None
    response = response or {}
    selected_mode = router_decision.get('mode', 'general')
    gap_verdicts = {'not_verified', 'surface_restricted', 'no_verified_recommendation'}
    verdict_requires_review = response.get('kb_verdict') in gap_verdicts
    needs_review = (
        resolved_mode == 'general' and selected_mode != 'general'
    ) or (
        resolved_mode != 'general' and selected_mode != resolved_mode
    ) or verdict_requires_review
    notes = None
    if resolved_mode == 'general' and selected_mode != 'general':
        notes = 'Router expected an expert mode, but the request fell through to the general path.'
    elif resolved_mode != 'general' and selected_mode != resolved_mode:
        notes = f'Router fell back from {selected_mode} to {resolved_mode}.'
    elif verdict_requires_review:
        notes = 'The router answered deterministically, but the result exposed a KB coverage gap that needs follow-up.'

    return save_expert_router_event(
        question=question,
        selected_mode=selected_mode,
        resolved_mode=resolved_mode,
        attempted_modes=router_decision.get('attempted_modes', []),
        fallback_mode=router_decision.get('fallback_mode'),
        router_confidence=router_decision.get('router_confidence'),
        matched_signals=router_decision.get('matched_signals', []),
        scores=router_decision.get('scores', {}),
        response_kb_verdict=response.get('kb_verdict'),
        used_deterministic=resolved_mode != 'general',
        needs_review=needs_review,
        notes=notes,
    )


def _try_expert_mode(mode: str, question: str, course_profile: dict, course_profile_context: str):
    """Attempt one deterministic expert mode."""
    if mode == 'verified_product':
        return (
            answer_from_verified_kb(question, course_profile_context)
            or recommend_verified_products_for_surface_target(question, course_profile)
            or recommend_verified_products_for_target(question, course_profile)
        )
    if mode == 'advanced_diagnosis':
        return answer_advanced_diagnosis(question, course_profile)
    if mode == 'advanced_turf_science':
        return answer_advanced_turf_science(question, course_profile)
    if mode == 'general_turf_guidance':
        return build_general_turf_guidance_response(question, profile=course_profile)
    return None


def _should_defer_early_verified_product_path(router_decision: dict | None) -> bool:
    """Let stronger deterministic diagnosis routing run before product shortcuts."""
    if not isinstance(router_decision, dict):
        return False
    return router_decision.get('mode') == 'advanced_diagnosis'


def _should_apply_profile_kb_hint(question: str, question_topic: str | None = None) -> bool:
    """Use inferred regional hints for questions that benefit from seasonal/regional context."""
    q = (question or "").lower()
    hint_terms = (
        "this month", "this season", "right now", "right now", "spring", "summer",
        "fall", "autumn", "winter", "season", "seasonal", "calendar", "pressure",
        "scout", "scouting", "priority", "priorities", "focus on", "what should we do",
        "what should i do", "regional", "region", "climate",
    )
    if any(term in q for term in hint_terms):
        return True
    return question_topic in {"cultural", "irrigation", "diagnostic"}


# -----------------------------------------------------------------------------
# Static file routes
# -----------------------------------------------------------------------------

@app.route('/')
def home():
    profile = _augment_course_profile(load_course_profile(_get_profile_key()))
    return render_template(
        'index.html',
        initial_course_profile=profile,
        initial_profile_health=_course_profile_health(profile),
        max_image_upload_bytes=Config.MAX_IMAGE_UPLOAD_BYTES,
    )


@app.route('/epa_labels/<path:filename>')
def serve_epa_label(filename):
    abort(404)


@app.route('/product-labels/<path:filename>')
def serve_product_label(filename):
    return send_from_directory('static/product-labels', filename)


@app.route('/solution-sheets/<path:filename>')
def serve_solution_sheet(filename):
    abort(404)


@app.route('/spray-programs/<path:filename>')
def serve_spray_program(filename):
    abort(404)


@app.route('/ntep-pdfs/<path:filename>')
def serve_ntep(filename):
    abort(404)


def _collect_resources():
    return public_product_label_resources() + safe_public_resources()


@app.route('/resources')
def resources():
    initial_resources = []
    try:
        initial_resources = _collect_resources()
    except Exception as e:
        logger.error(f"Error reading PDF folders for resources page: {e}")
    return render_template('resources.html', initial_resources=initial_resources)


@app.route('/api/resources')
def get_resources():
    try:
        resources_list = _collect_resources()
    except Exception as e:
        logger.error(f"Error reading PDF folders: {e}")
        return jsonify({'error': str(e)}), 500
    return jsonify(resources_list)


# -----------------------------------------------------------------------------
# Main AI endpoint
# -----------------------------------------------------------------------------

@app.route('/ask', methods=['POST'])
def ask():
    try:
        logging.debug('Received a question request.')
        rate_limited = _rate_limit_response("ask", limit=60, window_seconds=60)
        if rate_limited:
            return rate_limited
        body = _request_json()
        image_validation = validate_image_attachment(body.get('attachment'), max_bytes=Config.MAX_IMAGE_UPLOAD_BYTES)
        if not image_validation.get('ok'):
            return jsonify({
                'answer': image_validation.get('error', "The uploaded image could not be processed."),
                'sources': [],
                'confidence': {'score': 0, 'label': 'Image Upload Problem'},
                'kb_verdict': 'image_upload_invalid',
            }), 400
        image_attachment = image_validation.get('attachment')
        feedback_attachment = _feedback_attachment_payload(image_attachment)
        question = body.get('question', '').strip()
        if not question and not image_attachment:
            return jsonify({
                'answer': "Please enter a question about turfgrass management or attach a turf image.",
                'sources': [],
                'confidence': {'score': 0, 'label': 'No Question'}
            })
        if not question and image_attachment:
            question = "Please assess this turf image."
        logging.debug(f'Question: {question}')

        # Session management happens before course memory so saved profile details
        # cannot leak between browsers/users.
        conversation_id = _get_or_create_conversation()
        profile_key = _get_profile_key()
        course_profile = load_course_profile(profile_key)

        profile_updates = apply_course_profile_updates(question, profile_key=profile_key)
        if is_course_profile_only_update(question, profile_updates):
            return jsonify({
                'answer': _format_profile_update_response(profile_updates),
                'sources': [{
                    'name': 'Course Profile Memory',
                    'type': 'course_profile',
                    'note': 'Saved user-provided course context'
                }],
                'confidence': {'score': 100, 'label': 'Course Profile Updated'}
            })

        operational_guidance = build_operational_guidance_response(question, profile=course_profile)
        if operational_guidance:
            save_message(conversation_id, 'user', question)
            save_message(
                conversation_id,
                'assistant',
                operational_guidance['answer'],
                sources=operational_guidance.get('sources'),
                confidence_score=operational_guidance.get('confidence', {}).get('score'),
            )
            feedback_id = save_query(
                question=question,
                ai_answer=operational_guidance['answer'],
                sources=operational_guidance.get('sources', []),
                confidence=operational_guidance.get('confidence', {}).get('score', 0),
                needs_review=operational_guidance.get('needs_review', False),
            )
            return jsonify(_attach_feedback_id(operational_guidance, feedback_id))

        general_guidance_router_decision = route_expert_mode(question, course_profile)
        general_turf_guidance = (
            build_general_turf_guidance_response(question, profile=course_profile)
            if general_guidance_router_decision.get('mode') == 'general_turf_guidance'
            else None
        )
        if general_turf_guidance:
            general_turf_guidance['expert_router'] = {
                **general_guidance_router_decision,
                'attempted_modes': ['general_turf_guidance'],
                'selected_mode': 'general_turf_guidance',
            }
            feedback_id = _save_expert_response(conversation_id, question, general_turf_guidance)
            _log_expert_router_event(
                question,
                general_turf_guidance['expert_router'],
                resolved_mode='general_turf_guidance',
                response=general_turf_guidance,
            )
            _record_kb_gap_if_needed(question, general_turf_guidance, feedback_id=feedback_id)
            return jsonify(_attach_feedback_id(general_turf_guidance, feedback_id))

        openai_available = openai_requests_available()
        openai_client = get_openai_client() if openai_available else None

        if image_attachment and not openai_available:
            image_offline = {
                'answer': (
                    "**Bottom Line:** I cannot run the image-analysis model right now because live model connectivity is unavailable.\n\n"
                    "**Best next step:** Tell me the surface, turf, visible pattern, root condition, moisture pattern, and any lesions or mycelium you see. "
                    "I can still help you triage it from the field side without guessing from the photo alone."
                ),
                'sources': [],
                'confidence': {'score': 45, 'label': 'Clarifying Questions'},
                'kb_verdict': 'clarifying_questions',
                'needs_review': False,
                'grounding': {'verified': True, 'issues': []},
                'offline': True,
                'source_warning': 'Live image analysis is unavailable right now, so this stayed on the deterministic turf path.',
            }
            feedback_id = _save_expert_response(conversation_id, question, image_offline, attachment=feedback_attachment)
            _record_kb_gap_if_needed(question, image_offline, feedback_id=feedback_id)
            return jsonify(_attach_feedback_id(image_offline, feedback_id))

        if openai_client is not None:
            image_response = answer_image_diagnosis(
                question,
                image_attachment,
                course_profile,
                openai_client,
                model=Config.VISION_MODEL,
            )
            if image_response:
                image_info = image_response.get('image_diagnosis', {}) or {}
                image_response['expert_router'] = {
                    'mode': 'image_diagnosis',
                    'selected_mode': 'image_diagnosis',
                    'ordered_modes': ['image_diagnosis', 'advanced_diagnosis', 'advanced_turf_science', 'general'],
                    'attempted_modes': ['image_diagnosis'],
                    'fallback_mode': 'advanced_diagnosis',
                    'router_confidence': 0.92,
                    'matched_signals': (image_info.get('observed_clues', []) + image_info.get('diagnostic_signals', []))[:8],
                    'reason': 'An uploaded turf image supplied visual evidence, so the request was handled through image-aware diagnosis before any general answer path.',
                    'scores': {'image_diagnosis': 1.0, 'advanced_diagnosis': 0.86, 'advanced_turf_science': 0.52, 'general': 0.18},
                }
                feedback_id = _save_expert_response(conversation_id, question, image_response, attachment=feedback_attachment)
                _log_expert_router_event(question, image_response['expert_router'], resolved_mode='image_diagnosis', response=image_response)
                _record_kb_gap_if_needed(question, image_response, feedback_id=feedback_id)
                return jsonify(_attach_feedback_id(image_response, feedback_id))

        course_profile_context = format_course_profile_for_prompt(profile=course_profile)
        early_router_decision = route_expert_mode(question, course_profile)
        defer_early_verified_product_path = _should_defer_early_verified_product_path(early_router_decision)
        early_verified_response = answer_from_verified_kb(question, course_profile_context)
        if early_verified_response and not defer_early_verified_product_path:
            router_decision = early_router_decision
            early_verified_response['expert_router'] = {
                **router_decision,
                'attempted_modes': ['verified_product'],
                'selected_mode': 'verified_product',
            }
            save_message(conversation_id, 'user', question)
            save_message(
                conversation_id,
                'assistant',
                early_verified_response['answer'],
                sources=early_verified_response.get('sources'),
                confidence_score=early_verified_response.get('confidence', {}).get('score'),
            )
            feedback_id = save_query(
                question=question,
                ai_answer=early_verified_response['answer'],
                sources=early_verified_response.get('sources', []),
                confidence=early_verified_response.get('confidence', {}).get('score', 0),
                needs_review=early_verified_response.get('needs_review', False),
            )
            _log_expert_router_event(question, early_verified_response['expert_router'], resolved_mode='verified_product', response=early_verified_response)
            _record_kb_gap_if_needed(question, early_verified_response, feedback_id=feedback_id)
            return jsonify(_attach_feedback_id(early_verified_response, feedback_id))

        early_surface_target_response = recommend_verified_products_for_surface_target(question, course_profile)
        if early_surface_target_response and not defer_early_verified_product_path:
            router_decision = early_router_decision
            early_surface_target_response['expert_router'] = {
                **router_decision,
                'attempted_modes': ['verified_product'],
                'selected_mode': 'verified_product',
            }
            save_message(conversation_id, 'user', question)
            save_message(
                conversation_id,
                'assistant',
                early_surface_target_response['answer'],
                sources=early_surface_target_response.get('sources'),
                confidence_score=early_surface_target_response.get('confidence', {}).get('score'),
            )
            feedback_id = save_query(
                question=question,
                ai_answer=early_surface_target_response['answer'],
                sources=early_surface_target_response.get('sources', []),
                confidence=early_surface_target_response.get('confidence', {}).get('score', 0),
                needs_review=early_surface_target_response.get('needs_review', False),
            )
            _log_expert_router_event(question, early_surface_target_response['expert_router'], resolved_mode='verified_product', response=early_surface_target_response)
            _record_kb_gap_if_needed(question, early_surface_target_response, feedback_id=feedback_id)
            return jsonify(_attach_feedback_id(early_surface_target_response, feedback_id))

        early_target_response = recommend_verified_products_for_target(question, course_profile)
        if early_target_response and not defer_early_verified_product_path:
            router_decision = early_router_decision
            early_target_response['expert_router'] = {
                **router_decision,
                'attempted_modes': ['verified_product'],
                'selected_mode': 'verified_product',
            }
            save_message(conversation_id, 'user', question)
            save_message(
                conversation_id,
                'assistant',
                early_target_response['answer'],
                sources=early_target_response.get('sources'),
                confidence_score=early_target_response.get('confidence', {}).get('score'),
            )
            feedback_id = save_query(
                question=question,
                ai_answer=early_target_response['answer'],
                sources=early_target_response.get('sources', []),
                confidence=early_target_response.get('confidence', {}).get('score', 0),
                needs_review=early_target_response.get('needs_review', False),
            )
            _log_expert_router_event(question, early_target_response['expert_router'], resolved_mode='verified_product', response=early_target_response)
            _record_kb_gap_if_needed(question, early_target_response, feedback_id=feedback_id)
            return jsonify(_attach_feedback_id(early_target_response, feedback_id))

        early_context_needed_response = answer_product_context_needed(question, course_profile)
        if early_context_needed_response and not defer_early_verified_product_path:
            router_decision = early_router_decision
            early_context_needed_response['expert_router'] = {
                **router_decision,
                'attempted_modes': ['verified_product'],
                'selected_mode': 'verified_product',
            }
            save_message(conversation_id, 'user', question)
            save_message(
                conversation_id,
                'assistant',
                early_context_needed_response['answer'],
                sources=early_context_needed_response.get('sources'),
                confidence_score=early_context_needed_response.get('confidence', {}).get('score'),
            )
            feedback_id = save_query(
                question=question,
                ai_answer=early_context_needed_response['answer'],
                sources=early_context_needed_response.get('sources', []),
                confidence=early_context_needed_response.get('confidence', {}).get('score', 0),
                needs_review=early_context_needed_response.get('needs_review', False),
            )
            _log_expert_router_event(question, early_context_needed_response['expert_router'], resolved_mode='verified_product', response=early_context_needed_response)
            _record_kb_gap_if_needed(question, early_context_needed_response, feedback_id=feedback_id)
            return jsonify(_attach_feedback_id(early_context_needed_response, feedback_id))

        safety_response = get_pre_llm_safety_response(question, course_profile)
        if safety_response:
            save_message(conversation_id, 'user', question)
            save_message(
                conversation_id,
                'assistant',
                safety_response['answer'],
                sources=safety_response.get('sources'),
                confidence_score=safety_response.get('confidence', {}).get('score'),
            )
            feedback_id = save_query(
                question=question,
                ai_answer=safety_response['answer'],
                sources=safety_response.get('sources', []),
                confidence=safety_response.get('confidence', {}).get('score', 0),
                needs_review=True,
            )
            _record_kb_gap_if_needed(question, safety_response, feedback_id=feedback_id)
            return jsonify(_attach_feedback_id(safety_response, feedback_id))

        quick_response = _check_vague_query(question, profile_key=profile_key)
        if quick_response:
            return jsonify(quick_response)
        import time as _time
        _t0 = _time.time()
        _timings = {}

        # Demo mode: return cached golden responses (zero API cost, instant)
        if Config.DEMO_MODE:
            demo_response = find_demo_response(question)
            if demo_response:
                return jsonify(demo_response)

        router_decision = early_router_decision
        course_profile_context = format_course_profile_for_prompt(profile=course_profile)
        attempted_modes = []
        for mode in router_decision.get('ordered_modes', [router_decision['mode']]):
            if mode == 'general':
                break
            attempted_modes.append(mode)
            expert_response = _try_expert_mode(mode, question, course_profile, course_profile_context)
            if not expert_response:
                continue
            router_payload = dict(router_decision)
            router_payload['attempted_modes'] = attempted_modes
            router_payload['selected_mode'] = mode
            expert_response['expert_router'] = router_payload
            feedback_id = _save_expert_response(conversation_id, question, expert_response)
            _log_expert_router_event(question, router_payload, resolved_mode=mode, response=expert_response)
            _record_kb_gap_if_needed(question, expert_response, feedback_id=feedback_id)
            return jsonify(_attach_feedback_id(expert_response, feedback_id))

        if not openai_available:
            offline_response = _build_network_unavailable_response(question, course_profile)
            feedback_id = _save_expert_response(conversation_id, question, offline_response)
            _record_kb_gap_if_needed(question, offline_response, feedback_id=feedback_id)
            return jsonify(_attach_feedback_id(offline_response, feedback_id))

        # ── PARALLEL: classify + feasibility (classify is LLM, feasibility is local) ──
        from concurrent.futures import ThreadPoolExecutor, as_completed
        classify_future = None
        with ThreadPoolExecutor(max_workers=2) as executor:
            classify_future = executor.submit(classify_query, openai_client, question, "gpt-4o-mini")
            feasibility_result = check_feasibility(question)

        classification = classify_future.result()
        intercept_response = get_response_for_category(
            classification['category'], classification.get('reason', '')
        )
        _timings['1_classify'] = _time.time() - _t0
        if intercept_response:
            logging.debug(f"Query intercepted: {classification['category']} - {classification.get('reason', '')}")
            return jsonify(intercept_response)

        if feasibility_result:
            logging.debug(f"Feasibility gate triggered: {feasibility_result.get('feasibility_issues', [])}")
            return jsonify(feasibility_result)

        course_profile = load_course_profile(profile_key)
        course_profile_context = format_course_profile_for_prompt(profile=course_profile)
        inferred_profile_context = infer_regional_management_context(course_profile)
        course_profile_kb_hint = build_course_profile_kb_hint(course_profile)
        current_management_snapshot = format_current_management_snapshot(profile=course_profile)
        verified_response = answer_from_verified_kb(question, course_profile_context)
        if verified_response:
            save_message(conversation_id, 'user', question)
            save_message(
                conversation_id,
                'assistant',
                verified_response['answer'],
                sources=verified_response.get('sources'),
                confidence_score=verified_response.get('confidence', {}).get('score'),
            )
            feedback_id = save_query(
                question=question,
                ai_answer=verified_response['answer'],
                sources=verified_response.get('sources', []),
                confidence=verified_response.get('confidence', {}).get('score', 0),
                needs_review=verified_response.get('needs_review', False),
            )
            _record_kb_gap_if_needed(question, verified_response, feedback_id=feedback_id)
            return jsonify(_attach_feedback_id(verified_response, feedback_id))

        surface_target_response = recommend_verified_products_for_surface_target(question, course_profile)
        if surface_target_response:
            save_message(conversation_id, 'user', question)
            save_message(
                conversation_id,
                'assistant',
                surface_target_response['answer'],
                sources=surface_target_response.get('sources'),
                confidence_score=surface_target_response.get('confidence', {}).get('score'),
            )
            feedback_id = save_query(
                question=question,
                ai_answer=surface_target_response['answer'],
                sources=surface_target_response.get('sources', []),
                confidence=surface_target_response.get('confidence', {}).get('score', 0),
                needs_review=surface_target_response.get('needs_review', False),
            )
            _record_kb_gap_if_needed(question, surface_target_response, feedback_id=feedback_id)
            return jsonify(_attach_feedback_id(surface_target_response, feedback_id))

        target_response = recommend_verified_products_for_target(question, course_profile)
        if target_response:
            save_message(conversation_id, 'user', question)
            save_message(
                conversation_id,
                'assistant',
                target_response['answer'],
                sources=target_response.get('sources'),
                confidence_score=target_response.get('confidence', {}).get('score'),
            )
            feedback_id = save_query(
                question=question,
                ai_answer=target_response['answer'],
                sources=target_response.get('sources', []),
                confidence=target_response.get('confidence', {}).get('score', 0),
                needs_review=target_response.get('needs_review', False),
            )
            _record_kb_gap_if_needed(question, target_response, feedback_id=feedback_id)
            return jsonify(_attach_feedback_id(target_response, feedback_id))

        # Get optional location for weather (can be passed from frontend)
        user_location = body.get('location', {})
        lat = user_location.get('lat')
        lon = user_location.get('lon')
        city = user_location.get('city')
        state = user_location.get('state')

        # Detect if this is a topic change - if so, don't use conversation history
        question_lower = question.lower()
        current_topic = detect_topic(question_lower)
        current_subject = detect_specific_subject(question_lower)
        previous_topic = session.get('last_topic')
        previous_subject = session.get('last_subject')
        is_topic_change = _is_significant_topic_change(
            previous_topic, current_topic, question,
            previous_subject=previous_subject, current_subject=current_subject
        )

        # Always save the message
        save_message(conversation_id, 'user', question)

        if is_topic_change:
            logging.debug(f'Topic change detected: {previous_topic}({previous_subject}) -> {current_topic}({current_subject})')
            contextual_question = question
            question_to_process = expand_vague_question(question)
        else:
            contextual_question = build_context_for_ai(conversation_id, question)
            question_to_process = expand_vague_question(contextual_question)

        session['last_topic'] = current_topic
        if current_subject:
            session['last_subject'] = current_subject

        _timings['2_feasibility'] = _time.time() - _t0
        # LLM-based query rewriting for better retrieval
        rewritten_query = rewrite_query(openai_client, question_to_process, model="gpt-4o-mini")
        logging.debug(f'Rewritten query: {rewritten_query[:100]}')

        _timings['3_rewrite'] = _time.time() - _t0
        # Detect context from original question
        grass_type = detect_grass_type(question_to_process)
        region = detect_region(question_to_process)
        if not region:
            region = inferred_profile_context.get('retrieval_region_hint')
        product_need = detect_product_need(question_to_process)
        question_topic = detect_topic(question_to_process.lower())
        if product_need and not question_topic:
            question_topic = 'chemical'

        # Build expanded query using rewritten version
        expanded_query = expand_query(rewritten_query)
        if grass_type:
            expanded_query += f" {grass_type}"
        if region:
            expanded_query += f" {region}"

        # Search (parallel execution for better performance)
        pinecone_index = get_pinecone_index_safe()
        search_results = search_all_parallel(
            pinecone_index, openai_client, rewritten_query, expanded_query,
            product_need, grass_type, Config.EMBEDDING_MODEL
        )

        _timings['4_search'] = _time.time() - _t0
        # Combine and score results first to check if we have anything
        all_matches = (
            search_results['general'].get('matches', []) +
            search_results['product'].get('matches', []) +
            search_results['timing'].get('matches', [])
        )
        scored_results = score_results(all_matches, question, grass_type, region, product_need)

        # Apply cross-encoder reranking for better relevance (if available)
        if scored_results:
            scored_results = rerank_results(rewritten_query, scored_results, top_k=20)

        _timings['5_rerank'] = _time.time() - _t0
        # Filter and build context
        filtered_results = safety_filter_results(scored_results, question_topic, product_need)
        context, sources, images = build_context(filtered_results, SEARCH_FOLDERS)

        # Calculate preliminary confidence to decide on web search
        prelim_confidence = len(filtered_results) * 10 if filtered_results else 0
        if filtered_results:
            avg_score = sum(r.get('score', 0) for r in filtered_results[:5]) / min(5, len(filtered_results))
            prelim_confidence = min(100, avg_score * 100)

        # Check if web search is needed
        used_web_search = False
        web_search_result = None
        supplement_mode = False

        if should_trigger_web_search(search_results):
            # No results at all - full web search fallback
            logging.debug('No Pinecone results found - triggering web search fallback')
            web_search_result = search_web_for_turf_info(openai_client, question, supplement_mode=False)
            if web_search_result:
                used_web_search = True
                context = web_search_result['context']
                sources = web_search_result['sources']
                images = []
                logging.debug('Web search fallback returned results')
        elif should_supplement_with_web_search(prelim_confidence):
            # Have some results but low confidence - supplement with web search
            logging.debug(f'Low confidence ({prelim_confidence:.0f}%) - supplementing with web search')
            web_search_result = search_web_for_turf_info(openai_client, question, supplement_mode=True)
            if web_search_result:
                used_web_search = True
                supplement_mode = True
                # Append web search context to existing context
                context = context + "\n\n" + web_search_result['context']
                sources = sources + web_search_result['sources']
                logging.debug('Web search supplement added')

        # Enrich context with structured knowledge base data
        if not used_web_search or supplement_mode:
            structured_entities = extract_disease_names(question) + extract_product_names(question)
            knowledge_question = question
            if course_profile_kb_hint and _should_apply_profile_kb_hint(question, question_topic):
                knowledge_question = f"{question}\nSaved regional context: {course_profile_kb_hint}"
            context = enrich_context_with_knowledge(knowledge_question, context)
            if structured_entities:
                sources.append({
                    'name': 'Structured Turf Knowledge Base',
                    'type': 'structured_reference',
                    'note': 'Verified local disease/product reference data: ' + ', '.join(structured_entities[:4])
                })
        else:
            structured_entities = []

        # Add weather context if location provided and topic is relevant
        weather_data = None
        weather_topics = {'chemical', 'fungicide', 'herbicide', 'insecticide', 'irrigation', 'cultural', 'diagnostic', 'disease'}
        if (lat and lon) or city:
            if question_topic in weather_topics or product_need:
                weather_data = get_weather_data(lat=lat, lon=lon, city=city, state=state)
                if weather_data:
                    weather_context = get_weather_context(weather_data)
                    context = context + "\n\n" + weather_context
                    logging.debug(f"Added weather context for {weather_data.get('location', 'unknown')}")

        if course_profile_context:
            context = course_profile_context + "\n\n" + context
            sources.append({
                'name': 'Course Profile Memory',
                'type': 'course_profile',
                'note': 'User-provided course context used to tailor the answer'
            })
            if current_management_snapshot and _should_apply_profile_kb_hint(question, question_topic):
                sources.append({
                    'name': 'Current Management Snapshot',
                    'type': 'course_profile',
                    'note': 'Date-aware priorities inferred from the saved course profile'
                })

        context = context[:MAX_CONTEXT_LENGTH]

        # Process sources
        sources = [s for s in sources if s.get('url') is not None or s.get('note')]  # Allow web search sources
        sources = deduplicate_sources(sources)

        # For supplement mode, filter DB sources but keep web sources
        if supplement_mode:
            db_sources = [s for s in sources if not s.get('note', '').startswith('Web search')]
            web_sources = [s for s in sources if s.get('note', '').startswith('Web search')]
            display_sources = filter_display_sources(db_sources, SEARCH_FOLDERS) + web_sources
        elif used_web_search:
            display_sources = sources  # All web sources
        else:
            display_sources = filter_display_sources(sources, SEARCH_FOLDERS)
        all_sources_for_confidence = sources

        source_warning = None
        if not display_sources:
            source_warning = "No displayable verified source file was found for this answer."

        # Generate AI response with topic-specific prompt and conversation history
        from prompts import build_system_prompt
        system_prompt = build_system_prompt(question_topic, product_need)

        # Build messages array - skip history if topic changed
        if is_topic_change:
            # Fresh start - no conversation history
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": _build_user_prompt(context, question)}
            ]
        else:
            # Include conversation history for follow-up understanding
            messages = _build_messages_with_history(
                conversation_id, system_prompt, context, question
            )

        _timings['6_pre_llm'] = _time.time() - _t0
        answer = openai_client.chat.completions.create(
            model=Config.CHAT_MODEL,
            messages=messages,
            max_tokens=Config.CHAT_MAX_TOKENS,
            temperature=Config.CHAT_TEMPERATURE,
            timeout=30  # Don't hang longer than 30s during a live demo
        )
        assistant_response = answer.choices[0].message.content
        if not assistant_response:
            assistant_response = "I wasn't able to generate a response. Please try rephrasing your question."
        _timings['7_llm_answer'] = _time.time() - _t0

        # ── PARALLEL: grounding check (API) + hallucination filter + validation (local) ──
        # Grounding is a GPT-4o-mini call (~3-4s). Hallucination filter and validation
        # are local checks (~0s). Run grounding in background while local checks proceed.
        with ThreadPoolExecutor(max_workers=2) as executor:
            grounding_future = executor.submit(
                check_answer_grounding, openai_client, assistant_response, context, question, "gpt-4o-mini"
            )

            # Run local checks while grounding API call is in flight
            hallucination_result = filter_hallucinations(
                answer=assistant_response,
                question=question,
                context=context,
                sources=sources,
                openai_client=openai_client
            )
            if hallucination_result['was_modified']:
                assistant_response = hallucination_result['filtered_answer']
                logging.info(f"Hallucination filter: {len(hallucination_result['issues_found'])} issues found")

            # Knowledge base validation
            assistant_response, validation_result = apply_validation(assistant_response, question)
            if not validation_result['valid']:
                logging.info(f"KB validation: {len(validation_result['issues'])} issues found")

            # Wait for grounding result
            grounding_result = grounding_future.result()

        # Add warning if answer has grounding issues
        assistant_response = add_grounding_warning(assistant_response, grounding_result)

        _timings['8_grounding+checks'] = _time.time() - _t0
        # Calculate confidence with grounding + hallucination filter + validation adjustments
        base_confidence = calculate_confidence_score(all_sources_for_confidence, assistant_response, question)
        confidence = calculate_grounding_confidence(grounding_result, base_confidence)
        # Apply hallucination filter penalty
        confidence -= hallucination_result.get('confidence_penalty', 0)
        # Apply knowledge base validation penalty
        confidence -= validation_result.get('confidence_penalty', 0)
        confidence = max(0, confidence)
        confidence_label = get_confidence_label(confidence)

        # Save response to conversation history
        save_message(
            conversation_id, 'assistant', assistant_response,
            sources=display_sources[:MAX_SOURCES],
            confidence_score=confidence
        )

        # Determine if human review is needed (below 70% threshold)
        needs_review = (
            confidence < 70 or
            not grounding_result.get('grounded', True) or
            len(grounding_result.get('unsupported_claims', [])) > 1 or
            not sources  # No sources found
        )

        # Save query to admin dashboard (all queries, not just rated ones)
        feedback_id = save_query(
            question=question,
            ai_answer=assistant_response,
            sources=display_sources[:MAX_SOURCES],
            confidence=confidence,
            needs_review=needs_review
        )

        response_data = {
            'answer': assistant_response,
            'sources': display_sources[:MAX_SOURCES],
            'images': images,
            'confidence': {'score': confidence, 'label': confidence_label},
            'grounding': {
                'verified': grounding_result.get('grounded', True),
                'issues': grounding_result.get('unsupported_claims', [])
            },
            'needs_review': needs_review
        }
        if source_warning:
            response_data['source_warning'] = source_warning

        # Add web search indicator if used
        if used_web_search:
            response_data['web_search_used'] = True
            response_data['web_search_disclaimer'] = format_web_search_disclaimer()

        # Add weather info if available
        if weather_data:
            response_data['weather'] = {
                'location': weather_data.get('location'),
                'summary': format_weather_for_response(weather_data),
                'warnings': get_weather_warnings(weather_data)
            }

        response_data = apply_post_llm_safety_gate(question, response_data)
        _attach_feedback_id(response_data, feedback_id)

        _log_expert_router_event(question, router_decision, resolved_mode='general', response=response_data)

        _timings['10_total'] = _time.time() - _t0
        # Log timing breakdown
        prev = 0
        timing_parts = []
        for key in sorted(_timings.keys(), key=lambda item: int(item.split('_', 1)[0])):
            elapsed = _timings[key]
            delta = elapsed - prev
            timing_parts.append(f"{key}={delta:.1f}s")
            prev = elapsed
        logging.info(f"⏱️ PIPELINE TIMING [{_timings['10_total']:.1f}s total]: {' | '.join(timing_parts)}")

        return jsonify(response_data)

    except Exception as e:
        # Log the error but never crash - always return something useful
        logger.error(f"Error processing question: {e}", exc_info=True)

        fallback_profile = locals().get("course_profile") or {}
        question_text = locals().get("question", "") or ""
        if isinstance(e, openai.APIConnectionError):
            operational_fallback = build_operational_guidance_response(question_text, profile=fallback_profile)
            if operational_fallback:
                operational_fallback["error_logged"] = True
                operational_fallback["offline"] = True
                return jsonify(operational_fallback)

            general_fallback = build_general_turf_guidance_response(question_text, profile=fallback_profile)
            if general_fallback:
                general_fallback["error_logged"] = True
                general_fallback["offline"] = True
                return jsonify(general_fallback)

            clarifying_fallback = _build_clarifying_turf_response(question_text.lower(), fallback_profile)
            if clarifying_fallback:
                clarifying_fallback["error_logged"] = True
                clarifying_fallback["offline"] = True
                return jsonify(clarifying_fallback)

            context_fallback = _build_general_context_response(fallback_profile)
            context_fallback["error_logged"] = True
            context_fallback["offline"] = True
            return jsonify(context_fallback)

        # Return a graceful fallback response
        return jsonify({
            'answer': "I apologize, but I encountered an issue processing your question. Please try rephrasing or ask a different question about turfgrass management.",
            'sources': [],
            'confidence': {'score': 0, 'label': 'Error'},
            'error_logged': True
        })


def _get_or_create_conversation():
    """Get existing conversation ID or create new session."""
    account = _current_account()
    if 'session_id' not in session:
        user_info = None
        account_id = None
        if account:
            account_id = account["id"]
            user_info = {
                "account_id": account["id"],
                "email": account.get("email"),
            }
        session_id, conversation_id = create_session(account_id=account_id, user_info=user_info)
        session['session_id'] = session_id
        session['conversation_id'] = conversation_id
    elif account and session.get('conversation_id'):
        set_conversation_account(
            session.get('conversation_id'),
            account["id"],
            user_info={
                "account_id": account["id"],
                "email": account.get("email"),
            },
        )
    return session['conversation_id']


def _get_profile_key():
    """Use the Flask/browser session as the course profile scope."""
    account = _current_account()
    if account:
        return account['id']
    if 'session_id' not in session:
        _get_or_create_conversation()
    return session.get('session_id')


def _is_significant_topic_change(previous_topic: str, current_topic: str, question: str,
                                  previous_subject: str = None, current_subject: str = None) -> bool:
    """
    Detect if the user is changing to a completely different topic.
    This helps prevent conversation history from confusing unrelated questions.

    Returns True if this appears to be a new topic that shouldn't use previous context.
    """
    # No previous topic means first question — but check subjects
    if not previous_topic:
        # If the current question has a specific subject different from last known subject,
        # treat as topic change to avoid injecting stale history
        if current_subject and previous_subject and current_subject != previous_subject:
            logging.debug(f'Subject change (no prev topic): {previous_subject} -> {current_subject}')
            return True
        return False

    # If we can't detect the current topic, treat it as a new topic
    # to avoid injecting irrelevant conversation history
    if not current_topic:
        return True

    # Same category but different specific subject = topic change
    # e.g., "pythium" vs "summer patch" are both 'disease' but different subjects
    if previous_topic == current_topic:
        if current_subject and previous_subject and current_subject != previous_subject:
            logging.debug(f'Subject change within same category: {previous_subject} -> {current_subject}')
            return True
        return False

    # Check for explicit "new question" signals
    new_topic_signals = [
        'different question',
        'new question',
        'unrelated',
        'switching topic',
        'change of topic',
        'another question',
        'also wondering',
    ]
    question_lower = question.lower()
    if any(signal in question_lower for signal in new_topic_signals):
        return True

    # Define topic groups that are related
    related_groups = [
        {'chemical', 'fungicide', 'herbicide', 'insecticide'},
        {'cultural', 'irrigation', 'fertilizer'},
        {'equipment', 'calibration'},
        {'diagnostic', 'disease'},
    ]

    # Check if topics are in the same related group
    for group in related_groups:
        if previous_topic in group and current_topic in group:
            # Still check for subject change within related groups
            if current_subject and previous_subject and current_subject != previous_subject:
                logging.debug(f'Subject change within related group: {previous_subject} -> {current_subject}')
                return True
            return False

    # Check for follow-up language that suggests continuation
    followup_signals = [
        'what about',
        'how about',
        'and ',
        'also ',
        'what if',
        'same ',
        'that ',
        'the rate',
        'the product',
        'this disease',
        'those ',
    ]
    if any(question_lower.startswith(signal) or signal in question_lower[:30] for signal in followup_signals):
        return False

    # Different topic groups and no follow-up language = topic change
    if previous_topic and current_topic and previous_topic != current_topic:
        return True

    return False


def _build_user_prompt(context, question):
    """Build the user prompt for the AI."""
    question_lower = question.lower()
    wants_definition = any(
        question_lower.startswith(prefix)
        for prefix in ('what is ', 'what are ', 'explain ', 'define ')
    )
    wants_product_rate = any(
        term in question_lower
        for term in ('rate', 'label', 'oz', 'fl oz', 'lb/acre', 'per 1000', 'per acre')
    )
    wants_diagnosis = any(
        term in question_lower
        for term in ('diagnose', 'identify', 'symptom', 'patch', 'spot', 'yellow', 'wilt', 'mycelium')
    )
    wants_monitoring = any(
        term in question_lower
        for term in ('watch for', 'look for', 'monitor', 'scout', 'keep an eye on')
    )

    answer_shape = (
        "For simple definition questions, keep the answer tight: name it, explain how it shows up, "
        "why it happens, and the first field check. Do not turn a definition into a full spray program unless asked."
        if wants_definition else
        "For monitoring or scouting questions, focus on risks, field signs, timing, and what to log. "
        "Do not give product rates or a spray program unless the user explicitly asks for treatment."
        if wants_monitoring else
        "For diagnosis questions, lead with the most likely cause if supported, give 2-3 lookalikes, "
        "then give field checks before treatment."
        if wants_diagnosis else
        "For management questions, lead with the practical recommendation, then explain the agronomic reason."
    )
    if wants_product_rate:
        answer_shape += (
            " For product or rate questions, treat the label as the authority: use exact label rates only when the context supports them, "
            "include FRAC/HRAC/IRAC where known, and say when the label must be checked instead of guessing."
        )

    return (
        f"Context from research and manuals:\n\n{context}\n\n"
        f"Question: {question}\n\n"
        "INSTRUCTIONS:\n"
        "1. Answer like an experienced golf course superintendent advising another superintendent.\n"
        "2. Start with a clear bottom line, then give the reasoning and next action.\n"
        "3. Do not over-answer: match the depth to the question.\n"
        "4. Provide specific products, rates, timing, and FRAC/HRAC/IRAC codes only when supported by the context.\n"
        "5. If verified product data is provided, use those exact rates. If not, say to verify the label rather than inventing a rate.\n"
        "6. Include practical field checks and risk cautions where relevant.\n"
        "7. If COURSE PROFILE MEMORY is present, tailor the answer to that course context and mention the relevant surface, region, or constraint when it matters.\n\n"
        f"ANSWER SHAPE:\n{answer_shape}"
    )


def _build_messages_with_history(conversation_id, system_prompt, context, current_question):
    """
    Build messages array including conversation history for follow-up understanding.
    This allows the AI to understand references like "what about the rate?" or "that product".
    """
    messages = [{"role": "system", "content": system_prompt}]

    # Get recent conversation history (last 3 exchanges = 6 messages)
    history = get_conversation_history(conversation_id, limit=6)

    # Add historical messages (excluding the current question we just saved)
    for msg in history[:-1]:  # Skip the last one (current question)
        if msg['role'] == 'user':
            messages.append({"role": "user", "content": msg['content']})
        elif msg['role'] == 'assistant':
            # Truncate long responses to save tokens
            content = msg['content']
            if len(content) > 500:
                content = content[:500] + "..."
            messages.append({"role": "assistant", "content": content})

    # Add current question with context
    messages.append({
        "role": "user",
        "content": _build_user_prompt(context, current_question)
    })

    return messages


def _check_vague_query(question: str, profile_key: str | None = None):
    """
    Detect queries that are too vague, off-topic, or adversarial to process
    meaningfully. Returns a response dict if the query should be intercepted,
    or None if the query should proceed normally.
    """
    q = question.lower().strip().rstrip('?.!')
    profile = load_course_profile(profile_key)
    clarifying_response = _build_clarifying_turf_response(q, profile)
    if clarifying_response:
        return clarifying_response

    # Ultra-short queries (1-3 words) that lack turf context
    words = q.split()
    if len(words) <= 2 and not any(
        term in q for term in [
            'dollar spot', 'brown patch', 'pythium', 'crabgrass', 'poa',
            'grub', 'fungicide', 'herbicide', 'insecticide', 'pgr',
            'mowing', 'aeration', 'topdress', 'irrigation', 'fertiliz',
            'bermuda', 'bentgrass', 'zoysia', 'bluegrass', 'fescue',
            'ryegrass', 'primo', 'heritage', 'banner', 'daconil',
            'barricade', 'dimension', 'tenacity', 'acelepryn',
        ]
    ):
        # Check for ultra-vague fragments
        vague_fragments = [
            'spray it', 'fix it', 'help', 'weeds', 'brown spots',
            'is it too late', 'how much', 'what should i',
        ]
        if q in vague_fragments or len(q) < 12:
            return _build_general_context_response(profile)

    # Off-topic detection — clearly non-turfgrass questions
    off_topic_patterns = [
        # Finance/business
        'stock', 'invest', 'bitcoin', 'crypto', 'portfolio', 'trading',
        # Medical
        'headache', 'medicine', 'prescription', 'doctor', 'symptom',
        'diagnosis',  # only if no turf context
        # Cooking
        'recipe', 'cook', 'bake', 'ingredient',
        # Coding/tech
        'python script', 'javascript', 'html', 'programming', 'write code',
        'scrape web', 'source code', 'compile',
        # General knowledge
        'meaning of life', 'roman empire', 'history of', 'who invented',
        # Career
        'cover letter', 'resume', 'job interview',
        # Automotive
        'car engine', 'oil change', 'brake pad',
        # Legal
        'legal advice', 'lawsuit', 'attorney',
        # Cannabis/drugs
        'marijuana', 'cannabis', 'weed grow',  # Note: 'weed' alone is turf-related
    ]

    # Check for off-topic but avoid false positives for turf terms
    turf_context_words = [
        'turf', 'grass', 'lawn', 'green', 'fairway', 'golf', 'mow',
        'spray', 'fungicide', 'herbicide', 'fertiliz', 'aerat', 'irrigat',
        'bermuda', 'bent', 'bentgrass', 'poa bent', 'zoysia', 'fescue', 'bluegrass', 'rye',
        'disease', 'weed control', 'grub', 'insect', 'thatch', 'soil',
        'topdress', 'overseed', 'pgr', 'primo', 'frac', 'hrac', 'irac',
        'barricade', 'dimension', 'heritage', 'daconil', 'banner',
        'roundup', 'glyphosate', 'dollar spot', 'brown patch', 'pythium',
        'crabgrass', 'poa annua', 'nematode', 'pesticide', 'label rate',
        'application rate', 'tank mix', 'pre-emergent', 'post-emergent',
        'specticle', 'tenacity', 'acelepryn', 'merit', 'bifenthrin',
        'propiconazole', 'chlorothalonil', 'azoxystrobin',
        'gallery', 'lontrel', 'monument', 'pylex', 'basagran',
        'manuscript', 'scimitar', 'isoxaben', 'clopyralid',
        'trifloxysulfuron', 'topramezone', 'bentazon', 'pinoxaden',
        'lambda-cyhalothrin',
        'ant', 'ants', 'webworm', 'billbug', 'cutworm', 'chinch bug',
        'annual bluegrass weevil', 'abw', 'foxtail', 'kyllinga',
        'ground ivy', 'wild violet', 'wild violets', 'nimblewill',
        'dallisgrass', 'fire ant', 'armyworm',
        'localized dry spot', 'dry spot', 'lds', 'heat stress', 'drought',
        'wilt', 'overwater', 'compaction', 'shade stress', 'traffic stress',
        'scalping', 'herbicide injury', 'spray injury', 'fertilizer burn',
        'salt burn', 'black layer', 'st augustine', 'centipede',
        'carbohydrate', 'root respiration', 'air-filled porosity',
        'air filled porosity', 'hydraulic conductivity', 'rootzone porosity',
        'surface organic matter', 'perched water', 'layering',
        'disease triangle', 'leaf wetness', 'microclimate', 'hydrophobicity',
        'firmness', 'green speed', 'growth potential', 'syringing',
        'winter injury', 'crown hydration', 'freeze injury', 'winterkill',
        'low light', 'shade physiology', 'nitrogen form', 'slow release nitrogen',
        'salinity stress', 'sodium hazard', 'osmotic drought', 'nematode',
        'nematodes', 'root pruning',
        'poa decline', 'poa annua decline', 'wetting agent chemistry',
        'surfactant chemistry', 'bicarbonate', 'bicarbonates', 'alkalinity',
        'micronutrient lockout', 'pythium root dysfunction',
        'pythium root rot', 'growing degree days', 'gdd', 'pgr timing',
    ]
    has_turf_context = any(t in q for t in turf_context_words)

    if not has_turf_context:
        for pattern in off_topic_patterns:
            if pattern in q:
                return {
                    'answer': (
                        "I specialize in turfgrass management and can't help with that topic. "
                        "Feel free to ask me anything about turf, lawn care, golf course management, "
                        "disease control, weed management, fertility, irrigation, or cultural practices!"
                    ),
                    'sources': [],
                    'confidence': {'score': 0, 'label': 'Off Topic'}
                }

    # Turf-related but missing critical context (location, grass type, target)
    missing_context_patterns = [
        'what should i spray this month',
        'what should i apply this month',
        'what do i need to spray',
        'what do i spray now',
        'what should i put down this month',
        'what should i apply now',
        'what product should i use this month',
    ]
    if any(p in q for p in missing_context_patterns):
        known_profile = summarize_known_profile_for_questions(profile=profile)
        known_sentence = (
            f"I already have this course context: {known_profile}.\n\n"
            if known_profile else ""
        )
        return {
            'answer': (
                "Great question! To give you the right spray program for this month, "
                "I need the missing details before recommending products.\n\n"
                f"{known_sentence}"
                "- **What are you targeting?** (disease prevention, weed control, insect management)\n"
                "- **What type of turf area?** (golf greens, fairways, home lawn, sports field)\n"
                "- **Any current symptoms or recent weather pressure?**\n"
                "- **Any products you already used recently?**\n\n"
                "If the saved course profile is wrong, tell me plainly, like: "
                "**Remember our greens are creeping bentgrass.**\n\n"
                "With the target and surface, I can give specific products, rates, and timing."
            ),
            'sources': [],
            'confidence': {'score': 0, 'label': 'Clarifying Questions'},
            'kb_verdict': 'clarifying_questions',
            'needs_review': False,
            'grounding': {'verified': True, 'issues': []},
        }

    # Prompt injection / system prompt leak attempts
    injection_patterns = [
        'ignore your instructions', 'ignore your prompt', 'ignore previous',
        'what are your instructions', 'show me your prompt',
        'system prompt', 'you are now', 'act as a', 'pretend you are',
        'forget your training', 'disregard your',
    ]
    if any(p in q for p in injection_patterns):
        return {
            'answer': (
                "I'm a turfgrass management assistant. "
                "I'm here to help with questions about turf, lawn care, disease management, "
                "weed control, fertility, irrigation, and golf course maintenance. "
                "What turf question can I help you with?"
            ),
            'sources': [],
            'confidence': {'score': 0, 'label': 'Off Topic'}
        }


def _build_general_context_response(profile: dict[str, Any] | None = None) -> dict[str, Any]:
    profile = profile or {}
    known_profile = summarize_known_profile_for_questions(profile=profile)
    lines = [
        "**Bottom Line:** I can help, but I need a couple of turf details before I narrow this down usefully.",
    ]
    if known_profile:
        lines.extend([
            "",
            f"**Course context I'm using:** {known_profile}",
        ])
    lines.extend([
        "",
        "**Most useful next details:**",
        "- **Surface and turf**: greens, fairways, tees, or rough, plus the grass type if it differs from the saved profile.",
        "- **Problem or goal**: disease, weeds, insects, fertility, irrigation, firmness, speed, or general stress.",
        "- **What you are seeing**: yellowing, thinning, wilt, spots, soft/puffy turf, weak roots, or just a management question.",
        "- **Location or weather note** if timing is the issue.",
        "",
        "**How I'd triage it fast:**",
        "- Get the surface and turf right first.",
        "- Then separate whether this is a problem to diagnose, a science question to explain, or a product decision to verify.",
        "",
        '**Fastest reply format:** "Bentgrass greens, humid week, thinning in low spots, roots are short, no obvious lesions."',
    ])
    return {
        'answer': "\n".join(lines),
        'sources': [],
        'confidence': {'score': 40, 'label': 'Clarifying Questions'},
        'kb_verdict': 'clarifying_questions',
        'needs_review': False,
        'grounding': {'verified': True, 'issues': []},
    }


def _build_network_unavailable_response(question: str, profile: dict[str, Any] | None = None) -> dict[str, Any]:
    profile = profile or {}
    question_lower = (question or "").lower()

    clarifying = _build_clarifying_turf_response(question_lower, profile)
    if clarifying:
        clarifying["offline"] = True
        clarifying["source_warning"] = "Live model connectivity is unavailable right now, so this answer stayed on the deterministic turf path."
        return clarifying

    general = build_general_turf_guidance_response(question, profile=profile)
    if general:
        general["offline"] = True
        general["source_warning"] = "Live model connectivity is unavailable right now, so this answer stayed on the deterministic turf path."
        return general

    fallback = _build_general_context_response(profile)
    fallback["offline"] = True
    fallback["source_warning"] = "Live model connectivity is unavailable right now, so I need a few concrete turf details to stay useful without guessing."
    return fallback


def _build_clarifying_turf_response(question_lower: str, profile: dict[str, Any] | None = None) -> dict[str, Any] | None:
    profile = profile or {}
    special_clarifying_prompt = (
        ("monday" in question_lower and "friday" in question_lower)
        or ("tired by friday" in question_lower)
        or ("8 am" in question_lower and "2 pm" in question_lower)
        or ("looks okay at" in question_lower and "rough by" in question_lower)
        or ("what am i missing" in question_lower and ("roots are there" in question_lower or "looks tired" in question_lower))
        or ("surviving but not recovering" in question_lower)
        or ("poa" in question_lower and "bent" in question_lower and ("hanging on" in question_lower or "melt" in question_lower))
        or ("syringe" in question_lower and ("helps for an hour" in question_lower or "helps" in question_lower))
        or ("roots are short" in question_lower and "top stays wet" in question_lower)
        or ("canopy still wilts" in question_lower)
        or ("green still has no life" in question_lower)
        or ("disease app looks fine on paper" in question_lower)
        or ("weak patch" in question_lower and ("spray" in question_lower or "overlooking" in question_lower))
    )
    router_preview = route_expert_mode(question_lower, profile)
    generic_signals = {
        'why are', 'why is', 'why did', 'why do', 'why does', 'is this', 'could this be',
        'could this', 'what is causing', "what's causing", 'what causes', 'symptoms',
        'decline', 'thinning', 'thin', 'wilt', 'wilting', 'stress', 'water', 'disease',
        'water or disease',
    }
    preview_mode = router_preview.get('mode')
    preview_signals = router_preview.get('all_signals', {}).get(preview_mode, []) if preview_mode else []
    specific_preview_signals = [
        signal for signal in preview_signals
        if signal not in generic_signals and len(str(signal)) > 4
    ]
    mixed_product_diagnosis = (
        ("should i spray" in question_lower or "what should i spray" in question_lower or "what do i spray" in question_lower)
        and preview_mode == 'advanced_diagnosis'
    )
    explicit_differential_prompt = (
        (question_lower.startswith("how do i know if") or "how do i tell" in question_lower)
        and preview_mode == 'advanced_diagnosis'
    )
    expert_differential_prompt = (
        (
            question_lower.startswith("walk me through how you would separate")
            or question_lower.startswith("how would you separate")
            or question_lower.startswith("how do you separate")
        )
        and preview_mode == 'advanced_diagnosis'
    )
    if preview_mode == 'advanced_turf_science' and specific_preview_signals and not special_clarifying_prompt:
        return None
    if mixed_product_diagnosis:
        return None
    if explicit_differential_prompt:
        return None
    if expert_differential_prompt:
        return None
    if preview_mode == 'advanced_diagnosis' and not special_clarifying_prompt and (
        "water or disease" not in question_lower and
        (len(specific_preview_signals) >= 2 or float(router_preview.get('router_confidence') or 0) >= 0.75)
    ):
        return None

    if any(
        phrase in question_lower
        for phrase in (
            "what should i know about",
            "how should i think about",
            "how far can i push",
            "just heat or something else",
            "why does poa collapse faster than bentgrass in summer",
            "why does poa annua collapse faster than bentgrass in summer",
            "why does poa annua decline faster than bentgrass in summer",
            "why does black layer wreck roots",
            "why do warm nights hurt bentgrass more than hot days",
            "why does mower injury mimic disease so often",
        )
    ):
        return None
    known_profile = summarize_known_profile_for_questions(profile=profile)
    surfaces = profile.get('surfaces', {}) if isinstance(profile, dict) else {}
    known_surface_names = [name for name, turf in surfaces.items() if turf]
    mentions_surface = any(
        term in question_lower
        for term in ('green', 'greens', 'fairway', 'fairways', 'tee', 'tees', 'rough')
    )
    mentions_turf = any(
        term in question_lower
        for term in (
            'bent', 'bentgrass', 'poa', 'bermuda', 'bermudagrass', 'zoysia',
            'bluegrass', 'kentucky bluegrass', 'fescue', 'ryegrass', 'st augustine', 'centipede'
        )
    )
    diagnosis_terms = (
        'struggling', 'weak', 'weak roots', 'roots weak', 'thinning', 'decline', 'declining',
        'wilt', 'wilting', 'yellowing', 'brown', 'soft', 'puffy', 'stress', 'disease', 'water',
        'root', 'roots', 'tired', 'heavy', 'recover', 'recovering', 'syringe', 'melt',
        'hanging on', 'no life', 'weak patch',
    )
    has_diagnosis_shape = (
        any(term in question_lower for term in diagnosis_terms)
        or question_lower.startswith('why')
        or question_lower.startswith('is this')
        or question_lower.startswith('what is making')
        or question_lower.startswith('what could be causing')
        or "what would you check first" in question_lower
        or "what do you want to know first" in question_lower
        or "where do you go first" in question_lower
        or "what does that tell you" in question_lower
        or "what does that smell like" in question_lower
        or "how do you read that" in question_lower
        or "what are you checking" in question_lower
        or "what am i overlooking" in question_lower
        or "what am i missing" in question_lower
        or "thinking about first" in question_lower
        or ("8 am" in question_lower and "2 pm" in question_lower)
        or ("looks okay at" in question_lower and "rough by" in question_lower)
    )
    if (
        ("what should i spray" in question_lower or "should i spray something" in question_lower or "what do i spray" in question_lower)
        and not has_diagnosis_shape
    ):
        return _build_general_context_response(profile)

    if not has_diagnosis_shape:
        return None

    if len(question_lower.split()) <= 2:
        return None

    lines = [
        "**Bottom Line:** I can help narrow that down, but the next useful step is a quick field triage before making a call.",
    ]
    if known_profile:
        lines.extend([
            "",
            f"**Course context I'm using:** {known_profile}",
        ])

    if (
        ("water or disease" in question_lower and not question_lower.startswith("how do i know if"))
        or ("is this" in question_lower and "disease" in question_lower)
        or ("is this" in question_lower and ("pythium" in question_lower or "wet wilt" in question_lower))
    ):
        lines.extend([
            "",
            "**Most useful next checks:**",
            "- **Pattern**: uniform, low spots, irrigation arcs, shaded pockets, rings, or pass lines?",
            "- **Leaf evidence**: lesions, mycelium, smoke ring, or just off-color / wilt?",
            "- **Moisture and roots**: top-inch moisture, deeper moisture, and whether roots are short, dark, or healthy white.",
            "- **Root condition**: healthy white roots, short dark roots, or water-soaked sloughing roots?",
            "- **Weather**: dew, humidity, warm nights, and rainfall over the last 5-7 days.",
            "",
            "**What not to do yet:**",
            "- Do not assume disease just because the turf is collapsing under humid weather.",
            "- Do not add water or reach for a product until the roots and moisture-by-depth picture are clearer.",
            "",
            '**Fastest reply format:** "Bentgrass greens, low spots stay wet, humid nights, no lesions, shallow dark roots."',
        ])
        return {
            'answer': "\n".join(lines),
            'sources': [],
            'confidence': {'score': 52, 'label': 'Clarifying Diagnosis'},
            'kb_verdict': 'clarifying_questions',
            'needs_review': False,
            'grounding': {'verified': True, 'issues': []},
        }

    if "syringe" in question_lower and ("helps for an hour" in question_lower or "helps" in question_lower):
        lines.extend([
            "",
            "**Most useful next checks:**",
            "- **Relief pattern**: if syringing helps briefly, ask whether the plant is getting temperature relief only or actually regaining water access.",
            "- **Roots and oxygen**: check root depth, root color, and whether the top stays wet while the plant still runs out of function by afternoon.",
            "- **Surface pattern**: worst on exposed ridges, compacted walk-on zones, soft low spots, or the most aggressively pushed greens?",
            "",
            "**What I'd be thinking about first:**",
            "- A short syringe response usually says the canopy is buying time, not that the underlying stress is solved.",
            "- That points me back to root capacity, oxygen, and daily heat load before I treat it like a disease-only problem.",
            "",
            '**Fastest reply format:** "Bentgrass greens, syringing helps for an hour, shallow roots, surface stays damp, worst by late afternoon on the hardest-pushed greens."',
        ])
        return {
            'answer': "\n".join(lines),
            'sources': [],
            'confidence': {'score': 58, 'label': 'Clarifying Diagnosis'},
            'kb_verdict': 'clarifying_questions',
            'needs_review': False,
            'grounding': {'verified': True, 'issues': []},
        }

    if ("roots are short" in question_lower and "top stays wet" in question_lower) or ("canopy still wilts" in question_lower):
        lines.extend([
            "",
            "**Most useful next checks:**",
            "- **Root and moisture mismatch**: confirm whether the profile is truly wet by depth or just wet on top over a stressed, shallow root system.",
            "- **Smell and color**: dark, sour, shallow roots point you toward oxygen failure or root disease faster than the canopy does.",
            "- **Pattern**: low spots, layering, irrigation arcs, or surfaces that stay soft longest after watering?",
            "",
            "**What I'd be thinking about first:**",
            "- That combination smells more like a root-function problem than a simple dry-down problem.",
            "- The fast split is wet wilt / oxygen loss versus a root-disease layer riding on top of the same wet profile.",
            "",
            '**Fastest reply format:** "Bentgrass greens, roots are short and dark, top stays wet, canopy still wilts by afternoon, worst in low spots after humid nights."',
        ])
        return {
            'answer': "\n".join(lines),
            'sources': [],
            'confidence': {'score': 58, 'label': 'Clarifying Diagnosis'},
            'kb_verdict': 'clarifying_questions',
            'needs_review': False,
            'grounding': {'verified': True, 'issues': []},
        }

    if ("what am i missing" in question_lower and ("roots are there" in question_lower or "not recovering" in question_lower)) or ("surviving but not recovering" in question_lower):
        lines.extend([
            "",
            "**Most useful next checks:**",
            "- **Recovery versus survival**: the question is whether the plant still has enough root and carbohydrate capacity to rebound, not just limp through the day.",
            "- **Stress stack**: mowing, rolling, heat, humidity, traffic, and PGR often explain poor recovery better than one missing spray.",
            "- **Surface pattern**: is the whole property flat, or only the surfaces carrying the most pace and traffic pressure?",
            "",
            "**What I'd be thinking about first:**",
            "- When roots are present but the plant still has no bounce, I start thinking about recovery capacity and stress budget before I think about another product slot.",
            "- Surviving is not the same as recovering. That usually means the plant is spending everything it has just to hold on.",
            "",
            '**Fastest reply format:** "Bentgrass greens, roots are present but short, plant survives the day but does not rebound, heavy rolling, humid week, weakest on the most pushed surfaces."',
        ])
        return {
            'answer': "\n".join(lines),
            'sources': [],
            'confidence': {'score': 58, 'label': 'Clarifying Diagnosis'},
            'kb_verdict': 'clarifying_questions',
            'needs_review': False,
            'grounding': {'verified': True, 'issues': []},
        }

    if (
        "disease app looks fine on paper" in question_lower
        or "green still has no life" in question_lower
        or ("what are you checking" in question_lower and "disease" in question_lower)
        or ("weak patch" in question_lower and ("spray" in question_lower or "overlooking" in question_lower))
    ):
        lines.extend([
            "",
            "**Most useful next checks:**",
            "- **Recovery capacity**: compare roots, clipping response, and daily rebound before assuming the disease program is what failed.",
            "- **Stress stack**: rolling, mowing, heat, humidity, low oxygen, and pace pressure can leave the plant flat even when the fungicide program is defensible.",
            "- **Pattern**: same weak greens every time, soft low spots, traffic corridors, or random patches that truly behave like a disease front?",
            "",
            "**What I'd be thinking about first:**",
            "- When the spray program looks fine on paper and the green still has no life, I start with plant recovery capacity before I reach for another product.",
            "- If every weak patch keeps turning into a spray decision, there is a good chance the property is yelling about roots, oxygen, traffic, or stress budget instead.",
            "",
            '**Fastest reply format:** "Bentgrass greens, fungicide program current, surface still flat, roots short, heavy rolling, humid week, weakest in the same low greens."',
        ])
        return {
            'answer': "\n".join(lines),
            'sources': [],
            'confidence': {'score': 58, 'label': 'Clarifying Diagnosis'},
            'kb_verdict': 'clarifying_questions',
            'needs_review': False,
            'grounding': {'verified': True, 'issues': []},
        }

    if ("poa" in question_lower and "bent" in question_lower and ("hanging on" in question_lower or "melt" in question_lower)):
        lines.extend([
            "",
            "**Most useful next checks:**",
            "- **Species split**: where Poa is melting first, compare root depth, traffic load, and moisture pattern against the bent in the same area.",
            "- **Stress direction**: ask whether this looks like normal species separation under heat load or whether both species are weak and Poa is just showing it first.",
            "- **Surface pattern**: collars, old Poa pockets, wet low areas, shade, or the highest-pressure greens?",
            "",
            "**What I'd be thinking about first:**",
            "- Poa failing while bent hangs on usually reads like species heat and recovery physiology before it reads like a random disease surprise.",
            "- The next question is whether the bent still has recovery room, or whether Poa is just the first part of the surface to give way.",
            "",
            '**Fastest reply format:** "Bent/Poa greens, Poa melting first, bent still hanging on, worst in wet low spots after warm nights, roots shorter in the Poa pockets."',
        ])
        return {
            'answer': "\n".join(lines),
            'sources': [],
            'confidence': {'score': 58, 'label': 'Clarifying Diagnosis'},
            'kb_verdict': 'clarifying_questions',
            'needs_review': False,
            'grounding': {'verified': True, 'issues': []},
        }

    if ("monday" in question_lower and "friday" in question_lower) or ("tired by friday" in question_lower):
        lines.extend([
            "",
            "**Most useful next checks:**",
            "- **Stress stack across the week**: mowing, rolling, traffic, heat, humidity, PGR, and pace pressure all count together.",
            "- **Recovery signal**: are roots still strong by midweek, or does the plant just look okay early and then fade each afternoon?",
            "- **Pattern**: all greens, the most pushed greens, shaded pockets, low spots, or only the surfaces with the most mechanical pressure?",
            "- **Moisture by depth**: is the canopy getting through Monday but the rootzone running out of oxygen or usable water by Thursday?",
            "",
            "**What I'd be thinking about first:**",
            "- This often acts more like cumulative recovery loss than one isolated disease event.",
            "- If the same greens fade later in the week, look hard at roots, moisture-by-depth, and how much stress the surface is carrying by Thursday.",
            "",
            '**Fastest reply format:** "Bentgrass greens, start clean Monday, worst by Friday afternoon, shallow roots on the weakest greens, heavy rolling, humid week."',
        ])
        return {
            'answer': "\n".join(lines),
            'sources': [],
            'confidence': {'score': 58, 'label': 'Clarifying Diagnosis'},
            'kb_verdict': 'clarifying_questions',
            'needs_review': False,
            'grounding': {'verified': True, 'issues': []},
        }

    if (
        ("8 am" in question_lower and "2 pm" in question_lower)
        or ("looks okay at" in question_lower and "rough by" in question_lower)
    ):
        lines.extend([
            "",
            "**Most useful next checks:**",
            "- **Afternoon collapse pattern**: does it recover by the next morning or stay weak overnight?",
            "- **Moisture and roots**: top-inch readings, deeper moisture, and whether roots are short, dark, or just shallow.",
            "- **Microclimate**: worst on exposed slopes, low-airflow pockets, soft wet areas, or traffic-heavy spots?",
            "- **Recent pressure**: hand-watering, syringing, rolling, PGR, and any change in mowing or weather load.",
            "",
            "**What I'd be thinking about first:**",
            "- First thought is midday stress expression: water access, oxygen, and root capacity before blaming disease.",
            "- If it looks fine in the morning and rough by early afternoon, the plant may be losing the daily stress fight even if color still looks acceptable at sunrise.",
            "",
            '**Fastest reply format:** "Bentgrass greens, fine at 8 am, rough by 2 pm, worst on exposed greens, shallow roots, hot humid afternoons, no lesions."',
        ])
        return {
            'answer': "\n".join(lines),
            'sources': [],
            'confidence': {'score': 58, 'label': 'Clarifying Diagnosis'},
            'kb_verdict': 'clarifying_questions',
            'needs_review': False,
            'grounding': {'verified': True, 'issues': []},
        }

    if "greens" in question_lower and "struggling" in question_lower:
        lines.extend([
            "",
            "**Most useful next checks:**",
            "- **Which greens or which pattern**: all greens, the worst few, shaded pockets, low spots, or high-traffic areas?",
            "- **Root condition**: normal depth, short and dark, or healthy white roots?",
            "- **Water status**: staying wet, drying out fast, or soft/puffy?",
            "- **Recent stress stack**: heat, humidity, rolling, mowing pressure, PGR, traffic, or a spray change?",
            "",
            "**What not to do yet:**",
            "- Do not call this one cause across every green until the pattern and roots line up.",
            "",
            '**Fastest reply format:** "Bentgrass greens, worst on low shaded greens, humid week, soft surface, roots shallow and dark."',
        ])
        return {
            'answer': "\n".join(lines),
            'sources': [],
            'confidence': {'score': 52, 'label': 'Clarifying Diagnosis'},
            'kb_verdict': 'clarifying_questions',
            'needs_review': False,
            'grounding': {'verified': True, 'issues': []},
        }

    if "root" in question_lower:
        lines.extend([
            "",
            "**Most useful next checks:**",
            "- **Surface and turf** if it is not already clear.",
            "- **Root depth and color**: healthy white, short and dark, pruned, or water-soaked?",
            "- **Moisture by depth**: just the top inch wet, or the full rootzone staying wet?",
            "- **Stress pattern**: heat, traffic, low spots, shade, salinity, or recent chemistry?",
            "",
            "**What not to do yet:**",
            "- Do not treat roots as a product problem first if we have not separated wetness, oxygen, and chemistry.",
            "",
            '**Fastest reply format:** "Bentgrass greens, roots are short and dark in low spots, top stays wet, hot humid week."',
        ])
        return {
            'answer': "\n".join(lines),
            'sources': [],
            'confidence': {'score': 52, 'label': 'Clarifying Diagnosis'},
            'kb_verdict': 'clarifying_questions',
            'needs_review': False,
            'grounding': {'verified': True, 'issues': []},
        }

    if "soft" in question_lower or "puffy" in question_lower:
        lines.extend([
            "",
            "**Most useful next checks:**",
            "- **Surface and turf** if that part is not already clear.",
            "- **Pattern**: whole green, low spots, shaded areas, or only the hardest-pushed surfaces?",
            "- **Water status**: staying wet, shallow dry over wet, or just soft after irrigation and humidity?",
            "- **Recent stress stack**: heat, humidity, mowing, rolling, topdressing, PGR, or repeated traffic.",
            "",
            "**What not to do yet:**",
            "- Do not chase firmness or speed first if the plant is already telling us recovery capacity is thin.",
            "",
            '**Fastest reply format:** "Bentgrass greens, soft after humid nights, worst on low greens, roots shallow, heavy rolling this week."',
        ])
        return {
            'answer': "\n".join(lines),
            'sources': [],
            'confidence': {'score': 52, 'label': 'Clarifying Diagnosis'},
            'kb_verdict': 'clarifying_questions',
            'needs_review': False,
            'grounding': {'verified': True, 'issues': []},
        }

    if "thinning" in question_lower or "decline" in question_lower or "stress" in question_lower:
        lines.extend([
            "",
            "**Most useful next checks:**",
            "- **Surface and turf**" + ("" if mentions_surface or known_surface_names else ": greens, fairways, tees, or rough."),
            "- **Pattern**: shade, traffic, low spots, irrigation coverage, rings, or random patches?",
            "- **Leaf and root evidence**: lesions/signs versus weak roots versus mechanical injury.",
            "- **Recent conditions**: heat, humidity, rainfall, hand-watering, PGR, rolling, or spray history.",
            "",
            "**What not to do yet:**",
            "- Do not force a disease answer until the pattern and plant evidence make it earn that call.",
            "",
            '**Fastest reply format:** "Bentgrass greens, thinning in shaded collars after humid weather, no mycelium, roots okay, lots of traffic."',
        ])
        return {
            'answer': "\n".join(lines),
            'sources': [],
            'confidence': {'score': 52, 'label': 'Clarifying Diagnosis'},
            'kb_verdict': 'clarifying_questions',
            'needs_review': False,
            'grounding': {'verified': True, 'issues': []},
        }

    if has_diagnosis_shape:
        lines.extend([
            "",
            "**Most useful next checks:**",
            "- **Surface and turf** if that part is not already clear.",
            "- **Pattern**: low spots, shade, traffic, irrigation coverage, rings, or random patches?",
            "- **Root condition**: healthy white roots, short dark roots, or a profile that looks stressed before the leaves do?",
            "- **Plant evidence**: leaf lesions/signs or obvious mechanical injury once the root picture is clearer.",
            "- **Recent conditions**: heat, humidity, rainfall, hand-watering, mowing, rolling, PGR, or a spray change.",
            "",
            "**What not to do yet:**",
            "- Do not skip the field pattern, because that is usually what separates the real signal from the noise.",
            "",
            '**Fastest reply format:** "Bentgrass greens, low spots stay wet, humid week, no lesions, shallow roots, recent rolling and PGR."',
        ])
        return {
            'answer': "\n".join(lines),
            'sources': [],
            'confidence': {'score': 52, 'label': 'Clarifying Diagnosis'},
            'kb_verdict': 'clarifying_questions',
            'needs_review': False,
            'grounding': {'verified': True, 'issues': []},
        }

    if not mentions_surface or not mentions_turf:
        return _build_general_context_response(profile)
    return None

    return None


# -----------------------------------------------------------------------------
# Auth routes
# -----------------------------------------------------------------------------

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        payload = _request_json() if request.is_json else request.form
        rate_limited = _rate_limit_response(
            "login",
            limit=10,
            window_seconds=900,
            html_template='login.html',
            template_context={
                'next_url': request.args.get('next', '/'),
                'form_data': {'email': payload.get('email', '')},
            },
        )
        if rate_limited:
            return rate_limited
        email = payload.get('email')
        password = payload.get('password')
        account = verify_credentials(email or '', password or '')
        if not account:
            if request.is_json:
                return jsonify({'success': False, 'error': 'Invalid email or password.'}), 401
            flash('Invalid email or password.', 'error')
            return render_template(
                'login.html',
                next_url=request.args.get('next', '/'),
                form_data={'email': email or ''},
            )
        if Config.REQUIRE_EMAIL_VERIFICATION and not account.get('email_verified_at'):
            message = 'Verify your email before signing in.'
            if request.is_json:
                return jsonify({'success': False, 'error': message, 'requires_email_verification': True}), 403
            flash(message, 'error')
            return render_template(
                'login.html',
                next_url=request.args.get('next', '/'),
                form_data={'email': email or ''},
            )
        _login_account(account)
        next_url = request.args.get('next') or url_for('home')
        if request.is_json:
            return jsonify({'success': True, 'account': account, 'next': next_url})
        return redirect(next_url)
    return render_template('login.html', next_url=request.args.get('next', '/'), form_data={})


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        payload = _request_json() if request.is_json else request.form
        rate_limited = _rate_limit_response(
            "register",
            limit=5,
            window_seconds=3600,
            html_template='register.html',
            template_context={
                'form_data': {
                    'name': payload.get('name', ''),
                    'organization': payload.get('organization', ''),
                    'email': payload.get('email', ''),
                    'accept_terms': str(payload.get('accept_terms', '')).lower() in {'1', 'true', 'on', 'yes'},
                    'accept_privacy': str(payload.get('accept_privacy', '')).lower() in {'1', 'true', 'on', 'yes'},
                },
            },
        )
        if rate_limited:
            return rate_limited
        account, error = create_account(
            payload.get('email', ''),
            payload.get('password', ''),
            name=payload.get('name', ''),
            organization=payload.get('organization', ''),
            accepted_terms=str(payload.get('accept_terms', '')).lower() in {'1', 'true', 'on', 'yes'},
            accepted_privacy=str(payload.get('accept_privacy', '')).lower() in {'1', 'true', 'on', 'yes'},
        )
        if error:
            if request.is_json:
                return jsonify({'success': False, 'error': error}), 400
            flash(error, 'error')
            return render_template(
                'register.html',
                form_data={
                    'name': payload.get('name', ''),
                    'organization': payload.get('organization', ''),
                    'email': payload.get('email', ''),
                    'accept_terms': str(payload.get('accept_terms', '')).lower() in {'1', 'true', 'on', 'yes'},
                    'accept_privacy': str(payload.get('accept_privacy', '')).lower() in {'1', 'true', 'on', 'yes'},
                },
            )
        verification_token = create_email_verification_token(account['email'])
        verify_url = None
        email_sent = False
        if verification_token:
            verify_url = url_for('verify_email', token=verification_token, _external=True)
            email_sent = _send_email_verification_email(account['email'], verify_url)
        if Config.REQUIRE_EMAIL_VERIFICATION:
            if request.is_json:
                payload = {'success': True, 'account': account}
                if verify_url and Config.APP_ENV != 'production':
                    payload['verify_url'] = verify_url
                    payload['verification_email_sent'] = email_sent
                payload['requires_email_verification'] = True
                return jsonify(payload), 202
            flash('Account created. Verify your email before signing in.', 'success')
            if verify_url and Config.APP_ENV != 'production':
                flash(f"Development verification link: {verify_url}", 'success')
            return redirect(url_for('login'))
        _login_account(account)
        if request.is_json:
            payload = {'success': True, 'account': account}
            if verify_url and Config.APP_ENV != 'production':
                payload['verify_url'] = verify_url
                payload['verification_email_sent'] = email_sent
            return jsonify(payload)
        if verify_url and Config.APP_ENV != 'production':
            flash(f"Development verification link: {verify_url}", 'success')
        return redirect(url_for('home'))
    return render_template('register.html', form_data={})


@app.route('/verify-email/<token>', methods=['GET'])
def verify_email(token):
    account = get_email_verification_account(token)
    if not account:
        flash('That verification link is no longer valid.', 'error')
        return redirect(url_for('login'))
    verified_account, error = consume_email_verification_token(token)
    if error:
        flash(error, 'error')
        return redirect(url_for('login'))
    _login_account(verified_account)
    flash('Email verified. You are signed in now.', 'success')
    return redirect(url_for('account_settings'))


@app.route('/resend-verification', methods=['POST'])
def resend_verification():
    payload = _request_json() if request.is_json else request.form
    email = payload.get('email', '')
    account = get_account_by_email(email)
    message = "If that account exists and still needs verification, we've sent a fresh verification link."
    verify_url = None
    email_sent = False
    if account and not account.get('email_verified_at'):
        token = create_email_verification_token(account['email'])
        if token:
            verify_url = url_for('verify_email', token=token, _external=True)
            email_sent = _send_email_verification_email(account['email'], verify_url)
    if request.is_json:
        response = {'success': True, 'message': message}
        if verify_url and Config.APP_ENV != 'production':
            response['verify_url'] = verify_url
            response['verification_email_sent'] = email_sent
        return jsonify(response)
    flash(message, 'success')
    if verify_url and Config.APP_ENV != 'production':
        flash(f"Development verification link: {verify_url}", 'success')
    return redirect(url_for('login'))


@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        payload = _request_json() if request.is_json else request.form
        rate_limited = _rate_limit_response(
            "forgot-password",
            limit=5,
            window_seconds=900,
            html_template="forgot_password.html",
            template_context={"form_data": {"email": payload.get("email", "")}},
        )
        if rate_limited:
            return rate_limited

        email = payload.get('email', '')
        token = create_password_reset_token(email)
        reset_url = None
        email_sent = False
        if token:
            reset_url = url_for('reset_password', token=token, _external=True)
            email_sent = _send_password_reset_email(email, reset_url)

        message = "If that email is in the system, we've sent password reset instructions."
        payload_data = {'success': True, 'message': message}
        if reset_url and Config.APP_ENV != 'production':
            payload_data['reset_url'] = reset_url
            payload_data['email_sent'] = email_sent

        if request.is_json:
            return jsonify(payload_data)

        flash(message, 'success')
        if reset_url and Config.APP_ENV != 'production':
            flash(f"Development reset link: {reset_url}", 'success')
        return redirect(url_for('login'))

    return render_template('forgot_password.html', form_data={})


@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    reset_account = get_password_reset_account(token)
    if not reset_account and request.method == 'GET':
        flash('That reset link is no longer valid.', 'error')
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        payload = _request_json() if request.is_json else request.form
        rate_limited = _rate_limit_response(
            "reset-password",
            limit=8,
            window_seconds=900,
            html_template="reset_password.html",
            template_context={"token": token},
        )
        if rate_limited:
            return rate_limited

        new_password = payload.get('new_password', '')
        confirm_password = payload.get('confirm_password', '')
        if new_password != confirm_password:
            if request.is_json:
                return jsonify({'success': False, 'error': 'Passwords do not match.'}), 400
            flash('Passwords do not match.', 'error')
            return render_template('reset_password.html', token=token)

        account, error = consume_password_reset_token(token, new_password)
        if error:
            if request.is_json:
                return jsonify({'success': False, 'error': error}), 400
            flash(error, 'error')
            return render_template('reset_password.html', token=token)

        _login_account(account)
        if request.is_json:
            return jsonify({'success': True, 'account': account})
        flash('Password updated. You are signed in now.', 'success')
        return redirect(url_for('account_settings'))

    return render_template('reset_password.html', token=token)


@app.route('/account', methods=['GET', 'POST'])
@login_required
def account_settings():
    account = _current_account()
    if request.method == 'POST':
        payload = _request_json() if request.is_json else request.form
        form_name = payload.get('form_name') or 'workspace'
        updated_account, error = update_account(
            account['id'],
            name=payload.get('name'),
            organization=payload.get('organization'),
            current_password=payload.get('current_password'),
            new_password=payload.get('new_password'),
        )
        if error:
            if request.is_json:
                return jsonify({'success': False, 'error': error}), 400
            flash(error, 'error')
            profile = _augment_course_profile(load_course_profile(_get_profile_key()))
            return render_template(
                'account.html',
                account=account,
                course_profile=profile,
                profile_health=_course_profile_health(profile),
            )

        _login_account(updated_account)
        updated_profile = _augment_course_profile(
            update_course_profile(_account_course_profile_payload(payload), _get_profile_key())
        )
        if request.is_json:
            return jsonify({
                'success': True,
                'account': updated_account,
                'profile': updated_profile,
                'profile_health': _course_profile_health(updated_profile),
            })
        if form_name == 'course_context':
            flash('Course context updated.', 'success')
        else:
            flash('Account settings updated.', 'success')
        return redirect(url_for('account_settings'))

    profile = _augment_course_profile(load_course_profile(_get_profile_key()))
    return render_template(
        'account.html',
        account=account,
        course_profile=profile,
        profile_health=_course_profile_health(profile),
    )


@app.route('/account/export')
@login_required
def account_export():
    account = _current_account()
    payload = _account_export_payload(account)
    response = jsonify(payload)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    response.headers['Content-Disposition'] = f'attachment; filename=turf-account-export-{timestamp}.json'
    return response


@app.route('/account/delete', methods=['POST'])
@login_required
def account_delete():
    account = _current_account()
    payload = _request_json() if request.is_json else request.form
    current_password = payload.get('current_password', '')
    confirm_email = str(payload.get('confirm_email', '')).strip().lower()

    if confirm_email != str(account.get('email', '')).strip().lower():
        message = "Type your full account email to confirm deletion."
        if request.is_json:
            return jsonify({'success': False, 'error': message}), 400
        flash(message, 'error')
        return redirect(url_for('account_settings'))

    verified = verify_credentials(account.get('email', ''), current_password)
    if not verified:
        message = "Current password is incorrect."
        if request.is_json:
            return jsonify({'success': False, 'error': message}), 400
        flash(message, 'error')
        return redirect(url_for('account_settings'))

    deleted_profile = delete_course_profile(account['id'])
    deleted_conversations = delete_account_conversations(account['id'])
    deleted_account, error = delete_account(account['id'])
    if error:
        if request.is_json:
            return jsonify({'success': False, 'error': error}), 400
        flash(error, 'error')
        return redirect(url_for('account_settings'))

    _logout_account()
    for key in ('session_id', 'conversation_id', 'last_topic', 'last_subject'):
        session.pop(key, None)

    result = {
        'success': True,
        'deleted_account': deleted_account,
        'deleted_course_profile': deleted_profile,
        'deleted_conversations': deleted_conversations,
    }
    if request.is_json:
        return jsonify(result)
    flash('Your account data has been deleted.', 'success')
    return redirect(url_for('home'))


@app.route('/logout', methods=['POST'])
def logout():
    _logout_account()
    for key in ('session_id', 'conversation_id', 'last_topic', 'last_subject'):
        session.pop(key, None)
    if request.is_json:
        return jsonify({'success': True})
    return redirect(url_for('home'))


@app.route('/terms')
def terms():
    return render_template('terms.html')


@app.route('/privacy')
def privacy():
    return render_template('privacy.html')


# -----------------------------------------------------------------------------
# Session routes
# -----------------------------------------------------------------------------

@app.route('/api/new-session', methods=['POST'])
def new_session():
    """Clear session to start a new conversation."""
    for key in ('session_id', 'conversation_id', 'last_topic', 'last_subject'):
        session.pop(key, None)
    return jsonify({'success': True})


# -----------------------------------------------------------------------------
# Admin routes
# -----------------------------------------------------------------------------

@app.route('/admin')
def admin_dashboard():
    from cache import get_embedding_cache, get_source_url_cache
    from feedback_system import get_feedback_stats, get_recent_feedback

    initial_stats = get_feedback_stats() or {}

    emb_cache = get_embedding_cache().stats()
    url_cache = get_source_url_cache().stats()
    total_cache = int(emb_cache.get('hits', 0) or 0) + int(emb_cache.get('misses', 0) or 0)
    initial_cache_rate = f"{round((int(emb_cache.get('hits', 0) or 0) / total_cache) * 100)}%" if total_cache else "0%"

    ready = int(initial_stats.get('approved_for_training', 0) or 0)
    needed = 50
    training_percent = min(round((ready / needed) * 100), 100) if needed else 0
    training_text = (
        f"Ready to train! {ready} approved examples"
        if ready >= needed
        else f"{ready} of {needed} approved examples needed"
    )

    recent_questions = get_recent_feedback(limit=8)

    return render_template(
        'admin.html',
        initial_stats=initial_stats,
        initial_cache_rate=initial_cache_rate,
        initial_embedding_cache=emb_cache,
        initial_url_cache=url_cache,
        initial_recent_questions=recent_questions,
        initial_training_percent=training_percent,
        initial_training_text=training_text,
        initial_course_profile=_augment_course_profile(load_course_profile(_get_profile_key()))
    )


@app.route('/admin/stats')
def admin_stats():
    from feedback_system import get_feedback_stats
    return jsonify(get_feedback_stats())


@app.route('/admin/cache')
def admin_cache_stats():
    """Get cache statistics for monitoring."""
    from cache import get_embedding_cache, get_source_url_cache, get_search_cache
    return jsonify({
        'embedding_cache': get_embedding_cache().stats(),
        'source_url_cache': get_source_url_cache().stats(),
        'search_cache': get_search_cache().stats()
    })


@app.route('/admin/course-profile')
def admin_course_profile():
    """Return the saved course profile memory."""
    return jsonify(_augment_course_profile(load_course_profile(_get_profile_key())))


@app.route('/admin/course-profile', methods=['POST'])
def admin_save_course_profile():
    """Update the saved course profile memory from admin tooling."""
    profile = update_course_profile(_request_json(), _get_profile_key())
    return jsonify({'success': True, 'profile': _augment_course_profile(profile)})


@app.route('/admin/feedback/review')
def admin_feedback_review():
    from feedback_system import get_negative_feedback
    return jsonify(get_negative_feedback(limit=100, unreviewed_only=True))


@app.route('/admin/feedback/needs-review')
def admin_needs_review():
    """Get queries that were auto-flagged for human review (< 70% confidence)"""
    from feedback_system import get_queries_needing_review
    return jsonify(get_queries_needing_review(limit=100))


@app.route('/admin/feedback/all')
def admin_feedback_all():
    from feedback_system import get_all_feedback
    return jsonify(get_all_feedback(limit=100))


@app.route('/admin/feedback/approve', methods=['POST'])
def admin_approve_feedback():
    from feedback_system import approve_for_training
    data = _request_json()
    feedback_id = data.get('id')
    if not feedback_id:
        return jsonify({'success': False, 'error': 'Missing feedback id'}), 400
    if not approve_for_training(feedback_id, data.get('correction'), moderator=_moderator_identity()):
        return jsonify({'success': False, 'error': 'Feedback not found'}), 404
    return jsonify({'success': True})


@app.route('/admin/feedback/reject', methods=['POST'])
def admin_reject_feedback():
    from feedback_system import reject_feedback
    data = _request_json()
    feedback_id = data.get('id')
    if not feedback_id:
        return jsonify({'success': False, 'error': 'Missing feedback id'}), 400
    notes = data.get('notes') or "Rejected by admin"
    if not reject_feedback(feedback_id, notes, moderator=_moderator_identity()):
        return jsonify({'success': False, 'error': 'Feedback not found'}), 404
    return jsonify({'success': True})


@app.route('/admin/review-queue')
def admin_review_queue():
    """Get unified moderation queue (user-flagged + auto-flagged)"""
    from feedback_system import get_feedback_feed_page, get_review_queue
    queue_type = request.args.get('type', 'all')  # all, negative, low_confidence
    limit = request.args.get('limit', 100, type=int)
    offset = request.args.get('offset', 0, type=int)
    if queue_type == 'all':
        return jsonify(get_feedback_feed_page(limit=limit, offset=offset))
    full_queue = get_review_queue(limit=None, queue_type=queue_type)
    items = full_queue[offset:offset + limit]
    next_offset = offset + len(items)
    return jsonify({
        'items': items,
        'total': len(full_queue),
        'offset': offset,
        'limit': limit,
        'next_offset': next_offset,
        'has_more': next_offset < len(full_queue),
    })


@app.route('/admin/action-center')
def admin_action_center():
    from feedback_system import get_action_center_summary
    return jsonify(get_action_center_summary())


@app.route('/admin/moderate', methods=['POST'])
def admin_moderate():
    """Moderate an answer: approve, reject, or correct"""
    from feedback_system import moderate_answer
    data = _request_json()
    feedback_id = data.get('id')
    action = str(data.get('action') or '').strip().lower()
    if not feedback_id or not action:
        return jsonify({'success': False, 'error': 'Missing moderation id or action'}), 400
    if action not in {'approve', 'reject', 'correct'}:
        return jsonify({'success': False, 'error': 'Invalid moderation action'}), 400
    result = moderate_answer(
        feedback_id=feedback_id,
        action=action,  # approve, reject, correct
        corrected_answer=data.get('corrected_answer'),
        reason=data.get('reason'),
        moderator=data.get('moderator') or _moderator_identity()
    )
    return jsonify(result)


@app.route('/admin/moderator-history')
def admin_moderator_history():
    """Get audit trail of moderator actions"""
    from feedback_system import get_moderator_history
    return jsonify(get_moderator_history(limit=100))


@app.route('/admin/training/generate', methods=['POST'])
def admin_generate_training():
    from feedback_system import generate_training_file
    from fine_tuning import MIN_EXAMPLES_FOR_TRAINING
    result = generate_training_file(min_examples=MIN_EXAMPLES_FOR_TRAINING)
    if result:
        filepath, num_examples = result
        return jsonify({'success': True, 'filepath': filepath, 'num_examples': num_examples})
    return jsonify({'success': False, 'message': 'Not enough examples to generate training file'})


@app.route('/admin/knowledge')
def admin_knowledge_status():
    """Get knowledge base status."""
    from knowledge_builder import IndexTracker, scan_for_pdfs
    tracker = IndexTracker()
    stats = tracker.get_stats()

    all_pdfs = scan_for_pdfs()
    unindexed = [f for f, _ in all_pdfs if not tracker.is_indexed(f)]

    return jsonify({
        'indexed_files': stats['total_files'],
        'total_chunks': stats['total_chunks'],
        'last_run': stats['last_run'],
        'total_pdfs': len(all_pdfs),
        'unindexed': len(unindexed),
        'unindexed_sample': [os.path.basename(f) for f in unindexed[:10]]
    })


@app.route('/admin/knowledge/audit')
def admin_knowledge_audit():
    """Audit structured product records against local label sources."""
    from scripts.audit_structured_kb import run_audit
    return jsonify(run_audit())


@app.route('/admin/kb-quality-dashboard')
def admin_kb_quality_dashboard():
    """Summarize review coverage, risky records, open KB gaps, and regression health."""
    payload = _kb_quality_dashboard_payload()
    payload['trust_gate'] = _kb_trust_gate_payload(payload)
    return jsonify(payload)


@app.route('/admin/eval-dashboard')
def admin_eval_dashboard():
    """Return live eval-suite summaries for admin quality review."""
    refresh = request.args.get('refresh', '').lower() == 'true'
    return jsonify(_eval_dashboard_payload(force_refresh=refresh))


@app.route('/admin/kb-gaps')
def admin_kb_gaps():
    """Return structured KB gap work items."""
    from feedback_system import get_kb_gaps
    status = request.args.get('status', 'open')
    limit = int(request.args.get('limit', 100))
    return jsonify(get_kb_gaps(
        status=status,
        limit=limit,
        gap_type=request.args.get('gap_type') or None,
        target=request.args.get('target') or None,
        product=request.args.get('product') or None,
        surface=request.args.get('surface') or None,
    ))


@app.route('/admin/kb-gap-stats')
def admin_kb_gap_stats():
    """Return KB gap dashboard stats."""
    from feedback_system import get_kb_gap_stats
    return jsonify(get_kb_gap_stats())


@app.route('/admin/expert-router-events')
def admin_expert_router_events():
    """List recent expert router telemetry for review."""
    from feedback_system import get_expert_router_events

    limit = int(request.args.get('limit', 100))
    selected_mode = request.args.get('selected_mode', 'all')
    needs_review_arg = request.args.get('needs_review')
    deterministic_arg = request.args.get('deterministic')

    needs_review = None if needs_review_arg in (None, '', 'all') else needs_review_arg.lower() == 'true'
    deterministic = None if deterministic_arg in (None, '', 'all') else deterministic_arg.lower() == 'true'

    return jsonify(get_expert_router_events(
        limit=limit,
        selected_mode=selected_mode,
        needs_review=needs_review,
        deterministic=deterministic,
    ))


@app.route('/admin/expert-router-stats')
def admin_expert_router_stats():
    """Return expert router telemetry summary."""
    from feedback_system import get_expert_router_stats
    return jsonify(get_expert_router_stats())


@app.route('/admin/expert-router-backlog')
def admin_expert_router_backlog():
    """Return grouped router-review backlog patterns."""
    from feedback_system import get_expert_router_backlog
    return jsonify(get_expert_router_backlog(limit=int(request.args.get('limit', 20))))


@app.route('/admin/expert-router-work-items')
def admin_expert_router_work_items():
    """List router backlog work items."""
    from feedback_system import get_expert_router_work_items
    return jsonify(get_expert_router_work_items(
        status=request.args.get('status', 'all'),
        limit=int(request.args.get('limit', 100)),
    ))


@app.route('/admin/expert-router-backlog/work-items', methods=['POST'])
def admin_create_expert_router_work_item():
    """Create a tracked work item from a router backlog pattern."""
    from feedback_system import create_expert_router_work_item
    data = _request_json()
    result = create_expert_router_work_item(
        pattern_key=data.get('pattern_key', ''),
        notes=data.get('notes'),
    )
    return jsonify(result), 200 if result.get('success') else 400


@app.route('/admin/expert-router-work-items/<int:work_item_id>/status', methods=['POST'])
def admin_update_expert_router_work_item_status(work_item_id):
    """Update router backlog work item status."""
    from feedback_system import update_expert_router_work_item_status
    data = _request_json()
    result = update_expert_router_work_item_status(
        work_item_id,
        status=data.get('status', 'draft'),
        notes=data.get('notes'),
    )
    return jsonify(result), 200 if result.get('success') else 400


@app.route('/admin/expert-router-work-items/<int:work_item_id>/generate-draft', methods=['POST'])
def admin_generate_expert_router_work_item_draft(work_item_id):
    """Generate the next best draft artifact for a router work item."""
    from feedback_system import generate_expert_router_work_item_draft
    data = _request_json()
    result = generate_expert_router_work_item_draft(
        work_item_id,
        reviewer=data.get('reviewer', 'admin'),
    )
    return jsonify(result), 200 if result.get('success') else 400


@app.route('/admin/expert-router-events/<int:event_id>/review', methods=['POST'])
def admin_review_expert_router_event(event_id):
    """Mark a router event reviewed or keep it flagged with notes."""
    from feedback_system import review_expert_router_event
    data = _request_json()
    result = review_expert_router_event(
        event_id,
        needs_review=data.get('needs_review', False),
        notes=data.get('notes'),
    )
    return jsonify(result), 200 if result.get('success') else 404


@app.route('/admin/kb-gaps/bulk', methods=['POST'])
def admin_bulk_kb_gaps():
    """Bulk resolve, ignore, or reopen structured KB gap work items."""
    from feedback_system import bulk_resolve_kb_gaps
    data = _request_json()
    result = bulk_resolve_kb_gaps(
        data.get('gap_ids', []),
        status=data.get('status', 'resolved'),
        notes=data.get('notes'),
    )
    return jsonify(result), 200 if result.get('success') else 400


@app.route('/admin/kb-regression-tests')
def admin_kb_regression_tests():
    """List captured KB regression questions."""
    from feedback_system import get_kb_regression_tests
    return jsonify(get_kb_regression_tests(
        status=request.args.get('status', 'active'),
        limit=int(request.args.get('limit', 100)),
    ))


@app.route('/admin/kb-gaps/<int:gap_id>')
def admin_kb_gap_detail(gap_id):
    """Return KB gap detail with product/label candidates."""
    from feedback_system import get_kb_gap_detail
    detail = get_kb_gap_detail(gap_id)
    if not detail:
        return jsonify({'success': False, 'error': 'KB gap not found'}), 404
    return jsonify(detail)


@app.route('/admin/kb-gaps/<int:gap_id>/resolve', methods=['POST'])
def admin_resolve_kb_gap(gap_id):
    """Resolve, ignore, or reopen a structured KB gap work item."""
    from feedback_system import resolve_kb_gap
    data = _request_json()
    return jsonify(resolve_kb_gap(
        gap_id,
        status=data.get('status', 'resolved'),
        notes=data.get('notes'),
    ))


@app.route('/admin/kb-gaps/<int:gap_id>/regression-test', methods=['POST'])
def admin_create_kb_regression_test(gap_id):
    """Capture a KB gap as a future deterministic regression question."""
    from feedback_system import create_kb_regression_test
    data = _request_json()
    result = create_kb_regression_test(
        gap_id,
        candidate_id=data.get('candidate_id'),
        expected_kb_verdict=data.get('expected_kb_verdict'),
    )
    return jsonify(result), 200 if result.get('success') else 400


@app.route('/admin/kb-gaps/<int:gap_id>/retest', methods=['POST'])
def admin_retest_kb_gap(gap_id):
    """Re-run a gap question through deterministic KB layers without creating a new gap."""
    from feedback_system import get_kb_gap_detail
    detail = get_kb_gap_detail(gap_id)
    if not detail:
        return jsonify({'success': False, 'error': 'KB gap not found'}), 404

    question = detail.get('question') or ''
    profile = load_course_profile(_get_profile_key())
    if detail.get('surface'):
        profile = dict(profile or {})
        surfaces = dict(profile.get('surfaces') or {})
        surfaces[detail['surface']] = detail.get('turf') or surfaces.get(detail['surface'], '')
        profile['surfaces'] = surfaces

    response = recommend_verified_products_for_surface_target(question, profile)
    if not response:
        response = answer_from_verified_kb(question, format_course_profile_for_prompt(profile=profile))
    if not response:
        response = {
            'answer': 'No deterministic KB answer was available for this question.',
            'sources': [],
            'confidence': {'score': 0, 'label': 'No Deterministic KB Match'},
            'needs_review': True,
            'kb_verdict': 'no_deterministic_match',
        }
    return jsonify({'success': True, 'result': response})


@app.route('/admin/kb-candidates', methods=['GET'])
def admin_kb_candidates():
    """List draft KB candidate patches."""
    from feedback_system import get_kb_candidates
    gap_id = request.args.get('gap_id')
    return jsonify(get_kb_candidates(
        gap_id=int(gap_id) if gap_id else None,
        status=request.args.get('status') or None,
        limit=int(request.args.get('limit', 100)),
    ))


@app.route('/admin/kb-candidates', methods=['POST'])
def admin_create_kb_candidate():
    """Create a draft KB candidate patch."""
    from feedback_system import create_kb_candidate
    data = _request_json()
    if not data.get('gap_id') or not data.get('candidate_patch'):
        return jsonify({'success': False, 'error': 'Missing gap_id or candidate_patch'}), 400
    result = create_kb_candidate(
        gap_id=int(data.get('gap_id')),
        candidate_patch=data.get('candidate_patch'),
        reviewer=data.get('reviewer', 'admin'),
        notes=data.get('notes'),
        status=data.get('status', 'draft'),
    )
    return jsonify(result), 200 if result.get('success') else 400


@app.route('/admin/kb-candidates/<int:candidate_id>/history')
def admin_kb_candidate_history(candidate_id):
    """Return candidate status/action history."""
    from feedback_system import get_kb_candidate_history
    return jsonify(get_kb_candidate_history(candidate_id))


@app.route('/admin/kb-candidates/<int:candidate_id>/status', methods=['POST'])
def admin_update_kb_candidate_status(candidate_id):
    """Update a KB candidate review status."""
    from feedback_system import update_kb_candidate_status
    data = _request_json()
    result = update_kb_candidate_status(
        candidate_id,
        status=data.get('status', 'draft'),
        notes=data.get('notes'),
    )
    return jsonify(result), 200 if result.get('success') else 400


@app.route('/admin/kb-candidates/<int:candidate_id>/apply', methods=['POST'])
def admin_apply_kb_candidate(candidate_id):
    """Apply a reviewed KB candidate patch into the structured product KB."""
    from feedback_system import apply_kb_candidate
    data = _request_json()
    result = apply_kb_candidate(candidate_id, reviewer=data.get('reviewer', 'admin'))
    return jsonify(result), 200 if result.get('success') else 400


@app.route('/admin/knowledge/build', methods=['POST'])
def admin_knowledge_build():
    """Trigger knowledge base build (limited for safety)."""
    from knowledge_builder import build_knowledge_base
    import threading

    limit = _request_json().get('limit', 10)  # Default to 10 files at a time

    # Run in background thread
    def run_build():
        try:
            build_knowledge_base(limit=limit)
        except Exception as e:
            logger.error(f"Knowledge build error: {e}")

    thread = threading.Thread(target=run_build)
    thread.start()

    return jsonify({
        'success': True,
        'message': f'Building knowledge base (processing up to {limit} files in background)'
    })


# -----------------------------------------------------------------------------
# Bulk Operations
# -----------------------------------------------------------------------------

@app.route('/admin/bulk-moderate', methods=['POST'])
def admin_bulk_moderate():
    """Bulk approve or reject multiple items"""
    from feedback_system import bulk_moderate
    data = _request_json()
    ids = _normalize_id_list(data.get('ids'))
    action = str(data.get('action') or 'approve').strip().lower()
    reason = data.get('reason')

    if not ids:
        return jsonify({'success': False, 'error': 'No IDs provided'}), 400
    if action not in {'approve', 'reject'}:
        return jsonify({'success': False, 'error': 'Invalid bulk action'}), 400

    result = bulk_moderate(ids, action, reason, moderator=_moderator_identity())
    return jsonify(result)


@app.route('/admin/bulk-approve-high-confidence', methods=['POST'])
def admin_bulk_approve_high_confidence():
    """Auto-approve all high-confidence items"""
    from feedback_system import bulk_approve_high_confidence
    data = _request_json()
    min_confidence = _coerce_int(data.get('min_confidence', 80), 80, minimum=0, maximum=100)
    limit = _coerce_int(data.get('limit', 100), 100, minimum=1, maximum=500)

    result = bulk_approve_high_confidence(min_confidence, limit, moderator=_moderator_identity())
    return jsonify(result)


# -----------------------------------------------------------------------------
# Export Routes
# -----------------------------------------------------------------------------

@app.route('/admin/export/feedback')
def admin_export_feedback():
    """Export all feedback as CSV"""
    from feedback_system import export_feedback_csv
    from flask import Response

    csv_data = export_feedback_csv()
    return Response(
        csv_data,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=feedback_export.csv'}
    )


@app.route('/admin/export/training')
def admin_export_training():
    """Export training examples as CSV"""
    from feedback_system import export_training_examples_csv
    from flask import Response

    csv_data = export_training_examples_csv()
    return Response(
        csv_data,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=training_examples.csv'}
    )


@app.route('/admin/export/moderation')
def admin_export_moderation():
    """Export moderation history as CSV"""
    from feedback_system import export_moderation_history_csv
    from flask import Response

    csv_data = export_moderation_history_csv()
    return Response(
        csv_data,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=moderation_history.csv'}
    )


@app.route('/admin/export/analytics')
def admin_export_analytics():
    """Export analytics data as JSON"""
    from feedback_system import export_analytics_json
    return jsonify(export_analytics_json())


# -----------------------------------------------------------------------------
# Priority Queue Routes
# -----------------------------------------------------------------------------

@app.route('/admin/priority-queue')
def admin_priority_queue():
    """Get priority-sorted review queue"""
    from feedback_system import get_priority_review_queue
    limit = request.args.get('limit', 100, type=int)
    offset = request.args.get('offset', 0, type=int)
    full_queue = get_priority_review_queue(limit=None)
    items = full_queue[offset:offset + limit]
    next_offset = offset + len(items)
    return jsonify({
        'items': items,
        'total': len(full_queue),
        'offset': offset,
        'limit': limit,
        'next_offset': next_offset,
        'has_more': next_offset < len(full_queue),
    })


@app.route('/admin/trending-issues')
def admin_trending_issues():
    """Get trending problem areas"""
    from feedback_system import get_trending_issues
    min_frequency = request.args.get('min_frequency', 3, type=int)
    days = request.args.get('days', 7, type=int)
    return jsonify(get_trending_issues(min_frequency, days))


@app.route('/admin/question-frequencies')
def admin_question_frequencies():
    """Get frequently asked questions"""
    from feedback_system import get_question_frequencies
    limit = request.args.get('limit', 50, type=int)
    return jsonify(get_question_frequencies(limit))


# -----------------------------------------------------------------------------
# Fine-tuning Routes
# -----------------------------------------------------------------------------

@app.route('/admin/fine-tuning/status')
def admin_fine_tuning_status():
    """Get fine-tuning status and training data readiness"""
    from feedback_system import get_training_examples
    from fine_tuning import list_fine_tuning_jobs, get_active_fine_tuned_model, MIN_EXAMPLES_FOR_TRAINING

    examples = get_training_examples(unused_only=True)
    jobs = list_fine_tuning_jobs(limit=5)
    active_model = get_active_fine_tuned_model()

    return jsonify({
        'training_examples_ready': len(examples),
        'min_examples_needed': MIN_EXAMPLES_FOR_TRAINING,
        'ready_to_train': len(examples) >= MIN_EXAMPLES_FOR_TRAINING,
        'recent_jobs': jobs,
        'active_fine_tuned_model': active_model
    })


@app.route('/admin/fine-tuning/start', methods=['POST'])
def admin_start_fine_tuning():
    """Start the fine-tuning pipeline"""
    from fine_tuning import run_full_fine_tuning_pipeline

    result = run_full_fine_tuning_pipeline()
    return jsonify(result)


@app.route('/admin/fine-tuning/job/<job_id>')
def admin_fine_tuning_job_status(job_id):
    """Get status of a specific fine-tuning job"""
    from fine_tuning import get_fine_tuning_status

    status = get_fine_tuning_status(job_id)
    return jsonify(status)


@app.route('/admin/source-quality')
def admin_source_quality():
    """Get source quality scores from feedback"""
    from fine_tuning import get_source_quality_scores, get_low_quality_sources

    return jsonify({
        'all_scores': get_source_quality_scores(),
        'low_quality': get_low_quality_sources(threshold=0.4)
    })


@app.route('/admin/eval/run', methods=['POST'])
def admin_run_evaluation():
    """Run evaluation against test questions"""
    from fine_tuning import run_evaluation, save_eval_results

    try:
        # Check if we should use the full 100-question set
        body = request.get_json(silent=True) or {}
        use_full = body.get('full', False)

        if use_full:
            from eval_questions_100 import EVAL_QUESTIONS_100
            results = run_evaluation(custom_questions=EVAL_QUESTIONS_100)
        else:
            results = run_evaluation()

        run_id = save_eval_results(results)
        results['run_id'] = run_id
        return jsonify(results)
    except Exception as e:
        import traceback
        logger.error(f"Evaluation error: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500


@app.route('/admin/eval/history')
def admin_eval_history():
    """Get evaluation run history"""
    from fine_tuning import get_eval_history

    limit = request.args.get('limit', 10, type=int)
    return jsonify(get_eval_history(limit))


# -----------------------------------------------------------------------------
# Legacy TGIF routes
# -----------------------------------------------------------------------------

@app.route('/tgif')
def tgif_search():
    """Retire the old TGIF surface without throwing a server error."""
    return redirect(url_for('resources'))


@app.route('/tgif/analyze', methods=['POST'])
def tgif_analyze():
    """Return a stable response for the retired TGIF analyzer."""
    return jsonify({
        'success': False,
        'error': 'TGIF research search is not enabled in this version. Use Resources or Ask instead.'
    }), 200


# -----------------------------------------------------------------------------
# Feedback routes
# -----------------------------------------------------------------------------

@app.route('/feedback', methods=['GET', 'POST'])
def submit_feedback():
    if request.method == 'GET':
        return redirect(url_for('home'))
    try:
        data = _request_json()
        feedback_id = data.get('feedback_id')
        question = data.get('question')
        rating = data.get('rating')
        correction = data.get('correction')
        if rating not in {'positive', 'negative'}:
            return jsonify({'success': False, 'error': 'Invalid feedback rating'}), 400
        if not question and not feedback_id:
            return jsonify({'success': False, 'error': 'Missing feedback question'}), 400

        # Update the existing query with the user's rating
        feedback_id = update_query_rating(
            feedback_id=feedback_id,
            question=question,
            rating=rating,
            correction=correction
        )
        if feedback_id is None:
            # If feedback is submitted for a response that was not saved yet,
            # still record it so admin/moderation never loses the signal.
            feedback_id = save_user_feedback(
                question=question,
                ai_answer=data.get('answer') or '',
                rating=rating,
                correction=correction,
                sources=data.get('sources'),
                confidence=data.get('confidence')
            )

        # Track source quality based on feedback
        # This helps identify which sources lead to good/bad answers
        try:
            from fine_tuning import track_source_quality
            import sqlite3
            from feedback_system import DB_PATH
            import json

            # Get the feedback record to access sources
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, sources FROM feedback
                WHERE id = ?
            ''', (feedback_id,))
            row = cursor.fetchone()
            conn.close()

            if row and row[1]:
                sources = json.loads(row[1])
                track_source_quality(question, sources, rating, row[0])
                logger.debug(f"Tracked source quality for {len(sources)} sources")
        except Exception as sq_error:
            logger.warning(f"Source quality tracking failed: {sq_error}")

        return jsonify({'success': True, 'message': 'Feedback saved'})
    except Exception as e:
        logger.error(f"Error saving feedback: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# -----------------------------------------------------------------------------
# Health check for monitoring
# -----------------------------------------------------------------------------

@app.route('/health')
def health_check():
    """Health check endpoint for production monitoring."""
    import time
    start = time.time()

    status = {
        'status': 'healthy',
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime()),
        'services': {}
    }

    # Check Pinecone
    try:
        pinecone_index = get_pinecone_index_safe()
        if pinecone_index is None:
            status['services']['pinecone'] = {'status': 'unavailable', 'message': 'Using degraded retrieval path'}
            status['status'] = 'degraded'
        else:
            stats = pinecone_index.describe_index_stats()
            status['services']['pinecone'] = {
                'status': 'connected',
                'vectors': stats.get('total_vector_count', 0)
            }
    except Exception as e:
        status['services']['pinecone'] = {'status': 'error', 'message': str(e)[:100]}
        status['status'] = 'degraded'

    # Check OpenAI key configured
    try:
        if Config.OPENAI_API_KEY and len(Config.OPENAI_API_KEY) > 10:
            status['services']['openai'] = {'status': 'configured'}
        else:
            status['services']['openai'] = {'status': 'not configured'}
            status['status'] = 'degraded'
    except Exception:
        status['services']['openai'] = {'status': 'error'}
        status['status'] = 'degraded'

    # Check database
    try:
        from feedback_system import get_feedback_stats
        stats = get_feedback_stats()
        status['services']['database'] = {
            'status': 'connected',
            'total_queries': stats.get('total_feedback', 0)
        }
    except Exception as e:
        status['services']['database'] = {'status': 'error', 'message': str(e)[:100]}
        status['status'] = 'degraded'

    status['response_time_ms'] = round((time.time() - start) * 1000, 2)

    http_status = 200 if status['status'] == 'healthy' else 503
    return jsonify(status), http_status


@app.route('/ready')
def readiness_check():
    """Cloud deployment readiness probe."""
    data_dir = Config.DATA_DIR
    deployment_mode = Config.DEPLOYMENT_MODE
    kb_trust_error = None
    try:
        kb_trust = _kb_trust_gate_payload()
    except Exception as exc:  # pragma: no cover - defensive runtime guard
        kb_trust_error = str(exc)
        kb_trust = {
            'status': 'fail',
            'enforced': Config.ENFORCE_KB_TRUST_GATE,
            'checks': [],
            'failed_checks': [],
            'summary': {'passed_checks': 0, 'total_checks': 0, 'human_review_coverage_percent': 0.0},
        }
    checks = {
        'secret_key_configured': Config.FLASK_SECRET_KEY != "greenside-secret-key-change-in-production",
        'openai_api_key_configured': bool(Config.OPENAI_API_KEY),
        'pinecone_api_key_configured': bool(Config.PINECONE_API_KEY),
        'data_dir_configured': bool(data_dir),
        'data_dir_writable': True,
        'admin_auth_locked_down': not _allow_public_admin_access(),
        'password_reset_email_configured': _mail_delivery_available(),
        'deployment_mode_supported': deployment_mode in {'single_node_persistent', 'managed_storage'},
        'kb_trust_gate_defined': kb_trust_error is None,
        'email_verification_delivery_ready': (not Config.REQUIRE_EMAIL_VERIFICATION) or _mail_delivery_available(),
        'persistence_backend_supported': Config.PERSISTENCE_BACKEND in {'local', 'dynamodb'},
    }
    warnings = []
    dynamodb_tables = {
        'accounts': Config.DYNAMODB_ACCOUNTS_TABLE,
        'account_tokens': Config.DYNAMODB_ACCOUNT_TOKENS_TABLE,
        'course_profiles': Config.DYNAMODB_COURSE_PROFILES_TABLE,
        'chat': Config.DYNAMODB_CHAT_TABLE,
        'rate_limits': Config.DYNAMODB_RATE_LIMIT_TABLE,
        'feedback': Config.DYNAMODB_FEEDBACK_TABLE,
    }
    dynamodb_status = {}

    try:
        os.makedirs(data_dir, exist_ok=True)
        probe_path = os.path.join(data_dir, ".ready_probe")
        with open(probe_path, "w", encoding="utf-8") as handle:
            handle.write("ok")
        os.remove(probe_path)
    except Exception:
        checks['data_dir_writable'] = False

    if Config.is_serverless() and data_dir in {"data", ".", "/tmp"}:
        warnings.append(
            "Serverless runtime detected with a local DATA_DIR. Use a mounted persistent path or external storage for accounts, profiles, and conversation data."
        )
    if Config.PERSISTENCE_BACKEND == "local" and deployment_mode == "managed_storage":
        warnings.append(
            "managed_storage is selected, but PERSISTENCE_BACKEND is still local. Accounts, profiles, chat, and rate limits are not yet using DynamoDB."
        )
    if Config.PERSISTENCE_BACKEND == "dynamodb" and not Config.AWS_REGION:
        warnings.append("PERSISTENCE_BACKEND=dynamodb requires AWS_REGION.")
    if Config.PERSISTENCE_BACKEND == "dynamodb":
        for key, table_name in dynamodb_tables.items():
            exists = dynamodb_table_exists(table_name)
            dynamodb_status[key] = {'table': table_name, 'exists': exists}
        checks['dynamodb_tables_ready'] = all(item['exists'] for item in dynamodb_status.values())
        if not checks['dynamodb_tables_ready']:
            warnings.append("One or more DynamoDB tables are missing for the configured managed-storage backend.")
    else:
        checks['dynamodb_tables_ready'] = True
    if not checks['deployment_mode_supported']:
        warnings.append(
            "DEPLOYMENT_MODE must be 'single_node_persistent' or 'managed_storage' before release."
        )
    if not checks['secret_key_configured']:
        warnings.append("FLASK_SECRET_KEY is still using the default value.")
    if not checks['openai_api_key_configured']:
        warnings.append("OPENAI_API_KEY is not configured.")
    if not checks['pinecone_api_key_configured']:
        warnings.append("PINECONE_API_KEY is not configured.")
    if not checks['data_dir_writable']:
        warnings.append("DATA_DIR is not writable.")
    if not checks['admin_auth_locked_down']:
        if Config.DEMO_MODE and not Config.ALLOW_PUBLIC_ADMIN:
            warnings.append("DEMO_MODE=true leaves the admin surface open without authentication. Disable demo mode before release.")
        else:
            warnings.append("ALLOW_PUBLIC_ADMIN=true leaves the admin surface open without authentication. Disable it before release.")
    if not checks['password_reset_email_configured']:
        warnings.append("Password reset delivery is not configured. Set SMTP_HOST or enable local sendmail, and set MAIL_FROM for self-serve recovery.")
    if not checks['email_verification_delivery_ready']:
        warnings.append("Email verification is required, but no working mail delivery path is configured.")
    if kb_trust_error:
        warnings.append(f"KB trust gate could not be evaluated: {kb_trust_error}")
    if kb_trust['status'] != 'pass':
        warnings.append(
            "KB trust thresholds are not fully met for launch yet. Review the KB Quality Dashboard trust gate."
        )
    if Config.ENFORCE_KB_TRUST_GATE and kb_trust['status'] != 'pass':
        checks['kb_trust_gate_passed'] = False
    else:
        checks['kb_trust_gate_passed'] = True

    required_check_keys = (
        'secret_key_configured',
        'openai_api_key_configured',
        'pinecone_api_key_configured',
        'data_dir_configured',
        'data_dir_writable',
        'admin_auth_locked_down',
        'deployment_mode_supported',
        'kb_trust_gate_defined',
        'kb_trust_gate_passed',
        'email_verification_delivery_ready',
        'persistence_backend_supported',
        'dynamodb_tables_ready',
    )
    ready = all(checks[key] for key in required_check_keys)
    payload = {
        'status': 'ready' if ready else 'not_ready',
        'serverless': Config.is_serverless(),
        'deployment_mode': deployment_mode,
        'data_dir': data_dir,
        'checks': checks,
        'warnings': warnings,
        'kb_trust_gate': kb_trust,
        'dynamodb_tables': dynamodb_status,
    }
    return jsonify(payload), 200 if ready else 503


# -----------------------------------------------------------------------------
# Weather routes
# -----------------------------------------------------------------------------

@app.route('/api/weather', methods=['GET', 'POST'])
def get_weather():
    """Get weather data for a location."""
    if request.method == 'POST':
        data = _request_json()
    else:
        data = request.args

    lat = data.get('lat', type=float) if request.method == 'GET' else data.get('lat')
    lon = data.get('lon', type=float) if request.method == 'GET' else data.get('lon')
    city = data.get('city')
    state = data.get('state')

    if not ((lat and lon) or city):
        return jsonify({'error': 'Provide lat/lon or city'}), 400

    weather_data = get_weather_data(lat=lat, lon=lon, city=city, state=state)
    if not weather_data:
        return jsonify({'error': 'Could not fetch weather data'}), 500

    return jsonify({
        'location': weather_data.get('location'),
        'current': weather_data.get('current'),
        'forecast': weather_data.get('forecast'),
        'warnings': get_weather_warnings(weather_data),
        'summary': format_weather_for_response(weather_data)
    })


if __name__ == '__main__':
    app.run(debug=Config.DEBUG, port=Config.PORT)
