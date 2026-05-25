"""Audit structured KB records against local label PDFs.

The script does not mark draft data as verified. It reports whether each
structured product has required fields, a plausible local label source, and
whether stored targets/rate text can be found in extracted label text.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import re
import sys
from functools import lru_cache
from pathlib import Path

from PyPDF2 import PdfReader

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from knowledge_base import load_products  # noqa: E402


LABEL_DIRS = [
    ROOT / "static" / "product-labels",
    ROOT / "static" / "epa_labels",
]


REQUIRED_FIELDS = {
    "fungicides": ["trade_names", "rates", "not_for", "frac_code", "diseases"],
    "herbicides": ["trade_names", "rates", "not_for", "hrac_group", "target_weeds", "type"],
    "insecticides": ["trade_names", "rates", "not_for", "irac_group", "target_pests", "type"],
    "pgrs": ["trade_names", "rates", "not_for", "type"],
}


TARGET_FIELD = {
    "fungicides": "diseases",
    "herbicides": "target_weeds",
    "insecticides": "target_pests",
}


EXPANDED_LABEL_FIELDS = [
    "rei",
    "retreatment_interval",
    "irrigation_guidance",
    "rainfast",
    "tank_mix_guidance",
    "max_apps_per_year",
    "max_rate_per_app",
    "reseeding_interval",
    "overseeding_interval",
    "application_window_notes",
]


def normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def label_files() -> list[Path]:
    files = []
    for directory in LABEL_DIRS:
        if directory.exists():
            files.extend(sorted(directory.glob("*.pdf")))
    return files


def local_source_label(info: dict) -> Path | None:
    source_url = str(info.get("source_url", "") or "").strip()
    if not source_url.startswith("/static/"):
        return None
    path = ROOT / source_url.lstrip("/")
    return path if path.exists() else None


def find_label(active_ingredient: str, info: dict) -> Path | None:
    explicit = local_source_label(info)
    if explicit:
        return explicit
    names = [active_ingredient.replace("_", " ")] + [str(name) for name in info.get("trade_names", [])]
    candidates = []
    for label in label_files():
        label_name = normalize(label.name)
        for name in names:
            tokens = [token for token in normalize(name).split() if len(token) > 2]
            if tokens and all(token in label_name for token in tokens[:2]):
                score = len(tokens)
                candidates.append((score, label))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (-item[0], len(item[1].name)))
    return candidates[0][1]


@lru_cache(maxsize=512)
def pdf_text(path_str: str) -> str:
    path = Path(path_str)
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            reader = PdfReader(str(path))
            text = " ".join((page.extract_text() or "") for page in reader.pages)
        return normalize(text)
    except Exception:
        return ""


def rate_tokens(rate: str) -> list[str]:
    return [token for token in re.findall(r"\d+\.?\d*", str(rate)) if token not in {"1000"}]


def token_found(token: str, text: str) -> bool:
    normalized_token = normalize(token)
    candidates = {token, normalized_token}
    if len(token) >= 4 and token.isdigit():
        candidates.add(" ".join([token[0], token[1:]]))
    if "." in token:
        whole, decimal = token.split(".", 1)
        candidates.add(normalize(f"{whole} {decimal}"))
        candidates.add(normalize(f"{whole}.{decimal.rstrip('0') or '0'}"))
        candidates.add(normalize(f".{decimal}"))
        if decimal.endswith("0"):
            candidates.add(normalize(f".{decimal.rstrip('0')}"))
            candidates.add(normalize(f"{whole}.{decimal.rstrip('0')}"))
    return bool(token and any(candidate and candidate in text for candidate in candidates))


def target_terms(target: str) -> set[str]:
    display = target.replace("_", " ").replace("-", " ")
    terms = {normalize(target), normalize(display)}
    aliases = {
        "all_vegetation": {"all vegetation", "non selective", "nonselective"},
        "annual_bluegrass_weevil": {"annual bluegrass weevil", "abw"},
        "armyworms": {"armyworms", "armyworm"},
        "ants": {"ants"},
        "bentgrass": {"bentgrass", "creeping bentgrass"},
        "bermudagrass": {"bermudagrass", "bermuda"},
        "billbugs": {"billbug", "billbugs"},
        "broadleaf_weeds": {"broadleaf weeds", "broadleaf weed", "broadleaves"},
        "brown_ring_patch": {"brown ring patch", "waitea patch"},
        "caterpillars": {"caterpillars", "caterpillar", "turf caterpillars", "lepidopterous larvae"},
        "dallisgrass": {"dallisgrass"},
        "poa_annua": {"annual bluegrass"},
        "poa_trivialis": {"roughstalk bluegrass"},
        "fire_ants": {"fire ants", "fire ant"},
        "white_grubs": {"white grubs", "grubs"},
        "sod_webworms": {"sod webworms", "webworms", "sod worms", "turf caterpillars"},
        "chinch_bugs": {"chinch bug", "chinch bugs"},
        "cutworms": {"cutworm", "cutworms"},
        "dollar_spot": {"dollar spot"},
        "brown_patch": {"brown patch"},
        "fairy_ring": {"fairy ring"},
        "gray_leaf_spot": {"gray leaf spot", "grey leaf spot"},
        "gray_snow_mold": {"gray snow mold", "grey snow mold", "snow mold gray", "snowmold gray", "typhula blight"},
        "green_kyllinga": {"green kyllinga", "kyllinga"},
        "ground_ivy": {"ground ivy", "creeping charlie"},
        "kentucky_bluegrass": {"kentucky bluegrass", "bluegrass kentucky"},
        "leaf_spot": {"leaf spot"},
        "lance_nematodes": {"lance nematodes", "lance nematode", "lance"},
        "microdochium_patch": {"microdochium patch", "pink snow mold", "fusarium patch"},
        "necrotic_ring_spot": {"necrotic ring spot"},
        "non-selective": {"non selective", "nonselective"},
        "plantain": {"plantain"},
        "pink_snow_mold": {"pink snow mold", "snow mold pink", "microdochium nivale", "fusarium patch"},
        "pythium_blight": {"pythium blight", "pythium"},
        "pythium_root_rot": {"pythium root rot", "pythium root dysfunction", "pythium"},
        "spring_dead_spot": {"spring dead spot"},
        "ring_nematodes": {"ring nematodes", "ring nematode", "ring"},
        "root_knot_nematodes": {"root knot nematodes", "root knot nematode", "root-knot nematodes", "root-knot nematode", "root knot", "root-knot"},
        "sting_nematodes": {"sting nematodes", "sting nematode", "sting"},
        "surface_insects": {"surface insects", "surface feeding pests", "surface feeding insects"},
        "take_all_patch": {"take all patch", "take-all patch"},
        "turf_parasitic_nematodes": {"turf parasitic nematodes", "plant pathogenic nematodes", "nematodes"},
        "wild_strawberry": {"wild strawberry", "strawberry"},
        "wild_violets": {"wild violet", "wild violets", "violet", "violets"},
        "yellow_nutsedge": {"yellow nutsedge", "nutsedge"},
        "yellow_patch": {"yellow patch", "cool season brown patch"},
        "white_grubs": {
            "white grubs", "grubs", "japanese beetle", "european chafer",
            "masked chafer", "oriental beetle", "may june beetles", "phyllophaga",
        },
    }
    terms.update(normalize(alias) for alias in aliases.get(target, set()))
    return {term for term in terms if term}


def audit_record(category: str, active_ingredient: str, info: dict) -> dict:
    missing_fields = [
        field for field in REQUIRED_FIELDS.get(category, [])
        if field not in info or info.get(field) in (None, "", [], {})
    ]
    label = find_label(active_ingredient, info)
    text = pdf_text(str(label)) if label else ""

    rate_checks = []
    for rate_name, rate in info.get("rates", {}).items():
        tokens = rate_tokens(str(rate))
        found = bool(text) and all(token_found(token, text) for token in tokens)
        rate_checks.append({"name": rate_name, "rate": rate, "numbers_found_in_label": found})

    target_checks = []
    target_field = TARGET_FIELD.get(category)
    if target_field:
        for target in info.get(target_field, []):
            terms = target_terms(str(target))
            found = bool(text) and any(term in text for term in terms)
            target_checks.append({"target": target, "found_in_label_text": found})

    has_source_metadata = any(
        key in info for key in ["source", "source_url", "label_date", "reviewed_at", "epa_reg_no", "verified_at"]
    )

    warnings = []
    if missing_fields:
        warnings.append("missing_required_fields")
    if not label:
        warnings.append("no_label_candidate")
    if label and not text:
        warnings.append("label_text_unreadable")
    if not has_source_metadata:
        warnings.append("missing_source_metadata")
    if any(not check["numbers_found_in_label"] for check in rate_checks):
        warnings.append("rate_text_not_fully_verified")
    if any(not check["found_in_label_text"] for check in target_checks):
        warnings.append("target_text_not_fully_verified")

    return {
        "category": category,
        "active_ingredient": active_ingredient,
        "trade_names": info.get("trade_names", []),
        "label_candidate": str(label.relative_to(ROOT)) if label else None,
        "missing_fields": missing_fields,
        "has_source_metadata": has_source_metadata,
        "rate_checks": rate_checks,
        "target_checks": target_checks,
        "warnings": warnings,
    }


def run_audit() -> dict:
    products = load_products()
    records = []
    field_coverage = {field: 0 for field in EXPANDED_LABEL_FIELDS}
    for category, items in products.items():
        for active_ingredient, info in items.items():
            records.append(audit_record(category, active_ingredient, info))
            for field in EXPANDED_LABEL_FIELDS:
                value = info.get(field)
                if value not in (None, "", [], {}):
                    field_coverage[field] += 1

    warning_counts = {}
    for record in records:
        for warning in record["warnings"]:
            warning_counts[warning] = warning_counts.get(warning, 0) + 1

    total_records = len(records)
    field_coverage_summary = {
        field: {
            "records_with_value": count,
            "records_missing_value": total_records - count,
        }
        for field, count in field_coverage.items()
    }

    return {
        "summary": {
            "products": total_records,
            "label_pdfs": len(label_files()),
            "warnings": warning_counts,
            "records_with_no_warnings": sum(1 for record in records if not record["warnings"]),
            "expanded_field_coverage": field_coverage_summary,
        },
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="Print full JSON report.")
    parser.add_argument("--strict", action="store_true", help="Exit nonzero when any warning is present.")
    args = parser.parse_args()

    report = run_audit()
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("STRUCTURED KB AUDIT")
        print(json.dumps(report["summary"], indent=2, sort_keys=True))
        for record in report["records"]:
            if record["warnings"]:
                print(
                    f"- {record['category']}/{record['active_ingredient']}: "
                    f"{', '.join(record['warnings'])}; label={record['label_candidate']}"
                )

    return 1 if args.strict and report["summary"]["warnings"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
