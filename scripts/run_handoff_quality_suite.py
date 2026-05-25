#!/usr/bin/env python3
"""Run the core handoff-quality checks in a single command."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable

CHECKS = [
    ("Auth/Route/KB tests", [
        PYTHON,
        "-m",
        "unittest",
        str(ROOT / "test_auth_flow.py"),
        str(ROOT / "test_operational_route.py"),
        str(ROOT / "test_knowledge_base.py"),
    ]),
    ("Comprehensive 100 eval", [PYTHON, str(ROOT / "scripts" / "run_comprehensive_100_eval.py")]),
    ("Anti-slop eval", [PYTHON, str(ROOT / "scripts" / "run_anti_slop_eval.py")]),
    ("No-account eval", [PYTHON, str(ROOT / "scripts" / "run_no_account_turf_eval.py")]),
    ("Context-switch eval", [PYTHON, str(ROOT / "scripts" / "run_context_switch_eval.py")]),
    ("Image eval", [PYTHON, str(ROOT / "scripts" / "run_image_eval.py")]),
    ("Smoke check", [PYTHON, str(ROOT / "scripts" / "smoke_check_simple_app.py")]),
]


def main() -> int:
    print("HANDOFF QUALITY SUITE")
    print("=" * 72)
    for label, command in CHECKS:
        print(f"\n>>> {label}")
        result = subprocess.run(command, cwd=ROOT)
        if result.returncode != 0:
            print(f"\nFAILED: {label}")
            return result.returncode
    print("\nALL HANDOFF CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
