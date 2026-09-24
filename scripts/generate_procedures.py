#!/usr/bin/env python
"""Sinh bản ghi ``procedure`` cho các QTKĐ đang có trong sổ tài liệu (spec §5.1).

Mặc định dry-run. Đọc đầu mục Markdown trong ``build/spike_a/``, suy luận loại
thiết bị từ ``device_type`` đã seed (dự phòng bằng ánh xạ số QTKĐ đã biết), rồi
upsert ``procedure`` theo ``number``. Giữ ``document_id`` để truy nguyên P1.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import SessionLocal
from db.models import DeviceType, Document, DocumentType, Procedure
from knowledge.procedure import infer_device_type, parse_edition, parse_procedure_header
from knowledge.reference import device_type_aliases
from knowledge.seed_data import KNOWN_PROCEDURE_DEVICE_TYPES

ROOT = Path(__file__).resolve().parent.parent
MD_DIR = ROOT / "build" / "spike_a"


@dataclass(frozen=True)
class ProcedurePlan:
    number: str
    year: int | None
    title: str
    edition: str | None
    device_type_name: str | None
    document_id: str | None
    action: str  # "create" | "update"


def build_procedure_plan(session, md_dir: Path = MD_DIR) -> list[ProcedurePlan]:
    """Dựng kế hoạch procedure từ sổ tài liệu + Markdown, chưa ghi DB."""
    documents = (
        session.query(Document)
        .filter(Document.doc_type == DocumentType.QTKD)
        .order_by(Document.file_stem)
        .all()
    )
    device_types = session.query(DeviceType).all()
    candidates = [(item.name_vi, device_type_aliases(item)) for item in device_types]
    known_by_name = {item.name_vi for item in device_types}

    plans: list[ProcedurePlan] = []
    for document in documents:
        md_path = md_dir / f"{document.file_stem}.md"
        if not md_path.exists():
            continue
        header = parse_procedure_header(md_path.read_text(encoding="utf-8"))
        if header is None:
            continue
        device_type_name = infer_device_type(header.title, candidates)
        if device_type_name not in known_by_name:
            device_type_name = KNOWN_PROCEDURE_DEVICE_TYPES.get(header.number)
        existing = session.query(Procedure).filter(Procedure.number == header.number).one_or_none()
        plans.append(
            ProcedurePlan(
                number=header.number,
                year=header.year,
                title=header.title,
                edition=parse_edition(document.file_stem),
                device_type_name=device_type_name,
                document_id=document.file_stem,
                action="update" if existing else "create",
            )
        )
    return plans


def apply_procedure_plan(session, plans: list[ProcedurePlan]) -> int:
    """Upsert các procedure trong kế hoạch; trả số dòng đã ghi."""
    device_types = {item.name_vi: item for item in session.query(DeviceType).all()}
    written = 0
    for plan in plans:
        row = session.query(Procedure).filter(Procedure.number == plan.number).one_or_none()
        if row is None:
            row = Procedure(number=plan.number)
            session.add(row)
        row.year = plan.year
        row.title = plan.title
        row.edition = plan.edition
        row.document_id = plan.document_id
        device_type = device_types.get(plan.device_type_name or "")
        row.device_type_id = device_type.id if device_type is not None else None
        written += 1
    session.flush()
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description="Sinh bản ghi procedure cho QTKĐ")
    parser.add_argument("--apply", action="store_true", help="Ghi vào DB (mặc định dry-run)")
    args = parser.parse_args()

    session = SessionLocal()
    try:
        plans = build_procedure_plan(session)
        for plan in plans:
            print(
                f"{'APPLY' if args.apply else 'PLAN'} {plan.number} "
                f"({plan.year}) [{plan.device_type_name}] {plan.title[:60]}"
            )
        if args.apply:
            apply_procedure_plan(session, plans)
            session.commit()
        else:
            session.rollback()
    finally:
        session.close()
    print(f"Tổng: {len(plans)} procedure.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
