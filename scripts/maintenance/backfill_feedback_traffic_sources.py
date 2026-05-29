"""Backfill obvious non-user feedback rows using known repo QA/eval prompts.

This is intentionally conservative:
- only exact question-text matches are retagged
- only rows currently tagged as 'user' are eligible
- prompts are sourced from local test/eval/script files
"""

from __future__ import annotations

import argparse
import ast
import json
import sqlite3
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "data" / "greenside_feedback.db"
TRAFFIC_SOURCES = {"test", "eval", "script"}
QUESTION_PREFIXES = (
    "what ",
    "how ",
    "why ",
    "when ",
    "which ",
    "can ",
    "do ",
    "does ",
    "is ",
    "are ",
    "could ",
    "should ",
    "my ",
    "our ",
    "give me ",
    "preparations ",
    "walk me through ",
)


@dataclass(frozen=True)
class PromptSet:
    source: str
    questions: set[str]


def normalize_question(text: str) -> str:
    return " ".join(str(text or "").strip().split())


def looks_like_question_literal(value: str) -> bool:
    text = normalize_question(value)
    if len(text) < 12 or "\n" in text:
        return False
    lower = text.lower()
    return lower.endswith("?") or lower.startswith(QUESTION_PREFIXES)


def infer_source_for_path(path: Path) -> str | None:
    name = path.name
    if path.match("test_*.py"):
        return "test"
    if path.parent.name == "scripts":
        if name.startswith("run_") or "eval" in name or "probe" in name:
            return "eval"
        if "smoke" in name or "check" in name:
            return "script"
    if path.suffix == ".json" and path.parent.name == "scripts":
        if "eval" in name or "cases" in name:
            return "eval"
    return None


def extract_question_strings(path: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"), filename=str(path))
    except SyntaxError:
        return set()

    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            text = normalize_question(node.value)
            if looks_like_question_literal(text):
                found.add(text)
    return found


def _walk_json_questions(value) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "question" and isinstance(child, str):
                text = normalize_question(child)
                if looks_like_question_literal(text):
                    found.add(text)
            else:
                found.update(_walk_json_questions(child))
    elif isinstance(value, list):
        for child in value:
            found.update(_walk_json_questions(child))
    return found


def extract_question_strings_from_json(path: Path) -> set[str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return set()
    return _walk_json_questions(data)


def collect_repo_prompt_sets() -> list[PromptSet]:
    prompt_sets: dict[str, set[str]] = {source: set() for source in TRAFFIC_SOURCES}
    candidates = (
        list(ROOT.glob("test_*.py"))
        + list((ROOT / "scripts").glob("*.py"))
        + list((ROOT / "scripts").glob("*.json"))
    )
    for path in candidates:
        source = infer_source_for_path(path)
        if source not in TRAFFIC_SOURCES:
            continue
        if path.suffix == ".json":
            prompt_sets[source].update(extract_question_strings_from_json(path))
        else:
            prompt_sets[source].update(extract_question_strings(path))
    return [PromptSet(source=source, questions=questions) for source, questions in prompt_sets.items()]


def load_feedback_question_counts(conn: sqlite3.Connection) -> Counter[str]:
    cur = conn.cursor()
    cur.execute("SELECT question FROM feedback WHERE COALESCE(traffic_source, 'user') = 'user'")
    return Counter(normalize_question(row[0]) for row in cur.fetchall())


def build_matches(conn: sqlite3.Connection) -> dict[str, set[str]]:
    counts = load_feedback_question_counts(conn)
    repo_prompt_sets = collect_repo_prompt_sets()
    matches: dict[str, set[str]] = {source: set() for source in TRAFFIC_SOURCES}
    for prompt_set in repo_prompt_sets:
        for question in prompt_set.questions:
            if question in counts:
                matches[prompt_set.source].add(question)
    return matches


def update_matches(conn: sqlite3.Connection, matches: dict[str, set[str]]) -> dict[str, int]:
    updated: dict[str, int] = {}
    cur = conn.cursor()
    for source in ("eval", "script", "test"):
        questions = sorted(matches.get(source) or [])
        if not questions:
            updated[source] = 0
            continue
        placeholders = ",".join("?" for _ in questions)
        params = [source, *questions]
        sql = f"""
            UPDATE feedback
            SET traffic_source = ?
            WHERE COALESCE(traffic_source, 'user') = 'user'
              AND question IN ({placeholders})
        """
        cur.execute(sql, params)
        updated[source] = cur.rowcount
    conn.commit()
    return updated


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write changes to the feedback database.")
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)
    try:
        matches = build_matches(conn)
        question_counts = load_feedback_question_counts(conn)
        print(f"db_path={DB_PATH}")
        print(f"matched_eval_questions={len(matches['eval'])}")
        print(f"matched_script_questions={len(matches['script'])}")
        print(f"matched_test_questions={len(matches['test'])}")
        for source in ("eval", "script", "test"):
            total_rows = sum(question_counts[q] for q in matches[source])
            print(f"{source}_rows_to_retag={total_rows}")
            for question in sorted(matches[source])[:20]:
                print(f"{source}\t{question_counts[question]}\t{question}")

        if not args.apply:
            return 0

        updated = update_matches(conn, matches)
        print("applied=true")
        for source in ("eval", "script", "test"):
            print(f"{source}_rows_retagged={updated[source]}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
