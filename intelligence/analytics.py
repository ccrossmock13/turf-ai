"""
Intelligence Engine — Subsystem 9: Pipeline Analytics & Cost Intelligence
===========================================================================
Track per-request latency, token usage, and cost.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict
from collections import defaultdict

from intelligence.db import _get_conn, log_event

logger = logging.getLogger(__name__)


class PipelineAnalytics:
    """Track per-request latency, token usage, and cost."""

    # Cost rates per token (imported from config at runtime)
    _cost_rates = None

    @staticmethod
    def _get_cost_rates():
        if PipelineAnalytics._cost_rates is None:
            try:
                from config import Config
                PipelineAnalytics._cost_rates = Config.COST_RATES
            except Exception:
                PipelineAnalytics._cost_rates = {
                    'gpt-4o': {'prompt': 2.50 / 1_000_000, 'completion': 10.00 / 1_000_000},
                    'gpt-4o-mini': {'prompt': 0.150 / 1_000_000, 'completion': 0.600 / 1_000_000},
                    'text-embedding-3-small': {'prompt': 0.020 / 1_000_000, 'completion': 0.0},
                }
        return PipelineAnalytics._cost_rates

    @staticmethod
    def calculate_cost(prompt_tokens: int, completion_tokens: int, model: str) -> float:
        """Calculate USD cost for a given token usage."""
        rates = PipelineAnalytics._get_cost_rates()
        model_rates = rates.get(model, rates.get('gpt-4o', {}))
        cost = (prompt_tokens * model_rates.get('prompt', 0) +
                completion_tokens * model_rates.get('completion', 0))
        return round(cost, 8)

    @staticmethod
    def record_request(query_id: int, timings: Dict = None, token_usage: Dict = None,
                       grounding_tokens: int = 0, embedding_tokens: int = 0):
        """Record a complete pipeline execution with timing and cost data."""
        try:
            conn = _get_conn()
            model = (token_usage or {}).get('model', 'gpt-4o')
            prompt_tokens = (token_usage or {}).get('prompt_tokens', 0)
            completion_tokens = (token_usage or {}).get('completion_tokens', 0)
            total_tokens = prompt_tokens + completion_tokens

            # Calculate costs for each component
            main_cost = PipelineAnalytics.calculate_cost(prompt_tokens, completion_tokens, model)
            grounding_cost = PipelineAnalytics.calculate_cost(grounding_tokens, 0, 'gpt-4o-mini')
            embedding_cost = PipelineAnalytics.calculate_cost(embedding_tokens, 0, 'text-embedding-3-small')
            total_cost = main_cost + grounding_cost + embedding_cost

            total_latency_ms = (timings or {}).get('10_total', 0) * 1000

            conn.execute('''
                INSERT INTO pipeline_metrics
                (query_id, total_latency_ms, step_timings, prompt_tokens, completion_tokens,
                 total_tokens, model, cost_usd, grounding_tokens, grounding_cost_usd,
                 embedding_tokens, embedding_cost_usd, total_cost_usd)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (query_id, total_latency_ms, json.dumps(timings or {}),
                  prompt_tokens, completion_tokens, total_tokens, model, main_cost,
                  grounding_tokens, grounding_cost, embedding_tokens, embedding_cost, total_cost))

            # Update cost ledger (daily + monthly)
            now = datetime.now()
            daily_key = now.strftime('%Y-%m-%d')
            monthly_key = now.strftime('%Y-%m')

            for period_type, period_key in [('daily', daily_key), ('monthly', monthly_key)]:
                conn.execute('''
                    INSERT INTO cost_ledger (period_type, period_key, model, total_requests,
                        total_prompt_tokens, total_completion_tokens, total_cost_usd)
                    VALUES (?, ?, ?, 1, ?, ?, ?)
                    ON CONFLICT(period_type, period_key, model) DO UPDATE SET
                        total_requests = total_requests + 1,
                        total_prompt_tokens = total_prompt_tokens + ?,
                        total_completion_tokens = total_completion_tokens + ?,
                        total_cost_usd = total_cost_usd + ?,
                        avg_cost_per_request = (total_cost_usd + ?) / (total_requests + 1),
                        updated_at = CURRENT_TIMESTAMP
                ''', (period_type, period_key, model, prompt_tokens, completion_tokens, total_cost,
                      prompt_tokens, completion_tokens, total_cost, total_cost))

            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Pipeline metrics recording failed: {e}")

    @staticmethod
    def get_latency_percentiles(period: str = '24h') -> Dict:
        """Get p50, p95, p99 latency for a time period."""
        try:
            conn = _get_conn()
            hours = int(period.replace('h', '').replace('d', '')) * (24 if 'd' in period else 1)
            cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()

            rows = conn.execute('''
                SELECT total_latency_ms FROM pipeline_metrics
                WHERE timestamp > ? ORDER BY total_latency_ms
            ''', (cutoff,)).fetchall()
            conn.close()

            if not rows:
                return {'p50': 0, 'p95': 0, 'p99': 0, 'count': 0, 'mean': 0}

            latencies = [r['total_latency_ms'] for r in rows]
            n = len(latencies)
            return {
                'p50': latencies[n // 2],
                'p95': latencies[int(n * 0.95)] if n > 1 else latencies[0],
                'p99': latencies[int(n * 0.99)] if n > 1 else latencies[0],
                'count': n,
                'mean': round(sum(latencies) / n, 1),
                'min': latencies[0],
                'max': latencies[-1]
            }
        except Exception as e:
            logger.error(f"Latency percentiles error: {e}")
            return {'p50': 0, 'p95': 0, 'p99': 0, 'count': 0, 'mean': 0}

    @staticmethod
    def get_cost_summary(period: str = '24h') -> Dict:
        """Get cost breakdown by model and step for a time period."""
        try:
            conn = _get_conn()
            hours = int(period.replace('h', '').replace('d', '')) * (24 if 'd' in period else 1)
            cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()

            # Per-model cost
            by_model = conn.execute('''
                SELECT model, COUNT(*) as requests,
                       SUM(cost_usd) as main_cost,
                       SUM(total_cost_usd) as total_cost,
                       SUM(prompt_tokens) as prompt_tokens,
                       SUM(completion_tokens) as completion_tokens
                FROM pipeline_metrics WHERE timestamp > ?
                GROUP BY model
            ''', (cutoff,)).fetchall()

            # Total cost
            total = conn.execute('''
                SELECT COUNT(*) as requests,
                       SUM(total_cost_usd) as total_cost,
                       AVG(total_cost_usd) as avg_cost,
                       SUM(grounding_cost_usd) as grounding_cost,
                       SUM(embedding_cost_usd) as embedding_cost
                FROM pipeline_metrics WHERE timestamp > ?
            ''', (cutoff,)).fetchone()

            # Cost by hour trend
            hourly = conn.execute('''
                SELECT strftime('%Y-%m-%d %H:00', timestamp) as hour,
                       SUM(total_cost_usd) as cost, COUNT(*) as requests
                FROM pipeline_metrics WHERE timestamp > ?
                GROUP BY hour ORDER BY hour
            ''', (cutoff,)).fetchall()

            conn.close()

            return {
                'period': period,
                'total_requests': total['requests'] or 0,
                'total_cost_usd': round(total['total_cost'] or 0, 6),
                'avg_cost_per_request': round(total['avg_cost'] or 0, 6),
                'grounding_cost_usd': round(total['grounding_cost'] or 0, 6),
                'embedding_cost_usd': round(total['embedding_cost'] or 0, 6),
                'by_model': [dict(r) for r in by_model],
                'hourly_trend': [dict(r) for r in hourly]
            }
        except Exception as e:
            logger.error(f"Cost summary error: {e}")
            return {'error': str(e)}

    @staticmethod
    def get_throughput(period: str = '24h') -> Dict:
        """Get requests per hour trend."""
        try:
            conn = _get_conn()
            hours = int(period.replace('h', '').replace('d', '')) * (24 if 'd' in period else 1)
            cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()

            hourly = conn.execute('''
                SELECT strftime('%Y-%m-%d %H:00', timestamp) as hour,
                       COUNT(*) as requests,
                       AVG(total_latency_ms) as avg_latency
                FROM pipeline_metrics WHERE timestamp > ?
                GROUP BY hour ORDER BY hour
            ''', (cutoff,)).fetchall()

            total = conn.execute('''
                SELECT COUNT(*) as total FROM pipeline_metrics WHERE timestamp > ?
            ''', (cutoff,)).fetchone()

            conn.close()

            hours_elapsed = max(hours, 1)
            return {
                'period': period,
                'total_requests': total['total'] or 0,
                'avg_requests_per_hour': round((total['total'] or 0) / hours_elapsed, 2),
                'hourly_trend': [dict(r) for r in hourly]
            }
        except Exception as e:
            logger.error(f"Throughput error: {e}")
            return {'error': str(e)}

    @staticmethod
    def get_step_breakdown(period: str = '24h') -> Dict:
        """Get average time per pipeline step."""
        try:
            conn = _get_conn()
            hours = int(period.replace('h', '').replace('d', '')) * (24 if 'd' in period else 1)
            cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()

            rows = conn.execute('''
                SELECT step_timings FROM pipeline_metrics
                WHERE timestamp > ? AND step_timings IS NOT NULL
            ''', (cutoff,)).fetchall()
            conn.close()

            if not rows:
                return {'steps': {}, 'count': 0}

            step_sums = defaultdict(float)
            count = 0
            for row in rows:
                try:
                    timings = json.loads(row['step_timings'])
                    prev = 0
                    for key in sorted(timings.keys()):
                        delta = timings[key] - prev
                        step_sums[key] += delta * 1000  # convert to ms
                        prev = timings[key]
                    count += 1
                except (json.JSONDecodeError, TypeError):
                    continue

            steps = {k: round(v / max(count, 1), 1) for k, v in step_sums.items()}
            return {'steps': steps, 'count': count}
        except Exception as e:
            logger.error(f"Step breakdown error: {e}")
            return {'steps': {}, 'count': 0}

    @staticmethod
    def compute_hourly_aggregates():
        """Compute hourly aggregate metrics for anomaly detection baselines."""
        try:
            from intelligence.anomaly import AnomalyDetector

            conn = _get_conn()
            cutoff = (datetime.now() - timedelta(hours=1)).isoformat()

            row = conn.execute('''
                SELECT COUNT(*) as count,
                       AVG(total_latency_ms) as avg_latency,
                       AVG(total_cost_usd) as avg_cost,
                       SUM(total_cost_usd) as total_cost
                FROM pipeline_metrics WHERE timestamp > ?
            ''', (cutoff,)).fetchone()

            conn.close()

            if row and row['count'] > 0:
                # Store baseline data points for anomaly detector
                AnomalyDetector.record_metric('hourly_latency_avg', row['avg_latency'] or 0)
                AnomalyDetector.record_metric('hourly_cost_total', row['total_cost'] or 0)
                AnomalyDetector.record_metric('hourly_request_count', row['count'])

            log_event('pipeline_analytics', 'hourly_aggregates_computed')
        except Exception as e:
            logger.error(f"Hourly aggregates error: {e}")

    @staticmethod
    def check_budget() -> Dict:
        """
        Check cost budget utilization. Returns action recommendation.
        """
        from intelligence.features import FeatureFlags

        if not FeatureFlags.is_enabled('cost_enforcement'):
            return {'ok': True, 'action': 'none', 'daily_pct': 0, 'monthly_pct': 0}

        try:
            from config import Config
            conn = _get_conn()
            now = datetime.now()

            daily_key = now.strftime('%Y-%m-%d')
            monthly_key = now.strftime('%Y-%m')

            daily_row = conn.execute('''
                SELECT SUM(total_cost_usd) as total FROM cost_ledger
                WHERE period_type = 'daily' AND period_key = ?
            ''', (daily_key,)).fetchone()

            monthly_row = conn.execute('''
                SELECT SUM(total_cost_usd) as total FROM cost_ledger
                WHERE period_type = 'monthly' AND period_key = ?
            ''', (monthly_key,)).fetchone()
            conn.close()

            daily_spend = (daily_row['total'] or 0) if daily_row else 0
            monthly_spend = (monthly_row['total'] or 0) if monthly_row else 0

            daily_budget = Config.COST_BUDGET_DAILY
            monthly_budget = Config.COST_BUDGET_MONTHLY

            daily_pct = (daily_spend / daily_budget * 100) if daily_budget > 0 else 0
            monthly_pct = (monthly_spend / monthly_budget * 100) if monthly_budget > 0 else 0

            if daily_pct >= 100 or monthly_pct >= 100:
                action = 'budget_exceeded'
            elif daily_pct >= 80 or monthly_pct >= 80:
                action = 'fallback_model'
            else:
                action = 'none'

            return {
                'ok': action == 'none',
                'daily_pct': round(daily_pct, 1),
                'monthly_pct': round(monthly_pct, 1),
                'daily_spend': round(daily_spend, 4),
                'monthly_spend': round(monthly_spend, 4),
                'daily_budget': daily_budget,
                'monthly_budget': monthly_budget,
                'action': action
            }
        except Exception as e:
            logger.error(f"Budget check error: {e}")
            return {'ok': True, 'action': 'none', 'daily_pct': 0, 'monthly_pct': 0, 'error': str(e)}
