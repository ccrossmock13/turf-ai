"""
Web search fallback for when Pinecone returns no results.
Only triggered when vector search returns empty results, NOT for low confidence.
"""
import logging
from typing import Dict, List, Optional, Any
import openai

logger = logging.getLogger(__name__)

# Trusted turf management domains for web search
TRUSTED_DOMAINS = [
    "extension.umn.edu",
    "extension.psu.edu",
    "extension.purdue.edu",
    "turf.uconn.edu",
    "plantscience.psu.edu",
    "cals.ncsu.edu",
    "uky.edu",
    "extension.missouri.edu",
    "hort.purdue.edu",
    "ca.uky.edu",
    "gcsaa.org",
    "usga.org",
    "ars.usda.gov",
    "cropscience.bayer.us",
    "syngenta.com",
    "basf.com",
    "corteva.com",
]


def should_trigger_web_search(pinecone_results: Dict) -> bool:
    """
    Determine if web search should be triggered.

    Only returns True when Pinecone returns NO results.
    Does NOT trigger for low confidence results - those still have data to use.

    Args:
        pinecone_results: Results from Pinecone search

    Returns:
        True only if results are completely empty
    """
    if not pinecone_results:
        return True

    # Check all result categories
    general_matches = pinecone_results.get('general', {}).get('matches', [])
    product_matches = pinecone_results.get('product', {}).get('matches', [])
    timing_matches = pinecone_results.get('timing', {}).get('matches', [])

    total_matches = len(general_matches) + len(product_matches) + len(timing_matches)

    # Only trigger if absolutely no results
    return total_matches == 0


def search_web_for_turf_info(
    openai_client: openai.OpenAI,
    question: str,
    model: str = "gpt-4o-mini"
) -> Optional[Dict[str, Any]]:
    """
    Search the web for turf management information using OpenAI's knowledge.

    This is a fallback when our vector database has no relevant information.
    Uses the LLM's training data which includes university extension content.

    Args:
        openai_client: OpenAI client instance
        question: User's question
        model: Model to use for generating response

    Returns:
        Dict with 'context' and 'sources' or None if search fails
    """
    try:
        # Use a specific prompt to get academic/extension-quality information
        search_prompt = f"""You are a turfgrass research assistant. The user asked a question about turfgrass management,
but our primary database has no information on this topic.

Please provide research-based information to answer this question. Focus on:
1. Information from university extension services (like Penn State, Purdue, NC State, UK, etc.)
2. Scientific research and peer-reviewed findings
3. Industry best practices from GCSAA, USGA, or major turf chemical companies

Question: {question}

Provide a detailed, technical response with:
- Specific recommendations with rates/timings when applicable
- Scientific reasoning behind recommendations
- Any important caveats or regional considerations

Format your response as if it were coming from a university extension bulletin.
If you're not certain about specific rates or timings, say so rather than guessing."""

        response = openai_client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a turfgrass PhD providing research-based information. "
                               "Always be accurate and cite your reasoning. "
                               "If you're uncertain about specific details, acknowledge it."
                },
                {"role": "user", "content": search_prompt}
            ],
            temperature=0.3,
            max_tokens=1500
        )

        web_content = response.choices[0].message.content

        # Build context for the main response
        context = f"""[WEB SEARCH RESULT - No matches in verified database]

{web_content}

NOTE: This information is from general knowledge, not our verified document database.
Please verify critical rates and recommendations with product labels or local extension services."""

        # Create a generic source indicating web search was used
        sources = [{
            'title': 'Web Search Result (General Knowledge)',
            'url': None,
            'note': 'No matches found in verified database. Information from general turf science knowledge.'
        }]

        return {
            'context': context,
            'sources': sources,
            'is_web_search': True
        }

    except Exception as e:
        logger.error(f"Web search failed: {e}")
        return None


def format_web_search_disclaimer() -> str:
    """
    Return a disclaimer to prepend to web search results.
    """
    return (
        "⚠️ **Note:** This response is based on general turfgrass knowledge, "
        "not our verified document database. Please verify specific rates "
        "and recommendations with product labels or your local extension service."
    )
