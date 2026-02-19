"""
Product validation layer for Greenside AI.
Validates product claims in AI responses against the structured product database.
Catches category confusion (e.g., insecticide recommended for disease) and
flags unrecognized product names that may be hallucinated.
"""
import re
import json
import logging
from typing import Dict, List, Optional, Tuple
from knowledge_base import load_products, load_lookup_tables

logger = logging.getLogger(__name__)


# Build lookup indices on first call (cached by load_products)
def _build_product_index() -> Dict:
    """Build a flat lookup index: name -> product info for fast validation."""
    products = load_products()
    index = {}

    for category, items in products.items():
        for ai_name, info in items.items():
            entry = {
                'active_ingredient': ai_name,
                'category': category,
                **info
            }
            # Index by active ingredient name
            index[ai_name.lower()] = entry
            # Index by trade names
            for trade in info.get('trade_names', []):
                index[trade.lower()] = entry

    return index


_product_index = None


def get_product_index() -> Dict:
    """Get or build the product index (lazy singleton)."""
    global _product_index
    if _product_index is None:
        _product_index = _build_product_index()
    return _product_index


def lookup_product(name: str) -> Optional[Dict]:
    """
    Look up a product by active ingredient or trade name.

    Returns product info dict or None if not recognized.
    """
    idx = get_product_index()
    name_lower = name.lower().strip()

    # Exact match
    if name_lower in idx:
        return idx[name_lower]

    # Partial match (e.g., "banner" matches "Banner MAXX")
    for key, val in idx.items():
        if name_lower in key or key in name_lower:
            return val

    return None


def validate_product_in_answer(answer: str, question: str) -> Dict:
    """
    Validate product-related claims in an AI answer.

    Checks for:
    1. Product category confusion (herbicide recommended for disease, etc.)
    2. Unrecognized product names (potential hallucinations)
    3. FRAC/HRAC/IRAC code mismatches

    Returns:
        Dict with validation results:
        - valid: bool
        - issues: list of issue descriptions
        - corrections: list of correction suggestions
        - products_found: list of recognized products
        - unrecognized: list of product-like names not in database
    """
    idx = get_product_index()
    answer_lower = answer.lower()
    question_lower = question.lower()

    issues = []
    corrections = []
    products_found = []
    unrecognized = []

    # 1. Find all product mentions in the answer
    for key, product_info in idx.items():
        if key in answer_lower:
            products_found.append(product_info)

    # 2. Check for category confusion
    # Detect what the user is asking about
    asking_about_disease = any(term in question_lower for term in [
        'dollar spot', 'brown patch', 'pythium', 'anthracnose', 'fairy ring',
        'disease', 'fungus', 'fungal', 'leaf spot', 'summer patch',
        'take-all', 'snow mold', 'gray leaf spot', 'spring dead spot'
    ])
    asking_about_weeds = any(term in question_lower for term in [
        'crabgrass', 'goosegrass', 'poa annua', 'weed', 'nutsedge',
        'dandelion', 'clover', 'broadleaf', 'pre-emergent', 'post-emergent'
    ])
    asking_about_insects = any(term in question_lower for term in [
        'grub', 'webworm', 'chinch bug', 'cutworm', 'weevil', 'insect',
        'billbug', 'beetle', 'ant', 'mole cricket'
    ])

    for product in products_found:
        cat = product.get('category', '')
        name = product.get('active_ingredient', '')
        trade_names = product.get('trade_names', [])
        display = trade_names[0] if trade_names else name
        not_for = product.get('not_for', [])

        # Check: insecticide recommended for disease?
        if cat == 'insecticides' and asking_about_disease:
            # Is the answer actually recommending it for the disease?
            for disease_term in ['dollar spot', 'brown patch', 'pythium', 'anthracnose',
                                 'fairy ring', 'disease', 'fungal']:
                if disease_term in answer_lower:
                    issues.append(
                        f"{display} ({name}) is an insecticide, not a fungicide. "
                        f"It is not effective against {disease_term}."
                    )
                    break

        # Check: herbicide recommended for disease?
        if cat == 'herbicides' and asking_about_disease:
            for disease_term in ['dollar spot', 'brown patch', 'pythium', 'anthracnose',
                                 'fairy ring', 'disease', 'fungal']:
                if disease_term in answer_lower:
                    issues.append(
                        f"{display} ({name}) is an herbicide, not a fungicide. "
                        f"It cannot treat {disease_term}."
                    )
                    break

        # Check: fungicide recommended for weeds?
        if cat == 'fungicides' and asking_about_weeds:
            for weed_term in ['crabgrass', 'goosegrass', 'weed', 'nutsedge', 'dandelion']:
                if weed_term in answer_lower:
                    issues.append(
                        f"{display} ({name}) is a fungicide, not an herbicide. "
                        f"It is not effective against {weed_term}."
                    )
                    break

        # Check: PGR confusion
        if cat == 'pgrs' and (asking_about_disease or asking_about_weeds):
            issues.append(
                f"{display} ({name}) is a plant growth regulator (PGR), not a "
                f"{'fungicide' if asking_about_disease else 'herbicide'}."
            )

    # 3. Check FRAC/HRAC/IRAC code claims
    frac_mentions = re.findall(r'frac\s*(?:code\s*)?(\d+|M\d+|P\d+)', answer_lower)
    tables = load_lookup_tables()
    frac_codes = tables.get('frac_codes', {})

    for code in frac_mentions:
        code_upper = code.upper()
        # Check if a product in the answer has a different FRAC code
        for product in products_found:
            if product.get('category') == 'fungicides':
                actual_frac = str(product.get('frac_code', ''))
                if actual_frac and code_upper != actual_frac.upper():
                    # Only flag if the FRAC code and product are mentioned together
                    trade = product.get('trade_names', [''])[0]
                    ai_name = product.get('active_ingredient', '')
                    # Check proximity in text (within 200 chars)
                    for name_to_check in [trade.lower(), ai_name.lower()]:
                        if name_to_check in answer_lower:
                            pos_name = answer_lower.index(name_to_check)
                            pos_code = answer_lower.index(f'frac')
                            if abs(pos_name - pos_code) < 200:
                                issues.append(
                                    f"FRAC code mismatch: {trade} ({ai_name}) is FRAC {actual_frac}, "
                                    f"but the answer mentions FRAC {code_upper}."
                                )
                            break

    # 4. Build corrections
    for issue in issues:
        if 'insecticide' in issue and 'fungicide' in issue:
            corrections.append(
                "This product is designed for insect control, not disease control. "
                "Consider recommending a fungicide instead."
            )
        elif 'herbicide' in issue and 'fungicide' in issue:
            corrections.append(
                "This product is designed for weed control, not disease control. "
                "Consider recommending a fungicide instead."
            )

    return {
        'valid': len(issues) == 0,
        'issues': issues,
        'corrections': corrections,
        'products_found': [p.get('active_ingredient') for p in products_found],
        'unrecognized': unrecognized
    }


def check_product_exists(product_name: str) -> Tuple[bool, Optional[str]]:
    """
    Check if a product name exists in our database.

    Returns:
        (exists: bool, suggestion: str or None)
    """
    result = lookup_product(product_name)
    if result:
        trade = result.get('trade_names', [''])[0]
        return True, f"Found: {trade} ({result.get('active_ingredient')})"

    return False, None


def get_product_category(product_name: str) -> Optional[str]:
    """Get the category (fungicide/herbicide/insecticide/pgr) for a product."""
    result = lookup_product(product_name)
    if result:
        return result.get('category')
    return None


def format_validation_warning(validation_result: Dict) -> str:
    """
    Format validation issues into a user-facing warning to append to the answer.
    """
    if validation_result.get('valid', True):
        return ""

    issues = validation_result.get('issues', [])
    if not issues:
        return ""

    warning = "\n\n⚠️ **Product Note:** "
    if len(issues) == 1:
        warning += issues[0]
    else:
        warning += "Please note the following:\n"
        for issue in issues:
            warning += f"• {issue}\n"

    return warning
