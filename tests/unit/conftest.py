"""Fixture CSDL SQLite tối thiểu cho test đơn vị cần DB.

Chỉ dựng các bảng còn lại (``db.models.Base``) và một bộ dữ liệu nhỏ đủ để kiểm
tra nhận diện loại thiết bị / procedure của router văn bản.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from db.models import Base, DeviceType, Document, DocumentType, Procedure, Quantity, Unit

QTKD_STEM = "QTKD_1.061_2021_ND_V2"


def seed_dataset(session) -> dict:
    """Seed một QTKĐ nhỏ (Van an toàn) đã gắn loại thiết bị; trả dict id."""
    quantity = Quantity(code="pressure", name_vi="Áp suất", si_unit_code="Pa")
    session.add(quantity)
    session.flush()
    unit = Unit(
        code="bar", name_vi="Bar", quantity_id=quantity.id, factor_to_si=100000.0, offset_to_si=0.0
    )
    device_type = DeviceType(name_vi="Van an toàn", quantity_id=quantity.id)
    session.add_all([unit, device_type])
    session.flush()
    session.add(
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
    session.flush()
    procedure = Procedure(
        number="1.061",
        year=2021,
        title="Van an toàn",
        document_id=QTKD_STEM,
        device_type_id=device_type.id,
    )
    session.add(procedure)
    session.commit()
    return {
        "quantity_id": quantity.id,
        "device_type_id": device_type.id,
        "procedure_id": procedure.id,
    }


def _new_session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    return engine, factory


@pytest.fixture
def data_factory():
    """Trả ``(sessionmaker, ids)`` cho CSDL tối thiểu đã seed."""
    engine, factory = _new_session()
    bootstrap = factory()
    try:
        ids = seed_dataset(bootstrap)
    finally:
        bootstrap.close()
    try:
        yield factory, ids
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def data_db(data_factory):
    """Trả ``(session, ids)`` cho CSDL tối thiểu đã seed."""
    factory, ids = data_factory
    session = factory()
    try:
        yield session, ids
    finally:
        session.close()
