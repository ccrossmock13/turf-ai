"""Smoke check the simple Greenside AI app without starting a dev server."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
import pinecone


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="greenside-smoke-"))
os.environ.setdefault("APP_ENV", "production")
os.environ.setdefault("DEPLOYMENT_MODE", "single_node_persistent")
os.environ.setdefault("FLASK_SECRET_KEY", "smoke-secret-key-for-release-checks")
os.environ.setdefault("OPENAI_API_KEY", "smoke-openai-key")
os.environ.setdefault("PINECONE_API_KEY", "smoke-pinecone-key")
os.environ.setdefault("SMTP_HOST", "smtp.example.com")
os.environ.setdefault("MAIL_FROM", "smoke@example.com")


class _SmokeIndex:
    def describe_index_stats(self):
        return {"total_vector_count": 0}


class _SmokePinecone:
    def __init__(self, *args, **kwargs):
        pass

    def Index(self, name):
        return _SmokeIndex()


pinecone.Pinecone = _SmokePinecone

from app import app  # noqa: E402
from auth_store import create_account  # noqa: E402


def _csrf_token(client) -> str:
    with client.session_transaction() as session:
        token = session.get("_csrf_token")
        if not token:
            token = "smoke-csrf-token"
            session["_csrf_token"] = token
        return token


def _expect_status(client, method: str, path: str, expected: set[int], **kwargs) -> bool:
    if method.lower() == "post":
        if "json" in kwargs:
            kwargs["json"] = {"csrf_token": _csrf_token(client), **kwargs["json"]}
        else:
            kwargs["json"] = {"csrf_token": _csrf_token(client)}
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
        email = "smoke-admin@example.com"
        password = "StrongPass123!"
        create_account(
            email,
            password,
            name="Smoke Admin",
            organization="Smoke Test",
            accepted_terms=True,
            accepted_privacy=True,
            role="admin",
        )
        login = client.post("/login", json={"email": email, "password": password, "csrf_token": _csrf_token(client)})
        if login.status_code != 200:
            print("FAIL POST /login")
            return 1

        checks = [
            ("get", "/", {200}, {}),
            ("get", "/resources", {200}, {}),
            ("get", "/admin", {200}, {}),
            ("get", "/health", {200, 503}, {}),
            ("get", "/ready", {200}, {}),
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

        memory = client.post("/ask", json={"question": "Remember our greens are creeping bentgrass.", "csrf_token": _csrf_token(client)})
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
