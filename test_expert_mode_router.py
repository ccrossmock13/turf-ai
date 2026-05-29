import unittest

from expert_mode_router import route_expert_mode


class ExpertModeRouterTests(unittest.TestCase):
    def test_routes_verified_product_questions(self):
        decision = route_expert_mode("What should I use for dollar spot on greens?")

        self.assertEqual(decision["mode"], "verified_product")
        self.assertGreaterEqual(decision["router_confidence"], 0.5)
        self.assertIn("dollar_spot", decision["matched_signals"])

    def test_routes_diagnosis_for_symptom_questions(self):
        decision = route_expert_mode("My greens are wilting even though moisture readings are high. What is causing it?")

        self.assertEqual(decision["mode"], "advanced_diagnosis")
        self.assertIn("wilting", decision["matched_signals"])

    def test_routes_science_for_mechanism_questions(self):
        decision = route_expert_mode("How do growing degree days help with PGR timing?")

        self.assertEqual(decision["mode"], "advanced_turf_science")
        self.assertIn("growing degree days", decision["matched_signals"])

    def test_routes_broad_summer_decline_explainers_to_science(self):
        decision = route_expert_mode("What causes bentgrass to decline in summer?")

        self.assertEqual(decision["mode"], "advanced_turf_science")

    def test_routes_abw_timing_question_to_science_not_product(self):
        decision = route_expert_mode("What should I know about ABW timing on Poa fairways?")

        self.assertEqual(decision["mode"], "advanced_turf_science")

    def test_mixed_symptom_and_product_intent_routes_to_diagnosis(self):
        decision = route_expert_mode("My greens are wilting. Should I spray something?")

        self.assertEqual(decision["mode"], "advanced_diagnosis")
        self.assertIn("diagnose before recommending a product", decision["reason"])

    def test_routes_broad_turf_health_question_to_general_guidance(self):
        decision = route_expert_mode("What should I know about turf health in general?")

        self.assertEqual(decision["mode"], "general_turf_guidance")
        self.assertIn("turf health", decision["matched_signals"])

    def test_routes_primo_interval_explainer_to_science(self):
        decision = route_expert_mode("Why does clipping yield matter more than calendar interval in Primo timing?")

        self.assertEqual(decision["mode"], "advanced_turf_science")

    def test_routes_poa_vs_bent_summer_collapse_to_science(self):
        decision = route_expert_mode("Why does Poa collapse faster than bentgrass in summer?")

        self.assertEqual(decision["mode"], "advanced_turf_science")

    def test_routes_mower_injury_mimic_question_to_science(self):
        decision = route_expert_mode("Why does mower injury mimic disease so often?")

        self.assertEqual(decision["mode"], "advanced_turf_science")

    def test_routes_water_stress_vs_disease_walkthrough_to_diagnosis(self):
        decision = route_expert_mode("Walk me through how you would separate water stress from disease on greens before spraying.")

        self.assertEqual(decision["mode"], "advanced_diagnosis")

    def test_routes_summer_stress_short_version_to_general_guidance(self):
        decision = route_expert_mode("Give me the short version on summer stress.")

        self.assertEqual(decision["mode"], "general_turf_guidance")

    def test_routes_bleaching_mode_of_action_explainer_to_science(self):
        decision = route_expert_mode(
            "How should I think about bleaching injury and herbicide mode of action before calling this disease?"
        )

        self.assertEqual(decision["mode"], "advanced_turf_science")

    def test_routes_verified_fungicide_choices_question_to_product(self):
        decision = route_expert_mode("Which fungicide choices are verified for dollar spot?")

        self.assertEqual(decision["mode"], "verified_product")


if __name__ == "__main__":
    unittest.main()
