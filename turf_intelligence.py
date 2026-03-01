"""
Turf Intelligence Module — Central hub for advanced turfgrass management AI features.

Provides:
- Seasonal/GDD-aware context injection
- Dynamic model routing based on query complexity
- FRAC code rotation enforcement from spray history
- Follow-up question generation
- Knowledge gap transparency
- Weather-integrated spray window assessment
- Photo-based disease diagnosis pipeline
- Cultivar-specific recommendations
- Cross-module intelligence (pulls from spray, soil, scouting, irrigation)
- Tank mix compatibility checking
- Regional disease pressure mapping
- Cost-per-application calculations
- Predictive alerts based on conditions
- Community knowledge loop (feedback → knowledge gaps)
"""

import logging
import json
import math
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 1. SEASONAL / GDD AWARENESS
# ---------------------------------------------------------------------------

# Base temperatures for GDD calculation (Fahrenheit)
GDD_BASE_TEMPS = {
    'cool_season': 32,   # Base 32°F for cool-season turf
    'warm_season': 50,   # Base 50°F for warm-season turf
    'crabgrass': 50,     # Crabgrass germination
    'poa_annua': 70,     # Poa annua germination (inverted — counts cooling degree days)
}

# Seasonal context by month (Northern Hemisphere)
SEASONAL_CONTEXT = {
    1: {'season': 'winter', 'focus': 'dormancy management, snow mold prevention, equipment maintenance', 'active_diseases': ['snow mold', 'pink snow mold'], 'key_tasks': 'Review spray programs, calibrate equipment, plan spring applications'},
    2: {'season': 'late_winter', 'focus': 'pre-season planning, pre-emergent timing approaching', 'active_diseases': ['snow mold'], 'key_tasks': 'Order chemicals, soil testing, pre-emergent timing based on forsythia bloom'},
    3: {'season': 'early_spring', 'focus': 'pre-emergent application window, green-up, initial mowing', 'active_diseases': ['snow mold recovery', 'spring dead spot'], 'key_tasks': 'Apply pre-emergents at soil temp 55°F, begin mowing, first fertilizer'},
    4: {'season': 'spring', 'focus': 'active growth begins, pre-emergent window closing, disease pressure rising', 'active_diseases': ['dollar spot', 'red thread', 'leaf spot'], 'key_tasks': 'Topdressing, aerification, PGR programs begin, fungicide preventatives'},
    5: {'season': 'late_spring', 'focus': 'peak growth, disease pressure increasing, post-emergent herbicides', 'active_diseases': ['dollar spot', 'brown patch', 'anthracnose'], 'key_tasks': 'Fungicide rotations, mowing height management, irrigation scheduling'},
    6: {'season': 'early_summer', 'focus': 'heat stress approaching, disease pressure high, insect scouting', 'active_diseases': ['dollar spot', 'brown patch', 'pythium', 'summer patch', 'anthracnose'], 'key_tasks': 'Syringing, raise mowing heights, curative sprays if needed'},
    7: {'season': 'summer', 'focus': 'peak heat stress, maximum disease pressure, water management critical', 'active_diseases': ['pythium', 'brown patch', 'summer patch', 'anthracnose', 'fairy ring'], 'key_tasks': 'Hand watering, fans on greens, avoid traffic stress, monitor closely'},
    8: {'season': 'late_summer', 'focus': 'continued heat stress, fall prep begins, overseeding planning', 'active_diseases': ['pythium', 'brown patch', 'gray leaf spot', 'summer patch'], 'key_tasks': 'Plan fall aerification, seed ordering, reduce N on bentgrass'},
    9: {'season': 'early_fall', 'focus': 'overseeding window, aerification, fall fertilization', 'active_diseases': ['dollar spot', 'brown patch', 'gray leaf spot'], 'key_tasks': 'Core aerify, overseed, fall N program, pre-emergent for Poa annua'},
    10: {'season': 'fall', 'focus': 'fall recovery, winterization prep, final fungicide applications', 'active_diseases': ['dollar spot', 'leaf spot'], 'key_tasks': 'Winterizer fertilizer, snow mold prevention spray, lower HOC gradually'},
    11: {'season': 'late_fall', 'focus': 'winterization, snow mold prevention, final mowing', 'active_diseases': ['snow mold risk building'], 'key_tasks': 'Snow mold preventative sprays, drain irrigation, store equipment'},
    12: {'season': 'winter', 'focus': 'dormancy, equipment overhaul, planning for next season', 'active_diseases': ['snow mold under cover'], 'key_tasks': 'Equipment maintenance, budget planning, education/conferences'},
}

# Turfgrass zones by state
TURFGRASS_ZONES = {
    'cool_season': ['maine', 'new hampshire', 'vermont', 'massachusetts', 'rhode island',
                    'connecticut', 'new york', 'new jersey', 'pennsylvania', 'ohio',
                    'michigan', 'indiana', 'illinois', 'wisconsin', 'minnesota',
                    'iowa', 'north dakota', 'south dakota', 'nebraska', 'montana',
                    'wyoming', 'colorado', 'idaho', 'washington', 'oregon', 'alaska'],
    'transition': ['maryland', 'delaware', 'virginia', 'west virginia', 'kentucky',
                   'tennessee', 'north carolina', 'missouri', 'kansas', 'oklahoma',
                   'arkansas', 'new mexico'],
    'warm_season': ['south carolina', 'georgia', 'florida', 'alabama', 'mississippi',
                    'louisiana', 'texas', 'arizona', 'california', 'nevada', 'hawaii', 'utah'],
}


def calculate_gdd(high_temp, low_temp, base_temp=50):
    """Calculate Growing Degree Days for a single day.

    Args:
        high_temp: Daily high temperature (°F)
        low_temp: Daily low temperature (°F)
        base_temp: Base temperature for GDD calculation (°F)

    Returns:
        GDD value for the day (minimum 0)
    """
    avg = (high_temp + low_temp) / 2.0
    return max(0, avg - base_temp)


def estimate_season_gdd(month, day=15, zone='cool_season'):
    """Estimate cumulative GDD based on date and zone.

    Uses historical averages for rough estimation when weather data
    is unavailable. Returns approximate cumulative GDD from Jan 1.

    Args:
        month: Month number (1-12)
        day: Day of month
        zone: 'cool_season', 'transition', or 'warm_season'

    Returns:
        Estimated cumulative GDD (base 50)
    """
    # Approximate monthly GDD accumulation by zone (base 50°F)
    monthly_gdd = {
        'cool_season':  [0, 0, 10, 50, 180, 350, 500, 480, 300, 120, 20, 0],
        'transition':   [0, 5, 30, 100, 280, 450, 580, 560, 380, 180, 40, 5],
        'warm_season':  [10, 20, 80, 200, 400, 550, 620, 610, 480, 280, 100, 30],
    }
    gdd_table = monthly_gdd.get(zone, monthly_gdd['cool_season'])
    cumulative = sum(gdd_table[:month - 1])
    # Add partial month
    cumulative += gdd_table[month - 1] * (day / 30.0)
    return round(cumulative)


def get_turfgrass_zone(state):
    """Determine turfgrass zone from state name.

    Args:
        state: State name (lowercase)

    Returns:
        'cool_season', 'transition', or 'warm_season'
    """
    if not state:
        return None
    state_lower = state.lower()
    for zone, states in TURFGRASS_ZONES.items():
        if state_lower in states:
            return zone
    return None


def build_seasonal_context(month=None, day=None, state=None, grass_type=None):
    """Build seasonal context string for injection into system prompt.

    Args:
        month: Month number (1-12), defaults to current
        day: Day of month, defaults to current
        state: User's state for zone detection
        grass_type: User's primary grass type

    Returns:
        Seasonal context string for prompt injection
    """
    now = datetime.now()
    month = month or now.month
    day = day or now.day

    season_info = SEASONAL_CONTEXT.get(month, SEASONAL_CONTEXT[1])
    zone = get_turfgrass_zone(state) or ('warm_season' if grass_type and
           any(g in (grass_type or '').lower() for g in ['bermuda', 'zoysia', 'paspalum', 'st augustine', 'centipede', 'bahia'])
           else 'cool_season')

    estimated_gdd = estimate_season_gdd(month, day, zone)

    parts = [
        f"--- SEASONAL CONTEXT (as of {now.strftime('%B %d, %Y')}) ---",
        f"Season: {season_info['season'].replace('_', ' ').title()}",
        f"Turfgrass Zone: {zone.replace('_', ' ').title()}",
        f"Estimated Cumulative GDD (base 50°F): ~{estimated_gdd}",
        f"Seasonal Focus: {season_info['focus']}",
        f"Active Disease Pressure: {', '.join(season_info['active_diseases'])}",
        f"Key Tasks This Period: {season_info['key_tasks']}",
    ]

    if zone == 'transition':
        parts.append("Note: Transition zone — both cool-season and warm-season turf may be present. Tailor advice to the specific grass type.")

    return '\n'.join(parts)


# ---------------------------------------------------------------------------
# 2. DYNAMIC MODEL ROUTING
# ---------------------------------------------------------------------------

# Questions that can use the cheaper mini model
SIMPLE_QUESTION_PATTERNS = [
    'what is the rate',
    'how much',
    'application rate',
    'label rate',
    'how often',
    'what frac',
    'what hrac',
    'what is the active ingredient',
    'what class',
    'signal word',
    'rei for',
    'phi for',
    'restricted entry',
    'pre-harvest interval',
    'how to calibrate',
    'what nozzle',
    'mixing order',
]

# Questions that need the full model
COMPLEX_QUESTION_PATTERNS = [
    'diagnose', 'identify', 'what is wrong', "what's wrong",
    'program', 'plan', 'strategy', 'rotation',
    'why is', 'why are', 'why does',
    'compare', 'versus', 'vs',
    'best approach', 'should i',
    'differential', 'distinguish',
    'resistance management',
    'integrated pest management',
    'cultural practices for',
    'long-term', 'season-long',
    'explain', 'how does it work',
]


def select_model(question, intent=None, source_count=0):
    """Select the appropriate model based on query complexity.

    Args:
        question: User question text
        intent: Query intent dict from get_query_intent()
        source_count: Number of sources found (more sources = simpler answer)

    Returns:
        Dict with model selection:
        - model: model identifier string
        - reason: why this model was selected
        - max_tokens: appropriate token limit
        - temperature: appropriate temperature
    """
    q_lower = question.lower()

    # Always use full model for photo/image questions
    if any(kw in q_lower for kw in ['photo', 'image', 'picture', 'diagnose from']):
        return {
            'model': 'gpt-4o',
            'reason': 'image_diagnosis',
            'max_tokens': 1500,
            'temperature': 0.2,
        }

    # Check for simple patterns
    is_simple = any(p in q_lower for p in SIMPLE_QUESTION_PATTERNS)
    is_complex = any(p in q_lower for p in COMPLEX_QUESTION_PATTERNS)

    # Short questions with clear intent tend to be simple
    word_count = len(question.split())
    if word_count <= 8 and not is_complex:
        is_simple = True

    # Intent-based routing
    if intent:
        if intent.get('wants_rate') and not intent.get('wants_diagnosis'):
            is_simple = True
        if intent.get('wants_diagnosis'):
            is_complex = True

    if is_complex and not is_simple:
        return {
            'model': 'gpt-4o',
            'reason': 'complex_query',
            'max_tokens': 1500,
            'temperature': 0.2,
        }

    if is_simple and not is_complex:
        return {
            'model': 'gpt-4o-mini',
            'reason': 'simple_lookup',
            'max_tokens': 800,
            'temperature': 0.15,
        }

    # Default to full model for ambiguous cases
    return {
        'model': 'gpt-4o',
        'reason': 'default',
        'max_tokens': 1500,
        'temperature': 0.2,
    }


# ---------------------------------------------------------------------------
# 3. FRAC CODE ROTATION ENFORCEMENT
# ---------------------------------------------------------------------------

# FRAC code to product mapping
FRAC_CODE_MAP = {
    'FRAC1': {'group': 'MBC (Benzimidazoles)', 'products': ['cleary 3336', 'tersan'], 'resistance_risk': 'high'},
    'FRAC3': {'group': 'DMI (Triazoles)', 'products': ['banner maxx', 'bayleton', 'tourney', 'maxtima', 'propiconazole', 'myclobutanil'], 'resistance_risk': 'medium'},
    'FRAC7': {'group': 'SDHI (Carboxamides)', 'products': ['xzemplar', 'velista', 'posterity', 'lexicon', 'briskway'], 'resistance_risk': 'medium-high'},
    'FRAC11': {'group': 'QoI (Strobilurins)', 'products': ['heritage', 'insignia', 'headway', 'compass', 'disarm'], 'resistance_risk': 'high'},
    'FRAC12': {'group': 'Phenylpyrroles', 'products': ['medallion'], 'resistance_risk': 'low-medium'},
    'FRACM3': {'group': 'Dithiocarbamates', 'products': ['fore', 'mancozeb'], 'resistance_risk': 'low'},
    'FRACM5': {'group': 'Chloronitriles', 'products': ['daconil', 'chlorothalonil'], 'resistance_risk': 'low'},
    'FRAC29': {'group': 'Quinolines', 'products': ['secure', 'fluazinam'], 'resistance_risk': 'low'},
    'FRAC21': {'group': 'Quinone inhibitors', 'products': ['segway'], 'resistance_risk': 'medium'},
    'FRAC4': {'group': 'Phenylamides', 'products': ['subdue', 'metalaxyl'], 'resistance_risk': 'high'},
    'FRAC14': {'group': 'Lipid synthesis inhibitors', 'products': ['banol'], 'resistance_risk': 'low-medium'},
    'FRAC19': {'group': 'Polyoxins', 'products': ['endorse'], 'resistance_risk': 'medium'},
}

# Reverse lookup: product -> FRAC code
PRODUCT_TO_FRAC = {}
for code, info in FRAC_CODE_MAP.items():
    for product in info['products']:
        PRODUCT_TO_FRAC[product.lower()] = code


def get_frac_code(product_name):
    """Get FRAC code for a product.

    Args:
        product_name: Product name to look up

    Returns:
        FRAC code string or None
    """
    return PRODUCT_TO_FRAC.get(product_name.lower().strip())


def check_frac_rotation(user_id, proposed_product=None, area=None, days_back=60):
    """Check spray history for FRAC code rotation compliance.

    Args:
        user_id: User ID to check history for
        proposed_product: Product being considered (optional)
        area: Course area to check (optional, e.g. 'greens')
        days_back: How many days back to check

    Returns:
        Dict with rotation analysis:
        - compliant: bool
        - recent_frac_codes: list of recently used FRAC codes
        - warning: str or None
        - suggestion: str or None
    """
    try:
        from db import get_db
        cutoff = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')

        with get_db() as conn:
            query = '''SELECT product_name, date, area FROM spray_applications
                       WHERE user_id = ? AND date >= ?'''
            params = [user_id, cutoff]
            if area:
                query += ' AND LOWER(area) = ?'
                params.append(area.lower())
            query += ' ORDER BY date DESC LIMIT 20'

            rows = conn.execute(query, params).fetchall()

        recent_frac = []
        for row in rows:
            product = row['product_name'] if isinstance(row, dict) else row[0]
            frac = get_frac_code(product)
            if frac:
                recent_frac.append({
                    'product': product,
                    'frac': frac,
                    'date': row['date'] if isinstance(row, dict) else row[1],
                    'area': row['area'] if isinstance(row, dict) else row[2],
                })

        result = {
            'compliant': True,
            'recent_frac_codes': recent_frac,
            'warning': None,
            'suggestion': None,
        }

        if proposed_product:
            proposed_frac = get_frac_code(proposed_product)
            if proposed_frac and recent_frac:
                # Check consecutive same-FRAC usage
                consecutive_same = sum(1 for r in recent_frac[:3] if r['frac'] == proposed_frac)
                if consecutive_same >= 2:
                    frac_info = FRAC_CODE_MAP.get(proposed_frac, {})
                    result['compliant'] = False
                    result['warning'] = (
                        f"Resistance risk: {proposed_product.title()} ({proposed_frac} — {frac_info.get('group', 'unknown')}) "
                        f"has been used {consecutive_same} times in the last {days_back} days. "
                        f"Resistance risk for this group: {frac_info.get('resistance_risk', 'unknown')}."
                    )
                    # Suggest alternatives from different FRAC groups
                    used_codes = {r['frac'] for r in recent_frac[:3]}
                    alternatives = []
                    for code, info in FRAC_CODE_MAP.items():
                        if code not in used_codes:
                            alternatives.extend(info['products'][:2])
                    if alternatives:
                        result['suggestion'] = f"Consider rotating to a different mode of action: {', '.join(alt.title() for alt in alternatives[:4])}"

        return result
    except Exception as e:
        logger.warning(f"FRAC rotation check failed: {e}")
        return {
            'compliant': True,
            'recent_frac_codes': [],
            'warning': None,
            'suggestion': None,
        }


def build_frac_rotation_context(user_id, question, area=None):
    """Build FRAC rotation context for injection into prompts.

    Args:
        user_id: User ID
        question: User question (to detect product mentions)
        area: Course area

    Returns:
        Context string about rotation status, or empty string
    """
    # Detect products mentioned in question
    q_lower = question.lower()
    mentioned_product = None
    for product in PRODUCT_TO_FRAC:
        if product in q_lower:
            mentioned_product = product
            break

    rotation = check_frac_rotation(user_id, mentioned_product, area)
    if not rotation['recent_frac_codes']:
        return ''

    parts = ['--- SPRAY HISTORY & RESISTANCE MANAGEMENT ---']
    parts.append(f"Recent fungicide applications (last 60 days):")
    for entry in rotation['recent_frac_codes'][:5]:
        parts.append(f"  - {entry['product'].title()} ({entry['frac']}) on {entry['date']} [{entry['area']}]")

    if rotation['warning']:
        parts.append(f"\n⚠️ ROTATION WARNING: {rotation['warning']}")
    if rotation['suggestion']:
        parts.append(f"💡 SUGGESTION: {rotation['suggestion']}")

    return '\n'.join(parts)


# ---------------------------------------------------------------------------
# 4. FOLLOW-UP QUESTION GENERATION
# ---------------------------------------------------------------------------

FOLLOW_UP_TEMPLATES = {
    'disease': [
        "What cultural practices help prevent {subject}?",
        "What's the best FRAC rotation for {subject} control?",
        "What cultivars are resistant to {subject}?",
    ],
    'chemical': [
        "What's the tank mix compatibility for {subject}?",
        "What are the REI and PHI for {subject}?",
        "What's the cost per acre for {subject}?",
    ],
    'rate': [
        "Is {subject} safe on my turf type?",
        "What's the best timing for {subject} application?",
        "Can I tank mix {subject} with other products?",
    ],
    'cultural': [
        "When is the best time to {subject} based on GDD?",
        "How does {subject} affect disease pressure?",
        "What equipment settings for {subject}?",
    ],
    'diagnosis': [
        "What products treat this condition?",
        "What cultural practices help prevent this?",
        "Could this be caused by environmental stress instead?",
    ],
    'general': [
        "What products do you recommend for this?",
        "What are the best cultural practices?",
        "How does timing affect this recommendation?",
    ],
}


def generate_follow_up_suggestions(question, answer, intent=None, disease=None, product=None):
    """Generate contextual follow-up question suggestions.

    Args:
        question: Original user question
        answer: AI-generated answer
        intent: Query intent dict
        disease: Detected disease name
        product: Detected product name

    Returns:
        List of 2-3 follow-up question strings
    """
    suggestions = []
    intent_type = (intent or {}).get('type', 'general')

    # Get subject for template filling
    subject = product or disease or ''

    # Get templates for this intent type
    templates = FOLLOW_UP_TEMPLATES.get(intent_type, FOLLOW_UP_TEMPLATES['general'])

    for template in templates:
        if subject:
            suggestion = template.format(subject=subject.title())
        else:
            suggestion = template.format(subject='this')

        # Don't suggest questions similar to what was already asked
        if suggestion.lower() not in question.lower():
            suggestions.append(suggestion)

    # Add cost question if product mentioned
    if product and intent_type != 'rate':
        suggestions.append(f"What's the cost per acre for {product.title()}?")

    # Add resistance question for fungicide topics
    if intent_type in ('disease', 'chemical') and disease:
        suggestions.append(f"Is there known resistance to common fungicides for {disease.title()}?")

    return suggestions[:3]


# ---------------------------------------------------------------------------
# 5. KNOWLEDGE GAP TRANSPARENCY
# ---------------------------------------------------------------------------

def assess_knowledge_gaps(sources, confidence, question, context=''):
    """Assess whether the system has adequate knowledge to answer.

    Args:
        sources: List of source dicts from search
        confidence: Confidence score (0-100)
        question: Original question
        context: Built context string

    Returns:
        Dict with gap assessment:
        - has_gaps: bool
        - message: str to show user (or None)
        - severity: 'none', 'minor', 'major'
    """
    result = {
        'has_gaps': False,
        'message': None,
        'severity': 'none',
    }

    # No sources found
    if not sources or len(sources) == 0:
        result['has_gaps'] = True
        result['severity'] = 'major'
        result['message'] = (
            "I have limited data on this topic in my knowledge base. "
            "My response is based on general turfgrass science knowledge. "
            "Please verify recommendations with your local university extension office or product labels."
        )
        return result

    # Very low confidence
    if confidence < 45:
        result['has_gaps'] = True
        result['severity'] = 'major'
        result['message'] = (
            "I found some relevant information but my confidence is low. "
            "Please verify these recommendations against product labels and local extension guidelines."
        )
        return result

    # Few sources
    if len(sources) <= 2 and confidence < 65:
        result['has_gaps'] = True
        result['severity'] = 'minor'
        result['message'] = (
            "I found limited sources on this specific topic. "
            "The information provided should be verified against current product labels."
        )
        return result

    # Context too short relative to question complexity
    word_count = len(question.split())
    if word_count > 15 and len(context) < 500:
        result['has_gaps'] = True
        result['severity'] = 'minor'
        result['message'] = (
            "This is a complex question and my available sources may not cover all aspects. "
            "Consider consulting with your local agronomist for a comprehensive plan."
        )
        return result

    return result


# ---------------------------------------------------------------------------
# 6. WEATHER-INTEGRATED SPRAY WINDOWS
# ---------------------------------------------------------------------------

def assess_spray_window(weather_data):
    """Assess spray window quality based on weather conditions.

    Args:
        weather_data: Dict with weather info:
            - temp: temperature (°F)
            - wind_speed: wind speed (mph)
            - humidity: relative humidity (%)
            - rain_chance: precipitation probability (0-100)
            - conditions: text description

    Returns:
        Dict with spray window assessment:
        - quality: 'good', 'marginal', 'poor'
        - reasons: list of reasons
        - recommendations: list of actionable recommendations
        - phytotoxicity_risk: bool
    """
    if not weather_data:
        return {'quality': 'unknown', 'reasons': ['No weather data available'], 'recommendations': [], 'phytotoxicity_risk': False}

    temp = weather_data.get('temp', 75)
    wind = weather_data.get('wind_speed', 5)
    humidity = weather_data.get('humidity', 50)
    rain_chance = weather_data.get('rain_chance', 0)

    quality = 'good'
    reasons = []
    recommendations = []
    phyto_risk = False

    # Wind assessment
    if wind > 15:
        quality = 'poor'
        reasons.append(f'Wind speed {wind} mph exceeds 15 mph — significant drift risk')
        recommendations.append('Wait for wind to drop below 10 mph')
    elif wind > 10:
        if quality != 'poor':
            quality = 'marginal'
        reasons.append(f'Wind speed {wind} mph is moderate — some drift risk')
        recommendations.append('Use coarser nozzles and lower boom height')

    # Rain assessment
    if rain_chance > 60:
        quality = 'poor'
        reasons.append(f'Rain probability {rain_chance}% — product may wash off before absorption')
        recommendations.append('Delay application until rain passes. Most foliar products need 1-2 hours drying time.')
    elif rain_chance > 30:
        if quality != 'poor':
            quality = 'marginal'
        reasons.append(f'Rain probability {rain_chance}% — monitor forecast closely')
        recommendations.append('Apply early in the day to maximize drying time before rain')

    # Temperature assessment
    if temp > 90:
        phyto_risk = True
        if quality != 'poor':
            quality = 'marginal'
        reasons.append(f'Temperature {temp}°F exceeds 90°F — phytotoxicity risk')
        recommendations.append('Avoid DMI fungicides and chlorothalonil above 85°F. Consider early morning application (before 9 AM).')
    elif temp > 85:
        phyto_risk = True
        reasons.append(f'Temperature {temp}°F is elevated — monitor for phytotoxicity')
        recommendations.append('Avoid tank mixing DMI + contact fungicides in high heat')
    elif temp < 50:
        reasons.append(f'Temperature {temp}°F is low — reduced product efficacy for some systemic products')
        recommendations.append('Systemic fungicides require active growth for uptake. Consider contact options.')

    # Humidity assessment
    if humidity > 90 and temp > 75:
        reasons.append(f'High humidity ({humidity}%) + warm temps favor disease development')
        recommendations.append('Monitor closely for pythium and brown patch after application')

    if quality == 'good':
        reasons.append('Conditions are favorable for spray application')

    return {
        'quality': quality,
        'reasons': reasons,
        'recommendations': recommendations,
        'phytotoxicity_risk': phyto_risk,
    }


def build_weather_spray_context(weather_data):
    """Build weather/spray context for prompt injection.

    Args:
        weather_data: Weather data dict

    Returns:
        Context string about spray conditions
    """
    assessment = assess_spray_window(weather_data)
    if assessment['quality'] == 'unknown':
        return ''

    parts = ['--- CURRENT SPRAY CONDITIONS ---']
    parts.append(f"Spray Window Quality: {assessment['quality'].upper()}")
    for reason in assessment['reasons']:
        parts.append(f"  • {reason}")
    if assessment['phytotoxicity_risk']:
        parts.append("⚠️ PHYTOTOXICITY RISK: High temperatures — avoid DMI + chlorothalonil combinations")
    if assessment['recommendations']:
        parts.append("Recommendations:")
        for rec in assessment['recommendations']:
            parts.append(f"  → {rec}")
    return '\n'.join(parts)


# ---------------------------------------------------------------------------
# 7. PHOTO-BASED DISEASE DIAGNOSIS
# ---------------------------------------------------------------------------

DIAGNOSTIC_FEATURES = {
    'dollar_spot': {
        'visual': 'Small, silver-dollar sized tan spots; hourglass lesions on leaf blades; cobweb-like mycelium in morning dew',
        'conditions': 'Night temps >60°F, humidity >90%, low nitrogen, drought stress',
        'distinguishing': 'Hourglass-shaped lesion with tan center and reddish-brown border is diagnostic',
    },
    'brown_patch': {
        'visual': 'Circular patches 6 inches to several feet; smoke ring border (gray/dark) in early morning; leaves easily pulled from sheath',
        'conditions': 'Night temps >68°F, humidity >95%, excessive nitrogen, poor air circulation',
        'distinguishing': 'Smoke ring visible in early morning, leaves pull easily from sheath but roots are intact',
    },
    'pythium_blight': {
        'visual': 'Greasy, dark, water-soaked spots; cottony white mycelium; irregular streaks following drainage',
        'conditions': 'Night temps >68°F, daytime >86°F, humidity near 100%, poor drainage',
        'distinguishing': 'Cottony white mycelium visible in early morning; affected areas feel greasy',
    },
    'anthracnose': {
        'visual': 'Yellowing in irregular patches; basal rot (dark stem base); thinning canopy; black acervuli (fruiting bodies) visible with hand lens',
        'conditions': 'Heat stress + drought + low fertility + low mowing height',
        'distinguishing': 'Black fruiting bodies (acervuli) on stems visible at 10x; basal rot at crown',
    },
    'summer_patch': {
        'visual': 'Circular to ring-shaped patches; bronze/tan color; frog-eye pattern with green center',
        'conditions': 'Soil temps >65°F, compacted soils, excessive thatch, low pH',
        'distinguishing': 'Frog-eye rings with green grass in center; root system destroyed',
    },
    'fairy_ring': {
        'visual': 'Dark green rings or arcs; mushrooms may be present; hydrophobic soil in ring zone',
        'conditions': 'Organic matter decomposition, thatch, buried debris',
        'distinguishing': 'Distinct ring pattern; soil in ring may be hydrophobic (repels water)',
    },
    'gray_leaf_spot': {
        'visual': 'Diamond/oval shaped lesions on leaf blades; gray center with dark brown border; twisted/distorted leaf tips',
        'conditions': 'Temps >80°F, high humidity, excessive nitrogen, new seedings especially vulnerable',
        'distinguishing': 'Leaf lesions diamond/oval shaped; twisted leaf tips; primarily on perennial ryegrass',
    },
    'leaf_spot': {
        'visual': 'Purple-black spots/lesions on leaves; progresses to melting out (crown/root rot); thin/dead patches',
        'conditions': 'Cool, wet weather (spring/fall); low mowing; shade',
        'distinguishing': 'Dark purple lesions on individual leaves in early stage; melting out phase affects entire plant',
    },
}


def build_diagnostic_context(symptoms=None, grass_type=None, conditions=None):
    """Build diagnostic reference context for photo-based diagnosis.

    Args:
        symptoms: Described symptoms
        grass_type: Turf species
        conditions: Current weather/management conditions

    Returns:
        Diagnostic reference string for prompt injection
    """
    parts = ['--- DIAGNOSTIC REFERENCE ---']
    parts.append('Use the following visual reference to aid diagnosis:')
    parts.append('')

    for disease, info in DIAGNOSTIC_FEATURES.items():
        display_name = disease.replace('_', ' ').title()
        parts.append(f"**{display_name}**")
        parts.append(f"  Visual: {info['visual']}")
        parts.append(f"  Conditions: {info['conditions']}")
        parts.append(f"  Key Diagnostic: {info['distinguishing']}")
        parts.append('')

    parts.append("DIAGNOSTIC APPROACH:")
    parts.append("1. Describe the pattern (circular, irregular, streaks, individual plants)")
    parts.append("2. Note the color and lesion characteristics")
    parts.append("3. Consider recent weather conditions")
    parts.append("4. Provide differential diagnosis with confidence levels")
    parts.append("5. Recommend confirmation method (lab test, hand lens, pull test)")

    return '\n'.join(parts)


# ---------------------------------------------------------------------------
# 8. CULTIVAR-SPECIFIC RECOMMENDATIONS
# ---------------------------------------------------------------------------

CULTIVAR_DISEASE_SUSCEPTIBILITY = {
    'bentgrass': {
        'Penncross': {'dollar_spot': 'high', 'anthracnose': 'moderate', 'brown_patch': 'moderate'},
        'A-4': {'dollar_spot': 'low', 'anthracnose': 'moderate', 'brown_patch': 'low'},
        'Declaration': {'dollar_spot': 'low', 'anthracnose': 'low', 'brown_patch': 'low'},
        'Tyee': {'dollar_spot': 'low', 'anthracnose': 'moderate', 'brown_patch': 'low'},
        'T-1': {'dollar_spot': 'moderate', 'anthracnose': 'moderate', 'brown_patch': 'low'},
        '007': {'dollar_spot': 'low', 'anthracnose': 'low', 'brown_patch': 'moderate'},
        'Memorial': {'dollar_spot': 'low', 'anthracnose': 'low', 'brown_patch': 'low'},
        'Pure Distinction': {'dollar_spot': 'low', 'anthracnose': 'moderate', 'brown_patch': 'low'},
    },
    'bermudagrass': {
        'TifEagle': {'spring_dead_spot': 'moderate', 'dollar_spot': 'moderate', 'large_patch': 'moderate'},
        'Champion': {'spring_dead_spot': 'high', 'dollar_spot': 'low', 'large_patch': 'moderate'},
        'MiniVerde': {'spring_dead_spot': 'low', 'dollar_spot': 'low', 'large_patch': 'low'},
        'Tifway 419': {'spring_dead_spot': 'moderate', 'large_patch': 'moderate', 'dollar_spot': 'moderate'},
        'Latitude 36': {'spring_dead_spot': 'low', 'large_patch': 'low', 'cold_tolerance': 'excellent'},
        'NorthBridge': {'spring_dead_spot': 'low', 'large_patch': 'low', 'cold_tolerance': 'excellent'},
    },
    'bluegrass': {
        'Midnight': {'dollar_spot': 'moderate', 'summer_patch': 'low', 'leaf_spot': 'low'},
        'Award': {'dollar_spot': 'moderate', 'summer_patch': 'moderate', 'leaf_spot': 'low'},
        'Bewitched': {'dollar_spot': 'low', 'summer_patch': 'low', 'leaf_spot': 'low'},
    },
}


def get_cultivar_context(grass_type, cultivar=None, disease=None):
    """Get cultivar-specific disease susceptibility context.

    Args:
        grass_type: General grass type (e.g. 'bentgrass')
        cultivar: Specific cultivar name (e.g. 'Penncross')
        disease: Disease being asked about

    Returns:
        Context string about cultivar susceptibility, or empty string
    """
    if not grass_type:
        return ''

    grass_key = None
    for key in CULTIVAR_DISEASE_SUSCEPTIBILITY:
        if key in grass_type.lower():
            grass_key = key
            break

    if not grass_key:
        return ''

    cultivars = CULTIVAR_DISEASE_SUSCEPTIBILITY[grass_key]

    parts = [f'--- CULTIVAR DISEASE SUSCEPTIBILITY ({grass_key.title()}) ---']

    if cultivar:
        # Show specific cultivar info
        cultivar_info = None
        for cv_name, info in cultivars.items():
            if cv_name.lower() == cultivar.lower():
                cultivar_info = info
                parts.append(f"Your cultivar: {cv_name}")
                for d, level in info.items():
                    parts.append(f"  {d.replace('_', ' ').title()}: {level} susceptibility")
                break

        if not cultivar_info:
            parts.append(f"Cultivar '{cultivar}' not in database. Showing general {grass_key} info.")
            cultivar = None

    if not cultivar:
        # Show comparison table
        if disease:
            disease_key = disease.lower().replace(' ', '_')
            parts.append(f"Cultivar resistance to {disease.title()}:")
            for cv_name, info in cultivars.items():
                level = info.get(disease_key, 'unknown')
                parts.append(f"  {cv_name}: {level}")
        else:
            for cv_name, info in list(cultivars.items())[:5]:
                diseases_str = ', '.join(f"{d.replace('_', ' ')}: {l}" for d, l in list(info.items())[:3])
                parts.append(f"  {cv_name}: {diseases_str}")

    return '\n'.join(parts)


# ---------------------------------------------------------------------------
# 9. CROSS-MODULE INTELLIGENCE
# ---------------------------------------------------------------------------

def build_cross_module_context(user_id, question, area=None):
    """Pull data from all feature modules to enrich AI context.

    Assembles relevant data from spray history, soil tests, scouting reports,
    and irrigation data based on the question being asked.

    Args:
        user_id: User ID
        question: User question (to determine what data is relevant)
        area: Course area filter (optional)

    Returns:
        Context string with cross-module data, or empty string
    """
    if not user_id:
        return ''

    parts = []
    q_lower = question.lower()

    try:
        from db import get_db

        with get_db() as conn:
            # Recent spray applications (last 90 days)
            if any(kw in q_lower for kw in ['spray', 'fungicide', 'herbicide', 'product', 'apply',
                                             'rotation', 'frac', 'what should i use', 'control',
                                             'disease', 'weed', 'treat']):
                cutoff = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
                sprays = conn.execute(
                    '''SELECT product_name, date, area, rate, rate_unit
                       FROM spray_applications
                       WHERE user_id = ? AND date >= ?
                       ORDER BY date DESC LIMIT 10''',
                    (user_id, cutoff)
                ).fetchall()
                if sprays:
                    parts.append('--- YOUR RECENT SPRAY HISTORY (last 90 days) ---')
                    for s in sprays:
                        name = s['product_name'] if isinstance(s, dict) else s[0]
                        date = s['date'] if isinstance(s, dict) else s[1]
                        s_area = s['area'] if isinstance(s, dict) else s[2]
                        rate = s['rate'] if isinstance(s, dict) else s[3]
                        unit = s['rate_unit'] if isinstance(s, dict) else s[4]
                        parts.append(f"  {date}: {name} at {rate} {unit} on {s_area}")

            # Recent soil tests
            if any(kw in q_lower for kw in ['soil', 'ph', 'nutrient', 'fertiliz', 'nitrogen',
                                             'potassium', 'phosphor', 'lime', 'amendment']):
                try:
                    from soil_testing import get_soil_tests
                    tests = get_soil_tests(user_id)
                    if tests:
                        parts.append('--- YOUR RECENT SOIL TESTS ---')
                        for t in tests[:3]:
                            t_area = t.get('area', 'unknown')
                            t_date = t.get('date', 'unknown')
                            ph_val = t.get('ph', 'N/A')
                            om = t.get('organic_matter', 'N/A')
                            parts.append(f"  {t_date} ({t_area}): pH={ph_val}, OM={om}%")
                except Exception:
                    pass

            # Active scouting issues
            if any(kw in q_lower for kw in ['diagnose', 'issue', 'problem', 'disease', 'pest',
                                             'weed', 'damage', 'scout', 'identify']):
                try:
                    from scouting_log import get_open_issues
                    issues = get_open_issues(user_id)
                    if issues:
                        parts.append('--- YOUR ACTIVE SCOUTING ISSUES ---')
                        for issue in issues[:5]:
                            i_type = issue.get('issue_type', 'unknown')
                            i_area = issue.get('area', 'unknown')
                            severity = issue.get('severity', 'unknown')
                            diagnosis = issue.get('diagnosis', 'undiagnosed')
                            parts.append(f"  {i_type} on {i_area}: {diagnosis} (severity: {severity}/5)")
                except Exception:
                    pass

            # Nutrient budget tracking
            if any(kw in q_lower for kw in ['nitrogen', 'fertiliz', 'nutrient', 'n budget',
                                             'how much n', 'fertilizer program']):
                try:
                    year = datetime.now().year
                    nutrients = conn.execute(
                        '''SELECT area,
                           SUM(CAST(json_extract(nutrients_applied, '$.n_per_1000') AS REAL)) as total_n
                           FROM spray_applications
                           WHERE user_id = ? AND date >= ? AND nutrients_applied IS NOT NULL
                           GROUP BY area''',
                        (user_id, f'{year}-01-01')
                    ).fetchall()
                    if nutrients:
                        parts.append(f'--- YOUR {year} NITROGEN APPLIED ---')
                        for n in nutrients:
                            n_area = n['area'] if isinstance(n, dict) else n[0]
                            total_n = n['total_n'] if isinstance(n, dict) else n[1]
                            if total_n:
                                parts.append(f"  {n_area}: {total_n:.2f} lbs N / 1000 sq ft applied YTD")
                except Exception:
                    pass

    except Exception as e:
        logger.warning(f"Cross-module context build failed: {e}")

    return '\n'.join(parts)


# ---------------------------------------------------------------------------
# 10. TANK MIX COMPATIBILITY
# ---------------------------------------------------------------------------

# Compatibility matrix: (product_a, product_b) -> 'compatible', 'caution', 'incompatible'
TANK_MIX_COMPATIBILITY = {
    # Compatible pairs
    ('heritage', 'daconil'): {'status': 'compatible', 'notes': 'Common preventative combination'},
    ('heritage', 'primo'): {'status': 'compatible', 'notes': 'Fungicide + PGR is standard practice'},
    ('banner maxx', 'daconil'): {'status': 'caution', 'notes': 'Avoid above 85°F — phytotoxicity risk with DMI + contact in heat'},
    ('headway', 'primo'): {'status': 'compatible', 'notes': 'Standard combination for greens'},
    ('medallion', 'daconil'): {'status': 'compatible', 'notes': 'Good rotation combination'},
    ('xzemplar', 'daconil'): {'status': 'compatible', 'notes': 'SDHI + contact — good resistance management'},
    ('velista', 'daconil'): {'status': 'compatible', 'notes': 'SDHI + contact combination'},
    ('posterity', 'daconil'): {'status': 'compatible', 'notes': 'SDHI + contact combination'},
    ('subdue', 'daconil'): {'status': 'compatible', 'notes': 'Pythium + broad-spectrum combination'},
    ('primo', 'iron'): {'status': 'compatible', 'notes': 'PGR + iron for color without growth'},
    ('tenacity', 'barricade'): {'status': 'caution', 'notes': 'Check label for timing restrictions on new seedings'},
    ('prodiamine', 'dimension'): {'status': 'incompatible', 'notes': 'Do not combine two pre-emergents — redundant and may cause phytotoxicity'},
    ('specticle', 'barricade'): {'status': 'incompatible', 'notes': 'Do not combine two pre-emergents'},
    # High-heat warnings
    ('banner maxx', 'heritage'): {'status': 'caution', 'notes': 'DMI + strobilurin may increase phytotoxicity risk above 85°F'},
    ('tourney', 'daconil'): {'status': 'caution', 'notes': 'DMI + chlorothalonil — avoid in extreme heat (>90°F)'},
}


def check_tank_mix_compatibility(products):
    """Check compatibility of multiple products in a tank mix.

    Args:
        products: List of product name strings

    Returns:
        Dict with compatibility assessment:
        - overall: 'compatible', 'caution', 'incompatible'
        - details: list of compatibility notes
        - warnings: list of warning strings
    """
    if not products or len(products) < 2:
        return {'overall': 'compatible', 'details': [], 'warnings': []}

    products_lower = [p.lower().strip() for p in products]
    overall = 'compatible'
    details = []
    warnings = []

    # Check each pair
    for i in range(len(products_lower)):
        for j in range(i + 1, len(products_lower)):
            pair = (products_lower[i], products_lower[j])
            pair_rev = (products_lower[j], products_lower[i])

            compat = TANK_MIX_COMPATIBILITY.get(pair) or TANK_MIX_COMPATIBILITY.get(pair_rev)

            if compat:
                status = compat['status']
                details.append({
                    'products': f"{products[i]} + {products[j]}",
                    'status': status,
                    'notes': compat['notes'],
                })
                if status == 'incompatible':
                    overall = 'incompatible'
                    warnings.append(f"⚠️ {products[i]} + {products[j]}: {compat['notes']}")
                elif status == 'caution' and overall != 'incompatible':
                    overall = 'caution'
                    warnings.append(f"⚡ {products[i]} + {products[j]}: {compat['notes']}")
            else:
                details.append({
                    'products': f"{products[i]} + {products[j]}",
                    'status': 'unknown',
                    'notes': 'No compatibility data available — check product labels',
                })

    # General tank mix rules
    if len(products_lower) > 3:
        warnings.append("Mixing more than 3 products increases compatibility risk — always do a jar test first")

    return {'overall': overall, 'details': details, 'warnings': warnings}


# ---------------------------------------------------------------------------
# 11. REGIONAL DISEASE PRESSURE
# ---------------------------------------------------------------------------

REGIONAL_DISEASE_CALENDAR = {
    'cool_season': {
        'spring': ['dollar spot', 'red thread', 'leaf spot', 'necrotic ring spot'],
        'summer': ['dollar spot', 'brown patch', 'pythium', 'summer patch', 'anthracnose'],
        'fall': ['dollar spot', 'leaf spot', 'red thread', 'gray leaf spot'],
        'winter': ['snow mold', 'pink snow mold'],
    },
    'warm_season': {
        'spring': ['spring dead spot', 'large patch', 'dollar spot'],
        'summer': ['dollar spot', 'pythium', 'brown patch', 'fairy ring', 'gray leaf spot'],
        'fall': ['large patch', 'dollar spot', 'helminthosporium'],
        'winter': ['large patch (dormancy transition)', 'spring dead spot (prevention window)'],
    },
    'transition': {
        'spring': ['dollar spot', 'spring dead spot', 'leaf spot', 'brown patch'],
        'summer': ['dollar spot', 'brown patch', 'pythium', 'summer patch', 'anthracnose', 'gray leaf spot'],
        'fall': ['dollar spot', 'large patch', 'leaf spot', 'brown patch'],
        'winter': ['snow mold (cool-season)', 'large patch (warm-season)'],
    },
}


def get_regional_disease_pressure(state=None, month=None, zone=None):
    """Get expected disease pressure for a region and time.

    Args:
        state: US state name
        month: Month number (1-12)
        zone: Turfgrass zone override

    Returns:
        Dict with disease pressure info:
        - zone: turfgrass zone
        - season: current season name
        - active_diseases: list of likely active diseases
        - high_risk: list of highest-risk diseases
    """
    if not zone and state:
        zone = get_turfgrass_zone(state)
    zone = zone or 'cool_season'
    month = month or datetime.now().month

    # Map month to season
    if month in (3, 4, 5):
        season = 'spring'
    elif month in (6, 7, 8):
        season = 'summer'
    elif month in (9, 10, 11):
        season = 'fall'
    else:
        season = 'winter'

    diseases = REGIONAL_DISEASE_CALENDAR.get(zone, {}).get(season, [])

    # First 2-3 diseases in the list are highest risk
    high_risk = diseases[:3] if len(diseases) >= 3 else diseases

    return {
        'zone': zone,
        'season': season,
        'active_diseases': diseases,
        'high_risk': high_risk,
    }


# ---------------------------------------------------------------------------
# 12. COST PER APPLICATION
# ---------------------------------------------------------------------------

# Approximate product costs (USD per unit) — representative pricing
PRODUCT_COSTS = {
    'heritage': {'cost_per_unit': 180.0, 'unit': 'lb', 'rate_per_1000': 0.4, 'rate_unit': 'oz'},
    'daconil': {'cost_per_unit': 55.0, 'unit': 'gal', 'rate_per_1000': 3.6, 'rate_unit': 'fl oz'},
    'banner maxx': {'cost_per_unit': 190.0, 'unit': 'gal', 'rate_per_1000': 2.0, 'rate_unit': 'fl oz'},
    'medallion': {'cost_per_unit': 280.0, 'unit': 'lb', 'rate_per_1000': 0.25, 'rate_unit': 'oz'},
    'xzemplar': {'cost_per_unit': 340.0, 'unit': 'gal', 'rate_per_1000': 0.26, 'rate_unit': 'fl oz'},
    'posterity': {'cost_per_unit': 360.0, 'unit': 'gal', 'rate_per_1000': 0.35, 'rate_unit': 'fl oz'},
    'velista': {'cost_per_unit': 195.0, 'unit': 'lb', 'rate_per_1000': 0.3, 'rate_unit': 'oz'},
    'briskway': {'cost_per_unit': 260.0, 'unit': 'gal', 'rate_per_1000': 0.7, 'rate_unit': 'fl oz'},
    'headway': {'cost_per_unit': 320.0, 'unit': 'gal', 'rate_per_1000': 3.0, 'rate_unit': 'fl oz'},
    'primo': {'cost_per_unit': 230.0, 'unit': 'gal', 'rate_per_1000': 0.5, 'rate_unit': 'fl oz'},
    'tourney': {'cost_per_unit': 240.0, 'unit': 'lb', 'rate_per_1000': 0.28, 'rate_unit': 'oz'},
    'subdue': {'cost_per_unit': 190.0, 'unit': 'gal', 'rate_per_1000': 2.0, 'rate_unit': 'fl oz'},
    'acelepryn': {'cost_per_unit': 450.0, 'unit': 'gal', 'rate_per_1000': 0.46, 'rate_unit': 'fl oz'},
    'tenacity': {'cost_per_unit': 90.0, 'unit': 'gal', 'rate_per_1000': 0.18, 'rate_unit': 'fl oz'},
    'specticle': {'cost_per_unit': 400.0, 'unit': 'gal', 'rate_per_1000': 0.12, 'rate_unit': 'fl oz'},
    'barricade': {'cost_per_unit': 75.0, 'unit': 'gal', 'rate_per_1000': 1.5, 'rate_unit': 'fl oz'},
    'secure': {'cost_per_unit': 170.0, 'unit': 'gal', 'rate_per_1000': 0.5, 'rate_unit': 'fl oz'},
    'lexicon': {'cost_per_unit': 350.0, 'unit': 'gal', 'rate_per_1000': 0.47, 'rate_unit': 'fl oz'},
}


def calculate_cost_per_application(product_name, area_sqft=1000, rate=None):
    """Calculate estimated cost per application for a product.

    Args:
        product_name: Product name
        area_sqft: Area in square feet (default 1000)
        rate: Override rate per 1000 sq ft (optional)

    Returns:
        Dict with cost estimate or None if product not found
    """
    product_lower = product_name.lower().strip()
    cost_data = PRODUCT_COSTS.get(product_lower)
    if not cost_data:
        return None

    use_rate = rate or cost_data['rate_per_1000']
    cost_per_unit = cost_data['cost_per_unit']
    unit = cost_data['unit']

    # Convert rate to cost
    # Rate is in oz or fl oz per 1000 sq ft
    # Cost is per lb or per gallon
    if 'oz' in cost_data['rate_unit']:
        if unit == 'lb':
            # Convert oz rate to lb, then multiply by cost per lb
            oz_per_lb = 16.0
            cost_per_1000 = (use_rate / oz_per_lb) * cost_per_unit
        elif unit == 'gal':
            # Convert fl oz rate to gallons, then multiply by cost per gallon
            fl_oz_per_gal = 128.0
            cost_per_1000 = (use_rate / fl_oz_per_gal) * cost_per_unit
        else:
            cost_per_1000 = use_rate * cost_per_unit
    else:
        cost_per_1000 = use_rate * cost_per_unit

    # Scale to requested area
    cost_for_area = cost_per_1000 * (area_sqft / 1000.0)
    cost_per_acre = cost_per_1000 * 43.56  # 43,560 sq ft / 1000

    return {
        'product': product_name.title(),
        'rate': use_rate,
        'rate_unit': cost_data['rate_unit'],
        'cost_per_1000_sqft': round(cost_per_1000, 2),
        'cost_per_acre': round(cost_per_acre, 2),
        'cost_for_area': round(cost_for_area, 2),
        'area_sqft': area_sqft,
        'note': 'Estimated cost — actual pricing varies by distributor and volume',
    }


def build_cost_context(question):
    """Build cost context for products mentioned in a question.

    Args:
        question: User question

    Returns:
        Context string with cost estimates, or empty string
    """
    q_lower = question.lower()
    costs_found = []

    for product in PRODUCT_COSTS:
        if product in q_lower:
            cost = calculate_cost_per_application(product)
            if cost:
                costs_found.append(cost)

    if not costs_found:
        return ''

    parts = ['--- ESTIMATED PRODUCT COSTS ---']
    parts.append('(Prices are approximate — actual costs vary by distributor)')
    for c in costs_found:
        parts.append(
            f"  {c['product']}: ~${c['cost_per_1000_sqft']:.2f}/1000 sq ft "
            f"(~${c['cost_per_acre']:.2f}/acre) at {c['rate']} {c['rate_unit']}/1000 sq ft"
        )
    return '\n'.join(parts)


# ---------------------------------------------------------------------------
# 13. PREDICTIVE ALERTS
# ---------------------------------------------------------------------------

def generate_predictive_alerts(user_id, weather_data=None, state=None, grass_type=None):
    """Generate proactive alerts based on conditions and history.

    Args:
        user_id: User ID for spray history
        weather_data: Current/forecast weather
        state: User's state
        grass_type: User's grass type

    Returns:
        List of alert dicts with type, severity, message
    """
    alerts = []
    now = datetime.now()

    # Disease pressure alerts based on season and region
    pressure = get_regional_disease_pressure(state, now.month)
    if pressure['high_risk']:
        alerts.append({
            'type': 'disease_pressure',
            'severity': 'info',
            'message': f"Current high-risk diseases for your region: {', '.join(pressure['high_risk'])}. Consider preventative applications.",
        })

    # Weather-based alerts
    if weather_data:
        temp = weather_data.get('temp', 75)
        humidity = weather_data.get('humidity', 50)

        # Pythium alert
        if temp > 85 and humidity > 85:
            alerts.append({
                'type': 'pythium_risk',
                'severity': 'warning',
                'message': f"Pythium blight conditions detected: {temp}°F with {humidity}% humidity. Monitor closely and consider preventative Subdue application.",
            })

        # Brown patch alert
        if temp > 68 and humidity > 90:
            night_temp = weather_data.get('night_temp', temp - 15)
            if night_temp > 68:
                alerts.append({
                    'type': 'brown_patch_risk',
                    'severity': 'warning',
                    'message': f"Brown patch conditions: night temps >68°F with high humidity. Avoid late-day nitrogen and excessive irrigation.",
                })

        # Heat stress alert
        if temp > 92:
            alerts.append({
                'type': 'heat_stress',
                'severity': 'critical',
                'message': f"Extreme heat ({temp}°F). Prioritize syringing, fan operation, and avoid unnecessary traffic on greens.",
            })

    # Spray rotation alert
    try:
        rotation = check_frac_rotation(user_id, days_back=30)
        if rotation['warning']:
            alerts.append({
                'type': 'rotation_warning',
                'severity': 'warning',
                'message': rotation['warning'],
            })
    except Exception:
        pass

    return alerts


# ---------------------------------------------------------------------------
# 14. COMMUNITY KNOWLEDGE LOOP
# ---------------------------------------------------------------------------

def process_community_feedback(question, rating, correction, sources=None):
    """Process user feedback to identify knowledge gaps for improvement.

    Args:
        question: Original question
        rating: User rating ('positive', 'negative')
        correction: User correction text
        sources: Sources used in the answer

    Returns:
        Dict with feedback analysis for knowledge improvement
    """
    result = {
        'gap_identified': False,
        'gap_topic': None,
        'gap_type': None,
        'action': None,
    }

    if rating != 'negative' or not correction:
        return result

    correction_lower = correction.lower()

    # Detect feedback categories
    if any(kw in correction_lower for kw in ['wrong rate', 'incorrect rate', 'rate is wrong', 'rate should be']):
        result['gap_identified'] = True
        result['gap_type'] = 'incorrect_rate'
        result['gap_topic'] = question[:100]
        result['action'] = 'verify_product_label_rates'

    elif any(kw in correction_lower for kw in ['wrong product', 'not safe', 'phytotox', 'damaged', 'burned']):
        result['gap_identified'] = True
        result['gap_type'] = 'safety_issue'
        result['gap_topic'] = question[:100]
        result['action'] = 'review_product_safety_data'

    elif any(kw in correction_lower for kw in ['outdated', 'old', 'discontinued', 'no longer available']):
        result['gap_identified'] = True
        result['gap_type'] = 'stale_data'
        result['gap_topic'] = question[:100]
        result['action'] = 'update_knowledge_base'

    elif any(kw in correction_lower for kw in ['missing', 'didn\'t mention', 'should include', 'also']):
        result['gap_identified'] = True
        result['gap_type'] = 'incomplete_coverage'
        result['gap_topic'] = question[:100]
        result['action'] = 'expand_topic_coverage'

    return result


def log_knowledge_gap(gap_info):
    """Log identified knowledge gap for future improvement.

    Args:
        gap_info: Dict from process_community_feedback

    Returns:
        bool indicating if gap was logged successfully
    """
    if not gap_info.get('gap_identified'):
        return False

    try:
        from db import get_db
        with get_db() as conn:
            # Create knowledge_gaps table if not exists
            conn.execute('''CREATE TABLE IF NOT EXISTS knowledge_gaps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                gap_type TEXT NOT NULL,
                action TEXT,
                occurrences INTEGER DEFAULT 1,
                resolved INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')

            # Check for existing gap on same topic
            existing = conn.execute(
                'SELECT id, occurrences FROM knowledge_gaps WHERE topic = ? AND gap_type = ? AND resolved = 0',
                (gap_info['gap_topic'], gap_info['gap_type'])
            ).fetchone()

            if existing:
                gap_id = existing['id'] if isinstance(existing, dict) else existing[0]
                count = (existing['occurrences'] if isinstance(existing, dict) else existing[1]) + 1
                conn.execute(
                    'UPDATE knowledge_gaps SET occurrences = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                    (count, gap_id)
                )
            else:
                conn.execute(
                    'INSERT INTO knowledge_gaps (topic, gap_type, action) VALUES (?, ?, ?)',
                    (gap_info['gap_topic'], gap_info['gap_type'], gap_info['action'])
                )

        return True
    except Exception as e:
        logger.warning(f"Failed to log knowledge gap: {e}")
        return False
