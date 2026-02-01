"""
Cross-encoder reranking for improved search result relevance.
Uses a lightweight model to score query-document pairs more accurately than vector similarity.
Falls back to BM25 if cross-encoder is unavailable.
"""
import logging
from typing import List, Dict, Optional
from functools import lru_cache

logger = logging.getLogger(__name__)

# Try to import sentence-transformers for cross-encoder
_cross_encoder = None
_cross_encoder_available = False

try:
    from sentence_transformers import CrossEncoder
    _cross_encoder_available = True
except ImportError:
    logger.warning("sentence-transformers not installed. Using BM25-only reranking.")


def get_cross_encoder():
    """
    Get or initialize the cross-encoder model.
    Uses a small, fast model suitable for reranking.
    """
    global _cross_encoder

    if not _cross_encoder_available:
        return None

    if _cross_encoder is None:
        try:
            # Use a small, fast cross-encoder model
            # ms-marco-MiniLM-L-6-v2 is optimized for passage reranking
            _cross_encoder = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2', max_length=512)
            logger.info("Cross-encoder model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load cross-encoder: {e}")
            return None

    return _cross_encoder


def rerank_with_cross_encoder(
    query: str,
    results: List[Dict],
    top_k: int = 20
) -> List[Dict]:
    """
    Rerank search results using a cross-encoder model.

    Cross-encoders jointly encode query and document together,
    allowing for better semantic matching than bi-encoder approaches.

    Args:
        query: The search query
        results: List of search results with 'metadata' containing 'text'
        top_k: Number of top results to return

    Returns:
        Reranked results sorted by cross-encoder score
    """
    if not results:
        return []

    encoder = get_cross_encoder()

    if encoder is None:
        # Fall back to returning results as-is (already BM25 reranked)
        logger.debug("Cross-encoder unavailable, using existing ranking")
        return results[:top_k]

    try:
        # Prepare query-document pairs
        pairs = []
        valid_indices = []

        for i, result in enumerate(results):
            text = result.get('metadata', {}).get('text', '')
            source = result.get('metadata', {}).get('source', '')

            if text:
                # Include source name for context
                doc_text = f"{source}: {text[:500]}"  # Limit length for efficiency
                pairs.append([query, doc_text])
                valid_indices.append(i)

        if not pairs:
            return results[:top_k]

        # Get cross-encoder scores
        scores = encoder.predict(pairs)

        # Combine scores with original results
        scored_results = []
        for idx, score in zip(valid_indices, scores):
            result = results[idx].copy()
            result['cross_encoder_score'] = float(score)
            # Blend cross-encoder score with original score
            original_score = result.get('rrf_score', result.get('score', 0))
            result['final_score'] = 0.7 * float(score) + 0.3 * original_score * 10
            scored_results.append(result)

        # Sort by final blended score
        scored_results.sort(key=lambda x: x['final_score'], reverse=True)

        logger.debug(f"Cross-encoder reranked {len(scored_results)} results")
        return scored_results[:top_k]

    except Exception as e:
        logger.error(f"Cross-encoder reranking failed: {e}")
        return results[:top_k]


def rerank_results(
    query: str,
    results: List[Dict],
    top_k: int = 20,
    use_cross_encoder: bool = True
) -> List[Dict]:
    """
    Main reranking function that combines multiple reranking strategies.

    Pipeline:
    1. BM25 hybrid reranking (already applied in scoring_service)
    2. Cross-encoder reranking (if available and enabled)

    Args:
        query: Search query
        results: Search results (already BM25 reranked)
        top_k: Number of results to return
        use_cross_encoder: Whether to apply cross-encoder reranking

    Returns:
        Final reranked results
    """
    if not results:
        return []

    # Apply cross-encoder reranking if enabled
    if use_cross_encoder and _cross_encoder_available:
        results = rerank_with_cross_encoder(query, results, top_k=min(top_k * 2, len(results)))

    return results[:top_k]


def is_cross_encoder_available() -> bool:
    """Check if cross-encoder reranking is available."""
    return _cross_encoder_available and get_cross_encoder() is not None
