"""Persistent rate limiting for single-node Greenside deployments."""

from __future__ import annotations

import os
import sqlite3
import threading
import time
import uuid
from pathlib import Path

from config import Config
from persistence_backend import dynamodb_table, to_plain_value, using_dynamodb

try:  # pragma: no cover - boto3 is deployment-specific
    from boto3.dynamodb.conditions import Key
except Exception:  # pragma: no cover
    Key = None


DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
DB_PATH = DATA_DIR / "greenside_rate_limits.db"
_INIT_LOCK = threading.Lock()


def _connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=5, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def _init_db() -> None:
    if using_dynamodb():
        return
    with _INIT_LOCK:
        conn = _connect()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS rate_limit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scope TEXT NOT NULL,
                    identity_key TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_rate_limit_scope_identity_time "
                "ON rate_limit_events(scope, identity_key, created_at)"
            )
        finally:
            conn.close()


class PersistentRateLimiter:
    def __init__(self) -> None:
        _init_db()

    def consume(self, scope: str, identity_key: str, *, limit: int, window_seconds: int) -> tuple[bool, int]:
        if using_dynamodb():
            return self._consume_dynamodb(scope, identity_key, limit=limit, window_seconds=window_seconds)
        now = time.time()
        cutoff = now - window_seconds
        conn = _connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "DELETE FROM rate_limit_events WHERE scope = ? AND identity_key = ? AND created_at <= ?",
                (scope, identity_key, cutoff),
            )
            row = conn.execute(
                """
                SELECT COUNT(*), MIN(created_at)
                FROM rate_limit_events
                WHERE scope = ? AND identity_key = ?
                """,
                (scope, identity_key),
            ).fetchone()
            count = int(row[0] or 0)
            oldest = float(row[1]) if row and row[1] is not None else None
            if count >= limit and oldest is not None:
                retry_after = max(1, int(window_seconds - (now - oldest)))
                conn.commit()
                return True, retry_after
            conn.execute(
                "INSERT INTO rate_limit_events (scope, identity_key, created_at) VALUES (?, ?, ?)",
                (scope, identity_key, now),
            )
            # Cheap global pruning to stop unbounded growth.
            conn.execute(
                "DELETE FROM rate_limit_events WHERE created_at <= ?",
                (now - max(window_seconds * 4, 86400),),
            )
            conn.commit()
            return False, 0
        finally:
            conn.close()

    def clear(self) -> None:
        if using_dynamodb():
            table = dynamodb_table(Config.DYNAMODB_RATE_LIMIT_TABLE)
            response = table.scan()
            for item in response.get("Items", []):
                clean = to_plain_value(item)
                table.delete_item(Key={"bucket_key": clean["bucket_key"], "event_id": clean["event_id"]})
            return
        _init_db()
        conn = _connect()
        try:
            conn.execute("DELETE FROM rate_limit_events")
            conn.commit()
        finally:
            conn.close()

    def _consume_dynamodb(self, scope: str, identity_key: str, *, limit: int, window_seconds: int) -> tuple[bool, int]:
        if Key is None:
            raise RuntimeError("boto3 is required for the DynamoDB persistence backend.")
        now = time.time()
        cutoff = now - window_seconds
        bucket_key = f"{scope}:{identity_key}"
        table = dynamodb_table(Config.DYNAMODB_RATE_LIMIT_TABLE)
        response = table.query(
            KeyConditionExpression=Key("bucket_key").eq(bucket_key) & Key("created_at").gte(cutoff),
        )
        items = [to_plain_value(item) for item in response.get("Items", [])]
        count = len(items)
        oldest = min((float(item.get("created_at")) for item in items), default=None)
        expired = table.query(
            KeyConditionExpression=Key("bucket_key").eq(bucket_key) & Key("created_at").lt(cutoff),
        ).get("Items", [])
        for item in expired:
            clean = to_plain_value(item)
            table.delete_item(Key={"bucket_key": clean["bucket_key"], "event_id": clean["event_id"]})
        if count >= limit and oldest is not None:
            retry_after = max(1, int(window_seconds - (now - oldest)))
            return True, retry_after
        table.put_item(
            Item={
                "bucket_key": bucket_key,
                "event_id": uuid.uuid4().hex,
                "created_at": now,
                "expires_at": int(now + max(window_seconds * 4, 86400)),
            }
        )
        return False, 0


RATE_LIMIT_BUCKETS = PersistentRateLimiter()
