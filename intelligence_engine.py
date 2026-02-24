"""
Intelligence Engine for Greenside AI
=====================================
8 Subsystems that create self-improving feedback loops:

1. Self-Healing Knowledge Loop — golden answers from recurring failures
2. Answer Versioning & A/B Testing — measure what works
3. Source Quality Intelligence — track which sources lead to good answers
4. Confidence Calibration Engine — calibrate predictions vs reality
5. Automated Regression Detection — catch quality drops
6. Topic Clustering & Trend Intelligence — understand what users ask
7. User Satisfaction Prediction — predict bad answers before users rate
8. Smart Escalation System — classify failures + suggest fixes
"""

import sqlite3
import os
import json
import math
import time
import hashlib
import logging
import threading
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Tuple
from collections import defaultdict

logger = logging.getLogger(__name__)

# Database path — same DB as feedback system
DATA_DIR = os.environ.get('DATA_DIR', 'data' if os.path.exists('data') else '.')
DB_PATH = os.path.join(DATA_DIR, 'greenside_feedback.db')

# ============================================================================
# DATABASE INITIALIZATION
# ============================================================================

def init_intelligence_tables():
    """Initialize all 15 intelligence engine tables."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # --- Subsystem 1: Self-Healing Knowledge Loop ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS golden_answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            category TEXT,
            embedding TEXT,
            source_feedback_id INTEGER,
            created_by TEXT DEFAULT 'admin',
            active BOOLEAN DEFAULT 1,
            times_used INTEGER DEFAULT 0,
            avg_rating_when_used REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # --- Subsystem 2: Answer Versioning & A/B Testing ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS answer_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern TEXT NOT NULL,
            answer_template TEXT NOT NULL,
            strategy TEXT DEFAULT 'default',
            metadata TEXT,
            performance_score REAL DEFAULT 0.0,
            times_served INTEGER DEFAULT 0,
            avg_rating REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ab_tests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            pattern TEXT NOT NULL,
            version_ids TEXT NOT NULL,
            traffic_split TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            total_impressions INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ended_at TIMESTAMP,
            winner_version_id INTEGER
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ab_test_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            test_id INTEGER NOT NULL,
            version_id INTEGER NOT NULL,
            query_id INTEGER,
            user_id TEXT,
            rating TEXT,
            confidence REAL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (test_id) REFERENCES ab_tests(id),
            FOREIGN KEY (version_id) REFERENCES answer_versions(id)
        )
    ''')

    # --- Subsystem 3: Source Quality Intelligence ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS source_reliability (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id TEXT NOT NULL UNIQUE,
            source_title TEXT,
            source_type TEXT,
            trust_score REAL DEFAULT 0.5,
            positive_count INTEGER DEFAULT 0,
            negative_count INTEGER DEFAULT 0,
            total_appearances INTEGER DEFAULT 0,
            avg_confidence_when_used REAL,
            admin_boost REAL DEFAULT 0.0,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # --- Subsystem 4: Confidence Calibration ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS confidence_calibration (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query_id INTEGER,
            predicted_confidence REAL NOT NULL,
            actual_rating TEXT,
            actual_satisfaction REAL,
            topic TEXT,
            category TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # --- Subsystem 5: Regression Detection ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS regression_tests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL,
            expected_answer TEXT NOT NULL,
            category TEXT,
            criteria TEXT,
            priority INTEGER DEFAULT 1,
            active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by TEXT DEFAULT 'admin'
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS regression_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trigger TEXT DEFAULT 'scheduled',
            total_tests INTEGER DEFAULT 0,
            passed INTEGER DEFAULT 0,
            warned INTEGER DEFAULT 0,
            failed INTEGER DEFAULT 0,
            avg_drift_score REAL,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            status TEXT DEFAULT 'running'
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS regression_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            test_id INTEGER NOT NULL,
            actual_answer TEXT,
            confidence REAL,
            drift_score REAL,
            status TEXT,
            issues TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (run_id) REFERENCES regression_runs(id),
            FOREIGN KEY (test_id) REFERENCES regression_tests(id)
        )
    ''')

    # --- Subsystem 6: Topic Clustering ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS topic_clusters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            description TEXT,
            centroid_embedding TEXT,
            question_count INTEGER DEFAULT 0,
            avg_confidence REAL,
            avg_satisfaction REAL,
            negative_rate REAL DEFAULT 0.0,
            trend_direction TEXT DEFAULT 'stable',
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            active BOOLEAN DEFAULT 1
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS question_topics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query_id INTEGER,
            question TEXT NOT NULL,
            cluster_id INTEGER,
            similarity_score REAL,
            embedding TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (cluster_id) REFERENCES topic_clusters(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS topic_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cluster_id INTEGER NOT NULL,
            period_start TIMESTAMP NOT NULL,
            period_end TIMESTAMP NOT NULL,
            question_count INTEGER DEFAULT 0,
            avg_confidence REAL,
            avg_satisfaction REAL,
            negative_count INTEGER DEFAULT 0,
            positive_count INTEGER DEFAULT 0,
            FOREIGN KEY (cluster_id) REFERENCES topic_clusters(id)
        )
    ''')

    # --- Subsystem 7: Satisfaction Prediction ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS satisfaction_predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query_id INTEGER,
            predicted_probability REAL NOT NULL,
            features TEXT,
            actual_rating TEXT,
            was_correct BOOLEAN,
            model_version INTEGER DEFAULT 1,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # --- Subsystem 8: Smart Escalation ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS escalation_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query_id INTEGER,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            failure_mode TEXT,
            failure_details TEXT,
            predicted_satisfaction REAL,
            confidence REAL,
            suggested_fix TEXT,
            similar_approved_ids TEXT,
            priority INTEGER DEFAULT 5,
            status TEXT DEFAULT 'open',
            resolved_by TEXT,
            resolution_action TEXT,
            resolution_notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resolved_at TIMESTAMP
        )
    ''')

    # --- Audit Log ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS intelligence_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subsystem TEXT NOT NULL,
            event_type TEXT NOT NULL,
            details TEXT,
            severity TEXT DEFAULT 'info',
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # --- Subsystem 9: Pipeline Analytics & Cost Intelligence ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pipeline_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query_id INTEGER,
            total_latency_ms REAL,
            step_timings TEXT,
            prompt_tokens INTEGER DEFAULT 0,
            completion_tokens INTEGER DEFAULT 0,
            total_tokens INTEGER DEFAULT 0,
            model TEXT,
            cost_usd REAL DEFAULT 0.0,
            grounding_tokens INTEGER DEFAULT 0,
            grounding_cost_usd REAL DEFAULT 0.0,
            embedding_tokens INTEGER DEFAULT 0,
            embedding_cost_usd REAL DEFAULT 0.0,
            total_cost_usd REAL DEFAULT 0.0,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cost_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            period_type TEXT NOT NULL,
            period_key TEXT NOT NULL,
            model TEXT,
            total_requests INTEGER DEFAULT 0,
            total_prompt_tokens INTEGER DEFAULT 0,
            total_completion_tokens INTEGER DEFAULT 0,
            total_cost_usd REAL DEFAULT 0.0,
            avg_cost_per_request REAL DEFAULT 0.0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(period_type, period_key, model)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cost_budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            budget_type TEXT NOT NULL UNIQUE,
            budget_usd REAL NOT NULL,
            current_spend_usd REAL DEFAULT 0.0,
            alert_threshold_pct REAL DEFAULT 80.0,
            alert_sent BOOLEAN DEFAULT 0,
            period_start TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # --- Subsystem 10: Anomaly Detection ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS anomaly_detections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            metric TEXT NOT NULL,
            detection_method TEXT NOT NULL,
            current_value REAL,
            baseline_mean REAL,
            baseline_std REAL,
            z_score REAL,
            severity TEXT DEFAULT 'info',
            message TEXT,
            acknowledged BOOLEAN DEFAULT 0,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS metric_baselines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            metric TEXT NOT NULL UNIQUE,
            mean REAL,
            std REAL,
            min_val REAL,
            max_val REAL,
            sample_count INTEGER DEFAULT 0,
            last_computed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # --- Subsystem 11: Alert System ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alert_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            metric TEXT NOT NULL,
            condition TEXT NOT NULL,
            threshold REAL NOT NULL,
            channels TEXT DEFAULT '["in_app"]',
            cooldown_minutes INTEGER DEFAULT 60,
            enabled BOOLEAN DEFAULT 1,
            last_fired TIMESTAMP,
            fire_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alert_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_id INTEGER,
            rule_name TEXT,
            metric TEXT,
            current_value REAL,
            threshold REAL,
            channel TEXT,
            message TEXT,
            delivered BOOLEAN DEFAULT 1,
            acknowledged BOOLEAN DEFAULT 0,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (rule_id) REFERENCES alert_rules(id)
        )
    ''')

    # --- Subsystem 12: Remediation & Circuit Breakers ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS remediation_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trigger_type TEXT NOT NULL,
            action_type TEXT NOT NULL,
            target TEXT,
            before_state TEXT,
            after_state TEXT,
            auto BOOLEAN DEFAULT 1,
            success BOOLEAN DEFAULT 1,
            details TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS circuit_breakers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id TEXT NOT NULL UNIQUE,
            state TEXT DEFAULT 'closed',
            failure_count INTEGER DEFAULT 0,
            last_failure TIMESTAMP,
            opened_at TIMESTAMP,
            recovery_at TIMESTAMP,
            total_trips INTEGER DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # --- Subsystem 13: Prompt Versioning ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS prompt_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version INTEGER NOT NULL,
            template_hash TEXT NOT NULL,
            template_text TEXT NOT NULL,
            description TEXT,
            changes TEXT,
            is_active BOOLEAN DEFAULT 0,
            total_queries INTEGER DEFAULT 0,
            avg_confidence REAL,
            avg_satisfaction REAL,
            created_by TEXT DEFAULT 'system',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            activated_at TIMESTAMP,
            deactivated_at TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS prompt_usage_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version_id INTEGER NOT NULL,
            query_id INTEGER,
            confidence REAL,
            satisfaction_rating TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (version_id) REFERENCES prompt_templates(id)
        )
    ''')

    # --- Subsystem 15: Knowledge Gaps ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS knowledge_gaps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT NOT NULL,
            category TEXT,
            gap_type TEXT NOT NULL,
            severity TEXT DEFAULT 'medium',
            avg_confidence REAL,
            avg_source_count REAL,
            question_count INTEGER DEFAULT 0,
            sample_questions TEXT,
            recommended_action TEXT,
            status TEXT DEFAULT 'open',
            resolved_at TIMESTAMP,
            detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS content_freshness (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id TEXT NOT NULL,
            source_title TEXT,
            last_cited TIMESTAMP,
            citation_count INTEGER DEFAULT 0,
            days_since_cited INTEGER DEFAULT 0,
            freshness_score REAL DEFAULT 1.0,
            status TEXT DEFAULT 'fresh',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # --- Subsystem 17: Conversation Intelligence ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conversation_analytics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL,
            turn_count INTEGER DEFAULT 0,
            unique_topics INTEGER DEFAULT 0,
            avg_confidence REAL,
            min_confidence REAL,
            resolution_status TEXT DEFAULT 'unknown',
            frustration_score REAL DEFAULT 0.0,
            frustration_signals TEXT,
            topic_drift_score REAL DEFAULT 0.0,
            total_latency_ms REAL DEFAULT 0.0,
            total_cost_usd REAL DEFAULT 0.0,
            first_message TIMESTAMP,
            last_message TIMESTAMP,
            analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # --- Indexes (original + new) ---
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_golden_category ON golden_answers(category)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_golden_active ON golden_answers(active)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_ab_status ON ab_tests(status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_source_trust ON source_reliability(trust_score)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_source_id ON source_reliability(source_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_calib_topic ON confidence_calibration(topic)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_regression_active ON regression_tests(active)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_cluster_active ON topic_clusters(active)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_qt_cluster ON question_topics(cluster_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_escalation_status ON escalation_queue(status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_escalation_priority ON escalation_queue(priority)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_events_subsystem ON intelligence_events(subsystem)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_events_time ON intelligence_events(timestamp)')
    # New indexes for enterprise subsystems
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_pipeline_query ON pipeline_metrics(query_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_pipeline_time ON pipeline_metrics(timestamp)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_cost_ledger_period ON cost_ledger(period_type, period_key)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_anomaly_metric ON anomaly_detections(metric)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_anomaly_severity ON anomaly_detections(severity)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_anomaly_time ON anomaly_detections(timestamp)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_alert_rule_metric ON alert_rules(metric)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_alert_history_time ON alert_history(timestamp)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_alert_history_rule ON alert_history(rule_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_circuit_source ON circuit_breakers(source_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_circuit_state ON circuit_breakers(state)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_prompt_active ON prompt_templates(is_active)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_prompt_version ON prompt_templates(version)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_knowledge_gap_status ON knowledge_gaps(status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_content_fresh_status ON content_freshness(status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_conv_analytics_cid ON conversation_analytics(conversation_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_remediation_time ON remediation_actions(timestamp)')

    # --- Anthropic-Grade: Feature Flags ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS feature_flags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            flag_name TEXT UNIQUE NOT NULL,
            enabled BOOLEAN DEFAULT 1,
            description TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_by TEXT DEFAULT 'system'
        )
    ''')

    # --- Anthropic-Grade: Data Retention Log ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS retention_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_name TEXT NOT NULL,
            rows_deleted INTEGER DEFAULT 0,
            ttl_days INTEGER,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # --- Anthropic-Grade: Query Moderation Log ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS query_moderation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT NOT NULL,
            score REAL DEFAULT 0,
            patterns_matched TEXT,
            action TEXT DEFAULT 'blocked',
            ip_address TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_feature_flags_name ON feature_flags(flag_name)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_retention_log_time ON retention_log(timestamp)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_query_moderation_time ON query_moderation(timestamp)')

    conn.commit()
    conn.close()
    logger.info("Intelligence engine tables initialized (33 tables)")


def log_event(subsystem: str, event_type: str, details: str = None, severity: str = 'info'):
    """Log an intelligence event for audit trail."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO intelligence_events (subsystem, event_type, details, severity)
            VALUES (?, ?, ?, ?)
        ''', (subsystem, event_type, details, severity))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to log event: {e}")


def _get_conn():
    """Get a database connection with row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ============================================================================
# SUBSYSTEM 1: SELF-HEALING KNOWLEDGE LOOP
# ============================================================================

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


# ============================================================================
# SUBSYSTEM 2: ANSWER VERSIONING & A/B TESTING
# ============================================================================

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


# ============================================================================
# SUBSYSTEM 3: SOURCE QUALITY INTELLIGENCE
# ============================================================================

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

            # Bayesian trust score: (positive + 1) / (total + 2) — Beta(1,1) prior
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


# ============================================================================
# SUBSYSTEM 4: CONFIDENCE CALIBRATION ENGINE
# ============================================================================

class ConfidenceCalibration:
    """
    Tracks predicted confidence vs actual user satisfaction.
    Computes calibration curves. Applies isotonic regression adjustment.
    """

    @staticmethod
    def record_calibration_point(query_id: int, predicted_confidence: float,
                                  actual_rating: str, topic: str = None, category: str = None):
        """Store a predicted vs actual data point."""
        # Convert rating to satisfaction score (0-1)
        satisfaction_map = {
            'helpful': 1.0, 'good': 1.0, 'correct': 1.0,
            'partially_helpful': 0.5, 'ok': 0.5,
            'wrong': 0.0, 'partially_wrong': 0.2, 'bad': 0.0, 'unhelpful': 0.1
        }
        satisfaction = satisfaction_map.get(actual_rating, 0.5)

        conn = _get_conn()
        conn.execute('''
            INSERT INTO confidence_calibration
            (query_id, predicted_confidence, actual_rating, actual_satisfaction, topic, category)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (query_id, predicted_confidence, actual_rating, satisfaction, topic, category))
        conn.commit()
        conn.close()

    @staticmethod
    def compute_calibration_curve(topic: str = None, num_bins: int = 10) -> Dict:
        """
        Compute calibration curve: binned predicted confidence vs actual satisfaction.
        Returns bins with predicted_avg, actual_avg, and count.
        """
        conn = _get_conn()
        if topic:
            rows = conn.execute('''
                SELECT predicted_confidence, actual_satisfaction
                FROM confidence_calibration WHERE topic = ?
                ORDER BY predicted_confidence
            ''', (topic,)).fetchall()
        else:
            rows = conn.execute('''
                SELECT predicted_confidence, actual_satisfaction
                FROM confidence_calibration
                ORDER BY predicted_confidence
            ''').fetchall()
        conn.close()

        if not rows:
            return {'bins': [], 'total_points': 0, 'ece': 0}

        # Create bins
        bin_size = 100.0 / num_bins
        bins = []
        for i in range(num_bins):
            bin_low = i * bin_size
            bin_high = (i + 1) * bin_size
            bin_points = [r for r in rows if bin_low <= r['predicted_confidence'] < bin_high]

            if bin_points:
                pred_avg = sum(r['predicted_confidence'] for r in bin_points) / len(bin_points)
                actual_avg = sum(r['actual_satisfaction'] for r in bin_points) / len(bin_points)
                bins.append({
                    'bin_low': bin_low,
                    'bin_high': bin_high,
                    'predicted_avg': round(pred_avg, 1),
                    'actual_satisfaction': round(actual_avg * 100, 1),  # Scale to 0-100
                    'count': len(bin_points),
                    'gap': round(abs(pred_avg - actual_avg * 100), 1)
                })

        # Expected Calibration Error (ECE)
        total = len(rows)
        ece = sum(b['count'] / total * b['gap'] for b in bins) if total > 0 else 0

        return {
            'bins': bins,
            'total_points': total,
            'ece': round(ece, 2),
            'topic': topic
        }

    @staticmethod
    def get_calibration_adjustment(raw_confidence: float, topic: str = None) -> float:
        """
        Apply isotonic regression to adjust raw confidence score.
        Uses historical calibration data to correct over/under-confidence.
        """
        conn = _get_conn()
        if topic:
            rows = conn.execute('''
                SELECT predicted_confidence, actual_satisfaction
                FROM confidence_calibration WHERE topic = ?
                ORDER BY predicted_confidence
            ''', (topic,)).fetchall()
        else:
            rows = conn.execute('''
                SELECT predicted_confidence, actual_satisfaction
                FROM confidence_calibration
                ORDER BY predicted_confidence
            ''').fetchall()
        conn.close()

        if len(rows) < 20:
            return raw_confidence  # Not enough data, return unadjusted

        # Simple isotonic regression: pool-adjacent-violators
        predictions = [r['predicted_confidence'] for r in rows]
        actuals = [r['actual_satisfaction'] * 100 for r in rows]

        isotonic = _isotonic_regression(predictions, actuals)

        # Find the closest calibration point
        closest_idx = min(range(len(predictions)),
                         key=lambda i: abs(predictions[i] - raw_confidence))

        adjusted = isotonic[closest_idx]
        return max(25.0, min(100.0, adjusted))

    @staticmethod
    def get_calibration_report() -> Dict:
        """Get full calibration report for admin dashboard."""
        conn = _get_conn()

        # Overall
        overall = ConfidenceCalibration.compute_calibration_curve()

        # Per topic
        topics = conn.execute('''
            SELECT DISTINCT topic FROM confidence_calibration
            WHERE topic IS NOT NULL
        ''').fetchall()
        conn.close()

        per_topic = {}
        for t in topics:
            per_topic[t['topic']] = ConfidenceCalibration.compute_calibration_curve(topic=t['topic'])

        # Find most miscalibrated topics
        miscalibrated = sorted(
            [(topic, data['ece']) for topic, data in per_topic.items() if data['total_points'] >= 10],
            key=lambda x: x[1], reverse=True
        )

        return {
            'overall': overall,
            'per_topic': per_topic,
            'most_miscalibrated': miscalibrated[:10],
            'total_data_points': overall['total_points']
        }


# ============================================================================
# SUBSYSTEM 5: AUTOMATED REGRESSION DETECTION
# ============================================================================

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


# ============================================================================
# SUBSYSTEM 6: TOPIC CLUSTERING & TREND INTELLIGENCE
# ============================================================================

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


# ============================================================================
# SUBSYSTEM 7: USER SATISFACTION PREDICTION
# ============================================================================

class SatisfactionPredictor:
    """
    Pure-Python logistic regression to predict satisfaction before users rate.
    No sklearn dependency — implements gradient descent from scratch.
    """

    # Model weights stored in memory (retrained periodically)
    _weights = None
    _bias = 0.0
    _feature_means = None
    _feature_stds = None
    _model_version = 0

    @staticmethod
    def extract_features(confidence: float, source_count: int, response_length: int,
                         grounding_score: float = 1.0, hallucination_penalties: int = 0,
                         topic_difficulty: float = 0.5, hour_of_day: int = 12) -> List[float]:
        """Extract feature vector from answer data."""
        return [
            confidence / 100.0,            # Normalized confidence
            min(source_count / 10.0, 1.0),  # Normalized source count
            min(response_length / 1000.0, 1.0),  # Normalized length
            grounding_score,                # 0-1
            hallucination_penalties / 5.0,  # Normalized penalties
            topic_difficulty,               # 0-1
            math.sin(2 * math.pi * hour_of_day / 24),  # Cyclical time encoding
            math.cos(2 * math.pi * hour_of_day / 24),
        ]

    @staticmethod
    def train_satisfaction_model(min_samples: int = 50) -> Dict:
        """
        Train logistic regression on historical feedback data.
        Pure Python implementation — no external ML libraries.
        """
        conn = _get_conn()
        rows = conn.execute('''
            SELECT f.confidence_score, f.sources, f.ai_answer, f.user_rating, f.timestamp
            FROM feedback f
            WHERE f.user_rating != 'unrated' AND f.confidence_score IS NOT NULL
            ORDER BY f.timestamp DESC LIMIT 2000
        ''').fetchall()
        conn.close()

        if len(rows) < min_samples:
            return {'success': False, 'reason': f'Need {min_samples} samples, have {len(rows)}'}

        # Build feature matrix and labels
        X = []
        y = []
        for row in rows:
            sources = json.loads(row['sources']) if row['sources'] else []
            hour = datetime.fromisoformat(row['timestamp']).hour if row['timestamp'] else 12
            features = SatisfactionPredictor.extract_features(
                confidence=row['confidence_score'] or 50,
                source_count=len(sources),
                response_length=len(row['ai_answer'] or ''),
                hour_of_day=hour
            )
            X.append(features)
            label = 1.0 if row['user_rating'] in ('helpful', 'good', 'correct') else 0.0
            y.append(label)

        # Normalize features
        n_features = len(X[0])
        means = [sum(x[i] for x in X) / len(X) for i in range(n_features)]
        stds = [max(0.001, math.sqrt(sum((x[i] - means[i])**2 for x in X) / len(X)))
                for i in range(n_features)]

        X_norm = [[(x[i] - means[i]) / stds[i] for i in range(n_features)] for x in X]

        # Logistic regression via gradient descent
        weights = [0.0] * n_features
        bias = 0.0
        lr = 0.1
        epochs = 100

        for epoch in range(epochs):
            grad_w = [0.0] * n_features
            grad_b = 0.0

            for x, label in zip(X_norm, y):
                z = sum(w * xi for w, xi in zip(weights, x)) + bias
                pred = _sigmoid(z)
                error = pred - label

                for j in range(n_features):
                    grad_w[j] += error * x[j]
                grad_b += error

            # Update
            for j in range(n_features):
                weights[j] -= lr * grad_w[j] / len(X)
            bias -= lr * grad_b / len(X)

        # Store model
        SatisfactionPredictor._weights = weights
        SatisfactionPredictor._bias = bias
        SatisfactionPredictor._feature_means = means
        SatisfactionPredictor._feature_stds = stds
        SatisfactionPredictor._model_version += 1

        # Compute accuracy
        correct = 0
        for x, label in zip(X_norm, y):
            z = sum(w * xi for w, xi in zip(weights, x)) + bias
            pred = 1.0 if _sigmoid(z) > 0.5 else 0.0
            if pred == label:
                correct += 1

        accuracy = correct / len(X)
        log_event('satisfaction_prediction', 'model_trained',
                  json.dumps({'accuracy': round(accuracy, 3), 'samples': len(X),
                             'version': SatisfactionPredictor._model_version}))

        return {
            'success': True,
            'accuracy': round(accuracy, 3),
            'samples': len(X),
            'version': SatisfactionPredictor._model_version
        }

    @staticmethod
    def predict_satisfaction(features: List[float]) -> float:
        """Predict probability of positive satisfaction (0-1)."""
        if SatisfactionPredictor._weights is None:
            return 0.5  # No model trained yet

        # Normalize
        means = SatisfactionPredictor._feature_means
        stds = SatisfactionPredictor._feature_stds
        x_norm = [(f - m) / s for f, m, s in zip(features, means, stds)]

        z = sum(w * xi for w, xi in zip(SatisfactionPredictor._weights, x_norm))
        z += SatisfactionPredictor._bias
        return _sigmoid(z)

    @staticmethod
    def record_prediction(query_id: int, probability: float, features: List[float],
                          actual_rating: str = None):
        """Store a prediction for later evaluation."""
        was_correct = None
        if actual_rating:
            predicted_positive = probability > 0.5
            actual_positive = actual_rating in ('helpful', 'good', 'correct')
            was_correct = predicted_positive == actual_positive

        conn = _get_conn()
        conn.execute('''
            INSERT INTO satisfaction_predictions
            (query_id, predicted_probability, features, actual_rating, was_correct, model_version)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (query_id, probability, json.dumps(features), actual_rating, was_correct,
              SatisfactionPredictor._model_version))
        conn.commit()
        conn.close()

    @staticmethod
    def get_prediction_accuracy() -> Dict:
        """Get prediction model accuracy stats."""
        conn = _get_conn()
        rows = conn.execute('''
            SELECT was_correct, model_version FROM satisfaction_predictions
            WHERE was_correct IS NOT NULL
            ORDER BY timestamp DESC LIMIT 500
        ''').fetchall()
        conn.close()

        if not rows:
            return {'accuracy': 0, 'total': 0}

        correct = sum(1 for r in rows if r['was_correct'])
        return {
            'accuracy': round(correct / len(rows), 3),
            'total': len(rows),
            'correct': correct,
            'model_version': SatisfactionPredictor._model_version
        }


# ============================================================================
# SUBSYSTEM 8: SMART ESCALATION SYSTEM
# ============================================================================

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


# ============================================================================
# SUBSYSTEM 9: PIPELINE ANALYTICS & COST INTELLIGENCE
# ============================================================================

class PipelineAnalytics:
    """Track per-request latency, token usage, and cost."""

    # Cost rates per token (imported from config at runtime)
    _cost_rates = None

    @staticmethod
    def _get_cost_rates():
        if PipelineAnalytics._cost_rates is None:
            try:
                from config import Config
                PipelineAnalytics._cost_rates = Config.COST_RATES
            except Exception:
                PipelineAnalytics._cost_rates = {
                    'gpt-4o': {'prompt': 2.50 / 1_000_000, 'completion': 10.00 / 1_000_000},
                    'gpt-4o-mini': {'prompt': 0.150 / 1_000_000, 'completion': 0.600 / 1_000_000},
                    'text-embedding-3-small': {'prompt': 0.020 / 1_000_000, 'completion': 0.0},
                }
        return PipelineAnalytics._cost_rates

    @staticmethod
    def calculate_cost(prompt_tokens: int, completion_tokens: int, model: str) -> float:
        """Calculate USD cost for a given token usage."""
        rates = PipelineAnalytics._get_cost_rates()
        model_rates = rates.get(model, rates.get('gpt-4o', {}))
        cost = (prompt_tokens * model_rates.get('prompt', 0) +
                completion_tokens * model_rates.get('completion', 0))
        return round(cost, 8)

    @staticmethod
    def record_request(query_id: int, timings: Dict = None, token_usage: Dict = None,
                       grounding_tokens: int = 0, embedding_tokens: int = 0):
        """Record a complete pipeline execution with timing and cost data."""
        try:
            conn = _get_conn()
            model = (token_usage or {}).get('model', 'gpt-4o')
            prompt_tokens = (token_usage or {}).get('prompt_tokens', 0)
            completion_tokens = (token_usage or {}).get('completion_tokens', 0)
            total_tokens = prompt_tokens + completion_tokens

            # Calculate costs for each component
            main_cost = PipelineAnalytics.calculate_cost(prompt_tokens, completion_tokens, model)
            grounding_cost = PipelineAnalytics.calculate_cost(grounding_tokens, 0, 'gpt-4o-mini')
            embedding_cost = PipelineAnalytics.calculate_cost(embedding_tokens, 0, 'text-embedding-3-small')
            total_cost = main_cost + grounding_cost + embedding_cost

            total_latency_ms = (timings or {}).get('10_total', 0) * 1000

            conn.execute('''
                INSERT INTO pipeline_metrics
                (query_id, total_latency_ms, step_timings, prompt_tokens, completion_tokens,
                 total_tokens, model, cost_usd, grounding_tokens, grounding_cost_usd,
                 embedding_tokens, embedding_cost_usd, total_cost_usd)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (query_id, total_latency_ms, json.dumps(timings or {}),
                  prompt_tokens, completion_tokens, total_tokens, model, main_cost,
                  grounding_tokens, grounding_cost, embedding_tokens, embedding_cost, total_cost))

            # Update cost ledger (daily + monthly)
            now = datetime.now()
            daily_key = now.strftime('%Y-%m-%d')
            monthly_key = now.strftime('%Y-%m')

            for period_type, period_key in [('daily', daily_key), ('monthly', monthly_key)]:
                conn.execute('''
                    INSERT INTO cost_ledger (period_type, period_key, model, total_requests,
                        total_prompt_tokens, total_completion_tokens, total_cost_usd)
                    VALUES (?, ?, ?, 1, ?, ?, ?)
                    ON CONFLICT(period_type, period_key, model) DO UPDATE SET
                        total_requests = total_requests + 1,
                        total_prompt_tokens = total_prompt_tokens + ?,
                        total_completion_tokens = total_completion_tokens + ?,
                        total_cost_usd = total_cost_usd + ?,
                        avg_cost_per_request = (total_cost_usd + ?) / (total_requests + 1),
                        updated_at = CURRENT_TIMESTAMP
                ''', (period_type, period_key, model, prompt_tokens, completion_tokens, total_cost,
                      prompt_tokens, completion_tokens, total_cost, total_cost))

            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Pipeline metrics recording failed: {e}")

    @staticmethod
    def get_latency_percentiles(period: str = '24h') -> Dict:
        """Get p50, p95, p99 latency for a time period."""
        try:
            conn = _get_conn()
            hours = int(period.replace('h', '').replace('d', '')) * (24 if 'd' in period else 1)
            cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()

            rows = conn.execute('''
                SELECT total_latency_ms FROM pipeline_metrics
                WHERE timestamp > ? ORDER BY total_latency_ms
            ''', (cutoff,)).fetchall()
            conn.close()

            if not rows:
                return {'p50': 0, 'p95': 0, 'p99': 0, 'count': 0, 'mean': 0}

            latencies = [r['total_latency_ms'] for r in rows]
            n = len(latencies)
            return {
                'p50': latencies[n // 2],
                'p95': latencies[int(n * 0.95)] if n > 1 else latencies[0],
                'p99': latencies[int(n * 0.99)] if n > 1 else latencies[0],
                'count': n,
                'mean': round(sum(latencies) / n, 1),
                'min': latencies[0],
                'max': latencies[-1]
            }
        except Exception as e:
            logger.error(f"Latency percentiles error: {e}")
            return {'p50': 0, 'p95': 0, 'p99': 0, 'count': 0, 'mean': 0}

    @staticmethod
    def get_cost_summary(period: str = '24h') -> Dict:
        """Get cost breakdown by model and step for a time period."""
        try:
            conn = _get_conn()
            hours = int(period.replace('h', '').replace('d', '')) * (24 if 'd' in period else 1)
            cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()

            # Per-model cost
            by_model = conn.execute('''
                SELECT model, COUNT(*) as requests,
                       SUM(cost_usd) as main_cost,
                       SUM(total_cost_usd) as total_cost,
                       SUM(prompt_tokens) as prompt_tokens,
                       SUM(completion_tokens) as completion_tokens
                FROM pipeline_metrics WHERE timestamp > ?
                GROUP BY model
            ''', (cutoff,)).fetchall()

            # Total cost
            total = conn.execute('''
                SELECT COUNT(*) as requests,
                       SUM(total_cost_usd) as total_cost,
                       AVG(total_cost_usd) as avg_cost,
                       SUM(grounding_cost_usd) as grounding_cost,
                       SUM(embedding_cost_usd) as embedding_cost
                FROM pipeline_metrics WHERE timestamp > ?
            ''', (cutoff,)).fetchone()

            # Cost by hour trend
            hourly = conn.execute('''
                SELECT strftime('%Y-%m-%d %H:00', timestamp) as hour,
                       SUM(total_cost_usd) as cost, COUNT(*) as requests
                FROM pipeline_metrics WHERE timestamp > ?
                GROUP BY hour ORDER BY hour
            ''', (cutoff,)).fetchall()

            conn.close()

            return {
                'period': period,
                'total_requests': total['requests'] or 0,
                'total_cost_usd': round(total['total_cost'] or 0, 6),
                'avg_cost_per_request': round(total['avg_cost'] or 0, 6),
                'grounding_cost_usd': round(total['grounding_cost'] or 0, 6),
                'embedding_cost_usd': round(total['embedding_cost'] or 0, 6),
                'by_model': [dict(r) for r in by_model],
                'hourly_trend': [dict(r) for r in hourly]
            }
        except Exception as e:
            logger.error(f"Cost summary error: {e}")
            return {'error': str(e)}

    @staticmethod
    def get_throughput(period: str = '24h') -> Dict:
        """Get requests per hour trend."""
        try:
            conn = _get_conn()
            hours = int(period.replace('h', '').replace('d', '')) * (24 if 'd' in period else 1)
            cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()

            hourly = conn.execute('''
                SELECT strftime('%Y-%m-%d %H:00', timestamp) as hour,
                       COUNT(*) as requests,
                       AVG(total_latency_ms) as avg_latency
                FROM pipeline_metrics WHERE timestamp > ?
                GROUP BY hour ORDER BY hour
            ''', (cutoff,)).fetchall()

            total = conn.execute('''
                SELECT COUNT(*) as total FROM pipeline_metrics WHERE timestamp > ?
            ''', (cutoff,)).fetchone()

            conn.close()

            hours_elapsed = max(hours, 1)
            return {
                'period': period,
                'total_requests': total['total'] or 0,
                'avg_requests_per_hour': round((total['total'] or 0) / hours_elapsed, 2),
                'hourly_trend': [dict(r) for r in hourly]
            }
        except Exception as e:
            logger.error(f"Throughput error: {e}")
            return {'error': str(e)}

    @staticmethod
    def get_step_breakdown(period: str = '24h') -> Dict:
        """Get average time per pipeline step."""
        try:
            conn = _get_conn()
            hours = int(period.replace('h', '').replace('d', '')) * (24 if 'd' in period else 1)
            cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()

            rows = conn.execute('''
                SELECT step_timings FROM pipeline_metrics
                WHERE timestamp > ? AND step_timings IS NOT NULL
            ''', (cutoff,)).fetchall()
            conn.close()

            if not rows:
                return {'steps': {}, 'count': 0}

            step_sums = defaultdict(float)
            count = 0
            for row in rows:
                try:
                    timings = json.loads(row['step_timings'])
                    prev = 0
                    for key in sorted(timings.keys()):
                        delta = timings[key] - prev
                        step_sums[key] += delta * 1000  # convert to ms
                        prev = timings[key]
                    count += 1
                except (json.JSONDecodeError, TypeError):
                    continue

            steps = {k: round(v / max(count, 1), 1) for k, v in step_sums.items()}
            return {'steps': steps, 'count': count}
        except Exception as e:
            logger.error(f"Step breakdown error: {e}")
            return {'steps': {}, 'count': 0}

    @staticmethod
    def compute_hourly_aggregates():
        """Compute hourly aggregate metrics for anomaly detection baselines."""
        try:
            conn = _get_conn()
            cutoff = (datetime.now() - timedelta(hours=1)).isoformat()

            row = conn.execute('''
                SELECT COUNT(*) as count,
                       AVG(total_latency_ms) as avg_latency,
                       AVG(total_cost_usd) as avg_cost,
                       SUM(total_cost_usd) as total_cost
                FROM pipeline_metrics WHERE timestamp > ?
            ''', (cutoff,)).fetchone()

            conn.close()

            if row and row['count'] > 0:
                # Store baseline data points for anomaly detector
                AnomalyDetector.record_metric('hourly_latency_avg', row['avg_latency'] or 0)
                AnomalyDetector.record_metric('hourly_cost_total', row['total_cost'] or 0)
                AnomalyDetector.record_metric('hourly_request_count', row['count'])

            log_event('pipeline_analytics', 'hourly_aggregates_computed')
        except Exception as e:
            logger.error(f"Hourly aggregates error: {e}")

    @staticmethod
    def check_budget() -> Dict:
        """
        Check cost budget utilization. Returns action recommendation.
        Returns: {'ok': bool, 'daily_pct': float, 'monthly_pct': float,
                  'action': str, 'daily_spend': float, 'monthly_spend': float}
        """
        if not FeatureFlags.is_enabled('cost_enforcement'):
            return {'ok': True, 'action': 'none', 'daily_pct': 0, 'monthly_pct': 0}

        try:
            from config import Config
            conn = _get_conn()
            now = datetime.now()

            daily_key = now.strftime('%Y-%m-%d')
            monthly_key = now.strftime('%Y-%m')

            daily_row = conn.execute('''
                SELECT SUM(total_cost_usd) as total FROM cost_ledger
                WHERE period_type = 'daily' AND period_key = ?
            ''', (daily_key,)).fetchone()

            monthly_row = conn.execute('''
                SELECT SUM(total_cost_usd) as total FROM cost_ledger
                WHERE period_type = 'monthly' AND period_key = ?
            ''', (monthly_key,)).fetchone()
            conn.close()

            daily_spend = (daily_row['total'] or 0) if daily_row else 0
            monthly_spend = (monthly_row['total'] or 0) if monthly_row else 0

            daily_budget = Config.COST_BUDGET_DAILY
            monthly_budget = Config.COST_BUDGET_MONTHLY

            daily_pct = (daily_spend / daily_budget * 100) if daily_budget > 0 else 0
            monthly_pct = (monthly_spend / monthly_budget * 100) if monthly_budget > 0 else 0

            if daily_pct >= 100 or monthly_pct >= 100:
                action = 'budget_exceeded'
            elif daily_pct >= 80 or monthly_pct >= 80:
                action = 'fallback_model'
            else:
                action = 'none'

            return {
                'ok': action == 'none',
                'daily_pct': round(daily_pct, 1),
                'monthly_pct': round(monthly_pct, 1),
                'daily_spend': round(daily_spend, 4),
                'monthly_spend': round(monthly_spend, 4),
                'daily_budget': daily_budget,
                'monthly_budget': monthly_budget,
                'action': action
            }
        except Exception as e:
            logger.error(f"Budget check error: {e}")
            return {'ok': True, 'action': 'none', 'daily_pct': 0, 'monthly_pct': 0, 'error': str(e)}


# ============================================================================
# SUBSYSTEM 10: ANOMALY DETECTION ENGINE
# ============================================================================

class AnomalyDetector:
    """Detect anomalies in system metrics using z-score and CUSUM methods."""

    # In-memory metric history for CUSUM (lightweight)
    _metric_history = defaultdict(list)
    _max_history = 168  # 7 days of hourly points

    @staticmethod
    def record_metric(metric: str, value: float):
        """Record a metric data point for anomaly detection."""
        AnomalyDetector._metric_history[metric].append({
            'value': value, 'timestamp': time.time()
        })
        # Trim to max history
        if len(AnomalyDetector._metric_history[metric]) > AnomalyDetector._max_history:
            AnomalyDetector._metric_history[metric] = \
                AnomalyDetector._metric_history[metric][-AnomalyDetector._max_history:]

    @staticmethod
    def compute_baselines():
        """Compute or update baselines for all tracked metrics."""
        try:
            conn = _get_conn()
            cutoff = (datetime.now() - timedelta(days=7)).isoformat()

            # Latency baseline
            lat = conn.execute('''
                SELECT AVG(total_latency_ms) as mean,
                       AVG(total_latency_ms * total_latency_ms) as mean_sq,
                       MIN(total_latency_ms) as min_val,
                       MAX(total_latency_ms) as max_val,
                       COUNT(*) as n
                FROM pipeline_metrics WHERE timestamp > ?
            ''', (cutoff,)).fetchone()

            if lat and lat['n'] > 10:
                mean = lat['mean']
                std = math.sqrt(max(0, lat['mean_sq'] - mean * mean))
                conn.execute('''
                    INSERT INTO metric_baselines (metric, mean, std, min_val, max_val, sample_count)
                    VALUES ('latency_ms', ?, ?, ?, ?, ?)
                    ON CONFLICT(metric) DO UPDATE SET
                        mean=?, std=?, min_val=?, max_val=?, sample_count=?,
                        last_computed=CURRENT_TIMESTAMP
                ''', (mean, std, lat['min_val'], lat['max_val'], lat['n'],
                      mean, std, lat['min_val'], lat['max_val'], lat['n']))

            # Cost baseline (per request)
            cost = conn.execute('''
                SELECT AVG(total_cost_usd) as mean,
                       AVG(total_cost_usd * total_cost_usd) as mean_sq,
                       MIN(total_cost_usd) as min_val,
                       MAX(total_cost_usd) as max_val,
                       COUNT(*) as n
                FROM pipeline_metrics WHERE timestamp > ?
            ''', (cutoff,)).fetchone()

            if cost and cost['n'] > 10:
                mean = cost['mean']
                std = math.sqrt(max(0, cost['mean_sq'] - mean * mean))
                conn.execute('''
                    INSERT INTO metric_baselines (metric, mean, std, min_val, max_val, sample_count)
                    VALUES ('cost_per_request', ?, ?, ?, ?, ?)
                    ON CONFLICT(metric) DO UPDATE SET
                        mean=?, std=?, min_val=?, max_val=?, sample_count=?,
                        last_computed=CURRENT_TIMESTAMP
                ''', (mean, std, cost['min_val'], cost['max_val'], cost['n'],
                      mean, std, cost['min_val'], cost['max_val'], cost['n']))

            # Confidence baseline
            conf = conn.execute('''
                SELECT AVG(predicted_confidence) as mean,
                       AVG(predicted_confidence * predicted_confidence) as mean_sq,
                       COUNT(*) as n
                FROM confidence_calibration WHERE timestamp > ?
            ''', (cutoff,)).fetchone()

            if conf and conf['n'] > 10:
                mean = conf['mean']
                std = math.sqrt(max(0, conf['mean_sq'] - mean * mean))
                conn.execute('''
                    INSERT INTO metric_baselines (metric, mean, std, min_val, max_val, sample_count)
                    VALUES ('confidence', ?, ?, 0, 100, ?)
                    ON CONFLICT(metric) DO UPDATE SET
                        mean=?, std=?, sample_count=?, last_computed=CURRENT_TIMESTAMP
                ''', (mean, std, conf['n'], mean, std, conf['n']))

            conn.commit()
            conn.close()
            log_event('anomaly_detector', 'baselines_computed')
        except Exception as e:
            logger.error(f"Baseline computation error: {e}")

    @staticmethod
    def check_zscore(metric: str, value: float) -> Optional[Dict]:
        """Check if a metric value is anomalous using z-score (>2.5 sigma)."""
        try:
            conn = _get_conn()
            baseline = conn.execute(
                'SELECT mean, std, sample_count FROM metric_baselines WHERE metric = ?',
                (metric,)
            ).fetchone()
            conn.close()

            if not baseline or baseline['sample_count'] < 10 or baseline['std'] < 0.001:
                return None

            z = abs(value - baseline['mean']) / baseline['std']
            if z > 2.5:
                severity = 'critical' if z > 4.0 else 'warning' if z > 3.0 else 'info'
                return {
                    'metric': metric,
                    'method': 'zscore',
                    'current_value': value,
                    'baseline_mean': baseline['mean'],
                    'baseline_std': baseline['std'],
                    'z_score': round(z, 2),
                    'severity': severity,
                    'message': f"{metric} is {z:.1f} sigma from baseline ({value:.2f} vs {baseline['mean']:.2f})"
                }
            return None
        except Exception as e:
            logger.error(f"Z-score check error: {e}")
            return None

    @staticmethod
    def check_cusum(metric: str, sensitivity: float = 1.0) -> Optional[Dict]:
        """CUSUM change-point detection for gradual drift."""
        history = AnomalyDetector._metric_history.get(metric, [])
        if len(history) < 20:
            return None

        values = [h['value'] for h in history]
        n = len(values)
        mean = sum(values[:n // 2]) / (n // 2)  # baseline from first half
        std = math.sqrt(sum((v - mean) ** 2 for v in values[:n // 2]) / (n // 2))
        if std < 0.001:
            return None

        # CUSUM statistics
        slack = sensitivity * std
        cusum_pos = 0
        cusum_neg = 0
        threshold = 5 * std  # detect after 5 sigma cumulative shift

        for v in values[n // 2:]:
            cusum_pos = max(0, cusum_pos + (v - mean) - slack)
            cusum_neg = max(0, cusum_neg + (mean - v) - slack)

            if cusum_pos > threshold or cusum_neg > threshold:
                direction = 'increase' if cusum_pos > threshold else 'decrease'
                recent_mean = sum(values[-5:]) / 5
                severity = 'warning'
                if abs(recent_mean - mean) > 3 * std:
                    severity = 'critical'

                return {
                    'metric': metric,
                    'method': 'cusum',
                    'current_value': values[-1],
                    'baseline_mean': round(mean, 4),
                    'baseline_std': round(std, 4),
                    'z_score': round((recent_mean - mean) / std, 2),
                    'severity': severity,
                    'message': f"CUSUM detected gradual {direction} in {metric}: "
                               f"recent mean {recent_mean:.2f} vs baseline {mean:.2f}"
                }
        return None

    @staticmethod
    def check_all() -> List[Dict]:
        """Run all anomaly checks on key metrics. Called by scheduler."""
        detections = []
        try:
            conn = _get_conn()
            cutoff = (datetime.now() - timedelta(hours=1)).isoformat()

            # Check recent latency
            lat = conn.execute('''
                SELECT AVG(total_latency_ms) as avg_lat
                FROM pipeline_metrics WHERE timestamp > ?
            ''', (cutoff,)).fetchone()

            if lat and lat['avg_lat']:
                result = AnomalyDetector.check_zscore('latency_ms', lat['avg_lat'])
                if result:
                    detections.append(result)

            # Check recent cost
            cost = conn.execute('''
                SELECT SUM(total_cost_usd) as total_cost
                FROM pipeline_metrics WHERE timestamp > ?
            ''', (cutoff,)).fetchone()

            if cost and cost['total_cost']:
                AnomalyDetector.record_metric('hourly_cost', cost['total_cost'])

            # Check confidence trend
            conf = conn.execute('''
                SELECT AVG(predicted_confidence) as avg_conf
                FROM confidence_calibration WHERE timestamp > ?
            ''', (cutoff,)).fetchone()

            if conf and conf['avg_conf']:
                result = AnomalyDetector.check_zscore('confidence', conf['avg_conf'])
                if result:
                    detections.append(result)

            conn.close()

            # CUSUM checks on accumulated history
            for metric in ['hourly_cost', 'hourly_latency_avg', 'hourly_request_count']:
                result = AnomalyDetector.check_cusum(metric)
                if result:
                    detections.append(result)

            # Store detections
            if detections:
                conn = _get_conn()
                for d in detections:
                    conn.execute('''
                        INSERT INTO anomaly_detections
                        (metric, detection_method, current_value, baseline_mean, baseline_std,
                         z_score, severity, message)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (d['metric'], d['method'], d['current_value'],
                          d.get('baseline_mean'), d.get('baseline_std'),
                          d.get('z_score'), d['severity'], d['message']))
                conn.commit()
                conn.close()
                log_event('anomaly_detector', 'anomalies_detected',
                          json.dumps({'count': len(detections)}), 'warning')

        except Exception as e:
            logger.error(f"Anomaly check_all error: {e}")

        return detections

    @staticmethod
    def get_recent_anomalies(limit: int = 50) -> List[Dict]:
        """Get recent anomaly detections."""
        try:
            conn = _get_conn()
            rows = conn.execute('''
                SELECT * FROM anomaly_detections
                ORDER BY timestamp DESC LIMIT ?
            ''', (limit,)).fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"Get anomalies error: {e}")
            return []


# ============================================================================
# SUBSYSTEM 11: MULTI-CHANNEL ALERT SYSTEM
# ============================================================================

class AlertEngine:
    """Configurable alert rules with multi-channel dispatch."""

    @staticmethod
    def init_default_rules():
        """Create default alert rules if none exist."""
        try:
            conn = _get_conn()
            existing = conn.execute('SELECT COUNT(*) FROM alert_rules').fetchone()[0]
            if existing > 0:
                conn.close()
                return

            defaults = [
                ('Latency Spike', 'latency_p95', 'gt', 10000, '["in_app"]', 30),
                ('Cost Overrun (Hourly)', 'hourly_cost', 'gt', 1.0, '["in_app"]', 60),
                ('Confidence Drop', 'avg_confidence', 'lt', 50, '["in_app"]', 60),
                ('Error Rate Spike', 'error_rate', 'gt', 0.1, '["in_app"]', 15),
                ('Low Satisfaction', 'satisfaction_rate', 'lt', 0.5, '["in_app"]', 120),
            ]
            for name, metric, condition, threshold, channels, cooldown in defaults:
                conn.execute('''
                    INSERT INTO alert_rules (name, metric, condition, threshold, channels, cooldown_minutes)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (name, metric, condition, threshold, channels, cooldown))

            conn.commit()
            conn.close()
            log_event('alert_engine', 'default_rules_created')
        except Exception as e:
            logger.error(f"Init default rules error: {e}")

    @staticmethod
    def create_rule(name: str, metric: str, condition: str, threshold: float,
                    channels: List[str] = None, cooldown_minutes: int = 60) -> int:
        """Create a new alert rule."""
        try:
            conn = _get_conn()
            cursor = conn.execute('''
                INSERT INTO alert_rules (name, metric, condition, threshold, channels, cooldown_minutes)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (name, metric, condition, threshold,
                  json.dumps(channels or ['in_app']), cooldown_minutes))
            rule_id = cursor.lastrowid
            conn.commit()
            conn.close()
            log_event('alert_engine', 'rule_created', json.dumps({'id': rule_id, 'name': name}))
            return rule_id
        except Exception as e:
            logger.error(f"Create rule error: {e}")
            return 0

    @staticmethod
    def evaluate_rules() -> List[Dict]:
        """Evaluate all active rules against current metrics."""
        fired = []
        try:
            conn = _get_conn()
            rules = conn.execute(
                'SELECT * FROM alert_rules WHERE enabled = 1'
            ).fetchall()

            now = datetime.now()
            metrics = AlertEngine._collect_current_metrics(conn)

            for rule in rules:
                rule = dict(rule)
                metric_val = metrics.get(rule['metric'])
                if metric_val is None:
                    continue

                # Check cooldown
                if rule['last_fired']:
                    last = datetime.fromisoformat(rule['last_fired'])
                    if (now - last).total_seconds() < rule['cooldown_minutes'] * 60:
                        continue

                # Evaluate condition
                triggered = False
                if rule['condition'] == 'gt' and metric_val > rule['threshold']:
                    triggered = True
                elif rule['condition'] == 'lt' and metric_val < rule['threshold']:
                    triggered = True
                elif rule['condition'] == 'eq' and abs(metric_val - rule['threshold']) < 0.001:
                    triggered = True

                if triggered:
                    message = (f"Alert: {rule['name']} — {rule['metric']} is "
                               f"{metric_val:.4f} (threshold: {rule['condition']} {rule['threshold']})")

                    channels = json.loads(rule['channels'])
                    for channel in channels:
                        AlertEngine._dispatch(rule['id'], rule['name'], rule['metric'],
                                              metric_val, rule['threshold'], channel, message)

                    conn.execute('''
                        UPDATE alert_rules SET last_fired = ?, fire_count = fire_count + 1
                        WHERE id = ?
                    ''', (now.isoformat(), rule['id']))

                    fired.append({
                        'rule_id': rule['id'],
                        'rule_name': rule['name'],
                        'metric': rule['metric'],
                        'value': metric_val,
                        'threshold': rule['threshold'],
                        'channels': channels
                    })

            conn.commit()
            conn.close()

            if fired:
                log_event('alert_engine', 'rules_fired',
                          json.dumps({'count': len(fired)}), 'warning')

        except Exception as e:
            logger.error(f"Evaluate rules error: {e}")

        return fired

    @staticmethod
    def _collect_current_metrics(conn) -> Dict[str, float]:
        """Collect current metric values for rule evaluation."""
        metrics = {}
        cutoff = (datetime.now() - timedelta(hours=1)).isoformat()

        try:
            # Latency p95
            lats = conn.execute('''
                SELECT total_latency_ms FROM pipeline_metrics
                WHERE timestamp > ? ORDER BY total_latency_ms
            ''', (cutoff,)).fetchall()
            if lats:
                n = len(lats)
                metrics['latency_p95'] = lats[int(n * 0.95)]['total_latency_ms'] if n > 1 else lats[0]['total_latency_ms']
                metrics['latency_avg'] = sum(r['total_latency_ms'] for r in lats) / n

            # Cost
            cost = conn.execute('''
                SELECT SUM(total_cost_usd) as total FROM pipeline_metrics WHERE timestamp > ?
            ''', (cutoff,)).fetchone()
            metrics['hourly_cost'] = cost['total'] or 0 if cost else 0

            # Confidence
            conf = conn.execute('''
                SELECT AVG(predicted_confidence) as avg_conf
                FROM confidence_calibration WHERE timestamp > ?
            ''', (cutoff,)).fetchone()
            metrics['avg_confidence'] = conf['avg_conf'] or 75 if conf else 75

            # Satisfaction rate
            sat = conn.execute('''
                SELECT COUNT(CASE WHEN was_correct = 1 THEN 1 END) as correct,
                       COUNT(*) as total
                FROM satisfaction_predictions
                WHERE actual_rating IS NOT NULL AND timestamp > ?
            ''', (cutoff,)).fetchone()
            if sat and sat['total'] > 0:
                metrics['satisfaction_rate'] = sat['correct'] / sat['total']

            # Error rate (escalations / total queries in the period)
            esc = conn.execute('''
                SELECT COUNT(*) as esc_count FROM escalation_queue WHERE created_at > ?
            ''', (cutoff,)).fetchone()
            total_q = conn.execute('''
                SELECT COUNT(*) as count FROM pipeline_metrics WHERE timestamp > ?
            ''', (cutoff,)).fetchone()
            if total_q and total_q['count'] > 0:
                metrics['error_rate'] = (esc['esc_count'] or 0) / total_q['count']

        except Exception as e:
            logger.error(f"Collect metrics error: {e}")

        return metrics

    @staticmethod
    def _dispatch(rule_id: int, rule_name: str, metric: str, value: float,
                  threshold: float, channel: str, message: str):
        """Dispatch alert to a channel."""
        try:
            conn = _get_conn()
            delivered = True

            if channel == 'webhook':
                delivered = AlertEngine._send_webhook(message)
            elif channel == 'email':
                delivered = AlertEngine._send_email(rule_name, message)
            # in_app always "delivered" (stored in DB)

            conn.execute('''
                INSERT INTO alert_history
                (rule_id, rule_name, metric, current_value, threshold, channel, message, delivered)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (rule_id, rule_name, metric, value, threshold, channel, message, delivered))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Alert dispatch error: {e}")

    @staticmethod
    def _send_webhook(message: str) -> bool:
        """Send alert to webhook (Slack/Teams/Discord)."""
        try:
            from config import Config
            url = Config.ALERT_WEBHOOK_URL
            if not url:
                return False

            import urllib.request
            payload = json.dumps({'text': message}).encode()
            req = urllib.request.Request(url, data=payload,
                                         headers={'Content-Type': 'application/json'})
            urllib.request.urlopen(req, timeout=10)
            return True
        except Exception as e:
            logger.error(f"Webhook send error: {e}")
            return False

    @staticmethod
    def _send_email(subject: str, body: str) -> bool:
        """Send alert email via SMTP."""
        try:
            from config import Config
            if not Config.ALERT_EMAIL_ENABLED:
                return False

            import smtplib
            from email.mime.text import MIMEText

            msg = MIMEText(body)
            msg['Subject'] = f"[Greenside AI Alert] {subject}"
            msg['From'] = Config.ALERT_EMAIL_FROM
            msg['To'] = Config.ALERT_EMAIL_TO

            with smtplib.SMTP(Config.ALERT_EMAIL_SMTP_HOST, Config.ALERT_EMAIL_SMTP_PORT) as server:
                server.starttls()
                server.login(Config.ALERT_EMAIL_FROM, Config.ALERT_EMAIL_PASSWORD)
                server.send_message(msg)
            return True
        except Exception as e:
            logger.error(f"Email send error: {e}")
            return False

    @staticmethod
    def get_alert_history(limit: int = 100) -> List[Dict]:
        """Get recent alert history."""
        try:
            conn = _get_conn()
            rows = conn.execute('''
                SELECT * FROM alert_history ORDER BY timestamp DESC LIMIT ?
            ''', (limit,)).fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"Get alert history error: {e}")
            return []

    @staticmethod
    def get_rules() -> List[Dict]:
        """Get all alert rules."""
        try:
            conn = _get_conn()
            rows = conn.execute('SELECT * FROM alert_rules ORDER BY id').fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"Get rules error: {e}")
            return []


# ============================================================================
# SUBSYSTEM 12: AUTOMATED REMEDIATION & CIRCUIT BREAKERS
# ============================================================================

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
                    # Reset count — failures are too spread out
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


class RemediationEngine:
    """Automated remediation engine with predefined actions."""

    @staticmethod
    def execute(trigger_type: str, context: Dict = None) -> Optional[Dict]:
        """Execute a remediation action based on trigger type."""
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


# ============================================================================
# SUBSYSTEM 13: PROMPT VERSIONING & OPTIMIZATION
# ============================================================================

class PromptVersioning:
    """Version control for system prompts with performance tracking."""

    @staticmethod
    def create_version(template_text: str, description: str = '',
                       changes: str = '', created_by: str = 'admin') -> int:
        """Create a new prompt version."""
        try:
            conn = _get_conn()
            template_hash = hashlib.sha256(template_text.encode()).hexdigest()[:16]

            # Get next version number
            max_v = conn.execute('SELECT MAX(version) FROM prompt_templates').fetchone()[0]
            version = (max_v or 0) + 1

            cursor = conn.execute('''
                INSERT INTO prompt_templates
                (version, template_hash, template_text, description, changes, created_by)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (version, template_hash, template_text, description, changes, created_by))
            version_id = cursor.lastrowid
            conn.commit()
            conn.close()
            log_event('prompt_versioning', 'version_created',
                      json.dumps({'id': version_id, 'version': version}))
            return version_id
        except Exception as e:
            logger.error(f"Create prompt version error: {e}")
            return 0

    @staticmethod
    def activate_version(version_id: int) -> bool:
        """Activate a prompt version (deactivate all others)."""
        try:
            conn = _get_conn()
            conn.execute('UPDATE prompt_templates SET is_active = 0, deactivated_at = CURRENT_TIMESTAMP WHERE is_active = 1')
            conn.execute('''
                UPDATE prompt_templates SET is_active = 1, activated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (version_id,))
            conn.commit()
            conn.close()
            log_event('prompt_versioning', 'version_activated',
                      json.dumps({'id': version_id}))
            return True
        except Exception as e:
            logger.error(f"Activate version error: {e}")
            return False

    @staticmethod
    def get_active_version() -> Optional[Dict]:
        """Get the currently active prompt version."""
        try:
            conn = _get_conn()
            row = conn.execute(
                'SELECT * FROM prompt_templates WHERE is_active = 1 LIMIT 1'
            ).fetchone()
            conn.close()
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"Get active version error: {e}")
            return None

    @staticmethod
    def rollback(version_id: int) -> bool:
        """Rollback to a specific prompt version."""
        return PromptVersioning.activate_version(version_id)

    @staticmethod
    def log_usage(version_id: int, query_id: int, confidence: float = None,
                  satisfaction: str = None):
        """Log usage of a prompt version for performance tracking."""
        try:
            conn = _get_conn()
            conn.execute('''
                INSERT INTO prompt_usage_log (version_id, query_id, confidence, satisfaction_rating)
                VALUES (?, ?, ?, ?)
            ''', (version_id, query_id, confidence, satisfaction))
            conn.execute('''
                UPDATE prompt_templates SET total_queries = total_queries + 1 WHERE id = ?
            ''', (version_id,))
            if confidence is not None:
                conn.execute('''
                    UPDATE prompt_templates
                    SET avg_confidence = (COALESCE(avg_confidence, 0) * (total_queries - 1) + ?) / total_queries
                    WHERE id = ?
                ''', (confidence, version_id))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Log prompt usage error: {e}")

    @staticmethod
    def get_all_versions() -> List[Dict]:
        """Get all prompt versions with performance data."""
        try:
            conn = _get_conn()
            rows = conn.execute('''
                SELECT id, version, template_hash, description, changes, is_active,
                       total_queries, avg_confidence, avg_satisfaction,
                       created_by, created_at, activated_at
                FROM prompt_templates ORDER BY version DESC
            ''').fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"Get all versions error: {e}")
            return []

    @staticmethod
    def compare_versions(v1_id: int, v2_id: int) -> Dict:
        """Compare two prompt versions' text and performance."""
        try:
            conn = _get_conn()
            v1 = conn.execute('SELECT * FROM prompt_templates WHERE id = ?', (v1_id,)).fetchone()
            v2 = conn.execute('SELECT * FROM prompt_templates WHERE id = ?', (v2_id,)).fetchone()
            conn.close()

            if not v1 or not v2:
                return {'error': 'Version not found'}

            v1, v2 = dict(v1), dict(v2)
            # Simple line diff
            lines1 = v1['template_text'].splitlines()
            lines2 = v2['template_text'].splitlines()
            added = [l for l in lines2 if l not in lines1]
            removed = [l for l in lines1 if l not in lines2]

            return {
                'v1': {'id': v1_id, 'version': v1['version'], 'queries': v1['total_queries'],
                       'avg_confidence': v1['avg_confidence']},
                'v2': {'id': v2_id, 'version': v2['version'], 'queries': v2['total_queries'],
                       'avg_confidence': v2['avg_confidence']},
                'lines_added': len(added),
                'lines_removed': len(removed),
                'added_sample': added[:10],
                'removed_sample': removed[:10]
            }
        except Exception as e:
            logger.error(f"Compare versions error: {e}")
            return {'error': str(e)}


# ============================================================================
# SUBSYSTEM 14: GRADIENT BOOSTED SATISFACTION PREDICTOR
# ============================================================================

class DecisionStump:
    """A single decision tree stump (max depth 3) for gradient boosting."""

    def __init__(self, max_depth: int = 3):
        self.max_depth = max_depth
        self.tree = None

    def fit(self, X: List[List[float]], residuals: List[float]):
        """Fit a decision tree on features and residuals."""
        self.tree = self._build_tree(X, residuals, depth=0)

    def predict(self, X: List[List[float]]) -> List[float]:
        """Predict for a list of samples."""
        return [self._predict_one(x) for x in X]

    def _predict_one(self, x: List[float]) -> float:
        node = self.tree
        if node is None:
            return 0.0
        while node.get('left') is not None:
            if x[node['feature']] <= node['threshold']:
                node = node['left']
            else:
                node = node['right']
        return node['value']

    def _build_tree(self, X: List[List[float]], residuals: List[float], depth: int) -> Dict:
        if not X or depth >= self.max_depth or len(X) < 4:
            val = sum(residuals) / max(len(residuals), 1)
            return {'value': val}

        best_feature = -1
        best_threshold = 0
        best_gain = -1
        n = len(X)
        n_features = len(X[0]) if X else 0

        total_sum = sum(residuals)
        total_sq = sum(r * r for r in residuals)
        base_var = total_sq / n - (total_sum / n) ** 2

        for f in range(n_features):
            # Get unique sorted values
            vals = sorted(set(x[f] for x in X))
            if len(vals) < 2:
                continue

            # Try midpoint thresholds (sample if too many)
            thresholds = []
            step = max(1, len(vals) // 10)
            for i in range(0, len(vals) - 1, step):
                thresholds.append((vals[i] + vals[i + 1]) / 2)

            for t in thresholds:
                left_r = [residuals[i] for i in range(n) if X[i][f] <= t]
                right_r = [residuals[i] for i in range(n) if X[i][f] > t]

                if len(left_r) < 2 or len(right_r) < 2:
                    continue

                # Variance reduction
                left_mean = sum(left_r) / len(left_r)
                right_mean = sum(right_r) / len(right_r)
                left_var = sum((r - left_mean) ** 2 for r in left_r) / len(left_r)
                right_var = sum((r - right_mean) ** 2 for r in right_r) / len(right_r)
                weighted_var = (len(left_r) * left_var + len(right_r) * right_var) / n
                gain = base_var - weighted_var

                if gain > best_gain:
                    best_gain = gain
                    best_feature = f
                    best_threshold = t

        if best_feature < 0 or best_gain < 1e-6:
            val = sum(residuals) / n
            return {'value': val}

        left_idx = [i for i in range(n) if X[i][best_feature] <= best_threshold]
        right_idx = [i for i in range(n) if X[i][best_feature] > best_threshold]

        return {
            'feature': best_feature,
            'threshold': best_threshold,
            'gain': best_gain,
            'left': self._build_tree([X[i] for i in left_idx],
                                     [residuals[i] for i in left_idx], depth + 1),
            'right': self._build_tree([X[i] for i in right_idx],
                                      [residuals[i] for i in right_idx], depth + 1)
        }


class GradientBoostedPredictor:
    """Pure-Python gradient boosted decision trees for satisfaction prediction."""

    _model = None  # {'trees': [...], 'base_prediction': float, 'feature_names': [...]}
    _feature_names = [
        'confidence', 'source_count', 'response_length', 'grounding_score',
        'hallucination_count', 'topic_difficulty', 'hour_of_day', 'day_of_week',
        'query_word_count', 'has_web_search', 'has_weather', 'num_images',
        'latency_ms', 'cost_usd', 'source_avg_trust', 'question_specificity',
        'is_follow_up', 'conversation_turn', 'category_lawn', 'category_disease',
        'category_weed', 'category_pest', 'category_fertilizer'
    ]

    @staticmethod
    def train(n_trees: int = 50, learning_rate: float = 0.1, max_depth: int = 3) -> Dict:
        """Train gradient boosted model on historical data."""
        try:
            conn = _get_conn()
            # Fetch labeled data (predictions that got actual ratings)
            rows = conn.execute('''
                SELECT sp.features, sp.actual_rating, sp.predicted_probability,
                       pm.total_latency_ms, pm.total_cost_usd
                FROM satisfaction_predictions sp
                LEFT JOIN pipeline_metrics pm ON sp.query_id = pm.query_id
                WHERE sp.actual_rating IS NOT NULL
                ORDER BY sp.timestamp DESC LIMIT 5000
            ''').fetchall()
            conn.close()

            if len(rows) < 50:
                return {'status': 'insufficient_data', 'count': len(rows)}

            # Build feature matrix and labels
            X = []
            y = []
            for row in rows:
                try:
                    features = json.loads(row['features']) if row['features'] else {}
                    if isinstance(features, dict):
                        feature_vec = [features.get(name, 0.0) for name in GradientBoostedPredictor._feature_names]
                    elif isinstance(features, list):
                        feature_vec = features + [0.0] * max(0, len(GradientBoostedPredictor._feature_names) - len(features))
                    else:
                        continue

                    # Add latency and cost from pipeline_metrics if available
                    if row['total_latency_ms']:
                        idx_lat = GradientBoostedPredictor._feature_names.index('latency_ms')
                        feature_vec[idx_lat] = row['total_latency_ms']
                    if row['total_cost_usd']:
                        idx_cost = GradientBoostedPredictor._feature_names.index('cost_usd')
                        feature_vec[idx_cost] = row['total_cost_usd']

                    X.append(feature_vec)
                    label = 1.0 if row['actual_rating'] in ('helpful', 'good', 'correct') else 0.0
                    y.append(label)
                except (json.JSONDecodeError, TypeError, ValueError):
                    continue

            if len(X) < 30:
                return {'status': 'insufficient_valid_data', 'count': len(X)}

            # Train gradient boosted model
            n = len(X)
            base_pred = sum(y) / n
            predictions = [base_pred] * n
            trees = []

            for i in range(n_trees):
                # Compute residuals
                residuals = [y[j] - predictions[j] for j in range(n)]

                # Fit a tree on residuals
                stump = DecisionStump(max_depth=max_depth)
                stump.fit(X, residuals)
                tree_preds = stump.predict(X)

                # Update predictions
                for j in range(n):
                    predictions[j] += learning_rate * tree_preds[j]
                    predictions[j] = max(0.01, min(0.99, predictions[j]))

                trees.append(stump.tree)

            # Compute feature importance (sum of gains per feature)
            importance = [0.0] * len(GradientBoostedPredictor._feature_names)
            for tree in trees:
                GradientBoostedPredictor._accumulate_importance(tree, importance)

            total_imp = sum(importance) or 1
            importance = [round(imp / total_imp, 4) for imp in importance]

            # Compute accuracy
            correct = sum(1 for j in range(n) if (predictions[j] > 0.5) == (y[j] > 0.5))
            accuracy = correct / n

            # Store model
            GradientBoostedPredictor._model = {
                'trees': trees,
                'base_prediction': base_pred,
                'learning_rate': learning_rate,
                'n_trees': len(trees),
                'feature_names': GradientBoostedPredictor._feature_names,
                'feature_importance': importance,
                'training_accuracy': accuracy,
                'training_samples': n,
                'trained_at': datetime.now().isoformat()
            }

            log_event('gradient_boosted', 'model_trained',
                      json.dumps({'accuracy': round(accuracy, 4), 'samples': n,
                                  'trees': len(trees)}))

            return {
                'status': 'trained',
                'accuracy': round(accuracy, 4),
                'samples': n,
                'trees': len(trees),
                'feature_importance': dict(zip(GradientBoostedPredictor._feature_names, importance))
            }
        except Exception as e:
            logger.error(f"Gradient boosted training error: {e}")
            return {'status': 'error', 'message': str(e)}

    @staticmethod
    def _accumulate_importance(node: Dict, importance: List[float]):
        if node is None or 'feature' not in node:
            return
        importance[node['feature']] += node.get('gain', 0)
        if node.get('left'):
            GradientBoostedPredictor._accumulate_importance(node['left'], importance)
        if node.get('right'):
            GradientBoostedPredictor._accumulate_importance(node['right'], importance)

    @staticmethod
    def predict(features: List[float]) -> float:
        """Predict satisfaction probability using gradient boosted model."""
        model = GradientBoostedPredictor._model
        if model is None:
            return 0.5  # No model trained yet, return neutral

        prediction = model['base_prediction']
        lr = model['learning_rate']

        for tree in model['trees']:
            node = tree
            if node is None:
                continue
            while node and node.get('left') is not None:
                feat_idx = node['feature']
                if feat_idx < len(features) and features[feat_idx] <= node['threshold']:
                    node = node['left']
                else:
                    node = node['right']
            if node:
                prediction += lr * node.get('value', 0)

        return max(0.01, min(0.99, prediction))

    @staticmethod
    def feature_importance() -> Dict:
        """Get feature importance from the trained model."""
        model = GradientBoostedPredictor._model
        if not model:
            return {'status': 'no_model'}

        imp = model.get('feature_importance', [])
        names = model.get('feature_names', [])
        ranked = sorted(zip(names, imp), key=lambda x: x[1], reverse=True)
        return {
            'ranked': [{'feature': n, 'importance': i} for n, i in ranked],
            'accuracy': model.get('training_accuracy'),
            'samples': model.get('training_samples'),
            'trees': model.get('n_trees'),
            'trained_at': model.get('trained_at')
        }


# ============================================================================
# SUBSYSTEM 15: KNOWLEDGE GAP ANALYZER
# ============================================================================

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


# ============================================================================
# SUBSYSTEM 16: EXECUTIVE DASHBOARD & REPORTING
# ============================================================================

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

            # 1. Availability (20%) — based on requests in last 24h vs expected
            req_count = conn.execute('''
                SELECT COUNT(*) as count FROM pipeline_metrics WHERE timestamp > ?
            ''', (cutoff_24h,)).fetchone()['count']
            # Score: 100 if any requests, scale by expected volume
            availability = min(100, (req_count / max(1, 1)) * 100) if req_count > 0 else 50
            components['availability'] = {'score': round(availability, 1), 'weight': 0.20,
                                           'detail': f"{req_count} requests in 24h"}

            # 2. Latency p95 (15%) — target <10s, critical >20s
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


# ============================================================================
# SUBSYSTEM 17: CONVERSATION INTELLIGENCE
# ============================================================================

class ConversationIntelligence:
    """Analyze multi-turn conversation quality and detect frustration."""

    @staticmethod
    def analyze_conversation(conversation_id: str) -> Optional[Dict]:
        """Analyze a single conversation's quality metrics."""
        try:
            # Read from conversation DB
            conv_db = os.path.join(DATA_DIR, 'greenside_conversations.db')
            if not os.path.exists(conv_db):
                return None

            conn = sqlite3.connect(conv_db)
            conn.row_factory = sqlite3.Row

            messages = conn.execute('''
                SELECT role, content, timestamp FROM messages
                WHERE session_id = ? ORDER BY timestamp
            ''', (conversation_id,)).fetchall()
            conn.close()

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
            feedback_conn = _get_conn()
            feedback_conn.execute('''
                INSERT OR REPLACE INTO conversation_analytics
                (conversation_id, turn_count, resolution_status, frustration_score,
                 frustration_signals, topic_drift_score, first_message, last_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (conversation_id, turns, resolution, frustration_score,
                  json.dumps(frustration_signals), drift_score,
                  result['first_message'], result['last_message']))
            feedback_conn.commit()
            feedback_conn.close()

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
            conv_db = os.path.join(DATA_DIR, 'greenside_conversations.db')
            if not os.path.exists(conv_db):
                return

            conn = sqlite3.connect(conv_db)
            conn.row_factory = sqlite3.Row
            cutoff = (datetime.now() - timedelta(days=days)).isoformat()

            sessions = conn.execute('''
                SELECT DISTINCT session_id FROM messages
                WHERE timestamp > ? AND role = 'user'
            ''', (cutoff,)).fetchall()
            conn.close()

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


# ============================================================================
# ANTHROPIC-GRADE: FEATURE FLAGS
# ============================================================================

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


# ============================================================================
# ANTHROPIC-GRADE: RATE LIMITER
# ============================================================================

class RateLimiter:
    """In-memory token bucket rate limiter. No external dependencies."""

    _buckets = {}  # key -> {'tokens': float, 'last_refill': float}
    _lock = threading.Lock()
    _blocked_count = 0

    # Default limits
    ASK_LIMIT_PER_MIN = 30
    API_LIMIT_PER_MIN = 100
    GLOBAL_LIMIT_PER_MIN = 500

    @staticmethod
    def _get_bucket(key: str, rate_per_min: int) -> dict:
        """Get or create a token bucket for a key."""
        now = time.time()
        with RateLimiter._lock:
            if key not in RateLimiter._buckets:
                RateLimiter._buckets[key] = {
                    'tokens': rate_per_min,
                    'last_refill': now,
                    'rate': rate_per_min
                }

            bucket = RateLimiter._buckets[key]
            # Refill tokens based on elapsed time
            elapsed = now - bucket['last_refill']
            tokens_to_add = elapsed * (bucket['rate'] / 60.0)
            bucket['tokens'] = min(bucket['rate'], bucket['tokens'] + tokens_to_add)
            bucket['last_refill'] = now
            return bucket

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

        with RateLimiter._lock:
            if ip_bucket['tokens'] < 1:
                RateLimiter._blocked_count += 1
                wait = 60.0 / ip_bucket['rate']
                return {'allowed': False, 'retry_after': max(1, int(wait))}

            if global_bucket['tokens'] < 1:
                RateLimiter._blocked_count += 1
                wait = 60.0 / global_bucket['rate']
                return {'allowed': False, 'retry_after': max(1, int(wait))}

            ip_bucket['tokens'] -= 1
            global_bucket['tokens'] -= 1
            return {'allowed': True, 'retry_after': 0}

    @staticmethod
    def get_status() -> Dict:
        """Get rate limiter status."""
        return {
            'enabled': FeatureFlags.is_enabled('rate_limiting'),
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
        """Remove buckets that haven't been used in 10 minutes."""
        cutoff = time.time() - 600
        with RateLimiter._lock:
            to_delete = [k for k, v in RateLimiter._buckets.items()
                         if v['last_refill'] < cutoff]
            for k in to_delete:
                del RateLimiter._buckets[k]


# ============================================================================
# ANTHROPIC-GRADE: DATA RETENTION MANAGER
# ============================================================================

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


# ============================================================================
# ANTHROPIC-GRADE: TRAINING ORCHESTRATOR
# ============================================================================

class TrainingOrchestrator:
    """Monitor quality metrics and flag when retraining is recommended."""

    @staticmethod
    def check_readiness() -> Dict:
        """Check if conditions warrant model retraining."""
        reasons = []
        metrics = {}

        try:
            conn = _get_conn()

            # Check 1: Rolling 24h satisfaction score
            satisfaction_row = conn.execute('''
                SELECT AVG(CASE WHEN was_correct = 1 THEN 1.0 ELSE 0.0 END) as accuracy,
                       COUNT(*) as total
                FROM satisfaction_predictions
                WHERE timestamp > datetime('now', '-24 hours') AND actual_rating IS NOT NULL
            ''').fetchone()

            if satisfaction_row and satisfaction_row['total'] > 10:
                accuracy = satisfaction_row['accuracy'] or 0
                metrics['satisfaction_accuracy_24h'] = round(accuracy, 3)
                metrics['satisfaction_sample_size'] = satisfaction_row['total']
                if accuracy < 0.6:
                    reasons.append(f"Satisfaction accuracy dropped to {accuracy:.1%} (threshold: 60%)")

            # Check 2: Golden answer count since last training
            golden_count = conn.execute('''
                SELECT COUNT(*) FROM golden_answers
                WHERE active = 1 AND created_at > datetime('now', '-30 days')
            ''').fetchone()[0]
            metrics['new_golden_answers_30d'] = golden_count
            if golden_count >= 50:
                reasons.append(f"{golden_count} new golden answers available for training")

            # Check 3: Regression detections in last 7 days
            regression_count = conn.execute('''
                SELECT COUNT(*) FROM intelligence_events
                WHERE subsystem = 'regression' AND severity = 'warning'
                AND timestamp > datetime('now', '-7 days')
            ''').fetchone()[0]
            metrics['regressions_7d'] = regression_count
            if regression_count >= 3:
                reasons.append(f"{regression_count} quality regressions in last 7 days")

            # Check 4: Negative feedback rate trending up
            neg_rate_row = conn.execute('''
                SELECT
                    SUM(CASE WHEN actual_rating IN ('unhelpful', 'bad', 'incorrect') THEN 1 ELSE 0 END) as neg,
                    COUNT(*) as total
                FROM satisfaction_predictions
                WHERE timestamp > datetime('now', '-48 hours') AND actual_rating IS NOT NULL
            ''').fetchone()
            if neg_rate_row and neg_rate_row['total'] > 10:
                neg_rate = (neg_rate_row['neg'] or 0) / neg_rate_row['total']
                metrics['negative_feedback_rate_48h'] = round(neg_rate, 3)
                if neg_rate > 0.3:
                    reasons.append(f"Negative feedback rate at {neg_rate:.1%} (threshold: 30%)")

            conn.close()

            ready = len(reasons) >= 2  # Need at least 2 signals

            # Create alert if ready and alerting is enabled
            if ready and FeatureFlags.is_enabled('alerting'):
                try:
                    AlertEngine._dispatch(
                        rule_id=0,
                        rule_name='training_readiness',
                        metric='training_readiness',
                        value=float(len(reasons)),
                        threshold=2.0,
                        channel='in_app',
                        message=f"Training recommended: {'; '.join(reasons)}"
                    )
                except Exception:
                    pass

            return {
                'ready': ready,
                'reasons': reasons,
                'metrics': metrics,
                'checked_at': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Training readiness check error: {e}")
            return {'ready': False, 'reasons': [], 'metrics': {}, 'error': str(e)}


# ============================================================================
# ANTHROPIC-GRADE: INPUT SANITIZATION
# ============================================================================

class InputSanitizer:
    """Score-based prompt injection detection with pattern matching."""

    import re as _re

    _PATTERNS = [
        # Direct injection attempts
        (_re.compile(r'ignore\s+(all\s+)?previous\s+(instructions|prompts|context)', _re.IGNORECASE), 5),
        (_re.compile(r'disregard\s+(all\s+)?previous', _re.IGNORECASE), 5),
        (_re.compile(r'forget\s+(everything|all|your)\s+(instructions|rules|training)', _re.IGNORECASE), 5),
        (_re.compile(r'you\s+are\s+now\s+', _re.IGNORECASE), 4),
        (_re.compile(r'new\s+instructions?\s*:', _re.IGNORECASE), 4),
        (_re.compile(r'system\s*:\s*', _re.IGNORECASE), 3),
        (_re.compile(r'\[INST\]', _re.IGNORECASE), 4),
        (_re.compile(r'\[/INST\]', _re.IGNORECASE), 4),
        (_re.compile(r'<\|im_start\|>', _re.IGNORECASE), 4),
        (_re.compile(r'<<SYS>>', _re.IGNORECASE), 5),
        (_re.compile(r'act\s+as\s+(a\s+)?(different|new|another)', _re.IGNORECASE), 3),
        (_re.compile(r'pretend\s+(you\s+are|to\s+be)\s+', _re.IGNORECASE), 3),
        (_re.compile(r'override\s+(your\s+)?(rules|instructions|safety)', _re.IGNORECASE), 5),
        (_re.compile(r'reveal\s+(your\s+)?(system\s+)?prompt', _re.IGNORECASE), 4),
        (_re.compile(r'what\s+is\s+your\s+system\s+prompt', _re.IGNORECASE), 3),
        (_re.compile(r'jailbreak', _re.IGNORECASE), 5),
        (_re.compile(r'DAN\s+mode', _re.IGNORECASE), 5),
        (_re.compile(r'developer\s+mode', _re.IGNORECASE), 3),
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
        import re
        b64_matches = re.findall(r'[A-Za-z0-9+/]{50,}={0,2}', query)
        if b64_matches:
            # Try to decode and check for injection patterns
            import base64
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


# ============================================================================
# BACKGROUND SCHEDULER
# ============================================================================

class IntelligenceScheduler:
    """Background scheduler for periodic intelligence jobs."""

    _running = False
    _thread = None

    @staticmethod
    def start():
        """Start the background intelligence scheduler."""
        if IntelligenceScheduler._running:
            return

        IntelligenceScheduler._running = True
        IntelligenceScheduler._thread = threading.Thread(
            target=IntelligenceScheduler._run_loop, daemon=True
        )
        IntelligenceScheduler._thread.start()
        log_event('scheduler', 'started')
        logger.info("Intelligence scheduler started")

    @staticmethod
    def stop():
        """Stop the scheduler."""
        IntelligenceScheduler._running = False
        log_event('scheduler', 'stopped')

    @staticmethod
    def _run_loop():
        """Main scheduler loop with 4 cadences."""
        last_15min = 0
        last_hourly = 0
        last_6hour = 0
        last_daily = 0

        while IntelligenceScheduler._running:
            now = time.time()

            try:
                # 15-minute tasks (anomaly detection + alerting)
                if now - last_15min >= 900:
                    logger.info("Running 15-min intelligence tasks")
                    IntelligenceScheduler._run_15min()
                    last_15min = now

                # Hourly tasks
                if now - last_hourly >= 3600:
                    logger.info("Running hourly intelligence tasks")
                    IntelligenceScheduler._run_hourly()
                    last_hourly = now

                # 6-hour tasks
                if now - last_6hour >= 21600:
                    logger.info("Running 6-hour intelligence tasks")
                    IntelligenceScheduler._run_6hourly()
                    last_6hour = now

                # Daily tasks
                if now - last_daily >= 86400:
                    logger.info("Running daily intelligence tasks")
                    IntelligenceScheduler._run_daily()
                    last_daily = now

            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                log_event('scheduler', 'error', str(e), 'error')

            time.sleep(60)  # Check every minute

    @staticmethod
    def _run_15min():
        """Every 15 min: anomaly detection + alert evaluation."""
        try:
            AnomalyDetector.check_all()
        except Exception as e:
            logger.error(f"Anomaly check failed: {e}")

        try:
            AlertEngine.evaluate_rules()
        except Exception as e:
            logger.error(f"Alert evaluation failed: {e}")

        log_event('scheduler', '15min_complete')

    @staticmethod
    def _run_hourly():
        """Hourly: topic metrics, calibration, pipeline aggregates, baselines."""
        try:
            TopicIntelligence.update_topic_metrics()
        except Exception as e:
            logger.error(f"Topic metrics update failed: {e}")

        try:
            ConfidenceCalibration.compute_calibration_curve()
        except Exception as e:
            logger.error(f"Calibration curve update failed: {e}")

        try:
            PipelineAnalytics.compute_hourly_aggregates()
        except Exception as e:
            logger.error(f"Pipeline aggregates failed: {e}")

        try:
            AnomalyDetector.compute_baselines()
        except Exception as e:
            logger.error(f"Baseline computation failed: {e}")

        log_event('scheduler', 'hourly_complete')

    @staticmethod
    def _run_6hourly():
        """6-hourly: clustering, emerging topics, satisfaction model, gradient boosted training."""
        try:
            TopicIntelligence.cluster_questions()
        except Exception as e:
            logger.error(f"Clustering failed: {e}")

        try:
            TopicIntelligence.detect_emerging_topics()
        except Exception as e:
            logger.error(f"Emerging topics detection failed: {e}")

        try:
            SatisfactionPredictor.train_satisfaction_model()
        except Exception as e:
            logger.error(f"Satisfaction model training failed: {e}")

        try:
            GradientBoostedPredictor.train()
        except Exception as e:
            logger.error(f"Gradient boosted training failed: {e}")

        try:
            KnowledgeGapAnalyzer.detect_gaps()
        except Exception as e:
            logger.error(f"Knowledge gap detection failed: {e}")

        try:
            TrainingOrchestrator.check_readiness()
        except Exception as e:
            logger.error(f"Training readiness check failed: {e}")

        log_event('scheduler', '6hourly_complete')

    @staticmethod
    def _run_daily():
        """Daily: regression, source reliability, content freshness, conversation analysis, retention, digest."""
        try:
            SourceQualityIntelligence.update_batch_from_feedback()
        except Exception as e:
            logger.error(f"Source reliability batch update failed: {e}")

        try:
            KnowledgeGapAnalyzer.track_content_freshness()
        except Exception as e:
            logger.error(f"Content freshness tracking failed: {e}")

        try:
            ConversationIntelligence.batch_analyze_recent(days=1)
        except Exception as e:
            logger.error(f"Conversation analysis failed: {e}")

        # Data retention cleanup
        try:
            DataRetentionManager.run_cleanup()
        except Exception as e:
            logger.error(f"Data retention cleanup failed: {e}")

        # Rate limiter bucket cleanup
        try:
            RateLimiter.cleanup_old_buckets()
        except Exception as e:
            logger.error(f"Rate limiter cleanup failed: {e}")

        # Weekly digest on Mondays
        if datetime.now().weekday() == 0:
            try:
                ExecutiveDashboard.generate_weekly_digest()
            except Exception as e:
                logger.error(f"Weekly digest failed: {e}")

        log_event('scheduler', 'daily_complete')


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _keyword_similarity(text1: str, text2: str) -> float:
    """Simple keyword overlap similarity (Jaccard on words)."""
    if not text1 or not text2:
        return 0.0
    stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
                  'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
                  'would', 'could', 'should', 'may', 'might', 'can', 'shall',
                  'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from',
                  'it', 'this', 'that', 'and', 'or', 'but', 'not', 'what',
                  'how', 'when', 'where', 'which', 'who', 'i', 'my', 'me'}
    words1 = set(w.lower().strip('.,?!') for w in text1.split()) - stop_words
    words2 = set(w.lower().strip('.,?!') for w in text2.split()) - stop_words
    if not words1 or not words2:
        return 0.0
    intersection = words1 & words2
    union = words1 | words2
    return len(intersection) / len(union) if union else 0.0


def _wilson_score_interval(positive: int, total: int, z: float = 1.96) -> Tuple[float, float]:
    """Wilson score confidence interval for binomial proportion."""
    if total == 0:
        return (0.0, 0.0)
    p_hat = positive / total
    denominator = 1 + z * z / total
    center = (p_hat + z * z / (2 * total)) / denominator
    spread = z * math.sqrt((p_hat * (1 - p_hat) + z * z / (4 * total)) / total) / denominator
    return (max(0, center - spread), min(1, center + spread))


def _sigmoid(z: float) -> float:
    """Sigmoid activation function."""
    if z > 500:
        return 1.0
    if z < -500:
        return 0.0
    return 1.0 / (1.0 + math.exp(-z))


def _isotonic_regression(x: List[float], y: List[float]) -> List[float]:
    """
    Pool-adjacent-violators algorithm for isotonic regression.
    Ensures output is non-decreasing.
    """
    n = len(y)
    if n == 0:
        return []

    result = list(y)
    # Forward pass: ensure non-decreasing
    i = 0
    while i < n:
        j = i
        sum_val = result[i]
        count = 1

        while j + 1 < n and result[j + 1] < sum_val / count:
            j += 1
            sum_val += result[j]
            count += 1

        avg = sum_val / count
        for k in range(i, j + 1):
            result[k] = avg

        i = j + 1

    return result


def _compute_drift_score(expected: str, actual: str, criteria: str = None) -> Dict:
    """
    Compute semantic drift between expected and actual answers.
    Returns score (0=identical, 1=completely different) and issues list.
    """
    if not actual:
        return {'score': 1.0, 'issues': ['No answer generated']}

    issues = []
    score = 0.0

    # Keyword overlap
    keyword_sim = _keyword_similarity(expected, actual)
    keyword_drift = 1.0 - keyword_sim
    score += keyword_drift * 0.4

    # Length ratio
    len_ratio = len(actual) / max(len(expected), 1)
    if len_ratio < 0.3 or len_ratio > 3.0:
        issues.append(f"Length ratio: {len_ratio:.1f}x")
        score += 0.2

    # Check criteria keywords if provided
    if criteria:
        criteria_keywords = [k.strip().lower() for k in criteria.split(',')]
        actual_lower = actual.lower()
        missing = [k for k in criteria_keywords if k and k not in actual_lower]
        if missing:
            issues.append(f"Missing criteria: {', '.join(missing)}")
            score += len(missing) / max(len(criteria_keywords), 1) * 0.4

    score = min(1.0, score)
    if keyword_drift > 0.7:
        issues.append(f"Low keyword overlap ({keyword_sim:.2f})")

    return {'score': round(score, 3), 'issues': issues}


def _agglomerative_cluster(embeddings: List[List[float]], threshold: float = 0.7,
                           min_size: int = 5) -> Dict[int, List[int]]:
    """
    Simple agglomerative clustering using cosine similarity.
    Returns dict of cluster_id -> list of member indices.
    """
    n = len(embeddings)
    if n == 0:
        return {}

    # Start with each point as its own cluster
    assignments = list(range(n))

    # Compute pairwise similarities (only upper triangle, limit for performance)
    max_pairs = min(n * (n - 1) // 2, 50000)
    pairs = []

    # Sample pairs if too many
    if n > 300:
        import random
        sample_indices = random.sample(range(n), min(300, n))
        for i in range(len(sample_indices)):
            for j in range(i + 1, len(sample_indices)):
                idx_i = sample_indices[i]
                idx_j = sample_indices[j]
                sim = _cosine_similarity(embeddings[idx_i], embeddings[idx_j])
                if sim >= threshold:
                    pairs.append((idx_i, idx_j, sim))
    else:
        for i in range(n):
            for j in range(i + 1, n):
                sim = _cosine_similarity(embeddings[i], embeddings[j])
                if sim >= threshold:
                    pairs.append((i, j, sim))

    # Sort by similarity descending
    pairs.sort(key=lambda x: x[2], reverse=True)

    # Merge clusters greedily
    for i, j, sim in pairs:
        ci = assignments[i]
        cj = assignments[j]
        if ci != cj:
            # Merge smaller into larger
            target = min(ci, cj)
            source = max(ci, cj)
            for k in range(n):
                if assignments[k] == source:
                    assignments[k] = target

    # Build cluster dict
    clusters = defaultdict(list)
    for idx, cluster_id in enumerate(assignments):
        clusters[cluster_id].append(idx)

    # Filter by min size
    return {k: v for k, v in clusters.items() if len(v) >= min_size}


def _compute_centroid(embeddings: List[List[float]]) -> List[float]:
    """Compute the centroid of a list of embeddings."""
    if not embeddings:
        return []
    dim = len(embeddings[0])
    centroid = [0.0] * dim
    for emb in embeddings:
        for i in range(dim):
            centroid[i] += emb[i]
    n = len(embeddings)
    return [c / n for c in centroid]


def _auto_name_cluster(questions: List[str]) -> str:
    """Auto-generate a cluster name from common keywords in questions."""
    stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
                  'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
                  'could', 'should', 'can', 'to', 'of', 'in', 'for', 'on',
                  'with', 'at', 'by', 'from', 'it', 'this', 'that', 'and',
                  'or', 'but', 'not', 'what', 'how', 'when', 'where', 'which',
                  'who', 'i', 'my', 'me', 'best', 'good', 'use', 'need'}

    word_counts = defaultdict(int)
    for q in questions:
        words = set(w.lower().strip('.,?!') for w in q.split()) - stop_words
        for w in words:
            if len(w) > 2:
                word_counts[w] += 1

    top_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)[:3]
    if top_words:
        return ' '.join(w[0].title() for w in top_words)
    return 'Uncategorized'


# ============================================================================
# UNIFIED API — Convenience functions for app.py integration
# ============================================================================

def process_answer_intelligence(query_id: int, question: str, answer: str,
                                 confidence: float, sources: List = None,
                                 category: str = None, user_id: str = None,
                                 grounding_result: Dict = None,
                                 hallucination_result: Dict = None,
                                 embedding: List[float] = None,
                                 timings: Dict = None,
                                 token_usage: Dict = None,
                                 ab_assignment: Dict = None):
    """
    Main integration point — called after /ask generates an answer.
    Runs all intelligence subsystems on the answer.
    Returns any modifications or flags.
    """
    result = {
        'golden_answers_injected': [],
        'confidence_adjusted': confidence,
        'ab_test': None,
        'topic': None,
        'satisfaction_prediction': None,
        'escalation': None,
        'pipeline_cost': None
    }

    # Enterprise: Record pipeline metrics + cost
    try:
        PipelineAnalytics.record_request(
            query_id=query_id,
            timings=timings,
            token_usage=token_usage
        )
        if token_usage:
            cost = PipelineAnalytics.calculate_cost(
                token_usage.get('prompt_tokens', 0),
                token_usage.get('completion_tokens', 0),
                token_usage.get('model', 'gpt-4o')
            )
            result['pipeline_cost'] = cost
    except Exception as _pe:
        logger.warning(f"Pipeline metrics recording skipped: {_pe}")

    # Enterprise: Log prompt version usage
    try:
        active_prompt = PromptVersioning.get_active_version()
        if active_prompt:
            PromptVersioning.log_usage(active_prompt['id'], query_id, confidence)
    except Exception as _pv:
        logger.warning(f"Prompt version logging skipped: {_pv}")

    try:
        # 1. Check for golden answer matches (already done before LLM call typically)
        # This is informational — the actual injection happens in the prompt building

        # 2. A/B test — use pre-assignment from app.py (assigned BEFORE LLM call)
        if ab_assignment:
            result['ab_test'] = ab_assignment

        # 3. Source quality adjustment (already done in reranking typically)

        # 4. Confidence calibration
        adjusted = ConfidenceCalibration.get_calibration_adjustment(confidence, category)
        result['confidence_adjusted'] = adjusted

        # 5. Topic assignment
        if embedding:
            topic = TopicIntelligence.assign_topic(question, embedding)
            if topic:
                result['topic'] = topic
                TopicIntelligence.store_question_embedding(question, embedding, query_id,
                                                           topic['cluster_id'])
            else:
                TopicIntelligence.store_question_embedding(question, embedding, query_id)

        # 6. Satisfaction prediction
        source_count = len(sources) if sources else 0
        features = SatisfactionPredictor.extract_features(
            confidence=confidence,
            source_count=source_count,
            response_length=len(answer),
            grounding_score=grounding_result.get('confidence', 1.0) if grounding_result else 1.0,
            hallucination_penalties=len(hallucination_result.get('penalties', [])) if hallucination_result else 0,
            topic_difficulty=0.5,  # Default; could be computed from topic cluster metrics
            hour_of_day=datetime.now().hour
        )
        satisfaction_prob = SatisfactionPredictor.predict_satisfaction(features)
        result['satisfaction_prediction'] = round(satisfaction_prob, 3)
        SatisfactionPredictor.record_prediction(query_id, satisfaction_prob, features)

        # 7. Calibration recording (will be updated when user rates)

        # 8. Smart escalation check
        failure = SmartEscalation.classify_failure_mode(
            confidence=confidence,
            grounding_result=grounding_result,
            hallucination_result=hallucination_result,
            source_count=source_count,
            predicted_satisfaction=satisfaction_prob
        )

        if failure:
            similar = SmartEscalation.find_similar_approved(question)
            suggested_fix = similar[0]['approved_answer'] if similar else None
            similar_ids = [s['feedback_id'] for s in similar]

            esc_id = SmartEscalation.create_escalation(
                query_id=query_id,
                question=question,
                answer=answer,
                failure_mode=failure['failure_mode'],
                failure_details=failure['details'],
                predicted_satisfaction=satisfaction_prob,
                confidence=confidence,
                suggested_fix=suggested_fix,
                similar_ids=similar_ids,
                priority=failure['priority']
            )
            result['escalation'] = {
                'id': esc_id,
                'failure_mode': failure['failure_mode'],
                'priority': failure['priority']
            }

    except Exception as e:
        logger.error(f"Intelligence processing error: {e}")
        log_event('system', 'processing_error', str(e), 'error')

    return result


def process_feedback_intelligence(query_id: int, question: str, rating: str,
                                   confidence: float, sources: List = None,
                                   category: str = None, correction: str = None,
                                   original_answer: str = None):
    """
    Called when a user submits feedback/rating.
    Updates calibration, source reliability, prediction accuracy,
    and auto-creates golden answers from user corrections.
    """
    try:
        # Record calibration point
        ConfidenceCalibration.record_calibration_point(
            query_id=query_id,
            predicted_confidence=confidence,
            actual_rating=rating,
            topic=category
        )

        # Update source reliability
        if sources:
            for source in sources:
                source_id = str(source.get('id', source.get('source', str(source))))
                source_title = source.get('title', source.get('metadata', {}).get('title', ''))
                SourceQualityIntelligence.update_source_reliability(
                    source_id=source_id,
                    rating=rating,
                    confidence=confidence,
                    source_title=source_title
                )

        # Update satisfaction prediction accuracy
        conn = _get_conn()
        pred = conn.execute('''
            SELECT id, predicted_probability FROM satisfaction_predictions
            WHERE query_id = ? ORDER BY timestamp DESC LIMIT 1
        ''', (query_id,)).fetchone()

        if pred:
            predicted_positive = pred['predicted_probability'] > 0.5
            actual_positive = rating in ('helpful', 'good', 'correct')
            was_correct = predicted_positive == actual_positive
            conn.execute('''
                UPDATE satisfaction_predictions SET actual_rating = ?, was_correct = ?
                WHERE id = ?
            ''', (rating, was_correct, pred['id']))
            conn.commit()
        conn.close()

        # CLOSED LOOP: Auto-create golden answer from user correction
        if correction and len(correction.strip()) > 20:
            _auto_promote_correction_to_golden(
                query_id=query_id,
                question=question,
                correction=correction,
                category=category
            )

        # CLOSED LOOP: Track negative feedback accumulation per topic
        if rating in ('unhelpful', 'bad', 'incorrect') and category:
            _track_negative_accumulation(question, category, query_id)

    except Exception as e:
        logger.error(f"Feedback intelligence error: {e}")
        log_event('system', 'feedback_processing_error', str(e), 'error')


def _auto_promote_correction_to_golden(query_id: int, question: str,
                                        correction: str, category: str = None):
    """Auto-create a golden answer from a user correction."""
    try:
        conn = _get_conn()
        # Check if a similar golden answer already exists
        existing = conn.execute('''
            SELECT id FROM golden_answers
            WHERE question = ? AND active = 1 LIMIT 1
        ''', (question,)).fetchone()

        if existing:
            # Update existing golden answer with the correction
            conn.execute('''
                UPDATE golden_answers SET answer = ?, updated_at = CURRENT_TIMESTAMP,
                    created_by = 'auto_correction'
                WHERE id = ?
            ''', (correction, existing['id']))
            log_event('self_healing', 'golden_answer_updated_from_correction',
                      json.dumps({'golden_id': existing['id'], 'query_id': query_id}))
        else:
            # Create new golden answer
            conn.execute('''
                INSERT INTO golden_answers (question, answer, category, source_feedback_id, created_by)
                VALUES (?, ?, ?, ?, 'auto_correction')
            ''', (question, correction, category, query_id))
            log_event('self_healing', 'golden_answer_auto_created',
                      json.dumps({'query_id': query_id, 'question': question[:100]}))

        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Auto-promote correction error: {e}")


def _track_negative_accumulation(question: str, category: str, query_id: int):
    """Track negative feedback per topic. Alert if threshold reached."""
    try:
        conn = _get_conn()
        # Count recent negative feedback for this category
        neg_count = conn.execute('''
            SELECT COUNT(*) FROM confidence_calibration
            WHERE topic = ? AND actual_rating IN ('unhelpful', 'bad', 'incorrect')
            AND timestamp > datetime('now', '-7 days')
        ''', (category,)).fetchone()[0]
        conn.close()

        if neg_count >= 3:
            log_event('feedback_loop', 'negative_accumulation_alert',
                      json.dumps({
                          'category': category,
                          'negative_count_7d': neg_count,
                          'latest_query_id': query_id
                      }), 'warning')
    except Exception as e:
        logger.error(f"Negative accumulation tracking error: {e}")


def get_intelligence_overview() -> Dict:
    """Get high-level intelligence dashboard data."""
    try:
        conn = _get_conn()

        # Golden answers count
        golden_count = conn.execute('SELECT COUNT(*) FROM golden_answers WHERE active = 1').fetchone()[0]

        # Active A/B tests
        ab_count = conn.execute('SELECT COUNT(*) FROM ab_tests WHERE status = "active"').fetchone()[0]

        # Source reliability stats
        source_count = conn.execute('SELECT COUNT(*) FROM source_reliability').fetchone()[0]
        avg_trust = conn.execute('SELECT AVG(trust_score) FROM source_reliability').fetchone()[0]

        # Calibration data points
        calib_count = conn.execute('SELECT COUNT(*) FROM confidence_calibration').fetchone()[0]

        # Regression test stats
        reg_tests = conn.execute('SELECT COUNT(*) FROM regression_tests WHERE active = 1').fetchone()[0]
        latest_run = conn.execute('''
            SELECT passed, warned, failed FROM regression_runs
            ORDER BY started_at DESC LIMIT 1
        ''').fetchone()

        # Topic clusters
        cluster_count = conn.execute('SELECT COUNT(*) FROM topic_clusters WHERE active = 1').fetchone()[0]

        # Escalation queue
        open_escalations = conn.execute('SELECT COUNT(*) FROM escalation_queue WHERE status = "open"').fetchone()[0]

        # Satisfaction prediction accuracy
        pred_accuracy = SatisfactionPredictor.get_prediction_accuracy()

        # Recent events
        recent_events = conn.execute('''
            SELECT * FROM intelligence_events ORDER BY timestamp DESC LIMIT 20
        ''').fetchall()

        # Enterprise metrics
        pipeline_count = conn.execute('SELECT COUNT(*) FROM pipeline_metrics').fetchone()[0]
        total_cost = conn.execute('SELECT SUM(total_cost_usd) FROM pipeline_metrics').fetchone()[0]
        anomaly_count = conn.execute('''
            SELECT COUNT(*) FROM anomaly_detections
            WHERE acknowledged = 0 AND timestamp > datetime('now', '-24 hours')
        ''').fetchone()[0]
        alert_count = conn.execute('''
            SELECT COUNT(*) FROM alert_history
            WHERE acknowledged = 0 AND timestamp > datetime('now', '-24 hours')
        ''').fetchone()[0]
        open_breakers = conn.execute('''
            SELECT COUNT(*) FROM circuit_breakers WHERE state = 'open'
        ''').fetchone()[0]
        prompt_versions = conn.execute('SELECT COUNT(*) FROM prompt_templates').fetchone()[0]
        gap_count = conn.execute('''
            SELECT COUNT(*) FROM knowledge_gaps WHERE status = 'open'
        ''').fetchone()[0]

        conn.close()

        # System health score
        try:
            health = ExecutiveDashboard.compute_system_health()
            health_score = health.get('health_score', 0)
            health_status = health.get('status', 'unknown')
        except Exception:
            health_score = 0
            health_status = 'unknown'

        # Anthropic-grade: feature flags, rate limiting, budget, training
        feature_flags_count = len([f for f in FeatureFlags.get_all_flags() if f.get('enabled')])
        rate_limit_status = RateLimiter.get_status()
        budget_status = PipelineAnalytics.check_budget()
        training_ready = False
        try:
            tr = TrainingOrchestrator.check_readiness()
            training_ready = tr.get('ready', False)
        except Exception:
            pass

        return {
            'golden_answers': golden_count,
            'active_ab_tests': ab_count,
            'tracked_sources': source_count,
            'avg_source_trust': round(avg_trust or 0.5, 3),
            'calibration_points': calib_count,
            'regression_tests': reg_tests,
            'latest_regression': dict(latest_run) if latest_run else None,
            'topic_clusters': cluster_count,
            'open_escalations': open_escalations,
            'prediction_accuracy': pred_accuracy,
            # Enterprise metrics
            'pipeline_requests_tracked': pipeline_count,
            'total_cost_usd': round(total_cost or 0, 4),
            'active_anomalies': anomaly_count,
            'active_alerts': alert_count,
            'open_circuit_breakers': open_breakers,
            'prompt_versions': prompt_versions,
            'knowledge_gaps': gap_count,
            'system_health_score': health_score,
            'system_health_status': health_status,
            # Anthropic-grade metrics
            'feature_flags_enabled': feature_flags_count,
            'rate_limit_blocked': rate_limit_status.get('blocked_requests_total', 0),
            'budget_daily_pct': budget_status.get('daily_pct', 0),
            'budget_monthly_pct': budget_status.get('monthly_pct', 0),
            'training_ready': training_ready,
            'recent_events': [dict(e) for e in recent_events]
        }
    except Exception as e:
        logger.error(f"Overview error: {e}")
        return {'error': str(e)}


# Initialize tables on import
try:
    init_intelligence_tables()
except Exception as e:
    logger.error(f"Failed to initialize intelligence tables: {e}")

# Initialize default alert rules
try:
    AlertEngine.init_default_rules()
except Exception as e:
    logger.error(f"Failed to initialize alert rules: {e}")

# Initialize default feature flags
try:
    FeatureFlags.init_defaults()
except Exception as e:
    logger.error(f"Failed to initialize feature flags: {e}")
