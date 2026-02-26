"""
Intelligence Engine — Subsystem 17: Conversation Intelligence + Executive Dashboard
======================================================================================
Analyze multi-turn conversation quality, detect frustration,
and provide C-suite level system health scoring and reporting.
"""

import json
import logging
from db import get_db, CONVERSATIONS_DB, FEEDBACK_DB
from datetime import datetime, timedelta
from typing import List, Dict, Optional

from intelligence.db import _get_conn, log_event
from intelligence.helpers import _keyword_similarity

logger = logging.getLogger(__name__)


class ConversationIntelligence:
    """Analyze multi-turn conversation quality and detect frustration."""

    @staticmethod
    def analyze_conversation(conversation_id: str) -> Optional[Dict]:
        """Analyze a single conversation's quality metrics."""
        try:
            # Read from conversation DB
            with get_db(CONVERSATIONS_DB) as conn:
                messages = conn.execute('''
                    SELECT m.role, m.content, m.timestamp FROM messages m
                    JOIN conversations c ON m.conversation_id = c.id
                    WHERE c.session_id = ? ORDER BY m.timestamp
                ''', (conversation_id,)).fetchall()

            if not messages:
                return None

            turns = len([m for m in messages if m['role'] == 'user'])
            ai_messages = [m for m in messages if m['role'] == 'assistant']

            # Detect frustration signals
            frustration_signals = []
            user_messages = [m for m in messages if m['role'] == 'user']
            for i, msg in enumerate(user_messages):
                content = msg['content'].lower().strip()
                # Very short follow-ups
                if len(content) < 15 and i > 0:
                    frustration_signals.append({'type': 'short_followup', 'message': content})
                # Negative indicators
                if any(w in content for w in ['wrong', 'incorrect', 'no that', "that's not",
                                                'not what i', 'try again', 'not helpful']):
                    frustration_signals.append({'type': 'negative_feedback', 'message': content[:50]})
                # Repeated question pattern
                if i > 0 and _keyword_similarity(content, user_messages[i-1]['content'].lower()) > 0.7:
                    frustration_signals.append({'type': 'repeated_question', 'message': content[:50]})

            frustration_score = min(1.0, len(frustration_signals) * 0.3)

            # Resolution status
            if turns == 1:
                resolution = 'single_turn'
            elif frustration_score > 0.5:
                resolution = 'frustrated'
            elif turns <= 3:
                resolution = 'resolved'
            else:
                resolution = 'extended'

            # Topic drift (how different are sequential user questions)
            drift_score = 0.0
            if len(user_messages) > 1:
                drifts = []
                for i in range(1, len(user_messages)):
                    sim = _keyword_similarity(user_messages[i-1]['content'], user_messages[i]['content'])
                    drifts.append(1.0 - sim)
                drift_score = sum(drifts) / len(drifts)

            result = {
                'conversation_id': conversation_id,
                'turn_count': turns,
                'resolution_status': resolution,
                'frustration_score': round(frustration_score, 3),
                'frustration_signals': frustration_signals,
                'topic_drift_score': round(drift_score, 3),
                'first_message': messages[0]['timestamp'] if messages else None,
                'last_message': messages[-1]['timestamp'] if messages else None,
            }

            # Store analysis
            with get_db(FEEDBACK_DB) as feedback_conn:
                feedback_conn.execute('''
                    INSERT OR REPLACE INTO conversation_analytics
                    (conversation_id, turn_count, resolution_status, frustration_score,
                     frustration_signals, topic_drift_score, first_message, last_message)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (conversation_id, turns, resolution, frustration_score,
                      json.dumps(frustration_signals), drift_score,
                      result['first_message'], result['last_message']))

            return result
        except Exception as e:
            logger.error(f"Analyze conversation error: {e}")
            return None

    @staticmethod
    def get_conversation_quality_metrics() -> Dict:
        """Get aggregate conversation quality metrics."""
        try:
            conn = _get_conn()

            stats = conn.execute('''
                SELECT COUNT(*) as total,
                       AVG(turn_count) as avg_turns,
                       AVG(frustration_score) as avg_frustration,
                       AVG(topic_drift_score) as avg_drift,
                       COUNT(CASE WHEN resolution_status = 'resolved' THEN 1 END) as resolved,
                       COUNT(CASE WHEN resolution_status = 'frustrated' THEN 1 END) as frustrated,
                       COUNT(CASE WHEN resolution_status = 'single_turn' THEN 1 END) as single_turn,
                       COUNT(CASE WHEN resolution_status = 'extended' THEN 1 END) as extended
                FROM conversation_analytics
            ''').fetchone()

            recent = conn.execute('''
                SELECT * FROM conversation_analytics
                ORDER BY analyzed_at DESC LIMIT 20
            ''').fetchall()

            conn.close()

            return {
                'total_conversations': stats['total'] or 0,
                'avg_turns': round(stats['avg_turns'] or 0, 1),
                'avg_frustration': round(stats['avg_frustration'] or 0, 3),
                'avg_topic_drift': round(stats['avg_drift'] or 0, 3),
                'resolution_breakdown': {
                    'resolved': stats['resolved'] or 0,
                    'frustrated': stats['frustrated'] or 0,
                    'single_turn': stats['single_turn'] or 0,
                    'extended': stats['extended'] or 0
                },
                'recent': [dict(r) for r in recent]
            }
        except Exception as e:
            logger.error(f"Conversation metrics error: {e}")
            return {'error': str(e)}

    @staticmethod
    def detect_frustration_signals(days: int = 7) -> List[Dict]:
        """Find conversations with high frustration in recent period."""
        try:
            conn = _get_conn()
            cutoff = (datetime.now() - timedelta(days=days)).isoformat()

            rows = conn.execute('''
                SELECT * FROM conversation_analytics
                WHERE frustration_score > 0.3
                AND analyzed_at > ?
                ORDER BY frustration_score DESC
                LIMIT 50
            ''', (cutoff,)).fetchall()
            conn.close()

            results = []
            for r in rows:
                r = dict(r)
                try:
                    r['frustration_signals'] = json.loads(r.get('frustration_signals', '[]'))
                except (json.JSONDecodeError, TypeError):
                    r['frustration_signals'] = []
                results.append(r)

            return results
        except Exception as e:
            logger.error(f"Detect frustration error: {e}")
            return []

    @staticmethod
    def batch_analyze_recent(days: int = 7):
        """Analyze all recent conversations that haven't been analyzed."""
        try:
            cutoff = (datetime.now() - timedelta(days=days)).isoformat()

            with get_db(CONVERSATIONS_DB) as conn:
                sessions = conn.execute('''
                    SELECT DISTINCT c.session_id FROM messages m
                    JOIN conversations c ON m.conversation_id = c.id
                    WHERE m.timestamp > ? AND m.role = 'user'
                ''', (cutoff,)).fetchall()

            analyzed = 0
            for session in sessions:
                result = ConversationIntelligence.analyze_conversation(session['session_id'])
                if result:
                    analyzed += 1

            if analyzed > 0:
                log_event('conversation_intelligence', 'batch_analyzed',
                          json.dumps({'count': analyzed}))
        except Exception as e:
            logger.error(f"Batch analyze error: {e}")


class ExecutiveDashboard:
    """C-suite level system health scoring and reporting."""

    @staticmethod
    def compute_system_health() -> Dict:
        """Compute overall system health score (0-100)."""
        try:
            conn = _get_conn()
            components = {}
            cutoff_24h = (datetime.now() - timedelta(hours=24)).isoformat()
            cutoff_7d = (datetime.now() - timedelta(days=7)).isoformat()

            # 1. Availability (20%) -- based on requests in last 24h vs expected
            req_count = conn.execute('''
                SELECT COUNT(*) as count FROM pipeline_metrics WHERE timestamp > ?
            ''', (cutoff_24h,)).fetchone()['count']
            # Score: 100 if any requests, scale by expected volume
            availability = min(100, (req_count / max(1, 1)) * 100) if req_count > 0 else 50
            components['availability'] = {'score': round(availability, 1), 'weight': 0.20,
                                           'detail': f"{req_count} requests in 24h"}

            # 2. Latency p95 (15%) -- target <10s, critical >20s
            lats = conn.execute('''
                SELECT total_latency_ms FROM pipeline_metrics
                WHERE timestamp > ? ORDER BY total_latency_ms
            ''', (cutoff_24h,)).fetchall()
            if lats:
                n = len(lats)
                p95 = lats[int(n * 0.95)]['total_latency_ms'] if n > 1 else lats[0]['total_latency_ms']
                lat_score = max(0, min(100, 100 - (p95 - 5000) / 150))
            else:
                p95 = 0
                lat_score = 75
            components['latency'] = {'score': round(lat_score, 1), 'weight': 0.15,
                                      'detail': f"p95: {p95:.0f}ms"}

            # 3. User satisfaction (25%)
            sat = conn.execute('''
                SELECT COUNT(CASE WHEN was_correct = 1 THEN 1 END) as correct,
                       COUNT(*) as total
                FROM satisfaction_predictions
                WHERE actual_rating IS NOT NULL AND timestamp > ?
            ''', (cutoff_7d,)).fetchone()
            if sat and sat['total'] > 0:
                sat_rate = sat['correct'] / sat['total']
                sat_score = sat_rate * 100
            else:
                sat_rate = 0.75
                sat_score = 75
            components['satisfaction'] = {'score': round(sat_score, 1), 'weight': 0.25,
                                           'detail': f"{sat_rate:.1%} satisfaction rate"}

            # 4. Confidence calibration accuracy (10%)
            calib = conn.execute('''
                SELECT COUNT(*) as total,
                       AVG(ABS(predicted_confidence/100.0 - COALESCE(actual_satisfaction, 0.5))) as avg_error
                FROM confidence_calibration WHERE timestamp > ?
            ''', (cutoff_7d,)).fetchone()
            if calib and calib['total'] > 0:
                calib_score = max(0, 100 - (calib['avg_error'] or 0.5) * 200)
            else:
                calib_score = 60
            components['calibration'] = {'score': round(calib_score, 1), 'weight': 0.10,
                                          'detail': f"Calibration error: {(calib['avg_error'] or 0.5):.3f}"}

            # 5. Cost efficiency (10%)
            cost = conn.execute('''
                SELECT SUM(total_cost_usd) as total, COUNT(*) as count
                FROM pipeline_metrics WHERE timestamp > ?
            ''', (cutoff_24h,)).fetchone()
            if cost and cost['count'] > 0:
                avg_cost = (cost['total'] or 0) / cost['count']
                cost_score = max(0, min(100, 100 - avg_cost * 10000))
            else:
                avg_cost = 0
                cost_score = 80
            components['cost_efficiency'] = {'score': round(cost_score, 1), 'weight': 0.10,
                                              'detail': f"Avg ${avg_cost:.4f}/request"}

            # 6. Content coverage (10%)
            gaps = conn.execute('''
                SELECT COUNT(*) as count FROM knowledge_gaps WHERE status = 'open'
            ''').fetchone()['count']
            coverage_score = max(0, 100 - gaps * 10)
            components['content_coverage'] = {'score': round(coverage_score, 1), 'weight': 0.10,
                                               'detail': f"{gaps} open knowledge gaps"}

            # 7. Escalation resolution (10%)
            esc = conn.execute('''
                SELECT COUNT(CASE WHEN status = 'open' THEN 1 END) as open_count,
                       COUNT(CASE WHEN status = 'resolved' THEN 1 END) as resolved,
                       COUNT(*) as total
                FROM escalation_queue WHERE created_at > ?
            ''', (cutoff_7d,)).fetchone()
            if esc and esc['total'] > 0:
                resolution_rate = esc['resolved'] / esc['total']
                esc_score = resolution_rate * 100
            else:
                resolution_rate = 1.0
                esc_score = 85
            components['escalation_resolution'] = {'score': round(esc_score, 1), 'weight': 0.10,
                                                    'detail': f"{resolution_rate:.1%} resolution rate"}

            conn.close()

            # Weighted health score
            health_score = sum(c['score'] * c['weight'] for c in components.values())

            status = 'healthy' if health_score >= 80 else 'degraded' if health_score >= 60 else 'critical'

            return {
                'health_score': round(health_score, 1),
                'status': status,
                'components': components,
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"System health error: {e}")
            return {'health_score': 0, 'status': 'error', 'error': str(e)}

    @staticmethod
    def generate_weekly_digest() -> Dict:
        """Generate a weekly performance digest."""
        try:
            conn = _get_conn()
            cutoff = (datetime.now() - timedelta(days=7)).isoformat()

            # Query volume
            vol = conn.execute('''
                SELECT COUNT(*) as total,
                       SUM(total_cost_usd) as total_cost,
                       AVG(total_latency_ms) as avg_latency,
                       AVG(total_cost_usd) as avg_cost
                FROM pipeline_metrics WHERE timestamp > ?
            ''', (cutoff,)).fetchone()

            # Satisfaction
            sat = conn.execute('''
                SELECT COUNT(CASE WHEN was_correct = 1 THEN 1 END) as correct,
                       COUNT(*) as total
                FROM satisfaction_predictions
                WHERE actual_rating IS NOT NULL AND timestamp > ?
            ''', (cutoff,)).fetchone()

            # Top topics
            topics = conn.execute('''
                SELECT tc.name, COUNT(qt.id) as count
                FROM question_topics qt
                JOIN topic_clusters tc ON qt.cluster_id = tc.id
                WHERE qt.timestamp > ?
                GROUP BY tc.name ORDER BY count DESC LIMIT 5
            ''', (cutoff,)).fetchall()

            # Escalations
            esc = conn.execute('''
                SELECT COUNT(*) as total,
                       COUNT(CASE WHEN status = 'resolved' THEN 1 END) as resolved
                FROM escalation_queue WHERE created_at > ?
            ''', (cutoff,)).fetchone()

            # Alerts fired
            alerts = conn.execute('''
                SELECT COUNT(*) as count FROM alert_history WHERE timestamp > ?
            ''', (cutoff,)).fetchone()

            # Regressions
            reg = conn.execute('''
                SELECT passed, warned, failed FROM regression_runs
                WHERE started_at > ? ORDER BY started_at DESC LIMIT 1
            ''', (cutoff,)).fetchone()

            conn.close()

            digest = {
                'period': f"{(datetime.now() - timedelta(days=7)).strftime('%b %d')} - {datetime.now().strftime('%b %d, %Y')}",
                'total_queries': vol['total'] or 0,
                'total_cost_usd': round(vol['total_cost'] or 0, 4),
                'avg_latency_ms': round(vol['avg_latency'] or 0, 0),
                'avg_cost_per_query': round(vol['avg_cost'] or 0, 6),
                'satisfaction_rate': round((sat['correct'] or 0) / max(sat['total'] or 1, 1), 3),
                'satisfaction_total_rated': sat['total'] or 0,
                'top_topics': [{'name': t['name'], 'count': t['count']} for t in topics],
                'escalations_total': esc['total'] or 0,
                'escalations_resolved': esc['resolved'] or 0,
                'alerts_fired': alerts['count'] or 0,
                'regression_results': dict(reg) if reg else None,
                'generated_at': datetime.now().isoformat()
            }

            # Compute ROI
            queries = digest['total_queries']
            est_hours_saved = queries * 0.05  # assume 3 min per manual answer
            est_cost_saved = est_hours_saved * 50  # $50/hr analyst
            digest['roi'] = {
                'queries_automated': queries,
                'est_human_hours_saved': round(est_hours_saved, 1),
                'est_cost_saved_usd': round(est_cost_saved, 2),
                'ai_cost_usd': digest['total_cost_usd'],
                'roi_multiple': round(est_cost_saved / max(digest['total_cost_usd'], 0.01), 1)
            }

            log_event('executive_dashboard', 'weekly_digest_generated')
            return digest
        except Exception as e:
            logger.error(f"Weekly digest error: {e}")
            return {'error': str(e)}

    @staticmethod
    def get_kpi_trends(period: str = '30d') -> Dict:
        """Get time-series KPI data for trend charts."""
        try:
            conn = _get_conn()
            days = int(period.replace('d', ''))
            cutoff = (datetime.now() - timedelta(days=days)).isoformat()

            # Daily query volume + cost
            daily = conn.execute('''
                SELECT strftime('%Y-%m-%d', timestamp) as day,
                       COUNT(*) as queries,
                       SUM(total_cost_usd) as cost,
                       AVG(total_latency_ms) as avg_latency
                FROM pipeline_metrics WHERE timestamp > ?
                GROUP BY day ORDER BY day
            ''', (cutoff,)).fetchall()

            # Daily satisfaction
            daily_sat = conn.execute('''
                SELECT strftime('%Y-%m-%d', timestamp) as day,
                       COUNT(CASE WHEN was_correct = 1 THEN 1 END) as correct,
                       COUNT(*) as total
                FROM satisfaction_predictions
                WHERE actual_rating IS NOT NULL AND timestamp > ?
                GROUP BY day ORDER BY day
            ''', (cutoff,)).fetchall()

            conn.close()

            return {
                'period': period,
                'daily_metrics': [dict(r) for r in daily],
                'daily_satisfaction': [
                    {'day': r['day'],
                     'rate': round(r['correct'] / max(r['total'], 1), 3),
                     'total_rated': r['total']}
                    for r in daily_sat
                ]
            }
        except Exception as e:
            logger.error(f"KPI trends error: {e}")
            return {'error': str(e)}

    @staticmethod
    def compute_roi_metrics() -> Dict:
        """Compute return-on-investment metrics."""
        try:
            conn = _get_conn()
            total = conn.execute('''
                SELECT COUNT(*) as queries, SUM(total_cost_usd) as cost
                FROM pipeline_metrics
            ''').fetchone()

            monthly = conn.execute('''
                SELECT COUNT(*) as queries, SUM(total_cost_usd) as cost
                FROM pipeline_metrics
                WHERE timestamp > datetime('now', '-30 days')
            ''').fetchone()

            conn.close()

            all_queries = total['queries'] or 0
            all_cost = total['cost'] or 0
            month_queries = monthly['queries'] or 0
            month_cost = monthly['cost'] or 0

            return {
                'all_time': {
                    'queries': all_queries,
                    'cost_usd': round(all_cost, 4),
                    'cost_per_query': round(all_cost / max(all_queries, 1), 6),
                    'est_hours_saved': round(all_queries * 0.05, 1),
                    'est_cost_saved': round(all_queries * 0.05 * 50, 2)
                },
                'last_30_days': {
                    'queries': month_queries,
                    'cost_usd': round(month_cost, 4),
                    'cost_per_query': round(month_cost / max(month_queries, 1), 6),
                    'est_hours_saved': round(month_queries * 0.05, 1),
                    'est_cost_saved': round(month_queries * 0.05 * 50, 2)
                }
            }
        except Exception as e:
            logger.error(f"ROI metrics error: {e}")
            return {'error': str(e)}
