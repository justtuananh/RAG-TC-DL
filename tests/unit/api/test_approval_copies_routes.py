"""Tab "Tài liệu phê duyệt": bản cứng PDF/ảnh chỉ để xem, không vào chatbot.

Quyền theo vai trò, kiểm định dạng thật của tệp, chặn đường dẫn thoát thư mục,
và xoá tài liệu thì xoá luôn các bản phê duyệt của nó.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app
from auth import get_current_user
from db import get_db
from db.models import AppUser, UserRole
from knowledge import approval_copies

pytestmark = pytest.mark.unit

STEM = "QTKD_1.061_2021"
URL = f"/api/documents/{STEM}/approval-copies"
PDF = b"%PDF-1.7\n%scan\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


@pytest.fixture
def store(tmp_path, settings_override):
    source = tmp_path / "TC_DL"
    source.mkdir()
    (source / f"{STEM}.docx").write_bytes(b"docx")
    copies = tmp_path / "approval_copies"
    settings_override({"paths.source_dir": str(source), "paths.approval_copies_dir": str(copies)})
    return copies


@pytest.fixture
def as_role():
    """Giả người đăng nhập theo vai trò, không cần DB (audit được thay bằng hàm rỗng)."""

    def sign_in(role: UserRole) -> TestClient:
        user = AppUser(id=1, username=role.value, full_name=None, role=role)
        app.dependency_overrides[get_current_user] = lambda: user
        return TestClient(app)

    app.dependency_overrides[get_db] = lambda: None
    yield sign_in
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _no_audit(monkeypatch):
    monkeypatch.setattr("api.routes.approval_copies.record_audit", lambda *a, **k: None)


def test_technician_uploads_and_viewer_sees_the_file(store, as_role):
    resp = as_role(UserRole.TECHNICIAN).post(URL, files={"file": ("bản ký.pdf", PDF, "application/pdf")})
    assert resp.status_code == 201
    copy = resp.json()
    assert copy["name"] == "bản ký.pdf" and copy["size"] == len(PDF) and copy["uploaded_by"] == "technician"

    viewer = as_role(UserRole.VIEWER)
    listed = viewer.get(URL).json()["copies"]
    assert [c["id"] for c in listed] == [copy["id"]]
    file_resp = viewer.get(f"{URL}/{copy['id']}/file")
    assert file_resp.status_code == 200
    assert file_resp.content == PDF
    assert file_resp.headers["content-type"] == "application/pdf"
    assert file_resp.headers["content-disposition"].startswith("inline")


def test_copies_are_stored_outside_the_chatbot_corpus(store, as_role):
    as_role(UserRole.APPROVER).post(URL, files={"file": ("anh.png", PNG, "image/png")})
    assert list((store / STEM).glob("*.png"))
    assert not list((store.parent / "TC_DL").glob("*.png"))


def test_newest_copy_is_listed_first(store, as_role):
    client = as_role(UserRole.ADMIN)
    first = client.post(URL, files={"file": ("a.pdf", PDF, "application/pdf")}).json()
    second = client.post(URL, files={"file": ("b.png", PNG, "image/png")}).json()
    assert [c["id"] for c in client.get(URL).json()["copies"]] == [second["id"], first["id"]]


def test_viewer_cannot_upload_or_delete(store, as_role):
    copy = as_role(UserRole.TECHNICIAN).post(URL, files={"file": ("a.pdf", PDF, "application/pdf")}).json()
    viewer = as_role(UserRole.VIEWER)
    assert viewer.post(URL, files={"file": ("a.pdf", PDF, "application/pdf")}).status_code == 403
    assert viewer.delete(f"{URL}/{copy['id']}").status_code == 403


@pytest.mark.parametrize(
    ("name", "data"),
    [("a.docx", b"PK\x03\x04"), ("gia.pdf", b"MZ not a pdf"), ("gia.png", PDF), ("rong.pdf", b"")],
)
def test_rejects_wrong_type_or_disguised_file(store, as_role, name, data):
    resp = as_role(UserRole.TECHNICIAN).post(URL, files={"file": (name, data, "application/octet-stream")})
    assert resp.status_code == 400


def test_rejects_oversized_file(store, as_role, settings_override):
    settings_override({"ingestion.max_upload_bytes": 10})
    resp = as_role(UserRole.TECHNICIAN).post(URL, files={"file": ("a.pdf", PDF, "application/pdf")})
    assert resp.status_code == 413


def test_unknown_document_and_copy_are_404(store, as_role):
    client = as_role(UserRole.ADMIN)
    assert client.get("/api/documents/khong_co/approval-copies").status_code == 404
    assert client.post("/api/documents/khong_co/approval-copies", files={"file": ("a.pdf", PDF)}).status_code == 404
    assert client.get(f"{URL}/{'0' * 32}/file").status_code == 404
    assert client.get(f"{URL}/not-a-uuid/file").status_code == 404


def test_path_traversal_in_stem_is_rejected(store):
    with pytest.raises(approval_copies.ApprovalCopyError):
        approval_copies.list_copies("..")
    with pytest.raises(approval_copies.ApprovalCopyError):
        approval_copies.save_copy("../x", "a.pdf", PDF, None)


def test_delete_removes_file_and_metadata(store, as_role):
    client = as_role(UserRole.TECHNICIAN)
    copy = client.post(URL, files={"file": ("a.pdf", PDF, "application/pdf")}).json()
    assert client.delete(f"{URL}/{copy['id']}").status_code == 204
    assert client.get(URL).json()["copies"] == []
    assert list((store / STEM).iterdir()) == []


def test_deleting_the_document_removes_its_copies(store):
    approval_copies.save_copy(STEM, "a.pdf", PDF, None)
    approval_copies.delete_all(STEM)
    assert approval_copies.list_copies(STEM) == []
    assert not (store / STEM).exists()
