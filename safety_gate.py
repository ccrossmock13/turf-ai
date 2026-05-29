"""Strict safety gate for high-risk turf questions."""

from __future__ import annotations

from typing import Any

from verified_kb import _detect_product, _detect_surface, _detect_target, _looks_like_product_decision


HIGH_RISK_PRODUCT_TERMS = (
    "tank mix", "mix with", "compatible", "compatibility", "combine",
    "reentry", "rei", "pre harvest", "pre-harvest", "phi", "interval",
    "retreatment", "retreat", "legal", "label says",
)

RATE_CONTEXT_TERMS = (
    "rate", "how much", "oz", "ounces", "fl oz", "per 1000", "per acre", "lb/acre",
)

DIAGNOSIS_CONFIRM_TERMS = (
    "definitely", "for sure", "certain", "confirm", "confirmed", "right?",
    "100%",
)


def get_pre_llm_safety_response(question: str, course_profile: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Block high-risk questions before the LLM fallback can improvise."""
    q = (question or "").lower().strip()
    if not q:
        return None

    if _looks_like_science_explainer(q):
        return None

    if any(term in q for term in HIGH_RISK_PRODUCT_TERMS) and not _looks_like_physical_compatibility_question(q):
        return _build_product_safety_block(
            "I do not have verified tank-mix, interval, REI/PHI, or compatibility authority in the deterministic KB yet, so I should not answer that from a model guess.",
            next_step="Check the current label, compatibility guidance, and site-specific restrictions before acting.",
        )

    product = _detect_product(q)
    target_key, target_display = _detect_target(q)
    surface = _detect_surface(q)

    if product and any(term in q for term in RATE_CONTEXT_TERMS) and not target_key and product.get("category") != "pgrs":
        return _build_product_safety_block(
            f"I have a product match for **{product['display_name']}**, but I do not have enough context to safely give a rate.",
            next_step=(
                "Tell me the target, surface, and turf so I can use verified structured KB support instead of guessing a label rate."
            ),
            product=product["display_name"],
            surface=surface,
        )

    if _looks_like_diagnosis_confirmation(q) and not any(term in q for term in HIGH_RISK_PRODUCT_TERMS):
        return _build_diagnosis_confirmation_block(course_profile or {})

    return None


def apply_post_llm_safety_gate(question: str, response_data: dict[str, Any]) -> dict[str, Any]:
    """Replace risky fallback answers when confidence/support is too weak."""
    q = (question or "").lower().strip()
    if not q:
        return response_data

    explicit_high_risk_term = any(term in q for term in HIGH_RISK_PRODUCT_TERMS) and not _looks_like_physical_compatibility_question(q)
    high_risk_product = (_detect_product(q) and _looks_like_product_decision(q)) or explicit_high_risk_term
    confirmatory_diagnosis = _looks_like_diagnosis_confirmation(q)
    confidence = float(response_data.get("confidence", {}).get("score", 0) or 0)
    grounding = response_data.get("grounding", {}) or {}
    unsupported = grounding.get("issues", []) or []

    if high_risk_product and (confidence < 85 or unsupported or response_data.get("needs_review")):
        return _build_product_safety_block(
            "I do not have enough verified support to answer that safely.",
            next_step="Use the verified KB path or the current label rather than relying on an LLM fallback for this kind of decision.",
        )

    if confirmatory_diagnosis and (confidence < 88 or unsupported or response_data.get("needs_review")):
        return _build_diagnosis_confirmation_block({})

    return response_data


def _looks_like_diagnosis_confirmation(q: str) -> bool:
    disease_or_problem_terms = (
        "pythium", "dollar spot", "brown patch", "anthracnose", "wet wilt",
        "disease", "pathogen", "root rot", "nematode", "what is causing",
    )
    return any(term in q for term in DIAGNOSIS_CONFIRM_TERMS) and any(term in q for term in disease_or_problem_terms)


def _looks_like_physical_compatibility_question(q: str) -> bool:
    return "sand compatibility" in q or ("topdressing" in q and "compatibility" in q) or ("layering" in q and "compatibility" in q)


def _looks_like_science_explainer(q: str) -> bool:
    science_openers = ("how does", "how do", "why does", "why do", "why can", "when does")
    if _detect_product(q) and not any(q.startswith(prefix) for prefix in science_openers):
        return False
    science_terms = (
        "growing degree days", "gdd", "fixed intervals", "calendar interval",
        "warm nights", "hot days alone", "low nitrogen", "leaf wetness",
        "when does gypsum", "why does poa annua", "mower injury",
        "reclaimed water", "clipping yield", "primo timing",
        "how does", "why does", "why do", "why can", "when does",
    )
    return any(term in q for term in science_terms)


def _build_product_safety_block(bottom_line: str, next_step: str, product: str | None = None, surface: str | None = None) -> dict[str, Any]:
    lines = [f"**Bottom Line:** {bottom_line}"]
    if product:
        lines.append(f"**Product context:** {product}.")
    if surface:
        lines.append(f"**Surface context I heard:** {surface}.")
    lines.extend([
        "**Safety posture:** For products, rates, tank mixes, and legal-use questions, I only want to answer from verified structured KB support or the current label.",
        f"**Next step:** {next_step}",
    ])
    return {
        "answer": "\n\n".join(lines),
        "sources": [{
            "name": "Answer Safety Gate",
            "type": "safety_policy",
        }],
        "confidence": {"score": 20, "label": "Need Verified Support"},
        "needs_review": False,
        "grounding": {
            "verified": False,
            "issues": ["Blocked by strict answer safety gate."],
        },
        "kb_verdict": "safety_blocked",
    }


def _build_diagnosis_confirmation_block(course_profile: dict[str, Any]) -> dict[str, Any]:
    profile_surfaces = (course_profile or {}).get("surfaces", {}) if isinstance(course_profile, dict) else {}
    known_surface = next((name for name, turf in profile_surfaces.items() if turf), None)
    lines = [
        "**Bottom Line:** I should not confirm a disease or root problem from a short text description alone.",
        "**Safety posture:** Diagnosis answers should stay at the level of working hypotheses until they are supported by pattern, roots, signs, weather, and field checks.",
        "**What I would need:** surface, turf species, recent weather, moisture by depth, root condition, pattern, and any visible lesions or signs.",
        "**Next step:** Treat this as a field-confirmation question, not a certainty question.",
    ]
    if known_surface:
        lines.append(f"**Saved course context:** I can use your stored {known_surface} context once you add the symptom details.")
    return {
        "answer": "\n\n".join(lines),
        "sources": [{
            "name": "Answer Safety Gate",
            "type": "safety_policy",
        }],
        "confidence": {"score": 25, "label": "Needs Field Confirmation"},
        "needs_review": False,
        "grounding": {
            "verified": False,
            "issues": ["Blocked by diagnosis confirmation safety gate."],
        },
        "kb_verdict": "safety_blocked",
    }
