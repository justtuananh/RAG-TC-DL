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

from retrieval import doc_profile, doc_scope
from retrieval.normalize import fold
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
# Tài liệu đã nhúng và sẵn sàng nhưng KHÔNG giữ dòng procedure (TCVN, hoặc QTKĐ trùng số với một
# QTKĐ khác nhưng là thiết bị khác). Thiếu tập này, chúng không bao giờ được tìm khi câu hỏi không nêu thiết bị.
_extra_stems: frozenset[str] | None = None
# (file_stem, số hiệu TCVN, từ khoá kiểu thiết bị) rút từ hồ sơ tài liệu, dựng một lần cho mọi tài liệu đã nạp.
_profile_index: tuple[tuple[str, str | None, tuple[str, ...], str], ...] | None = None
_TCVN_DIGITS_RE = re.compile(r"\d{3,5}")
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


def _load_db_extra_stems(mapped: set[str]) -> frozenset[str]:
    """file_stem của tài liệu ``ready`` không nằm trong map số; rỗng nếu không đọc được DB."""
    try:
        from db import SessionLocal
        from db.models import Document, IngestStatus

        session = SessionLocal()
        try:
            rows = session.query(Document.file_stem).filter(
                Document.ingest_status == IngestStatus.READY
            )
            return frozenset(stem for (stem,) in rows if stem not in mapped)
        finally:
            session.close()
    except Exception:
        return frozenset()


def _ensure_extra_stems() -> frozenset[str]:
    global _extra_stems
    if _extra_stems is None:
        _extra_stems = _load_db_extra_stems(set(_ensure_mapping().values()))
    return _extra_stems


def _ensure_profile_index() -> tuple[tuple[str, str | None, tuple[str, ...], str], ...]:
    global _profile_index
    if _profile_index is None:
        entries = []
        for stem in sorted(known_files()):
            profile = doc_profile.profile_for(stem)
            if profile is None:
                continue
            code = profile.code
            digits = None
            if code is not None and code.kind == "TCVN":
                match = _TCVN_DIGITS_RE.search(code.number)
                digits = match.group(0) if match else None
            if digits or profile.keywords or profile.subject:
                entries.append((stem, digits, profile.keywords, profile.subject))
        _profile_index = tuple(_drop_family_names(entries))
    return _profile_index


_FAMILY_NAME_MAX_WORDS = 2


def _drop_family_names(entries: list[tuple[str, str | None, tuple[str, ...], str]]) -> list:
    """Tên đối tượng ngắn ("áp kế" của 1.139 "Áp kế kiểu lò xo ...") mở đầu tên tài liệu khác ("áp kế pittông",
    "áp kế đo chênh lệch áp suất") là tên HỌ thiết bị: khớp nó không đủ để ghim một tài liệu ("áp kế chênh áp
    ПКУ-М" từng bị ghim sang 1.139). Tài liệu vẫn ghim được bằng số QTKĐ, kiểu, hoặc alias."""
    subjects = {subject for *_, subject in entries if subject}

    def is_family(subject: str) -> bool:
        return len(subject.split()) <= _FAMILY_NAME_MAX_WORDS and any(
            other.startswith(subject + " ") for other in subjects
        )

    return [
        (stem, digits, keywords, "" if is_family(subject) else subject)
        for stem, digits, keywords, subject in entries
    ]


def _profile_stems(folded_query: str, raw_query: str) -> tuple[set[str], list[set[str]]]:
    """(mã, các nhóm tên) - tài liệu nêu đích danh bằng mã TCVN/ISO ("TCVN 6165", "ISO/IEC 17025"); và nhóm
    tài liệu nêu bằng kiểu thiết bị ("DPI 610") hoặc tên đối tượng lấy từ tên tài liệu ("lưu lượng kế chất
    lỏng"). Các tài liệu cùng một tên đối tượng ("bàn tạo áp": 1.033 và 1.062) là MỘT nhóm."""
    compact = doc_profile.normalize_keyword(raw_query)
    by_code: set[str] = set()
    by_keyword: list[set[str]] = []
    keyword_subjects: list[str] = []
    by_subject: dict[str, set[str]] = {}
    for stem, digits, keywords, subject in _ensure_profile_index():
        if digits and re.search(rf"\b(?:tcvn|iso)\b[^0-9]{{0,20}}{digits}(?!\d)", folded_query):
            by_code.add(stem)
        elif any(re.search(rf"{re.escape(keyword)}(?!\d)", compact) for keyword in keywords):
            # Dừng ở ranh giới số: kiểu "mp6" (МП-6) không khớp câu hỏi về "MP-600".
            by_keyword.append({stem})
            keyword_subjects.append(subject)
        elif subject and re.search(rf"(?<!\w){re.escape(subject)}(?!\w)", folded_query):
            by_subject.setdefault(subject, set()).add(stem)
    longer = list(by_subject) + [s for s in keyword_subjects if s]
    named = [stems for subject, stems in by_subject.items() if not _extended_by(subject, longer)]
    return by_code, by_keyword + named


def _extended_by(subject: str, others: list[str]) -> bool:
    """Tên họ thiết bị ("áp kế" của 1.139) mà câu hỏi đã nêu dài hơn ("áp kế pittông") hoặc đã ghim kiểu
    cụ thể ("áp kế MP-6" → A_04 "áp kế pittông chuẩn ..."): chỉ là phần đầu của tên kia, không ghim thêm."""
    return any(other != subject and other.startswith(subject + " ") for other in others)


def _stem_number(stem: str) -> str | None:
    match = _STEM_NUMBER_RE.search(stem)
    return match.group(1) if match else None


def _stems_for_number(number: str, folded_query: str, mapping: dict[str, str]) -> set[str]:
    """Các file mang số QTKĐ này: bản giữ dòng procedure cùng tài liệu khác thiết bị trùng số.

    Câu hỏi nêu cả năm ("1.062:2016") thì thu hẹp về file có năm đó; không file nào khớp năm
    thì giữ tất cả thay vì để mất hết.
    """
    candidates = {stem for stem in [mapping.get(number)] if stem}
    candidates |= {stem for stem in _ensure_extra_stems() if _stem_number(stem) == number}
    if not candidates:
        # Bảng procedure không có số này (dòng mã đọc nhầm, vd. 1.141 từng bị ghi 1.137 lấy từ danh sách viện
        # dẫn): tài liệu mang số đó trong tên tệp.
        candidates = {stem for stem in mapping.values() if _stem_number(stem) == number}
    year = re.search(rf"{re.escape(number)}\s*[:/_-]\s*(\d{{4}})", folded_query)
    if year and len(candidates) > 1:
        narrowed = {s for s in candidates if f"_{number}_{year.group(1)}" in fold(s)}
        if narrowed:
            return narrowed
    return candidates


def invalidate() -> None:
    """Bỏ map số và alias đã nạp; lần gọi sau dựng lại từ DB (hoặc Qdrant).

    Ingestion gọi sau khi nhúng hoặc xóa tài liệu, để QTKĐ mới tải lên được ghim
    ngay mà không phải khởi động lại API.
    """
    global _number_to_stem, _device_aliases, _extra_stems, _profile_index
    _number_to_stem = None
    _device_aliases = None
    _extra_stems = None
    _profile_index = None
    doc_scope.invalidate()


def route_files(query: str) -> frozenset[str]:
    """Tập file_stem phân biệt mà query nhắc tới (số QTKĐ tường minh + alias).

    Rỗng = không tín hiệu; 1 phần tử = ghim file; ≥2 = câu so sánh nhiều thiết bị
    → retriever chạy phễu RIÊNG cho từng file (một phễu chung bị cụm từ vựng áp
    đảo — 3 file áp kế píttông — đè bẹp file thiểu số: đo Q115/Q116 top-5 không
    còn chunk 1.061 nào dù query nhắc 'van an toàn').
    """
    mapping = _ensure_mapping()
    q = fold(query)

    by_code, named_groups = _profile_stems(q, query)
    alias_groups = [
        {mapping[n] for n in numbers if n in mapping}
        for alias, numbers in _ensure_device_aliases().items()
        if re.search(r"(?<!\w)" + re.escape(fold(alias)) + r"(?!\w)", q)
    ]
    by_number: set[str] = set()
    for num in _NUMBER_RE.findall(q):
        candidates = _stems_for_number(num, q, mapping)
        by_number |= _narrow_shared_number(candidates, alias_groups + named_groups)
    stems = by_number | by_code
    for group in alias_groups:
        stems |= _unless_confirming(group, by_number)
    if not by_number:
        # Tên lấy từ tên tài liệu ("áp kế pít tông" của 1.071) là tên loại thiết bị, không phải mã: câu đã nêu
        # số QTKĐ ("áp kế pít tông theo QTKĐ 1.159") thì số quyết định, tên không kéo thêm tài liệu khác.
        for group in named_groups:
            stems |= group
    named = frozenset(stems)
    # Mã nêu đích danh thắng mọi phạm vi theo loại câu hỏi. Không thì "thiết bị chuẩn mẫu ..." chỉ tìm trong
    # nhóm tài liệu chuẩn mẫu dù câu nêu tên loại thiết bị của QTKĐ khác.
    if by_number or by_code or not named or not doc_scope.asks_priority(query):
        return named
    return doc_scope.restrict_named(query, named, known_files())


def _narrow_shared_number(by_number: set[str], named_groups: list[set[str]]) -> set[str]:
    """Số QTKĐ dùng chung cho nhiều tài liệu (1.062: bàn tạo áp 2021 và cột đo xăng dầu 2016) mà câu hỏi nêu
    tên thiết bị của MỘT trong số đó ("Điều kiện kiểm định bàn tạo áp QTKĐ 1.062"): giữ tài liệu khớp tên.
    Tên không khớp tài liệu nào mang số đó (câu so sánh với thiết bị khác) thì giữ nguyên."""
    if len(by_number) < 2:
        return by_number
    named = set().union(*named_groups) if named_groups else set()
    return (by_number & named) or by_number


def _unless_confirming(named: set[str], by_number: set[str]) -> set[str]:
    """Tên thiết bị chỉ XÁC NHẬN số QTKĐ đã nêu thì không thêm tài liệu: "bàn tạo áp theo QTKĐ 1.062:2021"
    là đúng 1.062:2021, không kéo thêm 1.033 (cũng là bàn tạo áp). Tên mâu thuẫn số thì vẫn thêm (câu mơ hồ)."""
    return set() if named & by_number else named


def device_aliases() -> dict[str, tuple[str, ...]]:
    """Từ điển thiết bị: alias (chữ thường) → các số QTKĐ (đã nạp từ DB, dự phòng bằng hằng số)."""
    return dict(_ensure_device_aliases())


def known_files() -> frozenset[str]:
    """Mọi file_stem QTKĐ đang được định tuyến (đã nạp), dùng cho truy hồi phủ đủ tài liệu."""
    return frozenset(_ensure_mapping().values()) | _ensure_extra_stems()


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
