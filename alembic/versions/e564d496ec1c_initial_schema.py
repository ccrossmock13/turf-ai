"""Initial schema — captures all existing tables.

Sources:
  - chat_history.py       (conversations, messages, users, course_profiles,
                            spray_applications, custom_products, sprayers,
                            user_inventory, spray_templates, inventory_quantities)
  - feedback_system.py    (feedback, training_examples, training_runs,
                            moderator_actions)
  - intelligence/db.py    (golden_answers, answer_versions, ab_tests,
                            ab_test_results, source_reliability,
                            confidence_calibration, regression_tests,
                            regression_runs, regression_results,
                            topic_clusters, question_topics, topic_metrics,
                            satisfaction_predictions, escalation_queue,
                            intelligence_events, pipeline_metrics,
                            cost_ledger, cost_budgets, anomaly_detections,
                            metric_baselines, alert_rules, alert_history,
                            remediation_actions, circuit_breakers,
                            prompt_templates, prompt_usage_log,
                            knowledge_gaps, content_freshness,
                            conversation_analytics, feature_flags,
                            retention_log, query_moderation)
  - fine_tuning.py        (source_quality, eval_runs)

Revision ID: e564d496ec1c
Revises:
Create Date: 2026-02-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e564d496ec1c"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_sqlite() -> bool:
    """Return True when running against SQLite."""
    return op.get_bind().dialect.name == "sqlite"


def _auto_pk():
    """Return the appropriate auto-increment PK column.

    SQLite  : INTEGER PRIMARY KEY AUTOINCREMENT
    Postgres: SERIAL (or BIGSERIAL) — sa.Integer + autoincrement=True
    Both work fine with sa.Column("id", sa.Integer, primary_key=True, autoincrement=True).
    """
    return sa.Column("id", sa.Integer, primary_key=True, autoincrement=True)


def _ts_default():
    """CURRENT_TIMESTAMP default usable on both dialects."""
    return sa.text("CURRENT_TIMESTAMP")


# ---------------------------------------------------------------------------
# upgrade
# ---------------------------------------------------------------------------

def upgrade() -> None:
    # ==================================================================
    # chat_history.py tables  (greenside_conversations.db)
    # ==================================================================

    op.create_table(
        "conversations",
        _auto_pk(),
        sa.Column("session_id", sa.Text, nullable=False),
        sa.Column("created_at", sa.TIMESTAMP, server_default=_ts_default()),
        sa.Column("last_active", sa.TIMESTAMP, server_default=_ts_default()),
        sa.Column("user_info", sa.Text),
        sa.Column("user_id", sa.Integer),
    )
    op.create_index("idx_session", "conversations", ["session_id"])
    op.create_index("idx_conv_user", "conversations", ["user_id"])

    op.create_table(
        "users",
        _auto_pk(),
        sa.Column("email", sa.Text, nullable=False, unique=True),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("created_at", sa.TIMESTAMP, server_default=_ts_default()),
        sa.Column("last_login", sa.TIMESTAMP),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("1")),
    )
    op.create_index("idx_users_email", "users", ["email"])

    op.create_table(
        "messages",
        _auto_pk(),
        sa.Column("conversation_id", sa.Integer, nullable=False),
        sa.Column("role", sa.Text, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("sources", sa.Text),
        sa.Column("confidence_score", sa.Float),
        sa.Column("timestamp", sa.TIMESTAMP, server_default=_ts_default()),
    )
    op.create_index("idx_conv_time", "messages", ["conversation_id", "timestamp"])

    op.create_table(
        "course_profiles",
        _auto_pk(),
        sa.Column("user_id", sa.Integer, nullable=False, unique=True),
        sa.Column("course_name", sa.Text),
        sa.Column("city", sa.Text),
        sa.Column("state", sa.Text),
        sa.Column("region", sa.Text),
        sa.Column("primary_grass", sa.Text),
        sa.Column("secondary_grasses", sa.Text),
        sa.Column("turf_type", sa.Text),
        sa.Column("role", sa.Text),
        sa.Column("greens_grass", sa.Text),
        sa.Column("fairways_grass", sa.Text),
        sa.Column("rough_grass", sa.Text),
        sa.Column("tees_grass", sa.Text),
        sa.Column("soil_type", sa.Text),
        sa.Column("irrigation_source", sa.Text),
        sa.Column("mowing_heights", sa.Text),
        sa.Column("annual_n_budget", sa.Text),
        sa.Column("notes", sa.Text),
        sa.Column("cultivars", sa.Text),
        sa.Column("updated_at", sa.TIMESTAMP, server_default=_ts_default()),
        # Acreage columns (added via migration in chat_history.py)
        sa.Column("greens_acreage", sa.Float),
        sa.Column("fairways_acreage", sa.Float),
        sa.Column("rough_acreage", sa.Float),
        sa.Column("tees_acreage", sa.Float),
        # Sprayer config
        sa.Column("default_gpa", sa.Float),
        sa.Column("tank_size", sa.Float),
        # Soil / water quality
        sa.Column("soil_ph", sa.Float),
        sa.Column("soil_om", sa.Float),
        sa.Column("water_ph", sa.Float),
        sa.Column("water_ec", sa.Float),
        # Profile overhaul
        sa.Column("green_speed_target", sa.Float),
        sa.Column("budget_tier", sa.Text),
        sa.Column("climate_zone", sa.Text),
        sa.Column("common_problems", sa.Text),
        sa.Column("preferred_products", sa.Text),
        sa.Column("overseeding_program", sa.Text),
    )
    op.create_index("idx_profiles_user", "course_profiles", ["user_id"])

    # -- Spray tracker tables -----------------------------------------------

    op.create_table(
        "spray_applications",
        _auto_pk(),
        sa.Column("user_id", sa.Integer, nullable=False),
        sa.Column("date", sa.Text, nullable=False),
        sa.Column("area", sa.Text, nullable=False),
        sa.Column("product_id", sa.Text, nullable=False),
        sa.Column("product_name", sa.Text, nullable=False),
        sa.Column("product_category", sa.Text, nullable=False),
        sa.Column("rate", sa.Float, nullable=False),
        sa.Column("rate_unit", sa.Text, nullable=False),
        sa.Column("area_acreage", sa.Float, nullable=False),
        sa.Column("carrier_volume_gpa", sa.Float),
        sa.Column("total_product", sa.Float),
        sa.Column("total_product_unit", sa.Text),
        sa.Column("total_carrier_gallons", sa.Float),
        sa.Column("nutrients_applied", sa.Text),
        sa.Column("weather_temp", sa.Float),
        sa.Column("weather_wind", sa.Text),
        sa.Column("weather_conditions", sa.Text),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.TIMESTAMP, server_default=_ts_default()),
        # Columns added via migrations in chat_history.py
        sa.Column("products_json", sa.Text),
        sa.Column("application_method", sa.Text),
        sa.Column("efficacy_rating", sa.Integer),
        sa.Column("efficacy_notes", sa.Text),
    )
    op.create_index("idx_spray_user", "spray_applications", ["user_id"])
    op.create_index("idx_spray_date", "spray_applications", ["user_id", "date"])
    op.create_index("idx_spray_area", "spray_applications", ["user_id", "area"])

    op.create_table(
        "custom_products",
        _auto_pk(),
        sa.Column("user_id", sa.Integer, nullable=False),
        sa.Column("product_name", sa.Text, nullable=False),
        sa.Column("brand", sa.Text),
        sa.Column("product_type", sa.Text, nullable=False, server_default=sa.text("'fertilizer'")),
        sa.Column("npk", sa.Text),
        sa.Column("secondary_nutrients", sa.Text),
        sa.Column("form_type", sa.Text),
        sa.Column("density_lbs_per_gallon", sa.Float),
        sa.Column("sgn", sa.Integer),
        sa.Column("default_rate", sa.Float),
        sa.Column("rate_unit", sa.Text),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.TIMESTAMP, server_default=_ts_default()),
    )
    op.create_index("idx_custom_products_user", "custom_products", ["user_id"])

    op.create_table(
        "sprayers",
        _auto_pk(),
        sa.Column("user_id", sa.Integer, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("gpa", sa.Float, nullable=False),
        sa.Column("tank_size", sa.Float, nullable=False),
        sa.Column("nozzle_type", sa.Text),
        sa.Column("areas", sa.Text, nullable=False, server_default=sa.text("'[]'")),
        sa.Column("is_default", sa.Integer, server_default=sa.text("0")),
        sa.Column("created_at", sa.TIMESTAMP, server_default=_ts_default()),
    )
    op.create_index("idx_sprayers_user", "sprayers", ["user_id"])

    op.create_table(
        "user_inventory",
        _auto_pk(),
        sa.Column("user_id", sa.Integer, nullable=False),
        sa.Column("product_id", sa.Text, nullable=False),
        sa.Column("added_at", sa.TIMESTAMP, server_default=_ts_default()),
        sa.UniqueConstraint("user_id", "product_id"),
    )
    op.create_index("idx_inventory_user", "user_inventory", ["user_id"])

    op.create_table(
        "spray_templates",
        _auto_pk(),
        sa.Column("user_id", sa.Integer, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("products_json", sa.Text, nullable=False),
        sa.Column("application_method", sa.Text),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.TIMESTAMP, server_default=_ts_default()),
    )
    op.create_index("idx_templates_user", "spray_templates", ["user_id"])

    op.create_table(
        "inventory_quantities",
        _auto_pk(),
        sa.Column("user_id", sa.Integer, nullable=False),
        sa.Column("product_id", sa.Text, nullable=False),
        sa.Column("quantity", sa.Float, server_default=sa.text("0")),
        sa.Column("unit", sa.Text, server_default=sa.text("'lbs'")),
        sa.Column("supplier", sa.Text),
        sa.Column("cost_per_unit", sa.Float),
        sa.Column("notes", sa.Text),
        sa.Column("updated_at", sa.TIMESTAMP, server_default=_ts_default()),
        sa.UniqueConstraint("user_id", "product_id"),
    )
    op.create_index("idx_inv_qty_user", "inventory_quantities", ["user_id"])

    # ==================================================================
    # feedback_system.py tables  (greenside_feedback.db)
    # ==================================================================

    op.create_table(
        "feedback",
        _auto_pk(),
        sa.Column("question", sa.Text, nullable=False),
        sa.Column("ai_answer", sa.Text, nullable=False),
        sa.Column("user_rating", sa.Text, nullable=False),
        sa.Column("user_correction", sa.Text),
        sa.Column("sources", sa.Text),
        sa.Column("confidence_score", sa.Float),
        sa.Column("timestamp", sa.TIMESTAMP, server_default=_ts_default()),
        sa.Column("reviewed", sa.Boolean, server_default=sa.text("0")),
        sa.Column("approved_for_training", sa.Boolean, server_default=sa.text("0")),
        sa.Column("notes", sa.Text),
    )
    op.create_index("idx_rating", "feedback", ["user_rating"])
    op.create_index("idx_reviewed", "feedback", ["reviewed"])
    op.create_index("idx_approved", "feedback", ["approved_for_training"])

    op.create_table(
        "training_examples",
        _auto_pk(),
        sa.Column("feedback_id", sa.Integer, nullable=False),
        sa.Column("question", sa.Text, nullable=False),
        sa.Column("ideal_answer", sa.Text, nullable=False),
        sa.Column("created_at", sa.TIMESTAMP, server_default=_ts_default()),
        sa.Column("used_in_training", sa.Boolean, server_default=sa.text("0")),
        sa.Column("training_run_id", sa.Text),
    )

    op.create_table(
        "training_runs",
        _auto_pk(),
        sa.Column("run_id", sa.Text, nullable=False, unique=True),
        sa.Column("num_examples", sa.Integer, nullable=False),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("model_id", sa.Text),
        sa.Column("started_at", sa.TIMESTAMP, server_default=_ts_default()),
        sa.Column("completed_at", sa.TIMESTAMP),
        sa.Column("notes", sa.Text),
    )

    op.create_table(
        "moderator_actions",
        _auto_pk(),
        sa.Column("feedback_id", sa.Integer, nullable=False),
        sa.Column("action", sa.Text, nullable=False),
        sa.Column("moderator", sa.Text, server_default=sa.text("'admin'")),
        sa.Column("original_answer", sa.Text),
        sa.Column("corrected_answer", sa.Text),
        sa.Column("reason", sa.Text),
        sa.Column("timestamp", sa.TIMESTAMP, server_default=_ts_default()),
    )
    op.create_index("idx_mod_actions", "moderator_actions", ["feedback_id"])

    # ==================================================================
    # intelligence/db.py tables  (greenside_feedback.db)
    # ==================================================================

    # Subsystem 1: Self-Healing Knowledge Loop
    op.create_table(
        "golden_answers",
        _auto_pk(),
        sa.Column("question", sa.Text, nullable=False),
        sa.Column("answer", sa.Text, nullable=False),
        sa.Column("category", sa.Text),
        sa.Column("embedding", sa.Text),
        sa.Column("source_feedback_id", sa.Integer),
        sa.Column("created_by", sa.Text, server_default=sa.text("'admin'")),
        sa.Column("active", sa.Boolean, server_default=sa.text("1")),
        sa.Column("times_used", sa.Integer, server_default=sa.text("0")),
        sa.Column("avg_rating_when_used", sa.Float),
        sa.Column("created_at", sa.TIMESTAMP, server_default=_ts_default()),
        sa.Column("updated_at", sa.TIMESTAMP, server_default=_ts_default()),
    )
    op.create_index("idx_golden_category", "golden_answers", ["category"])
    op.create_index("idx_golden_active", "golden_answers", ["active"])

    # Subsystem 2: Answer Versioning & A/B Testing
    op.create_table(
        "answer_versions",
        _auto_pk(),
        sa.Column("pattern", sa.Text, nullable=False),
        sa.Column("answer_template", sa.Text, nullable=False),
        sa.Column("strategy", sa.Text, server_default=sa.text("'default'")),
        sa.Column("metadata", sa.Text),
        sa.Column("performance_score", sa.Float, server_default=sa.text("0.0")),
        sa.Column("times_served", sa.Integer, server_default=sa.text("0")),
        sa.Column("avg_rating", sa.Float),
        sa.Column("created_at", sa.TIMESTAMP, server_default=_ts_default()),
    )

    op.create_table(
        "ab_tests",
        _auto_pk(),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("pattern", sa.Text, nullable=False),
        sa.Column("version_ids", sa.Text, nullable=False),
        sa.Column("traffic_split", sa.Text, nullable=False),
        sa.Column("status", sa.Text, server_default=sa.text("'active'")),
        sa.Column("total_impressions", sa.Integer, server_default=sa.text("0")),
        sa.Column("created_at", sa.TIMESTAMP, server_default=_ts_default()),
        sa.Column("ended_at", sa.TIMESTAMP),
        sa.Column("winner_version_id", sa.Integer),
    )
    op.create_index("idx_ab_status", "ab_tests", ["status"])

    op.create_table(
        "ab_test_results",
        _auto_pk(),
        sa.Column("test_id", sa.Integer, nullable=False),
        sa.Column("version_id", sa.Integer, nullable=False),
        sa.Column("query_id", sa.Integer),
        sa.Column("user_id", sa.Text),
        sa.Column("rating", sa.Text),
        sa.Column("confidence", sa.Float),
        sa.Column("timestamp", sa.TIMESTAMP, server_default=_ts_default()),
    )

    # Subsystem 3: Source Quality Intelligence
    op.create_table(
        "source_reliability",
        _auto_pk(),
        sa.Column("source_id", sa.Text, nullable=False, unique=True),
        sa.Column("source_title", sa.Text),
        sa.Column("source_type", sa.Text),
        sa.Column("trust_score", sa.Float, server_default=sa.text("0.5")),
        sa.Column("positive_count", sa.Integer, server_default=sa.text("0")),
        sa.Column("negative_count", sa.Integer, server_default=sa.text("0")),
        sa.Column("total_appearances", sa.Integer, server_default=sa.text("0")),
        sa.Column("avg_confidence_when_used", sa.Float),
        sa.Column("admin_boost", sa.Float, server_default=sa.text("0.0")),
        sa.Column("last_updated", sa.TIMESTAMP, server_default=_ts_default()),
    )
    op.create_index("idx_source_trust", "source_reliability", ["trust_score"])
    op.create_index("idx_source_id", "source_reliability", ["source_id"])

    # Subsystem 4: Confidence Calibration
    op.create_table(
        "confidence_calibration",
        _auto_pk(),
        sa.Column("query_id", sa.Integer),
        sa.Column("predicted_confidence", sa.Float, nullable=False),
        sa.Column("actual_rating", sa.Text),
        sa.Column("actual_satisfaction", sa.Float),
        sa.Column("topic", sa.Text),
        sa.Column("category", sa.Text),
        sa.Column("timestamp", sa.TIMESTAMP, server_default=_ts_default()),
    )
    op.create_index("idx_calib_topic", "confidence_calibration", ["topic"])

    # Subsystem 5: Regression Detection
    op.create_table(
        "regression_tests",
        _auto_pk(),
        sa.Column("question", sa.Text, nullable=False),
        sa.Column("expected_answer", sa.Text, nullable=False),
        sa.Column("category", sa.Text),
        sa.Column("criteria", sa.Text),
        sa.Column("priority", sa.Integer, server_default=sa.text("1")),
        sa.Column("active", sa.Boolean, server_default=sa.text("1")),
        sa.Column("created_at", sa.TIMESTAMP, server_default=_ts_default()),
        sa.Column("created_by", sa.Text, server_default=sa.text("'admin'")),
    )
    op.create_index("idx_regression_active", "regression_tests", ["active"])

    op.create_table(
        "regression_runs",
        _auto_pk(),
        sa.Column("trigger", sa.Text, server_default=sa.text("'scheduled'")),
        sa.Column("total_tests", sa.Integer, server_default=sa.text("0")),
        sa.Column("passed", sa.Integer, server_default=sa.text("0")),
        sa.Column("warned", sa.Integer, server_default=sa.text("0")),
        sa.Column("failed", sa.Integer, server_default=sa.text("0")),
        sa.Column("avg_drift_score", sa.Float),
        sa.Column("started_at", sa.TIMESTAMP, server_default=_ts_default()),
        sa.Column("completed_at", sa.TIMESTAMP),
        sa.Column("status", sa.Text, server_default=sa.text("'running'")),
    )

    op.create_table(
        "regression_results",
        _auto_pk(),
        sa.Column("run_id", sa.Integer, nullable=False),
        sa.Column("test_id", sa.Integer, nullable=False),
        sa.Column("actual_answer", sa.Text),
        sa.Column("confidence", sa.Float),
        sa.Column("drift_score", sa.Float),
        sa.Column("status", sa.Text),
        sa.Column("issues", sa.Text),
        sa.Column("timestamp", sa.TIMESTAMP, server_default=_ts_default()),
    )

    # Subsystem 6: Topic Clustering
    op.create_table(
        "topic_clusters",
        _auto_pk(),
        sa.Column("name", sa.Text),
        sa.Column("description", sa.Text),
        sa.Column("centroid_embedding", sa.Text),
        sa.Column("question_count", sa.Integer, server_default=sa.text("0")),
        sa.Column("avg_confidence", sa.Float),
        sa.Column("avg_satisfaction", sa.Float),
        sa.Column("negative_rate", sa.Float, server_default=sa.text("0.0")),
        sa.Column("trend_direction", sa.Text, server_default=sa.text("'stable'")),
        sa.Column("first_seen", sa.TIMESTAMP, server_default=_ts_default()),
        sa.Column("last_seen", sa.TIMESTAMP, server_default=_ts_default()),
        sa.Column("active", sa.Boolean, server_default=sa.text("1")),
    )
    op.create_index("idx_cluster_active", "topic_clusters", ["active"])

    op.create_table(
        "question_topics",
        _auto_pk(),
        sa.Column("query_id", sa.Integer),
        sa.Column("question", sa.Text, nullable=False),
        sa.Column("cluster_id", sa.Integer),
        sa.Column("similarity_score", sa.Float),
        sa.Column("embedding", sa.Text),
        sa.Column("timestamp", sa.TIMESTAMP, server_default=_ts_default()),
    )
    op.create_index("idx_qt_cluster", "question_topics", ["cluster_id"])

    op.create_table(
        "topic_metrics",
        _auto_pk(),
        sa.Column("cluster_id", sa.Integer, nullable=False),
        sa.Column("period_start", sa.TIMESTAMP, nullable=False),
        sa.Column("period_end", sa.TIMESTAMP, nullable=False),
        sa.Column("question_count", sa.Integer, server_default=sa.text("0")),
        sa.Column("avg_confidence", sa.Float),
        sa.Column("avg_satisfaction", sa.Float),
        sa.Column("negative_count", sa.Integer, server_default=sa.text("0")),
        sa.Column("positive_count", sa.Integer, server_default=sa.text("0")),
    )

    # Subsystem 7: Satisfaction Prediction
    op.create_table(
        "satisfaction_predictions",
        _auto_pk(),
        sa.Column("query_id", sa.Integer),
        sa.Column("predicted_probability", sa.Float, nullable=False),
        sa.Column("features", sa.Text),
        sa.Column("actual_rating", sa.Text),
        sa.Column("was_correct", sa.Boolean),
        sa.Column("model_version", sa.Integer, server_default=sa.text("1")),
        sa.Column("timestamp", sa.TIMESTAMP, server_default=_ts_default()),
    )

    # Subsystem 8: Smart Escalation
    op.create_table(
        "escalation_queue",
        _auto_pk(),
        sa.Column("query_id", sa.Integer),
        sa.Column("question", sa.Text, nullable=False),
        sa.Column("answer", sa.Text, nullable=False),
        sa.Column("failure_mode", sa.Text),
        sa.Column("failure_details", sa.Text),
        sa.Column("predicted_satisfaction", sa.Float),
        sa.Column("confidence", sa.Float),
        sa.Column("suggested_fix", sa.Text),
        sa.Column("similar_approved_ids", sa.Text),
        sa.Column("priority", sa.Integer, server_default=sa.text("5")),
        sa.Column("status", sa.Text, server_default=sa.text("'open'")),
        sa.Column("resolved_by", sa.Text),
        sa.Column("resolution_action", sa.Text),
        sa.Column("resolution_notes", sa.Text),
        sa.Column("created_at", sa.TIMESTAMP, server_default=_ts_default()),
        sa.Column("resolved_at", sa.TIMESTAMP),
    )
    op.create_index("idx_escalation_status", "escalation_queue", ["status"])
    op.create_index("idx_escalation_priority", "escalation_queue", ["priority"])

    # Audit Log
    op.create_table(
        "intelligence_events",
        _auto_pk(),
        sa.Column("subsystem", sa.Text, nullable=False),
        sa.Column("event_type", sa.Text, nullable=False),
        sa.Column("details", sa.Text),
        sa.Column("severity", sa.Text, server_default=sa.text("'info'")),
        sa.Column("timestamp", sa.TIMESTAMP, server_default=_ts_default()),
    )
    op.create_index("idx_events_subsystem", "intelligence_events", ["subsystem"])
    op.create_index("idx_events_time", "intelligence_events", ["timestamp"])

    # Subsystem 9: Pipeline Analytics & Cost Intelligence
    op.create_table(
        "pipeline_metrics",
        _auto_pk(),
        sa.Column("query_id", sa.Integer),
        sa.Column("total_latency_ms", sa.Float),
        sa.Column("step_timings", sa.Text),
        sa.Column("prompt_tokens", sa.Integer, server_default=sa.text("0")),
        sa.Column("completion_tokens", sa.Integer, server_default=sa.text("0")),
        sa.Column("total_tokens", sa.Integer, server_default=sa.text("0")),
        sa.Column("model", sa.Text),
        sa.Column("cost_usd", sa.Float, server_default=sa.text("0.0")),
        sa.Column("grounding_tokens", sa.Integer, server_default=sa.text("0")),
        sa.Column("grounding_cost_usd", sa.Float, server_default=sa.text("0.0")),
        sa.Column("embedding_tokens", sa.Integer, server_default=sa.text("0")),
        sa.Column("embedding_cost_usd", sa.Float, server_default=sa.text("0.0")),
        sa.Column("total_cost_usd", sa.Float, server_default=sa.text("0.0")),
        sa.Column("timestamp", sa.TIMESTAMP, server_default=_ts_default()),
    )
    op.create_index("idx_pipeline_query", "pipeline_metrics", ["query_id"])
    op.create_index("idx_pipeline_time", "pipeline_metrics", ["timestamp"])

    op.create_table(
        "cost_ledger",
        _auto_pk(),
        sa.Column("period_type", sa.Text, nullable=False),
        sa.Column("period_key", sa.Text, nullable=False),
        sa.Column("model", sa.Text),
        sa.Column("total_requests", sa.Integer, server_default=sa.text("0")),
        sa.Column("total_prompt_tokens", sa.Integer, server_default=sa.text("0")),
        sa.Column("total_completion_tokens", sa.Integer, server_default=sa.text("0")),
        sa.Column("total_cost_usd", sa.Float, server_default=sa.text("0.0")),
        sa.Column("avg_cost_per_request", sa.Float, server_default=sa.text("0.0")),
        sa.Column("updated_at", sa.TIMESTAMP, server_default=_ts_default()),
        sa.UniqueConstraint("period_type", "period_key", "model"),
    )
    op.create_index("idx_cost_ledger_period", "cost_ledger", ["period_type", "period_key"])

    op.create_table(
        "cost_budgets",
        _auto_pk(),
        sa.Column("budget_type", sa.Text, nullable=False, unique=True),
        sa.Column("budget_usd", sa.Float, nullable=False),
        sa.Column("current_spend_usd", sa.Float, server_default=sa.text("0.0")),
        sa.Column("alert_threshold_pct", sa.Float, server_default=sa.text("80.0")),
        sa.Column("alert_sent", sa.Boolean, server_default=sa.text("0")),
        sa.Column("period_start", sa.TIMESTAMP),
        sa.Column("updated_at", sa.TIMESTAMP, server_default=_ts_default()),
    )

    # Subsystem 10: Anomaly Detection
    op.create_table(
        "anomaly_detections",
        _auto_pk(),
        sa.Column("metric", sa.Text, nullable=False),
        sa.Column("detection_method", sa.Text, nullable=False),
        sa.Column("current_value", sa.Float),
        sa.Column("baseline_mean", sa.Float),
        sa.Column("baseline_std", sa.Float),
        sa.Column("z_score", sa.Float),
        sa.Column("severity", sa.Text, server_default=sa.text("'info'")),
        sa.Column("message", sa.Text),
        sa.Column("acknowledged", sa.Boolean, server_default=sa.text("0")),
        sa.Column("timestamp", sa.TIMESTAMP, server_default=_ts_default()),
    )
    op.create_index("idx_anomaly_metric", "anomaly_detections", ["metric"])
    op.create_index("idx_anomaly_severity", "anomaly_detections", ["severity"])
    op.create_index("idx_anomaly_time", "anomaly_detections", ["timestamp"])

    op.create_table(
        "metric_baselines",
        _auto_pk(),
        sa.Column("metric", sa.Text, nullable=False, unique=True),
        sa.Column("mean", sa.Float),
        sa.Column("std", sa.Float),
        sa.Column("min_val", sa.Float),
        sa.Column("max_val", sa.Float),
        sa.Column("sample_count", sa.Integer, server_default=sa.text("0")),
        sa.Column("last_computed", sa.TIMESTAMP, server_default=_ts_default()),
    )

    # Subsystem 11: Alert System
    op.create_table(
        "alert_rules",
        _auto_pk(),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("metric", sa.Text, nullable=False),
        sa.Column("condition", sa.Text, nullable=False),
        sa.Column("threshold", sa.Float, nullable=False),
        sa.Column("channels", sa.Text, server_default=sa.text("'[\"in_app\"]'")),
        sa.Column("cooldown_minutes", sa.Integer, server_default=sa.text("60")),
        sa.Column("enabled", sa.Boolean, server_default=sa.text("1")),
        sa.Column("last_fired", sa.TIMESTAMP),
        sa.Column("fire_count", sa.Integer, server_default=sa.text("0")),
        sa.Column("created_at", sa.TIMESTAMP, server_default=_ts_default()),
    )
    op.create_index("idx_alert_rule_metric", "alert_rules", ["metric"])

    op.create_table(
        "alert_history",
        _auto_pk(),
        sa.Column("rule_id", sa.Integer),
        sa.Column("rule_name", sa.Text),
        sa.Column("metric", sa.Text),
        sa.Column("current_value", sa.Float),
        sa.Column("threshold", sa.Float),
        sa.Column("channel", sa.Text),
        sa.Column("message", sa.Text),
        sa.Column("delivered", sa.Boolean, server_default=sa.text("1")),
        sa.Column("acknowledged", sa.Boolean, server_default=sa.text("0")),
        sa.Column("timestamp", sa.TIMESTAMP, server_default=_ts_default()),
    )
    op.create_index("idx_alert_history_time", "alert_history", ["timestamp"])
    op.create_index("idx_alert_history_rule", "alert_history", ["rule_id"])

    # Subsystem 12: Remediation & Circuit Breakers
    op.create_table(
        "remediation_actions",
        _auto_pk(),
        sa.Column("trigger_type", sa.Text, nullable=False),
        sa.Column("action_type", sa.Text, nullable=False),
        sa.Column("target", sa.Text),
        sa.Column("before_state", sa.Text),
        sa.Column("after_state", sa.Text),
        sa.Column("auto", sa.Boolean, server_default=sa.text("1")),
        sa.Column("success", sa.Boolean, server_default=sa.text("1")),
        sa.Column("details", sa.Text),
        sa.Column("timestamp", sa.TIMESTAMP, server_default=_ts_default()),
    )
    op.create_index("idx_remediation_time", "remediation_actions", ["timestamp"])

    op.create_table(
        "circuit_breakers",
        _auto_pk(),
        sa.Column("source_id", sa.Text, nullable=False, unique=True),
        sa.Column("state", sa.Text, server_default=sa.text("'closed'")),
        sa.Column("failure_count", sa.Integer, server_default=sa.text("0")),
        sa.Column("last_failure", sa.TIMESTAMP),
        sa.Column("opened_at", sa.TIMESTAMP),
        sa.Column("recovery_at", sa.TIMESTAMP),
        sa.Column("total_trips", sa.Integer, server_default=sa.text("0")),
        sa.Column("updated_at", sa.TIMESTAMP, server_default=_ts_default()),
    )
    op.create_index("idx_circuit_source", "circuit_breakers", ["source_id"])
    op.create_index("idx_circuit_state", "circuit_breakers", ["state"])

    # Subsystem 13: Prompt Versioning
    op.create_table(
        "prompt_templates",
        _auto_pk(),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("template_hash", sa.Text, nullable=False),
        sa.Column("template_text", sa.Text, nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("changes", sa.Text),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("0")),
        sa.Column("total_queries", sa.Integer, server_default=sa.text("0")),
        sa.Column("avg_confidence", sa.Float),
        sa.Column("avg_satisfaction", sa.Float),
        sa.Column("created_by", sa.Text, server_default=sa.text("'system'")),
        sa.Column("created_at", sa.TIMESTAMP, server_default=_ts_default()),
        sa.Column("activated_at", sa.TIMESTAMP),
        sa.Column("deactivated_at", sa.TIMESTAMP),
    )
    op.create_index("idx_prompt_active", "prompt_templates", ["is_active"])
    op.create_index("idx_prompt_version", "prompt_templates", ["version"])

    op.create_table(
        "prompt_usage_log",
        _auto_pk(),
        sa.Column("version_id", sa.Integer, nullable=False),
        sa.Column("query_id", sa.Integer),
        sa.Column("confidence", sa.Float),
        sa.Column("satisfaction_rating", sa.Text),
        sa.Column("timestamp", sa.TIMESTAMP, server_default=_ts_default()),
    )

    # Subsystem 15: Knowledge Gaps
    op.create_table(
        "knowledge_gaps",
        _auto_pk(),
        sa.Column("topic", sa.Text, nullable=False),
        sa.Column("category", sa.Text),
        sa.Column("gap_type", sa.Text, nullable=False),
        sa.Column("severity", sa.Text, server_default=sa.text("'medium'")),
        sa.Column("avg_confidence", sa.Float),
        sa.Column("avg_source_count", sa.Float),
        sa.Column("question_count", sa.Integer, server_default=sa.text("0")),
        sa.Column("sample_questions", sa.Text),
        sa.Column("recommended_action", sa.Text),
        sa.Column("status", sa.Text, server_default=sa.text("'open'")),
        sa.Column("resolved_at", sa.TIMESTAMP),
        sa.Column("detected_at", sa.TIMESTAMP, server_default=_ts_default()),
    )
    op.create_index("idx_knowledge_gap_status", "knowledge_gaps", ["status"])

    op.create_table(
        "content_freshness",
        _auto_pk(),
        sa.Column("source_id", sa.Text, nullable=False, unique=True),
        sa.Column("source_title", sa.Text),
        sa.Column("last_cited", sa.TIMESTAMP),
        sa.Column("citation_count", sa.Integer, server_default=sa.text("0")),
        sa.Column("days_since_cited", sa.Integer, server_default=sa.text("0")),
        sa.Column("freshness_score", sa.Float, server_default=sa.text("1.0")),
        sa.Column("status", sa.Text, server_default=sa.text("'fresh'")),
        sa.Column("updated_at", sa.TIMESTAMP, server_default=_ts_default()),
    )
    op.create_index("idx_cf_source_id", "content_freshness", ["source_id"], unique=True)
    op.create_index("idx_content_fresh_status", "content_freshness", ["status"])

    # Subsystem 17: Conversation Intelligence
    op.create_table(
        "conversation_analytics",
        _auto_pk(),
        sa.Column("conversation_id", sa.Text, nullable=False),
        sa.Column("turn_count", sa.Integer, server_default=sa.text("0")),
        sa.Column("unique_topics", sa.Integer, server_default=sa.text("0")),
        sa.Column("avg_confidence", sa.Float),
        sa.Column("min_confidence", sa.Float),
        sa.Column("resolution_status", sa.Text, server_default=sa.text("'unknown'")),
        sa.Column("frustration_score", sa.Float, server_default=sa.text("0.0")),
        sa.Column("frustration_signals", sa.Text),
        sa.Column("topic_drift_score", sa.Float, server_default=sa.text("0.0")),
        sa.Column("total_latency_ms", sa.Float, server_default=sa.text("0.0")),
        sa.Column("total_cost_usd", sa.Float, server_default=sa.text("0.0")),
        sa.Column("first_message", sa.TIMESTAMP),
        sa.Column("last_message", sa.TIMESTAMP),
        sa.Column("analyzed_at", sa.TIMESTAMP, server_default=_ts_default()),
    )
    op.create_index("idx_conv_analytics_cid", "conversation_analytics", ["conversation_id"])

    # Anthropic-Grade: Feature Flags
    op.create_table(
        "feature_flags",
        _auto_pk(),
        sa.Column("flag_name", sa.Text, nullable=False, unique=True),
        sa.Column("enabled", sa.Boolean, server_default=sa.text("1")),
        sa.Column("description", sa.Text),
        sa.Column("updated_at", sa.TIMESTAMP, server_default=_ts_default()),
        sa.Column("updated_by", sa.Text, server_default=sa.text("'system'")),
    )
    op.create_index("idx_feature_flags_name", "feature_flags", ["flag_name"])

    # Anthropic-Grade: Data Retention Log
    op.create_table(
        "retention_log",
        _auto_pk(),
        sa.Column("table_name", sa.Text, nullable=False),
        sa.Column("rows_deleted", sa.Integer, server_default=sa.text("0")),
        sa.Column("ttl_days", sa.Integer),
        sa.Column("timestamp", sa.TIMESTAMP, server_default=_ts_default()),
    )
    op.create_index("idx_retention_log_time", "retention_log", ["timestamp"])

    # Anthropic-Grade: Query Moderation Log
    op.create_table(
        "query_moderation",
        _auto_pk(),
        sa.Column("query", sa.Text, nullable=False),
        sa.Column("score", sa.Float, server_default=sa.text("0")),
        sa.Column("patterns_matched", sa.Text),
        sa.Column("action", sa.Text, server_default=sa.text("'blocked'")),
        sa.Column("ip_address", sa.Text),
        sa.Column("timestamp", sa.TIMESTAMP, server_default=_ts_default()),
    )
    op.create_index("idx_query_moderation_time", "query_moderation", ["timestamp"])

    # ==================================================================
    # fine_tuning.py tables  (greenside_feedback.db)
    # ==================================================================

    op.create_table(
        "source_quality",
        _auto_pk(),
        sa.Column("source_name", sa.Text, nullable=False),
        sa.Column("source_url", sa.Text, unique=True),
        sa.Column("positive_count", sa.Integer, server_default=sa.text("0")),
        sa.Column("negative_count", sa.Integer, server_default=sa.text("0")),
        sa.Column("quality_score", sa.Float, server_default=sa.text("0.5")),
        sa.Column("last_updated", sa.TIMESTAMP, server_default=_ts_default()),
    )

    op.create_table(
        "eval_runs",
        _auto_pk(),
        sa.Column("run_date", sa.TIMESTAMP, server_default=_ts_default()),
        sa.Column("total_questions", sa.Integer),
        sa.Column("avg_overall_score", sa.Float),
        sa.Column("avg_confidence", sa.Float),
        sa.Column("avg_keyword_score", sa.Float),
        sa.Column("details", sa.Text),
    )


# ---------------------------------------------------------------------------
# downgrade
# ---------------------------------------------------------------------------

def downgrade() -> None:
    # Drop in reverse order to respect any implicit FK ordering.
    tables = [
        "eval_runs",
        "source_quality",
        "query_moderation",
        "retention_log",
        "feature_flags",
        "conversation_analytics",
        "content_freshness",
        "knowledge_gaps",
        "prompt_usage_log",
        "prompt_templates",
        "circuit_breakers",
        "remediation_actions",
        "alert_history",
        "alert_rules",
        "metric_baselines",
        "anomaly_detections",
        "cost_budgets",
        "cost_ledger",
        "pipeline_metrics",
        "intelligence_events",
        "escalation_queue",
        "satisfaction_predictions",
        "topic_metrics",
        "question_topics",
        "topic_clusters",
        "regression_results",
        "regression_runs",
        "regression_tests",
        "confidence_calibration",
        "source_reliability",
        "ab_test_results",
        "ab_tests",
        "answer_versions",
        "golden_answers",
        "moderator_actions",
        "training_runs",
        "training_examples",
        "feedback",
        "inventory_quantities",
        "spray_templates",
        "user_inventory",
        "sprayers",
        "custom_products",
        "spray_applications",
        "course_profiles",
        "messages",
        "users",
        "conversations",
    ]
    for table in tables:
        op.drop_table(table)
