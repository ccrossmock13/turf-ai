"""Knowledge Editor data access for the admin UI."""

from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from knowledge_base import load_diseases, load_pests, load_products, load_weeds


STORE_PATH = Path(__file__).resolve().parent / "data" / "knowledge_editor.json"
TARGET_KINDS = ("diseases", "weeds", "pests")


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_store() -> dict[str, Any]:
    return {
        "products": {},
        "targets": {kind: {} for kind in TARGET_KINDS},
    }


def _deep_merge(base: Any, overlay: Any) -> Any:
    if isinstance(base, dict) and isinstance(overlay, dict):
        merged = copy.deepcopy(base)
        for key, value in overlay.items():
            merged[key] = _deep_merge(merged.get(key), value)
        return merged
    return copy.deepcopy(overlay)


def _record_current(base: dict[str, Any] | None, published: dict[str, Any] | None, draft: dict[str, Any] | None) -> dict[str, Any]:
    current = copy.deepcopy(base or {})
    if published:
        current = _deep_merge(current, published)
    if draft:
        current = _deep_merge(current, draft)
    return current


def _normalize_store(data: dict[str, Any] | None) -> dict[str, Any]:
    store = _default_store()
    if isinstance(data, dict):
        if isinstance(data.get("products"), dict):
            store["products"] = data["products"]
        targets = data.get("targets")
        if isinstance(targets, dict):
            for kind in TARGET_KINDS:
                if isinstance(targets.get(kind), dict):
                    store["targets"][kind] = targets[kind]
    return store


def load_editor_store() -> dict[str, Any]:
    if not STORE_PATH.exists():
        return _default_store()
    with STORE_PATH.open("r", encoding="utf-8") as handle:
        return _normalize_store(json.load(handle))


def save_editor_store(store: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_store(store)
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with STORE_PATH.open("w", encoding="utf-8") as handle:
        json.dump(normalized, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return normalized


def _product_base_records() -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for category, items in (load_products() or {}).items():
        for key, info in (items or {}).items():
            record = copy.deepcopy(info or {})
            record.setdefault("category", category)
            records[key] = record
    return records


def _target_base_records(kind: str) -> dict[str, dict[str, Any]]:
    loaders = {
        "diseases": load_diseases,
        "weeds": load_weeds,
        "pests": load_pests,
    }
    if kind not in loaders:
        raise ValueError(f"Unsupported target kind: {kind}")
    return copy.deepcopy(loaders[kind]())


def _match_query(text: str, query: str) -> bool:
    return query.lower() in text.lower()


def knowledge_editor_summary() -> dict[str, Any]:
    store = load_editor_store()
    summary = {
        "products": {"drafts": 0, "published_overrides": 0},
        "targets": {},
    }
    for item in store["products"].values():
        if item.get("draft"):
            summary["products"]["drafts"] += 1
        if item.get("published"):
            summary["products"]["published_overrides"] += 1
    for kind in TARGET_KINDS:
        bucket = {"drafts": 0, "published_overrides": 0}
        for item in store["targets"][kind].values():
            if item.get("draft"):
                bucket["drafts"] += 1
            if item.get("published"):
                bucket["published_overrides"] += 1
        summary["targets"][kind] = bucket
    return summary


def list_product_editor_records(query: str = "", limit: int = 50) -> list[dict[str, Any]]:
    base_records = _product_base_records()
    store = load_editor_store()["products"]
    keys = sorted(set(base_records) | set(store))
    items: list[dict[str, Any]] = []
    for key in keys:
        base = base_records.get(key)
        overlay = store.get(key, {})
        current = _record_current(base, overlay.get("published"), overlay.get("draft"))
        haystack = " ".join(
            [
                key,
                str(current.get("category") or ""),
                str(current.get("note") or ""),
                " ".join(str(name) for name in (current.get("trade_names") or [])),
            ]
        )
        if query and not _match_query(haystack, query):
            continue
        display_name = (current.get("trade_names") or [None])[0] or key
        items.append(
            {
                "key": key,
                "kind": current.get("category") or "products",
                "display_name": display_name,
                "has_draft": bool(overlay.get("draft")),
                "has_published_override": bool(overlay.get("published")),
                "updated_at": overlay.get("updated_at"),
            }
        )
        if len(items) >= limit:
            break
    return items


def get_product_editor_record(key: str) -> dict[str, Any]:
    base = _product_base_records().get(key)
    stored = load_editor_store()["products"].get(key, {})
    return {
        "key": key,
        "base": copy.deepcopy(base),
        "draft": copy.deepcopy(stored.get("draft")),
        "published": copy.deepcopy(stored.get("published")),
        "current": _record_current(base, stored.get("published"), stored.get("draft")),
        "updated_at": stored.get("updated_at"),
        "updated_by": stored.get("updated_by"),
        "published_at": stored.get("published_at"),
        "published_by": stored.get("published_by"),
        "draft_at": stored.get("draft_at"),
        "draft_by": stored.get("draft_by"),
    }


def save_product_editor_record(key: str, patch: dict[str, Any], publish: bool = False, actor: str = "admin") -> dict[str, Any]:
    store = load_editor_store()
    product_store = store["products"]
    item = copy.deepcopy(product_store.get(key, {}))
    now = _utcnow_iso()
    if publish:
        item["published"] = copy.deepcopy(patch)
        item["published_at"] = now
        item["published_by"] = actor
        item.pop("draft", None)
        item.pop("draft_at", None)
        item.pop("draft_by", None)
    else:
        item["draft"] = copy.deepcopy(patch)
        item["draft_at"] = now
        item["draft_by"] = actor
    item["updated_at"] = now
    item["updated_by"] = actor
    product_store[key] = item
    save_editor_store(store)
    return get_product_editor_record(key)


def list_target_editor_records(kind: str, query: str = "", limit: int = 50) -> list[dict[str, Any]]:
    base_records = _target_base_records(kind)
    store = load_editor_store()["targets"][kind]
    keys = sorted(set(base_records) | set(store))
    items: list[dict[str, Any]] = []
    for key in keys:
        base = base_records.get(key)
        overlay = store.get(key, {})
        current = _record_current(base, overlay.get("published"), overlay.get("draft"))
        haystack = " ".join(
            [
                key,
                str(current.get("type") or ""),
                " ".join(str(value) for value in (current.get("chemical_control", {}).get("top_products") or [])),
            ]
        )
        if query and not _match_query(haystack, query):
            continue
        items.append(
            {
                "key": key,
                "kind": kind,
                "display_name": current.get("type") or key,
                "has_draft": bool(overlay.get("draft")),
                "has_published_override": bool(overlay.get("published")),
                "updated_at": overlay.get("updated_at"),
            }
        )
        if len(items) >= limit:
            break
    return items


def get_target_editor_record(kind: str, key: str) -> dict[str, Any]:
    base = _target_base_records(kind).get(key)
    stored = load_editor_store()["targets"][kind].get(key, {})
    return {
        "key": key,
        "kind": kind,
        "base": copy.deepcopy(base),
        "draft": copy.deepcopy(stored.get("draft")),
        "published": copy.deepcopy(stored.get("published")),
        "current": _record_current(base, stored.get("published"), stored.get("draft")),
        "updated_at": stored.get("updated_at"),
        "updated_by": stored.get("updated_by"),
        "published_at": stored.get("published_at"),
        "published_by": stored.get("published_by"),
        "draft_at": stored.get("draft_at"),
        "draft_by": stored.get("draft_by"),
    }


def save_target_editor_record(kind: str, key: str, patch: dict[str, Any], publish: bool = False, actor: str = "admin") -> dict[str, Any]:
    if kind not in TARGET_KINDS:
        raise ValueError(f"Unsupported target kind: {kind}")
    store = load_editor_store()
    target_store = store["targets"][kind]
    item = copy.deepcopy(target_store.get(key, {}))
    now = _utcnow_iso()
    if publish:
        item["published"] = copy.deepcopy(patch)
        item["published_at"] = now
        item["published_by"] = actor
        item.pop("draft", None)
        item.pop("draft_at", None)
        item.pop("draft_by", None)
    else:
        item["draft"] = copy.deepcopy(patch)
        item["draft_at"] = now
        item["draft_by"] = actor
    item["updated_at"] = now
    item["updated_by"] = actor
    target_store[key] = item
    save_editor_store(store)
    return get_target_editor_record(kind, key)


def apply_published_product_overlays(products: dict[str, Any] | None = None) -> dict[str, Any]:
    merged = copy.deepcopy(products if products is not None else load_products())
    store = load_editor_store()["products"]
    for key, item in store.items():
        published = item.get("published")
        if not published:
            continue
        category = published.get("category") or merged.get(next(iter(merged), ""), {}).get(key, {}).get("category") or "fungicides"
        merged.setdefault(category, {})
        merged[category][key] = _deep_merge(merged[category].get(key, {}), published)
    return merged


def apply_published_target_overlays(kind: str, records: dict[str, Any] | None = None) -> dict[str, Any]:
    merged = copy.deepcopy(records if records is not None else _target_base_records(kind))
    store = load_editor_store()["targets"][kind]
    for key, item in store.items():
        published = item.get("published")
        if not published:
            continue
        merged[key] = _deep_merge(merged.get(key, {}), published)
    return merged
