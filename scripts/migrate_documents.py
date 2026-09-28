#!/usr/bin/env python
"""Import existing TC_DL/ sources into the document ledger.

The default mode is dry-run. Use --apply after reviewing the proposed rows.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import SessionLocal
from db.models import Document, DocumentType, IngestStatus
from ingestion.classify import classify_document

ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = ROOT / "TC_DL"
OUT_DIR = ROOT / "build" / "spike_a"


def _safe(value: str) -> str:
    """Sanitize a filename stem exactly like ``ingestion.spike_a._safe``.

    Bản sao này phải khớp TỪNG KÝ TỰ: chữ có dấu tiếng Việt (``isalnum()`` là
    True) được GIỮ nguyên, chỉ ký tự khác mới thành ``_``. Lệch chuẩn hoá sẽ tạo
    file_stem khác ingestion, khiến ``ingestion_jobs._find_source`` không tìm ra
    tệp gốc và sinh dòng tài liệu trùng.
    """
    return "".join(c if c.isalnum() or c in "-._" else "_" for c in value)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def iter_sources():
    for path in sorted(SOURCE_DIR.glob("*")):
        if path.suffix.lower() in {".docx", ".doc", ".pdf", ".xlsx", ".xls"}:
            yield path


def migrate(apply: bool) -> int:
    db = SessionLocal()
    changed = 0
    try:
        for path in iter_sources():
            stem = _safe(path.stem)
            digest = _sha256(path)
            existing = db.query(Document).filter(Document.file_stem == stem).one_or_none()
            classification = classify_document(path)
            md_exists = (OUT_DIR / f"{stem}.md").exists()

            # Đã có dòng và nội dung không đổi: chỉ cập nhật lại doc_type khi phân
            # loại mới khác (ví dụ .xls NAS trước đây xếp "khac"), KHÔNG xóa dòng.
            if existing and existing.sha256 == digest:
                if existing.doc_type.value == classification.doc_type:
                    print(f"SKIP {path.name}: already imported")
                    continue
                existing.doc_type = DocumentType(classification.doc_type)
                db.add(existing)
                changed += 1
                print(
                    f"{'APPLY' if apply else 'PLAN'} {path.name} -> "
                    f"{classification.doc_type} (cập nhật loại)"
                )
                continue

            row = existing or Document(id=stem, file_stem=stem)
            row.display_name = path.name
            row.ext = path.suffix[1:].upper()
            row.doc_type = DocumentType(classification.doc_type)
            row.sha256 = digest
            row.size_bytes = path.stat().st_size
            row.ingest_status = IngestStatus.READY if md_exists else IngestStatus.PENDING
            row.ingest_error = None
            db.add(row)
            changed += 1
            print(f"{'APPLY' if apply else 'PLAN'} {path.name} -> {classification.doc_type}")
        if apply:
            db.commit()
        else:
            db.rollback()
    finally:
        db.close()
    return changed


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    raise SystemExit(0 if migrate(args.apply) >= 0 else 1)
