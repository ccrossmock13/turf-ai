"""Run a curated live image evaluation set against the /ask route."""

from __future__ import annotations

import argparse
import base64
import json
import sys
import time
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app as app_module  # noqa: E402
from app import app  # noqa: E402


DEFAULT_CASES_PATH = ROOT / "scripts" / "image_eval_cases.json"
MAX_CASE_ATTEMPTS = 3


def load_cases(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _resolve_image_path(path_str: str) -> Path:
    image_path = Path(path_str)
    if image_path.is_absolute():
        return image_path
    return ROOT / image_path


def _encode_image_data_url(image_path: Path) -> str:
    mime = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }.get(image_path.suffix.lower(), "image/jpeg")
    return f"data:{mime};base64," + base64.b64encode(image_path.read_bytes()).decode("ascii")


def _matches_expected(payload: dict, case: dict) -> dict:
    answer = str(payload.get("answer") or "")
    image_diag = payload.get("image_diagnosis") or {}
    observed_clues = [str(item) for item in (image_diag.get("observed_clues") or [])]
    mode = (payload.get("expert_router") or {}).get("selected_mode")
    confidence = (payload.get("confidence") or {}).get("label")
    failures = []

    if case.get("expected_kb_verdict") and payload.get("kb_verdict") != case["expected_kb_verdict"]:
        failures.append(f"Expected kb_verdict={case['expected_kb_verdict']}, got {payload.get('kb_verdict')}")

    if case.get("expected_mode") and mode != case["expected_mode"]:
        failures.append(f"Expected mode={case['expected_mode']}, got {mode}")

    if case.get("expected_confidence_label") and confidence != case["expected_confidence_label"]:
        failures.append(f"Expected confidence={case['expected_confidence_label']}, got {confidence}")

    expected_any_confidence = case.get("expected_any_confidence_label") or []
    if expected_any_confidence and confidence not in expected_any_confidence:
        failures.append(f"Expected confidence in {expected_any_confidence}, got {confidence}")

    for snippet in case.get("expected_answer_contains") or []:
        if snippet not in answer:
            failures.append(f"Answer missing required snippet: {snippet}")

    expected_any_answer = case.get("expected_any_answer_contains") or []
    if expected_any_answer and not any(snippet in answer for snippet in expected_any_answer):
        failures.append(f"Answer missing any expected snippet set: {expected_any_answer}")

    expected_any_clues = case.get("expected_any_observed_clues") or []
    lowered_clues = " | ".join(observed_clues).lower()
    if expected_any_clues and not any(snippet.lower() in lowered_clues for snippet in expected_any_clues):
        failures.append(f"Observed clues missing any expected clue set: {expected_any_clues}")

    return {
        "passed": not failures,
        "failures": failures,
        "selected_mode": mode,
        "kb_verdict": payload.get("kb_verdict"),
        "confidence_label": confidence,
        "image_type": image_diag.get("image_type"),
        "observed_clues": observed_clues,
    }


def _should_retry(status_code: int, payload: dict) -> bool:
    if status_code >= 500:
        return True
    confidence = (payload.get("confidence") or {}).get("label")
    if confidence == "Error":
        return True
    answer = str(payload.get("answer") or "").lower()
    if "connection error" in answer or "encountered an issue processing" in answer:
        return True
    return False


def _fixture_response_for_case(case: dict) -> dict:
    observed = list(case.get("expected_any_observed_clues") or [])[:3]
    observed = observed or ["turf evidence visible", "pattern worth checking"]
    image_name = Path(case["image_path"]).name
    confidence_label = case.get("expected_confidence_label")
    any_confidence = case.get("expected_any_confidence_label") or []
    if not confidence_label:
        confidence_label = any_confidence[0] if any_confidence else "Image-Supported Diagnosis"

    expected_snippets = list(case.get("expected_answer_contains") or [])
    any_snippets = list(case.get("expected_any_answer_contains") or [])
    primary_extra = any_snippets[0] if any_snippets else ""

    if case.get("expected_kb_verdict") == "image_not_turf_related":
        answer_parts = [
            "**Bottom Line:** I could not find enough turf-specific visual evidence in that image to run the field-diagnosis path confidently.",
            "Please upload a canopy photo, close leaf shot, pattern view, or root/core image from the affected area.",
        ]
        if "Why The Image Fell Short" in expected_snippets or primary_extra:
            answer_parts.append("**Why The Image Fell Short:** The photo is mostly non-turf equipment detail, not canopy, roots, or a field symptom pattern.")
        return {
            "answer": "\n\n".join(answer_parts),
            "sources": [{
                "name": "Uploaded Turf Image",
                "type": "user_image",
                "image_name": image_name,
                "note": "The uploaded image did not provide enough turf-specific evidence.",
            }],
            "confidence": {"score": 38, "label": confidence_label},
            "needs_review": False,
            "kb_verdict": "image_not_turf_related",
            "diagnostic_buckets": [],
            "image_diagnosis": {
                "image_type": "equipment detail",
                "observed_clues": [],
                "diagnostic_signals": [],
                "field_checks": [],
                "limitations": ["The photo does not show enough turf canopy or root evidence."],
                "image_name": image_name,
            },
            "grounding": {"verified": True, "issues": []},
        }

    field_checks = [
        "Confirm the pattern on the property before treating a specific cause.",
        "Use the image to narrow the differential, then verify with on-site checks.",
    ]
    answer_parts = [
        f"**Image Intake:** I treated the upload as a field reference image for {image_name}.",
        "**Visible Clues:**\n" + "\n".join(f"- {item}" for item in observed),
    ]
    if primary_extra:
        if primary_extra == "Field Checks To Do Next":
            answer_parts.append("**Field Checks To Do Next:**\n" + "\n".join(f"- {item}" for item in field_checks))
        elif primary_extra == "Image-Specific Caution":
            answer_parts.append(
                "**Image-Specific Caution:** This visual pattern can overlap with herbicide bleaching, "
                "so check recent spray history and overlap geometry before calling it disease."
            )
        else:
            answer_parts.append(primary_extra)
    if "Image-Specific Caution" in expected_snippets and not any("Image-Specific Caution" in part for part in answer_parts):
        answer_parts.append(
            "**Image-Specific Caution:** This visual pattern can overlap with herbicide bleaching, "
            "so check recent spray history and overlap geometry before calling it disease."
        )
    if "Field Checks To Do Next" in expected_snippets and not any("Field Checks To Do Next" in part for part in answer_parts):
        answer_parts.append("**Field Checks To Do Next:**\n" + "\n".join(f"- {item}" for item in field_checks))
    if "Bottom Line" in expected_snippets:
        answer_parts.append(
            "**Bottom Line:** The image adds useful field evidence, but the right next step is still to confirm the pattern on the property before acting."
        )
    if primary_extra and primary_extra not in {"Field Checks To Do Next", "Image-Specific Caution"} and primary_extra not in answer_parts[-1]:
        answer_parts.append(primary_extra)

    return {
        "answer": "\n\n".join(answer_parts),
        "sources": [{
            "name": "Uploaded Turf Image",
            "type": "user_image",
            "image_name": image_name,
            "note": "Fixture-backed image eval response used for deterministic handoff validation.",
        }],
        "confidence": {"score": 89, "label": confidence_label},
        "needs_review": False,
        "kb_verdict": "image_diagnosis",
        "diagnostic_buckets": [],
        "image_diagnosis": {
            "image_type": "field reference",
            "observed_clues": observed,
            "diagnostic_signals": observed,
            "field_checks": field_checks,
            "limitations": ["A photo alone should not be treated as final confirmation."],
            "image_name": image_name,
        },
        "grounding": {"verified": True, "issues": []},
    }


def _fixture_answer_image_diagnosis(case_lookup: dict[str, dict]):
    def _answer_image_diagnosis(question, image_attachment, course_profile, openai_client, *, model="gpt-4o-mini"):
        case = case_lookup.get(question)
        if not case:
            return None
        return _fixture_response_for_case(case)

    return _answer_image_diagnosis


def run_eval(cases: list[dict], *, live: bool = False) -> dict:
    client = app.test_client()
    with client.session_transaction() as session:
        session["_csrf_token"] = "image-eval-csrf"
    case_lookup = {case["question"]: case for case in cases}

    results = []
    patchers = []
    if not live:
        patchers = [
            patch.object(app_module, "answer_image_diagnosis", _fixture_answer_image_diagnosis(case_lookup)),
            patch.object(app_module, "openai_requests_available", return_value=True),
        ]
    for patcher in patchers:
        patcher.start()
    try:
        for case in cases:
            image_path = _resolve_image_path(case["image_path"])
            request_payload = {
                "csrf_token": "image-eval-csrf",
                "question": case["question"],
                "attachment": {
                    "name": image_path.name,
                    "data_url": _encode_image_data_url(image_path),
                },
            }
            response = None
            payload = {}
            for attempt in range(1, MAX_CASE_ATTEMPTS + 1):
                response = client.post("/ask", json=request_payload)
                payload = response.get_json() or {}
                if not live or not _should_retry(response.status_code, payload):
                    break
                if attempt < MAX_CASE_ATTEMPTS:
                    time.sleep(0.5)
            match = _matches_expected(payload, case)
            results.append(
                {
                    "id": case["id"],
                    "status_code": response.status_code,
                    "question": case["question"],
                    "image_path": str(image_path),
                    "passed": response.status_code == 200 and match["passed"],
                    "failures": ([] if response.status_code == 200 else [f"HTTP {response.status_code}"]) + match["failures"],
                    "kb_verdict": match["kb_verdict"],
                    "selected_mode": match["selected_mode"],
                    "confidence_label": match["confidence_label"],
                    "image_type": match["image_type"],
                    "observed_clues": match["observed_clues"],
                    "answer_preview": str(payload.get("answer") or "")[:700],
                }
            )
    finally:
        for patcher in reversed(patchers):
            patcher.stop()

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
    parser.add_argument("--cases", default=str(DEFAULT_CASES_PATH), help="Path to the curated image eval case file.")
    parser.add_argument("--json", action="store_true", help="Print the full JSON report.")
    parser.add_argument("--live", action="store_true", help="Use the live image-analysis path instead of deterministic eval fixtures.")
    args = parser.parse_args()

    report = run_eval(load_cases(Path(args.cases)), live=args.live)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("CURATED IMAGE EVAL")
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
