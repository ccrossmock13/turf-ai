"""
Intelligence Engine — Subsystems 7 & 14: Satisfaction Prediction
=================================================================
SatisfactionPredictor (logistic regression) and
GradientBoostedPredictor (gradient boosted decision trees).
"""

import json
import math
import logging
from datetime import datetime
from typing import List, Dict

from intelligence.db import _get_conn, log_event
from intelligence.helpers import _sigmoid

logger = logging.getLogger(__name__)


class SatisfactionPredictor:
    """
    Pure-Python logistic regression to predict satisfaction before users rate.
    No sklearn dependency -- implements gradient descent from scratch.
    """

    # Model weights stored in memory (retrained periodically)
    _weights = None
    _bias = 0.0
    _feature_means = None
    _feature_stds = None
    _model_version = 0

    @staticmethod
    def extract_features(confidence: float, source_count: int, response_length: int,
                         grounding_score: float = 1.0, hallucination_penalties: int = 0,
                         topic_difficulty: float = 0.5, hour_of_day: int = 12) -> List[float]:
        """Extract feature vector from answer data."""
        return [
            confidence / 100.0,            # Normalized confidence
            min(source_count / 10.0, 1.0),  # Normalized source count
            min(response_length / 1000.0, 1.0),  # Normalized length
            grounding_score,                # 0-1
            hallucination_penalties / 5.0,  # Normalized penalties
            topic_difficulty,               # 0-1
            math.sin(2 * math.pi * hour_of_day / 24),  # Cyclical time encoding
            math.cos(2 * math.pi * hour_of_day / 24),
        ]

    @staticmethod
    def train_satisfaction_model(min_samples: int = 50) -> Dict:
        """
        Train logistic regression on historical feedback data.
        Pure Python implementation -- no external ML libraries.
        """
        conn = _get_conn()
        rows = conn.execute('''
            SELECT f.confidence_score, f.sources, f.ai_answer, f.user_rating, f.timestamp
            FROM feedback f
            WHERE f.user_rating != 'unrated' AND f.confidence_score IS NOT NULL
            ORDER BY f.timestamp DESC LIMIT 2000
        ''').fetchall()
        conn.close()

        if len(rows) < min_samples:
            return {'success': False, 'reason': f'Need {min_samples} samples, have {len(rows)}'}

        # Build feature matrix and labels
        X = []
        y = []
        for row in rows:
            sources = json.loads(row['sources']) if row['sources'] else []
            hour = datetime.fromisoformat(row['timestamp']).hour if row['timestamp'] else 12
            features = SatisfactionPredictor.extract_features(
                confidence=row['confidence_score'] or 50,
                source_count=len(sources),
                response_length=len(row['ai_answer'] or ''),
                hour_of_day=hour
            )
            X.append(features)
            label = 1.0 if row['user_rating'] in ('helpful', 'good', 'correct') else 0.0
            y.append(label)

        # Normalize features
        n_features = len(X[0])
        means = [sum(x[i] for x in X) / len(X) for i in range(n_features)]
        stds = [max(0.001, math.sqrt(sum((x[i] - means[i])**2 for x in X) / len(X)))
                for i in range(n_features)]

        X_norm = [[(x[i] - means[i]) / stds[i] for i in range(n_features)] for x in X]

        # Logistic regression via gradient descent
        weights = [0.0] * n_features
        bias = 0.0
        lr = 0.1
        epochs = 100

        for epoch in range(epochs):
            grad_w = [0.0] * n_features
            grad_b = 0.0

            for x, label in zip(X_norm, y):
                z = sum(w * xi for w, xi in zip(weights, x)) + bias
                pred = _sigmoid(z)
                error = pred - label

                for j in range(n_features):
                    grad_w[j] += error * x[j]
                grad_b += error

            # Update
            for j in range(n_features):
                weights[j] -= lr * grad_w[j] / len(X)
            bias -= lr * grad_b / len(X)

        # Store model
        SatisfactionPredictor._weights = weights
        SatisfactionPredictor._bias = bias
        SatisfactionPredictor._feature_means = means
        SatisfactionPredictor._feature_stds = stds
        SatisfactionPredictor._model_version += 1

        # Compute accuracy
        correct = 0
        for x, label in zip(X_norm, y):
            z = sum(w * xi for w, xi in zip(weights, x)) + bias
            pred = 1.0 if _sigmoid(z) > 0.5 else 0.0
            if pred == label:
                correct += 1

        accuracy = correct / len(X)
        log_event('satisfaction_prediction', 'model_trained',
                  json.dumps({'accuracy': round(accuracy, 3), 'samples': len(X),
                             'version': SatisfactionPredictor._model_version}))

        return {
            'success': True,
            'accuracy': round(accuracy, 3),
            'samples': len(X),
            'version': SatisfactionPredictor._model_version
        }

    @staticmethod
    def predict_satisfaction(features: List[float]) -> float:
        """Predict probability of positive satisfaction (0-1)."""
        if SatisfactionPredictor._weights is None:
            return 0.5  # No model trained yet

        # Normalize
        means = SatisfactionPredictor._feature_means
        stds = SatisfactionPredictor._feature_stds
        x_norm = [(f - m) / s for f, m, s in zip(features, means, stds)]

        z = sum(w * xi for w, xi in zip(SatisfactionPredictor._weights, x_norm))
        z += SatisfactionPredictor._bias
        return _sigmoid(z)

    @staticmethod
    def record_prediction(query_id: int, probability: float, features: List[float],
                          actual_rating: str = None):
        """Store a prediction for later evaluation."""
        was_correct = None
        if actual_rating:
            predicted_positive = probability > 0.5
            actual_positive = actual_rating in ('helpful', 'good', 'correct')
            was_correct = predicted_positive == actual_positive

        conn = _get_conn()
        conn.execute('''
            INSERT INTO satisfaction_predictions
            (query_id, predicted_probability, features, actual_rating, was_correct, model_version)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (query_id, probability, json.dumps(features), actual_rating, was_correct,
              SatisfactionPredictor._model_version))
        conn.commit()
        conn.close()

    @staticmethod
    def get_prediction_accuracy() -> Dict:
        """Get prediction model accuracy stats."""
        conn = _get_conn()
        rows = conn.execute('''
            SELECT was_correct, model_version FROM satisfaction_predictions
            WHERE was_correct IS NOT NULL
            ORDER BY timestamp DESC LIMIT 500
        ''').fetchall()
        conn.close()

        if not rows:
            return {'accuracy': 0, 'total': 0}

        correct = sum(1 for r in rows if r['was_correct'])
        return {
            'accuracy': round(correct / len(rows), 3),
            'total': len(rows),
            'correct': correct,
            'model_version': SatisfactionPredictor._model_version
        }


class DecisionStump:
    """A single decision tree stump (max depth 3) for gradient boosting."""

    def __init__(self, max_depth: int = 3):
        self.max_depth = max_depth
        self.tree = None

    def fit(self, X: List[List[float]], residuals: List[float]):
        """Fit a decision tree on features and residuals."""
        self.tree = self._build_tree(X, residuals, depth=0)

    def predict(self, X: List[List[float]]) -> List[float]:
        """Predict for a list of samples."""
        return [self._predict_one(x) for x in X]

    def _predict_one(self, x: List[float]) -> float:
        node = self.tree
        if node is None:
            return 0.0
        while node.get('left') is not None:
            if x[node['feature']] <= node['threshold']:
                node = node['left']
            else:
                node = node['right']
        return node['value']

    def _build_tree(self, X: List[List[float]], residuals: List[float], depth: int) -> Dict:
        if not X or depth >= self.max_depth or len(X) < 4:
            val = sum(residuals) / max(len(residuals), 1)
            return {'value': val}

        best_feature = -1
        best_threshold = 0
        best_gain = -1
        n = len(X)
        n_features = len(X[0]) if X else 0

        total_sum = sum(residuals)
        total_sq = sum(r * r for r in residuals)
        base_var = total_sq / n - (total_sum / n) ** 2

        for f in range(n_features):
            # Get unique sorted values
            vals = sorted(set(x[f] for x in X))
            if len(vals) < 2:
                continue

            # Try midpoint thresholds (sample if too many)
            thresholds = []
            step = max(1, len(vals) // 10)
            for i in range(0, len(vals) - 1, step):
                thresholds.append((vals[i] + vals[i + 1]) / 2)

            for t in thresholds:
                left_r = [residuals[i] for i in range(n) if X[i][f] <= t]
                right_r = [residuals[i] for i in range(n) if X[i][f] > t]

                if len(left_r) < 2 or len(right_r) < 2:
                    continue

                # Variance reduction
                left_mean = sum(left_r) / len(left_r)
                right_mean = sum(right_r) / len(right_r)
                left_var = sum((r - left_mean) ** 2 for r in left_r) / len(left_r)
                right_var = sum((r - right_mean) ** 2 for r in right_r) / len(right_r)
                weighted_var = (len(left_r) * left_var + len(right_r) * right_var) / n
                gain = base_var - weighted_var

                if gain > best_gain:
                    best_gain = gain
                    best_feature = f
                    best_threshold = t

        if best_feature < 0 or best_gain < 1e-6:
            val = sum(residuals) / n
            return {'value': val}

        left_idx = [i for i in range(n) if X[i][best_feature] <= best_threshold]
        right_idx = [i for i in range(n) if X[i][best_feature] > best_threshold]

        return {
            'feature': best_feature,
            'threshold': best_threshold,
            'gain': best_gain,
            'left': self._build_tree([X[i] for i in left_idx],
                                     [residuals[i] for i in left_idx], depth + 1),
            'right': self._build_tree([X[i] for i in right_idx],
                                      [residuals[i] for i in right_idx], depth + 1)
        }


class GradientBoostedPredictor:
    """Pure-Python gradient boosted decision trees for satisfaction prediction."""

    _model = None  # {'trees': [...], 'base_prediction': float, 'feature_names': [...]}
    _feature_names = [
        'confidence', 'source_count', 'response_length', 'grounding_score',
        'hallucination_count', 'topic_difficulty', 'hour_of_day', 'day_of_week',
        'query_word_count', 'has_web_search', 'has_weather', 'num_images',
        'latency_ms', 'cost_usd', 'source_avg_trust', 'question_specificity',
        'is_follow_up', 'conversation_turn', 'category_lawn', 'category_disease',
        'category_weed', 'category_pest', 'category_fertilizer'
    ]

    @staticmethod
    def train(n_trees: int = 50, learning_rate: float = 0.1, max_depth: int = 3) -> Dict:
        """Train gradient boosted model on historical data."""
        try:
            conn = _get_conn()
            # Fetch labeled data (predictions that got actual ratings)
            rows = conn.execute('''
                SELECT sp.features, sp.actual_rating, sp.predicted_probability,
                       pm.total_latency_ms, pm.total_cost_usd
                FROM satisfaction_predictions sp
                LEFT JOIN pipeline_metrics pm ON sp.query_id = pm.query_id
                WHERE sp.actual_rating IS NOT NULL
                ORDER BY sp.timestamp DESC LIMIT 5000
            ''').fetchall()
            conn.close()

            if len(rows) < 50:
                return {'status': 'insufficient_data', 'count': len(rows)}

            # Build feature matrix and labels
            X = []
            y = []
            for row in rows:
                try:
                    features = json.loads(row['features']) if row['features'] else {}
                    if isinstance(features, dict):
                        feature_vec = [features.get(name, 0.0) for name in GradientBoostedPredictor._feature_names]
                    elif isinstance(features, list):
                        feature_vec = features + [0.0] * max(0, len(GradientBoostedPredictor._feature_names) - len(features))
                    else:
                        continue

                    # Add latency and cost from pipeline_metrics if available
                    if row['total_latency_ms']:
                        idx_lat = GradientBoostedPredictor._feature_names.index('latency_ms')
                        feature_vec[idx_lat] = row['total_latency_ms']
                    if row['total_cost_usd']:
                        idx_cost = GradientBoostedPredictor._feature_names.index('cost_usd')
                        feature_vec[idx_cost] = row['total_cost_usd']

                    X.append(feature_vec)
                    label = 1.0 if row['actual_rating'] in ('helpful', 'good', 'correct') else 0.0
                    y.append(label)
                except (json.JSONDecodeError, TypeError, ValueError):
                    continue

            if len(X) < 30:
                return {'status': 'insufficient_valid_data', 'count': len(X)}

            # Train gradient boosted model
            n = len(X)
            base_pred = sum(y) / n
            predictions = [base_pred] * n
            trees = []

            for i in range(n_trees):
                # Compute residuals
                residuals = [y[j] - predictions[j] for j in range(n)]

                # Fit a tree on residuals
                stump = DecisionStump(max_depth=max_depth)
                stump.fit(X, residuals)
                tree_preds = stump.predict(X)

                # Update predictions
                for j in range(n):
                    predictions[j] += learning_rate * tree_preds[j]
                    predictions[j] = max(0.01, min(0.99, predictions[j]))

                trees.append(stump.tree)

            # Compute feature importance (sum of gains per feature)
            importance = [0.0] * len(GradientBoostedPredictor._feature_names)
            for tree in trees:
                GradientBoostedPredictor._accumulate_importance(tree, importance)

            total_imp = sum(importance) or 1
            importance = [round(imp / total_imp, 4) for imp in importance]

            # Compute accuracy
            correct = sum(1 for j in range(n) if (predictions[j] > 0.5) == (y[j] > 0.5))
            accuracy = correct / n

            # Store model
            GradientBoostedPredictor._model = {
                'trees': trees,
                'base_prediction': base_pred,
                'learning_rate': learning_rate,
                'n_trees': len(trees),
                'feature_names': GradientBoostedPredictor._feature_names,
                'feature_importance': importance,
                'training_accuracy': accuracy,
                'training_samples': n,
                'trained_at': datetime.now().isoformat()
            }

            log_event('gradient_boosted', 'model_trained',
                      json.dumps({'accuracy': round(accuracy, 4), 'samples': n,
                                  'trees': len(trees)}))

            return {
                'status': 'trained',
                'accuracy': round(accuracy, 4),
                'samples': n,
                'trees': len(trees),
                'feature_importance': dict(zip(GradientBoostedPredictor._feature_names, importance))
            }
        except Exception as e:
            logger.error(f"Gradient boosted training error: {e}")
            return {'status': 'error', 'message': str(e)}

    @staticmethod
    def _accumulate_importance(node: Dict, importance: List[float]):
        if node is None or 'feature' not in node:
            return
        importance[node['feature']] += node.get('gain', 0)
        if node.get('left'):
            GradientBoostedPredictor._accumulate_importance(node['left'], importance)
        if node.get('right'):
            GradientBoostedPredictor._accumulate_importance(node['right'], importance)

    @staticmethod
    def predict(features: List[float]) -> float:
        """Predict satisfaction probability using gradient boosted model."""
        model = GradientBoostedPredictor._model
        if model is None:
            return 0.5  # No model trained yet, return neutral

        prediction = model['base_prediction']
        lr = model['learning_rate']

        for tree in model['trees']:
            node = tree
            if node is None:
                continue
            while node and node.get('left') is not None:
                feat_idx = node['feature']
                if feat_idx < len(features) and features[feat_idx] <= node['threshold']:
                    node = node['left']
                else:
                    node = node['right']
            if node:
                prediction += lr * node.get('value', 0)

        return max(0.01, min(0.99, prediction))

    @staticmethod
    def feature_importance() -> Dict:
        """Get feature importance from the trained model."""
        model = GradientBoostedPredictor._model
        if not model:
            return {'status': 'no_model'}

        imp = model.get('feature_importance', [])
        names = model.get('feature_names', [])
        ranked = sorted(zip(names, imp), key=lambda x: x[1], reverse=True)
        return {
            'ranked': [{'feature': n, 'importance': i} for n, i in ranked],
            'accuracy': model.get('training_accuracy'),
            'samples': model.get('training_samples'),
            'trees': model.get('n_trees'),
            'trained_at': model.get('trained_at')
        }
