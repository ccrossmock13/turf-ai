"""
Database connection utilities for Greenside AI.
Supports both SQLite (local dev) and PostgreSQL (production).

When DATABASE_URL is set, uses PostgreSQL with connection pooling.
Otherwise, falls back to SQLite with WAL mode.
"""

import os
import re
import sqlite3
import logging
from contextlib import contextmanager

logger = logging.getLogger(__name__)

DATA_DIR = os.environ.get('DATA_DIR', 'data' if os.path.exists('data') else '.')
CONVERSATIONS_DB = os.path.join(DATA_DIR, 'greenside_conversations.db')
FEEDBACK_DB = os.path.join(DATA_DIR, 'greenside_feedback.db')

# Detect database backend from DATABASE_URL
_DATABASE_URL = os.environ.get('DATABASE_URL')
_pg_pool = None


def _get_pg_pool():
    """Lazily initialize the PostgreSQL connection pool."""
    global _pg_pool
    if _pg_pool is None and _DATABASE_URL:
        try:
            from psycopg2 import pool
            _pg_pool = pool.ThreadedConnectionPool(
                minconn=2,
                maxconn=20,
                dsn=_DATABASE_URL
            )
            logger.info("PostgreSQL connection pool initialized (2-20 connections)")
        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL pool: {e}")
            raise
    return _pg_pool


def is_postgres():
    """Check if we're using PostgreSQL."""
    return bool(_DATABASE_URL)


# ---------------------------------------------------------------------------
# SQL Conversion: SQLite → PostgreSQL
# ---------------------------------------------------------------------------

def _convert_sqlite_to_pg(sql):
    """Convert SQLite SQL syntax to PostgreSQL.

    Handles:
    - ? → %s parameter placeholders
    - INTEGER PRIMARY KEY AUTOINCREMENT → SERIAL PRIMARY KEY
    - DATE('now') → CURRENT_DATE
    - DATE('now', '-N days') → CURRENT_DATE - INTERVAL 'N days'
    - date('now', ? || ' days') → CURRENT_DATE + (CAST(%s AS INTEGER) * INTERVAL '1 day')
    - GROUP_CONCAT(col) → STRING_AGG(CAST(col AS TEXT), ',')
    - INSERT ... RETURNING id (for lastrowid support)
    """
    # Parameter placeholders
    sql = sql.replace('?', '%s')

    # Auto-increment primary keys
    sql = sql.replace('INTEGER PRIMARY KEY AUTOINCREMENT', 'SERIAL PRIMARY KEY')

    # Date functions — handle specific patterns first
    # DATE('now', '-N days') or DATE('now', '-N day')
    sql = re.sub(
        r"[Dd][Aa][Tt][Ee]\(\s*'now'\s*,\s*'(-?\d+)\s+days?'\s*\)",
        lambda m: f"(CURRENT_DATE + INTERVAL '{m.group(1)} days')",
        sql
    )
    # date('now', %s || ' days') — parameterized offset
    sql = re.sub(
        r"[Dd][Aa][Tt][Ee]\(\s*'now'\s*,\s*(%s)\s*\|\|\s*'\s*days?'\s*\)",
        r"(CURRENT_DATE + (CAST(\1 AS INTEGER) * INTERVAL '1 day'))",
        sql
    )
    # DATE('now') → CURRENT_DATE
    sql = re.sub(r"[Dd][Aa][Tt][Ee]\(\s*'now'\s*\)", 'CURRENT_DATE', sql)

    # GROUP_CONCAT → STRING_AGG
    sql = re.sub(
        r'GROUP_CONCAT\((\w+)\)',
        r"STRING_AGG(CAST(\1 AS TEXT), ',')",
        sql,
        flags=re.IGNORECASE
    )

    # Add RETURNING id for INSERT ... VALUES statements (for lastrowid)
    stripped = sql.strip()
    upper = stripped.upper()
    if (upper.startswith('INSERT') and 'VALUES' in upper
            and 'RETURNING' not in upper
            and 'SELECT' not in upper.split('VALUES')[0]):
        sql = stripped.rstrip(';') + ' RETURNING id'

    return sql


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def add_column(conn, table, column, col_type):
    """Add a column to a table if it doesn't exist. Works with both backends."""
    if is_postgres():
        conn.execute(f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {col_type}')
    else:
        try:
            conn.execute(f'ALTER TABLE {table} ADD COLUMN {column} {col_type}')
        except Exception:
            pass


def table_exists(conn, table_name):
    """Check if a table exists. Works with both backends."""
    if is_postgres():
        cursor = conn.execute(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = %s)",
            (table_name,)
        )
        row = cursor.fetchone()
        return row[0] if row else False
    else:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,)
        )
        return cursor.fetchone() is not None


def get_integrity_error():
    """Return the appropriate IntegrityError class for the current backend."""
    if is_postgres():
        try:
            import psycopg2
            return psycopg2.IntegrityError
        except ImportError:
            return Exception
    return sqlite3.IntegrityError


# ---------------------------------------------------------------------------
# PostgreSQL Row/Cursor/Connection Wrappers
# ---------------------------------------------------------------------------

class _PgRowWrapper:
    """Make psycopg2 rows behave like sqlite3.Row (dict-like access)."""

    def __init__(self, cursor, row):
        self._data = {}
        if cursor.description and row:
            for i, col in enumerate(cursor.description):
                self._data[col.name] = row[i]

    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self._data.values())[key]
        return self._data[key]

    def __contains__(self, key):
        return key in self._data

    def get(self, key, default=None):
        return self._data.get(key, default)

    def keys(self):
        return self._data.keys()

    def values(self):
        return self._data.values()

    def items(self):
        return self._data.items()


class _PgCursorWrapper:
    """Wrap psycopg2 cursor to return dict-like rows with full SQL conversion."""

    def __init__(self, cursor):
        self._cursor = cursor

    def execute(self, sql, params=None):
        converted = _convert_sqlite_to_pg(sql)
        self._cursor.execute(converted, params)
        return self

    def executemany(self, sql, params_list):
        # Don't add RETURNING for executemany
        converted = sql.replace('?', '%s')
        converted = converted.replace('INTEGER PRIMARY KEY AUTOINCREMENT', 'SERIAL PRIMARY KEY')
        self._cursor.executemany(converted, params_list)
        return self

    def fetchone(self):
        row = self._cursor.fetchone()
        if row is None:
            return None
        return _PgRowWrapper(self._cursor, row)

    def fetchall(self):
        rows = self._cursor.fetchall()
        return [_PgRowWrapper(self._cursor, r) for r in rows]

    @property
    def lastrowid(self):
        return self._cursor.fetchone()[0] if self._cursor.description else None

    @property
    def rowcount(self):
        return self._cursor.rowcount

    @property
    def description(self):
        return self._cursor.description


class _PgConnWrapper:
    """Wrap psycopg2 connection to provide sqlite3-compatible interface."""

    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql, params=None):
        cursor = self._conn.cursor()
        converted = _convert_sqlite_to_pg(sql)
        # Skip SQLite PRAGMAs on PostgreSQL
        if converted.strip().upper().startswith('PRAGMA'):
            return _PgCursorWrapper(cursor)
        cursor.execute(converted, params)
        return _PgCursorWrapper(cursor)

    def cursor(self):
        return _PgCursorWrapper(self._conn.cursor())

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        # Return connection to pool instead of closing
        pool = _get_pg_pool()
        if pool:
            pool.putconn(self._conn)

    @property
    def row_factory(self):
        return None

    @row_factory.setter
    def row_factory(self, value):
        pass  # No-op for PG, we handle row wrapping ourselves


# ---------------------------------------------------------------------------
# Connection Management
# ---------------------------------------------------------------------------

@contextmanager
def get_db(db_path=None):
    """
    Context manager for database connections.
    Uses PostgreSQL when DATABASE_URL is set, otherwise SQLite with WAL.

    Usage:
        with get_db() as conn:
            conn.execute('SELECT ...')

    Args:
        db_path: Path to SQLite database. Ignored when using PostgreSQL.
                 Defaults to CONVERSATIONS_DB for SQLite.
    """
    if is_postgres():
        pool = _get_pg_pool()
        raw_conn = pool.getconn()
        conn = _PgConnWrapper(raw_conn)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()  # Returns to pool
    else:
        if db_path is None:
            db_path = CONVERSATIONS_DB
        conn = sqlite3.connect(db_path)
        conn.execute('PRAGMA journal_mode=WAL')
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def connect(db_path=None):
    """
    Simple connection factory. Returns a connection object.
    Caller is responsible for closing.

    For PostgreSQL: returns a pool-wrapped connection.
    For SQLite: returns a WAL-enabled connection with Row factory.
    """
    if is_postgres():
        pool = _get_pg_pool()
        raw_conn = pool.getconn()
        return _PgConnWrapper(raw_conn)
    else:
        if db_path is None:
            db_path = CONVERSATIONS_DB
        conn = sqlite3.connect(db_path)
        conn.execute('PRAGMA journal_mode=WAL')
        conn.row_factory = sqlite3.Row
        return conn


def enable_wal(db_path):
    """
    Enable WAL mode on a SQLite database. No-op for PostgreSQL.
    """
    if is_postgres():
        return 'wal'  # PG doesn't need WAL pragma
    conn = sqlite3.connect(db_path)
    result = conn.execute('PRAGMA journal_mode=WAL').fetchone()
    conn.close()
    logger.info(f"WAL mode set on {os.path.basename(db_path)}: {result[0]}")
    return result[0]
