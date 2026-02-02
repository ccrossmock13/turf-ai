"""
Query expansion utilities for improving search recall.
Handles synonyms, abbreviations, and vague question expansion.
"""

# Comprehensive turf industry synonym mappings
SYNONYMS = {
    # Products -> Active ingredients and aliases
    'heritage': 'heritage fungicide azoxystrobin strobilurin QoI FRAC11',
    'lexicon': 'lexicon intrinsic fluxapyroxad pyraclostrobin SDHI',
    'xzemplar': 'xzemplar fungicide fluxapyroxad SDHI FRAC7',
    'dedicate': 'dedicate stressgard azoxystrobin fungicide',
    'headway': 'headway azoxystrobin propiconazole DMI strobilurin',
    'banner maxx': 'banner maxx propiconazole DMI FRAC3',
    'daconil': 'daconil chlorothalonil contact fungicide FRACM5',
    'medallion': 'medallion fludioxonil phenylpyrrole FRAC12',
    'secure': 'secure fluazinam contact fungicide',
    'velista': 'velista penthiopyrad SDHI FRAC7',
    'posterity': 'posterity pydiflumetofen SDHI',
    'briskway': 'briskway azoxystrobin difenoconazole',
    'insignia': 'insignia pyraclostrobin strobilurin',
    'tartan': 'tartan trifloxystrobin triadimefon',
    'tourney': 'tourney metconazole DMI FRAC3',
    'maxtima': 'maxtima mefentrifluconazole DMI',

    # Herbicides
    'tenacity': 'tenacity herbicide mesotrione HPPD whitening',
    'drive': 'drive xlr8 herbicide quinclorac crabgrass',
    'monument': 'monument herbicide trifloxysulfuron ALS',
    'revolver': 'revolver foramsulfuron ALS herbicide',
    'barricade': 'barricade prodiamine pre-emergent preemergent',
    'dimension': 'dimension dithiopyr pre-emergent preemergent',
    'specticle': 'specticle indaziflam pre-emergent preemergent',
    'certainty': 'certainty sulfosulfuron ALS herbicide sedge',
    'sedgehammer': 'sedgehammer halosulfuron nutsedge sedge',
    'dismiss': 'dismiss sulfentrazone sedge broadleaf',
    'speedzone': 'speedzone carfentrazone 2,4-D broadleaf',
    'quicksilver': 'quicksilver carfentrazone burndown',
    'pylex': 'pylex topramezone HPPD bermuda',

    # PGRs
    'primo': 'primo maxx trinexapac-ethyl PGR plant growth regulator',
    'trimmit': 'trimmit paclobutrazol PGR growth regulator',
    'cutless': 'cutless flurprimidol PGR growth regulator',
    'anuew': 'anuew prohexadione calcium PGR',
    'proxy': 'proxy ethephon PGR seedhead suppression',

    # Insecticides
    'acelepryn': 'acelepryn chlorantraniliprole grub preventive diamide',
    'merit': 'merit imidacloprid neonicotinoid grub systemic',
    'arena': 'arena clothianidin neonicotinoid',
    'dylox': 'dylox trichlorfon grub curative fast-acting',
    'talstar': 'talstar bifenthrin pyrethroid surface',

    # Diseases
    'dollar spot': 'dollar spot sclerotinia homoeocarpa clarireedia jacksonii',
    'brown patch': 'brown patch rhizoctonia solani large patch',
    'pythium': 'pythium blight cottony blight grease spot',
    'anthracnose': 'anthracnose colletotrichum cereale basal rot foliar',
    'fairy ring': 'fairy ring basidiomycete mushroom hydrophobic',
    'summer patch': 'summer patch magnaporthiopsis poae necrotic ring',
    'take-all': 'take-all patch gaeumannomyces graminis',
    'gray leaf spot': 'gray leaf spot pyricularia grisea magnaporthe',
    'snow mold': 'snow mold pink gray microdochium typhula',
    'spring dead spot': 'spring dead spot ophiosphaerella bermuda',
    'red thread': 'red thread laetisaria fuciformis pink patch',
    'rust': 'rust puccinia crown leaf stem',
    'leaf spot': 'leaf spot helminthosporium bipolaris drechslera',
    'necrotic ring': 'necrotic ring spot ophiosphaerella korrae',

    # Weeds
    'crabgrass': 'crabgrass digitaria smooth hairy annual grass',
    'goosegrass': 'goosegrass eleusine indica annual grass',
    'poa': 'poa annua annual bluegrass winter annual',
    'poa annua': 'poa annua annual bluegrass winter annual triv',
    'nutsedge': 'nutsedge yellow purple cyperus sedge',
    'clover': 'clover white trifolium repens broadleaf',
    'dandelion': 'dandelion taraxacum broadleaf perennial',
    'ground ivy': 'ground ivy creeping charlie glechoma broadleaf',
    'spurge': 'spurge euphorbia spotted prostrate broadleaf',
    'knotweed': 'knotweed prostrate polygonum broadleaf',
    'plantain': 'plantain broadleaf buckhorn perennial',

    # Grasses
    'bentgrass': 'creeping bentgrass agrostis stolonifera velvet colonial',
    'bermudagrass': 'bermudagrass bermuda cynodon dactylon hybrid common',
    'zoysiagrass': 'zoysiagrass zoysia japonica matrella',
    'bluegrass': 'kentucky bluegrass poa pratensis KBG cool-season',
    'ryegrass': 'perennial ryegrass lolium perenne PRG',
    'fescue': 'tall fescue fine fescue festuca arundinacea',
    'paspalum': 'seashore paspalum paspalum vaginatum salt-tolerant',
    'st augustine': 'st augustinegrass stenotaphrum secundatum',
    'centipede': 'centipedegrass eremochloa ophiuroides',
    'bahia': 'bahiagrass paspalum notatum',

    # Cultural practices
    'aerify': 'aerification aeration core hollow tine solid',
    'topdress': 'topdressing sand application dressing',
    'overseed': 'overseeding interseeding renovation',
    'verticut': 'verticutting vertical mowing dethatching',
    'syringe': 'syringing light watering cooling',
    'scalp': 'scalping low mow renovation',

    # Equipment
    'reel mower': 'reel mower cylinder mower bedknife',
    'rotary mower': 'rotary mower deck blade',
    'sprayer': 'sprayer boom nozzle calibration GPM',
    'spreader': 'spreader broadcast drop spinner',
    'roller': 'roller lightweight vibratory smoothing',

    # General terms
    'rate': 'application rate dosage amount per 1000 sq ft per acre oz fl',
    'tank mix': 'tank mixing compatibility co-apply combination',
    'grub': 'grubs white grubs scarab beetle larvae japanese chafer',
    'worm': 'cutworm armyworm sod webworm caterpillar',
    'mite': 'mites eriophyid bermudagrass mite',
    'nematode': 'nematodes sting lance root-knot',
    'thatch': 'thatch layer organic matter decomposition',
    'compaction': 'compaction soil hardpan traffic',
    'drought': 'drought stress wilt dry LDS localized dry spot',
    'heat stress': 'heat stress summer decline high temperature',
    'winter kill': 'winterkill winter injury cold damage desiccation',
    'salt': 'salinity sodium chloride effluent reclaimed',
    'ph': 'pH acidity alkalinity lime sulfur',
    'nitrogen': 'nitrogen N fertility fertilizer urea ammonium',
    'iron': 'iron Fe chlorosis yellowing micronutrient',
    'potassium': 'potassium K stress tolerance',
}

# Turf-specific stop words to remove from queries
STOP_WORDS = {
    'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
    'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
    'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
    'should', 'may', 'might', 'must', 'shall', 'can', 'need', 'dare',
    'what', 'how', 'when', 'where', 'why', 'which', 'who', 'whom',
    'this', 'that', 'these', 'those', 'am', 'if', 'then', 'else',
    'so', 'than', 'too', 'very', 'just', 'about', 'into', 'through',
    'during', 'before', 'after', 'above', 'below', 'between', 'under',
    'again', 'further', 'once', 'here', 'there', 'all', 'each', 'few',
    'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only',
    'own', 'same', 'also', 'any', 'both', 'each', 'i', 'me', 'my', 'myself',
    'we', 'our', 'ours', 'you', 'your', 'yours', 'he', 'him', 'his', 'she',
    'her', 'hers', 'it', 'its', 'they', 'them', 'their', 'theirs',
    # Turf-specific common words to ignore
    'turf', 'grass', 'lawn', 'green', 'fairway', 'course', 'golf',
    'please', 'help', 'thanks', 'thank', 'need', 'want', 'like',
    'get', 'use', 'using', 'used', 'best', 'good', 'recommend',
}


def expand_query(question: str) -> str:
    """
    Expand query with synonyms and context to improve search.

    Args:
        question: Original user question

    Returns:
        Expanded query with relevant synonyms
    """
    expanded = question.lower()
    expansions_found = []

    # Check for each synonym mapping
    for term, expansion in SYNONYMS.items():
        if term in expanded:
            expansions_found.append(expansion)

    # Combine original with expansions
    if expansions_found:
        return f"{expanded} {' '.join(expansions_found)}"
    return expanded


def extract_keywords(question: str) -> list:
    """
    Extract meaningful keywords from a question.

    Args:
        question: User question

    Returns:
        List of keywords with stop words removed
    """
    import re
    words = re.findall(r'\b\w+\b', question.lower())
    return [w for w in words if w not in STOP_WORDS and len(w) > 2]


def expand_vague_question(question: str) -> str:
    """
    Expand vague questions to be more specific and searchable.

    Args:
        question: Original question (possibly vague)

    Returns:
        Expanded, more specific question
    """
    question_lower = question.lower().strip()

    # Don't expand already detailed questions
    if len(question) > 50:
        return question

    # Disease expansions
    diseases = {
        'dollar spot': 'What fungicide should I use to control dollar spot? Include rates and timing.',
        'brown patch': 'What fungicide should I use to control brown patch? Include rates and timing.',
        'pythium': 'What fungicide should I use to control pythium blight? Include rates and timing.',
        'summer patch': 'What fungicide should I use to control summer patch? Include rates and timing.',
        'anthracnose': 'What fungicide should I use to control anthracnose? Include rates and timing.',
        'fairy ring': 'How do I control fairy ring? Include both cultural and chemical options.',
        'snow mold': 'What fungicide should I use to prevent snow mold? Include application timing.',
        'rust': 'What fungicide should I use to control rust? Include rates.',
        'take-all': 'How do I manage take-all patch? Include cultural and chemical approaches.',
        'gray leaf spot': 'What fungicide for gray leaf spot? Include rates and resistance management.',
        'spring dead spot': 'How do I prevent spring dead spot in bermuda? Include timing.',
        'red thread': 'What fungicide for red thread? Include cultural practices.',
        'leaf spot': 'What fungicide for leaf spot and melting out? Include rates.',
    }

    for disease, expanded in diseases.items():
        if question_lower == disease or question_lower == f"{disease}?":
            return expanded

    # Weed expansions
    weeds = {
        'crabgrass': 'What pre-emergent herbicide should I use for crabgrass control? Include timing and rates.',
        'poa': 'How do I control Poa annua? Include both pre and post-emergent options.',
        'poa annua': 'How do I control Poa annua? Include both pre and post-emergent options.',
        'goosegrass': 'What herbicide should I use for goosegrass? Include timing and rates.',
        'nutsedge': 'What herbicide works for nutsedge? Include rates and timing.',
        'clover': 'What herbicide should I use for clover in turf?',
        'dandelion': 'What post-emergent herbicide for dandelions?',
        'ground ivy': 'What herbicide for ground ivy (creeping charlie)?',
        'sedge': 'What herbicide controls sedges? Include nutsedge and kyllinga.',
    }

    for weed, expanded in weeds.items():
        if question_lower == weed or question_lower == f"{weed}?":
            return expanded

    # Generic help
    if question_lower in ['help', 'help?', 'what spray', 'what to use', 'what do i do']:
        return "I need help with a turf problem. What information do you need from me to give a recommendation?"

    # Product rate lookups
    products = [
        'heritage', 'lexicon', 'xzemplar', 'primo', 'tenacity', 'monument',
        'barricade', 'dimension', 'acelepryn', 'medallion', 'headway',
        'banner', 'daconil', 'secure', 'velista', 'posterity', 'tourney',
        'specticle', 'certainty', 'dismiss', 'drive', 'revolver'
    ]

    for product in products:
        if question_lower == product or question_lower == f"{product}?":
            return f"What is the application rate for {product.title()}? Include target pest and turf type safety."

    # Sick/dying turf patterns
    sick_patterns = ['sick', 'dying', 'dead', 'brown', 'yellow', 'thin', 'weak', 'wilting']
    if any(pattern in question_lower for pattern in sick_patterns) and len(question) < 30:
        return f"My turf shows these symptoms: {question}. Help me diagnose the problem and recommend treatment."

    return question


def generate_query_variants(question: str) -> list:
    """
    Generate multiple query variants for better recall.
    Uses different phrasings to catch more relevant results.

    Args:
        question: Original user question

    Returns:
        List of query variants (including original)
    """
    variants = [question]
    question_lower = question.lower()

    # Get intent to guide variant generation
    intent = get_query_intent(question)

    # Add synonym-expanded version
    expanded = expand_query(question)
    if expanded != question.lower():
        variants.append(expanded)

    # Generate product-focused variant
    if intent.get('product_mentioned'):
        product = intent['product_mentioned']
        variants.append(f"{product} label rate application timing turf")

    # Generate disease-focused variant
    if intent.get('disease_mentioned'):
        disease = intent['disease_mentioned']
        variants.append(f"{disease} control treatment fungicide cultural management")

    # Generate weed-focused variant
    if intent.get('weed_mentioned'):
        weed = intent['weed_mentioned']
        variants.append(f"{weed} herbicide control pre-emergent post-emergent timing")

    # Add rate-focused variant for product questions
    if intent.get('wants_rate') or 'rate' in question_lower:
        variants.append(f"{question} product label application oz fl oz per 1000 sq ft")

    # Add cultural practice variant for management questions
    if any(word in question_lower for word in ['management', 'program', 'plan', 'schedule']):
        variants.append(f"{question} cultural practices timing calendar program")

    # Limit to avoid too many searches
    return variants[:4]


def get_query_intent(question: str) -> dict:
    """
    Analyze query to determine user intent.

    Args:
        question: User question

    Returns:
        Dict with intent classification
    """
    question_lower = question.lower()

    intent = {
        'type': 'general',
        'wants_rate': False,
        'wants_cultural': False,
        'wants_chemical': False,
        'wants_diagnosis': False,
        'product_mentioned': None,
        'disease_mentioned': None,
        'weed_mentioned': None,
    }

    # Check for rate questions
    rate_patterns = ['rate', 'how much', 'dosage', 'oz', 'fl oz', 'per 1000', 'per acre']
    if any(p in question_lower for p in rate_patterns):
        intent['wants_rate'] = True
        intent['type'] = 'rate'

    # Check for cultural practice questions
    cultural_patterns = ['mow', 'water', 'irrigat', 'fertil', 'aerif', 'topdress', 'overseed']
    if any(p in question_lower for p in cultural_patterns):
        intent['wants_cultural'] = True
        intent['type'] = 'cultural'

    # Check for chemical questions
    chemical_patterns = ['spray', 'apply', 'fungicide', 'herbicide', 'insecticide', 'chemical', 'product']
    if any(p in question_lower for p in chemical_patterns):
        intent['wants_chemical'] = True
        intent['type'] = 'chemical'

    # Check for diagnosis questions
    diag_patterns = ['diagnose', 'identify', 'what is', "what's wrong", 'problem', 'issue', 'dying', 'dead']
    if any(p in question_lower for p in diag_patterns):
        intent['wants_diagnosis'] = True
        intent['type'] = 'diagnosis'

    # Extract mentioned products
    for product in SYNONYMS:
        if product in question_lower and any(cat in SYNONYMS[product] for cat in ['fungicide', 'herbicide', 'insecticide', 'PGR']):
            intent['product_mentioned'] = product
            break

    # Extract mentioned diseases
    disease_terms = ['dollar spot', 'brown patch', 'pythium', 'anthracnose', 'fairy ring',
                     'summer patch', 'snow mold', 'gray leaf spot', 'spring dead spot', 'rust']
    for disease in disease_terms:
        if disease in question_lower:
            intent['disease_mentioned'] = disease
            break

    # Extract mentioned weeds
    weed_terms = ['crabgrass', 'poa', 'goosegrass', 'nutsedge', 'clover', 'dandelion', 'sedge']
    for weed in weed_terms:
        if weed in question_lower:
            intent['weed_mentioned'] = weed
            break

    return intent
