"""
Knowledge base loader for structured turf management data.
Provides quick lookup for products, diseases, and reference tables.
"""
import json
import os
import logging
from typing import Dict, Optional, List, Any
from functools import lru_cache

logger = logging.getLogger(__name__)

KNOWLEDGE_DIR = os.path.join(os.path.dirname(__file__), 'knowledge')

# Scientific-name-to-common-name aliases for turf diseases.
# Used by photo lookup functions to resolve Latin binomials to their
# JSON-key common names before matching.
DISEASE_ALIASES = {
    'rhizoctonia solani': 'brown patch',
    'rhizoctonia cerealis': 'yellow patch',
    'sclerotinia homoeocarpa': 'dollar spot',
    'clarireedia jacksonii': 'dollar spot',
    'magnaporthe poae': 'summer patch',
    'gaeumannomyces graminis': 'take-all root rot',
    'colletotrichum cereale': 'anthracnose',
    'pyricularia grisea': 'gray leaf spot',
    'microdochium nivale': 'pink snow mold',
    'typhula incarnata': 'gray snow mold',
    'pythium aphanidermatum': 'pythium blight',
    'ophiosphaerella korrae': 'spring dead spot',
    'ophiosphaerella herpotricha': 'spring dead spot',
    'laetisaria fuciformis': 'red thread',
    'waitea circinata': 'brown ring patch',
    'large patch': 'large patch',
    'rhizoctonia zeae': 'large patch',
}


@lru_cache(maxsize=1)
def load_products() -> Dict:
    """Load the products knowledge base."""
    try:
        with open(os.path.join(KNOWLEDGE_DIR, 'products.json'), 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load products.json: {e}")
        return {}


@lru_cache(maxsize=1)
def load_diseases() -> Dict:
    """Load the diseases knowledge base."""
    try:
        with open(os.path.join(KNOWLEDGE_DIR, 'diseases.json'), 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load diseases.json: {e}")
        return {}


@lru_cache(maxsize=1)
def load_lookup_tables() -> Dict:
    """Load reference lookup tables."""
    try:
        with open(os.path.join(KNOWLEDGE_DIR, 'lookup_tables.json'), 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load lookup_tables.json: {e}")
        return {}


@lru_cache(maxsize=1)
def load_disease_photos() -> Dict:
    """Load the disease photo mapping."""
    try:
        with open(os.path.join(KNOWLEDGE_DIR, 'disease_photos.json'), 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load disease_photos.json: {e}")
        return {}


@lru_cache(maxsize=1)
def load_weed_photos() -> Dict:
    """Load the weed photo mapping."""
    try:
        with open(os.path.join(KNOWLEDGE_DIR, 'weed_photos.json'), 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load weed_photos.json: {e}")
        return {}


@lru_cache(maxsize=1)
def load_pest_photos() -> Dict:
    """Load the pest/insect photo mapping."""
    try:
        with open(os.path.join(KNOWLEDGE_DIR, 'pest_photos.json'), 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load pest_photos.json: {e}")
        return {}


def get_disease_photos(disease_name: str) -> List[Dict]:
    """
    Get reference photos for a disease.

    Args:
        disease_name: Disease name from detect_specific_subject() e.g. 'dollar spot'

    Returns:
        List of dicts with 'url' and 'caption' keys. Empty list if none found.
    """
    photos_data = load_disease_photos()
    if not photos_data:
        return []

    # Resolve scientific-name synonyms to common names first
    lowered = disease_name.lower().strip()
    if lowered in DISEASE_ALIASES:
        disease_name = DISEASE_ALIASES[lowered]

    # Alias common alternate names to their JSON keys
    aliases = {
        'downy_mildew': 'yellow_tuft',
        'stripe_smut': 'smuts',
        'melting_out': 'leaf_spot',
        'net_blotch': 'leaf_spot',
        'leaf_and_sheath_spot': 'mini_ring',
        'pink_snow_mold': 'microdochium_patch',
        'fusarium': 'microdochium_patch',
        'fusarium_patch': 'microdochium_patch',
        'grey_leaf_spot': 'gray_leaf_spot',
        'pythium_blight': 'pythium',
        'blue_green_algae': 'blue_green_algae',
    }

    # Normalize: 'dollar spot' -> 'dollar_spot', 'take-all' -> 'take_all'
    normalized = disease_name.lower().strip().replace(' ', '_').replace('-', '_')

    # Check aliases first
    if normalized in aliases:
        normalized = aliases[normalized]

    entry = photos_data.get(normalized)
    if not entry:
        # Partial match fallback
        for key in photos_data:
            if normalized in key or key in normalized:
                entry = photos_data[key]
                break

    if not entry:
        return []

    result = []
    for photo in entry.get('photos', []):
        filename = photo.get('filename', '')
        if not filename:
            continue
        # Only include if the file actually exists
        filepath = os.path.join(os.path.dirname(__file__), 'static', 'disease-photos', filename)
        result.append({
            'url': f'/disease-photos/{filename}',
            'caption': photo.get('caption', ''),
            'exists': os.path.isfile(filepath)
        })

    return result


def get_weed_photos(weed_name: str) -> List[Dict]:
    """
    Get reference photos for a weed.

    Args:
        weed_name: Weed name e.g. 'crabgrass', 'dandelion', 'goosegrass'

    Returns:
        List of dicts with 'url' and 'caption' keys. Empty list if none found.
    """
    photos_data = load_weed_photos()
    if not photos_data:
        return []

    # Resolve scientific-name synonyms to common names first
    lowered = weed_name.lower().strip()
    if lowered in DISEASE_ALIASES:
        weed_name = DISEASE_ALIASES[lowered]

    # Aliases for common alternate names
    aliases = {
        'poa_annua': 'annual_bluegrass',
        'poa_trivialis': 'roughstalk_bluegrass',
        'creeping_charlie': 'ground_ivy',
        'pennywort': 'dollarweed__pennywort',
        'dollarweed': 'dollarweed__pennywort',
        'oxalis': 'yellow_woodsorrel__oxalis',
        'yellow_woodsorrel': 'yellow_woodsorrel__oxalis',
        'prostrate_spurge': 'spotted_spurge__prostrate_spurge',
        'spotted_spurge': 'spotted_spurge__prostrate_spurge',
        'bull_paspalum': 'thin_paspalum__bull_paspalum',
        'thin_paspalum': 'thin_paspalum__bull_paspalum',
        'annual_ryegrass': 'ryegrass_italian__annual',
        'italian_ryegrass': 'ryegrass_italian__annual',
        'perennial_ryegrass': 'ryegrass_perennial',
        'shepherds_purse': 'shepherd_s_purse',
    }

    # Normalize: 'crabgrass' -> 'crabgrass', 'Poa annua' -> 'poa_annua'
    normalized = weed_name.lower().strip().replace(' ', '_').replace('-', '_')
    # Remove commas and clean
    normalized = normalized.replace(',', '').replace("'", '')
    while '__' in normalized:
        normalized = normalized.replace('__', '_')

    if normalized in aliases:
        normalized = aliases[normalized]

    entry = photos_data.get(normalized)
    if not entry:
        # Partial match fallback
        for key in photos_data:
            if normalized in key or key in normalized:
                entry = photos_data[key]
                break

    if not entry:
        return []

    result = []
    for photo in entry.get('photos', []):
        filename = photo.get('filename', '')
        if not filename:
            continue
        filepath = os.path.join(os.path.dirname(__file__), 'static', 'weed-photos', filename)
        result.append({
            'url': f'/weed-photos/{filename}',
            'caption': photo.get('caption', ''),
            'exists': os.path.isfile(filepath)
        })

    return result


def get_pest_photos(pest_name: str) -> List[Dict]:
    """
    Get reference photos for a pest/insect.

    Args:
        pest_name: Pest name e.g. 'white grubs', 'armyworm', 'mole cricket'

    Returns:
        List of dicts with 'url' and 'caption' keys. Empty list if none found.
    """
    photos_data = load_pest_photos()
    if not photos_data:
        return []

    # Resolve scientific-name synonyms to common names first
    lowered = pest_name.lower().strip()
    if lowered in DISEASE_ALIASES:
        pest_name = DISEASE_ALIASES[lowered]

    aliases = {
        'grub': 'white_grubs',
        'grubs': 'white_grubs',
        'white_grub': 'white_grubs',
        'armyworm': 'fall_armyworm',
        'army_worm': 'fall_armyworm',
        'webworm': 'sod_webworm',
        'web_worm': 'sod_webworm',
        'billbug': 'hunting_billbug',
        'abw': 'annual_bluegrass_weevil',
        'bluegrass_weevil': 'annual_bluegrass_weevil',
        'mite': 'bermudagrass_mites',
        'crane_fly': 'crane_fly_larvae',
        'leatherjacket': 'crane_fly_larvae',
        'spittlebug': 'twolined_spittlebug',
        'fire_ant': 'fire_ants',
        'ant': 'nuisance_ants',
        'ants': 'nuisance_ants',
        'mealybug': 'rhodesgrass_mealybug',
        'bee': 'ground_nesting_bees',
        'bees': 'ground_nesting_bees',
        'wasp': 'cicada_killer_wasp',
        'nematode': 'nematodes',
    }

    normalized = pest_name.lower().strip().replace(' ', '_').replace('-', '_')

    if normalized in aliases:
        normalized = aliases[normalized]

    entry = photos_data.get(normalized)
    if not entry:
        for key in photos_data:
            if normalized in key or key in normalized:
                entry = photos_data[key]
                break

    if not entry:
        return []

    result = []
    for photo in entry.get('photos', []):
        filename = photo.get('filename', '')
        if not filename:
            continue
        filepath = os.path.join(os.path.dirname(__file__), 'static', 'pest-photos', filename)
        result.append({
            'url': f'/pest-photos/{filename}',
            'caption': photo.get('caption', ''),
            'exists': os.path.isfile(filepath)
        })

    return result


def get_product_info(product_name: str) -> Optional[Dict]:
    """
    Look up product information by name or trade name.
    
    Args:
        product_name: Active ingredient or trade name
        
    Returns:
        Product info dict or None if not found
    """
    products = load_products()
    name_lower = product_name.lower()
    
    # Search all product categories
    for category in ['fungicides', 'herbicides', 'insecticides', 'pgrs']:
        if category not in products:
            continue
            
        for ai_name, info in products[category].items():
            # Check active ingredient name
            if name_lower in ai_name.lower():
                return {'active_ingredient': ai_name, 'category': category, **info}
            
            # Check trade names
            trade_names = info.get('trade_names', [])
            for trade in trade_names:
                if name_lower in trade.lower():
                    return {'active_ingredient': ai_name, 'category': category, **info}
    
    return None


def get_disease_info(disease_name: str) -> Optional[Dict]:
    """
    Look up disease information by name.
    
    Args:
        disease_name: Disease common name
        
    Returns:
        Disease info dict or None if not found
    """
    diseases = load_diseases()
    name_lower = disease_name.lower().replace(' ', '_').replace('-', '_')
    
    # Direct match
    if name_lower in diseases:
        return {'name': name_lower, **diseases[name_lower]}
    
    # Partial match
    for disease_key, info in diseases.items():
        if name_lower in disease_key or disease_key in name_lower:
            return {'name': disease_key, **info}
    
    return None


def get_frac_code_info(frac_code: str) -> Optional[Dict]:
    """Get FRAC code information."""
    tables = load_lookup_tables()
    frac_codes = tables.get('frac_codes', {})
    return frac_codes.get(str(frac_code))


def get_products_for_disease(disease_name: str) -> List[Dict]:
    """
    Get recommended products for a specific disease.
    
    Args:
        disease_name: Disease to treat
        
    Returns:
        List of product recommendations
    """
    disease_info = get_disease_info(disease_name)
    if not disease_info:
        return []
    
    # Get top products from disease info
    chemical_control = disease_info.get('chemical_control', {})
    top_products = chemical_control.get('top_products', [])
    
    recommendations = []
    for product_name in top_products:
        product_info = get_product_info(product_name)
        if product_info:
            recommendations.append(product_info)
    
    return recommendations


def build_context_from_knowledge(question: str) -> str:
    """
    Build additional context from knowledge base based on question content.
    
    Args:
        question: User's question
        
    Returns:
        Additional context string to append to RAG context
    """
    context_parts = []
    question_lower = question.lower()
    
    # Check for product mentions
    products = load_products()
    for category in ['fungicides', 'herbicides', 'insecticides', 'pgrs']:
        if category not in products:
            continue
        for ai_name, info in products[category].items():
            if ai_name in question_lower:
                context_parts.append(f"[Knowledge Base - {ai_name}]: {json.dumps(info, indent=2)}")
                break
            for trade in info.get('trade_names', []):
                if trade.lower() in question_lower:
                    context_parts.append(f"[Knowledge Base - {trade}]: {json.dumps(info, indent=2)}")
                    break
    
    # Check for disease mentions
    diseases = load_diseases()
    for disease_name, info in diseases.items():
        display_name = disease_name.replace('_', ' ')
        if display_name in question_lower or disease_name in question_lower:
            # Include only key information to avoid context bloat
            summary = {
                'pathogen': info.get('pathogen'),
                'environmental_triggers': info.get('environmental_triggers'),
                'cultural_control': info.get('cultural_control'),
                'chemical_control': info.get('chemical_control')
            }
            context_parts.append(f"[Knowledge Base - {display_name}]: {json.dumps(summary, indent=2)}")
            break
    
    return '\n\n'.join(context_parts)


def get_conversion(conversion_name: str) -> Optional[float]:
    """Get a conversion factor."""
    tables = load_lookup_tables()
    conversions = tables.get('conversions', {})
    return conversions.get(conversion_name)


def get_environmental_threshold(threshold_name: str) -> Optional[int]:
    """Get an environmental threshold value."""
    tables = load_lookup_tables()
    thresholds = tables.get('environmental_thresholds', {})
    return thresholds.get(threshold_name)


def extract_product_names(question: str) -> List[str]:
    """
    Extract product names mentioned in a question.

    Args:
        question: User's question

    Returns:
        List of recognized product names
    """
    found_products = []
    question_lower = question.lower()
    products = load_products()

    for category in ['fungicides', 'herbicides', 'insecticides', 'pgrs']:
        if category not in products:
            continue
        for ai_name, info in products[category].items():
            if ai_name.lower() in question_lower:
                found_products.append(ai_name)
            for trade in info.get('trade_names', []):
                if trade.lower() in question_lower:
                    found_products.append(trade)

    return list(set(found_products))


def extract_disease_names(question: str) -> List[str]:
    """
    Extract disease names mentioned in a question.

    Args:
        question: User's question

    Returns:
        List of recognized disease names
    """
    found_diseases = []
    question_lower = question.lower()
    diseases = load_diseases()

    for disease_name in diseases.keys():
        display_name = disease_name.replace('_', ' ')
        if display_name in question_lower or disease_name in question_lower:
            found_diseases.append(display_name)

    return list(set(found_diseases))


def enrich_context_with_knowledge(question: str, existing_context: str) -> str:
    """
    Enrich RAG context with structured knowledge base data.

    Args:
        question: User's question
        existing_context: Existing context from vector search

    Returns:
        Enhanced context with knowledge base additions
    """
    kb_context = build_context_from_knowledge(question)

    if kb_context:
        return f"{existing_context}\n\n--- VERIFIED PRODUCT/DISEASE DATA ---\n\n{kb_context}"

    return existing_context
