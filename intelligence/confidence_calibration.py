"""
Intelligence Engine — Subsystem 4: Confidence Calibration Engine
=================================================================
Tracks predicted confidence vs actual user satisfaction.
"""

import logging
from typing import List, Dict, Optional

from intelligence.db import _get_conn
from intelligence.helpers import _isotonic_regression

logger = logging.getLogger(__name__)


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
