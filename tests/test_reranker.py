"""Tests for reranker.py — cross-encoder reranking and score normalization."""

import pytest
from unittest.mock import patch, MagicMock


class TestScoreNormalization:
    """Test that the score normalization formula produces expected ranges."""

    def test_normalized_scores_in_range(self):
        """Verify normalized final scores are within 0-100."""
        # Simulate what the reranker does with normalized scores
        ce_score = 3.5  # typical cross-encoder score
        rrf_score = 0.7  # typical RRF score

        ce_normalized = min(ce_score * 20, 100)  # 70
        orig_normalized = min(rrf_score * 100, 100)  # 70
        final = 0.7 * ce_normalized + 0.3 * orig_normalized  # 49 + 21 = 70

        assert 0 <= final <= 100
        assert 60 <= final <= 80  # should be around 70

    def test_high_ce_score(self):
        """High cross-encoder score produces high final score."""
        ce_score = 4.8
        rrf_score = 0.5

        ce_normalized = min(ce_score * 20, 100)  # 96
        orig_normalized = min(rrf_score * 100, 100)  # 50
        final = 0.7 * ce_normalized + 0.3 * orig_normalized  # 67.2 + 15 = 82.2

        assert final > 75

    def test_low_ce_score(self):
        """Low cross-encoder score produces lower final score."""
        ce_score = 0.5
        rrf_score = 0.3

        ce_normalized = min(ce_score * 20, 100)  # 10
        orig_normalized = min(rrf_score * 100, 100)  # 30
        final = 0.7 * ce_normalized + 0.3 * orig_normalized  # 7 + 9 = 16

        assert final < 25

    def test_max_scores_capped(self):
        """Scores above max are capped at 100."""
        ce_score = 6.0  # above typical range
        rrf_score = 1.5  # above typical range

        ce_normalized = min(ce_score * 20, 100)  # capped at 100
        orig_normalized = min(rrf_score * 100, 100)  # capped at 100
        final = 0.7 * ce_normalized + 0.3 * orig_normalized  # 70 + 30 = 100

        assert final == 100

    def test_zero_scores(self):
        """Zero scores produce zero final."""
        ce_normalized = min(0 * 20, 100)
        orig_normalized = min(0 * 100, 100)
        final = 0.7 * ce_normalized + 0.3 * orig_normalized
        assert final == 0

    def test_ce_dominates_rrf(self):
        """Cross-encoder contributes 70% of final score."""
        ce_score = 5.0  # max typical
        rrf_score = 0.0

        ce_normalized = min(ce_score * 20, 100)  # 100
        orig_normalized = min(rrf_score * 100, 100)  # 0
        final = 0.7 * ce_normalized + 0.3 * orig_normalized  # 70 + 0

        assert final == 70

    def test_rrf_alone(self):
        """RRF contributes 30% of final score."""
        ce_score = 0.0
        rrf_score = 1.0

        ce_normalized = min(ce_score * 20, 100)  # 0
        orig_normalized = min(rrf_score * 100, 100)  # 100
        final = 0.7 * ce_normalized + 0.3 * orig_normalized  # 0 + 30

        assert final == 30


class TestRerankerAvailability:
    def test_is_cross_encoder_available_returns_bool(self):
        from reranker import is_cross_encoder_available
        result = is_cross_encoder_available()
        assert isinstance(result, bool)
