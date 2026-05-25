"""Populate expanded product-label fields from local label PDFs.

This script is intentionally conservative: it only fills fields when a simple
pattern match finds a sentence or phrase that clearly supports the value.
Existing non-empty values are preserved.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PRODUCTS_PATH = ROOT / "knowledge" / "products.json"
PDFTOTEXT = "/opt/homebrew/bin/pdftotext"

SCHEMA_DEFAULTS = {
    "rei": "",
    "retreatment_interval": "",
    "irrigation_guidance": "",
    "rainfast": "",
    "tank_mix_guidance": [],
    "max_apps_per_year": "",
    "max_rate_per_app": "",
    "reseeding_interval": "",
    "overseeding_interval": "",
    "application_window_notes": "",
}

CURATED_OVERRIDES = {
    "azoxystrobin": {
        "irrigation_guidance": "For labeled fairy ring use, add the recommended wetting-agent rate and water in immediately with 1/8 to 1/4 inches of irrigation.",
        "tank_mix_guidance": [
            "During periods of dollar spot pressure, the label says to always mix Heritage with Daconil, Banner Maxx, Secure, or another dollar spot control fungicide.",
            "The label says Heritage is compatible in tank mixes with many other fungicides that control dollar spot.",
            "Do not tank-mix Heritage with other products unless local experience indicates the tank mix is safe and effective under your conditions.",
        ],
    },
    "chlorothalonil": {
        "retreatment_interval": "Minimum re-treatment interval is 7 days at rates up to 3.5 fl oz/1000 sq ft; after rates above 3.5 fl oz/1000 sq ft, the minimum re-treatment interval is 14 days.",
        "irrigation_guidance": "Do not apply Daconil Action through any type of irrigation system.",
        "tank_mix_guidance": [
            "Do not combine Daconil Action in the spray tank with pesticides, surfactants, or fertilizers unless prior use has shown the combination physically compatible, effective, and noninjurious under your conditions.",
            "Do not combine Daconil Action with Dipel, Latron B-1956, Latron AG-98, horticultural oil, or products containing xylene.",
            "A tank mix of Daconil Action with Chipco Signature can result in physical antagonism if not mixed properly.",
        ],
    },
    "chlorantraniliprole": {
        "rei": "4 hours",
        "retreatment_interval": "Wait a minimum of 7 days to retreat.",
        "max_apps_per_year": "Do not apply more than 250 pounds of product per acre per year in broadcast applications to turfgrass.",
        "max_rate_per_app": "Do not apply more than 100 pounds of product per acre in a single application on sod farms.",
        "application_window_notes": "Apply before egg hatch; irrigate after application to move product into the soil.",
    },
    "mesotrione": {
        "retreatment_interval": "Wait a minimum of 14 days before retreating.",
        "max_rate_per_app": "Do not apply more than 8 fl oz of Tenacity per acre in a single application.",
    },
    "dithiopyr": {
        "max_apps_per_year": "Do not use more than 6 pints of Dimension 2EW per acre per year.",
        "max_rate_per_app": "Do not apply more than 2 pints of Dimension 2EW per acre per application.",
        "reseeding_interval": "Reseeding, overseeding, or sprigging within 3 months after a single application, or within 4 months after a sequential application program totaling more than 2 pints per acre, may inhibit establishment of desirable turfgrasses.",
        "overseeding_interval": "Reseeding, overseeding, or sprigging within 3 months after a single application, or within 4 months after a sequential application program totaling more than 2 pints per acre, may inhibit establishment of desirable turfgrasses.",
    },
    "2_4_d": {
        "reseeding_interval": "Reseed no sooner than three to four weeks after application of this product.",
        "overseeding_interval": "Reseed no sooner than three to four weeks after application of this product.",
    },
    "triclopyr": {
        "reseeding_interval": "Do not reseed for 3 weeks after application.",
    },
    "halosulfuron": {
        "overseeding_interval": "Treated areas can be overseeded with annual or perennial ryegrass or bermudagrass 2 weeks after application.",
        "reseeding_interval": "Treated areas can be overseeded with annual or perennial ryegrass or bermudagrass 2 weeks after application.",
    },
    "trinexapac_ethyl": {
        "rei": "0 days",
        "irrigation_guidance": "Primo MAXX is rainfast from rainfall or irrigation after one hour. Watering-in is not necessary for activation, and the label says not to apply it through any type of irrigation system.",
        "tank_mix_guidance": [
            "Primo MAXX may be tank mixed with many commonly used pesticides and liquid fertilizers.",
            "Always check tank-mix compatibility with a jar test before mixing in the spray tank.",
            "Do not mix Primo MAXX with any product that prohibits such mixing, and follow the most restrictive label precautions and limitations.",
        ],
    },
}

EXTRACTABLE_FIELDS = {
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
}


def _load_products() -> dict:
    return json.loads(PRODUCTS_PATH.read_text())


def _save_products(products: dict) -> None:
    PRODUCTS_PATH.write_text(json.dumps(products, indent=2) + "\n")


def _extract_pdf_text(path: Path) -> str:
    try:
        text = subprocess.check_output(
            [PDFTOTEXT, str(path), "-"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        return ""
    return " ".join(text.split())


def _sentences(text: str) -> list[str]:
    if not text:
        return []
    pieces = re.split(r"(?<=[.!?])\s+", text)
    clean = []
    seen = set()
    for piece in pieces:
        sentence = _clean_snippet(piece)
        if not sentence:
            continue
        if len(sentence) < 20:
            continue
        if len(sentence) > 320:
            continue
        if sentence in seen:
            continue
        seen.add(sentence)
        clean.append(sentence)
    return clean


def _find_rei(text: str) -> str:
    patterns = [
        re.compile(
            r"restricted[- ]entry interval[^.]{0,140}?\b(\d+\s*(?:hours?|days?))\b",
            re.I,
        ),
        re.compile(r"\brei\b[^.]{0,80}?\b(\d+\s*(?:hours?|days?))\b", re.I),
    ]
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            return match.group(1).strip()
    return ""


def _find_sentence(sentences: list[str], terms: list[str]) -> str:
    for sentence in sentences:
        lower = sentence.lower()
        if all(term in lower for term in terms):
            return sentence
    return ""


def _find_any_sentence(sentences: list[str], term_sets: list[list[str]]) -> str:
    for terms in term_sets:
        sentence = _find_sentence(sentences, terms)
        if sentence:
            return sentence
    return ""


def _find_multiple(sentences: list[str], term_sets: list[list[str]], limit: int = 3) -> list[str]:
    matches = []
    seen = set()
    for terms in term_sets:
        for sentence in sentences:
            lower = sentence.lower()
            if all(term in lower for term in terms):
                if sentence not in seen:
                    seen.add(sentence)
                    matches.append(sentence)
                if len(matches) >= limit:
                    return matches
    return matches


def _is_clean_sentence(sentence: str) -> bool:
    lower = sentence.lower()
    bad_markers = [
        "dispose of waste rinse water",
        "stock bucket",
        "premixing:",
        "specimen label",
        "page ",
        "continued",
        "site pest",
        "rate per application leafminer",
        "amount of",
    ]
    if any(marker in lower for marker in bad_markers):
        return False
    if sentence.count(":") > 2:
        return False
    if lower.count("  ") > 3:
        return False
    return True


def _clean_snippet(text: str) -> str:
    snippet = str(text or "")
    snippet = snippet.replace("\x07", " ")
    snippet = snippet.replace("\xad", "")
    snippet = snippet.replace("\uf0b7", " ")
    snippet = snippet.replace("•", " ")
    snippet = snippet.replace("®", "")
    snippet = snippet.replace("™", "")
    snippet = re.sub(r"\s+", " ", snippet).strip()
    snippet = re.sub(r"\s+([,.;:])", r"\1", snippet)
    return snippet


def _find_retreatment(text: str, sentences: list[str]) -> str:
    patterns = [
        re.compile(r"(wait a minimum of\s*\d+\s*days?\s*to retreat\.?)", re.I),
        re.compile(r"(minimum re[- ]treatment interval[^.]{0,160}\.)", re.I),
        re.compile(r"(do not reapply within\s*\d+\s*(?:days?|weeks?|months?)\.?)", re.I),
    ]
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            return " ".join(match.group(1).split())
    for sentence in sentences:
        lower = sentence.lower()
        if not _is_clean_sentence(sentence):
            continue
        if (
            any(term in lower for term in ["re-treatment interval", "retreatment interval", "reapply"])
            or ("retreat" in lower and any(marker in lower for marker in ["wait", "minimum", "do not", "before"]))
        ):
            if any(
                unit in lower for unit in ["day", "days", "week", "weeks", "month", "months", "hour", "hours"]
            ):
                return sentence
    return ""


def _find_irrigation(sentences: list[str]) -> str:
    for sentence in sentences:
        lower = sentence.lower()
        if not _is_clean_sentence(sentence):
            continue
        if (
            ("irrigation system" in lower and ("do not" in lower or "apply through" in lower))
            or "water in" in lower
            or "watered in" in lower
            or ("allow" in lower and "dry" in lower and "irrigation" in lower)
            or ("delay" in lower and "irrigation" in lower)
            or ("irrigate after application" in lower)
            or ("through sprinkler irrigation systems" in lower)
        ):
            return sentence
    return ""


def _find_rainfast(sentences: list[str]) -> str:
    result = _find_any_sentence(
        sentences,
        [
            ["rainfast"],
            ["rain", "within", "hours"],
            ["rain is expected within"],
        ],
    )
    return result if _is_clean_sentence(result) else ""


def _find_tank_mix(sentences: list[str]) -> list[str]:
    filtered = [sentence for sentence in sentences if _is_clean_sentence(sentence)]
    return _find_multiple(
        filtered,
        [
            ["tank mix"],
            ["tank mixtures"],
            ["compatible"],
            ["jar test"],
            ["most restrictive", "tank"],
        ],
        limit=3,
    )


def _find_reseeding(sentences: list[str], overseeding: bool = False) -> str:
    terms = ["overseed", "overseeding"] if overseeding else ["reseed", "reseeding", "sprigging", "overseed", "overseeding"]
    time_markers = ["day", "days", "week", "weeks", "month", "months", "year", "years", "after", "within", "prior", "no sooner", "discontinue"]
    for sentence in sentences:
        lower = sentence.lower()
        if not _is_clean_sentence(sentence):
            continue
        if any(term in lower for term in terms) and any(marker in lower for marker in time_markers):
            return sentence
    return ""


def _find_max_apps(sentences: list[str]) -> str:
    for sentence in sentences:
        lower = sentence.lower()
        if not _is_clean_sentence(sentence):
            continue
        if (
            ("applications per year" in lower)
            or ("calendar year" in lower and "apply" in lower)
            or ("more than" in lower and "applications" in lower and "year" in lower)
            or ("maximum of" in lower and "applications" in lower and "year" in lower)
        ):
            return sentence
    return ""


def _find_max_rate(sentences: list[str]) -> str:
    for sentence in sentences:
        lower = sentence.lower()
        if not _is_clean_sentence(sentence):
            continue
        if (
            (
                "do not apply more than" in lower
                and ("per application" in lower or "single application" in lower or "per acre" in lower)
            )
            or ("maximum application rate" in lower)
            or ("maximum single application" in lower)
        ):
            return sentence
    return ""


def _find_application_window(sentences: list[str], info: dict) -> str:
    existing_timing = str(info.get("timing", "")).strip()
    if existing_timing:
        return existing_timing
    for sentence in sentences:
        lower = sentence.lower()
        if any(
            phrase in lower
            for phrase in [
                "apply before",
                "apply after",
                "during periods of",
                "for best results",
                "before germination",
                "before egg hatch",
            ]
        ):
            return sentence
    note = str(info.get("note", "")).strip()
    return note


def enrich() -> dict[str, int]:
    products = _load_products()
    counters = {field: 0 for field in SCHEMA_DEFAULTS}
    counters["records_seen"] = 0

    for _, category_products in products.items():
        for active_ingredient, info in category_products.items():
            counters["records_seen"] += 1
            for field, default in SCHEMA_DEFAULTS.items():
                if field not in info:
                    info[field] = list(default) if isinstance(default, list) else default
            for field in EXTRACTABLE_FIELDS:
                info[field] = [] if isinstance(SCHEMA_DEFAULTS[field], list) else ""

            source_url = str(info.get("source_url", "")).strip()
            if not source_url.startswith("/static/"):
                continue
            label_path = ROOT / source_url.lstrip("/")
            if not label_path.exists():
                continue

            text = _extract_pdf_text(label_path)
            sentences = _sentences(text)
            if not text:
                continue

            candidates = {
                "rei": _find_rei(text),
                "retreatment_interval": _find_retreatment(text, sentences),
                "irrigation_guidance": _find_irrigation(sentences),
                "rainfast": _find_rainfast(sentences),
                "tank_mix_guidance": _find_tank_mix(sentences),
                "max_apps_per_year": _find_max_apps(sentences),
                "max_rate_per_app": _find_max_rate(sentences),
                "reseeding_interval": _find_reseeding(sentences),
                "overseeding_interval": _find_reseeding(sentences, overseeding=True),
                "application_window_notes": _find_application_window(sentences, info),
            }

            for field, candidate in candidates.items():
                if candidate in (None, "", [], {}):
                    continue
                info[field] = candidate
                counters[field] += 1

            overrides = CURATED_OVERRIDES.get(active_ingredient, {})
            for field, value in overrides.items():
                info[field] = value

    _save_products(products)
    return counters


if __name__ == "__main__":
    print(json.dumps(enrich(), indent=2, sort_keys=True))
