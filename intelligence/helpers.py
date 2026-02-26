"""
Intelligence Engine — Helper functions
=======================================
Pure utility functions used across subsystems.
"""

import math
from typing import List, Dict, Tuple
from collections import defaultdict


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _keyword_similarity(text1: str, text2: str) -> float:
    """Simple keyword overlap similarity (Jaccard on words)."""
    if not text1 or not text2:
        return 0.0
    stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
                  'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
                  'would', 'could', 'should', 'may', 'might', 'can', 'shall',
                  'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from',
                  'it', 'this', 'that', 'and', 'or', 'but', 'not', 'what',
                  'how', 'when', 'where', 'which', 'who', 'i', 'my', 'me'}
    words1 = set(w.lower().strip('.,?!') for w in text1.split()) - stop_words
    words2 = set(w.lower().strip('.,?!') for w in text2.split()) - stop_words
    if not words1 or not words2:
        return 0.0
    intersection = words1 & words2
    union = words1 | words2
    return len(intersection) / len(union) if union else 0.0


def _wilson_score_interval(positive: int, total: int, z: float = 1.96) -> Tuple[float, float]:
    """Wilson score confidence interval for binomial proportion."""
    if total == 0:
        return (0.0, 0.0)
    p_hat = positive / total
    denominator = 1 + z * z / total
    center = (p_hat + z * z / (2 * total)) / denominator
    spread = z * math.sqrt((p_hat * (1 - p_hat) + z * z / (4 * total)) / total) / denominator
    return (max(0, center - spread), min(1, center + spread))


def _sigmoid(z: float) -> float:
    """Sigmoid activation function."""
    if z > 500:
        return 1.0
    if z < -500:
        return 0.0
    return 1.0 / (1.0 + math.exp(-z))


def _isotonic_regression(x: List[float], y: List[float]) -> List[float]:
    """
    Pool-adjacent-violators algorithm for isotonic regression.
    Ensures output is non-decreasing.
    """
    n = len(y)
    if n == 0:
        return []

    result = list(y)
    # Forward pass: ensure non-decreasing
    i = 0
    while i < n:
        j = i
        sum_val = result[i]
        count = 1

        while j + 1 < n and result[j + 1] < sum_val / count:
            j += 1
            sum_val += result[j]
            count += 1

        avg = sum_val / count
        for k in range(i, j + 1):
            result[k] = avg

        i = j + 1

    return result


def _compute_drift_score(expected: str, actual: str, criteria: str = None) -> Dict:
    """
    Compute semantic drift between expected and actual answers.
    Returns score (0=identical, 1=completely different) and issues list.
    """
    if not actual:
        return {'score': 1.0, 'issues': ['No answer generated']}

    issues = []
    score = 0.0

    # Keyword overlap
    keyword_sim = _keyword_similarity(expected, actual)
    keyword_drift = 1.0 - keyword_sim
    score += keyword_drift * 0.4

    # Length ratio
    len_ratio = len(actual) / max(len(expected), 1)
    if len_ratio < 0.3 or len_ratio > 3.0:
        issues.append(f"Length ratio: {len_ratio:.1f}x")
        score += 0.2

    # Check criteria keywords if provided
    if criteria:
        criteria_keywords = [k.strip().lower() for k in criteria.split(',')]
        actual_lower = actual.lower()
        missing = [k for k in criteria_keywords if k and k not in actual_lower]
        if missing:
            issues.append(f"Missing criteria: {', '.join(missing)}")
            score += len(missing) / max(len(criteria_keywords), 1) * 0.4

    score = min(1.0, score)
    if keyword_drift > 0.7:
        issues.append(f"Low keyword overlap ({keyword_sim:.2f})")

    return {'score': round(score, 3), 'issues': issues}


def _agglomerative_cluster(embeddings: List[List[float]], threshold: float = 0.7,
                           min_size: int = 5) -> Dict[int, List[int]]:
    """
    Simple agglomerative clustering using cosine similarity.
    Returns dict of cluster_id -> list of member indices.
    """
    n = len(embeddings)
    if n == 0:
        return {}

    # Start with each point as its own cluster
    assignments = list(range(n))

    # Compute pairwise similarities (only upper triangle, limit for performance)
    pairs = []

    # Sample pairs if too many
    if n > 300:
        import random
        sample_indices = random.sample(range(n), min(300, n))
        for i in range(len(sample_indices)):
            for j in range(i + 1, len(sample_indices)):
                idx_i = sample_indices[i]
                idx_j = sample_indices[j]
                sim = _cosine_similarity(embeddings[idx_i], embeddings[idx_j])
                if sim >= threshold:
                    pairs.append((idx_i, idx_j, sim))
    else:
        for i in range(n):
            for j in range(i + 1, n):
                sim = _cosine_similarity(embeddings[i], embeddings[j])
                if sim >= threshold:
                    pairs.append((i, j, sim))

    # Sort by similarity descending
    pairs.sort(key=lambda x: x[2], reverse=True)

    # Merge clusters greedily
    for i, j, sim in pairs:
        ci = assignments[i]
        cj = assignments[j]
        if ci != cj:
            # Merge smaller into larger
            target = min(ci, cj)
            source = max(ci, cj)
            for k in range(n):
                if assignments[k] == source:
                    assignments[k] = target

    # Build cluster dict
    clusters = defaultdict(list)
    for idx, cluster_id in enumerate(assignments):
        clusters[cluster_id].append(idx)

    # Filter by min size
    return {k: v for k, v in clusters.items() if len(v) >= min_size}


def _compute_centroid(embeddings: List[List[float]]) -> List[float]:
    """Compute the centroid of a list of embeddings."""
    if not embeddings:
        return []
    dim = len(embeddings[0])
    centroid = [0.0] * dim
    for emb in embeddings:
        for i in range(dim):
            centroid[i] += emb[i]
    n = len(embeddings)
    return [c / n for c in centroid]


def _auto_name_cluster(questions: List[str]) -> str:
    """Auto-generate a cluster name from common keywords in questions."""
    stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
                  'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
                  'could', 'should', 'can', 'to', 'of', 'in', 'for', 'on',
                  'with', 'at', 'by', 'from', 'it', 'this', 'that', 'and',
                  'or', 'but', 'not', 'what', 'how', 'when', 'where', 'which',
                  'who', 'i', 'my', 'me', 'best', 'good', 'use', 'need'}

    word_counts = defaultdict(int)
    for q in questions:
        words = set(w.lower().strip('.,?!') for w in q.split()) - stop_words
        for w in words:
            if len(w) > 2:
                word_counts[w] += 1

    top_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)[:3]
    if top_words:
        return ' '.join(w[0].title() for w in top_words)
    return 'Uncategorized'
