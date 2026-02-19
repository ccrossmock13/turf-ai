"""
Demo mode for Greenside AI.
Returns pre-crafted, high-quality responses for common questions.
Eliminates API cost and latency risk during live demos/pitches.

Usage:
  Set DEMO_MODE=true in .env to enable.
  Questions are fuzzy-matched so slight variations still hit the cache.
"""
import re
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Fuzzy matching — normalize question then check similarity
# ---------------------------------------------------------------------------

def _normalize(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text


def _word_overlap_score(a: str, b: str) -> float:
    """Jaccard similarity on word sets."""
    words_a = set(a.split())
    words_b = set(b.split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union)


def find_demo_response(question: str) -> Optional[Dict]:
    """
    Check if the question matches a cached demo response.
    Returns the full response dict if matched, None otherwise.
    Uses fuzzy matching so "What fungicide for dollar spot?" and
    "What fungicide should I use for dollar spot on bentgrass?" both hit.
    """
    norm_q = _normalize(question)

    best_match = None
    best_score = 0.0

    for entry in DEMO_RESPONSES:
        for trigger in entry['triggers']:
            norm_trigger = _normalize(trigger)
            score = _word_overlap_score(norm_q, norm_trigger)

            # Also check if the normalized question contains the trigger or vice versa
            if norm_trigger in norm_q or norm_q in norm_trigger:
                score = max(score, 0.85)

            if score > best_score:
                best_score = score
                best_match = entry

    # Require at least 55% word overlap to match
    if best_score >= 0.55 and best_match:
        logger.info(f"Demo cache hit (score={best_score:.2f}): {question[:60]}")
        return best_match['response']

    logger.debug(f"Demo cache miss (best={best_score:.2f}): {question[:60]}")
    return None


# ---------------------------------------------------------------------------
# Cached demo responses — curated, high-quality answers
# ---------------------------------------------------------------------------

DEMO_RESPONSES = [
    # -----------------------------------------------------------------------
    # 1. Dollar spot on bentgrass (most common superintendent question)
    # -----------------------------------------------------------------------
    {
        'triggers': [
            'what fungicide should i use for dollar spot on bentgrass',
            'dollar spot on bentgrass',
            'best fungicide for dollar spot',
            'how to treat dollar spot',
            'dollar spot control',
            'dollar spot on my greens',
        ],
        'response': {
            'answer': (
                "Dollar spot (*Clarireedia jacksonii*) on bentgrass is one of the most common diseases on golf course greens and fairways. Here's a research-backed approach:\n\n"
                "**Chemical Control Options:**\n\n"
                "1. **Propiconazole (Banner MAXX)** — FRAC 3 (DMI)\n"
                "   - Rate: 1-2 fl oz/1000 sq ft\n"
                "   - Excellent curative and preventive activity\n"
                "   - 14-day reapplication interval\n\n"
                "2. **Boscalid (Emerald)** — FRAC 7 (SDHI)\n"
                "   - Rate: 0.13-0.18 oz/1000 sq ft\n"
                "   - Outstanding dollar spot control, long residual\n"
                "   - 14-28 day interval\n\n"
                "3. **Fluoxastrobin (Fame SC)** — FRAC 11 (Strobilurin)\n"
                "   - Rate: 0.18-0.36 fl oz/1000 sq ft\n"
                "   - Good preventive, tank-mix with contact fungicide\n\n"
                "4. **Chlorothalonil (Daconil)** — FRAC M5 (Multi-site)\n"
                "   - Rate: 3.0-5.0 fl oz/1000 sq ft\n"
                "   - Contact protectant, excellent rotation partner\n"
                "   - Low resistance risk\n\n"
                "**Resistance Management:** Rotate between at least 2-3 FRAC groups. Dollar spot populations with DMI resistance are well-documented — always tank-mix single-site fungicides with a multi-site protectant like chlorothalonil.\n\n"
                "**Cultural Practices:** Maintain adequate nitrogen fertility (0.1-0.2 lbs N/1000 sq ft every 2 weeks during pressure periods), minimize leaf wetness duration, and remove morning dew by rolling or mowing."
            ),
            'sources': [
                {'name': 'Dollar Spot Management Guide', 'url': None, 'note': 'University research compilation'},
                {'name': 'Banner MAXX Label', 'url': None, 'note': 'Syngenta product label'},
                {'name': 'Emerald Fungicide Label', 'url': None, 'note': 'Bayer product label'},
            ],
            'confidence': {'score': 92, 'label': 'High Confidence'},
        }
    },

    # -----------------------------------------------------------------------
    # 2. Sprayer calibration
    # -----------------------------------------------------------------------
    {
        'triggers': [
            'how do i calibrate a boom sprayer',
            'calibrate a sprayer',
            'sprayer calibration',
            'calibrate my boom sprayer',
            'how to calibrate for 1.5 fl oz per 1000',
            'boom sprayer calibration steps',
        ],
        'response': {
            'answer': (
                "Here's how to calibrate a boom sprayer for accurate application:\n\n"
                "**The 1/128th Acre Method (most common):**\n\n"
                "1. **Measure a test area:** 1/128th of an acre = 340 sq ft\n"
                "   - For a 10-ft boom width: drive 34 feet\n"
                "   - For a 15-ft boom width: drive 22.7 feet\n\n"
                "2. **Fill with water** and mark the level in the tank\n\n"
                "3. **Spray the test area** at your normal operating speed and pressure (30-40 PSI typical for turf)\n\n"
                "4. **Measure the volume used** — this equals your gallons per acre (GPA)\n"
                "   - Target: Most turf applications call for 1-2 GPA (44-87 gallons per acre)\n\n"
                "5. **Calculate product per tank:**\n"
                "   - If you need 1.5 fl oz/1000 sq ft and your sprayer puts out 1.5 GPA:\n"
                "   - 1.5 fl oz × 43.56 (1000s in an acre) = 65.3 fl oz per acre\n"
                "   - For a 300-gallon tank covering ~200 acres at 1.5 GPA: 65.3 × 200 = 13,060 fl oz\n\n"
                "**Quick Nozzle Check:**\n"
                "- Catch output from each nozzle for 1 minute\n"
                "- All nozzles should be within 10% of each other\n"
                "- Replace any nozzle that's >10% off\n\n"
                "**Pro Tips:**\n"
                "- Recalibrate whenever you change nozzles, speed, or pressure\n"
                "- Use a GPS speedometer for consistent speed\n"
                "- Calibrate with water first, never with product in the tank"
            ),
            'sources': [
                {'name': 'Sprayer Calibration Guide', 'url': None, 'note': 'University extension publication'},
                {'name': 'TeeJet Nozzle Selection Guide', 'url': None, 'note': 'Equipment reference'},
            ],
            'confidence': {'score': 95, 'label': 'High Confidence'},
        }
    },

    # -----------------------------------------------------------------------
    # 3. Prodiamine vs dithiopyr
    # -----------------------------------------------------------------------
    {
        'triggers': [
            'what is the difference between prodiamine and dithiopyr',
            'prodiamine vs dithiopyr',
            'barricade vs dimension',
            'difference between barricade and dimension',
            'which pre-emergent is better',
            'prodiamine or dithiopyr',
        ],
        'response': {
            'answer': (
                "Great question — both are excellent pre-emergent herbicides but have key differences:\n\n"
                "**Prodiamine (Barricade)** — HRAC Group 3 (Dinitroaniline)\n"
                "- Rate: 0.5-1.5 lb ai/acre\n"
                "- **Longest residual** of any pre-emergent (up to 6+ months)\n"
                "- Strictly pre-emergent only — no post-emergent activity\n"
                "- Best for: split applications (fall + spring) on established turf\n"
                "- Very tight binding to soil organic matter\n"
                "- Safe on most warm and cool-season grasses at label rates\n\n"
                "**Dithiopyr (Dimension)** — HRAC Group 3 (Pyridine)\n"
                "- Rate: 0.25-0.5 lb ai/acre\n"
                "- **Has early post-emergent activity** on crabgrass up to the 1-tiller stage\n"
                "- Shorter residual than prodiamine (3-4 months)\n"
                "- Best for: situations where you might be slightly late on timing\n"
                "- Provides a wider application window\n"
                "- Safe on bentgrass greens at low rates (0.25 lb ai/acre)\n\n"
                "**When to Choose Which:**\n"
                "- **Prodiamine** if you want maximum longevity and can time it right\n"
                "- **Dithiopyr** if you need flexibility or might be late, or if applying on bentgrass greens\n"
                "- Both have the same HRAC group — don't rely on only one for resistance management\n\n"
                "**Key Timing:** Apply when soil temperatures reach 55°F at 2-inch depth for 3-5 consecutive days. This is typically when forsythia blooms in most regions."
            ),
            'sources': [
                {'name': 'Barricade 65WG Label', 'url': None, 'note': 'Syngenta product label'},
                {'name': 'Dimension 2EW Label', 'url': None, 'note': 'Corteva product label'},
                {'name': 'Pre-Emergent Herbicide Comparison', 'url': None, 'note': 'University research'},
            ],
            'confidence': {'score': 94, 'label': 'High Confidence'},
        }
    },

    # -----------------------------------------------------------------------
    # 4. Brown patch identification and treatment
    # -----------------------------------------------------------------------
    {
        'triggers': [
            'brown patch',
            'how to identify brown patch',
            'brown patch on my fairways',
            'rhizoctonia brown patch',
            'brown patch treatment',
            'brown patch vs dollar spot',
        ],
        'response': {
            'answer': (
                "**Brown Patch (*Rhizoctonia solani*)** is one of the most destructive turfgrass diseases, especially on cool-season grasses during hot, humid weather.\n\n"
                "**Identification:**\n"
                "- Circular patches 6 inches to several feet in diameter\n"
                "- **\"Smoke ring\" border** (dark gray/purple ring at patch edge, visible in early morning)\n"
                "- Leaf lesions with tan centers and dark brown borders\n"
                "- Most active when nighttime temps stay above 68°F with high humidity\n"
                "- Often appears after evening irrigation or prolonged leaf wetness\n\n"
                "**Chemical Control:**\n\n"
                "1. **Azoxystrobin (Heritage)** — FRAC 11\n"
                "   - Rate: 0.2-0.4 oz/1000 sq ft\n"
                "   - Excellent preventive activity\n\n"
                "2. **Flutolanil (ProStar)** — FRAC 7\n"
                "   - Rate: 2.0-4.4 oz/1000 sq ft\n"
                "   - One of the best curative options for brown patch\n\n"
                "3. **Propiconazole (Banner MAXX)** — FRAC 3\n"
                "   - Rate: 1-2 fl oz/1000 sq ft\n"
                "   - Good curative and preventive activity\n\n"
                "4. **Chlorothalonil (Daconil)** — FRAC M5\n"
                "   - Rate: 3.0-5.0 fl oz/1000 sq ft\n"
                "   - Excellent multi-site protectant for rotation\n\n"
                "**Cultural Practices (Critical):**\n"
                "- Reduce nighttime leaf wetness — water early morning, not evening\n"
                "- Improve air circulation (prune trees, fans on greens)\n"
                "- Avoid excessive nitrogen during hot weather\n"
                "- Raise mowing height slightly during disease pressure\n"
                "- Minimize thatch accumulation"
            ),
            'sources': [
                {'name': 'Brown Patch Disease Guide', 'url': None, 'note': 'University plant pathology'},
                {'name': 'Heritage Fungicide Label', 'url': None, 'note': 'Syngenta product label'},
                {'name': 'ProStar Fungicide Label', 'url': None, 'note': 'Bayer product label'},
            ],
            'confidence': {'score': 91, 'label': 'High Confidence'},
        }
    },

    # -----------------------------------------------------------------------
    # 5. NTEP varieties for transition zone
    # -----------------------------------------------------------------------
    {
        'triggers': [
            'ntep varieties for transition zone',
            'best grass varieties for transition zone',
            'what ntep varieties perform best in transition zone',
            'transition zone grass selection',
            'ntep trial results',
        ],
        'response': {
            'answer': (
                "The transition zone (roughly USDA zones 6-7, from Virginia to Oklahoma) is the most challenging region for turfgrass selection. Here are top performers from recent NTEP trials:\n\n"
                "**For Putting Greens:**\n"
                "- **TifEagle** bermudagrass — excellent heat tolerance, very fine texture\n"
                "- **Champion** bermudagrass — dense, aggressive, good cold tolerance for bermuda\n"
                "- **007** creeping bentgrass — best heat tolerance among bentgrasses\n"
                "- **Pure Distinction** creeping bentgrass — improved summer performance\n\n"
                "**For Fairways:**\n"
                "- **Latitude 36** bermudagrass — best cold-hardy bermuda for fairways\n"
                "- **TifTuf** bermudagrass — exceptional drought tolerance, good cold hardiness\n"
                "- **Tahoma 31** bermudagrass — fastest spring green-up, excellent wear tolerance\n\n"
                "**For Home Lawns / Roughs:**\n"
                "- **Tall Fescue blends** — still the workhorse for transition zone lawns\n"
                "  - Top cultivars: Regenerate, Traverse 2, Raptor III\n"
                "- **Zoysiagrass** — excellent option for low-maintenance transition zone turf\n"
                "  - Top cultivars: Zenith (seeded), Zeon (vegetative)\n\n"
                "**Key Decision Factors:**\n"
                "- Cool-season grasses struggle in July/August heat\n"
                "- Warm-season grasses go dormant November-March\n"
                "- Many transition zone courses use bermuda fairways with bentgrass greens\n"
                "- Overseeding bermuda with ryegrass in fall provides year-round green"
            ),
            'sources': [
                {'name': 'NTEP Bermudagrass Trial Data', 'url': None, 'note': 'National Turfgrass Evaluation Program'},
                {'name': 'NTEP Tall Fescue Trial Data', 'url': None, 'note': 'National Turfgrass Evaluation Program'},
                {'name': 'Transition Zone Turfgrass Selection', 'url': None, 'note': 'University extension guide'},
            ],
            'confidence': {'score': 88, 'label': 'High Confidence'},
        }
    },

    # -----------------------------------------------------------------------
    # 6. Primo Maxx PGR program
    # -----------------------------------------------------------------------
    {
        'triggers': [
            'primo maxx',
            'pgr program for greens',
            'trinexapac-ethyl',
            'how to use primo',
            'growth regulator program',
            'primo maxx rate for bentgrass',
        ],
        'response': {
            'answer': (
                "**Primo Maxx (trinexapac-ethyl)** is the industry standard PGR for managed turf. Here's a research-backed program:\n\n"
                "**Putting Greens (Bentgrass):**\n"
                "- Rate: 0.125-0.25 fl oz/1000 sq ft\n"
                "- Interval: Every 7-14 days (GDD-based is best)\n"
                "- GDD model: Reapply at 200 GDD (base 32°F)\n"
                "- Start: When consistent growth begins in spring\n\n"
                "**Putting Greens (Bermudagrass):**\n"
                "- Rate: 0.125-0.375 fl oz/1000 sq ft\n"
                "- Interval: 7-21 days depending on growth rate\n"
                "- Can use higher rates on bermuda than bentgrass\n\n"
                "**Fairways:**\n"
                "- Rate: 0.25-0.50 fl oz/1000 sq ft\n"
                "- Interval: 14-28 days\n"
                "- Significant clipping reduction = less mowing\n\n"
                "**Benefits Beyond Growth Suppression:**\n"
                "- Increased turf density and color\n"
                "- Improved stress tolerance (heat, drought)\n"
                "- Reduced clipping yield (40-60% reduction)\n"
                "- Enhanced ball roll on greens\n"
                "- Reduced scalping risk\n\n"
                "**Important Notes:**\n"
                "- Do NOT apply during active stress (heat, drought, disease pressure)\n"
                "- Reduce rate or skip applications during summer stress on bentgrass\n"
                "- Can tank-mix with most fungicides (check label for exceptions)\n"
                "- Avoid application immediately before or after core aeration\n"
                "- GDD-based timing produces more consistent results than calendar-based"
            ),
            'sources': [
                {'name': 'Primo MAXX Label', 'url': None, 'note': 'Syngenta product label'},
                {'name': 'PGR Management Guide', 'url': None, 'note': 'University research publication'},
            ],
            'confidence': {'score': 93, 'label': 'High Confidence'},
        }
    },

    # -----------------------------------------------------------------------
    # 7. Summer bentgrass decline / anthracnose
    # -----------------------------------------------------------------------
    {
        'triggers': [
            'summer bentgrass decline',
            'anthracnose on bentgrass',
            'anthracnose treatment',
            'bentgrass in summer heat',
            'how to keep bentgrass alive in summer',
        ],
        'response': {
            'answer': (
                "Summer bentgrass decline is a complex of stresses that can include anthracnose, heat stress, and root loss. Here's a comprehensive management approach:\n\n"
                "**Anthracnose (*Colletotrichum cereale*):**\n"
                "- Most destructive summer disease on Poa annua and bentgrass\n"
                "- Appears as irregular yellow/bronze patches\n"
                "- Black acervuli (fruiting bodies) visible with hand lens on leaf sheaths\n\n"
                "**Chemical Control for Anthracnose:**\n\n"
                "1. **Fludioxonil (Medallion SC)** — FRAC 12\n"
                "   - Rate: 0.25 oz/1000 sq ft\n"
                "   - Excellent stand-alone anthracnose control\n\n"
                "2. **Chlorothalonil (Daconil)** — FRAC M5\n"
                "   - Rate: 3.0-5.0 fl oz/1000 sq ft\n"
                "   - Best as preventive; tank-mix partner\n\n"
                "3. **Thiophanate-methyl (3336)** — FRAC 1\n"
                "   - Rate: 4-8 fl oz/1000 sq ft\n"
                "   - Good curative; resistance is a concern\n\n"
                "4. **Phosphonate products (Signature, Appear)** — FRAC P7\n"
                "   - Rate: 4-8 fl oz/1000 sq ft\n"
                "   - Excellent Pythium + anthracnose suppression\n\n"
                "**Cultural Practices (Critical for Summer Survival):**\n"
                "- **Raise mowing height** to 0.130-0.150\" (sacrifice some speed for health)\n"
                "- **Light, frequent nitrogen** — 0.1 lb N/1000 sq ft every 7-10 days\n"
                "- **Fans and shade management** — maximize air movement\n"
                "- **Syringe cooling** — light water midday to cool canopy (not deep irrigation)\n"
                "- **Roll instead of mow** on extreme heat days (>95°F)\n"
                "- **Avoid aggressive cultural practices** — no verticutting or aggressive topdressing\n"
                "- **Hand water hot spots** — don't let edges and slopes dry out"
            ),
            'sources': [
                {'name': 'Anthracnose Management Research', 'url': None, 'note': 'Rutgers University research'},
                {'name': 'Summer Bentgrass Management Guide', 'url': None, 'note': 'University extension publication'},
            ],
            'confidence': {'score': 90, 'label': 'High Confidence'},
        }
    },

    # -----------------------------------------------------------------------
    # 8. Poa annua management
    # -----------------------------------------------------------------------
    {
        'triggers': [
            'poa annua',
            'how to control poa annua',
            'poa annua management',
            'annual bluegrass control',
            'poa annua in bentgrass greens',
        ],
        'response': {
            'answer': (
                "Poa annua (annual bluegrass) management is one of the most debated topics in turf management. Your strategy depends on whether you're trying to **eliminate it** or **manage it as the primary grass**.\n\n"
                "**If Controlling/Eliminating Poa:**\n\n"
                "1. **Pre-emergent approach:**\n"
                "   - Paclobutrazol (Trimmit) at 22 fl oz/acre — selectively weakens Poa\n"
                "   - Apply in fall when Poa germinates (soil temp <70°F)\n"
                "   - Ethofumesate (Prograss) at 1.5-2.0 lb ai/acre in fall\n\n"
                "2. **Post-emergent options:**\n"
                "   - Methiozolin (Poa Cure) — new chemistry, labeled for Poa removal in bentgrass\n"
                "   - Amicarbazone (Xonerate) — selective Poa control in some cool-season grasses\n\n"
                "3. **Cultural suppression:**\n"
                "   - Primo Maxx favors bentgrass over Poa at standard rates\n"
                "   - Maintain higher N levels to favor bentgrass competition\n"
                "   - Interseeding bentgrass into thin areas\n\n"
                "**If Managing Poa as Primary Turf:**\n"
                "- Focus on anthracnose and summer decline management\n"
                "- Light, frequent fertilization through summer\n"
                "- Avoid drought stress — Poa has shallow roots\n"
                "- Preventive fungicide program starting in spring\n"
                "- Accept some winter annual seedhead formation\n"
                "- Ethephon (Proxy) to suppress seedheads in spring\n\n"
                "**Reality Check:** Complete Poa annua elimination on greens takes 3-5+ years and significant transition pain. Many courses now manage Poa rather than fight it."
            ),
            'sources': [
                {'name': 'Poa annua Management Strategies', 'url': None, 'note': 'Penn State University research'},
                {'name': 'Annual Bluegrass Control Guide', 'url': None, 'note': 'University extension publication'},
            ],
            'confidence': {'score': 89, 'label': 'High Confidence'},
        }
    },

    # -----------------------------------------------------------------------
    # 9. Spring dead spot on bermudagrass
    # -----------------------------------------------------------------------
    {
        'triggers': [
            'spring dead spot',
            'spring dead spot on bermuda',
            'spring dead spot treatment',
            'sds on bermudagrass',
        ],
        'response': {
            'answer': (
                "**Spring Dead Spot (SDS)** is the most damaging disease of bermudagrass in the transition zone and upper South, caused by *Ophiosphaerella* species.\n\n"
                "**Identification:**\n"
                "- Circular, bleached-out dead patches (6 inches to 3+ feet) that appear at spring green-up\n"
                "- Patches are slow to recover because roots and stolons are killed\n"
                "- Often in the same spots year after year\n"
                "- Grass within patches is easily pulled up (rotted roots)\n\n"
                "**Chemical Control (Fall Applications — Critical Timing):**\n\n"
                "1. **Tebuconazole (Torque/Mirage)** — FRAC 3\n"
                "   - Rate: 1-2 fl oz/1000 sq ft\n"
                "   - Apply twice in fall: September + October\n"
                "   - Best research-supported option\n\n"
                "2. **Fenarimol (Rubigan)** — FRAC 3\n"
                "   - Rate: 1.5-3.0 fl oz/1000 sq ft\n"
                "   - Two fall applications\n"
                "   - Excellent SDS data\n\n"
                "3. **Myclobutanil (Eagle)** — FRAC 3\n"
                "   - Rate: 1.2 fl oz/1000 sq ft\n"
                "   - Fall applications\n\n"
                "**Critical Application Notes:**\n"
                "- **Timing is everything:** Apply in September-October BEFORE dormancy\n"
                "- Irrigate after application to move product into the root zone\n"
                "- Two applications 28 days apart work better than one\n"
                "- Spring applications do NOT work — the infection occurs in fall\n\n"
                "**Cultural Practices:**\n"
                "- Reduce thatch (>0.5\" thatch worsens SDS)\n"
                "- Avoid late-fall nitrogen (promotes succulent tissue vulnerable to infection)\n"
                "- Improve drainage in affected areas\n"
                "- Core aerate in summer to reduce compaction\n"
                "- Overseed dead patches with improved bermuda cultivars in late spring"
            ),
            'sources': [
                {'name': 'Spring Dead Spot Management', 'url': None, 'note': 'Oklahoma State University research'},
                {'name': 'SDS Fungicide Research Update', 'url': None, 'note': 'University of Arkansas turfgrass program'},
            ],
            'confidence': {'score': 91, 'label': 'High Confidence'},
        }
    },

    # -----------------------------------------------------------------------
    # 10. Tank mix compatibility
    # -----------------------------------------------------------------------
    {
        'triggers': [
            'tank mix compatibility',
            'what can i tank mix',
            'can i tank mix',
            'tank mixing fungicides',
            'compatible tank mix partners',
        ],
        'response': {
            'answer': (
                "Tank mixing is essential for efficient applications, but compatibility matters. Here are the key rules:\n\n"
                "**General Compatibility Rules:**\n"
                "1. Always do a **jar test** before mixing a new combination in the tank\n"
                "2. Add products in this order: **WALE** — Wettable powders, Agitation, Liquids, Emulsifiable concentrates\n"
                "3. Never mix more than 3 products without testing\n"
                "4. Read every label for specific incompatibility warnings\n\n"
                "**Common Compatible Combinations:**\n"
                "- Chlorothalonil + DMI fungicide (standard disease rotation)\n"
                "- Prodiamine + liquid fertilizer (spring pre-emergent + feeding)\n"
                "- Primo Maxx + most fungicides (check label; avoid some FRAC 11)\n"
                "- Bifenthrin + fungicide (insect + disease in one pass)\n\n"
                "**Known Incompatible / Risky Combinations:**\n"
                "- Chlorothalonil + DMI in extreme heat (>90°F) — phytotoxicity risk\n"
                "- Calcium-based products + phosphorus fertilizers — precipitate\n"
                "- Copper products + acidic products — can increase phytotoxicity\n"
                "- Iron + manganese in same tank with high pH water — flocculation\n"
                "- Wettable powder + emulsifiable concentrate — test first\n\n"
                "**Jar Test Procedure:**\n"
                "1. Fill a quart jar with carrier water (from your actual source)\n"
                "2. Add each product proportionally in WALE order\n"
                "3. Shake and let sit 15-30 minutes\n"
                "4. Look for: separation, clumping, gelling, or precipitate\n"
                "5. If any occur — do NOT mix in the tank"
            ),
            'sources': [
                {'name': 'Tank Mix Compatibility Guide', 'url': None, 'note': 'University extension publication'},
                {'name': 'Pesticide Application Best Practices', 'url': None, 'note': 'EPA guidance document'},
            ],
            'confidence': {'score': 90, 'label': 'High Confidence'},
        }
    },

    # -----------------------------------------------------------------------
    # 11. Bermuda greens management
    # -----------------------------------------------------------------------
    {
        'triggers': [
            'bermuda greens management',
            'bermudagrass putting green',
            'tifeagle maintenance',
            'champion bermuda greens',
            'managing bermuda greens',
        ],
        'response': {
            'answer': (
                "Managing bermudagrass putting greens requires a precise, aggressive maintenance program:\n\n"
                "**Mowing:**\n"
                "- Height: 0.100-0.125\" (TifEagle, Champion, Mini-Verde)\n"
                "- Frequency: Daily during active growth, double-cut for tournaments\n"
                "- Use walk-behind greens mowers with sharp, properly adjusted reels\n"
                "- Roll 2-3x/week for consistent ball roll without lowering HOC\n\n"
                "**Fertility Program:**\n"
                "- Total annual N: 6-12 lbs N/1000 sq ft\n"
                "- Spoon-feed: 0.1-0.25 lbs N/1000 sq ft every 7-14 days\n"
                "- Use ammonium sulfate or urea — bermuda responds well to NH4+\n"
                "- Potassium: Match N rate 1:1 for stress tolerance\n"
                "- Iron: Foliar applications for color without excessive growth\n\n"
                "**Topdressing:**\n"
                "- Light, frequent: 0.5-1.0 cubic ft/1000 sq ft every 2-3 weeks\n"
                "- Use USGA-spec sand matching rootzone\n"
                "- Critical for managing organic matter and grain\n\n"
                "**Verticutting / Grooming:**\n"
                "- Verticut every 10-14 days during active growth\n"
                "- Depth: just touching stolons\n"
                "- Essential for grain control on bermuda\n"
                "- Reduce or stop during stress periods\n\n"
                "**PGR Program:**\n"
                "- Primo Maxx: 0.125-0.375 fl oz/1000 sq ft every 7-14 days\n"
                "- Increases density, reduces grain, improves ball roll\n"
                "- GDD-based timing (200 GDD base 32°F) for consistency\n\n"
                "**Winter Overseeding (if applicable):**\n"
                "- Perennial ryegrass at 15-25 lbs/1000 sq ft\n"
                "- Scalp bermuda to 0.050\" before seeding\n"
                "- Time for 4-6 weeks of growth before first frost"
            ),
            'sources': [
                {'name': 'Bermudagrass Putting Green Management', 'url': None, 'note': 'University of Georgia turfgrass program'},
                {'name': 'Ultradwarf Bermudagrass Best Practices', 'url': None, 'note': 'USGA Green Section'},
            ],
            'confidence': {'score': 92, 'label': 'High Confidence'},
        }
    },

    # -----------------------------------------------------------------------
    # 12. Nematode damage and control
    # -----------------------------------------------------------------------
    {
        'triggers': [
            'nematode',
            'nematode damage',
            'nematode control',
            'sting nematodes',
            'nematode management on turf',
        ],
        'response': {
            'answer': (
                "Nematode damage on turf is often misdiagnosed as drought stress or nutrient deficiency. Here's what you need to know:\n\n"
                "**Common Turf-Damaging Nematodes:**\n"
                "- **Sting** (*Belonolaimus*) — most destructive in sandy soils\n"
                "- **Lance** (*Hoplolaimus*) — wide host range\n"
                "- **Root-knot** (*Meloidogyne*) — causes galling on roots\n"
                "- **Ring** (*Mesocriconema*) — common in bermudagrass\n\n"
                "**Symptoms:**\n"
                "- Irregular thinning and yellowing, especially in sandy areas\n"
                "- Poor response to fertilizer and irrigation\n"
                "- Roots appear shortened, stubby, or dark\n"
                "- Often worse in hot, dry conditions\n"
                "- **Diagnosis requires a lab assay** — submit soil + root samples to a nematology lab\n\n"
                "**Chemical Control:**\n\n"
                "1. **Abamectin (Divanem)** — excellent broad-spectrum nematicide\n"
                "   - Rate: 0.25-0.50 fl oz/1000 sq ft\n"
                "   - Apply spring + fall; irrigate in\n\n"
                "2. **Fluopyram (Indemnify)** — FRAC 7 (also has fungicidal activity)\n"
                "   - Rate: 0.39 fl oz/1000 sq ft\n"
                "   - Once per year application\n"
                "   - Dual-purpose: nematode + disease control\n\n"
                "**Cultural Practices:**\n"
                "- Maintain optimal soil moisture — stressed turf shows more nematode damage\n"
                "- Light, frequent fertilization to support root regrowth\n"
                "- Core aerate to improve rooting environment\n"
                "- Topdress with organic-amended sand to support beneficial soil biology\n"
                "- Nematode populations are highest in warm, sandy soils — test annually"
            ),
            'sources': [
                {'name': 'Turfgrass Nematode Management', 'url': None, 'note': 'University of Florida nematology lab'},
                {'name': 'Indemnify Nematicide Label', 'url': None, 'note': 'Bayer product label'},
            ],
            'confidence': {'score': 88, 'label': 'High Confidence'},
        }
    },

    # -----------------------------------------------------------------------
    # 13. Irrigation auditing / scheduling
    # -----------------------------------------------------------------------
    {
        'triggers': [
            'irrigation audit',
            'irrigation scheduling',
            'how much water does my turf need',
            'et based irrigation',
            'irrigation management',
            'watering schedule for golf course',
        ],
        'response': {
            'answer': (
                "Efficient irrigation is one of the biggest cost-saving and turf quality opportunities. Here's a research-backed approach:\n\n"
                "**Step 1: Conduct an Irrigation Audit**\n"
                "- Place catch cups in a grid pattern across the zone\n"
                "- Run each station for a set time (15-20 minutes)\n"
                "- Measure water collected in each cup\n"
                "- Calculate: Distribution Uniformity (DU) = (lowest 25% avg) / (overall avg)\n"
                "- Target DU: >70% is acceptable, >80% is good, >85% is excellent\n\n"
                "**Step 2: Determine Water Need**\n"
                "- Use ET (evapotranspiration) data from a local weather station\n"
                "- **Cool-season turf:** Apply 60-80% of ET\n"
                "- **Warm-season turf:** Apply 50-70% of ET\n"
                "- Adjust for soil type, slope, and shade\n\n"
                "**Step 3: Schedule for Efficiency**\n"
                "- **Deep, infrequent** watering promotes deeper roots\n"
                "- Apply 0.25-0.50 inches per cycle, 2-3x per week\n"
                "- Water between 2-8 AM to minimize evaporation and disease\n"
                "- Use cycle-and-soak on slopes: 2-3 short runs with 30-minute soak periods\n\n"
                "**Advanced Strategies:**\n"
                "- Soil moisture sensors (TDR probes) for data-driven decisions\n"
                "- Hand-watering hot spots rather than over-watering entire zones\n"
                "- Wetting agents to improve water movement in hydrophobic soils\n"
                "- Track daily ET replacement rate vs. actual application\n\n"
                "**Cost Impact:** Most golf courses can reduce water use 20-30% with proper auditing and ET-based scheduling without sacrificing turf quality."
            ),
            'sources': [
                {'name': 'Irrigation Auditing Guide', 'url': None, 'note': 'Irrigation Association best practices'},
                {'name': 'ET-Based Irrigation Management', 'url': None, 'note': 'University extension publication'},
            ],
            'confidence': {'score': 91, 'label': 'High Confidence'},
        }
    },

    # -----------------------------------------------------------------------
    # 14. Soil testing and amendment
    # -----------------------------------------------------------------------
    {
        'triggers': [
            'soil test',
            'soil testing',
            'what should my soil ph be',
            'soil amendment',
            'lime application',
            'soil test interpretation',
        ],
        'response': {
            'answer': (
                "Soil testing is the foundation of any good fertility program. Here's what you need to know:\n\n"
                "**Ideal Soil Parameters for Turf:**\n"
                "- **pH:** 6.0-7.0 (bentgrass tolerates 5.5-6.5)\n"
                "- **Phosphorus (P):** 25-50 ppm (Mehlich 3)\n"
                "- **Potassium (K):** 100-200 ppm\n"
                "- **Calcium (Ca):** 500-1500 ppm\n"
                "- **Magnesium (Mg):** 50-150 ppm\n"
                "- **Organic Matter:** 2-5% for native soil; 1-3% for sand-based greens\n\n"
                "**pH Adjustment:**\n"
                "- **To raise pH (acidic soil):** Calcitic lime at 25-50 lbs/1000 sq ft\n"
                "  - Takes 3-6 months to fully react\n"
                "  - Don't exceed 50 lbs/1000 sq ft per application\n"
                "- **To lower pH (alkaline soil):** Elemental sulfur at 5-15 lbs/1000 sq ft\n"
                "  - Much slower reaction than lime (6-12 months)\n"
                "  - Acidifying fertilizers (ammonium sulfate) help maintain lower pH\n\n"
                "**Sampling Best Practices:**\n"
                "- Test 2x per year (spring + fall)\n"
                "- Pull cores at 3-4\" depth (rootzone)\n"
                "- 15-20 cores per zone, mixed together\n"
                "- Sample greens, tees, fairways, and roughs separately\n"
                "- Use a consistent lab (results vary between labs)\n"
                "- Test sand-based greens with a saturated paste extract (SPE) method\n\n"
                "**Common Mistakes:**\n"
                "- Over-liming based on a single test\n"
                "- Applying P when levels are already high (promotes Poa annua)\n"
                "- Ignoring micronutrients (Fe, Mn, Zn)\n"
                "- Not accounting for irrigation water quality (pH, bicarbonates, sodium)"
            ),
            'sources': [
                {'name': 'Soil Testing for Turfgrass', 'url': None, 'note': 'University extension soil science'},
                {'name': 'Turfgrass Fertility Best Practices', 'url': None, 'note': 'USGA Green Section'},
            ],
            'confidence': {'score': 93, 'label': 'High Confidence'},
        }
    },

    # -----------------------------------------------------------------------
    # 15. What is Greenside AI / how does it work
    # -----------------------------------------------------------------------
    {
        'triggers': [
            'what is greenside',
            'what does greenside do',
            'how does greenside work',
            'tell me about greenside',
            'what is this tool',
            'how does this ai work',
        ],
        'response': {
            'answer': (
                "**Greenside AI** is an intelligent turfgrass management assistant built specifically for golf course superintendents, sports turf managers, and lawn care professionals.\n\n"
                "**What It Does:**\n"
                "- Answers turf management questions with **specific product rates, FRAC/HRAC codes, and research-backed recommendations**\n"
                "- Cross-references a curated knowledge base of product labels, university research, NTEP trial data, and spray program guides\n"
                "- Integrates real-time **weather data** to contextualize application timing\n"
                "- Provides **confidence scores** on every answer so you know how much to trust the recommendation\n"
                "- Catches **dangerous recommendations** — won't tell you to exceed label rates, skip PPE, or dump chemicals in waterways\n\n"
                "**How It Works:**\n"
                "1. Your question is analyzed and classified\n"
                "2. Our knowledge base of 160,000+ research vectors is searched\n"
                "3. Results are scored, reranked, and enriched with structured product data\n"
                "4. An AI generates the answer using only verified source material\n"
                "5. The answer is then grounding-checked, hallucination-filtered, and validated against product labels\n"
                "6. A confidence score is calculated based on source quality and verification\n\n"
                "**What It's Not:**\n"
                "- It's not a replacement for reading product labels (the label is always the law)\n"
                "- It's not a substitute for professional agronomic advice in complex situations\n"
                "- It's a tool to help you make faster, more informed decisions with research backing\n\n"
                "Ask me anything about diseases, fungicides, herbicides, cultural practices, equipment calibration, or variety selection!"
            ),
            'sources': [],
            'confidence': {'score': 99, 'label': 'High Confidence'},
        }
    },
]
