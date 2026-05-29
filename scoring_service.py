"""
Scoring service for ranking search results.
Handles relevance scoring, boosting, and filtering logic.
Includes hybrid BM25 reranking for better keyword matching.
"""
from chunk_store import get_match_text
from scoring import keyword_score, combined_relevance_score, boost_for_source_match
from bm25_search import rerank_with_bm25
from constants import (
    HERBICIDES, FUNGICIDES, INSECTICIDES,
    US_STATES, GRASS_TYPES, TOPIC_KEYWORDS,
    LOW_QUALITY_SOURCES, HIGH_VALUE_FUNGICIDE_SOURCES,
    WRONG_TYPE_KEYWORDS,
    VECTOR_SCORE_WEIGHT, KEYWORD_SCORE_WEIGHT,
    SCORE_BOOSTS, SCORE_PENALTIES,
    MAX_CHUNK_LENGTH, MAX_SOURCES, MAX_CONTEXT_LENGTH
)


def score_results(matches, question, grass_type, region, product_need, use_hybrid=True):
    """
    Score and rank search results based on multiple relevance factors.

    Args:
        matches: List of search result matches
        question: Original user question
        grass_type: Detected grass type (or None)
        region: Detected region (or None)
        product_need: Detected product type need (fungicide/herbicide/insecticide or None)
        use_hybrid: Whether to use BM25 hybrid reranking

    Returns:
        List of scored results sorted by score descending
    """
    matches = matches or []

    # Apply BM25 hybrid reranking first if enabled
    if use_hybrid and matches:
        matches = rerank_with_bm25(question, matches, top_k=50)

    question_lower = question.lower()
    scored_results = []

    for match in matches:
        if not match or 'metadata' not in match:
            continue

        text = get_match_text(match)
        source = match.get('metadata', {}).get('source', 'Unknown')

        # Calculate base score using enhanced keyword scoring
        vector_score = match.get('score', 0)
        rrf_score = match.get('rrf_score', 0)  # From hybrid search
        kw_score = combined_relevance_score(text, question)
        source_boost = boost_for_source_match(source, question)

        # Combine scores: vector + keyword + RRF bonus
        if rrf_score > 0:
            # Use RRF score as base when available
            combined_score = rrf_score * 10 * source_boost
        else:
            combined_score = (VECTOR_SCORE_WEIGHT * vector_score) + (KEYWORD_SCORE_WEIGHT * kw_score)
            combined_score *= source_boost

        # Apply boosts and penalties
        combined_score = _apply_fungicide_boosts(combined_score, match, product_need, question_lower)
        combined_score = _apply_grass_type_boost(combined_score, match, text, source, grass_type)
        combined_score = _apply_state_boost(combined_score, source, question_lower)
        combined_score = _apply_region_boost(combined_score, text, source, region)
        combined_score = _apply_water_boost(combined_score, text, source, question_lower)
        combined_score = _apply_wrong_grass_penalty(combined_score, text, grass_type)
        combined_score = _apply_country_penalty(combined_score, match)
        combined_score = _apply_product_type_penalties(combined_score, text, source, product_need)

        scored_results.append({
            'text': text,
            'source': source,
            'score': combined_score,
            'match_id': match.get('id', 'unknown'),
            'metadata': match['metadata']
        })

    scored_results.sort(key=lambda x: x['score'], reverse=True)
    return scored_results


def _apply_fungicide_boosts(score, match, product_need, question_lower):
    """Apply boosts for fungicide-related searches."""
    if product_need != 'fungicide':
        return score

    source_type = match['metadata'].get('type', '')
    source_name = match['metadata'].get('source', '').lower()

    # Boost high-value fungicide sources
    if any(pattern in source_name for pattern in HIGH_VALUE_FUNGICIDE_SOURCES):
        score *= SCORE_BOOSTS['high_value_fungicide']

    # Boost product labels
    if 'label' in source_type.lower() or 'pesticide_label' in source_type.lower():
        score *= SCORE_BOOSTS['product_label']
    elif 'solution' in source_type.lower() or 'sheet' in source_type.lower():
        score *= SCORE_PENALTIES['solution_sheet']

    # Penalize low-quality sources
    if any(bad in source_name for bad in LOW_QUALITY_SOURCES):
        score *= SCORE_PENALTIES['low_quality_source']

    # Boost if product keyword in source name
    for keyword in question_lower.split():
        if len(keyword) > 4 and keyword in source_name:
            score *= SCORE_BOOSTS['keyword_in_source']

    return score


def _apply_grass_type_boost(score, match, text, source, grass_type):
    """Boost score if grass type matches."""
    if not grass_type:
        return score

    text_lower = text.lower()
    source_lower = source.lower()
    doc_name = (match['metadata'].get('document_name') or '').lower()
    grass_lower = grass_type.lower()

    if grass_lower in text_lower or grass_lower in source_lower or grass_lower in doc_name:
        score *= SCORE_BOOSTS['grass_type_match']

    return score


def _apply_state_boost(score, source, question_lower):
    """Boost score if state matches."""
    source_lower = source.lower()
    for state in US_STATES:
        if state in question_lower and state in source_lower:
            score *= SCORE_BOOSTS['state_match']
            break
    return score


def _apply_region_boost(score, text, source, region):
    """Boost score if region matches."""
    if not region:
        return score

    text_lower = text.lower()
    source_lower = source.lower()

    if region in text_lower or region in source_lower:
        score *= SCORE_BOOSTS['region_match']

    return score


def _apply_water_boost(score, text, source, question_lower):
    """Boost score for water-related queries."""
    water_keywords = TOPIC_KEYWORDS['water']
    if any(kw in question_lower for kw in water_keywords):
        source_lower = source.lower()
        text_lower = text.lower()[:500]
        if any(kw in source_lower or kw in text_lower for kw in water_keywords):
            score *= SCORE_BOOSTS['water_keyword_match']
    return score


def _apply_wrong_grass_penalty(score, text, grass_type):
    """Penalize results about wrong grass types."""
    if not grass_type:
        return score

    wrong_grasses = [g for g in GRASS_TYPES if g != grass_type]
    text_lower = text.lower()[:200]

    for wrong_grass in wrong_grasses:
        if wrong_grass in text_lower:
            score *= SCORE_PENALTIES['wrong_grass']
            break

    return score


def _apply_country_penalty(score, match):
    """Penalize Canadian products for US users."""
    if match['metadata'].get('country', 'USA') == 'Canada':
        score *= SCORE_PENALTIES['canada_product']
    return score


def _apply_product_type_penalties(score, text, source, product_need):
    """Penalize results about wrong product types."""
    if not product_need:
        return score

    text_lower = text.lower()
    source_lower = source.lower()

    # Penalize wrong product names
    if product_need == 'fungicide':
        if any(h in text_lower or h in source_lower for h in HERBICIDES):
            score *= SCORE_PENALTIES['wrong_product_type']
        elif any(i in text_lower or i in source_lower for i in INSECTICIDES):
            score *= SCORE_PENALTIES['wrong_product_type']
    elif product_need == 'herbicide':
        if any(f in text_lower or f in source_lower for f in FUNGICIDES):
            score *= SCORE_PENALTIES['wrong_product_type']
        elif any(i in text_lower or i in source_lower for i in INSECTICIDES):
            score *= SCORE_PENALTIES['wrong_product_type']
    elif product_need == 'insecticide':
        if any(f in text_lower or f in source_lower for f in FUNGICIDES):
            score *= SCORE_PENALTIES['wrong_product_type']
        elif any(h in text_lower or h in source_lower for h in HERBICIDES):
            score *= SCORE_PENALTIES['wrong_product_type']

    # Penalize wrong type keywords
    wrong_types = WRONG_TYPE_KEYWORDS.get(product_need, [])
    if any(wt in text_lower[:300] for wt in wrong_types):
        score *= SCORE_PENALTIES['wrong_type_keyword']

    return score


def safety_filter_results(scored_results, question_topic, product_need, limit=20):
    """
    Apply safety filtering to remove irrelevant product results.

    Args:
        scored_results: List of scored results
        question_topic: Detected topic (irrigation/equipment/cultural/chemical)
        product_need: Detected product type need
        limit: Maximum results to process

    Returns:
        Filtered list of results
    """
    all_products = HERBICIDES + FUNGICIDES
    filtered = []

    for result in scored_results[:limit]:
        source = result['source'].lower()
        text = result['text'].lower()[:300]
        skip = False

        # Skip chemical products for non-chemical topics
        if question_topic in ('irrigation', 'equipment'):
            if any(prod in source for prod in all_products):
                skip = True

        # Skip wrong product types for chemical topics
        if question_topic == 'chemical':
            if product_need == 'fungicide':
                if any(h in source or h in text for h in HERBICIDES):
                    skip = True
            elif product_need == 'herbicide':
                if any(f in source or f in text for f in FUNGICIDES):
                    skip = True

        if not skip:
            filtered.append(result)

    return filtered


def _truncate_with_headroom(text, max_chars):
    """Truncate text cleanly without exceeding the requested budget."""
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    if max_chars <= 3:
        return text[:max_chars]
    clipped = text[: max_chars - 3].rstrip()
    return f"{clipped}..."


def _select_diversified_results(filtered_results, max_results, max_per_source=2):
    """Prefer broader source coverage before taking extra chunks from the same document."""
    selected = []
    overflow = []
    per_source_counts = {}

    for result in filtered_results:
        source_key = (result.get('source') or '').strip().lower()
        current_count = per_source_counts.get(source_key, 0)
        if current_count < max_per_source:
            selected.append(result)
            per_source_counts[source_key] = current_count + 1
        else:
            overflow.append(result)
        if len(selected) >= max_results:
            return selected[:max_results]

    for result in overflow:
        selected.append(result)
        if len(selected) >= max_results:
            break

    return selected[:max_results]


def select_evidence_results(filtered_results, question, question_topic, product_need, max_results=6):
    """
    Select the best prompt evidence from already-ranked results without changing retrieval.

    This keeps the existing retrieval/ranking path intact and only narrows the
    evidence passed into the answer prompt.
    """
    if not filtered_results:
        return []

    question_lower = (question or '').lower()
    selected = []
    overflow = []
    per_source_counts = {}
    max_per_source = 2

    wants_rate = any(term in question_lower for term in ('rate', 'rei', 'rainfast', 'retreatment', 'per 1000', 'per acre', 'oz', 'lb/acre'))
    wants_timing = question_topic == 'timing' or any(term in question_lower for term in ('when', 'timing', 'schedule', 'interval', 'calendar', 'program'))
    wants_diagnosis = question_topic in {'diagnostic', 'disease'} or any(term in question_lower for term in ('diagnose', 'identify', 'symptom', 'spot', 'patch', 'wilt', 'yellow'))

    def priority(result):
        metadata = result.get('metadata', {}) or {}
        source = (result.get('source') or '').lower()
        text = (result.get('text') or '').lower()
        source_type = (metadata.get('type') or '').lower()
        score = float(result.get('score', 0))

        bonus = 0.0
        if wants_rate:
            if 'label' in source_type or 'pesticide_label' in source_type:
                bonus += 6.0
            if any(term in text[:500] for term in ('rate', 'rei', 'rainfast', 'retreatment', 'per 1000', 'per acre', 'fl oz', 'lb ai')):
                bonus += 3.0
        if wants_timing:
            if any(term in text[:500] for term in ('timing', 'schedule', 'calendar', 'interval', 'preventive', 'curative')):
                bonus += 4.0
        if wants_diagnosis:
            if any(term in text[:500] for term in ('symptom', 'sign', 'lesion', 'mycelium', 'root', 'wilt', 'pattern')):
                bonus += 4.0
        if product_need == 'fungicide' and ('label' in source_type or 'chemical control' in source):
            bonus += 2.0
        return score + bonus

    ranked = sorted(filtered_results, key=priority, reverse=True)
    for result in ranked:
        source_key = (result.get('source') or '').strip().lower()
        current_count = per_source_counts.get(source_key, 0)
        if current_count < max_per_source:
            selected.append(result)
            per_source_counts[source_key] = current_count + 1
        else:
            overflow.append(result)
        if len(selected) >= max_results:
            return selected[:max_results]

    for result in overflow:
        selected.append(result)
        if len(selected) >= max_results:
            break

    return selected[:max_results]


def assemble_context_sections(sections, max_chars=MAX_CONTEXT_LENGTH):
    """
    Build a deterministic final context from ordered sections with per-section budgets.

    Args:
        sections: Iterable of dicts with `title`, `content`, and optional `max_chars`
        max_chars: Total context budget

    Returns:
        Combined context string within the total budget
    """
    parts = []
    remaining = max_chars

    for section in sections:
        content = (section.get('content') or '').strip()
        if not content or remaining <= 0:
            continue

        title = section.get('title', '').strip()
        section_budget = min(section.get('max_chars', remaining), remaining)
        if section_budget <= 0:
            continue

        prefix = f"--- {title} ---\n\n" if title else ""
        suffix = "\n\n"
        overhead = len(prefix) + len(suffix)
        if overhead >= section_budget:
            continue

        body = _truncate_with_headroom(content, section_budget - overhead)
        if not body:
            continue

        rendered = f"{prefix}{body}{suffix}"
        if len(rendered) > remaining:
            rendered = _truncate_with_headroom(rendered.rstrip(), remaining)
        parts.append(rendered.rstrip())
        remaining -= len(parts[-1]) + 2

    return "\n\n".join(parts).strip()


def build_context(filtered_results, search_folders, max_results=MAX_SOURCES, max_chars=MAX_CONTEXT_LENGTH):
    """
    Build context string and source list from filtered results.

    Args:
        filtered_results: List of filtered, scored results
        search_folders: List of folders to search for PDFs
        max_results: Maximum number of results to include
        max_chars: Total character budget for the retrieval context

    Returns:
        Tuple of (context_string, sources_list, images_list)
    """
    from search_service import find_source_url

    context_parts = []
    sources = []
    images = []
    remaining_chars = max_chars
    selected_results = _select_diversified_results(filtered_results, max_results=max_results)
    per_result_budget = max(350, min(MAX_CHUNK_LENGTH, max_chars // max(1, len(selected_results))))

    for i, result in enumerate(selected_results, 1):
        source = result['source']
        metadata = result['metadata']
        header = f"[Source {i}: {source}]\n"
        separator = "\n\n---\n\n"
        available_for_chunk = min(per_result_budget, remaining_chars) - len(header) - len(separator)
        if available_for_chunk <= 80:
            break

        chunk_text = _truncate_with_headroom(result['text'][:MAX_CHUNK_LENGTH], available_for_chunk)
        context_block = f"{header}{chunk_text}{separator}"
        if len(context_block) > remaining_chars:
            context_block = _truncate_with_headroom(context_block.rstrip(), remaining_chars)
        if not context_block:
            break

        context_parts.append(context_block.rstrip())
        remaining_chars -= len(context_parts[-1]) + 2

        source_url = find_source_url(source, search_folders)
        sources.append({
            'number': i,
            'name': source,
            'url': source_url,
            'type': metadata.get('type', 'document'),
            'note': None if source_url else 'Local reference on file',
        })

        # Check for equipment images
        if 'equipment' in result['match_id'].lower():
            images.extend(_get_equipment_images(result['match_id']))

    return "\n\n".join(context_parts).strip(), sources, images


def _get_equipment_images(match_id):
    """Get equipment-related images for a match."""
    import os
    images = []
    parts = match_id.split('-chunk-')
    if len(parts) > 0:
        doc_name = parts[0].replace('equipment-', '')
        for page in range(1, 4):
            image_path = f"{doc_name}_page_{page}.jpg"
            if os.path.exists(f"static/images/{image_path}"):
                images.append(image_path)
    return images
