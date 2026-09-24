"""Trích xuất §6 cho QTKĐ đang có trong sổ tài liệu — chạy theo lô ngoài giờ.

Spec §9 Sprint 5: §6 là tác vụ nạp (không tương tác), nên chạy trên model lớn hơn
theo lô ngoài giờ. Script này là đường batch đó: đọc QTKĐ trong DB, chạy
``knowledge.llm_extract`` + ghi ``pending`` như đường ingestion.

Mặc định DRY-RUN: chỉ chạy LLM + xác minh và in tổng kết, KHÔNG ghi DB. Thêm
``--apply`` để ghi (mọi dòng vẫn ``pending`` — P3 chỉ lộ dữ liệu đã duyệt).

Usage:
  python scripts/extract_section6.py                 # dry-run toàn bộ QTKĐ
  python scripts/extract_section6.py --apply         # ghi pending
  python scripts/extract_section6.py --file-stem X --apply
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from db import SessionLocal
from db.models import Document, DocumentType, Procedure
from knowledge import llm_extract
from knowledge.extract import extract_section6_and_store

OUT_DIR = Path("build/spike_a")


def _iter_qtkd(session, file_stem: str | None):
    query = session.query(Document).filter(Document.doc_type == DocumentType.QTKD)
    if file_stem:
        query = query.filter(Document.file_stem == file_stem)
    return query.order_by(Document.file_stem).all()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Trích xuất §6 bằng LLM cho QTKĐ")
    parser.add_argument(
        "--apply", action="store_true", help="Ghi extraction pending (mặc định dry-run)"
    )
    parser.add_argument("--file-stem", help="Chỉ chạy một tài liệu")
    args = parser.parse_args(argv)

    client = llm_extract.default_client()
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
                summary = extract_section6_and_store(
                    session, document, text, procedure=procedure, client=client
                )
                session.commit()
                print(f"[ghi] {document.file_stem}: {summary.facts} dòng pending")
                total += summary.facts
            else:
                result = llm_extract.extract_section6(text, client)
                status = result.error or "ok"
                print(
                    f"[dry-run] {document.file_stem}: chấp nhận {len(result.facts)}, "
                    f"loại {len(result.rejected)}, lỗi={status}"
                )
                total += len(result.facts)
    finally:
        session.close()
    print(f"Tổng dữ kiện §6: {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
