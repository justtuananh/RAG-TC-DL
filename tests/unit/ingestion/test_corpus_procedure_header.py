"""T4: kiểm tra trích xuất đầu mục QTKĐ (``knowledge.procedure.parse_procedure_header``)."""

from __future__ import annotations

import hashlib

import pytest

from db.models import Document, DocumentType, Procedure
from knowledge.procedure import ensure_procedure, parse_procedure_header
from tests.unit.ingestion.conftest import load_manifest

_MANIFEST = load_manifest()


def _abf_ids() -> list[str]:
    return sorted(mid for mid, obj in _MANIFEST.items() if obj["group"] in ("A", "B", "F"))


def _params():
    return [pytest.param(manifest_id, id=manifest_id) for manifest_id in _abf_ids()]


@pytest.mark.parametrize("manifest_id", _params())
def test_procedure_header_matches_manifest(manifest_id, corpus_markdown):
    """Với mọi file nhóm A/B/F: ``number`` khớp ``procedure_number`` và tiêu đề
    không rỗng."""
    assert manifest_id in corpus_markdown, f"{manifest_id}: chưa có Markdown (spike_a lỗi?)"
    md_text = corpus_markdown[manifest_id]
    expected_number = _MANIFEST[manifest_id]["procedure_number"]

    header = parse_procedure_header(md_text)
    assert header is not None, f"{manifest_id}: không tìm thấy header QTKĐ"
    assert header.number == expected_number
    assert header.title and header.title.strip()


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


def test_new_version_document_reassigns_procedure(session, corpus_manifest, corpus_markdown):
    """Nạp F02 (QTKĐ 9.001 phiên bản 2) sau A01: ``Procedure`` số "9.001" trỏ tới
    document của F02 để router văn bản ghim bản mới."""
    for doc_id in ("A01", "F02"):
        document = _make_document(doc_id, corpus_manifest[doc_id])
        session.add(document)
        session.flush()
        ensure_procedure(session, document, corpus_markdown[doc_id])
        session.commit()

    procedure = session.query(Procedure).filter(Procedure.number == "9.001").one()
    assert procedure.document_id == "F02"
