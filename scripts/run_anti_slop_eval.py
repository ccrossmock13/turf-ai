"""Run a no-account anti-slop eval focused on canned, irrelevant, or robotic answers."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="turf-ai-anti-slop-eval-"))

from app import RATE_LIMIT_BUCKETS, app  # noqa: E402


DEFAULT_CASES_PATH = ROOT / "scripts" / "anti_slop_eval_cases.json"


def load_cases(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _make_client():
    RATE_LIMIT_BUCKETS.clear()
    client = app.test_client()
    with client.session_transaction() as session:
        session["_csrf_token"] = "anti-slop-eval-csrf"
    return client, "anti-slop-eval-csrf"


def _matches_expected(payload: dict, case: dict) -> dict:
    answer = str(payload.get("answer") or "")
    failures = []

    if case.get("expected_kb_verdict") and payload.get("kb_verdict") != case["expected_kb_verdict"]:
        failures.append(f"Expected kb_verdict={case['expected_kb_verdict']}, got {payload.get('kb_verdict')}")

    for snippet in case.get("expected_answer_contains") or []:
        if snippet not in answer:
            failures.append(f"Answer missing required snippet: {snippet}")

    for snippet in case.get("forbidden_answer_contains") or []:
        if snippet in answer:
            failures.append(f"Answer contained forbidden snippet: {snippet}")

    return {
        "passed": not failures,
        "failures": failures,
        "kb_verdict": payload.get("kb_verdict"),
        "confidence_label": (payload.get("confidence") or {}).get("label"),
    }


def run_eval(cases: list[dict]) -> dict:
    client, token = _make_client()
    results = []
    for case in cases:
        RATE_LIMIT_BUCKETS.clear()
        response = client.post(
            "/ask",
            json={
                "csrf_token": token,
                "question": case["question"],
            },
        )
        payload = response.get_json() or {}
        match = _matches_expected(payload, case)
        results.append(
            {
                "id": case["id"],
                "status_code": response.status_code,
                "question": case["question"],
                "passed": response.status_code == 200 and match["passed"],
                "failures": ([] if response.status_code == 200 else [f"HTTP {response.status_code}"]) + match["failures"],
                "kb_verdict": match["kb_verdict"],
                "confidence_label": match["confidence_label"],
                "answer_preview": str(payload.get("answer") or "")[:700],
            }
        )

    passed = sum(1 for result in results if result["passed"])
    return {
        "summary": {
            "cases": len(results),
            "passed": passed,
            "failed": len(results) - passed,
        },
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", default=str(DEFAULT_CASES_PATH), help="Path to the anti-slop eval case file.")
    parser.add_argument("--json", action="store_true", help="Print the full JSON report.")
    args = parser.parse_args()

    report = run_eval(load_cases(Path(args.cases)))
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("ANTI-SLOP EVAL")
        print(json.dumps(report["summary"], indent=2, sort_keys=True))
        for result in report["results"]:
            status = "PASS" if result["passed"] else "FAIL"
            print(f"{status} {result['id']} :: verdict={result['kb_verdict']} confidence={result['confidence_label']}")
            for failure in result["failures"]:
                print(f"  - {failure}")
    return 1 if report["summary"]["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
