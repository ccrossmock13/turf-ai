"""
Intelligence Engine Package
=============================
Re-exports all public names so that:
    from intelligence import SelfHealingLoop
    from intelligence import process_answer_intelligence
work identically to the old monolithic import.
"""

import logging

logger = logging.getLogger(__name__)

# ── Foundation ──────────────────────────────────────────────────────────────
from intelligence.ab_testing import ABTestingEngine
from intelligence.alerts import AlertEngine
from intelligence.analytics import PipelineAnalytics
from intelligence.anomaly import AnomalyDetector
from intelligence.circuit_breaker import CircuitBreaker
from intelligence.confidence_calibration import ConfidenceCalibration
from intelligence.conversation import ConversationIntelligence, ExecutiveDashboard
from intelligence.db import (
    DATA_DIR,
    DB_PATH,
    _get_conn,
    init_intelligence_tables,
    log_event,
)
from intelligence.escalation import RemediationEngine, SmartEscalation
from intelligence.features import (
    DataRetentionManager,
    FeatureFlags,
    InputSanitizer,
    RateLimiter,
)

# ── Helper functions ────────────────────────────────────────────────────────
from intelligence.helpers import (
    _agglomerative_cluster,
    _auto_name_cluster,
    _compute_centroid,
    _compute_drift_score,
    _cosine_similarity,
    _isotonic_regression,
    _keyword_similarity,
    _sigmoid,
    _wilson_score_interval,
)
from intelligence.knowledge_gaps import KnowledgeGapAnalyzer

# ── Orchestrator functions ──────────────────────────────────────────────────
from intelligence.orchestrator import (
    _auto_promote_correction_to_golden,
    _track_negative_accumulation,
    get_intelligence_overview,
    process_answer_intelligence,
    process_feedback_intelligence,
)
from intelligence.prompt_versioning import PromptVersioning
from intelligence.regression import RegressionDetector
from intelligence.satisfaction import (
    DecisionStump,
    GradientBoostedPredictor,
    SatisfactionPredictor,
)
from intelligence.scheduler import IntelligenceScheduler

# ── Subsystem classes ───────────────────────────────────────────────────────
from intelligence.self_healing import SelfHealingLoop
from intelligence.source_quality import SourceQualityIntelligence
from intelligence.topic_intelligence import TopicIntelligence
from intelligence.training import TrainingOrchestrator

# ── Initialization (runs on first import, same as the old monolith) ────────
try:
    init_intelligence_tables()
except Exception as e:
    logger.error(f"Failed to initialize intelligence tables: {e}")

try:
    AlertEngine.init_default_rules()
except Exception as e:
    logger.error(f"Failed to initialize alert rules: {e}")

try:
    FeatureFlags.init_defaults()
except Exception as e:
    logger.error(f"Failed to initialize feature flags: {e}")


# ── __all__ for `from intelligence import *` ───────────────────────────────
__all__ = [
    # db
    "DATA_DIR",
    "DB_PATH",
    "init_intelligence_tables",
    "log_event",
    "_get_conn",
    # helpers
    "_cosine_similarity",
    "_keyword_similarity",
    "_wilson_score_interval",
    "_sigmoid",
    "_isotonic_regression",
    "_compute_drift_score",
    "_agglomerative_cluster",
    "_compute_centroid",
    "_auto_name_cluster",
    # classes
    "SelfHealingLoop",
    "ABTestingEngine",
    "SourceQualityIntelligence",
    "ConfidenceCalibration",
    "RegressionDetector",
    "TopicIntelligence",
    "SatisfactionPredictor",
    "DecisionStump",
    "GradientBoostedPredictor",
    "SmartEscalation",
    "RemediationEngine",
    "PipelineAnalytics",
    "AnomalyDetector",
    "AlertEngine",
    "CircuitBreaker",
    "PromptVersioning",
    "KnowledgeGapAnalyzer",
    "ConversationIntelligence",
    "ExecutiveDashboard",
    "FeatureFlags",
    "RateLimiter",
    "DataRetentionManager",
    "InputSanitizer",
    "TrainingOrchestrator",
    "IntelligenceScheduler",
    # orchestrator functions
    "process_answer_intelligence",
    "process_feedback_intelligence",
    "get_intelligence_overview",
    "_auto_promote_correction_to_golden",
    "_track_negative_accumulation",
]
