"""
Feedback & Learning System
Collects user corrections and builds training data for continuous improvement
"""

import sqlite3
import os
from datetime import datetime, timezone
import json
import logging
import uuid
import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

from advanced_diagnosis import DIAGNOSTIC_BUCKETS
from advanced_turf_science import SCIENCE_TOPIC_ALIASES
from config import Config
from knowledge_base import load_advanced_turf_science, load_diagnostic_frameworks
from persistence_backend import dynamodb_table, to_plain_value, using_dynamodb
from source_policy import sanitize_source_url

# Use data directory for Docker persistence, fallback to current dir for local dev
DATA_DIR = os.environ.get('DATA_DIR', 'data' if os.path.exists('data') else '.')
DB_PATH = os.path.join(DATA_DIR, 'greenside_feedback.db')
PRODUCTS_PATH = os.path.join(os.path.dirname(__file__), 'knowledge', 'products.json')
KB_CANDIDATE_STATUSES = {'draft', 'needs_label_review', 'approved', 'rejected', 'applied_to_kb'}
LABEL_REVIEWED_STATUSES = {'label_reviewed', 'human_label_reviewed', 'reviewed', 'approved_label_review'}
PRODUCT_TARGET_FIELDS = {
    'fungicides': 'diseases',
    'herbicides': 'target_weeds',
    'insecticides': 'target_pests',
}
EVAL_TRAFFIC_TAG = 'eval_traffic'


def _normalize_review_queue_question(question: Optional[str]) -> str:
    text = str(question or "").strip().lower()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[?!.,;:]+$", "", text)
    return text


@lru_cache(maxsize=1)
def _load_eval_question_registry() -> set[str]:
    questions: set[str] = set()
    scripts_dir = Path(__file__).resolve().parent / 'scripts'
    if not scripts_dir.exists():
        return questions

    for path in scripts_dir.glob('*_eval_cases.json'):
        try:
            payload = json.loads(path.read_text(encoding='utf-8'))
        except Exception:
            continue
        if not isinstance(payload, list):
            continue
        for item in payload:
            if not isinstance(item, dict):
                continue
            question = item.get('question')
            if isinstance(question, str):
                normalized = _normalize_review_queue_question(question)
                if normalized:
                    questions.add(normalized)
            steps = item.get('steps')
            if isinstance(steps, list):
                for step in steps:
                    normalized = _normalize_review_queue_question(step)
                    if normalized:
                        questions.add(normalized)
    return questions


def _is_eval_traffic_question(question: Optional[str]) -> bool:
    normalized = _normalize_review_queue_question(question)
    return bool(normalized and normalized in _load_eval_question_registry())


def _normalize_failure_tags(failure_tags=None) -> list[str]:
    normalized: list[str] = []
    for tag in failure_tags or []:
        text = str(tag or '').strip()
        if text and text not in normalized:
            normalized.append(text)
    return normalized


def _with_eval_failure_tag(question: Optional[str], failure_tags=None) -> list[str]:
    normalized = _normalize_failure_tags(failure_tags)
    if _is_eval_traffic_question(question) and EVAL_TRAFFIC_TAG not in normalized:
        normalized.append(EVAL_TRAFFIC_TAG)
    return normalized


def _is_eval_feedback_item(item: Optional[dict]) -> bool:
    if not isinstance(item, dict):
        return False
    tags = _normalize_failure_tags(item.get('failure_tags'))
    return EVAL_TRAFFIC_TAG in tags


def _exclude_eval_feedback(items: list[dict]) -> list[dict]:
    return [item for item in items if not _is_eval_feedback_item(item)]


def _include_only_eval_feedback(items: list[dict]) -> list[dict]:
    return [item for item in items if _is_eval_feedback_item(item)]


def _deduplicate_review_queue_items(items: list[dict], limit: Optional[int] = None) -> list[dict]:
    deduped: list[dict] = []
    by_question: dict[str, dict] = {}

    for item in items:
        normalized = _normalize_review_queue_question(item.get("question"))
        entry = dict(item)
        entry["question"] = str(entry.get("question") or "").strip()
        entry.setdefault("duplicate_count", 1)
        entry.setdefault("duplicate_feedback_ids", [item.get("id")])
        entry["normalized_question"] = normalized

        if normalized and normalized in by_question:
            existing = by_question[normalized]
            existing["duplicate_count"] += 1
            duplicate_ids = existing.setdefault("duplicate_feedback_ids", [])
            duplicate_id = item.get("id")
            if duplicate_id and duplicate_id not in duplicate_ids:
                duplicate_ids.append(duplicate_id)
            continue

        if normalized:
            by_question[normalized] = entry
        deduped.append(entry)

    for entry in deduped:
        entry.pop("normalized_question", None)

    if limit is not None:
        return deduped[:limit]
    return deduped


def _review_queue_raw_limit(limit: Optional[int]) -> int:
    if limit is None:
        return 10_000
    requested = int(limit or 100)
    return max(requested * 10, 200)


def _feedback_runtime_uses_dynamodb() -> bool:
    return using_dynamodb()


def _feedback_table():
    return dynamodb_table(Config.DYNAMODB_FEEDBACK_TABLE)


def _scan_feedback_table_items() -> list[dict]:
    """Scan the full feedback table, following DynamoDB pagination when needed."""
    if not _feedback_runtime_uses_dynamodb():
        return []
    table = _feedback_table()
    response = table.scan()
    items = list(response.get("Items", []))
    last_evaluated_key = response.get("LastEvaluatedKey")
    while last_evaluated_key:
        response = table.scan(ExclusiveStartKey=last_evaluated_key)
        items.extend(response.get("Items", []))
        last_evaluated_key = response.get("LastEvaluatedKey")
    return [to_plain_value(item) for item in items]


def _load_feedback_items() -> list[dict]:
    if not _feedback_runtime_uses_dynamodb():
        return []
    items = [
        item
        for item in _scan_feedback_table_items()
        if item.get("item_type") in {None, "feedback"}
    ]
    items.sort(key=lambda item: item.get("timestamp") or "", reverse=True)
    return items


def _save_feedback_item(item: dict) -> None:
    _feedback_table().put_item(Item=item)


def _load_feedback_items_by_type(item_type: str) -> list[dict]:
    if not _feedback_runtime_uses_dynamodb():
        return []
    items = [
        item
        for item in _scan_feedback_table_items()
        if item.get("item_type") == item_type
    ]
    sort_key = "updated_at" if item_type == "router_work_item" else "created_at"
    items.sort(
        key=lambda item: (item.get(sort_key) or item.get("created_at") or "", item.get("id") or ""),
        reverse=True,
    )
    return items


def _load_feedback_records(limit: Optional[int] = None) -> list[dict]:
    """Return normalized feedback records across the active persistence backend."""
    if _feedback_runtime_uses_dynamodb():
        items = _load_feedback_items()
        if limit is not None:
            return items[:limit]
        return items

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        query = '''
            SELECT id, question, ai_answer, user_rating, user_correction, sources,
                   confidence_score, timestamp, reviewed, approved_for_training, notes, attachment_json, failure_tags_json
            FROM feedback
            ORDER BY timestamp DESC
        '''
        params = ()
        if limit is not None:
            query += ' LIMIT ?'
            params = (limit,)
        cursor.execute(query, params)
        rows = cursor.fetchall()
    finally:
        conn.close()

    return [{
        'id': row[0],
        'question': row[1],
        'ai_answer': row[2],
        'user_rating': row[3],
        'user_correction': row[4],
        'sources': json.loads(row[5]) if row[5] else [],
        'confidence_score': row[6],
        'timestamp': row[7],
        'reviewed': bool(row[8]),
        'approved_for_training': bool(row[9]),
        'notes': row[10],
        'attachment': json.loads(row[11]) if row[11] else None,
        'failure_tags': json.loads(row[12]) if len(row) > 12 and row[12] else [],
    } for row in rows]


def _load_training_example_items(unused_only: bool = True, limit: Optional[int] = None) -> list[dict]:
    """Return normalized training examples across the active persistence backend."""
    if _feedback_runtime_uses_dynamodb():
        items = _load_feedback_items_by_type('training_example')
        if unused_only:
            items = [item for item in items if not item.get('used_in_training')]
        if limit is not None:
            items = items[:limit]
        return items

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        query = '''
            SELECT id, feedback_id, question, ideal_answer, created_at, used_in_training, training_run_id
            FROM training_examples
        '''
        params = ()
        if unused_only:
            query += ' WHERE used_in_training = 0'
        query += ' ORDER BY created_at DESC'
        if limit is not None:
            query += ' LIMIT ?'
            params = (limit,)
        cursor.execute(query, params)
        rows = cursor.fetchall()
    finally:
        conn.close()

    return [{
        'id': row[0],
        'feedback_id': row[1],
        'question': row[2],
        'ideal_answer': row[3],
        'created_at': row[4],
        'used_in_training': bool(row[5]),
        'training_run_id': row[6],
    } for row in rows]


def _load_moderator_action_items(limit: Optional[int] = None) -> list[dict]:
    """Return normalized moderator actions across the active persistence backend."""
    if _feedback_runtime_uses_dynamodb():
        items = _load_feedback_items_by_type('moderator_action')
        if limit is not None:
            items = items[:limit]
        return items

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        query = '''
            SELECT ma.id, ma.feedback_id, ma.action, ma.moderator,
                   ma.original_answer, ma.corrected_answer, ma.reason, ma.timestamp,
                   f.question
            FROM moderator_actions ma
            LEFT JOIN feedback f ON ma.feedback_id = f.id
            ORDER BY ma.timestamp DESC
        '''
        params = ()
        if limit is not None:
            query += ' LIMIT ?'
            params = (limit,)
        cursor.execute(query, params)
        rows = cursor.fetchall()
    finally:
        conn.close()

    return [{
        'id': row[0],
        'feedback_id': row[1],
        'action': row[2],
        'moderator': row[3],
        'original_answer': row[4],
        'corrected_answer': row[5],
        'reason': row[6],
        'timestamp': row[7],
        'question': row[8],
    } for row in rows]


def _create_training_example_if_missing(cursor, feedback_id, question, ideal_answer):
    """Create one training example per feedback item, reusing the existing row when present."""
    cursor.execute('''
        SELECT id FROM training_examples
        WHERE feedback_id = ?
        ORDER BY created_at DESC, id DESC
        LIMIT 1
    ''', (feedback_id,))
    existing = cursor.fetchone()
    if existing:
        cursor.execute('''
            UPDATE training_examples
            SET question = ?, ideal_answer = ?
            WHERE id = ?
        ''', (question, ideal_answer, existing[0]))
        return existing[0], True

    cursor.execute('''
        INSERT INTO training_examples (feedback_id, question, ideal_answer)
        VALUES (?, ?, ?)
    ''', (feedback_id, question, ideal_answer))
    return cursor.lastrowid, False


def _save_training_example_item(feedback_id, question, ideal_answer, created_at=None):
    """Create or update one training example per feedback item in DynamoDB."""
    if not _feedback_runtime_uses_dynamodb():
        return None, False
    training_example_id = f"training-example:{feedback_id}"
    existing = _load_feedback_item_by_id(training_example_id, expected_type='training_example')
    item = {
        'id': training_example_id,
        'item_type': 'training_example',
        'feedback_id': str(feedback_id),
        'question': question,
        'ideal_answer': ideal_answer,
        'created_at': (
            existing.get('created_at')
            if existing and existing.get('created_at')
            else created_at or datetime.now(timezone.utc).isoformat()
        ),
        'used_in_training': bool(existing.get('used_in_training')) if existing else False,
        'training_run_id': existing.get('training_run_id') if existing else None,
    }
    _save_feedback_item(item)
    return training_example_id, bool(existing)


def _save_moderator_action_item(feedback_id, action, moderator='admin', original_answer=None, corrected_answer=None, reason=None):
    if not _feedback_runtime_uses_dynamodb():
        return None
    action_id = uuid.uuid4().hex
    _save_feedback_item({
        'id': action_id,
        'item_type': 'moderator_action',
        'feedback_id': str(feedback_id),
        'action': action,
        'moderator': moderator,
        'original_answer': original_answer,
        'corrected_answer': corrected_answer,
        'reason': reason,
        'timestamp': datetime.now(timezone.utc).isoformat(),
    })
    return action_id


def _save_training_run_item(run_id, num_examples=None, status='started', notes=None, model_id=None, completed=False):
    """Create or update a training-run record in DynamoDB."""
    if not _feedback_runtime_uses_dynamodb():
        return None
    existing = _load_feedback_item_by_id(run_id, expected_type='training_run')
    item = {
        'id': str(run_id),
        'item_type': 'training_run',
        'run_id': str(run_id),
        'num_examples': num_examples if num_examples is not None else (existing.get('num_examples') if existing else None),
        'status': status if status is not None else (existing.get('status') if existing else 'started'),
        'notes': notes if notes is not None else (existing.get('notes') if existing else None),
        'model_id': model_id if model_id is not None else (existing.get('model_id') if existing else None),
        'created_at': existing.get('created_at') if existing else datetime.now(timezone.utc).isoformat(),
        'completed_at': datetime.now(timezone.utc).isoformat() if completed else (existing.get('completed_at') if existing else None),
    }
    _save_feedback_item(item)
    return item


def _load_feedback_item_by_id(item_id: str, expected_type: Optional[str] = None) -> Optional[dict]:
    if not _feedback_runtime_uses_dynamodb():
        return None
    response = _feedback_table().get_item(Key={"id": str(item_id)})
    item = response.get("Item")
    if not item:
        return None
    item = to_plain_value(item)
    if expected_type and item.get("item_type") != expected_type:
        return None
    return item


def _count_local_training_examples_unused() -> int:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT COUNT(*) FROM training_examples WHERE used_in_training = 0')
        return cursor.fetchone()[0]
    except sqlite3.OperationalError:
        return 0
    finally:
        conn.close()


def _count_local_training_runs() -> int:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT COUNT(*) FROM training_runs')
        return cursor.fetchone()[0]
    except sqlite3.OperationalError:
        return 0
    finally:
        conn.close()


def get_recent_feedback(limit=8):
    """Return a compact recent-feedback feed for admin surfaces."""
    rows = _exclude_eval_feedback(_load_feedback_records(limit=None))
    if limit is not None:
        rows = rows[:limit]
    return [{
        'id': row.get('id'),
        'question': row.get('question'),
        'ai_answer': row.get('ai_answer'),
        'rating': row.get('user_rating'),
        'correction': row.get('user_correction'),
        'timestamp': row.get('timestamp'),
        'confidence': row.get('confidence_score'),
    } for row in rows]


def get_all_feedback(limit=100):
    """Return the admin feedback feed from the active persistence backend."""
    return get_recent_feedback(limit=limit)


def get_feedback_feed_page(limit=100, offset=0):
    """Return a paged admin feedback feed with a total count."""
    safe_limit = max(1, min(int(limit or 100), 500))
    safe_offset = max(0, int(offset or 0))

    rows = _exclude_eval_feedback(_load_feedback_records(limit=None))
    total = len(rows)
    page = rows[safe_offset:safe_offset + safe_limit]
    items = [{
        'id': row.get('id'),
        'question': row.get('question'),
        'ai_answer': row.get('ai_answer'),
        'rating': row.get('user_rating'),
        'user_correction': row.get('user_correction'),
        'sources': row.get('sources') or [],
        'attachment': row.get('attachment'),
        'failure_tags': row.get('failure_tags') or [],
        'confidence': row.get('confidence_score'),
        'timestamp': row.get('timestamp'),
        'reviewed': bool(row.get('reviewed')),
        'approved_for_training': bool(row.get('approved_for_training')),
        'needs_review': bool(row.get('needs_review')),
        'review_type': (
            'user_flagged' if row.get('user_rating') == 'negative'
            else 'no_feedback' if row.get('user_rating') == 'unrated'
            else 'auto_flagged'
        ),
    } for row in page]
    next_offset = safe_offset + len(items)
    return {
        'items': items,
        'total': total,
        'offset': safe_offset,
        'limit': safe_limit,
        'next_offset': next_offset,
        'has_more': next_offset < total,
    }


def get_eval_traffic_feed_page(limit=50, offset=0):
    """Return a paged feed of automated eval/demo traffic isolated from the main admin queue."""
    safe_limit = max(1, min(int(limit or 50), 200))
    safe_offset = max(0, int(offset or 0))
    rows = _include_only_eval_feedback(_load_feedback_records(limit=None))
    total = len(rows)
    page = rows[safe_offset:safe_offset + safe_limit]
    items = [{
        'id': row.get('id'),
        'question': row.get('question'),
        'ai_answer': row.get('ai_answer'),
        'rating': row.get('user_rating'),
        'user_correction': row.get('user_correction'),
        'sources': row.get('sources') or [],
        'attachment': row.get('attachment'),
        'failure_tags': row.get('failure_tags') or [],
        'confidence': row.get('confidence_score'),
        'timestamp': row.get('timestamp'),
        'reviewed': bool(row.get('reviewed')),
        'approved_for_training': bool(row.get('approved_for_training')),
        'needs_review': bool(row.get('needs_review')),
        'review_type': (
            'user_flagged' if row.get('user_rating') == 'negative'
            else 'no_feedback' if row.get('user_rating') == 'unrated'
            else 'auto_flagged'
        ),
    } for row in page]
    next_offset = safe_offset + len(items)
    return {
        'items': items,
        'total': total,
        'offset': safe_offset,
        'limit': safe_limit,
        'next_offset': next_offset,
        'has_more': next_offset < total,
        'pending_review': sum(1 for row in rows if row.get('needs_review') and not row.get('reviewed')),
    }

def init_feedback_database():
    """Initialize SQLite database for feedback collection"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Feedback table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL,
            ai_answer TEXT NOT NULL,
            user_rating TEXT NOT NULL,
            user_correction TEXT,
            sources TEXT,
            confidence_score REAL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reviewed BOOLEAN DEFAULT 0,
            approved_for_training BOOLEAN DEFAULT 0,
            notes TEXT
        )
    ''')
    
    # Training examples generated from feedback
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS training_examples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            feedback_id INTEGER NOT NULL,
            question TEXT NOT NULL,
            ideal_answer TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            used_in_training BOOLEAN DEFAULT 0,
            training_run_id TEXT,
            FOREIGN KEY (feedback_id) REFERENCES feedback (id)
        )
    ''')
    
    # Training runs tracking
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS training_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL UNIQUE,
            num_examples INTEGER NOT NULL,
            status TEXT NOT NULL,
            model_id TEXT,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            notes TEXT
        )
    ''')

    # Moderator actions audit trail
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS moderator_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            feedback_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            moderator TEXT DEFAULT 'admin',
            original_answer TEXT,
            corrected_answer TEXT,
            reason TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (feedback_id) REFERENCES feedback (id)
        )
    ''')

    # Indexes
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_rating ON feedback(user_rating)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_reviewed ON feedback(reviewed)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_approved ON feedback(approved_for_training)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_mod_actions ON moderator_actions(feedback_id)')
    for column_name, column_sql in (
        ('needs_review', 'BOOLEAN DEFAULT 0'),
        ('attachment_json', 'TEXT'),
        ('failure_tags_json', 'TEXT'),
    ):
        try:
            cursor.execute(f'SELECT {column_name} FROM feedback LIMIT 1')
        except sqlite3.OperationalError:
            cursor.execute(f'ALTER TABLE feedback ADD COLUMN {column_name} {column_sql}')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS kb_gaps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            feedback_id INTEGER,
            question TEXT NOT NULL,
            ai_answer TEXT,
            kb_verdict TEXT,
            product TEXT,
            target TEXT,
            surface TEXT,
            turf TEXT,
            gap_type TEXT NOT NULL,
            suggested_action TEXT,
            status TEXT DEFAULT 'open',
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resolved_at TIMESTAMP,
            FOREIGN KEY (feedback_id) REFERENCES feedback (id)
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_kb_gaps_status ON kb_gaps(status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_kb_gaps_type ON kb_gaps(gap_type)')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS kb_candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gap_id INTEGER,
            candidate_patch TEXT NOT NULL,
            status TEXT DEFAULT 'draft',
            reviewer TEXT DEFAULT 'admin',
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (gap_id) REFERENCES kb_gaps (id)
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_kb_candidates_gap ON kb_candidates(gap_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_kb_candidates_status ON kb_candidates(status)')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS kb_candidate_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id INTEGER NOT NULL,
            gap_id INTEGER,
            action TEXT NOT NULL,
            reviewer TEXT DEFAULT 'admin',
            old_status TEXT,
            new_status TEXT,
            notes TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (candidate_id) REFERENCES kb_candidates (id),
            FOREIGN KEY (gap_id) REFERENCES kb_gaps (id)
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_kb_candidate_actions_candidate ON kb_candidate_actions(candidate_id)')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS kb_regression_tests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gap_id INTEGER,
            candidate_id INTEGER,
            question TEXT NOT NULL,
            expected_kb_verdict TEXT,
            expected_target TEXT,
            expected_surface TEXT,
            expected_product TEXT,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_result TEXT,
            last_run_at TIMESTAMP,
            FOREIGN KEY (gap_id) REFERENCES kb_gaps (id),
            FOREIGN KEY (candidate_id) REFERENCES kb_candidates (id)
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_kb_regression_gap ON kb_regression_tests(gap_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_kb_regression_status ON kb_regression_tests(status)')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS expert_router_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL,
            selected_mode TEXT NOT NULL,
            resolved_mode TEXT NOT NULL,
            fallback_mode TEXT,
            attempted_modes TEXT,
            router_confidence REAL,
            matched_signals TEXT,
            scores TEXT,
            response_kb_verdict TEXT,
            used_deterministic BOOLEAN DEFAULT 0,
            needs_review BOOLEAN DEFAULT 0,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_router_events_selected_mode ON expert_router_events(selected_mode)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_router_events_resolved_mode ON expert_router_events(resolved_mode)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_router_events_review ON expert_router_events(needs_review)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_router_events_created_at ON expert_router_events(created_at)')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS expert_router_work_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern_key TEXT NOT NULL UNIQUE,
            suggestion_type TEXT NOT NULL,
            title TEXT NOT NULL,
            summary TEXT,
            action TEXT,
            status TEXT DEFAULT 'draft',
            event_count INTEGER DEFAULT 0,
            sample_questions TEXT,
            gap_ids TEXT,
            draft_type TEXT,
            draft_payload TEXT,
            linked_candidate_id INTEGER,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_router_work_items_status ON expert_router_work_items(status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_router_work_items_type ON expert_router_work_items(suggestion_type)')
    for column_name, column_sql in (
        ('draft_type', 'TEXT'),
        ('draft_payload', 'TEXT'),
        ('linked_candidate_id', 'INTEGER'),
    ):
        try:
            cursor.execute(f'SELECT {column_name} FROM expert_router_work_items LIMIT 1')
        except sqlite3.OperationalError:
            cursor.execute(f'ALTER TABLE expert_router_work_items ADD COLUMN {column_name} {column_sql}')
    
    conn.commit()
    conn.close()
    print("✅ Feedback database initialized")

def save_feedback(question, ai_answer, rating, correction=None, sources=None, confidence=None, attachment=None, failure_tags=None):
    """Save user feedback (when user rates)"""
    tagged_failure_tags = _with_eval_failure_tag(question, failure_tags)
    if _feedback_runtime_uses_dynamodb():
        feedback_id = uuid.uuid4().hex
        _save_feedback_item({
            'id': feedback_id,
            'item_type': 'feedback',
            'question': question,
            'ai_answer': ai_answer,
            'user_rating': rating,
            'user_correction': correction,
            'sources': sources or [],
            'confidence_score': confidence,
            'attachment': attachment,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'reviewed': False,
            'approved_for_training': False,
            'needs_review': False,
            'notes': None,
            'failure_tags': tagged_failure_tags,
        })
        return feedback_id
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    sources_json = json.dumps(sources) if sources else None
    attachment_json = json.dumps(attachment) if attachment else None
    failure_tags_json = json.dumps(tagged_failure_tags)

    try:
        cursor.execute('SELECT failure_tags_json FROM feedback LIMIT 1')
    except sqlite3.OperationalError:
        cursor.execute('ALTER TABLE feedback ADD COLUMN failure_tags_json TEXT')

    cursor.execute('''
        INSERT INTO feedback
        (question, ai_answer, user_rating, user_correction, sources, confidence_score, attachment_json, failure_tags_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (question, ai_answer, rating, correction, sources_json, confidence, attachment_json, failure_tags_json))

    feedback_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return feedback_id


def save_query(question, ai_answer, sources=None, confidence=None, topic=None, needs_review=False, attachment=None, failure_tags=None):
    """Save every query automatically (before user rates)"""
    tagged_failure_tags = _with_eval_failure_tag(question, failure_tags)
    if _feedback_runtime_uses_dynamodb():
        feedback_id = uuid.uuid4().hex
        _save_feedback_item({
            'id': feedback_id,
            'item_type': 'feedback',
            'question': question,
            'ai_answer': ai_answer,
            'user_rating': 'unrated',
            'user_correction': None,
            'sources': sources or [],
            'confidence_score': confidence,
            'attachment': attachment,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'reviewed': False,
            'approved_for_training': False,
            'needs_review': bool(needs_review),
            'notes': None,
            'failure_tags': tagged_failure_tags,
        })
        return feedback_id
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        sources_json = json.dumps(sources) if sources else None
        attachment_json = json.dumps(attachment) if attachment else None
        failure_tags_json = json.dumps(tagged_failure_tags)

        try:
            cursor.execute('SELECT failure_tags_json FROM feedback LIMIT 1')
        except sqlite3.OperationalError:
            cursor.execute('ALTER TABLE feedback ADD COLUMN failure_tags_json TEXT')

        # Use 'unrated' as the default rating
        cursor.execute('''
            INSERT INTO feedback
            (question, ai_answer, user_rating, sources, confidence_score, needs_review, attachment_json, failure_tags_json)
            VALUES (?, ?, 'unrated', ?, ?, ?, ?, ?)
        ''', (question, ai_answer, sources_json, confidence, 1 if needs_review else 0, attachment_json, failure_tags_json))

        query_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return query_id
    except Exception as e:
        logging.getLogger(__name__).error(f"DB error in save_query: {e}")
        return None


def _classify_gap_type(kb_verdict=None, product=None, target=None, surface=None):
    verdict = str(kb_verdict or '').lower()
    if verdict == 'surface_restricted':
        return 'surface_restriction'
    if verdict == 'not_verified' and product:
        return 'product_target_not_verified'
    if verdict == 'no_verified_recommendation':
        return 'missing_surface_target_product'
    if target and surface:
        return 'surface_target_gap'
    return 'kb_review_gap'


def _suggest_gap_action(gap_type, product=None, target=None, surface=None, turf=None):
    if gap_type == 'surface_restriction':
        return 'Review label turf safety and structured allowed_turf/prohibited_turf fields.'
    if gap_type == 'product_target_not_verified':
        return f"Verify whether {product or 'the product'} is labeled for {target or 'the target'}; add target/rate only if label-backed."
    if gap_type == 'missing_surface_target_product':
        return f"Add verified product options, rates, and restrictions for {target or 'this target'} on {surface or 'this surface'}{f' ({turf})' if turf else ''}."
    if gap_type == 'surface_target_gap':
        return f"Review structured KB coverage for {target or 'target'} on {surface or 'surface'}."
    return 'Review answer and update structured KB if the gap is legitimate.'


def save_kb_gap(
    question,
    ai_answer=None,
    kb_verdict=None,
    product=None,
    target=None,
    surface=None,
    turf=None,
    feedback_id=None,
    suggested_action=None,
    notes=None,
):
    """Create or reuse an open KB gap work item."""
    gap_type = _classify_gap_type(kb_verdict=kb_verdict, product=product, target=target, surface=surface)
    suggested_action = suggested_action or _suggest_gap_action(gap_type, product=product, target=target, surface=surface, turf=turf)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        try:
            cursor.execute('SELECT id FROM kb_gaps LIMIT 1')
        except sqlite3.OperationalError:
            init_feedback_database()

        cursor.execute('''
            SELECT id FROM kb_gaps
            WHERE status = 'open'
              AND question = ?
              AND COALESCE(kb_verdict, '') = COALESCE(?, '')
              AND COALESCE(product, '') = COALESCE(?, '')
              AND COALESCE(target, '') = COALESCE(?, '')
              AND COALESCE(surface, '') = COALESCE(?, '')
            ORDER BY created_at DESC
            LIMIT 1
        ''', (question, kb_verdict, product, target, surface))
        existing = cursor.fetchone()
        if existing:
            return existing[0]

        cursor.execute('''
            INSERT INTO kb_gaps
            (feedback_id, question, ai_answer, kb_verdict, product, target, surface, turf, gap_type, suggested_action, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            feedback_id, question, ai_answer, kb_verdict, product, target, surface,
            turf, gap_type, suggested_action, notes
        ))
        gap_id = cursor.lastrowid
        conn.commit()
        return gap_id
    finally:
        conn.close()


def _candidate_patch_for_gap(gap: dict) -> dict:
    gap_type = gap.get('gap_type')
    needed_fields = []
    action_type = 'review_kb_gap'

    if gap_type == 'missing_surface_target_product':
        action_type = 'add_surface_target_product'
        needed_fields = [
            'verified_product',
            'active_ingredient',
            'rate',
            'allowed_turf',
            'prohibited_turf',
            'source_url',
            'label_review_status',
        ]
    elif gap_type == 'product_target_not_verified':
        action_type = 'add_product_target_label_support'
        needed_fields = [
            'product',
            'target',
            'rate',
            'source_url',
            'target_text_checked',
            'rate_text_checked',
        ]
    elif gap_type == 'surface_restriction':
        action_type = 'review_surface_restriction'
        needed_fields = [
            'allowed_turf',
            'prohibited_turf',
            'site_restrictions',
            'label_note',
            'source_url',
        ]
    else:
        needed_fields = ['source_url', 'review_note', 'label_review_status']

    return {
        'action_type': action_type,
        'target': gap.get('target'),
        'surface': gap.get('surface'),
        'turf': gap.get('turf'),
        'product': gap.get('product'),
        'needed_fields': needed_fields,
        'status_gate': 'Do not update products.json until a label/source supports the fields.',
    }


def _normalize_term(value):
    return str(value or '').lower().replace('_', ' ').replace('-', ' ').strip()


def _product_matches_gap(product_name, info, gap):
    target = _normalize_term(gap.get('target'))
    product = _normalize_term(gap.get('product'))
    haystack = ' '.join([
        product_name.replace('_', ' '),
        ' '.join(str(name) for name in info.get('trade_names', [])),
        ' '.join(str(item).replace('_', ' ') for item in info.get('diseases', [])),
        ' '.join(str(item).replace('_', ' ') for item in info.get('target_weeds', [])),
        ' '.join(str(item).replace('_', ' ') for item in info.get('target_pests', [])),
        ' '.join(str(item).replace('_', ' ') for item in info.get('allowed_turf', [])),
        ' '.join(str(item).replace('_', ' ') for item in info.get('prohibited_turf', [])),
        str(info.get('note', '')),
    ]).lower()

    if product and product in haystack:
        return True
    if target and target in haystack:
        return True
    if target.startswith('poa ') and 'poa annua' in haystack:
        return True
    if 'trivialis' in target and any(term in haystack for term in ['tenacity', 'mesotrione', 'poa', 'bentgrass']):
        return True
    return False


def _matching_product_records(gap):
    from knowledge_base import load_products

    matches = []
    for category, products in load_products().items():
        for active_ingredient, info in products.items():
            if not _product_matches_gap(active_ingredient, info, gap):
                continue
            matches.append({
                'category': category,
                'active_ingredient': active_ingredient,
                'trade_names': info.get('trade_names', []),
                'rates': info.get('rates', {}),
                'diseases': info.get('diseases', []),
                'target_weeds': info.get('target_weeds', []),
                'target_pests': info.get('target_pests', []),
                'allowed_turf': info.get('allowed_turf', []),
                'prohibited_turf': info.get('prohibited_turf', []),
                'site_restrictions': info.get('site_restrictions', []),
                'source_url': sanitize_source_url(info.get('source_url')),
                'source_name': f"{(info.get('trade_names') or [active_ingredient])[0]} Label",
                'label_review_status': info.get('label_review_status'),
                'verification_status': info.get('verification_status'),
                'note': info.get('note'),
            })
    return matches[:12]


def _label_candidates_for_gap(gap):
    terms = [
        _normalize_term(gap.get('product')),
        _normalize_term(gap.get('target')),
        _normalize_term(gap.get('turf')),
    ]
    terms = [term for term in terms if term]
    product_dir = os.path.join('static', 'product-labels')
    candidates = []
    if not os.path.isdir(product_dir):
        return candidates

    for filename in os.listdir(product_dir):
        if not filename.lower().endswith('.pdf'):
            continue
        clean_file = _normalize_term(filename)
        score = 0
        for term in terms:
            tokens = [token for token in term.split() if len(token) > 2]
            if any(token in clean_file for token in tokens):
                score += 1
        if score:
            candidates.append({
                'filename': filename,
                'url': None,
                'score': score,
            })
    return sorted(candidates, key=lambda item: (-item['score'], item['filename']))[:12]


def _moderation_history_for_gap(gap):
    feedback_id = gap.get('feedback_id')
    if not feedback_id:
        return []
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT action, moderator, corrected_answer, reason, timestamp
            FROM moderator_actions
            WHERE feedback_id = ?
            ORDER BY timestamp DESC
            LIMIT 20
        ''', (feedback_id,))
        rows = cursor.fetchall()
    finally:
        conn.close()
    return [{
        'action': row[0],
        'moderator': row[1],
        'corrected_answer': row[2],
        'reason': row[3],
        'timestamp': row[4],
    } for row in rows]


def _gap_row_to_dict(row) -> dict:
    gap = {
        'id': row[0],
        'feedback_id': row[1],
        'question': row[2],
        'ai_answer': row[3],
        'kb_verdict': row[4],
        'product': row[5],
        'target': row[6],
        'surface': row[7],
        'turf': row[8],
        'gap_type': row[9],
        'suggested_action': row[10],
        'status': row[11],
        'notes': row[12],
        'created_at': row[13],
        'resolved_at': row[14],
    }
    gap['candidate_patch'] = _candidate_patch_for_gap(gap)
    return gap


def get_kb_gaps(status='open', limit=100, gap_type=None, target=None, product=None, surface=None):
    """Return KB gap work items for admin review."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        try:
            cursor.execute('SELECT id FROM kb_gaps LIMIT 1')
        except sqlite3.OperationalError:
            init_feedback_database()

        where = []
        params = []
        if status != 'all':
            where.append('status = ?')
            params.append(status)
        if gap_type:
            where.append('gap_type = ?')
            params.append(gap_type)
        if target:
            where.append('target = ?')
            params.append(target)
        if product:
            where.append('product = ?')
            params.append(product)
        if surface:
            where.append('surface = ?')
            params.append(surface)

        where_sql = f"WHERE {' AND '.join(where)}" if where else ''
        cursor.execute(f'''
            SELECT id, feedback_id, question, ai_answer, kb_verdict, product, target,
                   surface, turf, gap_type, suggested_action, status, notes,
                   created_at, resolved_at
            FROM kb_gaps
            {where_sql}
            ORDER BY created_at DESC
            LIMIT ?
        ''', (*params, limit))
        rows = cursor.fetchall()
    finally:
        conn.close()

    return [_gap_row_to_dict(row) for row in rows]


def get_kb_gap_detail(gap_id):
    """Return a KB gap with candidate matches, labels, candidates, and history."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT id, feedback_id, question, ai_answer, kb_verdict, product, target,
                   surface, turf, gap_type, suggested_action, status, notes,
                   created_at, resolved_at
            FROM kb_gaps
            WHERE id = ?
        ''', (gap_id,))
        row = cursor.fetchone()
        if not row:
            return None
    finally:
        conn.close()

    gap = _gap_row_to_dict(row)
    gap['matching_products'] = _matching_product_records(gap)
    gap['label_candidates'] = _label_candidates_for_gap(gap)
    gap['moderation_history'] = _moderation_history_for_gap(gap)
    gap['candidates'] = get_kb_candidates(gap_id=gap_id)
    return gap


def get_kb_gap_stats():
    """Return moderation stats for KB gaps."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        stats = {}
        cursor.execute('SELECT status, COUNT(*) FROM kb_gaps GROUP BY status')
        stats['by_status'] = dict(cursor.fetchall())
        cursor.execute('SELECT gap_type, COUNT(*) FROM kb_gaps GROUP BY gap_type ORDER BY COUNT(*) DESC')
        stats['by_gap_type'] = dict(cursor.fetchall())
        cursor.execute('SELECT target, COUNT(*) FROM kb_gaps WHERE target IS NOT NULL GROUP BY target ORDER BY COUNT(*) DESC LIMIT 10')
        stats['top_targets'] = [{'target': row[0], 'count': row[1]} for row in cursor.fetchall()]
        cursor.execute('SELECT product, COUNT(*) FROM kb_gaps WHERE product IS NOT NULL GROUP BY product ORDER BY COUNT(*) DESC LIMIT 10')
        stats['top_products'] = [{'product': row[0], 'count': row[1]} for row in cursor.fetchall()]
        cursor.execute('SELECT surface, COUNT(*) FROM kb_gaps WHERE surface IS NOT NULL GROUP BY surface ORDER BY COUNT(*) DESC LIMIT 10')
        stats['top_surfaces'] = [{'surface': row[0], 'count': row[1]} for row in cursor.fetchall()]
        cursor.execute("SELECT COUNT(*) FROM kb_gaps WHERE status = 'open'")
        stats['open'] = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM kb_gaps WHERE status IN ('resolved', 'ignored') AND resolved_at >= datetime('now', '-7 days')")
        stats['closed_last_7_days'] = cursor.fetchone()[0]
        return stats
    finally:
        conn.close()


def save_expert_router_event(
    question,
    selected_mode,
    resolved_mode,
    attempted_modes=None,
    fallback_mode=None,
    router_confidence=None,
    matched_signals=None,
    scores=None,
    response_kb_verdict=None,
    used_deterministic=False,
    needs_review=False,
    notes=None,
):
    """Persist expert router behavior for admin review."""
    if _feedback_runtime_uses_dynamodb():
        event_id = uuid.uuid4().hex
        _save_feedback_item({
            'id': event_id,
            'item_type': 'router_event',
            'question': question,
            'selected_mode': selected_mode or 'general',
            'resolved_mode': resolved_mode or 'general',
            'fallback_mode': fallback_mode,
            'attempted_modes': attempted_modes or [],
            'router_confidence': router_confidence,
            'matched_signals': matched_signals or [],
            'scores': scores or {},
            'response_kb_verdict': response_kb_verdict,
            'used_deterministic': bool(used_deterministic),
            'needs_review': bool(needs_review),
            'notes': notes,
            'created_at': datetime.now(timezone.utc).isoformat(),
        })
        return event_id
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        try:
            cursor.execute('SELECT id FROM expert_router_events LIMIT 1')
        except sqlite3.OperationalError:
            init_feedback_database()

        cursor.execute('''
            INSERT INTO expert_router_events
            (question, selected_mode, resolved_mode, fallback_mode, attempted_modes,
             router_confidence, matched_signals, scores, response_kb_verdict,
             used_deterministic, needs_review, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            question,
            selected_mode or 'general',
            resolved_mode or 'general',
            fallback_mode,
            json.dumps(attempted_modes or []),
            router_confidence,
            json.dumps(matched_signals or []),
            json.dumps(scores or {}),
            response_kb_verdict,
            1 if used_deterministic else 0,
            1 if needs_review else 0,
            notes,
        ))
        event_id = cursor.lastrowid
        conn.commit()
        return event_id
    finally:
        conn.close()


def get_expert_router_events(limit=100, selected_mode=None, needs_review=None, deterministic=None):
    """List recent expert router events for admin review."""
    if _feedback_runtime_uses_dynamodb():
        items = _load_feedback_items_by_type('router_event')
        events = []
        for item in items:
            if selected_mode and selected_mode != 'all' and item.get('selected_mode') != selected_mode:
                continue
            if needs_review is not None and bool(item.get('needs_review')) != bool(needs_review):
                continue
            if deterministic is not None and bool(item.get('used_deterministic')) != bool(deterministic):
                continue
            event = {
                'id': item.get('id'),
                'question': item.get('question'),
                'selected_mode': item.get('selected_mode') or 'general',
                'resolved_mode': item.get('resolved_mode') or 'general',
                'fallback_mode': item.get('fallback_mode'),
                'attempted_modes': item.get('attempted_modes') or [],
                'router_confidence': item.get('router_confidence'),
                'matched_signals': item.get('matched_signals') or [],
                'scores': item.get('scores') or {},
                'response_kb_verdict': item.get('response_kb_verdict'),
                'used_deterministic': bool(item.get('used_deterministic')),
                'needs_review': bool(item.get('needs_review')),
                'notes': item.get('notes'),
                'created_at': item.get('created_at'),
            }
            event['improvement_suggestion'] = _build_router_improvement_suggestion(event)
            events.append(event)
            if len(events) >= limit:
                break
        return events
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        try:
            cursor.execute('SELECT id FROM expert_router_events LIMIT 1')
        except sqlite3.OperationalError:
            init_feedback_database()

        where = []
        params = []
        if selected_mode and selected_mode != 'all':
            where.append('selected_mode = ?')
            params.append(selected_mode)
        if needs_review is not None:
            where.append('needs_review = ?')
            params.append(1 if needs_review else 0)
        if deterministic is not None:
            where.append('used_deterministic = ?')
            params.append(1 if deterministic else 0)

        where_sql = f"WHERE {' AND '.join(where)}" if where else ''
        cursor.execute(f'''
            SELECT id, question, selected_mode, resolved_mode, fallback_mode,
                   attempted_modes, router_confidence, matched_signals, scores,
                   response_kb_verdict, used_deterministic, needs_review, notes, created_at
            FROM expert_router_events
            {where_sql}
            ORDER BY created_at DESC, id DESC
            LIMIT ?
        ''', (*params, limit))
        rows = cursor.fetchall()
    finally:
        conn.close()

    events = []
    for row in rows:
        event = {
            'id': row[0],
            'question': row[1],
            'selected_mode': row[2],
            'resolved_mode': row[3],
            'fallback_mode': row[4],
            'attempted_modes': json.loads(row[5]) if row[5] else [],
            'router_confidence': row[6],
            'matched_signals': json.loads(row[7]) if row[7] else [],
            'scores': json.loads(row[8]) if row[8] else {},
            'response_kb_verdict': row[9],
            'used_deterministic': bool(row[10]),
            'needs_review': bool(row[11]),
            'notes': row[12],
            'created_at': row[13],
        }
        event['improvement_suggestion'] = _build_router_improvement_suggestion(event)
        events.append(event)
    return events


def get_expert_router_stats():
    """Summarize expert router behavior for the admin dashboard."""
    if _feedback_runtime_uses_dynamodb():
        events = get_expert_router_events(limit=500)
        total_events = len(events)
        deterministic_hits = sum(1 for event in events if event.get('used_deterministic'))
        needs_review_count = sum(1 for event in events if event.get('needs_review'))
        fallback_events = sum(
            1
            for event in events
            if (event.get('selected_mode') or 'general') != (event.get('resolved_mode') or 'general')
        )
        by_selected_mode = {}
        by_resolved_mode = {}
        fallback_pairs = {}
        confidence_values = []
        suggestion_counts = {}
        for event in events:
            selected = event.get('selected_mode') or 'general'
            resolved = event.get('resolved_mode') or 'general'
            by_selected_mode[selected] = by_selected_mode.get(selected, 0) + 1
            by_resolved_mode[resolved] = by_resolved_mode.get(resolved, 0) + 1
            if selected != resolved:
                pair = (selected, resolved)
                fallback_pairs[pair] = fallback_pairs.get(pair, 0) + 1
            if event.get('router_confidence') is not None:
                confidence_values.append(float(event['router_confidence']))
            suggestion = event.get('improvement_suggestion') or {}
            suggestion_type = suggestion.get('type')
            if suggestion_type and event.get('needs_review'):
                suggestion_counts[suggestion_type] = suggestion_counts.get(suggestion_type, 0) + 1
        return {
            'total_events': total_events,
            'deterministic_hits': deterministic_hits,
            'needs_review': needs_review_count,
            'fallback_events': fallback_events,
            'deterministic_hit_rate': round((deterministic_hits / total_events) * 100, 1) if total_events else 0.0,
            'review_rate': round((needs_review_count / total_events) * 100, 1) if total_events else 0.0,
            'by_selected_mode': [
                {'mode': key, 'count': count}
                for key, count in sorted(by_selected_mode.items(), key=lambda item: (-item[1], item[0]))
            ],
            'by_resolved_mode': [
                {'mode': key, 'count': count}
                for key, count in sorted(by_resolved_mode.items(), key=lambda item: (-item[1], item[0]))
            ],
            'top_fallbacks': [
                {'selected_mode': pair[0], 'resolved_mode': pair[1], 'count': count}
                for pair, count in sorted(fallback_pairs.items(), key=lambda item: (-item[1], item[0]))
            ][:10],
            'avg_router_confidence': round(sum(confidence_values) / len(confidence_values), 2) if confidence_values else None,
            'top_suggestion_types': [
                {'type': key, 'count': count}
                for key, count in sorted(suggestion_counts.items(), key=lambda item: (-item[1], item[0]))
            ],
            'backlog_patterns': get_expert_router_backlog(limit=5),
        }
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        try:
            cursor.execute('SELECT id FROM expert_router_events LIMIT 1')
        except sqlite3.OperationalError:
            init_feedback_database()

        stats = {}

        cursor.execute('SELECT COUNT(*) FROM expert_router_events')
        total_events = cursor.fetchone()[0]
        stats['total_events'] = total_events

        cursor.execute('SELECT COUNT(*) FROM expert_router_events WHERE used_deterministic = 1')
        deterministic_hits = cursor.fetchone()[0]
        stats['deterministic_hits'] = deterministic_hits

        cursor.execute('SELECT COUNT(*) FROM expert_router_events WHERE needs_review = 1')
        stats['needs_review'] = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM expert_router_events WHERE selected_mode != resolved_mode')
        stats['fallback_events'] = cursor.fetchone()[0]

        stats['deterministic_hit_rate'] = round((deterministic_hits / total_events) * 100, 1) if total_events else 0.0
        stats['review_rate'] = round((stats['needs_review'] / total_events) * 100, 1) if total_events else 0.0

        cursor.execute('''
            SELECT selected_mode, COUNT(*)
            FROM expert_router_events
            GROUP BY selected_mode
            ORDER BY COUNT(*) DESC, selected_mode ASC
        ''')
        stats['by_selected_mode'] = [{'mode': row[0], 'count': row[1]} for row in cursor.fetchall()]

        cursor.execute('''
            SELECT resolved_mode, COUNT(*)
            FROM expert_router_events
            GROUP BY resolved_mode
            ORDER BY COUNT(*) DESC, resolved_mode ASC
        ''')
        stats['by_resolved_mode'] = [{'mode': row[0], 'count': row[1]} for row in cursor.fetchall()]

        cursor.execute('''
            SELECT selected_mode, resolved_mode, COUNT(*)
            FROM expert_router_events
            WHERE selected_mode != resolved_mode
            GROUP BY selected_mode, resolved_mode
            ORDER BY COUNT(*) DESC, selected_mode ASC, resolved_mode ASC
            LIMIT 10
        ''')
        stats['top_fallbacks'] = [{
            'selected_mode': row[0],
            'resolved_mode': row[1],
            'count': row[2],
        } for row in cursor.fetchall()]

        cursor.execute('''
            SELECT AVG(router_confidence)
            FROM expert_router_events
            WHERE router_confidence IS NOT NULL
        ''')
        avg_confidence = cursor.fetchone()[0]
        stats['avg_router_confidence'] = round(avg_confidence, 2) if avg_confidence is not None else None

        suggestion_counts = {}
        for event in get_expert_router_events(limit=200, needs_review=True):
            suggestion = event.get('improvement_suggestion') or {}
            suggestion_type = suggestion.get('type')
            if suggestion_type:
                suggestion_counts[suggestion_type] = suggestion_counts.get(suggestion_type, 0) + 1
        stats['top_suggestion_types'] = [
            {'type': key, 'count': count}
            for key, count in sorted(suggestion_counts.items(), key=lambda item: (-item[1], item[0]))
        ]
        stats['backlog_patterns'] = get_expert_router_backlog(limit=5)

        return stats
    finally:
        conn.close()


def review_expert_router_event(event_id, needs_review=False, notes=None):
    """Mark an expert router event reviewed or keep it flagged with notes."""
    if _feedback_runtime_uses_dynamodb():
        item = _load_feedback_item_by_id(event_id, expected_type='router_event')
        if not item:
            return {'success': False, 'error': 'Router event not found'}
        item['needs_review'] = bool(needs_review)
        if notes is not None:
            item['notes'] = notes
        _save_feedback_item(item)
        return {'success': True, 'id': event_id, 'needs_review': bool(needs_review), 'notes': item.get('notes')}
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        try:
            cursor.execute('SELECT id FROM expert_router_events LIMIT 1')
        except sqlite3.OperationalError:
            init_feedback_database()

        cursor.execute('''
            UPDATE expert_router_events
            SET needs_review = ?, notes = COALESCE(?, notes)
            WHERE id = ?
        ''', (1 if needs_review else 0, notes, event_id))
        conn.commit()
        if cursor.rowcount == 0:
            return {'success': False, 'error': 'Router event not found'}
        return {'success': True, 'id': event_id, 'needs_review': bool(needs_review), 'notes': notes}
    finally:
        conn.close()


def _contains_term(question_lower: str, term: str) -> bool:
    clean_question = f" {str(question_lower or '').lower()} "
    clean_term = f" {str(term or '').lower().strip()} "
    return clean_term in clean_question or str(term or '').lower() in str(question_lower or '').lower()


def _find_related_kb_gap(question: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT id, gap_type, kb_verdict, suggested_action, status
            FROM kb_gaps
            WHERE question = ?
            ORDER BY CASE WHEN status = 'open' THEN 0 ELSE 1 END, created_at DESC
            LIMIT 1
        ''', (question,))
        row = cursor.fetchone()
        if not row:
            return None
        return {
            'id': row[0],
            'gap_type': row[1],
            'kb_verdict': row[2],
            'suggested_action': row[3],
            'status': row[4],
        }
    finally:
        conn.close()


def _matched_diagnosis_labels(question_lower: str) -> list[str]:
    labels = []
    for bucket in DIAGNOSTIC_BUCKETS.values():
        if any(_contains_term(question_lower, trigger) for trigger in bucket.get('triggers', [])):
            labels.append(bucket.get('label'))
    return labels[:3]


def _matched_science_topics(question_lower: str) -> list[str]:
    topics = []
    for topic_key, aliases in SCIENCE_TOPIC_ALIASES.items():
        if any(_contains_term(question_lower, alias) for alias in aliases):
            topics.append(topic_key)
    return topics[:4]


def _build_router_improvement_suggestion(event: dict) -> Optional[dict]:
    question = event.get('question') or ''
    question_lower = question.lower()
    related_gap = _find_related_kb_gap(question)
    selected_mode = event.get('selected_mode')
    resolved_mode = event.get('resolved_mode')
    response_kb_verdict = event.get('response_kb_verdict')
    needs_review = bool(event.get('needs_review'))

    active_related_gap = related_gap if related_gap and related_gap.get('status') == 'open' else None

    if active_related_gap or response_kb_verdict in {'not_verified', 'surface_restricted', 'no_verified_recommendation'}:
        action = active_related_gap.get('suggested_action') if active_related_gap else 'Review the KB coverage and add structured support if the gap is legitimate.'
        return {
            'type': 'kb_gap',
            'title': 'KB follow-up available',
            'summary': action,
            'gap_id': active_related_gap.get('id') if active_related_gap else None,
            'gap_status': active_related_gap.get('status') if active_related_gap else None,
            'gap_type': active_related_gap.get('gap_type') if active_related_gap else None,
        }

    if selected_mode == 'advanced_diagnosis' or (resolved_mode == 'advanced_diagnosis' and event.get('needs_review')):
        buckets = _matched_diagnosis_labels(question_lower)
        if buckets:
            return {
                'type': 'diagnosis_topic',
                'title': 'Expand diagnosis coverage',
                'summary': f"Review diagnostic handling for: {', '.join(buckets)}.",
                'recommended_buckets': buckets,
                'action': 'Add aliases, field checks, or a stronger deterministic differential for this phrasing.',
            }

    if selected_mode == 'advanced_turf_science' or (resolved_mode == 'advanced_turf_science' and event.get('needs_review')):
        topics = _matched_science_topics(question_lower)
        if topics:
            return {
                'type': 'science_topic',
                'title': 'Expand science topic coverage',
                'summary': f"Review advanced turf science routing for: {', '.join(topic.replace('_', ' ') for topic in topics)}.",
                'recommended_topics': topics,
                'action': 'Add aliases or strengthen deterministic topic matching for this wording.',
            }

    if selected_mode == 'verified_product' and needs_review:
        return {
            'type': 'product_router',
            'title': 'Review product routing and extraction',
            'summary': 'This looked product-oriented. Check product detection, target extraction, and whether structured product support is missing.',
            'action': 'Tune product aliases or add verified product KB support if the question reflects a real coverage gap.',
        }

    if selected_mode != resolved_mode:
        return {
            'type': 'router_tuning',
            'title': 'Tune router overlap',
            'summary': f"The router selected {selected_mode}, but {resolved_mode} answered the question.",
            'action': 'Adjust aliases or scoring weights so the intended mode wins without needing fallback.',
        }

    return None


def get_expert_router_work_items(status='all', limit=100):
    """List router backlog work items."""
    if _feedback_runtime_uses_dynamodb():
        items = _load_feedback_items_by_type('router_work_item')
        work_items = []
        for item in items:
            item_status = item.get('status', 'draft')
            if status == 'open':
                if item_status in {'done', 'ignored'}:
                    continue
            elif status != 'all' and item_status != status:
                continue
            work_items.append({
                'id': item.get('id'),
                'pattern_key': item.get('pattern_key'),
                'suggestion_type': item.get('suggestion_type'),
                'title': item.get('title'),
                'summary': item.get('summary'),
                'action': item.get('action'),
                'status': item.get('status', 'draft'),
                'event_count': int(item.get('event_count') or 0),
                'sample_questions': item.get('sample_questions') or [],
                'gap_ids': item.get('gap_ids') or [],
                'draft_type': item.get('draft_type'),
                'draft_payload': item.get('draft_payload'),
                'linked_candidate_id': item.get('linked_candidate_id'),
                'notes': item.get('notes'),
                'created_at': item.get('created_at'),
                'updated_at': item.get('updated_at'),
            })
            if len(work_items) >= limit:
                break
        return work_items
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        try:
            cursor.execute('SELECT id FROM expert_router_work_items LIMIT 1')
        except sqlite3.OperationalError:
            init_feedback_database()

        where = ''
        params = []
        if status == 'open':
            where = "WHERE status NOT IN ('done', 'ignored')"
        elif status != 'all':
            where = 'WHERE status = ?'
            params.append(status)
        cursor.execute(f'''
            SELECT id, pattern_key, suggestion_type, title, summary, action, status,
                   event_count, sample_questions, gap_ids, draft_type, draft_payload,
                   linked_candidate_id, notes, created_at, updated_at
            FROM expert_router_work_items
            {where}
            ORDER BY updated_at DESC, id DESC
            LIMIT ?
        ''', (*params, limit))
        rows = cursor.fetchall()
    finally:
        conn.close()

    return [{
        'id': row[0],
        'pattern_key': row[1],
        'suggestion_type': row[2],
        'title': row[3],
        'summary': row[4],
        'action': row[5],
        'status': row[6],
        'event_count': row[7],
        'sample_questions': json.loads(row[8]) if row[8] else [],
        'gap_ids': json.loads(row[9]) if row[9] else [],
        'draft_type': row[10],
        'draft_payload': json.loads(row[11]) if row[11] else None,
        'linked_candidate_id': row[12],
        'notes': row[13],
        'created_at': row[14],
        'updated_at': row[15],
    } for row in rows]


def _expert_router_work_item_by_id(cursor, work_item_id):
    cursor.execute('''
        SELECT id, pattern_key, suggestion_type, title, summary, action, status,
               event_count, sample_questions, gap_ids, draft_type, draft_payload,
               linked_candidate_id, notes, created_at, updated_at
        FROM expert_router_work_items
        WHERE id = ?
        LIMIT 1
    ''', (work_item_id,))
    row = cursor.fetchone()
    if not row:
        return None
    return {
        'id': row[0],
        'pattern_key': row[1],
        'suggestion_type': row[2],
        'title': row[3],
        'summary': row[4],
        'action': row[5],
        'status': row[6],
        'event_count': row[7],
        'sample_questions': json.loads(row[8]) if row[8] else [],
        'gap_ids': json.loads(row[9]) if row[9] else [],
        'draft_type': row[10],
        'draft_payload': json.loads(row[11]) if row[11] else None,
        'linked_candidate_id': row[12],
        'notes': row[13],
        'created_at': row[14],
        'updated_at': row[15],
    }


def create_expert_router_work_item(pattern_key, notes=None):
    """Create or refresh a tracked work item from a backlog pattern."""
    backlog = get_expert_router_backlog(limit=200)
    pattern = next((item for item in backlog if item.get('pattern_key') == pattern_key), None)
    if not pattern:
        return {'success': False, 'error': 'Backlog pattern not found'}

    if _feedback_runtime_uses_dynamodb():
        existing = next(
            (item for item in get_expert_router_work_items(status='all', limit=500) if item.get('pattern_key') == pattern_key),
            None,
        )
        now = datetime.now(timezone.utc).isoformat()
        item = {
            'id': existing['id'] if existing else uuid.uuid4().hex,
            'item_type': 'router_work_item',
            'pattern_key': pattern_key,
            'suggestion_type': pattern.get('type') or 'router_tuning',
            'title': pattern.get('title') or 'Router follow-up',
            'summary': pattern.get('summary'),
            'action': pattern.get('action'),
            'status': existing.get('status', 'draft') if existing else 'draft',
            'event_count': pattern.get('count', 0),
            'sample_questions': pattern.get('sample_questions') or [],
            'gap_ids': pattern.get('gap_ids') or [],
            'draft_type': existing.get('draft_type') if existing else None,
            'draft_payload': existing.get('draft_payload') if existing else None,
            'linked_candidate_id': existing.get('linked_candidate_id') if existing else None,
            'notes': notes if notes is not None else (existing.get('notes') if existing else None),
            'created_at': existing.get('created_at') if existing else now,
            'updated_at': now,
        }
        _save_feedback_item(item)
        return {'success': True, 'id': item['id'], 'status': item['status'], 'pattern_key': pattern_key}

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        try:
            cursor.execute('SELECT id FROM expert_router_work_items LIMIT 1')
        except sqlite3.OperationalError:
            init_feedback_database()

        cursor.execute('''
            SELECT id, status FROM expert_router_work_items
            WHERE pattern_key = ?
            LIMIT 1
        ''', (pattern_key,))
        existing = cursor.fetchone()

        payload = (
            pattern_key,
            pattern.get('type') or 'router_tuning',
            pattern.get('title') or 'Router follow-up',
            pattern.get('summary'),
            pattern.get('action'),
            pattern.get('count', 0),
            json.dumps(pattern.get('sample_questions') or []),
            json.dumps(pattern.get('gap_ids') or []),
            notes,
        )

        if existing:
            cursor.execute('''
                UPDATE expert_router_work_items
                SET suggestion_type = ?, title = ?, summary = ?, action = ?,
                    event_count = ?, sample_questions = ?, gap_ids = ?,
                    notes = COALESCE(?, notes), updated_at = CURRENT_TIMESTAMP
                WHERE pattern_key = ?
            ''', (
                payload[1], payload[2], payload[3], payload[4], payload[5],
                payload[6], payload[7], payload[8], pattern_key
            ))
            work_item_id = existing[0]
            status = existing[1]
        else:
            cursor.execute('''
                INSERT INTO expert_router_work_items
                (pattern_key, suggestion_type, title, summary, action, event_count,
                 sample_questions, gap_ids, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', payload)
            work_item_id = cursor.lastrowid
            status = 'draft'

        conn.commit()
        return {'success': True, 'id': work_item_id, 'status': status, 'pattern_key': pattern_key}
    finally:
        conn.close()


def update_expert_router_work_item_status(work_item_id, status, notes=None):
    """Update a router work item status."""
    allowed = {'draft', 'in_progress', 'done', 'ignored'}
    if status not in allowed:
        return {'success': False, 'error': f'Invalid status: {status}'}

    if _feedback_runtime_uses_dynamodb():
        item = _load_feedback_item_by_id(work_item_id, expected_type='router_work_item')
        if not item:
            return {'success': False, 'error': 'Router work item not found'}
        item['status'] = status
        if notes is not None:
            item['notes'] = notes
        item['updated_at'] = datetime.now(timezone.utc).isoformat()
        _save_feedback_item(item)
        return {'success': True, 'id': work_item_id, 'status': status}

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        try:
            cursor.execute('SELECT id FROM expert_router_work_items LIMIT 1')
        except sqlite3.OperationalError:
            init_feedback_database()

        cursor.execute('''
            UPDATE expert_router_work_items
            SET status = ?, notes = COALESCE(?, notes), updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (status, notes, work_item_id))
        conn.commit()
        if cursor.rowcount == 0:
            return {'success': False, 'error': 'Router work item not found'}
        return {'success': True, 'id': work_item_id, 'status': status}
    finally:
        conn.close()


def generate_expert_router_work_item_draft(work_item_id, reviewer='admin'):
    """Generate the next best draft artifact for a router work item."""
    if _feedback_runtime_uses_dynamodb():
        work_item = _load_feedback_item_by_id(work_item_id, expected_type='router_work_item')
        if not work_item:
            return {'success': False, 'error': 'Router work item not found'}

        if work_item.get('draft_payload'):
            return {
                'success': True,
                'id': work_item_id,
                'draft_type': work_item.get('draft_type'),
                'draft_payload': work_item.get('draft_payload'),
                'linked_candidate_id': work_item.get('linked_candidate_id'),
                'reused': True,
            }

        if work_item.get('suggestion_type') == 'kb_gap' and work_item.get('gap_ids'):
            gap_id = work_item['gap_ids'][0]
            gap_detail = get_kb_gap_detail(gap_id)
            if not gap_detail:
                return {'success': False, 'error': 'Linked KB gap not found'}
            candidate_result = create_kb_candidate(
                gap_id=gap_id,
                candidate_patch=gap_detail.get('candidate_patch') or {},
                reviewer=reviewer,
                notes='Auto-created from router work item',
                status='draft',
            )
            if not candidate_result.get('success'):
                return candidate_result
            draft_type = 'kb_candidate'
            draft_payload = {
                'gap_id': gap_id,
                'candidate_id': candidate_result['id'],
                'candidate_patch': gap_detail.get('candidate_patch') or {},
            }
            linked_candidate_id = candidate_result['id']
        else:
            draft_type, draft_payload = _build_router_note_draft(work_item)
            linked_candidate_id = None

        work_item['draft_type'] = draft_type
        work_item['draft_payload'] = draft_payload
        work_item['linked_candidate_id'] = linked_candidate_id
        work_item['updated_at'] = datetime.now(timezone.utc).isoformat()
        _save_feedback_item(work_item)
        return {
            'success': True,
            'id': work_item_id,
            'draft_type': draft_type,
            'draft_payload': draft_payload,
            'linked_candidate_id': linked_candidate_id,
            'reused': False,
        }

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        try:
            cursor.execute('SELECT id FROM expert_router_work_items LIMIT 1')
        except sqlite3.OperationalError:
            init_feedback_database()

        work_item = _expert_router_work_item_by_id(cursor, work_item_id)
        if not work_item:
            return {'success': False, 'error': 'Router work item not found'}

        if work_item.get('draft_payload'):
            return {
                'success': True,
                'id': work_item_id,
                'draft_type': work_item.get('draft_type'),
                'draft_payload': work_item.get('draft_payload'),
                'linked_candidate_id': work_item.get('linked_candidate_id'),
                'reused': True,
            }

        if work_item['suggestion_type'] == 'kb_gap' and work_item.get('gap_ids'):
            gap_id = work_item['gap_ids'][0]
            gap_detail = get_kb_gap_detail(gap_id)
            if not gap_detail:
                return {'success': False, 'error': 'Linked KB gap not found'}
            candidate_result = create_kb_candidate(
                gap_id=gap_id,
                candidate_patch=gap_detail.get('candidate_patch') or {},
                reviewer=reviewer,
                notes='Auto-created from router work item',
                status='draft',
            )
            if not candidate_result.get('success'):
                return candidate_result
            draft_type = 'kb_candidate'
            draft_payload = {
                'gap_id': gap_id,
                'candidate_id': candidate_result['id'],
                'candidate_patch': gap_detail.get('candidate_patch') or {},
            }
            linked_candidate_id = candidate_result['id']
        else:
            draft_type, draft_payload = _build_router_note_draft(work_item)
            linked_candidate_id = None

        cursor.execute('''
            UPDATE expert_router_work_items
            SET draft_type = ?, draft_payload = ?, linked_candidate_id = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (
            draft_type,
            json.dumps(draft_payload, sort_keys=True),
            linked_candidate_id,
            work_item_id,
        ))
        conn.commit()
        return {
            'success': True,
            'id': work_item_id,
            'draft_type': draft_type,
            'draft_payload': draft_payload,
            'linked_candidate_id': linked_candidate_id,
            'reused': False,
        }
    finally:
        conn.close()


def _build_router_note_draft(work_item):
    suggestion_type = work_item.get('suggestion_type')
    sample_questions = work_item.get('sample_questions') or []

    if suggestion_type == 'diagnosis_topic':
        frameworks = load_diagnostic_frameworks()
        relevant = []
        for bucket_label in work_item.get('title', ''), *(work_item.get('sample_questions') or []):
            _ = bucket_label
        for bucket in _matched_diagnosis_labels(' '.join(sample_questions).lower()):
            relevant.append(bucket)
        sections = []
        for framework_key, framework in frameworks.items():
            name = framework.get('name') or framework_key.replace('_', ' ')
            if any(label.lower() in name.lower() for label in relevant):
                sections.append({
                    'framework': framework_key,
                    'name': name,
                    'problem_space': framework.get('problem_space', []),
                    'first_checks': framework.get('first_checks', []),
                })
        if not sections:
            sections = [{
                'framework': None,
                'name': label,
                'problem_space': [],
                'first_checks': [],
            } for label in relevant]
        return 'diagnosis_note', {
            'title': work_item.get('title'),
            'summary': work_item.get('summary'),
            'action': work_item.get('action'),
            'recommended_buckets': relevant,
            'sample_questions': sample_questions,
            'implementation_outline': [
                'Add broader aliases that match the sample phrasing.',
                'Strengthen deterministic differential logic for the suggested bucket.',
                'Add a regression test for each representative question.',
            ],
            'framework_sections': sections,
        }

    if suggestion_type == 'science_topic':
        science = load_advanced_turf_science()
        matched_topics = _matched_science_topics(' '.join(sample_questions).lower())
        sections = []
        for topic_key in matched_topics:
            record = science.get(topic_key)
            if not record:
                continue
            sections.append({
                'topic': topic_key,
                'principle': record.get('principle'),
                'mechanisms': record.get('mechanisms', [])[:3],
                'decision_rules': record.get('decision_rules', [])[:3],
            })
        return 'science_note', {
            'title': work_item.get('title'),
            'summary': work_item.get('summary'),
            'action': work_item.get('action'),
            'recommended_topics': matched_topics,
            'sample_questions': sample_questions,
            'implementation_outline': [
                'Add aliases or phrase variants from the sample questions.',
                'Verify the topic returns a deterministic advanced science answer.',
                'Add regression coverage for the new wording.',
            ],
            'topic_sections': sections,
        }

    return 'router_note', {
        'title': work_item.get('title'),
        'summary': work_item.get('summary'),
        'action': work_item.get('action'),
        'sample_questions': sample_questions,
        'implementation_outline': [
            'Review the selected vs resolved mode mismatch.',
            'Tune aliases or scoring weights to remove the fallback.',
            'Add a regression test for the repeated wording pattern.',
        ],
    }


def _router_backlog_key(suggestion: dict, event: dict) -> tuple[str, str]:
    suggestion_type = suggestion.get('type') or 'other'
    if suggestion_type == 'kb_gap':
        gap_type = suggestion.get('gap_type') or event.get('response_kb_verdict') or 'kb_gap'
        return suggestion_type, f"gap:{gap_type}"
    if suggestion_type == 'diagnosis_topic':
        buckets = suggestion.get('recommended_buckets') or []
        bucket_key = buckets[0] if buckets else 'diagnosis'
        return suggestion_type, f"diagnosis:{bucket_key}"
    if suggestion_type == 'science_topic':
        topics = suggestion.get('recommended_topics') or []
        topic_key = '|'.join(sorted(topics)) if topics else 'science'
        return suggestion_type, f"science:{topic_key}"
    if suggestion_type == 'product_router':
        return suggestion_type, f"product:{event.get('selected_mode') or 'verified_product'}"
    return suggestion_type, f"route:{event.get('selected_mode') or 'general'}->{event.get('resolved_mode') or 'general'}"


def get_expert_router_backlog(limit=10):
    """Aggregate repeated router-review events into backlog patterns."""
    events = get_expert_router_events(limit=500, needs_review=True)
    groups = {}

    for event in events:
        suggestion = event.get('improvement_suggestion')
        if not suggestion:
            continue
        _, pattern_key = _router_backlog_key(suggestion, event)
        group = groups.setdefault(pattern_key, {
            'pattern_key': pattern_key,
            'type': suggestion.get('type'),
            'title': suggestion.get('title') or 'Router follow-up',
            'summary': suggestion.get('summary') or '',
            'action': suggestion.get('action'),
            'count': 0,
            'selected_mode': event.get('selected_mode'),
            'resolved_mode': event.get('resolved_mode'),
            'gap_ids': [],
            'sample_questions': [],
            'recommended_buckets': [],
            'recommended_topics': [],
            'latest_created_at': event.get('created_at'),
        })
        group['count'] += 1
        if len(group['sample_questions']) < 3 and event.get('question') not in group['sample_questions']:
            group['sample_questions'].append(event.get('question'))
        if suggestion.get('gap_id') and suggestion['gap_id'] not in group['gap_ids']:
            group['gap_ids'].append(suggestion['gap_id'])
        for bucket in suggestion.get('recommended_buckets') or []:
            if bucket not in group['recommended_buckets']:
                group['recommended_buckets'].append(bucket)
        for topic in suggestion.get('recommended_topics') or []:
            if topic not in group['recommended_topics']:
                group['recommended_topics'].append(topic)
        latest = group.get('latest_created_at')
        created = event.get('created_at')
        if created and (not latest or created > latest):
            group['latest_created_at'] = created

    backlog = sorted(
        groups.values(),
        key=lambda item: (-item['count'], item.get('title') or '', item.get('pattern_key') or '')
    )
    annotated = backlog[:limit]

    existing_items = {item['pattern_key']: item for item in get_expert_router_work_items(status='all', limit=200)}
    for item in annotated:
        item['work_item'] = existing_items.get(item['pattern_key'])
    return annotated


def create_kb_candidate(gap_id, candidate_patch, reviewer='admin', notes=None, status='draft'):
    """Store a draft KB candidate patch for review."""
    if status not in KB_CANDIDATE_STATUSES:
        return {'success': False, 'error': f'Invalid candidate status: {status}'}
    if not isinstance(candidate_patch, dict):
        return {'success': False, 'error': 'candidate_patch must be an object'}

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT id FROM kb_gaps WHERE id = ?', (gap_id,))
        if not cursor.fetchone():
            return {'success': False, 'error': 'KB gap not found'}
        cursor.execute('''
            INSERT INTO kb_candidates (gap_id, candidate_patch, status, reviewer, notes)
            VALUES (?, ?, ?, ?, ?)
        ''', (gap_id, json.dumps(candidate_patch, sort_keys=True), status, reviewer, notes))
        candidate_id = cursor.lastrowid
        _record_candidate_action(
            cursor,
            candidate_id=candidate_id,
            gap_id=gap_id,
            action='created',
            reviewer=reviewer,
            old_status=None,
            new_status=status,
            notes=notes,
        )
        conn.commit()
        return {'success': True, 'id': candidate_id, 'status': status}
    finally:
        conn.close()


def get_kb_candidates(gap_id=None, status=None, limit=100):
    """List draft KB candidate patches."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        where = []
        params = []
        if gap_id is not None:
            where.append('gap_id = ?')
            params.append(gap_id)
        if status:
            where.append('status = ?')
            params.append(status)
        where_sql = f"WHERE {' AND '.join(where)}" if where else ''
        cursor.execute(f'''
            SELECT id, gap_id, candidate_patch, status, reviewer, notes, created_at, updated_at
            FROM kb_candidates
            {where_sql}
            ORDER BY created_at DESC
            LIMIT ?
        ''', (*params, limit))
        rows = cursor.fetchall()
    finally:
        conn.close()
    return [{
        'id': row[0],
        'gap_id': row[1],
        'candidate_patch': json.loads(row[2]) if row[2] else {},
        'status': row[3],
        'reviewer': row[4],
        'notes': row[5],
        'created_at': row[6],
        'updated_at': row[7],
    } for row in rows]


def update_kb_candidate_status(candidate_id, status, notes=None):
    """Move a KB candidate through review statuses."""
    if status not in KB_CANDIDATE_STATUSES:
        return {'success': False, 'error': f'Invalid candidate status: {status}'}
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT gap_id, status FROM kb_candidates WHERE id = ?', (candidate_id,))
        row = cursor.fetchone()
        if not row:
            return {'success': False, 'error': 'KB candidate not found'}
        gap_id, old_status = row
        cursor.execute('''
            UPDATE kb_candidates
            SET status = ?, notes = COALESCE(?, notes), updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (status, notes, candidate_id))
        _record_candidate_action(
            cursor,
            candidate_id=candidate_id,
            gap_id=gap_id,
            action='status_changed',
            reviewer='admin',
            old_status=old_status,
            new_status=status,
            notes=notes,
        )
        conn.commit()
        return {'success': True, 'id': candidate_id, 'status': status}
    finally:
        conn.close()


def _record_candidate_action(cursor, candidate_id, gap_id, action, reviewer='admin', old_status=None, new_status=None, notes=None):
    cursor.execute('''
        INSERT INTO kb_candidate_actions
        (candidate_id, gap_id, action, reviewer, old_status, new_status, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (candidate_id, gap_id, action, reviewer, old_status, new_status, notes))


def get_kb_candidate_history(candidate_id):
    """Return candidate audit actions."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT id, candidate_id, gap_id, action, reviewer, old_status, new_status, notes, timestamp
            FROM kb_candidate_actions
            WHERE candidate_id = ?
            ORDER BY timestamp DESC, id DESC
        ''', (candidate_id,))
        rows = cursor.fetchall()
    finally:
        conn.close()
    return [{
        'id': row[0],
        'candidate_id': row[1],
        'gap_id': row[2],
        'action': row[3],
        'reviewer': row[4],
        'old_status': row[5],
        'new_status': row[6],
        'notes': row[7],
        'timestamp': row[8],
    } for row in rows]


def _normalize_key(value):
    return str(value or '').lower().replace('-', '_').replace(' ', '_').strip('_')


def validate_kb_candidate_patch(candidate_patch):
    """Validate whether a candidate patch is safe to apply to products.json."""
    if not isinstance(candidate_patch, dict):
        return ['candidate_patch object']

    missing = []
    category = candidate_patch.get('category')
    if category not in PRODUCT_TARGET_FIELDS:
        missing.append('category (fungicides, herbicides, or insecticides)')

    for field in ['active_ingredient', 'target', 'rate', 'source_url', 'label_review_status']:
        if not candidate_patch.get(field):
            missing.append(field)

    if candidate_patch.get('label_review_status') and candidate_patch.get('label_review_status') not in LABEL_REVIEWED_STATUSES:
        missing.append('label_review_status must indicate human label review')

    if not candidate_patch.get('trade_names') and not candidate_patch.get('product'):
        active_ingredient = candidate_patch.get('active_ingredient')
        if not active_ingredient:
            missing.append('trade_names or product for new/updated record')

    return missing


def _load_products_file():
    with open(PRODUCTS_PATH, 'r', encoding='utf-8') as products_file:
        return json.load(products_file)


def _save_products_file(products):
    with open(PRODUCTS_PATH, 'w', encoding='utf-8') as products_file:
        json.dump(products, products_file, indent=2, sort_keys=False)
        products_file.write('\n')


def _merge_list(record, field, values):
    if values is None:
        return
    if isinstance(values, str):
        values = [values]
    existing = record.setdefault(field, [])
    for value in values:
        if value and value not in existing:
            existing.append(value)


def _candidate_by_id(cursor, candidate_id):
    cursor.execute('''
        SELECT id, gap_id, candidate_patch, status, reviewer, notes
        FROM kb_candidates
        WHERE id = ?
    ''', (candidate_id,))
    row = cursor.fetchone()
    if not row:
        return None
    return {
        'id': row[0],
        'gap_id': row[1],
        'candidate_patch': json.loads(row[2]) if row[2] else {},
        'status': row[3],
        'reviewer': row[4],
        'notes': row[5],
    }


def apply_kb_candidate(candidate_id, reviewer='admin'):
    """Apply a reviewed candidate patch into knowledge/products.json."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        candidate = _candidate_by_id(cursor, candidate_id)
        if not candidate:
            return {'success': False, 'error': 'KB candidate not found'}

        patch = candidate['candidate_patch']
        missing = validate_kb_candidate_patch(patch)
        if missing:
            _record_candidate_action(
                cursor,
                candidate_id=candidate_id,
                gap_id=candidate['gap_id'],
                action='apply_blocked',
                reviewer=reviewer,
                old_status=candidate['status'],
                new_status=candidate['status'],
                notes='Missing or invalid fields: ' + ', '.join(missing),
            )
            conn.commit()
            return {
                'success': False,
                'error': 'Candidate is not safe to apply yet',
                'missing_fields': missing,
            }

        category = patch['category']
        active_ingredient = _normalize_key(patch['active_ingredient'])
        target = _normalize_key(patch['target'])
        target_field = PRODUCT_TARGET_FIELDS[category]
        rate_key = patch.get('rate_key') or (target if category == 'insecticides' else 'standard')

        products = _load_products_file()
        products.setdefault(category, {})
        record = products[category].setdefault(active_ingredient, {
            'trade_names': patch.get('trade_names') or [patch.get('product') or patch['active_ingredient']],
            'rates': {},
            target_field: [],
            'not_for': [],
            'allowed_turf': [],
            'prohibited_turf': [],
            'site_restrictions': [],
        })

        _merge_list(record, 'trade_names', patch.get('trade_names') or patch.get('product'))
        _merge_list(record, target_field, target)
        _merge_list(record, 'allowed_turf', patch.get('allowed_turf'))
        _merge_list(record, 'prohibited_turf', patch.get('prohibited_turf'))
        _merge_list(record, 'site_restrictions', patch.get('site_restrictions'))

        record.setdefault('rates', {})
        if isinstance(patch.get('rates'), dict):
            record['rates'].update(patch['rates'])
        else:
            record['rates'][rate_key] = patch['rate']

        for optional_field in ['frac_code', 'frac_group', 'irac_code', 'irac_group', 'hrac_group', 'resistance_risk', 'note']:
            if patch.get(optional_field) is not None:
                record[optional_field] = patch[optional_field]

        record['verification_status'] = patch.get('verification_status', 'human_label_reviewed')
        record['source_type'] = patch.get('source_type', 'local_label_pdf')
        record['source_url'] = patch['source_url']
        record['label_review_status'] = patch['label_review_status']
        record['source_audit'] = {
            'rate_text_checked': True,
            'target_text_checked': True,
            'checked_at': datetime.utcnow().date().isoformat(),
            'warnings': [],
        }

        _save_products_file(products)

        cursor.execute('''
            UPDATE kb_candidates
            SET status = 'applied_to_kb', updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (candidate_id,))
        _record_candidate_action(
            cursor,
            candidate_id=candidate_id,
            gap_id=candidate['gap_id'],
            action='applied_to_kb',
            reviewer=reviewer,
            old_status=candidate['status'],
            new_status='applied_to_kb',
            notes=f"Updated {category}.{active_ingredient} for {target}.",
        )
        if candidate['gap_id']:
            cursor.execute('''
                UPDATE kb_gaps
                SET status = 'resolved',
                    notes = COALESCE(notes, 'Applied candidate to structured KB'),
                    resolved_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (candidate['gap_id'],))
        conn.commit()
        return {
            'success': True,
            'id': candidate_id,
            'status': 'applied_to_kb',
            'category': category,
            'active_ingredient': active_ingredient,
            'target': target,
            'target_field': target_field,
        }
    finally:
        conn.close()


def bulk_resolve_kb_gaps(gap_ids, status='resolved', notes=None):
    """Bulk resolve, ignore, or reopen KB gap work items."""
    allowed = {'resolved', 'ignored', 'open'}
    if status not in allowed:
        return {'success': False, 'error': f'Invalid status: {status}'}
    if not isinstance(gap_ids, list) or not gap_ids:
        return {'success': False, 'error': 'gap_ids must be a non-empty list'}

    clean_ids = [int(gap_id) for gap_id in gap_ids]
    placeholders = ','.join('?' for _ in clean_ids)
    resolved_expr = 'CURRENT_TIMESTAMP' if status in {'resolved', 'ignored'} else 'NULL'
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(f'''
            UPDATE kb_gaps
            SET status = ?, notes = COALESCE(?, notes), resolved_at = {resolved_expr}
            WHERE id IN ({placeholders})
        ''', (status, notes, *clean_ids))
        conn.commit()
        return {'success': True, 'updated': cursor.rowcount, 'status': status}
    finally:
        conn.close()


def create_kb_regression_test(gap_id, candidate_id=None, expected_kb_verdict=None):
    """Capture a gap question as a future deterministic regression check."""
    detail = get_kb_gap_detail(gap_id)
    if not detail:
        return {'success': False, 'error': 'KB gap not found'}

    verdict = expected_kb_verdict or (
        'verified_surface_target_options'
        if detail.get('gap_type') in {'missing_surface_target_product', 'surface_target_gap'}
        else 'verified'
    )

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT id, status
            FROM kb_regression_tests
            WHERE gap_id = ? AND question = ? AND expected_kb_verdict = ?
            ORDER BY created_at DESC, id DESC
            LIMIT 1
        ''', (gap_id, detail.get('question'), verdict))
        existing = cursor.fetchone()
        if existing:
            return {
                'success': True,
                'id': existing[0],
                'expected_kb_verdict': verdict,
                'deduplicated': True,
                'status': existing[1],
            }

        cursor.execute('''
            INSERT INTO kb_regression_tests
            (gap_id, candidate_id, question, expected_kb_verdict, expected_target, expected_surface, expected_product)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            gap_id,
            candidate_id,
            detail.get('question'),
            verdict,
            detail.get('target'),
            detail.get('surface'),
            detail.get('product'),
        ))
        test_id = cursor.lastrowid
        conn.commit()
        return {'success': True, 'id': test_id, 'expected_kb_verdict': verdict}
    finally:
        conn.close()


def get_kb_regression_tests(status='active', limit=100):
    """List captured KB regression questions."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        where = 'WHERE status = ?' if status != 'all' else ''
        params = [status] if status != 'all' else []
        cursor.execute(f'''
            SELECT id, gap_id, candidate_id, question, expected_kb_verdict,
                   expected_target, expected_surface, expected_product, status,
                   created_at, last_result, last_run_at
            FROM kb_regression_tests
            {where}
            ORDER BY created_at DESC
            LIMIT ?
        ''', (*params, limit))
        rows = cursor.fetchall()
    finally:
        conn.close()
    return [{
        'id': row[0],
        'gap_id': row[1],
        'candidate_id': row[2],
        'question': row[3],
        'expected_kb_verdict': row[4],
        'expected_target': row[5],
        'expected_surface': row[6],
        'expected_product': row[7],
        'status': row[8],
        'created_at': row[9],
        'last_result': json.loads(row[10]) if row[10] else None,
        'last_run_at': row[11],
    } for row in rows]


def resolve_kb_gap(gap_id, status='resolved', notes=None):
    """Resolve, ignore, or reopen a KB gap."""
    allowed = {'resolved', 'ignored', 'open'}
    if status not in allowed:
        return {'success': False, 'error': f'Invalid status: {status}'}

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        resolved_expr = 'CURRENT_TIMESTAMP' if status in {'resolved', 'ignored'} else 'NULL'
        cursor.execute(f'''
            UPDATE kb_gaps
            SET status = ?, notes = COALESCE(?, notes), resolved_at = {resolved_expr}
            WHERE id = ?
        ''', (status, notes, gap_id))
        conn.commit()
        if cursor.rowcount == 0:
            return {'success': False, 'error': 'KB gap not found'}
        return {'success': True, 'id': gap_id, 'status': status}
    finally:
        conn.close()


def retire_matching_open_kb_gaps(question, notes=None):
    """Mark older open KB gaps for a question as resolved when the app now handles it deterministically."""
    if not question:
        return {'success': False, 'updated': 0}

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            UPDATE kb_gaps
            SET status = 'resolved',
                notes = COALESCE(?, notes),
                resolved_at = CURRENT_TIMESTAMP
            WHERE status = 'open' AND question = ?
        ''', (notes, question))
        conn.commit()
        return {'success': True, 'updated': cursor.rowcount}
    finally:
        conn.close()


def get_queries_needing_review(limit=100):
    """Get queries flagged for human review (confidence < 70% or grounding issues)"""
    if _feedback_runtime_uses_dynamodb():
        items = [
            item for item in _load_feedback_items()
            if not item.get('reviewed') and (
                item.get('needs_review')
                or (
                    item.get('confidence_score') is not None
                    and item.get('confidence_score') < 70
                )
            )
        ][:limit]
        return [{
            'id': item.get('id'),
            'question': item.get('question'),
            'ai_answer': item.get('ai_answer'),
            'confidence': item.get('confidence_score'),
            'sources': item.get('sources') or [],
            'timestamp': item.get('timestamp'),
        } for item in items]
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Check if needs_review column exists
    try:
        cursor.execute('''
            SELECT id, question, ai_answer, confidence_score, sources, timestamp
            FROM feedback
            WHERE needs_review = 1 AND reviewed = 0
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (limit,))
    except sqlite3.OperationalError:
        # Fallback to confidence-based query if column doesn't exist
        cursor.execute('''
            SELECT id, question, ai_answer, confidence_score, sources, timestamp
            FROM feedback
            WHERE confidence_score < 70 AND reviewed = 0
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (limit,))

    results = cursor.fetchall()
    conn.close()

    queries = []
    for row in results:
        queries.append({
            'id': row[0],
            'question': row[1],
            'ai_answer': row[2],
            'confidence': row[3],
            'sources': json.loads(row[4]) if row[4] else [],
            'timestamp': row[5]
        })

    return queries


def update_query_rating(question, rating, correction=None, feedback_id=None):
    """Update an existing unrated query with the user's rating.

    Returns the updated row id when a matching query was found.
    """
    if _feedback_runtime_uses_dynamodb():
        target = None
        if feedback_id:
            target = _load_feedback_item_by_id(feedback_id, expected_type='feedback')
            if target and target.get('user_rating') != 'unrated':
                target = None
        if target is None:
            items = [
                item for item in _load_feedback_items()
                if item.get('question') == question and item.get('user_rating') == 'unrated'
            ]
            if not items:
                return None
            target = items[0]
        target['user_rating'] = rating
        target['user_correction'] = correction
        _save_feedback_item(target)
        return target['id']
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    if feedback_id is not None:
        cursor.execute('''
            SELECT id FROM feedback
            WHERE id = ? AND user_rating = 'unrated'
            LIMIT 1
        ''', (feedback_id,))
    else:
        cursor.execute('''
            SELECT id FROM feedback
            WHERE question = ? AND user_rating = 'unrated'
            ORDER BY timestamp DESC LIMIT 1
        ''', (question,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None

    feedback_id = row[0]
    cursor.execute('''
        UPDATE feedback
        SET user_rating = ?, user_correction = ?
        WHERE id = ?
    ''', (rating, correction, feedback_id))

    conn.commit()
    conn.close()
    return feedback_id

def get_negative_feedback(limit=50, unreviewed_only=True):
    """Get feedback that needs review"""
    if _feedback_runtime_uses_dynamodb():
        items = [
            item for item in _load_feedback_items()
            if item.get('user_rating') == 'negative'
            and (not unreviewed_only or not item.get('reviewed'))
        ][:limit]
        return [
            {
                'id': item.get('id'),
                'question': item.get('question'),
                'ai_answer': item.get('ai_answer'),
                'user_correction': item.get('user_correction'),
                'timestamp': item.get('timestamp'),
            }
            for item in items
        ]
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    query = '''
        SELECT id, question, ai_answer, user_correction, timestamp
        FROM feedback
        WHERE user_rating = 'negative'
    '''
    
    if unreviewed_only:
        query += ' AND reviewed = 0'
    
    query += ' ORDER BY timestamp DESC LIMIT ?'
    
    cursor.execute(query, (limit,))
    results = cursor.fetchall()
    conn.close()
    
    feedback_items = []
    for row in results:
        feedback_items.append({
            'id': row[0],
            'question': row[1],
            'ai_answer': row[2],
            'user_correction': row[3],
            'timestamp': row[4]
        })
    
    return feedback_items

def approve_for_training(feedback_id, ideal_answer, moderator='admin'):
    """Approve feedback and create training example"""
    if _feedback_runtime_uses_dynamodb():
        item = _load_feedback_item_by_id(feedback_id, expected_type='feedback')
        if not item:
            return False
        question = item.get('question')
        ai_answer = item.get('ai_answer')
        ideal_answer = ideal_answer or ai_answer
        item['reviewed'] = True
        item['approved_for_training'] = True
        _save_feedback_item(item)
        _save_training_example_item(
            feedback_id,
            question,
            ideal_answer,
            created_at=item.get('timestamp'),
        )
        _save_moderator_action_item(
            feedback_id,
            'approve',
            moderator=moderator,
            original_answer=ai_answer,
            corrected_answer=ideal_answer if ideal_answer != ai_answer else None,
            reason='Approved for training',
        )
        return True
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()

        # Get original question
        cursor.execute('SELECT question, ai_answer FROM feedback WHERE id = ?', (feedback_id,))
        row = cursor.fetchone()
        if not row:
            return False

        question, ai_answer = row
        ideal_answer = ideal_answer or ai_answer

        # Mark feedback as reviewed and approved
        cursor.execute('''
            UPDATE feedback
            SET reviewed = 1, approved_for_training = 1
            WHERE id = ?
        ''', (feedback_id,))

        _create_training_example_if_missing(cursor, feedback_id, question, ideal_answer)

        conn.commit()
        return True
    finally:
        conn.close()

def reject_feedback(feedback_id, notes=None, moderator='admin'):
    """Mark feedback as reviewed but not approved"""
    if _feedback_runtime_uses_dynamodb():
        item = _load_feedback_item_by_id(feedback_id, expected_type='feedback')
        if not item:
            return False
        item['reviewed'] = True
        item['approved_for_training'] = False
        if notes is not None:
            item['notes'] = notes
        _save_feedback_item(item)
        _save_moderator_action_item(
            feedback_id,
            'reject',
            moderator=moderator,
            original_answer=item.get('ai_answer'),
            corrected_answer=None,
            reason=notes,
        )
        return True
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE feedback
            SET reviewed = 1, approved_for_training = 0, notes = ?
            WHERE id = ?
        ''', (notes, feedback_id))

        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()

def get_training_examples(unused_only=True, limit=1000):
    """Get training examples ready for fine-tuning"""
    examples = _load_training_example_items(unused_only=unused_only, limit=limit)
    return [{
        'id': item.get('id'),
        'question': item.get('question'),
        'ideal_answer': item.get('ideal_answer'),
    } for item in examples]

def generate_training_file(output_path='feedback_training.jsonl', min_examples=50):
    """Generate JSONL training file from approved feedback"""
    examples = get_training_examples(unused_only=True)
    
    if len(examples) < min_examples:
        print(f"⚠️  Only {len(examples)} examples available. Need at least {min_examples} for training.")
        return None
    
    with open(output_path, 'w') as f:
        for ex in examples:
            training_obj = {
                "messages": [
                    {"role": "system", "content": "You are a specialized expert in turfgrass science."},
                    {"role": "user", "content": ex['question']},
                    {"role": "assistant", "content": ex['ideal_answer']}
                ]
            }
            f.write(json.dumps(training_obj) + '\n')
    
    print(f"✅ Generated training file: {output_path}")
    print(f"   Examples: {len(examples)}")
    
    return output_path, len(examples)

def mark_examples_used(run_id):
    """Mark training examples as used in a training run"""
    if _feedback_runtime_uses_dynamodb():
        examples = _load_training_example_items(unused_only=True, limit=None)
        for item in examples:
            item['used_in_training'] = True
            item['training_run_id'] = run_id
            _save_feedback_item(item)
        return
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE training_examples 
        SET used_in_training = 1, training_run_id = ?
        WHERE used_in_training = 0
    ''', (run_id,))
    
    conn.commit()
    conn.close()

def create_training_run(run_id, num_examples, notes=None):
    """Record a new training run"""
    if _feedback_runtime_uses_dynamodb():
        _save_training_run_item(
            run_id,
            num_examples=num_examples,
            status='started',
            notes=notes,
            model_id=None,
            completed=False,
        )
        return
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO training_runs (run_id, num_examples, status, notes)
        VALUES (?, ?, 'started', ?)
    ''', (run_id, num_examples, notes))
    
    conn.commit()
    conn.close()

def update_training_run(run_id, status, model_id=None):
    """Update training run status"""
    if _feedback_runtime_uses_dynamodb():
        _save_training_run_item(
            run_id,
            status=status,
            model_id=model_id,
            completed=(status == 'completed'),
        )
        return
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    if status == 'completed':
        cursor.execute('''
            UPDATE training_runs 
            SET status = ?, model_id = ?, completed_at = CURRENT_TIMESTAMP
            WHERE run_id = ?
        ''', (status, model_id, run_id))
    else:
        cursor.execute('''
            UPDATE training_runs 
            SET status = ?
            WHERE run_id = ?
        ''', (status, run_id))
    
    conn.commit()
    conn.close()

def get_review_queue(limit=100, queue_type='all'):
    """Get unified review queue: user-flagged negative + auto-flagged low-confidence"""
    if queue_type == 'all':
        rows = _exclude_eval_feedback(_load_feedback_records(limit=None))
        if limit is not None:
            rows = rows[:limit]
        items = []
        for row in rows:
            rating = row.get('user_rating')
            if rating == 'negative':
                review_type = 'user_flagged'
            elif rating == 'unrated':
                review_type = 'no_feedback'
            else:
                review_type = 'auto_flagged'
            items.append({
                'id': row.get('id'),
                'question': row.get('question'),
                'ai_answer': row.get('ai_answer'),
                'user_correction': row.get('user_correction'),
                'confidence': row.get('confidence_score'),
                'sources': row.get('sources') or [],
                'attachment': row.get('attachment'),
                'timestamp': row.get('timestamp'),
                'rating': rating,
                'needs_review': bool(row.get('needs_review')),
                'reviewed': bool(row.get('reviewed')),
                'approved_for_training': bool(row.get('approved_for_training')),
                'review_type': review_type,
            })
        return items

    raw_limit = _review_queue_raw_limit(limit)
    if _feedback_runtime_uses_dynamodb():
        items = [
            item for item in _load_feedback_items()
            if not item.get('reviewed') and not _is_eval_feedback_item(item)
        ]
        if queue_type == 'negative':
            items = [item for item in items if item.get('user_rating') == 'negative']
        elif queue_type == 'low_confidence':
            items = [item for item in items if item.get('needs_review') and item.get('user_rating') != 'negative']
            items.sort(key=lambda item: (item.get('confidence_score') if item.get('confidence_score') is not None else 999, item.get('timestamp') or '' ))
        else:
            items = [item for item in items if item.get('user_rating') == 'negative' or item.get('needs_review')]
            items.sort(key=lambda item: (
                0 if item.get('user_rating') == 'negative' else 1,
                item.get('confidence_score') if item.get('confidence_score') is not None else 999,
                item.get('timestamp') or '',
            ))
        if limit is not None:
            items = items[:raw_limit]
        output = []
        for item in items:
            rating = item.get('user_rating')
            if rating == 'negative':
                review_type = 'user_flagged'
            elif rating == 'unrated':
                review_type = 'no_feedback'
            else:
                review_type = 'auto_flagged'
            output.append({
                'id': item.get('id'),
                'question': item.get('question'),
                'ai_answer': item.get('ai_answer'),
                'user_correction': item.get('user_correction'),
                'confidence': item.get('confidence_score'),
                'sources': item.get('sources') or [],
                'attachment': item.get('attachment'),
                'failure_tags': item.get('failure_tags') or [],
                'timestamp': item.get('timestamp'),
                'rating': rating,
                'needs_review': bool(item.get('needs_review')),
                'review_type': review_type,
            })
        return _deduplicate_review_queue_items(output, limit=limit)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Ensure needs_review column exists
    try:
        cursor.execute('SELECT needs_review FROM feedback LIMIT 1')
    except sqlite3.OperationalError:
        cursor.execute('ALTER TABLE feedback ADD COLUMN needs_review BOOLEAN DEFAULT 0')
    try:
        cursor.execute('SELECT attachment_json FROM feedback LIMIT 1')
    except sqlite3.OperationalError:
        cursor.execute('ALTER TABLE feedback ADD COLUMN attachment_json TEXT')
    try:
        cursor.execute('SELECT failure_tags_json FROM feedback LIMIT 1')
    except sqlite3.OperationalError:
        cursor.execute('ALTER TABLE feedback ADD COLUMN failure_tags_json TEXT')

    if queue_type == 'negative':
        # Only user-flagged negative feedback
            cursor.execute('''
            SELECT id, question, ai_answer, user_correction, confidence_score,
                   sources, timestamp, user_rating, needs_review, attachment_json, failure_tags_json
            FROM feedback
            WHERE user_rating = 'negative' AND reviewed = 0
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (raw_limit,))
    elif queue_type == 'low_confidence':
        # Only auto-flagged low-confidence
        cursor.execute('''
            SELECT id, question, ai_answer, user_correction, confidence_score,
                   sources, timestamp, user_rating, needs_review, attachment_json, failure_tags_json
            FROM feedback
            WHERE needs_review = 1 AND reviewed = 0 AND user_rating != 'negative'
            ORDER BY confidence_score ASC, timestamp DESC
            LIMIT ?
        ''', (raw_limit,))
    else:
        # All items needing review (both types)
        cursor.execute('''
            SELECT id, question, ai_answer, user_correction, confidence_score,
                   sources, timestamp, user_rating, needs_review, attachment_json, failure_tags_json
            FROM feedback
            WHERE (user_rating = 'negative' OR needs_review = 1) AND reviewed = 0
            ORDER BY
                CASE WHEN user_rating = 'negative' THEN 0 ELSE 1 END,
                confidence_score ASC,
                timestamp DESC
            LIMIT ?
        ''', (raw_limit,))

    results = cursor.fetchall()
    conn.close()

    items = []
    for row in results:
        rating = row[7]
        # Determine review type based on user feedback
        if rating == 'negative':
            review_type = 'user_flagged'
        elif rating == 'unrated':
            review_type = 'no_feedback'
        else:
            review_type = 'auto_flagged'  # positive rating but low confidence

        items.append({
            'id': row[0],
            'question': row[1],
            'ai_answer': row[2],
            'user_correction': row[3],
            'confidence': row[4],
            'sources': json.loads(row[5]) if row[5] else [],
            'timestamp': row[6],
            'rating': rating,
            'needs_review': bool(row[8]),
            'attachment': json.loads(row[9]) if row[9] else None,
            'failure_tags': json.loads(row[10]) if len(row) > 10 and row[10] else [],
            'review_type': review_type
        })
    items = _exclude_eval_feedback(items)
    return _deduplicate_review_queue_items(items, limit=limit)


def moderate_answer(feedback_id, action, corrected_answer=None, reason=None, moderator='admin'):
    """Moderate a feedback item: approve, reject, or correct"""
    if _feedback_runtime_uses_dynamodb():
        item = _load_feedback_item_by_id(feedback_id, expected_type='feedback')
        if not item:
            return {'success': False, 'error': 'Feedback not found'}

        question = item.get('question')
        original_answer = item.get('ai_answer')

        if action == 'approve':
            ideal_answer = corrected_answer if corrected_answer else original_answer
            item['reviewed'] = True
            item['approved_for_training'] = True
            if reason is not None:
                item['notes'] = reason
            _save_feedback_item(item)
            _save_training_example_item(
                feedback_id,
                question,
                ideal_answer,
                created_at=item.get('timestamp'),
            )
            _save_moderator_action_item(
                feedback_id,
                'approve',
                moderator=moderator,
                original_answer=original_answer,
                corrected_answer=corrected_answer,
                reason=reason,
            )
        elif action == 'reject':
            item['reviewed'] = True
            item['approved_for_training'] = False
            item['notes'] = reason or 'Rejected by moderator'
            _save_feedback_item(item)
            _save_moderator_action_item(
                feedback_id,
                'reject',
                moderator=moderator,
                original_answer=original_answer,
                corrected_answer=None,
                reason=reason,
            )
        elif action == 'correct':
            item['user_correction'] = corrected_answer
            item['notes'] = reason
            _save_feedback_item(item)
            _save_moderator_action_item(
                feedback_id,
                'correct',
                moderator=moderator,
                original_answer=original_answer,
                corrected_answer=corrected_answer,
                reason=reason,
            )
        else:
            return {'success': False, 'error': 'Invalid moderation action'}
        return {'success': True, 'action': action}

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get original answer
    cursor.execute('SELECT question, ai_answer FROM feedback WHERE id = ?', (feedback_id,))
    result = cursor.fetchone()
    if not result:
        conn.close()
        return {'success': False, 'error': 'Feedback not found'}

    question, original_answer = result

    # Log the moderation action
    cursor.execute('''
        INSERT INTO moderator_actions
        (feedback_id, action, moderator, original_answer, corrected_answer, reason)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (feedback_id, action, moderator, original_answer, corrected_answer, reason))

    if action == 'approve':
        # Use correction if provided, otherwise use original answer
        ideal_answer = corrected_answer if corrected_answer else original_answer

        # Mark as reviewed and approved
        cursor.execute('''
            UPDATE feedback
            SET reviewed = 1, approved_for_training = 1, notes = ?
            WHERE id = ?
        ''', (reason, feedback_id))

        # Create training example
        _create_training_example_if_missing(cursor, feedback_id, question, ideal_answer)

    elif action == 'reject':
        # Mark as reviewed but not approved
        cursor.execute('''
            UPDATE feedback
            SET reviewed = 1, approved_for_training = 0, notes = ?
            WHERE id = ?
        ''', (reason or 'Rejected by moderator', feedback_id))

    elif action == 'correct':
        # Save correction for later approval
        cursor.execute('''
            UPDATE feedback
            SET user_correction = ?, notes = ?
            WHERE id = ?
        ''', (corrected_answer, reason, feedback_id))

    conn.commit()
    conn.close()

    return {'success': True, 'action': action}


def get_moderator_history(limit=100):
    """Get audit trail of moderator actions"""
    history = _load_moderator_action_items(limit=limit)
    return [{
        'id': item.get('id'),
        'feedback_id': item.get('feedback_id'),
        'action': item.get('action'),
        'moderator': item.get('moderator'),
        'original_answer': (item.get('original_answer')[:200] + '...') if item.get('original_answer') and len(item.get('original_answer')) > 200 else item.get('original_answer'),
        'corrected_answer': (item.get('corrected_answer')[:200] + '...') if item.get('corrected_answer') and len(item.get('corrected_answer')) > 200 else item.get('corrected_answer'),
        'reason': item.get('reason'),
        'timestamp': item.get('timestamp'),
        'question': (item.get('question')[:100] + '...') if item.get('question') and len(item.get('question')) > 100 else item.get('question'),
    } for item in history]


def get_feedback_stats():
    """Get statistics about feedback"""
    items = _exclude_eval_feedback(_load_feedback_records(limit=None))
    stats = {}
    today_prefix = datetime.now(timezone.utc).date().isoformat()
    stats['total_feedback'] = len(items)
    stats['today_count'] = sum(1 for item in items if str(item.get('timestamp') or '').startswith(today_prefix))
    ratings = {}
    for item in items:
        rating = item.get('user_rating')
        if rating:
            ratings[rating] = ratings.get(rating, 0) + 1
    for rating, count in ratings.items():
        stats[f'{rating}_feedback'] = count
    stats['unreviewed_negative'] = sum(
        1 for item in items if item.get('user_rating') == 'negative' and not item.get('reviewed')
    )
    stats['approved_for_training'] = sum(1 for item in items if item.get('approved_for_training'))
    stats['examples_ready'] = len(_load_training_example_items(unused_only=True, limit=None))
    stats['training_runs'] = len(_load_feedback_items_by_type('training_run')) if _feedback_runtime_uses_dynamodb() else _count_local_training_runs()
    conf_values = [item.get('confidence_score') for item in items if item.get('confidence_score') is not None]
    stats['avg_confidence'] = round(sum(conf_values) / len(conf_values), 1) if conf_values else None
    high = sum(1 for value in conf_values if value >= 80)
    medium = sum(1 for value in conf_values if 60 <= value < 80)
    low = sum(1 for value in conf_values if value < 60)
    stats['confidence_distribution'] = {'high': high, 'medium': medium, 'low': low}
    stats['auto_approved'] = sum(1 for value in conf_values if value >= 70)
    stats['flagged_for_review'] = sum(1 for value in conf_values if value < 70)
    stats['pending_review'] = sum(
        1 for item in items if item.get('needs_review') and not item.get('reviewed')
    )
    stats['eval_traffic_count'] = len(_include_only_eval_feedback(_load_feedback_records(limit=None)))
    return stats


def get_action_center_summary():
    """Return lightweight summary counts for the admin action center."""
    summary = {
        'pending_review': sum(
            1 for item in _exclude_eval_feedback(_load_feedback_records(limit=None))
            if item.get('needs_review') and not item.get('reviewed')
        ),
        'open_kb_gaps': 0,
        'router_needs_review': 0,
        'open_work_items': 0,
        'eval_traffic_count': len(_include_only_eval_feedback(_load_feedback_records(limit=None))),
    }
    if _feedback_runtime_uses_dynamodb():
        summary['open_kb_gaps'] = len(get_kb_gaps(status='open', limit=None))
        summary['router_needs_review'] = len(get_expert_router_events(limit=500, needs_review=True))
        summary['open_work_items'] = len(get_expert_router_work_items(status='open', limit=100))
        return summary

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        try:
            cursor.execute("SELECT COUNT(*) FROM kb_gaps WHERE status = 'open'")
            summary['open_kb_gaps'] = cursor.fetchone()[0]
        except sqlite3.OperationalError:
            summary['open_kb_gaps'] = 0
        try:
            cursor.execute('SELECT COUNT(*) FROM expert_router_events WHERE needs_review = 1')
            summary['router_needs_review'] = cursor.fetchone()[0]
        except sqlite3.OperationalError:
            summary['router_needs_review'] = 0
        try:
            cursor.execute("SELECT COUNT(*) FROM expert_router_work_items WHERE status = 'open'")
            summary['open_work_items'] = cursor.fetchone()[0]
        except sqlite3.OperationalError:
            summary['open_work_items'] = 0
    finally:
        conn.close()
    return summary


# =============================================================================
# BULK OPERATIONS
# =============================================================================

def bulk_moderate(feedback_ids, action, reason=None, moderator='admin'):
    """Bulk approve or reject multiple feedback items"""
    if _feedback_runtime_uses_dynamodb():
        results = {'success': 0, 'failed': 0, 'errors': []}
        for feedback_id in feedback_ids:
            result = moderate_answer(feedback_id, action, None, reason, moderator=moderator)
            if result.get('success'):
                results['success'] += 1
            else:
                results['failed'] += 1
                results['errors'].append(f"ID {feedback_id}: {result.get('error', 'Unknown error')}")
        return results
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    results = {'success': 0, 'failed': 0, 'errors': []}

    for feedback_id in feedback_ids:
        try:
            # Get original data
            cursor.execute('SELECT question, ai_answer FROM feedback WHERE id = ?', (feedback_id,))
            result = cursor.fetchone()
            if not result:
                results['failed'] += 1
                results['errors'].append(f"ID {feedback_id} not found")
                continue

            question, original_answer = result

            # Log the action
            cursor.execute('''
                INSERT INTO moderator_actions
                (feedback_id, action, moderator, original_answer, reason)
                VALUES (?, ?, ?, ?, ?)
            ''', (feedback_id, action, moderator, original_answer, reason or f'Bulk {action}'))

            if action == 'approve':
                cursor.execute('''
                    UPDATE feedback
                    SET reviewed = 1, approved_for_training = 1, notes = ?
                    WHERE id = ?
                ''', (reason or 'Bulk approved', feedback_id))

                # Create training example
                _create_training_example_if_missing(cursor, feedback_id, question, original_answer)

            elif action == 'reject':
                cursor.execute('''
                    UPDATE feedback
                    SET reviewed = 1, approved_for_training = 0, notes = ?
                    WHERE id = ?
                ''', (reason or 'Bulk rejected', feedback_id))

            results['success'] += 1

        except Exception as e:
            results['failed'] += 1
            results['errors'].append(f"ID {feedback_id}: {str(e)}")

    conn.commit()
    conn.close()

    return results


def bulk_approve_high_confidence(min_confidence=80, limit=100, moderator='admin'):
    """Auto-approve all high-confidence items that haven't been reviewed"""
    if _feedback_runtime_uses_dynamodb():
        ids = [
            item.get('id')
            for item in _load_feedback_records()
            if item.get('confidence_score') is not None
            and item.get('confidence_score') >= min_confidence
            and not item.get('reviewed')
            and item.get('user_rating') != 'negative'
        ][:limit]
    else:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id FROM feedback
            WHERE confidence_score >= ? AND reviewed = 0 AND user_rating != 'negative'
            LIMIT ?
        ''', (min_confidence, limit))
        ids = [row[0] for row in cursor.fetchall()]
        conn.close()

    if not ids:
        return {'success': 0, 'failed': 0, 'message': 'No items to approve'}

    result = bulk_moderate(
        ids,
        'approve',
        f'Auto-approved (confidence >= {min_confidence}%)',
        moderator=moderator,
    )
    result['message'] = f'Processed {len(ids)} high-confidence items'
    return result


# =============================================================================
# EXPORT FUNCTIONS
# =============================================================================

def export_feedback_csv():
    """Export all feedback to CSV format"""
    rows = _load_feedback_records(limit=None)

    # Build CSV
    import csv
    import io

    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        'ID', 'Question', 'AI Answer', 'User Rating', 'User Correction',
        'Confidence', 'Timestamp', 'Reviewed', 'Approved for Training', 'Notes'
    ])

    for row in rows:
        writer.writerow([
            row.get('id'),
            row.get('question'),
            row.get('ai_answer'),
            row.get('user_rating'),
            row.get('user_correction'),
            row.get('confidence_score'),
            row.get('timestamp'),
            row.get('reviewed'),
            row.get('approved_for_training'),
            row.get('notes'),
        ])

    return output.getvalue()


def export_training_examples_csv():
    """Export training examples to CSV format"""
    examples = _load_training_example_items(unused_only=False, limit=None)
    feedback_by_id = {str(item.get('id')): item for item in _load_feedback_records(limit=None)}

    import csv
    import io

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        'ID', 'Question', 'Ideal Answer', 'Created At', 'Used in Training', 'Original Confidence'
    ])

    for row in examples:
        feedback = feedback_by_id.get(str(row.get('feedback_id')))
        writer.writerow([
            row.get('id'),
            row.get('question'),
            row.get('ideal_answer'),
            row.get('created_at'),
            row.get('used_in_training'),
            feedback.get('confidence_score') if feedback else None,
        ])

    return output.getvalue()


def export_moderation_history_csv():
    """Export moderator actions to CSV"""
    rows = _load_moderator_action_items(limit=None)

    import csv
    import io

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        'ID', 'Feedback ID', 'Action', 'Moderator', 'Reason', 'Timestamp', 'Question'
    ])

    for row in rows:
        writer.writerow([
            row.get('id'),
            row.get('feedback_id'),
            row.get('action'),
            row.get('moderator'),
            row.get('reason'),
            row.get('timestamp'),
            row.get('question'),
        ])

    return output.getvalue()


def export_analytics_json():
    """Export comprehensive analytics data"""
    stats = get_feedback_stats()
    feedback_items = _load_feedback_records(limit=None)
    cutoff = datetime.now(timezone.utc).date().toordinal() - 30
    recent_items = []
    for item in feedback_items:
        timestamp = item.get('timestamp')
        if not timestamp:
            continue
        try:
            item_date = datetime.fromisoformat(str(timestamp).replace('Z', '+00:00')).date()
        except ValueError:
            continue
        if item_date.toordinal() >= cutoff:
            recent_items.append((item_date.isoformat(), item))

    daily_counts_map = {}
    daily_ratings = {}
    confidence_by_day = {}
    for day, item in recent_items:
        daily_counts_map[day] = daily_counts_map.get(day, 0) + 1

        rating = item.get('user_rating')
        if rating:
            daily_ratings.setdefault(day, {})
            daily_ratings[day][rating] = daily_ratings[day].get(rating, 0) + 1

        confidence = item.get('confidence_score')
        if confidence is not None:
            confidence_by_day.setdefault(day, []).append(confidence)

    daily_counts = [
        {'date': day, 'count': daily_counts_map[day]}
        for day in sorted(daily_counts_map)
    ]
    confidence_trend = [
        {'date': day, 'avg_confidence': round(sum(values) / len(values), 1)}
        for day, values in sorted(confidence_by_day.items())
    ]

    return {
        'stats': stats,
        'daily_counts': daily_counts,
        'daily_ratings': daily_ratings,
        'confidence_trend': confidence_trend,
        'exported_at': datetime.now().isoformat()
    }


# =============================================================================
# PRIORITY QUEUE WITH FREQUENCY DETECTION
# =============================================================================

def get_question_frequencies(limit=50):
    """Find frequently asked questions (potential problem areas)"""
    if _feedback_runtime_uses_dynamodb():
        grouped = {}
        for item in _load_feedback_items():
            normalized_q = (item.get('question') or '').strip().lower()
            if not normalized_q:
                continue
            bucket = grouped.setdefault(normalized_q, {
                'frequency': 0,
                'confidences': [],
                'negative_count': 0,
                'ids': [],
            })
            bucket['frequency'] += 1
            if item.get('confidence_score') is not None:
                bucket['confidences'].append(item.get('confidence_score'))
            if item.get('user_rating') == 'negative':
                bucket['negative_count'] += 1
            bucket['ids'].append(item.get('id'))

        frequencies = []
        for question, bucket in grouped.items():
            if bucket['frequency'] < 2:
                continue
            avg_confidence = (
                round(sum(bucket['confidences']) / len(bucket['confidences']), 1)
                if bucket['confidences'] else None
            )
            frequencies.append({
                'question': question,
                'frequency': bucket['frequency'],
                'avg_confidence': avg_confidence,
                'negative_count': bucket['negative_count'],
                'ids': bucket['ids'],
                'priority_score': _calculate_priority_score(
                    bucket['frequency'],
                    avg_confidence,
                    bucket['negative_count'],
                ),
            })
        frequencies.sort(key=lambda item: item['priority_score'], reverse=True)
        return frequencies[:limit]

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Use fuzzy matching by normalizing questions
    cursor.execute('''
        SELECT LOWER(TRIM(question)) as normalized_q,
               COUNT(*) as frequency,
               AVG(confidence_score) as avg_confidence,
               SUM(CASE WHEN user_rating = 'negative' THEN 1 ELSE 0 END) as negative_count,
               GROUP_CONCAT(id) as ids
        FROM feedback
        GROUP BY normalized_q
        HAVING COUNT(*) >= 2
        ORDER BY frequency DESC, avg_confidence ASC
        LIMIT ?
    ''', (limit,))

    results = cursor.fetchall()
    conn.close()

    frequencies = []
    for row in results:
        frequencies.append({
            'question': row[0],
            'frequency': row[1],
            'avg_confidence': round(row[2], 1) if row[2] else None,
            'negative_count': row[3],
            'ids': [int(x) for x in row[4].split(',')] if row[4] else [],
            'priority_score': _calculate_priority_score(row[1], row[2], row[3])
        })

    return sorted(frequencies, key=lambda x: x['priority_score'], reverse=True)


def _calculate_priority_score(frequency, avg_confidence, negative_count):
    """Calculate priority score for a question cluster"""
    score = 0

    # Frequency boost (more asks = higher priority)
    score += min(frequency * 10, 50)

    # Low confidence penalty
    if avg_confidence:
        if avg_confidence < 50:
            score += 30
        elif avg_confidence < 70:
            score += 15

    # Negative feedback boost
    score += negative_count * 20

    return score


def get_priority_review_queue(limit=100):
    """Get review queue sorted by priority (frequency + confidence + negative feedback)"""
    raw_limit = _review_queue_raw_limit(limit)
    if _feedback_runtime_uses_dynamodb():
        freq_map = {}
        for item in _load_feedback_items():
            if _is_eval_feedback_item(item):
                continue
            normalized_q = (item.get('question') or '').strip().lower()
            if not normalized_q:
                continue
            freq_map[normalized_q] = freq_map.get(normalized_q, 0) + 1

        items = []
        for item in _load_feedback_items():
            if item.get('reviewed') or _is_eval_feedback_item(item):
                continue
            rating = item.get('user_rating')
            if rating != 'negative' and not item.get('needs_review'):
                continue

            question = item.get('question') or ''
            normalized_q = question.strip().lower()
            frequency = freq_map.get(normalized_q, 1)
            confidence = item.get('confidence_score')

            priority = 0
            if rating == 'negative':
                priority += 50
            if confidence is not None and confidence < 50:
                priority += 30
            elif confidence is not None and confidence < 70:
                priority += 15
            priority += min(frequency * 5, 25)

            if rating == 'negative':
                review_type = 'user_flagged'
            elif rating == 'unrated':
                review_type = 'no_feedback'
            else:
                review_type = 'auto_flagged'

            items.append({
                'id': item.get('id'),
                'question': question,
                'ai_answer': item.get('ai_answer'),
                'user_correction': item.get('user_correction'),
                'confidence': confidence,
                'sources': item.get('sources') or [],
                'timestamp': item.get('timestamp'),
                'rating': rating,
                'needs_review': bool(item.get('needs_review')),
                'review_type': review_type,
                'frequency': frequency,
                'priority': priority,
                'is_trending': frequency >= 3,
            })

        items.sort(key=lambda item: (item['priority'], item.get('timestamp') or ''), reverse=True)
        if limit is not None:
            items = items[:raw_limit]
        return _deduplicate_review_queue_items(items, limit=limit)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Ensure needs_review column exists
    try:
        cursor.execute('SELECT needs_review FROM feedback LIMIT 1')
    except sqlite3.OperationalError:
        cursor.execute('ALTER TABLE feedback ADD COLUMN needs_review BOOLEAN DEFAULT 0')

    freq_map = {}
    for item in _exclude_eval_feedback(_load_feedback_records(limit=None)):
        normalized_q = _normalize_review_queue_question(item.get('question'))
        if normalized_q:
            freq_map[normalized_q] = freq_map.get(normalized_q, 0) + 1

    # Get items needing review
    cursor.execute('''
        SELECT id, question, ai_answer, user_correction, confidence_score,
               sources, timestamp, user_rating, needs_review
        FROM feedback
        WHERE (user_rating = 'negative' OR needs_review = 1) AND reviewed = 0
        ORDER BY timestamp DESC
        LIMIT ?
    ''', (raw_limit,))

    results = cursor.fetchall()
    conn.close()

    items = []
    for row in results:
        question = row[1]
        normalized_q = question.lower().strip()
        frequency = freq_map.get(normalized_q, 1)
        confidence = row[4]
        rating = row[7]

        # Calculate priority
        priority = 0
        if rating == 'negative':
            priority += 50  # User flagged = high priority
        if confidence and confidence < 50:
            priority += 30
        elif confidence and confidence < 70:
            priority += 15
        priority += min(frequency * 5, 25)  # Frequency boost

        # Determine review type
        if rating == 'negative':
            review_type = 'user_flagged'
        elif rating == 'unrated':
            review_type = 'no_feedback'
        else:
            review_type = 'auto_flagged'

        items.append({
            'id': row[0],
            'question': question,
            'ai_answer': row[2],
            'user_correction': row[3],
            'confidence': confidence,
            'sources': json.loads(row[5]) if row[5] else [],
            'timestamp': row[6],
            'rating': rating,
            'needs_review': bool(row[8]),
            'review_type': review_type,
            'frequency': frequency,
            'priority': priority,
            'is_trending': frequency >= 3
        })

    # Sort by priority (highest first)
    items = _exclude_eval_feedback(items)
    items.sort(key=lambda x: (x['priority'], x.get('timestamp') or ''), reverse=True)

    return _deduplicate_review_queue_items(items, limit=limit)


def get_trending_issues(min_frequency=3, days=7):
    """Get trending problem areas (frequently asked with low confidence or negative feedback)"""
    if _feedback_runtime_uses_dynamodb():
        cutoff_ordinal = datetime.now(timezone.utc).date().toordinal() - days
        grouped = {}
        for item in _load_feedback_items():
            timestamp = item.get('timestamp')
            if not timestamp:
                continue
            try:
                item_date = datetime.fromisoformat(str(timestamp).replace('Z', '+00:00')).date()
            except ValueError:
                continue
            if item_date.toordinal() < cutoff_ordinal:
                continue

            normalized_q = (item.get('question') or '').strip().lower()
            if not normalized_q:
                continue
            bucket = grouped.setdefault(normalized_q, {
                'frequency': 0,
                'confidences': [],
                'negative_count': 0,
                'last_asked': timestamp,
            })
            bucket['frequency'] += 1
            if item.get('confidence_score') is not None:
                bucket['confidences'].append(item.get('confidence_score'))
            if item.get('user_rating') == 'negative':
                bucket['negative_count'] += 1
            if timestamp > bucket['last_asked']:
                bucket['last_asked'] = timestamp

        trending = []
        for question, bucket in grouped.items():
            if bucket['frequency'] < min_frequency:
                continue
            avg_conf = (
                round(sum(bucket['confidences']) / len(bucket['confidences']), 1)
                if bucket['confidences'] else None
            )
            neg_count = bucket['negative_count']
            if (avg_conf is not None and avg_conf < 70) or neg_count > 0:
                trending.append({
                    'question': question,
                    'frequency': bucket['frequency'],
                    'avg_confidence': avg_conf,
                    'negative_count': neg_count,
                    'last_asked': bucket['last_asked'],
                    'severity': 'high' if ((avg_conf is not None and avg_conf < 50) or neg_count >= 2) else 'medium',
                })

        return sorted(trending, key=lambda item: (item['severity'] == 'high', item['frequency']), reverse=True)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT LOWER(TRIM(question)) as normalized_q,
               COUNT(*) as frequency,
               AVG(confidence_score) as avg_confidence,
               SUM(CASE WHEN user_rating = 'negative' THEN 1 ELSE 0 END) as negative_count,
               MAX(timestamp) as last_asked
        FROM feedback
        WHERE timestamp >= DATE('now', ? || ' days')
        GROUP BY normalized_q
        HAVING COUNT(*) >= ?
        ORDER BY frequency DESC
    ''', (f'-{days}', min_frequency))

    results = cursor.fetchall()
    conn.close()

    trending = []
    for row in results:
        # Only include if there's a problem (low confidence or negative feedback)
        avg_conf = row[2]
        neg_count = row[3]

        if (avg_conf and avg_conf < 70) or neg_count > 0:
            trending.append({
                'question': row[0],
                'frequency': row[1],
                'avg_confidence': round(avg_conf, 1) if avg_conf else None,
                'negative_count': neg_count,
                'last_asked': row[4],
                'severity': 'high' if (avg_conf and avg_conf < 50) or neg_count >= 2 else 'medium'
            })

    return sorted(trending, key=lambda x: (x['severity'] == 'high', x['frequency']), reverse=True)


# Initialize on import
try:
    init_feedback_database()
except Exception as e:
    logging.getLogger(__name__).error(f"Failed to initialize feedback database: {e}")

if __name__ == "__main__":
    print("\n" + "="*80)
    print("FEEDBACK SYSTEM TEST")
    print("="*80 + "\n")
    
    # Save some test feedback
    print("Saving test feedback...")
    
    save_feedback(
        question="What fungicide for dollar spot?",
        ai_answer="Use recommended rate of fungicide",
        rating="negative",
        correction="Heritage at 0.16 fl oz/1000 sq ft, 14-21 day interval",
        confidence=0.4
    )
    
    save_feedback(
        question="When to apply pre-emergent?",
        ai_answer="Apply when soil temps reach 55°F",
        rating="positive",
        confidence=0.85
    )
    
    # Get negative feedback
    negative = get_negative_feedback()
    print(f"\nNegative feedback items: {len(negative)}")
    
    if negative:
        print("\nExample:")
        print(f"  Q: {negative[0]['question']}")
        print(f"  Bad answer: {negative[0]['ai_answer']}")
        print(f"  User correction: {negative[0]['user_correction']}")
        
        # Approve it
        approve_for_training(
            negative[0]['id'],
            negative[0]['user_correction']
        )
        print("\n✅ Approved for training")
    
    # Get stats
    stats = get_feedback_stats()
    print("\n" + "="*80)
    print("FEEDBACK STATS")
    print("="*80)
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    # Generate training file
    print("\n" + "="*80)
    print("GENERATING TRAINING FILE")
    print("="*80)
    result = generate_training_file(min_examples=1)
    
    if result:
        filepath, count = result
        print(f"\n✅ Training file ready: {filepath} ({count} examples)")
