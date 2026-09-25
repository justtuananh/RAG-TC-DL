"""Hàng đợi duyệt: lọc, duyệt/từ chối/sửa, duyệt hàng loạt, audit, P1 (Sprint 6).

Chạy thuần trên SQLite in-memory: dựng extraction + dòng dữ kiện trực tiếp, gọi
``review.queue`` không qua FastAPI. Kiểm tra cả bất biến P1 (nguyên văn bất động
khi sửa giá trị) và P3 (view đã duyệt chỉ lộ sau khi duyệt).
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from auth.security import hash_password
from db.models import (
    AppUser,
    AuditLog,
    Base,
    Document,
    DocumentType,
    Extraction,
    ExtractionStatus,
    Procedure,
    ProcedureFact,
    ProcedureStandard,
    Term,
    UserRole,
)
from db.views import create_approved_views
from review import queue as review

STEM = "QTKD_1.061_2021_ND_V2"
OTHER_STEM = "QTKD_1.062_2021_ND_V2"


@pytest.fixture
def engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        create_approved_views(connection)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def session(engine):
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = factory()
    db.add_all(
        [
            Document(
                id=STEM,
                file_stem=STEM,
                display_name=f"{STEM}.docx",
                ext="DOCX",
                doc_type=DocumentType.QTKD,
                sha256="0" * 64,
                size_bytes=1,
            ),
            Document(
                id=OTHER_STEM,
                file_stem=OTHER_STEM,
                display_name=f"{OTHER_STEM}.docx",
                ext="DOCX",
                doc_type=DocumentType.QTKD,
                sha256="1" * 64,
                size_bytes=1,
            ),
        ]
    )
    db.commit()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def approver(session):
    user = AppUser(
        username="duyet",
        full_name="Người duyệt",
        password_hash=hash_password("x"),
        role=UserRole.APPROVER,
        is_active=1,
    )
    session.add(user)
    session.commit()
    return user


def _add_fact(
    session,
    *,
    extractor="rule:bang2.v1",
    section_path="4 Phương tiện kiểm định",
    fact_kind="working_range",
    confidence=0.9,
    document_id=STEM,
    quote="Phạm vi đo đến 1 400 bar",
    value_text="đến 1 400 bar",
    value_min=None,
    value_max=1400 * 100_000,
    char_start=10,
    char_end=33,
    procedure_id=None,
):
    extraction = Extraction(
        document_id=document_id,
        section_path=section_path,
        chunk_id="chunk-1",
        quote=quote,
        char_start=char_start,
        char_end=char_end,
        extractor=extractor,
        extractor_version="v1",
        confidence=confidence,
        status=ExtractionStatus.PENDING,
    )
    session.add(extraction)
    session.flush()
    session.add(
        ProcedureFact(
            extraction_id=extraction.id,
            procedure_id=procedure_id,
            fact_kind=fact_kind,
            label="Phạm vi đo",
            rel_op="range",
            value_min=value_min,
            value_max=value_max,
            value_text=value_text,
        )
    )
    session.commit()
    return extraction.id


def _add_standard(session, *, extractor="rule:bang2.v1", confidence=0.8):
    extraction = Extraction(
        document_id=STEM,
        section_path="4 Phương tiện kiểm định",
        quote="Bàn tạo áp",
        extractor=extractor,
        extractor_version="v1",
        confidence=confidence,
        status=ExtractionStatus.PENDING,
    )
    session.add(extraction)
    session.flush()
    session.add(
        ProcedureStandard(
            extraction_id=extraction.id,
            ord=1,
            name_vi="Bàn tạo áp",
            range_text="0 đến 1 400 bar",
        )
    )
    session.commit()
    return extraction.id


def _add_term(session, *, extractor="rule:thuatngu.v1", confidence=0.85):
    extraction = Extraction(
        document_id=STEM,
        section_path="2 Thuật ngữ và định nghĩa",
        quote="Độ chênh áp: là hiệu áp suất",
        extractor=extractor,
        extractor_version="v1",
        confidence=confidence,
        status=ExtractionStatus.PENDING,
    )
    session.add(extraction)
    session.flush()
    session.add(
        Term(
            extraction_id=extraction.id,
            term_vi="Độ chênh áp",
            term_en="differential pressure",
            definition="là hiệu áp suất",
        )
    )
    session.commit()
    return extraction.id


# ── Liệt kê + lọc ─────────────────────────────────────────────────────────────


def test_list_queue_defaults_to_pending_sorted_by_confidence(session):
    _add_fact(session, confidence=0.95)
    _add_fact(session, confidence=0.6, fact_kind="env_condition")
    items, total = review.list_queue(session)

    assert total == 2
    assert [item["confidence"] for item in items] == [0.6, 0.95]
    assert all(item["status"] == "pending" for item in items)


def test_list_queue_filters_document_fact_kind_and_confidence(session):
    _add_fact(session, confidence=0.95)
    _add_fact(session, confidence=0.6, fact_kind="env_condition")
    _add_fact(session, document_id=OTHER_STEM, confidence=0.9)
    _add_standard(session)

    by_doc, _ = review.list_queue(session, document_id=OTHER_STEM)
    assert {item["document_id"] for item in by_doc} == {OTHER_STEM}

    by_kind, total_kind = review.list_queue(session, fact_kind="env_condition")
    assert total_kind == 1
    assert by_kind[0]["data"]["fact_kind"] == "env_condition"

    by_conf, total_conf = review.list_queue(session, max_confidence=0.7)
    assert total_conf == 1
    assert by_conf[0]["confidence"] == pytest.approx(0.6)


def test_list_queue_fact_kind_does_not_duplicate_multi_fact_extraction(session):
    extraction_id = _add_fact(
        session, fact_kind="max_permissible_error", confidence=0.8, value_text="3%"
    )
    # Dòng thứ hai cùng extraction + cùng fact_kind (giá trị sàn, spec §5.4).
    session.add(
        ProcedureFact(
            extraction_id=extraction_id,
            fact_kind="max_permissible_error",
            label="Giá trị sàn",
            value_text="0,15 bar",
        )
    )
    session.commit()

    items, total = review.list_queue(session, fact_kind="max_permissible_error")
    assert total == 1
    assert [item["id"] for item in items] == [extraction_id]


def test_list_queue_extractor_filter_and_pagination(session):
    _add_fact(session, extractor="rule:bang2.v1", confidence=0.9)
    _add_fact(session, extractor="rule:phamvi.v1", confidence=0.5)
    _add_fact(session, extractor="rule:phamvi.v1", confidence=0.4)

    items, total = review.list_queue(session, extractor="rule:phamvi.v1")
    assert total == 2
    assert {item["extractor"] for item in items} == {"rule:phamvi.v1"}

    page, _ = review.list_queue(session, extractor="rule:phamvi.v1", limit=1, offset=0)
    assert len(page) == 1 and page[0]["confidence"] == pytest.approx(0.4)


def test_get_extraction_returns_source_and_404(session, monkeypatch):
    import ingestion_jobs

    extraction_id = _add_fact(session, char_start=5, char_end=18, quote="đến 1 400 bar")
    monkeypatch.setattr(
        ingestion_jobs,
        "get_markdown",
        lambda stem: "# 1 Phạm vi\n\nđến 1 400 bar trong đó\n",
    )

    item = review.get_extraction(session, extraction_id)
    assert item["source"]["quote"] == "đến 1 400 bar"
    assert item["source"]["section_text"] is not None

    with pytest.raises(review.NotFoundError):
        review.get_extraction(session, 999999)


# ── Duyệt / từ chối ───────────────────────────────────────────────────────────


def test_approve_sets_reviewer_and_writes_audit(session, approver):
    extraction_id = _add_fact(session)
    item = review.approve(session, extraction_id, approver, note="ok")

    assert item["status"] == "approved"
    assert item["reviewed_by"] == approver.id
    assert item["reviewed_at"] is not None

    log = session.query(AuditLog).one()
    assert log.action == "approve"
    assert log.entity_type == "extraction"
    assert log.entity_id == str(extraction_id)
    assert log.actor_id == approver.id
    assert log.before == {"status": "pending"}
    assert log.after["status"] == "approved"


def test_approve_twice_conflicts(session, approver):
    extraction_id = _add_fact(session)
    review.approve(session, extraction_id, approver)
    with pytest.raises(review.ConflictError):
        review.approve(session, extraction_id, approver)


def test_reject_requires_reason_and_records_it(session, approver):
    extraction_id = _add_fact(session)
    with pytest.raises(review.ValidationError):
        review.reject(session, extraction_id, approver, "   ")

    item = review.reject(session, extraction_id, approver, "Sai đơn vị")
    assert item["status"] == "rejected"
    assert item["review_note"] == "Sai đơn vị"

    log = session.query(AuditLog).one()
    assert log.action == "reject"
    assert log.after == {"status": "rejected", "reason": "Sai đơn vị"}


def test_reject_removes_from_approved_view(session, approver):
    approved = _add_fact(session)
    rejected = _add_fact(session, confidence=0.5)
    assert _view_count(session, "v_procedure_fact") == 0
    review.approve(session, approved, approver)
    assert _view_count(session, "v_procedure_fact") == 1
    review.reject(session, rejected, approver, "sai")
    assert _view_count(session, "v_procedure_fact") == 1
    assert session.get(Extraction, rejected).status == ExtractionStatus.REJECTED


# ── K08b: thay thế dữ kiện khi duyệt phiên bản mới của QTKĐ ──────────────────


def _procedure(session, *, number="1.061", document_id=STEM):
    procedure = Procedure(number=number, document_id=document_id)
    session.add(procedure)
    session.commit()
    return procedure


def test_approve_supersedes_approved_counterpart_in_other_document(session, approver):
    """Duyệt bản mới của QTKĐ thì bản đã duyệt của tài liệu cũ cùng khoá chuyển
    ``superseded``, bản mới trỏ ``supersedes_id`` và có audit."""
    procedure = _procedure(session)
    old_id = _add_fact(
        session, document_id=OTHER_STEM, procedure_id=procedure.id, value_text="đến 1 400 bar"
    )
    review.approve(session, old_id, approver)

    new_id = _add_fact(
        session, document_id=STEM, procedure_id=procedure.id, value_text="đến 1 600 bar"
    )
    review.approve(session, new_id, approver)

    assert session.get(Extraction, old_id).status == ExtractionStatus.SUPERSEDED
    assert session.get(Extraction, new_id).supersedes_id == old_id
    log = (
        session.query(AuditLog)
        .filter(AuditLog.action == "supersede", AuditLog.entity_id == str(old_id))
        .one()
    )
    assert log.after["status"] == "superseded"
    assert log.after["superseded_by"] == new_id


def test_approve_keeps_counterparts_without_match(session, approver):
    """Bản cũ không có đối ứng (khác khoá) vẫn giữ ``approved``."""
    procedure = _procedure(session)
    matching = _add_fact(session, document_id=OTHER_STEM, procedure_id=procedure.id)
    other_kind = _add_fact(
        session,
        document_id=OTHER_STEM,
        procedure_id=procedure.id,
        fact_kind="calibration_interval",
        confidence=0.5,
    )
    review.approve(session, matching, approver)
    review.approve(session, other_kind, approver)

    new_id = _add_fact(session, document_id=STEM, procedure_id=procedure.id)
    review.approve(session, new_id, approver)

    assert session.get(Extraction, matching).status == ExtractionStatus.SUPERSEDED
    assert session.get(Extraction, other_kind).status == ExtractionStatus.APPROVED


def test_approving_fact_of_old_document_does_not_supersede_current(session, approver):
    """Chỉ extraction thuộc tài liệu HIỆN HÀNH của QTKĐ mới kích hoạt thay thế."""
    procedure = _procedure(session)  # tài liệu hiện hành = STEM
    current = _add_fact(session, document_id=STEM, procedure_id=procedure.id)
    review.approve(session, current, approver)

    old = _add_fact(
        session, document_id=OTHER_STEM, procedure_id=procedure.id, value_text="đến 1 400 bar"
    )
    review.approve(session, old, approver)

    assert session.get(Extraction, current).status == ExtractionStatus.APPROVED
    assert session.get(Extraction, old).status == ExtractionStatus.APPROVED


def test_edit_and_approve_supersedes_counterpart(session, approver):
    """Đường "sửa giá trị rồi duyệt" cũng thay thế bản cũ cùng khoá."""
    procedure = _procedure(session)
    old = _add_fact(session, document_id=OTHER_STEM, procedure_id=procedure.id)
    review.approve(session, old, approver)

    new = _add_fact(session, document_id=STEM, procedure_id=procedure.id)
    review.edit_and_approve(session, new, approver, {"value_text": "đến 1 700 bar"})

    assert session.get(Extraction, old).status == ExtractionStatus.SUPERSEDED
    assert session.get(Extraction, new).supersedes_id == old


def test_bulk_approve_supersedes_counterpart(session, approver):
    """Duyệt hàng loạt theo luật cũng thay thế bản cũ cùng khoá."""
    procedure = _procedure(session)
    old = _add_fact(
        session,
        document_id=OTHER_STEM,
        procedure_id=procedure.id,
        extractor="rule:phamvi.v1",
    )
    review.approve(session, old, approver)

    new = _add_fact(
        session, document_id=STEM, procedure_id=procedure.id, extractor="rule:phamvi.v1"
    )
    review.bulk_approve(session, approver, extractor="rule:phamvi.v1", document_id=STEM)

    assert session.get(Extraction, old).status == ExtractionStatus.SUPERSEDED
    assert session.get(Extraction, new).supersedes_id == old


def test_approved_view_returns_single_version_per_key(session, approver):
    """P3: sau khi duyệt bản mới, view đã duyệt chỉ còn MỘT bản cho mỗi khoá."""
    procedure = _procedure(session)
    old = _add_fact(
        session, document_id=OTHER_STEM, procedure_id=procedure.id, value_text="đến 1 400 bar"
    )
    review.approve(session, old, approver)
    new = _add_fact(
        session, document_id=STEM, procedure_id=procedure.id, value_text="đến 1 600 bar"
    )
    review.approve(session, new, approver)

    rows = session.execute(
        text(
            "SELECT extraction_id, value_text FROM v_procedure_fact WHERE fact_kind = 'working_range'"
        )
    ).all()
    assert rows == [(new, "đến 1 600 bar")]


# ── Sửa giá trị rồi duyệt (P1) ────────────────────────────────────────────────


def test_edit_and_approve_changes_value_but_preserves_quote(session, approver):
    extraction_id = _add_fact(
        session,
        quote="đến 1 400 bar",
        char_start=100,
        char_end=113,
        value_text="đến 1 400 bar",
        value_max=1400 * 100_000,
    )
    original = session.get(Extraction, extraction_id)
    original_quote = original.quote
    original_start, original_end = original.char_start, original.char_end

    item = review.edit_and_approve(
        session,
        extraction_id,
        approver,
        {"value_text": "đến 1 600 bar", "value_max": 1600 * 100_000},
        note="sửa theo nguồn",
    )

    assert item["status"] == "approved"
    assert item["data"]["value_text"] == "đến 1 600 bar"
    assert item["data"]["value_max"] == pytest.approx(1600 * 100_000)

    refreshed = session.get(Extraction, extraction_id)
    assert refreshed.quote == original_quote  # P1: nguyên văn bất động
    assert (refreshed.char_start, refreshed.char_end) == (original_start, original_end)

    log = session.query(AuditLog).one()
    assert log.action == "edit_approve"
    assert log.before["data"]["value_text"] == "đến 1 400 bar"
    assert log.after["data"]["value_text"] == "đến 1 600 bar"


def test_edit_and_approve_rejects_unknown_field(session, approver):
    extraction_id = _add_fact(session)
    with pytest.raises(review.ValidationError):
        review.edit_and_approve(session, extraction_id, approver, {"quote": "đổi trái phép"})
    assert session.get(Extraction, extraction_id).status == ExtractionStatus.PENDING


def test_edit_and_approve_requires_a_change(session, approver):
    extraction_id = _add_fact(session)
    with pytest.raises(review.ValidationError):
        review.edit_and_approve(session, extraction_id, approver, {})


# ── Duyệt hàng loạt theo luật ─────────────────────────────────────────────────


def test_bulk_approve_only_same_rule_pending(session, approver):
    same_a = _add_fact(session, extractor="rule:bang2.v1", confidence=0.9)
    same_b = _add_fact(
        session, extractor="rule:bang2.v1", confidence=0.7, fact_kind="env_condition"
    )
    same_std = _add_standard(session, extractor="rule:bang2.v1")
    other = _add_fact(session, extractor="rule:phamvi.v1", confidence=0.5)
    already = _add_fact(session, extractor="rule:bang2.v1", confidence=0.8)
    review.approve(session, already, approver)

    result = review.bulk_approve(session, approver, extractor="rule:bang2.v1")
    assert result["approved_count"] == 3
    assert set(result["ids"]) == {same_a, same_b, same_std}

    assert session.get(Extraction, other).status == ExtractionStatus.PENDING
    assert session.get(Extraction, already).status == ExtractionStatus.APPROVED
    assert session.get(Extraction, same_std).status == ExtractionStatus.APPROVED

    # Mỗi dòng được duyệt hàng loạt có audit riêng, đánh dấu bulk.
    bulk_logs = (
        session.query(AuditLog)
        .filter(AuditLog.action == "approve", AuditLog.entity_id == str(same_a))
        .all()
    )
    assert bulk_logs and bulk_logs[0].after.get("bulk") is True


def test_bulk_approve_requires_extractor(session, approver):
    with pytest.raises(review.ValidationError):
        review.bulk_approve(session, approver, extractor="")


def test_bulk_approve_scopes_to_document(session, approver):
    here = _add_fact(session, extractor="rule:bang2.v1")
    there = _add_fact(session, extractor="rule:bang2.v1", document_id=OTHER_STEM)

    result = review.bulk_approve(session, approver, extractor="rule:bang2.v1", document_id=STEM)
    assert result["ids"] == [here]
    assert session.get(Extraction, there).status == ExtractionStatus.PENDING


# ── Audit history ─────────────────────────────────────────────────────────────


def test_audit_history_returns_actor_and_payload(session, approver):
    extraction_id = _add_fact(session, value_text="đến 1 400 bar")
    review.edit_and_approve(
        session, extraction_id, approver, {"value_text": "đến 1 600 bar"}, note="sửa"
    )

    history = review.audit_history(session, extraction_id)
    assert len(history) == 1
    entry = history[0]
    assert entry["action"] == "edit_approve"
    assert entry["actor_username"] == "duyet"
    assert entry["before"]["data"]["value_text"] == "đến 1 400 bar"
    assert entry["after"]["data"]["value_text"] == "đến 1 600 bar"
    assert review.audit_history(session, 999999) == []


# ── P3: view đã duyệt là nguồn duy nhất cho tra cứu ───────────────────────────


def test_pending_and_rejected_absent_from_approved_views(session, approver):
    approved = _add_fact(session, confidence=0.9)
    pending = _add_fact(session, confidence=0.6)
    rejected = _add_fact(session, confidence=0.5)
    review.approve(session, approved, approver)
    review.reject(session, rejected, approver, "sai")

    rows = session.execute(text("SELECT extraction_id FROM v_procedure_fact")).scalars().all()
    assert rows == [approved]
    assert pending not in rows and rejected not in rows


def _view_count(session, view: str) -> int:
    return session.execute(text(f"select count(*) from {view}")).scalar_one()
