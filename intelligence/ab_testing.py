"""
Intelligence Engine — Subsystem 2: Answer Versioning & A/B Testing
===================================================================
Stores multiple answer versions per question pattern.
Runs A/B tests with deterministic bucket assignment.
"""

import json
import hashlib
import math
import logging
from datetime import datetime
from typing import List, Dict, Optional

from intelligence.db import _get_conn, log_event
from intelligence.helpers import _keyword_similarity, _wilson_score_interval

logger = logging.getLogger(__name__)


class ABTestingEngine:
    """
    Stores multiple answer versions per question pattern.
    Runs A/B tests with deterministic bucket assignment.
    Measures statistical significance via Wilson score intervals.
    """

    @staticmethod
    def create_answer_version(pattern: str, answer_template: str,
                               strategy: str = 'default', metadata: Dict = None) -> int:
        """Store an answer version for a pattern."""
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO answer_versions (pattern, answer_template, strategy, metadata)
            VALUES (?, ?, ?, ?)
        ''', (pattern, answer_template, strategy, json.dumps(metadata) if metadata else None))
        version_id = cursor.lastrowid
        conn.commit()
        conn.close()
        log_event('ab_testing', 'version_created', json.dumps({'id': version_id, 'pattern': pattern}))
        return version_id

    @staticmethod
    def create_ab_test(name: str, pattern: str, version_ids: List[int],
                       traffic_split: List[float] = None) -> int:
        """Create a new A/B test."""
        if traffic_split is None:
            # Equal split
            traffic_split = [1.0 / len(version_ids)] * len(version_ids)

        assert len(version_ids) == len(traffic_split), "Version IDs and traffic split must match"
        assert abs(sum(traffic_split) - 1.0) < 0.01, "Traffic split must sum to 1.0"

        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO ab_tests (name, pattern, version_ids, traffic_split)
            VALUES (?, ?, ?, ?)
        ''', (name, pattern, json.dumps(version_ids), json.dumps(traffic_split)))
        test_id = cursor.lastrowid
        conn.commit()
        conn.close()
        log_event('ab_testing', 'test_created', json.dumps({'id': test_id, 'name': name}))
        return test_id

    @staticmethod
    def get_ab_assignment(query: str, user_id: str) -> Optional[Dict]:
        """
        Get A/B test assignment for a query. Uses deterministic hashing
        so same user always gets same version.
        """
        conn = _get_conn()
        tests = conn.execute('''
            SELECT * FROM ab_tests WHERE status = 'active'
        ''').fetchall()
        conn.close()

        for test in tests:
            pattern = test['pattern'].lower()
            if pattern in query.lower() or _keyword_similarity(query, pattern) > 0.5:
                version_ids = json.loads(test['version_ids'])
                traffic_split = json.loads(test['traffic_split'])

                # Deterministic bucket assignment
                hash_input = f"{user_id}:{test['id']}"
                hash_val = int(hashlib.md5(hash_input.encode()).hexdigest(), 16) % 1000
                bucket = hash_val / 1000.0

                cumulative = 0.0
                assigned_version = version_ids[0]
                for i, split in enumerate(traffic_split):
                    cumulative += split
                    if bucket < cumulative:
                        assigned_version = version_ids[i]
                        break

                # Get version details
                conn = _get_conn()
                version = conn.execute('SELECT * FROM answer_versions WHERE id = ?',
                                      (assigned_version,)).fetchone()
                conn.execute('UPDATE ab_tests SET total_impressions = total_impressions + 1 WHERE id = ?',
                           (test['id'],))
                conn.commit()
                conn.close()

                if version:
                    return {
                        'test_id': test['id'],
                        'test_name': test['name'],
                        'version_id': assigned_version,
                        'answer_template': version['answer_template'],
                        'strategy': version['strategy']
                    }

        return None

    @staticmethod
    def record_ab_result(test_id: int, version_id: int, query_id: int = None,
                         user_id: str = None, rating: str = None, confidence: float = None):
        """Record an A/B test result."""
        conn = _get_conn()
        conn.execute('''
            INSERT INTO ab_test_results (test_id, version_id, query_id, user_id, rating, confidence)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (test_id, version_id, query_id, user_id, rating, confidence))

        # Update version stats
        if rating:
            version = conn.execute('SELECT times_served, avg_rating FROM answer_versions WHERE id = ?',
                                  (version_id,)).fetchone()
            if version:
                times = version['times_served'] + 1
                rating_val = 1.0 if rating in ('helpful', 'good', 'correct') else 0.0
                current_avg = version['avg_rating'] or 0.0
                new_avg = (current_avg * version['times_served'] + rating_val) / times
                conn.execute('''
                    UPDATE answer_versions SET times_served = ?, avg_rating = ? WHERE id = ?
                ''', (times, new_avg, version_id))

        conn.commit()
        conn.close()

    @staticmethod
    def analyze_ab_test(test_id: int) -> Dict:
        """
        Analyze A/B test results with Wilson score confidence intervals.
        Returns per-version stats and statistical significance.
        """
        conn = _get_conn()
        test = conn.execute('SELECT * FROM ab_tests WHERE id = ?', (test_id,)).fetchone()
        if not test:
            conn.close()
            return {'error': 'Test not found'}

        version_ids = json.loads(test['version_ids'])
        results = {}

        for vid in version_ids:
            rows = conn.execute('''
                SELECT rating, confidence FROM ab_test_results
                WHERE test_id = ? AND version_id = ? AND rating IS NOT NULL
            ''', (test_id, vid)).fetchall()

            total = len(rows)
            positive = sum(1 for r in rows if r['rating'] in ('helpful', 'good', 'correct'))
            negative = total - positive
            avg_confidence = sum(r['confidence'] or 0 for r in rows) / total if total > 0 else 0

            # Wilson score interval (95% confidence)
            lower, upper = _wilson_score_interval(positive, total)

            results[vid] = {
                'total': total,
                'positive': positive,
                'negative': negative,
                'positive_rate': round(positive / total, 3) if total > 0 else 0,
                'avg_confidence': round(avg_confidence, 1),
                'wilson_lower': round(lower, 3),
                'wilson_upper': round(upper, 3)
            }

        conn.close()

        # Determine if there's a statistically significant winner
        winner = None
        if len(results) >= 2:
            sorted_versions = sorted(results.items(), key=lambda x: x[1]['wilson_lower'], reverse=True)
            best = sorted_versions[0]
            second = sorted_versions[1]
            # Winner if best's lower bound > second's upper bound
            if best[1]['wilson_lower'] > second[1]['wilson_upper']:
                winner = best[0]

        return {
            'test_id': test_id,
            'name': test['name'],
            'status': test['status'],
            'total_impressions': test['total_impressions'],
            'versions': results,
            'winner': winner,
            'significant': winner is not None
        }

    @staticmethod
    def get_active_tests() -> List[Dict]:
        """Get all active A/B tests."""
        conn = _get_conn()
        rows = conn.execute('SELECT * FROM ab_tests WHERE status = "active" ORDER BY created_at DESC').fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @staticmethod
    def end_test(test_id: int, winner_version_id: int = None):
        """End an A/B test, optionally declaring a winner."""
        conn = _get_conn()
        conn.execute('''
            UPDATE ab_tests SET status = 'completed', ended_at = ?, winner_version_id = ?
            WHERE id = ?
        ''', (datetime.now().isoformat(), winner_version_id, test_id))
        conn.commit()
        conn.close()
        log_event('ab_testing', 'test_ended', json.dumps({'id': test_id, 'winner': winner_version_id}))
