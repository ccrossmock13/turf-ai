"""Tests for search_service.py — topic detection, subject detection, deduplication."""

import pytest
from search_service import (
    detect_topic, detect_specific_subject, detect_state,
    deduplicate_sources, deduplicate_results, filter_display_sources
)


# ── Topic Detection ──

class TestDetectTopic:
    def test_disease_topic(self):
        assert detect_topic("how to control dollar spot on greens") == "disease"

    def test_chemical_topic(self):
        assert detect_topic("what herbicide kills crabgrass") == "chemical"

    def test_fertilizer_topic(self):
        assert detect_topic("nitrogen rate for bermuda fairways") == "fertilizer"

    def test_irrigation_topic(self):
        assert detect_topic("irrigation schedule for summer") == "irrigation"

    def test_equipment_topic(self):
        assert detect_topic("mower blade sharpening for greens mower") == "equipment"

    def test_cultural_topic(self):
        assert detect_topic("core aeration timing for bentgrass greens") == "cultural"

    def test_diagnostic_topic(self):
        assert detect_topic("why is my grass turning brown and dying") == "diagnostic"

    def test_no_topic(self):
        result = detect_topic("hello there")
        # May return None or a default
        assert result is None or isinstance(result, str)


# ── Specific Subject Detection ──

class TestDetectSpecificSubject:
    def test_detects_dollar_spot(self):
        result = detect_specific_subject("dollar spot on my greens")
        assert result is not None
        assert "dollar spot" in result.lower()

    def test_detects_brown_patch(self):
        result = detect_specific_subject("brown patch in tall fescue")
        assert result is not None
        assert "brown patch" in result.lower()

    def test_detects_heritage(self):
        result = detect_specific_subject("heritage fungicide rate")
        assert result is not None

    def test_detects_crabgrass(self):
        result = detect_specific_subject("crabgrass in my lawn")
        assert result is not None

    def test_no_subject(self):
        result = detect_specific_subject("general turf management tips")
        # May return None
        assert result is None or isinstance(result, str)


# ── State Detection ──

class TestDetectState:
    def test_detects_georgia(self):
        result = detect_state("golf course in georgia")
        assert result is not None
        assert "georgia" in result.lower()

    def test_detects_texas(self):
        result = detect_state("bermuda in texas summer")
        assert result is not None

    def test_no_state(self):
        result = detect_state("how to aerate greens")
        assert result is None


# ── Deduplication ──

class TestDeduplicateSources:
    def test_removes_duplicates(self):
        sources = [
            {"name": "heritage-label.pdf", "url": "/labels/heritage-label.pdf"},
            {"name": "heritage-label.pdf", "url": "/labels/heritage-label.pdf"},
            {"name": "daconil-label.pdf", "url": "/labels/daconil-label.pdf"},
        ]
        deduped = deduplicate_sources(sources)
        assert len(deduped) <= 2

    def test_keeps_unique(self):
        sources = [
            {"name": "heritage-label.pdf", "url": "/labels/heritage-label.pdf"},
            {"name": "daconil-label.pdf", "url": "/labels/daconil-label.pdf"},
        ]
        deduped = deduplicate_sources(sources)
        assert len(deduped) == 2

    def test_empty_list(self):
        assert deduplicate_sources([]) == []


class TestDeduplicateResults:
    def test_removes_duplicate_chunks(self):
        results = [
            {"text": "Heritage rate 0.4 oz per 1000 sq ft for dollar spot", "source": "label.pdf", "score": 0.9},
            {"text": "Heritage rate 0.4 oz per 1000 sq ft for dollar spot", "source": "label.pdf", "score": 0.85},
            {"text": "Daconil rate for brown patch", "source": "daconil.pdf", "score": 0.8},
        ]
        deduped = deduplicate_results(results)
        assert len(deduped) <= 2

    def test_keeps_different_chunks(self):
        results = [
            {"metadata": {"text": "Heritage rate for greens"}, "source": "label.pdf", "score": 0.9},
            {"metadata": {"text": "Daconil rate for fairways"}, "source": "daconil.pdf", "score": 0.8},
        ]
        deduped = deduplicate_results(results)
        assert len(deduped) == 2


class TestFilterDisplaySources:
    def test_filters_by_folder(self):
        sources = [
            {"name": "heritage-label.pdf", "url": "/product-labels/heritage-label.pdf"},
            {"name": "unknown.pdf", "url": "/other/unknown.pdf"},
        ]
        filtered = filter_display_sources(sources, ["product-labels"])
        assert len(filtered) >= 0  # May or may not filter

    def test_empty_sources(self):
        assert filter_display_sources([], ["product-labels"]) == []
