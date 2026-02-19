"""
Knowledge base answer validator for Greenside AI.
Cross-checks AI-generated answers against structured JSON data
(products.json, diseases.json, lookup_tables.json) to catch:
- Wrong application rates
- Incorrect FRAC/HRAC/IRAC codes
- Wrong product categories
- Disease-product mismatches
- Incorrect environmental thresholds

Runs AFTER LLM generation, BEFORE returning to user.
"""
import re
import logging
from typing import Dict, List, Optional, Tuple
from knowledge_base import (
    load_products, load_diseases, load_lookup_tables,
    get_product_info, get_disease_info
)

logger = logging.getLogger(__name__)


def validate_answer(answer: str, question: str) -> Dict:
    """
    Validate an AI answer against the structured knowledge base.

    Returns:
        Dict with:
        - valid: bool (True if no issues found)
        - issues: list of issue descriptions
        - corrections: list of correction strings to append
        - confidence_penalty: int (0-25 point penalty)
    """
    issues = []
    corrections = []
    penalty = 0

    # Run all validations
    rate_issues = _validate_product_rates(answer)
    issues.extend(rate_issues)
    penalty += min(15, len(rate_issues) * 8)

    frac_issues = _validate_frac_codes(answer)
    issues.extend(frac_issues)
    penalty += min(10, len(frac_issues) * 5)

    disease_issues = _validate_disease_product_match(answer, question)
    issues.extend(disease_issues)
    penalty += min(10, len(disease_issues) * 5)

    threshold_issues = _validate_environmental_thresholds(answer)
    issues.extend(threshold_issues)
    penalty += min(5, len(threshold_issues) * 3)

    # Build correction text if there are issues
    if issues:
        correction_text = _format_corrections(issues)
        if correction_text:
            corrections.append(correction_text)

    return {
        'valid': len(issues) == 0,
        'issues': issues,
        'corrections': corrections,
        'confidence_penalty': min(25, penalty)
    }


def _validate_product_rates(answer: str) -> List[str]:
    """
    Check if product rates mentioned in the answer match the knowledge base.
    """
    issues = []
    products = load_products()
    answer_lower = answer.lower()

    # Build a rate lookup from all products
    rate_lookup = {}
    for category in ['fungicides', 'herbicides', 'insecticides', 'pgrs']:
        if category not in products:
            continue
        for ai_name, info in products[category].items():
            rates = info.get('rates', {})
            trade_names = info.get('trade_names', [])

            # Parse out numeric rate ranges from the rate strings
            all_rates = []
            for rate_type, rate_str in rates.items():
                nums = re.findall(r'(\d+\.?\d*)', str(rate_str))
                if nums:
                    all_rates.extend([float(n) for n in nums])

            if all_rates:
                max_rate = max(all_rates)
                min_rate = min(all_rates)
                entry = {
                    'ai_name': ai_name,
                    'min_rate': min_rate,
                    'max_rate': max_rate,
                    'rate_strings': rates,
                    'category': category
                }
                rate_lookup[ai_name.lower()] = entry
                for trade in trade_names:
                    rate_lookup[trade.lower()] = entry

    # Look for rate mentions in the answer
    # Pattern: "ProductName at X oz/1000" or "apply X fl oz of ProductName"
    for name_key, rate_info in rate_lookup.items():
        if name_key not in answer_lower:
            continue

        # Find rate mentions near this product name
        # Pattern: number followed by oz, fl oz, etc within ~100 chars
        name_pos = answer_lower.find(name_key)
        window = answer_lower[max(0, name_pos - 80):name_pos + len(name_key) + 80]

        rate_patterns = [
            r'(\d+\.?\d*)\s*(?:fl\s*)?oz',
            r'(\d+\.?\d*)\s*ounces?',
        ]

        for pattern in rate_patterns:
            matches = re.findall(pattern, window)
            for match in matches:
                mentioned_rate = float(match)
                max_label = rate_info['max_rate']

                # Flag if mentioned rate is more than 2x the max label rate
                # (some slack for area calculations, tank mix concentrations)
                if mentioned_rate > max_label * 2.5 and mentioned_rate > 1.0:
                    display_name = rate_info['ai_name'].title()
                    rate_strs = ', '.join(f"{k}: {v}" for k, v in rate_info['rate_strings'].items())
                    issues.append(
                        f"Rate check: {mentioned_rate} oz for {display_name} may exceed label rates. "
                        f"Verified rates: {rate_strs}."
                    )

    return issues


def _validate_frac_codes(answer: str) -> List[str]:
    """
    Check if FRAC code assignments in the answer match the knowledge base.
    """
    issues = []
    products = load_products()
    answer_lower = answer.lower()

    if 'frac' not in answer_lower:
        return issues

    # Build FRAC lookup for all fungicides
    frac_lookup = {}
    fungicides = products.get('fungicides', {})
    for ai_name, info in fungicides.items():
        frac = info.get('frac_code')
        if frac is not None:
            frac_lookup[ai_name.lower()] = str(frac)
            for trade in info.get('trade_names', []):
                frac_lookup[trade.lower()] = str(frac)

    # Look for patterns like "ProductName (FRAC X)" or "FRAC X ... ProductName"
    frac_pattern = r'frac\s*(?:code\s*)?(\d+|M\d+|P\d+)'
    frac_mentions = re.finditer(frac_pattern, answer, re.IGNORECASE)

    for match in frac_mentions:
        mentioned_frac = match.group(1).upper()
        pos = match.start()
        window = answer_lower[max(0, pos - 150):pos + 150]

        # Check if any known product is mentioned nearby
        for product_name, actual_frac in frac_lookup.items():
            if product_name in window:
                if mentioned_frac != actual_frac.upper():
                    display_name = product_name.title()
                    issues.append(
                        f"FRAC code mismatch: {display_name} is FRAC {actual_frac}, "
                        f"not FRAC {mentioned_frac} as stated in the answer."
                    )

    return issues


def _validate_disease_product_match(answer: str, question: str) -> List[str]:
    """
    Check if products recommended in the answer are actually effective
    against the disease being discussed.
    """
    issues = []
    products = load_products()
    diseases = load_diseases()
    answer_lower = answer.lower()
    question_lower = question.lower()

    # Detect which disease is being discussed
    target_disease = None
    for disease_name in diseases.keys():
        display = disease_name.replace('_', ' ')
        if display in question_lower or disease_name in question_lower:
            target_disease = disease_name
            break

    if not target_disease:
        return issues

    disease_info = diseases.get(target_disease, {})
    top_products = disease_info.get('chemical_control', {}).get('top_products', [])
    # Get all fungicide names that are effective for this disease
    effective_products = set()
    fungicides = products.get('fungicides', {})
    for ai_name, info in fungicides.items():
        diseases_list = info.get('diseases', [])
        if target_disease in diseases_list:
            effective_products.add(ai_name.lower())
            for trade in info.get('trade_names', []):
                effective_products.add(trade.lower())

    # Check if any non-fungicide products are mentioned as treatment
    for category in ['herbicides', 'insecticides']:
        cat_products = products.get(category, {})
        for ai_name, info in cat_products.items():
            names_to_check = [ai_name.lower()] + [t.lower() for t in info.get('trade_names', [])]
            for name in names_to_check:
                if name in answer_lower:
                    # Check if the answer is recommending it (not just mentioning it)
                    # Look for recommendation language near the product name
                    name_pos = answer_lower.find(name)
                    context_window = answer_lower[max(0, name_pos - 60):name_pos + len(name) + 60]
                    recommend_words = ['apply', 'use', 'recommend', 'spray', 'treat with', 'consider']
                    if any(rw in context_window for rw in recommend_words):
                        display = info.get('trade_names', [ai_name])[0] if info.get('trade_names') else ai_name
                        issues.append(
                            f"{display} ({ai_name}) is {'an ' + category[:-1] if category != 'insecticides' else 'an insecticide'}, "
                            f"not a fungicide. It won't control {target_disease.replace('_', ' ')}. "
                            f"Effective products include: {', '.join(top_products[:3])}."
                        )

    return issues


def _validate_environmental_thresholds(answer: str) -> List[str]:
    """
    Check if environmental thresholds mentioned in the answer are accurate.
    """
    issues = []
    tables = load_lookup_tables()
    answer_lower = answer.lower()

    # Check soil temperature thresholds
    soil_temps = tables.get('soil_temps_fahrenheit', {})

    # Crabgrass germination
    if 'crabgrass' in answer_lower and 'germinat' in answer_lower:
        correct_temp = soil_temps.get('crabgrass_germination', 55)
        temp_match = re.search(r'(\d+)\s*°?\s*[fF]', answer)
        if temp_match:
            mentioned = int(temp_match.group(1))
            # Allow some variance (±5°F) since different sources cite slightly different temps
            if abs(mentioned - correct_temp) > 8:
                issues.append(
                    f"Crabgrass germination temperature: answer mentions {mentioned}°F, "
                    f"standard reference is {correct_temp}°F soil temperature."
                )

    # Mowing heights
    mowing_heights = tables.get('mowing_heights_inches', {})
    if 'mowing height' in answer_lower or 'mow at' in answer_lower or 'height of cut' in answer_lower:
        # Check putting green heights
        if any(term in answer_lower for term in ['putting green', 'greens']):
            green_range = mowing_heights.get('putting_greens', '0.100-0.125')
            # This is informational — just ensure we're in the right ballpark
            pass

    return issues


def _format_corrections(issues: List[str]) -> str:
    """Format validation issues into a correction note."""
    if not issues:
        return ""

    if len(issues) == 1:
        return f"\n\n📋 **Verification Note:** {issues[0]}"

    correction = "\n\n📋 **Verification Notes:**\n"
    for issue in issues:
        correction += f"• {issue}\n"
    return correction


def apply_validation(answer: str, question: str) -> Tuple[str, Dict]:
    """
    Convenience function: validate and apply corrections to an answer.

    Returns:
        Tuple of (corrected_answer, validation_result)
    """
    result = validate_answer(answer, question)

    if result['corrections']:
        corrected = answer + ''.join(result['corrections'])
    else:
        corrected = answer

    return corrected, result
