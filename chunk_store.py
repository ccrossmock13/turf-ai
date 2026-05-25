"""Local chunk reconstruction so document text stays out of remote metadata."""

from __future__ import annotations

import os
import re
from functools import lru_cache

import PyPDF2


CHUNK_SIZE = 800
CHUNK_OVERLAP = 150
MIN_CHUNK_SIZE = 200
MAX_CHUNKS_PER_DOC = 50


def extract_text_from_pdf(filepath: str) -> tuple[str, int]:
    """Extract text from a PDF file."""
    try:
        with open(filepath, "rb") as handle:
            reader = PyPDF2.PdfReader(handle)
            text = ""
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            return text.strip(), len(reader.pages)
    except Exception:
        return "", 0


def clean_text(text: str) -> str:
    """Normalize PDF text before chunking."""
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"Page \d+ of \d+", "", text)
    text = re.sub(r"http[s]?://\S+", "", text)
    return text.strip()


def smart_chunk(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into repeatable chunks with overlap."""
    if len(text) < chunk_size:
        return [text] if len(text) > MIN_CHUNK_SIZE else []

    chunks: list[str] = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        if end >= len(text):
            chunk = text[start:]
            if len(chunk) > MIN_CHUNK_SIZE:
                chunks.append(chunk)
            break

        search_start = max(start + chunk_size - 100, start)
        search_text = text[search_start : end + 50]
        best_break = -1
        for pattern in [". ", ".\n", "? ", "! ", "\n\n"]:
            idx = search_text.rfind(pattern)
            if idx > best_break:
                best_break = idx
        if best_break > 0:
            end = search_start + best_break + 1

        chunk = text[start:end].strip()
        if len(chunk) > MIN_CHUNK_SIZE:
            chunks.append(chunk)
        start = end - overlap

    return chunks[:MAX_CHUNKS_PER_DOC]


@lru_cache(maxsize=128)
def _chunks_for_filepath(filepath: str) -> tuple[str, ...]:
    if not filepath or not os.path.exists(filepath):
        return ()
    text, _ = extract_text_from_pdf(filepath)
    if len(text) < 500:
        return ()
    cleaned = clean_text(text)
    return tuple(smart_chunk(cleaned))


def get_chunk_text(filepath: str | None, chunk_id: int | str | None) -> str:
    """Reconstruct a stored chunk locally from filepath and chunk id."""
    if not filepath or chunk_id is None:
        return ""
    try:
        idx = int(chunk_id)
    except (TypeError, ValueError):
        return ""
    chunks = _chunks_for_filepath(filepath)
    if idx < 0 or idx >= len(chunks):
        return ""
    return chunks[idx]


def get_match_text(match: dict) -> str:
    """Return chunk text for a Pinecone match, preferring local reconstruction."""
    metadata = match.get("metadata", {}) if isinstance(match, dict) else {}
    filepath = metadata.get("filepath")
    chunk_id = metadata.get("chunk_id")
    hydrated = get_chunk_text(filepath, chunk_id)
    if hydrated:
        return hydrated
    return metadata.get("text", "") if hasattr(metadata, "get") else ""
