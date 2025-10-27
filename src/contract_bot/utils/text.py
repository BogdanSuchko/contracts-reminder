from __future__ import annotations

import os
import re
import unicodedata

DEFAULT_FILENAME = "document"


def sanitize_filename(name: str | None, fallback: str = DEFAULT_FILENAME) -> str:
    if not name:
        return fallback
    normalized = unicodedata.normalize("NFKD", name)
    normalized = normalized.replace(" ", "_")
    cleaned = re.sub(r"[^0-9A-Za-zА-Яа-я_.\-]", "", normalized)
    return cleaned or fallback


def humanize_filename(name: str | None) -> str:
    if not name:
        return DEFAULT_FILENAME
    stem, ext = os.path.splitext(name)
    candidate = stem.replace("_", " ")
    candidate = re.sub(r"(?<=[a-zа-я])(?=[A-ZА-Я])", " ", candidate)
    candidate = re.sub(r"\s+", " ", candidate).strip()
    if not candidate:
        candidate = stem
    ext = ext or ""
    return f"{candidate}{ext}"
