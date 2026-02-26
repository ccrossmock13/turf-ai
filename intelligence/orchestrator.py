"""
Intelligence Engine — Unified API / Orchestrator
==================================================
Convenience functions for app.py integration.
Main entry points: process_answer_intelligence, process_feedback_intelligence,
get_intelligence_overview.
"""

import json
import logging
from datetime import datetime
from typing import List, Dict

from intelligence.db import _get_conn, log_event

logger = logging.getLogger(__name__)


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
    Main integration point -- called after /ask generates an answer.
    Runs all intelligence subsystems on the answer.
    Returns any modifications or flags.
    """
    from intelligence.analytics import PipelineAnalytics
    from intelligence.prompt_versioning import PromptVersioning
    from intelligence.confidence_calibration import ConfidenceCalibration
    from intelligence.topic_intelligence import TopicIntelligence
    from intelligence.satisfaction import SatisfactionPredictor
    from intelligence.escalation import SmartEscalation

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
        # This is informational -- the actual injection happens in the prompt building

        # 2. A/B test -- use pre-assignment from app.py (assigned BEFORE LLM call)
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
    from intelligence.confidence_calibration import ConfidenceCalibration
    from intelligence.source_quality import SourceQualityIntelligence
    from intelligence.satisfaction import SatisfactionPredictor

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
    from intelligence.satisfaction import SatisfactionPredictor
    from intelligence.conversation import ExecutiveDashboard
    from intelligence.features import FeatureFlags, RateLimiter
    from intelligence.analytics import PipelineAnalytics
    from intelligence.training import TrainingOrchestrator

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
