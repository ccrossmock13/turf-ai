"""Audit the full structured turf knowledge base.

This complements audit_structured_kb.py, which focuses on product labels. This
script checks cross-links and shape across disease, weed, pest, turfgrass, and
abiotic stress records.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from knowledge_base import (  # noqa: E402
    load_advanced_turf_science,
    load_abiotic_stress,
    load_calibration_workflows,
    load_climate_zone_playbooks,
    load_cultivation_programs,
    load_diseases,
    load_diagnostic_frameworks,
    load_nutrient_diagnostics,
    load_fertility_programs,
    load_irrigation_programs,
    load_disease_ipm_playbooks,
    load_mowing_programs,
    load_pests,
    load_salinity_management,
    load_drainage_rootzone_programs,
    load_overseeding_transition_programs,
    load_regional_pressure_calendars,
    load_seasonal_operating_plans,
    load_surface_management_recipes,
    load_timing_windows,
    load_tournament_prep_recovery,
    load_products,
    load_turfgrasses,
    load_weeds,
)


REQUIRED_FIELDS = {
    "diseases": ["symptoms", "environmental_triggers", "cultural_control", "chemical_control"],
    "weeds": ["type", "life_cycle", "identification", "timing", "cultural_control", "chemical_control"],
    "pests": ["type", "damage", "scouting", "cultural_control", "chemical_control"],
    "turfgrasses": ["season", "primary_uses", "strengths", "weaknesses", "management", "diagnostic_notes"],
    "abiotic_stress": ["category", "common_sites", "symptoms", "diagnosis", "management"],
    "timing_windows": ["topic", "trigger", "primary_window", "related_targets", "cautions"],
    "fertility_programs": ["topic", "primary_goal", "suitable_sites", "core_principles", "benchmark_ranges", "cautions"],
    "irrigation_programs": ["topic", "primary_goal", "triggers", "program", "monitoring", "cautions"],
    "cultivation_programs": ["topic", "primary_goal", "timing", "methods", "expected_benefits", "cautions"],
    "diagnostic_frameworks": ["problem_space", "first_checks", "differentials", "confirmatory_signs", "avoid_assumptions", "escalation"],
    "mowing_programs": ["topic", "primary_goal", "suitable_sites", "core_principles", "benchmark_ranges", "cautions"],
    "salinity_management": ["topic", "primary_goal", "suitable_sites", "core_principles", "benchmark_ranges", "cautions"],
    "drainage_rootzone_programs": ["topic", "triggers", "program", "monitoring", "cautions"],
    "overseeding_transition_programs": ["topic", "primary_goal", "suitable_sites", "core_principles", "benchmark_ranges", "cautions"],
    "disease_ipm_playbooks": ["topic", "target_disease", "high_risk_sites", "scouting_focus", "environmental_drivers", "cultural_program", "chemical_strategy", "monitoring"],
    "surface_management_recipes": ["surface", "primary_goals", "mowing_and_speed", "water_management", "fertility", "cultivation", "signature_risks"],
    "climate_zone_playbooks": ["topic", "climate_profile", "best_fit_surfaces", "seasonal_priorities", "signature_risks", "management_biases", "watchouts"],
    "tournament_prep_recovery": ["topic", "objective", "prep_window", "prep_steps", "during_event", "recovery_steps", "failure_modes"],
    "nutrient_diagnostics": ["topic", "symptom_profile", "common_confusions", "high_risk_sites", "confirmation_steps", "response_strategy"],
    "calibration_workflows": ["topic", "objective", "when_to_use", "key_steps", "common_failures", "documents_to_check"],
    "seasonal_operating_plans": ["topic", "best_fit_surfaces", "spring_priorities", "summer_priorities", "fall_priorities", "winter_priorities", "key_metrics", "watchouts"],
    "regional_pressure_calendars": ["topic", "region", "spring_pressures", "summer_pressures", "fall_pressures", "winter_pressures", "key_targets", "scouting_focus", "timing_biases"],
    "advanced_turf_science": ["domain", "principle", "mechanisms", "field_indicators", "decision_rules", "management_implications", "cautions", "source_basis"],
}


def _product_index(products: dict) -> dict[str, dict]:
    index = {}
    for category, items in products.items():
        for active_ingredient, info in items.items():
            index[active_ingredient] = {"category": category, "active_ingredient": active_ingredient, **info}
            for trade_name in info.get("trade_names", []):
                index[str(trade_name).lower()] = {"category": category, "active_ingredient": active_ingredient, **info}
    return index


def _is_missing(value) -> bool:
    return value in (None, "", [], {})


def _audit_record(collection: str, key: str, info: dict, product_index: dict[str, dict]) -> dict:
    warnings = []
    missing_fields = [
        field for field in REQUIRED_FIELDS.get(collection, [])
        if field not in info or _is_missing(info.get(field))
    ]
    if missing_fields:
        warnings.append("missing_required_fields")

    unresolved_products = []
    chemical_control = info.get("chemical_control", {})
    if isinstance(chemical_control, dict):
        for product_name in chemical_control.get("top_products", []):
            if str(product_name).lower() not in product_index:
                unresolved_products.append(product_name)
    if unresolved_products:
        warnings.append("unresolved_top_products")

    empty_nested_sections = []
    for field, value in info.items():
        if isinstance(value, dict) and not value:
            empty_nested_sections.append(field)
    if empty_nested_sections:
        warnings.append("empty_nested_sections")

    return {
        "collection": collection,
        "key": key,
        "missing_fields": missing_fields,
        "unresolved_top_products": unresolved_products,
        "empty_nested_sections": empty_nested_sections,
        "warnings": warnings,
    }


def run_audit() -> dict:
    products = load_products()
    product_index = _product_index(products)
    collections = {
        "diseases": load_diseases(),
        "weeds": load_weeds(),
        "pests": load_pests(),
        "turfgrasses": load_turfgrasses(),
        "abiotic_stress": load_abiotic_stress(),
        "timing_windows": load_timing_windows(),
        "fertility_programs": load_fertility_programs(),
        "irrigation_programs": load_irrigation_programs(),
        "cultivation_programs": load_cultivation_programs(),
        "diagnostic_frameworks": load_diagnostic_frameworks(),
        "mowing_programs": load_mowing_programs(),
        "salinity_management": load_salinity_management(),
        "drainage_rootzone_programs": load_drainage_rootzone_programs(),
        "overseeding_transition_programs": load_overseeding_transition_programs(),
        "disease_ipm_playbooks": load_disease_ipm_playbooks(),
        "surface_management_recipes": load_surface_management_recipes(),
        "climate_zone_playbooks": load_climate_zone_playbooks(),
        "tournament_prep_recovery": load_tournament_prep_recovery(),
        "nutrient_diagnostics": load_nutrient_diagnostics(),
        "calibration_workflows": load_calibration_workflows(),
        "seasonal_operating_plans": load_seasonal_operating_plans(),
        "regional_pressure_calendars": load_regional_pressure_calendars(),
        "advanced_turf_science": load_advanced_turf_science(),
    }

    records = []
    for collection, items in collections.items():
        for key, info in items.items():
            records.append(_audit_record(collection, key, info, product_index))

    warning_counts = {}
    for record in records:
        for warning in record["warnings"]:
            warning_counts[warning] = warning_counts.get(warning, 0) + 1

    return {
        "summary": {
            "products": sum(len(items) for items in products.values()),
            "records": len(records),
            "records_with_no_warnings": sum(1 for record in records if not record["warnings"]),
            "collections": {name: len(items) for name, items in collections.items()},
            "warnings": warning_counts,
        },
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="Print full JSON report.")
    parser.add_argument("--strict", action="store_true", help="Exit nonzero when any warning is present.")
    args = parser.parse_args()

    report = run_audit()
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("FULL STRUCTURED KB AUDIT")
        print(json.dumps(report["summary"], indent=2, sort_keys=True))
        for record in report["records"]:
            if record["warnings"]:
                print(
                    f"- {record['collection']}/{record['key']}: "
                    f"{', '.join(record['warnings'])}"
                )

    return 1 if args.strict and report["summary"]["warnings"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
