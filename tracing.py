"""
Structured request tracing for Greenside AI.
Generates a unique trace_id per request and tracks timing/metadata through
every pipeline step. Outputs structured JSON log lines for observability.

Usage in app.py:
    from tracing import Trace

    trace = Trace(question=question)
    trace.step("query_rewrite", rewritten_query=rq)
    trace.step("vector_search", result_count=len(matches))
    ...
    trace.finish(confidence=85, source_count=3)
    # Automatically logs the full trace as structured JSON
"""

import json
import logging
import time
import uuid
from typing import Any, Dict, Optional

logger = logging.getLogger("greenside.trace")


class Trace:
    """Structured trace for a single /ask request."""

    def __init__(self, question: str, user_id: Optional[int] = None, session_id: Optional[str] = None):
        self.trace_id = uuid.uuid4().hex[:12]
        self.question = question[:200]  # truncate for logging
        self.user_id = user_id
        self.session_id = session_id
        self.start_time = time.time()
        self.steps = []
        self._step_start = self.start_time
        self.metadata = {}

        logger.info(f"[{self.trace_id}] START | q=\"{self.question[:80]}\" | user={user_id}")

    def step(self, name: str, **kwargs):
        """Record a pipeline step with timing and optional metadata."""
        now = time.time()
        elapsed_ms = round((now - self._step_start) * 1000)
        total_ms = round((now - self.start_time) * 1000)

        step_data = {
            "name": name,
            "elapsed_ms": elapsed_ms,
            "total_ms": total_ms,
        }
        if kwargs:
            step_data["data"] = {k: _safe_serialize(v) for k, v in kwargs.items()}

        self.steps.append(step_data)
        self._step_start = now

        # Log each step in real-time for debugging
        data_str = ""
        if kwargs:
            data_str = " | " + " ".join(f"{k}={_safe_serialize(v)}" for k, v in kwargs.items())
        logger.debug(f"[{self.trace_id}] {name} ({elapsed_ms}ms){data_str}")

    def set(self, key: str, value: Any):
        """Set metadata on the trace."""
        self.metadata[key] = _safe_serialize(value)

    def finish(self, **kwargs):
        """Complete the trace and log the full structured record."""
        total_ms = round((time.time() - self.start_time) * 1000)

        record = {
            "trace_id": self.trace_id,
            "question": self.question,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "total_ms": total_ms,
            "step_count": len(self.steps),
            "steps": self.steps,
            "metadata": {**self.metadata, **{k: _safe_serialize(v) for k, v in kwargs.items()}},
        }

        # Log summary line
        step_names = " → ".join(s["name"] for s in self.steps)
        confidence = kwargs.get("confidence", "?")
        source_count = kwargs.get("source_count", "?")
        logger.info(
            f"[{self.trace_id}] DONE {total_ms}ms | "
            f"confidence={confidence} sources={source_count} | "
            f"{step_names}"
        )

        # Log full structured record at DEBUG level
        logger.debug(f"[{self.trace_id}] TRACE_RECORD: {json.dumps(record, default=str)}")

        return record

    def to_dict(self) -> Dict:
        """Return trace as dict (for API responses or testing)."""
        return {
            "trace_id": self.trace_id,
            "total_ms": round((time.time() - self.start_time) * 1000),
            "steps": self.steps,
            "metadata": self.metadata,
        }


def _safe_serialize(value: Any) -> Any:
    """Safely serialize a value for logging — truncate large strings, summarize lists."""
    if isinstance(value, str):
        return value[:200] if len(value) > 200 else value
    if isinstance(value, (list, tuple)):
        return f"[{len(value)} items]" if len(value) > 5 else value
    if isinstance(value, dict):
        return f"{{{len(value)} keys}}" if len(value) > 5 else value
    if isinstance(value, (int, float, bool, type(None))):
        return value
    return str(value)[:100]
