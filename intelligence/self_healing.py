"""
Intelligence Engine — Subsystem 1: Self-Healing Knowledge Loop
===============================================================
Detects recurring low-quality answer patterns and creates 'golden answers'.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict

from intelligence.db import _get_conn, log_event
from intelligence.helpers import _cosine_similarity, _keyword_similarity

logger = logging.getLogger(__name__)


class SelfHealingLoop:
    """
    Detects recurring low-quality answer patterns and creates 'golden answers'
    that get injected as few-shot examples for similar future questions.
    """

    @staticmethod
    def detect_weak_patterns(min_occurrences: int = 3, days: int = 30) -> List[Dict]:
        """
        Find question patterns with consistently low ratings or confidence.
        Returns patterns that need golden answers.
        """
        conn = _get_conn()
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        rows = conn.execute('''
            SELECT
                question,
                COUNT(*) as occurrence_count,
                AVG(confidence_score) as avg_confidence,
                SUM(CASE WHEN user_rating IN ('wrong', 'partially_wrong', 'bad') THEN 1 ELSE 0 END) as negative_count,
                SUM(CASE WHEN user_rating IN ('helpful', 'good', 'correct') THEN 1 ELSE 0 END) as positive_count,
                GROUP_CONCAT(DISTINCT user_rating) as ratings
            FROM feedback
            WHERE timestamp >= ? AND user_rating != 'unrated'
            GROUP BY question
            HAVING COUNT(*) >= ?
            AND (AVG(confidence_score) < 60 OR
                 CAST(SUM(CASE WHEN user_rating IN ('wrong', 'partially_wrong', 'bad') THEN 1 ELSE 0 END) AS REAL) / COUNT(*) > 0.3)
            ORDER BY avg_confidence ASC
        ''', (cutoff, min_occurrences)).fetchall()

        conn.close()
        patterns = []
        for row in rows:
            total = row['negative_count'] + row['positive_count']
            negative_rate = row['negative_count'] / total if total > 0 else 0
            patterns.append({
                'question': row['question'],
                'occurrences': row['occurrence_count'],
                'avg_confidence': round(row['avg_confidence'] or 0, 1),
                'negative_rate': round(negative_rate, 2),
                'ratings': row['ratings']
            })

        if patterns:
            log_event('self_healing', 'weak_patterns_detected',
                      json.dumps({'count': len(patterns)}))
        return patterns

    @staticmethod
    def create_golden_answer(question: str, answer: str, category: str = None,
                             source_feedback_id: int = None, embedding: List[float] = None) -> int:
        """Create a golden answer for a question pattern."""
        conn = _get_conn()
        embedding_json = json.dumps(embedding) if embedding else None

        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO golden_answers (question, answer, category, embedding, source_feedback_id)
            VALUES (?, ?, ?, ?, ?)
        ''', (question, answer, category, embedding_json, source_feedback_id))

        golden_id = cursor.lastrowid
        conn.commit()
        conn.close()

        log_event('self_healing', 'golden_answer_created',
                  json.dumps({'id': golden_id, 'category': category}))
        return golden_id

    @staticmethod
    def get_relevant_golden_answers(query: str, category: str = None,
                                     query_embedding: List[float] = None,
                                     limit: int = 3) -> List[Dict]:
        """
        Find golden answers relevant to the current query.
        Uses cosine similarity if embeddings available, falls back to keyword matching.
        """
        conn = _get_conn()

        # Get active golden answers
        if category:
            rows = conn.execute('''
                SELECT * FROM golden_answers
                WHERE active = 1 AND (category = ? OR category IS NULL)
                ORDER BY times_used DESC
            ''', (category,)).fetchall()
        else:
            rows = conn.execute('''
                SELECT * FROM golden_answers WHERE active = 1
                ORDER BY times_used DESC
            ''').fetchall()

        conn.close()

        if not rows:
            return []

        results = []
        for row in rows:
            score = 0.0

            # Embedding-based similarity
            if query_embedding and row['embedding']:
                try:
                    golden_emb = json.loads(row['embedding'])
                    score = _cosine_similarity(query_embedding, golden_emb)
                except (json.JSONDecodeError, TypeError):
                    score = _keyword_similarity(query, row['question'])
            else:
                score = _keyword_similarity(query, row['question'])

            if score > 0.3:  # Relevance threshold
                results.append({
                    'id': row['id'],
                    'question': row['question'],
                    'answer': row['answer'],
                    'category': row['category'],
                    'similarity': round(score, 3),
                    'times_used': row['times_used']
                })

        # Sort by similarity and return top N
        results.sort(key=lambda x: x['similarity'], reverse=True)
        return results[:limit]

    @staticmethod
    def record_golden_answer_usage(golden_id: int, rating: str = None):
        """Record that a golden answer was used and optionally its rating."""
        conn = _get_conn()
        conn.execute('''
            UPDATE golden_answers SET times_used = times_used + 1, updated_at = ?
            WHERE id = ?
        ''', (datetime.now().isoformat(), golden_id))

        if rating:
            # Update running average
            row = conn.execute('SELECT times_used, avg_rating_when_used FROM golden_answers WHERE id = ?',
                              (golden_id,)).fetchone()
            if row:
                current_avg = row['avg_rating_when_used'] or 0.0
                rating_val = 1.0 if rating in ('helpful', 'good', 'correct') else 0.0
                new_avg = (current_avg * (row['times_used'] - 1) + rating_val) / row['times_used']
                conn.execute('UPDATE golden_answers SET avg_rating_when_used = ? WHERE id = ?',
                           (new_avg, golden_id))

        conn.commit()
        conn.close()

    @staticmethod
    def get_all_golden_answers(include_inactive: bool = False) -> List[Dict]:
        """Get all golden answers for admin view."""
        conn = _get_conn()
        if include_inactive:
            rows = conn.execute('SELECT * FROM golden_answers ORDER BY created_at DESC').fetchall()
        else:
            rows = conn.execute('SELECT * FROM golden_answers WHERE active = 1 ORDER BY created_at DESC').fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @staticmethod
    def update_golden_answer(golden_id: int, **kwargs) -> bool:
        """Update a golden answer's fields."""
        allowed = {'question', 'answer', 'category', 'active', 'embedding'}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return False

        conn = _get_conn()
        set_clause = ', '.join(f'{k} = ?' for k in updates)
        values = list(updates.values()) + [datetime.now().isoformat(), golden_id]
        conn.execute(f'UPDATE golden_answers SET {set_clause}, updated_at = ? WHERE id = ?', values)
        conn.commit()
        conn.close()
        return True

    @staticmethod
    def delete_golden_answer(golden_id: int) -> bool:
        """Soft-delete a golden answer."""
        return SelfHealingLoop.update_golden_answer(golden_id, active=False)
