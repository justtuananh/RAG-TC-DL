"""Router đọc alias thiết bị từ DB, có bộ nhớ đệm, có dự phòng khi DB vắng.

Bảo vệ cổng Sprint 3: eval truy hồi không tụt sau khi đổi nguồn alias.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import retrieval.router as router_mod
from db.models import Base, DeviceType, Procedure
from knowledge.reference import device_alias_map
from knowledge.seed_data import DEVICE_TYPES, KNOWN_PROCEDURE_DEVICE_TYPES, seed_reference_data

MAPPING = {
    "1.061": "QTKD_1.061_2021_ND_V2",
    "1.063": "QTKD_1.063_2021_BPL",
    "1.159": "QTKD_1.159_2021_ND_FINAL",
    "1.160": "QTKD_1.160_2021_ND_FINAL",
    "1.190": "2023._QTKD_1.190_2023_DPI_610_ND_24.01.24",
}


@pytest.fixture
def stem_mapping(monkeypatch):
    monkeypatch.setattr(router_mod, "_number_to_stem", dict(MAPPING))
    return MAPPING


def test_fallback_used_when_db_unavailable(stem_mapping, monkeypatch):
    monkeypatch.setattr(router_mod, "_load_db_device_aliases", lambda: None)
    monkeypatch.setattr(router_mod, "_device_aliases", None)

    assert router_mod.route("kiểm định van an toàn") == MAPPING["1.061"]
    assert router_mod.route("dpi 610") == MAPPING["1.190"]
    assert router_mod.route("akkđ là gì") == MAPPING["1.160"]


def test_db_aliases_used_when_available(stem_mapping, monkeypatch):
    monkeypatch.setattr(
        router_mod,
        "_load_db_device_aliases",
        lambda: {"dpi 610": ("1.190",), "van an toàn": ("1.061",)},
    )
    monkeypatch.setattr(router_mod, "_device_aliases", None)

    assert router_mod.route("dpi 610") == MAPPING["1.190"]
    assert router_mod.route_files("van an toàn") == frozenset({MAPPING["1.061"]})


def test_alias_pointing_to_two_procedures_is_ambiguous(stem_mapping, monkeypatch):
    # Một loại thiết bị dùng cho hai QTKĐ → không ghim file nào (rơi về toàn kho).
    monkeypatch.setattr(
        router_mod,
        "_load_db_device_aliases",
        lambda: {"van an toàn": ("1.061", "1.063")},
    )
    monkeypatch.setattr(router_mod, "_device_aliases", None)

    assert router_mod.route_files("kiểm định van an toàn") == frozenset(
        {MAPPING["1.061"], MAPPING["1.063"]}
    )
    assert router_mod.route("kiểm định van an toàn") is None


def test_ensure_device_aliases_caches(stem_mapping, monkeypatch):
    calls = {"n": 0}

    def fake_loader():
        calls["n"] += 1
        return {"dpi 610": ("1.190",)}

    monkeypatch.setattr(router_mod, "_load_db_device_aliases", fake_loader)
    monkeypatch.setattr(router_mod, "_device_aliases", None)

    assert router_mod.route("dpi 610") == MAPPING["1.190"]
    assert router_mod.route("dpi 610") == MAPPING["1.190"]
    assert calls["n"] == 1


def test_router_uses_real_device_alias_map(stem_mapping, monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = factory()
    try:
        seed_reference_data(db)
        by_name = {row.name_vi: row for row in db.query(DeviceType).all()}
        for number, name in KNOWN_PROCEDURE_DEVICE_TYPES.items():
            db.add(Procedure(number=number, device_type_id=by_name[name].id))
        db.commit()

        monkeypatch.setattr(router_mod, "_load_db_device_aliases", lambda: device_alias_map(db))
        monkeypatch.setattr(router_mod, "_device_aliases", None)

        assert router_mod.route("kiểm định bình phân ly") == MAPPING["1.063"]
        assert router_mod.route("áp kế píttông tiêu chuẩn") == MAPPING["1.159"]
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_seeded_device_types_match_router_fallback_aliases():
    """Bảo đảm seed không bỏ sót alias nào của router cũ."""
    seeded: dict[str, str] = {}
    for row in DEVICE_TYPES:
        for alias in [row["name_vi"], *row["aliases"]]:
            seeded.setdefault(alias.lower(), row["name_vi"])
    for alias in router_mod._FALLBACK_DEVICE_ALIASES:
        assert alias in seeded, alias
