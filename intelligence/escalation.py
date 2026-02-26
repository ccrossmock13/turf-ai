"""
Intelligence Engine — Subsystem 8 & 12: Smart Escalation + Remediation
========================================================================
SmartEscalation and RemediationEngine.
"""

import json
import logging
from datetime import datetime
from typing import List, Dict, Optional

from intelligence.db import _get_conn, log_event
from intelligence.helpers import _keyword_similarity

logger = logging.getLogger(__name__)


class SmartEscalation:
    """
    Classifies failure modes, finds similar approved answers,
    suggests corrections. Prioritized queue for admin.
    """

    FAILURE_MODES = [
        'hallucination',        # Answer contains unverified claims
        'outdated_info',        # Information may be stale
        'wrong_category',       # Answered about wrong topic/grass type
        'insufficient_sources', # Not enough supporting evidence
        'off_topic',           # Question not in domain
        'safety_concern',      # Dangerous recommendation
        'low_confidence',      # System unsure of answer
        'predicted_negative',  # Satisfaction model predicts bad rating
    ]

    @staticmethod
    def create_escalation(query_id: int, question: str, answer: str,
                          failure_mode: str, failure_details: str = None,
                          predicted_satisfaction: float = None, confidence: float = None,
                          suggested_fix: str = None, similar_ids: List[int] = None,
                          priority: int = 5) -> int:
        """Add an item to the smart escalation queue."""
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO escalation_queue
            (query_id, question, answer, failure_mode, failure_details,
             predicted_satisfaction, confidence, suggested_fix, similar_approved_ids, priority)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (query_id, question, answer, failure_mode, failure_details,
              predicted_satisfaction, confidence, suggested_fix,
              json.dumps(similar_ids) if similar_ids else None, priority))
        esc_id = cursor.lastrowid
        conn.commit()
        conn.close()

        log_event('escalation', 'created',
                  json.dumps({'id': esc_id, 'mode': failure_mode, 'priority': priority}),
                  severity='warning')
        return esc_id

    @staticmethod
    def classify_failure_mode(confidence: float, grounding_result: Dict = None,
                               hallucination_result: Dict = None,
                               source_count: int = 0,
                               predicted_satisfaction: float = None) -> Optional[Dict]:
        """
        Classify failure mode based on answer metadata.
        Returns failure mode + details, or None if no failure detected.
        """
        failure_mode = None
        details = []
        priority = 5

        # Check for hallucination
        if grounding_result and not grounding_result.get('grounded', True):
            failure_mode = 'hallucination'
            claims = grounding_result.get('unsupported_claims', [])
            details.append(f"Unsupported claims: {', '.join(claims[:3])}")
            priority = 9

        # Check hallucination filter results
        if hallucination_result and hallucination_result.get('penalties'):
            if not failure_mode:
                failure_mode = 'hallucination'
            details.append(f"Filter penalties: {hallucination_result['penalties']}")
            priority = max(priority, 8)

        # Check safety concerns
        if hallucination_result and any('dangerous' in str(p).lower()
                                        for p in hallucination_result.get('penalties', [])):
            failure_mode = 'safety_concern'
            priority = 10

        # Insufficient sources
        if source_count == 0:
            failure_mode = failure_mode or 'insufficient_sources'
            details.append("No sources found")
            priority = max(priority, 7)
        elif source_count < 2:
            if not failure_mode:
                failure_mode = 'insufficient_sources'
            details.append(f"Only {source_count} source(s)")

        # Low confidence
        if confidence < 40:
            failure_mode = failure_mode or 'low_confidence'
            details.append(f"Confidence: {confidence}")
            priority = max(priority, 6)

        # Predicted negative satisfaction
        if predicted_satisfaction is not None and predicted_satisfaction < 0.4:
            failure_mode = failure_mode or 'predicted_negative'
            details.append(f"Predicted satisfaction: {predicted_satisfaction:.2f}")
            priority = max(priority, 7)

        if failure_mode:
            return {
                'failure_mode': failure_mode,
                'details': '; '.join(details),
                'priority': priority
            }
        return None

    @staticmethod
    def find_similar_approved(question: str, question_embedding: List[float] = None,
                               category: str = None, limit: int = 3) -> List[Dict]:
        """Find similar previously-approved answers as correction suggestions."""
        conn = _get_conn()

        # Search in feedback that was approved
        rows = conn.execute('''
            SELECT f.id, f.question, f.ai_answer, f.confidence_score,
                   ma.corrected_answer
            FROM feedback f
            LEFT JOIN moderator_actions ma ON f.id = ma.feedback_id AND ma.action = 'approve'
            WHERE f.approved_for_training = 1
            ORDER BY f.timestamp DESC LIMIT 500
        ''').fetchall()
        conn.close()

        if not rows:
            return []

        # Score by keyword similarity (embedding similarity would be better but this is fast)
        scored = []
        for row in rows:
            sim = _keyword_similarity(question, row['question'])
            if sim > 0.2:
                scored.append({
                    'feedback_id': row['id'],
                    'question': row['question'],
                    'approved_answer': row['corrected_answer'] or row['ai_answer'],
                    'confidence': row['confidence_score'],
                    'similarity': round(sim, 3)
                })

        scored.sort(key=lambda x: x['similarity'], reverse=True)
        return scored[:limit]

    @staticmethod
    def get_smart_escalation_queue(status: str = 'open', limit: int = 50) -> List[Dict]:
        """Get prioritized escalation queue."""
        conn = _get_conn()
        rows = conn.execute('''
            SELECT * FROM escalation_queue
            WHERE status = ?
            ORDER BY priority DESC, created_at ASC
            LIMIT ?
        ''', (status, limit)).fetchall()
        conn.close()

        results = []
        for row in rows:
            item = dict(row)
            if item.get('similar_approved_ids'):
                try:
                    item['similar_approved_ids'] = json.loads(item['similar_approved_ids'])
                except json.JSONDecodeError:
                    pass
            results.append(item)
        return results

    @staticmethod
    def resolve_escalation(escalation_id: int, action: str, resolved_by: str = 'admin',
                            notes: str = None, corrected_answer: str = None) -> bool:
        """Resolve an escalation. If corrected_answer provided, optionally create golden answer."""
        from intelligence.self_healing import SelfHealingLoop

        conn = _get_conn()
        escalation = conn.execute('SELECT * FROM escalation_queue WHERE id = ?',
                                 (escalation_id,)).fetchone()
        if not escalation:
            conn.close()
            return False

        conn.execute('''
            UPDATE escalation_queue SET
                status = 'resolved', resolved_by = ?,
                resolution_action = ?, resolution_notes = ?,
                resolved_at = ?
            WHERE id = ?
        ''', (resolved_by, action, notes, datetime.now().isoformat(), escalation_id))
        conn.commit()
        conn.close()

        # If admin provided a corrected answer, offer to create golden answer
        if corrected_answer and action in ('correct', 'approve_with_fix'):
            SelfHealingLoop.create_golden_answer(
                question=escalation['question'],
                answer=corrected_answer,
                source_feedback_id=escalation['query_id']
            )

        log_event('escalation', 'resolved',
                  json.dumps({'id': escalation_id, 'action': action}))
        return True

    @staticmethod
    def get_escalation_stats() -> Dict:
        """Get escalation queue statistics."""
        conn = _get_conn()
        stats = {}

        # By status
        for status in ['open', 'resolved', 'dismissed']:
            count = conn.execute('SELECT COUNT(*) FROM escalation_queue WHERE status = ?',
                               (status,)).fetchone()[0]
            stats[f'{status}_count'] = count

        # By failure mode
        modes = conn.execute('''
            SELECT failure_mode, COUNT(*) as count
            FROM escalation_queue WHERE status = 'open'
            GROUP BY failure_mode ORDER BY count DESC
        ''').fetchall()
        stats['by_failure_mode'] = {r['failure_mode']: r['count'] for r in modes}

        # Average resolution time
        avg_time = conn.execute('''
            SELECT AVG(julianday(resolved_at) - julianday(created_at)) * 24 as avg_hours
            FROM escalation_queue WHERE status = 'resolved'
        ''').fetchone()
        stats['avg_resolution_hours'] = round(avg_time['avg_hours'] or 0, 1)

        conn.close()
        return stats


class RemediationEngine:
    """Automated remediation engine with predefined actions."""

    @staticmethod
    def execute(trigger_type: str, context: Dict = None) -> Optional[Dict]:
        """Execute a remediation action based on trigger type."""
        from intelligence.circuit_breaker import CircuitBreaker

        context = context or {}
        try:
            action = None

            if trigger_type == 'source_failure':
                source_id = context.get('source_id')
                if source_id:
                    CircuitBreaker.record_failure(source_id)
                    action = {
                        'action_type': 'circuit_breaker',
                        'target': source_id,
                        'details': 'Recorded failure for circuit breaker evaluation'
                    }

            elif trigger_type == 'high_latency':
                action = {
                    'action_type': 'fallback_model_suggestion',
                    'target': 'gpt-4o',
                    'before_state': json.dumps({'model': context.get('model', 'gpt-4o')}),
                    'after_state': json.dumps({'suggestion': 'Consider switching to gpt-4o-mini'}),
                    'details': f"Latency {context.get('latency_ms', 0):.0f}ms exceeded threshold"
                }

            elif trigger_type == 'cost_overrun':
                action = {
                    'action_type': 'cost_alert',
                    'target': 'budget',
                    'before_state': json.dumps({'spend': context.get('current_spend', 0)}),
                    'after_state': json.dumps({'budget': context.get('budget', 0)}),
                    'details': f"Cost ${context.get('current_spend', 0):.4f} approaching budget ${context.get('budget', 0):.2f}"
                }

            if action:
                conn = _get_conn()
                conn.execute('''
                    INSERT INTO remediation_actions
                    (trigger_type, action_type, target, before_state, after_state, details)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (trigger_type, action['action_type'], action.get('target'),
                      action.get('before_state'), action.get('after_state'),
                      action.get('details')))
                conn.commit()
                conn.close()
                log_event('remediation', action['action_type'],
                          json.dumps({'trigger': trigger_type}))

            return action
        except Exception as e:
            logger.error(f"Remediation execute error: {e}")
            return None

    @staticmethod
    def get_history(limit: int = 50) -> List[Dict]:
        """Get remediation action history."""
        try:
            conn = _get_conn()
            rows = conn.execute('''
                SELECT * FROM remediation_actions ORDER BY timestamp DESC LIMIT ?
            ''', (limit,)).fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"Get remediation history error: {e}")
            return []
