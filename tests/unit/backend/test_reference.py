"""Khung khái niệm đã seed + ánh xạ alias thiết bị (knowledge.reference)."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from db.models import Base, DeviceType, Procedure
from knowledge.reference import (
    device_alias_map,
    device_type_aliases,
    load_device_types,
    load_quantities,
    procedure_device_type_map,
)
from knowledge.seed_data import DEVICE_TYPES, KNOWN_PROCEDURE_DEVICE_TYPES, seed_reference_data
from retrieval.router import _FALLBACK_DEVICE_ALIASES


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
    seed_reference_data(db)
    _create_procedures(db)
    db.commit()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def _create_procedures(session) -> None:
    by_name = {row.name_vi: row for row in session.query(DeviceType).all()}
    for number, name in KNOWN_PROCEDURE_DEVICE_TYPES.items():
        device_type = by_name[name]
        session.add(
            Procedure(
                number=number,
                year=2021,
                title=f"QTKĐ {number}",
                device_type_id=device_type.id,
                document_id=None,
            )
        )


def test_seed_counts(session):
    assert len(load_quantities(session)) == 6
    assert len(load_device_types(session)) == len(DEVICE_TYPES) == 7


def test_device_type_aliases_include_name_and_dedupe(session):
    device_type = session.query(DeviceType).filter(DeviceType.name_vi == "Van an toàn").one()
    aliases = device_type_aliases(device_type)
    assert "van an toàn" in aliases
    assert len(aliases) == len(set(aliases))


def test_device_alias_map_maps_every_known_number(session):
    mapping = device_alias_map(session)
    assert mapping["van an toàn"] == ("1.061",)
    assert mapping["bàn tạo áp"] == ("1.062",)
    assert mapping["bình phân ly"] == ("1.063",)
    assert mapping["h3000"] == ("1.071",)
    assert mapping["áp kế píttông tiêu chuẩn"] == ("1.159",)
    assert mapping["akkđ"] == ("1.160",)
    assert mapping["dpi 610"] == ("1.190",)


def test_device_alias_map_covers_router_fallback(session):
    """Mọi alias dự phòng của router phải có trong DB và trỏ đúng QTKĐ.

    Đây là hàng rào giữ eval truy hồi không tụt khi router đổi nguồn alias.
    """
    mapping = device_alias_map(session)
    for alias, number in _FALLBACK_DEVICE_ALIASES.items():
        assert alias in mapping, alias
        assert number in mapping[alias], (alias, number, mapping[alias])


def test_known_procedure_device_types_all_exist(session):
    names = {row.name_vi for row in session.query(DeviceType).all()}
    assert set(KNOWN_PROCEDURE_DEVICE_TYPES.values()) <= names


def test_procedure_device_type_map(session):
    result = procedure_device_type_map(session)
    assert result["1.061"] == "Van an toàn"
    assert result["1.190"] == "Thiết bị hiệu chuẩn áp suất"
