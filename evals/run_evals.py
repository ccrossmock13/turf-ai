"""
Greenside AI Evaluation Runner
Runs the eval dataset against the live /ask endpoint and scores results.

Usage:
    python evals/run_evals.py                    # Run all evals
    python evals/run_evals.py --topic chemical    # Run only chemical topic
    python evals/run_evals.py --difficulty easy    # Run only easy questions
    python evals/run_evals.py --id rate-01        # Run single eval
    python evals/run_evals.py --quick             # Run 20 representative evals
"""

import argparse
import json
import os
import sys
import time
import requests
from datetime import datetime

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from evals.eval_dataset import EVAL_DATASET


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BASE_URL = os.environ.get("EVAL_BASE_URL", "http://localhost:5001")
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

# Quick mode: representative subset across all topics
QUICK_IDS = [
    "rate-01", "rate-05", "rate-08", "rate-14",
    "disease-01", "disease-04", "disease-10",
    "cultural-01", "cultural-06", "cultural-08",
    "fert-01", "fert-04", "fert-08",
    "weed-01", "weed-06",
    "insect-01", "insect-06",
    "irrig-01", "irrig-06",
    "safety-03", "safety-05",
]


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------
def score_response(eval_item, response_data):
    """Score a single response against eval criteria. Returns dict with scores."""
    answer = (response_data.get("answer") or "").lower()
    confidence = 0
    conf_data = response_data.get("confidence", {})
    if isinstance(conf_data, dict):
        confidence = conf_data.get("score", 0)
    elif isinstance(conf_data, (int, float)):
        confidence = conf_data
    sources = response_data.get("sources", [])

    result = {
        "id": eval_item["id"],
        "question": eval_item["question"],
        "topic": eval_item["topic"],
        "difficulty": eval_item["difficulty"],
        "answer_preview": (response_data.get("answer") or "")[:200],
        "confidence": confidence,
        "source_count": len(sources),
        "scores": {},
        "passed": True,
        "failures": [],
    }

    # 1. Must-contain check (40 points)
    must_contain = eval_item["must_contain"]
    if must_contain:
        found = sum(1 for kw in must_contain if kw.lower() in answer)
        ratio = found / len(must_contain)
        result["scores"]["must_contain"] = round(ratio * 40)
        if ratio < 0.5:
            result["passed"] = False
            missing = [kw for kw in must_contain if kw.lower() not in answer]
            result["failures"].append(f"Missing keywords: {missing}")
    else:
        result["scores"]["must_contain"] = 40

    # 2. Must-not-contain check (15 points — deduction)
    must_not = eval_item["must_not_contain"]
    hallucinated = [kw for kw in must_not if kw.lower() in answer]
    if hallucinated:
        result["scores"]["no_hallucination"] = 0
        result["passed"] = False
        result["failures"].append(f"Hallucination detected: {hallucinated}")
    else:
        result["scores"]["no_hallucination"] = 15

    # 3. Confidence threshold (15 points)
    min_conf = eval_item["min_confidence"]
    if confidence >= min_conf:
        result["scores"]["confidence"] = 15
    elif confidence >= min_conf * 0.7:
        result["scores"]["confidence"] = 8
    else:
        result["scores"]["confidence"] = 0
        result["failures"].append(f"Low confidence: {confidence} (min: {min_conf})")

    # 4. Answer length / substance (15 points)
    word_count = len(answer.split())
    if word_count >= 50:
        result["scores"]["substance"] = 15
    elif word_count >= 25:
        result["scores"]["substance"] = 10
    elif word_count >= 10:
        result["scores"]["substance"] = 5
    else:
        result["scores"]["substance"] = 0
        result["failures"].append(f"Answer too short: {word_count} words")

    # 5. Sources provided (15 points)
    if len(sources) >= 2:
        result["scores"]["sources"] = 15
    elif len(sources) >= 1:
        result["scores"]["sources"] = 10
    else:
        result["scores"]["sources"] = 5

    result["total_score"] = sum(result["scores"].values())
    return result


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
def run_eval(eval_item, session_cookies=None):
    """Run a single eval against the /ask endpoint."""
    try:
        resp = requests.post(
            f"{BASE_URL}/ask",
            json={"question": eval_item["question"]},
            cookies=session_cookies,
            timeout=60,
        )
        if resp.status_code == 401:
            return {"error": "Authentication required — log in first or enable DEMO_MODE"}
        if resp.status_code != 200:
            return {"error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
        return resp.json()
    except requests.exceptions.ConnectionError:
        return {"error": f"Cannot connect to {BASE_URL} — is the server running?"}
    except Exception as e:
        return {"error": str(e)}


def get_session_cookies():
    """Try to get session cookies by logging in or using demo mode."""
    # Try demo mode first
    try:
        resp = requests.get(f"{BASE_URL}/", timeout=5)
        if resp.status_code == 200:
            return resp.cookies
    except Exception:
        pass
    return None


def run_all(evals, session_cookies=None, delay=1.0):
    """Run all evals and return results."""
    results = []
    total = len(evals)

    for i, eval_item in enumerate(evals, 1):
        print(f"  [{i}/{total}] {eval_item['id']}: {eval_item['question'][:60]}...")

        response = run_eval(eval_item, session_cookies)

        if "error" in response:
            print(f"    ERROR: {response['error']}")
            results.append({
                "id": eval_item["id"],
                "question": eval_item["question"],
                "topic": eval_item["topic"],
                "difficulty": eval_item["difficulty"],
                "error": response["error"],
                "total_score": 0,
                "passed": False,
            })
            if "Authentication" in response.get("error", ""):
                print("\n  Stopping — authentication required.")
                break
            continue

        scored = score_response(eval_item, response)
        results.append(scored)

        status = "PASS" if scored["passed"] else "FAIL"
        print(f"    {status} — Score: {scored['total_score']}/100, Confidence: {scored['confidence']}")
        if scored["failures"]:
            for f in scored["failures"]:
                print(f"    ! {f}")

        if i < total:
            time.sleep(delay)

    return results


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------
def generate_report(results):
    """Generate summary report from eval results."""
    total = len(results)
    passed = sum(1 for r in results if r.get("passed"))
    errors = sum(1 for r in results if "error" in r)
    scored_results = [r for r in results if "total_score" in r and "error" not in r]

    avg_score = sum(r["total_score"] for r in scored_results) / len(scored_results) if scored_results else 0
    avg_confidence = sum(r.get("confidence", 0) for r in scored_results) / len(scored_results) if scored_results else 0

    # By topic
    topic_scores = {}
    for r in scored_results:
        topic = r["topic"]
        if topic not in topic_scores:
            topic_scores[topic] = {"scores": [], "passed": 0, "total": 0}
        topic_scores[topic]["scores"].append(r["total_score"])
        topic_scores[topic]["total"] += 1
        if r.get("passed"):
            topic_scores[topic]["passed"] += 1

    # By difficulty
    diff_scores = {}
    for r in scored_results:
        diff = r["difficulty"]
        if diff not in diff_scores:
            diff_scores[diff] = {"scores": [], "passed": 0, "total": 0}
        diff_scores[diff]["scores"].append(r["total_score"])
        diff_scores[diff]["total"] += 1
        if r.get("passed"):
            diff_scores[diff]["passed"] += 1

    report = []
    report.append("=" * 70)
    report.append("GREENSIDE AI EVALUATION REPORT")
    report.append(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("=" * 70)
    report.append("")
    report.append(f"Total Evals:     {total}")
    report.append(f"Passed:          {passed}/{total} ({passed/total*100:.0f}%)" if total else "")
    report.append(f"Errors:          {errors}")
    report.append(f"Avg Score:       {avg_score:.1f}/100")
    report.append(f"Avg Confidence:  {avg_confidence:.1f}%")
    report.append("")

    report.append("--- BY TOPIC ---")
    for topic, data in sorted(topic_scores.items()):
        avg = sum(data["scores"]) / len(data["scores"])
        report.append(f"  {topic:15s}  {data['passed']}/{data['total']} passed  avg: {avg:.0f}/100")
    report.append("")

    report.append("--- BY DIFFICULTY ---")
    for diff in ["easy", "medium", "hard"]:
        if diff in diff_scores:
            data = diff_scores[diff]
            avg = sum(data["scores"]) / len(data["scores"])
            report.append(f"  {diff:10s}  {data['passed']}/{data['total']} passed  avg: {avg:.0f}/100")
    report.append("")

    # Bottom 10
    worst = sorted(scored_results, key=lambda r: r["total_score"])[:10]
    if worst:
        report.append("--- LOWEST SCORING (needs improvement) ---")
        for r in worst:
            report.append(f"  [{r['id']}] Score: {r['total_score']}/100 — {r['question'][:55]}")
            for f in r.get("failures", []):
                report.append(f"    ! {f}")
        report.append("")

    return "\n".join(report)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Run Greenside AI evals")
    parser.add_argument("--topic", help="Filter by topic (chemical, disease, cultural, etc.)")
    parser.add_argument("--difficulty", help="Filter by difficulty (easy, medium, hard)")
    parser.add_argument("--id", help="Run single eval by ID")
    parser.add_argument("--quick", action="store_true", help="Run 20 representative evals")
    parser.add_argument("--delay", type=float, default=1.5, help="Delay between evals (seconds)")
    parser.add_argument("--url", help="Base URL (default: http://localhost:5001)")
    args = parser.parse_args()

    global BASE_URL
    if args.url:
        BASE_URL = args.url

    # Filter dataset
    evals = EVAL_DATASET
    if args.id:
        evals = [e for e in evals if e["id"] == args.id]
    elif args.quick:
        evals = [e for e in evals if e["id"] in QUICK_IDS]
    else:
        if args.topic:
            evals = [e for e in evals if e["topic"] == args.topic]
        if args.difficulty:
            evals = [e for e in evals if e["difficulty"] == args.difficulty]

    if not evals:
        print("No evals match the filter criteria.")
        return

    print(f"\nGreenside AI Eval Suite — {len(evals)} questions")
    print(f"Target: {BASE_URL}")
    print("-" * 50)

    cookies = get_session_cookies()
    results = run_all(evals, cookies, delay=args.delay)

    # Generate report
    report = generate_report(results)
    print("\n" + report)

    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_path = os.path.join(RESULTS_DIR, f"eval_{timestamp}.json")
    report_path = os.path.join(RESULTS_DIR, f"eval_{timestamp}.txt")

    with open(results_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    with open(report_path, "w") as f:
        f.write(report)

    print(f"\nResults saved to: {results_path}")
    print(f"Report saved to:  {report_path}")


if __name__ == "__main__":
    main()
