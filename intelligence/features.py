"""
Intelligence Engine — Feature Flags, Rate Limiter, Data Retention, Input Sanitizer
====================================================================================
Per-subsystem feature flag management, rate limiting, TTL-based cleanup,
and score-based prompt injection detection.
"""

import os
import re
import json
import time
import logging
import threading
import base64
from datetime import datetime, timedelta
from typing import List, Dict

from intelligence.db import _get_conn, log_event

logger = logging.getLogger(__name__)


class FeatureFlags:
    """Per-subsystem feature flag management with DB persistence."""

    _DEFAULT_FLAGS = {
        'ab_testing': (True, 'A/B testing engine'),
        'anomaly_detection': (True, 'Anomaly detection engine'),
        'alerting': (True, 'Multi-channel alert system'),
        'circuit_breaker': (True, 'Circuit breaker pattern'),
        'prompt_versioning': (True, 'Prompt version management'),
        'gradient_boosted': (True, 'Gradient boosted predictor'),
        'knowledge_gaps': (True, 'Knowledge gap analyzer'),
        'conversation_intelligence': (True, 'Conversation quality analysis'),
        'cost_enforcement': (True, 'Cost budget enforcement'),
        'rate_limiting': (False, 'Rate limiting (disabled by default)'),
        'data_retention': (True, 'Automatic data retention cleanup'),
        'content_freshness_enforcement': (True, 'Content freshness penalty in ranking'),
    }

    # In-memory cache to avoid DB hits on every request
    _cache = {}
    _cache_time = 0
    _CACHE_TTL = 30  # seconds

    @staticmethod
    def init_defaults():
        """Initialize default feature flags if they don't exist."""
        try:
            conn = _get_conn()
            for flag_name, (enabled, description) in FeatureFlags._DEFAULT_FLAGS.items():
                conn.execute('''
                    INSERT OR IGNORE INTO feature_flags (flag_name, enabled, description)
                    VALUES (?, ?, ?)
                ''', (flag_name, enabled, description))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Feature flags init error: {e}")

    @staticmethod
    def is_enabled(flag_name: str) -> bool:
        """Check if a feature flag is enabled. Uses in-memory cache."""
        now = time.time()
        if now - FeatureFlags._cache_time > FeatureFlags._CACHE_TTL or not FeatureFlags._cache:
            FeatureFlags._refresh_cache()

        return FeatureFlags._cache.get(flag_name, True)

    @staticmethod
    def _refresh_cache():
        """Refresh the in-memory flag cache from DB."""
        try:
            conn = _get_conn()
            rows = conn.execute('SELECT flag_name, enabled FROM feature_flags').fetchall()
            conn.close()
            FeatureFlags._cache = {r['flag_name']: bool(r['enabled']) for r in rows}
            FeatureFlags._cache_time = time.time()
        except Exception as e:
            logger.error(f"Feature flag cache refresh error: {e}")

    @staticmethod
    def set_flag(flag_name: str, enabled: bool, updated_by: str = 'admin') -> bool:
        """Toggle a feature flag."""
        try:
            conn = _get_conn()
            conn.execute('''
                UPDATE feature_flags SET enabled = ?, updated_at = CURRENT_TIMESTAMP, updated_by = ?
                WHERE flag_name = ?
            ''', (enabled, updated_by, flag_name))
            conn.commit()
            conn.close()
            # Invalidate cache
            FeatureFlags._cache_time = 0
            log_event('feature_flags', 'flag_toggled',
                      json.dumps({'flag': flag_name, 'enabled': enabled, 'by': updated_by}))
            return True
        except Exception as e:
            logger.error(f"Feature flag set error: {e}")
            return False

    @staticmethod
    def get_all_flags() -> List[Dict]:
        """Get all feature flags with their current state."""
        try:
            conn = _get_conn()
            rows = conn.execute('''
                SELECT flag_name, enabled, description, updated_at, updated_by
                FROM feature_flags ORDER BY flag_name
            ''').fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"Get all flags error: {e}")
            return []


class RateLimiter:
    """Token bucket rate limiter. Uses Redis when available, in-memory fallback."""

    _buckets = {}  # Fallback: in-memory {key -> {'tokens': float, 'last_refill': float}}
    _lock = threading.Lock()
    _blocked_count = 0
    _redis = None
    _redis_checked = False

    # Default limits
    ASK_LIMIT_PER_MIN = 30
    API_LIMIT_PER_MIN = 100
    GLOBAL_LIMIT_PER_MIN = 500

    @staticmethod
    def _get_redis():
        """Lazily connect to Redis for rate limiting."""
        if not RateLimiter._redis_checked:
            RateLimiter._redis_checked = True
            redis_url = os.environ.get('REDIS_URL')
            if redis_url:
                try:
                    import redis as _rl_redis
                    RateLimiter._redis = _rl_redis.Redis.from_url(redis_url)
                    RateLimiter._redis.ping()
                    logger.info("RateLimiter using Redis backend")
                except Exception:
                    RateLimiter._redis = None
        return RateLimiter._redis

    @staticmethod
    def _get_bucket(key: str, rate_per_min: int) -> dict:
        """Get or create a token bucket for a key."""
        now = time.time()
        r = RateLimiter._get_redis()

        if r:
            try:
                rkey = f"rl:{key}"
                pipe = r.pipeline()
                pipe.hsetnx(rkey, 'tokens', str(float(rate_per_min)))
                pipe.hsetnx(rkey, 'last_refill', str(now))
                pipe.hsetnx(rkey, 'rate', str(float(rate_per_min)))
                pipe.hgetall(rkey)
                results = pipe.execute()
                raw = results[3]
                bucket = {
                    'tokens': float(raw[b'tokens']),
                    'last_refill': float(raw[b'last_refill']),
                    'rate': float(raw[b'rate']),
                }
                # Refill
                elapsed = now - bucket['last_refill']
                tokens_to_add = elapsed * (bucket['rate'] / 60.0)
                new_tokens = min(bucket['rate'], bucket['tokens'] + tokens_to_add)
                r.hset(rkey, mapping={
                    'tokens': str(new_tokens),
                    'last_refill': str(now),
                })
                r.expire(rkey, 600)  # Auto-cleanup after 10 min idle
                bucket['tokens'] = new_tokens
                bucket['last_refill'] = now
                return bucket
            except Exception:
                pass  # Fall through to in-memory

        # In-memory fallback
        with RateLimiter._lock:
            if key not in RateLimiter._buckets:
                RateLimiter._buckets[key] = {
                    'tokens': rate_per_min,
                    'last_refill': now,
                    'rate': rate_per_min
                }

            bucket = RateLimiter._buckets[key]
            elapsed = now - bucket['last_refill']
            tokens_to_add = elapsed * (bucket['rate'] / 60.0)
            bucket['tokens'] = min(bucket['rate'], bucket['tokens'] + tokens_to_add)
            bucket['last_refill'] = now
            return bucket

    @staticmethod
    def _consume_token(key: str) -> bool:
        """Consume a token from a bucket. Returns True if consumed."""
        r = RateLimiter._get_redis()
        if r:
            try:
                new_val = r.hincrbyfloat(f"rl:{key}", 'tokens', -1)
                return True
            except Exception:
                pass
        # In-memory fallback
        with RateLimiter._lock:
            if key in RateLimiter._buckets:
                RateLimiter._buckets[key]['tokens'] -= 1
        return True

    @staticmethod
    def check_rate_limit(ip: str, route_type: str = 'api') -> dict:
        """
        Check if a request should be rate limited.
        Returns {'allowed': bool, 'retry_after': int}
        """
        if not FeatureFlags.is_enabled('rate_limiting'):
            return {'allowed': True, 'retry_after': 0}

        rate = RateLimiter.ASK_LIMIT_PER_MIN if route_type == 'ask' else RateLimiter.API_LIMIT_PER_MIN

        # Per-IP check
        ip_key = f"ip:{ip}:{route_type}"
        ip_bucket = RateLimiter._get_bucket(ip_key, rate)

        # Global check
        global_bucket = RateLimiter._get_bucket('global', RateLimiter.GLOBAL_LIMIT_PER_MIN)

        if ip_bucket['tokens'] < 1:
            RateLimiter._blocked_count += 1
            wait = 60.0 / ip_bucket['rate']
            return {'allowed': False, 'retry_after': max(1, int(wait))}

        if global_bucket['tokens'] < 1:
            RateLimiter._blocked_count += 1
            wait = 60.0 / global_bucket['rate']
            return {'allowed': False, 'retry_after': max(1, int(wait))}

        RateLimiter._consume_token(ip_key)
        RateLimiter._consume_token('global')
        return {'allowed': True, 'retry_after': 0}

    @staticmethod
    def get_status() -> Dict:
        """Get rate limiter status."""
        backend = 'redis' if RateLimiter._get_redis() else 'in-memory'
        return {
            'enabled': FeatureFlags.is_enabled('rate_limiting'),
            'backend': backend,
            'blocked_requests_total': RateLimiter._blocked_count,
            'active_buckets': len(RateLimiter._buckets),
            'limits': {
                'ask_per_min': RateLimiter.ASK_LIMIT_PER_MIN,
                'api_per_min': RateLimiter.API_LIMIT_PER_MIN,
                'global_per_min': RateLimiter.GLOBAL_LIMIT_PER_MIN,
            }
        }

    @staticmethod
    def cleanup_old_buckets():
        """Remove buckets that haven't been used in 10 minutes. No-op when using Redis (TTL handles it)."""
        if RateLimiter._get_redis():
            return  # Redis keys have TTL, no manual cleanup needed
        cutoff = time.time() - 600
        with RateLimiter._lock:
            to_delete = [k for k, v in RateLimiter._buckets.items()
                         if v['last_refill'] < cutoff]
            for k in to_delete:
                del RateLimiter._buckets[k]


class DataRetentionManager:
    """Configurable TTL-based data cleanup for all intelligence tables."""

    # Table -> TTL in days (0 = never delete)
    DEFAULT_TTLS = {
        'pipeline_metrics': 30,
        'anomaly_detections': 90,
        'alert_history': 90,
        'remediation_actions': 90,
        'conversation_analytics': 180,
        'ab_test_results': 365,
        'satisfaction_predictions': 365,
        'confidence_calibration': 365,
        'intelligence_events': 90,
        'prompt_usage_log': 180,
        'query_moderation': 90,
        'retention_log': 365,
        'metric_baselines': 90,
        'cost_ledger': 365,
        # Never delete:
        'golden_answers': 0,
        'answer_versions': 0,
        'regression_tests': 0,
        'topic_clusters': 0,
        'source_reliability': 0,
        'feature_flags': 0,
    }

    @staticmethod
    def run_cleanup() -> Dict:
        """Run cleanup on all tables with configured TTLs. Returns summary."""
        if not FeatureFlags.is_enabled('data_retention'):
            return {'skipped': True, 'reason': 'feature_flag_disabled'}

        results = {}
        total_deleted = 0

        try:
            conn = _get_conn()
            for table_name, ttl_days in DataRetentionManager.DEFAULT_TTLS.items():
                if ttl_days <= 0:
                    continue

                cutoff = (datetime.now() - timedelta(days=ttl_days)).isoformat()
                try:
                    # Check count before delete
                    count_before = conn.execute(f'SELECT COUNT(*) FROM {table_name}').fetchone()[0]

                    # Detect time column (tables use timestamp, created_at, or updated_at)
                    cols = [r[1] for r in conn.execute(f'PRAGMA table_info({table_name})').fetchall()]
                    time_col = 'timestamp'
                    if 'timestamp' not in cols:
                        if 'created_at' in cols:
                            time_col = 'created_at'
                        elif 'updated_at' in cols:
                            time_col = 'updated_at'
                        else:
                            continue  # No time column, skip

                    conn.execute(f'''
                        DELETE FROM {table_name} WHERE {time_col} < ?
                    ''', (cutoff,))

                    count_after = conn.execute(f'SELECT COUNT(*) FROM {table_name}').fetchone()[0]
                    deleted = count_before - count_after

                    if deleted > 0:
                        results[table_name] = deleted
                        total_deleted += deleted

                        # Log to retention_log
                        conn.execute('''
                            INSERT INTO retention_log (table_name, rows_deleted, ttl_days)
                            VALUES (?, ?, ?)
                        ''', (table_name, deleted, ttl_days))

                except Exception as te:
                    logger.warning(f"Retention cleanup for {table_name} failed: {te}")

            conn.commit()
            conn.close()

            if total_deleted > 0:
                log_event('data_retention', 'cleanup_complete',
                          json.dumps({'total_deleted': total_deleted, 'tables': results}))

        except Exception as e:
            logger.error(f"Data retention cleanup error: {e}")

        return {'total_deleted': total_deleted, 'tables': results}

    @staticmethod
    def get_status() -> Dict:
        """Get retention status: row counts and TTLs for all tracked tables."""
        try:
            conn = _get_conn()
            status = {}
            for table_name, ttl_days in DataRetentionManager.DEFAULT_TTLS.items():
                try:
                    count = conn.execute(f'SELECT COUNT(*) FROM {table_name}').fetchone()[0]
                    status[table_name] = {'row_count': count, 'ttl_days': ttl_days}
                except Exception:
                    status[table_name] = {'row_count': 'error', 'ttl_days': ttl_days}

            # Last cleanup info
            last_cleanup = conn.execute('''
                SELECT table_name, rows_deleted, timestamp
                FROM retention_log ORDER BY timestamp DESC LIMIT 10
            ''').fetchall()
            conn.close()

            return {
                'tables': status,
                'last_cleanups': [dict(r) for r in last_cleanup],
                'enabled': FeatureFlags.is_enabled('data_retention')
            }
        except Exception as e:
            logger.error(f"Retention status error: {e}")
            return {'error': str(e)}


class InputSanitizer:
    """Score-based prompt injection detection with pattern matching."""

    _PATTERNS = [
        # Direct injection attempts
        (re.compile(r'ignore\s+(all\s+)?previous\s+(instructions|prompts|context)', re.IGNORECASE), 5),
        (re.compile(r'disregard\s+(all\s+)?previous', re.IGNORECASE), 5),
        (re.compile(r'forget\s+(everything|all|your)\s+(instructions|rules|training)', re.IGNORECASE), 5),
        (re.compile(r'you\s+are\s+now\s+', re.IGNORECASE), 4),
        (re.compile(r'new\s+instructions?\s*:', re.IGNORECASE), 4),
        (re.compile(r'system\s*:\s*', re.IGNORECASE), 3),
        (re.compile(r'\[INST\]', re.IGNORECASE), 4),
        (re.compile(r'\[/INST\]', re.IGNORECASE), 4),
        (re.compile(r'<\|im_start\|>', re.IGNORECASE), 4),
        (re.compile(r'<<SYS>>', re.IGNORECASE), 5),
        (re.compile(r'act\s+as\s+(a\s+)?(different|new|another)', re.IGNORECASE), 3),
        (re.compile(r'pretend\s+(you\s+are|to\s+be)\s+', re.IGNORECASE), 3),
        (re.compile(r'override\s+(your\s+)?(rules|instructions|safety)', re.IGNORECASE), 5),
        (re.compile(r'reveal\s+(your\s+)?(system\s+)?prompt', re.IGNORECASE), 4),
        (re.compile(r'what\s+is\s+your\s+system\s+prompt', re.IGNORECASE), 3),
        (re.compile(r'jailbreak', re.IGNORECASE), 5),
        (re.compile(r'DAN\s+mode', re.IGNORECASE), 5),
        (re.compile(r'developer\s+mode', re.IGNORECASE), 3),
    ]

    _BLOCK_THRESHOLD = 8  # Total score to block
    _WARN_THRESHOLD = 4   # Total score to flag/warn

    @staticmethod
    def check_query(query: str, ip_address: str = None) -> Dict:
        """
        Check a query for injection patterns.
        Returns {'safe': bool, 'score': int, 'patterns': [], 'action': str}
        """
        if not query:
            return {'safe': True, 'score': 0, 'patterns': [], 'action': 'allow'}

        total_score = 0
        matched_patterns = []

        # Pattern matching
        for pattern, weight in InputSanitizer._PATTERNS:
            if pattern.search(query):
                total_score += weight
                matched_patterns.append(pattern.pattern)

        # Length heuristic: very long queries with any pattern match are suspicious
        if len(query) > 2000 and total_score > 0:
            total_score += 3
            matched_patterns.append('excessive_length_with_patterns')

        # Base64 detection: check for large base64-encoded blocks
        b64_matches = re.findall(r'[A-Za-z0-9+/]{50,}={0,2}', query)
        if b64_matches:
            # Try to decode and check for injection patterns
            for b64 in b64_matches:
                try:
                    decoded = base64.b64decode(b64 + '==').decode('utf-8', errors='ignore')
                    for pattern, weight in InputSanitizer._PATTERNS[:5]:
                        if pattern.search(decoded):
                            total_score += weight
                            matched_patterns.append(f'base64_encoded:{pattern.pattern}')
                except Exception:
                    pass

        # Determine action
        if total_score >= InputSanitizer._BLOCK_THRESHOLD:
            action = 'blocked'
        elif total_score >= InputSanitizer._WARN_THRESHOLD:
            action = 'flagged'
        else:
            action = 'allow'

        # Log to DB if not clean
        if action != 'allow':
            try:
                conn = _get_conn()
                conn.execute('''
                    INSERT INTO query_moderation (query, score, patterns_matched, action, ip_address)
                    VALUES (?, ?, ?, ?, ?)
                ''', (query[:500], total_score, json.dumps(matched_patterns), action, ip_address))
                conn.commit()
                conn.close()
            except Exception as e:
                logger.error(f"Moderation log error: {e}")

        return {
            'safe': action != 'blocked',
            'score': total_score,
            'patterns': matched_patterns,
            'action': action
        }

    @staticmethod
    def get_blocked_queries(limit: int = 50) -> List[Dict]:
        """Get recent blocked/flagged queries."""
        try:
            conn = _get_conn()
            rows = conn.execute('''
                SELECT query, score, patterns_matched, action, ip_address, timestamp
                FROM query_moderation ORDER BY timestamp DESC LIMIT ?
            ''', (limit,)).fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"Get blocked queries error: {e}")
            return []
