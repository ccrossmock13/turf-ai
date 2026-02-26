"""
Intelligence Engine — Subsystem 6: Topic Clustering & Trend Intelligence
==========================================================================
Clusters questions using embeddings. Tracks per-topic quality metrics.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional

from intelligence.db import _get_conn, log_event
from intelligence.helpers import (
    _cosine_similarity, _agglomerative_cluster,
    _compute_centroid, _auto_name_cluster
)

logger = logging.getLogger(__name__)


class TopicIntelligence:
    """
    Clusters questions using embeddings. Tracks per-topic quality metrics.
    Detects emerging topics and seasonal patterns.
    """

    @staticmethod
    def store_question_embedding(question: str, embedding: List[float],
                                  query_id: int = None, cluster_id: int = None):
        """Store a question with its embedding for future clustering."""
        conn = _get_conn()
        conn.execute('''
            INSERT INTO question_topics (query_id, question, cluster_id, embedding)
            VALUES (?, ?, ?, ?)
        ''', (query_id, question, cluster_id, json.dumps(embedding)))
        conn.commit()
        conn.close()

    @staticmethod
    def cluster_questions(min_cluster_size: int = 5, similarity_threshold: float = 0.7) -> Dict:
        """
        Run agglomerative clustering on stored question embeddings.
        Groups similar questions into topic clusters.
        """
        conn = _get_conn()
        rows = conn.execute('''
            SELECT id, question, embedding FROM question_topics
            WHERE embedding IS NOT NULL
            ORDER BY timestamp DESC LIMIT 5000
        ''').fetchall()
        conn.close()

        if len(rows) < min_cluster_size:
            return {'clusters_created': 0, 'reason': 'insufficient_data'}

        # Parse embeddings
        questions = []
        embeddings = []
        ids = []
        for row in rows:
            try:
                emb = json.loads(row['embedding'])
                questions.append(row['question'])
                embeddings.append(emb)
                ids.append(row['id'])
            except (json.JSONDecodeError, TypeError):
                continue

        if len(embeddings) < min_cluster_size:
            return {'clusters_created': 0, 'reason': 'insufficient_valid_embeddings'}

        # Simple agglomerative clustering
        clusters = _agglomerative_cluster(embeddings, similarity_threshold, min_cluster_size)

        # Create/update cluster records
        conn = _get_conn()
        clusters_created = 0

        for cluster_idx, member_indices in clusters.items():
            if len(member_indices) < min_cluster_size:
                continue

            cluster_questions = [questions[i] for i in member_indices]
            cluster_embeddings = [embeddings[i] for i in member_indices]

            # Compute centroid
            centroid = _compute_centroid(cluster_embeddings)

            # Auto-name using most common words
            name = _auto_name_cluster(cluster_questions)

            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO topic_clusters (name, centroid_embedding, question_count, last_seen)
                VALUES (?, ?, ?, ?)
            ''', (name, json.dumps(centroid), len(member_indices), datetime.now().isoformat()))
            cluster_id = cursor.lastrowid

            # Update question-to-cluster mappings
            for idx in member_indices:
                sim = _cosine_similarity(embeddings[idx], centroid)
                conn.execute('''
                    UPDATE question_topics SET cluster_id = ?, similarity_score = ?
                    WHERE id = ?
                ''', (cluster_id, sim, ids[idx]))

            clusters_created += 1

        conn.commit()
        conn.close()

        log_event('topic_clustering', 'clustering_complete',
                  json.dumps({'clusters_created': clusters_created, 'questions_processed': len(embeddings)}))
        return {'clusters_created': clusters_created, 'questions_processed': len(embeddings)}

    @staticmethod
    def assign_topic(query: str, embedding: List[float]) -> Optional[Dict]:
        """Assign a new question to the closest existing cluster."""
        conn = _get_conn()
        clusters = conn.execute('''
            SELECT id, name, centroid_embedding FROM topic_clusters WHERE active = 1
        ''').fetchall()
        conn.close()

        if not clusters:
            return None

        best_match = None
        best_similarity = 0.0

        for cluster in clusters:
            try:
                centroid = json.loads(cluster['centroid_embedding'])
                sim = _cosine_similarity(embedding, centroid)
                if sim > best_similarity:
                    best_similarity = sim
                    best_match = cluster
            except (json.JSONDecodeError, TypeError):
                continue

        if best_match and best_similarity > 0.5:
            return {
                'cluster_id': best_match['id'],
                'cluster_name': best_match['name'],
                'similarity': round(best_similarity, 3)
            }

        return None

    @staticmethod
    def update_topic_metrics():
        """Background job: compute per-topic quality metrics for the past period."""
        conn = _get_conn()
        clusters = conn.execute('SELECT id FROM topic_clusters WHERE active = 1').fetchall()

        now = datetime.now()
        period_start = (now - timedelta(days=7)).isoformat()
        period_end = now.isoformat()

        for cluster in clusters:
            # Get questions in this cluster with feedback
            rows = conn.execute('''
                SELECT f.confidence_score, f.user_rating
                FROM question_topics qt
                JOIN feedback f ON qt.question = f.question
                WHERE qt.cluster_id = ? AND f.timestamp >= ?
            ''', (cluster['id'], period_start)).fetchall()

            if rows:
                avg_conf = sum(r['confidence_score'] or 0 for r in rows) / len(rows)
                positive = sum(1 for r in rows if r['user_rating'] in ('helpful', 'good', 'correct'))
                negative = sum(1 for r in rows if r['user_rating'] in ('wrong', 'bad', 'partially_wrong'))
                rated = positive + negative
                avg_sat = positive / rated if rated > 0 else 0.5

                conn.execute('''
                    INSERT INTO topic_metrics
                    (cluster_id, period_start, period_end, question_count,
                     avg_confidence, avg_satisfaction, negative_count, positive_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (cluster['id'], period_start, period_end, len(rows),
                      avg_conf, avg_sat, negative, positive))

                # Update cluster aggregate
                neg_rate = negative / rated if rated > 0 else 0
                conn.execute('''
                    UPDATE topic_clusters SET
                        question_count = ?, avg_confidence = ?,
                        avg_satisfaction = ?, negative_rate = ?,
                        last_seen = ?
                    WHERE id = ?
                ''', (len(rows), avg_conf, avg_sat, neg_rate,
                      period_end, cluster['id']))

        conn.commit()
        conn.close()
        log_event('topic_clustering', 'metrics_updated')

    @staticmethod
    def get_topic_dashboard() -> Dict:
        """Get topic intelligence dashboard."""
        conn = _get_conn()
        clusters = conn.execute('''
            SELECT * FROM topic_clusters WHERE active = 1
            ORDER BY question_count DESC
        ''').fetchall()

        # Emerging topics (new in last 7 days with growing volume)
        week_ago = (datetime.now() - timedelta(days=7)).isoformat()
        emerging = conn.execute('''
            SELECT * FROM topic_clusters
            WHERE active = 1 AND first_seen >= ?
            ORDER BY question_count DESC LIMIT 10
        ''', (week_ago,)).fetchall()

        # Problematic topics (high negative rate)
        problematic = conn.execute('''
            SELECT * FROM topic_clusters
            WHERE active = 1 AND negative_rate > 0.3 AND question_count >= 5
            ORDER BY negative_rate DESC LIMIT 10
        ''').fetchall()

        conn.close()

        return {
            'total_clusters': len(clusters),
            'clusters': [dict(c) for c in clusters[:50]],
            'emerging': [dict(e) for e in emerging],
            'problematic': [dict(p) for p in problematic]
        }

    @staticmethod
    def detect_emerging_topics(days: int = 7) -> List[Dict]:
        """Find new or rapidly growing topics."""
        conn = _get_conn()
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        rows = conn.execute('''
            SELECT * FROM topic_clusters
            WHERE active = 1 AND first_seen >= ?
            ORDER BY question_count DESC
        ''', (cutoff,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]
