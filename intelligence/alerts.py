"""
Intelligence Engine — Subsystem 11: Multi-Channel Alert System
================================================================
Configurable alert rules with multi-channel dispatch.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict

from intelligence.db import _get_conn, log_event

logger = logging.getLogger(__name__)


class AlertEngine:
    """Configurable alert rules with multi-channel dispatch."""

    @staticmethod
    def init_default_rules():
        """Create default alert rules if none exist."""
        try:
            conn = _get_conn()
            existing = conn.execute('SELECT COUNT(*) FROM alert_rules').fetchone()[0]
            if existing > 0:
                conn.close()
                return

            defaults = [
                ('Latency Spike', 'latency_p95', 'gt', 10000, '["in_app"]', 30),
                ('Cost Overrun (Hourly)', 'hourly_cost', 'gt', 1.0, '["in_app"]', 60),
                ('Confidence Drop', 'avg_confidence', 'lt', 50, '["in_app"]', 60),
                ('Error Rate Spike', 'error_rate', 'gt', 0.1, '["in_app"]', 15),
                ('Low Satisfaction', 'satisfaction_rate', 'lt', 0.5, '["in_app"]', 120),
            ]
            for name, metric, condition, threshold, channels, cooldown in defaults:
                conn.execute('''
                    INSERT INTO alert_rules (name, metric, condition, threshold, channels, cooldown_minutes)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (name, metric, condition, threshold, channels, cooldown))

            conn.commit()
            conn.close()
            log_event('alert_engine', 'default_rules_created')
        except Exception as e:
            logger.error(f"Init default rules error: {e}")

    @staticmethod
    def create_rule(name: str, metric: str, condition: str, threshold: float,
                    channels: List[str] = None, cooldown_minutes: int = 60) -> int:
        """Create a new alert rule."""
        try:
            conn = _get_conn()
            cursor = conn.execute('''
                INSERT INTO alert_rules (name, metric, condition, threshold, channels, cooldown_minutes)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (name, metric, condition, threshold,
                  json.dumps(channels or ['in_app']), cooldown_minutes))
            rule_id = cursor.lastrowid
            conn.commit()
            conn.close()
            log_event('alert_engine', 'rule_created', json.dumps({'id': rule_id, 'name': name}))
            return rule_id
        except Exception as e:
            logger.error(f"Create rule error: {e}")
            return 0

    @staticmethod
    def evaluate_rules() -> List[Dict]:
        """Evaluate all active rules against current metrics."""
        fired = []
        try:
            conn = _get_conn()
            rules = conn.execute(
                'SELECT * FROM alert_rules WHERE enabled = 1'
            ).fetchall()

            now = datetime.now()
            metrics = AlertEngine._collect_current_metrics(conn)

            for rule in rules:
                rule = dict(rule)
                metric_val = metrics.get(rule['metric'])
                if metric_val is None:
                    continue

                # Check cooldown
                if rule['last_fired']:
                    last = datetime.fromisoformat(rule['last_fired'])
                    if (now - last).total_seconds() < rule['cooldown_minutes'] * 60:
                        continue

                # Evaluate condition
                triggered = False
                if rule['condition'] == 'gt' and metric_val > rule['threshold']:
                    triggered = True
                elif rule['condition'] == 'lt' and metric_val < rule['threshold']:
                    triggered = True
                elif rule['condition'] == 'eq' and abs(metric_val - rule['threshold']) < 0.001:
                    triggered = True

                if triggered:
                    message = (f"Alert: {rule['name']} — {rule['metric']} is "
                               f"{metric_val:.4f} (threshold: {rule['condition']} {rule['threshold']})")

                    channels = json.loads(rule['channels'])
                    for channel in channels:
                        AlertEngine._dispatch(rule['id'], rule['name'], rule['metric'],
                                              metric_val, rule['threshold'], channel, message)

                    conn.execute('''
                        UPDATE alert_rules SET last_fired = ?, fire_count = fire_count + 1
                        WHERE id = ?
                    ''', (now.isoformat(), rule['id']))

                    fired.append({
                        'rule_id': rule['id'],
                        'rule_name': rule['name'],
                        'metric': rule['metric'],
                        'value': metric_val,
                        'threshold': rule['threshold'],
                        'channels': channels
                    })

            conn.commit()
            conn.close()

            if fired:
                log_event('alert_engine', 'rules_fired',
                          json.dumps({'count': len(fired)}), 'warning')

        except Exception as e:
            logger.error(f"Evaluate rules error: {e}")

        return fired

    @staticmethod
    def _collect_current_metrics(conn) -> Dict[str, float]:
        """Collect current metric values for rule evaluation."""
        metrics = {}
        cutoff = (datetime.now() - timedelta(hours=1)).isoformat()

        try:
            # Latency p95
            lats = conn.execute('''
                SELECT total_latency_ms FROM pipeline_metrics
                WHERE timestamp > ? ORDER BY total_latency_ms
            ''', (cutoff,)).fetchall()
            if lats:
                n = len(lats)
                metrics['latency_p95'] = lats[int(n * 0.95)]['total_latency_ms'] if n > 1 else lats[0]['total_latency_ms']
                metrics['latency_avg'] = sum(r['total_latency_ms'] for r in lats) / n

            # Cost
            cost = conn.execute('''
                SELECT SUM(total_cost_usd) as total FROM pipeline_metrics WHERE timestamp > ?
            ''', (cutoff,)).fetchone()
            metrics['hourly_cost'] = cost['total'] or 0 if cost else 0

            # Confidence
            conf = conn.execute('''
                SELECT AVG(predicted_confidence) as avg_conf
                FROM confidence_calibration WHERE timestamp > ?
            ''', (cutoff,)).fetchone()
            metrics['avg_confidence'] = conf['avg_conf'] or 75 if conf else 75

            # Satisfaction rate
            sat = conn.execute('''
                SELECT COUNT(CASE WHEN was_correct = 1 THEN 1 END) as correct,
                       COUNT(*) as total
                FROM satisfaction_predictions
                WHERE actual_rating IS NOT NULL AND timestamp > ?
            ''', (cutoff,)).fetchone()
            if sat and sat['total'] > 0:
                metrics['satisfaction_rate'] = sat['correct'] / sat['total']

            # Error rate (escalations / total queries in the period)
            esc = conn.execute('''
                SELECT COUNT(*) as esc_count FROM escalation_queue WHERE created_at > ?
            ''', (cutoff,)).fetchone()
            total_q = conn.execute('''
                SELECT COUNT(*) as count FROM pipeline_metrics WHERE timestamp > ?
            ''', (cutoff,)).fetchone()
            if total_q and total_q['count'] > 0:
                metrics['error_rate'] = (esc['esc_count'] or 0) / total_q['count']

        except Exception as e:
            logger.error(f"Collect metrics error: {e}")

        return metrics

    @staticmethod
    def _dispatch(rule_id: int, rule_name: str, metric: str, value: float,
                  threshold: float, channel: str, message: str):
        """Dispatch alert to a channel."""
        try:
            conn = _get_conn()
            delivered = True

            if channel == 'webhook':
                delivered = AlertEngine._send_webhook(message)
            elif channel == 'email':
                delivered = AlertEngine._send_email(rule_name, message)
            # in_app always "delivered" (stored in DB)

            conn.execute('''
                INSERT INTO alert_history
                (rule_id, rule_name, metric, current_value, threshold, channel, message, delivered)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (rule_id, rule_name, metric, value, threshold, channel, message, delivered))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Alert dispatch error: {e}")

    @staticmethod
    def _send_webhook(message: str) -> bool:
        """Send alert to webhook (Slack/Teams/Discord)."""
        try:
            from config import Config
            url = Config.ALERT_WEBHOOK_URL
            if not url:
                return False

            import urllib.request
            payload = json.dumps({'text': message}).encode()
            req = urllib.request.Request(url, data=payload,
                                         headers={'Content-Type': 'application/json'})
            urllib.request.urlopen(req, timeout=10)
            return True
        except Exception as e:
            logger.error(f"Webhook send error: {e}")
            return False

    @staticmethod
    def _send_email(subject: str, body: str) -> bool:
        """Send alert email via SMTP."""
        try:
            from config import Config
            if not Config.ALERT_EMAIL_ENABLED:
                return False

            import smtplib
            from email.mime.text import MIMEText

            msg = MIMEText(body)
            msg['Subject'] = f"[Greenside AI Alert] {subject}"
            msg['From'] = Config.ALERT_EMAIL_FROM
            msg['To'] = Config.ALERT_EMAIL_TO

            with smtplib.SMTP(Config.ALERT_EMAIL_SMTP_HOST, Config.ALERT_EMAIL_SMTP_PORT) as server:
                server.starttls()
                server.login(Config.ALERT_EMAIL_FROM, Config.ALERT_EMAIL_PASSWORD)
                server.send_message(msg)
            return True
        except Exception as e:
            logger.error(f"Email send error: {e}")
            return False

    @staticmethod
    def get_alert_history(limit: int = 100) -> List[Dict]:
        """Get recent alert history."""
        try:
            conn = _get_conn()
            rows = conn.execute('''
                SELECT * FROM alert_history ORDER BY timestamp DESC LIMIT ?
            ''', (limit,)).fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"Get alert history error: {e}")
            return []

    @staticmethod
    def get_rules() -> List[Dict]:
        """Get all alert rules."""
        try:
            conn = _get_conn()
            rows = conn.execute('SELECT * FROM alert_rules ORDER BY id').fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"Get rules error: {e}")
            return []
