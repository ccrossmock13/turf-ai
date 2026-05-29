"""Knowledge Editor data access for the admin UI."""

from __future__ import annotations

import copy
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from knowledge_base import load_diseases, load_pests, load_products, load_weeds


STORE_PATH = Path(__file__).resolve().parent / "data" / "knowledge_editor.json"
TARGET_KINDS = ("diseases", "weeds", "pests")
PRODUCT_CATEGORIES = ("fungicides", "herbicides", "insecticides", "pgrs")


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_editor_key(value: str) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text[:120]


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


def suggest_product_editor_key(payload: dict[str, Any] | None = None) -> str:
    payload = payload or {}
    trade_names = payload.get("trade_names") or []
    first_name = trade_names[0] if isinstance(trade_names, list) and trade_names else ""
    source = first_name or payload.get("display_name") or payload.get("name") or ""
    return normalize_editor_key(source)


def suggest_target_editor_key(payload: dict[str, Any] | None = None) -> str:
    payload = payload or {}
    return normalize_editor_key(payload.get("type") or payload.get("display_name") or payload.get("name") or "")


def _record_counts(record: dict[str, Any] | None) -> dict[str, int]:
    record = record or {}
    return {
        "trade_names": len(record.get("trade_names") or []),
        "targets": len(record.get("diseases") or record.get("target_weeds") or record.get("target_pests") or []),
        "field_signs": len(record.get("symptoms") or record.get("identification") or record.get("damage") or {}),
        "conditions": len(record.get("environmental_triggers") or record.get("timing") or record.get("scouting") or {}),
        "first_steps": len(record.get("cultural_control") or {}),
        "top_products": len((record.get("chemical_control") or {}).get("top_products") or []),
    }


def _build_product_readiness(key: str, current: dict[str, Any]) -> dict[str, Any]:
    counts = _record_counts(current)
    warnings: list[str] = []
    category = str(current.get("category") or "").strip().lower()
    if not normalize_editor_key(key):
        warnings.append("Record key is missing or invalid.")
    if category not in PRODUCT_CATEGORIES:
        warnings.append("Choose a valid product category.")
    if counts["trade_names"] == 0:
        warnings.append("Add at least one trade name.")
    if not str((current.get("rates") or {}).get("standard") or "").strip():
        warnings.append("Add a standard rate.")
    if counts["targets"] == 0:
        warnings.append("Add at least one verified target.")
    return {
        "publish_ready": not warnings,
        "warnings": warnings,
        "counts": counts,
        "summary": {
            "category": category or "unknown",
            "trade_name_preview": ", ".join((current.get("trade_names") or [])[:3]) or "No trade names yet",
            "target_preview": ", ".join((current.get("diseases") or current.get("target_weeds") or current.get("target_pests") or [])[:4]) or "No targets yet",
            "standard_rate": str((current.get("rates") or {}).get("standard") or "").strip() or "No standard rate yet",
        },
    }


def _build_target_readiness(kind: str, key: str, current: dict[str, Any]) -> dict[str, Any]:
    counts = _record_counts(current)
    warnings: list[str] = []
    if kind not in TARGET_KINDS:
        warnings.append("Unsupported target group.")
    if not normalize_editor_key(key):
        warnings.append("Record key is missing or invalid.")
    if not str(current.get("type") or "").strip():
        warnings.append("Add a type or label.")
    if counts["field_signs"] == 0:
        warnings.append("Add at least one field sign.")
    if counts["first_steps"] == 0:
        warnings.append("Add at least one first step.")
    return {
        "publish_ready": not warnings,
        "warnings": warnings,
        "counts": counts,
        "summary": {
            "kind": kind,
            "type": str(current.get("type") or "").strip() or "No type yet",
            "field_sign_preview": ", ".join(list((current.get("symptoms") or current.get("identification") or current.get("damage") or {}).values())[:3]) or "No field signs yet",
            "top_product_preview": ", ".join(((current.get("chemical_control") or {}).get("top_products") or [])[:4]) or "No top products yet",
        },
    }


def _format_preview_list(values: list[Any], *, empty: str = "none", limit: int = 4) -> str:
    cleaned = [str(value).strip() for value in (values or []) if str(value).strip()]
    if not cleaned:
        return empty
    preview = cleaned[:limit]
    suffix = f" (+{len(cleaned) - limit} more)" if len(cleaned) > limit else ""
    return ", ".join(preview) + suffix


def _flatten_preview_value(value: Any) -> str:
    if isinstance(value, dict):
        return _format_preview_list(list(value.values()))
    if isinstance(value, list):
        return _format_preview_list(value)
    text = str(value or "").strip()
    return text or "none"


def _product_changed_fields(base: dict[str, Any] | None, candidate: dict[str, Any]) -> list[dict[str, str]]:
    base = base or {}
    comparisons = [
        ("Category", base.get("category"), candidate.get("category")),
        ("Trade names", base.get("trade_names"), candidate.get("trade_names")),
        ("Standard rate", (base.get("rates") or {}).get("standard"), (candidate.get("rates") or {}).get("standard")),
        ("REI", base.get("rei"), candidate.get("rei")),
        (
            "Targets",
            base.get("diseases") or base.get("target_weeds") or base.get("target_pests"),
            candidate.get("diseases") or candidate.get("target_weeds") or candidate.get("target_pests"),
        ),
        ("Notes", base.get("note"), candidate.get("note")),
    ]
    changed: list[dict[str, str]] = []
    for label, before, after in comparisons:
        if _flatten_preview_value(before) == _flatten_preview_value(after):
            continue
        changed.append(
            {
                "label": label,
                "before": _flatten_preview_value(before),
                "after": _flatten_preview_value(after),
            }
        )
    return changed


def _target_changed_fields(base: dict[str, Any] | None, candidate: dict[str, Any]) -> list[dict[str, str]]:
    base = base or {}
    comparisons = [
        ("Type", base.get("type"), candidate.get("type")),
        ("Field signs", base.get("symptoms") or base.get("identification") or base.get("damage"), candidate.get("symptoms") or candidate.get("identification") or candidate.get("damage")),
        ("Conditions", base.get("environmental_triggers") or base.get("timing") or base.get("scouting"), candidate.get("environmental_triggers") or candidate.get("timing") or candidate.get("scouting")),
        ("First steps", base.get("cultural_control"), candidate.get("cultural_control")),
        ("Top products", (base.get("chemical_control") or {}).get("top_products"), (candidate.get("chemical_control") or {}).get("top_products")),
        ("Notes", (base.get("chemical_control") or {}).get("notes"), (candidate.get("chemical_control") or {}).get("notes")),
    ]
    changed: list[dict[str, str]] = []
    for label, before, after in comparisons:
        if _flatten_preview_value(before) == _flatten_preview_value(after):
            continue
        changed.append(
            {
                "label": label,
                "before": _flatten_preview_value(before),
                "after": _flatten_preview_value(after),
            }
        )
    return changed


def _build_product_answer_impact(key: str, base: dict[str, Any] | None, candidate: dict[str, Any], readiness: dict[str, Any]) -> dict[str, Any]:
    category = str(candidate.get("category") or "").strip().lower() or "unknown"
    targets = candidate.get("diseases") or candidate.get("target_weeds") or candidate.get("target_pests") or []
    trade_names = candidate.get("trade_names") or []
    changed_fields = _product_changed_fields(base, candidate)
    if base:
        summary = f"Updates the {category} product record `{key}` used by structured product answers."
    else:
        summary = f"Adds a new {category} product record `{key}` to structured product answers."
    if readiness.get("publish_ready") and targets:
        summary += f" Matching questions for {_format_preview_list(targets)} can use this record after publish."
    return {
        "summary": summary,
        "record_scope": "product",
        "category": category,
        "trade_name_preview": _format_preview_list(trade_names, empty="none"),
        "target_preview": _format_preview_list(targets, empty="none"),
        "changed_fields": changed_fields,
    }


def _build_target_answer_impact(kind: str, key: str, base: dict[str, Any] | None, candidate: dict[str, Any], readiness: dict[str, Any]) -> dict[str, Any]:
    label = str(candidate.get("type") or "").strip() or key
    top_products = (candidate.get("chemical_control") or {}).get("top_products") or []
    changed_fields = _target_changed_fields(base, candidate)
    if base:
        summary = f"Updates the {kind[:-1]} guidance record `{key}` used by structured diagnosis and management answers."
    else:
        summary = f"Adds a new {kind[:-1]} guidance record `{key}` for structured diagnosis and management answers."
    if readiness.get("publish_ready"):
        summary += f" Questions routed to {label} can surface this guidance after publish."
    return {
        "summary": summary,
        "record_scope": kind[:-1],
        "type_label": label,
        "top_product_preview": _format_preview_list(top_products, empty="none"),
        "changed_fields": changed_fields,
    }


def _build_product_answer_preview(key: str, candidate: dict[str, Any], readiness: dict[str, Any]) -> dict[str, Any]:
    category = str(candidate.get("category") or "").strip().lower() or "product"
    trade_name = ((candidate.get("trade_names") or [key])[0] or key).strip() or key
    targets = candidate.get("diseases") or candidate.get("target_weeds") or candidate.get("target_pests") or []
    target_text = _format_preview_list(targets, empty="the listed target")
    standard_rate = str((candidate.get("rates") or {}).get("standard") or "").strip()
    rei = str(candidate.get("rei") or "").strip()
    note = str(candidate.get("note") or "").strip()
    scenario = f"What can I use for {targets[0].replace('_', ' ')}?" if targets else f"Tell me about {trade_name}"
    if readiness.get("publish_ready"):
        lines = [
            f"**Bottom Line:** This draft would let the verified KB surface **{trade_name}** as a structured {category} option for **{target_text.replace('_', ' ')}**.",
            "",
            "SIMULATED ANSWER SHAPE",
            f"- Product: {trade_name}",
            f"- Category: {category}",
            f"- Verified targets: {target_text}",
        ]
        if standard_rate:
            lines.append(f"- Standard rate shown: {standard_rate}")
        if rei:
            lines.append(f"- REI shown: {rei}")
        if note:
            lines.append(f"- Notes carried into the record: {note}")
    else:
        lines = [
            f"**Bottom Line:** This draft is not ready to produce a clean structured {category} answer yet.",
            "",
            "Before publish, the answer would still be blocked by missing required fields.",
        ]
    return {
        "scenario_question": scenario,
        "answer": "\n".join(lines),
        "ready": bool(readiness.get("publish_ready")),
    }


def _build_target_answer_preview(kind: str, key: str, candidate: dict[str, Any], readiness: dict[str, Any]) -> dict[str, Any]:
    label = str(candidate.get("type") or "").strip() or key.replace("_", " ")
    field_signs = list((candidate.get("symptoms") or candidate.get("identification") or candidate.get("damage") or {}).values())
    conditions = list((candidate.get("environmental_triggers") or candidate.get("timing") or candidate.get("scouting") or {}).values())
    first_steps = list((candidate.get("cultural_control") or {}).values())
    top_products = (candidate.get("chemical_control") or {}).get("top_products") or []
    notes = str((candidate.get("chemical_control") or {}).get("notes") or "").strip()
    scenario = f"How do I manage {label}?"
    if readiness.get("publish_ready"):
        lines = [
            f"**Bottom Line:** This draft would add structured {kind[:-1]} guidance for **{label}**.",
            "",
            "SIMULATED ANSWER SHAPE",
            f"- Field signs: {_format_preview_list(field_signs, empty='none')}",
            f"- Conditions: {_format_preview_list(conditions, empty='none')}",
            f"- First steps: {_format_preview_list(first_steps, empty='none')}",
        ]
        if top_products:
            lines.append(f"- Top products surfaced: {_format_preview_list(top_products, empty='none')}")
        if notes:
            lines.append(f"- Notes surfaced: {notes}")
    else:
        lines = [
            f"**Bottom Line:** This draft is not ready to produce clean structured guidance for **{label}** yet.",
            "",
            "Before publish, the answer would still be blocked by missing required fields.",
        ]
    return {
        "scenario_question": scenario,
        "answer": "\n".join(lines),
        "ready": bool(readiness.get("publish_ready")),
    }


def build_product_editor_preview(key: str, patch: dict[str, Any] | None = None) -> dict[str, Any]:
    record = get_product_editor_record(normalize_editor_key(key) or key)
    base = record.get("base")
    published = record.get("published")
    draft = record.get("draft")
    candidate = _record_current(base, published, patch if patch is not None else draft)
    readiness = _build_product_readiness(key, candidate)
    return {
        "key": normalize_editor_key(key),
        "current": candidate,
        "readiness": readiness,
        "impact": _build_product_answer_impact(normalize_editor_key(key), base, candidate, readiness),
        "answer_preview": _build_product_answer_preview(normalize_editor_key(key), candidate, readiness),
        "base_exists": bool(base),
        "has_draft": bool(draft),
        "has_published_override": bool(published),
    }


def build_target_editor_preview(kind: str, key: str, patch: dict[str, Any] | None = None) -> dict[str, Any]:
    record = get_target_editor_record(kind, normalize_editor_key(key) or key)
    base = record.get("base")
    published = record.get("published")
    draft = record.get("draft")
    candidate = _record_current(base, published, patch if patch is not None else draft)
    readiness = _build_target_readiness(kind, key, candidate)
    return {
        "key": normalize_editor_key(key),
        "kind": kind,
        "current": candidate,
        "readiness": readiness,
        "impact": _build_target_answer_impact(kind, normalize_editor_key(key), base, candidate, readiness),
        "answer_preview": _build_target_answer_preview(kind, normalize_editor_key(key), candidate, readiness),
        "base_exists": bool(base),
        "has_draft": bool(draft),
        "has_published_override": bool(published),
    }


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
                "has_published": bool(overlay.get("published")),
                "updated_at": overlay.get("updated_at"),
            }
        )
        if len(items) >= limit:
            break
    return items


def get_product_editor_record(key: str) -> dict[str, Any]:
    key = normalize_editor_key(key)
    base = _product_base_records().get(key)
    stored = load_editor_store()["products"].get(key, {})
    current = _record_current(base, stored.get("published"), stored.get("draft"))
    return {
        "key": key,
        "base": copy.deepcopy(base),
        "draft": copy.deepcopy(stored.get("draft")),
        "published": copy.deepcopy(stored.get("published")),
        "current": current,
        "readiness": _build_product_readiness(key, current),
        "updated_at": stored.get("updated_at"),
        "updated_by": stored.get("updated_by"),
        "published_at": stored.get("published_at"),
        "published_by": stored.get("published_by"),
        "draft_at": stored.get("draft_at"),
        "draft_by": stored.get("draft_by"),
    }


def save_product_editor_record(key: str, patch: dict[str, Any], publish: bool = False, actor: str = "admin") -> dict[str, Any]:
    key = normalize_editor_key(key)
    store = load_editor_store()
    product_store = store["products"]
    item = copy.deepcopy(product_store.get(key, {}))
    preview = build_product_editor_preview(key, patch)
    if publish and not preview["readiness"]["publish_ready"]:
        raise ValueError("; ".join(preview["readiness"]["warnings"]))
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
                "has_published": bool(overlay.get("published")),
                "updated_at": overlay.get("updated_at"),
            }
        )
        if len(items) >= limit:
            break
    return items


def get_target_editor_record(kind: str, key: str) -> dict[str, Any]:
    key = normalize_editor_key(key)
    base = _target_base_records(kind).get(key)
    stored = load_editor_store()["targets"][kind].get(key, {})
    current = _record_current(base, stored.get("published"), stored.get("draft"))
    return {
        "key": key,
        "kind": kind,
        "base": copy.deepcopy(base),
        "draft": copy.deepcopy(stored.get("draft")),
        "published": copy.deepcopy(stored.get("published")),
        "current": current,
        "readiness": _build_target_readiness(kind, key, current),
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
    key = normalize_editor_key(key)
    store = load_editor_store()
    target_store = store["targets"][kind]
    item = copy.deepcopy(target_store.get(key, {}))
    preview = build_target_editor_preview(kind, key, patch)
    if publish and not preview["readiness"]["publish_ready"]:
        raise ValueError("; ".join(preview["readiness"]["warnings"]))
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
