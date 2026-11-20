"""Tóm tắt tài liệu - knowledge.doc_summary: sinh nháp, sửa, duyệt, dùng bản đã duyệt."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import db as db_pkg
from db.models import AppUser, Base, Document, DocumentSummary, DocumentType, IngestStatus, UserRole
from knowledge import doc_summary

STEM = "QTKD_1.061_2021_ND_V2_2"
MARKDOWN = """QTKĐ 1.061 : 2021
VAN AN TOÀN CÓ PHẠM VI LÀM VIỆC ĐẾN 1 400 bar
QUY TRÌNH KIỂM ĐỊNH
Mục lục
1 Phạm vi áp dụng 3
# 1 Phạm vi áp dụng
Quy trình này áp dụng cho van an toàn có áp suất đặt đến 1 400 bar, cấp chính xác 0,5.
# 2 Các phép kiểm định
Kiểm tra bên ngoài; kiểm tra kỹ thuật; kiểm tra đo lường.
$$ \\delta = \\frac{P_{d} - P_{c}}{P_{c}} \\cdot 100 \\% $$
![hình](assets/a.png)
"""
SUMMARY = "- **Đối tượng và phạm vi:** van an toàn đến 1400 bar, cấp chính xác 0.5."


@pytest.fixture
def store(monkeypatch, tmp_path, settings_override):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(db_pkg, "SessionLocal", factory)
    settings_override({"paths.markdown_dir": str(tmp_path)})
    (tmp_path / f"{STEM}.md").write_text(MARKDOWN, encoding="utf-8")
    session = factory()
    session.add(
        Document(
            id=STEM, file_stem=STEM, display_name=f"{STEM}.docx", ext="DOCX",
            doc_type=DocumentType.QTKD, sha256="0" * 64, size_bytes=1,
        )
    )
    session.add_all([
        AppUser(id=1, username="tech", password_hash="x", role=UserRole.TECHNICIAN),
        AppUser(id=2, username="duyet", full_name="Người duyệt", password_hash="x", role=UserRole.APPROVER),
    ])
    session.commit()
    session.close()
    calls: list[list[dict]] = []

    def fake_llm(messages):
        calls.append(messages)
        return f"```markdown\n{SUMMARY}\n```"

    monkeypatch.setattr(doc_summary, "_call_llm", fake_llm)
    yield {"factory": factory, "calls": calls, "dir": tmp_path}
    engine.dispose()


def _user(store, user_id: int) -> AppUser:
    session = store["factory"]()
    try:
        return session.get(AppUser, user_id)
    finally:
        session.close()


def test_source_excerpt_starts_at_section_one_and_drops_formulas_and_images():
    text = doc_summary.source_excerpt(MARKDOWN, 10_000)
    assert text.startswith("# 1 Phạm vi áp dụng")
    assert "[công thức]" in text and "\\frac" not in text and "assets/a.png" not in text


def test_source_excerpt_is_capped_on_a_line_boundary():
    full = doc_summary.source_excerpt(MARKDOWN, 10_000)
    capped = doc_summary.source_excerpt(MARKDOWN, 60)
    assert len(capped) <= 60 and full.startswith(capped) and full[len(capped)] == "\n"


def test_number_warnings_ignore_thousand_spaces_and_decimal_comma():
    source = "áp suất đến 1 400 bar, cấp chính xác 0,5"
    assert doc_summary.number_warnings("đến 1400 bar, cấp 0.5", source) == []
    assert doc_summary.number_warnings("chu kỳ 12 tháng", source) == ["Số liệu không thấy trong tài liệu: 12"]


def test_generate_writes_a_draft_from_the_document_text(store):
    result = doc_summary.generate(STEM)
    assert result["status"] == "draft"
    assert result["text"] == SUMMARY == result["generated_text"]  # bỏ hàng rào ```markdown
    assert result["warnings"] == []
    prompt = store["calls"][0][1]["content"]
    assert "QTKĐ 1.061:2021" in prompt and "# 1 Phạm vi áp dụng" in prompt


def test_generate_skips_unchanged_document_and_redrafts_changed_one(store):
    first = doc_summary.generate(STEM)
    approved = doc_summary.decide(STEM, first["revision"], True, "", _user(store, 2))
    assert doc_summary.generate(STEM)["status"] == "approved"
    assert len(store["calls"]) == 1  # Markdown không đổi: không gọi lại LLM

    (store["dir"] / f"{STEM}.md").write_text(MARKDOWN + "\n# 3 Chu kỳ\n12 tháng\n", encoding="utf-8")
    assert doc_summary.get(STEM)["stale"] is True
    assert doc_summary.approved_text(STEM) is None  # chưa sinh lại: bản đã duyệt không được dùng nữa
    redrafted = doc_summary.generate(STEM)
    assert redrafted["status"] == "draft" and redrafted["revision"] > approved["revision"]
    assert redrafted["reviewed_by"] is None and doc_summary.approved_text(STEM) is None


def test_llm_failure_is_recorded_and_can_be_regenerated(store, monkeypatch):
    def broken(_messages):
        raise RuntimeError("Ollama 500")

    monkeypatch.setattr(doc_summary, "_call_llm", broken)
    failed = doc_summary.generate(STEM)
    assert failed["status"] == "error" and failed["error"] == "Ollama 500"
    monkeypatch.setattr(doc_summary, "_call_llm", lambda _m: SUMMARY)
    assert doc_summary.generate(STEM)["status"] == "draft"


def test_edit_returns_to_draft_and_flags_invented_numbers(store):
    draft = doc_summary.generate(STEM)
    approved = doc_summary.decide(STEM, draft["revision"], True, "ok", _user(store, 2))
    edited = doc_summary.edit(STEM, approved["revision"], "- Chu kỳ kiểm định 12 tháng.", _user(store, 1))
    assert edited["status"] == "draft" and edited["edited_by"] == "tech"
    assert edited["warnings"] == ["Số liệu không thấy trong tài liệu: 12"]
    assert edited["generated_text"] == SUMMARY


def test_stale_revision_is_a_conflict(store):
    draft = doc_summary.generate(STEM)
    doc_summary.edit(STEM, draft["revision"], "- Bản sửa.", None)
    with pytest.raises(doc_summary.Conflict):
        doc_summary.edit(STEM, draft["revision"], "- Bản sửa khác.", None)


def test_only_approved_summary_reaches_chat(store):
    draft = doc_summary.generate(STEM)
    assert doc_summary.approved_text(STEM) is None
    approved = doc_summary.decide(STEM, draft["revision"], True, "", _user(store, 2))
    assert approved["reviewed_by"] == "Người duyệt (duyet)"
    assert doc_summary.approved_text(STEM) == SUMMARY
    revoked = doc_summary.decide(STEM, approved["revision"], False, "Sai phạm vi", _user(store, 2))
    assert revoked["status"] == "rejected" and doc_summary.approved_text(STEM) is None


def test_reject_needs_a_note_and_rejected_cannot_be_approved_directly(store):
    draft = doc_summary.generate(STEM)
    with pytest.raises(doc_summary.SummaryError):
        doc_summary.decide(STEM, draft["revision"], False, "  ", None)
    rejected = doc_summary.decide(STEM, draft["revision"], False, "Thiếu ý", None)
    with pytest.raises(doc_summary.Conflict):
        doc_summary.decide(STEM, rejected["revision"], True, "", None)


def test_unknown_document_and_missing_markdown_are_not_found(store):
    with pytest.raises(doc_summary.NotFound):
        doc_summary.get("khong_co")
    (store["dir"] / f"{STEM}.md").unlink()
    with pytest.raises(doc_summary.NotFound):
        doc_summary.generate(STEM)


def test_approved_text_survives_an_unreachable_database(monkeypatch):
    def down():
        raise RuntimeError("không kết nối được")

    monkeypatch.setattr(db_pkg, "SessionLocal", down)
    assert doc_summary.approved_text(STEM) is None


def test_delete_for_removes_the_summary_row(store):
    doc_summary.generate(STEM)
    session = store["factory"]()
    doc_summary.delete_for(session, STEM)
    session.commit()
    assert session.query(DocumentSummary).count() == 0
    session.close()


def test_draft_of_an_outdated_document_cannot_be_approved(store):
    draft = doc_summary.generate(STEM)
    (store["dir"] / f"{STEM}.md").write_text(MARKDOWN + "\nThêm.\n", encoding="utf-8")
    with pytest.raises(doc_summary.Conflict):
        doc_summary.decide(STEM, draft["revision"], True, "", None)


def test_edit_and_decide_refuse_a_summary_being_generated(store, monkeypatch):
    def during_generation(_messages):
        row = doc_summary.get(STEM)
        assert row["status"] == "generating"
        with pytest.raises(doc_summary.Conflict):
            doc_summary.edit(STEM, row["revision"], "- Chen ngang.", None)
        with pytest.raises(doc_summary.Conflict):
            doc_summary.decide(STEM, row["revision"], True, "", None)
        return SUMMARY

    monkeypatch.setattr(doc_summary, "_call_llm", during_generation)
    assert doc_summary.generate(STEM)["text"] == SUMMARY


def test_request_during_a_running_generation_reruns_afterwards(monkeypatch):
    submitted: list[tuple[str, bool]] = []
    monkeypatch.setattr(doc_summary, "_submit", lambda stem, force: submitted.append((stem, force)))
    monkeypatch.setattr(doc_summary, "generate", lambda stem, force: None)

    assert doc_summary.queue(STEM) is True
    assert doc_summary.is_queued(STEM)
    assert doc_summary.queue(STEM, force=True) is False  # gộp, không chạy song song
    assert doc_summary.queue(STEM) is False
    assert submitted == [(STEM, False)]

    doc_summary._run_queued(STEM, False)  # lần đầu xong: chạy lại ngay với force gộp
    assert submitted == [(STEM, False), (STEM, True)] and doc_summary.is_queued(STEM)
    doc_summary._run_queued(STEM, True)
    assert not doc_summary.is_queued(STEM)


def test_check_can_generate_needs_a_ready_processed_document(store, settings_override):
    with pytest.raises(doc_summary.Conflict):
        doc_summary.check_can_generate(STEM)  # tài liệu còn pending
    session = store["factory"]()
    session.get(Document, STEM).ingest_status = IngestStatus.READY
    session.commit()
    session.close()
    doc_summary.check_can_generate(STEM)
    (store["dir"] / f"{STEM}.md").unlink()
    with pytest.raises(doc_summary.NotFound):
        doc_summary.check_can_generate(STEM)
    settings_override({"doc_summary.enabled": False})
    with pytest.raises(doc_summary.Conflict):
        doc_summary.check_can_generate(STEM)
