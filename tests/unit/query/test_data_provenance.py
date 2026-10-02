"""Xuất xứ từng ô số: tài liệu, mục, chunk, trích dẫn (P1, Sprint 8)."""

from __future__ import annotations

import pytest
from sqlalchemy import text

from query import provenance as qp
from query import records as qr


def test_measurement_provenance_cell_text(data_db):
    db, ids = data_db
    record = qr.get_record(db, ids["record_a_id"])
    point = record["measurements"][0]
    source = qp.measurement_provenance(db, point["id"], "error")
    assert source["kind"] == "measurement"
    assert source["field"] == "error"
    assert source["value_text"] == "0,1"
    assert source["file_stem"] == "BB_2024_001"
    assert source["section_path"] == "Phụ lục A"
    assert source["chunk_id"] == "chunk-record-a"
    assert source["source_quote"].startswith("Số hiệu: SN-1")
    assert source["measurement_id"] == point["id"]
    assert source["record_id"] == ids["record_a_id"]


def test_measurement_provenance_defaults_to_row_quote(data_db):
    db, ids = data_db
    point = qr.get_record(db, ids["record_a_id"])["measurements"][0]
    source = qp.measurement_provenance(db, point["id"])
    assert source["quote"] == "1 | 10 | 10,1 | 0,1 | 0,5"


def test_fact_provenance(data_db):
    db, ids = data_db
    source = qp.fact_provenance(db, ids["range_fact_id"])
    assert source["kind"] == "fact"
    assert source["field"] == "working_range"
    assert source["value_text"] == "(0 ÷ 1600) bar"
    assert source["file_stem"] == "QTKD_1.061_2021_ND_V2"
    assert source["section_path"] == "1 Phạm vi áp dụng"
    assert source["chunk_id"] == "chunk-range"
    assert source["fact_id"] == ids["range_fact_id"]


def test_record_provenance(data_db):
    db, ids = data_db
    source = qp.record_provenance(db, ids["record_a_id"])
    assert source["kind"] == "record"
    assert source["record_id"] == ids["record_a_id"]
    assert source["chunk_id"] == "chunk-record-a"


def test_extraction_provenance(data_db):
    db, ids = data_db
    source = qp.extraction_provenance(db, ids["range_extraction_id"])
    assert source["kind"] == "extraction"
    assert source["chunk_id"] == "chunk-range"


def test_unknown_references_raise(data_db):
    db, _ = data_db
    with pytest.raises(qp.ProvenanceError):
        qp.measurement_provenance(db, 999999)
    with pytest.raises(qp.ProvenanceError):
        qp.fact_provenance(db, 999999)
    with pytest.raises(qp.ProvenanceError):
        qp.record_provenance(db, 999999)
    with pytest.raises(qp.ProvenanceError):
        qp.resolve(db)


def test_resolve_prefers_most_specific(data_db):
    db, ids = data_db
    source = qp.resolve(
        db,
        measurement_id=None,
        fact_id=ids["range_fact_id"],
        record_id=ids["record_a_id"],
    )
    assert source["kind"] == "fact"


def test_pending_extraction_has_no_provenance(data_db):
    db, _ = data_db
    # Extraction pending không nằm trong view đã duyệt nên không dựng được nguồn.
    pending = db.execute(text("SELECT id FROM extraction WHERE status = 'pending'")).scalar()
    with pytest.raises(qp.ProvenanceError):
        qp.extraction_provenance(db, pending)
