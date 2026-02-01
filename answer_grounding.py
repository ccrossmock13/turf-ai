"""
Answer grounding verification to reduce hallucination.
Checks if the AI response is supported by the retrieved sources.
"""
import logging
import re

logger = logging.getLogger(__name__)

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
    # Default response if check fails
    default_result = {
        "grounded": True,
        "confidence": 0.7,
        "issues": [],
        "unsupported_claims": []
    }

    # Skip check for very short answers
    if len(answer) < 50:
        return default_result

    try:
        response = openai_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "user", "content": GROUNDING_PROMPT.format(
                    context=context[:4000],  # Limit context size
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
    if grounding_result.get("grounded", True):
        return answer

    confidence = grounding_result.get("confidence", 1.0)
    issues = grounding_result.get("unsupported_claims", [])

    if confidence < 0.5 or len(issues) > 2:
        warning = "\n\n⚠️ **Note**: Some details in this response may need verification against product labels or university guidelines."
        return answer + warning

    return answer


def calculate_grounding_confidence(grounding_result: dict, base_confidence: float) -> float:
    """
    Adjust confidence score based on grounding check.
    Uses 0-100 scale. Only applies minor adjustments.

    Args:
        grounding_result: Result from grounding check
        base_confidence: Original confidence score (0-100)

    Returns:
        Adjusted confidence score (0-100)
    """
    is_grounded = grounding_result.get("grounded", True)
    num_issues = len(grounding_result.get("unsupported_claims", []))

    if not is_grounded:
        # Reduce confidence by 15 points if not grounded (not 50%)
        return max(30, base_confidence - 15)

    if num_issues > 0:
        # Reduce by 5 points per issue, max 15 point penalty
        penalty = min(15, num_issues * 5)
        return max(30, base_confidence - penalty)

    # Well-grounded gets a small boost
    return min(100, base_confidence + 5)
