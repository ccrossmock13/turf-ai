import unittest
from unittest.mock import patch

from image_diagnosis import answer_image_diagnosis, validate_image_attachment


SMALL_PNG_DATA_URL = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wn7XWQAAAAASUVORK5CYII="
)


class _FakeResponse:
    def __init__(self, content):
        self.choices = [type("Choice", (), {"message": type("Message", (), {"content": content})()})()]


class _FakeClient:
    def __init__(self, payload):
        self._payload = payload
        self.chat = type("Chat", (), {"completions": self})()

    def create(self, **kwargs):
        return _FakeResponse(self._payload)


class ImageDiagnosisTests(unittest.TestCase):
    def test_validate_image_attachment_rejects_invalid_payload(self):
        result = validate_image_attachment({"data_url": "not-an-image"}, max_bytes=1024)
        self.assertFalse(result["ok"])
        self.assertIn("PNG", result["error"])

    def test_validate_image_attachment_accepts_small_png(self):
        result = validate_image_attachment(
            {"data_url": SMALL_PNG_DATA_URL, "name": "leaf.png"},
            max_bytes=1024 * 1024,
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["attachment"]["mime_type"], "image/png")
        self.assertEqual(result["attachment"]["name"], "leaf.png")

    def test_answer_image_diagnosis_wraps_deterministic_diagnosis(self):
        fake_client = _FakeClient(
            '{"turf_related": true, "image_type": "leaf_closeup", '
            '"observed_clues": ["frayed leaf tips", "torn leaf tissue"], '
            '"diagnostic_signals": ["frayed leaf tips", "after mowing"], '
            '"field_checks": ["Inspect reel and bedknife setup."], '
            '"limitations": ["Photo alone cannot confirm disease."], '
            '"confidence_note": "The image is more consistent with mechanical injury than a foliar lesion pattern."}'
        )
        attachment = {"data_url": SMALL_PNG_DATA_URL, "name": "leaf.png"}
        base_response = {
            "answer": "**Bottom Line:** Treat this as a differential diagnosis.",
            "sources": [{"name": "Greenside Advanced Diagnosis Mode", "type": "structured_kb"}],
            "confidence": {"score": 91, "label": "Advanced Diagnosis"},
            "needs_review": False,
            "kb_verdict": "advanced_diagnosis",
            "diagnostic_buckets": ["Cut quality / leaf shredding issue"],
            "advanced_science_topics": ["mower_sharpness_leaf_shredding_disease_mimic_model"],
            "grounding": {"verified": True, "issues": []},
        }
        with patch("image_diagnosis.answer_advanced_diagnosis", return_value=base_response):
            result = answer_image_diagnosis(
                "Does this look like mower injury?",
                attachment,
                {"surfaces": {"greens": "creeping bentgrass"}},
                fake_client,
            )
        self.assertIsNotNone(result)
        self.assertEqual(result["kb_verdict"], "image_diagnosis")
        self.assertEqual(result["confidence"]["label"], "Image-Supported Diagnosis")
        self.assertIn("Image Intake", result["answer"])
        self.assertIn("Visible Clues", result["answer"])
        self.assertEqual(result["image_diagnosis"]["image_type"], "leaf closeup")

    def test_image_signal_mapping_can_push_pattern_phrasing_into_diagnosis(self):
        fake_client = _FakeClient(
            '{"turf_related": true, "image_type": "before_and_after_comparison", '
            '"observed_clues": ["lack of uniformity in cut", "visible mowing patterns", "differences in grass height"], '
            '"diagnostic_signals": [], '
            '"field_checks": ["Compare mower setup across units."], '
            '"limitations": ["A photo alone cannot confirm the root cause."], '
            '"confidence_note": "The photo suggests a repeatable mechanical pattern."}'
        )
        attachment = {"data_url": SMALL_PNG_DATA_URL, "name": "pattern.jpg"}
        captured = {}

        def _fake_diag(question, profile):
            captured["question"] = question
            return {
                "answer": "**Bottom Line:** Treat this as a differential diagnosis.",
                "sources": [{"name": "Greenside Advanced Diagnosis Mode", "type": "structured_kb"}],
                "confidence": {"score": 91, "label": "Advanced Diagnosis"},
                "needs_review": False,
                "kb_verdict": "advanced_diagnosis",
                "diagnostic_buckets": ["Application pattern / coverage issue"],
                "advanced_science_topics": ["sprayer_coverage_nozzle_pressure_canopy_deposition"],
                "grounding": {"verified": True, "issues": []},
            }

        with patch("image_diagnosis.answer_advanced_diagnosis", side_effect=_fake_diag):
            result = answer_image_diagnosis(
                "What does this fairway pattern suggest about cut quality or mower setup?",
                attachment,
                {"surfaces": {"fairways": "zoysiagrass"}},
                fake_client,
            )

        self.assertIn("application pattern", captured["question"].lower())
        self.assertIn("mowing uniformity", captured["question"].lower())
        self.assertEqual(result["kb_verdict"], "image_diagnosis")

    def test_image_signal_mapping_can_push_herbicide_bleaching_phrasing_into_diagnosis(self):
        fake_client = _FakeClient(
            '{"turf_related": true, "image_type": "field_image", '
            '"observed_clues": ["discoloration in patches", "light-colored areas among green turf"], '
            '"diagnostic_signals": [], '
            '"field_checks": ["Review recent herbicide use and overlap patterns."], '
            '"limitations": ["A photo alone cannot confirm the cause."], '
            '"confidence_note": "The image suggests a patchy discoloration pattern that needs field confirmation."}'
        )
        attachment = {"data_url": SMALL_PNG_DATA_URL, "name": "bleaching.jpg"}
        captured = {}

        def _fake_diag(question, profile):
            captured["question"] = question
            return {
                "answer": "**Bottom Line:** Treat this as a differential diagnosis.",
                "sources": [{"name": "Greenside Advanced Diagnosis Mode", "type": "structured_kb"}],
                "confidence": {"score": 91, "label": "Advanced Diagnosis"},
                "needs_review": False,
                "kb_verdict": "advanced_diagnosis",
                "diagnostic_buckets": ["Herbicide carryover / establishment failure"],
                "advanced_science_topics": ["herbicide_mode_of_action_injury_patterns"],
                "grounding": {"verified": True, "issues": []},
            }

        with patch("image_diagnosis.answer_advanced_diagnosis", side_effect=_fake_diag):
            result = answer_image_diagnosis(
                "Does this look more like herbicide bleaching or a turf disease?",
                attachment,
                {"surfaces": {"fairways": "kentucky bluegrass"}},
                fake_client,
            )

        lowered = captured["question"].lower()
        self.assertIn("herbicide injury pattern", lowered)
        self.assertIn("pigment inhibitor herbicide injury", lowered)
        self.assertEqual(result["kb_verdict"], "image_diagnosis")

    def test_image_response_adds_herbicide_caution_when_base_answer_misses_it(self):
        fake_client = _FakeClient(
            '{"turf_related": true, "image_type": "field_image", '
            '"observed_clues": ["discoloration in patches", "light-colored areas among green turf"], '
            '"diagnostic_signals": [], '
            '"field_checks": ["Review recent herbicide use."], '
            '"limitations": ["A photo alone cannot confirm the cause."], '
            '"confidence_note": "Potential bleaching pattern; field confirmation still needed."}'
        )
        attachment = {"data_url": SMALL_PNG_DATA_URL, "name": "bleaching.jpg"}
        base_response = {
            "answer": "**Bottom Line:** Start by checking application pattern and deposition quality.",
            "sources": [{"name": "Greenside Advanced Turf Science", "type": "structured_kb"}],
            "confidence": {"score": 90, "label": "Advanced Turf Science"},
            "needs_review": False,
            "kb_verdict": "advanced_turf_science",
            "diagnostic_buckets": [],
            "advanced_science_topics": ["sprayer_coverage_nozzle_pressure_canopy_deposition"],
            "grounding": {"verified": True, "issues": []},
        }

        with patch("image_diagnosis.answer_advanced_diagnosis", return_value=base_response):
            result = answer_image_diagnosis(
                "Does this look more like herbicide bleaching or a turf disease?",
                attachment,
                {"surfaces": {"fairways": "kentucky bluegrass"}},
                fake_client,
            )

        self.assertIn("Image-Specific Caution", result["answer"])
        self.assertIn("herbicide bleaching", result["answer"].lower())
