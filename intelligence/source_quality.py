"""
Intelligence Engine — Subsystem 3: Source Quality Intelligence
===============================================================
Tracks which Pinecone sources lead to good vs bad answers.
"""

import json
import logging
from datetime import datetime
from typing import List, Dict, Optional

from intelligence.db import _get_conn, log_event

logger = logging.getLogger(__name__)


class SourceQualityIntelligence:
    """
    Tracks which Pinecone sources lead to good vs bad answers.
    Computes Bayesian reliability scores. Admin can boost/penalize.
    """

    @staticmethod
    def update_source_reliability(source_id: str, rating: str, confidence: float = None,
                                   source_title: str = None, source_type: str = None):
        """Update reliability score for a source based on user feedback."""
        is_positive = rating in ('helpful', 'good', 'correct')

        conn = _get_conn()
        existing = conn.execute('SELECT * FROM source_reliability WHERE source_id = ?',
                               (source_id,)).fetchone()

        if existing:
            pos = existing['positive_count'] + (1 if is_positive else 0)
            neg = existing['negative_count'] + (0 if is_positive else 1)
            total = existing['total_appearances'] + 1

            # Bayesian trust score: (positive + 1) / (total + 2) -- Beta(1,1) prior
            trust = (pos + 1) / (total + 2)

            # Incorporate admin boost
            trust = min(1.0, max(0.0, trust + existing['admin_boost']))

            # Running average of confidence when this source is used
            if confidence is not None:
                old_avg = existing['avg_confidence_when_used'] or confidence
                new_avg = (old_avg * existing['total_appearances'] + confidence) / total
            else:
                new_avg = existing['avg_confidence_when_used']

            conn.execute('''
                UPDATE source_reliability SET
                    trust_score = ?, positive_count = ?, negative_count = ?,
                    total_appearances = ?, avg_confidence_when_used = ?,
                    source_title = COALESCE(?, source_title),
                    source_type = COALESCE(?, source_type),
                    last_updated = ?
                WHERE source_id = ?
            ''', (trust, pos, neg, total, new_avg, source_title, source_type,
                  datetime.now().isoformat(), source_id))
        else:
            trust = 0.75 if is_positive else 0.25
            conn.execute('''
                INSERT INTO source_reliability
                (source_id, source_title, source_type, trust_score,
                 positive_count, negative_count, total_appearances, avg_confidence_when_used)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?)
            ''', (source_id, source_title, source_type, trust,
                  1 if is_positive else 0, 0 if is_positive else 1, confidence))

        conn.commit()
        conn.close()

    @staticmethod
    def get_source_reliability(source_id: str) -> Optional[Dict]:
        """Get reliability info for a specific source."""
        conn = _get_conn()
        row = conn.execute('SELECT * FROM source_reliability WHERE source_id = ?',
                          (source_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def get_source_leaderboard(limit: int = 50, min_appearances: int = 3) -> List[Dict]:
        """Get sources ranked by reliability."""
        conn = _get_conn()
        rows = conn.execute('''
            SELECT * FROM source_reliability
            WHERE total_appearances >= ?
            ORDER BY trust_score DESC
            LIMIT ?
        ''', (min_appearances, limit)).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @staticmethod
    def apply_source_adjustments(sources: List[Dict]) -> List[Dict]:
        """
        Adjust source scores based on reliability data.
        Called during reranking in the /ask pipeline.
        """
        if not sources:
            return sources

        conn = _get_conn()
        adjusted = []
        for source in sources:
            source_id = source.get('id', source.get('metadata', {}).get('source', ''))
            reliability = conn.execute(
                'SELECT trust_score, admin_boost FROM source_reliability WHERE source_id = ?',
                (source_id,)
            ).fetchone()

            if reliability:
                # Multiply rerank score by trust score (0.0-1.0)
                multiplier = max(0.3, reliability['trust_score'] + reliability['admin_boost'])
                source['original_score'] = source.get('score', 1.0)
                source['score'] = source.get('score', 1.0) * multiplier
                source['trust_score'] = reliability['trust_score']
            else:
                source['trust_score'] = 0.5  # Unknown source gets neutral trust

            adjusted.append(source)

        conn.close()
        return adjusted

    @staticmethod
    def set_admin_boost(source_id: str, boost: float):
        """Admin manually boosts or penalizes a source (-0.5 to +0.5)."""
        boost = max(-0.5, min(0.5, boost))
        conn = _get_conn()
        conn.execute('''
            UPDATE source_reliability SET admin_boost = ?, last_updated = ?
            WHERE source_id = ?
        ''', (boost, datetime.now().isoformat(), source_id))
        conn.commit()
        conn.close()
        log_event('source_quality', 'admin_boost_set',
                  json.dumps({'source_id': source_id, 'boost': boost}))

    @staticmethod
    def update_batch_from_feedback():
        """Batch update source reliability from recent feedback."""
        conn = _get_conn()
        # Get recent feedback with sources
        rows = conn.execute('''
            SELECT question, ai_answer, user_rating, sources, confidence_score
            FROM feedback
            WHERE user_rating != 'unrated' AND sources IS NOT NULL
            AND timestamp >= datetime('now', '-7 days')
        ''').fetchall()
        conn.close()

        updated_count = 0
        for row in rows:
            try:
                sources = json.loads(row['sources']) if row['sources'] else []
                for source in sources:
                    source_id = source.get('id', source.get('source', str(source)))
                    source_title = source.get('title', source.get('metadata', {}).get('title', ''))
                    SourceQualityIntelligence.update_source_reliability(
                        source_id=str(source_id),
                        rating=row['user_rating'],
                        confidence=row['confidence_score'],
                        source_title=source_title
                    )
                    updated_count += 1
            except (json.JSONDecodeError, TypeError):
                continue

        log_event('source_quality', 'batch_update', json.dumps({'updated': updated_count}))
        return updated_count
