"""
Web search fallback for when Pinecone returns no results.
Only triggered when vector search returns empty results, NOT for low confidence.

Supports two modes:
1. Tavily API (real web search) - if TAVILY_API_KEY is set
2. OpenAI knowledge fallback - if no Tavily key
"""
import logging
import os
from typing import Dict, List, Optional, Any
import openai

logger = logging.getLogger(__name__)

# Try to import tavily
try:
    from tavily import TavilyClient
    TAVILY_AVAILABLE = True
except ImportError:
    TAVILY_AVAILABLE = False
    logger.info("Tavily not installed. Using OpenAI knowledge fallback for web search.")

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
    "greencast.basf.us",
    "turffactsheets.msu.edu",
]


def should_trigger_web_search(pinecone_results: Dict) -> bool:
    """
    Determine if web search should be triggered.

    Only returns True when Pinecone returns NO results.
    Does NOT trigger for low confidence results - those still have data to use.
    """
    if not pinecone_results:
        return True

    general_matches = pinecone_results.get('general', {}).get('matches', [])
    product_matches = pinecone_results.get('product', {}).get('matches', [])
    timing_matches = pinecone_results.get('timing', {}).get('matches', [])

    total_matches = len(general_matches) + len(product_matches) + len(timing_matches)
    return total_matches == 0


def _search_with_tavily(question: str) -> Optional[Dict[str, Any]]:
    """
    Perform real web search using Tavily API.
    Focuses on university extension and trusted turf sources.
    """
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key or not TAVILY_AVAILABLE:
        return None

    try:
        client = TavilyClient(api_key=api_key)

        # Build search query focused on turf management
        search_query = f"turfgrass {question} site:edu OR site:gcsaa.org OR site:usga.org"

        # Search with Tavily
        response = client.search(
            query=search_query,
            search_depth="advanced",
            include_domains=TRUSTED_DOMAINS,
            max_results=5,
            include_answer=True,
            include_raw_content=False,
        )

        if not response or not response.get('results'):
            return None

        # Build context from search results
        context_parts = ["[WEB SEARCH RESULTS - Real-time search from university extensions]\n"]
        sources = []

        # Add Tavily's AI-generated answer if available
        if response.get('answer'):
            context_parts.append(f"Summary: {response['answer']}\n")

        # Add individual search results
        for i, result in enumerate(response.get('results', [])[:5], 1):
            title = result.get('title', 'Unknown')
            content = result.get('content', '')[:500]  # Limit content length
            url = result.get('url', '')

            context_parts.append(f"\n[Source {i}: {title}]\n{content}\n")

            sources.append({
                'title': title,
                'url': url,
                'note': 'From web search'
            })

        context = "\n".join(context_parts)
        context += "\n\nNOTE: These are real-time web search results. Always verify rates with product labels."

        return {
            'context': context,
            'sources': sources,
            'is_web_search': True,
            'search_type': 'tavily'
        }

    except Exception as e:
        logger.error(f"Tavily search failed: {e}")
        return None


def _search_with_openai_fallback(
    openai_client: openai.OpenAI,
    question: str,
    model: str = "gpt-4o-mini"
) -> Optional[Dict[str, Any]]:
    """
    Fallback to OpenAI's knowledge when Tavily is not available.
    """
    try:
        search_prompt = f"""You are a turfgrass research assistant. The user asked a question about turfgrass management,
but our primary database has no information on this topic.

Please provide research-based information to answer this question. Focus on:
1. Information from university extension services (Penn State, Purdue, NC State, UK, etc.)
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

        context = f"""[WEB SEARCH RESULT - No matches in verified database]

{web_content}

NOTE: This information is from general knowledge, not our verified document database.
Please verify critical rates and recommendations with product labels or local extension services."""

        sources = [{
            'title': 'Web Search Result (General Knowledge)',
            'url': None,
            'note': 'No matches found in verified database. Information from general turf science knowledge.'
        }]

        return {
            'context': context,
            'sources': sources,
            'is_web_search': True,
            'search_type': 'openai_fallback'
        }

    except Exception as e:
        logger.error(f"OpenAI fallback search failed: {e}")
        return None


def search_web_for_turf_info(
    openai_client: openai.OpenAI,
    question: str,
    model: str = "gpt-4o-mini"
) -> Optional[Dict[str, Any]]:
    """
    Search the web for turf management information.

    First tries Tavily (real web search) if API key is available.
    Falls back to OpenAI knowledge if Tavily is not configured.
    """
    # Try real web search first
    tavily_result = _search_with_tavily(question)
    if tavily_result:
        logger.info("Web search completed via Tavily")
        return tavily_result

    # Fall back to OpenAI knowledge
    logger.info("Falling back to OpenAI knowledge for web search")
    return _search_with_openai_fallback(openai_client, question, model)


def format_web_search_disclaimer() -> str:
    """Return a disclaimer to prepend to web search results."""
    return (
        "**Note:** This response includes information from web search, "
        "not just our verified document database. Please verify specific rates "
        "and recommendations with product labels or your local extension service."
    )
