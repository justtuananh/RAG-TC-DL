"""QTKĐ file-stem router: detect which QTKĐ file a query targets.

Uses explicit QTKĐ number (e.g. "1.061") or device-name alias (e.g. "van an toàn")
found in the query text. Returns None when uncertain → full-corpus search.

Number map and device aliases are read lazily from the `procedure` table (+ its
`document` and `device_type`): the number comes from the document header, and the
row always points to the current version of a QTKĐ. When Postgres is unreachable
the number map falls back to a Qdrant file_stem scan and the aliases to a
hardcoded table, so retrieval never depends on Postgres being up.
"""

from __future__ import annotations

import re

from vectorstore import qdrant

# X.YYY — exactly one digit, dot, exactly 3 digits, NOT followed by another digit.
# Matches "1.061" / "1.160" but NOT "6.3", "0.05", "1400".
_NUMBER_RE = re.compile(r'(\d\.\d{3})(?!\d)')

# Device-name aliases (all lowercase) → QTKĐ number.
# Đây chỉ là DỰ PHÒNG khi DB chưa sẵn sàng/chưa seed. Nguồn sự thật là bảng
# `device_type` + `procedure` (Sprint 3); xem `_load_db_device_aliases`.
_FALLBACK_DEVICE_ALIASES: dict[str, str] = {
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
_device_aliases: dict[str, tuple[str, ...]] | None = None
# Tệp tải lên có thể giữ chữ "Đ" trong tên (stem "QTKĐ_9.001_...").
_STEM_NUMBER_RE = re.compile(r'QTK[DĐ]_(\d+\.\d+)')


def _load_db_device_aliases() -> dict[str, tuple[str, ...]] | None:
    """Đọc alias thiết bị từ DB (device_type + procedure); None nếu không đọc được.

    Bọc try/except rộng có chủ đích: router phải chạy được cả khi Postgres
    chưa lên hoặc chưa migrate — khi đó rơi về hằng số dự phòng để không đổi
    hành vi truy hồi hiện tại.
    """
    try:
        from db import SessionLocal
        from knowledge.reference import device_alias_map

        session = SessionLocal()
        try:
            mapping = device_alias_map(session)
        finally:
            session.close()
        return mapping or None
    except Exception:
        return None


def _ensure_device_aliases() -> dict[str, tuple[str, ...]]:
    global _device_aliases
    if _device_aliases is None:
        from_db = _load_db_device_aliases()
        if from_db:
            _device_aliases = from_db
        else:
            _device_aliases = {
                alias: (number,) for alias, number in _FALLBACK_DEVICE_ALIASES.items()
            }
    return _device_aliases


def _load_db_number_map() -> dict[str, str] | None:
    """Số QTKĐ → file_stem từ bảng ``procedure``; None nếu không đọc được DB.

    Bọc try/except rộng như ``_load_db_device_aliases``: DB chưa lên thì router
    rơi về quét Qdrant thay vì làm hỏng truy hồi.
    """
    try:
        from db import SessionLocal
        from knowledge.reference import procedure_stem_map

        session = SessionLocal()
        try:
            mapping = procedure_stem_map(session)
        finally:
            session.close()
        return mapping or None
    except Exception:
        return None


def _scan_qdrant_number_map() -> dict[str, str]:
    """Dự phòng: quét file_stem phân biệt trong Qdrant, lấy số QTKĐ từ tên tệp.

    Duyệt stem theo thứ tự sắp xếp để kết quả xác định; hai phiên bản cùng số thì
    stem lớn hơn thắng (năm nằm ngay sau số, nên bản mới hơn thắng).
    """
    client = qdrant.get_client()
    stems: set[str] = set()
    offset = None
    while True:
        results, next_offset = client.scroll(
            collection_name=qdrant.collection_name(),
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
    for stem in sorted(stems):
        m = _STEM_NUMBER_RE.search(stem)
        if m:
            mapping[m.group(1)] = stem
    return mapping


def _build_number_to_stem() -> dict[str, str]:
    """Map số QTKĐ → file_stem: bảng ``procedure`` trước, Qdrant khi DB không đọc được."""
    from_db = _load_db_number_map()
    if from_db is not None:
        return from_db
    return _scan_qdrant_number_map()


def _ensure_mapping() -> dict[str, str]:
    global _number_to_stem
    if _number_to_stem is None:
        _number_to_stem = _build_number_to_stem()
    return _number_to_stem


def invalidate() -> None:
    """Bỏ map số và alias đã nạp; lần gọi sau dựng lại từ DB (hoặc Qdrant).

    Ingestion gọi sau khi nhúng hoặc xóa tài liệu, để QTKĐ mới tải lên được ghim
    ngay mà không phải khởi động lại API.
    """
    global _number_to_stem, _device_aliases
    _number_to_stem = None
    _device_aliases = None


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
    for alias, numbers in _ensure_device_aliases().items():
        if alias in q:
            for number in numbers:
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
