"""Migration sổ tài liệu (scripts.migrate_documents): nhận .doc cũ và cập nhật doc_type.

Ca cập nhật kiểm đúng yêu cầu K1: tệp .xls NAS đã có dòng loại ``khac`` thì đổi
sang ``danh_muc`` mà KHÔNG xóa/dòng mới.
"""

from __future__ import annotations

import hashlib

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import scripts.migrate_documents as md
from db.models import Base, Document, DocumentType


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = factory()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def _point_at(tmp_path, session, monkeypatch):
    monkeypatch.setattr(md, "SOURCE_DIR", tmp_path)
    monkeypatch.setattr(md, "OUT_DIR", tmp_path / "out")
    monkeypatch.setattr(md, "SessionLocal", lambda: session)


def test_iter_sources_includes_legacy_doc(tmp_path, monkeypatch):
    monkeypatch.setattr(md, "SOURCE_DIR", tmp_path)
    (tmp_path / "4. Bieu 1 NAS.doc").write_bytes(b"\xd0\xcf\x11\xe0")
    (tmp_path / "ghi-chu.txt").write_bytes(b"x")
    names = [path.name for path in md.iter_sources()]
    assert names == ["4. Bieu 1 NAS.doc"]


def test_safe_matches_ingestion_for_vietnamese_stems():
    """Chuẩn hoá stem phải khớp ingestion, nếu không _find_source sẽ trượt."""
    from ingestion.spike_a import _safe as ingestion_safe

    for name in [
        "10. Bieu 7 Danh sách KĐV (NAS)",
        "7. Biểu 4 Danh mục QT 2022 NAS",
        "Biên bản kiểm định áp kế pittông SN 0391 2024-11-19",
    ]:
        assert md._safe(name) == ingestion_safe(name)


def test_registers_new_doc_file(tmp_path, session, monkeypatch):
    _point_at(tmp_path, session, monkeypatch)
    (tmp_path / "7. Biểu 4 Danh mục QT 2022 NAS.doc").write_bytes(b"\xd0\xcf\x11\xe0")

    changed = md.migrate(apply=True)

    assert changed == 1
    stem = md._safe("7. Biểu 4 Danh mục QT 2022 NAS")
    row = session.get(Document, stem)
    assert row is not None and row.doc_type == DocumentType.DANH_MUC
    assert row.ext == "DOC"


def test_updates_wrong_doc_type_without_duplicating(tmp_path, session, monkeypatch):
    _point_at(tmp_path, session, monkeypatch)
    path = tmp_path / "6. Bieu 3 Danh muc chuan mau 2022 NAS.xls"
    path.write_bytes(b"\xd0\xcf\x11\xe0")
    stem = md._safe(path.stem)
    session.add(
        Document(
            id=stem,
            file_stem=stem,
            display_name=path.name,
            ext="XLS",
            doc_type=DocumentType.KHAC,
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            size_bytes=1,
        )
    )
    session.commit()

    changed = md.migrate(apply=True)

    assert changed == 1
    rows = session.query(Document).filter(Document.file_stem == stem).all()
    assert len(rows) == 1
    assert rows[0].doc_type == DocumentType.DANH_MUC
