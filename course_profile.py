"""Small course-profile memory for the simple Greenside AI app.

This intentionally stays file-based so the older app can learn course context
without adding a new database or changing the framework.
"""

from __future__ import annotations

import copy
import json
import os
import re
from typing import Any


DEFAULT_PROFILE = {
    "course_name": "",
    "region": "",
    "surfaces": {
        "greens": "",
        "tees": "",
        "fairways": "",
        "rough": "",
    },
    "soil": "",
    "mowing_heights": {
        "greens": "",
        "tees": "",
        "fairways": "",
        "rough": "",
    },
    "preferred_products": [],
    "products_to_avoid": [],
    "notes": [],
}

PROFILE_PATH = os.path.join(os.getenv("DATA_DIR", "data"), "course_profile.json")


def _clean_value(value: Any, max_length: int = 120) -> str:
    """Normalize user-stated profile values without getting clever."""
    if value is None:
        return ""
    cleaned = str(value).strip().strip('"').strip("'").strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = cleaned.rstrip(" .!?")
    return cleaned[:max_length]


def _merge_profile(raw_profile: dict[str, Any] | None) -> dict[str, Any]:
    """Merge a loaded/supplied profile into the known safe schema."""
    profile = copy.deepcopy(DEFAULT_PROFILE)
    if not isinstance(raw_profile, dict):
        return profile

    for key in ("course_name", "region", "soil"):
        profile[key] = _clean_value(raw_profile.get(key))

    for section in ("surfaces", "mowing_heights"):
        values = raw_profile.get(section, {})
        if isinstance(values, dict):
            for surface in profile[section]:
                profile[section][surface] = _clean_value(values.get(surface))

    for key in ("preferred_products", "products_to_avoid", "notes"):
        values = raw_profile.get(key, [])
        if isinstance(values, str):
            values = [values]
        if isinstance(values, list):
            profile[key] = [
                cleaned
                for cleaned in (_clean_value(item) for item in values)
                if cleaned
            ][:20]

    return profile


def load_course_profile() -> dict[str, Any]:
    """Load the persisted course profile, falling back to a blank profile."""
    try:
        with open(PROFILE_PATH, "r", encoding="utf-8") as profile_file:
            return _merge_profile(json.load(profile_file))
    except FileNotFoundError:
        return copy.deepcopy(DEFAULT_PROFILE)
    except Exception:
        return copy.deepcopy(DEFAULT_PROFILE)


def save_course_profile(profile: dict[str, Any]) -> dict[str, Any]:
    """Persist a sanitized course profile and return the saved shape."""
    cleaned = _merge_profile(profile)
    directory = os.path.dirname(PROFILE_PATH)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(PROFILE_PATH, "w", encoding="utf-8") as profile_file:
        json.dump(cleaned, profile_file, indent=2, sort_keys=True)
    return cleaned


def update_course_profile(partial_profile: dict[str, Any]) -> dict[str, Any]:
    """Apply a partial profile update without wiping existing details."""
    current = load_course_profile()
    if not isinstance(partial_profile, dict):
        return save_course_profile(current)

    for key in ("course_name", "region", "soil"):
        if key in partial_profile:
            current[key] = _clean_value(partial_profile.get(key))

    for section in ("surfaces", "mowing_heights"):
        values = partial_profile.get(section)
        if isinstance(values, dict):
            for surface in current[section]:
                if surface in values:
                    current[section][surface] = _clean_value(values.get(surface))

    for key in ("preferred_products", "products_to_avoid", "notes"):
        if key in partial_profile:
            values = partial_profile.get(key, [])
            if isinstance(values, str):
                values = [values]
            if isinstance(values, list):
                current[key] = [
                    cleaned
                    for cleaned in (_clean_value(item) for item in values)
                    if cleaned
                ][:20]

    return save_course_profile(current)


def format_course_profile_for_prompt(profile: dict[str, Any] | None = None) -> str:
    """Return compact course context for prompt injection."""
    profile = _merge_profile(profile or load_course_profile())
    lines = []

    if profile["course_name"]:
        lines.append(f"Course: {profile['course_name']}")
    if profile["region"]:
        lines.append(f"Region/location: {profile['region']}")
    if profile["soil"]:
        lines.append(f"Soil note: {profile['soil']}")

    surface_parts = [
        f"{surface}: {value}"
        for surface, value in profile["surfaces"].items()
        if value
    ]
    if surface_parts:
        lines.append("Turf surfaces: " + "; ".join(surface_parts))

    mowing_parts = [
        f"{surface}: {value}"
        for surface, value in profile["mowing_heights"].items()
        if value
    ]
    if mowing_parts:
        lines.append("Mowing heights: " + "; ".join(mowing_parts))

    if profile["preferred_products"]:
        lines.append("Preferred products: " + ", ".join(profile["preferred_products"]))
    if profile["products_to_avoid"]:
        lines.append("Products to avoid: " + ", ".join(profile["products_to_avoid"]))
    if profile["notes"]:
        lines.append("Course notes: " + "; ".join(profile["notes"][:5]))

    if not lines:
        return ""
    return "--- COURSE PROFILE MEMORY ---\n" + "\n".join(lines)


def summarize_known_profile_for_questions(profile: dict[str, Any] | None = None) -> str:
    """Return a short plain-English summary for clarification prompts."""
    profile = _merge_profile(profile or load_course_profile())
    known = []
    if profile["region"]:
        known.append(f"region: {profile['region']}")
    for surface, value in profile["surfaces"].items():
        if value:
            known.append(f"{surface}: {value}")
    if profile["soil"]:
        known.append(f"soil: {profile['soil']}")
    if profile["products_to_avoid"]:
        known.append("avoid: " + ", ".join(profile["products_to_avoid"][:3]))
    if not known:
        return ""
    return "; ".join(known[:6])


def apply_course_profile_updates(text: str) -> dict[str, Any]:
    """Learn profile details only when the user states them explicitly."""
    text = text or ""
    profile = load_course_profile()
    updates: dict[str, Any] = {}

    course_name_match = re.search(
        r"\b(?:our course is|course name is|we are|we're)\s+([^;\n]+)",
        text,
        re.IGNORECASE,
    )
    if course_name_match and not re.search(r"\b(?:in|located)\s+", course_name_match.group(0), re.IGNORECASE):
        cleaned = _clean_value(course_name_match.group(1), max_length=80)
        if cleaned:
            profile["course_name"] = cleaned
            updates["course_name"] = cleaned

    surface_pattern = re.compile(
        r"\b(?:remember\s+)?(?:our|my)\s+"
        r"(greens|tees|fairways|rough)\s+(?:are|is)\s+([^;\n]+)",
        re.IGNORECASE,
    )
    for surface, value in surface_pattern.findall(text):
        cleaned = _clean_value(value)
        if cleaned:
            surface = surface.lower()
            profile["surfaces"][surface] = cleaned
            updates[f"surfaces.{surface}"] = cleaned

    mow_pattern = re.compile(
        r"\b(?:we\s+)?(?:mow|cut)\s+"
        r"(greens|tees|fairways|rough)\s+(?:at|to)\s+([^;\n]+)",
        re.IGNORECASE,
    )
    for surface, value in mow_pattern.findall(text):
        cleaned = _clean_value(value)
        if cleaned:
            surface = surface.lower()
            profile["mowing_heights"][surface] = cleaned
            updates[f"mowing_heights.{surface}"] = cleaned

    region_match = re.search(
        r"\b(?:we are in|we're in|our course is in|located in)\s+([^;\n]+)",
        text,
        re.IGNORECASE,
    )
    if region_match:
        cleaned = _clean_value(region_match.group(1))
        if cleaned:
            profile["region"] = cleaned
            updates["region"] = cleaned

    soil_match = re.search(
        r"\b(?:our\s+)?soil(?:\s+type)?\s+(?:is|are)\s+([^;\n]+)",
        text,
        re.IGNORECASE,
    )
    if soil_match:
        cleaned = _clean_value(soil_match.group(1))
        if cleaned:
            profile["soil"] = cleaned
            updates["soil"] = cleaned

    avoid_match = re.search(
        r"\b(?:avoid|do not use|don't use)\s+([^;\n]+?)\s+on\s+(?:our|my)\s+course",
        text,
        re.IGNORECASE,
    )
    if avoid_match:
        cleaned = _clean_value(avoid_match.group(1), max_length=80)
        if cleaned and cleaned not in profile["products_to_avoid"]:
            profile["products_to_avoid"].append(cleaned)
            updates["products_to_avoid"] = profile["products_to_avoid"]

    preferred_match = re.search(
        r"\b(?:we prefer|our preferred product(?:s)?(?: are| is)|we like)\s+([^;\n]+)",
        text,
        re.IGNORECASE,
    )
    if preferred_match:
        products = [
            _clean_value(item, max_length=80)
            for item in re.split(r",|\band\b", preferred_match.group(1), flags=re.IGNORECASE)
        ]
        added = False
        for product in products:
            if product and product not in profile["preferred_products"]:
                profile["preferred_products"].append(product)
                added = True
        if added:
            profile["preferred_products"] = profile["preferred_products"][:20]
            updates["preferred_products"] = profile["preferred_products"]

    disease_pressure_match = re.search(
        r"\b(?:we have|our course has|we fight|we struggle with)\s+([^.;\n]+?)\s+"
        r"(?:pressure|issues|problems|every year|annually)",
        text,
        re.IGNORECASE,
    )
    if disease_pressure_match:
        note = _clean_value(f"Recurring pressure: {disease_pressure_match.group(1)}", max_length=120)
        if note and note not in profile["notes"]:
            profile["notes"].append(note)
            profile["notes"] = profile["notes"][:20]
            updates["notes"] = profile["notes"]

    if updates:
        save_course_profile(profile)
    return updates


def is_course_profile_only_update(text: str, updates: dict[str, Any]) -> bool:
    """Detect simple memory statements that should not go through full RAG."""
    if not updates:
        return False
    text = (text or "").strip().lower()
    if "?" in text:
        return False
    return (
        text.startswith("remember ")
        or text.startswith("our ")
        or text.startswith("my ")
        or text.startswith("we are in")
        or text.startswith("we're in")
        or text.startswith("course name is")
        or text.startswith("our course is in")
        or text.startswith("our course is")
        or text.startswith("located in")
        or text.startswith("we mow")
        or text.startswith("we cut")
        or text.startswith("we prefer")
        or text.startswith("we like")
        or text.startswith("avoid")
        or text.startswith("do not use")
        or text.startswith("don't use")
        or text.startswith("we have")
        or text.startswith("we fight")
        or text.startswith("we struggle")
    )
