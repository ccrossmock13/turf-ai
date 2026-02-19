"""
Answer feasibility gate for Greenside AI.
Runs BEFORE search and LLM generation to catch contradictions,
impossible scenarios, and absurd parameters. Returns early with a
helpful correction instead of wasting API calls on unanswerable questions.
"""
import re
import logging
from typing import Dict, Optional, List

logger = logging.getLogger(__name__)


# --- Grass type classification ---
WARM_SEASON_GRASSES = {
    'bermudagrass', 'bermuda', 'cynodon',
    'zoysiagrass', 'zoysia',
    'st. augustinegrass', 'st augustine', 'stenotaphrum',
    'centipedegrass', 'centipede',
    'bahiagrass', 'bahia',
    'buffalograss', 'buffalo grass',
    'paspalum', 'seashore paspalum',
}

COOL_SEASON_GRASSES = {
    'bentgrass', 'bent grass', 'agrostis', 'creeping bent',
    'kentucky bluegrass', 'kbg', 'poa pratensis', 'bluegrass',
    'tall fescue', 'fescue',
    'perennial ryegrass', 'ryegrass', 'rye grass',
    'fine fescue',
}

# States/regions where warm-season grasses can't survive winters
COLD_CLIMATE_INDICATORS = [
    'minnesota', 'wisconsin', 'michigan', 'maine', 'vermont',
    'new hampshire', 'north dakota', 'south dakota', 'montana',
    'wyoming', 'alaska', 'idaho', 'iowa',
]

WINTER_MONTHS = ['december', 'january', 'february']
DORMANT_WARM_MONTHS = ['november', 'december', 'january', 'february', 'march']

# Realistic parameter bounds
PARAMETER_BOUNDS = {
    'ph': {'min': 2.0, 'max': 12.0, 'label': 'Soil pH', 'typical': '5.5-7.5'},
    'nitrogen_per_1000': {'min': 0.01, 'max': 8.0, 'label': 'Nitrogen per 1000 sq ft per application', 'typical': '0.25-1.5 lbs'},
    'mowing_height_home': {'min': 0.5, 'max': 6.0, 'label': 'Home lawn mowing height', 'typical': '2.5-4.0 inches'},
    'mowing_height_green': {'min': 0.06, 'max': 0.200, 'label': 'Putting green height', 'typical': '0.100-0.150 inches'},
    'water_per_night': {'min': 0, 'max': 2.0, 'label': 'Irrigation per night', 'typical': '0.25-0.5 inches'},
}


def check_feasibility(question: str) -> Optional[Dict]:
    """
    Check if a question contains contradictions, impossibilities, or absurd values.

    Returns None if the question is feasible (proceed normally).
    Returns a response dict if the question should be intercepted.
    """
    q_lower = question.lower()
    issues = []

    # Run all checks
    issues.extend(_check_grass_season_contradiction(q_lower))
    issues.extend(_check_geographic_impossibility(q_lower))
    issues.extend(_check_conflicting_actions(q_lower))
    issues.extend(_check_absurd_parameters(q_lower, question))
    issues.extend(_check_impossible_scenarios(q_lower))
    issues.extend(_check_label_category_mismatch(q_lower))
    issues.extend(_check_safety_violations(q_lower, question))

    if not issues:
        return None

    # Build a helpful response addressing the issues
    response = _build_feasibility_response(issues, question)
    logger.info(f"Feasibility gate triggered: {len(issues)} issue(s) for: {question[:80]}")
    return response


def _check_grass_season_contradiction(q: str) -> List[Dict]:
    """Detect warm-season/cool-season misclassification."""
    issues = []

    # "cool-season bermudagrass" or "warm-season bentgrass"
    for grass in WARM_SEASON_GRASSES:
        if grass in q and 'cool-season' in q and 'not cool-season' not in q:
            issues.append({
                'type': 'contradiction',
                'message': f"{grass.title()} is a **warm-season** grass, not cool-season. "
                           f"It thrives in temperatures above 80°F and goes dormant below 60°F.",
                'severity': 'high'
            })
            break

    for grass in COOL_SEASON_GRASSES:
        if grass in q and 'warm-season' in q and 'not warm-season' not in q:
            issues.append({
                'type': 'contradiction',
                'message': f"{grass.title()} is a **cool-season** grass, not warm-season. "
                           f"It grows best between 60-75°F.",
                'severity': 'high'
            })
            break

    return issues


def _check_geographic_impossibility(q: str) -> List[Dict]:
    """Detect grass types that can't survive in mentioned climates."""
    issues = []

    # Warm-season grass + cold climate + winter context
    detected_warm_grass = None
    for grass in WARM_SEASON_GRASSES:
        if grass in q:
            detected_warm_grass = grass
            break

    if detected_warm_grass:
        in_cold_climate = any(loc in q for loc in COLD_CLIMATE_INDICATORS)
        in_winter = any(month in q for month in WINTER_MONTHS)

        if in_cold_climate and in_winter:
            issues.append({
                'type': 'geographic_impossibility',
                'message': f"{detected_warm_grass.title()} is a warm-season grass that goes "
                           f"completely dormant (and may not survive) in cold northern climates "
                           f"during winter. It won't respond to fertilization or active management "
                           f"when dormant.",
                'severity': 'high'
            })
        elif in_cold_climate:
            issues.append({
                'type': 'geographic_concern',
                'message': f"Note: {detected_warm_grass.title()} is a warm-season grass with limited "
                           f"cold hardiness. In northern climates, winter survival can be a significant "
                           f"challenge. Consider whether this is the best grass choice for your location.",
                'severity': 'medium'
            })

    # Bermuda overseeding in winter in cold climates
    if ('overseed' in q or 'seeding' in q) and detected_warm_grass:
        if in_winter if 'in_winter' in dir() else any(m in q for m in WINTER_MONTHS):
            cold = any(loc in q for loc in COLD_CLIMATE_INDICATORS)
            if cold:
                issues.append({
                    'type': 'impossible_timing',
                    'message': f"{detected_warm_grass.title()} requires soil temperatures above "
                               f"65°F for germination. Seeding in winter in a cold climate will not "
                               f"produce germination. Wait until late spring/early summer when soil "
                               f"temps are consistently warm.",
                    'severity': 'high'
                })

    return issues


def _check_conflicting_actions(q: str) -> List[Dict]:
    """Detect mutually exclusive turf management actions."""
    issues = []

    # Pre-emergent + overseeding
    has_pre_emergent = any(term in q for term in [
        'pre-emergent', 'preemergent', 'pre emergent', 'barricade', 'dimension',
        'prodiamine', 'dithiopyr', 'pendimethalin', 'indaziflam', 'specticle'
    ])
    has_seeding = any(term in q for term in [
        'overseed', 'over-seed', 'seed', 'seeding', 'reseed', 'establish from seed'
    ])

    if has_pre_emergent and has_seeding:
        issues.append({
            'type': 'conflicting_actions',
            'message': "**Pre-emergent herbicides and overseeding are conflicting actions.** "
                       "Pre-emergent herbicides work by preventing seed germination — including "
                       "desirable turfgrass seed. You typically need to wait 8-16 weeks after "
                       "pre-emergent application before seeding (check the specific product label), "
                       "or use siduron (Tupersan), which is the only pre-emergent safe for use "
                       "at time of seeding.",
            'severity': 'high'
        })

    # Kill grass + keep it green
    wants_kill = any(term in q for term in ['kill all', 'kill the', 'eliminate', 'destroy'])
    wants_green = any(term in q for term in ['keep green', 'keep it green', 'stay green', 'looking green'])
    if wants_kill and wants_green:
        issues.append({
            'type': 'contradiction',
            'message': "You can't kill turfgrass and keep it green at the same time. "
                       "Could you clarify your goal? Options include:\n"
                       "- **Renovation**: Kill existing turf, then establish new turf\n"
                       "- **Transition**: Gradually replace one grass species with another\n"
                       "- **Selective control**: Target specific weeds while keeping desirable turf",
            'severity': 'high'
        })

    return issues


def _check_absurd_parameters(q: str, original: str) -> List[Dict]:
    """Detect unrealistic numerical values in the question."""
    issues = []

    # pH check
    ph_match = re.search(r'ph\s*(?:of|is|at|=|:)?\s*(\d+\.?\d*)', q)
    if ph_match:
        ph_val = float(ph_match.group(1))
        if ph_val > 12 or ph_val < 2:
            issues.append({
                'type': 'absurd_value',
                'message': f"A soil pH of {ph_val} is not realistic and is highly unlikely in any natural soil. "
                           f"The pH scale has a range of 0-14, but soils typically range from "
                           f"4.0-9.0 (turf ideal: 6.0-7.0). A reading of {ph_val} is impossible under "
                           f"normal conditions and likely indicates a calibration error — "
                           f"retest with a freshly calibrated meter or verify with a soil lab.",
                'severity': 'high'
            })

    # Nitrogen rate check (lbs per 1000)
    n_match = re.search(r'(\d+\.?\d*)\s*(?:lbs?|pounds?)\s*(?:of\s+)?(?:nitrogen|n)\s*(?:per|/)\s*(?:1[,.]?000|thousand)', q)
    if not n_match:
        n_match = re.search(r'(\d+\.?\d*)\s*(?:lbs?|pounds?)\s*(?:of\s+)?(?:nitrogen|n\b)', q)
    if n_match:
        n_val = float(n_match.group(1))
        if n_val > 5:
            issues.append({
                'type': 'absurd_value',
                'message': f"**{n_val} lbs of nitrogen per 1000 sq ft is extremely excessive.** "
                           f"Typical application rates are 0.25-1.5 lbs N per 1000 sq ft. "
                           f"Annual totals rarely exceed 4-6 lbs N per 1000 sq ft. "
                           f"Applying {n_val} lbs would likely cause severe burn, salt damage, "
                           f"and environmental contamination.",
                'severity': 'high'
            })

    # Mowing height for home lawn
    mow_match = re.search(r'(?:mow|mowing|height|hoc)\s*(?:at|to|of)?\s*(\d*\.?\d+)\s*(?:inch|in|")', q)
    if mow_match:
        height = float(mow_match.group(1))
        is_home = any(term in q for term in ['home lawn', 'residential', 'home yard', 'my lawn', 'my yard'])
        is_green = any(term in q for term in ['green', 'putting'])

        if is_home and height < 0.5:
            issues.append({
                'type': 'absurd_value',
                'message': f"A mowing height of {height} inches is far too low for a home lawn. "
                           f"That's putting green territory (0.100-0.150\"). Home lawns should be "
                           f"mowed at 2.5-4.0 inches for cool-season grasses or 1.0-2.0 inches for "
                           f"warm-season grasses. Mowing this low would scalp and kill the turf.",
                'severity': 'high'
            })

    # Water rate per night
    water_match = re.search(r'(\d+\.?\d*)\s*inch(?:es)?\s*(?:of\s+)?water\s*(?:per|a|each)?\s*night', q)
    if not water_match:
        water_match = re.search(r'water\s+(\d+\.?\d*)\s*inch(?:es)?\s*(?:per|a|each)?\s*night', q)
    if water_match:
        water_val = float(water_match.group(1))
        if water_val > 2:
            issues.append({
                'type': 'absurd_value',
                'message': f"{water_val} inches of water per night is far too much and would cause "
                           f"flooding, root rot, and disease. Most turf only needs about 1-1.5 inch per week "
                           f"total — that's typically 0.25-0.5 inches per session, 2-3 times per week. "
                           f"Applying {water_val} inches nightly is excessive by any standard. "
                           f"Check your irrigation system output — a typical rotor head applies about "
                           f"0.3-0.5 inches per hour. A reading of {water_val} inches likely indicates "
                           f"a measurement or calibration error.",
                'severity': 'high'
            })

    # Product rate check — Heritage at 10 oz (label max ~0.4 oz)
    heritage_match = re.search(r'heritage\s*(?:at|@)?\s*(\d+\.?\d*)\s*(?:oz|ounce)', q)
    if heritage_match:
        rate = float(heritage_match.group(1))
        if rate > 2:
            issues.append({
                'type': 'absurd_value',
                'message': f"Heritage (azoxystrobin) at {rate} oz/1000 sq ft **far exceeds the "
                           f"label rate**. The standard Heritage rate is 0.2-0.4 oz/1000 sq ft. "
                           f"Applying {rate} oz would be a **label violation** (federal law), "
                           f"risk phytotoxicity, and waste product.",
                'severity': 'high'
            })

    return issues


def _check_impossible_scenarios(q: str) -> List[Dict]:
    """Detect physically impossible or absurd scenarios."""
    issues = []

    # Growing turf on Mars, moon, etc.
    space_locations = ['mars', 'moon', 'jupiter', 'space station', 'outer space', 'venus', 'saturn']
    if any(loc in q for loc in space_locations):
        issues.append({
            'type': 'impossible_scenario',
            'message': "Turfgrass requires Earth's atmosphere, soil, and climate conditions to grow. "
                       "There are no established turfgrass management practices for extraterrestrial "
                       "environments. I can help with any Earth-based turf management questions!",
            'severity': 'high'
        })

    # FRAC codes that don't exist
    frac_match = re.search(r'frac\s*(?:code\s*)?(\d+)', q)
    if frac_match:
        frac_num = int(frac_match.group(1))
        valid_frac = {1, 2, 3, 4, 5, 7, 9, 11, 12, 13, 14, 17, 19, 21, 22, 27, 28, 29, 33, 40, 43, 49, 50}
        if frac_num > 50 or (frac_num > 0 and frac_num not in valid_frac and frac_num < 50):
            # Only flag clearly fake ones (high numbers)
            if frac_num > 50:
                issues.append({
                    'type': 'nonexistent_classification',
                    'message': f"FRAC {frac_num} is not a recognized fungicide resistance group. "
                               f"The FRAC (Fungicide Resistance Action Committee) code system "
                               f"currently goes up to around FRAC 50. Common codes include "
                               f"FRAC 3 (DMIs), FRAC 7 (SDHIs), FRAC 11 (strobilurins), and FRAC M5 "
                               f"(multi-site). Would you like information about a specific FRAC group?",
                    'severity': 'medium'
                })

    return issues


def _check_label_category_mismatch(q: str) -> List[Dict]:
    """Detect when a product is being asked about for the wrong use category."""
    issues = []

    # Zoysia + cool-season-only label
    if 'zoysia' in q and ('cool-season' in q or 'cool season' in q) and 'label' in q:
        if any(term in q for term in ['use it anyway', 'apply anyway', 'use it on', 'can i use']):
            issues.append({
                'type': 'label_violation',
                'message': "**Using a product labeled only for cool-season turf on zoysiagrass "
                           "is an off-label application.** This can cause turf injury and is a "
                           "violation of federal law (FIFRA). Always follow the product label — "
                           "it is a legal document. Look for products specifically labeled for "
                           "warm-season or zoysiagrass turf.",
                'severity': 'high'
            })

    return issues


def _check_safety_violations(q: str, original: str) -> List[Dict]:
    """
    Detect safety-critical questions where the user is asking about
    dangerous practices. These get a direct safety warning rather than
    being passed to the LLM which might give a permissive answer.
    """
    issues = []

    # --- 1. Doubling / exceeding label rate ---
    double_rate = any(phrase in q for phrase in [
        'double the rate', 'double the fungicide', 'double the herbicide',
        'double the insecticide', 'twice the rate', 'twice the label',
        'double the application', '2x the rate', '2x the label',
        'triple the rate', '3x the rate',
    ])
    if double_rate:
        issues.append({
            'type': 'safety_label_violation',
            'message': "**Exceeding the label rate is a violation of federal law (FIFRA).** "
                       "The label is the law — applying more than the maximum label rate is "
                       "illegal, risks phytotoxicity and turf damage, harms the environment, "
                       "and accelerates resistance development. If the standard rate isn't "
                       "providing adequate control, consider rotating to a different mode of "
                       "action, improving cultural practices, or consulting your distributor.",
            'severity': 'high'
        })

    # Explicit "label says X but I want Y" pattern (much higher rate)
    label_override = re.search(
        r'label\s+says?\s+(?:apply\s+)?(?:at\s+)?(\d+\.?\d*)\s*(?:fl\s*)?oz.*?(?:but|want|use|apply)\s+(\d+\.?\d*)\s*(?:fl\s*)?oz',
        q
    )
    if label_override:
        label_rate = float(label_override.group(1))
        desired_rate = float(label_override.group(2))
        if desired_rate > label_rate * 1.5:
            issues.append({
                'type': 'safety_label_violation',
                'message': f"**Applying {desired_rate} oz when the label says {label_rate} oz is a "
                           f"federal violation.** The label maximum rate is a legal limit, not a suggestion. "
                           f"Exceeding it is illegal under FIFRA, risks phytotoxicity, and won't necessarily "
                           f"improve efficacy. Always follow the label — the label is the law.",
                'severity': 'high'
            })

    # --- 2. Pre-rain application (environmental risk) ---
    pre_rain = any(phrase in q for phrase in [
        'before a heavy rain', 'before rain', 'before it rains',
        'before the storm', 'before a rainstorm', 'before heavy rain',
        'right before rain',
    ])
    mentions_pesticide = any(term in q for term in [
        'herbicide', 'fungicide', 'insecticide', 'pesticide',
        'roundup', 'glyphosate', 'spray', 'apply',
    ])
    if pre_rain and mentions_pesticide:
        issues.append({
            'type': 'safety_environmental',
            'message': "**Applying pesticides before heavy rain risks runoff and environmental "
                       "contamination.** Rain can wash products off target into storm drains, "
                       "ponds, and waterways — harming aquatic life and violating environmental "
                       "regulations. Most labels require no rain within 24-48 hours after "
                       "application. Check the specific product label for rain-free requirements "
                       "and always monitor the forecast before spraying.",
            'severity': 'high'
        })

    # --- 3. Application near water bodies ---
    near_water = any(phrase in q for phrase in [
        'near a pond', 'near the pond', 'near water', 'by the pond',
        'by the lake', 'near the lake', 'near a lake', 'by the stream',
        'near the creek', 'near a creek', 'along the water',
        'next to the pond', 'next to water',
    ])
    if near_water and mentions_pesticide:
        issues.append({
            'type': 'safety_water_buffer',
            'message': "**Most pesticide labels require buffer zones near water bodies.** "
                       "Typical setbacks are 25-100+ feet from ponds, lakes, streams, and "
                       "wetlands. Some products (especially aquatic-toxic ones) have strict "
                       "no-spray zones. Always check the product label for specific buffer "
                       "zone requirements, use drift-reducing nozzles, and avoid spraying "
                       "when wind could carry product toward water.",
            'severity': 'high'
        })

    # --- 4. PPE dismissal ---
    ppe_dismissal = any(phrase in q for phrase in [
        'just wear shorts', 'without ppe', 'no ppe',
        'don\'t need ppe', 'do i need ppe', 'skip ppe',
        'don\'t need gloves', 'without gloves',
        'no protection', 'without protection',
    ])
    mentions_chemical = any(term in q for term in [
        'fungicide', 'herbicide', 'insecticide', 'pesticide',
        'spray', 'apply', 'daconil', 'chlorothalonil',
    ])
    if ppe_dismissal and mentions_chemical:
        issues.append({
            'type': 'safety_ppe_required',
            'message': "**PPE (Personal Protective Equipment) is legally required per the product label.** "
                       "At minimum, most pesticide labels require long pants, long-sleeved shirt, "
                       "chemical-resistant gloves, and closed-toe shoes. Many products also require "
                       "eye protection and respirators. The PPE section of the label is a legal "
                       "requirement, not a suggestion. Failure to wear proper PPE puts your health "
                       "at serious risk from dermal absorption, inhalation, and eye exposure.",
            'severity': 'high'
        })

    # --- 5. REI (Re-Entry Interval) violation ---
    rei_violation = any(phrase in q for phrase in [
        'play immediately', 'golfers play immediately',
        'play right after', 'play right away',
        'let golfers on', 'mow right after spray',
        'no waiting', 'no wait time',
    ])
    mentions_spray_product = any(term in q for term in [
        'spray', 'apply', 'daconil', 'chlorothalonil', 'fungicide',
        'herbicide', 'insecticide', 'pesticide', 'greens',
    ])
    if rei_violation and mentions_spray_product:
        issues.append({
            'type': 'safety_rei_violation',
            'message': "**All pesticides have a Re-Entry Interval (REI) that must be observed.** "
                       "The REI is the minimum time after application before people can safely enter "
                       "the treated area without PPE. For most turf products, this is 'until dry' "
                       "(typically 2-4 hours), but some products have 12-24+ hour REIs. Allowing "
                       "golfers or workers onto freshly treated areas is a label violation and "
                       "a health risk. Check the label for the specific REI.",
            'severity': 'high'
        })

    # --- 6. Same MOA (mode of action) resistance risk ---
    same_moa = any(phrase in q for phrase in [
        'three different dmi', '3 dmi', 'three dmi',
        'back to back to back', 'same mode of action',
        'same frac', 'same moa', 'only dmi', 'only strobilurin',
        'only use frac 3', 'only use frac 11', 'all frac 3',
        'all frac 11', 'all dmi fungicides',
    ])
    if same_moa:
        issues.append({
            'type': 'safety_resistance_risk',
            'message': "**Using the same mode of action (MOA) repeatedly accelerates fungicide resistance.** "
                       "Resistance management requires rotating between different FRAC groups. "
                       "For example, alternate between FRAC 3 (DMIs like propiconazole), "
                       "FRAC 11 (strobilurins like azoxystrobin), FRAC 7 (SDHIs), and "
                       "multi-site products (FRAC M5 like chlorothalonil). "
                       "Use at least 2-3 different MOA groups in your spray program, and always "
                       "tank-mix a single-site fungicide with a multi-site protectant.",
            'severity': 'high'
        })

    # --- 7. Illegal disposal ---
    illegal_disposal = any(phrase in q for phrase in [
        'dump them in', 'dump in the ditch', 'dump in the drain',
        'pour down the drain', 'pour in the ditch', 'dump leftover',
        'pour leftover', 'dispose in the ditch', 'throw away pesticide',
        'pour out the extra', 'dump the extra',
    ])
    if illegal_disposal:
        issues.append({
            'type': 'safety_illegal_disposal',
            'message': "**Dumping pesticides into drainage areas, waterways, or storm drains is illegal and extremely "
                       "hazardous.** This violates federal EPA and state environmental regulations, "
                       "contaminates water sources, kills aquatic life, and can result in severe penalties. "
                       "Leftover pesticide must be: (1) applied to a labeled site at label rates, "
                       "(2) stored properly in original containers, or (3) taken to a hazardous waste "
                       "collection facility. Never mix different pesticide leftovers together. "
                       "Contact your state Department of Agriculture for disposal guidance.",
            'severity': 'high'
        })

    # --- 8. Extreme heat phytotoxicity ---
    heat_spray = re.search(r'(9[5-9]|10\d|11\d)\s*°?\s*[fF]', original)
    if not heat_spray:
        heat_spray = any(phrase in q for phrase in [
            '98 degrees', '100 degrees', '95 degrees', '98°', '100°', '105°',
        ])
    mentions_tank_mix = any(term in q for term in [
        'tank mix', 'tank-mix', 'chlorothalonil', 'daconil',
        'dmi', 'triazole',
    ])
    if heat_spray and (mentions_tank_mix or mentions_pesticide):
        issues.append({
            'type': 'safety_heat_phytotoxicity',
            'message': "**Applying pesticides in extreme heat (>90°F) significantly increases "
                       "phytotoxicity risk.** Tank mixes are especially dangerous — chlorothalonil + "
                       "DMI combinations in high heat are a well-known cause of turf burn. "
                       "Best practice: spray in early morning or evening when temps are below 85°F, "
                       "avoid tank mixes during heat stress periods, ensure adequate irrigation "
                       "before application, and consider delaying non-critical sprays until "
                       "temperatures moderate.",
            'severity': 'high'
        })

    # --- 9. Expired product use ---
    expired = any(phrase in q for phrase in [
        'expired', 'past expiration', 'out of date', 'past its date',
        'shelf life', 'old fungicide', 'old herbicide', 'old pesticide',
        'years old', 'year old',
    ])
    wants_to_use = any(phrase in q for phrase in [
        'can i use', 'still use', 'still good', 'still work',
        'still effective', 'okay to use', 'safe to use',
        'apply it', 'spray it', 'use it',
    ])
    if expired and wants_to_use:
        issues.append({
            'type': 'safety_expired_product',
            'message': "**Using expired pesticides is not recommended.** Active ingredients degrade "
                       "over time, reducing efficacy and potentially changing the chemical composition "
                       "in unpredictable ways. Expired products may: not control the target pest, "
                       "cause unexpected phytotoxicity, clog spray equipment, and still carry "
                       "applicator safety risks. Dispose of expired products through your local "
                       "hazardous waste program and use fresh product for reliable results.",
            'severity': 'high'
        })

    # --- 10. Mixing leftover pesticides ---
    mixing_leftovers = any(phrase in q for phrase in [
        'mix leftover', 'mix remaining', 'combine leftover',
        'mix pesticides together', 'mix different pesticides',
        'mix them together', 'pour them together',
    ])
    if mixing_leftovers:
        issues.append({
            'type': 'safety_dangerous_mixing',
            'message': "**Never mix leftover pesticides together.** Combining different products can "
                       "cause dangerous chemical reactions, produce toxic fumes, reduce efficacy, "
                       "create unknown residues, and violate label requirements. Each product "
                       "must be stored, applied, and disposed of separately per its label. "
                       "Only mix products in a tank mix if both labels specifically allow the combination.",
            'severity': 'high'
        })

    return issues


def _build_feasibility_response(issues: List[Dict], question: str) -> Dict:
    """Build a user-friendly response from feasibility issues."""
    high_severity = [i for i in issues if i['severity'] == 'high']
    medium_severity = [i for i in issues if i['severity'] == 'medium']

    # Build the answer
    parts = []

    if high_severity:
        parts.append("I noticed some important concerns with your question that I want to address before providing advice:\n")
        for issue in high_severity:
            parts.append(f"**{issue['type'].replace('_', ' ').title()}:** {issue['message']}\n")

    if medium_severity:
        for issue in medium_severity:
            parts.append(f"**Note:** {issue['message']}\n")

    parts.append("\nPlease clarify or adjust your question and I'll be happy to help with specific, "
                 "research-backed recommendations!")

    answer = "\n".join(parts)

    # Determine confidence based on severity
    if high_severity:
        confidence_score = 0
        confidence_label = 'Issue Detected'
    else:
        confidence_score = 40
        confidence_label = 'Needs Clarification'

    return {
        'answer': answer,
        'sources': [],
        'confidence': {'score': confidence_score, 'label': confidence_label},
        'feasibility_issues': [i['type'] for i in issues]
    }
