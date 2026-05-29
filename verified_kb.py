"""Deterministic verified-answer layer for structured turf product data.

This module answers only when the local knowledge base explicitly supports a
product-target relationship. It exists so product/rate answers do not depend on
the LLM inventing or inferring label details.
"""

from __future__ import annotations

import os
import re
from typing import Any

from constants import FUNGICIDES, HERBICIDES, INSECTICIDES, PGRS, SEARCH_FOLDERS
from knowledge_base import load_products, load_weeds
from search_service import find_source_url
from source_policy import sanitize_source_url


TARGET_ALIASES = {
    "dollar_spot": {"dollar spot"},
    "brown_patch": {"brown patch"},
    "pythium_blight": {"pythium", "pythium blight", "cottony blight"},
    "pythium_root_rot": {"pythium root rot"},
    "anthracnose": {"anthracnose"},
    "summer_patch": {"summer patch"},
    "take_all_patch": {"take-all patch", "take all patch"},
    "gray_leaf_spot": {"gray leaf spot", "grey leaf spot"},
    "spring_dead_spot": {"spring dead spot"},
    "fairy_ring": {"fairy ring"},
    "microdochium_patch": {"microdochium", "pink snow mold"},
    "yellow_patch": {"yellow patch"},
    "crabgrass": {"crabgrass"},
    "goosegrass": {"goosegrass"},
    "poa_annua": {"poa annua", "annual bluegrass"},
    "poa_trivialis": {"poa trivialis", "roughstalk bluegrass"},
    "yellow_nutsedge": {"yellow nutsedge", "nutsedge"},
    "green_kyllinga": {"green kyllinga", "kyllinga"},
    "clover": {"clover"},
    "broadleaf_weeds": {"broadleaf weeds", "broadleaf weed", "broadleaves"},
    "nimblewill": {"nimblewill"},
    "bentgrass": {"bentgrass"},
    "dandelion": {"dandelion"},
    "plantain": {"plantain"},
    "wild_violets": {"wild violets", "wild violet", "violets", "violet"},
    "ground_ivy": {"ground ivy", "creeping charlie"},
    "wild_strawberry": {"wild strawberry"},
    "foxtail": {"foxtail", "foxtails"},
    "dallisgrass": {"dallisgrass"},
    "non-selective": {"non-selective", "non selective", "nonselective"},
    "all_vegetation": {"all vegetation", "everything", "total vegetation"},
    "white_grubs": {"white grubs", "grubs", "grub"},
    "sod_webworms": {"sod webworms", "webworms", "sod webworm"},
    "annual_bluegrass_weevil": {"annual bluegrass weevil", "abw"},
    "chinch_bugs": {"chinch bugs", "chinch bug"},
    "billbugs": {"billbugs", "billbug"},
    "cutworms": {"cutworms", "cutworm"},
    "caterpillars": {"caterpillars", "caterpillar"},
    "ants": {"ants", "ant"},
    "fire_ants": {"fire ants", "fire ant"},
    "armyworms": {"armyworms", "armyworm"},
    "surface_insects": {"surface insects"},
}

CANONICAL_TARGET_LABELS = {
    "poa_annua": "annual bluegrass",
    "poa_trivialis": "roughstalk bluegrass",
    "annual_bluegrass_weevil": "annual bluegrass weevil",
}

KNOWN_PRODUCT_TERMS = {
    term.lower()
    for term in (FUNGICIDES + HERBICIDES + INSECTICIDES + PGRS)
}


COMPARISON_PAIR_CONFIGS: dict[frozenset[str], dict[str, Any]] = {
    frozenset({"prodiamine", "dithiopyr"}): {
        "primary": "prodiamine",
        "secondary": "dithiopyr",
        "summary": "are verified crabgrass/goosegrass herbicide options, but they are not the same fit.",
        "primary_read": "lean on this when you want longer residual prevention and you are not counting on early post-emergent cleanup.",
        "secondary_read": "use this when you want more timing flexibility or you may be a little late and still want early post-emergent help.",
        "separation": [
            "Pick **{primary}** for maximum residual and a cleaner pure pre-emergent program.",
            "Pick **{secondary}** when you want a wider timing window and the added early post-emergent piece.",
        ],
        "important": "They are both HRAC Group 3 herbicides, so this is not a mode-of-action rotation by itself.",
    },
    frozenset({"mesotrione", "topramezone"}): {
        "primary": "mesotrione",
        "secondary": "topramezone",
        "summary": "are verified HPPD herbicides, but they fill different turf-use roles.",
        "primary_read": "use this when seeding safety and broad turf-establishment flexibility matter more than raw goosegrass strength.",
        "secondary_read": "use this when you need a stronger post-emergent cleanup tool on listed species and you can live inside the tighter turf-tolerance window.",
        "separation": [
            "Pick **{primary}** when establishment timing and seeding flexibility are central to the program.",
            "Pick **{secondary}** when post-emergent goosegrass or bermudagrass suppression is the bigger priority.",
        ],
        "important": "They are both HRAC Group 27 herbicides, so rotating away from that group still matters for resistance management.",
    },
    frozenset({"chlorothalonil", "propiconazole"}): {
        "primary": "chlorothalonil",
        "secondary": "propiconazole",
        "summary": "are verified fungicide options, but one is a multi-site contact anchor and the other is a single-site systemic triazole.",
        "primary_read": "use this when you want a broader contact protectant and stronger resistance-management support.",
        "secondary_read": "use this when you want a systemic FRAC 3 option and the target list lines up cleanly with the disease you are chasing.",
        "separation": [
            "Pick **{primary}** when resistance-management posture and a multi-site protectant are the bigger priorities.",
            "Pick **{secondary}** when the target is squarely in its wheelhouse and a systemic FRAC 3 fits the program.",
        ],
        "important": "This is a true FRAC contrast: **{primary}** is M5 and **{secondary}** is FRAC 3.",
    },
    frozenset({"chlorothalonil", "fluazinam"}): {
        "primary": "chlorothalonil",
        "secondary": "fluazinam",
        "summary": "are verified contact fungicide options, but they fill different slots in a program.",
        "primary_read": "lean on this when you want a classic broad contact anchor and strong resistance-management support from a multi-site protectant.",
        "secondary_read": "lean on this when the target list lines up cleanly and you want the Secure fit for diseases like dollar spot or anthracnose in the stored program notes.",
        "separation": [
            "Pick **{primary}** when broad contact coverage and a multi-site backbone are the bigger priorities.",
            "Pick **{secondary}** when the disease list fits and you want the Secure profile specifically in that rotation slot.",
        ],
        "important": "This is not the same FRAC posture: **{primary}** is M5 and **{secondary}** is FRAC 29.",
    },
    frozenset({"azoxystrobin", "propiconazole"}): {
        "primary": "azoxystrobin",
        "secondary": "propiconazole",
        "summary": "are verified fungicides, but they bring different disease strengths and FRAC profiles.",
        "primary_read": "lean on this when diseases like summer patch, take-all patch, or spring dead spot are part of the conversation.",
        "secondary_read": "lean on this when the focus is tighter around dollar spot, brown patch, or anthracnose and a FRAC 3 triazole fits the rotation.",
        "separation": [
            "Pick **{primary}** when the target list needs the broader root and patch-disease coverage stored in the KB.",
            "Pick **{secondary}** when the disease list is narrower and a triazole slot fits the resistance plan.",
        ],
        "important": "This is also a FRAC contrast: **{primary}** is FRAC 11 and **{secondary}** is FRAC 3.",
    },
    frozenset({"azoxystrobin", "azoxystrobin_propiconazole"}): {
        "primary": "azoxystrobin",
        "secondary": "azoxystrobin_propiconazole",
        "summary": "are verified fungicide options, but one is a straight FRAC 11 strobilurin and the other is a premix that adds FRAC 3 propiconazole.",
        "primary_read": "lean on this when the Heritage disease profile fits and you want a cleaner straight FRAC 11 slot in the rotation.",
        "secondary_read": "lean on this when you want the Headway premix fit and the added triazole piece matters for the disease profile or resistance plan.",
        "separation": [
            "Pick **{primary}** when a straight azoxystrobin slot is enough and you do not need the premix structure.",
            "Pick **{secondary}** when you want the Headway FRAC 11 + 3 blend instead of Heritage alone.",
        ],
        "important": "This is not a one-for-one swap: **{primary}** is FRAC 11 alone, while **{secondary}** carries both FRAC 11 and FRAC 3.",
    },
    frozenset({"azoxystrobin", "fluazinam"}): {
        "primary": "azoxystrobin",
        "secondary": "fluazinam",
        "summary": "are verified fungicides, but one is a systemic FRAC 11 strobilurin and the other is a contact FRAC 29 option.",
        "primary_read": "lean on this when root and patch-disease coverage or a systemic QoI slot are the bigger priorities.",
        "secondary_read": "lean on this when the target list fits Secure and you want that contact-style disease-control fit in the rotation.",
        "separation": [
            "Pick **{primary}** when you need the broader Heritage disease profile and a systemic FRAC 11 option.",
            "Pick **{secondary}** when dollar spot, anthracnose, or brown patch pressure lines up with the Secure profile you want in that spray slot.",
        ],
        "important": "This is a real FRAC and movement difference: **{primary}** is FRAC 11 and **{secondary}** is FRAC 29.",
    },
    frozenset({"fludioxonil", "fluazinam"}): {
        "primary": "fludioxonil",
        "secondary": "fluazinam",
        "summary": "are verified contact fungicides, but they are not the same fit in a disease program.",
        "primary_read": "lean on this when the disease list fits the Medallion-style fludioxonil slot and you want that FRAC 12 contact profile in the rotation.",
        "secondary_read": "lean on this when the Secure disease profile fits better and you want that FRAC 29 contact option in the program.",
        "separation": [
            "Pick **{primary}** when the target and program slot call for the Medallion fludioxonil profile.",
            "Pick **{secondary}** when the stored Secure targets and FRAC 29 posture are the cleaner fit.",
        ],
        "important": "They are both contact-style fungicides, but they are not the same FRAC group: **{primary}** is FRAC 12 and **{secondary}** is FRAC 29.",
    },
    frozenset({"propiconazole", "azoxystrobin_propiconazole"}): {
        "primary": "propiconazole",
        "secondary": "azoxystrobin_propiconazole",
        "summary": "are verified fungicide options, but one is a straight FRAC 3 triazole and the other is a premix that adds FRAC 11 azoxystrobin.",
        "primary_read": "lean on this when you want a simple Banner MAXX triazole slot and the target list fits that program cleanly.",
        "secondary_read": "lean on this when you want the Headway premix fit and the added azoxystrobin piece matters for the disease profile or resistance plan.",
        "separation": [
            "Pick **{primary}** when a straight FRAC 3 triazole is enough and you do not need the premix structure.",
            "Pick **{secondary}** when you want the FRAC 11 + 3 Headway blend as the program tool instead of Banner alone.",
        ],
        "important": "This is not a one-for-one swap: **{primary}** is FRAC 3 alone, while **{secondary}** carries both FRAC 11 and FRAC 3.",
    },
    frozenset({"chlorantraniliprole", "cyantraniliprole"}): {
        "primary": "chlorantraniliprole",
        "secondary": "cyantraniliprole",
        "summary": "are verified IRAC 28 anthranilic diamides, but they are not the same operational fit.",
        "primary_read": "lean on this when you want a preventive soil-directed grub or caterpillar program.",
        "secondary_read": "lean on this when you want a product with both contact and systemic language plus stronger annual bluegrass weevil discussion in the stored notes.",
        "separation": [
            "Pick **{primary}** when preventive timing is the core plan.",
            "Pick **{secondary}** when you want the broader contact/systemic posture and more ABW-centered operational flexibility.",
        ],
        "important": "They share IRAC Group 28, so they should not be treated as an IRAC rotation away from one another.",
    },
    frozenset({"trinexapac_ethyl", "ethephon"}): {
        "primary": "trinexapac_ethyl",
        "secondary": "ethephon",
        "summary": "are PGR tools, but they are doing different jobs on the property.",
        "primary_read": "use this as the core clipping-growth regulator and surface-management PGR.",
        "secondary_read": "use this when seedhead suppression is the main goal, especially around Poa annua.",
        "separation": [
            "Pick **{primary}** when your main goal is steady growth regulation and surface management.",
            "Pick **{secondary}** when seedhead suppression is the real reason you are reaching for a PGR.",
        ],
        "important": "These are not interchangeable growth regulators: one is a Type A late-pathway GA inhibitor and the other is an ethylene generator.",
    },
}


def answer_from_verified_kb(question: str, course_profile_context: str = "") -> dict[str, Any] | None:
    """Return a deterministic answer for explicit product-target questions."""
    q = (question or "").lower()
    comparison_response = _answer_product_comparison_question(q)
    if comparison_response:
        return comparison_response
    if re.search(r"\b(separate|walk me through|how would you separate|how do you separate)\b", q):
        return None
    if not _looks_like_product_decision(q):
        return None

    detected_products = _detect_products(q)
    if _looks_like_tank_mix_question(q) and len(detected_products) >= 2:
        tank_mix_response = _answer_tank_mix_question(detected_products[:2], q)
        if tank_mix_response:
            return tank_mix_response

    product = _detect_product(q)
    target_key, target_display = _detect_target(q)
    if _target_looks_like_surface_context(q, target_key):
        target_key, target_display = None, None
    catalog_terms = _detect_catalog_product_terms(q)
    if not product:
        unstructured_product_response = _answer_unstructured_product_question(q, catalog_terms)
        if unstructured_product_response:
            return unstructured_product_response
        return None

    if _looks_like_rei_question(q):
        rei_response = _answer_rei_question(product)
        if rei_response:
            return rei_response

    if _looks_like_interval_question(q):
        interval_response = _answer_interval_question(product)
        if interval_response:
            return interval_response

    if _looks_like_rainfast_question(q):
        rainfast_response = _answer_rainfast_question(product)
        if rainfast_response:
            return rainfast_response

    if _looks_like_irrigation_question(q):
        irrigation_response = _answer_irrigation_question(product)
        if irrigation_response:
            return irrigation_response

    if _looks_like_max_use_question(q):
        max_use_response = _answer_max_use_question(product, q)
        if max_use_response:
            return max_use_response

    if _looks_like_reseeding_question(q):
        reseeding_response = _answer_reseeding_question(product, q)
        if reseeding_response:
            return reseeding_response
        wants_overseed = "overseed" in q or "overseeding" in q
        primary_field = "overseeding_interval" if wants_overseed else "reseeding_interval"
        alternate_field = "reseeding_interval" if wants_overseed else "overseeding_interval"
        stored_note = (
            product["info"].get(primary_field)
            or product["info"].get(alternate_field)
            or ""
        )
        source = _source_for_product(product)
        provenance = _provenance_for_product(product, source)
        return {
            "answer": _build_missing_field_answer(
                product,
                "reseeding or overseeding guidance",
                provenance,
                stored_note=stored_note,
            ),
            "sources": [source],
            "confidence": {"score": 35, "label": "Not Verified Yet"},
            "needs_review": True,
            "grounding": {
                "verified": False,
                "issues": [f"No verified reseeding or overseeding guidance stored for {product['display_name']}."],
            },
            "kb_verdict": "not_verified",
            "product": product["display_name"],
            "surface": _detect_surface(q),
        }

    if _looks_like_application_window_question(q):
        application_window_response = _answer_application_window_question(product)
        if application_window_response:
            return application_window_response

    if _looks_like_supported_targets_question(q, product, target_key):
        supported_targets_response = _answer_supported_targets_question(product)
        if supported_targets_response:
            return supported_targets_response

    if _looks_like_label_question(q):
        label_response = _answer_label_question(product)
        if label_response:
            return label_response

    if _looks_like_rate_question(q) and not target_key and product["category"] != "pgrs":
        rate_response = _answer_general_product_rate(product)
        if rate_response:
            return rate_response

    if product["category"] == "pgrs" and (
        _looks_like_rate_question(q)
        or _looks_like_application_window_question(q)
        or "apply" in q
        or "use" in q
        or "spray" in q
    ):
        pgr_response = _answer_pgr_surface_rate(product, q, course_profile_context)
        if pgr_response:
            return pgr_response
        if not target_key:
            return None

    if not target_key:
        return None

    supported_targets = _supported_targets(product)
    is_supported = target_key in supported_targets
    source = _source_for_product(product)
    provenance = _provenance_for_product(product, source)
    surface_issue = _surface_restriction_issue(product, q)

    if surface_issue:
        answer = _build_surface_restricted_answer(product, target_display, surface_issue, provenance)
        return {
            "answer": answer,
            "sources": [source],
            "confidence": {"score": 30, "label": "Surface Restriction"},
            "needs_review": False,
            "grounding": {
                "verified": False,
                "issues": [surface_issue],
            },
            "kb_verdict": "surface_restricted",
            "product": product["display_name"],
            "target": target_key,
            "surface": _detect_surface(q),
        }

    if not is_supported:
        answer = _build_unsupported_answer(product, target_display, supported_targets, provenance)
        return {
            "answer": answer,
            "sources": [source],
            "confidence": {"score": 35, "label": "Not Verified Yet"},
            "needs_review": False,
            "grounding": {
                "verified": False,
                "issues": [
                    f"{product['display_name']} is not listed in the structured KB for {target_display}."
                ],
            },
            "kb_verdict": "not_verified",
            "product": product["display_name"],
            "target": target_key,
            "surface": _detect_surface(q),
        }

    answer = _build_supported_answer(product, target_display, provenance, course_profile_context, q)
    return {
        "answer": answer,
        "sources": [source],
        "confidence": {"score": 95, "label": "Verified KB Match"},
        "needs_review": False,
        "grounding": {"verified": True, "issues": []},
        "kb_verdict": "verified",
        "product": product["display_name"],
        "target": target_key,
        "surface": _detect_surface(q),
    }


def recommend_verified_products_for_surface_target(
    question: str,
    course_profile: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Recommend verified products when the user provides target + surface but no product."""
    q = (question or "").lower()
    if _detect_product(q):
        return None

    target_key, target_display = _detect_target(q)
    if not target_key:
        return None

    surface, turf = _resolve_surface_and_turf(q, course_profile or {})
    if not surface:
        return None
    if _surface_turf_mismatch_note(q, surface, turf):
        return None

    if re.search(r"\b(know about|think about|timing|threshold|thresholds|life ?cycle|lifecycle|meaning|interpret)\b", q):
        return None
    if re.search(r"\b(separate|versus| vs |walk me through|how would you separate|how do you separate)\b", q):
        return None

    decision_patterns = [
        r"\brecommend\b",
        r"\buse\b",
        r"\bspray\b",
        r"\bapply\b",
        r"\bcontrol\b",
        r"\bcontrols\b",
        r"\btreat\b",
        r"\boptions\b",
        r"\bproduct\b",
        r"\bfungicide\b",
        r"\bherbicide\b",
        r"\binsecticide\b",
    ]
    if not any(re.search(pattern, q) for pattern in decision_patterns):
        return None

    candidates = []
    blocked = []
    for product in _all_product_records():
        if product["category"] not in {"fungicides", "herbicides", "insecticides"}:
            continue
        if target_key not in _supported_targets(product):
            continue

        surface_question = f"{q} on {turf} {surface}"
        issue = _surface_restriction_issue(product, surface_question)
        if issue:
            blocked.append((product, issue))
            continue

        candidates.append(product)

    if not candidates:
        unsupported_response = _answer_known_unsupported_surface_target(
            target_key=target_key,
            target_display=target_display or target_key.replace("_", " "),
            surface=surface,
            turf=turf,
        )
        if unsupported_response:
            return unsupported_response
        return {
            "answer": (
                f"**Bottom Line:** I don't have a verified product recommendation for "
                f"**{target_display}** on **{surface} ({turf or 'surface turf not saved'})**.\n\n"
                "I would not invent products or rates for that use pattern. Confirm the target, surface turf, "
                "and label support before making an application."
            ),
            "sources": [],
            "confidence": {"score": 35, "label": "No Verified Surface-Target Match"},
            "needs_review": False,
            "grounding": {
                "verified": False,
                "issues": [f"No verified product candidates for {target_display} on {surface}."],
            },
            "kb_verdict": "no_verified_recommendation",
            "target": target_key,
            "surface": surface,
            "turf": turf,
        }

    ranked = _rank_recommendation_candidates(candidates, q, target_key=target_key, surface=surface)
    top = ranked[:4]
    sources = [_source_for_product(product) for product in top]
    for index, source in enumerate(sources, start=1):
        source["number"] = index

    answer = _build_surface_target_recommendation_answer(
        target_display=target_display or target_key.replace("_", " "),
        surface=surface,
        turf=turf,
        products=top,
        blocked=blocked,
    )
    return {
        "answer": answer,
        "sources": sources,
        "confidence": {"score": 93, "label": "Verified Surface-Target Options"},
        "needs_review": False,
        "grounding": {"verified": True, "issues": []},
        "kb_verdict": "verified_surface_target_options",
        "target": target_key,
        "surface": surface,
        "turf": turf,
    }


def recommend_verified_products_for_target(
    question: str,
    course_profile: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Recommend verified products when the user gives a target but no specific product or surface."""
    q = (question or "").lower()
    if _detect_product(q):
        return None

    target_key, target_display = _detect_target(q)
    if not target_key:
        return None

    surface, _ = _resolve_surface_and_turf(q, course_profile or {})
    if surface:
        return None

    mentioned_turf_terms = _mentioned_surface_terms(_strip_target_aliases(q, target_key)) - {"cool-season", "warm-season"}
    if mentioned_turf_terms:
        return None

    if re.search(r"\b(know about|think about|timing|threshold|thresholds|life ?cycle|lifecycle|meaning|interpret)\b", q):
        return None
    if re.search(r"\b(separate|versus| vs |walk me through|how would you separate|how do you separate)\b", q):
        return None

    decision_patterns = [
        r"\brecommend\b",
        r"\buse\b",
        r"\bspray\b",
        r"\bapply\b",
        r"\bcontrol\b",
        r"\bcontrols\b",
        r"\btreat\b",
        r"\boptions\b",
        r"\bproduct\b",
        r"\bfungicide\b",
        r"\bfungicides\b",
        r"\bherbicide\b",
        r"\bherbicides\b",
        r"\binsecticide\b",
        r"\binsecticides\b",
    ]
    if not any(re.search(pattern, q) for pattern in decision_patterns):
        return None

    requested_categories = _requested_product_categories(q, target_key)
    candidates = []
    for product in _all_product_records():
        if requested_categories and product["category"] not in requested_categories:
            continue
        if target_key not in _supported_targets(product):
            continue
        candidates.append(product)

    if not candidates:
        return None

    ranked = _rank_recommendation_candidates(candidates, q, target_key=target_key, surface=None)
    top = ranked[:5]
    sources = [_source_for_product(product) for product in top]
    for index, source in enumerate(sources, start=1):
        source["number"] = index

    answer = _build_target_recommendation_answer(
        target_display=target_display or target_key.replace("_", " "),
        products=top,
        requested_categories=requested_categories,
    )
    return {
        "answer": answer,
        "sources": sources,
        "confidence": {"score": 91, "label": "Verified Target Options"},
        "needs_review": False,
        "grounding": {"verified": True, "issues": []},
        "kb_verdict": "verified_target_options",
        "target": target_key,
    }


def _answer_known_unsupported_surface_target(
    target_key: str,
    target_display: str,
    surface: str,
    turf: str,
) -> dict[str, Any] | None:
    weeds = load_weeds()
    weed_info = weeds.get(target_key)
    if not isinstance(weed_info, dict):
        return None

    chemical_control = weed_info.get("chemical_control", {}) or {}
    top_products = chemical_control.get("top_products", []) or []
    notes = str(chemical_control.get("notes", "") or "").strip()
    if top_products:
        return None
    if "no broadly safe verified selective control" not in notes.lower():
        return None

    surface_text = f"{surface} ({turf})" if turf else surface
    answer = (
        f"**Bottom Line:** I do **not** have a broadly safe verified selective product recommendation for "
        f"**{target_display}** on **{surface_text}** right now.\n\n"
        f"**What I do have:** {notes}\n\n"
        "**Safer posture:** Treat this as a contamination / renovation / physical-removal decision unless you have "
        "surface-specific label support that has been reviewed and added to the verified product records.\n\n"
        "**Important:** I would not imply mesotrione, Tenacity, or another product is verified here unless that exact "
        "surface-target use is stored and reviewed in the verified product records."
    )
    return {
        "answer": answer,
        "sources": [],
        "confidence": {"score": 90, "label": "Known Unsupported In KB"},
        "needs_review": False,
        "grounding": {"verified": True, "issues": []},
        "kb_verdict": "known_no_verified_selective_control",
        "target": target_key,
        "surface": surface,
        "turf": turf,
    }


def answer_product_context_needed(
    question: str,
    course_profile: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Return a deterministic clarification when a product question is too vague to answer safely."""
    q = (question or "").lower()
    if not q:
        return None

    product = _detect_product(q)
    target_key, target_display = _detect_target(q)
    surface, turf = _resolve_surface_and_turf(q, course_profile or {})
    surface_turf_mismatch = _surface_turf_mismatch_note(q, surface, turf) if surface else None

    if product:
        if product["category"] == "pgrs" and (_looks_like_rate_question(q) or "use" in q or "apply" in q):
            if surface:
                return None
            return _build_context_needed_response(
                heading=f"I need the **surface** before I can give a precise verified answer for **{product['display_name']}**.",
                missing_items=["surface (greens, fairways, tees, or rough)"],
                product_name=product["display_name"],
            )

        if not target_key and (_looks_like_rate_question(q) or "use" in q or "apply" in q or "spray" in q):
            missing = ["target problem"]
            if not surface and product["category"] != "pgrs":
                missing.append("surface")
            return _build_context_needed_response(
                heading=f"I have **{product['display_name']}** in the verified product records, but I need a little more context before I treat this as a specific verified recommendation.",
                missing_items=missing,
                product_name=product["display_name"],
                extra_note=(
                    f"Saved surface context heard: **{surface} ({turf})**."
                    if surface and turf else None
                ),
            )

    mystery_disease_terms = [
        "mystery disease", "unknown disease", "what should i spray", "what should i use",
        "what should i treat", "what do i spray", "what do i use",
    ]
    generic_problem_terms = ["disease", "fungus", "fungal", "issue", "problem"]
    if any(term in q for term in mystery_disease_terms) and any(term in q for term in generic_problem_terms):
        missing = ["symptoms or target disease", "surface turf"]
        if surface:
            missing = ["symptoms or target disease"]
        return _build_context_needed_response(
            heading="I should not jump from a vague disease description straight to a product recommendation.",
            missing_items=missing,
            extra_note=(
                f"Saved surface context heard: **{surface} ({turf})**."
                if surface and turf else None
            ),
        )

    if surface_turf_mismatch and target_key and _looks_like_product_decision(q):
        return _build_context_needed_response(
            heading="Your question mentions a turf type that does not line up with the saved turf for that surface, so I should pause before giving a verified product list.",
            missing_items=["confirm the surface turf"],
            extra_note=surface_turf_mismatch,
        )

    if (
        not product
        and target_key
        and _looks_like_product_decision(q)
        and _mentioned_surface_terms(_strip_target_aliases(q, target_key))
        and not surface
    ):
        mentioned_turf = sorted(_mentioned_surface_terms(_strip_target_aliases(q, target_key)) - {"cool-season", "warm-season"})
        mentioned_turf_text = ", ".join(mentioned_turf) if mentioned_turf else "that turf"
        return _build_context_needed_response(
            heading="I have the target and turf type, but I still need the **surface** before I can give a verified product recommendation.",
            missing_items=["surface (greens, fairways, tees, or rough)"],
            extra_note=(
                f"I heard **{target_display or target_key.replace('_', ' ')}** on **{mentioned_turf_text}**. "
                "On turf like bentgrass, the verified options can differ a lot between greens and fairways."
            ),
        )

    return None


def _strip_target_aliases(q: str, target_key: str | None) -> str:
    if not target_key:
        return q
    cleaned = q
    for alias in TARGET_ALIASES.get(target_key, set()):
        cleaned = re.sub(rf"\b{re.escape(alias)}\b", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _all_product_records() -> list[dict[str, Any]]:
    records = []
    for category, products in load_products().items():
        for ai_name, info in products.items():
            trade_names = info.get("trade_names") or []
            records.append({
                "active_ingredient": ai_name,
                "category": category,
                "display_name": trade_names[0] if trade_names else ai_name.replace("_", " ").title(),
                "matched_name": trade_names[0] if trade_names else ai_name.replace("_", " "),
                "info": info,
            })
    return records


def _resolve_surface_and_turf(q: str, course_profile: dict[str, Any]) -> tuple[str | None, str]:
    surface = _detect_surface(q)
    surfaces = course_profile.get("surfaces", {}) if isinstance(course_profile, dict) else {}
    if surface:
        return surface, str(surfaces.get(surface, "") or "").strip()

    inferred_surface = _infer_surface_from_saved_turf_mentions(q, surfaces)
    if inferred_surface:
        return inferred_surface, str(surfaces.get(inferred_surface, "") or "").strip()

    saved = [(surface_name, turf) for surface_name, turf in surfaces.items() if turf]
    if len(saved) == 1:
        return saved[0][0], str(saved[0][1]).strip()
    return None, ""


def _infer_surface_from_saved_turf_mentions(q: str, surfaces: dict[str, Any]) -> str | None:
    if not isinstance(surfaces, dict):
        return None

    mentioned_terms = _mentioned_surface_terms(q)
    if not mentioned_terms:
        return None

    matches = []
    for surface_name, turf in surfaces.items():
        turf_text = str(turf or "").strip().lower()
        if not turf_text:
            continue

        saved_terms = _mentioned_surface_terms(turf_text)
        normalized_turf = turf_text.replace("-", " ")
        if "bentgrass" in normalized_turf:
            saved_terms.add("bentgrass")
            saved_terms.add("cool-season")
        if "bermuda" in normalized_turf or "bermudagrass" in normalized_turf:
            saved_terms.add("bermudagrass")
            saved_terms.add("warm-season")
        if "bluegrass" in normalized_turf:
            saved_terms.add("bluegrass")
            saved_terms.add("cool-season")
        if "fescue" in normalized_turf:
            saved_terms.add("fescue")
            saved_terms.add("cool-season")
        if "ryegrass" in normalized_turf:
            saved_terms.add("ryegrass")
            saved_terms.add("cool-season")
        if "zoysia" in normalized_turf or "zoysiagrass" in normalized_turf:
            saved_terms.add("zoysiagrass")
            saved_terms.add("warm-season")
        if "st augustine" in normalized_turf or "st. augustine" in normalized_turf:
            saved_terms.add("st_augustinegrass")
            saved_terms.add("warm-season")
        if "centipede" in normalized_turf:
            saved_terms.add("centipedegrass")
            saved_terms.add("warm-season")

        overlap = mentioned_terms & saved_terms
        if overlap:
            matches.append((surface_name, len(overlap), turf_text))

    if not matches:
        return None

    matches.sort(key=lambda item: (-item[1], item[0]))
    best_surface, best_score, _ = matches[0]
    tied_surfaces = {surface_name for surface_name, score, _ in matches if score == best_score}
    if len(tied_surfaces) > 1:
        return None
    return best_surface


def _rank_recommendation_candidates(
    products: list[dict[str, Any]],
    q: str,
    target_key: str | None = None,
    surface: str | None = None,
) -> list[dict[str, Any]]:
    def score(product: dict[str, Any]) -> tuple[int, str]:
        value = 0
        info = product["info"]
        rates = info.get("rates", {})
        if rates:
            value += 5
        if info.get("label_review_status") in {"label_reviewed", "machine_audited_clean"}:
            value += 3
        if info.get("source_url"):
            value += 2
        mode = _mode_of_action(product)
        if mode:
            value += 1
        product_type = str(info.get("type", "")).lower()
        if "pre" in product_type and not any(term in q for term in ["pre", "prevent", "before"]):
            value -= 2

        resistance_risk = str(info.get("resistance_risk", "")).lower()
        if resistance_risk == "low":
            value += 7
        elif resistance_risk == "medium":
            value += 3
        elif resistance_risk in {"medium-high", "medium high"}:
            value += 1
        elif resistance_risk == "high":
            value -= 5

        frac_code = str(info.get("frac_code", "")).upper()
        frac_group = str(info.get("frac_group", "")).lower()
        if product["category"] == "fungicides":
            if frac_code.startswith("M") or "multi-site" in frac_group or "multi site" in frac_group:
                value += 6
            if target_key == "dollar_spot":
                if frac_code in {"M5", "29"}:
                    value += 5
                if frac_code == "7":
                    value += 3
                if frac_code == "3":
                    value += 1
                if frac_code in {"1", "2"}:
                    value -= 3
                if surface == "greens" and frac_code == "1":
                    value -= 3

        return (-value, product["display_name"])

    return sorted(products, key=score)


def _best_rate_for_target(product: dict[str, Any], target_key: str | None = None) -> str:
    rates = product["info"].get("rates", {})
    if not rates:
        return "No verified rate is stored."
    if target_key and target_key in rates:
        return str(rates[target_key])
    if "standard" in rates:
        return str(rates["standard"])
    return "; ".join(f"{key}: {value}" for key, value in rates.items())


def _build_surface_target_recommendation_answer(
    target_display: str,
    surface: str,
    turf: str,
    products: list[dict[str, Any]],
    blocked: list[tuple[dict[str, Any], str]],
) -> str:
    surface_text = f"{surface} ({turf})" if turf else surface
    lines = [
        f"**Bottom Line:** I found verified options for **{target_display}** on **{surface_text}**.",
        "",
        "**Verified options:**",
    ]

    target_key = target_display.replace(" ", "_")
    for product in products:
        mode = _mode_of_action(product)
        product_type = product["info"].get("type", "")
        detail = f"- **{product['display_name']}**: {_best_rate_for_target(product, target_key)}"
        if product_type:
            detail += f"; use pattern: {product_type}"
        if mode:
            detail += f"; {mode}"
        lines.append(detail)

    lines.extend([
        "",
        "**Surface check:** These options passed the stored surface restriction check for the saved or requested surface.",
        "**Ranking logic:** Options are ordered by stored support, surface fit, rate availability, and resistance-management preference. Lower-resistance and multi-site options are favored when otherwise appropriate.",
        "**Next step:** Pick based on resistance rotation, recent applications, pressure level, and current label/site restrictions.",
    ])
    if blocked:
        blocked_names = ", ".join(product["display_name"] for product, _ in blocked[:3])
        lines.append(f"**Blocked by surface restrictions:** {blocked_names}.")
    return "\n".join(lines)


def _build_target_recommendation_answer(
    target_display: str,
    products: list[dict[str, Any]],
    requested_categories: set[str],
) -> str:
    category_label_map = {
        "fungicides": "fungicides",
        "herbicides": "herbicides",
        "insecticides": "insecticides",
    }
    if len(requested_categories) == 1:
        requested_label = category_label_map.get(next(iter(requested_categories)), "products")
    else:
        requested_label = "products"

    lines = [
        f"**Bottom Line:** I found verified {requested_label} for **{target_display}**.",
        "",
        "**Verified options:**",
    ]

    target_key = target_display.replace(" ", "_")
    for product in products:
        mode = _mode_of_action(product)
        product_type = product["info"].get("type", "")
        detail = f"- **{product['display_name']}**: {_best_rate_for_target(product, target_key)}"
        if product_type:
            detail += f"; use pattern: {product_type}"
        if mode:
            detail += f"; {mode}"
        lines.append(detail)

    lines.extend([
        "",
        "**Important:** These are verified target matches, but I have **not** screened them to a specific surface or turf species in this answer.",
        "**Next step:** Add the surface or turf type if you want me to narrow these to safer, more specific verified options.",
    ])
    return "\n".join(lines)


def _build_context_needed_response(
    heading: str,
    missing_items: list[str],
    product_name: str | None = None,
    extra_note: str | None = None,
) -> dict[str, Any]:
    lines = [f"**Bottom Line:** {heading}", ""]
    lines.append("**Need before I answer:**")
    lines.extend(f"- {item}" for item in missing_items)
    if extra_note:
        lines.extend(["", extra_note])
    lines.extend([
        "",
        "**Why:** The verified product records can answer these questions cleanly when the use pattern is specific. "
        "Without that context, I would rather ask for the missing piece than guess.",
    ])
    return {
        "answer": "\n".join(lines),
        "sources": [],
        "confidence": {"score": 84, "label": "Needs More Context"},
        "needs_review": False,
        "grounding": {"verified": True, "issues": []},
        "kb_verdict": "needs_more_context",
        "product": product_name,
    }


def _looks_like_product_decision(q: str) -> bool:
    decision_patterns = [
        r"\brate\b",
        r"\bapply\b",
        r"\buse\b",
        r"\bspray\b",
        r"\bsafe on\b",
        r"\bsafe for\b",
        r"\bunsafe on\b",
        r"\bfit on\b",
        r"\ballowed on\b",
        r"\bcontrol\b",
        r"\bcontrols\b",
        r"\bkill\b",
        r"\btreat\b",
        r"\bwork on\b",
        r"\beffective\b",
        r"\blabel\b",
        r"\boz\b",
        r"\blb/acre\b",
        r"\bper 1000\b",
        r"\btank mix\b",
        r"\bmix with\b",
        r"\brei\b",
        r"\breentry\b",
        r"\bre-entry\b",
        r"\bstay off\b",
        r"\bback on\b",
        r"\bgo back on\b",
        r"\binterval\b",
        r"\bretreat\b",
        r"\bretreatment\b",
        r"\bspray again\b",
        r"\breapply\b",
        r"\breapplied\b",
        r"\bcome back\b",
        r"\birrigation\b",
        r"\birrigate\b",
        r"\bwater in\b",
        r"\bwatering in\b",
        r"\bwater this in\b",
        r"\brainfast\b",
        r"\bshows up after\b",
        r"\bit rains\b",
        r"\bbefore rain\b",
        r"\bafter rain\b",
        r"\breseed\b",
        r"\breseeding\b",
        r"\bseed after\b",
        r"\bseeding\b",
        r"\boverseed\b",
        r"\boverseeding\b",
        r"\bsprigging\b",
        r"\bmax rate\b",
        r"\bmaximum rate\b",
        r"\blargest single\b",
        r"\bannual limit\b",
        r"\bannual max\b",
        r"\bhow often can i use\b",
        r"\bmax annual\b",
        r"\bhow many applications\b",
        r"\bhow many times per year\b",
        r"\bhow many times can i apply\b",
        r"\bapplications per year\b",
        r"\bper year\b",
        r"\bcalendar year\b",
        r"\bafter mowing\b",
        r"\bbefore mowing\b",
        r"\bmow after\b",
        r"\bmow before\b",
        r"\bmow right after\b",
        r"\bwhen should i apply\b",
        r"\bwhen can i apply\b",
        r"\bused for\b",
        r"\bgood for\b",
        r"\bwhat is .+ for\b",
    ]
    return any(re.search(pattern, q) for pattern in decision_patterns)


def _looks_like_product_comparison_question(q: str) -> bool:
    comparison_patterns = [
        r"\bdifference between\b",
        r"\bdiffer\b",
        r"\bcompare\b",
        r"\bversus\b",
        r"\bvs\b",
        r"\bor\b",
        r"\bbetter\b",
    ]
    return any(re.search(pattern, q) for pattern in comparison_patterns)


def _answer_product_comparison_question(q: str) -> dict[str, Any] | None:
    if not _looks_like_product_comparison_question(q):
        return None
    products = _detect_products(q)
    catalog_terms = _detect_catalog_product_terms(q)
    if len(products) < 2 and len(catalog_terms) >= 2:
        listed = ", ".join(f"**{term.title()}**" for term in catalog_terms[:2])
        structured = ", ".join(f"**{product['display_name']}**" for product in products) or "neither product"
        return {
            "answer": (
                f"**Bottom Line:** I do not have both products structured well enough to give a verified comparison for {listed}.\n\n"
                f"**What I can verify right now:** {structured} is in the structured product set. "
                "The missing product needs a completed label-backed record before I should compare them like a known pair."
            ),
            "sources": [_source_for_product(product) for product in products],
            "confidence": {"score": 35, "label": "Not Verified Yet"},
            "needs_review": True,
            "grounding": {"verified": False, "issues": ["Comparison product pair is not fully structured in the KB."]},
            "kb_verdict": "not_verified",
        }
    if len(products) < 2:
        return None

    normalized = frozenset(product["active_ingredient"] for product in products[:2])
    config = COMPARISON_PAIR_CONFIGS.get(normalized)
    if not config:
        return None

    first, second = products[:2]
    if first["active_ingredient"] != config["primary"]:
        first, second = second, first

    answer = _build_product_comparison_answer(first, second, q, config)
    sources = [_source_for_product(first), _source_for_product(second)]
    return {
        "answer": answer,
        "sources": sources,
        "confidence": {"score": 92, "label": "Verified Product Comparison"},
        "needs_review": False,
        "grounding": {"verified": True, "issues": []},
        "kb_verdict": "verified_comparison",
        "product": f"{first['display_name']} vs {second['display_name']}",
        "comparison": [first["active_ingredient"], second["active_ingredient"]],
    }


def _answer_unstructured_product_question(q: str, catalog_terms: list[str]) -> dict[str, Any] | None:
    if not catalog_terms:
        return None
    if len(catalog_terms) >= 2 and _looks_like_product_comparison_question(q):
        return None
    if not _looks_like_product_decision(q):
        return None

    product_name = catalog_terms[0].title()
    return {
        "answer": (
            f"**Bottom Line:** I do not have **{product_name}** structured well enough yet to give a verified product answer.\n\n"
            f"**What that means right now:** I should not guess on targets, intervals, rates, or label restrictions for **{product_name}** until its label-backed record is completed.\n\n"
            "**Best next step:** Either ask about a product that is already fully verified, or fill the label-backed record for this product before relying on the chatbot for a confident recommendation."
        ),
        "sources": [],
        "confidence": {"score": 35, "label": "Not Verified Yet"},
        "needs_review": True,
        "grounding": {"verified": False, "issues": [f"{product_name} is not structured in the verified KB."]},
        "kb_verdict": "not_verified",
        "product": product_name,
    }


def _build_product_comparison_answer(
    first: dict[str, Any],
    second: dict[str, Any],
    q: str,
    config: dict[str, Any],
) -> str:
    first_info = first["info"]
    second_info = second["info"]
    target_key, target_display = _detect_target(q)
    first_targets = ", ".join(str(t).replace("_", " ") for t in _product_targets_for_comparison(first)[:5]) or "stored targets"
    second_targets = ", ".join(str(t).replace("_", " ") for t in _product_targets_for_comparison(second)[:5]) or "stored targets"
    lines = [
        f"**Bottom Line:** Both **{first['display_name']}** ({first['active_ingredient'].replace('_', ' ')}) and **{second['display_name']}** ({second['active_ingredient'].replace('_', ' ')}) {config['summary']}",
        "",
    ]
    if target_key and target_display:
        lines.extend([
            f"**Target context heard:** {target_display}.",
            f"- **{first['display_name']}** {'does' if target_key in _supported_targets(first) else 'does not'} have that target stored in the verified product records.",
            f"- **{second['display_name']}** {'does' if target_key in _supported_targets(second) else 'does not'} have that target stored in the verified product records.",
            "",
        ])
    lines.extend([
        f"**{first['display_name']} ({first['active_ingredient'].replace('_', ' ').title()})**",
        f"- {(_mode_of_action(first) or 'Mode/group not stored')}",
        f"- Stored use pattern: {first_info.get('type', 'not stored')}",
        f"- Stored standard rate: {_best_rate_for_target(first, target_key)}",
        f"- Stored targets: {first_targets}",
        f"- In the field: {config['primary_read']}",
        "",
        f"**{second['display_name']} ({second['active_ingredient'].replace('_', ' ').title()})**",
        f"- {(_mode_of_action(second) or 'Mode/group not stored')}",
        f"- Stored use pattern: {second_info.get('type', 'not stored')}",
        f"- Stored standard rate: {_best_rate_for_target(second, target_key)}",
        f"- Stored targets: {second_targets}",
        f"- In the field: {config['secondary_read']}",
        "",
        "**How I would separate them:**",
    ])
    lines.extend(f"- {line.format(primary=first['display_name'], secondary=second['display_name'])}" for line in config["separation"])
    lines.extend([
        "",
        f"**Important:** {config['important'].format(primary=first['display_name'], secondary=second['display_name'])}",
    ])
    return "\n".join(lines)


def _product_targets_for_comparison(product: dict[str, Any]) -> list[str]:
    info = product["info"]
    for field in ("diseases", "target_weeds", "target_pests"):
        values = info.get(field)
        if values:
            return [str(value) for value in values]
    return []


def _detect_catalog_product_terms(q: str) -> list[str]:
    hits = []
    for term in sorted(KNOWN_PRODUCT_TERMS, key=len, reverse=True):
        if re.search(rf"\b{re.escape(term)}\b", q):
            hits.append(term)
    unique = []
    for term in hits:
        if term not in unique:
            unique.append(term)
    return unique


def _requested_product_categories(q: str, target_key: str | None) -> set[str]:
    requested = set()
    if re.search(r"\bfungicide(s)?\b", q):
        requested.add("fungicides")
    if re.search(r"\bherbicide(s)?\b", q):
        requested.add("herbicides")
    if re.search(r"\binsecticide(s)?\b", q):
        requested.add("insecticides")
    if requested or not target_key:
        return requested

    inferred = set()
    for product in _all_product_records():
        if target_key in _supported_targets(product):
            inferred.add(product["category"])
    return inferred


def _detect_product(q: str) -> dict[str, Any] | None:
    products = _detect_products(q)
    return products[0] if products else None


def _detect_products(q: str) -> list[dict[str, Any]]:
    found = []
    seen = set()
    for category, products in load_products().items():
        for ai_name, info in products.items():
            trade_names = [str(name) for name in info.get("trade_names", [])]
            shorthand = []
            for trade_name in trade_names:
                first_token = trade_name.split()[0].strip()
                if len(first_token) >= 5:
                    shorthand.append(first_token)
            names = [ai_name.replace("_", " ")] + trade_names + shorthand
            for name in names:
                name_lower = name.lower()
                if name_lower and re.search(rf"\b{re.escape(name_lower)}\b", q):
                    trade_names = info.get("trade_names") or []
                    normalized_key = f"{category}:{ai_name}"
                    if normalized_key in seen:
                        break
                    seen.add(normalized_key)
                    found.append({
                        "active_ingredient": ai_name,
                        "category": category,
                        "display_name": trade_names[0] if trade_names else ai_name.replace("_", " ").title(),
                        "matched_name": name,
                        "info": info,
                    })
                    break
    return found


def _detect_target(q: str) -> tuple[str | None, str | None]:
    # Prefer longer aliases first so "poa trivialis" wins before "poa".
    aliases = []
    for key, names in TARGET_ALIASES.items():
        for name in names:
            aliases.append((key, name))
    aliases.sort(key=lambda item: len(item[1]), reverse=True)

    for key, name in aliases:
        if re.search(rf"\b{re.escape(name)}\b", q):
            return key, _display_target_name(key)
    return None, None


def _display_target_name(target: str) -> str:
    key = str(target).lower().replace(" ", "_").replace("-", "_")
    return CANONICAL_TARGET_LABELS.get(key, key.replace("_", " "))


def _target_looks_like_surface_context(question_lower: str, target_key: str | None) -> bool:
    if target_key != "bentgrass":
        return False
    surface_context_patterns = [
        r"\bon\s+bentgrass\s+greens?\b",
        r"\bin\s+bentgrass\s+greens?\b",
        r"\bfor\s+bentgrass\s+greens?\b",
        r"\bbentgrass\s+greens?\b",
    ]
    return any(re.search(pattern, question_lower) for pattern in surface_context_patterns)


def _supported_targets(product: dict[str, Any]) -> set[str]:
    info = product["info"]
    category = product["category"]
    target_fields = {
        "fungicides": "diseases",
        "herbicides": "target_weeds",
        "insecticides": "target_pests",
    }
    field = target_fields.get(category)
    if not field:
        return set()

    targets = set()
    for target in info.get(field, []):
        target_key = str(target).lower().replace(" ", "_").replace("-", "_")
        targets.add(target_key)
        for canonical, aliases in TARGET_ALIASES.items():
            if target_key == canonical or target_key in {alias.replace(" ", "_") for alias in aliases}:
                targets.add(canonical)
    return targets


def _answer_pgr_surface_rate(
    product: dict[str, Any],
    q: str,
    course_profile_context: str,
) -> dict[str, Any] | None:
    """Answer PGR rate questions when the KB has a surface-specific rate."""
    surface = _detect_surface(q)
    rates = product["info"].get("rates", {})
    if not rates:
        return None

    if not surface:
        return _build_context_needed_response(
            heading=f"I need the **surface** before I can give a precise verified answer for **{product['display_name']}**.",
            missing_items=["surface (greens, fairways, tees, or rough)"],
            product_name=product["display_name"],
        )

    rate_key = surface if surface in rates else "standard" if "standard" in rates else None
    if not rate_key:
        return {
            "answer": (
                f"**Bottom Line:** I have **{product['display_name']}** in the verified product records, "
                f"but it does not include a verified rate for **{surface or 'that surface'}**.\n\n"
                f"**Rates currently stored:** {_format_rates(product)}.\n\n"
                "Add the surface-specific label rate before allowing a confident recommendation."
            ),
            "sources": [_source_for_product(product)],
            "confidence": {"score": 35, "label": "Surface Rate Missing"},
            "needs_review": True,
            "grounding": {
                "verified": False,
                "issues": [f"No structured KB rate for {surface or 'requested surface'}."],
            },
            "kb_verdict": "not_verified",
            "product": product["display_name"],
            "surface": surface,
        }

    source = _source_for_product(product)
    provenance = _provenance_for_product(product, source)
    mode = product["info"].get("type", "")
    note = product["info"].get("note", "")
    profile_line = (
        "\n\nAny saved course context only helped narrow the surface or use pattern. The rate itself comes from the verified product record."
        if course_profile_context else ""
    )
    answer = (
        f"**Bottom Line:** I can verify **{product['display_name']}** "
        f"for **{rate_key}** at **{rates[rate_key]}**.\n\n"
        f"**Product type:** {mode}.\n\n"
        f"**Stored note:** {note or 'No additional note stored.'}\n\n"
        f"**Source:** {provenance}\n\n"
        "Use this as the working verified answer, then follow any site-specific restrictions stored on the current label."
        f"{profile_line}"
    )
    return {
        "answer": answer,
        "sources": [source],
        "confidence": {"score": 95, "label": "Verified KB Match"},
        "needs_review": False,
        "grounding": {"verified": True, "issues": []},
        "kb_verdict": "verified",
        "product": product["display_name"],
        "surface": surface,
    }


def _detect_surface(q: str) -> str | None:
    surface_aliases = {
        "greens": {"green", "greens", "putting green", "putting greens"},
        "fairways": {"fairway", "fairways"},
        "tees": {"tee", "tees", "tee box", "tee boxes"},
        "rough": {"rough", "roughs"},
    }
    for surface, aliases in surface_aliases.items():
        if any(re.search(rf"\b{re.escape(alias)}\b", q) for alias in aliases):
            return surface
    return None


def _surface_restriction_issue(product: dict[str, Any], q: str) -> str | None:
    """Catch target-supported but surface-unsafe recommendations."""
    info = product["info"]
    note = str(info.get("note", "")).lower()
    combined = f"{q} {note}"
    cool_surfaces = {
        "bentgrass", "creeping bentgrass", "tall fescue", "fine fescue",
        "kentucky bluegrass", "bluegrass", "ryegrass", "cool-season", "cool season",
    }
    warm_surfaces = {
        "bermudagrass", "bermuda", "zoysia", "zoysiagrass", "st. augustine",
        "st augustine", "centipede", "centipedegrass", "warm-season", "warm season",
    }

    mentioned_surfaces = _mentioned_surface_terms(q)
    prohibited = _expanded_surface_terms(info.get("prohibited_turf", []))
    allowed = _expanded_surface_terms(info.get("allowed_turf", []))

    blocked = sorted(mentioned_surfaces & prohibited)
    if blocked:
        blocked_text = ", ".join(term.replace("_", " ") for term in blocked)
        return (
            f"{product['display_name']} has a structured KB surface restriction for "
            f"{blocked_text}. The question mentions that turf surface."
        )

    if allowed and mentioned_surfaces and not (mentioned_surfaces & allowed):
        return (
            f"{product['display_name']} is only structured as allowed for "
            f"{', '.join(sorted(allowed))}. The requested turf surface is outside that allowed list."
        )

    asks_cool_surface = any(surface in q for surface in cool_surfaces)
    asks_warm_surface = any(surface in q for surface in warm_surfaces)

    if asks_cool_surface and (
        "warm-season" in note
        or "warm season" in note
        or "not safe on cool-season" in note
        or "not safe on cool season" in note
    ):
        return (
            f"{product['display_name']} has a KB surface restriction: {product['info'].get('note')}. "
            "The question mentions cool-season turf, so this use pattern should not be treated as verified."
        )

    if asks_warm_surface and ("cool-season turf only" in note or "cool season turf only" in note):
        return (
            f"{product['display_name']} has a KB surface restriction: {product['info'].get('note')}. "
            "The question mentions warm-season turf, so this use pattern should not be treated as verified."
        )

    unsafe_surface_match = re.search(r"not safe on ([^.]+)", combined)
    if unsafe_surface_match:
        unsafe_text = unsafe_surface_match.group(1)
        if any(surface in q and surface in unsafe_text for surface in sorted(cool_surfaces | warm_surfaces)):
            return (
                f"{product['display_name']} has a KB surface restriction: {product['info'].get('note')}. "
                "The requested turf surface appears in that restriction."
            )

    return None


def _mentioned_surface_terms(q: str) -> set[str]:
    terms = {
        "cool-season": {"cool-season", "cool season"},
        "warm-season": {"warm-season", "warm season"},
        "bentgrass": {"bentgrass", "creeping bentgrass", "bent"},
        "creeping_bentgrass": {"creeping bentgrass"},
        "colonial_bentgrass": {"colonial bentgrass"},
        "velvet_bentgrass": {"velvet bentgrass"},
        "bermudagrass": {"bermudagrass", "bermuda"},
        "bluegrass": {"kentucky bluegrass", "bluegrass", "kbg"},
        "centipedegrass": {"centipede", "centipedegrass"},
        "fescue": {"tall fescue", "fine fescue", "fescue"},
        "ryegrass": {"perennial ryegrass", "ryegrass"},
        "st_augustinegrass": {"st. augustine", "st augustine", "st augustinegrass"},
        "zoysiagrass": {"zoysia", "zoysiagrass"},
    }
    found = set()
    for canonical, aliases in terms.items():
        if any(re.search(rf"\b{re.escape(alias)}\b", q) for alias in aliases):
            found.add(canonical)
    if found & {"bentgrass", "creeping_bentgrass", "colonial_bentgrass", "velvet_bentgrass", "bluegrass", "fescue", "ryegrass"}:
        found.add("cool-season")
    if found & {"bermudagrass", "centipedegrass", "st_augustinegrass", "zoysiagrass"}:
        found.add("warm-season")
    return found


def _surface_turf_mismatch_note(q: str, surface: str | None, saved_turf: str) -> str | None:
    if not surface or not saved_turf:
        return None

    mentioned_terms = _mentioned_surface_terms(q) - {"cool-season", "warm-season"}
    if not mentioned_terms:
        return None

    saved_terms = _mentioned_surface_terms(str(saved_turf).lower()) - {"cool-season", "warm-season"}
    if not saved_terms:
        return None

    if mentioned_terms & saved_terms:
        return None

    mentioned_text = ", ".join(sorted(mentioned_terms))
    return (
        f"I heard **{mentioned_text}** for **{surface}**, but your saved profile says "
        f"**{surface} = {saved_turf}**. I should confirm which turf is actually in play before treating that as a verified surface-target recommendation."
    )


def _expanded_surface_terms(values: list[str]) -> set[str]:
    expanded = set()
    for value in values or []:
        normalized = str(value).lower().replace(" ", "_").replace("-", "_")
        if normalized in {"cool_season", "cool_season_turf"}:
            expanded.update({
                "cool-season",
                "bentgrass",
                "creeping_bentgrass",
                "colonial_bentgrass",
                "velvet_bentgrass",
                "bluegrass",
                "fescue",
                "ryegrass",
            })
        elif normalized in {"warm_season", "warm_season_turf"}:
            expanded.update({"warm-season", "bermudagrass", "centipedegrass", "st_augustinegrass", "zoysiagrass"})
        elif normalized in {"st_augustine", "st_augustinegrass"}:
            expanded.add("st_augustinegrass")
        elif normalized in {"zoysia", "zoysiagrass"}:
            expanded.add("zoysiagrass")
        elif normalized in {"bermuda", "bermudagrass"}:
            expanded.add("bermudagrass")
        elif normalized in {"centipede", "centipedegrass"}:
            expanded.add("centipedegrass")
        elif normalized in {"tall_fescue", "fine_fescue"}:
            expanded.add("fescue")
        elif normalized in {"kentucky_bluegrass", "bluegrass"}:
            expanded.add("bluegrass")
        elif normalized == "creeping_bentgrass":
            expanded.update({"creeping_bentgrass", "bentgrass"})
        elif normalized == "colonial_bentgrass":
            expanded.add("colonial_bentgrass")
        elif normalized == "velvet_bentgrass":
            expanded.add("velvet_bentgrass")
        elif normalized == "bentgrass":
            expanded.add("bentgrass")
        elif normalized in {"perennial_ryegrass", "ryegrass"}:
            expanded.add("ryegrass")
        else:
            expanded.add(normalized.replace("_", "-"))
    return expanded


def _format_rates(product: dict[str, Any]) -> str:
    rates = product["info"].get("rates", {})
    if not rates:
        return "No verified rate is stored."
    return "; ".join(f"{key}: {value}" for key, value in rates.items())


def _looks_like_rate_question(q: str) -> bool:
    return any(term in q for term in ["rate", "how much", "oz", "ounces", "per 1000", "per acre", "lb/acre"])


def _looks_like_tank_mix_question(q: str) -> bool:
    return "tank mix" in q or "mix with" in q or "compatible" in q or "compatibility" in q


def _looks_like_rei_question(q: str) -> bool:
    return any(
        term in q
        for term in [
            "rei",
            "reentry",
            "re-entry",
            "restricted-entry interval",
            "restricted entry interval",
            "stay off",
            "back on",
            "go back on",
        ]
    )


def _looks_like_interval_question(q: str) -> bool:
    interval_terms = [
        "retreatment interval",
        "re-treatment interval",
        "retreat interval",
        "how soon can i reapply",
        "how soon can it be reapplied",
        "how soon can this be reapplied",
        "be reapplied",
        "how soon can i apply",
        "how soon can i retreat",
        "how long until i can reapply",
        "how long until i can apply",
        "how long until i can retreat",
        "come back with",
        "days between applications",
        "minimum interval",
    ]
    return any(term in q for term in interval_terms) or (
        any(term in q for term in ["how soon can i spray", "how soon can i apply"]) and "again" in q
    )


def _looks_like_irrigation_question(q: str) -> bool:
    irrigation_terms = [
        "water in",
        "watering in",
        "water this in",
        "irrigate",
        "irrigation",
        "water after application",
        "rainfast",
        "through irrigation",
    ]
    return any(term in q for term in irrigation_terms)


def _looks_like_rainfast_question(q: str) -> bool:
    return any(
        term in q
        for term in [
            "rainfast",
            "rain after application",
            "rain after spray",
            "rain after spraying",
            "rain shows up after",
            "it rains",
            "before rain",
            "after rain",
        ]
    )


def _looks_like_max_use_question(q: str) -> bool:
    max_terms = [
        "max rate",
        "maximum rate",
        "largest single",
        "max annual",
        "annual max",
        "maximum annual",
        "annual limit",
        "how often can i use",
        "in a year",
        "how many applications",
        "how many times per year",
        "how many times can i apply",
        "applications per year",
        "per year",
        "calendar year",
        "single application",
        "per application",
        "max application",
    ]
    return any(term in q for term in max_terms)


def _looks_like_reseeding_question(q: str) -> bool:
    return any(term in q for term in ["reseed", "reseeding", "seed after", "seeding", "overseed", "overseeding", "sprigging"])


def _looks_like_application_window_question(q: str) -> bool:
    application_terms = [
        "after mowing",
        "before mowing",
        "after application",
        "before application",
        "when should i apply",
        "when can i apply",
        "when do i apply",
        "when should i spray",
        "when can i spray",
        "timing note",
        "mow after",
        "mow before",
        "mow right after",
        "can i mow after",
        "can i mow before",
        "allow it to dry before mowing",
    ]
    return any(term in q for term in application_terms)


def _looks_like_label_question(q: str) -> bool:
    return "label" in q and not _looks_like_tank_mix_question(q)


def _looks_like_supported_targets_question(q: str, product: dict[str, Any], target_key: str | None) -> bool:
    if target_key:
        return False
    if (
        _looks_like_rate_question(q)
        or _looks_like_interval_question(q)
        or _looks_like_rei_question(q)
        or _looks_like_tank_mix_question(q)
        or _looks_like_rainfast_question(q)
        or _looks_like_irrigation_question(q)
        or _looks_like_max_use_question(q)
        or _looks_like_reseeding_question(q)
        or _looks_like_application_window_question(q)
    ):
        return False

    category = product["category"]
    category_terms = {
        "fungicides": ["disease", "diseases", "fungi", "fungus", "pathogen", "pathogens"],
        "herbicides": ["weed", "weeds"],
        "insecticides": ["pest", "pests", "insect", "insects", "bugs"],
    }
    generic_markers = [
        "what does",
        "what can",
        "what is",
        "what's",
        "controls",
        "control",
        "treat",
        "treats",
        "used for",
        "good for",
        "listed for",
    ]
    explicit_for_pattern = bool(re.search(r"\bwhat(?:'s| is)?\s+.+\s+for\b", q))
    has_category_term = any(term in q for term in category_terms.get(category, []))
    has_generic_marker = any(marker in q for marker in generic_markers)
    return has_category_term or explicit_for_pattern or (
        has_generic_marker and any(term in q for term in ["control", "treat", "used for", "good for", "listed for"])
    )


def _answer_general_product_rate(product: dict[str, Any]) -> dict[str, Any] | None:
    rates = product["info"].get("rates", {})
    if not rates:
        return None
    source = _source_for_product(product)
    provenance = _provenance_for_product(product, source)
    return {
        "answer": (
            f"**Bottom Line:** I can verify stored rate guidance for **{product['display_name']}**.\n\n"
            f"**Rates currently stored:** {_format_rates(product)}.\n\n"
            "**Best next step:** Match the rate to the target, surface, and turf before spraying. "
            "If you give me the target and surface, I can narrow this to the more specific verified answer when that support exists.\n\n"
            f"**Source:** {provenance}"
        ),
        "sources": [source],
        "confidence": {"score": 90, "label": "Verified KB Rate Summary"},
        "needs_review": False,
        "grounding": {"verified": True, "issues": []},
        "kb_verdict": "verified",
        "product": product["display_name"],
    }


def _answer_supported_targets_question(product: dict[str, Any]) -> dict[str, Any] | None:
    supported = sorted(_supported_targets(product))
    if not supported:
        return None

    target_labels = [_display_target_name(target) for target in supported]
    source = _source_for_product(product)
    provenance = _provenance_for_product(product, source)

    heading_map = {
        "fungicides": "diseases",
        "herbicides": "target weeds",
        "insecticides": "target pests",
    }
    heading = heading_map.get(product["category"], "supported targets")
    bullets = "\n".join(f"- {label}" for label in target_labels)

    return {
        "answer": (
            f"**Bottom Line:** Here are the verified {heading} I have for **{product['display_name']}**.\n\n"
            f"**Verified list:**\n{bullets}\n\n"
            "In the field: use that list to narrow the call, then match the final rate, surface, and timing to the exact use pattern before you spray.\n\n"
            f"**Source:** {provenance}"
        ),
        "sources": [source],
        "confidence": {"score": 91, "label": "Verified Supported Targets"},
        "needs_review": False,
        "grounding": {"verified": True, "issues": []},
        "kb_verdict": "verified",
        "product": product["display_name"],
    }


def _answer_rei_question(product: dict[str, Any]) -> dict[str, Any] | None:
    rei = _clean_label_snippet(product["info"].get("rei", ""))
    if not _looks_like_verified_rei(rei):
        return None
    source = _source_for_product(product)
    provenance = _provenance_for_product(product, source)
    return {
        "answer": (
            f"**Bottom Line:** The restricted-entry interval for **{product['display_name']}** is **{rei}**.\n\n"
            "If your site or current label is more restrictive, follow that more restrictive direction.\n\n"
            f"**Source:** {provenance}"
        ),
        "sources": [source],
        "confidence": {"score": 92, "label": "Verified Label Interval"},
        "needs_review": False,
        "grounding": {"verified": True, "issues": []},
        "kb_verdict": "verified",
        "product": product["display_name"],
    }


def _answer_interval_question(product: dict[str, Any]) -> dict[str, Any] | None:
    interval = product["info"].get("retreatment_interval")
    if not interval:
        return None
    source = _source_for_product(product)
    provenance = _provenance_for_product(product, source)
    return {
        "answer": (
            f"**Bottom Line:** Here is the re-treatment guidance I have for **{product['display_name']}**.\n\n"
            f"**Clock to watch:** {interval}\n\n"
            "Match that interval to the exact rate, target, and use pattern before you build the spray schedule around it.\n\n"
            f"**Source:** {provenance}"
        ),
        "sources": [source],
        "confidence": {"score": 91, "label": "Verified Re-Treatment Interval"},
        "needs_review": False,
        "grounding": {"verified": True, "issues": []},
        "kb_verdict": "verified",
        "product": product["display_name"],
    }


def _answer_irrigation_question(product: dict[str, Any]) -> dict[str, Any] | None:
    irrigation = product["info"].get("irrigation_guidance")
    if not irrigation:
        timing = str(product["info"].get("timing", ""))
        if "irrigat" in timing.lower() or "water" in timing.lower():
            irrigation = timing
    if not irrigation:
        return None
    source = _source_for_product(product)
    provenance = _provenance_for_product(product, source)
    return {
        "answer": (
            f"**Bottom Line:** Here is the irrigation guidance for **{product['display_name']}**.\n\n"
            f"**What the label says:** {irrigation}\n\n"
            "Practical read: use that to decide whether this is a true water-in application, a wait-for-rain situation, or a case where irrigation should stay out of it.\n\n"
            f"**Source:** {provenance}"
        ),
        "sources": [source],
        "confidence": {"score": 90, "label": "Verified Irrigation Guidance"},
        "needs_review": False,
        "grounding": {"verified": True, "issues": []},
        "kb_verdict": "verified",
        "product": product["display_name"],
    }


def _answer_rainfast_question(product: dict[str, Any]) -> dict[str, Any] | None:
    rainfast = _clean_label_snippet(product["info"].get("rainfast", ""))
    if not rainfast:
        return None
    source = _source_for_product(product)
    provenance = _provenance_for_product(product, source)
    return {
        "answer": (
            f"**Bottom Line:** Here is the rainfast or post-rain guidance for **{product['display_name']}**.\n\n"
            f"**What the label says:** {rainfast}\n\n"
            "Practical read: use that rainfall guidance in the exact use pattern you are making, especially if foliar and watered-in uses are treated differently.\n\n"
            f"**Source:** {provenance}"
        ),
        "sources": [source],
        "confidence": {"score": 90, "label": "Verified Rainfast Guidance"},
        "needs_review": False,
        "grounding": {"verified": True, "issues": []},
        "kb_verdict": "verified",
        "product": product["display_name"],
    }


def _answer_max_use_question(product: dict[str, Any], q: str) -> dict[str, Any] | None:
    wants_annual = any(term in q for term in ["max annual", "annual max", "maximum annual", "annual limit", "per year", "calendar year", "in a year"])
    wants_single = any(term in q for term in ["single application", "largest single", "per application", "max rate", "maximum rate", "max application"])
    wants_application_count = any(
        term in q for term in ["how many applications", "how many times per year", "how many times can i apply", "applications per year", "how often can i use", "in a year"]
    )

    annual = _clean_label_snippet(product["info"].get("max_apps_per_year", ""))
    single = _clean_label_snippet(product["info"].get("max_rate_per_app", ""))

    if wants_single and not _looks_like_clean_single_application_limit(single):
        single = ""
    if wants_application_count and not _looks_like_clean_application_count_limit(annual):
        annual = ""
    if wants_annual and not wants_application_count and not _looks_like_clean_annual_limit(annual):
        annual = ""

    if wants_application_count and annual:
        summary = f"**Stored annual application limit:** {annual}"
        label = "Verified Annual Application Limit"
    elif wants_annual and annual:
        summary = f"**Stored annual limit:** {annual}"
        label = "Verified Annual Use Limit"
    elif wants_single and single:
        summary = f"**Stored per-application limit:** {single}"
        label = "Verified Max Application Rate"
    elif annual and _looks_like_clean_annual_limit(annual):
        summary = f"**Stored annual limit:** {annual}"
        label = "Verified Annual Use Limit"
    elif single and _looks_like_clean_single_application_limit(single):
        summary = f"**Stored per-application limit:** {single}"
        label = "Verified Max Application Rate"
    else:
        return None

    source = _source_for_product(product)
    provenance = _provenance_for_product(product, source)
    return {
        "answer": (
            f"**Bottom Line:** Here is the maximum-use guidance for **{product['display_name']}**.\n\n"
            f"{summary}\n\n"
            "Practical read: keep the use site, timing, and unit basis lined up before you treat this as the working limit.\n\n"
            f"**Source:** {provenance}"
        ),
        "sources": [source],
        "confidence": {"score": 89, "label": label},
        "needs_review": False,
        "grounding": {"verified": True, "issues": []},
        "kb_verdict": "verified",
        "product": product["display_name"],
    }


def _answer_reseeding_question(product: dict[str, Any], q: str) -> dict[str, Any] | None:
    wants_overseed = "overseed" in q or "overseeding" in q
    field = "overseeding_interval" if wants_overseed else "reseeding_interval"
    guidance = _clean_label_snippet(product["info"].get(field, ""))
    if not _looks_like_clean_reseeding_guidance(guidance):
        alternate = "reseeding_interval" if wants_overseed else "overseeding_interval"
        alternate_guidance = _clean_label_snippet(product["info"].get(alternate, ""))
        guidance = alternate_guidance if _looks_like_clean_reseeding_guidance(alternate_guidance) else ""
    if not guidance:
        return None
    source = _source_for_product(product)
    provenance = _provenance_for_product(product, source)
    label = "Verified Overseeding Interval" if wants_overseed else "Verified Reseeding Interval"
    action = "overseeding" if wants_overseed else "reseeding"
    return {
        "answer": (
            f"**Bottom Line:** Here is the {action} timing guidance for **{product['display_name']}**.\n\n"
            f"**What the label says:** {guidance}\n\n"
            "Practical read: use the exact timing, rate range, and turf/use-site context before you put seed, sprigs, or grow-in plans on the calendar.\n\n"
            f"**Source:** {provenance}"
        ),
        "sources": [source],
        "confidence": {"score": 89, "label": label},
        "needs_review": False,
        "grounding": {"verified": True, "issues": []},
        "kb_verdict": "verified",
        "product": product["display_name"],
    }


def _answer_application_window_question(product: dict[str, Any]) -> dict[str, Any] | None:
    guidance = _clean_label_snippet(product["info"].get("application_window_notes", ""))
    if not _looks_like_clean_application_window_guidance(guidance):
        return None
    source = _source_for_product(product)
    provenance = _provenance_for_product(product, source)
    return {
        "answer": (
            f"**Bottom Line:** Here is the timing or mowing-window guidance for **{product['display_name']}**.\n\n"
            f"**What the label says:** {guidance}\n\n"
            "Practical read: use that guidance before you change mowing, watering, or application timing around the spray window.\n\n"
            f"**Source:** {provenance}"
        ),
        "sources": [source],
        "confidence": {"score": 89, "label": "Verified Application Window Guidance"},
        "needs_review": False,
        "grounding": {"verified": True, "issues": []},
        "kb_verdict": "verified",
        "product": product["display_name"],
    }


def _answer_label_question(product: dict[str, Any]) -> dict[str, Any] | None:
    source = _source_for_product(product)
    provenance = _provenance_for_product(product, source)
    if not source.get("url"):
        return None
    parts = [
        f"**Bottom Line:** I have a label-backed record for **{product['display_name']}**.",
        f"**Label source:** {source['url']}.",
    ]
    if product["info"].get("rei"):
        parts.append(f"**Stored REI:** {product['info']['rei']}.")
    if product["info"].get("retreatment_interval"):
        parts.append(f"**Stored re-treatment interval:** {product['info']['retreatment_interval']}.")
    if product["info"].get("irrigation_guidance"):
        parts.append(f"**Stored irrigation guidance:** {product['info']['irrigation_guidance']}.")
    if product["info"].get("rainfast"):
        parts.append(f"**Stored rainfast guidance:** {product['info']['rainfast']}.")
    if product["info"].get("application_window_notes"):
        parts.append(f"**Stored timing / mowing note:** {product['info']['application_window_notes']}.")
    if product["info"].get("rates"):
        parts.append(f"**Stored rates:** {_format_rates(product)}.")
    parts.append(f"**Source:** {provenance}")
    return {
        "answer": "\n\n".join(parts),
        "sources": [source],
        "confidence": {"score": 90, "label": "Verified Label Reference"},
        "needs_review": False,
        "grounding": {"verified": True, "issues": []},
        "kb_verdict": "verified",
        "product": product["display_name"],
    }


def _clean_label_snippet(text: str) -> str:
    snippet = " ".join(str(text or "").split())
    snippet = snippet.replace("\x07", " ")
    snippet = snippet.replace("\xad", "")
    snippet = snippet.replace("\uf0b7", " ")
    snippet = snippet.replace("•", " ")
    snippet = snippet.replace("®", "")
    snippet = snippet.replace("™", "")
    snippet = re.sub(r"\s+", " ", snippet)
    return snippet.strip()


def _looks_like_clean_single_application_limit(text: str) -> bool:
    lower = _clean_label_snippet(text).lower()
    return bool(lower) and "do not apply more than" in lower and (
        "single application" in lower or "per application" in lower
    )


def _looks_like_clean_annual_limit(text: str) -> bool:
    lower = _clean_label_snippet(text).lower()
    has_limit_phrase = any(
        term in lower
        for term in [
            "do not apply more than",
            "do not exceed",
            "maximum annual application rate",
            "maximum yearly",
            "maximum use rate",
            "total of",
        ]
    )
    has_time_window = any(
        term in lower
        for term in [
            "per year",
            "calendar year",
            "12 month",
            "12-month",
            "per season",
        ]
    )
    return bool(lower) and ((has_limit_phrase and has_time_window) or ("applications per year" in lower))


def _looks_like_clean_application_count_limit(text: str) -> bool:
    lower = _clean_label_snippet(text).lower()
    if not lower:
        return False
    mentions_count = any(term in lower for term in ["applications", "application can be made", "times per year", "make more than"])
    return mentions_count and ("per year" in lower or "calendar year" in lower)


def _looks_like_verified_rei(text: str) -> bool:
    lower = _clean_label_snippet(text).lower()
    if not lower:
        return False
    if lower.startswith("no explicit") or lower.startswith("no verified"):
        return False
    return any(
        term in lower
        for term in [
            "hour",
            "hours",
            "day",
            "days",
            "sprays have dried",
            "surface is dry",
        ]
    )


def _looks_like_clean_reseeding_guidance(text: str) -> bool:
    lower = _clean_label_snippet(text).lower()
    if not lower:
        return False
    mentions_seed = any(term in lower for term in ["reseed", "reseeding", "seed", "seeding", "overseed", "overseeding", "sprigging", "sprigged", "sodded", "sodding"])
    mentions_timing = any(term in lower for term in ["after", "within", "month", "months", "week", "weeks", "day", "days", "prior", "no sooner"])
    return mentions_seed and mentions_timing


def _looks_like_clean_application_window_guidance(text: str) -> bool:
    lower = _clean_label_snippet(text).lower()
    if not lower:
        return False
    timing_terms = [
        "after mowing",
        "before mowing",
        "before or after application",
        "within 3 days",
        "within 5 days",
        "24 hours after application",
        "mowed 2 or 3 times before treating",
        "delay watering",
        "delay mowing",
        "allow",
        "completely dry before mowing",
        "timing",
        "apply after",
        "apply before",
        "after treatment until",
        "until after",
        "after sufficient irrigation",
        "after sufficient rainfall",
        "until spray deposited",
        "until spray",
        "thoroughly dry",
        "12-24 hours",
    ]
    action_terms = ["mow", "mowing", "water", "watering", "apply", "application", "spray", "treatment"]
    return any(term in lower for term in timing_terms) and any(term in lower for term in action_terms)


def _answer_tank_mix_question(products: list[dict[str, Any]], q: str) -> dict[str, Any] | None:
    first, second = products[0], products[1]
    first_guidance = first["info"].get("tank_mix_guidance") or []
    second_guidance = second["info"].get("tank_mix_guidance") or []
    if not first_guidance and not second_guidance:
        return None

    matched_notes = []
    target_key, target_display = _detect_target(q)
    if target_key == "dollar_spot":
        for note in first_guidance + second_guidance:
            if "dollar spot" in note.lower():
                matched_notes.append(note)
    if not matched_notes:
        matched_notes = (first_guidance[:2] + second_guidance[:2])[:4]

    sources = [_source_for_product(first), _source_for_product(second)]
    for index, source in enumerate(sources, start=1):
        source["number"] = index

    lines = [
        f"**Bottom Line:** I have structured label-backed tank-mix guidance for **{first['display_name']}** and **{second['display_name']}**.",
    ]
    if target_display:
        lines.append(f"**Target context heard:** {target_display}.")
    lines.append("")
    lines.append("**Stored guidance:**")
    lines.extend(f"- {note}" for note in matched_notes[:4])
    lines.extend([
        "",
        "**Practical read:** Follow the most restrictive label, rate, and precaution in the combination. "
        "When the label calls for compatibility checks, treat the jar test and local experience as part of the decision, not as optional extras.",
    ])
    return {
        "answer": "\n".join(lines),
        "sources": sources,
        "confidence": {"score": 89, "label": "Verified Tank-Mix Guidance"},
        "needs_review": False,
        "grounding": {"verified": True, "issues": []},
        "kb_verdict": "verified",
        "product": f"{first['display_name']} + {second['display_name']}",
        "target": target_key,
    }


def _mode_of_action(product: dict[str, Any]) -> str:
    info = product["info"]
    if product["category"] == "fungicides":
        frac = info.get("frac_code")
        group = info.get("frac_group")
        return f"FRAC {frac}" + (f" ({group})" if group else "") if frac else ""
    if product["category"] == "herbicides":
        hrac = info.get("hrac_group")
        return f"HRAC Group {hrac}" if hrac else ""
    if product["category"] == "insecticides":
        irac = info.get("irac_group")
        return f"IRAC Group {irac}" if irac else ""
    return ""


def _source_for_product(product: dict[str, Any]) -> dict[str, Any]:
    info = product["info"]
    source_url = sanitize_source_url(info.get("source_url"))
    if info.get("source_url"):
        return {
            "number": 1,
            "name": f"{product['display_name']} Label",
            "url": source_url,
            "type": info.get("source_type", "verified_label_on_file"),
            "note": f"Structured KB product-target-rate authority; status: {info.get('verification_status', 'unknown')}",
        }

    names = [product["display_name"], product["matched_name"], product["active_ingredient"].replace("_", " ")]
    url = None
    source_name = f"{product['display_name']} Structured KB"
    for name in names:
        url = find_source_url(f"{name} label", SEARCH_FOLDERS) or _find_label_by_name(name)
        if url:
            source_name = f"{product['display_name']} Label"
            break

    return {
        "number": 1,
        "name": source_name,
        "url": url,
        "type": "verified_label" if url else "structured_reference",
        "note": "Structured KB product-target-rate authority",
    }


def _find_label_by_name(name: str) -> str | None:
    return None


def _provenance_for_product(product: dict[str, Any], source: dict[str, Any]) -> str:
    source_text = source["name"]
    if source.get("url"):
        source_text += f" ({source['url']})"
    return f"Local structured KB entry for {product['display_name']}; source: {source_text}."


def _build_supported_answer(
    product: dict[str, Any],
    target_display: str,
    provenance: str,
    course_profile_context: str,
    question_text: str,
) -> str:
    mode = _mode_of_action(product)
    note = product["info"].get("note", "")
    product_type = str(product["info"].get("type", "")).lower()
    surface_line = ""
    if course_profile_context:
        surface_line = "\n\nAny saved course context only helped narrow the fit. The verified match itself comes from the product-target KB entry."

    is_preem_only = (
        product["category"] == "herbicides"
        and "pre-emergent" in product_type
        and "post-emergent" not in product_type
    )

    if is_preem_only and not any(
        term in question_text for term in ["pre-em", "pre em", "preem", "prevent", "before germination"]
    ):
        bottom_line = (
            f"**Bottom Line:** I can verify **{product['display_name']}** "
            f"for **pre-emergent management of {target_display}**, not as a generic post-emergent cleanup answer."
        )
    else:
        bottom_line = (
            f"**Bottom Line:** Yes. I can verify **{product['display_name']}** "
            f"for **{target_display}**."
        )

    parts = [bottom_line, f"**Verified rate:** {_format_rates(product)}."]
    if product_type:
        parts.append(f"**Use pattern:** {product['info'].get('type')}.")
    if mode:
        parts.append(f"**Mode of action:** {mode}.")
    if note:
        parts.append(f"**Stored note:** {note}.")
    parts.append(f"**Source:** {provenance}")
    parts.append(
        "This is the verified match. Before spraying, make sure the exact surface, use site, and any site-specific label restrictions still line up."
    )
    return "\n\n".join(parts) + surface_line


def _build_unsupported_answer(
    product: dict[str, Any],
    target_display: str,
    supported_targets: set[str],
    provenance: str,
) -> str:
    listed = ", ".join(sorted(_display_target_name(target) for target in supported_targets)) or "no targets stored"
    return (
        f"**Bottom Line:** No. I do **not** have verified support for **{product['display_name']}** on **{target_display}**.\n\n"
        f"**What I can verify for {product['display_name']}:** {listed}.\n\n"
        f"**Source:** {provenance}\n\n"
        "If that target is truly on the label, the product record needs to be updated before I should answer as if it is supported."
    )


def _build_missing_field_answer(
    product: dict[str, Any],
    field_label: str,
    provenance: str,
    stored_note: str | None = None,
) -> str:
    detail = ""
    cleaned_note = _clean_label_snippet(stored_note or "")
    if cleaned_note:
        detail = f"**What the stored label record says:** {cleaned_note}\n\n"
    return (
        f"**Bottom Line:** I do not have verified {field_label.lower()} stored for **{product['display_name']}**.\n\n"
        f"{detail}"
        f"**Source:** {provenance}\n\n"
        "I would not fill that gap with a guessed timing or restriction. If the label clearly supports it, the product record needs to be updated first."
    )


def _build_surface_restricted_answer(
    product: dict[str, Any],
    target_display: str,
    surface_issue: str,
    provenance: str,
) -> str:
    return (
        f"**Bottom Line:** I can't verify **{product['display_name']}** for **{target_display}** on that turf surface.\n\n"
        f"**Surface restriction:** {surface_issue}\n\n"
        f"**Source:** {provenance}\n\n"
        "Do not treat the target match alone as enough. A product can be labeled for a weed or pest but still be unsafe "
        "on a specific turf species or surface."
    )
