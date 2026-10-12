"""Đọc đầu mục QTKĐ, suy luận loại thiết bị và sinh bản ghi ``procedure``.

Dùng bởi ``scripts/generate_procedures.py`` để sinh bản ghi ``procedure`` cho các
QTKĐ đang có, và bởi ``ingestion.jobs`` sau khi nhúng một tài liệu QTKĐ mới (để
router văn bản luôn có dòng ``procedure``). Các hàm thuần nhận text Markdown +
danh sách ứng viên; ``ensure_procedure`` là điểm ghi DB duy nhất ở đây.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from knowledge.reference import device_type_aliases, normalize_alias
from knowledge.seed_data import KNOWN_PROCEDURE_DEVICE_TYPES

# Dòng mã QTKĐ: "QTKĐ 1.061 : 2021" / "QTKD 1.062 :2021" (K11: nhận cả không dấu Đ).
_HEADER_RE = re.compile(
    r"QTK[ĐD]\s*([0-9]+(?:\.[0-9]+)?)\s*[:\-]?\s*(\d{4})",
    re.IGNORECASE,
)
_STOP_RE = re.compile(r"^(QUY TRÌNH KIỂM ĐỊNH|HÀ NỘI|HỒ CHÍ MINH)\b", re.IGNORECASE)
_STEM_RE = re.compile(r"QTKD[_\s]*([0-9.]+)[_\s]+(\d{4})[_\s]+(.+)$", re.IGNORECASE)


@dataclass(frozen=True)
class ProcedureHeader:
    """Đầu mục một QTKĐ rút từ Markdown."""

    number: str
    year: int | None
    title: str
    edition: str | None = None


def parse_procedure_header(text: str) -> ProcedureHeader | None:
    """Rút số, năm và tiêu đề QTKĐ từ Markdown; ``None`` nếu không thấy mã."""
    lines = [line.strip() for line in (text or "").splitlines()]
    number: str | None = None
    year: int | None = None
    index = -1
    for i, line in enumerate(lines):
        match = _HEADER_RE.search(line)
        if match:
            number, year = match.group(1), int(match.group(2))
            index = i
            break
    if number is None:
        return None

    title_lines: list[str] = []
    for line in lines[index + 1 :]:
        if not line:
            continue
        if _STOP_RE.match(line):
            break
        title_lines.append(line)
    title = " ".join(title_lines).strip()
    return ProcedureHeader(number=number, year=year, title=title)


def parse_edition(stem: str) -> str | None:
    """Rút phần phiên bản sau năm từ file_stem, ví dụ ``ND_V2`` hay ``FINAL``."""
    match = _STEM_RE.search(stem or "")
    if not match:
        return None
    edition = match.group(3).strip(" _")
    return edition or None


def infer_device_type(title: str, candidates) -> str | None:
    """Khớp tiêu đề với tên/alias loại thiết bị, chọn khớp dài nhất.

    ``candidates`` là iterable ``(key, aliases)``; trả ``key`` khớp tốt nhất.
    Khớp dài nhất giúp ưu tiên alias đặc thù (``h3000``) hơn tên chung.
    """
    normalized_title = normalize_alias(title)
    best: str | None = None
    best_length = 0
    for key, aliases in candidates:
        for alias in aliases:
            normalized = normalize_alias(alias)
            if normalized and normalized in normalized_title and len(normalized) > best_length:
                best, best_length = key, len(normalized)
    return best


def newer_version_document_id(session, document, header: ProcedureHeader) -> str | None:
    """``document_id`` của phiên bản MỚI HƠN đang giữ số QTKĐ này, nếu có.

    Mỗi số QTKĐ chỉ có một dòng ``procedure`` trỏ tới phiên bản hiện hành. Tài
    liệu có năm ban hành nhỏ hơn năm của bản đang giữ là bản cũ; cùng năm hoặc
    thiếu năm thì bản xử lý sau thắng (phiên bản sửa đổi trong năm).
    """
    from db.models import Procedure

    current = session.query(Procedure).filter(Procedure.number == header.number).one_or_none()
    if current is None or current.document_id in (None, document.id):
        return None
    if current.year is not None and header.year is not None and current.year > header.year:
        return current.document_id
    return None


def ensure_procedure(session, document, text: str):
    """Tìm procedure của tài liệu; tạo mới từ đầu mục Markdown nếu chưa có.

    Giữ ``procedure.document_id`` để truy nguyên P1. Trả ``None`` nếu văn bản
    không có mã QTKĐ - khi đó router văn bản không ghim được file, nhưng tài liệu
    vẫn được nhúng bình thường - hoặc nếu tài liệu là phiên bản cũ hơn bản đang
    giữ số QTKĐ (dòng procedure giữ nguyên, trỏ bản mới).
    """
    from db.models import DeviceType, Procedure

    procedure = session.query(Procedure).filter(Procedure.document_id == document.id).one_or_none()
    if procedure is not None:
        return procedure

    header = parse_procedure_header(text)
    if header is None:
        return None
    if newer_version_document_id(session, document, header) is not None:
        return None

    procedure = session.query(Procedure).filter(Procedure.number == header.number).one_or_none()
    if procedure is None:
        procedure = Procedure(number=header.number)
        session.add(procedure)
    procedure.year = header.year
    procedure.title = header.title
    procedure.document_id = document.id
    procedure.edition = parse_edition(document.file_stem)

    candidates = [
        (item.name_vi, device_type_aliases(item)) for item in session.query(DeviceType).all()
    ]
    device_type_name = infer_device_type(header.title, candidates)
    if device_type_name is None:
        device_type_name = KNOWN_PROCEDURE_DEVICE_TYPES.get(header.number)
    device_type = (
        session.query(DeviceType).filter(DeviceType.name_vi == device_type_name).one_or_none()
        if device_type_name
        else None
    )
    procedure.device_type_id = device_type.id if device_type is not None else None
    session.flush()
    return procedure
