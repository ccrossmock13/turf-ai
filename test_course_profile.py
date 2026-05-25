import unittest
from datetime import date

from course_profile import (
    build_course_profile_kb_hint,
    build_current_management_snapshot,
    build_operational_guidance_response,
    format_current_management_snapshot,
    format_course_profile_for_prompt,
    infer_regional_management_context,
)


class CourseProfileInferenceTests(unittest.TestCase):
    def test_transition_zone_profile_infers_regional_context(self):
        profile = {
            "region": "Louisville, Kentucky transition zone",
            "surfaces": {
                "greens": "creeping bentgrass",
                "tees": "",
                "fairways": "kentucky bluegrass",
                "rough": "tall fescue",
            },
        }

        inferred = infer_regional_management_context(profile)

        self.assertEqual(inferred["regional_archetype"], "Cool-season transition zone")
        self.assertEqual(inferred["seasonal_operating_plan"], "Cool season transition zone seasonal operating plan")
        self.assertEqual(inferred["regional_pressure_calendar"], "Transition zone cool season regional pressure calendar")
        self.assertEqual(inferred["retrieval_region_hint"], "transition zone")

    def test_southeast_warm_season_profile_infers_regional_context(self):
        profile = {
            "region": "Atlanta, Georgia",
            "surfaces": {
                "greens": "",
                "tees": "bermudagrass",
                "fairways": "bermudagrass",
                "rough": "zoysiagrass",
            },
        }

        inferred = infer_regional_management_context(profile)

        self.assertEqual(inferred["regional_archetype"], "Warm-season Southeast")
        self.assertEqual(inferred["seasonal_operating_plan"], "Warm season southeast seasonal operating plan")
        self.assertEqual(inferred["regional_pressure_calendar"], "Southeast warm season regional pressure calendar")

    def test_course_profile_prompt_includes_inferred_region_lines(self):
        profile = {
            "region": "Phoenix, Arizona",
            "surfaces": {
                "greens": "",
                "tees": "",
                "fairways": "bermudagrass",
                "rough": "",
            },
        }

        prompt = format_course_profile_for_prompt(profile=profile)

        self.assertIn("Inferred regional archetype: Arid West bermudagrass", prompt)
        self.assertIn("Auto seasonal plan: Arid west bermudagrass seasonal operating plan", prompt)
        self.assertIn("Auto pressure calendar: Arid west bermudagrass regional pressure calendar", prompt)

    def test_course_profile_kb_hint_contains_regional_and_surface_terms(self):
        profile = {
            "region": "Minneapolis, Minnesota",
            "surfaces": {
                "greens": "creeping bentgrass",
                "tees": "perennial ryegrass",
                "fairways": "kentucky bluegrass",
                "rough": "",
            },
        }

        hint = build_course_profile_kb_hint(profile=profile).lower()

        self.assertIn("northern cool season", hint)
        self.assertIn("northern cool season seasonal operating plan", hint)
        self.assertIn("northern cool season regional pressure calendar", hint)
        self.assertIn("greens creeping bentgrass", hint)

    def test_current_management_snapshot_uses_date_and_region(self):
        profile = {
            "region": "Louisville, Kentucky transition zone",
            "surfaces": {
                "greens": "creeping bentgrass",
                "tees": "",
                "fairways": "kentucky bluegrass",
                "rough": "tall fescue",
            },
        }

        snapshot = build_current_management_snapshot(profile=profile, as_of=date(2026, 4, 8))

        self.assertEqual(snapshot["season"], "Spring")
        self.assertEqual(snapshot["regional_archetype"], "Cool-season transition zone")
        self.assertIn("Restore density and rooting", snapshot["current_priorities"][0])
        self.assertIn("brown patch preventive", " ".join(snapshot["timing_windows"]).lower())
        self.assertTrue(snapshot["surface_cards"])
        self.assertEqual(snapshot["surface_cards"][0]["surface"], "greens")

    def test_format_current_management_snapshot_is_prompt_ready(self):
        profile = {
            "region": "Atlanta, Georgia",
            "surfaces": {
                "greens": "",
                "tees": "bermudagrass",
                "fairways": "bermudagrass",
                "rough": "zoysiagrass",
            },
        }

        snapshot_text = format_current_management_snapshot(profile=profile, as_of=date(2026, 7, 8))

        self.assertIn("CURRENT MANAGEMENT SNAPSHOT", snapshot_text)
        self.assertIn("current season: summer", snapshot_text.lower())
        self.assertIn("Warm-season Southeast", snapshot_text)
        self.assertIn("Scout now for:", snapshot_text)

    def test_operational_guidance_response_for_priorities(self):
        profile = {
            "region": "Louisville, Kentucky transition zone",
            "surfaces": {
                "greens": "creeping bentgrass",
                "tees": "",
                "fairways": "kentucky bluegrass",
                "rough": "tall fescue",
            },
        }

        response = build_operational_guidance_response(
            "What should we focus on this month?",
            profile=profile,
            as_of=date(2026, 4, 8),
        )

        self.assertIsNotNone(response)
        self.assertEqual(response["confidence"]["label"], "Current Priorities")
        self.assertIn("Top priorities for April", response["answer"])
        self.assertIn("Scout now for:", response["answer"])
        self.assertIn("Surface-specific next actions:", response["answer"])
        self.assertIn("**Greens (creeping bentgrass)**", response["answer"])
        self.assertIn("**Fairways (kentucky bluegrass)**", response["answer"])

    def test_operational_guidance_response_for_spray_question_stays_target_safe(self):
        profile = {
            "region": "Atlanta, Georgia",
            "surfaces": {
                "greens": "",
                "tees": "bermudagrass",
                "fairways": "bermudagrass",
                "rough": "zoysiagrass",
            },
        }

        response = build_operational_guidance_response(
            "What should I spray this month?",
            profile=profile,
            as_of=date(2026, 7, 8),
        )

        self.assertIsNotNone(response)
        self.assertEqual(response["confidence"]["label"], "Profile-Based Spray Guidance")
        self.assertIn("I would not jump straight to a product list", response["answer"])
        self.assertIn("tell me the target and surface", response["answer"])

    def test_operational_guidance_filters_to_requested_surface(self):
        profile = {
            "region": "Louisville, Kentucky transition zone",
            "surfaces": {
                "greens": "creeping bentgrass",
                "tees": "",
                "fairways": "kentucky bluegrass",
                "rough": "tall fescue",
            },
        }

        response = build_operational_guidance_response(
            "What should we focus on for greens this month?",
            profile=profile,
            as_of=date(2026, 4, 8),
        )

        self.assertIsNotNone(response)
        self.assertEqual(response["confidence"]["label"], "Surface-Specific Priorities")
        self.assertIn("**Greens (creeping bentgrass)**", response["answer"])
        self.assertNotIn("**Fairways (kentucky bluegrass)**", response["answer"])


if __name__ == "__main__":
    unittest.main()
