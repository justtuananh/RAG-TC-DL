"""Trích xuất Phụ lục A cho QTKĐ đang có — sinh cấu hình đọc hồ sơ.

Spec §7: Phụ lục A là mẫu biên bản. Luật ``rule:phuluc_a`` rút trường đầu mục và
bảng kết quả thành dữ kiện ``appendix_field``; người duyệt xác nhận một lần cho
mỗi QTKĐ, rồi ``records.template`` mới dựng cấu hình đọc hồ sơ (chỉ đọc bản đã
duyệt — P3).

Mặc định DRY-RUN: chỉ chạy luật và in tổng kết. Thêm ``--apply`` để ghi ``pending``.

Usage:
  python scripts/extract_appendix.py                 # dry-run toàn bộ QTKĐ
  python scripts/extract_appendix.py --apply         # ghi pending
  python scripts/extract_appendix.py --file-stem X --apply
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from db import SessionLocal
from db.models import Document, DocumentType, Procedure
from knowledge.extract import extract_appendix_and_store
from knowledge.rules import extract_appendix

OUT_DIR = Path("build/spike_a")


def _iter_qtkd(session, file_stem: str | None):
    query = session.query(Document).filter(Document.doc_type == DocumentType.QTKD)
    if file_stem:
        query = query.filter(Document.file_stem == file_stem)
    return query.order_by(Document.file_stem).all()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Trích xuất Phụ lục A cho QTKĐ")
    parser.add_argument(
        "--apply", action="store_true", help="Ghi extraction pending (mặc định dry-run)"
    )
    parser.add_argument("--file-stem", help="Chỉ chạy một tài liệu")
    args = parser.parse_args(argv)

    session = SessionLocal()
    total = 0
    try:
        for document in _iter_qtkd(session, args.file_stem):
            md_path = OUT_DIR / f"{document.file_stem}.md"
            if not md_path.exists():
                print(f"[bỏ qua] {document.file_stem}: chưa có Markdown")
                continue
            text = md_path.read_text(encoding="utf-8")
            if args.apply:
                procedure = (
                    session.query(Procedure)
                    .filter(Procedure.document_id == document.id)
                    .one_or_none()
                )
                summary = extract_appendix_and_store(session, document, text, procedure=procedure)
                session.commit()
                print(f"[ghi] {document.file_stem}: {summary.facts} dòng pending")
                total += summary.facts
            else:
                hits = extract_appendix(text)
                print(f"[dry-run] {document.file_stem}: {len(hits)} trường Phụ lục A")
                total += len(hits)
    finally:
        session.close()
    print(f"Tổng trường Phụ lục A: {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
