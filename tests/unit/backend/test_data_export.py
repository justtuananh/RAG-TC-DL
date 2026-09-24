"""Xuất Excel kèm cột xuất xứ (Sprint 8)."""

from __future__ import annotations

import io
import zipfile

from query import export as qe
from query import provenance as qp
from query import records as qr


def _read_sheet(payload: bytes) -> str:
    archive = zipfile.ZipFile(io.BytesIO(payload))
    assert "xl/worksheets/sheet1.xml" in archive.namelist()
    return archive.read("xl/worksheets/sheet1.xml").decode("utf-8")


def test_xlsx_is_valid_zip(data_db):
    db, _ = data_db
    records, _ = qr.list_records(db)
    payload = qe.records_xlsx(records)
    assert payload[:2] == b"PK"
    archive = zipfile.ZipFile(io.BytesIO(payload))
    assert archive.testzip() is None
    assert "xl/workbook.xml" in archive.namelist()


def test_headers_include_provenance_columns():
    headers = list(qe.EXPORT_HEADERS)
    assert "Tài liệu nguồn" in headers
    assert "Mục nguồn" in headers
    assert "Chunk nguồn" in headers
    assert "Trích dẫn nguồn" in headers
    # Có cột nguồn xen sau các ô số.
    assert "Nguồn ngày kiểm định" in headers
    assert "Nguồn phạm vi" in headers
    assert "Nguồn cấp chính xác" in headers


def test_export_rows_carry_source_refs(data_db):
    db, ids = data_db

    def lookup(fact_id: int):
        return qp.fact_provenance(db, fact_id)

    records, _ = qr.list_records(db, sort="calibrated_at", order="asc")
    rows = qe.build_export_rows(records, lookup)
    assert len(rows) == 2
    for row in rows:
        assert len(row) == len(qe.EXPORT_HEADERS)
    first = dict(zip(qe.EXPORT_HEADERS, rows[0], strict=True))
    assert first["Tài liệu nguồn"] == "BB_2024_001"
    assert first["Mục nguồn"] == "Phụ lục A"
    assert first["Chunk nguồn"] == "chunk-record-a"
    assert first["Trích dẫn nguồn"].startswith("Số hiệu: SN-1")
    # Nguồn phạm vi trỏ về QTKĐ + dữ kiện đã duyệt.
    assert "QTKD_1.061_2021_ND_V2" in first["Nguồn phạm vi"]
    assert "1 Phạm vi áp dụng" in first["Nguồn phạm vi"]


def test_export_only_approved(data_db):
    db, _ = data_db
    records, _ = qr.list_records(db)
    payload = qe.records_xlsx(records)
    sheet = _read_sheet(payload)
    assert "SN-1" in sheet
    assert "SN-PENDING" not in sheet


def test_export_escapes_xml(data_db):
    db, _ = data_db
    records, _ = qr.list_records(db)
    records[0]["manufacturer"] = "A < B & C"
    payload = qe.records_xlsx(records)
    sheet = _read_sheet(payload)
    assert "A &lt; B &amp; C" in sheet
