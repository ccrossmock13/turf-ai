"""Small course-profile memory for the simple Greenside AI app.

This intentionally stays file-based so the older app can learn course context
without adding a new database or changing the framework.
"""

from __future__ import annotations

import copy
import json
import os
import re
from datetime import date, datetime
from typing import Any

from config import Config
from persistence_backend import dynamodb_table, to_plain_value, using_dynamodb


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


def _profile_path(profile_key: str | None = None) -> str:
    """Return a safe profile file path, optionally scoped to one session."""
    if not profile_key:
        return PROFILE_PATH
    safe_key = re.sub(r"[^a-zA-Z0-9_-]", "", str(profile_key))[:80]
    if not safe_key:
        return PROFILE_PATH
    return os.path.join(os.getenv("DATA_DIR", "data"), "course_profiles", f"{safe_key}.json")


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


def load_course_profile(profile_key: str | None = None) -> dict[str, Any]:
    """Load the persisted course profile, falling back to a blank profile."""
    if using_dynamodb():
        key = str(profile_key or "default")
        response = dynamodb_table(Config.DYNAMODB_COURSE_PROFILES_TABLE).get_item(Key={"profile_key": key})
        item = response.get("Item")
        if not item:
            return copy.deepcopy(DEFAULT_PROFILE)
        return _merge_profile(to_plain_value(item.get("profile")))
    try:
        with open(_profile_path(profile_key), "r", encoding="utf-8") as profile_file:
            return _merge_profile(json.load(profile_file))
    except FileNotFoundError:
        return copy.deepcopy(DEFAULT_PROFILE)
    except Exception:
        return copy.deepcopy(DEFAULT_PROFILE)


def save_course_profile(profile: dict[str, Any], profile_key: str | None = None) -> dict[str, Any]:
    """Persist a sanitized course profile and return the saved shape."""
    cleaned = _merge_profile(profile)
    if using_dynamodb():
        key = str(profile_key or "default")
        dynamodb_table(Config.DYNAMODB_COURSE_PROFILES_TABLE).put_item(Item={"profile_key": key, "profile": cleaned})
        return cleaned
    path = _profile_path(profile_key)
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as profile_file:
        json.dump(cleaned, profile_file, indent=2, sort_keys=True)
    return cleaned


def delete_course_profile(profile_key: str | None = None) -> bool:
    """Delete one stored course profile if it exists."""
    if using_dynamodb():
        key = str(profile_key or "default")
        dynamodb_table(Config.DYNAMODB_COURSE_PROFILES_TABLE).delete_item(Key={"profile_key": key})
        return True
    path = _profile_path(profile_key)
    try:
        os.remove(path)
        return True
    except FileNotFoundError:
        return False
    except Exception:
        return False


def update_course_profile(partial_profile: dict[str, Any], profile_key: str | None = None) -> dict[str, Any]:
    """Apply a partial profile update without wiping existing details."""
    current = load_course_profile(profile_key)
    if not isinstance(partial_profile, dict):
        return save_course_profile(current, profile_key)

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

    return save_course_profile(current, profile_key)


def format_course_profile_for_prompt(profile: dict[str, Any] | None = None, profile_key: str | None = None) -> str:
    """Return compact course context for prompt injection."""
    profile = _merge_profile(profile or load_course_profile(profile_key))
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

    inferred = infer_regional_management_context(profile)
    if inferred.get("regional_archetype"):
        lines.append(f"Inferred regional archetype: {inferred['regional_archetype']}")
    if inferred.get("seasonal_operating_plan"):
        lines.append(f"Auto seasonal plan: {inferred['seasonal_operating_plan']}")
    if inferred.get("regional_pressure_calendar"):
        lines.append(f"Auto pressure calendar: {inferred['regional_pressure_calendar']}")

    if not lines:
        return ""
    profile_block = "--- COURSE PROFILE MEMORY ---\n" + "\n".join(lines)
    snapshot_block = format_current_management_snapshot(profile=profile)
    if snapshot_block:
        return profile_block + "\n\n" + snapshot_block
    return profile_block


def summarize_known_profile_for_questions(profile: dict[str, Any] | None = None, profile_key: str | None = None) -> str:
    """Return a short plain-English summary for clarification prompts."""
    profile = _merge_profile(profile or load_course_profile(profile_key))
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


def infer_regional_management_context(profile: dict[str, Any] | None = None, profile_key: str | None = None) -> dict[str, str]:
    """Infer a likely regional turf-management archetype from saved profile details."""
    profile = _merge_profile(profile or load_course_profile(profile_key))
    region_text = f" {profile.get('region', '')} ".lower()
    surface_text = " ".join(str(value).lower() for value in profile.get("surfaces", {}).values() if value)

    warm_terms = ("bermuda", "bermudagrass", "zoysia", "zoysiagrass", "st augustine", "st. augustine", "centipede")
    cool_terms = ("bentgrass", "creeping bent", "poa", "annual bluegrass", "bluegrass", "kentucky bluegrass", "fescue", "ryegrass")

    has_warm = any(term in surface_text for term in warm_terms)
    has_cool = any(term in surface_text for term in cool_terms)

    def has_any(*terms: str) -> bool:
        return any(term in region_text for term in terms)

    inferred: dict[str, str] = {}

    if has_any("arizona", " az ", "phoenix", "scottsdale", "tucson", "nevada", " nv ", "las vegas", "desert", "palm springs"):
        if has_warm or "bermuda" in surface_text:
            inferred = {
                "regional_archetype": "Arid West bermudagrass",
                "climate_zone_playbook": "Arid west warm season climate",
                "seasonal_operating_plan": "Arid west bermudagrass seasonal operating plan",
                "regional_pressure_calendar": "Arid west bermudagrass regional pressure calendar",
                "retrieval_region_hint": "arid west bermudagrass",
            }
    elif has_any("transition zone", "kentucky", " ky ", "tennessee", " tn ", "virginia", " va ", "maryland", " md ", "missouri", " mo ", "kansas", " ks ", "north carolina", " nc "):
        if has_cool or not has_warm:
            inferred = {
                "regional_archetype": "Cool-season transition zone",
                "climate_zone_playbook": "Humid transition zone cool season climate",
                "seasonal_operating_plan": "Cool season transition zone seasonal operating plan",
                "regional_pressure_calendar": "Transition zone cool season regional pressure calendar",
                "retrieval_region_hint": "transition zone",
            }
    elif has_any("florida", " fl ", "georgia", " ga ", "alabama", " al ", "mississippi", " ms ", "louisiana", " la ", "south carolina", " sc "):
        if has_warm or not has_cool:
            inferred = {
                "regional_archetype": "Warm-season Southeast",
                "climate_zone_playbook": "Humid southeast warm season climate",
                "seasonal_operating_plan": "Warm season southeast seasonal operating plan",
                "regional_pressure_calendar": "Southeast warm season regional pressure calendar",
                "retrieval_region_hint": "southeast warm season",
            }
    elif has_any("minnesota", " mn ", "wisconsin", " wi ", "michigan", " mi ", "new york", " ny ", "massachusetts", " ma ", "maine", " me ", "vermont", " vt ", "new hampshire", " nh ", "north dakota", " nd ", "south dakota", " sd ", "iowa", " ia "):
        if has_cool or not has_warm:
            inferred = {
                "regional_archetype": "Northern cool season",
                "climate_zone_playbook": "Northern cool season intensive climate",
                "seasonal_operating_plan": "Northern cool season seasonal operating plan",
                "regional_pressure_calendar": "Northern cool season regional pressure calendar",
                "retrieval_region_hint": "northern cool season",
            }

    return inferred


def build_course_profile_kb_hint(profile: dict[str, Any] | None = None, profile_key: str | None = None) -> str:
    """Build a compact hint string so KB lookups can inherit saved regional context."""
    profile = _merge_profile(profile or load_course_profile(profile_key))
    inferred = infer_regional_management_context(profile)

    parts = []
    if inferred.get("regional_archetype"):
        parts.append(inferred["regional_archetype"])
    if inferred.get("climate_zone_playbook"):
        parts.append(inferred["climate_zone_playbook"])
    if inferred.get("seasonal_operating_plan"):
        parts.append(inferred["seasonal_operating_plan"])
    if inferred.get("regional_pressure_calendar"):
        parts.append(inferred["regional_pressure_calendar"])

    for surface, value in profile.get("surfaces", {}).items():
        cleaned = _clean_value(value)
        if cleaned:
            parts.append(f"{surface} {cleaned}")

    return " | ".join(parts[:8])


def _season_for_month(month: int) -> str:
    if month in (12, 1, 2):
        return "winter"
    if month in (3, 4, 5):
        return "spring"
    if month in (6, 7, 8):
        return "summer"
    return "fall"


def _detect_requested_surfaces(question: str) -> list[str]:
    """Find course surfaces explicitly requested in a question."""
    q = (question or "").lower()
    aliases = {
        "greens": ("green", "greens", "putting surface", "putting surfaces"),
        "tees": ("tee", "tees", "tee box", "tee boxes"),
        "fairways": ("fairway", "fairways"),
        "rough": ("rough", "roughs"),
    }
    requested = []
    for surface, terms in aliases.items():
        if any(re.search(rf"\b{re.escape(term)}\b", q) for term in terms):
            requested.append(surface)
    return requested


def _surface_recipe_lookup_name(surface: str, turf: str) -> str:
    """Map saved surface turf text to the nearest structured surface recipe."""
    turf_lower = (turf or "").lower()
    surface_lower = (surface or "").lower()

    if surface_lower == "greens":
        if "poa" in turf_lower or "annual bluegrass" in turf_lower:
            return "poa greens"
        if "bent" in turf_lower:
            return "bentgrass greens"
    if "bermuda" in turf_lower:
        if "rye" in turf_lower or "overseed" in turf_lower:
            return "overseeded bermudagrass"
        return "bermudagrass fairways"
    if "zoysia" in turf_lower:
        return "zoysiagrass fairways"
    if "fescue" in turf_lower:
        return "tall fescue sports turf"
    return f"{turf} {surface}".strip()


def _build_surface_focus_cards(
    profile: dict[str, Any],
    snapshot: dict[str, Any],
    requested_surfaces: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Build current-priority cards for each saved/requested course surface."""
    from knowledge_base import get_surface_management_recipe_info

    surfaces = profile.get("surfaces", {})
    requested = set(requested_surfaces or [])
    cards = []

    for surface in ("greens", "tees", "fairways", "rough"):
        turf = _clean_value(surfaces.get(surface))
        if not turf:
            continue
        if requested and surface not in requested:
            continue

        recipe = get_surface_management_recipe_info(_surface_recipe_lookup_name(surface, turf)) or {}
        risks = list(recipe.get("signature_risks", [])[:4])
        mowing = recipe.get("mowing_and_speed", {}) if isinstance(recipe.get("mowing_and_speed"), dict) else {}
        water = recipe.get("water_management", {}) if isinstance(recipe.get("water_management"), dict) else {}
        fertility = recipe.get("fertility", {}) if isinstance(recipe.get("fertility"), dict) else {}
        cultivation = recipe.get("cultivation", {}) if isinstance(recipe.get("cultivation"), dict) else {}

        regional_targets = list(snapshot.get("scouting_targets", [])[:3])
        scout_now = risks[:2] + [target for target in regional_targets if target not in risks[:2]]

        cultural_actions = []
        for section in (mowing, cultivation):
            approach = section.get("approach")
            if approach:
                cultural_actions.append(approach)

        watchouts = []
        for section in (mowing, water, fertility, cultivation):
            watchouts.extend(section.get("watchouts", [])[:1])
        watchouts.extend(snapshot.get("cautions", [])[:1])

        cards.append({
            "surface": surface,
            "turf": turf,
            "recipe": recipe.get("name", ""),
            "scout_now": scout_now[:4],
            "cultural": cultural_actions[:2],
            "water": water.get("approach", ""),
            "fertility": fertility.get("approach", ""),
            "spray_decision": (
                "Use the current scouting targets and timing windows to pick a target first; "
                "only then move to verified products and rates."
            ),
            "watchouts": watchouts[:4],
        })

    return cards


def build_current_management_snapshot(
    profile: dict[str, Any] | None = None,
    profile_key: str | None = None,
    as_of: date | datetime | None = None,
    question: str | None = None,
) -> dict[str, Any]:
    """Build a compact date-aware management snapshot from saved course context."""
    from knowledge_base import (
        get_regional_pressure_calendar_info,
        get_seasonal_operating_plan_info,
    )

    profile = _merge_profile(profile or load_course_profile(profile_key))
    inferred = infer_regional_management_context(profile)
    if not inferred:
        return {}

    current_date = as_of.date() if isinstance(as_of, datetime) else as_of or date.today()
    season = _season_for_month(current_date.month)
    month_name = current_date.strftime("%B")

    plan = get_seasonal_operating_plan_info(inferred.get("seasonal_operating_plan", "")) or {}
    pressure = get_regional_pressure_calendar_info(inferred.get("regional_pressure_calendar", "")) or {}

    priorities = list(plan.get(f"{season}_priorities", [])[:3])
    scouting_targets = list(pressure.get(f"{season}_pressures", [])[:4])
    cautions = list(plan.get("watchouts", [])[:3])

    timing_by_archetype = {
        "Cool-season transition zone": {
            "spring": ["crabgrass preemergent", "summer patch preventive", "brown patch preventive"],
            "summer": ["pythium blight preventive", "localized dry spot response", "brown patch preventive"],
            "fall": ["poa annua preemergent", "cool-season turf aeration timing"],
            "winter": ["poa annua seedhead suppression timing"],
        },
        "Northern cool season": {
            "spring": ["crabgrass preemergent", "cool-season turf aeration timing"],
            "summer": ["white grub preventive", "localized dry spot response"],
            "fall": ["poa annua preemergent", "cool-season turf aeration timing"],
            "winter": ["poa annua seedhead suppression timing"],
        },
        "Warm-season Southeast": {
            "spring": ["crabgrass preemergent", "goosegrass preemergent", "warm-season turf aeration timing"],
            "summer": ["white grub preventive", "localized dry spot response"],
            "fall": ["poa annua preemergent", "spring dead spot preventive"],
            "winter": ["poa annua seedhead suppression timing"],
        },
        "Arid West bermudagrass": {
            "spring": ["goosegrass preemergent", "crabgrass preemergent", "warm-season turf aeration timing"],
            "summer": ["localized dry spot response", "white grub preventive"],
            "fall": ["poa annua preemergent", "spring dead spot preventive"],
            "winter": ["poa annua seedhead suppression timing"],
        },
    }
    timing_windows = timing_by_archetype.get(inferred.get("regional_archetype", ""), {}).get(season, [])

    surface_focus = [
        f"{surface}: {value}"
        for surface, value in profile.get("surfaces", {}).items()
        if value
    ][:3]

    snapshot = {
        "date": current_date.isoformat(),
        "month": month_name,
        "season": season.title(),
        "regional_archetype": inferred.get("regional_archetype", ""),
        "seasonal_operating_plan": inferred.get("seasonal_operating_plan", ""),
        "regional_pressure_calendar": inferred.get("regional_pressure_calendar", ""),
        "surface_focus": surface_focus,
        "current_priorities": priorities,
        "scouting_targets": scouting_targets,
        "timing_windows": timing_windows,
        "cautions": cautions,
    }
    snapshot["surface_cards"] = _build_surface_focus_cards(
        profile,
        snapshot,
        requested_surfaces=_detect_requested_surfaces(question or ""),
    )
    return snapshot


def format_current_management_snapshot(
    profile: dict[str, Any] | None = None,
    profile_key: str | None = None,
    as_of: date | datetime | None = None,
    question: str | None = None,
) -> str:
    """Return a prompt-ready current management summary."""
    snapshot = build_current_management_snapshot(profile=profile, profile_key=profile_key, as_of=as_of, question=question)
    if not snapshot:
        return ""

    lines = [
        f"As of {snapshot['month']}, current season: {snapshot['season']}",
        f"Regional archetype: {snapshot['regional_archetype']}",
    ]
    if snapshot.get("surface_focus"):
        lines.append("Surface focus: " + "; ".join(snapshot["surface_focus"]))
    if snapshot.get("current_priorities"):
        lines.append("Current priorities: " + "; ".join(snapshot["current_priorities"]))
    if snapshot.get("scouting_targets"):
        lines.append("Scout now for: " + "; ".join(snapshot["scouting_targets"]))
    if snapshot.get("timing_windows"):
        lines.append("Relevant timing windows: " + "; ".join(snapshot["timing_windows"]))
    if snapshot.get("cautions"):
        lines.append("Current cautions: " + "; ".join(snapshot["cautions"]))
    if snapshot.get("surface_cards"):
        surface_bits = [
            f"{card['surface']}: {card['turf']}"
            for card in snapshot["surface_cards"][:4]
        ]
        lines.append("Surface-specific focus: " + "; ".join(surface_bits))

    return "--- CURRENT MANAGEMENT SNAPSHOT ---\n" + "\n".join(lines)


def build_operational_guidance_response(
    question: str,
    profile: dict[str, Any] | None = None,
    profile_key: str | None = None,
    as_of: date | datetime | None = None,
) -> dict[str, Any] | None:
    """Return a deterministic current-priorities answer for operational questions."""
    q = (question or "").strip().lower()
    if not q:
        return None

    priority_terms = (
        "what should we do", "what should i do", "what should we focus on",
        "priorities", "priority", "this month", "this season", "right now",
    )
    scout_terms = ("what should we scout", "what should i scout", "scout for", "scouting")
    spray_terms = (
        "what should i spray this month", "what should i apply this month",
        "what do i need to spray", "what do i spray now",
        "what should i put down this month", "what should i apply now",
        "what product should i use this month",
    )

    keep_healthy_pattern = re.search(
        r"\bhow do i keep\b.*\b(healthy|recovering)\b",
        q,
    )
    seasonal_watch_pattern = re.search(
        r"\bwhat (?:should|do) i watch(?: for)?\b",
        q,
    )

    is_priority = any(term in q for term in priority_terms) or bool(keep_healthy_pattern)
    is_scout = any(term in q for term in scout_terms) or bool(seasonal_watch_pattern)
    is_spray = any(term in q for term in spray_terms)
    if not any((is_priority, is_scout, is_spray)):
        return None

    profile = _merge_profile(profile or load_course_profile(profile_key))
    requested_surfaces = _detect_requested_surfaces(question)
    snapshot = build_current_management_snapshot(
        profile=profile,
        profile_key=profile_key,
        as_of=as_of,
        question=question,
    )
    if not snapshot:
        return None

    month = snapshot.get("month", "")
    season = snapshot.get("season", "")
    archetype = snapshot.get("regional_archetype", "")
    surface_focus = snapshot.get("surface_focus", [])
    priorities = snapshot.get("current_priorities", [])
    scouting_targets = snapshot.get("scouting_targets", [])
    timing_windows = snapshot.get("timing_windows", [])
    cautions = snapshot.get("cautions", [])
    surface_cards = snapshot.get("surface_cards", [])

    intro = f"This is the current management snapshot for {month} on your {archetype} setup."
    if surface_focus:
        intro += " Surface focus: " + "; ".join(surface_focus) + "."

    def append_surface_cards(lines: list[str], heading: str = "Surface-specific next actions:") -> None:
        if not surface_cards:
            return
        lines.extend(["", heading])
        for card in surface_cards:
            lines.append(f"- **{card['surface'].title()} ({card['turf']})**")
            if card.get("scout_now"):
                lines.append("  Scout: " + "; ".join(card["scout_now"][:4]))
            if card.get("cultural"):
                lines.append("  Cultural: " + "; ".join(card["cultural"][:2]))
            if card.get("water"):
                lines.append("  Water: " + card["water"])
            if card.get("fertility"):
                lines.append("  Fertility: " + card["fertility"])
            lines.append("  Spray decision: " + card["spray_decision"])
            if card.get("watchouts"):
                lines.append("  Watchouts: " + "; ".join(card["watchouts"][:3]))

    if is_spray:
        answer_lines = [
            intro,
            "",
            f"I would not jump straight to a product list for {month} without a target, but these are the main buckets to work from first:",
        ]
        if scouting_targets:
            answer_lines.append("- Main pressure to scout now: " + "; ".join(scouting_targets[:4]))
        if timing_windows:
            answer_lines.append("- Relevant timing windows: " + "; ".join(timing_windows[:4]))
        if priorities:
            answer_lines.append("- Operational priorities: " + "; ".join(priorities[:3]))
        answer_lines.append("- To narrow this to products and rates, tell me the target and surface: disease, weeds, insects, fertility, or a specific symptom.")
        append_surface_cards(answer_lines)
        label = "Profile-Based Spray Guidance"
    elif is_scout:
        answer_lines = [
            intro,
            "",
            f"For {season.lower()} scouting, I would focus on:",
        ]
        if scouting_targets:
            answer_lines.append("- " + "; ".join(scouting_targets[:4]))
        if timing_windows:
            answer_lines.append("- Timing windows to watch: " + "; ".join(timing_windows[:4]))
        if cautions:
            answer_lines.append("- Current cautions: " + "; ".join(cautions[:3]))
        append_surface_cards(answer_lines, heading="Surface-specific scouting:")
        label = "Profile-Based Scouting"
    else:
        answer_lines = [
            intro,
            "",
            f"Top priorities for {month}:",
        ]
        if priorities:
            answer_lines.append("- " + "; ".join(priorities[:3]))
        if scouting_targets:
            answer_lines.append("- Scout now for: " + "; ".join(scouting_targets[:4]))
        if timing_windows:
            answer_lines.append("- Timing windows: " + "; ".join(timing_windows[:4]))
        if cautions:
            answer_lines.append("- Watchouts: " + "; ".join(cautions[:3]))
        append_surface_cards(answer_lines)
        label = "Current Priorities"
        if requested_surfaces:
            label = "Surface-Specific Priorities"

    return {
        "answer": "\n".join(answer_lines),
        "sources": [
            {
                "name": "Course Profile Memory",
                "type": "course_profile",
                "note": "User-provided course context used to infer region and surface priorities",
            },
            {
                "name": "Current Management Snapshot",
                "type": "course_profile",
                "note": f"Deterministic {month} {season.lower()} priorities from saved regional context",
            },
        ],
        "confidence": {"score": 92, "label": label},
        "needs_review": False,
        "operational_guidance": True,
        "snapshot": snapshot,
    }


def build_general_turf_guidance_response(
    question: str,
    profile: dict[str, Any] | None = None,
    profile_key: str | None = None,
    as_of: date | datetime | None = None,
) -> dict[str, Any] | None:
    """Return deterministic broad agronomy guidance for general turf-health questions."""
    q = (question or "").strip().lower()
    if not q:
        return None

    if _looks_like_bentgrass_seeding_prep_question(q):
        return _build_bentgrass_seeding_prep_response(profile=profile, profile_key=profile_key)

    weekly_watch_mode = bool(re.search(r"\bwhat should i be watching\b", q))

    broad_terms = (
        "turf health", "keep turf healthy", "keep turf in good shape", "healthy turf",
        "what matters most", "perform well", "what makes turf", "in general",
        "generally", "overall", "biggest drivers", "fundamentals", "summer stress",
        "what gets superintendents in trouble fastest", "what am i probably missing",
    )
    guidance_patterns = (
        re.search(r"\bhow do i keep\b.*\bturf\b", q),
        re.search(r"\bwhat should i know about\b.*\bturf\b", q),
        re.search(r"\bwhat should i know about\b.*\bgreens\b", q),
        re.search(r"\bwhat should i know about\b.*\bfairways\b", q),
        re.search(r"\bhow do i keep\b.*\bgreens?\b", q),
        re.search(r"\bhow do i keep\b.*\bfairways?\b", q),
        re.search(r"\bhow do i keep\b.*\balive\b", q),
        re.search(r"\bwhat should i be watching\b", q),
        re.search(r"\bwhat makes\b.*\bperform well\b", q),
        re.search(r"\bwhat matters most\b", q),
        re.search(r"\bwhat gets superintendents in trouble fastest\b", q),
        re.search(r"\bwhat am i probably missing\b", q),
        re.search(r"\bsummer stress\b", q),
    )
    if not any(term in q for term in broad_terms) and not any(guidance_patterns):
        return None

    profile = _merge_profile(profile or load_course_profile(profile_key))
    snapshot = build_current_management_snapshot(
        profile=profile,
        profile_key=profile_key,
        as_of=as_of,
        question=question,
    )
    requested_surfaces = _detect_requested_surfaces(question)
    surface_cards = snapshot.get("surface_cards", []) if snapshot else []
    if requested_surfaces and surface_cards:
        surface_cards = [card for card in surface_cards if card.get("surface") in requested_surfaces]

    month = snapshot.get("month", "") if snapshot else ""
    season = snapshot.get("season", "") if snapshot else ""
    archetype = snapshot.get("regional_archetype", "") if snapshot else ""
    scouting_targets = snapshot.get("scouting_targets", []) if snapshot else []
    timing_windows = snapshot.get("timing_windows", []) if snapshot else []
    cautions = snapshot.get("cautions", []) if snapshot else []

    surface_focus = [
        f"{surface}: {value}"
        for surface, value in profile.get("surfaces", {}).items()
        if value
    ][:4]
    if weekly_watch_mode:
        intro = (
            "**Bottom Line:** The best weekly watch list is the one that catches stress early enough to change the week before the surface gets behind."
        )
        if month and archetype:
            intro += (
                f" For {month} in your {archetype} setup, that usually means watching root strength, moisture-by-depth, and stress stacking before the canopy starts asking for rescue."
            )
    elif "what gets superintendents in trouble fastest" in q or "summer stress" in q:
        intro = (
            "**Bottom Line:** During summer stress, the biggest mistakes are usually not dramatic. They are the extra small pushes that stack onto turf that was already short on recovery room."
        )
        if month and archetype:
            intro += (
                f" In {month} under your {archetype} conditions, that usually means protecting roots, oxygen, and recovery capacity before you ask for one more day of pace or appearance."
            )
    elif "what am i probably missing" in q:
        intro = (
            "**Bottom Line:** When the disease program looks busy but the surface still feels flat, the thing being missed is usually plant recovery capacity, not one more product slot."
        )
    else:
        intro = (
            "**Bottom Line:** Most turf problems get easier when you stop treating them like isolated events "
            "and manage the whole plant first: water and oxygen, root strength, stress load, and disciplined scouting before reacting."
        )
        if month and archetype:
            intro += (
                f" For {month} in your {archetype} setup, that usually means staying ahead of the seasonal "
                "stress stack instead of chasing symptoms after the surface already feels behind."
            )

    answer_lines = [intro]
    if surface_focus:
        answer_lines.extend([
            "",
            "**Course context I'm using:** " + "; ".join(surface_focus) + ".",
            "The question underneath all of this is: are we helping the plant recover, or just asking it to hide stress for another day?",
        ])

    answer_lines.extend([
        "",
        "**What I'd watch first this week:**" if weekly_watch_mode else "**What matters most:**",
        "- **Water and oxygen together**: avoid both chronic wetness and chronic deficit, and check moisture by depth instead of judging the surface alone.",
        "- **Roots before color**: if roots are weak, shallow, or oxygen-limited, extra fertility can make the turf look better briefly without fixing why it is vulnerable.",
        "- **Stress budget discipline**: mowing, rolling, traffic, heat, humidity, and PGR all hit the same plant, so a small extra push matters more than people think.",
        "- **Surface physical condition**: firmness, organic matter, topdressing consistency, and infiltration quietly decide how forgiving the turf will be.",
        "- **Scouting before reacting**: pattern, roots, leaf evidence, and recent weather usually tell you more than the first dramatic symptom does.",
    ])
    answer_lines.extend([
        "",
        "**What usually gets people in trouble first:**",
        "- Trying to win back appearance before the roots and moisture picture make sense.",
        "- Treating every weak area like a spray problem when the surface is really carrying a water, traffic, or oxygen problem.",
        "- Letting one extra stress stack onto turf that was already tight from heat, humidity, pace, or mechanical pressure.",
    ])

    if scouting_targets or timing_windows or cautions:
        answer_lines.append("")
        answer_lines.append("**What I'd watch first today:**")
        if scouting_targets:
            answer_lines.append("- Start with the current pressures: " + "; ".join(scouting_targets[:4]))
        if timing_windows:
            answer_lines.append("- Then look at the timing windows that matter right now: " + "; ".join(timing_windows[:4]))
        if cautions:
            answer_lines.append("- Do not get trapped by the usual mistakes: " + "; ".join(cautions[:3]))

    if surface_cards:
        answer_lines.extend(["", "**Surface-specific emphasis:**"])
        for card in surface_cards[:3]:
            line = f"- **{card['surface'].title()} ({card['turf']})**: "
            priorities = []
            if card.get("scout_now"):
                priorities.append("watch " + "; ".join(card["scout_now"][:2]))
            if card.get("cultural"):
                focus = str(card["cultural"][0]).strip().rstrip(".")
                if focus:
                    priorities.append(focus)
            if card.get("watchouts"):
                priorities.append("be careful with " + "; ".join(card["watchouts"][:2]))
            answer_lines.append(line + ". ".join(priorities))

    short_list = []
    if scouting_targets:
        short_list.append("Scout the highest-likelihood pressures before changing the program.")
    if cautions:
        short_list.append("Protect the plant from stacking one more avoidable stress this week.")
    if surface_cards:
        short_list.append("Treat the weakest surface like the pace car for the rest of the property.")
    if short_list:
        answer_lines.extend([
            "",
            "**If I only had one walk this morning:**",
        ])
        answer_lines.extend(f"- {item}" for item in short_list[:3])
        answer_lines.extend([
            "",
            "**What I'd measure before lunch:**",
            "- Rooting depth and whether the weak spots are actually rooting shallower than the rest of the surface.",
            "- Moisture by depth, not just what the top looks like.",
            "- Whether the pattern follows traffic, shade, spray geometry, drainage, or a specific elevation change.",
        ])

    answer_lines.extend([
        "",
        "**What good operators usually do well:**",
        "- They stop small stress signals from stacking into a bigger recovery problem.",
        "- They use the pattern on the property to narrow the cause before changing the program.",
        "- They protect recovery capacity instead of trying to win every day on appearance alone.",
        "",
        "**When I would slow down before changing the program:**",
        "- When the pattern is unclear and the answer could still be water, roots, chemistry, traffic, or disease.",
        "- When the surface looks bad but the roots and moisture picture have not been checked yet.",
        "- When the turf is asking for recovery and the next change would just hide stress for another day.",
        "",
        "**What not to do:**",
        "- Do not treat every weak patch like a product problem first.",
        "- Do not chase short-term color at the expense of roots, firmness, or recovery capacity.",
        "- Do not ignore the pattern: where it shows up usually tells you more than how dramatic it looks.",
    ])

    return {
        "answer": "\n".join(answer_lines),
        "sources": [
            {
                "name": "Course Profile Memory",
                "type": "course_profile",
                "note": "Saved course context used to tailor broad turf guidance",
            },
            {
                "name": "General Turf Guidance",
                "type": "structured_kb",
                "note": "Deterministic general agronomy guidance built from profile and seasonal context",
            },
        ],
        "confidence": {"score": 90, "label": "General Turf Guidance"},
        "needs_review": False,
        "operational_guidance": True,
        "kb_verdict": "general_turf_guidance",
    }


def _looks_like_bentgrass_seeding_prep_question(question_lower: str) -> bool:
    seed_terms = ("seed", "seeding", "seeded", "seedbed", "grow-in", "grow in", "establishment")
    prep_terms = ("prepare", "preparation", "prep", "before", "getting ready", "ready for")
    green_terms = ("green", "greens", "bent", "bentgrass", "creeping bentgrass")
    return (
        any(term in question_lower for term in seed_terms)
        and any(term in question_lower for term in green_terms)
        and any(term in question_lower for term in prep_terms)
    )


def _build_bentgrass_seeding_prep_response(
    profile: dict[str, Any] | None = None,
    profile_key: str | None = None,
) -> dict[str, Any]:
    profile = _merge_profile(profile or load_course_profile(profile_key))
    surface_focus = [
        f"{surface}: {value}"
        for surface, value in profile.get("surfaces", {}).items()
        if value
    ][:4]

    answer_lines = [
        "**Bottom Line:** Preparing to seed a bentgrass green is mostly about giving the seed a clean, firm, oxygenated seedbed and a grow-in environment you can hold steady for the first few weeks.",
    ]
    if surface_focus:
        answer_lines.extend([
            "",
            "**Course context I'm using:** " + "; ".join(surface_focus) + ".",
        ])
    answer_lines.extend([
        "",
        "**What I'd get right before seed goes down:**",
        "- **Seedbed firmness and smoothness**: firm enough that footprints are shallow and the surface stays true after final prep.",
        "- **Clean surface layer**: remove soft organic debris, weak thatch, and anything that keeps seed from touching the upper rootzone evenly.",
        "- **Moisture uniformity first**: correct dry fingers, puddling zones, and irrigation misses before the grow-in starts.",
        "- **Gas exchange and drainage**: if the top stays sealed or soft, germination can look fine at first and then stall when the roots need oxygen.",
        "- **Traffic plan**: know how you will protect the surface from carts, mowers, hoses, and foot traffic before the first seedling shows.",
        "",
        "**What usually sets bentgrass establishment back:**",
        "- Letting the surface stay wet on top but unstable underneath.",
        "- Chasing speed or cleanup too early instead of protecting the stand.",
        "- Uneven moisture during germination, then overcorrecting with too much water once seedlings appear.",
        "- Starting with a seedbed that is softer, dirtier, or less uniform than it looked during prep.",
        "",
        "**What I'd confirm before I pull the trigger:**",
        "- Irrigation coverage is even enough to hold the surface uniformly damp without making it anaerobic.",
        "- Topdressing, brushing, and mowing plans are set for establishment, not for mature-green expectations.",
        "- Any herbicide or residual-chemistry history is understood before seed goes out.",
        "- Labor is lined up for light, frequent grow-in attention during the first stretch instead of reactive rescue after the stand gets uneven.",
        "",
        "**What not to do:**",
        "- Do not start with a surface that still has unresolved drainage or sealing problems.",
        "- Do not let first-germination success fool you into thinking the rooting environment is good enough.",
        "- Do not turn it into a product question first when the seedbed and moisture plan are still the real swing factors.",
    ])

    return {
        "answer": "\n".join(answer_lines),
        "sources": [
            {
                "name": "General Turf Guidance",
                "type": "structured_kb",
                "note": "Deterministic turf-establishment guidance for bentgrass green preparation",
            },
        ],
        "confidence": {"score": 91, "label": "General Turf Guidance"},
        "needs_review": False,
        "operational_guidance": True,
        "kb_verdict": "general_turf_guidance",
        "grounding": {"verified": True, "issues": []},
    }


def apply_course_profile_updates(text: str, profile_key: str | None = None) -> dict[str, Any]:
    """Learn profile details only when the user states them explicitly."""
    text = text or ""
    profile = load_course_profile(profile_key)
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
        save_course_profile(profile, profile_key)
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
