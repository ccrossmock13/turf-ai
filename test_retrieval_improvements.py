import unittest
from unittest.mock import patch

from knowledge_base import build_context_from_knowledge
from scoring_service import assemble_context_sections, build_context, select_evidence_results
from search_service import search_all_parallel


class RetrievalImprovementTests(unittest.TestCase):
    def test_search_all_parallel_merges_multiple_general_queries_without_duplicates(self):
        query_to_results = {
            "original query": {"matches": [
                {"id": "doc-1", "score": 0.60, "metadata": {"source": "Doc 1", "text": "alpha"}},
                {"id": "doc-2", "score": 0.50, "metadata": {"source": "Doc 2", "text": "beta"}},
            ]},
            "rewritten query": {"matches": [
                {"id": "doc-1", "score": 0.90, "metadata": {"source": "Doc 1", "text": "alpha better"}},
                {"id": "doc-3", "score": 0.55, "metadata": {"source": "Doc 3", "text": "gamma"}},
            ]},
        }

        with patch("search_service.get_embedding", side_effect=lambda client, text, model: text), \
             patch("search_service.search_general", side_effect=lambda index, embedding, query_text="": query_to_results[query_text]), \
             patch("search_service.search_products", return_value={"matches": []}), \
             patch("search_service.search_timing", return_value={"matches": []}):
            results = search_all_parallel(
                index=object(),
                openai_client=object(),
                question="original query",
                expanded_query="expanded query",
                product_need=None,
                grass_type=None,
                general_queries=["original query", "rewritten query"],
            )

        merged = results["general"]["matches"]
        self.assertEqual([match["id"] for match in merged], ["doc-1", "doc-3", "doc-2"])
        self.assertEqual(merged[0]["score"], 0.90)

    def test_build_context_respects_budget_and_keeps_sources(self):
        filtered_results = [
            {
                "text": "A" * 500,
                "source": "First Source",
                "match_id": "doc-1",
                "metadata": {"type": "document"},
            },
            {
                "text": "B" * 500,
                "source": "Second Source",
                "match_id": "doc-2",
                "metadata": {"type": "document"},
            },
        ]

        with patch("search_service.find_source_url", return_value="/static/product-labels/test.pdf"):
            context, sources, images = build_context(filtered_results, ["static/product-labels"], max_chars=420)

        self.assertLessEqual(len(context), 420)
        self.assertIn("[Source 1: First Source]", context)
        self.assertTrue(sources)
        self.assertEqual(images, [])

    def test_build_context_diversifies_sources_before_taking_extra_chunks(self):
        filtered_results = [
            {"text": "A" * 120, "source": "Doc A", "match_id": "a-1", "metadata": {"type": "document"}},
            {"text": "A" * 120, "source": "Doc A", "match_id": "a-2", "metadata": {"type": "document"}},
            {"text": "A" * 120, "source": "Doc A", "match_id": "a-3", "metadata": {"type": "document"}},
            {"text": "B" * 120, "source": "Doc B", "match_id": "b-1", "metadata": {"type": "document"}},
        ]

        with patch("search_service.find_source_url", return_value="/static/product-labels/test.pdf"):
            context, sources, _ = build_context(filtered_results, ["static/product-labels"], max_results=3, max_chars=1200)

        self.assertEqual([source["name"] for source in sources], ["Doc A", "Doc A", "Doc B"])
        self.assertIn("[Source 3: Doc B]", context)

    def test_assemble_context_sections_applies_section_caps_in_order(self):
        combined = assemble_context_sections(
            [
                {"title": "ONE", "content": "A" * 200, "max_chars": 80},
                {"title": "TWO", "content": "B" * 200, "max_chars": 80},
            ],
            max_chars=140,
        )

        self.assertLessEqual(len(combined), 140)
        self.assertIn("--- ONE ---", combined)
        self.assertIn("--- TWO ---", combined)

    def test_build_context_from_knowledge_uses_question_aware_product_summary(self):
        context = build_context_from_knowledge("What is the rei and rainfast for Daconil?")

        self.assertIn('"rei"', context)
        self.assertIn('"rainfast"', context)
        self.assertNotIn('"source_audit"', context)

    def test_select_evidence_results_prefers_rate_evidence_for_rate_questions(self):
        filtered_results = [
            {
                "text": "General disease overview without label numbers.",
                "source": "Disease Overview",
                "score": 20.0,
                "match_id": "doc-1",
                "metadata": {"type": "article"},
            },
            {
                "text": "Label says apply 3.5 to 5 fl oz per 1000 sq ft. REI 12 hours. Rainfast when dry.",
                "source": "Daconil Label",
                "score": 18.0,
                "match_id": "doc-2",
                "metadata": {"type": "pesticide_label"},
            },
        ]

        selected = select_evidence_results(
            filtered_results,
            question="What is the rate and rei for Daconil?",
            question_topic="chemical",
            product_need="fungicide",
            max_results=1,
        )

        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["source"], "Daconil Label")


if __name__ == "__main__":
    unittest.main()
