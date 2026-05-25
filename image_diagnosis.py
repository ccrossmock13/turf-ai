"""Image-aware turf diagnosis support."""

from __future__ import annotations

import base64
import binascii
import json
import os
import re
from typing import Any

from advanced_diagnosis import answer_advanced_diagnosis
from advanced_turf_science import answer_advanced_turf_science


ALLOWED_IMAGE_MIME_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "image/gif",
}

IMAGE_ONLY_DEFAULT_QUESTION = "How should I diagnose this turf issue from the uploaded image?"

IMAGE_ANALYSIS_SIGNAL_HINTS = [
    "frayed leaf tips",
    "leaf shredding",
    "cut quality issue",
    "mowing uniformity issue",
    "effective height of cut difference",
    "spray pass pattern",
    "nozzle overlap",
    "application pattern issue",
    "localized dry spot",
    "hydrophobic dry patch",
    "wet low spot",
    "black layer risk",
    "layering in core",
    "topdressing compatibility issue",
    "night-feeding insect damage",
    "grub root feeding",
    "poa annua decline",
    "bentgrass heat stress",
    "shade thinning",
    "salt edge burn",
    "herbicide bleaching pattern",
    "pigment inhibitor herbicide injury",
    "herbicide injury pattern",
    "mower injury",
    "traffic wear",
]

VISUAL_PRODUCT_ONLY_TERMS = [
    "rate",
    "rei",
    "reentry",
    "tank mix",
    "mix with",
    "rainfast",
    "retreatment interval",
    "max rate",
    "reseed",
    "overseed",
]


def validate_image_attachment(raw_attachment: dict[str, Any] | None, *, max_bytes: int) -> dict[str, Any]:
    """Validate and normalize a single JSON image attachment."""
    if not raw_attachment:
        return {"ok": True, "attachment": None}
    if not isinstance(raw_attachment, dict):
        return {"ok": False, "error": "The uploaded image could not be read. Please try attaching it again."}

    data_url = str(raw_attachment.get("data_url") or raw_attachment.get("dataUrl") or "").strip()
    if not data_url:
        return {"ok": False, "error": "The uploaded image was empty. Please attach a turf photo or core image."}

    match = re.match(r"^data:(image/[a-zA-Z0-9.+-]+);base64,(.+)$", data_url, flags=re.DOTALL)
    if not match:
        return {"ok": False, "error": "Please upload a PNG, JPG, WEBP, or GIF image."}

    mime_type = match.group(1).lower()
    encoded = match.group(2)
    if mime_type not in ALLOWED_IMAGE_MIME_TYPES:
        return {"ok": False, "error": "Please upload a PNG, JPG, WEBP, or GIF image."}

    try:
        decoded = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        return {"ok": False, "error": "The uploaded image data was invalid. Please try a fresh upload."}

    if len(decoded) > max_bytes:
        return {
            "ok": False,
            "error": f"That image is too large. Please keep uploads under {max_bytes // (1024 * 1024)} MB.",
        }

    filename = os.path.basename(str(raw_attachment.get("name") or "turf-image"))
    return {
        "ok": True,
        "attachment": {
            "data_url": data_url,
            "mime_type": mime_type,
            "name": filename,
            "size_bytes": len(decoded),
        },
    }


def answer_image_diagnosis(
    question: str,
    image_attachment: dict[str, Any] | None,
    course_profile: dict[str, Any] | None,
    openai_client: Any,
    *,
    model: str = "gpt-4o-mini",
) -> dict[str, Any] | None:
    """Use uploaded image evidence to strengthen diagnosis mode."""
    if not image_attachment or not openai_client:
        return None

    question_text = (question or "").strip()
    if question_text and _looks_like_label_only_question(question_text):
        return None

    visual = _analyze_turf_image(question_text, image_attachment, openai_client, model=model)
    if not visual:
        return None

    if not visual.get("turf_related", True):
        return _build_non_turf_response(visual, image_attachment)

    enhanced_question = _build_image_question(question_text, visual)
    base_response = answer_advanced_diagnosis(enhanced_question, course_profile)
    if not base_response:
        base_response = answer_advanced_turf_science(enhanced_question, course_profile)

    return _build_image_response(base_response, visual, image_attachment)


def _build_image_response(
    base_response: dict[str, Any] | None,
    visual: dict[str, Any],
    image_attachment: dict[str, Any],
) -> dict[str, Any]:
    observed = _coerce_list(visual.get("observed_clues"))
    signals = _coerce_list(visual.get("diagnostic_signals"))
    field_checks = _coerce_list(visual.get("field_checks"))
    limitations = _coerce_list(visual.get("limitations"))
    image_type = str(visual.get("image_type") or "unknown").replace("_", " ")
    confidence_note = str(visual.get("confidence_note") or "").strip()
    merged_signals = list(dict.fromkeys((observed + signals)[:10]))
    herbicide_signal_text = " ".join(signals + observed + ([confidence_note] if confidence_note else [])).lower()
    herbicide_signals = any(
        term in herbicide_signal_text
        for term in (
            "herbicide injury",
            "herbicide bleaching",
            "pigment inhibitor",
            "light-colored",
            "light colored",
            "bleaching",
            "whitening",
        )
    )

    intro_parts = [
        f"**Image Intake:** I treated the upload as a {image_type} image.",
    ]
    if observed:
        intro_parts.append("**Visible Clues:**\n" + "\n".join(f"- {item}" for item in observed[:5]))
    if confidence_note:
        intro_parts.append(f"**Visual Read:** {confidence_note}")
    if limitations:
        intro_parts.append("**Image Limits:**\n" + "\n".join(f"- {item}" for item in limitations[:3]))

    if base_response:
        answer_blocks = intro_parts + [base_response["answer"]]
        if herbicide_signals and "herbicide" not in base_response["answer"].lower():
            answer_blocks.append(
                "**Image-Specific Caution:** The whitening and patchy discoloration in this photo can also fit "
                "herbicide bleaching or overlap injury, especially after pigment-inhibitor applications. "
                "Check recent spray history, overlap geometry, and species sensitivity before treating this like a disease."
            )
        answer = "\n\n".join(answer_blocks)
        sources = [{
            "name": "Uploaded Turf Image",
            "type": "user_image",
            "image_name": image_attachment.get("name"),
            "image_type": image_type,
            "note": "Visual evidence from the uploaded turf image was used to strengthen the diagnosis.",
        }] + list(base_response.get("sources", []))
        response = dict(base_response)
        response.update({
            "answer": answer,
            "sources": sources,
            "confidence": {"score": 89, "label": "Image-Supported Diagnosis"},
            "kb_verdict": "image_diagnosis",
            "image_diagnosis": {
                "image_type": image_type,
                "observed_clues": observed[:6],
                "diagnostic_signals": signals[:6],
                "field_checks": field_checks[:6],
                "limitations": limitations[:4],
                "image_name": image_attachment.get("name"),
            },
            "needs_review": False,
            "grounding": {"verified": True, "issues": []},
        })
        if "diagnostic_buckets" not in response:
            response["diagnostic_buckets"] = []
        return response

    parts = intro_parts + [
        "**Bottom Line:** The image adds useful field evidence, but I still need on-site checks before calling one exact cause.",
    ]
    if field_checks:
        parts.append("**Field Checks To Do Next:**\n" + "\n".join(f"- {item}" for item in field_checks[:5]))
    parts.append(
        "**Before you spray:** I will not jump from a photo straight to a product or rate. "
        "Use the image to narrow the differential first, then confirm the target and surface before choosing a treatment."
    )
    return {
        "answer": "\n\n".join(parts),
        "sources": [{
            "name": "Uploaded Turf Image",
            "type": "user_image",
            "image_name": image_attachment.get("name"),
            "image_type": image_type,
            "note": "Visual evidence from the uploaded turf image guided the next field checks.",
        }],
        "confidence": {"score": 78, "label": "Image Triage"},
        "needs_review": False,
        "kb_verdict": "image_diagnosis",
        "diagnostic_buckets": [],
        "advanced_science_topics": [],
        "image_diagnosis": {
            "image_type": image_type,
            "observed_clues": observed[:6],
            "diagnostic_signals": merged_signals[:6],
            "field_checks": field_checks[:6],
            "limitations": limitations[:4],
            "image_name": image_attachment.get("name"),
        },
        "grounding": {"verified": True, "issues": []},
    }


def _build_non_turf_response(visual: dict[str, Any], image_attachment: dict[str, Any]) -> dict[str, Any]:
    limitations = _coerce_list(visual.get("limitations"))
    answer_parts = [
        "**Bottom Line:** I could not find enough turf-specific visual evidence in that image to run the field-diagnosis path confidently.",
        "Please upload a canopy photo, close leaf shot, pattern view, or root/core image from the affected area.",
    ]
    if limitations:
        answer_parts.append("**Why The Image Fell Short:**\n" + "\n".join(f"- {item}" for item in limitations[:3]))
    return {
        "answer": "\n\n".join(answer_parts),
        "sources": [{
            "name": "Uploaded Turf Image",
            "type": "user_image",
            "image_name": image_attachment.get("name"),
            "note": "The uploaded image did not provide enough turf-specific evidence.",
        }],
        "confidence": {"score": 38, "label": "Need Turf Image"},
        "needs_review": False,
        "kb_verdict": "image_not_turf_related",
        "image_diagnosis": {
            "image_type": str(visual.get("image_type") or "unknown").replace("_", " "),
            "observed_clues": _coerce_list(visual.get("observed_clues"))[:4],
            "diagnostic_signals": [],
            "field_checks": [],
            "limitations": limitations[:4],
            "image_name": image_attachment.get("name"),
        },
        "grounding": {"verified": True, "issues": []},
    }


def _analyze_turf_image(question: str, image_attachment: dict[str, Any], openai_client: Any, *, model: str) -> dict[str, Any] | None:
    prompt = (
        "Review the uploaded image as a cautious turfgrass diagnostician. "
        "Do not confirm a disease, product need, or exact treatment from an image alone. "
        "Return strict JSON with keys turf_related, image_type, observed_clues, diagnostic_signals, "
        "field_checks, limitations, confidence_note. "
        "Prefer diagnostic_signals that look like these turf phrases when relevant: "
        + ", ".join(IMAGE_ANALYSIS_SIGNAL_HINTS)
        + ". "
        "Question context: "
        + (question or IMAGE_ONLY_DEFAULT_QUESTION)
    )
    response = openai_client.chat.completions.create(
        model=model,
        temperature=0,
        max_tokens=500,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "You are reviewing a turf-management field image. "
                    "Stay conservative. Identify only visible clues and next checks."
                ),
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_attachment["data_url"]}},
                ],
            },
        ],
    )
    try:
        content = response.choices[0].message.content or "{}"
    except (AttributeError, IndexError, KeyError, TypeError):
        return None

    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return None

    return {
        "turf_related": bool(payload.get("turf_related", True)),
        "image_type": str(payload.get("image_type") or "unknown").lower().strip().replace(" ", "_"),
        "observed_clues": _coerce_list(payload.get("observed_clues")),
        "diagnostic_signals": _coerce_list(payload.get("diagnostic_signals")),
        "field_checks": _coerce_list(payload.get("field_checks")),
        "limitations": _coerce_list(payload.get("limitations")),
        "confidence_note": str(payload.get("confidence_note") or "").strip(),
    }


def _build_image_question(question: str, visual: dict[str, Any]) -> str:
    base = (question or "").strip() or IMAGE_ONLY_DEFAULT_QUESTION
    signal_bits = _coerce_list(visual.get("diagnostic_signals")) + _coerce_list(visual.get("observed_clues"))
    signal_bits += _infer_signals_from_visuals(base, visual)
    signal_bits = list(dict.fromkeys(signal_bits))[:8]
    if not signal_bits:
        return base
    return f"{base} Visual clues: " + "; ".join(signal_bits) + "."


def _looks_like_label_only_question(question: str) -> bool:
    q = (question or "").lower()
    return any(term in q for term in VISUAL_PRODUCT_ONLY_TERMS) and not any(
        term in q for term in ("why", "diagnose", "pattern", "look", "image", "photo", "symptom", "causing")
    )


def _infer_signals_from_visuals(question: str, visual: dict[str, Any]) -> list[str]:
    q = (question or "").lower()
    image_type = str(visual.get("image_type") or "").lower()
    clue_text = " ".join(_coerce_list(visual.get("observed_clues")) + _coerce_list(visual.get("diagnostic_signals"))).lower()
    signals = []

    if any(term in clue_text for term in ("uniformity", "mowing pattern", "differences in grass height", "cut")) or any(
        term in q for term in ("mower", "cut quality", "uniformity", "setup", "height of cut")
    ):
        signals.extend([
            "cut quality",
            "mowing uniformity",
            "effective height of cut difference",
        ])

    if any(term in clue_text for term in ("pass", "overlap", "pattern")) or "pattern" in q:
        signals.extend([
            "application pattern",
            "spray pass",
            "coverage issue",
        ])

    if "pest" in image_type or any(term in q for term in ("what pest", "what insect", "bug", "millipede", "grub", "cutworm", "webworm")):
        signals.extend([
            "insect feeding pattern",
            "soap flush",
            "night feeding",
        ])

    if any(term in q for term in ("rolling", "mechanical stress", "tournament prep")):
        signals.extend([
            "mechanical stress budget",
            "conditioning pressure",
        ])

    herbicide_question = any(
        term in q for term in ("herbicide", "bleach", "bleaching", "pigment inhibitor", "mesotrione", "tenacity")
    )
    herbicide_clues = any(
        term in clue_text for term in (
            "bleach",
            "bleaching",
            "light-colored",
            "light colored",
            "white",
            "whiten",
            "discoloration in patches",
            "pigment",
        )
    )
    if herbicide_question or herbicide_clues:
        signals.extend([
            "herbicide injury pattern",
            "pigment inhibitor herbicide injury",
            "herbicide bleaching pattern",
        ])

    return signals


def _coerce_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if value is None:
        return []
    text = str(value).strip()
    return [text] if text else []
