"""
Intelligence Engine — Subsystem 16: Knowledge Gap Analyzer
============================================================
Detect knowledge gaps and content freshness issues.
"""

import json
import logging
from datetime import datetime
from typing import List, Dict

from intelligence.db import _get_conn, log_event

logger = logging.getLogger(__name__)


class KnowledgeGapAnalyzer:
    """Detect knowledge gaps and content freshness issues."""

    @staticmethod
    def detect_gaps() -> List[Dict]:
        """Find question patterns with insufficient knowledge coverage."""
        try:
            conn = _get_conn()
            gaps = []

            # Low confidence questions (patterns with consistently low confidence)
            low_conf = conn.execute('''
                SELECT cc.topic, COUNT(*) as count,
                       AVG(cc.predicted_confidence) as avg_conf,
                       GROUP_CONCAT(DISTINCT SUBSTR(qt.question, 1, 100)) as samples
                FROM confidence_calibration cc
                LEFT JOIN question_topics qt ON cc.query_id = qt.query_id
                WHERE cc.predicted_confidence < 55
                AND cc.timestamp > datetime('now', '-30 days')
                GROUP BY cc.topic
                HAVING count >= 3
                ORDER BY avg_conf ASC
            ''').fetchall()

            for row in low_conf:
                row = dict(row)
                samples = (row['samples'] or '').split(',')[:5]
                gaps.append({
                    'topic': row['topic'] or 'Unknown',
                    'gap_type': 'low_confidence',
                    'severity': 'high' if row['avg_conf'] < 40 else 'medium',
                    'avg_confidence': round(row['avg_conf'], 1),
                    'question_count': row['count'],
                    'sample_questions': samples,
                    'recommended_action': 'Add more training data or curated answers for this topic'
                })

            # High escalation topics
            esc_topics = conn.execute('''
                SELECT eq.failure_mode, COUNT(*) as count,
                       GROUP_CONCAT(DISTINCT SUBSTR(eq.question, 1, 100)) as samples
                FROM escalation_queue eq
                WHERE eq.status = 'open'
                AND eq.created_at > datetime('now', '-30 days')
                GROUP BY eq.failure_mode
                HAVING count >= 2
                ORDER BY count DESC
            ''').fetchall()

            for row in esc_topics:
                row = dict(row)
                samples = (row['samples'] or '').split(',')[:5]
                gaps.append({
                    'topic': row['failure_mode'],
                    'gap_type': 'high_escalation',
                    'severity': 'high',
                    'question_count': row['count'],
                    'sample_questions': samples,
                    'recommended_action': f"Address recurring {row['failure_mode']} failures"
                })

            # Store detected gaps
            for gap in gaps:
                conn.execute('''
                    INSERT INTO knowledge_gaps
                    (topic, category, gap_type, severity, avg_confidence, question_count,
                     sample_questions, recommended_action)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (gap['topic'], gap.get('category'), gap['gap_type'], gap['severity'],
                      gap.get('avg_confidence'), gap['question_count'],
                      json.dumps(gap['sample_questions']), gap['recommended_action']))

            conn.commit()
            conn.close()

            if gaps:
                log_event('knowledge_gaps', 'gaps_detected',
                          json.dumps({'count': len(gaps)}), 'info')

            return gaps
        except Exception as e:
            logger.error(f"Detect gaps error: {e}")
            return []

    @staticmethod
    def get_gap_report() -> List[Dict]:
        """Get the current knowledge gap report."""
        try:
            conn = _get_conn()
            rows = conn.execute('''
                SELECT * FROM knowledge_gaps
                WHERE status = 'open'
                ORDER BY
                    CASE severity WHEN 'critical' THEN 0 WHEN 'high' THEN 1
                    WHEN 'medium' THEN 2 ELSE 3 END,
                    question_count DESC
            ''').fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"Get gap report error: {e}")
            return []

    @staticmethod
    def track_content_freshness():
        """Track which sources are stale (not cited recently)."""
        try:
            conn = _get_conn()

            # Update citation counts from source_reliability
            sources = conn.execute('SELECT * FROM source_reliability').fetchall()

            for source in sources:
                source = dict(source)
                source_id = source['source_id']
                total = source['total_appearances']

                # Check last citation in pipeline metrics (via source reliability updates)
                last_updated = source.get('last_updated', '')
                days_since = 0
                if last_updated:
                    try:
                        last_dt = datetime.fromisoformat(last_updated)
                        days_since = (datetime.now() - last_dt).days
                    except (ValueError, TypeError):
                        days_since = 999

                freshness = max(0.0, 1.0 - (days_since / 90.0))  # 0 at 90+ days
                status = 'fresh' if days_since < 30 else 'aging' if days_since < 90 else 'stale'

                conn.execute('''
                    INSERT INTO content_freshness
                    (source_id, source_title, last_cited, citation_count, days_since_cited,
                     freshness_score, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(source_id) DO UPDATE SET
                        last_cited = ?, citation_count = ?, days_since_cited = ?,
                        freshness_score = ?, status = ?, updated_at = CURRENT_TIMESTAMP
                ''', (source_id, source.get('source_title', ''), last_updated,
                      total, days_since, freshness, status,
                      last_updated, total, days_since, freshness, status))

            conn.commit()
            conn.close()
            log_event('knowledge_gaps', 'freshness_tracked')
        except Exception as e:
            logger.error(f"Track freshness error: {e}")

    @staticmethod
    def get_freshness_report() -> List[Dict]:
        """Get content freshness report."""
        try:
            conn = _get_conn()
            # Add unique constraint if not exists for upsert
            try:
                conn.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_cf_source_id ON content_freshness(source_id)')
            except Exception:
                pass
            rows = conn.execute('''
                SELECT * FROM content_freshness
                ORDER BY freshness_score ASC, days_since_cited DESC
            ''').fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"Get freshness report error: {e}")
            return []

    @staticmethod
    def get_coverage_matrix() -> Dict:
        """Get category x quality heatmap data."""
        try:
            conn = _get_conn()
            categories = conn.execute('''
                SELECT DISTINCT topic FROM confidence_calibration WHERE topic IS NOT NULL
            ''').fetchall()

            matrix = []
            for cat in categories:
                topic = cat['topic']
                stats = conn.execute('''
                    SELECT AVG(predicted_confidence) as avg_conf,
                           COUNT(*) as count,
                           SUM(CASE WHEN actual_satisfaction > 0.5 THEN 1 ELSE 0 END) as positive
                    FROM confidence_calibration WHERE topic = ?
                    AND timestamp > datetime('now', '-30 days')
                ''', (topic,)).fetchone()

                if stats and stats['count'] > 0:
                    matrix.append({
                        'category': topic,
                        'query_count': stats['count'],
                        'avg_confidence': round(stats['avg_conf'] or 0, 1),
                        'satisfaction_rate': round((stats['positive'] or 0) / stats['count'], 3),
                        'quality_score': round(((stats['avg_conf'] or 0) / 100 +
                                               (stats['positive'] or 0) / stats['count']) / 2, 3)
                    })

            conn.close()
            matrix.sort(key=lambda x: x['quality_score'])
            return {'categories': matrix}
        except Exception as e:
            logger.error(f"Coverage matrix error: {e}")
            return {'categories': []}
