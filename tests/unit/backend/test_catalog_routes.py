"""API danh mục NAS: quyền, tìm không dấu, lọc nhóm, liên kết QTKĐ, P3 (Pha D1).

Chạy in-process: FastAPI TestClient + SQLite đã seed bốn danh mục thật và một
extraction danh mục ``pending`` phải luôn bị ẩn khỏi mọi bề mặt tra cứu.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import api_server
from auth.security import create_access_token, hash_password
from catalogs.readers import read_catalog
from catalogs.store import store_catalog_draft
from catalogs.types import InspectorDraft
from db import get_db
from db.models import (
    AppUser,
    Base,
    Document,
    DocumentType,
    Extraction,
    ExtractionStatus,
    Procedure,
    UserRole,
)
from db.views import create_all_approved_views

NAS = Path(__file__).resolve().parents[2] / "data" / "nas"
FIXTURES = (
    ("bieu3_chuan_mau.xlsx", 84),
    ("bieu7_kdv.docx", 8),
    ("bieu4_danh_muc_qt.docx", 70),
    ("bieu1_linh_vuc.docx", 39),
)
QTKD_STEM = "QTKD_1.159_2021"
PASSWORD = "correct-horse-battery"


@pytest.fixture
def catalog_factory():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        create_all_approved_views(connection)
    factory = sessionmaker(bind=engine, autoflush=False)
    db = factory()
    try:
        db.add(
            Document(
                id=QTKD_STEM,
                file_stem=QTKD_STEM,
                display_name="QTKD 1.159.docx",
                ext="DOCX",
                doc_type=DocumentType.QTKD,
                sha256="f" * 64,
                size_bytes=1,
            )
        )
        db.flush()
        db.add(Procedure(number="1.159", year=2021, title="Áp kế pít tông", document_id=QTKD_STEM))
        for index, (name, _) in enumerate(FIXTURES):
            stem = name.rsplit(".", 1)[0]
            db.add(
                Document(
                    id=stem,
                    file_stem=stem,
                    display_name=name,
                    ext=name.rsplit(".", 1)[1].upper(),
                    doc_type=DocumentType.DANH_MUC,
                    sha256=str(index) * 64,
                    size_bytes=1,
                )
            )
        db.flush()

        for name, _ in FIXTURES:
            document = db.query(Document).filter(Document.id == name.rsplit(".", 1)[0]).one()
            store_catalog_draft(db, document=document, draft=read_catalog(NAS / name))
        # Extraction danh mục CHƯA duyệt ở tài liệu khác — phải luôn vắng mặt (P3).
        tam = Document(
            id="bieu7_tam",
            file_stem="bieu7_tam",
            display_name="bieu7_tam.docx",
            ext="DOCX",
            doc_type=DocumentType.DANH_MUC,
            sha256="e" * 64,
            size_bytes=1,
        )
        db.add(tam)
        db.flush()
        draft = type(
            "D",
            (),
            {
                "kind": "inspector",
                "title": "Danh sách tạm",
                "source_text": "Nguyễn Văn Tạm | 1990",
                "warnings": [],
                "items": [
                    InspectorDraft(
                        ord=1,
                        name="Nguyễn Văn Tạm",
                        birth_year=1990,
                        rank=None,
                        position=None,
                        education=None,
                        specialization=None,
                    )
                ],
            },
        )()
        store_catalog_draft(db, document=tam, draft=draft)
        db.commit()

        for row in db.query(Extraction).all():
            if row.document_id != "bieu7_tam":
                row.status = ExtractionStatus.APPROVED
        for username, role in (
            ("admin", UserRole.ADMIN),
            ("duyet", UserRole.APPROVER),
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
    try:
        yield factory
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def client(catalog_factory, settings_override):
    def override_get_db():
        db = catalog_factory()
        try:
            yield db
        finally:
            db.close()

    api_server.app.dependency_overrides[get_db] = override_get_db
    settings_override({"auth.enabled": True})
    with TestClient(api_server.app) as test_client:
        yield test_client
    api_server.app.dependency_overrides.clear()


def _headers(catalog_factory, role: str = "viewer") -> dict:
    db = catalog_factory()
    try:
        user = db.query(AppUser).filter(AppUser.role == UserRole(role)).one()
        return {"Authorization": f"Bearer {create_access_token(user.id, user.username, role)}"}
    finally:
        db.close()


def test_catalog_routes_require_token(client):
    assert client.get("/api/data/catalogs").status_code == 401
    assert client.get("/api/data/catalogs/lab_standard").status_code == 401


def test_counts_endpoint(client, catalog_factory):
    body = client.get("/api/data/catalogs", headers=_headers(catalog_factory)).json()
    assert body["counts"] == {
        "lab_standard": 84,
        "inspector": 8,
        "procedure_catalog": 70,
        "capability": 39,
    }


def test_search_is_accent_insensitive_with_provenance(client, catalog_factory):
    headers = _headers(catalog_factory, "viewer")
    body = client.get(
        "/api/data/catalogs/lab_standard", headers=headers, params={"q": "ap ke pittong"}
    ).json()
    assert body["total"] == 8
    row = body["items"][0]
    assert row["provenance"]["document_id"] == "bieu3_chuan_mau"
    assert row["provenance"]["display_name"] == "bieu3_chuan_mau.xlsx"
    assert row["provenance"]["quote"]
    assert row["provenance"]["extraction_id"] == row["extraction_id"]


def test_inspector_search_by_name_and_pending_hidden(client, catalog_factory):
    headers = _headers(catalog_factory, "viewer")
    body = client.get(
        "/api/data/catalogs/inspector", headers=headers, params={"q": "Pham Van Ha"}
    ).json()
    assert body["total"] == 1
    assert body["items"][0]["card_no"] == "043/A1"

    pending = client.get(
        "/api/data/catalogs/inspector", headers=headers, params={"q": "Nguyen Van Tam"}
    ).json()
    assert pending["total"] == 0


def test_group_filter_and_groups(client, catalog_factory):
    headers = _headers(catalog_factory, "viewer")
    body = client.get(
        "/api/data/catalogs/procedure_catalog", headers=headers, params={"group": "I"}
    ).json()
    assert body["total"] == 18
    assert all(item["group_code"] == "I" for item in body["items"])
    assert body["groups"] == [
        {"code": code, "title": title}
        for code, title in (
            ("I", "Lĩnh vực áp suất"),
            ("II", "Lĩnh vực tốc độ vòng quay"),
            ("III", "Lĩnh vực nhiệt độ, độ ẩm"),
            ("IV", "Lĩnh vực dung tích, lưu lượng"),
            ("V", "Phương tiện đo hóa lý"),
            ("VI", "Thử nghiệm môi trường"),
        )
    ]


def test_procedure_catalog_links_existing_qtkd(client, catalog_factory):
    headers = _headers(catalog_factory, "viewer")
    body = client.get(
        "/api/data/catalogs/procedure_catalog", headers=headers, params={"q": "1.159"}
    ).json()
    assert body["total"] >= 1
    row = body["items"][0]
    assert row["procedure_number"] == "1.159"
    assert row["procedure_link"]["number"] == "1.159"
    assert row["procedure_link"]["document_id"] == QTKD_STEM


def test_pagination_and_limit_cap(client, catalog_factory):
    headers = _headers(catalog_factory, "viewer")
    body = client.get(
        "/api/data/catalogs/lab_standard", headers=headers, params={"limit": 10, "offset": 5}
    ).json()
    assert body["total"] == 84
    assert len(body["items"]) == 10
    assert body["limit"] == 10 and body["offset"] == 5


def test_unknown_kind_is_400(client, catalog_factory):
    headers = _headers(catalog_factory, "viewer")
    assert client.get("/api/data/catalogs/khong_biet", headers=headers).status_code == 400


def test_all_roles_can_read_catalogs(client, catalog_factory):
    for role in ("viewer", "approver", "admin"):
        assert (
            client.get(
                "/api/data/catalogs/inspector", headers=_headers(catalog_factory, role)
            ).status_code
            == 200
        )
