import unittest
from pathlib import Path

from scripts.audit_structured_kb import run_audit as run_structured_kb_audit
from scripts.run_ambiguity_eval import load_cases as load_ambiguity_eval_cases
from scripts.run_anti_slop_eval import load_cases as load_anti_slop_eval_cases
from scripts.run_context_switch_eval import load_cases as load_context_switch_eval_cases
from scripts.run_general_turf_eval import load_cases as load_general_turf_eval_cases
from scripts.run_image_eval import load_cases as load_image_eval_cases
from scripts.run_no_account_turf_eval import load_cases as load_no_account_turf_eval_cases
from scripts.run_comprehensive_100_eval import load_cases as load_comprehensive_100_eval_cases
from scripts.run_phd_turf_eval import load_cases as load_phd_turf_eval_cases
from scripts.run_product_label_eval import load_cases as load_product_label_eval_cases
from knowledge_base import (
    build_context_from_knowledge,
    extract_advanced_turf_science_names,
    extract_calibration_workflow_names,
    extract_climate_zone_playbook_names,
    extract_cultivation_program_names,
    extract_drainage_rootzone_program_names,
    extract_disease_ipm_playbook_names,
    extract_diagnostic_framework_names,
    extract_fertility_program_names,
    extract_abiotic_stress_names,
    extract_irrigation_program_names,
    extract_mowing_program_names,
    extract_nutrient_diagnostic_names,
    extract_overseeding_transition_program_names,
    extract_pest_names,
    extract_regional_pressure_calendar_names,
    extract_salinity_management_names,
    extract_seasonal_operating_plan_names,
    extract_surface_management_recipe_names,
    extract_tournament_prep_recovery_names,
    extract_turfgrass_names,
    extract_timing_window_names,
    extract_weed_names,
    get_advanced_turf_science_info,
    get_abiotic_stress_info,
    get_calibration_workflow_info,
    get_climate_zone_playbook_info,
    get_cultivation_program_info,
    get_drainage_rootzone_program_info,
    get_disease_ipm_playbook_info,
    get_diagnostic_framework_info,
    get_fertility_program_info,
    get_irrigation_program_info,
    get_mowing_program_info,
    get_nutrient_diagnostics_info,
    get_overseeding_transition_program_info,
    get_pest_info,
    get_regional_pressure_calendar_info,
    get_salinity_management_info,
    get_seasonal_operating_plan_info,
    get_surface_management_recipe_info,
    get_tournament_prep_recovery_info,
    get_timing_window_info,
    get_turfgrass_info,
    get_weed_info,
    load_advanced_turf_science,
    load_abiotic_stress,
    load_calibration_workflows,
    load_climate_zone_playbooks,
    load_cultivation_programs,
    load_drainage_rootzone_programs,
    load_disease_ipm_playbooks,
    load_diagnostic_frameworks,
    load_fertility_programs,
    load_irrigation_programs,
    load_mowing_programs,
    load_nutrient_diagnostics,
    load_overseeding_transition_programs,
    load_pests,
    load_products,
    load_regional_pressure_calendars,
    load_salinity_management,
    load_seasonal_operating_plans,
    load_surface_management_recipes,
    load_tournament_prep_recovery,
    load_timing_windows,
    load_turfgrasses,
    load_weeds,
)


class KnowledgeBaseExpansionTests(unittest.TestCase):
    def test_curated_image_eval_cases_load(self):
        root = Path(__file__).resolve().parent
        cases = load_image_eval_cases(root / "scripts" / "image_eval_cases.json")
        self.assertGreaterEqual(len(cases), 9)
        self.assertTrue(all(case.get("id") for case in cases))
        self.assertTrue(all(case.get("image_path") for case in cases))
        self.assertTrue(all(case.get("question") for case in cases))

    def test_general_turf_eval_cases_load(self):
        root = Path(__file__).resolve().parent
        cases = load_general_turf_eval_cases(root / "scripts" / "general_turf_eval_cases.json")
        self.assertGreaterEqual(len(cases), 26)
        self.assertTrue(all(case.get("id") for case in cases))
        self.assertTrue(all(case.get("question") for case in cases))

    def test_ambiguity_eval_cases_load(self):
        root = Path(__file__).resolve().parent
        cases = load_ambiguity_eval_cases(root / "scripts" / "ambiguity_eval_cases.json")
        self.assertGreaterEqual(len(cases), 18)
        self.assertTrue(all(case.get("id") for case in cases))
        self.assertTrue(all(case.get("question") for case in cases))

    def test_anti_slop_eval_cases_load(self):
        root = Path(__file__).resolve().parent
        cases = load_anti_slop_eval_cases(root / "scripts" / "anti_slop_eval_cases.json")
        self.assertGreaterEqual(len(cases), 31)
        self.assertTrue(all(case.get("id") for case in cases))
        self.assertTrue(all(case.get("question") for case in cases))

    def test_product_label_eval_cases_load(self):
        root = Path(__file__).resolve().parent
        cases = load_product_label_eval_cases(root / "scripts" / "product_label_eval_cases.json")
        self.assertGreaterEqual(len(cases), 124)
        self.assertTrue(all(case.get("id") for case in cases))
        self.assertTrue(all(case.get("question") for case in cases))

    def test_no_account_turf_eval_cases_load(self):
        root = Path(__file__).resolve().parent
        cases = load_no_account_turf_eval_cases(root / "scripts" / "no_account_turf_eval_cases.json")
        self.assertGreaterEqual(len(cases), 39)
        self.assertTrue(all(case.get("id") for case in cases))
        self.assertTrue(all(case.get("question") for case in cases))

    def test_phd_turf_eval_cases_load(self):
        root = Path(__file__).resolve().parent
        cases = load_phd_turf_eval_cases(root / "scripts" / "phd_turf_eval_cases.json")
        self.assertGreaterEqual(len(cases), 22)
        self.assertTrue(all(case.get("id") for case in cases))
        self.assertTrue(all(case.get("question") for case in cases))

    def test_comprehensive_100_eval_cases_load(self):
        cases = load_comprehensive_100_eval_cases()
        self.assertEqual(len(cases), 100)
        self.assertTrue(all(case.get("id") for case in cases))
        self.assertTrue(all(case.get("question") for case in cases))

    def test_context_switch_eval_cases_load(self):
        root = Path(__file__).resolve().parent
        cases = load_context_switch_eval_cases(root / "scripts" / "context_switch_eval_cases.json")
        self.assertGreaterEqual(len(cases), 5)
        self.assertTrue(all(case.get("id") for case in cases))
        self.assertTrue(all(case.get("steps") for case in cases))

    def test_all_products_have_expanded_label_schema_fields(self):
        products = load_products()
        required_fields = {
            "rei",
            "retreatment_interval",
            "irrigation_guidance",
            "rainfast",
            "tank_mix_guidance",
            "max_apps_per_year",
            "max_rate_per_app",
            "reseeding_interval",
            "overseeding_interval",
            "application_window_notes",
        }

        for _, category_products in products.items():
            for _, info in category_products.items():
                self.assertTrue(required_fields.issubset(set(info.keys())))

    def test_structured_kb_audit_reports_expanded_field_coverage(self):
        report = run_structured_kb_audit()
        coverage = report["summary"]["expanded_field_coverage"]

        self.assertIn("rei", coverage)
        self.assertIn("irrigation_guidance", coverage)
        self.assertGreaterEqual(coverage["rei"]["records_with_value"], 40)
        self.assertGreaterEqual(coverage["irrigation_guidance"]["records_with_value"], 40)
        self.assertGreaterEqual(coverage["tank_mix_guidance"]["records_with_value"], 40)

    def test_structured_kb_has_launch_trust_gate_field_coverage_floor(self):
        report = run_structured_kb_audit()
        coverage = report["summary"]["expanded_field_coverage"]
        total = report["summary"]["products"]

        self.assertGreaterEqual((coverage["rei"]["records_with_value"] / total) * 100, 80)
        self.assertGreaterEqual((coverage["irrigation_guidance"]["records_with_value"] / total) * 100, 85)
        self.assertGreaterEqual((coverage["tank_mix_guidance"]["records_with_value"] / total) * 100, 80)
        self.assertGreaterEqual((coverage["max_rate_per_app"]["records_with_value"] / total) * 100, 75)

    def test_weeds_load_and_lookup(self):
        weeds = load_weeds()

        self.assertIn("crabgrass", weeds)
        self.assertIn("poa_trivialis", weeds)
        self.assertEqual(get_weed_info("roughstalk bluegrass")["name"], "poa_trivialis")

    def test_pests_load_and_lookup_aliases(self):
        pests = load_pests()

        self.assertIn("white_grubs", pests)
        self.assertIn("sod_webworms", pests)
        self.assertEqual(get_pest_info("grubs")["name"], "white_grubs")
        self.assertEqual(get_pest_info("ABW")["name"], "annual_bluegrass_weevil")

    def test_context_includes_weed_and_pest_knowledge(self):
        weed_context = build_context_from_knowledge("How should I time goosegrass control?")
        pest_context = build_context_from_knowledge("When should I treat grubs?")

        self.assertIn("goosegrass weed", weed_context)
        self.assertIn("white grubs pest", pest_context)

    def test_extractors_find_new_knowledge_terms(self):
        self.assertIn("green kyllinga", extract_weed_names("green kyllinga in a wet fairway"))
        self.assertIn("sod webworms", extract_pest_names("soap flush for webworms"))

    def test_turfgrasses_load_and_lookup_aliases(self):
        turfgrasses = load_turfgrasses()

        self.assertIn("creeping_bentgrass", turfgrasses)
        self.assertIn("bermudagrass", turfgrasses)
        self.assertEqual(get_turfgrass_info("bentgrass")["name"], "creeping_bentgrass")
        self.assertEqual(get_turfgrass_info("st augustine")["name"], "st_augustinegrass")

    def test_abiotic_stress_load_and_lookup_aliases(self):
        stresses = load_abiotic_stress()

        self.assertIn("localized_dry_spot", stresses)
        self.assertIn("black_layer", stresses)
        self.assertEqual(get_abiotic_stress_info("LDS")["name"], "localized_dry_spot")
        self.assertEqual(get_abiotic_stress_info("spray injury")["name"], "herbicide_injury")

    def test_context_includes_turfgrass_and_abiotic_knowledge(self):
        turf_context = build_context_from_knowledge("Bentgrass greens are thinning in heat")
        stress_context = build_context_from_knowledge("Localized dry spot on my greens")

        self.assertIn("creeping bentgrass turfgrass", turf_context)
        self.assertIn("heat stress", turf_context)
        self.assertIn("localized dry spot", stress_context)

    def test_extractors_find_turfgrass_and_abiotic_terms(self):
        self.assertIn("bermudagrass", extract_turfgrass_names("bermuda fairway"))
        self.assertIn("fertilizer burn", extract_abiotic_stress_names("fertilizer burn on rough"))

    def test_timing_windows_load_and_lookup(self):
        timing_windows = load_timing_windows()

        self.assertIn("crabgrass_preemergent", timing_windows)
        self.assertIn("white_grub_preventive", timing_windows)
        self.assertEqual(get_timing_window_info("summer patch")["name"], "summer_patch_preventive")

    def test_context_includes_timing_window_knowledge(self):
        context = build_context_from_knowledge("When should I apply crabgrass pre-emergent?")

        self.assertIn("crabgrass preemergent timing", context)
        self.assertIn("55F", context)

    def test_timing_window_extractor_requires_timing_intent(self):
        self.assertIn(
            "white grub preventive",
            extract_timing_window_names("When is preventive timing for white grubs?")
        )
        self.assertEqual([], extract_timing_window_names("I found white grubs"))

    def test_fertility_programs_load_and_lookup(self):
        programs = load_fertility_programs()

        self.assertIn("greens_spoon_feeding", programs)
        self.assertEqual(get_fertility_program_info("spoon feeding")["name"], "greens_spoon_feeding")

    def test_irrigation_programs_load_and_lookup(self):
        programs = load_irrigation_programs()

        self.assertIn("deficit_irrigation_greens", programs)
        self.assertEqual(get_irrigation_program_info("uniformity")["name"], "irrigation_uniformity_audit")

    def test_cultivation_programs_load_and_lookup(self):
        programs = load_cultivation_programs()

        self.assertIn("core_aeration_greens", programs)
        self.assertEqual(get_cultivation_program_info("needle tine")["name"], "summer_venting_and_needle_tining")

    def test_diagnostic_frameworks_load_and_lookup(self):
        frameworks = load_diagnostic_frameworks()

        self.assertIn("wilt_vs_disease_on_greens", frameworks)
        self.assertEqual(get_diagnostic_framework_info("spray injury")["name"], "herbicide_injury_framework")
        self.assertEqual(get_diagnostic_framework_info("reclaimed water")["name"], "water_quality_chemistry_framework")
        self.assertEqual(get_diagnostic_framework_info("slow green-up")["name"], "warm_season_slow_greenup_framework")
        self.assertEqual(get_diagnostic_framework_info("nematode assay")["name"], "nematode_sampling_interpretation_framework")
        self.assertEqual(get_diagnostic_framework_info("residual herbicide")["name"], "herbicide_carryover_framework")
        self.assertEqual(get_diagnostic_framework_info("grub damage")["name"], "insect_feeding_pattern_framework")
        self.assertEqual(get_diagnostic_framework_info("species fit")["name"], "species_fit_renovation_framework")
        self.assertEqual(get_diagnostic_framework_info("ryegrass hanging on")["name"], "overseeded_transition_competition_framework")
        self.assertEqual(get_diagnostic_framework_info("seedlings dying")["name"], "seedling_establishment_failure_framework")
        self.assertEqual(get_diagnostic_framework_info("spray passes")["name"], "application_pattern_coverage_framework")
        self.assertEqual(get_diagnostic_framework_info("repeated rolling")["name"], "mechanical_stress_budget_framework")
        self.assertEqual(get_diagnostic_framework_info("frayed leaf tips")["name"], "cut_quality_leaf_shredding_framework")
        self.assertEqual(get_diagnostic_framework_info("topdressing drift")["name"], "topdressing_program_drift_framework")

    def test_context_includes_advanced_agronomy_knowledge(self):
        fertility_context = build_context_from_knowledge("How should I spoon feed bentgrass greens in summer?")
        irrigation_context = build_context_from_knowledge("Should I use deficit irrigation and hand watering on greens?")
        cultivation_context = build_context_from_knowledge("When should we core aerate greens and topdress?")
        diagnostic_context = build_context_from_knowledge("How do I tell wilt from disease on greens?")

        self.assertIn("greens spoon feeding fertility", fertility_context)
        self.assertIn("deficit irrigation greens irrigation", irrigation_context)
        self.assertIn("core aeration greens cultivation", cultivation_context)
        self.assertIn("wilt vs disease on greens diagnostic", diagnostic_context)

    def test_extractors_find_advanced_agronomy_terms(self):
        self.assertIn("greens spoon feeding", extract_fertility_program_names("summer spoon feeding on poa greens"))
        self.assertIn("irrigation uniformity audit", extract_irrigation_program_names("we need an irrigation audit for dry spots"))
        self.assertIn("summer venting and needle tining", extract_cultivation_program_names("should we needle tine in summer"))
        self.assertIn("wilt vs disease on greens", extract_diagnostic_framework_names("how do I separate wilt from disease on greens"))
        self.assertIn("nematode sampling interpretation framework", extract_diagnostic_framework_names("how should I read a nematode assay?"))
        self.assertIn("herbicide carryover framework", extract_diagnostic_framework_names("could this be residual herbicide carryover?"))
        self.assertIn("insect feeding pattern framework", extract_diagnostic_framework_names("could this grub damage really be insect feeding?"))
        self.assertIn("species fit renovation framework", extract_diagnostic_framework_names("is this really a species fit problem or a renovation decision?"))
        self.assertIn("overseeded transition competition framework", extract_diagnostic_framework_names("our ryegrass is hanging on too long in spring transition"))
        self.assertIn("seedling establishment failure framework", extract_diagnostic_framework_names("germination looked fine but now the seedlings are dying"))
        self.assertIn("application pattern coverage framework", extract_diagnostic_framework_names("the pattern lines up with spray passes and nozzle overlap"))
        self.assertIn("mechanical stress budget framework", extract_diagnostic_framework_names("greens are getting beat up after repeated rolling and tournament prep stress"))
        self.assertIn("cut quality leaf shredding framework", extract_diagnostic_framework_names("frayed leaf tips after mowing look like disease"))
        self.assertIn("topdressing program drift framework", extract_diagnostic_framework_names("could this layering after topdressing be a sand compatibility issue?"))

    def test_mowing_programs_load_and_lookup(self):
        programs = load_mowing_programs()

        self.assertIn("greens_mowing_and_rolling_balance", programs)
        self.assertEqual(get_mowing_program_info("tournament speed")["name"], "tournament_speed_tradeoffs")

    def test_salinity_management_load_and_lookup(self):
        programs = load_salinity_management()

        self.assertIn("ec_monitoring_program", programs)
        self.assertEqual(get_salinity_management_info("reclaimed water")["name"], "reclaimed_water_management")

    def test_drainage_rootzone_programs_load_and_lookup(self):
        programs = load_drainage_rootzone_programs()

        self.assertIn("surface_drainage_correction", programs)
        self.assertEqual(get_drainage_rootzone_program_info("black layer")["name"], "black_layer_prevention_program")

    def test_overseeding_transition_programs_load_and_lookup(self):
        programs = load_overseeding_transition_programs()

        self.assertIn("bermudagrass_overseeding_window", programs)
        self.assertEqual(get_overseeding_transition_program_info("seedhead suppression")["name"], "poa_annua_seedhead_suppression_program")

    def test_context_includes_new_specialist_program_knowledge(self):
        mowing_context = build_context_from_knowledge("How should we balance rolling and green speed for a tournament?")
        salinity_context = build_context_from_knowledge("How should I monitor EC and reclaimed water issues on greens?")
        drainage_context = build_context_from_knowledge("Could layering and black layer be causing drainage problems?")
        overseeding_context = build_context_from_knowledge("When should we overseed bermudagrass and manage spring transition?")

        self.assertTrue(
            "greens mowing and rolling balance mowing" in mowing_context
            or "rolling frequency under stress mowing" in mowing_context
        )
        self.assertIn("ec monitoring program salinity", salinity_context)
        self.assertIn("layering and perched water table drainage", drainage_context)
        self.assertIn("bermudagrass overseeding window overseeding", overseeding_context)

    def test_extractors_find_new_specialist_terms(self):
        self.assertIn("tournament speed tradeoffs", extract_mowing_program_names("tournament speed is pushing the greens"))
        self.assertIn("reclaimed water management", extract_salinity_management_names("reclaimed water salinity has me worried"))
        self.assertIn("black layer prevention program", extract_drainage_rootzone_program_names("could black layer be the problem"))
        self.assertIn("spring transition acceleration", extract_overseeding_transition_program_names("how do we speed spring transition"))

    def test_disease_ipm_playbooks_load_and_lookup(self):
        playbooks = load_disease_ipm_playbooks()

        self.assertIn("dollar_spot_ipm", playbooks)
        self.assertEqual(get_disease_ipm_playbook_info("anthracnose")["name"], "anthracnose_ipm")

    def test_surface_management_recipes_load_and_lookup(self):
        recipes = load_surface_management_recipes()

        self.assertIn("bentgrass_greens_recipe", recipes)
        self.assertEqual(get_surface_management_recipe_info("bermudagrass fairways")["name"], "bermudagrass_fairways_recipe")

    def test_context_includes_playbooks_and_surface_recipes(self):
        playbook_context = build_context_from_knowledge("Give me a dollar spot IPM plan for fairways")
        recipe_context = build_context_from_knowledge("How should I manage bentgrass greens in summer?")

        self.assertIn("dollar spot ipm playbook", playbook_context)
        self.assertIn("bentgrass greens recipe", recipe_context)

    def test_extractors_find_playbook_and_recipe_terms(self):
        self.assertIn("fairy ring ipm", extract_disease_ipm_playbook_names("fairy ring ipm for greens"))
        self.assertIn("bentgrass greens recipe", extract_surface_management_recipe_names("need a bentgrass greens recipe for summer"))

    def test_climate_zone_playbooks_load_and_lookup(self):
        playbooks = load_climate_zone_playbooks()

        self.assertIn("humid_transition_zone_cool_season", playbooks)
        self.assertEqual(
            get_climate_zone_playbook_info("transition zone")["name"],
            "humid_transition_zone_cool_season",
        )

    def test_tournament_prep_recovery_load_and_lookup(self):
        programs = load_tournament_prep_recovery()

        self.assertIn("greens_speed_ramp_plan", programs)
        self.assertEqual(
            get_tournament_prep_recovery_info("green speed")["name"],
            "greens_speed_ramp_plan",
        )

    def test_nutrient_diagnostics_load_and_lookup(self):
        diagnostics = load_nutrient_diagnostics()

        self.assertIn("nitrogen_deficiency", diagnostics)
        self.assertEqual(
            get_nutrient_diagnostics_info("fertilizer burn")["name"],
            "salt_or_fertilizer_burn_diagnostics",
        )

    def test_calibration_workflows_load_and_lookup(self):
        workflows = load_calibration_workflows()

        self.assertIn("sprayer_output_verification", workflows)
        self.assertEqual(
            get_calibration_workflow_info("sprayer calibration")["name"],
            "sprayer_output_verification",
        )

    def test_context_includes_climate_tournament_nutrient_and_calibration_knowledge(self):
        climate_context = build_context_from_knowledge("How should I manage cool-season turf in the transition zone?")
        tournament_context = build_context_from_knowledge("How should we ramp green speed for a tournament?")
        nutrient_context = build_context_from_knowledge("How do I diagnose nitrogen deficiency on greens?")
        calibration_context = build_context_from_knowledge("Walk me through sprayer output calibration")

        self.assertIn("humid transition zone cool season climate", climate_context)
        self.assertIn("greens speed ramp plan tournament", tournament_context)
        self.assertIn("nitrogen deficiency nutrient", nutrient_context)
        self.assertIn("sprayer output verification calibration", calibration_context)

    def test_extractors_find_climate_tournament_nutrient_and_calibration_terms(self):
        self.assertIn(
            "humid transition zone cool season",
            extract_climate_zone_playbook_names("transition zone management is killing us"),
        )
        self.assertIn(
            "greens speed ramp plan",
            extract_tournament_prep_recovery_names("need a green speed plan for tournament week"),
        )
        self.assertIn(
            "nitrogen deficiency",
            extract_nutrient_diagnostic_names("looks like nitrogen deficiency on fairways"),
        )
        self.assertIn(
            "sprayer output verification",
            extract_calibration_workflow_names("we need sprayer output calibration today"),
        )

    def test_seasonal_operating_plans_load_and_lookup(self):
        plans = load_seasonal_operating_plans()

        self.assertIn("cool_season_transition_zone_calendar", plans)
        self.assertEqual(
            get_seasonal_operating_plan_info("transition zone calendar")["name"],
            "cool_season_transition_zone_calendar",
        )

    def test_regional_pressure_calendars_load_and_lookup(self):
        calendars = load_regional_pressure_calendars()

        self.assertIn("transition_zone_cool_season_pressure", calendars)
        self.assertEqual(
            get_regional_pressure_calendar_info("transition zone pressure")["name"],
            "transition_zone_cool_season_pressure",
        )

    def test_context_includes_seasonal_plan_and_pressure_calendar_knowledge(self):
        plan_context = build_context_from_knowledge("What should we focus on in the transition zone this season?")
        pressure_context = build_context_from_knowledge("Give me a transition zone pressure calendar for cool-season turf")

        self.assertIn("cool season transition zone seasonal operating plan", plan_context.lower())
        self.assertIn("transition zone cool season regional pressure calendar", pressure_context.lower())

    def test_extractors_find_seasonal_plan_and_pressure_calendar_terms(self):
        self.assertIn(
            "cool season transition zone",
            extract_seasonal_operating_plan_names("transition zone planning for this year"),
        )
        self.assertIn(
            "transition zone cool season pressure",
            extract_regional_pressure_calendar_names("need a transition zone pressure calendar"),
        )

    def test_advanced_turf_science_load_and_lookup(self):
        science = load_advanced_turf_science()

        self.assertIn("cool_season_heat_carbohydrate_decline", science)
        self.assertIn("usga_rootzone_porosity_hydraulic_conductivity", science)
        self.assertIn("winter_crown_hydration_freeze_injury", science)
        self.assertIn("salinity_osmotic_sodium_structure_stress", science)
        self.assertIn("poa_annua_vs_bentgrass_summer_decline", science)
        self.assertIn("pythium_root_dysfunction_vs_wet_wilt", science)
        self.assertIn("gdd_growth_potential_pgr_timing", science)
        self.assertIn("anthracnose_basal_rot_stress_complex", science)
        self.assertIn("fairy_ring_hydrophobicity_nitrogen_masking", science)
        self.assertIn("soil_ph_buffering_acidification_programs", science)
        self.assertIn("bermudagrass_spring_dead_spot_transition_recovery", science)
        self.assertIn("salt_vs_drought_ec_moisture_interpretation", science)
        self.assertIn("zoysiagrass_spring_greenup_thatch_temperature", science)
        self.assertIn("bermudagrass_shade_cold_carbohydrate_limits", science)
        self.assertIn("warm_season_fall_hardening_winter_survival", science)
        self.assertIn("reclaimed_water_nutrient_credit_salt_balance", science)
        self.assertIn("gypsum_sar_dispersion_decision_logic", science)
        self.assertIn("nematode_lab_interpretation_threshold_context", science)
        self.assertIn("nematicide_expectation_root_recovery_logic", science)
        self.assertIn("herbicide_mode_of_action_injury_patterns", science)
        self.assertIn("herbicide_carryover_residual_transition_risk", science)
        self.assertIn("tournament_greens_stress_budget_model", science)
        self.assertIn("tournament_fairway_tee_recovery_traffic_model", science)
        self.assertIn("annual_bluegrass_weevil_lifecycle_threshold_timing", science)
        self.assertIn("white_grub_species_threshold_recovery_logic", science)
        self.assertIn("sod_webworm_cutworm_night_feeding_diagnostics", science)
        self.assertIn("chinch_bug_heat_drought_interaction_model", science)
        self.assertIn("species_fit_surface_region_tradeoff_model", science)
        self.assertIn("renovation_vs_rescue_program_decision_model", science)
        self.assertIn("overseeded_ryegrass_transition_competition_model", science)
        self.assertIn("seedling_establishment_temperature_moisture_oxygen_balance", science)
        self.assertIn("cultivar_diversity_stress_disease_buffering", science)
        self.assertIn("sprayer_coverage_nozzle_pressure_canopy_deposition", science)
        self.assertIn("roller_frequency_mechanical_stress_budget", science)
        self.assertIn("soil_test_cec_base_saturation_practical_limits", science)
        self.assertIn("spray_water_ph_hardness_adjuvant_interaction_model", science)
        self.assertIn("mower_sharpness_leaf_shredding_disease_mimic_model", science)
        self.assertIn("topdressing_organic_matter_dilution_layering_drift", science)
        self.assertEqual(
            get_advanced_turf_science_info("carbohydrate reserves")["name"],
            "cool_season_heat_carbohydrate_decline",
        )
        self.assertEqual(
            get_advanced_turf_science_info("air-filled porosity")["name"],
            "usga_rootzone_porosity_hydraulic_conductivity",
        )
        self.assertEqual(
            get_advanced_turf_science_info("sodium hazard")["name"],
            "salinity_osmotic_sodium_structure_stress",
        )
        self.assertEqual(
            get_advanced_turf_science_info("bicarbonates")["name"],
            "bicarbonate_alkalinity_micronutrient_lockout",
        )
        self.assertEqual(
            get_advanced_turf_science_info("pythium root dysfunction")["name"],
            "pythium_root_dysfunction_vs_wet_wilt",
        )
        self.assertEqual(
            get_advanced_turf_science_info("anthracnose basal rot")["name"],
            "anthracnose_basal_rot_stress_complex",
        )
        self.assertEqual(
            get_advanced_turf_science_info("spring dead spot")["name"],
            "bermudagrass_spring_dead_spot_transition_recovery",
        )
        self.assertEqual(
            get_advanced_turf_science_info("reclaimed water nutrient credit")["name"],
            "reclaimed_water_nutrient_credit_salt_balance",
        )
        self.assertEqual(
            get_advanced_turf_science_info("SAR")["name"],
            "gypsum_sar_dispersion_decision_logic",
        )
        self.assertEqual(
            get_advanced_turf_science_info("nematode assay")["name"],
            "nematode_lab_interpretation_threshold_context",
        )
        self.assertEqual(
            get_advanced_turf_science_info("herbicide carryover")["name"],
            "herbicide_carryover_residual_transition_risk",
        )
        self.assertEqual(
            get_advanced_turf_science_info("ABW timing")["name"],
            "annual_bluegrass_weevil_lifecycle_threshold_timing",
        )
        self.assertEqual(
            get_advanced_turf_science_info("species fit")["name"],
            "species_fit_surface_region_tradeoff_model",
        )
        self.assertEqual(
            get_advanced_turf_science_info("ryegrass hanging on")["name"],
            "overseeded_ryegrass_transition_competition_model",
        )
        self.assertEqual(
            get_advanced_turf_science_info("seedling establishment")["name"],
            "seedling_establishment_temperature_moisture_oxygen_balance",
        )
        self.assertEqual(
            get_advanced_turf_science_info("cultivar diversity")["name"],
            "cultivar_diversity_stress_disease_buffering",
        )
        self.assertEqual(
            get_advanced_turf_science_info("nozzle pressure")["name"],
            "sprayer_coverage_nozzle_pressure_canopy_deposition",
        )
        self.assertEqual(
            get_advanced_turf_science_info("rolling frequency")["name"],
            "roller_frequency_mechanical_stress_budget",
        )
        self.assertEqual(
            get_advanced_turf_science_info("base saturation")["name"],
            "soil_test_cec_base_saturation_practical_limits",
        )
        self.assertEqual(
            get_advanced_turf_science_info("spray water pH")["name"],
            "spray_water_ph_hardness_adjuvant_interaction_model",
        )
        self.assertEqual(
            get_advanced_turf_science_info("mower sharpness")["name"],
            "mower_sharpness_leaf_shredding_disease_mimic_model",
        )
        self.assertEqual(
            get_advanced_turf_science_info("topdressing consistency")["name"],
            "topdressing_organic_matter_dilution_layering_drift",
        )

    def test_context_includes_advanced_turf_science_knowledge(self):
        physiology_context = build_context_from_knowledge("Why do bentgrass greens lose carbohydrate reserves in heat?")
        soil_context = build_context_from_knowledge("How do air-filled porosity and hydraulic conductivity affect greens?")
        disease_context = build_context_from_knowledge("Explain leaf wetness and the disease triangle for dollar spot")

        self.assertIn("cool season heat carbohydrate decline advanced science", physiology_context)
        self.assertIn("usga rootzone porosity hydraulic conductivity advanced science", soil_context)
        self.assertIn("disease triangle leaf wetness microclimate advanced science", disease_context)

    def test_extractors_find_advanced_turf_science_terms(self):
        self.assertIn(
            "cool season heat carbohydrate decline",
            extract_advanced_turf_science_names("carbohydrate reserves on bentgrass greens"),
        )
        self.assertIn(
            "firmness green speed plant health tradeoff",
            extract_advanced_turf_science_names("firmness and green speed tradeoffs"),
        )
        self.assertIn(
            "nematode root pruning stress complex",
            extract_advanced_turf_science_names("could nematodes be pruning roots?"),
        )
        self.assertIn(
            "gdd growth potential pgr timing",
            extract_advanced_turf_science_names("how do growing degree days help with PGR timing?"),
        )
        self.assertIn(
            "wetting agent chemistry functional groups",
            extract_advanced_turf_science_names("how do wetting agent chemistry types differ?"),
        )
        self.assertIn(
            "anthracnose basal rot stress complex",
            extract_advanced_turf_science_names("why is anthracnose basal rot getting worse on Poa greens?"),
        )
        self.assertIn(
            "salt vs drought ec moisture interpretation",
            extract_advanced_turf_science_names("is this salt stress versus drought even though moisture is okay?"),
        )
        self.assertIn(
            "zoysiagrass spring greenup thatch temperature",
            extract_advanced_turf_science_names("why is zoysia green up so slow this spring?"),
        )
        self.assertIn(
            "reclaimed water nutrient credit salt balance",
            extract_advanced_turf_science_names("how should I think about reclaimed water nutrient credit and salts?"),
        )
        self.assertIn(
            "gypsum sar dispersion decision logic",
            extract_advanced_turf_science_names("when does gypsum help with SAR and sodium dispersion?"),
        )
        self.assertIn(
            "nematode lab interpretation threshold context",
            extract_advanced_turf_science_names("how should I read this nematode assay report?"),
        )
        self.assertIn(
            "herbicide carryover residual transition risk",
            extract_advanced_turf_science_names("could this reseeding failure be herbicide carryover?"),
        )
        self.assertIn(
            "tournament greens stress budget model",
            extract_advanced_turf_science_names("how should we think about tournament stress budget on greens?"),
        )
        self.assertIn(
            "annual bluegrass weevil lifecycle threshold timing",
            extract_advanced_turf_science_names("how should I think about ABW timing and thresholds?"),
        )
        self.assertIn(
            "species fit surface region tradeoff model",
            extract_advanced_turf_science_names("how should I think about species fit for this surface and region?"),
        )
        self.assertIn(
            "overseeded ryegrass transition competition model",
            extract_advanced_turf_science_names("our ryegrass is hanging on and bermuda transition is stuck"),
        )
        self.assertIn(
            "seedling establishment temperature moisture oxygen balance",
            extract_advanced_turf_science_names("germination looked fine but seedlings keep dying after emergence"),
        )
        self.assertIn(
            "cultivar diversity stress disease buffering",
            extract_advanced_turf_science_names("does cultivar diversity help buffer disease and stress risk?"),
        )
        self.assertIn(
            "sprayer coverage nozzle pressure canopy deposition",
            extract_advanced_turf_science_names("how do nozzle pressure and sprayer coverage affect canopy deposition?"),
        )
        self.assertIn(
            "roller frequency mechanical stress budget",
            extract_advanced_turf_science_names("how does rolling frequency stack mechanical stress on greens?"),
        )
        self.assertIn(
            "soil test cec base saturation practical limits",
            extract_advanced_turf_science_names("how should I interpret CEC and base saturation on a soil test?"),
        )
        self.assertIn(
            "spray water ph hardness adjuvant interaction model",
            extract_advanced_turf_science_names("how do spray water pH, hardness, and adjuvant fit affect performance?"),
        )
        self.assertIn(
            "mower sharpness leaf shredding disease mimic model",
            extract_advanced_turf_science_names("how does mower sharpness and leaf shredding mimic disease?"),
        )
        self.assertIn(
            "topdressing organic matter dilution layering drift",
            extract_advanced_turf_science_names("how does topdressing consistency affect organic matter dilution and layering drift?"),
        )


if __name__ == "__main__":
    unittest.main()
