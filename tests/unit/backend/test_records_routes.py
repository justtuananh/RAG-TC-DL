"""API nạp hồ sơ + đọc hồ sơ đã duyệt (Sprint 7).

Chạy in-process: FastAPI TestClient + SQLite in-memory. Kiểm ma trận quyền, luồng
nạp hồ sơ qua hàng đợi duyệt, và P3 (hồ sơ ``pending`` không lộ ra ``/api/records``).
"""

from __future__ import annotations

import json

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
    Base,
    Document,
    DocumentType,
    Extraction,
    ExtractionStatus,
    Procedure,
    ProcedureFact,
    UserRole,
)
from db.views import create_all_approved_views

PASSWORD = "correct-horse-battery"
QTKD_STEM = "QTKD_1.061_2021_ND_V2"
RECORD_STEM = "BB_2024_001"


@pytest.fixture
def session_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        create_all_approved_views(connection)
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    yield factory
    Base.metadata.drop_all(engine)
    engine.dispose()


def _seed(session_factory) -> int:
    db = session_factory()
    try:
        db.add(
            Document(
                id=QTKD_STEM,
                file_stem=QTKD_STEM,
                display_name=f"{QTKD_STEM}.docx",
                ext="DOCX",
                doc_type=DocumentType.QTKD,
                sha256="0" * 64,
                size_bytes=1,
            )
        )
        db.add(
            Document(
                id=RECORD_STEM,
                file_stem=RECORD_STEM,
                display_name=f"{RECORD_STEM}.docx",
                ext="DOCX",
                doc_type=DocumentType.HO_SO_KIEM_DINH,
                sha256="1" * 64,
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
        procedure = Procedure(number="1.061", document_id=QTKD_STEM)
        db.add(procedure)
        db.commit()

        def fact(label, value_text=None, role="header"):
            extraction = Extraction(
                document_id=QTKD_STEM,
                section_path="Phụ lục A",
                quote=f"{label}: {value_text or ''}",
                extractor="rule:phuluc_a.v1",
                extractor_version="v1",
                confidence=0.9,
                status=ExtractionStatus.APPROVED,
            )
            db.add(extraction)
            db.flush()
            db.add(
                ProcedureFact(
                    extraction_id=extraction.id,
                    procedure_id=procedure.id,
                    fact_kind="appendix_field",
                    label=label,
                    value_text=value_text,
                    condition_text=role,
                )
            )

        fact("Số hiệu")
        fact(
            "Bảng A.1 - Xác định sai số và độ chênh áp",
            json.dumps(
                {
                    "title": "Bảng A.1",
                    "columns": ["Lần kiểm tra", "Áp suất", "Sai số", "Ghi chú"],
                },
                ensure_ascii=False,
            ),
            role="table",
        )
        db.commit()
        return procedure.id
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
def client(session_factory, users, monkeypatch, data_dir):
    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    api_server.app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(auth_deps, "AUTH_ENABLED", True)
    monkeypatch.setattr(
        ingestion_jobs,
        "get_source_path",
        lambda stem: data_dir / "record_bien_ban.docx" if stem == RECORD_STEM else None,
    )
    with TestClient(api_server.app) as test_client:
        yield test_client
    api_server.app.dependency_overrides.clear()


def _auth(users, role: str) -> dict:
    user_id, username = users[role]
    return {"Authorization": f"Bearer {create_access_token(user_id, username, role)}"}


def test_ingest_requires_token(client):
    assert client.post(f"/api/records/ingest/{RECORD_STEM}").status_code == 401


@pytest.mark.parametrize("role", ["viewer", "approver"])
def test_ingest_forbids_non_technicians(client, users, role):
    resp = client.post(f"/api/records/ingest/{RECORD_STEM}", headers=_auth(users, role))
    assert resp.status_code == 403


def test_ingest_unknown_document_is_404(client, users):
    resp = client.post("/api/records/ingest/khong-ton-tai", headers=_auth(users, "technician"))
    assert resp.status_code == 404


def test_technician_ingests_record_into_pending(client, users, session_factory):
    db = session_factory()
    procedure_id = db.query(Procedure).one().id
    db.close()

    resp = client.post(
        f"/api/records/ingest/{RECORD_STEM}",
        headers=_auth(users, "technician"),
        json={"procedure_id": procedure_id},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["measurement_points"] == 3
    assert body["needs_identification"] is False

    # P3: hồ sơ mới pending nên chưa lộ ra bề mặt đã duyệt.
    listed = client.get("/api/records", headers=_auth(users, "approver"))
    assert listed.status_code == 200
    assert listed.json()["total"] == 0

    # Duyệt extraction của hồ sơ → hồ sơ lộ ra.
    extraction_id = body["extraction_id"]
    approved = client.post(
        f"/api/extractions/{extraction_id}/approve", headers=_auth(users, "approver")
    )
    assert approved.status_code == 200

    listed = client.get("/api/records", headers=_auth(users, "approver"))
    assert listed.json()["total"] == 1
    assert listed.json()["records"][0]["id"] == body["record_id"]


def test_records_list_requires_reviewer(client, users):
    assert client.get("/api/records").status_code == 401
    assert client.get("/api/records", headers=_auth(users, "viewer")).status_code == 403
    assert client.get("/api/records", headers=_auth(users, "technician")).status_code == 403
    assert client.get("/api/records", headers=_auth(users, "approver")).status_code == 200
