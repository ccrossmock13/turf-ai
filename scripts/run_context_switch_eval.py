#!/usr/bin/env python3
"""Run a conversation-level context switch eval through /ask."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

APP_ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = APP_ROOT / "scripts" / "context_switch_eval_cases.json"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from app import app


def load_cases(path: Path = CASES_PATH) -> list[dict]:
    return json.loads(path.read_text())


def _new_client():
    return app.test_client()


def run_eval(cases: list[dict]) -> dict:
    results = []
    with tempfile.TemporaryDirectory(prefix="context-switch-eval-") as tmpdir:
        with patch("app.Config.DATA_DIR", tmpdir):
            for case in cases:
                client = _new_client()
                with client.session_transaction() as session:
                    session.clear()
                    session["_csrf_token"] = "context-switch-csrf"

                last_data = None
                for step in case["steps"]:
                    response = client.post(
                        "/ask",
                        json={"question": step, "csrf_token": "context-switch-csrf"},
                    )
                    try:
                        data = response.get_json() or {}
                    except Exception:
                        data = {}
                    last_data = {"status_code": response.status_code, **data}

                answer = (last_data or {}).get("answer", "") or ""
                selected_mode = (
                    (last_data or {}).get("selected_mode")
                    or ((last_data or {}).get("expert_router") or {}).get("selected_mode")
                )
                passed = True
                reasons = []

                if (last_data or {}).get("status_code") != 200:
                    passed = False
                    reasons.append(f"status_code={(last_data or {}).get('status_code')}")
                if case.get("expected_kb_verdict") != (last_data or {}).get("kb_verdict"):
                    passed = False
                    reasons.append(f"kb_verdict={(last_data or {}).get('kb_verdict')}")
                if case.get("expected_mode") != selected_mode:
                    passed = False
                    reasons.append(f"mode={selected_mode}")
                confidence_label = ((last_data or {}).get("confidence") or {}).get("label")
                if case.get("expected_confidence_label") != confidence_label:
                    passed = False
                    reasons.append(f"confidence={confidence_label}")

                for snippet in case.get("expected_answer_contains", []):
                    if snippet.lower() not in answer.lower():
                        passed = False
                        reasons.append(f"missing:{snippet}")

                for snippet in case.get("expected_answer_not_contains", []):
                    if snippet.lower() in answer.lower():
                        passed = False
                        reasons.append(f"forbidden:{snippet}")

                results.append(
                    {
                        "id": case["id"],
                        "passed": passed,
                        "reasons": reasons,
                        "kb_verdict": (last_data or {}).get("kb_verdict"),
                        "mode": selected_mode,
                        "confidence": confidence_label,
                    }
                )

    passed = sum(1 for item in results if item["passed"])
    failed = len(results) - passed
    return {"cases": len(results), "passed": passed, "failed": failed, "results": results}


def main() -> None:
    report = run_eval(load_cases())
    print("CONTEXT SWITCH EVAL")
    print(json.dumps({k: report[k] for k in ("cases", "failed", "passed")}, indent=2))
    for item in report["results"]:
        status = "PASS" if item["passed"] else "FAIL"
        extra = ""
        if item["reasons"]:
            extra = f" :: {'; '.join(item['reasons'])}"
        print(
            f"{status} {item['id']} :: verdict={item['kb_verdict']} "
            f"mode={item['mode']} confidence={item['confidence']}{extra}"
        )


if __name__ == "__main__":
    main()
