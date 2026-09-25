"""T9: kiểm tra hành vi supersede khi nạp lại/nạp phiên bản mới (pipeline thật,
không mô phỏng bằng tay — mọi thay đổi trạng thái đều do
``knowledge.extract.extract_and_store``/``extract_appendix_and_store`` tạo ra).
"""

from __future__ import annotations

import hashlib

from db.models import (
    Document,
    DocumentType,
    Extraction,
    ExtractionStatus,
    Procedure,
    ProcedureFact,
)
from knowledge.extract import extract_and_store, extract_appendix_and_store
from review import queue as review


def _make_document(doc_id: str, obj: dict) -> Document:
    return Document(
        id=doc_id,
        file_stem=doc_id,
        display_name=obj["file"],
        ext="DOCX",
        doc_type=DocumentType.QTKD,
        sha256=hashlib.sha256(doc_id.encode()).hexdigest(),
        size_bytes=1,
    )


def test_rule_reextraction_supersedes_old_and_new_is_pending(
    session, corpus_manifest, corpus_markdown
):
    """Trích lại CÙNG tài liệu A01 bằng luật: extraction luật cũ chuyển
    ``superseded``, extraction mới ở trạng thái ``pending``."""
    document = _make_document("A01", corpus_manifest["A01"])
    session.add(document)
    session.flush()
    md_text = corpus_markdown["A01"]

    first_summary = extract_and_store(session, document, md_text)
    session.commit()
    assert first_summary.facts + first_summary.standards + first_summary.terms > 0

    first_ids = {
        row.id
        for row in session.query(Extraction)
        .filter(Extraction.document_id == "A01", Extraction.extractor.like("rule:%"))
        .all()
    }
    assert first_ids
    assert all(
        row.status == ExtractionStatus.PENDING
        for row in session.query(Extraction).filter(Extraction.id.in_(first_ids)).all()
    )

    second_summary = extract_and_store(session, document, md_text)
    session.commit()

    old_rows = session.query(Extraction).filter(Extraction.id.in_(first_ids)).all()
    assert old_rows and all(row.status == ExtractionStatus.SUPERSEDED for row in old_rows)
    assert second_summary.superseded == len(first_ids)

    new_rows = (
        session.query(Extraction)
        .filter(Extraction.document_id == "A01", Extraction.status == ExtractionStatus.PENDING)
        .all()
    )
    assert new_rows
    assert all(row.supersedes_id in first_ids for row in new_rows if row.supersedes_id)


def test_new_version_document_reassigns_procedure(session, corpus_manifest, corpus_markdown):
    """Nạp F02 (QTKĐ 9.001 phiên bản 2) sau A01: ``Procedure`` số "9.001" trỏ tới
    document của F02 (``ensure_procedure`` cập nhật ``document_id`` khi tìm thấy
    procedure trùng số) — hành vi này ĐÚNG bình thường, không phải mã K."""
    a01 = _make_document("A01", corpus_manifest["A01"])
    session.add(a01)
    session.flush()
    extract_and_store(session, a01, corpus_markdown["A01"])
    session.commit()

    f02 = _make_document("F02", corpus_manifest["F02"])
    session.add(f02)
    session.flush()
    extract_and_store(session, f02, corpus_markdown["F02"])
    session.commit()

    procedure = session.query(Procedure).filter(Procedure.number == "9.001").one()
    assert procedure.document_id == "F02"


def test_rule_reextraction_does_not_supersede_llm_or_appendix(
    session, corpus_manifest, corpus_markdown
):
    """K08a: trích lại bằng luật chỉ thay thế extraction ``rule:*`` (trừ
    ``rule:phuluc_a``); LLM và Phụ lục A có vòng đời riêng."""
    document = _make_document("A01", corpus_manifest["A01"])
    session.add(document)
    session.flush()
    md_text = corpus_markdown["A01"]
    extract_and_store(session, document, md_text)
    extract_appendix_and_store(session, document, md_text)
    session.flush()

    # Một extraction LLM giả (vòng đời riêng, không có trong corpus luật).
    llm = Extraction(
        document_id="A01",
        quote="Sai số cho phép ± 3 %",
        extractor="llm:test",
        confidence=0.9,
        status=ExtractionStatus.APPROVED,
    )
    session.add(llm)
    session.flush()
    session.add(
        ProcedureFact(
            extraction_id=llm.id,
            fact_kind="max_permissible_error",
            label="Giới hạn sai số",
            value_text="± 3 %",
        )
    )
    for row in session.query(Extraction).filter(Extraction.document_id == "A01").all():
        row.status = ExtractionStatus.APPROVED
    session.commit()

    rule_ids = {
        row.id
        for row in session.query(Extraction)
        .filter(
            Extraction.document_id == "A01",
            Extraction.extractor.like("rule:%"),
            ~Extraction.extractor.like("rule:phuluc_a%"),
        )
        .all()
    }
    appendix_ids = {
        row.id
        for row in session.query(Extraction)
        .filter(Extraction.document_id == "A01", Extraction.extractor.like("rule:phuluc_a%"))
        .all()
    }
    assert rule_ids and appendix_ids

    extract_and_store(session, document, md_text)
    session.commit()

    assert all(
        session.get(Extraction, rid).status == ExtractionStatus.SUPERSEDED for rid in rule_ids
    )
    assert all(
        session.get(Extraction, rid).status == ExtractionStatus.APPROVED for rid in appendix_ids
    )
    assert session.get(Extraction, llm.id).status == ExtractionStatus.APPROVED


def test_new_version_does_not_supersede_until_approved(session, corpus_manifest, corpus_markdown):
    """K08b (quyết định 2026-09-25): nạp F02 KHÔNG đụng dữ kiện đã duyệt của A01;
    duyệt một dữ kiện của F02 mới thay thế đúng dữ kiện cùng khoá của A01 (ba
    khẳng định của kế hoạch)."""
    a01 = _make_document("A01", corpus_manifest["A01"])
    session.add(a01)
    session.flush()
    extract_and_store(session, a01, corpus_markdown["A01"])
    extract_appendix_and_store(session, a01, corpus_markdown["A01"])
    session.flush()
    a01_extractions = session.query(Extraction).filter(Extraction.document_id == "A01").all()
    for row in a01_extractions:
        row.status = ExtractionStatus.APPROVED
    session.commit()
    approved_ids = {row.id for row in a01_extractions}
    assert approved_ids

    f02 = _make_document("F02", corpus_manifest["F02"])
    session.add(f02)
    session.flush()
    extract_and_store(session, f02, corpus_markdown["F02"])
    session.commit()

    # (1) Nạp F02 không thay thế dữ kiện đã duyệt của A01.
    still_approved = (
        session.query(Extraction)
        .filter(Extraction.id.in_(approved_ids), Extraction.status == ExtractionStatus.APPROVED)
        .count()
    )
    assert still_approved == len(approved_ids), (
        f"nạp F02 đã thay thế {len(approved_ids) - still_approved} dữ kiện của A01 (K08b)"
    )

    f02_new = (
        session.query(Extraction)
        .join(ProcedureFact, ProcedureFact.extraction_id == Extraction.id)
        .filter(
            Extraction.document_id == "F02",
            ProcedureFact.fact_kind == "working_range",
            ProcedureFact.label == "Phạm vi đo",
        )
        .one()
    )
    a01_old = (
        session.query(Extraction)
        .join(ProcedureFact, ProcedureFact.extraction_id == Extraction.id)
        .filter(
            Extraction.document_id == "A01",
            ProcedureFact.fact_kind == "working_range",
            ProcedureFact.label == "Phạm vi đo",
        )
        .one()
    )

    review.approve(session, f02_new.id, actor=None)
    session.commit()
    session.refresh(a01_old)
    session.refresh(f02_new)

    # (2) Đúng dữ kiện cùng khoá của A01 thành superseded + liên kết đúng.
    assert a01_old.status == ExtractionStatus.SUPERSEDED
    assert f02_new.supersedes_id == a01_old.id

    # (3) Các dữ kiện khác của A01 vẫn approved.
    remaining = (
        session.query(Extraction)
        .filter(
            Extraction.id.in_(approved_ids - {a01_old.id}),
            Extraction.status == ExtractionStatus.APPROVED,
        )
        .count()
    )
    assert remaining == len(approved_ids) - 1
