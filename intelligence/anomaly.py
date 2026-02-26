"""
Intelligence Engine — Subsystem 10: Anomaly Detection Engine
==============================================================
Detect anomalies in system metrics using z-score and CUSUM methods.
"""

import math
import time
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from collections import defaultdict

from intelligence.db import _get_conn, log_event

logger = logging.getLogger(__name__)


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
