#!/usr/bin/env python3
"""Run the core demo prompts through /ask with the same CSRF/session shape as the UI."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import app  # noqa: E402


PROMPTS = [
    "What diseases does Daconil control?",
    "What fungicides control dollar spot?",
    "What is the difference between prodiamine and dithiopyr?",
    "What controls annual bluegrass weevil?",
    "What should I spray on bermuda fairways for goosegrass?",
    "Why does Poa annua decline faster than bentgrass in summer?",
    "How do I tell drought stress from disease stress?",
    "What should I be watching on greens this week?",
    "What is Headway used for?",
    "Can I overseed after Kerb SC?",
]


def main() -> int:
    app.testing = True
    failures = 0

    with app.test_client() as client:
        with client.session_transaction() as session:
            session["_csrf_token"] = "demo-prompt-check"

        print("DEMO PROMPT CHECK")
        print("=" * 72)
        for prompt in PROMPTS:
            response = client.post(
                "/ask",
                json={"csrf_token": "demo-prompt-check", "question": prompt},
            )
            payload = response.get_json() or {}
            label = payload.get("confidence", {}).get("label")
            verdict = payload.get("kb_verdict")
            ok = response.status_code == 200
            if not ok:
                failures += 1
            status = "PASS" if ok else "FAIL"
            print(f"{status} {response.status_code} | {verdict} | {label} | {prompt}")

    print(f"\nDemo prompt check {'failed' if failures else 'passed'}: {failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
