"""
Knowledge base loader for structured turf management data.
Provides quick lookup for products, diseases, and reference tables.
"""
import json
import os
import logging
import re
from typing import Dict, Optional, List, Any
from functools import lru_cache

logger = logging.getLogger(__name__)

KNOWLEDGE_DIR = os.path.join(os.path.dirname(__file__), 'knowledge')
PRODUCT_OPTIONAL_FIELD_DEFAULTS = {
    "rei": "",
    "retreatment_interval": "",
    "irrigation_guidance": "",
    "rainfast": "",
    "tank_mix_guidance": [],
    "max_apps_per_year": "",
    "max_rate_per_app": "",
    "reseeding_interval": "",
    "overseeding_interval": "",
    "application_window_notes": "",
}


def _normalize_product_schema(products: Dict) -> Dict:
    normalized = {}
    for category, items in (products or {}).items():
        normalized[category] = {}
        for active_ingredient, info in (items or {}).items():
            normalized_info = dict(info or {})
            for field, default in PRODUCT_OPTIONAL_FIELD_DEFAULTS.items():
                if field not in normalized_info:
                    normalized_info[field] = list(default) if isinstance(default, list) else default
            normalized[category][active_ingredient] = normalized_info
    return normalized


@lru_cache(maxsize=1)
def load_products() -> Dict:
    """Load the products knowledge base."""
    try:
        with open(os.path.join(KNOWLEDGE_DIR, 'products.json'), 'r') as f:
            return _normalize_product_schema(json.load(f))
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
def load_weeds() -> Dict:
    """Load the weeds knowledge base."""
    try:
        with open(os.path.join(KNOWLEDGE_DIR, 'weeds.json'), 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load weeds.json: {e}")
        return {}


@lru_cache(maxsize=1)
def load_pests() -> Dict:
    """Load the insect pests knowledge base."""
    try:
        with open(os.path.join(KNOWLEDGE_DIR, 'pests.json'), 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load pests.json: {e}")
        return {}


@lru_cache(maxsize=1)
def load_turfgrasses() -> Dict:
    """Load the turfgrass species knowledge base."""
    try:
        with open(os.path.join(KNOWLEDGE_DIR, 'turfgrasses.json'), 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load turfgrasses.json: {e}")
        return {}


@lru_cache(maxsize=1)
def load_abiotic_stress() -> Dict:
    """Load the abiotic stress and non-pest diagnosis knowledge base."""
    try:
        with open(os.path.join(KNOWLEDGE_DIR, 'abiotic_stress.json'), 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load abiotic_stress.json: {e}")
        return {}


@lru_cache(maxsize=1)
def load_timing_windows() -> Dict:
    """Load timing window knowledge for seasonal turf decisions."""
    try:
        with open(os.path.join(KNOWLEDGE_DIR, 'timing_windows.json'), 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load timing_windows.json: {e}")
        return {}


@lru_cache(maxsize=1)
def load_fertility_programs() -> Dict:
    """Load structured fertility-program knowledge."""
    try:
        with open(os.path.join(KNOWLEDGE_DIR, 'fertility_programs.json'), 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load fertility_programs.json: {e}")
        return {}


@lru_cache(maxsize=1)
def load_irrigation_programs() -> Dict:
    """Load structured irrigation-program knowledge."""
    try:
        with open(os.path.join(KNOWLEDGE_DIR, 'irrigation_programs.json'), 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load irrigation_programs.json: {e}")
        return {}


@lru_cache(maxsize=1)
def load_cultivation_programs() -> Dict:
    """Load structured cultivation-program knowledge."""
    try:
        with open(os.path.join(KNOWLEDGE_DIR, 'cultivation_programs.json'), 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load cultivation_programs.json: {e}")
        return {}


@lru_cache(maxsize=1)
def load_diagnostic_frameworks() -> Dict:
    """Load structured diagnostic frameworks for turf troubleshooting."""
    try:
        with open(os.path.join(KNOWLEDGE_DIR, 'diagnostic_frameworks.json'), 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load diagnostic_frameworks.json: {e}")
        return {}


@lru_cache(maxsize=1)
def load_mowing_programs() -> Dict:
    """Load structured mowing and rolling program knowledge."""
    try:
        with open(os.path.join(KNOWLEDGE_DIR, 'mowing_programs.json'), 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load mowing_programs.json: {e}")
        return {}


@lru_cache(maxsize=1)
def load_salinity_management() -> Dict:
    """Load structured salinity and EC management knowledge."""
    try:
        with open(os.path.join(KNOWLEDGE_DIR, 'salinity_management.json'), 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load salinity_management.json: {e}")
        return {}


@lru_cache(maxsize=1)
def load_drainage_rootzone_programs() -> Dict:
    """Load structured drainage and rootzone-management knowledge."""
    try:
        with open(os.path.join(KNOWLEDGE_DIR, 'drainage_rootzone_programs.json'), 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load drainage_rootzone_programs.json: {e}")
        return {}


@lru_cache(maxsize=1)
def load_overseeding_transition_programs() -> Dict:
    """Load structured overseeding and transition program knowledge."""
    try:
        with open(os.path.join(KNOWLEDGE_DIR, 'overseeding_transition_programs.json'), 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load overseeding_transition_programs.json: {e}")
        return {}


@lru_cache(maxsize=1)
def load_disease_ipm_playbooks() -> Dict:
    """Load structured disease IPM playbooks."""
    try:
        with open(os.path.join(KNOWLEDGE_DIR, 'disease_ipm_playbooks.json'), 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load disease_ipm_playbooks.json: {e}")
        return {}


@lru_cache(maxsize=1)
def load_surface_management_recipes() -> Dict:
    """Load structured surface management recipes."""
    try:
        with open(os.path.join(KNOWLEDGE_DIR, 'surface_management_recipes.json'), 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load surface_management_recipes.json: {e}")
        return {}


@lru_cache(maxsize=1)
def load_climate_zone_playbooks() -> Dict:
    """Load structured climate-zone playbooks."""
    try:
        with open(os.path.join(KNOWLEDGE_DIR, 'climate_zone_playbooks.json'), 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load climate_zone_playbooks.json: {e}")
        return {}


@lru_cache(maxsize=1)
def load_tournament_prep_recovery() -> Dict:
    """Load structured tournament prep and recovery plans."""
    try:
        with open(os.path.join(KNOWLEDGE_DIR, 'tournament_prep_recovery.json'), 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load tournament_prep_recovery.json: {e}")
        return {}


@lru_cache(maxsize=1)
def load_nutrient_diagnostics() -> Dict:
    """Load structured nutrient-diagnostic knowledge."""
    try:
        with open(os.path.join(KNOWLEDGE_DIR, 'nutrient_diagnostics.json'), 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load nutrient_diagnostics.json: {e}")
        return {}


@lru_cache(maxsize=1)
def load_calibration_workflows() -> Dict:
    """Load structured sprayer and spreader calibration workflows."""
    try:
        with open(os.path.join(KNOWLEDGE_DIR, 'calibration_workflows.json'), 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load calibration_workflows.json: {e}")
        return {}


@lru_cache(maxsize=1)
def load_seasonal_operating_plans() -> Dict:
    """Load structured seasonal operating plans."""
    try:
        with open(os.path.join(KNOWLEDGE_DIR, 'seasonal_operating_plans.json'), 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load seasonal_operating_plans.json: {e}")
        return {}


@lru_cache(maxsize=1)
def load_regional_pressure_calendars() -> Dict:
    """Load structured regional pest, weed, and disease pressure calendars."""
    try:
        with open(os.path.join(KNOWLEDGE_DIR, 'regional_pressure_calendars.json'), 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load regional_pressure_calendars.json: {e}")
        return {}


@lru_cache(maxsize=1)
def load_advanced_turf_science() -> Dict:
    """Load advanced turf science principles for physiology, soil physics, epidemiology, and playability."""
    try:
        with open(os.path.join(KNOWLEDGE_DIR, 'advanced_turf_science.json'), 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load advanced_turf_science.json: {e}")
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


def get_weed_info(weed_name: str) -> Optional[Dict]:
    """Look up weed information by common name."""
    weeds = load_weeds()
    name_lower = disease_name_to_key(weed_name)

    if name_lower in weeds:
        return {'name': name_lower, **weeds[name_lower]}

    aliases = {
        'roughstalk_bluegrass': 'poa_trivialis',
        'roughstalk': 'poa_trivialis',
        'annual_bluegrass': 'poa_annua',
        'nutsedge': 'yellow_nutsedge',
        'kyllinga': 'green_kyllinga',
        'violet': 'wild_violets',
        'violets': 'wild_violets',
        'wild_violet': 'wild_violets',
        'creeping_charlie': 'ground_ivy',
    }
    if name_lower in aliases and aliases[name_lower] in weeds:
        key = aliases[name_lower]
        return {'name': key, **weeds[key]}

    for weed_key, info in weeds.items():
        display_name = weed_key.replace('_', ' ')
        if name_lower in weed_key or weed_key in name_lower or display_name in weed_name.lower():
            return {'name': weed_key, **info}

    return None


def get_pest_info(pest_name: str) -> Optional[Dict]:
    """Look up insect pest information by common name."""
    pests = load_pests()
    name_lower = disease_name_to_key(pest_name)

    if name_lower in pests:
        return {'name': name_lower, **pests[name_lower]}

    aliases = {
        'grubs': 'white_grubs',
        'grub': 'white_grubs',
        'webworms': 'sod_webworms',
        'webworm': 'sod_webworms',
        'abw': 'annual_bluegrass_weevil',
        'chinch_bug': 'chinch_bugs',
        'billbug': 'billbugs',
        'cutworm': 'cutworms',
    }
    if name_lower in aliases and aliases[name_lower] in pests:
        key = aliases[name_lower]
        return {'name': key, **pests[key]}

    for pest_key, info in pests.items():
        display_name = pest_key.replace('_', ' ')
        if name_lower in pest_key or pest_key in name_lower or display_name in pest_name.lower():
            return {'name': pest_key, **info}

    return None


def get_turfgrass_info(turfgrass_name: str) -> Optional[Dict]:
    """Look up turfgrass species information by common name."""
    turfgrasses = load_turfgrasses()
    name_lower = disease_name_to_key(turfgrass_name)

    aliases = {
        'bentgrass': 'creeping_bentgrass',
        'creeping_bent': 'creeping_bentgrass',
        'poa': 'annual_bluegrass',
        'poa_annua': 'annual_bluegrass',
        'annual_bluegrass': 'annual_bluegrass',
        'kbg': 'kentucky_bluegrass',
        'bluegrass': 'kentucky_bluegrass',
        'kentucky_bluegrass': 'kentucky_bluegrass',
        'fescue': 'tall_fescue',
        'tall_fescue': 'tall_fescue',
        'ryegrass': 'perennial_ryegrass',
        'perennial_ryegrass': 'perennial_ryegrass',
        'fine_fescue': 'fine_fescue',
        'bermuda': 'bermudagrass',
        'bermudagrass': 'bermudagrass',
        'zoysia': 'zoysiagrass',
        'zoysiagrass': 'zoysiagrass',
        'st_augustine': 'st_augustinegrass',
        'st_augustinegrass': 'st_augustinegrass',
        'centipede': 'centipedegrass',
        'centipedegrass': 'centipedegrass',
    }
    key = aliases.get(name_lower, name_lower)
    if key in turfgrasses:
        return {'name': key, **turfgrasses[key]}

    for turf_key, info in turfgrasses.items():
        display_name = turf_key.replace('_', ' ')
        if name_lower in turf_key or turf_key in name_lower or display_name in turfgrass_name.lower():
            return {'name': turf_key, **info}

    return None


def get_abiotic_stress_info(stress_name: str) -> Optional[Dict]:
    """Look up abiotic stress or non-pest diagnostic information by name."""
    stresses = load_abiotic_stress()
    name_lower = disease_name_to_key(stress_name)

    aliases = {
        'lds': 'localized_dry_spot',
        'dry_spot': 'localized_dry_spot',
        'wilt': 'drought_stress',
        'dry': 'drought_stress',
        'too_wet': 'overwatering',
        'wet': 'overwatering',
        'shade': 'shade_stress',
        'traffic': 'traffic_stress',
        'wear': 'traffic_stress',
        'mower_scalp': 'scalping',
        'mower_injury': 'scalping',
        'chemical_injury': 'herbicide_injury',
        'spray_injury': 'herbicide_injury',
        'fertilizer_injury': 'fertilizer_burn',
        'salt_burn': 'fertilizer_burn',
        'pgr': 'pgr_stress',
        'blacklayer': 'black_layer',
    }
    key = aliases.get(name_lower, name_lower)
    if key in stresses:
        return {'name': key, **stresses[key]}

    for stress_key, info in stresses.items():
        display_name = stress_key.replace('_', ' ')
        if name_lower in stress_key or stress_key in name_lower or display_name in stress_name.lower():
            return {'name': stress_key, **info}

    return None


def get_timing_window_info(timing_name: str) -> Optional[Dict]:
    """Look up timing window information by topic or related target."""
    windows = load_timing_windows()
    name_lower = disease_name_to_key(timing_name)
    if name_lower in windows:
        return {'name': name_lower, **windows[name_lower]}

    for window_key, info in windows.items():
        display_name = window_key.replace('_', ' ')
        related_targets = [str(target).lower() for target in info.get('related_targets', [])]
        if (
            name_lower in window_key
            or window_key in name_lower
            or display_name in timing_name.lower()
            or name_lower in related_targets
        ):
            return {'name': window_key, **info}

    return None


def get_fertility_program_info(topic_name: str) -> Optional[Dict]:
    """Look up fertility-program information by topic or keyword."""
    programs = load_fertility_programs()
    name_lower = disease_name_to_key(topic_name)
    if name_lower in programs:
        return {'name': name_lower, **programs[name_lower]}

    aliases = {
        'spoon_feeding': 'greens_spoon_feeding',
        'spoon feeding': 'greens_spoon_feeding',
        'spoon feed': 'greens_spoon_feeding',
        'fall nitrogen': 'cool_season_fall_nitrogen',
        'cool season fall nitrogen': 'cool_season_fall_nitrogen',
        'warm season nitrogen': 'warm_season_growth_season_nitrogen',
        'bermuda nitrogen': 'warm_season_growth_season_nitrogen',
        'potassium leaching': 'sand_based_potassium_and_leaching',
        'sand potassium': 'sand_based_potassium_and_leaching',
        'iron color': 'iron_color_vs_true_nitrogen_need',
        'phosphorus establishment': 'phosphorus_for_establishment_only',
    }
    key = aliases.get(topic_name.lower(), aliases.get(name_lower, name_lower))
    if key in programs:
        return {'name': key, **programs[key]}

    for program_key, info in programs.items():
        display_name = program_key.replace('_', ' ')
        if name_lower in program_key or program_key in name_lower or display_name in topic_name.lower():
            return {'name': program_key, **info}

    return None


def get_irrigation_program_info(topic_name: str) -> Optional[Dict]:
    """Look up irrigation-program information by topic or keyword."""
    programs = load_irrigation_programs()
    name_lower = disease_name_to_key(topic_name)
    if name_lower in programs:
        return {'name': name_lower, **programs[name_lower]}

    aliases = {
        'deficit irrigation': 'deficit_irrigation_greens',
        'syringing': 'syringing_for_canopy_cooling',
        'hand watering': 'hand_watering_hot_spots',
        'wetting agent': 'wetting_agent_strategy_for_lds',
        'deep and infrequent': 'fairway_deep_infrequent_irrigation',
        'deep infrequent': 'fairway_deep_infrequent_irrigation',
        'irrigation audit': 'irrigation_uniformity_audit',
        'uniformity': 'irrigation_uniformity_audit',
    }
    key = aliases.get(topic_name.lower(), aliases.get(name_lower, name_lower))
    if key in programs:
        return {'name': key, **programs[key]}

    for program_key, info in programs.items():
        display_name = program_key.replace('_', ' ')
        if name_lower in program_key or program_key in name_lower or display_name in topic_name.lower():
            return {'name': program_key, **info}

    return None


def get_cultivation_program_info(topic_name: str) -> Optional[Dict]:
    """Look up cultivation-program information by topic or keyword."""
    programs = load_cultivation_programs()
    name_lower = disease_name_to_key(topic_name)
    if name_lower in programs:
        return {'name': name_lower, **programs[name_lower]}

    aliases = {
        'core aeration': 'core_aeration_greens',
        'core aerate': 'core_aeration_greens',
        'aerification': 'core_aeration_greens',
        'venting': 'summer_venting_and_needle_tining',
        'needle tine': 'summer_venting_and_needle_tining',
        'topdressing': 'frequent_light_topdressing',
        'solid tine': 'solid_tining_and_root_pruning_balance',
        'fairway aeration': 'fairway_cultivation_and_topdressing',
        'verticutting': 'verticutting_and_grooming_management',
        'grooming': 'verticutting_and_grooming_management',
    }
    key = aliases.get(topic_name.lower(), aliases.get(name_lower, name_lower))
    if key in programs:
        return {'name': key, **programs[key]}

    for program_key, info in programs.items():
        display_name = program_key.replace('_', ' ')
        if name_lower in program_key or program_key in name_lower or display_name in topic_name.lower():
            return {'name': program_key, **info}

    return None


def get_diagnostic_framework_info(topic_name: str) -> Optional[Dict]:
    """Look up structured diagnostic-framework information."""
    frameworks = load_diagnostic_frameworks()
    name_lower = disease_name_to_key(topic_name)
    if name_lower in frameworks:
        return {'name': name_lower, **frameworks[name_lower]}

    aliases = {
        'wilt vs disease': 'wilt_vs_disease_on_greens',
        'ring pattern': 'ring_pattern_diagnostics',
        'rootzone failure': 'rootzone_failure_framework',
        'herbicide injury': 'herbicide_injury_framework',
        'spray injury': 'herbicide_injury_framework',
        'pgr stress': 'pgr_stress_framework',
        'traffic compaction': 'traffic_compaction_decline',
        'anthracnose decline': 'anthracnose_decline_framework',
        'salt vs drought': 'salt_vs_drought_framework',
        'slow green-up': 'warm_season_slow_greenup_framework',
        'slow green up': 'warm_season_slow_greenup_framework',
        'reclaimed water': 'water_quality_chemistry_framework',
        'water quality': 'water_quality_chemistry_framework',
        'nematode assay': 'nematode_sampling_interpretation_framework',
        'nematode sample': 'nematode_sampling_interpretation_framework',
        'residual herbicide': 'herbicide_carryover_framework',
        'carryover': 'herbicide_carryover_framework',
        'grub damage': 'insect_feeding_pattern_framework',
        'abw': 'insect_feeding_pattern_framework',
        'webworm': 'insect_feeding_pattern_framework',
        'cutworm': 'insect_feeding_pattern_framework',
        'chinch bug': 'insect_feeding_pattern_framework',
        'species fit': 'species_fit_renovation_framework',
        'renovation': 'species_fit_renovation_framework',
        'ryegrass hanging on': 'overseeded_transition_competition_framework',
        'ryegrass is hanging on': 'overseeded_transition_competition_framework',
        'hanging on too long': 'overseeded_transition_competition_framework',
        'spring transition ryegrass': 'overseeded_transition_competition_framework',
        'seedlings dying': 'seedling_establishment_failure_framework',
        'germination looked fine': 'seedling_establishment_failure_framework',
        'establishment failure': 'seedling_establishment_failure_framework',
        'spray passes': 'application_pattern_coverage_framework',
        'nozzle overlap': 'application_pattern_coverage_framework',
        'application pattern': 'application_pattern_coverage_framework',
        'repeated rolling': 'mechanical_stress_budget_framework',
        'rolling frequency': 'mechanical_stress_budget_framework',
        'tournament prep stress': 'mechanical_stress_budget_framework',
        'frayed leaf tips': 'cut_quality_leaf_shredding_framework',
        'cut quality': 'cut_quality_leaf_shredding_framework',
        'leaf shredding': 'cut_quality_leaf_shredding_framework',
        'topdressing drift': 'topdressing_program_drift_framework',
        'sand compatibility': 'topdressing_program_drift_framework',
        'layering after topdressing': 'topdressing_program_drift_framework',
    }
    key = aliases.get(topic_name.lower(), aliases.get(name_lower, name_lower))
    if key in frameworks:
        return {'name': key, **frameworks[key]}

    for framework_key, info in frameworks.items():
        display_name = framework_key.replace('_', ' ')
        if name_lower in framework_key or framework_key in name_lower or display_name in topic_name.lower():
            return {'name': framework_key, **info}

    return None


def get_mowing_program_info(topic_name: str) -> Optional[Dict]:
    """Look up mowing and rolling program information."""
    programs = load_mowing_programs()
    name_lower = disease_name_to_key(topic_name)
    if name_lower in programs:
        return {'name': name_lower, **programs[name_lower]}

    aliases = {
        'rolling': 'rolling_frequency_under_stress',
        'green speed': 'greens_mowing_and_rolling_balance',
        'tournament speed': 'tournament_speed_tradeoffs',
        'scalping': 'scalping_prevention_program',
        'fairway mowing': 'fairway_mowing_frequency_management',
        'rough mowing': 'rough_mowing_and_clipping_management',
    }
    key = aliases.get(topic_name.lower(), aliases.get(name_lower, name_lower))
    if key in programs:
        return {'name': key, **programs[key]}

    for program_key, info in programs.items():
        display_name = program_key.replace('_', ' ')
        if name_lower in program_key or program_key in name_lower or display_name in topic_name.lower():
            return {'name': program_key, **info}

    return None


def get_salinity_management_info(topic_name: str) -> Optional[Dict]:
    """Look up salinity-management information."""
    programs = load_salinity_management()
    name_lower = disease_name_to_key(topic_name)
    if name_lower in programs:
        return {'name': name_lower, **programs[name_lower]}

    aliases = {
        'ec': 'ec_monitoring_program',
        'salinity': 'salt_stress_diagnostics',
        'salt stress': 'salt_stress_diagnostics',
        'leaching': 'leaching_program_for_salts',
        'sodium': 'sodium_hazard_and_structure_loss',
        'reclaimed water': 'reclaimed_water_management',
        'gypsum': 'gypsum_and_amendment_decision_tree',
    }
    key = aliases.get(topic_name.lower(), aliases.get(name_lower, name_lower))
    if key in programs:
        return {'name': key, **programs[key]}

    for program_key, info in programs.items():
        display_name = program_key.replace('_', ' ')
        if name_lower in program_key or program_key in name_lower or display_name in topic_name.lower():
            return {'name': program_key, **info}

    return None


def get_drainage_rootzone_program_info(topic_name: str) -> Optional[Dict]:
    """Look up drainage and rootzone-management information."""
    programs = load_drainage_rootzone_programs()
    name_lower = disease_name_to_key(topic_name)
    if name_lower in programs:
        return {'name': name_lower, **programs[name_lower]}

    aliases = {
        'surface drainage': 'surface_drainage_correction',
        'subsurface drainage': 'subsurface_drainage_evaluation',
        'perched water': 'layering_and_perched_water_table',
        'layering': 'layering_and_perched_water_table',
        'organic matter': 'organic_matter_profile_management',
        'black layer': 'black_layer_prevention_program',
        'construction mismatch': 'construction_profile_mismatch',
    }
    key = aliases.get(topic_name.lower(), aliases.get(name_lower, name_lower))
    if key in programs:
        return {'name': key, **programs[key]}

    for program_key, info in programs.items():
        display_name = program_key.replace('_', ' ')
        if name_lower in program_key or program_key in name_lower or display_name in topic_name.lower():
            return {'name': program_key, **info}

    return None


def get_overseeding_transition_program_info(topic_name: str) -> Optional[Dict]:
    """Look up overseeding and transition program information."""
    programs = load_overseeding_transition_programs()
    name_lower = disease_name_to_key(topic_name)
    if name_lower in programs:
        return {'name': name_lower, **programs[name_lower]}

    aliases = {
        'overseed': 'bermudagrass_overseeding_window',
        'overseeding': 'bermudagrass_overseeding_window',
        'transition': 'spring_transition_acceleration',
        'seedhead suppression': 'poa_annua_seedhead_suppression_program',
        'seedhead': 'poa_annua_seedhead_suppression_program',
        'establishment restriction': 'cool_season_overseeding_restrictions',
        'mowing seedlings': 'overseed_mowing_and_establishment',
        'transition failure': 'transition_failure_diagnostics',
    }
    key = aliases.get(topic_name.lower(), aliases.get(name_lower, name_lower))
    if key in programs:
        return {'name': key, **programs[key]}

    for program_key, info in programs.items():
        display_name = program_key.replace('_', ' ')
        if name_lower in program_key or program_key in name_lower or display_name in topic_name.lower():
            return {'name': program_key, **info}

    return None


def get_disease_ipm_playbook_info(topic_name: str) -> Optional[Dict]:
    """Look up disease IPM playbook information."""
    playbooks = load_disease_ipm_playbooks()
    name_lower = disease_name_to_key(topic_name)
    if name_lower in playbooks:
        return {'name': name_lower, **playbooks[name_lower]}

    aliases = {
        'dollar spot': 'dollar_spot_ipm',
        'brown patch': 'brown_patch_ipm',
        'pythium blight': 'pythium_blight_ipm',
        'summer patch': 'summer_patch_ipm',
        'anthracnose': 'anthracnose_ipm',
        'fairy ring': 'fairy_ring_ipm',
    }
    key = aliases.get(topic_name.lower(), aliases.get(name_lower, name_lower))
    if key in playbooks:
        return {'name': key, **playbooks[key]}

    for playbook_key, info in playbooks.items():
        display_name = playbook_key.replace('_', ' ')
        if name_lower in playbook_key or playbook_key in name_lower or display_name in topic_name.lower():
            return {'name': playbook_key, **info}

    return None


def get_surface_management_recipe_info(topic_name: str) -> Optional[Dict]:
    """Look up surface management recipe information."""
    recipes = load_surface_management_recipes()
    name_lower = disease_name_to_key(topic_name)
    if name_lower in recipes:
        return {'name': name_lower, **recipes[name_lower]}

    aliases = {
        'bentgrass greens': 'bentgrass_greens_recipe',
        'poa greens': 'poa_annua_greens_recipe',
        'bermudagrass fairways': 'bermudagrass_fairways_recipe',
        'tall fescue sports turf': 'tall_fescue_sports_turf_recipe',
        'zoysiagrass fairways': 'zoysiagrass_fairways_recipe',
        'overseeded bermudagrass': 'ryegrass_overseeded_transition_recipe',
    }
    key = aliases.get(topic_name.lower(), aliases.get(name_lower, name_lower))
    if key in recipes:
        return {'name': key, **recipes[key]}

    for recipe_key, info in recipes.items():
        display_name = recipe_key.replace('_', ' ')
        if name_lower in recipe_key or recipe_key in name_lower or display_name in topic_name.lower():
            return {'name': recipe_key, **info}

    return None


def get_climate_zone_playbook_info(topic_name: str) -> Optional[Dict]:
    """Look up climate-zone playbook information."""
    playbooks = load_climate_zone_playbooks()
    name_lower = disease_name_to_key(topic_name)
    if name_lower in playbooks:
        return {'name': name_lower, **playbooks[name_lower]}

    aliases = {
        'transition zone': 'humid_transition_zone_cool_season',
        'humid transition zone': 'humid_transition_zone_cool_season',
        'northern cool season': 'northern_cool_season_intensive',
        'arid west': 'arid_west_warm_season',
        'desert': 'arid_west_warm_season',
        'humid southeast': 'humid_southeast_warm_season',
        'coastal': 'marine_cool_season_coastal',
        'marine climate': 'marine_cool_season_coastal',
        'upper midwest': 'upper_midwest_winter_stress',
        'winter stress': 'upper_midwest_winter_stress',
    }
    key = aliases.get(topic_name.lower(), aliases.get(name_lower, name_lower))
    if key in playbooks:
        return {'name': key, **playbooks[key]}

    for playbook_key, info in playbooks.items():
        display_name = playbook_key.replace('_', ' ')
        if name_lower in playbook_key or playbook_key in name_lower or display_name in topic_name.lower():
            return {'name': playbook_key, **info}

    return None


def get_tournament_prep_recovery_info(topic_name: str) -> Optional[Dict]:
    """Look up tournament prep and recovery information."""
    programs = load_tournament_prep_recovery()
    name_lower = disease_name_to_key(topic_name)
    if name_lower in programs:
        return {'name': name_lower, **programs[name_lower]}

    aliases = {
        'green speed': 'greens_speed_ramp_plan',
        'speed ramp': 'greens_speed_ramp_plan',
        'firmness': 'firmness_and_moisture_tournament_plan',
        'moisture plan': 'firmness_and_moisture_tournament_plan',
        'fairway presentation': 'fairway_tournament_presentation_plan',
        'event recovery greens': 'event_recovery_greens_plan',
        'event recovery fairway': 'event_recovery_fairway_plan',
        'weather disruption': 'weather_disruption_event_plan',
        'tournament weather': 'weather_disruption_event_plan',
    }
    key = aliases.get(topic_name.lower(), aliases.get(name_lower, name_lower))
    if key in programs:
        return {'name': key, **programs[key]}

    for program_key, info in programs.items():
        display_name = program_key.replace('_', ' ')
        if name_lower in program_key or program_key in name_lower or display_name in topic_name.lower():
            return {'name': program_key, **info}

    return None


def get_nutrient_diagnostics_info(topic_name: str) -> Optional[Dict]:
    """Look up nutrient-diagnostic information."""
    diagnostics = load_nutrient_diagnostics()
    name_lower = disease_name_to_key(topic_name)
    if name_lower in diagnostics:
        return {'name': name_lower, **diagnostics[name_lower]}

    aliases = {
        'nitrogen deficiency': 'nitrogen_deficiency',
        'n deficiency': 'nitrogen_deficiency',
        'potassium deficiency': 'potassium_deficiency',
        'k deficiency': 'potassium_deficiency',
        'iron deficiency': 'iron_deficiency_or_color_loss',
        'color loss': 'iron_deficiency_or_color_loss',
        'phosphorus deficiency': 'phosphorus_deficiency_or_establishment_issue',
        'p deficiency': 'phosphorus_deficiency_or_establishment_issue',
        'micronutrient lockout': 'micronutrient_lockout_high_ph',
        'high ph chlorosis': 'micronutrient_lockout_high_ph',
        'fertilizer burn': 'salt_or_fertilizer_burn_diagnostics',
        'salt burn': 'salt_or_fertilizer_burn_diagnostics',
    }
    key = aliases.get(topic_name.lower(), aliases.get(name_lower, name_lower))
    if key in diagnostics:
        return {'name': key, **diagnostics[key]}

    for diagnostic_key, info in diagnostics.items():
        display_name = diagnostic_key.replace('_', ' ')
        if name_lower in diagnostic_key or diagnostic_key in name_lower or display_name in topic_name.lower():
            return {'name': diagnostic_key, **info}

    return None


def get_calibration_workflow_info(topic_name: str) -> Optional[Dict]:
    """Look up application calibration workflow information."""
    workflows = load_calibration_workflows()
    name_lower = disease_name_to_key(topic_name)
    if name_lower in workflows:
        return {'name': name_lower, **workflows[name_lower]}

    aliases = {
        'sprayer output': 'sprayer_output_verification',
        'sprayer calibration': 'sprayer_output_verification',
        'mixing sequence': 'sprayer_mixing_sequence_workflow',
        'tank mixing': 'sprayer_mixing_sequence_workflow',
        'spreader pattern': 'spreader_pattern_testing',
        'granular conversion': 'granular_rate_per_1000_conversion',
        'per 1000 conversion': 'granular_rate_per_1000_conversion',
        'travel speed': 'travel_speed_checkpoint_workflow',
        'speed check': 'travel_speed_checkpoint_workflow',
        'recordkeeping': 'recordkeeping_and_post_application_review',
        'post application review': 'recordkeeping_and_post_application_review',
    }
    key = aliases.get(topic_name.lower(), aliases.get(name_lower, name_lower))
    if key in workflows:
        return {'name': key, **workflows[key]}

    for workflow_key, info in workflows.items():
        display_name = workflow_key.replace('_', ' ')
        if name_lower in workflow_key or workflow_key in name_lower or display_name in topic_name.lower():
            return {'name': workflow_key, **info}

    return None


def get_seasonal_operating_plan_info(topic_name: str) -> Optional[Dict]:
    """Look up seasonal operating plan information."""
    plans = load_seasonal_operating_plans()
    name_lower = disease_name_to_key(topic_name)
    if name_lower in plans:
        return {'name': name_lower, **plans[name_lower]}

    aliases = {
        'transition zone calendar': 'cool_season_transition_zone_calendar',
        'cool season transition zone': 'cool_season_transition_zone_calendar',
        'cool season transition zone seasonal operating plan': 'cool_season_transition_zone_calendar',
        'northern cool season': 'northern_cool_season_calendar',
        'northern cool season seasonal operating plan': 'northern_cool_season_calendar',
        'southeast warm season': 'warm_season_southeast_calendar',
        'warm season southeast': 'warm_season_southeast_calendar',
        'warm season southeast seasonal operating plan': 'warm_season_southeast_calendar',
        'arid west bermudagrass': 'arid_west_bermudagrass_calendar',
        'arid west bermudagrass seasonal operating plan': 'arid_west_bermudagrass_calendar',
    }
    key = aliases.get(topic_name.lower(), aliases.get(name_lower, name_lower))
    if key in plans:
        return {'name': key, **plans[key]}

    for plan_key, info in plans.items():
        display_name = plan_key.replace('_', ' ')
        if name_lower in plan_key or plan_key in name_lower or display_name in topic_name.lower():
            return {'name': plan_key, **info}

    return None


def get_regional_pressure_calendar_info(topic_name: str) -> Optional[Dict]:
    """Look up regional pressure calendar information."""
    calendars = load_regional_pressure_calendars()
    name_lower = disease_name_to_key(topic_name)
    if name_lower in calendars:
        return {'name': name_lower, **calendars[name_lower]}

    aliases = {
        'transition zone pressure': 'transition_zone_cool_season_pressure',
        'cool season transition pressure': 'transition_zone_cool_season_pressure',
        'transition zone cool season regional pressure calendar': 'transition_zone_cool_season_pressure',
        'northern cool season pressure': 'northern_cool_season_pressure',
        'northern cool season regional pressure calendar': 'northern_cool_season_pressure',
        'southeast warm season pressure': 'southeast_warm_season_pressure',
        'southeast warm season regional pressure calendar': 'southeast_warm_season_pressure',
        'arid west bermudagrass pressure': 'arid_west_bermudagrass_pressure',
        'arid west bermudagrass regional pressure calendar': 'arid_west_bermudagrass_pressure',
    }
    key = aliases.get(topic_name.lower(), aliases.get(name_lower, name_lower))
    if key in calendars:
        return {'name': key, **calendars[key]}

    for calendar_key, info in calendars.items():
        display_name = calendar_key.replace('_', ' ')
        if name_lower in calendar_key or calendar_key in name_lower or display_name in topic_name.lower():
            return {'name': calendar_key, **info}

    return None


def get_advanced_turf_science_info(topic_name: str) -> Optional[Dict]:
    """Look up advanced turf science principle records."""
    science = load_advanced_turf_science()
    name_lower = disease_name_to_key(topic_name)
    if name_lower in science:
        return {'name': name_lower, **science[name_lower]}

    aliases = {
        'heat stress physiology': 'cool_season_heat_carbohydrate_decline',
        'carbohydrate': 'cool_season_heat_carbohydrate_decline',
        'carbohydrate reserves': 'cool_season_heat_carbohydrate_decline',
        'carbohydrate_reserves': 'cool_season_heat_carbohydrate_decline',
        'root respiration': 'root_respiration_oxygen_balance',
        'root_respiration': 'root_respiration_oxygen_balance',
        'oxygen balance': 'root_respiration_oxygen_balance',
        'oxygen_balance': 'root_respiration_oxygen_balance',
        'air filled porosity': 'usga_rootzone_porosity_hydraulic_conductivity',
        'air_filled_porosity': 'usga_rootzone_porosity_hydraulic_conductivity',
        'hydraulic conductivity': 'usga_rootzone_porosity_hydraulic_conductivity',
        'hydraulic_conductivity': 'usga_rootzone_porosity_hydraulic_conductivity',
        'rootzone porosity': 'usga_rootzone_porosity_hydraulic_conductivity',
        'rootzone_porosity': 'usga_rootzone_porosity_hydraulic_conductivity',
        'organic matter physics': 'surface_organic_matter_physics',
        'organic_matter_physics': 'surface_organic_matter_physics',
        'surface organic matter': 'surface_organic_matter_physics',
        'surface_organic_matter': 'surface_organic_matter_physics',
        'perched water': 'perched_water_layering_diagnostics',
        'perched_water': 'perched_water_layering_diagnostics',
        'layering': 'perched_water_layering_diagnostics',
        'disease triangle': 'disease_triangle_leaf_wetness_microclimate',
        'disease_triangle': 'disease_triangle_leaf_wetness_microclimate',
        'leaf wetness': 'disease_triangle_leaf_wetness_microclimate',
        'leaf_wetness': 'disease_triangle_leaf_wetness_microclimate',
        'dollar spot epidemiology': 'dollar_spot_epidemiology_nitrogen_leaf_wetness',
        'dollar_spot_epidemiology': 'dollar_spot_epidemiology_nitrogen_leaf_wetness',
        'brown patch epidemiology': 'brown_patch_rhizoctonia_heat_humidity',
        'brown_patch_epidemiology': 'brown_patch_rhizoctonia_heat_humidity',
        'pgr rebound': 'pgr_growth_suppression_thermal_rebound',
        'pgr_rebound': 'pgr_growth_suppression_thermal_rebound',
        'growth potential': 'pgr_growth_suppression_thermal_rebound',
        'growth_potential': 'pgr_growth_suppression_thermal_rebound',
        'deficit irrigation': 'et_deficit_irrigation_syringing',
        'deficit_irrigation': 'et_deficit_irrigation_syringing',
        'syringing': 'et_deficit_irrigation_syringing',
        'localized dry spot hydrophobicity': 'localized_dry_spot_hydrophobicity',
        'localized_dry_spot_hydrophobicity': 'localized_dry_spot_hydrophobicity',
        'hydrophobicity': 'localized_dry_spot_hydrophobicity',
        'firmness': 'firmness_green_speed_plant_health_tradeoff',
        'green speed': 'firmness_green_speed_plant_health_tradeoff',
        'green_speed': 'firmness_green_speed_plant_health_tradeoff',
        'traffic recovery': 'traffic_recovery_carbohydrate_growth_rate',
        'traffic_recovery': 'traffic_recovery_carbohydrate_growth_rate',
        'winter injury': 'winter_crown_hydration_freeze_injury',
        'winter_injury': 'winter_crown_hydration_freeze_injury',
        'crown hydration': 'winter_crown_hydration_freeze_injury',
        'crown_hydration': 'winter_crown_hydration_freeze_injury',
        'freeze injury': 'winter_crown_hydration_freeze_injury',
        'freeze_injury': 'winter_crown_hydration_freeze_injury',
        'shade physiology': 'shade_light_carbohydrate_morphology',
        'shade_physiology': 'shade_light_carbohydrate_morphology',
        'low light': 'shade_light_carbohydrate_morphology',
        'low_light': 'shade_light_carbohydrate_morphology',
        'nitrogen form': 'nitrogen_form_release_growth_stress_balance',
        'nitrogen_form': 'nitrogen_form_release_growth_stress_balance',
        'slow release nitrogen': 'nitrogen_form_release_growth_stress_balance',
        'slow_release_nitrogen': 'nitrogen_form_release_growth_stress_balance',
        'salinity stress': 'salinity_osmotic_sodium_structure_stress',
        'salinity_stress': 'salinity_osmotic_sodium_structure_stress',
        'sodium hazard': 'salinity_osmotic_sodium_structure_stress',
        'sodium_hazard': 'salinity_osmotic_sodium_structure_stress',
        'osmotic drought': 'salinity_osmotic_sodium_structure_stress',
        'osmotic_drought': 'salinity_osmotic_sodium_structure_stress',
        'nematode': 'nematode_root_pruning_stress_complex',
        'nematodes': 'nematode_root_pruning_stress_complex',
        'root pruning': 'nematode_root_pruning_stress_complex',
        'root_pruning': 'nematode_root_pruning_stress_complex',
        'poa annua decline': 'poa_annua_vs_bentgrass_summer_decline',
        'poa_annua_decline': 'poa_annua_vs_bentgrass_summer_decline',
        'poa decline': 'poa_annua_vs_bentgrass_summer_decline',
        'poa_decline': 'poa_annua_vs_bentgrass_summer_decline',
        'wetting agent chemistry': 'wetting_agent_chemistry_functional_groups',
        'wetting_agent_chemistry': 'wetting_agent_chemistry_functional_groups',
        'surfactant chemistry': 'wetting_agent_chemistry_functional_groups',
        'surfactant_chemistry': 'wetting_agent_chemistry_functional_groups',
        'bicarbonate': 'bicarbonate_alkalinity_micronutrient_lockout',
        'bicarbonates': 'bicarbonate_alkalinity_micronutrient_lockout',
        'alkalinity': 'bicarbonate_alkalinity_micronutrient_lockout',
        'micronutrient lockout': 'bicarbonate_alkalinity_micronutrient_lockout',
        'micronutrient_lockout': 'bicarbonate_alkalinity_micronutrient_lockout',
        'pythium root dysfunction': 'pythium_root_dysfunction_vs_wet_wilt',
        'pythium_root_dysfunction': 'pythium_root_dysfunction_vs_wet_wilt',
        'pythium root rot': 'pythium_root_dysfunction_vs_wet_wilt',
        'pythium_root_rot': 'pythium_root_dysfunction_vs_wet_wilt',
        'growing degree days': 'gdd_growth_potential_pgr_timing',
        'growing_degree_days': 'gdd_growth_potential_pgr_timing',
        'gdd': 'gdd_growth_potential_pgr_timing',
        'pgr timing': 'gdd_growth_potential_pgr_timing',
        'pgr_timing': 'gdd_growth_potential_pgr_timing',
        'anthracnose basal rot': 'anthracnose_basal_rot_stress_complex',
        'anthracnose_basal_rot': 'anthracnose_basal_rot_stress_complex',
        'anthracnose decline': 'anthracnose_basal_rot_stress_complex',
        'basal rot': 'anthracnose_basal_rot_stress_complex',
        'fairy ring hydrophobicity': 'fairy_ring_hydrophobicity_nitrogen_masking',
        'fairy_ring_hydrophobicity': 'fairy_ring_hydrophobicity_nitrogen_masking',
        'fairy ring masking': 'fairy_ring_hydrophobicity_nitrogen_masking',
        'green ring': 'fairy_ring_hydrophobicity_nitrogen_masking',
        'soil ph buffering': 'soil_ph_buffering_acidification_programs',
        'soil_ph_buffering': 'soil_ph_buffering_acidification_programs',
        'acidification program': 'soil_ph_buffering_acidification_programs',
        'water acidification': 'soil_ph_buffering_acidification_programs',
        'spring dead spot': 'bermudagrass_spring_dead_spot_transition_recovery',
        'spring_dead_spot': 'bermudagrass_spring_dead_spot_transition_recovery',
        'bermuda spring recovery': 'bermudagrass_spring_dead_spot_transition_recovery',
        'bermuda transition': 'bermudagrass_spring_dead_spot_transition_recovery',
        'salt vs drought': 'salt_vs_drought_ec_moisture_interpretation',
        'salt_vs_drought': 'salt_vs_drought_ec_moisture_interpretation',
        'salt stress versus drought': 'salt_vs_drought_ec_moisture_interpretation',
        'osmotic stress': 'salt_vs_drought_ec_moisture_interpretation',
        'zoysia green up': 'zoysiagrass_spring_greenup_thatch_temperature',
        'zoysia green-up': 'zoysiagrass_spring_greenup_thatch_temperature',
        'slow zoysia spring': 'zoysiagrass_spring_greenup_thatch_temperature',
        'zoysia spring lag': 'zoysiagrass_spring_greenup_thatch_temperature',
        'bermuda shade': 'bermudagrass_shade_cold_carbohydrate_limits',
        'bermudagrass shade': 'bermudagrass_shade_cold_carbohydrate_limits',
        'fall hardening': 'warm_season_fall_hardening_winter_survival',
        'winter survival': 'warm_season_fall_hardening_winter_survival',
        'reclaimed water nutrient credit': 'reclaimed_water_nutrient_credit_salt_balance',
        'reclaimed water salts': 'reclaimed_water_nutrient_credit_salt_balance',
        'effluent water': 'reclaimed_water_nutrient_credit_salt_balance',
        'sar': 'gypsum_sar_dispersion_decision_logic',
        'soil dispersion': 'gypsum_sar_dispersion_decision_logic',
        'gypsum decision': 'gypsum_sar_dispersion_decision_logic',
        'nematode lab': 'nematode_lab_interpretation_threshold_context',
        'nematode assay': 'nematode_lab_interpretation_threshold_context',
        'nematode threshold': 'nematode_lab_interpretation_threshold_context',
        'nematicide expectations': 'nematicide_expectation_root_recovery_logic',
        'nematicide recovery': 'nematicide_expectation_root_recovery_logic',
        'herbicide mode of action': 'herbicide_mode_of_action_injury_patterns',
        'herbicide injury pattern': 'herbicide_mode_of_action_injury_patterns',
        'herbicide carryover': 'herbicide_carryover_residual_transition_risk',
        'residual herbicide': 'herbicide_carryover_residual_transition_risk',
        'carryover risk': 'herbicide_carryover_residual_transition_risk',
        'tournament stress budget': 'tournament_greens_stress_budget_model',
        'greens conditioning stress': 'tournament_greens_stress_budget_model',
        'greens conditioning budget': 'tournament_greens_stress_budget_model',
        'conditioning budget': 'tournament_greens_stress_budget_model',
        'tournament fairway traffic': 'tournament_fairway_tee_recovery_traffic_model',
        'tournament tee traffic': 'tournament_fairway_tee_recovery_traffic_model',
        'abw timing': 'annual_bluegrass_weevil_lifecycle_threshold_timing',
        'annual bluegrass weevil timing': 'annual_bluegrass_weevil_lifecycle_threshold_timing',
        'abw lifecycle': 'annual_bluegrass_weevil_lifecycle_threshold_timing',
        'grub threshold': 'white_grub_species_threshold_recovery_logic',
        'white grub threshold': 'white_grub_species_threshold_recovery_logic',
        'sod webworm': 'sod_webworm_cutworm_night_feeding_diagnostics',
        'cutworm feeding': 'sod_webworm_cutworm_night_feeding_diagnostics',
        'chinch bug drought': 'chinch_bug_heat_drought_interaction_model',
        'chinch bug heat stress': 'chinch_bug_heat_drought_interaction_model',
        'species fit': 'species_fit_surface_region_tradeoff_model',
        'surface fit': 'species_fit_surface_region_tradeoff_model',
        'renovation decision': 'renovation_vs_rescue_program_decision_model',
        'renovation versus rescue': 'renovation_vs_rescue_program_decision_model',
        'ryegrass hanging on': 'overseeded_ryegrass_transition_competition_model',
        'ryegrass is hanging on': 'overseeded_ryegrass_transition_competition_model',
        'hanging on too long': 'overseeded_ryegrass_transition_competition_model',
        'spring transition ryegrass': 'overseeded_ryegrass_transition_competition_model',
        'bermuda transition competition': 'overseeded_ryegrass_transition_competition_model',
        'seedling establishment': 'seedling_establishment_temperature_moisture_oxygen_balance',
        'seedlings dying': 'seedling_establishment_temperature_moisture_oxygen_balance',
        'germination looked fine': 'seedling_establishment_temperature_moisture_oxygen_balance',
        'cultivar diversity': 'cultivar_diversity_stress_disease_buffering',
        'mixed cultivars': 'cultivar_diversity_stress_disease_buffering',
        'sprayer coverage': 'sprayer_coverage_nozzle_pressure_canopy_deposition',
        'nozzle pressure': 'sprayer_coverage_nozzle_pressure_canopy_deposition',
        'application pattern': 'sprayer_coverage_nozzle_pressure_canopy_deposition',
        'rolling frequency': 'roller_frequency_mechanical_stress_budget',
        'repeated rolling': 'roller_frequency_mechanical_stress_budget',
        'cec': 'soil_test_cec_base_saturation_practical_limits',
        'base saturation': 'soil_test_cec_base_saturation_practical_limits',
        'spray water ph': 'spray_water_ph_hardness_adjuvant_interaction_model',
        'water hardness spray': 'spray_water_ph_hardness_adjuvant_interaction_model',
        'adjuvant interaction': 'spray_water_ph_hardness_adjuvant_interaction_model',
        'mower sharpness': 'mower_sharpness_leaf_shredding_disease_mimic_model',
        'leaf shredding': 'mower_sharpness_leaf_shredding_disease_mimic_model',
        'cut quality': 'mower_sharpness_leaf_shredding_disease_mimic_model',
        'topdressing consistency': 'topdressing_organic_matter_dilution_layering_drift',
        'organic matter dilution': 'topdressing_organic_matter_dilution_layering_drift',
        'sand compatibility': 'topdressing_organic_matter_dilution_layering_drift',
    }
    key = aliases.get(topic_name.lower(), aliases.get(name_lower, name_lower))
    if key in science:
        return {'name': key, **science[key]}

    for science_key, info in science.items():
        display_name = science_key.replace('_', ' ')
        if name_lower in science_key or science_key in name_lower or display_name in topic_name.lower():
            return {'name': science_key, **info}

    return None


def disease_name_to_key(name: str) -> str:
    return (name or '').lower().replace(' ', '_').replace('-', '_')


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
                'chemical_control': info.get('chemical_control'),
                'recommended_product_details': get_products_for_disease(display_name)
            }
            context_parts.append(f"[Knowledge Base - {display_name}]: {json.dumps(summary, indent=2)}")
            break

    # Check for weed mentions
    weeds = load_weeds()
    for weed_name, info in weeds.items():
        display_name = weed_name.replace('_', ' ')
        if display_name in question_lower or weed_name in question_lower:
            summary = {
                'type': info.get('type'),
                'life_cycle': info.get('life_cycle'),
                'identification': info.get('identification'),
                'timing': info.get('timing'),
                'cultural_control': info.get('cultural_control'),
                'chemical_control': info.get('chemical_control'),
            }
            context_parts.append(f"[Knowledge Base - {display_name} weed]: {json.dumps(summary, indent=2)}")
            break

    # Check for insect pest mentions
    pests = load_pests()
    pest_aliases = {
        'grub': 'white_grubs',
        'grubs': 'white_grubs',
        'webworm': 'sod_webworms',
        'webworms': 'sod_webworms',
        'abw': 'annual_bluegrass_weevil',
        'chinch bug': 'chinch_bugs',
        'billbug': 'billbugs',
        'cutworm': 'cutworms',
    }
    for alias, pest_key in pest_aliases.items():
        if alias in question_lower and pest_key in pests:
            info = pests[pest_key]
            summary = {
                'type': info.get('type'),
                'damage': info.get('damage'),
                'scouting': info.get('scouting'),
                'cultural_control': info.get('cultural_control'),
                'chemical_control': info.get('chemical_control'),
            }
            context_parts.append(f"[Knowledge Base - {pest_key.replace('_', ' ')} pest]: {json.dumps(summary, indent=2)}")
            break
    else:
        for pest_name, info in pests.items():
            display_name = pest_name.replace('_', ' ')
            if display_name in question_lower or pest_name in question_lower:
                summary = {
                    'type': info.get('type'),
                    'damage': info.get('damage'),
                    'scouting': info.get('scouting'),
                    'cultural_control': info.get('cultural_control'),
                    'chemical_control': info.get('chemical_control'),
                }
                context_parts.append(f"[Knowledge Base - {display_name} pest]: {json.dumps(summary, indent=2)}")
                break

    # Check for turfgrass species mentions
    turfgrasses = load_turfgrasses()
    turf_aliases = {
        'bentgrass': 'creeping_bentgrass',
        'poa annua': 'annual_bluegrass',
        'annual bluegrass': 'annual_bluegrass',
        'kentucky bluegrass': 'kentucky_bluegrass',
        'bluegrass': 'kentucky_bluegrass',
        'kbg': 'kentucky_bluegrass',
        'tall fescue': 'tall_fescue',
        'fescue': 'tall_fescue',
        'ryegrass': 'perennial_ryegrass',
        'fine fescue': 'fine_fescue',
        'bermuda': 'bermudagrass',
        'bermudagrass': 'bermudagrass',
        'zoysia': 'zoysiagrass',
        'zoysiagrass': 'zoysiagrass',
        'st augustine': 'st_augustinegrass',
        'st. augustine': 'st_augustinegrass',
        'centipede': 'centipedegrass',
    }
    for alias, turf_key in turf_aliases.items():
        if alias in question_lower and turf_key in turfgrasses:
            info = turfgrasses[turf_key]
            summary = {
                'season': info.get('season'),
                'primary_uses': info.get('primary_uses'),
                'strengths': info.get('strengths'),
                'weaknesses': info.get('weaknesses'),
                'management': info.get('management'),
                'diagnostic_notes': info.get('diagnostic_notes'),
            }
            context_parts.append(f"[Knowledge Base - {turf_key.replace('_', ' ')} turfgrass]: {json.dumps(summary, indent=2)}")
            break

    # Check for abiotic/non-pest stress mentions
    stresses = load_abiotic_stress()
    stress_aliases = {
        'localized dry spot': 'localized_dry_spot',
        'dry spot': 'localized_dry_spot',
        'lds': 'localized_dry_spot',
        'heat stress': 'heat_stress',
        'heat': 'heat_stress',
        'drought': 'drought_stress',
        'wilt': 'drought_stress',
        'too wet': 'overwatering',
        'overwater': 'overwatering',
        'compaction': 'compaction',
        'compact': 'compaction',
        'shade': 'shade_stress',
        'traffic': 'traffic_stress',
        'wear': 'traffic_stress',
        'scalp': 'scalping',
        'scalping': 'scalping',
        'herbicide injury': 'herbicide_injury',
        'spray injury': 'herbicide_injury',
        'fertilizer burn': 'fertilizer_burn',
        'salt burn': 'fertilizer_burn',
        'pgr stress': 'pgr_stress',
        'black layer': 'black_layer',
    }
    for alias, stress_key in stress_aliases.items():
        if alias in question_lower and stress_key in stresses:
            info = stresses[stress_key]
            summary = {
                'category': info.get('category'),
                'common_sites': info.get('common_sites'),
                'symptoms': info.get('symptoms'),
                'diagnosis': info.get('diagnosis'),
                'management': info.get('management'),
            }
            context_parts.append(f"[Knowledge Base - {stress_key.replace('_', ' ')}]: {json.dumps(summary, indent=2)}")
            break

    # Check for seasonal timing windows. Only add this context when the question
    # is actually timing-oriented so broad target mentions do not overfill prompts.
    if any(term in question_lower for term in ['when', 'timing', 'window', 'soil temp', 'soil temperature', 'schedule', 'preventive', 'pre-emergent', 'pre emergent', 'aerate', 'aeration']):
        timing_windows = load_timing_windows()
        timing_matches = []
        for timing_key, info in timing_windows.items():
            score = _timing_window_score(question_lower, timing_key, info)
            if score:
                timing_matches.append((score, timing_key, info))
        if timing_matches:
            _, timing_key, info = sorted(timing_matches, key=lambda item: item[0], reverse=True)[0]
            summary = {
                'topic': info.get('topic'),
                'trigger': info.get('trigger'),
                'soil_temperature': info.get('soil_temperature'),
                'air_temperature': info.get('air_temperature'),
                'primary_window': info.get('primary_window'),
                'follow_up': info.get('follow_up'),
                'related_targets': info.get('related_targets'),
                'related_products': info.get('related_products'),
                'cautions': info.get('cautions'),
            }
            context_parts.append(f"[Knowledge Base - {timing_key.replace('_', ' ')} timing]: {json.dumps(summary, indent=2)}")

    # Check for fertility-program topics.
    fertility_aliases = {
        'spoon feeding': 'greens_spoon_feeding',
        'spoon-feeding': 'greens_spoon_feeding',
        'spoon feed': 'greens_spoon_feeding',
        'fall nitrogen': 'cool_season_fall_nitrogen',
        'summer nitrogen': 'warm_season_growth_season_nitrogen',
        'potassium': 'sand_based_potassium_and_leaching',
        'leaching': 'sand_based_potassium_and_leaching',
        'iron': 'iron_color_vs_true_nitrogen_need',
        'phosphorus': 'phosphorus_for_establishment_only',
    }
    for alias, program_key in fertility_aliases.items():
        if alias in question_lower and program_key in load_fertility_programs():
            info = load_fertility_programs()[program_key]
            summary = {
                'topic': info.get('topic'),
                'primary_goal': info.get('primary_goal'),
                'suitable_sites': info.get('suitable_sites'),
                'core_principles': info.get('core_principles'),
                'benchmark_ranges': info.get('benchmark_ranges'),
                'cautions': info.get('cautions'),
                'monitoring': info.get('monitoring'),
            }
            context_parts.append(f"[Knowledge Base - {program_key.replace('_', ' ')} fertility]: {json.dumps(summary, indent=2)}")
            break

    # Check for irrigation-program topics.
    irrigation_aliases = {
        'deficit irrigation': 'deficit_irrigation_greens',
        'syring': 'syringing_for_canopy_cooling',
        'hand water': 'hand_watering_hot_spots',
        'wetting agent': 'wetting_agent_strategy_for_lds',
        'deep and infrequent': 'fairway_deep_infrequent_irrigation',
        'deep infrequent': 'fairway_deep_infrequent_irrigation',
        'uniformity': 'irrigation_uniformity_audit',
        'irrigation audit': 'irrigation_uniformity_audit',
    }
    for alias, program_key in irrigation_aliases.items():
        if alias in question_lower and program_key in load_irrigation_programs():
            info = load_irrigation_programs()[program_key]
            summary = {
                'topic': info.get('topic'),
                'primary_goal': info.get('primary_goal'),
                'triggers': info.get('triggers'),
                'program': info.get('program'),
                'monitoring': info.get('monitoring'),
                'cautions': info.get('cautions'),
            }
            context_parts.append(f"[Knowledge Base - {program_key.replace('_', ' ')} irrigation]: {json.dumps(summary, indent=2)}")
            break

    # Check for cultivation-program topics.
    cultivation_aliases = {
        'core aeration': 'core_aeration_greens',
        'core aerate': 'core_aeration_greens',
        'aerification': 'core_aeration_greens',
        'venting': 'summer_venting_and_needle_tining',
        'needle tine': 'summer_venting_and_needle_tining',
        'topdress': 'frequent_light_topdressing',
        'solid tine': 'solid_tining_and_root_pruning_balance',
        'verticut': 'verticutting_and_grooming_management',
        'grooming': 'verticutting_and_grooming_management',
        'fairway cultivation': 'fairway_cultivation_and_topdressing',
    }
    for alias, program_key in cultivation_aliases.items():
        if alias in question_lower and program_key in load_cultivation_programs():
            info = load_cultivation_programs()[program_key]
            summary = {
                'topic': info.get('topic'),
                'primary_goal': info.get('primary_goal'),
                'timing': info.get('timing'),
                'methods': info.get('methods'),
                'expected_benefits': info.get('expected_benefits'),
                'cautions': info.get('cautions'),
            }
            context_parts.append(f"[Knowledge Base - {program_key.replace('_', ' ')} cultivation]: {json.dumps(summary, indent=2)}")
            break

    # Check for diagnostic-framework topics.
    diagnostic_aliases = {
        'wilt': 'wilt_vs_disease_on_greens',
        'ring': 'ring_pattern_diagnostics',
        'rootzone': 'rootzone_failure_framework',
        'herbicide injury': 'herbicide_injury_framework',
        'spray injury': 'herbicide_injury_framework',
        'pgr stress': 'pgr_stress_framework',
        'traffic': 'traffic_compaction_decline',
        'compaction': 'traffic_compaction_decline',
        'anthracnose': 'anthracnose_decline_framework',
        'salt stress': 'salt_vs_drought_framework',
        'salinity': 'salt_vs_drought_framework',
        'spring dead spot': 'bermuda_spring_transition_failure',
        'bermuda transition': 'bermuda_spring_transition_failure',
        'slow green up': 'warm_season_slow_greenup_framework',
        'slow green-up': 'warm_season_slow_greenup_framework',
        'zoysia': 'warm_season_slow_greenup_framework',
        'water quality': 'water_quality_chemistry_framework',
        'reclaimed water': 'water_quality_chemistry_framework',
        'alkalinity': 'water_quality_chemistry_framework',
        'nematode sample': 'nematode_sampling_interpretation_framework',
        'nematode assay': 'nematode_sampling_interpretation_framework',
        'carryover': 'herbicide_carryover_framework',
        'residual herbicide': 'herbicide_carryover_framework',
        'grub damage': 'insect_feeding_pattern_framework',
        'abw': 'insect_feeding_pattern_framework',
        'webworm': 'insect_feeding_pattern_framework',
        'cutworm': 'insect_feeding_pattern_framework',
        'chinch bug': 'insect_feeding_pattern_framework',
        'species fit': 'species_fit_renovation_framework',
        'renovation': 'species_fit_renovation_framework',
        'ryegrass hanging on': 'overseeded_transition_competition_framework',
        'spring transition ryegrass': 'overseeded_transition_competition_framework',
        'seedlings dying': 'seedling_establishment_failure_framework',
        'establishment failure': 'seedling_establishment_failure_framework',
    }
    for alias, framework_key in diagnostic_aliases.items():
        if alias in question_lower and framework_key in load_diagnostic_frameworks():
            info = load_diagnostic_frameworks()[framework_key]
            summary = {
                'problem_space': info.get('problem_space'),
                'first_checks': info.get('first_checks'),
                'differentials': info.get('differentials'),
                'confirmatory_signs': info.get('confirmatory_signs'),
                'avoid_assumptions': info.get('avoid_assumptions'),
                'escalation': info.get('escalation'),
            }
            context_parts.append(f"[Knowledge Base - {framework_key.replace('_', ' ')} diagnostic]: {json.dumps(summary, indent=2)}")
            break

    disease_playbook_aliases = {
        'dollar spot': 'dollar_spot_ipm',
        'brown patch': 'brown_patch_ipm',
        'pythium blight': 'pythium_blight_ipm',
        'summer patch': 'summer_patch_ipm',
        'anthracnose': 'anthracnose_ipm',
        'fairy ring': 'fairy_ring_ipm',
    }
    for alias, playbook_key in disease_playbook_aliases.items():
        if alias in question_lower and playbook_key in load_disease_ipm_playbooks():
            info = load_disease_ipm_playbooks()[playbook_key]
            summary = {
                'topic': info.get('topic'),
                'target_disease': info.get('target_disease'),
                'high_risk_sites': info.get('high_risk_sites'),
                'scouting_focus': info.get('scouting_focus'),
                'environmental_drivers': info.get('environmental_drivers'),
                'cultural_program': info.get('cultural_program'),
                'chemical_strategy': info.get('chemical_strategy'),
                'monitoring': info.get('monitoring'),
            }
            context_parts.append(f"[Knowledge Base - {playbook_key.replace('_', ' ')} playbook]: {json.dumps(summary, indent=2)}")
            break

    surface_recipe_aliases = {
        'bentgrass greens': 'bentgrass_greens_recipe',
        'poa greens': 'poa_annua_greens_recipe',
        'bermudagrass fairways': 'bermudagrass_fairways_recipe',
        'tall fescue sports turf': 'tall_fescue_sports_turf_recipe',
        'zoysiagrass fairways': 'zoysiagrass_fairways_recipe',
        'overseeded bermudagrass': 'ryegrass_overseeded_transition_recipe',
        'spring transition': 'ryegrass_overseeded_transition_recipe',
    }
    for alias, recipe_key in surface_recipe_aliases.items():
        if alias in question_lower and recipe_key in load_surface_management_recipes():
            info = load_surface_management_recipes()[recipe_key]
            summary = {
                'surface': info.get('surface'),
                'primary_goals': info.get('primary_goals'),
                'mowing_and_speed': info.get('mowing_and_speed'),
                'water_management': info.get('water_management'),
                'fertility': info.get('fertility'),
                'cultivation': info.get('cultivation'),
                'signature_risks': info.get('signature_risks'),
            }
            context_parts.append(f"[Knowledge Base - {recipe_key.replace('_', ' ')} recipe]: {json.dumps(summary, indent=2)}")
            break

    mowing_aliases = {
        'rolling': 'rolling_frequency_under_stress',
        'green speed': 'greens_mowing_and_rolling_balance',
        'tournament speed': 'tournament_speed_tradeoffs',
        'scalp': 'scalping_prevention_program',
        'fairway mowing': 'fairway_mowing_frequency_management',
        'rough mowing': 'rough_mowing_and_clipping_management',
    }
    for alias, program_key in mowing_aliases.items():
        if alias in question_lower and program_key in load_mowing_programs():
            info = load_mowing_programs()[program_key]
            summary = {
                'topic': info.get('topic'),
                'primary_goal': info.get('primary_goal'),
                'suitable_sites': info.get('suitable_sites'),
                'core_principles': info.get('core_principles'),
                'benchmark_ranges': info.get('benchmark_ranges'),
                'cautions': info.get('cautions'),
                'monitoring': info.get('monitoring'),
            }
            context_parts.append(f"[Knowledge Base - {program_key.replace('_', ' ')} mowing]: {json.dumps(summary, indent=2)}")
            break

    salinity_aliases = {
        'ec': 'ec_monitoring_program',
        'salinity': 'salt_stress_diagnostics',
        'salt stress': 'salt_stress_diagnostics',
        'leaching': 'leaching_program_for_salts',
        'sodium': 'sodium_hazard_and_structure_loss',
        'reclaimed water': 'reclaimed_water_management',
        'gypsum': 'gypsum_and_amendment_decision_tree',
    }
    for alias, program_key in salinity_aliases.items():
        if alias in question_lower and program_key in load_salinity_management():
            info = load_salinity_management()[program_key]
            summary = {
                'topic': info.get('topic'),
                'primary_goal': info.get('primary_goal'),
                'suitable_sites': info.get('suitable_sites'),
                'core_principles': info.get('core_principles'),
                'benchmark_ranges': info.get('benchmark_ranges'),
                'cautions': info.get('cautions'),
                'monitoring': info.get('monitoring'),
            }
            context_parts.append(f"[Knowledge Base - {program_key.replace('_', ' ')} salinity]: {json.dumps(summary, indent=2)}")
            break

    drainage_aliases = {
        'surface drainage': 'surface_drainage_correction',
        'subsurface drainage': 'subsurface_drainage_evaluation',
        'perched water': 'layering_and_perched_water_table',
        'layering': 'layering_and_perched_water_table',
        'organic matter': 'organic_matter_profile_management',
        'black layer': 'black_layer_prevention_program',
        'construction mismatch': 'construction_profile_mismatch',
    }
    for alias, program_key in drainage_aliases.items():
        if alias in question_lower and program_key in load_drainage_rootzone_programs():
            info = load_drainage_rootzone_programs()[program_key]
            summary = {
                'topic': info.get('topic'),
                'triggers': info.get('triggers'),
                'program': info.get('program'),
                'monitoring': info.get('monitoring'),
                'cautions': info.get('cautions'),
            }
            context_parts.append(f"[Knowledge Base - {program_key.replace('_', ' ')} drainage]: {json.dumps(summary, indent=2)}")
            break

    overseeding_aliases = {
        'overseed': 'bermudagrass_overseeding_window',
        'overseeding': 'bermudagrass_overseeding_window',
        'transition': 'spring_transition_acceleration',
        'seedhead suppression': 'poa_annua_seedhead_suppression_program',
        'seedhead': 'poa_annua_seedhead_suppression_program',
        'establishment restriction': 'cool_season_overseeding_restrictions',
        'mowing seedlings': 'overseed_mowing_and_establishment',
        'transition failure': 'transition_failure_diagnostics',
    }
    for alias, program_key in overseeding_aliases.items():
        if alias in question_lower and program_key in load_overseeding_transition_programs():
            info = load_overseeding_transition_programs()[program_key]
            summary = {
                'topic': info.get('topic'),
                'primary_goal': info.get('primary_goal'),
                'suitable_sites': info.get('suitable_sites'),
                'core_principles': info.get('core_principles'),
                'benchmark_ranges': info.get('benchmark_ranges'),
                'cautions': info.get('cautions'),
                'monitoring': info.get('monitoring'),
            }
            context_parts.append(f"[Knowledge Base - {program_key.replace('_', ' ')} overseeding]: {json.dumps(summary, indent=2)}")
            break

    climate_aliases = {
        'transition zone': 'humid_transition_zone_cool_season',
        'humid transition zone': 'humid_transition_zone_cool_season',
        'northern cool season': 'northern_cool_season_intensive',
        'arid west': 'arid_west_warm_season',
        'desert': 'arid_west_warm_season',
        'humid southeast': 'humid_southeast_warm_season',
        'coastal': 'marine_cool_season_coastal',
        'marine climate': 'marine_cool_season_coastal',
        'upper midwest': 'upper_midwest_winter_stress',
        'winter stress': 'upper_midwest_winter_stress',
    }
    for alias, playbook_key in climate_aliases.items():
        if alias in question_lower and playbook_key in load_climate_zone_playbooks():
            info = load_climate_zone_playbooks()[playbook_key]
            summary = {
                'topic': info.get('topic'),
                'climate_profile': info.get('climate_profile'),
                'best_fit_surfaces': info.get('best_fit_surfaces'),
                'seasonal_priorities': info.get('seasonal_priorities'),
                'signature_risks': info.get('signature_risks'),
                'management_biases': info.get('management_biases'),
                'watchouts': info.get('watchouts'),
            }
            context_parts.append(f"[Knowledge Base - {playbook_key.replace('_', ' ')} climate]: {json.dumps(summary, indent=2)}")
            break

    tournament_aliases = {
        'green speed': 'greens_speed_ramp_plan',
        'speed ramp': 'greens_speed_ramp_plan',
        'firmness': 'firmness_and_moisture_tournament_plan',
        'moisture plan': 'firmness_and_moisture_tournament_plan',
        'fairway presentation': 'fairway_tournament_presentation_plan',
        'event recovery greens': 'event_recovery_greens_plan',
        'event recovery fairway': 'event_recovery_fairway_plan',
        'weather disruption': 'weather_disruption_event_plan',
        'tournament weather': 'weather_disruption_event_plan',
    }
    for alias, program_key in tournament_aliases.items():
        if alias in question_lower and program_key in load_tournament_prep_recovery():
            info = load_tournament_prep_recovery()[program_key]
            summary = {
                'topic': info.get('topic'),
                'objective': info.get('objective'),
                'prep_window': info.get('prep_window'),
                'prep_steps': info.get('prep_steps'),
                'during_event': info.get('during_event'),
                'recovery_steps': info.get('recovery_steps'),
                'failure_modes': info.get('failure_modes'),
            }
            context_parts.append(f"[Knowledge Base - {program_key.replace('_', ' ')} tournament]: {json.dumps(summary, indent=2)}")
            break

    nutrient_aliases = {
        'nitrogen deficiency': 'nitrogen_deficiency',
        'n deficiency': 'nitrogen_deficiency',
        'potassium deficiency': 'potassium_deficiency',
        'k deficiency': 'potassium_deficiency',
        'iron deficiency': 'iron_deficiency_or_color_loss',
        'color loss': 'iron_deficiency_or_color_loss',
        'phosphorus deficiency': 'phosphorus_deficiency_or_establishment_issue',
        'p deficiency': 'phosphorus_deficiency_or_establishment_issue',
        'micronutrient lockout': 'micronutrient_lockout_high_ph',
        'high ph chlorosis': 'micronutrient_lockout_high_ph',
        'fertilizer burn': 'salt_or_fertilizer_burn_diagnostics',
        'salt burn': 'salt_or_fertilizer_burn_diagnostics',
    }
    for alias, diagnostic_key in nutrient_aliases.items():
        if alias in question_lower and diagnostic_key in load_nutrient_diagnostics():
            info = load_nutrient_diagnostics()[diagnostic_key]
            summary = {
                'topic': info.get('topic'),
                'symptom_profile': info.get('symptom_profile'),
                'common_confusions': info.get('common_confusions'),
                'high_risk_sites': info.get('high_risk_sites'),
                'confirmation_steps': info.get('confirmation_steps'),
                'response_strategy': info.get('response_strategy'),
            }
            context_parts.append(f"[Knowledge Base - {diagnostic_key.replace('_', ' ')} nutrient]: {json.dumps(summary, indent=2)}")
            break

    calibration_aliases = {
        'sprayer output': 'sprayer_output_verification',
        'sprayer calibration': 'sprayer_output_verification',
        'mixing sequence': 'sprayer_mixing_sequence_workflow',
        'tank mixing': 'sprayer_mixing_sequence_workflow',
        'spreader pattern': 'spreader_pattern_testing',
        'granular conversion': 'granular_rate_per_1000_conversion',
        'per 1000 conversion': 'granular_rate_per_1000_conversion',
        'travel speed': 'travel_speed_checkpoint_workflow',
        'speed check': 'travel_speed_checkpoint_workflow',
        'recordkeeping': 'recordkeeping_and_post_application_review',
        'post application review': 'recordkeeping_and_post_application_review',
    }
    for alias, workflow_key in calibration_aliases.items():
        if alias in question_lower and workflow_key in load_calibration_workflows():
            info = load_calibration_workflows()[workflow_key]
            summary = {
                'topic': info.get('topic'),
                'objective': info.get('objective'),
                'when_to_use': info.get('when_to_use'),
                'key_steps': info.get('key_steps'),
                'common_failures': info.get('common_failures'),
                'documents_to_check': info.get('documents_to_check'),
            }
            context_parts.append(f"[Knowledge Base - {workflow_key.replace('_', ' ')} calibration]: {json.dumps(summary, indent=2)}")
            break

    seasonal_plan_aliases = {
        'transition zone': 'cool_season_transition_zone_calendar',
        'cool-season transition zone': 'cool_season_transition_zone_calendar',
        'northern cool season': 'northern_cool_season_calendar',
        'southeast warm season': 'warm_season_southeast_calendar',
        'warm-season southeast': 'warm_season_southeast_calendar',
        'arid west bermudagrass': 'arid_west_bermudagrass_calendar',
    }
    for alias, plan_key in seasonal_plan_aliases.items():
        if alias in question_lower and plan_key in load_seasonal_operating_plans():
            info = load_seasonal_operating_plans()[plan_key]
            summary = {
                'topic': info.get('topic'),
                'best_fit_surfaces': info.get('best_fit_surfaces'),
                'spring_priorities': info.get('spring_priorities'),
                'summer_priorities': info.get('summer_priorities'),
                'fall_priorities': info.get('fall_priorities'),
                'winter_priorities': info.get('winter_priorities'),
                'key_metrics': info.get('key_metrics'),
                'watchouts': info.get('watchouts'),
            }
            context_parts.append(f"[Knowledge Base - {plan_key.replace('_', ' ')} seasonal plan]: {json.dumps(summary, indent=2)}")
            break

    regional_pressure_aliases = {
        'transition zone pressure': 'transition_zone_cool_season_pressure',
        'cool-season transition pressure': 'transition_zone_cool_season_pressure',
        'northern cool season pressure': 'northern_cool_season_pressure',
        'southeast warm season pressure': 'southeast_warm_season_pressure',
        'arid west bermudagrass pressure': 'arid_west_bermudagrass_pressure',
        'pressure calendar': 'transition_zone_cool_season_pressure',
    }
    for alias, calendar_key in regional_pressure_aliases.items():
        if alias in question_lower and calendar_key in load_regional_pressure_calendars():
            info = load_regional_pressure_calendars()[calendar_key]
            summary = {
                'topic': info.get('topic'),
                'region': info.get('region'),
                'spring_pressures': info.get('spring_pressures'),
                'summer_pressures': info.get('summer_pressures'),
                'fall_pressures': info.get('fall_pressures'),
                'winter_pressures': info.get('winter_pressures'),
                'key_targets': info.get('key_targets'),
                'scouting_focus': info.get('scouting_focus'),
                'timing_biases': info.get('timing_biases'),
            }
            context_parts.append(f"[Knowledge Base - {calendar_key.replace('_', ' ')} pressure]: {json.dumps(summary, indent=2)}")
            break

    advanced_science_aliases = {
        'carbohydrate': 'cool_season_heat_carbohydrate_decline',
        'carbohydrate reserves': 'cool_season_heat_carbohydrate_decline',
        'heat stress physiology': 'cool_season_heat_carbohydrate_decline',
        'root respiration': 'root_respiration_oxygen_balance',
        'oxygen balance': 'root_respiration_oxygen_balance',
        'air filled porosity': 'usga_rootzone_porosity_hydraulic_conductivity',
        'air-filled porosity': 'usga_rootzone_porosity_hydraulic_conductivity',
        'hydraulic conductivity': 'usga_rootzone_porosity_hydraulic_conductivity',
        'rootzone porosity': 'usga_rootzone_porosity_hydraulic_conductivity',
        'organic matter physics': 'surface_organic_matter_physics',
        'surface organic matter': 'surface_organic_matter_physics',
        'perched water': 'perched_water_layering_diagnostics',
        'layering': 'perched_water_layering_diagnostics',
        'disease triangle': 'disease_triangle_leaf_wetness_microclimate',
        'leaf wetness': 'disease_triangle_leaf_wetness_microclimate',
        'dollar spot epidemiology': 'dollar_spot_epidemiology_nitrogen_leaf_wetness',
        'brown patch epidemiology': 'brown_patch_rhizoctonia_heat_humidity',
        'pgr rebound': 'pgr_growth_suppression_thermal_rebound',
        'growth potential': 'pgr_growth_suppression_thermal_rebound',
        'deficit irrigation': 'et_deficit_irrigation_syringing',
        'syringing': 'et_deficit_irrigation_syringing',
        'hydrophobicity': 'localized_dry_spot_hydrophobicity',
        'firmness': 'firmness_green_speed_plant_health_tradeoff',
        'green speed': 'firmness_green_speed_plant_health_tradeoff',
        'traffic recovery': 'traffic_recovery_carbohydrate_growth_rate',
        'winter injury': 'winter_crown_hydration_freeze_injury',
        'crown hydration': 'winter_crown_hydration_freeze_injury',
        'freeze injury': 'winter_crown_hydration_freeze_injury',
        'shade physiology': 'shade_light_carbohydrate_morphology',
        'low light': 'shade_light_carbohydrate_morphology',
        'nitrogen form': 'nitrogen_form_release_growth_stress_balance',
        'slow release nitrogen': 'nitrogen_form_release_growth_stress_balance',
        'salinity stress': 'salinity_osmotic_sodium_structure_stress',
        'sodium hazard': 'salinity_osmotic_sodium_structure_stress',
        'osmotic drought': 'salinity_osmotic_sodium_structure_stress',
        'nematode': 'nematode_root_pruning_stress_complex',
        'nematodes': 'nematode_root_pruning_stress_complex',
        'root pruning': 'nematode_root_pruning_stress_complex',
        'poa annua decline': 'poa_annua_vs_bentgrass_summer_decline',
        'poa decline': 'poa_annua_vs_bentgrass_summer_decline',
        'decline faster than bentgrass': 'poa_annua_vs_bentgrass_summer_decline',
        'wetting agent chemistry': 'wetting_agent_chemistry_functional_groups',
        'surfactant chemistry': 'wetting_agent_chemistry_functional_groups',
        'bicarbonate': 'bicarbonate_alkalinity_micronutrient_lockout',
        'bicarbonates': 'bicarbonate_alkalinity_micronutrient_lockout',
        'alkalinity': 'bicarbonate_alkalinity_micronutrient_lockout',
        'micronutrient lockout': 'bicarbonate_alkalinity_micronutrient_lockout',
        'pythium root dysfunction': 'pythium_root_dysfunction_vs_wet_wilt',
        'pythium root rot': 'pythium_root_dysfunction_vs_wet_wilt',
        'pythium vs wet wilt': 'pythium_root_dysfunction_vs_wet_wilt',
        'growing degree days': 'gdd_growth_potential_pgr_timing',
        'gdd': 'gdd_growth_potential_pgr_timing',
        'pgr timing': 'gdd_growth_potential_pgr_timing',
    }
    for alias, science_key in advanced_science_aliases.items():
        if alias in question_lower and science_key in load_advanced_turf_science():
            info = load_advanced_turf_science()[science_key]
            summary = {
                'domain': info.get('domain'),
                'principle': info.get('principle'),
                'mechanisms': info.get('mechanisms'),
                'field_indicators': info.get('field_indicators'),
                'decision_rules': info.get('decision_rules'),
                'management_implications': info.get('management_implications'),
                'benchmark_ranges': info.get('benchmark_ranges'),
                'cautions': info.get('cautions'),
                'source_basis': info.get('source_basis'),
            }
            context_parts.append(f"[Knowledge Base - {science_key.replace('_', ' ')} advanced science]: {json.dumps(summary, indent=2)}")
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

    # Classic symptom-language shortcuts for questions that describe a disease
    # without naming it. Keep these conservative so we add context, not a diagnosis.
    if (
        ('greasy' in question_lower or 'water-soaked' in question_lower or 'water soaked' in question_lower)
        and ('hot' in question_lower or 'wet' in question_lower or 'humid' in question_lower)
    ) or (
        'cottony mycelium' in question_lower and ('streak' in question_lower or 'overnight' in question_lower)
    ):
        found_diseases.append('pythium blight')

    if 'smoke ring' in question_lower or (
        'circular' in question_lower and 'patch' in question_lower and ('humid' in question_lower or 'night' in question_lower)
    ):
        found_diseases.append('brown patch')

    return list(set(found_diseases))


def extract_weed_names(question: str) -> List[str]:
    """Extract weed names mentioned in a question."""
    found_weeds = []
    question_lower = question.lower()

    for weed_name in load_weeds().keys():
        display_name = weed_name.replace('_', ' ')
        if display_name in question_lower or weed_name in question_lower:
            found_weeds.append(display_name)

    return list(set(found_weeds))


def extract_pest_names(question: str) -> List[str]:
    """Extract insect pest names mentioned in a question."""
    found_pests = []
    question_lower = question.lower()
    aliases = {
        'grub': 'white grubs',
        'grubs': 'white grubs',
        'webworm': 'sod webworms',
        'webworms': 'sod webworms',
        'abw': 'annual bluegrass weevil',
        'chinch bug': 'chinch bugs',
        'billbug': 'billbugs',
        'cutworm': 'cutworms',
    }

    for alias, display in aliases.items():
        if alias in question_lower:
            found_pests.append(display)

    for pest_name in load_pests().keys():
        display_name = pest_name.replace('_', ' ')
        if display_name in question_lower or pest_name in question_lower:
            found_pests.append(display_name)

    return list(set(found_pests))


def extract_turfgrass_names(question: str) -> List[str]:
    """Extract turfgrass species names mentioned in a question."""
    found_turfgrasses = []
    question_lower = question.lower()
    aliases = {
        'bentgrass': 'creeping bentgrass',
        'poa annua': 'annual bluegrass',
        'annual bluegrass': 'annual bluegrass',
        'kentucky bluegrass': 'kentucky bluegrass',
        'bluegrass': 'kentucky bluegrass',
        'kbg': 'kentucky bluegrass',
        'tall fescue': 'tall fescue',
        'fescue': 'tall fescue',
        'ryegrass': 'perennial ryegrass',
        'fine fescue': 'fine fescue',
        'bermuda': 'bermudagrass',
        'bermudagrass': 'bermudagrass',
        'zoysia': 'zoysiagrass',
        'zoysiagrass': 'zoysiagrass',
        'st augustine': 'st augustinegrass',
        'st. augustine': 'st augustinegrass',
        'centipede': 'centipedegrass',
    }

    for alias, display in aliases.items():
        if alias in question_lower:
            found_turfgrasses.append(display)

    return list(set(found_turfgrasses))


def extract_abiotic_stress_names(question: str) -> List[str]:
    """Extract abiotic stress/non-pest problem names mentioned in a question."""
    found_stresses = []
    question_lower = question.lower()
    aliases = {
        'localized dry spot': 'localized dry spot',
        'dry spot': 'localized dry spot',
        'lds': 'localized dry spot',
        'heat stress': 'heat stress',
        'drought': 'drought stress',
        'wilt': 'drought stress',
        'too wet': 'overwatering',
        'overwater': 'overwatering',
        'compaction': 'compaction',
        'compact': 'compaction',
        'shade': 'shade stress',
        'traffic': 'traffic stress',
        'wear': 'traffic stress',
        'scalp': 'scalping',
        'scalping': 'scalping',
        'herbicide injury': 'herbicide injury',
        'spray injury': 'herbicide injury',
        'fertilizer burn': 'fertilizer burn',
        'salt burn': 'fertilizer burn',
        'pgr stress': 'pgr stress',
        'black layer': 'black layer',
    }

    for alias, display in aliases.items():
        if alias in question_lower:
            found_stresses.append(display)

    return list(set(found_stresses))


def extract_timing_window_names(question: str) -> List[str]:
    """Extract timing window topics mentioned in a question."""
    question_lower = question.lower()
    if not any(term in question_lower for term in ['when', 'timing', 'window', 'soil temp', 'soil temperature', 'schedule', 'preventive', 'pre-emergent', 'pre emergent', 'aerate', 'aeration']):
        return []

    found_windows = []
    for timing_key, info in load_timing_windows().items():
        if _timing_window_score(question_lower, timing_key, info):
            found_windows.append(timing_key.replace('_', ' '))

    return list(set(found_windows))


def extract_fertility_program_names(question: str) -> List[str]:
    """Extract fertility-program topics mentioned in a question."""
    found_programs = []
    question_lower = question.lower()
    aliases = {
        'spoon feeding': 'greens spoon feeding',
        'spoon-feeding': 'greens spoon feeding',
        'fall nitrogen': 'cool season fall nitrogen',
        'summer nitrogen': 'warm season growth season nitrogen',
        'potassium': 'sand based potassium and leaching',
        'iron': 'iron color vs true nitrogen need',
        'phosphorus': 'phosphorus for establishment only',
    }
    for alias, display in aliases.items():
        if alias in question_lower:
            found_programs.append(display)
    return list(set(found_programs))


def extract_irrigation_program_names(question: str) -> List[str]:
    """Extract irrigation-program topics mentioned in a question."""
    found_programs = []
    question_lower = question.lower()
    aliases = {
        'deficit irrigation': 'deficit irrigation greens',
        'syring': 'syringing for canopy cooling',
        'hand water': 'hand watering hot spots',
        'wetting agent': 'wetting agent strategy for lds',
        'deep and infrequent': 'fairway deep infrequent irrigation',
        'deep infrequent': 'fairway deep infrequent irrigation',
        'uniformity': 'irrigation uniformity audit',
        'irrigation audit': 'irrigation uniformity audit',
    }
    for alias, display in aliases.items():
        if alias in question_lower:
            found_programs.append(display)
    return list(set(found_programs))


def extract_cultivation_program_names(question: str) -> List[str]:
    """Extract cultivation-program topics mentioned in a question."""
    found_programs = []
    question_lower = question.lower()
    aliases = {
        'core aeration': 'core aeration greens',
        'core aerate': 'core aeration greens',
        'aerification': 'core aeration greens',
        'venting': 'summer venting and needle tining',
        'needle tine': 'summer venting and needle tining',
        'topdress': 'frequent light topdressing',
        'solid tine': 'solid tining and root pruning balance',
        'verticut': 'verticutting and grooming management',
        'grooming': 'verticutting and grooming management',
        'fairway cultivation': 'fairway cultivation and topdressing',
    }
    for alias, display in aliases.items():
        if alias in question_lower:
            found_programs.append(display)
    return list(set(found_programs))


def extract_diagnostic_framework_names(question: str) -> List[str]:
    """Extract diagnostic-framework topics mentioned in a question."""
    found_frameworks = []
    question_lower = question.lower()
    aliases = {
        'wilt': 'wilt vs disease on greens',
        'ring': 'ring pattern diagnostics',
        'rootzone': 'rootzone failure framework',
        'herbicide injury': 'herbicide injury framework',
        'spray injury': 'herbicide injury framework',
        'pgr stress': 'pgr stress framework',
        'traffic': 'traffic compaction decline',
        'compaction': 'traffic compaction decline',
        'anthracnose': 'anthracnose decline framework',
        'salt stress': 'salt vs drought framework',
        'salinity': 'salt vs drought framework',
        'spring dead spot': 'bermuda spring transition failure',
        'bermuda transition': 'bermuda spring transition failure',
        'slow green up': 'warm season slow greenup framework',
        'slow green-up': 'warm season slow greenup framework',
        'zoysia': 'warm season slow greenup framework',
        'water quality': 'water quality chemistry framework',
        'reclaimed water': 'water quality chemistry framework',
        'alkalinity': 'water quality chemistry framework',
        'nematode sample': 'nematode sampling interpretation framework',
        'nematode assay': 'nematode sampling interpretation framework',
        'carryover': 'herbicide carryover framework',
        'residual herbicide': 'herbicide carryover framework',
        'grub damage': 'insect feeding pattern framework',
        'abw': 'insect feeding pattern framework',
        'webworm': 'insect feeding pattern framework',
        'cutworm': 'insect feeding pattern framework',
        'chinch bug': 'insect feeding pattern framework',
        'species fit': 'species fit renovation framework',
        'renovation': 'species fit renovation framework',
        'ryegrass hanging on': 'overseeded transition competition framework',
        'ryegrass is hanging on': 'overseeded transition competition framework',
        'hanging on too long': 'overseeded transition competition framework',
        'spring transition ryegrass': 'overseeded transition competition framework',
        'seedlings dying': 'seedling establishment failure framework',
        'germination looked fine': 'seedling establishment failure framework',
        'establishment failure': 'seedling establishment failure framework',
        'spray passes': 'application pattern coverage framework',
        'nozzle overlap': 'application pattern coverage framework',
        'application pattern': 'application pattern coverage framework',
        'repeated rolling': 'mechanical stress budget framework',
        'rolling frequency': 'mechanical stress budget framework',
        'tournament prep stress': 'mechanical stress budget framework',
        'frayed leaf tips': 'cut quality leaf shredding framework',
        'cut quality': 'cut quality leaf shredding framework',
        'leaf shredding': 'cut quality leaf shredding framework',
        'topdressing drift': 'topdressing program drift framework',
        'sand compatibility': 'topdressing program drift framework',
        'layering after topdressing': 'topdressing program drift framework',
    }
    for alias, display in aliases.items():
        escaped = re.escape(alias)
        prefix = r"\b" if alias[:1].isalnum() else ""
        suffix = r"\b" if alias[-1:].isalnum() else ""
        if re.search(prefix + escaped + suffix, question_lower):
            found_frameworks.append(display)
    return list(set(found_frameworks))


def extract_mowing_program_names(question: str) -> List[str]:
    """Extract mowing and rolling program topics mentioned in a question."""
    found_programs = []
    question_lower = question.lower()
    aliases = {
        'rolling': 'rolling frequency under stress',
        'green speed': 'greens mowing and rolling balance',
        'tournament speed': 'tournament speed tradeoffs',
        'scalp': 'scalping prevention program',
        'fairway mowing': 'fairway mowing frequency management',
        'rough mowing': 'rough mowing and clipping management',
    }
    for alias, display in aliases.items():
        if alias in question_lower:
            found_programs.append(display)
    return list(set(found_programs))


def extract_salinity_management_names(question: str) -> List[str]:
    """Extract salinity and EC management topics mentioned in a question."""
    found_programs = []
    question_lower = question.lower()
    aliases = {
        'ec': 'ec monitoring program',
        'salinity': 'salt stress diagnostics',
        'salt stress': 'salt stress diagnostics',
        'leaching': 'leaching program for salts',
        'sodium': 'sodium hazard and structure loss',
        'reclaimed water': 'reclaimed water management',
        'gypsum': 'gypsum and amendment decision framework',
    }
    for alias, display in aliases.items():
        if alias in question_lower:
            found_programs.append(display)
    return list(set(found_programs))


def extract_drainage_rootzone_program_names(question: str) -> List[str]:
    """Extract drainage and rootzone-management topics mentioned in a question."""
    found_programs = []
    question_lower = question.lower()
    aliases = {
        'surface drainage': 'surface drainage correction',
        'subsurface drainage': 'subsurface drainage evaluation',
        'perched water': 'layering and perched water table',
        'layering': 'layering and perched water table',
        'organic matter': 'organic matter profile management',
        'black layer': 'black layer prevention program',
        'construction mismatch': 'construction profile mismatch',
    }
    for alias, display in aliases.items():
        if alias in question_lower:
            found_programs.append(display)
    return list(set(found_programs))


def extract_overseeding_transition_program_names(question: str) -> List[str]:
    """Extract overseeding and transition topics mentioned in a question."""
    found_programs = []
    question_lower = question.lower()
    aliases = {
        'overseed': 'bermudagrass overseeding window',
        'overseeding': 'bermudagrass overseeding window',
        'transition': 'spring transition acceleration',
        'seedhead suppression': 'poa annua seedhead suppression program',
        'seedhead': 'poa annua seedhead suppression program',
        'establishment restriction': 'cool season overseeding restrictions',
        'mowing seedlings': 'overseed mowing and establishment',
        'transition failure': 'transition failure diagnostics',
    }
    for alias, display in aliases.items():
        if alias in question_lower:
            found_programs.append(display)
    return list(set(found_programs))


def extract_disease_ipm_playbook_names(question: str) -> List[str]:
    """Extract disease IPM playbook topics mentioned in a question."""
    found_playbooks = []
    question_lower = question.lower()
    aliases = {
        'dollar spot': 'dollar spot ipm',
        'brown patch': 'brown patch ipm',
        'pythium blight': 'pythium blight ipm',
        'summer patch': 'summer patch ipm',
        'anthracnose': 'anthracnose ipm',
        'fairy ring': 'fairy ring ipm',
    }
    for alias, display in aliases.items():
        if alias in question_lower:
            found_playbooks.append(display)
    return list(set(found_playbooks))


def extract_surface_management_recipe_names(question: str) -> List[str]:
    """Extract surface management recipe topics mentioned in a question."""
    found_recipes = []
    question_lower = question.lower()
    aliases = {
        'bentgrass greens': 'bentgrass greens recipe',
        'poa greens': 'poa annua greens recipe',
        'bermudagrass fairways': 'bermudagrass fairways recipe',
        'tall fescue sports turf': 'tall fescue sports turf recipe',
        'zoysiagrass fairways': 'zoysiagrass fairways recipe',
        'overseeded bermudagrass': 'ryegrass overseeded transition recipe',
        'spring transition': 'ryegrass overseeded transition recipe',
    }
    for alias, display in aliases.items():
        if alias in question_lower:
            found_recipes.append(display)
    return list(set(found_recipes))


def extract_climate_zone_playbook_names(question: str) -> List[str]:
    """Extract climate-zone playbook topics mentioned in a question."""
    found_playbooks = []
    question_lower = question.lower()
    aliases = {
        'transition zone': 'humid transition zone cool season',
        'humid transition zone': 'humid transition zone cool season',
        'northern cool season': 'northern cool season intensive',
        'arid west': 'arid west warm season',
        'desert': 'arid west warm season',
        'humid southeast': 'humid southeast warm season',
        'coastal': 'marine cool season coastal',
        'marine climate': 'marine cool season coastal',
        'upper midwest': 'upper midwest winter stress',
        'winter stress': 'upper midwest winter stress',
    }
    for alias, display in aliases.items():
        if alias in question_lower:
            found_playbooks.append(display)
    return list(set(found_playbooks))


def extract_tournament_prep_recovery_names(question: str) -> List[str]:
    """Extract tournament prep and recovery topics mentioned in a question."""
    found_programs = []
    question_lower = question.lower()
    aliases = {
        'green speed': 'greens speed ramp plan',
        'speed ramp': 'greens speed ramp plan',
        'firmness': 'firmness and moisture tournament plan',
        'moisture plan': 'firmness and moisture tournament plan',
        'fairway presentation': 'fairway tournament presentation plan',
        'event recovery greens': 'event recovery greens plan',
        'event recovery fairway': 'event recovery fairway plan',
        'weather disruption': 'weather disruption event plan',
        'tournament weather': 'weather disruption event plan',
    }
    for alias, display in aliases.items():
        if alias in question_lower:
            found_programs.append(display)
    return list(set(found_programs))


def extract_nutrient_diagnostic_names(question: str) -> List[str]:
    """Extract nutrient diagnostic topics mentioned in a question."""
    found_diagnostics = []
    question_lower = question.lower()
    aliases = {
        'nitrogen deficiency': 'nitrogen deficiency',
        'n deficiency': 'nitrogen deficiency',
        'potassium deficiency': 'potassium deficiency',
        'k deficiency': 'potassium deficiency',
        'iron deficiency': 'iron deficiency or color loss',
        'color loss': 'iron deficiency or color loss',
        'phosphorus deficiency': 'phosphorus deficiency or establishment issue',
        'p deficiency': 'phosphorus deficiency or establishment issue',
        'micronutrient lockout': 'micronutrient lockout high ph',
        'high ph chlorosis': 'micronutrient lockout high ph',
        'fertilizer burn': 'salt or fertilizer burn diagnostics',
        'salt burn': 'salt or fertilizer burn diagnostics',
    }
    for alias, display in aliases.items():
        if alias in question_lower:
            found_diagnostics.append(display)
    return list(set(found_diagnostics))


def extract_calibration_workflow_names(question: str) -> List[str]:
    """Extract calibration workflow topics mentioned in a question."""
    found_workflows = []
    question_lower = question.lower()
    aliases = {
        'sprayer output': 'sprayer output verification',
        'sprayer calibration': 'sprayer output verification',
        'mixing sequence': 'sprayer mixing sequence workflow',
        'tank mixing': 'sprayer mixing sequence workflow',
        'spreader pattern': 'spreader pattern testing',
        'granular conversion': 'granular rate per 1000 conversion',
        'per 1000 conversion': 'granular rate per 1000 conversion',
        'travel speed': 'travel speed checkpoint workflow',
        'speed check': 'travel speed checkpoint workflow',
        'recordkeeping': 'recordkeeping and post application review',
        'post application review': 'recordkeeping and post application review',
    }
    for alias, display in aliases.items():
        if alias in question_lower:
            found_workflows.append(display)
    return list(set(found_workflows))


def extract_seasonal_operating_plan_names(question: str) -> List[str]:
    """Extract seasonal operating plan topics mentioned in a question."""
    found_plans = []
    question_lower = question.lower()
    aliases = {
        'transition zone': 'cool season transition zone',
        'cool-season transition zone': 'cool season transition zone',
        'northern cool season': 'northern cool season',
        'southeast warm season': 'warm season southeast',
        'warm-season southeast': 'warm season southeast',
        'arid west bermudagrass': 'arid west bermudagrass',
    }
    for alias, display in aliases.items():
        if alias in question_lower:
            found_plans.append(display)
    return list(set(found_plans))


def extract_regional_pressure_calendar_names(question: str) -> List[str]:
    """Extract regional pressure calendar topics mentioned in a question."""
    found_calendars = []
    question_lower = question.lower()
    aliases = {
        'transition zone pressure': 'transition zone cool season pressure',
        'cool-season transition pressure': 'transition zone cool season pressure',
        'northern cool season pressure': 'northern cool season pressure',
        'southeast warm season pressure': 'southeast warm season pressure',
        'arid west bermudagrass pressure': 'arid west bermudagrass pressure',
    }
    for alias, display in aliases.items():
        if alias in question_lower:
            found_calendars.append(display)
    return list(set(found_calendars))


def extract_advanced_turf_science_names(question: str) -> List[str]:
    """Extract advanced turf science topics mentioned in a question."""
    found_topics = []
    question_lower = question.lower()
    aliases = {
        'carbohydrate': 'cool season heat carbohydrate decline',
        'carbohydrate reserves': 'cool season heat carbohydrate decline',
        'heat stress physiology': 'cool season heat carbohydrate decline',
        'root respiration': 'root respiration oxygen balance',
        'oxygen balance': 'root respiration oxygen balance',
        'air filled porosity': 'usga rootzone porosity hydraulic conductivity',
        'air-filled porosity': 'usga rootzone porosity hydraulic conductivity',
        'hydraulic conductivity': 'usga rootzone porosity hydraulic conductivity',
        'rootzone porosity': 'usga rootzone porosity hydraulic conductivity',
        'organic matter physics': 'surface organic matter physics',
        'surface organic matter': 'surface organic matter physics',
        'perched water': 'perched water layering diagnostics',
        'layering': 'perched water layering diagnostics',
        'disease triangle': 'disease triangle leaf wetness microclimate',
        'leaf wetness': 'disease triangle leaf wetness microclimate',
        'dollar spot epidemiology': 'dollar spot epidemiology nitrogen leaf wetness',
        'brown patch epidemiology': 'brown patch rhizoctonia heat humidity',
        'pgr rebound': 'pgr growth suppression thermal rebound',
        'growth potential': 'pgr growth suppression thermal rebound',
        'deficit irrigation': 'et deficit irrigation syringing',
        'syringing': 'et deficit irrigation syringing',
        'hydrophobicity': 'localized dry spot hydrophobicity',
        'firmness': 'firmness green speed plant health tradeoff',
        'green speed': 'firmness green speed plant health tradeoff',
        'traffic recovery': 'traffic recovery carbohydrate growth rate',
        'winter injury': 'winter crown hydration freeze injury',
        'crown hydration': 'winter crown hydration freeze injury',
        'freeze injury': 'winter crown hydration freeze injury',
        'shade physiology': 'shade light carbohydrate morphology',
        'low light': 'shade light carbohydrate morphology',
        'nitrogen form': 'nitrogen form release growth stress balance',
        'slow release nitrogen': 'nitrogen form release growth stress balance',
        'salinity stress': 'salinity osmotic sodium structure stress',
        'sodium hazard': 'salinity osmotic sodium structure stress',
        'osmotic drought': 'salinity osmotic sodium structure stress',
        'nematode': 'nematode root pruning stress complex',
        'nematodes': 'nematode root pruning stress complex',
        'root pruning': 'nematode root pruning stress complex',
        'poa annua decline': 'poa annua vs bentgrass summer decline',
        'poa decline': 'poa annua vs bentgrass summer decline',
        'decline faster than bentgrass': 'poa annua vs bentgrass summer decline',
        'wetting agent chemistry': 'wetting agent chemistry functional groups',
        'surfactant chemistry': 'wetting agent chemistry functional groups',
        'bicarbonate': 'bicarbonate alkalinity micronutrient lockout',
        'bicarbonates': 'bicarbonate alkalinity micronutrient lockout',
        'alkalinity': 'bicarbonate alkalinity micronutrient lockout',
        'micronutrient lockout': 'bicarbonate alkalinity micronutrient lockout',
        'pythium root dysfunction': 'pythium root dysfunction vs wet wilt',
        'pythium root rot': 'pythium root dysfunction vs wet wilt',
        'pythium vs wet wilt': 'pythium root dysfunction vs wet wilt',
        'growing degree days': 'gdd growth potential pgr timing',
        'gdd': 'gdd growth potential pgr timing',
        'pgr timing': 'gdd growth potential pgr timing',
        'anthracnose basal rot': 'anthracnose basal rot stress complex',
        'anthracnose decline': 'anthracnose basal rot stress complex',
        'basal rot': 'anthracnose basal rot stress complex',
        'fairy ring hydrophobicity': 'fairy ring hydrophobicity nitrogen masking',
        'fairy ring masking': 'fairy ring hydrophobicity nitrogen masking',
        'green ring': 'fairy ring hydrophobicity nitrogen masking',
        'soil ph buffering': 'soil ph buffering acidification programs',
        'acidification program': 'soil ph buffering acidification programs',
        'water acidification': 'soil ph buffering acidification programs',
        'spring dead spot': 'bermudagrass spring dead spot transition recovery',
        'bermuda spring recovery': 'bermudagrass spring dead spot transition recovery',
        'bermuda transition': 'bermudagrass spring dead spot transition recovery',
        'salt vs drought': 'salt vs drought ec moisture interpretation',
        'salt stress versus drought': 'salt vs drought ec moisture interpretation',
        'osmotic stress': 'salt vs drought ec moisture interpretation',
        'zoysia green up': 'zoysiagrass spring greenup thatch temperature',
        'zoysia green-up': 'zoysiagrass spring greenup thatch temperature',
        'zoysia spring lag': 'zoysiagrass spring greenup thatch temperature',
        'bermuda shade': 'bermudagrass shade cold carbohydrate limits',
        'bermudagrass shade': 'bermudagrass shade cold carbohydrate limits',
        'fall hardening': 'warm season fall hardening winter survival',
        'winter survival': 'warm season fall hardening winter survival',
        'reclaimed water nutrient credit': 'reclaimed water nutrient credit salt balance',
        'reclaimed water salts': 'reclaimed water nutrient credit salt balance',
        'effluent water': 'reclaimed water nutrient credit salt balance',
        'sar': 'gypsum sar dispersion decision logic',
        'soil dispersion': 'gypsum sar dispersion decision logic',
        'gypsum decision': 'gypsum sar dispersion decision logic',
        'nematode lab': 'nematode lab interpretation threshold context',
        'nematode assay': 'nematode lab interpretation threshold context',
        'nematode threshold': 'nematode lab interpretation threshold context',
        'nematicide expectations': 'nematicide expectation root recovery logic',
        'nematicide recovery': 'nematicide expectation root recovery logic',
        'herbicide mode of action': 'herbicide mode of action injury patterns',
        'herbicide injury pattern': 'herbicide mode of action injury patterns',
        'herbicide carryover': 'herbicide carryover residual transition risk',
        'residual herbicide': 'herbicide carryover residual transition risk',
        'carryover risk': 'herbicide carryover residual transition risk',
        'tournament stress budget': 'tournament greens stress budget model',
        'greens conditioning stress': 'tournament greens stress budget model',
        'greens conditioning budget': 'tournament greens stress budget model',
        'conditioning budget': 'tournament greens stress budget model',
        'tournament fairway traffic': 'tournament fairway tee recovery traffic model',
        'tournament tee traffic': 'tournament fairway tee recovery traffic model',
        'abw timing': 'annual bluegrass weevil lifecycle threshold timing',
        'annual bluegrass weevil timing': 'annual bluegrass weevil lifecycle threshold timing',
        'abw lifecycle': 'annual bluegrass weevil lifecycle threshold timing',
        'grub threshold': 'white grub species threshold recovery logic',
        'white grub threshold': 'white grub species threshold recovery logic',
        'sod webworm': 'sod webworm cutworm night feeding diagnostics',
        'cutworm feeding': 'sod webworm cutworm night feeding diagnostics',
        'chinch bug drought': 'chinch bug heat drought interaction model',
        'chinch bug heat stress': 'chinch bug heat drought interaction model',
        'species fit': 'species fit surface region tradeoff model',
        'surface fit': 'species fit surface region tradeoff model',
        'renovation decision': 'renovation vs rescue program decision model',
        'renovation versus rescue': 'renovation vs rescue program decision model',
        'ryegrass hanging on': 'overseeded ryegrass transition competition model',
        'ryegrass is hanging on': 'overseeded ryegrass transition competition model',
        'hanging on too long': 'overseeded ryegrass transition competition model',
        'spring transition ryegrass': 'overseeded ryegrass transition competition model',
        'bermuda transition competition': 'overseeded ryegrass transition competition model',
        'seedling establishment': 'seedling establishment temperature moisture oxygen balance',
        'seedlings dying': 'seedling establishment temperature moisture oxygen balance',
        'germination looked fine': 'seedling establishment temperature moisture oxygen balance',
        'cultivar diversity': 'cultivar diversity stress disease buffering',
        'mixed cultivars': 'cultivar diversity stress disease buffering',
        'sprayer coverage': 'sprayer coverage nozzle pressure canopy deposition',
        'nozzle pressure': 'sprayer coverage nozzle pressure canopy deposition',
        'application pattern': 'sprayer coverage nozzle pressure canopy deposition',
        'rolling frequency': 'roller frequency mechanical stress budget',
        'repeated rolling': 'roller frequency mechanical stress budget',
        'cec': 'soil test cec base saturation practical limits',
        'base saturation': 'soil test cec base saturation practical limits',
        'spray water ph': 'spray water ph hardness adjuvant interaction model',
        'water hardness spray': 'spray water ph hardness adjuvant interaction model',
        'adjuvant interaction': 'spray water ph hardness adjuvant interaction model',
        'mower sharpness': 'mower sharpness leaf shredding disease mimic model',
        'leaf shredding': 'mower sharpness leaf shredding disease mimic model',
        'cut quality': 'mower sharpness leaf shredding disease mimic model',
        'topdressing consistency': 'topdressing organic matter dilution layering drift',
        'organic matter dilution': 'topdressing organic matter dilution layering drift',
        'sand compatibility': 'topdressing organic matter dilution layering drift',
    }
    for alias, display in aliases.items():
        escaped = re.escape(alias)
        prefix = r"\b" if alias[:1].isalnum() else ""
        suffix = r"\b" if alias[-1:].isalnum() else ""
        if re.search(prefix + escaped + suffix, question_lower):
            found_topics.append(display)
    return list(set(found_topics))


def _timing_window_score(question_lower: str, timing_key: str, info: dict) -> int:
    """Score timing-window relevance while ignoring generic timing words."""
    score = 0
    topic = str(info.get('topic', '')).lower()
    related_targets = [str(target).replace('_', ' ').lower() for target in info.get('related_targets', [])]

    for target in related_targets:
        if target and target in question_lower:
            score += 5

    key_terms = set(timing_key.replace('_', ' ').split())
    topic_terms = set(topic.split())
    generic = {
        'timing', 'window', 'turf', 'season', 'seasonal', 'preventive',
        'pre', 'post', 'control', 'response',
    }
    for term in sorted((key_terms | topic_terms) - generic):
        if len(term) > 4 and term in question_lower:
            score += 2

    if 'aerate' in question_lower or 'aeration' in question_lower:
        if 'aeration' in timing_key:
            score += 6
        if 'warm' in question_lower and 'warm_season' in timing_key:
            score += 10
        if 'cool' in question_lower and 'cool_season' in timing_key:
            score += 10
        if any(term in question_lower for term in ['bermuda', 'bermudagrass', 'zoysia', 'zoysiagrass', 'st augustine', 'centipede']):
            if 'warm_season' in timing_key:
                score += 8
            if 'cool_season' in timing_key:
                score -= 8
        if any(term in question_lower for term in ['bentgrass', 'bluegrass', 'fescue', 'ryegrass']):
            if 'cool_season' in timing_key:
                score += 8
            if 'warm_season' in timing_key:
                score -= 8

    if 'curative' in question_lower and 'curative' in timing_key:
        score += 6
    if 'preventive' in question_lower and 'preventive' in timing_key:
        score += 6

    return max(score, 0)


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
        # Put structured data first so it survives context truncation.
        return f"--- STRUCTURED TURF KNOWLEDGE BASE DATA ---\n\n{kb_context}\n\n--- RETRIEVED SOURCE CONTEXT ---\n\n{existing_context}"

    return existing_context
