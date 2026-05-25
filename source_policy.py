"""Shared source-access policy for locally stored documents."""

from __future__ import annotations

import os
from typing import Any


RESTRICTED_SOURCE_URL_PREFIXES = (
    "/static/epa_labels/",
    "/static/solution-sheets/",
    "/static/spray-programs/",
    "/static/ntep-pdfs/",
    "/epa_labels/",
    "/solution-sheets/",
    "/spray-programs/",
    "/ntep-pdfs/",
)


def is_restricted_source_url(url: str | None) -> bool:
    """Return True when a URL points at locally stored third-party PDFs."""
    if not url:
        return False
    return any(url.startswith(prefix) for prefix in RESTRICTED_SOURCE_URL_PREFIXES)


def sanitize_source_url(url: str | None) -> str | None:
    """Hide restricted local-document URLs from user-facing surfaces."""
    if is_restricted_source_url(url):
        return None
    return url


def safe_public_resources() -> list[dict[str, Any]]:
    """Return only safe public resource links."""
    return [
        {
            "filename": "USGA Green Section",
            "url": "https://www.usga.org/course-care.html",
            "category": "Official Resources",
        },
        {
            "filename": "GCSAA Resources",
            "url": "https://www.gcsaa.org/",
            "category": "Official Resources",
        },
        {
            "filename": "Purdue Turfgrass Science",
            "url": "https://turf.purdue.edu/",
            "category": "Official Resources",
        },
        {
            "filename": "Rutgers Center for Turfgrass Science",
            "url": "https://turf.rutgers.edu/",
            "category": "Official Resources",
        },
        {
            "filename": "EPA Pesticide Product and Label Search",
            "url": "https://ordspub.epa.gov/ords/pesticides/f?p=PPLS:1",
            "category": "Official Resources",
        },
    ]


def public_product_label_resources(base_dir: str = "static/product-labels") -> list[dict[str, Any]]:
    """Return product-label PDFs that are allowed to be viewed again."""
    resources: list[dict[str, Any]] = []
    if not os.path.isdir(base_dir):
        return resources

    for root, _, files in os.walk(base_dir):
        for filename in files:
            if not filename.lower().endswith(".pdf") or filename.startswith("."):
                continue
            full_path = os.path.join(root, filename)
            relative_path = full_path.replace("static/", "")
            resources.append(
                {
                    "filename": filename,
                    "url": f"/static/{relative_path}",
                    "category": "Product Labels",
                }
            )

    resources.sort(key=lambda item: item["filename"].lower())
    return resources
