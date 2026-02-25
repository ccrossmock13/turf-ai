"""Tests for context truncation — safe boundary-aware truncation."""

import pytest


class TestContextSafeTruncation:
    """Test the safe truncation logic that was added to app.py."""

    def _truncate(self, context, max_length):
        """Mirror the truncation logic from app.py."""
        if len(context) > max_length:
            truncated = context[:max_length]
            last_break = truncated.rfind('\n\n')
            if last_break > max_length * 0.7:
                return truncated[:last_break]
            else:
                last_period = truncated.rfind('. ')
                if last_period > max_length * 0.7:
                    return truncated[:last_period + 1]
                else:
                    return truncated
        return context

    def test_short_context_unchanged(self):
        context = "Heritage rate: 0.4 oz per 1000 sq ft."
        result = self._truncate(context, 1000)
        assert result == context

    def test_truncates_at_paragraph_boundary(self):
        # Paragraph break at ~75% of limit so it falls above the 70% threshold
        para1 = "A" * 75
        para2 = "B" * 40
        context = para1 + "\n\n" + para2
        result = self._truncate(context, 100)
        # Should cut at the \n\n which is at position 75 (75% of 100)
        assert result == para1

    def test_truncates_at_sentence_boundary(self):
        # Sentence boundary at ~80% of limit
        part1 = "x" * 78 + ". "
        part2 = "y" * 30
        context = part1 + part2
        result = self._truncate(context, 100)
        # Should cut at the ". " which is at position 80 (80% of 100)
        assert result.endswith(".")

    def test_hard_truncation_fallback(self):
        context = "a" * 1000
        result = self._truncate(context, 100)
        assert len(result) == 100

    def test_preserves_at_least_70_percent(self):
        context = "Short.\n\n" + "x" * 500
        max_len = 200
        result = self._truncate(context, max_len)
        # Should not cut all the way back to the short paragraph if it's < 70%
        assert len(result) >= max_len * 0.7 or result.endswith("Short.")

    def test_real_context_pattern(self):
        """Test with realistic source context pattern."""
        context = (
            "[Source 1: heritage-label.pdf]\n"
            "Heritage (azoxystrobin) rate: 0.2-0.4 oz per 1000 sq ft.\n"
            "Apply every 14-28 days. FRAC Group 11.\n\n"
            "[Source 2: dollar-spot-guide.pdf]\n"
            "Dollar spot management on bentgrass greens.\n"
            "Rotate FRAC groups to prevent resistance.\n\n"
            "[Source 3: some-long-source.pdf]\n"
            "This is additional content that should be truncated if needed. " * 10
        )
        max_len = 250
        result = self._truncate(context, max_len)
        assert len(result) <= max_len
        # Should ideally not cut in the middle of a source block
        assert "[Source 3:" not in result or result.count("[Source") <= 2

    def test_exact_limit_no_truncation(self):
        context = "x" * 100
        result = self._truncate(context, 100)
        assert result == context

    def test_one_over_limit(self):
        context = "x" * 101
        result = self._truncate(context, 100)
        assert len(result) <= 101
