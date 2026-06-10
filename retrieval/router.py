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
    # Biến thể chính tả thực tế trong câu hỏi: "píttông" (có dấu í) và đảo trật tự
    # "pittông áp kế" — thiếu chúng, câu so sánh 2 thiết bị chỉ bắt được 1 tín hiệu
    # và bị ghim nhầm 1 file (đo trên answer-set Q115–Q117).
    "áp kế píttông tiêu chuẩn": "1.159",
    "pittông áp kế": "1.159",
    "píttông áp kế": "1.159",
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


def route_files(query: str) -> frozenset[str]:
    """Tập file_stem phân biệt mà query nhắc tới (số QTKĐ tường minh + alias).

    Rỗng = không tín hiệu; 1 phần tử = ghim file; ≥2 = câu so sánh nhiều thiết bị
    → retriever chạy phễu RIÊNG cho từng file (một phễu chung bị cụm từ vựng áp
    đảo — 3 file áp kế píttông — đè bẹp file thiểu số: đo Q115/Q116 top-5 không
    còn chunk 1.061 nào dù query nhắc 'van an toàn').
    """
    mapping = _ensure_mapping()
    q = query.lower()

    stems: set[str] = set()
    for num in _NUMBER_RE.findall(q):
        stem = mapping.get(num)
        if stem:
            stems.add(stem)
    for alias, number in _DEVICE_ALIASES.items():
        if alias in q:
            stem = mapping.get(number)
            if stem:
                stems.add(stem)
    return frozenset(stems)


def route(query: str) -> str | None:
    """Return file_stem if query clearly targets EXACTLY one QTKĐ file, else None.

    Đúng 1 stem → ghim file đó; 0 hoặc ≥2 (câu so sánh nhiều thiết bị, hoặc số
    và alias mâu thuẫn) → None. Trước đây tín hiệu ĐẦU TIÊN thắng nên câu so
    sánh "van an toàn (1.061) và áp kế (1.159)" bị ghim 1 file, nửa kia không
    bao giờ được retrieve (đo: 2 wrong_refusal cross_file).
    """
    stems = route_files(query)
    if len(stems) == 1:
        return next(iter(stems))
    return None
