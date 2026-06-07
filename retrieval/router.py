"""QTKĐ file-stem router: detect which QTKĐ file a query targets.

Uses explicit QTKĐ number (e.g. "1.061") or device-name alias (e.g. "van an toàn")
found in the query text. Returns None when uncertain → full-corpus search.

Number map is built lazily from Qdrant on first call (one-time scan, ~0.1s).
"""
from __future__ import annotations

import os
import re
from qdrant_client import QdrantClient

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION = "qtkd_rag"

# X.YYY — exactly one digit, dot, exactly 3 digits, NOT followed by another digit.
# Matches "1.061" / "1.160" but NOT "6.3", "0.05", "1400".
_NUMBER_RE = re.compile(r'(\d\.\d{3})(?!\d)')

# Device-name aliases (all lowercase) → QTKĐ number
_DEVICE_ALIASES: dict[str, str] = {
    "van an toàn": "1.061",
    "bàn tạo áp": "1.062",
    "bình phân ly": "1.063",
    "h3000": "1.071",
    "áp kế pittông tiêu chuẩn": "1.159",
    "thiết bị đo áp suất số": "1.160",
    "akkđ": "1.160",
    "dpi 610": "1.190",
    "dpi610": "1.190",
}

_number_to_stem: dict[str, str] | None = None
_STEM_NUMBER_RE = re.compile(r'QTKD_(\d+\.\d+)')


def _build_number_to_stem() -> dict[str, str]:
    """Scroll Qdrant for distinct file_stems, map QTKĐ number → full file_stem."""
    client = QdrantClient(url=QDRANT_URL)
    stems: set[str] = set()
    offset = None
    while True:
        results, next_offset = client.scroll(
            collection_name=COLLECTION,
            limit=500,
            offset=offset,
            with_payload=["file_stem"],
            with_vectors=False,
        )
        for r in results:
            fs = (r.payload or {}).get("file_stem")
            if fs:
                stems.add(fs)
        if next_offset is None:
            break
        offset = next_offset

    mapping: dict[str, str] = {}
    for stem in stems:
        m = _STEM_NUMBER_RE.search(stem)
        if m:
            mapping[m.group(1)] = stem
    return mapping


def _ensure_mapping() -> dict[str, str]:
    global _number_to_stem
    if _number_to_stem is None:
        _number_to_stem = _build_number_to_stem()
    return _number_to_stem


def route(query: str) -> str | None:
    """Return file_stem if query clearly targets one QTKĐ file, else None.

    Priority:
    1. Explicit QTKĐ number in query (highest confidence).
    2. Device-name alias (medium confidence).
    Returns None when no signal found → caller falls back to full-corpus search.
    """
    mapping = _ensure_mapping()
    q = query.lower()

    # Highest confidence: explicit number like "1.061", "1.160"
    m = _NUMBER_RE.search(q)
    if m:
        stem = mapping.get(m.group(1))
        if stem:
            return stem

    # Medium confidence: device alias
    for alias, number in _DEVICE_ALIASES.items():
        if alias in q:
            stem = mapping.get(number)
            if stem:
                return stem

    return None
