"""
Intelligence Engine API blueprint.

Extracted from app.py — contains all /api/intelligence/* routes:
  - Overview, events, golden-answers, weak-patterns
  - A/B testing, answer versions
  - Source quality intelligence
  - Confidence calibration
  - Regression detection
  - Topic clustering
  - Satisfaction prediction
  - Smart escalation
  - Promote to golden
  - Pipeline analytics & cost
  - Anomaly detection
  - Alert system (rules CRUD)
  - Remediation & circuit breakers
  - Prompt versioning
  - Knowledge gaps & content freshness
  - Executive dashboard
  - Gradient boosted predictor
  - Conversation intelligence
  - Feature flags
  - Data retention
  - Rate limiting status
  - Cost budget
  - Training readiness
  - Input sanitization
"""

import json

from flask import Blueprint, jsonify, request

from config import Config
from intelligence_engine import (
    ABTestingEngine,
    AlertEngine,
    AnomalyDetector,
    CircuitBreaker,
    ConfidenceCalibration,
    ConversationIntelligence,
    DataRetentionManager,
    ExecutiveDashboard,
    FeatureFlags,
    GradientBoostedPredictor,
    InputSanitizer,
    KnowledgeGapAnalyzer,
    PipelineAnalytics,
    PromptVersioning,
    RateLimiter,
    RegressionDetector,
    RemediationEngine,
    SatisfactionPredictor,
    SelfHealingLoop,
    SmartEscalation,
    SourceQualityIntelligence,
    TopicIntelligence,
    TrainingOrchestrator,
    get_intelligence_overview,
)

intelligence_bp = Blueprint("intelligence", __name__)


# ---------------------------------------------------------------------------
# Overview & Events
# ---------------------------------------------------------------------------


@intelligence_bp.route("/api/intelligence/overview")
def intelligence_overview():
    """Get high-level intelligence dashboard data."""
    return jsonify(get_intelligence_overview())


@intelligence_bp.route("/api/intelligence/events")
def intelligence_events():
    """Get recent intelligence events (audit log)."""
    from intelligence_engine import _get_conn

    limit = request.args.get("limit", 50, type=int)
    subsystem = request.args.get("subsystem")
    conn = _get_conn()
    if subsystem:
        rows = conn.execute(
            "SELECT * FROM intelligence_events WHERE subsystem = ? ORDER BY timestamp DESC LIMIT ?", (subsystem, limit)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM intelligence_events ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


# ---------------------------------------------------------------------------
# Self-Healing Knowledge Loop
# ---------------------------------------------------------------------------


@intelligence_bp.route("/api/intelligence/golden-answers")
def get_golden_answers():
    """Get all golden answers."""
    include_inactive = request.args.get("include_inactive", "false") == "true"
    return jsonify(SelfHealingLoop.get_all_golden_answers(include_inactive))


@intelligence_bp.route("/api/intelligence/golden-answers", methods=["POST"])
def create_golden_answer():
    """Create a new golden answer."""
    data = request.json
    golden_id = SelfHealingLoop.create_golden_answer(
        question=data["question"],
        answer=data["answer"],
        category=data.get("category"),
        source_feedback_id=data.get("source_feedback_id"),
    )
    return jsonify({"success": True, "id": golden_id})


@intelligence_bp.route("/api/intelligence/golden-answers/<int:golden_id>", methods=["PUT"])
def update_golden_answer(golden_id):
    """Update a golden answer."""
    data = request.json
    success = SelfHealingLoop.update_golden_answer(golden_id, **data)
    return jsonify({"success": success})


@intelligence_bp.route("/api/intelligence/golden-answers/<int:golden_id>", methods=["DELETE"])
def delete_golden_answer(golden_id):
    """Soft-delete a golden answer."""
    success = SelfHealingLoop.delete_golden_answer(golden_id)
    return jsonify({"success": success})


@intelligence_bp.route("/api/intelligence/weak-patterns")
def get_weak_patterns():
    """Detect recurring low-quality answer patterns."""
    days = request.args.get("days", 30, type=int)
    min_occ = request.args.get("min_occurrences", 3, type=int)
    return jsonify(SelfHealingLoop.detect_weak_patterns(min_occ, days))


# ---------------------------------------------------------------------------
# A/B Testing
# ---------------------------------------------------------------------------


@intelligence_bp.route("/api/intelligence/ab-tests")
def get_ab_tests():
    """Get active A/B tests."""
    return jsonify(ABTestingEngine.get_active_tests())


@intelligence_bp.route("/api/intelligence/ab-tests", methods=["POST"])
def create_ab_test():
    """Create a new A/B test."""
    data = request.json
    test_id = ABTestingEngine.create_ab_test(
        name=data["name"],
        pattern=data["pattern"],
        version_ids=data["version_ids"],
        traffic_split=data.get("traffic_split"),
    )
    return jsonify({"success": True, "id": test_id})


@intelligence_bp.route("/api/intelligence/ab-tests/<int:test_id>/analyze")
def analyze_ab_test(test_id):
    """Analyze A/B test results with statistical significance."""
    return jsonify(ABTestingEngine.analyze_ab_test(test_id))


@intelligence_bp.route("/api/intelligence/ab-tests/<int:test_id>/end", methods=["POST"])
def end_ab_test(test_id):
    """End an A/B test."""
    data = request.json or {}
    ABTestingEngine.end_test(test_id, data.get("winner_version_id"))
    return jsonify({"success": True})


@intelligence_bp.route("/api/intelligence/answer-versions", methods=["POST"])
def create_answer_version():
    """Create an answer version for A/B testing."""
    data = request.json
    version_id = ABTestingEngine.create_answer_version(
        pattern=data["pattern"],
        answer_template=data["answer_template"],
        strategy=data.get("strategy", "default"),
        metadata=data.get("metadata"),
    )
    return jsonify({"success": True, "id": version_id})


# ---------------------------------------------------------------------------
# Source Quality Intelligence
# ---------------------------------------------------------------------------


@intelligence_bp.route("/api/intelligence/sources")
def get_source_leaderboard():
    """Get sources ranked by reliability."""
    limit = request.args.get("limit", 50, type=int)
    min_appearances = request.args.get("min_appearances", 3, type=int)
    return jsonify(SourceQualityIntelligence.get_source_leaderboard(limit, min_appearances))


@intelligence_bp.route("/api/intelligence/sources/<path:source_id>")
def get_source_detail(source_id):
    """Get reliability info for a specific source."""
    result = SourceQualityIntelligence.get_source_reliability(source_id)
    if result:
        return jsonify(result)
    return jsonify({"error": "Source not found"}), 404


@intelligence_bp.route("/api/intelligence/sources/<path:source_id>/boost", methods=["POST"])
def set_source_boost(source_id):
    """Admin boost/penalize a source."""
    data = request.json
    SourceQualityIntelligence.set_admin_boost(source_id, data.get("boost", 0.0))
    return jsonify({"success": True})


# ---------------------------------------------------------------------------
# Confidence Calibration
# ---------------------------------------------------------------------------


@intelligence_bp.route("/api/intelligence/calibration-report")
def get_calibration_report():
    """Get full confidence calibration report."""
    return jsonify(ConfidenceCalibration.get_calibration_report())


@intelligence_bp.route("/api/intelligence/calibration-curve")
def get_calibration_curve():
    """Get calibration curve for a specific topic."""
    topic = request.args.get("topic")
    return jsonify(ConfidenceCalibration.compute_calibration_curve(topic=topic))


# ---------------------------------------------------------------------------
# Regression Detection
# ---------------------------------------------------------------------------


@intelligence_bp.route("/api/intelligence/regression-tests")
def get_regression_tests():
    """Get all regression tests."""
    active_only = request.args.get("active_only", "true") == "true"
    return jsonify(RegressionDetector.get_regression_tests(active_only))


@intelligence_bp.route("/api/intelligence/regression-tests", methods=["POST"])
def add_regression_test():
    """Add a new regression test case."""
    data = request.json
    test_id = RegressionDetector.add_regression_test(
        question=data["question"],
        expected_answer=data["expected_answer"],
        category=data.get("category"),
        criteria=data.get("criteria"),
        priority=data.get("priority", 1),
    )
    return jsonify({"success": True, "id": test_id})


@intelligence_bp.route("/api/intelligence/regression-tests/<int:test_id>", methods=["PUT"])
def update_regression_test(test_id):
    """Update a regression test."""
    data = request.json
    success = RegressionDetector.update_regression_test(test_id, **data)
    return jsonify({"success": success})


@intelligence_bp.route("/api/intelligence/regression-tests/<int:test_id>", methods=["DELETE"])
def delete_regression_test(test_id):
    """Soft-delete a regression test."""
    success = RegressionDetector.delete_regression_test(test_id)
    return jsonify({"success": success})


@intelligence_bp.route("/api/intelligence/regression-dashboard")
def get_regression_dashboard():
    """Get regression testing dashboard."""
    return jsonify(RegressionDetector.get_regression_dashboard())


@intelligence_bp.route("/api/intelligence/regression-run", methods=["POST"])
def run_regression_suite():
    """Manually trigger a regression test run."""
    result = RegressionDetector.run_regression_suite(trigger="manual")
    return jsonify(result)


# ---------------------------------------------------------------------------
# Topic Clustering
# ---------------------------------------------------------------------------


@intelligence_bp.route("/api/intelligence/topics")
def get_topic_dashboard():
    """Get topic intelligence dashboard."""
    return jsonify(TopicIntelligence.get_topic_dashboard())


@intelligence_bp.route("/api/intelligence/topics/emerging")
def get_emerging_topics():
    """Get emerging topics."""
    days = request.args.get("days", 7, type=int)
    return jsonify(TopicIntelligence.detect_emerging_topics(days))


@intelligence_bp.route("/api/intelligence/topics/cluster", methods=["POST"])
def run_topic_clustering():
    """Manually trigger topic clustering."""
    result = TopicIntelligence.cluster_questions()
    return jsonify(result)


# ---------------------------------------------------------------------------
# Satisfaction Prediction
# ---------------------------------------------------------------------------


@intelligence_bp.route("/api/intelligence/satisfaction/accuracy")
def get_satisfaction_accuracy():
    """Get satisfaction prediction model accuracy."""
    return jsonify(SatisfactionPredictor.get_prediction_accuracy())


@intelligence_bp.route("/api/intelligence/satisfaction/train", methods=["POST"])
def train_satisfaction_model_route():
    """Manually trigger satisfaction model training."""
    result = SatisfactionPredictor.train_satisfaction_model()
    return jsonify(result)


# ---------------------------------------------------------------------------
# Smart Escalation
# ---------------------------------------------------------------------------


@intelligence_bp.route("/api/intelligence/escalations")
def get_escalation_queue():
    """Get smart escalation queue."""
    status = request.args.get("status", "open")
    limit = request.args.get("limit", 50, type=int)
    return jsonify(SmartEscalation.get_smart_escalation_queue(status, limit))


@intelligence_bp.route("/api/intelligence/escalations/stats")
def get_escalation_stats():
    """Get escalation queue statistics."""
    return jsonify(SmartEscalation.get_escalation_stats())


@intelligence_bp.route("/api/intelligence/escalations/<int:esc_id>/resolve", methods=["POST"])
def resolve_escalation(esc_id):
    """Resolve an escalation."""
    data = request.json
    success = SmartEscalation.resolve_escalation(
        escalation_id=esc_id,
        action=data.get("action", "dismiss"),
        resolved_by=data.get("resolved_by", "admin"),
        notes=data.get("notes"),
        corrected_answer=data.get("corrected_answer"),
    )
    return jsonify({"success": success})


# ---------------------------------------------------------------------------
# Promote from moderation to golden answer
# ---------------------------------------------------------------------------


@intelligence_bp.route("/api/intelligence/promote-to-golden", methods=["POST"])
def promote_to_golden():
    """Promote an approved moderation answer to golden answer."""
    data = request.json
    golden_id = SelfHealingLoop.create_golden_answer(
        question=data["question"],
        answer=data["answer"],
        category=data.get("category"),
        source_feedback_id=data.get("feedback_id"),
    )
    return jsonify({"success": True, "golden_id": golden_id})


# =============================================================================
# ENTERPRISE INTELLIGENCE API ENDPOINTS
# =============================================================================

# ---------------------------------------------------------------------------
# Pipeline Analytics & Cost
# ---------------------------------------------------------------------------


@intelligence_bp.route("/api/intelligence/pipeline-metrics")
def api_pipeline_metrics():
    """Get pipeline latency, throughput, and cost metrics."""
    period = request.args.get("period", "24h")
    return jsonify(
        {
            "latency": PipelineAnalytics.get_latency_percentiles(period),
            "throughput": PipelineAnalytics.get_throughput(period),
            "cost": PipelineAnalytics.get_cost_summary(period),
            "steps": PipelineAnalytics.get_step_breakdown(period),
        }
    )


@intelligence_bp.route("/api/intelligence/cost-summary")
def api_cost_summary():
    """Get cost breakdown by model and step."""
    period = request.args.get("period", "24h")
    return jsonify(PipelineAnalytics.get_cost_summary(period))


# ---------------------------------------------------------------------------
# Anomaly Detection
# ---------------------------------------------------------------------------


@intelligence_bp.route("/api/intelligence/anomalies")
def api_anomalies():
    """Get recent anomaly detections."""
    limit = request.args.get("limit", 50, type=int)
    return jsonify({"anomalies": AnomalyDetector.get_recent_anomalies(limit)})


@intelligence_bp.route("/api/intelligence/anomalies/check", methods=["POST"])
def api_anomaly_check():
    """Run anomaly detection now."""
    detections = AnomalyDetector.check_all()
    return jsonify({"detections": detections, "count": len(detections)})


# ---------------------------------------------------------------------------
# Alert System
# ---------------------------------------------------------------------------


@intelligence_bp.route("/api/intelligence/alerts")
def api_alerts():
    """Get alert history."""
    limit = request.args.get("limit", 100, type=int)
    return jsonify({"alerts": AlertEngine.get_alert_history(limit)})


@intelligence_bp.route("/api/intelligence/alert-rules")
def api_alert_rules_get():
    """Get all alert rules."""
    return jsonify({"rules": AlertEngine.get_rules()})


@intelligence_bp.route("/api/intelligence/alert-rules", methods=["POST"])
def api_alert_rules_create():
    """Create a new alert rule."""
    data = request.json
    rule_id = AlertEngine.create_rule(
        name=data["name"],
        metric=data["metric"],
        condition=data["condition"],
        threshold=float(data["threshold"]),
        channels=data.get("channels", ["in_app"]),
        cooldown_minutes=data.get("cooldown_minutes", 60),
    )
    return jsonify({"success": True, "rule_id": rule_id})


@intelligence_bp.route("/api/intelligence/alert-rules/<int:rule_id>", methods=["PUT"])
def api_alert_rules_update(rule_id):
    """Update an alert rule."""
    data = request.json
    from intelligence_engine import _get_conn

    conn = _get_conn()
    conn.execute(
        """
        UPDATE alert_rules SET name=?, metric=?, condition=?, threshold=?,
        channels=?, cooldown_minutes=?, enabled=? WHERE id=?
    """,
        (
            data.get("name"),
            data.get("metric"),
            data.get("condition"),
            data.get("threshold"),
            json.dumps(data.get("channels", ["in_app"])),
            data.get("cooldown_minutes", 60),
            data.get("enabled", True),
            rule_id,
        ),
    )
    conn.commit()
    conn.close()
    return jsonify({"success": True})


@intelligence_bp.route("/api/intelligence/alert-rules/<int:rule_id>", methods=["DELETE"])
def api_alert_rules_delete(rule_id):
    """Disable an alert rule."""
    from intelligence_engine import _get_conn

    conn = _get_conn()
    conn.execute("UPDATE alert_rules SET enabled = 0 WHERE id = ?", (rule_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})


# ---------------------------------------------------------------------------
# Remediation & Circuit Breakers
# ---------------------------------------------------------------------------


@intelligence_bp.route("/api/intelligence/remediations")
def api_remediations():
    """Get remediation action history."""
    limit = request.args.get("limit", 50, type=int)
    return jsonify({"actions": RemediationEngine.get_history(limit)})


@intelligence_bp.route("/api/intelligence/circuit-breakers")
def api_circuit_breakers():
    """Get circuit breaker status."""
    return jsonify({"breakers": CircuitBreaker.get_all_breakers()})


# ---------------------------------------------------------------------------
# Prompt Versioning
# ---------------------------------------------------------------------------


@intelligence_bp.route("/api/intelligence/prompt-versions")
def api_prompt_versions():
    """Get all prompt versions."""
    return jsonify({"versions": PromptVersioning.get_all_versions()})


@intelligence_bp.route("/api/intelligence/prompt-versions", methods=["POST"])
def api_prompt_version_create():
    """Create a new prompt version."""
    data = request.json
    version_id = PromptVersioning.create_version(
        template_text=data["template_text"],
        description=data.get("description", ""),
        changes=data.get("changes", ""),
        created_by=data.get("created_by", "admin"),
    )
    return jsonify({"success": True, "version_id": version_id})


@intelligence_bp.route("/api/intelligence/prompt-versions/<int:version_id>/activate", methods=["POST"])
def api_prompt_version_activate(version_id):
    """Activate a prompt version."""
    success = PromptVersioning.activate_version(version_id)
    return jsonify({"success": success})


@intelligence_bp.route("/api/intelligence/prompt-versions/<int:version_id>/rollback", methods=["POST"])
def api_prompt_version_rollback(version_id):
    """Rollback to a prompt version."""
    success = PromptVersioning.rollback(version_id)
    return jsonify({"success": success})


@intelligence_bp.route("/api/intelligence/prompt-versions/compare")
def api_prompt_version_compare():
    """Compare two prompt versions."""
    v1 = request.args.get("v1", type=int)
    v2 = request.args.get("v2", type=int)
    if not v1 or not v2:
        return jsonify({"error": "v1 and v2 parameters required"}), 400
    return jsonify(PromptVersioning.compare_versions(v1, v2))


# ---------------------------------------------------------------------------
# Knowledge Gaps
# ---------------------------------------------------------------------------


@intelligence_bp.route("/api/intelligence/knowledge-gaps")
def api_knowledge_gaps():
    """Get knowledge gap report."""
    return jsonify({"gaps": KnowledgeGapAnalyzer.get_gap_report()})


@intelligence_bp.route("/api/intelligence/knowledge-gaps/detect", methods=["POST"])
def api_detect_knowledge_gaps():
    """Run knowledge gap detection now."""
    gaps = KnowledgeGapAnalyzer.detect_gaps()
    return jsonify({"gaps": gaps, "count": len(gaps)})


@intelligence_bp.route("/api/intelligence/content-freshness")
def api_content_freshness():
    """Get content freshness report."""
    return jsonify({"sources": KnowledgeGapAnalyzer.get_freshness_report()})


@intelligence_bp.route("/api/intelligence/coverage-matrix")
def api_coverage_matrix():
    """Get coverage quality matrix by category."""
    return jsonify(KnowledgeGapAnalyzer.get_coverage_matrix())


# ---------------------------------------------------------------------------
# Executive Dashboard
# ---------------------------------------------------------------------------


@intelligence_bp.route("/api/intelligence/executive/health")
def api_executive_health():
    """Get system health score (0-100)."""
    return jsonify(ExecutiveDashboard.compute_system_health())


@intelligence_bp.route("/api/intelligence/executive/weekly-digest")
def api_weekly_digest():
    """Get weekly performance digest."""
    return jsonify(ExecutiveDashboard.generate_weekly_digest())


@intelligence_bp.route("/api/intelligence/executive/kpi-trends")
def api_kpi_trends():
    """Get KPI time-series data."""
    period = request.args.get("period", "30d")
    return jsonify(ExecutiveDashboard.get_kpi_trends(period))


@intelligence_bp.route("/api/intelligence/executive/roi")
def api_roi_metrics():
    """Get ROI metrics."""
    return jsonify(ExecutiveDashboard.compute_roi_metrics())


# ---------------------------------------------------------------------------
# Gradient Boosted Predictor
# ---------------------------------------------------------------------------


@intelligence_bp.route("/api/intelligence/gradient-boosted/train", methods=["POST"])
def api_gradient_boosted_train():
    """Train the gradient boosted satisfaction model."""
    result = GradientBoostedPredictor.train()
    return jsonify(result)


@intelligence_bp.route("/api/intelligence/gradient-boosted/importance")
def api_gradient_boosted_importance():
    """Get feature importance from gradient boosted model."""
    return jsonify(GradientBoostedPredictor.feature_importance())


# ---------------------------------------------------------------------------
# Conversation Intelligence
# ---------------------------------------------------------------------------


@intelligence_bp.route("/api/intelligence/conversations")
def api_conversations():
    """Get conversation quality metrics."""
    return jsonify(ConversationIntelligence.get_conversation_quality_metrics())


@intelligence_bp.route("/api/intelligence/conversations/frustration")
def api_conversations_frustration():
    """Get frustration signals from conversations."""
    days = request.args.get("days", 7, type=int)
    return jsonify({"conversations": ConversationIntelligence.detect_frustration_signals(days)})


@intelligence_bp.route("/api/intelligence/conversations/analyze", methods=["POST"])
def api_conversations_analyze():
    """Batch analyze recent conversations."""
    days = request.json.get("days", 7) if request.json else 7
    ConversationIntelligence.batch_analyze_recent(days)
    return jsonify({"success": True})


# ---------------------------------------------------------------------------
# Feature Flags
# ---------------------------------------------------------------------------


@intelligence_bp.route("/api/intelligence/feature-flags")
def api_feature_flags():
    """Get all feature flag states."""
    return jsonify(FeatureFlags.get_all_flags())


@intelligence_bp.route("/api/intelligence/feature-flags", methods=["POST"])
def api_feature_flags_toggle():
    """Toggle a feature flag."""
    data = request.json or {}
    flag_name = data.get("flag_name")
    enabled = data.get("enabled")
    if not flag_name or enabled is None:
        return jsonify({"error": "flag_name and enabled required"}), 400
    ok = FeatureFlags.set_flag(flag_name, bool(enabled))
    return jsonify({"success": ok})


# ---------------------------------------------------------------------------
# Data Retention
# ---------------------------------------------------------------------------


@intelligence_bp.route("/api/intelligence/data-retention/status")
def api_data_retention_status():
    """Get data retention status per table."""
    return jsonify(DataRetentionManager.get_status())


@intelligence_bp.route("/api/intelligence/data-retention/run", methods=["POST"])
def api_data_retention_run():
    """Trigger data retention cleanup now."""
    result = DataRetentionManager.run_cleanup()
    return jsonify(result)


# ---------------------------------------------------------------------------
# Rate Limiting
# ---------------------------------------------------------------------------


@intelligence_bp.route("/api/intelligence/rate-limit/status")
def api_rate_limit_status():
    """Get rate limiter status."""
    return jsonify(RateLimiter.get_status())


# ---------------------------------------------------------------------------
# Cost Budget
# ---------------------------------------------------------------------------


@intelligence_bp.route("/api/intelligence/cost-budget/status")
def api_cost_budget_status():
    """Get cost budget utilization."""
    return jsonify(PipelineAnalytics.check_budget())


@intelligence_bp.route("/api/intelligence/cost-budget/set", methods=["POST"])
def api_cost_budget_set():
    """Update cost budget limits (runtime only, does not persist to .env)."""
    data = request.json or {}
    if "daily" in data:
        Config.COST_BUDGET_DAILY = float(data["daily"])
    if "monthly" in data:
        Config.COST_BUDGET_MONTHLY = float(data["monthly"])
    return jsonify({"success": True, "daily": Config.COST_BUDGET_DAILY, "monthly": Config.COST_BUDGET_MONTHLY})


# ---------------------------------------------------------------------------
# Training Readiness
# ---------------------------------------------------------------------------


@intelligence_bp.route("/api/intelligence/training/status")
def api_training_status():
    """Check training readiness."""
    return jsonify(TrainingOrchestrator.check_readiness())


@intelligence_bp.route("/api/intelligence/training/check", methods=["POST"])
def api_training_check():
    """Run training readiness check now."""
    return jsonify(TrainingOrchestrator.check_readiness())


# ---------------------------------------------------------------------------
# Input Sanitization
# ---------------------------------------------------------------------------


@intelligence_bp.route("/api/intelligence/sanitization/blocked")
def api_sanitization_blocked():
    """Get recent blocked/flagged queries."""
    limit = request.args.get("limit", 50, type=int)
    return jsonify(InputSanitizer.get_blocked_queries(limit))
