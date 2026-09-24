"""API hàng đợi duyệt: ma trận quyền 401/403, luồng duyệt/từ chối/sửa/hàng loạt,
audit, và P3 (dữ liệu chưa duyệt không lộ ra bề mặt đã duyệt) — Sprint 6.

Chạy in-process: FastAPI TestClient (ASGI, không socket) + SQLite in-memory, view
đã duyệt dựng bằng cùng hàm `create_approved_views`. Không cần Postgres.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import api_server
import auth.dependencies as auth_deps
import ingestion_jobs
from auth.security import create_access_token, hash_password
from db import get_db
from db.models import (
    AppUser,
    AuditLog,
    Base,
    Document,
    DocumentType,
    Extraction,
    ExtractionStatus,
    ProcedureFact,
    UserRole,
)
from db.views import create_approved_views
from query import approved as approved_query

PASSWORD = "correct-horse-battery"
STEM = "QTKD_1.061_2021_ND_V2"


@pytest.fixture
def session_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        create_approved_views(connection)
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    yield factory
    Base.metadata.drop_all(engine)
    engine.dispose()


def _seed(session_factory):
    db = session_factory()
    try:
        db.add(
            Document(
                id=STEM,
                file_stem=STEM,
                display_name=f"{STEM}.docx",
                ext="DOCX",
                doc_type=DocumentType.QTKD,
                sha256="0" * 64,
                size_bytes=1,
            )
        )
        for username, role in (
            ("admin", UserRole.ADMIN),
            ("duyet", UserRole.APPROVER),
            ("tech", UserRole.TECHNICIAN),
            ("viewer", UserRole.VIEWER),
        ):
            db.add(
                AppUser(
                    username=username,
                    full_name=username,
                    password_hash=hash_password(PASSWORD),
                    role=role,
                    is_active=1,
                )
            )
        db.commit()
    finally:
        db.close()


def _add_extraction(session_factory, *, extractor="rule:bang2.v1", confidence=0.9, value_text="cũ"):
    db = session_factory()
    try:
        extraction = Extraction(
            document_id=STEM,
            section_path="4 Phương tiện kiểm định",
            chunk_id="chunk-1",
            quote="Phạm vi đo đến 1 400 bar",
            char_start=10,
            char_end=33,
            extractor=extractor,
            extractor_version="v1",
            confidence=confidence,
            status=ExtractionStatus.PENDING,
        )
        db.add(extraction)
        db.flush()
        db.add(
            ProcedureFact(
                extraction_id=extraction.id,
                fact_kind="working_range",
                label="Phạm vi đo",
                value_text=value_text,
                value_max=1400 * 100_000,
            )
        )
        db.commit()
        return extraction.id
    finally:
        db.close()


@pytest.fixture
def users(session_factory):
    _seed(session_factory)
    db = session_factory()
    try:
        return {u.role.value: (u.id, u.username) for u in db.query(AppUser).all()}
    finally:
        db.close()


@pytest.fixture
def client(session_factory, users, monkeypatch):
    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    api_server.app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(auth_deps, "AUTH_ENABLED", True)
    # Nguồn nguyên văn đọc từ file; cố định nó để test tất định.
    monkeypatch.setattr(
        ingestion_jobs,
        "get_markdown",
        lambda stem: "# 4 Phương tiện kiểm định\n\nPhạm vi đo đến 1 400 bar trong mục.\n",
    )
    with TestClient(api_server.app) as test_client:
        yield test_client
    api_server.app.dependency_overrides.clear()


def _token(users, role: str) -> str:
    user_id, username = users[role]
    return create_access_token(user_id, username, role)


def _auth(users, role: str) -> dict:
    return {"Authorization": f"Bearer {_token(users, role)}"}


# ── Ma trận quyền ─────────────────────────────────────────────────────────────


def test_queue_requires_token(client):
    assert client.get("/api/extractions").status_code == 401


@pytest.mark.parametrize("role", ["viewer", "technician"])
def test_queue_forbids_non_reviewers(client, users, role):
    assert client.get("/api/extractions", headers=_auth(users, role)).status_code == 403


@pytest.mark.parametrize("role", ["approver", "admin"])
def test_queue_allows_reviewers(client, users, role):
    resp = client.get("/api/extractions", headers=_auth(users, role))
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending"


WRITE_ROUTES = [
    ("post", "/api/extractions/1/approve", {"json": {}}),
    ("post", "/api/extractions/1/reject", {"json": {"reason": "sai"}}),
    ("post", "/api/extractions/1/edit", {"json": {"value_text": "mới"}}),
    ("post", "/api/extractions/bulk-approve", {"json": {"extractor": "rule:bang2.v1"}}),
    ("get", "/api/extractions/1", {}),
    ("get", "/api/extractions/1/audit", {}),
]


@pytest.mark.parametrize("method, path, kwargs", WRITE_ROUTES)
def test_review_routes_reject_missing_token(client, method, path, kwargs):
    assert getattr(client, method)(path, **kwargs).status_code == 401


@pytest.mark.parametrize("method, path, kwargs", WRITE_ROUTES)
def test_review_routes_forbid_viewer(client, users, method, path, kwargs):
    resp = getattr(client, method)(path, headers=_auth(users, "viewer"), **kwargs)
    assert resp.status_code == 403


# ── Luồng duyệt ───────────────────────────────────────────────────────────────


def test_list_filters_and_never_returns_unapproved_by_default(client, users, session_factory):
    pending = _add_extraction(session_factory, confidence=0.6, value_text="đến 1 400 bar")
    approved = _add_extraction(session_factory, confidence=0.9)
    client.post(f"/api/extractions/{approved}/approve", headers=_auth(users, "approver"))

    body = client.get("/api/extractions", headers=_auth(users, "approver")).json()
    assert body["total"] == 1
    assert [item["id"] for item in body["items"]] == [pending]

    # Lọc theo điểm tin cậy và theo tài liệu.
    filtered = client.get(
        "/api/extractions",
        params={"document_id": STEM, "max_confidence": 0.7},
        headers=_auth(users, "approver"),
    ).json()
    assert [item["id"] for item in filtered["items"]] == [pending]

    # Lịch sử có thể xem lại dòng đã duyệt.
    history = client.get(
        "/api/extractions", params={"status": "approved"}, headers=_auth(users, "approver")
    ).json()
    assert [item["id"] for item in history["items"]] == [approved]


def test_approve_records_audit_and_updates_queue(client, users, session_factory):
    extraction_id = _add_extraction(session_factory)

    resp = client.post(
        f"/api/extractions/{extraction_id}/approve",
        headers=_auth(users, "approver"),
        json={"note": "đạt"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"

    db = session_factory()
    try:
        log = db.query(AuditLog).one()
        assert log.action == "approve"
        assert log.entity_id == str(extraction_id)
        assert log.actor_id == users["approver"][0]
    finally:
        db.close()

    assert client.get("/api/extractions", headers=_auth(users, "approver")).json()["total"] == 0


def test_approve_twice_conflicts_and_unknown_is_404(client, users, session_factory):
    extraction_id = _add_extraction(session_factory)
    headers = _auth(users, "approver")
    assert (
        client.post(f"/api/extractions/{extraction_id}/approve", headers=headers).status_code == 200
    )
    assert (
        client.post(f"/api/extractions/{extraction_id}/approve", headers=headers).status_code == 409
    )
    assert client.post("/api/extractions/999999/approve", headers=headers).status_code == 404


def test_reject_requires_reason_and_records_it(client, users, session_factory):
    extraction_id = _add_extraction(session_factory)
    headers = _auth(users, "approver")

    assert (
        client.post(
            f"/api/extractions/{extraction_id}/reject", headers=headers, json={"reason": "  "}
        ).status_code
        == 400
    )
    assert (
        client.post(
            f"/api/extractions/{extraction_id}/reject",
            headers=headers,
            json={"reason": "Sai đơn vị"},
        ).status_code
        == 200
    )

    detail = client.get(f"/api/extractions/{extraction_id}", headers=headers).json()
    assert detail["status"] == "rejected"
    assert detail["review_note"] == "Sai đơn vị"


def test_edit_then_approve_changes_value_but_keeps_quote(client, users, session_factory):
    extraction_id = _add_extraction(session_factory, value_text="đến 1 400 bar")
    headers = _auth(users, "approver")

    resp = client.post(
        f"/api/extractions/{extraction_id}/edit",
        headers=headers,
        json={"value_text": "đến 1 600 bar", "value_max": 1600 * 100_000},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "approved"
    assert body["data"]["value_text"] == "đến 1 600 bar"
    # P1: nguyên văn nguồn không bị đụng tới.
    assert body["quote"] == "Phạm vi đo đến 1 400 bar"


def test_bulk_approve_same_rule(client, users, session_factory):
    _add_extraction(session_factory, extractor="rule:bang2.v1")
    _add_extraction(session_factory, extractor="rule:bang2.v1", confidence=0.7)
    other = _add_extraction(session_factory, extractor="rule:phamvi.v1", confidence=0.5)

    resp = client.post(
        "/api/extractions/bulk-approve",
        headers=_auth(users, "approver"),
        json={"extractor": "rule:bang2.v1", "document_id": STEM},
    )
    assert resp.status_code == 200
    assert resp.json()["approved_count"] == 2

    body = client.get("/api/extractions", headers=_auth(users, "approver")).json()
    assert [item["id"] for item in body["items"]] == [other]


def test_audit_history_endpoint(client, users, session_factory):
    extraction_id = _add_extraction(session_factory)
    headers = _auth(users, "approver")
    client.post(f"/api/extractions/{extraction_id}/approve", headers=headers, json={"note": "ok"})

    entries = client.get(f"/api/extractions/{extraction_id}/audit", headers=headers).json()[
        "entries"
    ]
    assert len(entries) == 1
    assert entries[0]["action"] == "approve"
    assert entries[0]["actor_username"] == "duyet"
    assert entries[0]["after"]["note"] == "ok"

    assert client.get("/api/extractions/999999/audit", headers=headers).status_code == 404


# ── P3: dữ liệu chưa duyệt không lộ ra bề mặt đã duyệt ────────────────────────


def test_unapproved_absent_from_approved_surfaces(client, users, session_factory):
    pending = _add_extraction(session_factory)
    headers = _auth(users, "approver")

    db = session_factory()
    try:
        assert approved_query.approved_counts(db) == {"facts": 0, "standards": 0, "terms": 0}
        assert approved_query.list_approved_facts(db) == []
    finally:
        db.close()

    client.post(f"/api/extractions/{pending}/approve", headers=headers)

    db = session_factory()
    try:
        assert approved_query.approved_counts(db)["facts"] == 1
        facts = approved_query.list_approved_facts(db)
        assert [fact["extraction_id"] for fact in facts] == [pending]
    finally:
        db.close()
