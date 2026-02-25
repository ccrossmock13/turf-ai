"""Tests for query_expansion.py — synonym expansion, vague question handling."""

import pytest
from query_expansion import expand_query, expand_vague_question, extract_keywords, get_query_intent


# ── Query Expansion ──

class TestExpandQuery:
    def test_heritage_expands(self):
        result = expand_query("heritage rate for greens")
        assert "azoxystrobin" in result
        assert "heritage" in result

    def test_barricade_expands(self):
        result = expand_query("barricade application timing")
        assert "prodiamine" in result
        assert "pre-emergent" in result

    def test_primo_expands(self):
        result = expand_query("primo rate for fairways")
        assert "trinexapac" in result
        assert "PGR" in result or "pgr" in result.lower()

    def test_tenacity_expands(self):
        result = expand_query("tenacity for poa trivialis")
        assert "mesotrione" in result

    def test_no_match_unchanged(self):
        result = expand_query("how do I fix my drainage")
        assert "drainage" in result

    def test_multiple_expansions(self):
        result = expand_query("tank mix heritage and daconil")
        assert "azoxystrobin" in result
        assert "chlorothalonil" in result

    def test_case_insensitive(self):
        result = expand_query("Heritage Rate")
        assert "azoxystrobin" in result

    def test_acelepryn(self):
        result = expand_query("acelepryn for grubs")
        assert "chlorantraniliprole" in result


# ── Vague Question Expansion ──

class TestExpandVagueQuestion:
    def test_dollar_spot_question_mark(self):
        result = expand_vague_question("dollar spot?")
        assert len(result) > len("dollar spot?")
        assert "fungicide" in result.lower() or "control" in result.lower()

    def test_crabgrass_question(self):
        result = expand_vague_question("crabgrass?")
        assert len(result) > len("crabgrass?")

    def test_already_specific(self):
        long_q = "What fungicide should I use to control dollar spot on bentgrass greens at 0.125 inch?"
        result = expand_vague_question(long_q)
        # Should return something (may or may not expand)
        assert len(result) > 0

    def test_empty_string(self):
        result = expand_vague_question("")
        assert result == ""


# ── Keyword Extraction ──

class TestExtractKeywords:
    def test_removes_stop_words(self):
        keywords = extract_keywords("what is the best fungicide for dollar spot")
        assert "what" not in keywords
        assert "is" not in keywords
        assert "the" not in keywords
        assert "fungicide" in keywords
        assert "dollar" in keywords

    def test_short_words_removed(self):
        keywords = extract_keywords("do I use it on my lawn")
        assert "do" not in keywords
        assert "on" not in keywords
        assert "my" not in keywords

    def test_preserves_important_words(self):
        keywords = extract_keywords("heritage fungicide application rate bentgrass")
        assert "heritage" in keywords
        assert "fungicide" in keywords
        assert "bentgrass" in keywords


# ── Query Intent ──

class TestGetQueryIntent:
    def test_rate_intent(self):
        result = get_query_intent("what is the Heritage rate per 1000 sq ft?")
        assert result["wants_rate"] is True

    def test_chemical_intent(self):
        result = get_query_intent("what fungicide for dollar spot?")
        assert result["wants_chemical"] is True

    def test_cultural_intent(self):
        result = get_query_intent("when to aerify bentgrass greens?")
        assert result["wants_cultural"] is True

    def test_diagnosis_intent(self):
        result = get_query_intent("what's wrong with my grass, it's dying?")
        assert result["wants_diagnosis"] is True

    def test_product_mentioned(self):
        result = get_query_intent("can I spray Heritage on bermuda?")
        assert result["product_mentioned"] is not None

    def test_disease_mentioned(self):
        result = get_query_intent("dollar spot treatment options")
        assert result["disease_mentioned"] is not None
