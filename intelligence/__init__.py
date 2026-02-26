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
from intelligence.db import (
    DATA_DIR,
    DB_PATH,
    init_intelligence_tables,
    log_event,
    _get_conn,
)

# ── Helper functions ────────────────────────────────────────────────────────
from intelligence.helpers import (
    _cosine_similarity,
    _keyword_similarity,
    _wilson_score_interval,
    _sigmoid,
    _isotonic_regression,
    _compute_drift_score,
    _agglomerative_cluster,
    _compute_centroid,
    _auto_name_cluster,
)

# ── Subsystem classes ───────────────────────────────────────────────────────
from intelligence.self_healing import SelfHealingLoop
from intelligence.ab_testing import ABTestingEngine
from intelligence.source_quality import SourceQualityIntelligence
from intelligence.confidence_calibration import ConfidenceCalibration
from intelligence.regression import RegressionDetector
from intelligence.topic_intelligence import TopicIntelligence
from intelligence.satisfaction import (
    SatisfactionPredictor,
    DecisionStump,
    GradientBoostedPredictor,
)
from intelligence.escalation import SmartEscalation, RemediationEngine
from intelligence.analytics import PipelineAnalytics
from intelligence.anomaly import AnomalyDetector
from intelligence.alerts import AlertEngine
from intelligence.circuit_breaker import CircuitBreaker
from intelligence.prompt_versioning import PromptVersioning
from intelligence.knowledge_gaps import KnowledgeGapAnalyzer
from intelligence.conversation import ConversationIntelligence, ExecutiveDashboard
from intelligence.features import (
    FeatureFlags,
    RateLimiter,
    DataRetentionManager,
    InputSanitizer,
)
from intelligence.training import TrainingOrchestrator
from intelligence.scheduler import IntelligenceScheduler

# ── Orchestrator functions ──────────────────────────────────────────────────
from intelligence.orchestrator import (
    process_answer_intelligence,
    process_feedback_intelligence,
    get_intelligence_overview,
    _auto_promote_correction_to_golden,
    _track_negative_accumulation,
)

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
    'DATA_DIR', 'DB_PATH', 'init_intelligence_tables', 'log_event', '_get_conn',
    # helpers
    '_cosine_similarity', '_keyword_similarity', '_wilson_score_interval',
    '_sigmoid', '_isotonic_regression', '_compute_drift_score',
    '_agglomerative_cluster', '_compute_centroid', '_auto_name_cluster',
    # classes
    'SelfHealingLoop',
    'ABTestingEngine',
    'SourceQualityIntelligence',
    'ConfidenceCalibration',
    'RegressionDetector',
    'TopicIntelligence',
    'SatisfactionPredictor', 'DecisionStump', 'GradientBoostedPredictor',
    'SmartEscalation', 'RemediationEngine',
    'PipelineAnalytics',
    'AnomalyDetector',
    'AlertEngine',
    'CircuitBreaker',
    'PromptVersioning',
    'KnowledgeGapAnalyzer',
    'ConversationIntelligence', 'ExecutiveDashboard',
    'FeatureFlags', 'RateLimiter', 'DataRetentionManager', 'InputSanitizer',
    'TrainingOrchestrator',
    'IntelligenceScheduler',
    # orchestrator functions
    'process_answer_intelligence',
    'process_feedback_intelligence',
    'get_intelligence_overview',
    '_auto_promote_correction_to_golden',
    '_track_negative_accumulation',
]
