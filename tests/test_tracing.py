"""Tests for tracing.py — structured request tracing."""

import pytest
import time
from tracing import Trace, _safe_serialize


class TestTrace:
    def test_trace_creates_id(self):
        trace = Trace(question="test question")
        assert isinstance(trace.trace_id, str)
        assert len(trace.trace_id) == 12

    def test_unique_trace_ids(self):
        t1 = Trace(question="q1")
        t2 = Trace(question="q2")
        assert t1.trace_id != t2.trace_id

    def test_step_records(self):
        trace = Trace(question="test")
        trace.step("classify", category="chemical")
        trace.step("search", result_count=15)
        assert len(trace.steps) == 2
        assert trace.steps[0]["name"] == "classify"
        assert trace.steps[1]["name"] == "search"

    def test_step_timing(self):
        trace = Trace(question="test")
        time.sleep(0.01)  # small delay
        trace.step("step1")
        assert trace.steps[0]["elapsed_ms"] >= 5  # at least 5ms

    def test_step_data(self):
        trace = Trace(question="test")
        trace.step("detect", topic="disease", grass="bentgrass")
        assert trace.steps[0]["data"]["topic"] == "disease"
        assert trace.steps[0]["data"]["grass"] == "bentgrass"

    def test_set_metadata(self):
        trace = Trace(question="test")
        trace.set("model", "gpt-4o")
        assert trace.metadata["model"] == "gpt-4o"

    def test_finish_returns_record(self):
        trace = Trace(question="heritage rate?", user_id=1)
        trace.step("classify", category="chemical")
        trace.step("search", count=10)
        record = trace.finish(confidence=85, source_count=3)
        assert record["trace_id"] == trace.trace_id
        assert record["question"] == "heritage rate?"
        assert record["user_id"] == 1
        assert record["step_count"] == 2
        assert record["total_ms"] >= 0
        assert record["metadata"]["confidence"] == 85
        assert record["metadata"]["source_count"] == 3

    def test_to_dict(self):
        trace = Trace(question="test")
        trace.step("step1")
        d = trace.to_dict()
        assert "trace_id" in d
        assert "steps" in d
        assert "total_ms" in d

    def test_question_truncated(self):
        long_q = "x" * 500
        trace = Trace(question=long_q)
        assert len(trace.question) == 200


class TestSafeSerialize:
    def test_short_string(self):
        assert _safe_serialize("hello") == "hello"

    def test_long_string_truncated(self):
        result = _safe_serialize("x" * 500)
        assert len(result) == 200

    def test_small_list(self):
        assert _safe_serialize([1, 2, 3]) == [1, 2, 3]

    def test_large_list_summarized(self):
        result = _safe_serialize(list(range(20)))
        assert result == "[20 items]"

    def test_small_dict(self):
        result = _safe_serialize({"a": 1, "b": 2})
        assert result == {"a": 1, "b": 2}

    def test_large_dict_summarized(self):
        result = _safe_serialize({str(i): i for i in range(10)})
        assert result == "{10 keys}"

    def test_numbers(self):
        assert _safe_serialize(42) == 42
        assert _safe_serialize(3.14) == 3.14

    def test_bool(self):
        assert _safe_serialize(True) is True

    def test_none(self):
        assert _safe_serialize(None) is None
