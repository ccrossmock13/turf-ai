"""Run a lightweight concurrent load probe against the local Flask app.

This uses Flask test clients plus a stubbed Pinecone client so we can measure
the app's deterministic request path without requiring live vendor services.
The result is not a production benchmark. It is a local capacity probe for the
current single-node app shape.
"""

from __future__ import annotations

import os
import statistics
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pinecone


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="greenside-load-"))
os.environ.setdefault("APP_ENV", "production")
os.environ.setdefault("DEPLOYMENT_MODE", "single_node_persistent")
os.environ.setdefault("FLASK_SECRET_KEY", "load-probe-secret-key")
os.environ.setdefault("OPENAI_API_KEY", "load-probe-openai-key")
os.environ.setdefault("PINECONE_API_KEY", "load-probe-pinecone-key")
os.environ.setdefault("SMTP_HOST", "smtp.example.com")
os.environ.setdefault("MAIL_FROM", "load@example.com")


class _ProbeIndex:
    def describe_index_stats(self):
        return {"total_vector_count": 0}


class _ProbePinecone:
    def __init__(self, *args, **kwargs):
        pass

    def Index(self, name):
        return _ProbeIndex()


pinecone.Pinecone = _ProbePinecone

from app import app  # noqa: E402
from auth_store import create_account  # noqa: E402
from rate_limit_store import RATE_LIMIT_BUCKETS  # noqa: E402


def _csrf_token(client) -> str:
    with client.session_transaction() as session:
        token = session.get("_csrf_token")
        if not token:
            token = "load-probe-csrf-token"
            session["_csrf_token"] = token
        return token


def _post_json(client, path: str, payload: dict):
    body = dict(payload)
    body.setdefault("csrf_token", _csrf_token(client))
    return client.post(path, json=body)


def _setup_client(user_num: int):
    email = f"load-user-{user_num}@example.com"
    password = "StrongPass123!"
    create_account(
        email,
        password,
        name=f"Load User {user_num}",
        organization="Load Probe",
        accepted_terms=True,
        accepted_privacy=True,
        role="user",
    )
    client = app.test_client()
    _post_json(client, "/login", {"email": email, "password": password})
    _post_json(
        client,
        "/account",
        {
            "region": "Louisville, Kentucky transition zone",
            "greens_surface": "Creeping bentgrass",
            "fairways_surface": "Kentucky bluegrass",
        },
    )
    return client


def _run_user_sequence(user_num: int, requests_per_user: int, question: str):
    client = _setup_client(user_num)
    latencies = []
    failures = 0
    for _ in range(requests_per_user):
        started = time.perf_counter()
        response = _post_json(client, "/ask", {"question": question})
        latency = (time.perf_counter() - started) * 1000
        latencies.append(latency)
        if response.status_code != 200:
            failures += 1
            continue
        payload = response.get_json() or {}
        if not payload.get("answer"):
            failures += 1
    return {"latencies_ms": latencies, "failures": failures}


def _run_mixed_user_sequence(user_num: int, requests_per_user: int, question: str):
    email = f"mixed-load-user-{user_num}@example.com"
    password = "StrongPass123!"
    create_account(
        email,
        password,
        name=f"Mixed Load User {user_num}",
        organization="Load Probe",
        accepted_terms=True,
        accepted_privacy=True,
        role="user",
    )
    client = app.test_client()
    latencies = []
    failures = 0

    started = time.perf_counter()
    response = _post_json(client, "/login", {"email": email, "password": password})
    latencies.append((time.perf_counter() - started) * 1000)
    if response.status_code != 200:
        return {"latencies_ms": latencies, "failures": 1}

    started = time.perf_counter()
    response = _post_json(
        client,
        "/account",
        {
            "region": "Louisville, Kentucky transition zone",
            "greens_surface": "Creeping bentgrass",
            "fairways_surface": "Kentucky bluegrass",
        },
    )
    latencies.append((time.perf_counter() - started) * 1000)
    if response.status_code != 200:
        failures += 1

    for _ in range(requests_per_user):
        started = time.perf_counter()
        response = _post_json(client, "/ask", {"question": question})
        latencies.append((time.perf_counter() - started) * 1000)
        if response.status_code != 200:
            failures += 1
            continue
        payload = response.get_json() or {}
        if not payload.get("answer"):
            failures += 1

    return {"latencies_ms": latencies, "failures": failures}


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(round((pct / 100) * (len(ordered) - 1)))))
    return ordered[idx]


def _summarize_run(name: str, concurrency: int, request_count: int, duration: float, latencies: list[float], failures: int):
    return {
        "scenario": name,
        "concurrency": concurrency,
        "requests": request_count,
        "failures": failures,
        "duration_seconds": round(duration, 3),
        "requests_per_second": round(request_count / duration, 2),
        "p50_ms": round(statistics.median(latencies), 1) if latencies else 0.0,
        "p95_ms": round(_percentile(latencies, 95), 1),
        "max_ms": round(max(latencies), 1) if latencies else 0.0,
    }


def run_probe(concurrency_levels: list[int], requests_per_user: int = 5):
    question = "What fungicide should I use for dollar spot on bentgrass?"
    results = []
    app.testing = True

    for concurrency in concurrency_levels:
        RATE_LIMIT_BUCKETS.clear()
        started = time.perf_counter()
        batch_latencies = []
        batch_failures = 0
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [
                executor.submit(_run_user_sequence, idx, requests_per_user, question)
                for idx in range(concurrency)
            ]
            for future in as_completed(futures):
                result = future.result()
                batch_latencies.extend(result["latencies_ms"])
                batch_failures += result["failures"]
        duration = max(time.perf_counter() - started, 0.001)
        request_count = concurrency * requests_per_user
        results.append(_summarize_run("ask_only_verified", concurrency, request_count, duration, batch_latencies, batch_failures))
    return results


def run_mixed_probe(concurrency_levels: list[int], asks_per_user: int = 3):
    question = "What fungicide should I use for dollar spot on bentgrass?"
    results = []
    app.testing = True

    for concurrency in concurrency_levels:
        RATE_LIMIT_BUCKETS.clear()
        started = time.perf_counter()
        batch_latencies = []
        batch_failures = 0
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [
                executor.submit(_run_mixed_user_sequence, idx + 5000, asks_per_user, question)
                for idx in range(concurrency)
            ]
            for future in as_completed(futures):
                result = future.result()
                batch_latencies.extend(result["latencies_ms"])
                batch_failures += result["failures"]
        duration = max(time.perf_counter() - started, 0.001)
        request_count = concurrency * (asks_per_user + 2)
        results.append(_summarize_run("mixed_login_profile_ask", concurrency, request_count, duration, batch_latencies, batch_failures))
    return results


def main() -> int:
    question = "What fungicide should I use for dollar spot on bentgrass?"
    results = run_probe([1, 5, 10, 20], requests_per_user=5)
    mixed_results = run_mixed_probe([5, 10], asks_per_user=3)

    print("Local load probe")
    print(f"question: {question}")
    for row in results + mixed_results:
        print(
            "{scenario:>22} concurrency={concurrency:>2} requests={requests:>3} failures={failures:>2} "
            "rps={requests_per_second:>6} p50={p50_ms:>6}ms p95={p95_ms:>6}ms max={max_ms:>6}ms".format(**row)
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
