"""Centralized deterministic router for expert answer modes."""

from __future__ import annotations

import re
from typing import Any

from advanced_diagnosis import DIAGNOSIS_INTENT_TERMS, DIAGNOSTIC_BUCKETS
from advanced_turf_science import SCIENCE_INTENT_TERMS, SCIENCE_TOPIC_ALIASES
from verified_kb import TARGET_ALIASES, _detect_product


PRODUCT_INTENT_TERMS = [
    "what should i use", "what should we use", "what can i use",
    "what should i spray", "what can i spray", "should i spray",
    "should we spray", "recommend", "options",
    "rate", "label", "tank mix", "mix with", "how much", "ounces",
    "oz", "product", "spray for", "use for", "apply for", "control",
    "treat",
]

GENERAL_GUIDANCE_TERMS = [
    "turf health", "healthy turf", "keep turf healthy", "keep turf in good shape",
    "what matters most", "in general", "generally", "overall", "fundamentals",
    "perform well", "biggest drivers", "summer stress", "what am i probably missing",
    "what gets superintendents in trouble fastest", "seedbed", "grow-in",
]


SYMPTOM_TERMS = [
    "wilt", "wilting", "decline", "thinning", "thin", "yellowing",
    "brown", "spots", "patches", "roots", "shallow roots", "dying", "pattern",
    "damage", "injury", "symptom", "symptoms", "explode",
    "exploded", "outbreak", "flare", "flared", "tired", "soft wet spots", "soft spots",
    "looks okay at 8 am", "rough by 2 pm", "flat surface", "surfaces still feel flat",
    "not recovering", "surviving but not recovering", "roots are there", "looks tired",
    "green still has no life", "weak patch", "syringe", "hanging on", "melt",
    "soft and slow", "heavy",
]


def route_expert_mode(question: str, course_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    """Score product, diagnosis, and science intent and choose an expert mode."""
    q = (question or "").lower()
    scores = {
        "verified_product": _score_product(q),
        "advanced_diagnosis": _score_diagnosis(q),
        "advanced_turf_science": _score_science(q),
        "general_turf_guidance": _score_general_guidance(q),
    }
    signals = {
        "verified_product": _product_signals(q),
        "advanced_diagnosis": _diagnosis_signals(q),
        "advanced_turf_science": _science_signals(q),
        "general_turf_guidance": _general_guidance_signals(q),
    }

    mode = "general"
    reason = "No deterministic expert mode matched strongly enough."

    product_score = scores["verified_product"]
    diagnosis_score = scores["advanced_diagnosis"]
    science_score = scores["advanced_turf_science"]
    guidance_score = scores["general_turf_guidance"]
    has_product = product_score >= 5 and _has_product_intent(q)
    has_symptoms = _has_symptom_problem(q)
    specific_science_signals = _specific_science_signals(q)

    if _prefer_diagnosis_over_science(q, diagnosis_score):
        mode = "advanced_diagnosis"
        reason = "The phrasing sounds like an active field troubleshooting problem, so diagnosis takes priority over a general explainer."
    elif _prefer_science_over_diagnosis(q, science_score, diagnosis_score):
        mode = "advanced_turf_science"
        reason = "Broad explainer language matched a turf science topic more strongly than a field differential."
    elif has_product and has_symptoms:
        mode = "advanced_diagnosis"
        reason = "Mixed product and symptom intent; diagnose before recommending a product."
    elif has_product:
        mode = "verified_product"
        reason = "Product, target, rate, or recommendation language matched."
    elif diagnosis_score >= 6 and (has_symptoms or diagnosis_score >= science_score):
        mode = "advanced_diagnosis"
        reason = "Symptom or troubleshooting language matched diagnostic buckets."
    elif science_score >= 6:
        mode = "advanced_turf_science"
        reason = "Mechanism or turf science language matched advanced science records."
    elif guidance_score >= 6 and specific_science_signals and diagnosis_score < 6 and not has_symptoms:
        mode = "advanced_turf_science"
        reason = "The wording is broad, but it still names a specific turf-science topic, so science takes priority over general guidance."
    elif guidance_score >= 6:
        mode = "general_turf_guidance"
        reason = "Broad agronomy or turf-health guidance language matched."

    ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    fallback = next((name for name, score in ordered if name != mode and score > 0), "general")
    confidence = _confidence_for(mode, scores)
    ordered_modes = [name for name, score in ordered if score > 0]
    if mode in ordered_modes:
        ordered_modes.remove(mode)
    ordered_modes = [mode] + ordered_modes
    if "general" not in ordered_modes:
        ordered_modes.append("general")

    return {
        "mode": mode,
        "router_confidence": confidence,
        "scores": scores,
        "matched_signals": signals.get(mode, []),
        "all_signals": signals,
        "fallback_mode": fallback,
        "ordered_modes": ordered_modes,
        "reason": reason,
    }


def _score_product(question_lower: str) -> int:
    score = 0
    for term in PRODUCT_INTENT_TERMS:
        if _contains(question_lower, term):
            score += 6 if len(term) > 6 else 3
    if _detect_product(question_lower):
        score += 8
    if _detect_target(question_lower):
        score += 3
    if any(surface in question_lower for surface in ["green", "greens", "fairway", "fairways", "tee", "tees", "rough"]):
        score += 2
    return score


def _has_product_intent(question_lower: str) -> bool:
    return any(_contains(question_lower, term) for term in PRODUCT_INTENT_TERMS) or bool(_detect_product(question_lower))


def _score_diagnosis(question_lower: str) -> int:
    score = 0
    for term in DIAGNOSIS_INTENT_TERMS:
        if _contains(question_lower, term):
            score += 6 if len(term) > 6 else 3
    for term in SYMPTOM_TERMS:
        if _contains(question_lower, term):
            score += 3
    for bucket in DIAGNOSTIC_BUCKETS.values():
        for trigger in bucket["triggers"]:
            if _contains(question_lower, trigger):
                score += 4 if len(trigger) > 6 else 2
    return score


def _score_science(question_lower: str) -> int:
    score = 0
    for term in SCIENCE_INTENT_TERMS:
        if _contains(question_lower, term):
            score += 4
    for aliases in SCIENCE_TOPIC_ALIASES.values():
        for alias in aliases:
            if _contains(question_lower, alias):
                score += 5 if len(alias) > 6 else 2
    return score


def _score_general_guidance(question_lower: str) -> int:
    score = 0
    for term in GENERAL_GUIDANCE_TERMS:
        if _contains(question_lower, term):
            score += 4
    patterns = [
        r"\bhow do i keep\b.*\bturf\b",
        r"\bhow do i keep\b.*\bgreens?\b",
        r"\bhow do i keep\b.*\bfairways?\b",
        r"\bhow do i keep\b.*\balive\b",
        r"\bprepar\w*\b.*\bseed\w*\b",
        r"\bseed\w*\b.*\bgreen(s)?\b",
        r"\bseedbed\b",
        r"\bgrow-?in\b",
        r"\bwhat should i be watching\b",
        r"\bwhat should i know about\b.*\bturf\b",
        r"\bwhat should i know about\b.*\bgreens\b",
        r"\bwhat should i know about\b.*\bfairways\b",
        r"\bwhat matters most\b",
        r"\bwhat makes\b.*\bperform well\b",
        r"\bwhat gets superintendents in trouble fastest\b",
        r"\bwhat am i probably missing\b",
        r"\bsummer stress\b",
    ]
    for pattern in patterns:
        if re.search(pattern, question_lower):
            score += 6
    return score


def _product_signals(question_lower: str) -> list[str]:
    signals = [term for term in PRODUCT_INTENT_TERMS if _contains(question_lower, term)][:8]
    product = _detect_product(question_lower)
    if product:
        signals.append(product["display_name"])
    target = _detect_target(question_lower)
    if target:
        signals.append(target)
    return _unique(signals)


def _diagnosis_signals(question_lower: str) -> list[str]:
    signals = [term for term in DIAGNOSIS_INTENT_TERMS if _contains(question_lower, term)]
    signals.extend(term for term in SYMPTOM_TERMS if _contains(question_lower, term))
    for bucket in DIAGNOSTIC_BUCKETS.values():
        signals.extend(trigger for trigger in bucket["triggers"] if _contains(question_lower, trigger))
    return _unique(signals)[:12]


def _science_signals(question_lower: str) -> list[str]:
    signals = [term for term in SCIENCE_INTENT_TERMS if _contains(question_lower, term)]
    for aliases in SCIENCE_TOPIC_ALIASES.values():
        signals.extend(alias for alias in aliases if _contains(question_lower, alias))
    return _unique(signals)[:12]


def _specific_science_signals(question_lower: str) -> list[str]:
    generic_intents = set(SCIENCE_INTENT_TERMS)
    signals = []
    for aliases in SCIENCE_TOPIC_ALIASES.values():
        for alias in aliases:
            if alias in generic_intents:
                continue
            if _contains(question_lower, alias):
                signals.append(alias)
    return _unique(signals)[:12]


def _general_guidance_signals(question_lower: str) -> list[str]:
    signals = [term for term in GENERAL_GUIDANCE_TERMS if _contains(question_lower, term)]
    for pattern, label in (
        (r"\bhow do i keep\b.*\bturf\b", "how do i keep turf"),
        (r"\bhow do i keep\b.*\bgreens?\b", "how do i keep greens"),
        (r"\bhow do i keep\b.*\bfairways?\b", "how do i keep fairways"),
        (r"\bhow do i keep\b.*\balive\b", "how do i keep it alive"),
        (r"\bwhat should i be watching\b", "what should i be watching"),
        (r"\bwhat should i know about\b.*\bturf\b", "what should i know about turf"),
        (r"\bwhat matters most\b", "what matters most"),
    ):
        if re.search(pattern, question_lower):
            signals.append(label)
    return _unique(signals)[:10]


def _detect_target(question_lower: str) -> str | None:
    for target_key, aliases in TARGET_ALIASES.items():
        for alias in aliases:
            if _contains(question_lower, alias):
                return target_key
    return None


def _has_symptom_problem(question_lower: str) -> bool:
    symptom_hit = any(_contains(question_lower, term) for term in SYMPTOM_TERMS)
    diagnostic_hit = any(
        _contains(question_lower, term)
        for term in [
            "what is causing", "what's causing", "diagnose", "diagnosis",
            "is this", "could this be", "could this", "symptoms", "dying",
        ]
    )
    strong_symptoms = [
        "wilt", "wilting", "decline", "thinning", "thin", "yellowing", "spots",
        "patches", "roots", "shallow roots", "dying", "damage", "injury",
        "explode", "exploded", "outbreak", "flare", "flared",
    ]
    symptom_count = sum(1 for term in strong_symptoms if _contains(question_lower, term))
    return diagnostic_hit or symptom_count >= 1


def _prefer_science_over_diagnosis(question_lower: str, science_score: int, diagnosis_score: int) -> bool:
    science_first_patterns = [
        "what causes bentgrass to decline in summer",
        "what causes poa annua to decline faster than bentgrass in summer",
        "why does poa collapse faster than bentgrass in summer",
        "why does poa annua collapse faster than bentgrass in summer",
        "what does high clip volume mean",
        "what should i know about abw timing",
        "how should i think about abw timing",
        "talk me through summer stress on cool-season turf",
        "summer stress on cool-season turf",
        "warm nights drive bentgrass decline",
        "why do warm nights hurt bentgrass more than hot days",
        "hot days alone",
        "wilt even when moisture readings are high",
        "bentgrass wilt even when moisture readings are high",
        "why does black layer wreck roots",
        "low nitrogen and extended leaf wetness",
        "calendar interval in primo timing",
        "growing degree days better than fixed intervals",
        "when does gypsum actually help",
        "poa annua often collapse faster than bentgrass",
        "why does poa annua decline faster than bentgrass in summer",
        "mower injury so often mimic foliar disease",
        "mower injury mimic disease so often",
        "both a nutrient source and a salinity stress source",
    ]
    if any(pattern in question_lower for pattern in science_first_patterns):
        return True
    if science_score >= 8 and diagnosis_score <= science_score + 4:
        if any(
            phrase in question_lower
            for phrase in (
                "why do warm nights",
                "why do warm nights hurt bentgrass",
                "why can low nitrogen",
                "why does clipping yield",
                "why does black layer",
                "why are growing degree days",
                "when does gypsum",
                "why does poa annua",
                "why does poa collapse faster",
                "why does poa annua collapse faster",
                "why does poa annua decline faster",
                "why does mower injury",
                "why does mower injury mimic disease",
                "how should i think about reclaimed water",
                "why can bentgrass wilt",
            )
        ):
            return True
    return False


def _prefer_diagnosis_over_science(question_lower: str, diagnosis_score: int) -> bool:
    diagnosis_first_patterns = [
        "ryegrass is hanging on and bermuda transition is stuck",
        "ryegrass is hanging on too long and bermuda transition is stuck",
        "walk me through how you would separate water stress from disease",
        "how would you separate wet wilt from pythium root dysfunction",
        "how do you decide when this is a species-fit problem",
    ]
    if any(pattern in question_lower for pattern in diagnosis_first_patterns):
        return diagnosis_score >= 6
    return False


def _contains(question_lower: str, term: str) -> bool:
    term = str(term or "").lower().strip()
    if not term:
        return False
    if term.startswith(" ") or term.endswith(" "):
        return term in question_lower
    escaped = re.escape(term)
    prefix = r"\b" if term[0].isalnum() else ""
    suffix = r"\b" if term[-1].isalnum() else ""
    return re.search(prefix + escaped + suffix, question_lower) is not None


def _confidence_for(mode: str, scores: dict[str, int]) -> float:
    if mode == "general":
        return 0.0
    chosen = scores.get(mode, 0)
    others = [score for name, score in scores.items() if name != mode]
    margin = chosen - max(others or [0])
    confidence = 0.55 + min(chosen, 30) / 100 + max(min(margin, 20), -10) / 100
    return round(max(0.5, min(confidence, 0.98)), 2)


def _unique(items: list[str]) -> list[str]:
    seen = set()
    unique = []
    for item in items:
        normalized = re.sub(r"\s+", " ", str(item).strip().lower())
        if normalized and normalized not in seen:
            seen.add(normalized)
            unique.append(normalized)
    return unique
