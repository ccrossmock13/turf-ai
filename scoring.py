"""
Enhanced keyword scoring with TF-IDF weighting and turf-specific boosting.
"""
import re
import math
from collections import Counter
from query_expansion import STOP_WORDS, SYNONYMS


# High-value terms that indicate strong relevance
BOOST_TERMS = {
    # Product names (exact matches are very relevant)
    'heritage', 'lexicon', 'xzemplar', 'headway', 'medallion', 'daconil',
    'tenacity', 'barricade', 'dimension', 'specticle', 'acelepryn', 'primo',
    # Disease names
    'dollar spot', 'brown patch', 'pythium', 'anthracnose', 'fairy ring',
    # Active ingredients
    'azoxystrobin', 'propiconazole', 'chlorothalonil', 'fluxapyroxad',
    'mesotrione', 'prodiamine', 'chlorantraniliprole',
    # FRAC/IRAC codes
    'frac', 'frac11', 'frac3', 'frac7', 'fracm5',
}

# Terms that indicate rate/dosage information
RATE_TERMS = {
    'oz', 'fl oz', 'ounce', 'lb', 'pound', 'gallon', 'gal',
    'per 1000', 'per acre', 'rate', 'dosage', 'application',
}


def tokenize(text: str) -> list:
    """Tokenize text into lowercase words."""
    return re.findall(r'\b\w+\b', text.lower())


def keyword_score(text: str, question: str) -> float:
    """
    Score text based on keyword overlap with question using TF-IDF principles.

    Args:
        text: Document text to score
        question: User's question

    Returns:
        Relevance score between 0 and 1
    """
    # Tokenize
    question_words = tokenize(question)
    text_words = tokenize(text)

    # Remove stop words from question
    question_keywords = [w for w in question_words if w not in STOP_WORDS and len(w) > 2]

    if not question_keywords:
        return 0.0

    # Count term frequencies in text
    text_tf = Counter(text_words)
    text_len = len(text_words)

    if text_len == 0:
        return 0.0

    score = 0.0
    matched_terms = 0

    for term in question_keywords:
        if term in text_tf:
            matched_terms += 1

            # TF component: log-scaled term frequency
            tf = 1 + math.log(text_tf[term]) if text_tf[term] > 0 else 0

            # Boost for high-value terms
            boost = 2.0 if term in BOOST_TERMS else 1.0

            # Boost for rate-related terms when asking about rates
            if term in RATE_TERMS:
                boost *= 1.5

            score += tf * boost

    # Normalize by number of query terms
    if len(question_keywords) > 0:
        score = score / len(question_keywords)

    # Also consider percentage of query terms matched
    coverage = matched_terms / len(question_keywords)

    # Combine score and coverage
    final_score = (0.6 * min(score / 3, 1.0)) + (0.4 * coverage)

    return min(final_score, 1.0)


def phrase_match_score(text: str, question: str) -> float:
    """
    Score based on exact phrase matches (important for multi-word terms).

    Args:
        text: Document text
        question: User's question

    Returns:
        Phrase match score between 0 and 1
    """
    text_lower = text.lower()
    question_lower = question.lower()

    # Check for multi-word phrase matches
    phrase_matches = 0
    total_phrases = 0

    # Check disease names
    diseases = ['dollar spot', 'brown patch', 'fairy ring', 'summer patch',
                'gray leaf spot', 'spring dead spot', 'snow mold', 'take-all']
    for disease in diseases:
        if disease in question_lower:
            total_phrases += 1
            if disease in text_lower:
                phrase_matches += 1

    # Check product names with spaces
    products = ['banner maxx', 'primo maxx', 'drive xlr8', 'poa annua']
    for product in products:
        if product in question_lower:
            total_phrases += 1
            if product in text_lower:
                phrase_matches += 1

    if total_phrases == 0:
        return 0.0

    return phrase_matches / total_phrases


def combined_relevance_score(text: str, question: str) -> float:
    """
    Calculate combined relevance score using multiple methods.

    Args:
        text: Document text
        question: User's question

    Returns:
        Combined relevance score between 0 and 1
    """
    kw_score = keyword_score(text, question)
    phrase_score = phrase_match_score(text, question)

    # Weight keyword matching higher, but boost for phrase matches
    if phrase_score > 0:
        return (0.7 * kw_score) + (0.3 * phrase_score)
    return kw_score


def boost_for_source_match(source_name: str, question: str) -> float:
    """
    Calculate boost multiplier if source name matches query terms.

    Args:
        source_name: Name of the source document
        question: User's question

    Returns:
        Boost multiplier (1.0 = no boost, higher = more relevant)
    """
    source_lower = source_name.lower()
    question_lower = question.lower()

    boost = 1.0

    # Check if product name is in both question and source
    for term in SYNONYMS:
        if term in question_lower and term in source_lower:
            boost *= 2.0
            break

    # Check for disease/weed terms
    problem_terms = ['dollar spot', 'brown patch', 'crabgrass', 'poa', 'pythium']
    for term in problem_terms:
        if term in question_lower and term in source_lower:
            boost *= 1.5
            break

    return boost
