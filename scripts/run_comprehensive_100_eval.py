"""Run a 100-question comprehensive turf evaluation set against /ask."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="turf-ai-comprehensive-eval-"))

from app import RATE_LIMIT_BUCKETS, app  # noqa: E402
from auth_store import create_account  # noqa: E402


DEFAULT_PROFILE = {
    "region": "Louisville, Kentucky transition zone",
    "soil": "sand based greens, some low spots stay wet",
    "surfaces": {
        "greens": "creeping bentgrass with some Poa annua",
        "fairways": "kentucky bluegrass",
        "tees": "bermudagrass",
        "rough": "tall fescue",
    },
}

SUITE_SPECS = [
    ("general_turf", ROOT / "scripts" / "general_turf_eval_cases.json", 27),
    ("ambiguity", ROOT / "scripts" / "ambiguity_eval_cases.json", 18),
    ("phd_turf", ROOT / "scripts" / "phd_turf_eval_cases.json", 22),
    ("product_label", ROOT / "scripts" / "product_label_eval_cases.json", 33),
]


def _load_json(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_cases() -> list[dict]:
    cases = []
    for suite_name, path, limit in SUITE_SPECS:
        suite_cases = _load_json(path)
        for case in suite_cases[:limit]:
            enriched = dict(case)
            enriched["suite"] = suite_name
            cases.append(enriched)
    return cases


def _make_client():
    RATE_LIMIT_BUCKETS.clear()
    client = app.test_client()
    with client.session_transaction() as session:
        session["_csrf_token"] = "comprehensive-100-eval-csrf"

    email = f"comprehensive-eval-{uuid.uuid4().hex[:8]}@example.com"
    password = "StrongPass123!"
    create_account(
        email,
        password,
        name="Comprehensive 100 Eval",
        organization="Eval",
        accepted_terms=True,
        accepted_privacy=True,
        role="admin",
    )
    login_response = client.post(
        "/login",
        json={"email": email, "password": password, "csrf_token": "comprehensive-100-eval-csrf"},
    )
    if login_response.status_code != 200:
        raise RuntimeError(f"Failed to log in eval account: HTTP {login_response.status_code}")
    with client.session_transaction() as session:
        token = session.get("_csrf_token") or "comprehensive-100-eval-csrf"

    save_response = client.post(
        "/admin/course-profile",
        json={
            "csrf_token": token,
            **DEFAULT_PROFILE,
        },
    )
    if save_response.status_code != 200:
        raise RuntimeError(f"Failed to save eval course profile: HTTP {save_response.status_code}")
    return client, token


def _matches_expected(payload: dict, case: dict) -> dict:
    answer = str(payload.get("answer") or "")
    mode = (payload.get("expert_router") or {}).get("selected_mode")
    confidence = (payload.get("confidence") or {}).get("label")
    failures = []

    if case.get("expected_kb_verdict") and payload.get("kb_verdict") != case["expected_kb_verdict"]:
        failures.append(f"Expected kb_verdict={case['expected_kb_verdict']}, got {payload.get('kb_verdict')}")

    if case.get("expected_mode") and mode != case["expected_mode"]:
        failures.append(f"Expected mode={case['expected_mode']}, got {mode}")

    if case.get("expected_topic") and payload.get("advanced_science_topic") != case["expected_topic"]:
        failures.append(f"Expected topic={case['expected_topic']}, got {payload.get('advanced_science_topic')}")

    if case.get("expected_confidence_label") and confidence != case["expected_confidence_label"]:
        failures.append(f"Expected confidence={case['expected_confidence_label']}, got {confidence}")

    if "expected_operational_guidance" in case:
        actual = bool(payload.get("operational_guidance"))
        if actual != bool(case["expected_operational_guidance"]):
            failures.append(
                f"Expected operational_guidance={case['expected_operational_guidance']}, got {actual}"
            )

    for bucket in case.get("expected_buckets") or []:
        actual_buckets = payload.get("diagnostic_buckets") or []
        if bucket not in actual_buckets:
            failures.append(f"Expected diagnostic bucket missing: {bucket}")

    for snippet in case.get("expected_answer_contains") or []:
        if snippet not in answer:
            failures.append(f"Answer missing required snippet: {snippet}")

    return {
        "passed": not failures,
        "failures": failures,
        "selected_mode": mode,
        "kb_verdict": payload.get("kb_verdict"),
        "confidence_label": confidence,
        "diagnostic_buckets": payload.get("diagnostic_buckets") or [],
        "advanced_science_topic": payload.get("advanced_science_topic"),
        "operational_guidance": bool(payload.get("operational_guidance")),
    }


def run_eval(cases: list[dict]) -> dict:
    results = []
    suite_summary: dict[str, dict[str, int]] = {}
    client = None
    token = None
    current_suite = None
    for case in cases:
        suite = case.get("suite", "unknown")
        if suite != current_suite:
            client, token = _make_client()
            current_suite = suite
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
        passed = response.status_code == 200 and match["passed"]
        suite_counts = suite_summary.setdefault(suite, {"cases": 0, "passed": 0, "failed": 0})
        suite_counts["cases"] += 1
        suite_counts["passed"] += 1 if passed else 0
        suite_counts["failed"] += 0 if passed else 1
        results.append(
            {
                "id": case["id"],
                "suite": suite,
                "status_code": response.status_code,
                "question": case["question"],
                "passed": passed,
                "failures": ([] if response.status_code == 200 else [f"HTTP {response.status_code}"]) + match["failures"],
                "kb_verdict": match["kb_verdict"],
                "selected_mode": match["selected_mode"],
                "confidence_label": match["confidence_label"],
                "diagnostic_buckets": match["diagnostic_buckets"],
                "advanced_science_topic": match["advanced_science_topic"],
                "operational_guidance": match["operational_guidance"],
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
        "suite_summary": suite_summary,
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="Print the full JSON report.")
    args = parser.parse_args()

    report = run_eval(load_cases())
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("COMPREHENSIVE 100 EVAL")
        print(json.dumps(report["summary"], indent=2, sort_keys=True))
        print("SUITE BREAKDOWN")
        print(json.dumps(report["suite_summary"], indent=2, sort_keys=True))
        for result in report["results"]:
            status = "PASS" if result["passed"] else "FAIL"
            print(
                f"{status} {result['id']} [{result['suite']}] :: verdict={result['kb_verdict']} "
                f"mode={result['selected_mode']} confidence={result['confidence_label']}"
            )
            for failure in result["failures"]:
                print(f"  - {failure}")
    return 1 if report["summary"]["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
