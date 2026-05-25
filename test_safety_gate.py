import unittest

from safety_gate import apply_post_llm_safety_gate, get_pre_llm_safety_response


class SafetyGateTests(unittest.TestCase):
    def test_pre_llm_blocks_tank_mix_question(self):
        result = get_pre_llm_safety_response("Can I tank mix Daconil and Heritage for dollar spot?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "safety_blocked")
        self.assertEqual(result["confidence"]["label"], "Need Verified Support")
        self.assertIn("tank-mix", result["answer"].lower())

    def test_pre_llm_blocks_rate_question_without_enough_context(self):
        result = get_pre_llm_safety_response("What rate of Daconil should I use?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "safety_blocked")
        self.assertIn("do not have enough context", result["answer"].lower())
        self.assertIn("target, surface, and turf", result["answer"].lower())

    def test_pre_llm_blocks_diagnosis_confirmation(self):
        result = get_pre_llm_safety_response("This is definitely pythium right?")

        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "safety_blocked")
        self.assertEqual(result["confidence"]["label"], "Needs Field Confirmation")
        self.assertIn("should not confirm", result["answer"].lower())

    def test_pre_llm_does_not_block_comparative_differential_question(self):
        result = get_pre_llm_safety_response("Is this water or disease?")

        self.assertIsNone(result)

    def test_post_llm_blocks_high_risk_low_confidence_answer(self):
        blocked = apply_post_llm_safety_gate(
            "Can I tank mix Daconil and Heritage?",
            {
                "answer": "Yes, probably.",
                "confidence": {"score": 62, "label": "Low"},
                "needs_review": True,
                "grounding": {"verified": False, "issues": ["unsupported claim"]},
                "sources": [],
            },
        )

        self.assertEqual(blocked["kb_verdict"], "safety_blocked")
        self.assertEqual(blocked["confidence"]["label"], "Need Verified Support")


if __name__ == "__main__":
    unittest.main()
