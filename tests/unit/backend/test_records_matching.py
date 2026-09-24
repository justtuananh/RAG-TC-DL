"""Đối sánh thiết bị theo loại + serial (Sprint 7).

Hai điều bắt buộc: không gộp nhầm hai serial khác nhau, và không tách đôi cùng
một serial viết khác kiểu hoa/thường. Thiếu serial → thiết bị tạm cờ
``needs_identification``, mỗi hồ sơ một thiết bị.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from db.models import Base, Device, DeviceType
from records.matching import find_device, find_or_create_device, normalize_serial


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = factory()
    db.add(DeviceType(name_vi="Van an toàn"))
    db.add(DeviceType(name_vi="Áp kế"))
    db.commit()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def _type_id(session, name: str) -> int:
    return session.query(DeviceType).filter(DeviceType.name_vi == name).one().id


def test_normalize_serial_casefolds_and_collapses_spaces():
    assert normalize_serial("  abC-123 ") == "abc-123"
    assert normalize_serial("ABC\u00a0123") == "abc 123"
    assert normalize_serial("") is None
    assert normalize_serial(None) is None


def test_same_serial_different_case_is_not_split(session):
    type_id = _type_id(session, "Van an toàn")
    first = find_or_create_device(session, device_type_id=type_id, serial_no="ABC-123")
    second = find_or_create_device(session, device_type_id=type_id, serial_no="abc-123 ")
    session.commit()

    assert first.id == second.id
    assert session.query(Device).count() == 1
    # Bản ghi giữ nguyên văn serial như lần đầu.
    assert first.serial_no == "ABC-123"
    assert first.serial_norm == "abc-123"


def test_different_serials_are_not_merged(session):
    type_id = _type_id(session, "Van an toàn")
    first = find_or_create_device(session, device_type_id=type_id, serial_no="ABC-123")
    second = find_or_create_device(session, device_type_id=type_id, serial_no="ABC-124")
    session.commit()

    assert first.id != second.id
    assert session.query(Device).count() == 2


def test_same_serial_different_device_type_is_not_merged(session):
    first = find_or_create_device(
        session, device_type_id=_type_id(session, "Van an toàn"), serial_no="X-1"
    )
    second = find_or_create_device(
        session, device_type_id=_type_id(session, "Áp kế"), serial_no="X-1"
    )
    session.commit()
    assert first.id != second.id


def test_missing_serial_creates_flagged_device_each_time(session):
    type_id = _type_id(session, "Van an toàn")
    first = find_or_create_device(session, device_type_id=type_id, serial_no=None)
    second = find_or_create_device(session, device_type_id=type_id, serial_no="   ")
    session.commit()

    assert first.id != second.id  # không gộp hai thiết bị khác nhau
    assert first.needs_identification == 1
    assert second.needs_identification == 1
    assert first.serial_no is None
    assert find_device(session, device_type_id=type_id, serial_no=None) is None


def test_find_device_matches_normalized_serial(session):
    type_id = _type_id(session, "Van an toàn")
    device = find_or_create_device(session, device_type_id=type_id, serial_no="SN-9")
    session.commit()
    assert find_device(session, device_type_id=type_id, serial_no="sn-9").id == device.id
