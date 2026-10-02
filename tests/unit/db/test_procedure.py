"""Đọc đầu mục QTKĐ và sinh procedure (knowledge.procedure + script)."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from db.models import Base, Document, DocumentType, Procedure
from knowledge.procedure import (
    infer_device_type,
    parse_edition,
    parse_procedure_header,
)
from knowledge.seed_data import DEVICE_TYPES, KNOWN_PROCEDURE_DEVICE_TYPES, seed_reference_data
from scripts.generate_procedures import apply_procedure_plan, build_procedure_plan

# file_stem → (số QTKĐ, năm, mảnh tiêu đề đặc trưng)
EXPECTED = {
    "QTKD_1.061_2021_ND_V2": ("1.061", 2021, "VAN AN TOÀN"),
    "QTKD_1.062_2021_ND": ("1.062", 2021, "BÀN TẠO ÁP"),
    "QTKD_1.063_2021_BPL": ("1.063", 2021, "BÌNH PHÂN LY"),
    "QTKD_1.071_2022_FINAL": ("1.071", 2022, "ÁP KẾ PÍT TÔNG"),
    "QTKD_1.159_2021_ND_FINAL": ("1.159", 2021, "ÁP KẾ PÍTTÔNG"),
    "QTKD_1.160_2021_ND_FINAL": ("1.160", 2021, "ÁP KẾ CHUẨN HIỆN SỐ"),
    "2023._QTKD_1.190_2023_DPI_610_ND_24.01.24": (
        "1.190",
        2023,
        "THIẾT BỊ HIỆU CHUẨN ÁP SUẤT",
    ),
}


@pytest.fixture(scope="module")
def md_dir(repo_root):
    return repo_root / "build" / "spike_a"


def _candidates() -> list[tuple[str, list[str]]]:
    return [(row["name_vi"], [row["name_vi"], *row["aliases"]]) for row in DEVICE_TYPES]


@pytest.mark.parametrize("stem, expected", EXPECTED.items())
def test_parse_headers_from_corpus(md_dir, stem, expected):
    number, year, title_fragment = expected
    text = (md_dir / f"{stem}.md").read_text(encoding="utf-8")
    header = parse_procedure_header(text)
    assert header is not None
    assert header.number == number
    assert header.year == year
    assert title_fragment in header.title.upper()


@pytest.mark.parametrize(
    "stem, edition",
    [
        ("QTKD_1.061_2021_ND_V2", "ND_V2"),
        ("QTKD_1.071_2022_FINAL", "FINAL"),
        ("QTKD_1.063_2021_BPL", "BPL"),
        ("2023._QTKD_1.190_2023_DPI_610_ND_24.01.24", "DPI_610_ND_24.01.24"),
    ],
)
def test_parse_edition(stem, edition):
    assert parse_edition(stem) == edition


def test_parse_edition_absent():
    assert parse_edition("khong_co_ma") is None


def test_infer_device_type_prefers_distinctive_alias():
    candidates = _candidates()
    assert (
        infer_device_type("ÁP KẾ PÍT TÔNG KIỂU H3000-SP-70/700", candidates)
        == "Áp kế píttông kiểu H3000"
    )
    assert (
        infer_device_type("THIẾT BỊ HIỆU CHUẨN ÁP SUẤT KIỂU DPI 610", candidates)
        == "Thiết bị hiệu chuẩn áp suất"
    )
    assert infer_device_type("VAN AN TOÀN CÓ PHẠM VI LÀM VIỆC", candidates) == "Van an toàn"


def test_infer_device_type_returns_none_for_unknown_title():
    assert infer_device_type("MỘT THIẾT BỊ LẠ KHÔNG CÓ ALIAS", _candidates()) is None


@pytest.mark.parametrize("code", ["QTKD", "QTKĐ", "qtkd", "qtkđ"])
def test_parse_procedure_header_accepts_qtkd_with_or_without_d(code):
    """K11: dòng mã nhận cả ``QTKD`` (không dấu Đ) lẫn ``QTKĐ``, mọi kiểu hoa thường."""
    md = f"{code} 9.013 : 2026\nVAN AN TOAN\nQUY TRINH KIEM DINH\n"
    header = parse_procedure_header(md)
    assert header is not None
    assert header.number == "9.013"
    assert header.year == 2026
    assert header.title.startswith("VAN AN TOAN")


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
    for index, (stem, _meta) in enumerate(EXPECTED.items()):
        db.add(
            Document(
                id=stem,
                file_stem=stem,
                display_name=f"{stem}.docx",
                ext="DOCX",
                doc_type=DocumentType.QTKD,
                sha256=f"{index:064d}",
                size_bytes=1,
            )
        )
    db.commit()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_build_and_apply_procedure_plan(session, md_dir):
    plans = build_procedure_plan(session, md_dir)
    assert len(plans) == len(EXPECTED)
    assert all(plan.action == "create" for plan in plans)

    written = apply_procedure_plan(session, plans)
    session.commit()
    assert written == len(EXPECTED)

    rows = {row.number: row for row in session.query(Procedure).all()}
    assert set(rows) == {number for number, _, _ in EXPECTED.values()}
    for number, device_type_name in KNOWN_PROCEDURE_DEVICE_TYPES.items():
        assert rows[number].device_type is not None
        assert rows[number].device_type.name_vi == device_type_name
        assert rows[number].document_id is not None  # P1: truy nguyên tài liệu


def test_build_procedure_plan_is_idempotent(session, md_dir):
    plans = build_procedure_plan(session, md_dir)
    apply_procedure_plan(session, plans)
    session.commit()

    second = build_procedure_plan(session, md_dir)
    assert all(plan.action == "update" for plan in second)
    apply_procedure_plan(session, second)
    session.commit()
    assert session.query(Procedure).count() == len(EXPECTED)
