"""
Intelligence Engine — Background Scheduler
=============================================
Background scheduler for periodic intelligence jobs.
"""

import time
import logging
import threading
from datetime import datetime

from intelligence.db import log_event

logger = logging.getLogger(__name__)


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
        from intelligence.anomaly import AnomalyDetector
        from intelligence.alerts import AlertEngine

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
        from intelligence.topic_intelligence import TopicIntelligence
        from intelligence.confidence_calibration import ConfidenceCalibration
        from intelligence.analytics import PipelineAnalytics
        from intelligence.anomaly import AnomalyDetector

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
        from intelligence.topic_intelligence import TopicIntelligence
        from intelligence.satisfaction import SatisfactionPredictor, GradientBoostedPredictor
        from intelligence.knowledge_gaps import KnowledgeGapAnalyzer
        from intelligence.training import TrainingOrchestrator

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
        from intelligence.source_quality import SourceQualityIntelligence
        from intelligence.knowledge_gaps import KnowledgeGapAnalyzer
        from intelligence.conversation import ConversationIntelligence, ExecutiveDashboard
        from intelligence.features import DataRetentionManager, RateLimiter

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
