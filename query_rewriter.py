"""
LLM-based query rewriting for improved search retrieval.
Uses GPT-4o-mini for cost-effective query expansion and clarification.
"""
import logging
from cache import get_embedding_cache

logger = logging.getLogger(__name__)

# Rewriter prompt template
REWRITE_PROMPT = """You are a query rewriter for a golf course turf management knowledge base. Your job is to transform user questions into optimized search queries.

The knowledge base contains:
- Product labels (fungicides, herbicides, insecticides, PGRs)
- Disease control guides with efficacy ratings
- Cultural practice guides (mowing, irrigation, aeration)
- Equipment manuals
- University research papers

Transform the user's question into a clear, specific search query that will retrieve the most relevant documents.

Rules:
1. Expand abbreviations (DS → dollar spot, BP → brown patch)
2. Add relevant context (grass type if mentioned, product category)
3. Include synonyms for key terms
4. Keep the query under 100 words
5. If the question is already specific, make minimal changes
6. For product questions, include "rate" and "application"
7. For disease questions, include "control" and "fungicide"
8. For weed questions, include "herbicide" and the weed lifecycle (annual/perennial)

Examples:
- "heritage rate" → "Heritage fungicide application rate per 1000 sq ft azoxystrobin dosage timing"
- "brown spots on my green" → "Brown patch disease diagnosis bentgrass putting green fungicide control Rhizoctonia"
- "when to spray barricade" → "Barricade prodiamine pre-emergent herbicide application timing soil temperature spring"
- "my bermuda is dying" → "Bermudagrass decline diagnosis disease insect damage cultural stress symptoms"

User question: {question}

Rewritten query:"""


# Simple cache for rewritten queries
_rewrite_cache = {}


def rewrite_query(openai_client, question: str, model: str = "gpt-4o-mini") -> str:
    """
    Rewrite a user question into an optimized search query.

    Args:
        openai_client: OpenAI client instance
        question: Original user question
        model: Model to use (default: gpt-4o-mini for cost efficiency)

    Returns:
        Rewritten, optimized search query
    """
    # Check cache first
    cache_key = question.lower().strip()
    if cache_key in _rewrite_cache:
        logger.debug(f"Query rewrite cache hit: {question[:50]}")
        return _rewrite_cache[cache_key]

    # Skip rewriting for already detailed questions
    if len(question) > 150:
        logger.debug("Question already detailed, skipping rewrite")
        return question

    try:
        response = openai_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "user", "content": REWRITE_PROMPT.format(question=question)}
            ],
            max_tokens=150,
            temperature=0.3
        )

        rewritten = response.choices[0].message.content.strip()

        # Sanity check - don't use if it's way too long or empty
        if not rewritten or len(rewritten) > 500:
            logger.warning("Query rewrite produced invalid result, using original")
            return question

        # Cache the result
        _rewrite_cache[cache_key] = rewritten

        logger.info(f"Query rewritten: '{question[:50]}' → '{rewritten[:50]}'")
        return rewritten

    except Exception as e:
        logger.error(f"Query rewrite failed: {e}")
        return question  # Fall back to original


def clear_rewrite_cache():
    """Clear the query rewrite cache."""
    global _rewrite_cache
    _rewrite_cache = {}
