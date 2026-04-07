"""Smoke check the simple Greenside AI app without starting a dev server."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="greenside-smoke-"))

from app import app  # noqa: E402


def _expect_status(client, method: str, path: str, expected: set[int], **kwargs) -> bool:
    response = getattr(client, method.lower())(path, **kwargs)
    ok = response.status_code in expected
    label = "PASS" if ok else "FAIL"
    print(f"{label} {method.upper():4} {path:30} {response.status_code}")
    if not ok:
        print(f"     expected one of {sorted(expected)}")
    return ok


def main() -> int:
    app.testing = True
    failures = 0

    with app.test_client() as client:
        checks = [
            ("get", "/", {200}, {}),
            ("get", "/resources", {200}, {}),
            ("get", "/admin", {200}, {}),
            ("get", "/health", {200, 503}, {}),
            ("get", "/api/resources", {200}, {}),
            ("get", "/admin/stats", {200}, {}),
            ("get", "/admin/cache", {200}, {}),
            ("get", "/admin/feedback/all", {200}, {}),
            ("get", "/admin/review-queue", {200}, {}),
            ("get", "/admin/course-profile", {200}, {}),
            ("post", "/api/new-session", {200}, {}),
            ("post", "/ask", {200}, {"json": {"question": ""}}),
            ("post", "/feedback", {400}, {"json": {"rating": "bad"}}),
            ("post", "/admin/bulk-moderate", {400}, {"json": {}}),
        ]

        for method, path, expected, kwargs in checks:
            if not _expect_status(client, method, path, expected, **kwargs):
                failures += 1

        memory = client.post("/ask", json={"question": "Remember our greens are creeping bentgrass."})
        if memory.status_code != 200 or memory.get_json().get("confidence", {}).get("label") != "Course Profile Updated":
            failures += 1
            print("FAIL POST /ask course profile memory")
        else:
            print("PASS POST /ask course profile memory")

        profile = client.get("/admin/course-profile").get_json()
        if profile.get("surfaces", {}).get("greens") != "creeping bentgrass":
            failures += 1
            print("FAIL GET  /admin/course-profile memory persisted")
        else:
            print("PASS GET  /admin/course-profile memory persisted")

    print(f"\nSmoke check {'failed' if failures else 'passed'}: {failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
