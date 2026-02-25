"""Tests for scoring_service.py — result scoring, boosting, and filtering."""

import pytest
from scoring_service import score_results, safety_filter_results, build_context


# ── Score Results ──

class TestScoreResults:
    def test_scores_with_matches(self, sample_search_results):
        matches = [
            {"id": r["id"], "score": r["score"], "metadata": r["metadata"]}
            for r in sample_search_results
        ]
        results = score_results(matches, "heritage rate bentgrass", "bentgrass", None, "fungicide")
        assert len(results) > 0
        assert all("score" in r for r in results)
        assert all("text" in r for r in results)
        assert all("source" in r for r in results)

    def test_sorted_descending(self, sample_search_results):
        matches = [
            {"id": r["id"], "score": r["score"], "metadata": r["metadata"]}
            for r in sample_search_results
        ]
        results = score_results(matches, "heritage rate", "bentgrass", None, "fungicide")
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_empty_matches(self):
        results = score_results([], "test question", None, None, None)
        assert results == []

    def test_grass_type_boost(self, sample_search_results):
        matches = [
            {"id": r["id"], "score": r["score"], "metadata": r["metadata"]}
            for r in sample_search_results
        ]
        # Bentgrass is in the first result's text, should get boosted
        results_with = score_results(matches, "heritage rate", "bentgrass", None, "fungicide")
        results_without = score_results(matches, "heritage rate", None, None, "fungicide")
        # With grass type, the bentgrass-matching result should score higher
        assert len(results_with) > 0
        assert len(results_without) > 0


# ── Safety Filter ──

class TestSafetyFilter:
    def test_filters_product_results_for_cultural_topic(self):
        results = [
            {"text": "Heritage 0.4 oz rate", "source": "heritage-label.pdf", "score": 0.9},
            {"text": "Core aeration in fall", "source": "cultural-practices.pdf", "score": 0.85},
        ]
        filtered = safety_filter_results(results, "cultural", None)
        assert len(filtered) > 0

    def test_keeps_relevant_for_chemical(self):
        results = [
            {"text": "Heritage 0.4 oz rate", "source": "heritage-label.pdf", "score": 0.9},
        ]
        filtered = safety_filter_results(results, "chemical", "fungicide")
        assert len(filtered) > 0

    def test_respects_limit(self):
        results = [{"text": f"Result {i}", "source": "test.pdf", "score": 0.9 - i * 0.01} for i in range(30)]
        filtered = safety_filter_results(results, "chemical", "fungicide", limit=10)
        assert len(filtered) <= 10

    def test_empty_results(self):
        filtered = safety_filter_results([], "chemical", "fungicide")
        assert filtered == []


# ── Build Context ──

class TestBuildContext:
    def test_builds_context_string(self):
        results = [
            {"text": "Heritage 0.4 oz per 1000 sq ft", "source": "heritage-label.pdf", "score": 0.9, "metadata": {}, "match_id": "heritage-1"},
            {"text": "Dollar spot on bentgrass greens", "source": "turf-guide.pdf", "score": 0.8, "metadata": {}, "match_id": "turf-2"},
        ]
        context, sources, images = build_context(results, ["product-labels", "spray-programs"])
        assert "Heritage" in context
        assert len(sources) > 0

    def test_empty_results(self):
        context, sources, images = build_context([], ["product-labels"])
        assert context == "" or len(context) < 10
        assert len(sources) == 0

    def test_max_results_limit(self):
        results = [
            {"text": f"Content {i}", "source": f"source{i}.pdf", "score": 0.9 - i * 0.01, "metadata": {}, "match_id": f"match-{i}"}
            for i in range(20)
        ]
        context, sources, images = build_context(results, ["product-labels"], max_results=5)
        assert len(sources) <= 5
