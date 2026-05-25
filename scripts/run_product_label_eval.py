"""Run a curated live evaluation set for product and label questions against /ask."""

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

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="turf-ai-product-eval-"))

from app import RATE_LIMIT_BUCKETS, app  # noqa: E402
from auth_store import create_account  # noqa: E402


DEFAULT_CASES_PATH = ROOT / "scripts" / "product_label_eval_cases.json"
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


def load_cases(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _make_client():
    RATE_LIMIT_BUCKETS.clear()
    client = app.test_client()
    with client.session_transaction() as session:
        session["_csrf_token"] = "product-label-eval-csrf"

    email = f"product-label-eval-{uuid.uuid4().hex[:8]}@example.com"
    password = "StrongPass123!"
    create_account(
        email,
        password,
        name="Product Label Eval",
        organization="Eval",
        accepted_terms=True,
        accepted_privacy=True,
        role="admin",
    )
    client.post("/login", json={"email": email, "password": password, "csrf_token": "product-label-eval-csrf"})
    with client.session_transaction() as session:
        token = session.get("_csrf_token") or "product-label-eval-csrf"

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

    if case.get("expected_confidence_label") and confidence != case["expected_confidence_label"]:
        failures.append(f"Expected confidence={case['expected_confidence_label']}, got {confidence}")

    for snippet in case.get("expected_answer_contains") or []:
        if snippet not in answer:
            failures.append(f"Answer missing required snippet: {snippet}")

    return {
        "passed": not failures,
        "failures": failures,
        "selected_mode": mode,
        "kb_verdict": payload.get("kb_verdict"),
        "confidence_label": confidence,
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
                "selected_mode": match["selected_mode"],
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
    parser.add_argument("--cases", default=str(DEFAULT_CASES_PATH), help="Path to the product/label eval case file.")
    parser.add_argument("--json", action="store_true", help="Print the full JSON report.")
    args = parser.parse_args()

    report = run_eval(load_cases(Path(args.cases)))
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("PRODUCT / LABEL EVAL")
        print(json.dumps(report["summary"], indent=2, sort_keys=True))
        for result in report["results"]:
            status = "PASS" if result["passed"] else "FAIL"
            print(
                f"{status} {result['id']} :: verdict={result['kb_verdict']} "
                f"mode={result['selected_mode']} confidence={result['confidence_label']}"
            )
            for failure in result["failures"]:
                print(f"  - {failure}")
    return 1 if report["summary"]["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
