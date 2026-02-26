"""
Intelligence Engine — Subsystem 12: Circuit Breaker
=====================================================
Circuit breaker pattern for failing sources/services.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict

from intelligence.db import _get_conn, log_event

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """Circuit breaker pattern for failing sources/services."""

    @staticmethod
    def record_failure(source_id: str):
        """Record a failure for a source. Opens breaker after threshold."""
        try:
            from config import Config
            threshold = Config.CIRCUIT_BREAKER_THRESHOLD
            window = Config.CIRCUIT_BREAKER_WINDOW
            recovery = Config.CIRCUIT_BREAKER_RECOVERY

            conn = _get_conn()
            now = datetime.now()

            existing = conn.execute(
                'SELECT * FROM circuit_breakers WHERE source_id = ?', (source_id,)
            ).fetchone()

            if existing:
                existing = dict(existing)
                # If already open, skip
                if existing['state'] == 'open':
                    conn.close()
                    return

                # Check if failures are within the window
                last = datetime.fromisoformat(existing['last_failure']) if existing['last_failure'] else None
                if last and (now - last).total_seconds() > window:
                    # Reset count -- failures are too spread out
                    conn.execute('''
                        UPDATE circuit_breakers
                        SET failure_count = 1, last_failure = ?, updated_at = ?
                        WHERE source_id = ?
                    ''', (now.isoformat(), now.isoformat(), source_id))
                else:
                    new_count = existing['failure_count'] + 1
                    if new_count >= threshold:
                        # OPEN the circuit breaker
                        recovery_at = (now + timedelta(seconds=recovery)).isoformat()
                        conn.execute('''
                            UPDATE circuit_breakers
                            SET state = 'open', failure_count = ?, last_failure = ?,
                                opened_at = ?, recovery_at = ?, total_trips = total_trips + 1,
                                updated_at = ?
                            WHERE source_id = ?
                        ''', (new_count, now.isoformat(), now.isoformat(),
                              recovery_at, now.isoformat(), source_id))
                        log_event('circuit_breaker', 'opened',
                                  json.dumps({'source_id': source_id, 'failures': new_count}), 'warning')
                    else:
                        conn.execute('''
                            UPDATE circuit_breakers
                            SET failure_count = ?, last_failure = ?, updated_at = ?
                            WHERE source_id = ?
                        ''', (new_count, now.isoformat(), now.isoformat(), source_id))
            else:
                conn.execute('''
                    INSERT INTO circuit_breakers (source_id, failure_count, last_failure, state)
                    VALUES (?, 1, ?, 'closed')
                ''', (source_id, now.isoformat()))

            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Circuit breaker record_failure error: {e}")

    @staticmethod
    def is_open(source_id: str) -> bool:
        """Check if a circuit breaker is open (source should be skipped)."""
        try:
            conn = _get_conn()
            row = conn.execute(
                'SELECT state, recovery_at FROM circuit_breakers WHERE source_id = ?',
                (source_id,)
            ).fetchone()
            conn.close()

            if not row or row['state'] == 'closed':
                return False

            # Check if recovery time has passed
            if row['recovery_at']:
                recovery = datetime.fromisoformat(row['recovery_at'])
                if datetime.now() >= recovery:
                    CircuitBreaker._close(source_id)
                    return False

            return True
        except Exception as e:
            logger.error(f"Circuit breaker is_open error: {e}")
            return False

    @staticmethod
    def _close(source_id: str):
        """Close (recover) a circuit breaker."""
        try:
            conn = _get_conn()
            conn.execute('''
                UPDATE circuit_breakers
                SET state = 'closed', failure_count = 0, updated_at = CURRENT_TIMESTAMP
                WHERE source_id = ?
            ''', (source_id,))
            conn.commit()
            conn.close()
            log_event('circuit_breaker', 'recovered',
                      json.dumps({'source_id': source_id}))
        except Exception as e:
            logger.error(f"Circuit breaker close error: {e}")

    @staticmethod
    def get_all_breakers() -> List[Dict]:
        """Get status of all circuit breakers."""
        try:
            conn = _get_conn()
            rows = conn.execute('SELECT * FROM circuit_breakers ORDER BY updated_at DESC').fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"Get breakers error: {e}")
            return []

    @staticmethod
    def filter_sources(sources: List[Dict]) -> List[Dict]:
        """Filter out sources whose circuit breaker is open."""
        if not sources:
            return sources
        filtered = []
        for s in sources:
            sid = str(s.get('id', s.get('source', '')))
            if sid and CircuitBreaker.is_open(sid):
                logger.info(f"Circuit breaker filtered source: {sid}")
                continue
            filtered.append(s)
        return filtered
