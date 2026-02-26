"""
Intelligence Engine — Subsystem 5: Automated Regression Detection
==================================================================
Golden test suite of curated Q&A pairs.
"""

import json
import logging
from datetime import datetime
from typing import List, Dict

from intelligence.db import _get_conn, log_event
from intelligence.helpers import _compute_drift_score

logger = logging.getLogger(__name__)


class RegressionDetector:
    """
    Golden test suite of curated Q&A pairs.
    Runs tests periodically to detect answer quality drift.
    """

    @staticmethod
    def add_regression_test(question: str, expected_answer: str,
                            category: str = None, criteria: str = None,
                            priority: int = 1) -> int:
        """Admin adds a regression test case."""
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO regression_tests (question, expected_answer, category, criteria, priority)
            VALUES (?, ?, ?, ?, ?)
        ''', (question, expected_answer, category, criteria, priority))
        test_id = cursor.lastrowid
        conn.commit()
        conn.close()
        log_event('regression', 'test_added', json.dumps({'id': test_id}))
        return test_id

    @staticmethod
    def get_regression_tests(active_only: bool = True) -> List[Dict]:
        """Get all regression tests."""
        conn = _get_conn()
        if active_only:
            rows = conn.execute('SELECT * FROM regression_tests WHERE active = 1 ORDER BY priority DESC').fetchall()
        else:
            rows = conn.execute('SELECT * FROM regression_tests ORDER BY priority DESC').fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @staticmethod
    def run_regression_suite(ask_function=None, trigger: str = 'scheduled') -> Dict:
        """
        Execute all active regression tests.
        ask_function should be a callable that takes a question and returns
        {'answer': str, 'confidence': float, 'sources': list}
        """
        conn = _get_conn()
        tests = conn.execute('SELECT * FROM regression_tests WHERE active = 1').fetchall()

        if not tests:
            conn.close()
            return {'error': 'No active regression tests'}

        # Create run record
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO regression_runs (trigger, total_tests) VALUES (?, ?)
        ''', (trigger, len(tests)))
        run_id = cursor.lastrowid
        conn.commit()

        passed = 0
        warned = 0
        failed = 0
        drift_scores = []

        for test in tests:
            try:
                if ask_function:
                    result = ask_function(test['question'])
                    actual_answer = result.get('answer', '')
                    confidence = result.get('confidence', 0)
                else:
                    actual_answer = ''
                    confidence = 0

                # Compute drift score
                drift = _compute_drift_score(test['expected_answer'], actual_answer,
                                            test['criteria'])
                drift_scores.append(drift['score'])

                # Classify result
                if drift['score'] < 0.2:
                    status = 'pass'
                    passed += 1
                elif drift['score'] < 0.5:
                    status = 'warn'
                    warned += 1
                else:
                    status = 'fail'
                    failed += 1

                cursor.execute('''
                    INSERT INTO regression_results
                    (run_id, test_id, actual_answer, confidence, drift_score, status, issues)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (run_id, test['id'], actual_answer, confidence,
                      drift['score'], status, json.dumps(drift['issues'])))

            except Exception as e:
                failed += 1
                cursor.execute('''
                    INSERT INTO regression_results
                    (run_id, test_id, drift_score, status, issues)
                    VALUES (?, ?, 1.0, 'error', ?)
                ''', (run_id, test['id'], json.dumps([str(e)])))

        # Update run summary
        avg_drift = sum(drift_scores) / len(drift_scores) if drift_scores else 0
        cursor.execute('''
            UPDATE regression_runs SET
                passed = ?, warned = ?, failed = ?,
                avg_drift_score = ?, completed_at = ?, status = 'completed'
            WHERE id = ?
        ''', (passed, warned, failed, avg_drift, datetime.now().isoformat(), run_id))

        conn.commit()
        conn.close()

        summary = {
            'run_id': run_id,
            'total': len(tests),
            'passed': passed,
            'warned': warned,
            'failed': failed,
            'avg_drift': round(avg_drift, 3),
            'trigger': trigger
        }

        severity = 'critical' if failed > 0 else ('warning' if warned > 0 else 'info')
        log_event('regression', 'suite_completed', json.dumps(summary), severity)
        return summary

    @staticmethod
    def get_regression_dashboard() -> Dict:
        """Get regression testing dashboard data."""
        conn = _get_conn()

        # Latest run
        latest = conn.execute('''
            SELECT * FROM regression_runs ORDER BY started_at DESC LIMIT 1
        ''').fetchone()

        # Last 10 runs trend
        runs = conn.execute('''
            SELECT id, passed, warned, failed, avg_drift_score, started_at
            FROM regression_runs ORDER BY started_at DESC LIMIT 10
        ''').fetchall()

        # Get results for latest run
        latest_results = []
        if latest:
            results = conn.execute('''
                SELECT rr.*, rt.question, rt.expected_answer, rt.category
                FROM regression_results rr
                JOIN regression_tests rt ON rr.test_id = rt.id
                WHERE rr.run_id = ?
                ORDER BY rr.drift_score DESC
            ''', (latest['id'],)).fetchall()
            latest_results = [dict(r) for r in results]

        conn.close()

        return {
            'latest_run': dict(latest) if latest else None,
            'latest_results': latest_results,
            'run_history': [dict(r) for r in runs],
            'test_count': len(RegressionDetector.get_regression_tests())
        }

    @staticmethod
    def update_regression_test(test_id: int, **kwargs) -> bool:
        """Update a regression test."""
        allowed = {'question', 'expected_answer', 'category', 'criteria', 'priority', 'active'}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return False
        conn = _get_conn()
        set_clause = ', '.join(f'{k} = ?' for k in updates)
        values = list(updates.values()) + [test_id]
        conn.execute(f'UPDATE regression_tests SET {set_clause} WHERE id = ?', values)
        conn.commit()
        conn.close()
        return True

    @staticmethod
    def delete_regression_test(test_id: int) -> bool:
        """Soft-delete a regression test."""
        return RegressionDetector.update_regression_test(test_id, active=False)
