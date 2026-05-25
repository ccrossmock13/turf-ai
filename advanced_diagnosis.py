"""Deterministic advanced diagnosis mode for turf symptom questions."""

from __future__ import annotations

import re
from typing import Any

from advanced_turf_science import SCIENCE_TOPIC_ALIASES
from course_profile import infer_regional_management_context, summarize_known_profile_for_questions
from knowledge_base import load_advanced_turf_science


DIAGNOSIS_INTENT_TERMS = [
    "diagnose", "diagnosis", "what is causing", "what's causing",
    "what causes", "why are", "why is", "why did", "why do", "why does", "how do i tell",
    "how should i diagnose", "is this", "could this be", "separate",
    "versus", " vs ", "symptom", "symptoms", "decline", "thinning",
    "thin", "wilt", "wilting", "spots", "patches", "yellowing",
    "brown", "roots look", "shallow roots", "dying", "blamed disease",
    "before you blamed disease", "where do you start", "where do you go first",
    "thinking about first", "what are you checking", "what does that tell you",
    "what does that smell like", "how do you read that", "what am i overlooking",
    "what am i missing",
]


PRODUCT_DECISION_TERMS = [
    "what should i use", "what should we use", "what can i spray",
    "what should i spray", "rate", "label", "tank mix", "mix with",
    "how much", "ounces", "oz", "product for",
]


DIAGNOSTIC_BUCKETS = {
    "wet_wilt_root_oxygen": {
        "label": "Wet wilt / root oxygen limitation",
        "topics": ["root_respiration_oxygen_balance", "perched_water_layering_diagnostics"],
        "triggers": [
            "wet", "moisture readings are high", "moisture is high", "saturated",
            "low spot", "low spots", "black layer", "anaerobic", "wilt",
            "wilting", "wet but wilt", "perched water", "layering",
            "water or disease", "from water or disease", "weak roots",
            "water stress", "water stress from disease", "separate water stress from disease",
        ],
        "supports": [
            "Wilt or decline is worse in wet areas, low spots, or after irrigation/rain.",
            "Roots are shallow, dark, sour-smelling, or concentrated above a layer.",
            "Moisture readings are high but the canopy still wilts under heat load."
        ],
        "rules_out": [
            "Uniformly dry profile by depth with rapid recovery after hand watering.",
            "Healthy white roots through the profile and no layering or saturation pattern."
        ],
        "field_checks": [
            "Pull plugs from healthy, transition, and bad areas; smell and inspect roots by depth.",
            "Record moisture at multiple depths, not only the top inch.",
            "Check whether symptoms map to low spots, drainage lines, irrigation arcs, or layered profiles."
        ],
    },
    "root_disease_pythium": {
        "label": "Pythium/root disease complex",
        "topics": ["pythium_root_dysfunction_vs_wet_wilt"],
        "triggers": [
            "pythium", "root dysfunction", "root rot", "root disease",
            "wet wilt", "short roots", "discolored roots", "water soaked roots",
        ],
        "supports": [
            "Roots are shortened, discolored, sparse, water-soaked, or sloughing.",
            "Symptoms express under heat after saturated or high-humidity periods.",
            "Pattern overlaps with wet low spots but persists after basic water correction."
        ],
        "rules_out": [
            "Lab results do not detect a root pathogen and roots are otherwise healthy.",
            "Symptoms fully resolve after correcting moisture/oxygen without disease-directed action."
        ],
        "field_checks": [
            "Submit roots and soil from the transition zone to a diagnostic lab.",
            "Compare root mass and color between healthy, transition, and symptomatic areas.",
            "Do not add water until rootzone oxygen and moisture-by-depth are checked."
        ],
    },
    "disease_microclimate": {
        "label": "Disease-favorable microclimate",
        "topics": [
            "disease_triangle_leaf_wetness_microclimate",
            "dollar_spot_epidemiology_nitrogen_leaf_wetness",
            "brown_patch_rhizoctonia_heat_humidity",
        ],
        "triggers": [
            "humid", "dew", "leaf wetness", "disease", "spot", "spots",
            "patch", "patches", "dollar spot", "brown patch", "mycelium",
            "warm nights", "smoke ring", "water or disease", "from water or disease",
            "water stress from disease", "separate water stress from disease",
        ],
        "supports": [
            "Symptoms track dew, shade, poor airflow, humidity, or warm nights.",
            "Lesions, mycelium, smoke rings, or patch margins match a known disease pattern.",
            "Outbreak follows nitrogen, mowing, moisture, or weather changes that increase susceptibility."
        ],
        "rules_out": [
            "No lesions or signs after close inspection.",
            "Symptoms map cleanly to traffic, irrigation coverage, salinity, or physical rootzone issues."
        ],
        "field_checks": [
            "Inspect leaves with a hand lens for lesions and signs early in the morning.",
            "Map symptoms against dew persistence, shade, airflow, and irrigation coverage.",
            "Check recent nitrogen, mowing height, rolling, and fungicide interval history."
        ],
    },
    "abiotic_water_distribution": {
        "label": "Localized dry spot / water distribution disorder",
        "topics": ["localized_dry_spot_hydrophobicity", "wetting_agent_chemistry_functional_groups"],
        "triggers": [
            "localized dry spot", "dry spot", "hydrophobic", "hydrophobicity",
            "wetting agent", "water repellency", "hot spot", "hand water",
        ],
        "supports": [
            "Dry pockets persist beside adequately moist turf.",
            "Water beads on dry cores or bypasses dry zones.",
            "Moisture readings vary sharply over short distances."
        ],
        "rules_out": [
            "Profile is uniformly wet and oxygen-limited rather than hydrophobic.",
            "Symptoms are ring/lesion-driven rather than moisture-distribution driven."
        ],
        "field_checks": [
            "Run water-drop tests on dry cores.",
            "Map volumetric water content across healthy and bad spots.",
            "Check wetting-agent timing, irrigation-in, and irrigation uniformity."
        ],
    },
    "species_heat_physiology": {
        "label": "Species heat physiology / carbohydrate stress",
        "topics": [
            "cool_season_heat_carbohydrate_decline",
            "poa_annua_vs_bentgrass_summer_decline",
            "traffic_recovery_carbohydrate_growth_rate",
        ],
        "triggers": [
            "heat", "summer", "poa", "poa annua", "bentgrass",
            "carbohydrate", "warm nights", "traffic", "recovery",
            "decline faster", "summer decline",
        ],
        "supports": [
            "Poa-dominant or trafficked areas decline first during heat or warm nights.",
            "Roots are shorter and recovery is slow despite adequate fertility.",
            "Recent mowing, rolling, PGR, traffic, or drought stress reduced recovery capacity."
        ],
        "rules_out": [
            "Symptoms occur equally across species and are unrelated to heat, traffic, or recovery demand.",
            "Lab or field signs clearly point to a primary pathogen or chemical injury."
        ],
        "field_checks": [
            "Compare root depth and species composition in good and bad zones.",
            "Check clipping yield trend, mowing/rolling intensity, and recent night temperatures.",
            "Reduce stress intensity and watch whether recovery improves with weather relief."
        ],
    },
    "shade_low_light": {
        "label": "Shade / low-light carbon limitation",
        "topics": ["shade_light_carbohydrate_morphology"],
        "triggers": ["shade", "shaded", "low light", "tree", "fertility is good"],
        "supports": [
            "Thinning aligns with trees, buildings, or low-airflow shaded pockets.",
            "Leaves are elongated, soft, and slower to recover.",
            "Disease pressure is higher where dew persists."
        ],
        "rules_out": [
            "Thinning is unrelated to light pattern and follows irrigation, traffic, or spray overlaps instead.",
            "Canopy receives adequate light and airflow but roots or lesions explain decline."
        ],
        "field_checks": [
            "Track hours of direct light and morning dew duration.",
            "Compare traffic intensity and mowing stress in shaded vs full-sun areas.",
            "Evaluate pruning, traffic rerouting, mowing height, and species suitability."
        ],
    },
    "chemistry_nutrient_salinity": {
        "label": "Water chemistry / nutrient availability stress",
        "topics": [
            "salinity_osmotic_sodium_structure_stress",
            "bicarbonate_alkalinity_micronutrient_lockout",
            "nitrogen_form_release_growth_stress_balance",
        ],
        "triggers": [
            "salinity", "sodium", "salt", "ec", "bicarbonate", "bicarbonates",
            "alkalinity", "micronutrient", "chlorosis", "pale", "yellowing",
            "nitrogen", "release rate",
        ],
        "supports": [
            "Stress or chlorosis persists despite apparently adequate fertility.",
            "Water/soil tests show EC, sodium, bicarbonate, alkalinity, or pH concerns.",
            "Symptoms are worse where irrigation accumulates or leaching is poor."
        ],
        "rules_out": [
            "Water and soil chemistry are normal and symptoms follow lesions, roots, or traffic instead.",
            "Color responds predictably to small nutrient corrections without recurring lockout."
        ],
        "field_checks": [
            "Pull irrigation-water and soil tests for pH, EC, sodium hazard, bicarbonates, and alkalinity.",
            "Separate iron/micronutrient color response from true nitrogen need.",
            "Assess drainage before leaching or amendment decisions."
        ],
    },
    "nematode_root_pruning": {
        "label": "Nematode/root-pruning stress complex",
        "topics": ["nematode_root_pruning_stress_complex"],
        "triggers": ["nematode", "nematodes", "root pruning", "stubby roots", "shallow roots"],
        "supports": [
            "Roots are stubby, pruned, sparse, or weak without a clear irrigation-only explanation.",
            "Symptoms intensify under heat or dry-down.",
            "Patches persist after reasonable water, fertility, and disease corrections."
        ],
        "rules_out": [
            "Nematology lab does not find damaging populations.",
            "Roots are healthy and symptoms map to another dominant pattern."
        ],
        "field_checks": [
            "Submit soil and roots from the margin of decline to a nematology lab.",
            "Compare roots from good, transition, and bad areas.",
            "Reduce secondary stress while waiting on lab confirmation."
        ],
    },
    "warm_season_greenup_recovery": {
        "label": "Warm-season slow green-up / recovery lag",
        "topics": [
            "zoysiagrass_spring_greenup_thatch_temperature",
            "bermudagrass_spring_dead_spot_transition_recovery",
            "warm_season_fall_hardening_winter_survival",
        ],
        "triggers": [
            "slow green up", "slow green-up", "green up", "green-up", "spring lag",
            "zoysia", "bermuda spring", "spring dead spot", "winter injury",
            "slow to recover in spring",
        ],
        "supports": [
            "Warm-season turf is lagging in spring where soils are cool, shaded, wet, or thatchy.",
            "Recovery depends on spread from healthy margins rather than instant green-up in dead centers.",
            "The same microsites stay behind after winter injury, traffic, or fall overgrowth."
        ],
        "rules_out": [
            "Turf is actively growing at normal speed and only color is lagging briefly after a cold snap.",
            "A clear disease, herbicide, or irrigation pattern explains the symptom better than seasonal lag."
        ],
        "field_checks": [
            "Compare soil warmth, thatch, moisture, and shade in slow and healthy areas.",
            "Inspect crowns and stolons to separate living lagging turf from true dead tissue.",
            "Review fall nitrogen, winter drainage, and early spring traffic history."
        ],
    },
    "water_quality_chemistry": {
        "label": "Water-quality chemistry stress",
        "topics": [
            "reclaimed_water_nutrient_credit_salt_balance",
            "gypsum_sar_dispersion_decision_logic",
            "soil_ph_buffering_acidification_programs",
        ],
        "triggers": [
            "water quality", "reclaimed water", "effluent water", "sar",
            "gypsum", "alkalinity", "chloride", "source water", "chemistry",
            "stress pattern",
        ],
        "supports": [
            "Symptoms track irrigation source, chemistry reports, or heavily irrigated zones.",
            "Water tests show salinity, sodium, alkalinity, or nutrient load concerns.",
            "Growth and color responses change with source-water shifts or leaching cycles."
        ],
        "rules_out": [
            "Water chemistry is normal and symptoms are explained better by traffic, shade, or a clear disease pattern.",
            "The issue resolves fully with simple moisture correction and no chemistry signal."
        ],
        "field_checks": [
            "Pull current irrigation-water analysis, not only old historical tests.",
            "Compare rootzone EC, pH, infiltration, and color on the most heavily irrigated areas.",
            "Separate nutrient-credit questions from salt-hazard questions before adjusting fertility."
        ],
    },
    "nematode_sampling_interpretation": {
        "label": "Nematode sampling / interpretation issue",
        "topics": [
            "nematode_lab_interpretation_threshold_context",
            "nematicide_expectation_root_recovery_logic",
        ],
        "triggers": [
            "nematode sample", "nematode assay", "nematode report", "nematode counts",
            "nematicide working", "after nematicide", "nematicide recovery",
        ],
        "supports": [
            "The question is really about how to read counts, species, or expected recovery rather than only whether nematodes exist.",
            "Roots are weak and the field picture needs to be tied back to the lab report.",
            "Recovery is being judged too quickly after a nematicide or root-protection program."
        ],
        "rules_out": [
            "No assay or sampling information is available and the issue is still purely a field differential.",
            "A clearer water, disease, or traffic pattern explains the symptoms without needing lab interpretation."
        ],
        "field_checks": [
            "Review how the sample was pulled and whether healthy and bad areas were both represented.",
            "Compare current root condition with the species and counts on the lab report.",
            "Judge response by root recovery trend, not just immediate color."
        ],
    },
    "herbicide_carryover_transition": {
        "label": "Herbicide carryover / transition risk",
        "topics": [
            "herbicide_mode_of_action_injury_patterns",
            "herbicide_carryover_residual_transition_risk",
        ],
        "triggers": [
            "carryover", "residual herbicide", "reseeding after herbicide",
            "transition failure after herbicide", "spray overlap", "bleaching pattern",
        ],
        "supports": [
            "Poor establishment or transition lines up with residual herbicide history or application zones.",
            "Seedlings or sensitive turf are affected more than mature turf nearby.",
            "Pattern and symptom type fit herbicide physiology better than disease or fertility."
        ],
        "rules_out": [
            "There is no meaningful spray history and the issue maps better to moisture or traffic.",
            "Untreated comparison areas decline the same way."
        ],
        "field_checks": [
            "Review product, rate, timing, rainfall, and reseeding interval history.",
            "Map whether injury follows overlaps, drift, or residual zones.",
            "Compare seedling response with mature turf and unaffected areas."
        ],
    },
    "insect_feeding_pattern": {
        "label": "Insect feeding pattern / life-stage issue",
        "topics": [
            "annual_bluegrass_weevil_lifecycle_threshold_timing",
            "white_grub_species_threshold_recovery_logic",
            "sod_webworm_cutworm_night_feeding_diagnostics",
            "chinch_bug_heat_drought_interaction_model",
        ],
        "triggers": [
            "grub", "grubs", "abw", "annual bluegrass weevil", "webworm", "cutworm",
            "chinch bug", "soap flush", "animal digging", "night feeding",
        ],
        "supports": [
            "The symptom pattern points toward feeding site, life stage, or scouting timing rather than a generic stress event.",
            "Damage timing lines up with known insect windows or night activity.",
            "The question is really about confirming the insect and stage before acting."
        ],
        "rules_out": [
            "No feeding evidence, insects, or timing fit the pattern.",
            "The decline maps more cleanly to disease, drought, or chemistry without insect confirmation."
        ],
        "field_checks": [
            "Open stems, crowns, thatch, or soil where the pattern is strongest.",
            "Use the right scouting method for the suspected pest and timing window.",
            "Confirm the feeding site before treating root, crown, or foliar damage as the same problem."
        ],
    },
    "species_fit_renovation": {
        "label": "Species fit / renovation decision",
        "topics": [
            "species_fit_surface_region_tradeoff_model",
            "renovation_vs_rescue_program_decision_model",
        ],
        "triggers": [
            "species fit", "wrong grass", "wrong species", "renovation", "convert this area",
            "keep rescuing", "phase renovation", "bad fit for this surface",
            "rescue program", "fit problem", "another rescue program",
        ],
        "supports": [
            "The same surface fails repeatedly under the same regional and management pressures.",
            "Another species or area is clearly performing better under the same constraints.",
            "The question is whether to keep rescuing or rethink the underlying fit."
        ],
        "rules_out": [
            "The issue is a short-term tactical miss rather than a repeating fit problem.",
            "There is not yet enough multi-season evidence to frame it as renovation versus rescue."
        ],
        "field_checks": [
            "Compare recurring failure zones with better-performing species or microsites.",
            "Review the rescue burden across several seasons, not just one month.",
            "List the limiting factors: shade, traffic, water, winter injury, labor, and rootzone."
        ],
    },
    "overseeded_transition_competition": {
        "label": "Overseed transition / bermuda competition",
        "topics": ["overseeded_ryegrass_transition_competition_model"],
        "triggers": [
            "overseed", "overseeded", "ryegrass hanging on", "ryegrass is hanging on", "transition competition",
            "spring transition", "bermuda transition", "ryegrass not transitioning",
            "transition is stuck", "bermuda transition is stuck", "hanging on too long",
        ],
        "supports": [
            "Ryegrass is persisting while bermudagrass recovery is slow or uneven.",
            "The weakest transition zones are shaded, compacted, wet, or traffic-heavy.",
            "Spring nitrogen, irrigation, or cool weather may be favoring ryegrass persistence."
        ],
        "rules_out": [
            "There is no overseeded ryegrass present or bermudagrass is already recovering strongly.",
            "A clear disease, herbicide, or winterkill pattern explains the issue better than species competition."
        ],
        "field_checks": [
            "Compare ryegrass density and bermudagrass spread in warm, cool, trafficked, and shaded areas.",
            "Review spring nitrogen, irrigation frequency, and surface use during the transition window.",
            "Check whether slow areas are also compacted or slower to warm."
        ],
    },
    "seedling_establishment_failure": {
        "label": "Seedling establishment failure stack",
        "topics": ["seedling_establishment_temperature_moisture_oxygen_balance"],
        "triggers": [
            "establishment failure", "seedlings dying", "germination then dies",
            "stand collapse", "new seed not taking", "seedling rooting failure",
            "germination looked fine", "after emergence",
        ],
        "supports": [
            "Initial germination occurred, but density collapsed during early rooting and survival.",
            "The pattern follows wetness, crusting, sealing, irrigation, or early traffic more than seed spread.",
            "Seedlings are shallow-rooted or easy to pull from the surface."
        ],
        "rules_out": [
            "There was little to no germination to begin with, suggesting a different establishment problem.",
            "A stronger residual chemistry or disease signal explains the failure more directly."
        ],
        "field_checks": [
            "Inspect seedling rooting depth and seed-soil contact in healthy and failed zones.",
            "Check moisture by depth, surface sealing, and whether traffic entered too early.",
            "Review salinity, residual chemistry, and water quality if the seedbed picture is incomplete."
        ],
    },
    "application_pattern_coverage": {
        "label": "Application pattern / coverage issue",
        "topics": ["sprayer_coverage_nozzle_pressure_canopy_deposition"],
        "triggers": [
            "spray pass", "spray passes", "nozzle overlap", "overlap band",
            "coverage issue", "application pattern", "streaking after spray",
        ],
        "supports": [
            "Symptoms line up with passes, skips, overlaps, or other spray geometry.",
            "The issue looks more like delivery quality than a broad agronomic stress pattern.",
            "Pattern checks or setup review are more informative than changing products blindly."
        ],
        "rules_out": [
            "The symptom follows topography, traffic, or irrigation instead of application lines.",
            "No meaningful application pattern can be mapped."
        ],
        "field_checks": [
            "Map the symptom against passes, edges, overlaps, and skips.",
            "Review nozzle type, pressure, speed, boom height, and carrier volume together.",
            "Use pattern verification before calling it chemistry failure."
        ],
    },
    "mechanical_stress_budget": {
        "label": "Mechanical stress budget overload",
        "topics": ["roller_frequency_mechanical_stress_budget"],
        "triggers": [
            "repeated rolling", "rolling frequency", "greens beat up",
            "after rolling", "tournament prep stress", "conditioning pressure",
        ],
        "supports": [
            "The decline lines up with repeated rolling, mowing intensity, or event preparation.",
            "Most-stressed greens show the issue first while stronger greens lag behind.",
            "Recovery improves when mechanical intensity backs off."
        ],
        "rules_out": [
            "Mechanical practices were light and the symptom maps more cleanly to moisture, disease, or chemistry.",
            "There is no recent increase in conditioning or traffic pressure."
        ],
        "field_checks": [
            "Add up mowing, rolling, weather, and traffic as one stress stack.",
            "Compare clipping yield and canopy rebound on strong versus weak greens.",
            "Check whether backing off rolling changes the trend."
        ],
    },
    "cut_quality_leaf_shredding": {
        "label": "Cut quality / leaf shredding issue",
        "topics": ["mower_sharpness_leaf_shredding_disease_mimic_model"],
        "triggers": [
            "frayed leaf tips", "leaf shredding", "cut quality", "dull reels",
            "after mowing", "shredded tips", "gray tips after mowing",
            "mower injury", "foliar disease", "tell mower injury", "mower injury from foliar disease",
        ],
        "supports": [
            "The symptom lines up with mowing timing and torn leaf tissue.",
            "Leaf-tip appearance looks mechanical before it looks pathological.",
            "The issue is strongest on the most aggressively mowed surfaces."
        ],
        "rules_out": [
            "Leaf tissue is cleanly cut and the symptom follows a clear disease or chemistry pattern instead.",
            "There is no mowing-timing relationship."
        ],
        "field_checks": [
            "Inspect leaf tips immediately after mowing with a hand lens.",
            "Check reel, bedknife, and setup on the unit used.",
            "Compare whether correcting cut quality changes the symptom trend."
        ],
    },
    "topdressing_program_drift": {
        "label": "Topdressing program drift / layering issue",
        "topics": ["topdressing_organic_matter_dilution_layering_drift"],
        "triggers": [
            "topdressing drift", "sand compatibility", "layering after topdressing",
            "surface softer after topdressing", "organic matter dilution slipping",
        ],
        "supports": [
            "Surface behavior changed after sand source, cadence, or integration changed.",
            "The symptom looks cumulative and physical rather than like one sudden event.",
            "Firmness and moisture consistency are no longer matching the intended topdressing program."
        ],
        "rules_out": [
            "Material and cadence stayed consistent and the problem maps more clearly to water or traffic.",
            "Profile inspection does not support layering or program drift."
        ],
        "field_checks": [
            "Review sand source, interval discipline, and incorporation consistency.",
            "Inspect the profile for new near-surface layering.",
            "Compare firmness and moisture behavior against previous stable periods."
        ],
    },
}


def answer_advanced_diagnosis(question: str, course_profile: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Return a structured differential diagnosis for symptom-style questions."""
    q = (question or "").lower()
    if not q or _looks_like_product_decision(q):
        return None

    scored = _score_buckets(q)
    if not scored:
        return None
    if not _looks_like_diagnosis(q) and scored[0][0] < 10:
        return None

    top = _select_top_buckets(scored)
    science = load_advanced_turf_science()
    topic_keys = []
    for _, _, bucket in top:
        for topic in bucket["topics"]:
            if topic in science and topic not in topic_keys:
                topic_keys.append(topic)

    answer = _build_diagnostic_answer(q, top, topic_keys, science, course_profile or {})
    return {
        "answer": answer,
        "sources": [{
            "name": "Advanced Diagnosis Framework",
            "type": "structured_kb",
            "topics": topic_keys,
        }],
        "confidence": {"score": 91, "label": "Advanced Diagnosis"},
        "needs_review": False,
        "kb_verdict": "advanced_diagnosis",
        "diagnostic_buckets": [bucket["label"] for _, _, bucket in top],
        "advanced_science_topics": topic_keys,
        "grounding": {"verified": True, "issues": []},
    }


def _looks_like_product_decision(question_lower: str) -> bool:
    return any(_contains_term(question_lower, term) for term in PRODUCT_DECISION_TERMS)


def _contains_term(question_lower: str, term: str) -> bool:
    escaped = re.escape(str(term or "").lower().strip())
    if not escaped:
        return False
    prefix = r"\b" if str(term or "")[:1].isalnum() else ""
    suffix = r"\b" if str(term or "")[-1:].isalnum() else ""
    return re.search(prefix + escaped + suffix, question_lower) is not None


def _looks_like_diagnosis(question_lower: str) -> bool:
    science_first_patterns = [
        "what causes bentgrass to decline in summer",
        "what causes poa annua to decline faster than bentgrass in summer",
        "what does high clip volume mean",
        "what should i know about abw timing",
        "how should i think about abw timing",
    ]
    if any(pattern in question_lower for pattern in science_first_patterns):
        return False

    strong_intent = [
        "diagnose", "diagnosis", "what is causing", "what's causing",
        "what causes", "why are", "why is", "why did", "why do", "why does", "how do i tell",
        "how do i know if",
        "how should i diagnose", "is this", "could this be", "could this", "could", "separate",
        "walk me through", "blamed disease", "before you blamed disease", "where do you start",
        "thinking about first",
        "versus", " vs ",
    ]
    symptom_terms = [
        "symptom", "symptoms", "decline", "thinning", "thin", "wilt",
        "wilting", "spots", "patches", "yellowing", "brown", "roots look",
        "shallow roots", "dying", "tired", "soft wet spots", "soft spots", "flat",
    ]
    if any(term in question_lower for term in strong_intent):
        return True
    return sum(1 for term in symptom_terms if term in question_lower) >= 2


def _score_buckets(question_lower: str) -> list[tuple[int, str, dict[str, Any]]]:
    scored = []
    for key, bucket in DIAGNOSTIC_BUCKETS.items():
        score = 0
        for trigger in bucket["triggers"]:
            if trigger in question_lower:
                score += 6 if len(trigger) > 8 else 3
        for topic in bucket["topics"]:
            for alias in SCIENCE_TOPIC_ALIASES.get(topic, []):
                if alias in question_lower:
                    score += 4
        score += _token_overlap(question_lower, bucket["label"])
        if score:
            scored.append((score, key, bucket))
    return sorted(scored, key=lambda item: item[0], reverse=True)


def _select_top_buckets(scored: list[tuple[int, str, dict[str, Any]]]) -> list[tuple[int, str, dict[str, Any]]]:
    if not scored:
        return []
    selected = [scored[0]]
    top_score, top_key, _ = scored[0]
    for item in scored[1:]:
        if len(selected) >= 3:
            break
        score, key, _ = item
        if top_key == "root_disease_pythium" and key == "wet_wilt_root_oxygen" and score >= 4:
            selected.append(item)
            continue
        if top_key == "wet_wilt_root_oxygen" and key == "disease_microclimate" and score >= 4:
            selected.append(item)
            continue
        if score < 6:
            continue
        if score < (top_score - 4) and score < max(8, int(top_score * 0.7)):
            continue
        selected.append(item)
    return selected


def _token_overlap(question_lower: str, text: str) -> int:
    q_tokens = set(re.findall(r"[a-z0-9]+", question_lower))
    text_tokens = set(re.findall(r"[a-z0-9]+", text.lower()))
    return min(len(q_tokens & {token for token in text_tokens if len(token) > 4}), 4)


def _build_diagnostic_answer(
    question_lower: str,
    top: list[tuple[int, str, dict[str, Any]]],
    topic_keys: list[str],
    science: dict[str, Any],
    profile: dict[str, Any],
) -> str:
    parts = [
        "**Bottom Line:** Treat this as a differential diagnosis, not a one-cause call. "
        "The first pass is to separate water/oxygen, pathogen, root, chemistry, and stress-pattern evidence before applying products or adding water."
    ]

    profile_note = _profile_note(profile)
    if profile_note:
        parts.append(f"**Why it matters here:** {profile_note}")

    first_checks = []
    for _, _, bucket in top:
        for check in bucket["field_checks"]:
            if check not in first_checks:
                first_checks.append(check)
    parts.append(_bullet_section("What I'd do first today", first_checks, limit=3))

    likely_lines = []
    for _, _, bucket in top:
        likely_lines.append(f"- **{bucket['label']}**")
        likely_lines.extend(f"  - Supports: {item}" for item in bucket["supports"][:2])
        likely_lines.extend(f"  - Rules out: {item}" for item in bucket["rules_out"][:1])
    parts.append("**Most Likely Buckets:**\n" + "\n".join(likely_lines))

    field_checks = list(first_checks)
    parts.append(_bullet_section("Field Checks To Do Today", field_checks, limit=7))

    decision_triggers = _decision_triggers(top)
    if decision_triggers:
        parts.append(_bullet_section("Decision Triggers", decision_triggers, limit=5))

    lab_triggers = _lab_triggers(question_lower, top)
    if lab_triggers:
        parts.append(_bullet_section("Lab Or Sample Triggers", lab_triggers, limit=5))

    kb_lines = []
    for topic_key in topic_keys[:5]:
        record = science.get(topic_key, {})
        if record.get("principle"):
            kb_lines.append(f"- **{topic_key.replace('_', ' ')}:** {record['principle']}")
    if kb_lines:
        parts.append("**Relevant Science Records:**\n" + "\n".join(kb_lines))

    parts.append(
        "**What Not To Do Yet:**\n"
        "- Do not add blanket irrigation until moisture-by-depth and root oxygen are checked.\n"
        "- Do not make a fungicide or nematicide call from canopy symptoms alone.\n"
        "- Do not chase color with nitrogen until roots, water distribution, and chemistry are ruled in or out."
    )
    parts.append(
        "**Fastest way to sharpen this call:**\n"
        "- Tell me the surface, turf, pattern, root condition, moisture-by-depth picture, and whether you see lesions or obvious mechanical injury."
    )
    parts.append(
        "**If you need a product call next:** I will only recommend one when the verified product KB has label-backed support."
    )
    return "\n\n".join(parts)


def _profile_note(profile: dict[str, Any]) -> str:
    known = summarize_known_profile_for_questions(profile=profile)
    inferred = infer_regional_management_context(profile)
    notes = []
    if known:
        notes.append(f"I am using your saved context ({known}).")
    if inferred.get("regional_archetype"):
        notes.append(f"Regionally, this maps to {inferred['regional_archetype']}.")
    return " ".join(notes)


def _lab_triggers(question_lower: str, top: list[tuple[int, str, dict[str, Any]]]) -> list[str]:
    labels = {key for _, key, _ in top}
    triggers = []
    if "root_disease_pythium" in labels or "nematode_root_pruning" in labels:
        triggers.append("Submit roots and soil from healthy, transition, and declining areas to a diagnostic lab.")
    if "disease_microclimate" in labels:
        triggers.append("Send a fresh symptomatic sample when lesions/signs are unclear or disease is spreading despite reasonable cultural correction.")
    if "chemistry_nutrient_salinity" in labels:
        triggers.append("Run irrigation-water and soil chemistry tests before acidification, gypsum, or micronutrient correction.")
    if "wet_wilt_root_oxygen" in labels and "pythium" in question_lower:
        triggers.append("Pair a physical rootzone check with a pathogen lab submission so wet wilt is not mistaken for disease-only decline.")
    return triggers


def _decision_triggers(top: list[tuple[int, str, dict[str, Any]]]) -> list[str]:
    labels = {key for _, key, _ in top}
    triggers = []
    if "species_fit_renovation" in labels:
        triggers.extend([
            "Recurring failure in the same environment after multiple rescue attempts pushes this toward species fit instead of another short-term rescue.",
            "If the rescue burden keeps rising while the surface still underperforms, compare renovation versus continued rescue before stacking more inputs.",
        ])
    return triggers


def _bullet_section(title: str, items: list[str], limit: int = 5) -> str:
    if not items:
        return ""
    return f"**{title}:**\n" + "\n".join(f"- {item}" for item in items[:limit])
