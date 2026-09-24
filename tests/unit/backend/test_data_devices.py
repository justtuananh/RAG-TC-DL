"""Lịch sử thiết bị: định danh, dòng thời gian, diễn biến sai số (Sprint 8)."""

from __future__ import annotations

import pytest

from query import records as qr


def test_device_history_identity_timeline_trend(data_db):
    db, ids = data_db
    history = qr.device_history(db, device_id=ids["device_id"])
    device = history["device"]
    assert device["serial_no"] == "SN-1"
    assert device["device_type_name"] == "Van an toàn"
    assert device["record_count"] == 2

    # Dòng thời gian cũ → mới.
    assert [record["calibrated_at"][:10] for record in history["records"]] == [
        "2024-01-15",
        "2025-01-15",
    ]
    assert history["records"][0]["verdict_label"] == "Đạt"
    assert history["records"][1]["verdict_label"] == "Không đạt"

    # Diễn biến sai số theo mốc đo 6.3.1: 0,1 → 0,8.
    assert len(history["trend"]) == 1
    series = history["trend"][0]
    assert series["step_code"] == "6.3.1"
    assert [point["error_value"] for point in series["points"]] == [0.1, 0.8]
    assert series["points"][0]["provenance"][0]["kind"] == "measurement"
    assert series["points"][0]["verdict_label"] == "Đạt"
    # Mỗi điểm đo có nguồn (P1).
    assert series["points"][1]["point_id"] is not None


def test_device_history_by_serial_is_normalized(data_db):
    db, ids = data_db
    history = qr.device_history(db, serial="  Sn-1  ")
    assert history["device"]["id"] == ids["device_id"]


def test_device_history_unknown_raises(data_db):
    db, _ = data_db
    with pytest.raises(qr.NotFoundError):
        qr.device_history(db, serial="khong-ton-tai")
    with pytest.raises(qr.NotFoundError):
        qr.device_history(db, device_id=987654)
    with pytest.raises(qr.QueryError):
        qr.device_history(db)


def test_pending_device_absent_from_history(data_db):
    db, ids = data_db
    with pytest.raises(qr.NotFoundError):
        qr.device_history(db, device_id=ids["pending_device_id"])


def test_list_devices_only_approved(data_db):
    db, _ = data_db
    devices, total = qr.list_devices(db)
    assert total == 1
    assert devices[0]["serial_no"] == "SN-1"
    assert devices[0]["record_count"] == 2
    assert devices[0]["dat_count"] == 1


def test_list_devices_search(data_db):
    db, _ = data_db
    _, total = qr.list_devices(db, q="acme")
    assert total == 1
    _, total = qr.list_devices(db, q="khong-co")
    assert total == 0
