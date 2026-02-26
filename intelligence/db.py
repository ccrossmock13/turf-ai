"""
Intelligence Engine — Database layer
=====================================
DB_PATH, init_intelligence_tables(), _get_conn(), log_event()
"""

import os
import logging
from datetime import datetime
from db import get_db, FEEDBACK_DB, is_postgres

logger = logging.getLogger(__name__)

# Database path — same DB as feedback system
DATA_DIR = os.environ.get('DATA_DIR', 'data' if os.path.exists('data') else '.')
DB_PATH = FEEDBACK_DB


def init_intelligence_tables():
    """Initialize all 15 intelligence engine tables."""
    with get_db(FEEDBACK_DB) as conn:
        _create_intelligence_tables(conn)


def _create_intelligence_tables(conn):
    """Internal: create all intelligence tables on the given connection."""
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
            source_id TEXT NOT NULL UNIQUE,
            source_title TEXT,
            last_cited TIMESTAMP,
            citation_count INTEGER DEFAULT 0,
            days_since_cited INTEGER DEFAULT 0,
            freshness_score REAL DEFAULT 1.0,
            status TEXT DEFAULT 'fresh',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_cf_source_id ON content_freshness(source_id)')

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

    logger.info("Intelligence engine tables initialized (33 tables)")


def log_event(subsystem: str, event_type: str, details: str = None, severity: str = 'info'):
    """Log an intelligence event for audit trail."""
    try:
        with get_db(FEEDBACK_DB) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO intelligence_events (subsystem, event_type, details, severity)
                VALUES (?, ?, ?, ?)
            ''', (subsystem, event_type, details, severity))
    except Exception as e:
        logger.error(f"Failed to log event: {e}")


def _get_conn():
    """Get a database connection with row factory and WAL mode."""
    from db import connect
    return connect(FEEDBACK_DB)
