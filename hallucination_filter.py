"""
Post-processing hallucination filter for Greenside AI.
Catches temporal hallucinations, fabricated products, and claims not supported
by retrieved sources. Runs AFTER the main GPT-4o response is generated.
"""
import re
import logging
from typing import Dict, List, Optional
from product_validator import lookup_product, validate_product_in_answer, format_validation_warning

logger = logging.getLogger(__name__)


def filter_hallucinations(
    answer: str,
    question: str,
    context: str,
    sources: list,
    openai_client=None,
    model: str = "gpt-4o-mini"
) -> Dict:
    """
    Post-processing filter that checks the AI response for hallucinations.

    Runs multiple checks:
    1. Temporal claims (year-specific discoveries, events)
    2. Fabricated product detection
    3. Product category validation
    4. Claims vs source verification (lightweight)

    Args:
        answer: The AI-generated answer
        question: Original user question
        context: Retrieved source context
        sources: Retrieved source documents
        openai_client: OpenAI client (optional, for LLM-based checks)
        model: Model for LLM checks

    Returns:
        Dict with:
        - filtered_answer: str (possibly modified answer)
        - issues_found: list of issues detected
        - was_modified: bool
        - confidence_penalty: float (0-30 point penalty)
    """
    issues = []
    modified_answer = answer
    confidence_penalty = 0

    # --- CHECK 1: Temporal hallucination detection ---
    temporal_result = _check_temporal_claims(answer, question, context)
    if temporal_result['flagged']:
        issues.extend(temporal_result['issues'])
        modified_answer = temporal_result['corrected_answer']
        confidence_penalty += temporal_result['penalty']

    # --- CHECK 2: Fabricated product detection ---
    product_result = _check_fabricated_products(answer, question)
    if product_result['flagged']:
        issues.extend(product_result['issues'])
        confidence_penalty += product_result['penalty']

    # --- CHECK 3: Product category validation ---
    validation_result = validate_product_in_answer(answer, question)
    if not validation_result['valid']:
        issues.extend(validation_result['issues'])
        warning = format_validation_warning(validation_result)
        if warning:
            modified_answer += warning
        confidence_penalty += min(15, len(validation_result['issues']) * 5)

    # --- CHECK 4: Dangerous mixing claims ---
    mixing_result = _check_dangerous_mixing(answer, question)
    if mixing_result['flagged']:
        issues.extend(mixing_result['issues'])
        confidence_penalty += mixing_result['penalty']

    return {
        'filtered_answer': modified_answer,
        'issues_found': issues,
        'was_modified': modified_answer != answer,
        'confidence_penalty': min(30, confidence_penalty)  # Cap at 30
    }


def _check_temporal_claims(answer: str, question: str, context: str) -> Dict:
    """
    Detect temporal hallucinations — claims about specific year events
    that aren't supported by the retrieved context.
    """
    flagged = False
    issues = []
    corrected = answer
    penalty = 0

    # Pattern: "In [year], [something was discovered/released/found]"
    temporal_patterns = [
        # "discovered in 2025", "released in 2024", etc.
        r'(?:discovered|released|published|found|introduced|identified|developed|launched|announced)\s+in\s+(20[2-3]\d)',
        # "In 2025, researchers discovered..."
        r'[Ii]n\s+(20[2-3]\d),?\s+(?:researchers?|scientists?|a\s+(?:new|novel))',
        # "The new disease discovered in 2025"
        r'(?:new|novel|recent)\s+\w+\s+(?:discovered|found|identified)\s+in\s+(20[2-3]\d)',
        # "A 2025 study" or "2025 research"
        r'[Aa]\s+(20[2-3]\d)\s+(?:study|research|paper|publication|report|finding)',
    ]

    answer_lower = answer.lower()
    context_lower = context.lower() if context else ""

    for pattern in temporal_patterns:
        matches = re.finditer(pattern, answer, re.IGNORECASE)
        for match in matches:
            year = match.group(1)
            year_int = int(year)

            # Check if the year-specific claim is supported by context
            if year not in context_lower:
                # The retrieved sources don't mention this year — likely hallucinated
                flagged = True
                claim_text = match.group(0)
                issues.append(
                    f"Temporal claim not supported by sources: '{claim_text}'. "
                    f"No retrieved documents reference events in {year}."
                )
                penalty = 20

                # Add a disclaimer to the answer
                disclaimer = (
                    f"\n\n⚠️ **Verification Note:** I was unable to verify the specific "
                    f"claim about events in {year} from my available sources. Please "
                    f"consult recent university extension publications or industry news "
                    f"for the latest confirmed information."
                )
                if disclaimer not in corrected:
                    corrected += disclaimer

    return {
        'flagged': flagged,
        'issues': issues,
        'corrected_answer': corrected,
        'penalty': penalty
    }


def _check_fabricated_products(answer: str, question: str) -> Dict:
    """
    Detect potentially fabricated product names in the answer.
    Looks for product-like patterns that aren't in our database.
    """
    flagged = False
    issues = []
    penalty = 0

    # Patterns that look like product names (capitalized + optional numbers/suffixes)
    # e.g., "TurfMaster Pro 5000", "GreenGuard XR", "SuperGreen 40-0-0"
    product_like_patterns = [
        # "ProductName Pro/Plus/Max/Ultra 1000"
        r'\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\s+(?:Pro|Plus|Max|Ultra|XR|SC|WG|EW|G|TL)\s*\d*\b',
        # Multi-word capitalized with number: "Green Guard 5000"
        r'\b([A-Z][a-z]+\s+[A-Z][a-z]+)\s+(\d{3,})\b',
    ]

    # Known real products to exclude from false positives
    known_product_index = {p.lower() for p in _get_all_known_product_names()}

    for pattern in product_like_patterns:
        matches = re.finditer(pattern, answer)
        for match in matches:
            full_name = match.group(0).strip()
            # Check if this is a real product
            if full_name.lower() not in known_product_index:
                result = lookup_product(full_name)
                if not result:
                    # Not in our database — could be fabricated
                    # But only flag if the question asked about it (not if model just mentioned it)
                    if full_name.lower() in question.lower():
                        flagged = True
                        issues.append(
                            f"Unrecognized product: '{full_name}' is not in our verified "
                            f"product database. The response may contain fabricated details."
                        )
                        penalty = 15

    return {
        'flagged': flagged,
        'issues': issues,
        'penalty': penalty
    }


def _check_dangerous_mixing(answer: str, question: str) -> Dict:
    """
    Check for dangerous product mixing recommendations.
    """
    flagged = False
    issues = []
    penalty = 0

    answer_lower = answer.lower()

    # Dangerous combinations to flag
    dangerous_mixes = [
        {
            'chemicals': ['bleach', 'chlorine'],
            'with': ['roundup', 'glyphosate', 'herbicide', 'pesticide', 'fungicide'],
            'issue': "Mixing bleach with pesticides is extremely dangerous and can produce toxic gases."
        },
        {
            'chemicals': ['bleach', 'chlorine'],
            'with': ['ammonia', 'ammonium'],
            'issue': "Mixing bleach with ammonia produces toxic chloramine gas."
        },
    ]

    for mix in dangerous_mixes:
        has_chem = any(c in answer_lower for c in mix['chemicals'])
        has_with = any(w in answer_lower for w in mix['with'])
        # Only flag if the answer is recommending the mix (not warning against it)
        if has_chem and has_with:
            # Check if the answer is actually recommending (not warning)
            warning_phrases = ['do not mix', 'never mix', 'dangerous', 'toxic',
                               'don\'t mix', 'avoid mixing', 'should not', 'do not']
            is_warning = any(w in answer_lower for w in warning_phrases)
            if not is_warning:
                flagged = True
                issues.append(mix['issue'])
                penalty = 20

    return {
        'flagged': flagged,
        'issues': issues,
        'penalty': penalty
    }


def _get_all_known_product_names() -> List[str]:
    """Get all known product names (trade names + active ingredients)."""
    from knowledge_base import load_products
    products = load_products()
    names = []
    for category, items in products.items():
        for ai_name, info in items.items():
            names.append(ai_name)
            names.extend(info.get('trade_names', []))
    return names
