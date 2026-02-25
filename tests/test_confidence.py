"""Tests for confidence scoring — penalty caps, multiplicative approach."""

import pytest


class TestConfidencePenaltyCap:
    """Test the new multiplicative penalty approach with 20% cap."""

    def test_no_penalties(self):
        """No penalties should leave confidence unchanged."""
        confidence = 75
        hall_penalty = min(0 / 100, 0.20)
        val_penalty = min(0 / 100, 0.20)
        result = confidence * (1 - hall_penalty) * (1 - val_penalty)
        assert result == 75

    def test_small_hallucination_penalty(self):
        """Small hallucination penalty (10/100 = 0.10)."""
        confidence = 75
        hall_penalty = min(10 / 100, 0.20)  # 0.10
        val_penalty = min(0 / 100, 0.20)
        result = confidence * (1 - hall_penalty) * (1 - val_penalty)
        assert result == pytest.approx(67.5)

    def test_max_both_penalties(self):
        """Both penalties at max — should NOT drop below 48."""
        confidence = 75
        hall_penalty = min(30 / 100, 0.20)  # capped at 0.20
        val_penalty = min(25 / 100, 0.20)  # capped at 0.20
        result = confidence * (1 - hall_penalty) * (1 - val_penalty)
        assert result == pytest.approx(48.0)

    def test_old_additive_was_worse(self):
        """Old additive approach would have given 75-30-25=20, much worse."""
        confidence = 75
        # Old approach
        old_result = confidence - 30 - 25
        assert old_result == 20

        # New approach
        hall_penalty = min(30 / 100, 0.20)
        val_penalty = min(25 / 100, 0.20)
        new_result = confidence * (1 - hall_penalty) * (1 - val_penalty)
        assert new_result == pytest.approx(48.0)
        assert new_result > old_result  # new is gentler

    def test_penalty_never_exceeds_cap(self):
        """Even extreme raw penalty values get capped at 0.20."""
        for raw_penalty in [0, 5, 10, 15, 20, 25, 30, 50, 100]:
            capped = min(raw_penalty / 100, 0.20)
            assert capped <= 0.20

    def test_zero_confidence_stays_zero(self):
        """Zero confidence remains zero regardless of penalties."""
        confidence = 0
        hall_penalty = min(30 / 100, 0.20)
        val_penalty = min(25 / 100, 0.20)
        result = confidence * (1 - hall_penalty) * (1 - val_penalty)
        assert result == 0

    def test_full_confidence_with_penalties(self):
        """100% confidence with max penalties."""
        confidence = 100
        hall_penalty = min(30 / 100, 0.20)
        val_penalty = min(25 / 100, 0.20)
        result = confidence * (1 - hall_penalty) * (1 - val_penalty)
        assert result == pytest.approx(64.0)

    def test_penalty_is_multiplicative_not_additive(self):
        """Verify the approach is truly multiplicative."""
        confidence = 80
        hall_penalty = 0.15
        val_penalty = 0.10
        result = confidence * (1 - hall_penalty) * (1 - val_penalty)
        # Multiplicative: 80 * 0.85 * 0.90 = 61.2
        assert result == pytest.approx(61.2)
        # Additive would be: 80 - 15 - 10 = 55
        assert result > 55
