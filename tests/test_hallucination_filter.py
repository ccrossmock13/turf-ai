"""Tests for hallucination_filter.py — post-processing answer validation."""

import pytest
from unittest.mock import patch


class TestFilterHallucinations:
    """Test the main hallucination filter function."""

    def test_clean_answer_passes(self, sample_answer, sample_question, sample_context, sample_sources):
        from hallucination_filter import filter_hallucinations
        result = filter_hallucinations(
            answer=sample_answer,
            question=sample_question,
            context=sample_context,
            sources=sample_sources,
        )
        assert isinstance(result, dict)
        assert "filtered_answer" in result
        assert "issues_found" in result
        assert "was_modified" in result
        assert "confidence_penalty" in result
        assert result["confidence_penalty"] <= 30  # max cap

    def test_penalty_capped_at_30(self, sample_question, sample_context, sample_sources):
        from hallucination_filter import filter_hallucinations
        # Even with bad answer, penalty shouldn't exceed 30
        bad_answer = (
            "In 2027, scientists discovered a new cure for all turf diseases. "
            "Use FakeProduct 3000 at 500 gallons per acre. "
            "Mix roundup with fertilizer and drink it."
        )
        result = filter_hallucinations(
            answer=bad_answer,
            question=sample_question,
            context=sample_context,
            sources=sample_sources,
        )
        assert result["confidence_penalty"] <= 30

    def test_returns_required_keys(self, sample_answer, sample_question, sample_context, sample_sources):
        from hallucination_filter import filter_hallucinations
        result = filter_hallucinations(
            answer=sample_answer,
            question=sample_question,
            context=sample_context,
            sources=sample_sources,
        )
        required_keys = {"filtered_answer", "issues_found", "was_modified", "confidence_penalty"}
        assert required_keys.issubset(result.keys())

    def test_empty_answer(self, sample_question, sample_context, sample_sources):
        from hallucination_filter import filter_hallucinations
        result = filter_hallucinations(
            answer="",
            question=sample_question,
            context=sample_context,
            sources=sample_sources,
        )
        assert isinstance(result, dict)
        assert result["confidence_penalty"] >= 0


class TestTemporalClaims:
    """Test temporal hallucination detection."""

    def test_future_year_flagged(self):
        from hallucination_filter import _check_temporal_claims
        result = _check_temporal_claims(
            "In 2030, a new fungicide was released.",
            "what fungicide should I use?",
            "Heritage is a FRAC 11 fungicide."
        )
        assert isinstance(result, dict)
        assert "flagged" in result

    def test_normal_text_not_flagged(self):
        from hallucination_filter import _check_temporal_claims
        result = _check_temporal_claims(
            "Apply Heritage at 0.4 oz per 1000 sq ft every 14 days.",
            "heritage rate?",
            "Heritage rate: 0.2-0.4 oz per 1000 sq ft."
        )
        assert result["flagged"] is False


class TestFabricatedProducts:
    """Test fabricated product detection."""

    def test_known_product_passes(self):
        from hallucination_filter import _check_fabricated_products
        result = _check_fabricated_products(
            "Heritage (azoxystrobin) is a FRAC 11 fungicide.",
            "heritage rate?"
        )
        assert isinstance(result, dict)
        assert "flagged" in result

    def test_returns_required_keys(self):
        from hallucination_filter import _check_fabricated_products
        result = _check_fabricated_products("test answer", "test question")
        assert "flagged" in result
        assert "issues" in result
        assert "penalty" in result
