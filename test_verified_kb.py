import unittest

from verified_kb import (
    answer_from_verified_kb,
    answer_product_context_needed,
    recommend_verified_products_for_target,
    recommend_verified_products_for_surface_target,
)


class VerifiedKbAnswerTests(unittest.TestCase):
    def test_supported_product_target_returns_verified_answer(self):
        result = answer_from_verified_kb("What rate should I apply Daconil for dollar spot?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertFalse(result["needs_review"])
        self.assertIn("3.5-5 fl oz/1000 sq ft", result["answer"])

    def test_general_product_rate_question_returns_verified_rate_summary(self):
        result = answer_from_verified_kb("What rate of Daconil should I use?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertEqual(result["confidence"]["label"], "Verified KB Rate Summary")
        self.assertIn("Rates currently stored", result["answer"])

    def test_supported_targets_question_returns_verified_diseases_for_daconil(self):
        result = answer_from_verified_kb("What diseases does Daconil control?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertEqual(result["confidence"]["label"], "Verified Supported Targets")
        self.assertIn("dollar spot", result["answer"].lower())
        self.assertIn("brown patch", result["answer"].lower())
        self.assertTrue(result["sources"])
        self.assertTrue(result["sources"][0].get("url", "").startswith("/static/product-labels/"))

    def test_supported_targets_question_returns_verified_diseases_for_heritage(self):
        result = answer_from_verified_kb("What diseases does Heritage control?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertEqual(result["confidence"]["label"], "Verified Supported Targets")
        self.assertIn("summer patch", result["answer"].lower())
        self.assertIn("anthracnose", result["answer"].lower())

    def test_supported_targets_question_returns_verified_diseases_for_banner(self):
        result = answer_from_verified_kb("What fungi does Banner MAXX control?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertEqual(result["confidence"]["label"], "Verified Supported Targets")
        self.assertIn("dollar spot", result["answer"].lower())
        self.assertIn("anthracnose", result["answer"].lower())

    def test_supported_targets_question_handles_plain_treat_wording(self):
        result = answer_from_verified_kb("What can Daconil treat?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertEqual(result["confidence"]["label"], "Verified Supported Targets")
        self.assertIn("leaf spot", result["answer"].lower())

    def test_verified_product_comparison_handles_prodiamine_vs_dithiopyr(self):
        result = answer_from_verified_kb("What is the difference between prodiamine and dithiopyr?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified_comparison")
        self.assertEqual(result["confidence"]["label"], "Verified Product Comparison")
        self.assertIn("Barricade", result["answer"])
        self.assertIn("Dimension", result["answer"])
        self.assertIn("longer residual", result["answer"].lower())
        self.assertIn("early post-emergent", result["answer"].lower())

    def test_verified_product_comparison_handles_tenacity_vs_pylex(self):
        result = answer_from_verified_kb("Tenacity vs Pylex for goosegrass?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified_comparison")
        self.assertIn("Tenacity", result["answer"])
        self.assertIn("Pylex", result["answer"])
        self.assertIn("goosegrass", result["answer"].lower())
        self.assertIn("does not", result["answer"].lower())

    def test_verified_product_comparison_handles_daconil_vs_banner(self):
        result = answer_from_verified_kb("What is the difference between Daconil and Banner MAXX?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified_comparison")
        self.assertIn("multi-site", result["answer"].lower())
        self.assertIn("frac 3", result["answer"].lower())

    def test_verified_product_comparison_handles_heritage_vs_banner(self):
        result = answer_from_verified_kb("Heritage vs Banner MAXX for anthracnose?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified_comparison")
        self.assertIn("Heritage", result["answer"])
        self.assertIn("Banner MAXX", result["answer"])
        self.assertIn("anthracnose", result["answer"].lower())

    def test_verified_product_comparison_handles_acelepryn_vs_ference(self):
        result = answer_from_verified_kb("Acelepryn vs Ference for ABW?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified_comparison")
        self.assertIn("IRAC Group 28", result["answer"])
        self.assertIn("annual bluegrass weevil", result["answer"].lower())

    def test_verified_product_comparison_handles_primo_vs_proxy(self):
        result = answer_from_verified_kb("Primo MAXX vs Proxy")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified_comparison")
        self.assertIn("seedhead suppression", result["answer"].lower())
        self.assertIn("growth regulation", result["answer"].lower())

    def test_verified_product_comparison_handles_secure_vs_daconil(self):
        result = answer_from_verified_kb("What is the difference between Secure and Daconil?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified_comparison")
        self.assertIn("Secure", result["answer"])
        self.assertIn("Daconil", result["answer"])
        self.assertIn("contact", result["answer"].lower())

    def test_verified_product_comparison_handles_banner_vs_headway(self):
        result = answer_from_verified_kb("What is the difference between Banner MAXX and Headway?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified_comparison")
        self.assertIn("Banner MAXX", result["answer"])
        self.assertIn("Headway", result["answer"])

    def test_headway_single_product_question_returns_verified_targets(self):
        result = answer_from_verified_kb("What is Headway used for?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertIn("Headway", result["answer"])
        self.assertIn("verified diseases", result["answer"].lower())

    def test_headway_single_product_interval_question_returns_verified_interval(self):
        result = answer_from_verified_kb("How soon can I spray Headway again?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertIn("Headway", result["answer"])
        self.assertIn("14-day or 28-day", result["answer"])

    def test_verified_product_comparison_handles_heritage_vs_secure(self):
        result = answer_from_verified_kb("What is the difference between Heritage and Secure?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified_comparison")
        self.assertIn("Heritage", result["answer"])
        self.assertIn("Secure", result["answer"])

    def test_verified_product_comparison_handles_secure_vs_medallion(self):
        result = answer_from_verified_kb("What is the difference between Secure and Medallion?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified_comparison")
        self.assertIn("Secure", result["answer"])
        self.assertIn("Medallion", result["answer"])

    def test_headway_single_product_good_for_question_returns_verified_targets(self):
        result = answer_from_verified_kb("What is Headway good for?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertIn("Headway", result["answer"])

    def test_lexicon_single_product_question_returns_verified_targets(self):
        result = answer_from_verified_kb("What is Lexicon used for?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertIn("Lexicon", result["answer"])
        self.assertIn("verified diseases", result["answer"].lower())

    def test_lexicon_single_product_interval_question_returns_verified_interval(self):
        result = answer_from_verified_kb("How soon can I spray Lexicon again?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertIn("Lexicon", result["answer"])
        self.assertIn("14- to 28-day", result["answer"])

    def test_poacure_single_product_question_returns_verified_targets(self):
        result = answer_from_verified_kb("What is PoaCure used for?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertIn("PoaCure", result["answer"])
        self.assertIn("annual bluegrass", result["answer"].lower())
        self.assertIn("roughstalk bluegrass", result["answer"].lower())

    def test_poacure_single_product_interval_question_returns_verified_interval(self):
        result = answer_from_verified_kb("How soon can I spray PoaCure again?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertIn("PoaCure", result["answer"])
        self.assertIn("2- to 3-week", result["answer"])

    def test_poacure_overseeding_question_returns_verified_timing(self):
        result = answer_from_verified_kb("Can I overseed after PoaCure?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertIn("45 days", result["answer"])
        self.assertIn("12 weeks", result["answer"])

    def test_briskway_single_product_question_returns_verified_targets(self):
        result = answer_from_verified_kb("What is Briskway used for?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertIn("Briskway", result["answer"])
        self.assertIn("anthracnose", result["answer"].lower())
        self.assertIn("dollar spot", result["answer"].lower())

    def test_briskway_single_product_interval_question_returns_verified_interval(self):
        result = answer_from_verified_kb("How soon can I spray Briskway again?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertIn("Briskway", result["answer"])
        self.assertIn("14- to 28-day", result["answer"])

    def test_briskway_supported_targets_question_returns_verified_diseases(self):
        result = answer_from_verified_kb("What diseases does Briskway control?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertIn("fairy ring", result["answer"].lower())
        self.assertIn("gray leaf spot", result["answer"].lower())

    def test_kerb_single_product_question_returns_verified_targets(self):
        result = answer_from_verified_kb("What is Kerb SC used for?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertIn("Kerb SC", result["answer"])
        self.assertIn("annual bluegrass", result["answer"].lower())
        self.assertIn("perennial ryegrass", result["answer"].lower())

    def test_kerb_single_product_interval_question_returns_verified_interval(self):
        result = answer_from_verified_kb("How soon can I spray Kerb SC again?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertIn("Kerb SC", result["answer"])
        self.assertIn("3 applications per year", result["answer"])

    def test_kerb_overseeding_question_returns_verified_timing(self):
        result = answer_from_verified_kb("Can I overseed after Kerb SC?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertIn("90 days", result["answer"])
        self.assertIn("activated charcoal", result["answer"].lower())

    def test_posterity_single_product_question_returns_verified_targets(self):
        result = answer_from_verified_kb("What is Posterity used for?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertIn("Posterity", result["answer"])
        self.assertIn("dollar spot", result["answer"].lower())
        self.assertIn("microdochium", result["answer"].lower())

    def test_posterity_single_product_interval_question_returns_verified_interval(self):
        result = answer_from_verified_kb("How soon can I spray Posterity again?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertIn("Posterity", result["answer"])
        self.assertIn("14- to 28-day", result["answer"])
        self.assertIn("2 sequential applications", result["answer"])

    def test_posterity_supported_targets_question_returns_verified_diseases(self):
        result = answer_from_verified_kb("What diseases does Posterity control?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertIn("fairy ring", result["answer"].lower())
        self.assertIn("spring dead spot", result["answer"].lower())

    def test_tartan_single_product_question_returns_verified_targets(self):
        result = answer_from_verified_kb("What is Tartan used for?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertIn("Tartan", result["answer"])
        self.assertIn("dollar spot", result["answer"].lower())
        self.assertIn("brown patch", result["answer"].lower())

    def test_tartan_single_product_interval_question_returns_verified_interval(self):
        result = answer_from_verified_kb("How soon can I spray Tartan again?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertIn("Tartan", result["answer"])
        self.assertIn("14- to 28-day", result["answer"])
        self.assertIn("3 sequential applications", result["answer"])

    def test_tartan_supported_targets_question_returns_verified_diseases(self):
        result = answer_from_verified_kb("What diseases does Tartan control?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertIn("fairy ring", result["answer"].lower())
        self.assertIn("summer patch", result["answer"].lower())

    def test_fiata_single_product_question_returns_verified_targets(self):
        result = answer_from_verified_kb("What is Fiata used for?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertIn("Fiata", result["answer"])
        self.assertIn("pythium blight", result["answer"].lower())

    def test_fiata_single_product_interval_question_returns_verified_interval(self):
        result = answer_from_verified_kb("How soon can I spray Fiata again?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertIn("Fiata", result["answer"])
        self.assertIn("14- to 28-day", result["answer"])

    def test_fiata_supported_targets_question_returns_verified_diseases(self):
        result = answer_from_verified_kb("What diseases does Fiata control?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertIn("pythium blight", result["answer"].lower())

    def test_instrata_single_product_question_returns_verified_targets(self):
        result = answer_from_verified_kb("What is Instrata used for?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertIn("Instrata", result["answer"])
        self.assertIn("anthracnose", result["answer"].lower())
        self.assertIn("dollar spot", result["answer"].lower())

    def test_instrata_single_product_interval_question_returns_verified_interval(self):
        result = answer_from_verified_kb("How soon can I spray Instrata again?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertIn("Instrata", result["answer"])
        self.assertIn("14- to 28-day", result["answer"])
        self.assertIn("21- to 28-day", result["answer"])

    def test_instrata_supported_targets_question_returns_verified_diseases(self):
        result = answer_from_verified_kb("What diseases does Instrata control?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertIn("summer patch", result["answer"].lower())
        self.assertIn("yellow patch", result["answer"].lower())

    def test_navicon_single_product_question_returns_verified_targets(self):
        result = answer_from_verified_kb("What is Navicon used for?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertIn("Navicon", result["answer"])
        self.assertIn("anthracnose", result["answer"].lower())
        self.assertIn("dollar spot", result["answer"].lower())

    def test_navicon_single_product_interval_question_returns_verified_interval(self):
        result = answer_from_verified_kb("How soon can I spray Navicon again?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertIn("Navicon", result["answer"])
        self.assertIn("14- to 28-day", result["answer"])
        self.assertIn("10 days", result["answer"])

    def test_navicon_supported_targets_question_returns_verified_diseases(self):
        result = answer_from_verified_kb("What diseases does Navicon control?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertIn("pythium blight", result["answer"].lower())
        self.assertIn("summer patch", result["answer"].lower())

    def test_interface_single_product_question_returns_verified_targets(self):
        result = answer_from_verified_kb("What is Interface used for?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertIn("Interface", result["answer"])
        self.assertIn("dollar spot", result["answer"].lower())
        self.assertIn("brown patch", result["answer"].lower())

    def test_interface_single_product_interval_question_returns_verified_interval(self):
        result = answer_from_verified_kb("How soon can I spray Interface again?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertIn("Interface", result["answer"])
        self.assertIn("14- to 21-day", result["answer"])
        self.assertIn("14- to 28-day", result["answer"])

    def test_interface_supported_targets_question_returns_verified_diseases(self):
        result = answer_from_verified_kb("What diseases does Interface control?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertIn("microdochium patch", result["answer"].lower())
        self.assertIn("pink snow mold", result["answer"].lower())

    def test_mirage_single_product_question_returns_verified_targets(self):
        result = answer_from_verified_kb("What is Mirage StressGard used for?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertIn("Mirage", result["answer"])
        self.assertIn("dollar spot", result["answer"].lower())
        self.assertIn("spring dead spot", result["answer"].lower())

    def test_mirage_single_product_interval_question_returns_verified_interval(self):
        result = answer_from_verified_kb("How soon can I spray Mirage StressGard again?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertIn("Mirage", result["answer"])
        self.assertIn("14- to 28-day", result["answer"])
        self.assertIn("10- to 14-day", result["answer"])

    def test_mirage_supported_targets_question_returns_verified_diseases(self):
        result = answer_from_verified_kb("What diseases does Mirage StressGard control?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertIn("fairy ring", result["answer"].lower())
        self.assertIn("take all patch", result["answer"].lower())

    def test_compass_single_product_question_returns_verified_targets(self):
        result = answer_from_verified_kb("What is Compass used for?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertIn("Compass", result["answer"])
        self.assertIn("anthracnose", result["answer"].lower())
        self.assertIn("summer patch", result["answer"].lower())

    def test_compass_single_product_interval_question_returns_verified_interval(self):
        result = answer_from_verified_kb("How soon can I spray Compass again?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertIn("Compass", result["answer"])
        self.assertIn("14- to 21-day", result["answer"])
        self.assertIn("21 to 28 days", result["answer"])

    def test_compass_supported_targets_question_returns_verified_diseases(self):
        result = answer_from_verified_kb("What diseases does Compass control?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertIn("rapid blight", result["answer"].lower())
        self.assertIn("dollar spot", result["answer"].lower())

    def test_concert_single_product_question_returns_verified_targets(self):
        result = answer_from_verified_kb("What is Concert used for?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertIn("Concert", result["answer"])
        self.assertIn("anthracnose", result["answer"].lower())
        self.assertIn("brown patch", result["answer"].lower())

    def test_concert_single_product_interval_question_returns_verified_interval(self):
        result = answer_from_verified_kb("How soon can I spray Concert again?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertIn("Concert", result["answer"])
        self.assertIn("14 days", result["answer"])
        self.assertIn("14- to 28-day", result["answer"])

    def test_concert_supported_targets_question_returns_verified_diseases(self):
        result = answer_from_verified_kb("What diseases does Concert control?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertIn("take all patch", result["answer"].lower())
        self.assertIn("gray snow mold", result["answer"].lower())

    def test_resilia_single_product_question_returns_verified_targets(self):
        result = answer_from_verified_kb("What is Resilia used for?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertIn("Resilia", result["answer"])
        self.assertIn("fairy ring", result["answer"].lower())
        self.assertIn("summer patch", result["answer"].lower())

    def test_resilia_single_product_interval_question_returns_verified_interval(self):
        result = answer_from_verified_kb("How soon can I spray Resilia again?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertIn("Resilia", result["answer"])
        self.assertIn("14- to 28-day", result["answer"])
        self.assertIn("14-day minimum", result["answer"])

    def test_resilia_supported_targets_question_returns_verified_diseases(self):
        result = answer_from_verified_kb("What diseases does Resilia control?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertIn("pythium root rot", result["answer"].lower())
        self.assertIn("spring dead spot", result["answer"].lower())

    def test_divanem_single_product_question_returns_verified_targets(self):
        result = answer_from_verified_kb("What is Divanem used for?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertIn("Divanem", result["answer"])
        self.assertIn("nematodes", result["answer"].lower())
        self.assertIn("bermudagrass mite", result["answer"].lower())

    def test_divanem_single_product_interval_question_returns_verified_interval(self):
        result = answer_from_verified_kb("How soon can I apply Divanem again?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertIn("Divanem", result["answer"])
        self.assertIn("14- to 21-day", result["answer"])
        self.assertIn("21- to 28-day", result["answer"])

    def test_divanem_supported_targets_question_returns_verified_pests(self):
        result = answer_from_verified_kb("What pests does Divanem control?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertIn("turf parasitic nematodes", result["answer"].lower())
        self.assertIn("bermudagrass mite", result["answer"].lower())

    def test_headway_single_product_for_question_returns_verified_targets(self):
        result = answer_from_verified_kb("What is Headway for?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertIn("Headway", result["answer"])
        self.assertIn("dollar spot", result["answer"].lower())

    def test_headway_vs_heritage_returns_verified_comparison(self):
        result = answer_from_verified_kb("Headway vs Heritage")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified_comparison")
        self.assertIn("Headway", result["answer"])
        self.assertIn("Heritage", result["answer"])
        self.assertIn("FRAC 11", result["answer"])

    def test_unsupported_product_target_answer_says_no_cleanly(self):
        result = answer_from_verified_kb("Does Xzemplar control anthracnose?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "not_verified")
        self.assertIn("**Bottom Line:** No.", result["answer"])
        self.assertIn("what i can verify for xzemplar", result["answer"].lower())

    def test_target_recommendation_returns_verified_fungicide_options(self):
        result = recommend_verified_products_for_target("What fungicides control dollar spot?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified_target_options")
        self.assertEqual(result["confidence"]["label"], "Verified Target Options")
        self.assertIn("Daconil", result["answer"])
        self.assertIn("Banner MAXX", result["answer"])

    def test_target_recommendation_returns_verified_herbicide_options(self):
        result = recommend_verified_products_for_target("What herbicides control crabgrass?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified_target_options")
        self.assertEqual(result["confidence"]["label"], "Verified Target Options")
        self.assertIn("Q4 Plus", result["answer"])
        self.assertIn("Drive XLR8", result["answer"])

    def test_target_recommendation_returns_verified_insecticide_options(self):
        result = recommend_verified_products_for_target("What insecticides control grubs?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified_target_options")
        self.assertEqual(result["confidence"]["label"], "Verified Target Options")
        self.assertIn("Acelepryn", result["answer"])
        self.assertIn("Ference", result["answer"])

    def test_target_recommendation_handles_plain_abw_controls_question(self):
        result = recommend_verified_products_for_target("What controls annual bluegrass weevil?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified_target_options")
        self.assertIn("Ference", result["answer"])
        self.assertIn("Provaunt WDG", result["answer"])

    def test_target_recommendation_defers_when_turf_is_named_without_surface(self):
        result = recommend_verified_products_for_target(
            "What fungicide should I use for dollar spot on bentgrass?"
        )

        self.assertIsNone(result)

    def test_pgr_rate_question_without_surface_returns_context_needed(self):
        result = answer_product_context_needed(
            "How much Primo should I use?",
            {
                "surfaces": {
                    "greens": "creeping bentgrass",
                    "fairways": "bermudagrass",
                    "tees": "bermudagrass",
                    "rough": "tall fescue",
                }
            },
        )

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "needs_more_context")
        self.assertEqual(result["confidence"]["label"], "Needs More Context")
        self.assertIn("surface", result["answer"].lower())

    def test_mystery_disease_question_returns_context_needed(self):
        result = answer_product_context_needed(
            "What should I spray on greens for a mystery disease?",
            {"surfaces": {"greens": "creeping bentgrass"}},
        )

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "needs_more_context")
        self.assertIn("symptoms or target disease", result["answer"].lower())

    def test_surface_target_question_can_infer_surface_from_saved_turf_name(self):
        result = recommend_verified_products_for_surface_target(
            "What fungicide should I use for dollar spot on bentgrass?",
            {
                "surfaces": {
                    "greens": "creeping bentgrass",
                    "fairways": "kentucky bluegrass",
                    "tees": "bermudagrass",
                    "rough": "tall fescue",
                }
            },
        )

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified_surface_target_options")
        self.assertEqual(result["surface"], "greens")
        self.assertEqual(result["turf"], "creeping bentgrass")
        self.assertIn("Daconil", result["answer"])

    def test_non_product_science_question_with_causes_does_not_trigger_product_path(self):
        result = recommend_verified_products_for_surface_target(
            "What causes Poa annua to decline faster than bentgrass in summer?",
            {
                "surfaces": {
                    "greens": "creeping bentgrass",
                    "fairways": "kentucky bluegrass",
                }
            },
        )

        self.assertIsNone(result)

    def test_target_plus_turf_without_surface_returns_context_needed(self):
        result = answer_product_context_needed(
            "What fungicide should I use for dollar spot on bentgrass?",
            {},
        )

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "needs_more_context")
        self.assertEqual(result["confidence"]["label"], "Needs More Context")
        self.assertIn("surface", result["answer"].lower())
        self.assertIn("bentgrass", result["answer"].lower())

    def test_bent_shorthand_can_use_saved_turf_name_as_surface_hint(self):
        result = recommend_verified_products_for_surface_target(
            "What fungicide for dollar spot on bent?",
            {
                "surfaces": {
                    "greens": "creeping bentgrass",
                    "fairways": "kentucky bluegrass",
                }
            },
        )

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified_surface_target_options")
        self.assertEqual(result["surface"], "greens")

    def test_explicit_surface_with_conflicting_turf_returns_context_needed(self):
        result = answer_product_context_needed(
            "What can I spray for dollar spot on bentgrass fairways?",
            {
                "surfaces": {
                    "greens": "creeping bentgrass",
                    "fairways": "kentucky bluegrass",
                }
            },
        )

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "needs_more_context")
        self.assertIn("saved profile says", result["answer"].lower())
        self.assertIn("fairways", result["answer"].lower())

    def test_rei_question_returns_verified_interval(self):
        result = answer_from_verified_kb("What is the reentry interval for Daconil?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertEqual(result["confidence"]["label"], "Verified Label Interval")
        self.assertIn("12 hours", result["answer"])

    def test_rei_plain_language_question_returns_verified_interval(self):
        result = answer_from_verified_kb("How long do I have to stay off Daconil-treated turf?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertEqual(result["confidence"]["label"], "Verified Label Interval")
        self.assertIn("12 hours", result["answer"])

    def test_rei_placeholder_does_not_turn_missing_interval_into_verified_answer(self):
        result = answer_from_verified_kb("REI for Briskway?")

        self.assertIsNone(result)

    def test_interval_question_returns_verified_guidance_for_daconil(self):
        result = answer_from_verified_kb("What is the retreatment interval for Daconil?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertEqual(result["confidence"]["label"], "Verified Re-Treatment Interval")
        self.assertIn("7 days", result["answer"])
        self.assertIn("14 days", result["answer"])

    def test_interval_plain_language_question_returns_verified_guidance_for_daconil(self):
        result = answer_from_verified_kb("How soon can I spray Daconil again?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertEqual(result["confidence"]["label"], "Verified Re-Treatment Interval")
        self.assertIn("7 days", result["answer"])

    def test_interval_plain_language_question_returns_verified_guidance_for_banner(self):
        result = answer_from_verified_kb("How soon can I spray Banner MAXX again?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertEqual(result["confidence"]["label"], "Verified Re-Treatment Interval")
        self.assertIn("28-day schedule", result["answer"].lower())
        self.assertIn("14-day schedule", result["answer"].lower())

    def test_primo_science_explainer_does_not_fall_into_verified_product_path(self):
        result = answer_from_verified_kb("Why does clipping yield matter more than calendar interval in Primo timing?")

        self.assertIsNone(result)

    def test_interval_question_returns_verified_guidance_for_acelepryn(self):
        result = answer_from_verified_kb("How soon can I retreat Acelepryn G?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertEqual(result["confidence"]["label"], "Verified Re-Treatment Interval")
        self.assertIn("7 days", result["answer"])

    def test_irrigation_question_returns_verified_guidance_for_primo(self):
        result = answer_from_verified_kb("Do I need to water in Primo MAXX after application?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertEqual(result["confidence"]["label"], "Verified Irrigation Guidance")
        self.assertIn("rainfast", result["answer"].lower())
        self.assertIn("watering-in is not necessary", result["answer"].lower())

    def test_irrigation_plain_language_question_returns_verified_guidance_for_primo(self):
        result = answer_from_verified_kb("Do I need to water this in after Primo MAXX?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertEqual(result["confidence"]["label"], "Verified Irrigation Guidance")
        self.assertIn("watering-in is not necessary", result["answer"].lower())

    def test_irrigation_question_returns_verified_guidance_for_dimension(self):
        result = answer_from_verified_kb("Do I need to water in Dimension after application?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertEqual(result["confidence"]["label"], "Verified Irrigation Guidance")
        self.assertIn("0.5 inch of water", result["answer"].lower())
        self.assertIn("6 hours", result["answer"].lower())

    def test_irrigation_question_returns_verified_guidance_for_dylox(self):
        result = answer_from_verified_kb("Do I need to water in Dylox after application?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertEqual(result["confidence"]["label"], "Verified Irrigation Guidance")
        self.assertIn("watering-in is mandatory", result["answer"].lower())
        self.assertIn("same day", result["answer"].lower())

    def test_irrigation_question_returns_verified_guidance_for_gallery_sc(self):
        result = answer_from_verified_kb("Do I need to water in Gallery SC after application?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertEqual(result["confidence"]["label"], "Verified Irrigation Guidance")
        self.assertIn("0.5 inches or more", result["answer"].lower())
        self.assertIn("activate gallery sc", result["answer"].lower())

    def test_irrigation_question_returns_verified_guidance_for_dismiss(self):
        result = answer_from_verified_kb("Do I need to water in Dismiss after application?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertEqual(result["confidence"]["label"], "Verified Irrigation Guidance")
        self.assertIn("within 24 hours", result["answer"].lower())
        self.assertIn("10 days", result["answer"].lower())

    def test_irrigation_question_returns_verified_guidance_for_provaunt(self):
        result = answer_from_verified_kb("Do I need to water in Provaunt WDG after application?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertEqual(result["confidence"]["label"], "Verified Irrigation Guidance")
        self.assertIn("1/8 inch", result["answer"].lower())
        self.assertIn("pre-wet with irrigation", result["answer"].lower())

    def test_irrigation_question_returns_verified_guidance_for_talstar(self):
        result = answer_from_verified_kb("Do I need to water in Talstar after application?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertEqual(result["confidence"]["label"], "Verified Irrigation Guidance")
        self.assertIn("0.25 inches", result["answer"].lower())

    def test_retreatment_question_returns_verified_guidance_for_subdue_maxx(self):
        result = answer_from_verified_kb("How soon can I spray Subdue MAXX again?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertEqual(result["confidence"]["label"], "Verified Re-Treatment Interval")
        self.assertIn("30 days", result["answer"].lower())

    def test_retreatment_question_for_conserve_sc_no_longer_leaks_tree_pest_copy(self):
        result = answer_from_verified_kb("How soon can I spray Conserve SC again?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertEqual(result["confidence"]["label"], "Verified Re-Treatment Interval")
        self.assertIn("no single fixed turf retreatment interval", result["answer"].lower())
        self.assertNotIn("emerald ash borer", result["answer"].lower())

    def test_rainfast_question_returns_verified_guidance(self):
        result = answer_from_verified_kb("Is Primo MAXX rainfast?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertEqual(result["confidence"]["label"], "Verified Rainfast Guidance")
        self.assertIn("one hour", result["answer"].lower())

    def test_rainfast_plain_language_question_returns_verified_guidance(self):
        result = answer_from_verified_kb("What if it rains after Primo MAXX?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertEqual(result["confidence"]["label"], "Verified Rainfast Guidance")
        self.assertIn("rainfast", result["answer"].lower())

    def test_rainfast_question_returns_verified_guidance_for_turflon_ester(self):
        result = answer_from_verified_kb("What if it rains after Turflon Ester?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertEqual(result["confidence"]["label"], "Verified Rainfast Guidance")
        self.assertIn("24 hours", result["answer"].lower())

    def test_max_application_question_returns_verified_guidance(self):
        result = answer_from_verified_kb("What is the max single application rate for Tenacity?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertEqual(result["confidence"]["label"], "Verified Max Application Rate")
        self.assertIn("8 fl oz", result["answer"].lower())

    def test_annual_limit_question_returns_verified_guidance_for_tenacity(self):
        result = answer_from_verified_kb("What's the annual limit on Tenacity?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertEqual(result["confidence"]["label"], "Verified Annual Use Limit")
        self.assertIn("16 oz", result["answer"].lower())

    def test_annual_limit_question_returns_verified_guidance(self):
        result = answer_from_verified_kb("What is the max annual amount of Acelepryn G?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertEqual(result["confidence"]["label"], "Verified Annual Use Limit")
        self.assertIn("per year", result["answer"].lower())

    def test_annual_application_count_question_returns_verified_guidance(self):
        result = answer_from_verified_kb("How many applications per year can I make with Heritage?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertEqual(result["confidence"]["label"], "Verified Annual Application Limit")
        self.assertIn("eight applications", result["answer"].lower())

    def test_annual_application_count_plain_language_question_returns_verified_guidance(self):
        result = answer_from_verified_kb("How often can I use Heritage in a year?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertEqual(result["confidence"]["label"], "Verified Annual Application Limit")
        self.assertIn("eight applications", result["answer"].lower())

    def test_reseeding_question_returns_verified_guidance(self):
        result = answer_from_verified_kb("How long after Dimension can I reseed?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertEqual(result["confidence"]["label"], "Verified Reseeding Interval")
        self.assertIn("3 months", result["answer"].lower())

    def test_reseeding_plain_language_question_returns_verified_guidance(self):
        result = answer_from_verified_kb("Can I seed after Dimension?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertEqual(result["confidence"]["label"], "Verified Reseeding Interval")
        self.assertIn("3 months", result["answer"].lower())

    def test_reseeding_question_returns_verified_guidance_for_tenacity(self):
        result = answer_from_verified_kb("Can I seed after Tenacity?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertEqual(result["confidence"]["label"], "Verified Reseeding Interval")
        self.assertIn("mowed two times", result["answer"].lower())

    def test_reseeding_question_returns_verified_guidance_for_pylex(self):
        result = answer_from_verified_kb("Can I seed after Pylex?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertEqual(result["confidence"]["label"], "Verified Reseeding Interval")
        self.assertIn("3 weeks", result["answer"].lower())

    def test_overseeding_question_returns_verified_guidance(self):
        result = answer_from_verified_kb("Can I overseed after SedgeHammer?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertEqual(result["confidence"]["label"], "Verified Overseeding Interval")
        self.assertIn("2 weeks", result["answer"].lower())

    def test_overseeding_question_returns_verified_guidance_for_tenacity(self):
        result = answer_from_verified_kb("Can I overseed after Tenacity?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertEqual(result["confidence"]["label"], "Verified Overseeding Interval")
        self.assertIn("four weeks after emergence", result["answer"].lower())

    def test_annual_limit_question_returns_verified_guidance_for_pylex(self):
        result = answer_from_verified_kb("What's the annual limit on Pylex?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertEqual(result["confidence"]["label"], "Verified Annual Use Limit")
        self.assertIn("4 fl ozs pylex per acre per year", result["answer"].lower())

    def test_annual_limit_question_returns_verified_guidance_for_lontrel(self):
        result = answer_from_verified_kb("What's the annual limit on Lontrel?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertEqual(result["confidence"]["label"], "Verified Annual Use Limit")
        self.assertIn("1 1/3 pint per acre per year", result["answer"].lower())

    def test_annual_limit_question_returns_verified_guidance_for_merit(self):
        result = answer_from_verified_kb("What's the annual limit on Merit?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertEqual(result["confidence"]["label"], "Verified Annual Use Limit")
        self.assertIn("1.6 pt", result["answer"].lower())

    def test_annual_limit_question_returns_verified_guidance_for_arena(self):
        result = answer_from_verified_kb("What's the annual limit on Arena?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertEqual(result["confidence"]["label"], "Verified Annual Use Limit")
        self.assertIn("12.8 oz per acre per year", result["answer"].lower())

    def test_annual_application_count_question_returns_verified_guidance_for_subdue_maxx(self):
        result = answer_from_verified_kb("How many applications per year can I make with Subdue MAXX?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertEqual(result["confidence"]["label"], "Verified Annual Application Limit")
        self.assertIn("3 applications", result["answer"].lower())

    def test_retreatment_question_recognizes_banner_reapplied_phrasing(self):
        result = answer_from_verified_kb("How soon can Banner MAXX be reapplied?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertEqual(result["confidence"]["label"], "Verified Re-Treatment Interval")
        self.assertIn("28-day schedule", result["answer"])
        self.assertIn("Banner MAXX", result["answer"])

    def test_annual_limit_question_returns_verified_guidance_for_drive_xlr8(self):
        result = answer_from_verified_kb("What's the annual limit on Drive XLR8?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertEqual(result["confidence"]["label"], "Verified Annual Use Limit")
        self.assertIn("128 fl ozs", result["answer"].lower())

    def test_annual_limit_question_returns_verified_guidance_for_basagran(self):
        result = answer_from_verified_kb("What's the annual limit on Basagran?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertEqual(result["confidence"]["label"], "Verified Annual Use Limit")
        self.assertIn("64 fl ozs", result["answer"].lower())

    def test_annual_limit_question_returns_verified_guidance_for_q4_plus(self):
        result = answer_from_verified_kb("What's the annual limit on Q4 Plus?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertEqual(result["confidence"]["label"], "Verified Annual Use Limit")
        self.assertIn("16 pints", result["answer"].lower())

    def test_annual_limit_question_returns_verified_guidance_for_specticle(self):
        result = answer_from_verified_kb("What's the annual limit on Specticle?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertEqual(result["confidence"]["label"], "Verified Annual Use Limit")

    def test_annual_max_phrase_returns_verified_guidance_for_primo_maxx(self):
        result = answer_from_verified_kb("What is the annual max for Primo MAXX?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertEqual(result["confidence"]["label"], "Verified Annual Use Limit")
        self.assertIn("19.0 pt", result["answer"])
        self.assertIn("7.0 fl oz per 1,000 sq ft per year", result["answer"].lower())

    def test_reseeding_question_without_verified_guidance_stays_not_verified_for_primo(self):
        result = answer_from_verified_kb("Can I seed after Primo MAXX?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "not_verified")
        self.assertIn("do not have verified reseeding or overseeding guidance", result["answer"].lower())

    def test_interval_question_returns_verified_guidance_for_scimitar(self):
        result = answer_from_verified_kb("How soon can I spray Scimitar again?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertEqual(result["confidence"]["label"], "Verified Re-Treatment Interval")
        self.assertIn("7-day intervals", result["answer"].lower())

    def test_interval_question_returns_verified_guidance_for_gallery_sc(self):
        result = answer_from_verified_kb("How soon can I spray Gallery SC again?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertEqual(result["confidence"]["label"], "Verified Re-Treatment Interval")
        self.assertIn("60 days", result["answer"].lower())

    def test_interval_question_returns_verified_guidance_for_confront(self):
        result = answer_from_verified_kb("How soon can I spray Confront again?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertEqual(result["confidence"]["label"], "Verified Re-Treatment Interval")
        self.assertIn("4 weeks", result["answer"].lower())

    def test_interval_question_returns_verified_guidance_for_q4_plus(self):
        result = answer_from_verified_kb("How soon can I spray Q4 Plus again?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertEqual(result["confidence"]["label"], "Verified Re-Treatment Interval")
        self.assertIn("30 days", result["answer"].lower())

    def test_interval_question_returns_verified_guidance_for_advion(self):
        result = answer_from_verified_kb("How soon can I apply Advion Fire Ant Bait again?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertEqual(result["confidence"]["label"], "Verified Re-Treatment Interval")
        self.assertIn("12 weeks", result["answer"].lower())
        self.assertIn("7 days", result["answer"].lower())

    def test_application_window_question_returns_verified_guidance_for_merit(self):
        result = answer_from_verified_kb("Can I mow right after Merit?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertEqual(result["confidence"]["label"], "Verified Application Window Guidance")
        self.assertIn("do not mow turf or lawn area", result["answer"].lower())

    def test_application_window_question_returns_verified_guidance_for_scimitar(self):
        result = answer_from_verified_kb("Can I mow right after Scimitar?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertEqual(result["confidence"]["label"], "Verified Application Window Guidance")
        self.assertIn("12-24 hours", result["answer"].lower())

    def test_application_window_question_returns_verified_guidance(self):
        result = answer_from_verified_kb("Can I mow after applying Banner MAXX?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertEqual(result["confidence"]["label"], "Verified Application Window Guidance")
        self.assertIn("after mowing", result["answer"].lower())
        self.assertIn("before mowing", result["answer"].lower())

    def test_application_window_plain_language_question_returns_verified_guidance(self):
        result = answer_from_verified_kb("Can I mow right after Banner MAXX?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertEqual(result["confidence"]["label"], "Verified Application Window Guidance")
        self.assertIn("after mowing", result["answer"].lower())

    def test_application_window_question_returns_verified_guidance_for_daconil(self):
        result = answer_from_verified_kb("Can I mow right after Daconil?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertEqual(result["confidence"]["label"], "Verified Application Window Guidance")
        self.assertIn("do not mow or water", result["answer"].lower())

    def test_application_window_question_returns_verified_guidance_for_basagran(self):
        result = answer_from_verified_kb("Can I mow right after Basagran?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertEqual(result["confidence"]["label"], "Verified Application Window Guidance")
        self.assertIn("3 days before or after", result["answer"].lower())
        self.assertIn("5 days", result["answer"].lower())

    def test_application_window_question_returns_verified_guidance_for_turflon_ester(self):
        result = answer_from_verified_kb("Can I mow right after Turflon Ester?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertEqual(result["confidence"]["label"], "Verified Application Window Guidance")
        self.assertIn("mow newly seeded turf 2 or 3 times before treating", result["answer"].lower())
        self.assertIn("24 hours after application", result["answer"].lower())

    def test_application_window_question_returns_verified_guidance_for_talstar(self):
        result = answer_from_verified_kb("Can I mow right after Talstar?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertEqual(result["confidence"]["label"], "Verified Application Window Guidance")
        self.assertIn("24 hours after application", result["answer"].lower())

    def test_application_window_question_returns_verified_guidance_for_provaunt(self):
        result = answer_from_verified_kb("Can I mow right after Provaunt WDG?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertEqual(result["confidence"]["label"], "Verified Application Window Guidance")
        self.assertIn("delay watering", result["answer"].lower())
        self.assertIn("24 hours after application", result["answer"].lower())

    def test_application_window_question_returns_verified_guidance_for_ference(self):
        result = answer_from_verified_kb("Can I mow right after Ference?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertEqual(result["confidence"]["label"], "Verified Application Window Guidance")
        self.assertIn("delay watering", result["answer"].lower())
        self.assertIn("24 hours after application", result["answer"].lower())

    def test_annual_limit_question_returns_verified_guidance_for_advion(self):
        result = answer_from_verified_kb("What's the annual limit on Advion Fire Ant Bait?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertEqual(result["confidence"]["label"], "Verified Annual Use Limit")
        self.assertIn("6 total pounds", result["answer"].lower())

    def test_application_window_question_returns_verified_guidance_for_q4_plus(self):
        result = answer_from_verified_kb("Can I mow right after Q4 Plus?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertEqual(result["confidence"]["label"], "Verified Application Window Guidance")
        self.assertIn("delay mowing 2 days before and until 2 days after", result["answer"].lower())

    def test_overseeding_question_returns_verified_guidance_for_gallery_sc(self):
        result = answer_from_verified_kb("Can I overseed after Gallery SC?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertEqual(result["confidence"]["label"], "Verified Overseeding Interval")
        self.assertIn("60 days", result["answer"].lower())

    def test_tank_mix_question_returns_verified_guidance_when_supported(self):
        result = answer_from_verified_kb("Can I tank mix Daconil and Heritage for dollar spot?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertEqual(result["confidence"]["label"], "Verified Tank-Mix Guidance")
        self.assertIn("dollar spot", result["answer"].lower())
        self.assertIn("compatibility", result["answer"].lower())

    def test_unsupported_product_target_is_blocked(self):
        result = answer_from_verified_kb("Can I use Tenacity to kill Poa trivialis in tall fescue?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "not_verified")
        self.assertTrue(result["needs_review"])
        self.assertIn("**Bottom Line:** No.", result["answer"])
        self.assertIn("do **not** have verified support", result["answer"])
        self.assertNotIn("**Bottom Line:** Yes", result["answer"])

    def test_non_product_question_falls_through(self):
        self.assertIsNone(answer_from_verified_kb("Why are my greens yellow after rain?"))

    def test_supported_target_with_unsafe_surface_is_blocked(self):
        result = answer_from_verified_kb("Can I use Specticle for crabgrass on bentgrass greens?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "surface_restricted")
        self.assertTrue(result["needs_review"])
        self.assertIn("can't verify", result["answer"])

    def test_structured_prohibited_surface_is_blocked(self):
        result = answer_from_verified_kb("Can I use Drive XLR8 for crabgrass on St Augustine?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "surface_restricted")
        self.assertTrue(result["needs_review"])
        self.assertIn("surface restriction", result["answer"].lower())

    def test_structured_allowed_surface_excludes_other_surfaces(self):
        result = answer_from_verified_kb("Can I use Acclaim Extra for crabgrass on bermudagrass?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "surface_restricted")
        self.assertTrue(result["needs_review"])
        self.assertIn("surface restriction", result["answer"].lower())

    def test_pgr_surface_rate_returns_verified_answer(self):
        result = answer_from_verified_kb("What Primo MAXX rate should I use on fairways?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertFalse(result["needs_review"])
        self.assertIn("6-11 fl oz/acre", result["answer"])

    def test_insect_pest_target_returns_verified_answer(self):
        result = answer_from_verified_kb("Can I use Bifenthrin for ants?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertFalse(result["needs_review"])
        self.assertIn("Talstar", result["answer"])

    def test_updated_acelepryn_record_returns_verified_answer(self):
        result = answer_from_verified_kb("Can I use Acelepryn for annual bluegrass weevil?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertFalse(result["needs_review"])
        self.assertIn("Acelepryn", result["answer"])
        self.assertIn("75-100 lb product/acre", result["answer"])

    def test_updated_merit_record_returns_verified_answer(self):
        result = answer_from_verified_kb("Can I use Merit for billbugs?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertFalse(result["needs_review"])
        self.assertIn("Merit", result["answer"])
        self.assertIn("1.25-1.6 pt/acre", result["answer"])

    def test_new_weed_alias_returns_verified_answer(self):
        result = answer_from_verified_kb("Can I use Drive XLR8 for foxtail on bermudagrass?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertFalse(result["needs_review"])
        self.assertIn("foxtail", result["answer"])

    def test_new_broadleaf_product_returns_verified_answer(self):
        result = answer_from_verified_kb("Can I use Lontrel for clover?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertFalse(result["needs_review"])
        self.assertIn("Lontrel", result["answer"])

    def test_new_grass_weed_product_returns_verified_answer(self):
        result = answer_from_verified_kb("Can I use Pylex for nimblewill?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertFalse(result["needs_review"])
        self.assertIn("Pylex", result["answer"])

    def test_new_insect_product_returns_verified_answer(self):
        result = answer_from_verified_kb("Can I use Scimitar for fire ants?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertFalse(result["needs_review"])
        self.assertIn("Scimitar", result["answer"])

    def test_confront_returns_verified_answer_for_clover(self):
        result = answer_from_verified_kb("Can I use Confront for clover?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertFalse(result["needs_review"])
        self.assertIn("Confront", result["answer"])
        self.assertIn("1-2 pt/acre", result["answer"])

    def test_q4_plus_returns_verified_answer_for_crabgrass_on_bermudagrass(self):
        result = answer_from_verified_kb("Can I use Q4 Plus for crabgrass on bermudagrass?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertFalse(result["needs_review"])
        self.assertIn("Q4 Plus", result["answer"])
        self.assertIn("5-7 pt/acre", result["answer"])

    def test_q4_plus_is_blocked_on_bentgrass(self):
        result = answer_from_verified_kb("Can I use Q4 Plus for crabgrass on bentgrass greens?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "surface_restricted")
        self.assertTrue(result["needs_review"])
        self.assertIn("surface restriction", result["answer"].lower())

    def test_conserve_sc_returns_verified_answer_for_cutworms(self):
        result = answer_from_verified_kb("Can I use Conserve SC for cutworms?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertFalse(result["needs_review"])
        self.assertIn("Conserve SC", result["answer"])
        self.assertIn("0.8-1.2 fl oz/1000 sq ft", result["answer"])

    def test_advion_returns_verified_answer_for_fire_ants(self):
        result = answer_from_verified_kb("Can I use Advion Fire Ant Bait for fire ants?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertFalse(result["needs_review"])
        self.assertIn("Advion Fire Ant Bait", result["answer"])
        self.assertIn("1.5 lb product/acre", result["answer"])

    def test_ference_returns_verified_answer_for_abw(self):
        result = answer_from_verified_kb("Can I use Ference for annual bluegrass weevil?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertFalse(result["needs_review"])
        self.assertIn("Ference", result["answer"])
        self.assertIn("12-20 fl oz/acre", result["answer"])

    def test_provaunt_returns_verified_answer_for_cutworms(self):
        result = answer_from_verified_kb("Can I use Provaunt WDG for cutworms?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertFalse(result["needs_review"])
        self.assertIn("Provaunt WDG", result["answer"])
        self.assertIn("3-6 oz/acre", result["answer"])

    def test_katana_returns_verified_answer_for_poa_annua(self):
        result = answer_from_verified_kb("Can I use Katana for Poa annua on bermudagrass?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertFalse(result["needs_review"])
        self.assertIn("Katana", result["answer"])
        self.assertIn("2.5-3.0 oz/acre", result["answer"])
        self.assertNotIn("pre-emergent management", result["answer"])

    def test_katana_is_blocked_on_cool_season_turf(self):
        result = answer_from_verified_kb("Can I use Katana for yellow nutsedge on bentgrass greens?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "surface_restricted")
        self.assertTrue(result["needs_review"])
        self.assertIn("surface restriction", result["answer"].lower())

    def test_preemergent_answer_does_not_read_like_post_cleanup(self):
        result = answer_from_verified_kb("Can I use Gallery SC for dandelion?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertIn("pre-emergent management", result["answer"])
        self.assertNotIn("**Bottom Line:** Yes.", result["answer"])

    def test_insignia_max_annual_answer_uses_insignia_data_not_pylex(self):
        result = answer_from_verified_kb("What is the annual max for Insignia?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertIn("Insignia", result["answer"])
        self.assertIn("4.4 fl oz", result["answer"])
        self.assertNotIn("Pylex", result["answer"])

    def test_insignia_reseeding_answer_no_longer_leaks_pylex_copy(self):
        result = answer_from_verified_kb("Can I reseed after Insignia?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "not_verified")
        self.assertIn("do not have verified reseeding", result["answer"].lower())
        self.assertNotIn("Bermudagrass control program", result["answer"])

    def test_banner_reseeding_answer_no_longer_leaks_ference_copy(self):
        result = answer_from_verified_kb("Can I reseed after Banner MAXX?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "not_verified")
        self.assertIn("do not have verified reseeding", result["answer"].lower())
        self.assertNotIn("Ference", result["answer"])

    def test_26gt_reseeding_answer_no_longer_leaks_talstar_copy(self):
        result = answer_from_verified_kb("Can I reseed after 26GT?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "not_verified")
        self.assertIn("do not have verified reseeding", result["answer"].lower())
        self.assertNotIn("Talstar", result["answer"])

    def test_roundup_reseeding_answer_no_longer_leaks_arena_copy(self):
        result = answer_from_verified_kb("Can I reseed after Roundup?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "not_verified")
        self.assertIn("do not have verified reseeding", result["answer"].lower())
        self.assertNotIn("Arena", result["answer"])

    def test_sedgehammer_interval_answer_no_longer_leaks_arena_copy(self):
        result = answer_from_verified_kb("How soon can I spray Sedgehammer again?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertIn("14 days", result["answer"])
        self.assertNotIn("Arena", result["answer"])

    def test_manuscript_interval_answer_no_longer_leaks_talstar_copy(self):
        result = answer_from_verified_kb("How soon can I spray Manuscript again?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified")
        self.assertIn("14 to 21 days", result["answer"])
        self.assertNotIn("Talstar", result["answer"])

    def test_surface_target_recommendation_returns_verified_options(self):
        profile = {
            "surfaces": {
                "greens": "creeping bentgrass",
                "fairways": "kentucky bluegrass",
                "tees": "",
                "rough": "tall fescue",
            }
        }

        result = recommend_verified_products_for_surface_target(
            "What should I use for dollar spot on greens?",
            profile,
        )

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified_surface_target_options")
        self.assertFalse(result["needs_review"])
        self.assertEqual(result["surface"], "greens")
        self.assertEqual(result["turf"], "creeping bentgrass")
        self.assertIn("Daconil", result["answer"])
        self.assertIn("Verified options", result["answer"])

    def test_surface_target_recommendation_ranks_dollar_spot_options_by_resistance_fit(self):
        profile = {
            "surfaces": {
                "greens": "creeping bentgrass",
                "fairways": "",
                "tees": "",
                "rough": "",
            }
        }

        result = recommend_verified_products_for_surface_target(
            "What should I use for dollar spot on greens?",
            profile,
        )

        self.assertIsNotNone(result)
        answer = result["answer"]
        self.assertLess(answer.index("**Daconil**"), answer.index("**Concert**"))
        self.assertLess(answer.index("**Secure**"), answer.index("**Concert**"))
        self.assertLess(answer.index("**Concert**"), answer.index("**Instrata**"))
        self.assertIn("**Concert**", answer)
        self.assertIn("**Instrata**", answer)
        self.assertIn("Ranking logic", answer)

    def test_surface_target_recommendation_returns_verified_poacure_match_for_poa_trivialis(self):
        profile = {
            "surfaces": {
                "greens": "creeping bentgrass",
                "fairways": "",
                "tees": "",
                "rough": "",
            }
        }

        result = recommend_verified_products_for_surface_target(
            "What should I use for Poa trivialis on greens?",
            profile,
        )

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "verified_surface_target_options")
        self.assertFalse(result["needs_review"])
        self.assertIn("PoaCure", result["answer"])
        self.assertIn("roughstalk bluegrass", result["answer"].lower())


if __name__ == "__main__":
    unittest.main()
