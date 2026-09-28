"""Bổ sung ngược trường đầu mục + ``cells`` cho hồ sơ ĐÃ duyệt trước Pha R.

Hồ sơ nạp trước migration 012 chỉ có vài cột; phần còn lại nằm trong
``source_text``. Lệnh này đọc lại tệp gốc bằng đúng bộ đọc và cấu hình Phụ lục A
như lúc nạp, rồi ghi ``record_field`` và ``measurement_point.cells`` cho hồ sơ đó.

Không mở lại vòng duyệt vì không có dữ liệu mới: một giá trị chỉ được ghi khi
nó nằm NGUYÊN VĂN trong ``source_text`` đã duyệt (P1/P3). Giá trị không tìm thấy
bị bỏ và báo lại. Chạy lại an toàn: trường của hồ sơ được ghi đè, ``cells`` chỉ
gán cho điểm đo có cùng ``step_code`` + ``quote``.

    python -m records.backfill            # mọi hồ sơ đã duyệt
    python -m records.backfill --dry-run  # chỉ báo cáo
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.orm import Session

from db.models import CalibrationRecord, Extraction, ExtractionStatus, RecordField
from knowledge import vnnum
from records.ingest import _read_source
from records.store import field_rows
from records.template import TemplateError, derive_mapping_config
from records.types import RecordDraft


@dataclass
class BackfillResult:
    record_id: int
    fields: int = 0
    cells: int = 0
    skipped: list[str] = field(default_factory=list)


def _flatten(text: str) -> str:
    """Nguồn dạng một dòng: bỏ ranh giới ô ``|`` vì một giá trị có thể gộp nhiều ô."""
    return vnnum.normalize_spaces((text or "").replace("|", " "))


def _in_source(value: str, source: str) -> bool:
    return _flatten(value) in source


def _verified_fields(draft: RecordDraft, source: str, result: BackfillResult):
    """Chỉ giữ trường có giá trị nằm nguyên văn trong nguồn đã duyệt."""
    kept = []
    for item in draft.fields:
        if not item.value.strip():
            continue
        if _in_source(item.value, source):
            kept.append(item)
        else:
            result.skipped.append(f"trường {item.label!r}")
    return kept


def _assign_cells(
    record: CalibrationRecord, draft: RecordDraft, source: str, result: BackfillResult
) -> None:
    """Gán ``cells`` cho điểm đo cùng ``step_code`` + ``quote``; ô lạ thì bỏ cả dòng."""
    by_key: dict[tuple[str | None, str], list] = {}
    for point in draft.measurements:
        by_key.setdefault((point.step_code, point.quote or ""), []).append(point)
    for stored in record.points:
        candidates = by_key.get((stored.step_code, stored.quote or ""))
        if not candidates:
            continue
        cells = candidates.pop(0).cells
        if not cells:
            continue
        if all(not cell["text"] or _in_source(cell["text"], source) for cell in cells):
            stored.cells = list(cells)
            result.cells += 1
        else:
            result.skipped.append(f"ô của dòng {stored.step_code} #{stored.ord}")


def backfill_record(
    db: Session, record: CalibrationRecord, source_path: Path, *, dry_run: bool = False
) -> BackfillResult:
    """Bổ sung cho MỘT hồ sơ đã duyệt; không commit."""
    result = BackfillResult(record_id=record.id)
    procedure = record.procedure
    if procedure is None:
        result.skipped.append("hồ sơ không gắn QTKĐ")
        return result
    config = derive_mapping_config(db, procedure_id=procedure.id, procedure_number=procedure.number)
    draft = _read_source(source_path, config)
    source = _flatten(record.source_text or record.extraction.quote or "")

    fields = _verified_fields(draft, source, result)
    rows = field_rows(db, fields, record_id=record.id)
    result.fields = len(rows)
    if dry_run:
        return result
    db.query(RecordField).filter(RecordField.record_id == record.id).delete()
    for row in rows:
        db.add(row)
    _assign_cells(record, draft, source, result)
    return result


def approved_records(db: Session) -> list[CalibrationRecord]:
    return (
        db.query(CalibrationRecord)
        .join(Extraction, Extraction.id == CalibrationRecord.extraction_id)
        .filter(Extraction.status == ExtractionStatus.APPROVED)
        .order_by(CalibrationRecord.id)
        .all()
    )


def main(argv: list[str] | None = None) -> int:
    import ingestion_jobs
    from db import SessionLocal

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    db = SessionLocal()
    try:
        for record in approved_records(db):
            stem = record.document.file_stem if record.document is not None else None
            path = ingestion_jobs.get_source_path(stem) if stem else None
            if path is None:
                print(f"#{record.id}: bỏ qua, không tìm thấy tệp gốc ({stem})")
                continue
            try:
                result = backfill_record(db, record, path, dry_run=args.dry_run)
            except TemplateError as exc:
                print(f"#{record.id}: bỏ qua, {exc}")
                continue
            skipped = f", bỏ {len(result.skipped)}: {result.skipped}" if result.skipped else ""
            print(f"#{record.id} {stem}: {result.fields} trường, {result.cells} dòng ô{skipped}")
        if args.dry_run:
            db.rollback()
        else:
            db.commit()
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
