"""
Intelligence Engine — Training Orchestrator
=============================================
Monitor quality metrics and flag when retraining is recommended.
"""

import json
import logging
from datetime import datetime
from typing import Dict

from intelligence.db import _get_conn, log_event

logger = logging.getLogger(__name__)


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
            if ready:
                try:
                    from intelligence.features import FeatureFlags
                    if FeatureFlags.is_enabled('alerting'):
                        from intelligence.alerts import AlertEngine
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
