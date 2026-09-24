"""Nối bộ đọc hồ sơ vào sổ cái: chọn QTKĐ → dựng cấu hình → đọc → ghi pending.

Đây là điểm vào cho tài liệu ``ho_so_kiem_dinh`` (biên bản Word) và ``phieu_do``
(phiếu đo Excel). QTKĐ áp dụng được nhận diện từ chính hồ sơ (ví dụ dòng
"Phương pháp kiểm định: QTKĐ 1.061 : 2021"), rồi cấu hình ánh xạ trường được
dựng từ Phụ lục A đã duyệt của QTKĐ đó. Không có cấu hình → không ghi gì.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

from lxml import etree
from sqlalchemy.orm import Session

from db.models import Document, Procedure
from records.docx_reader import _iter_blocks, read_docx
from records.store import StoreResult, store_record_draft
from records.template import TemplateError, derive_mapping_config
from records.xlsx_reader import _read_grid, read_xlsx

# Mã QTKĐ dạng "1.061" xuất hiện trong hồ sơ.
_PROCEDURE_RE = re.compile(r"\b(\d{1,4}\.\d{2,3})\b")
SUPPORTED_SUFFIXES = (".docx", ".xlsx")


class IngestError(ValueError):
    """Không nạp được hồ sơ (thiếu QTKĐ, thiếu cấu hình, định dạng lạ)."""


def detect_procedure_number(text: str | None) -> str | None:
    """Tìm mã QTKĐ trong văn bản hồ sơ; ``None`` nếu không thấy."""
    if not text:
        return None
    match = _PROCEDURE_RE.search(text)
    return match.group(1) if match else None


def find_procedure_for_record(
    db: Session, *, document: Document | None = None, text: str | None = None
) -> Procedure | None:
    """Tìm QTKĐ áp dụng: ưu tiên liên kết tài liệu, rồi mã trong văn bản."""
    if document is not None:
        procedure = (
            db.query(Procedure)
            .filter(Procedure.document_id == document.id)
            .one_or_none()
        )
        if procedure is not None:
            return procedure
    number = detect_procedure_number(text)
    if number:
        return db.query(Procedure).filter(Procedure.number == number).one_or_none()
    return None


def _read_source(path: Path, config):
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return read_docx(path, config)
    if suffix == ".xlsx":
        return read_xlsx(path, config)
    raise IngestError(f"Định dạng hồ sơ không được hỗ trợ: {suffix or '(không rõ)'}.")


def ingest_record_path(
    db: Session,
    *,
    document: Document,
    source_path: str | Path,
    procedure: Procedure | None = None,
    supersede: bool = True,
) -> StoreResult:
    """Đọc một tệp hồ sơ và ghi ``pending``; ném lỗi nghiệp vụ nếu thiếu cấu hình."""
    path = Path(source_path)
    if not path.exists():
        raise IngestError(f"Không tìm thấy tệp hồ sơ: {path}.")

    if procedure is None:
        # Đọc sơ bộ văn bản thô để tìm mã QTKĐ trước khi cần cấu hình.
        text = _peek_text(path)
        procedure = find_procedure_for_record(db, document=document, text=text)
    if procedure is None:
        raise IngestError(
            "Không xác định được QTKĐ áp dụng cho hồ sơ; hãy chỉ định procedure_id."
        )

    try:
        config = derive_mapping_config(
            db, procedure_id=procedure.id, procedure_number=procedure.number
        )
    except TemplateError as exc:
        raise IngestError(str(exc)) from exc

    draft = _read_source(path, config)
    return store_record_draft(
        db, document=document, draft=draft, procedure=procedure, supersede=supersede
    )


def _peek_text(path: Path) -> str:
    """Trích nhanh văn bản thô từ tệp để nhận diện mã QTKĐ (không cần cấu hình)."""
    try:
        if path.suffix.lower() == ".docx":
            with zipfile.ZipFile(path) as archive:
                root = etree.fromstring(archive.read("word/document.xml"))
            parts: list[str] = []
            for kind, payload in _iter_blocks(root):
                if kind == "p":
                    parts.append(str(payload))
                else:
                    parts.extend(" ".join(row) for row in payload)  # type: ignore[arg-type]
            return "\n".join(parts)
        if path.suffix.lower() == ".xlsx":
            return "\n".join(
                " ".join(cell for cell in row if cell) for row in _read_grid(path)
            )
    except Exception:  # noqa: BLE001 - nhận diện là best-effort; lỗi đọc sẽ nổi ở bước sau
        return ""
    return ""


def ingest_file_stem(
    file_stem: str, *, procedure_id: int | None = None, supersede: bool = True
) -> StoreResult:
    """Điểm vào cho API/script: nạp hồ sơ theo ``file_stem`` trong sổ tài liệu."""
    import ingestion_jobs
    from db import SessionLocal
    from db.models import Procedure as ProcedureModel

    source_path = ingestion_jobs.get_source_path(file_stem)
    if source_path is None:
        raise IngestError(f"Không tìm thấy tệp gốc của tài liệu {file_stem}.")

    db = SessionLocal()
    try:
        document = db.query(Document).filter(Document.file_stem == file_stem).one_or_none()
        if document is None:
            raise IngestError(f"Không tìm thấy tài liệu {file_stem} trong sổ.")
        procedure = None
        if procedure_id is not None:
            procedure = db.get(ProcedureModel, procedure_id)
            if procedure is None:
                raise IngestError(f"Không tìm thấy QTKĐ {procedure_id}.")
        result = ingest_record_path(
            db,
            document=document,
            source_path=source_path,
            procedure=procedure,
            supersede=supersede,
        )
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
