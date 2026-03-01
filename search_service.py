"""
Search service for querying Pinecone and processing results.
Handles embedding generation, vector search, and result filtering.
Includes caching and parallel query execution for performance.
"""
import os
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from constants import (
    HERBICIDES, FUNGICIDES, INSECTICIDES,
    TOPIC_KEYWORDS, US_STATES,
    GENERAL_SEARCH_TOP_K, PRODUCT_SEARCH_TOP_K,
    TIMING_SEARCH_TOP_K, ALGAE_SEARCH_TOP_K
)
from cache import get_cached_embedding, get_cached_source_url, get_cached_search_results

logger = logging.getLogger(__name__)

# Load topic keywords from JSON (cached on startup)
_TOPIC_KEYWORDS_PATH = os.path.join(os.path.dirname(__file__), 'knowledge', 'topic_keywords.json')
with open(_TOPIC_KEYWORDS_PATH) as f:
    TOPIC_KW = json.load(f)


def detect_topic(question_lower):
    """Detect the topic category from the question for prompt selection."""
    # Check for diagnostic questions first (pattern-based)
    if any(word in question_lower for word in TOPIC_KW['diagnostic']):
        return 'diagnostic'

    # Nematode-specific keywords
    if any(word in question_lower for word in TOPIC_KW['nematode']):
        return 'disease'

    # Disease-specific keywords
    if any(word in question_lower for word in TOPIC_KW['disease']):
        return 'disease'

    # Abiotic disorder keywords
    if any(word in question_lower for word in TOPIC_KW['abiotic']):
        return 'diagnostic'

    # Chemical/product questions
    if any(word in question_lower for word in TOPIC_KW['chemical']):
        return 'chemical'

    # Check for fertilizer questions
    if any(word in question_lower for word in TOPIC_KW['fertilizer']):
        return 'fertilizer'

    # Check standard topic keywords
    if any(word in question_lower for word in TOPIC_KW['irrigation']):
        return 'irrigation'
    elif any(word in question_lower for word in TOPIC_KW['equipment']):
        return 'equipment'
    elif any(word in question_lower for word in TOPIC_KW['cultural']):
        return 'cultural'
    return None


def detect_specific_subject(question_lower):
    """
    Extract the specific subject (disease name, product name, etc.) from a question.
    Used to detect topic changes within the same category (e.g., pythium vs summer patch).
    Returns a lowercase string or None.
    """
    # Specific diseases (loaded from topic_keywords.json)
    for d in TOPIC_KW['specific_diseases']:
        if d in question_lower:
            return d

    # Specific products / active ingredients
    products = [
        'heritage', 'azoxystrobin', 'daconil', 'chlorothalonil', 'banner maxx',
        'propiconazole', 'primo', 'trinexapac', 'tenacity', 'mesotrione',
        'barricade', 'prodiamine', 'dimension', 'dithiopyr', 'acclaim',
        'fenoxaprop', 'certainty', 'sulfosulfuron', 'monument', 'trifloxysulfuron',
        'specticle', 'indaziflam', 'lexicon', 'xzemplar', 'insignia',
        'pyraclostrobin', 'mancozeb', 'revysol', 'briskway', 'posterity',
        'rolling', 'aerification', 'topdressing',
        'verticutting', 'overseeding', 'dethatching'
    ]
    for p in products:
        if p in question_lower:
            return p

    # Specific weeds
    weeds = [
        'annual bluegrass', 'poa annua', 'annual sedge', 'barnyardgrass',
        'black medic', 'buckhorn plantain', 'canada thistle', 'carolina geranium',
        'carpetweed', 'common bermudagrass', 'common chickweed', 'common purslane',
        'corn speedwell', 'crabgrass', 'crowfootgrass', 'dallisgrass', 'dandelion',
        'dichondra', 'dollarweed', 'pennywort', 'doveweed', 'field sandbur',
        'florida betony', 'florida pusley', 'foxtail', 'globe sedge', 'goosegrass',
        'green kyllinga', 'kyllinga', 'ground ivy', 'creeping charlie', 'groundsel',
        'henbit', 'knotweed', 'lawn burweed', 'morningglory', 'morning glory',
        'mouse-ear chickweed', 'nimblewill', 'parsley-piert', 'persian speedwell',
        'purple nutsedge', 'nutsedge', 'quackgrass', 'roughstalk bluegrass',
        'poa trivialis', 'annual ryegrass', 'italian ryegrass', 'perennial ryegrass',
        "shepherd's purse", 'shepherds purse', 'southern sandbur', 'sandbur',
        'spotted spurge', 'prostrate spurge', 'thin paspalum', 'bull paspalum',
        'torpedograss', 'tropical carpetgrass', 'tropical signalgrass',
        'virginia buttonweed', 'white clover', 'clover', 'wild garlic',
        'wild violet', 'windmillgrass', 'yellow nutsedge', 'yellow woodsorrel',
        'oxalis', 'sedge'
    ]
    for w in weeds:
        if w in question_lower:
            return w

    # Specific nematode species (before general pests for specificity)
    nematodes = [
        'sting nematode', 'lance nematode', 'root-knot nematode', 'root knot nematode',
        'ring nematode', 'spiral nematode', 'stubby-root nematode', 'stubby root nematode',
        'stunt nematode', 'needle nematode', 'cyst nematode', 'lesion nematode',
        'sheath nematode', 'dagger nematode', 'pin nematode', 'awl nematode',
        'nematode', 'nematodes', 'nematicide',
    ]
    for n in nematodes:
        if n in question_lower:
            return n

    # Insects and pests
    pests = [
        'white grub', 'grub', 'grubs', 'japanese beetle', 'armyworm', 'army worm',
        'fall armyworm', 'cutworm', 'cut worm', 'sod webworm', 'webworm',
        'chinch bug', 'mole cricket', 'billbug', 'hunting billbug',
        'annual bluegrass weevil', 'abw', 'crane fly', 'leatherjacket',
        'fire ant', 'fire ants',
        'bermudagrass mite', 'zoysiagrass mite', 'mite', 'mites',
        'spittlebug', 'twolined spittlebug', 'green june beetle',
        'ground pearl', 'ground pearls', 'earthworm', 'earthworms',
        'mole', 'moles', 'vole', 'voles', 'millipede', 'springtail',
        'wireworm', 'crayfish', 'yellowjacket', 'wasp',
        'sugarcane beetle', 'rhodesgrass mealybug', 'mealybug',
    ]
    for pest in pests:
        if pest in question_lower:
            return pest

    # Abiotic disorders
    abiotic = [
        'winterkill', 'winter kill', 'winter desiccation', 'cold injury', 'cold damage',
        'ice damage', 'ice encasement', 'crown hydration', 'frost damage',
        'heat stress', 'heat damage', 'drought stress', 'drought damage',
        'salt damage', 'salt stress', 'salinity', 'salt burn',
        'chemical injury', 'herbicide injury', 'herbicide damage', 'chemical burn',
        'fertilizer burn', 'nitrogen burn',
        'scalping', 'mower damage', 'dull mower',
        'shade stress', 'shade damage',
        'compaction', 'soil compaction', 'traffic damage',
        'black layer', 'poor drainage', 'waterlogging',
        'localized dry spot', 'hydrophobic', 'lightning damage',
        'dog urine', 'dog damage',
    ]
    for a in abiotic:
        if a in question_lower:
            return a

    # Grass types
    grass_types = [
        'bermuda', 'bentgrass', 'zoysia', 'bluegrass', 'fescue', 'ryegrass'
    ]
    for g in grass_types:
        if g in question_lower:
            return g

    return None


def detect_state(question_lower):
    """Detect US state mentioned in the question."""
    for state in US_STATES:
        if state in question_lower:
            return state.title()
    return None


def get_embedding(openai_client, text, model="text-embedding-3-small"):
    """Generate embedding for text using OpenAI with caching."""
    return get_cached_embedding(openai_client, text, model)


def search_general(index, embedding, top_k=GENERAL_SEARCH_TOP_K, query_text=""):
    """Perform general vector search with caching."""
    try:
        results = get_cached_search_results(
            index, embedding, 'general', top_k,
            filters=None, query_text=query_text
        )
        logger.debug(f'General search returned {len(results.get("matches", []))} results')
        return results
    except Exception as e:
        logger.error(f'Error in general search: {e}')
        return {'matches': []}


def search_products(index, openai_client, question, product_need, model="text-embedding-3-small"):
    """Search for product-specific results based on product need with caching."""
    question_lower = question.lower()

    # Algae-specific search
    if any(word in question_lower for word in TOPIC_KEYWORDS['algae']):
        algae_query = f"{question} daconil chlorothalonil copper algae control"
        embedding = get_embedding(openai_client, algae_query, model)
        return get_cached_search_results(
            index, embedding, 'algae', ALGAE_SEARCH_TOP_K,
            filters=None, query_text=algae_query
        )

    # General product search
    if any(word in question_lower for word in TOPIC_KEYWORDS['product']):
        product_query = f"{question} product label application rate"
        embedding = get_embedding(openai_client, product_query, model)
        search_filter = {"type": {"$in": ["pesticide_label", "pesticide_product"]}}

        results = get_cached_search_results(
            index, embedding, 'product', PRODUCT_SEARCH_TOP_K,
            filters=search_filter, query_text=product_query
        )

        # Filter out wrong product types
        if product_need == 'fungicide':
            return _filter_non_fungicides(results)
        elif product_need == 'herbicide':
            return _filter_non_herbicides(results)
        else:
            return {'matches': results.get('matches', [])[:30]}

    return {'matches': []}


def _filter_non_fungicides(results):
    """Filter out herbicides and insecticides from fungicide search."""
    filtered = []
    for match in results.get('matches', []):
        source = match.get('metadata', {}).get('source', '').lower()
        text = match.get('metadata', {}).get('text', '').lower()[:200]

        is_herbicide = any(h in source or h in text for h in HERBICIDES)
        is_insecticide = any(i in source or i in text for i in INSECTICIDES)

        if not is_herbicide and not is_insecticide:
            filtered.append(match)

    return {'matches': filtered[:30]}


def _filter_non_herbicides(results):
    """Filter out fungicides from herbicide search."""
    filtered = []
    for match in results.get('matches', []):
        source = match.get('metadata', {}).get('source', '').lower()
        is_fungicide = any(f in source for f in FUNGICIDES)

        if not is_fungicide:
            filtered.append(match)

    return {'matches': filtered[:30]}


def search_timing(index, openai_client, question, grass_type, model="text-embedding-3-small"):
    """Search for timing-related results with caching."""
    question_lower = question.lower()

    if any(word in question_lower for word in TOPIC_KEYWORDS['timing']):
        timing_query = f"{question} timing schedule calendar program {grass_type or ''}"
        embedding = get_embedding(openai_client, timing_query, model)

        return get_cached_search_results(
            index, embedding, 'timing', TIMING_SEARCH_TOP_K,
            filters=None, query_text=timing_query
        )

    return {'matches': []}


def search_all_parallel(index, openai_client, question, expanded_query, product_need, grass_type, model="text-embedding-3-small"):
    """
    Execute all search queries in parallel for better performance.

    Args:
        index: Pinecone index
        openai_client: OpenAI client
        question: Original question
        expanded_query: Expanded query with grass type and region
        product_need: Detected product type need
        grass_type: Detected grass type
        model: Embedding model

    Returns:
        Dict with 'general', 'product', and 'timing' results
    """
    results = {
        'general': {'matches': []},
        'product': {'matches': []},
        'timing': {'matches': []}
    }

    # Generate primary embedding first (needed for general search)
    primary_embedding = get_embedding(openai_client, expanded_query, model)

    def do_general_search():
        return ('general', search_general(index, primary_embedding, query_text=expanded_query))

    def do_product_search():
        return ('product', search_products(index, openai_client, question, product_need, model))

    def do_timing_search():
        return ('timing', search_timing(index, openai_client, question, grass_type, model))

    # Execute searches in parallel
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [
            executor.submit(do_general_search),
            executor.submit(do_product_search),
            executor.submit(do_timing_search)
        ]

        for future in as_completed(futures):
            try:
                key, result = future.result()
                results[key] = result
            except Exception as e:
                logger.error(f"Error in parallel search: {e}")

    return results


def find_source_url(source_name, search_folders=None):
    """Find the URL for a source document using cache."""
    return get_cached_source_url(source_name, search_folders)


def deduplicate_sources(sources):
    """Remove duplicate sources by name with fuzzy matching."""
    seen_names = set()
    seen_normalized = set()
    unique = []

    for source in sources:
        # Support both 'name' (Pinecone sources) and 'title' (web search sources)
        name = source.get('name') or source.get('title') or ''
        if not name:
            # Source with no name/title — include it but skip dedup
            unique.append(source)
            continue

        # Normalize for fuzzy matching
        normalized = _normalize_source_name(name)

        # Skip if we've seen this exact name or a very similar one
        if name in seen_names:
            continue
        if normalized in seen_normalized:
            continue

        seen_names.add(name)
        seen_normalized.add(normalized)
        unique.append(source)

    return unique


def _normalize_source_name(name: str) -> str:
    """
    Normalize source name for fuzzy deduplication.
    Handles common variations in PDF naming.
    """
    import re

    # Lowercase
    normalized = name.lower()

    # Remove file extensions first
    normalized = re.sub(r'\.(pdf|doc|docx)$', '', normalized)

    # Remove version numbers
    normalized = re.sub(r'[-_]?v?\d+(\.\d+)?$', '', normalized)

    # Remove common suffixes (label, sds, etc.)
    normalized = re.sub(r'[-_\s]*(label|sds|msds|specimen|booklet|brochure)[-_\s]*', '', normalized)

    # Normalize separators to spaces
    normalized = re.sub(r'[-_\s]+', ' ', normalized).strip()

    return normalized


def deduplicate_results(results):
    """
    Remove duplicate search results by content similarity.
    Uses text hashing to identify near-duplicate chunks.
    """
    import hashlib

    seen_hashes = set()
    unique = []

    for result in results:
        metadata = result.get('metadata', {})
        text = metadata.get('text', '')

        # Create a hash of the first 200 chars (catches duplicate chunks)
        text_hash = hashlib.md5(text[:200].encode()).hexdigest()

        if text_hash not in seen_hashes:
            seen_hashes.add(text_hash)
            unique.append(result)

    return unique


def filter_display_sources(sources, allowed_folders):
    """Filter sources to only include those from allowed folders."""
    display = []
    for source in sources:
        url = source.get('url') or source.get('source') or ''
        if url and any(folder in url for folder in allowed_folders):
            display.append(source)
        elif not url:
            # Sources without URL/source path — include them anyway
            display.append(source)
    return display
