"""
Answer grounding verification to reduce hallucination.
Checks if the AI response is supported by the retrieved sources.
Enhanced with domain-specific validation for turfgrass products and rates.
"""
import logging
import re

logger = logging.getLogger(__name__)

# Domain-specific rate validation ranges (per 1000 sq ft)
RATE_RANGES = {
    'oz': (0.05, 16.0),      # Typical oz/1000 range for most products
    'fl oz': (0.05, 16.0),   # Typical fl oz/1000 range
    'lb': (0.1, 10.0),       # Typical lbs/1000 range
    'gal': (0.25, 5.0),      # Typical gal/acre range
}

# Known product name patterns for spell-check
KNOWN_PRODUCTS = [
    'heritage', 'lexicon', 'xzemplar', 'headway', 'renown', 'medallion',
    'interface', 'tartan', 'banner', 'bayleton', 'tourney', 'compass',
    'honor', 'posterity', 'secure', 'briskway', 'velista', 'concert',
    'daconil', 'chipco', 'subdue', 'banol', 'segway', 'disarm',
    'specticle', 'tenacity', 'monument', 'certainty', 'sedgehammer',
    'drive', 'barricade', 'dimension', 'primo', 'trimmit', 'cutless',
    'anuew', 'acelepryn', 'merit', 'arena', 'dylox', 'talstar',
    'maxtima', 'revysol', 'appear', 'proxy', 'embark',
]

# Grounding check prompt
GROUNDING_PROMPT = """You are a fact-checker for a turf management AI assistant. Your job is to verify if the AI's answer is supported by the provided source context.

Source Context:
{context}

AI Answer:
{answer}

User Question:
{question}

Analyze the answer and determine:
1. Is each claim in the answer supported by the sources?
2. Are there any hallucinated facts (specific rates, products, or claims not in sources)?
3. Is the answer accurate for the question asked?

Respond with a JSON object:
{{
    "grounded": true/false,
    "confidence": 0.0-1.0,
    "issues": ["list of specific issues if any"],
    "unsupported_claims": ["list of claims not found in sources"]
}}

Be strict about product rates - if the answer gives a specific rate like "0.5 oz/1000 sq ft" but the sources don't contain that exact rate, flag it."""


def check_answer_grounding(
    openai_client,
    answer: str,
    context: str,
    question: str,
    model: str = "gpt-4o-mini"
) -> dict:
    """
    Check if an answer is grounded in the source context.

    Args:
        openai_client: OpenAI client instance
        answer: The AI-generated answer
        context: The source context used to generate the answer
        question: The original user question
        model: Model to use for grounding check

    Returns:
        Dict with grounding analysis:
        - grounded: bool - whether answer is well-grounded
        - confidence: float - confidence in the answer (0-1)
        - issues: list - any issues found
        - unsupported_claims: list - claims not in sources
    """
    # Default response if check fails — default to NOT grounded so
    # failed checks don't silently pass as trusted
    default_result = {
        "grounded": False,
        "confidence": 0.3,
        "issues": ["Grounding check could not be completed"],
        "unsupported_claims": []
    }

    # Skip check for very short answers — these are usually simple/factual
    # and don't need grounding verification. Treat as neutral (not penalized).
    if len(answer) < 50:
        return {
            "grounded": True,
            "confidence": 0.6,
            "issues": [],
            "unsupported_claims": []
        }

    try:
        response = openai_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "user", "content": GROUNDING_PROMPT.format(
                    context=context[:8000],  # Increased context window for better grounding
                    answer=answer,
                    question=question
                )}
            ],
            max_tokens=300,
            temperature=0.1
        )

        result_text = response.choices[0].message.content.strip()

        # Parse JSON response
        import json
        # Extract JSON from response (handle markdown code blocks)
        json_match = re.search(r'\{[\s\S]*\}', result_text)
        if json_match:
            result = json.loads(json_match.group())
            logger.info(f"Grounding check: grounded={result.get('grounded')}, confidence={result.get('confidence')}")
            return result
        else:
            logger.warning("Could not parse grounding check response")
            return default_result

    except Exception as e:
        logger.error(f"Grounding check failed: {e}")
        return default_result


def add_grounding_warning(answer: str, grounding_result: dict) -> str:
    """
    Add a warning to the answer if grounding issues were found.

    Args:
        answer: Original AI answer
        grounding_result: Result from check_answer_grounding

    Returns:
        Answer with warning appended if needed
    """
    if grounding_result.get("grounded", False):
        return answer

    confidence = grounding_result.get("confidence", 0.3)
    issues = grounding_result.get("unsupported_claims", [])

    if confidence < 0.5 or len(issues) > 2:
        warning = "\n\n⚠️ **Note**: Some details in this response may need verification against product labels or university guidelines."
        return answer + warning

    return answer


def calculate_grounding_confidence(grounding_result: dict, base_confidence: float) -> float:
    """
    Adjust confidence score based on grounding check.
    Uses 0-100 scale. Stricter penalties for ungrounded answers.

    Designed for 70% auto-approval threshold:
    - Well-grounded answers: boost to help pass threshold
    - Ungrounded or issues: significant penalty to fail threshold

    Args:
        grounding_result: Result from grounding check
        base_confidence: Original confidence score (0-100)

    Returns:
        Adjusted confidence score (0-100)
    """
    is_grounded = grounding_result.get("grounded", False)
    grounding_confidence = grounding_result.get("confidence", 0.3)
    unsupported = grounding_result.get("unsupported_claims", [])
    issues = grounding_result.get("issues", [])
    num_issues = len(unsupported) + len(issues)

    if not is_grounded:
        # Penalty for ungrounded answers — proportional to issues found
        penalty = 15 + (3 * min(num_issues, 3))  # 15-24 point penalty
        return max(35, base_confidence - penalty)

    if num_issues > 0:
        # Small penalty per issue
        penalty = min(15, num_issues * 5)
        return max(40, base_confidence - penalty)

    # Grounding confidence from LLM check (0-1 scale)
    if grounding_confidence < 0.6:
        # Low LLM confidence even if "grounded" = small penalty
        return max(50, base_confidence - 5)
    elif grounding_confidence >= 0.85:
        # High confidence = boost
        return min(100, base_confidence + 10)
    elif grounding_confidence >= 0.7:
        # Good confidence = moderate boost
        return min(100, base_confidence + 6)

    return base_confidence


def validate_domain_specific(answer):
    """Perform domain-specific validation on turfgrass AI answers.

    Checks for:
    - Rate values within reasonable ranges
    - Known product name spelling
    - Dangerous recommendation patterns

    Args:
        answer: AI-generated answer text

    Returns:
        Dict with validation results:
        - valid: bool
        - warnings: list of warning strings
        - issues: list of issue descriptions
    """
    warnings = []
    issues = []
    answer_lower = answer.lower()

    # Check for rate values in reasonable ranges
    rate_patterns = re.findall(
        r'(\d+\.?\d*)\s*(oz|fl\s*oz|lb|lbs|gal|gallon)(?:\s*/\s*(?:1000|1,000)\s*sq\s*ft)?',
        answer_lower
    )
    for value_str, unit in rate_patterns:
        try:
            value = float(value_str)
            unit_key = unit.replace('lbs', 'lb').replace('gallon', 'gal').replace('fl oz', 'fl oz').strip()
            if unit_key.startswith('fl'):
                unit_key = 'fl oz'

            min_rate, max_rate = RATE_RANGES.get(unit_key, (0.01, 50.0))
            if value < min_rate:
                warnings.append(f"Rate {value} {unit} seems unusually low — verify against label")
            elif value > max_rate:
                issues.append(f"Rate {value} {unit} exceeds typical range ({min_rate}-{max_rate}) — may exceed label maximum")
        except (ValueError, TypeError):
            pass

    # Check for dangerous recommendations
    dangerous_patterns = [
        (r'glyphosate.*(?:green|fairway|tee|active)', 'Glyphosate on active turf warning — non-selective herbicide'),
        (r'(?:exceed|above|over).*label\s*rate', 'Recommendation may suggest exceeding label rate'),
        (r'(?:50|60|70|80|90|100)\s*lb.*nitrogen.*1000', 'Nitrogen rate appears extremely high'),
    ]
    for pattern, warning in dangerous_patterns:
        if re.search(pattern, answer_lower):
            issues.append(warning)

    return {
        'valid': len(issues) == 0,
        'warnings': warnings,
        'issues': issues,
    }
