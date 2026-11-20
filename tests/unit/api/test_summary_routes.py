"""Route tóm tắt tài liệu: quyền theo vai trò, mã lỗi nghiệp vụ, audit_log."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import db as db_pkg
from api.main import app
from auth.security import create_access_token
from db import get_db
from db.models import AppUser, AuditLog, Base, Document, DocumentType, IngestStatus, UserRole
from knowledge import doc_summary

STEM = "QTKD_1.061_2021_ND_V2_2"
URL = f"/api/documents/{STEM}/summary"


@pytest.fixture
def client(monkeypatch, tmp_path, settings_override):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    monkeypatch.setattr(db_pkg, "SessionLocal", factory)
    settings_override({"auth.enabled": True, "paths.markdown_dir": str(tmp_path)})
    (tmp_path / f"{STEM}.md").write_text("# 1 Phạm vi áp dụng\nVan an toàn đến 1 400 bar.\n", encoding="utf-8")
    monkeypatch.setattr(doc_summary, "_call_llm", lambda _m: "- Van an toàn đến 1 400 bar.")
    session = factory()
    session.add(
        Document(
            id=STEM, file_stem=STEM, display_name="a.docx", ext="DOCX",
            doc_type=DocumentType.QTKD, sha256="0" * 64, size_bytes=1, ingest_status=IngestStatus.READY,
        )
    )
    for user_id, role in enumerate(UserRole, start=1):
        session.add(AppUser(id=user_id, username=role.value, password_hash="x", role=role, is_active=1))
    session.commit()
    session.close()

    def override_get_db():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        test_client.factory = factory
        yield test_client
    app.dependency_overrides.clear()
    engine.dispose()


def _auth(role: UserRole) -> dict:
    user_id = list(UserRole).index(role) + 1
    return {"Authorization": f"Bearer {create_access_token(user_id, role.value, role.value)}"}


def test_read_requires_login_and_is_empty_before_generation(client):
    assert client.get(URL).status_code == 401
    resp = client.get(URL, headers=_auth(UserRole.VIEWER))
    assert resp.status_code == 200 and resp.json() == {"summary": None, "queued": False}
    assert client.get("/api/documents/khong_co/summary", headers=_auth(UserRole.VIEWER)).status_code == 404


def test_generate_is_for_editors_and_is_queued(client, monkeypatch):
    assert client.post(f"{URL}/generate", headers=_auth(UserRole.VIEWER)).status_code == 403
    assert client.post(f"{URL}/generate", headers=_auth(UserRole.APPROVER)).status_code == 403
    queued: list[tuple[str, bool]] = []
    monkeypatch.setattr(doc_summary, "_submit", lambda stem, force: queued.append((stem, force)))
    resp = client.post(f"{URL}/generate", headers=_auth(UserRole.TECHNICIAN))
    assert resp.status_code == 202 and queued == [(STEM, True)]
    assert client.get(URL, headers=_auth(UserRole.VIEWER)).json()["queued"] is True
    # Bấm lại khi đang sinh: gộp thành một lần chạy lại, không chạy song song.
    assert client.post(f"{URL}/generate", headers=_auth(UserRole.TECHNICIAN)).status_code == 202
    assert queued == [(STEM, True)]


def test_generate_refuses_documents_that_cannot_be_summarised(client):
    missing = client.post("/api/documents/khong_co/summary/generate", headers=_auth(UserRole.TECHNICIAN))
    assert missing.status_code == 404
    session = client.factory()
    session.get(Document, STEM).ingest_status = IngestStatus.SUPERSEDED
    session.commit()
    session.close()
    assert client.post(f"{URL}/generate", headers=_auth(UserRole.TECHNICIAN)).status_code == 409


def test_review_flow_respects_roles_and_writes_audit(client):
    revision = doc_summary.generate(STEM)["revision"]
    body = {"revision": revision, "note": ""}
    assert client.post(f"{URL}/approve", json=body, headers=_auth(UserRole.TECHNICIAN)).status_code == 403

    edited = client.put(URL, json={"revision": revision, "text": "- Bản sửa."}, headers=_auth(UserRole.TECHNICIAN))
    assert edited.status_code == 200 and edited.json()["summary"]["status"] == "draft"
    revision = edited.json()["summary"]["revision"]

    stale = client.post(f"{URL}/approve", json={"revision": revision - 1, "note": ""}, headers=_auth(UserRole.APPROVER))
    assert stale.status_code == 409
    no_note = client.post(f"{URL}/reject", json={"revision": revision, "note": ""}, headers=_auth(UserRole.APPROVER))
    assert no_note.status_code == 422

    approved = client.post(f"{URL}/approve", json={"revision": revision, "note": ""}, headers=_auth(UserRole.APPROVER))
    assert approved.status_code == 200 and approved.json()["summary"]["status"] == "approved"
    assert doc_summary.approved_text(STEM) == "- Bản sửa."

    session = client.factory()
    actions = [(row.action, row.entity_type) for row in session.query(AuditLog).order_by(AuditLog.id)]
    session.close()
    assert actions == [("edit", "document_summary"), ("approve", "document_summary")]
