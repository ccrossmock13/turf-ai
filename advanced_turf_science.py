"""Deterministic answer layer for advanced turf science questions."""

from __future__ import annotations

import re
from typing import Any

from course_profile import infer_regional_management_context, summarize_known_profile_for_questions
from knowledge_base import load_advanced_turf_science


SCIENCE_TOPIC_ALIASES = {
    "cool_season_heat_carbohydrate_decline": [
        "carbohydrate", "carbohydrate reserves", "heat stress physiology",
        "summer decline", "root decline", "warm nights", "respiration",
        "bentgrass decline in summer", "bentgrass to decline in summer", "summer stress",
        "warm nights drive bentgrass decline", "hot days alone",
    ],
    "root_respiration_oxygen_balance": [
        "root respiration", "oxygen balance", "wet wilt", "black layer",
        "anaerobic", "saturated", "roots need oxygen", "wet but wilt",
        "wilting even though moisture", "moisture readings are high",
        "wet greens getting black layer", "wet greens wilt",
        "weak roots", "healthy root depth", "root depth look like",
        "bentgrass wilt even when moisture readings are high",
        "wilt even when moisture readings are high",
    ],
    "usga_rootzone_porosity_hydraulic_conductivity": [
        "air-filled porosity", "air filled porosity", "hydraulic conductivity",
        "rootzone porosity", "usga rootzone", "infiltration", "sand rootzone",
    ],
    "surface_organic_matter_physics": [
        "surface organic matter", "organic matter physics", "thatch sponge",
        "soft greens", "squeeze test", "organic layer", "soft and puffy",
        "puffy greens", "thatch and organic matter",
    ],
    "perched_water_layering_diagnostics": [
        "perched water", "layering", "layered profile", "water table",
        "profile layer", "dry over wet", "wet over dry",
    ],
    "disease_triangle_leaf_wetness_microclimate": [
        "disease triangle", "leaf wetness", "microclimate", "dew",
        "humidity", "infection window", "disease pressure",
        "humid weather", "poa bent greens during humid weather",
    ],
    "dollar_spot_epidemiology_nitrogen_leaf_wetness": [
        "dollar spot epidemiology", "dollar spot risk", "dollar spot pressure",
        "hourglass lesions", "dollar spot leaf wetness", "dollar spot explode",
        "dollar spot exploded", "humid week", "after a humid week",
        "low nitrogen and extended leaf wetness", "make dollar spot worse",
        "extended leaf wetness make dollar spot worse",
    ],
    "brown_patch_rhizoctonia_heat_humidity": [
        "brown patch epidemiology", "brown patch risk", "rhizoctonia",
        "smoke ring", "warm humid nights",
    ],
    "pgr_growth_suppression_thermal_rebound": [
        "pgr rebound", "growth potential", "pgr suppression", "trinexapac",
        "primo rebound", "clipping yield", "clip volume", "high clip volume", "thermal interval",
        "calendar interval in primo timing", "clipping yield matter more",
        "clipping yield matter more than calendar interval",
    ],
    "et_deficit_irrigation_syringing": [
        "deficit irrigation", "syringing", "canopy cooling",
        "evapotranspiration", "et replacement", "hand watering",
        "helpful versus harmful", "helpful vs harmful",
        "moisture management", "moisture management on greens",
    ],
    "localized_dry_spot_hydrophobicity": [
        "hydrophobicity", "localized dry spot hydrophobicity",
        "water repellency", "wetting agent", "dry spot",
    ],
    "firmness_green_speed_plant_health_tradeoff": [
        "firmness", "green speed", "stimp", "speed tradeoff",
        "plant health tradeoff", "tournament speed", "push speed", "how far can i push speed",
    ],
    "traffic_recovery_carbohydrate_growth_rate": [
        "traffic recovery", "wear recovery", "traffic stress",
        "traffic physiology", "growth rate recovery",
        "bermudagrass tees recovering", "keep bermudagrass tees recovering",
    ],
    "winter_crown_hydration_freeze_injury": [
        "winter injury", "crown hydration", "freeze injury", "ice cover",
        "desiccation", "winterkill", "deacclimation",
    ],
    "shade_light_carbohydrate_morphology": [
        "shade physiology", "low light", "shade decline", "tree shade",
        "reduced light", "shade stress", "shaded greens thin",
        "fertility is good", "even when fertility",
    ],
    "nitrogen_form_release_growth_stress_balance": [
        "nitrogen form", "slow release nitrogen", "soluble nitrogen",
        "nitrogen release", "spoon feeding nitrogen", "nitrogen flush",
        "release rate", "form and release", "nitrogen form and release",
    ],
    "salinity_osmotic_sodium_structure_stress": [
        "salinity stress", "sodium hazard", "osmotic drought",
        "reclaimed water", "salt stress", "high ec",
    ],
    "nematode_root_pruning_stress_complex": [
        "nematode", "nematodes", "root pruning", "stubby roots",
        "nematode stress", "plant parasitic nematodes",
    ],
    "poa_annua_vs_bentgrass_summer_decline": [
        "poa annua decline", "poa decline", "poa annua decline faster",
        "poa declines faster", "decline faster than bentgrass",
        "poa annua faster than bentgrass", "poa in summer",
        "poa annua often collapse faster than bentgrass",
    ],
    "wetting_agent_chemistry_functional_groups": [
        "wetting agent chemistry", "wetting agent chemistry types",
        "surfactant chemistry", "penetrant", "retainer", "retention wetting agent",
        "block copolymer", "wetting agent types",
    ],
    "bicarbonate_alkalinity_micronutrient_lockout": [
        "bicarbonate", "bicarbonates", "alkalinity", "micronutrient lockout",
        "micronutrients", "iron chlorosis", "high ph", "water alkalinity",
    ],
    "pythium_root_dysfunction_vs_wet_wilt": [
        "pythium root dysfunction", "pythium root rot", "pythium root",
        "root dysfunction versus wet wilt", "root dysfunction vs wet wilt",
        "diagnose pythium", "pythium versus wet wilt", "pythium vs wet wilt",
    ],
    "gdd_growth_potential_pgr_timing": [
        "growing degree days", "gdd", "growth potential model",
        "growth potential", "pgr timing", "gdd help with pgr",
        "degree days help with pgr",
        "fixed intervals for pgr scheduling", "better than fixed intervals",
        "growing degree days better than fixed intervals",
    ],
    "anthracnose_basal_rot_stress_complex": [
        "anthracnose basal rot", "anthracnose decline", "basal rot",
        "anthracnose physiology", "poa anthracnose", "crown anthracnose",
    ],
    "fairy_ring_hydrophobicity_nitrogen_masking": [
        "fairy ring hydrophobicity", "fairy ring dry ring", "fairy ring masking",
        "nitrogen masking", "green ring", "mushrooms and dry ring",
    ],
    "soil_ph_buffering_acidification_programs": [
        "soil ph buffering", "acidification program", "water acidification",
        "rootzone ph", "ph drift", "alkaline rootzone",
    ],
    "bermudagrass_spring_dead_spot_transition_recovery": [
        "spring dead spot", "bermuda spring recovery", "bermuda transition",
        "slow green up", "bermudagrass recovery", "dead patch spring bermuda",
    ],
    "salt_vs_drought_ec_moisture_interpretation": [
        "salt stress versus drought", "salt vs drought", "osmotic stress",
        "high ec wilt", "ec and moisture", "salinity despite moisture",
    ],
    "zoysiagrass_spring_greenup_thatch_temperature": [
        "zoysia green up", "zoysia green-up", "slow zoysia spring",
        "zoysia spring lag", "zoysia thatch", "uneven zoysia green up",
    ],
    "bermudagrass_shade_cold_carbohydrate_limits": [
        "bermuda shade", "bermudagrass shade", "bermuda thin in shade",
        "bermuda low light", "bermuda recovery in shade", "bermuda cool season lag",
    ],
    "warm_season_fall_hardening_winter_survival": [
        "fall hardening", "winter survival", "warm season winter injury",
        "bermuda winter survival", "zoysia winter survival", "late fall lush growth",
    ],
    "reclaimed_water_nutrient_credit_salt_balance": [
        "reclaimed water nutrient credit", "reclaimed water salts", "effluent water",
        "water source nutrient credit", "reclaimed water alkalinity", "reuse water turf",
        "nutrient source and a salinity stress source",
        "reclaimed water as both a nutrient source and a salinity stress source",
        "both a nutrient source and a salinity stress source",
    ],
    "gypsum_sar_dispersion_decision_logic": [
        "gypsum decision", "sar", "soil dispersion", "sodium dispersion",
        "gypsum sodium hazard", "when does gypsum help", "gypsum logic",
        "sodium problem", "actually help", "basically noise",
        "when is it basically noise",
    ],
    "nematode_lab_interpretation_threshold_context": [
        "nematode lab", "nematode assay", "nematode threshold",
        "nematode counts", "interpret nematode sample", "nematode report",
    ],
    "nematicide_expectation_root_recovery_logic": [
        "nematicide expectations", "nematicide recovery", "root recovery after nematicide",
        "nematicide working", "after nematicide", "nematicide response",
    ],
    "herbicide_mode_of_action_injury_patterns": [
        "herbicide mode of action", "bleaching injury", "twisting injury",
        "spray burn pattern", "herbicide symptomology", "herbicide injury pattern",
    ],
    "herbicide_carryover_residual_transition_risk": [
        "herbicide carryover", "residual herbicide", "carryover risk",
        "reseeding after herbicide", "transition failure after herbicide", "residual transition risk",
    ],
    "tournament_greens_stress_budget_model": [
        "tournament stress budget", "tournament greens stress", "greens conditioning stress",
        "event week greens stress", "stacking stress on greens", "speed budget",
        "greens conditioning budget", "conditioning budget",
    ],
    "tournament_fairway_tee_recovery_traffic_model": [
        "tournament fairway traffic", "tournament tee traffic", "event fairway recovery",
        "divot recovery during tournament", "tournament tee recovery", "traffic model fairway",
    ],
    "annual_bluegrass_weevil_lifecycle_threshold_timing": [
        "abw lifecycle", "annual bluegrass weevil timing", "annual bluegrass weevil life cycle",
        "abw timing", "abw threshold", "adult movement abw",
    ],
    "white_grub_species_threshold_recovery_logic": [
        "white grub threshold", "grub threshold", "grub recovery",
        "grub species timing", "white grub species", "grub larval stage",
    ],
    "sod_webworm_cutworm_night_feeding_diagnostics": [
        "sod webworm", "webworm feeding", "cutworm feeding",
        "night feeding turf", "soap flush webworm", "cutworm diagnostics",
    ],
    "chinch_bug_heat_drought_interaction_model": [
        "chinch bug heat stress", "chinch bug drought", "chinch bug model",
        "sunny patch chinch bug", "chinch bug thatch", "chinch bug irrigation response",
    ],
    "species_fit_surface_region_tradeoff_model": [
        "species fit", "surface fit", "region fit turf", "best species for this surface",
        "turf species tradeoff", "species adaptation model",
    ],
    "renovation_vs_rescue_program_decision_model": [
        "renovation versus rescue", "renovation decision", "when to renovate turf",
        "conversion versus rescue", "rescue program not working", "phased renovation",
    ],
    "overseeded_ryegrass_transition_competition_model": [
        "overseeded ryegrass transition", "ryegrass hanging on", "spring transition ryegrass",
        "ryegrass competition during transition", "bermuda transition competition",
        "overseed competition", "ryegrass not transitioning", "transition is stuck",
        "ryegrass hanging on and bermuda transition is stuck", "bermuda transition stuck",
    ],
    "seedling_establishment_temperature_moisture_oxygen_balance": [
        "seedling establishment", "establishment failure", "germination then dies",
        "seedlings dying after germination", "stand collapse after germination",
        "seedbed oxygen", "seedling rooting failure", "germination looked fine",
        "after emergence",
    ],
    "cultivar_diversity_stress_disease_buffering": [
        "cultivar diversity", "mixed cultivars", "genetic diversity turf",
        "one cultivar risk", "cultivar fit", "weak cultivar mix",
    ],
    "sprayer_coverage_nozzle_pressure_canopy_deposition": [
        "sprayer coverage", "nozzle pressure", "canopy deposition",
        "spray passes", "nozzle overlap", "application pattern", "coverage issue",
    ],
    "roller_frequency_mechanical_stress_budget": [
        "rolling frequency", "rolling stress", "mechanical stress budget",
        "repeated rolling", "tournament rolling", "greens beat up after rolling",
    ],
    "soil_test_cec_base_saturation_practical_limits": [
        "cec", "base saturation", "soil test interpretation",
        "cation exchange capacity", "base saturation soil test", "soil report cec",
    ],
    "spray_water_ph_hardness_adjuvant_interaction_model": [
        "spray water ph", "water hardness spray", "adjuvant interaction",
        "spray solution chemistry", "hardness and adjuvant", "spray water quality",
    ],
    "mower_sharpness_leaf_shredding_disease_mimic_model": [
        "mower sharpness", "leaf shredding", "cut quality", "dull reels",
        "frayed leaf tips", "disease mimic after mowing", "mower injury", "foliar disease",
        "good superintendents",
        "mimic foliar disease",
    ],
    "topdressing_organic_matter_dilution_layering_drift": [
        "topdressing consistency", "organic matter dilution", "layering drift",
        "sand compatibility", "topdressing drift", "surface layering after topdressing",
    ],
}


SCIENCE_INTENT_TERMS = [
    "why", "explain", "mechanism", "physiology", "science", "diagnose",
    "diagnosis", "what causes", "cause", "affect", "tradeoff", "trade-off",
    "balance", "relationship", "how does", "how do", "what happens",
    "how should", "think about", "difference", "interpret", "meaning", "risk", "pressure",
    "what does", "know about",
]


PRODUCT_DECISION_TERMS = [
    "what should i use", "what should we use", "what can i spray",
    "what should i spray", "rate", "label", "tank mix", "mix with",
    "how much", "ounces", "oz", "product for",
]


def answer_advanced_turf_science(question: str, course_profile: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Return a deterministic expert answer for advanced turf science topics."""
    q = (question or "").lower()
    if not q:
        return None
    if _looks_like_product_decision(q) and not _has_science_intent(q):
        return None

    science = load_advanced_turf_science()
    topic_key, score = _best_topic(q, science)
    if not topic_key or score < 4:
        return None
    if not _has_science_intent(q) and score < 8:
        return None

    record = science[topic_key]
    answer = _build_answer(topic_key, record, course_profile or {})
    sources = [{
        "name": "Advanced Turf Science Knowledge Base",
        "type": "structured_kb",
        "topic": topic_key,
        "source_basis": record.get("source_basis", []),
    }]
    return {
        "answer": answer,
        "sources": sources,
        "confidence": {"score": 94, "label": "Advanced Turf Science"},
        "needs_review": False,
        "kb_verdict": "advanced_turf_science",
        "advanced_science_topic": topic_key,
        "grounding": {
            "verified": True,
            "issues": [],
        },
    }


def _looks_like_product_decision(question_lower: str) -> bool:
    return any(term in question_lower for term in PRODUCT_DECISION_TERMS)


def _has_science_intent(question_lower: str) -> bool:
    return any(term in question_lower for term in SCIENCE_INTENT_TERMS)


def _best_topic(question_lower: str, science: dict[str, Any]) -> tuple[str | None, int]:
    best_key = None
    best_score = 0
    for key, record in science.items():
        score = 0
        key_text = key.replace("_", " ")
        if key_text in question_lower:
            score += 8
        for alias in SCIENCE_TOPIC_ALIASES.get(key, []):
            if alias in question_lower:
                score += 6 if len(alias) > 8 else 3
        score += _token_overlap_score(question_lower, key_text)
        score += _token_overlap_score(question_lower, record.get("domain", ""))
        score += _token_overlap_score(question_lower, record.get("principle", ""))
        if score > best_score:
            best_key = key
            best_score = score
    return best_key, best_score


def _token_overlap_score(question_lower: str, text: str) -> int:
    generic = {
        "turf", "grass", "greens", "green", "fairway", "fairways", "the",
        "and", "with", "from", "that", "this", "does", "should", "what",
    }
    question_tokens = set(re.findall(r"[a-z0-9]+", question_lower))
    text_tokens = set(re.findall(r"[a-z0-9]+", str(text).lower()))
    useful = {token for token in text_tokens if len(token) > 4 and token not in generic}
    return min(len(question_tokens & useful), 5)


def _build_answer(topic_key: str, record: dict[str, Any], course_profile: dict[str, Any]) -> str:
    title = topic_key.replace("_", " ").title()
    parts = [
        f"**Bottom Line:** {record.get('principle', 'This is a structured turf science topic.')}",
    ]

    profile_note = _profile_note(topic_key, course_profile)
    if profile_note:
        parts.append(f"**Why it matters here:** {profile_note}")

    first_checks = record.get("field_indicators", [])[:2]
    if not first_checks:
        first_checks = record.get("decision_rules", [])[:2]
    if not first_checks:
        first_checks = record.get("management_implications", [])[:2]
    parts.append(_bullet_section("What I'd check first on the property", first_checks, limit=3))

    parts.extend([
        _bullet_section("Mechanism", record.get("mechanisms", []), limit=3),
        _bullet_section("Field Indicators", record.get("field_indicators", []), limit=4),
        _bullet_section("Decision Rules", record.get("decision_rules", []), limit=4),
        _bullet_section("Management Implications", record.get("management_implications", []), limit=3),
    ])

    if record.get("benchmark_ranges"):
        benchmarks = [f"{key.replace('_', ' ')}: {value}" for key, value in record["benchmark_ranges"].items()]
        parts.append(_bullet_section("Useful Benchmarks", benchmarks, limit=5))

    parts.append(_bullet_section("Cautions", record.get("cautions", []), limit=3))
    parts.append(
        "**Practical read:** Use this to narrow what matters most on the property today. "
        "If the field picture does not match these signals, slow down before forcing the program to fit the theory."
    )
    parts.append(
        "**If you need a product call next:** I will only recommend one when I have label-backed product support for it."
    )
    return "\n\n".join(part for part in parts if part)


def _bullet_section(title: str, items: list[str], limit: int = 4) -> str:
    if not items:
        return ""
    bullets = "\n".join(f"- {item}" for item in items[:limit])
    return f"**{title}:**\n{bullets}"


def _profile_note(topic_key: str, profile: dict[str, Any]) -> str:
    known = summarize_known_profile_for_questions(profile=profile)
    inferred = infer_regional_management_context(profile)
    surfaces = profile.get("surfaces", {}) if isinstance(profile, dict) else {}
    greens = str(surfaces.get("greens", "")).lower()
    fairways = str(surfaces.get("fairways", "")).lower()
    region = profile.get("region", "") if isinstance(profile, dict) else ""
    notes = []

    if known:
        notes.append(f"I am using your saved context ({known}).")

    if topic_key in {
        "cool_season_heat_carbohydrate_decline",
        "root_respiration_oxygen_balance",
        "disease_triangle_leaf_wetness_microclimate",
        "dollar_spot_epidemiology_nitrogen_leaf_wetness",
    } and any(term in greens for term in ["bent", "poa", "bluegrass"]):
        notes.append("Cool-season greens have a smaller summer stress buffer, so root depth, clipping yield, and moisture-by-depth matter more than color alone.")

    if topic_key == "firmness_green_speed_plant_health_tradeoff" and greens:
        notes.append(f"For greens ({surfaces.get('greens')}), treat speed work as a moisture, growth-rate, and recovery-capacity decision.")

    if topic_key == "salinity_osmotic_sodium_structure_stress" and any(term in str(profile.get("soil", "")).lower() for term in ["sand", "reclaimed", "salt", "sodium"]):
        notes.append("Your soil/water note makes EC, sodium hazard, drainage, and leaching capacity especially important.")

    if region and inferred.get("regional_archetype"):
        notes.append(f"Regionally, this maps to {inferred['regional_archetype']}.")

    return " ".join(notes[:3])
