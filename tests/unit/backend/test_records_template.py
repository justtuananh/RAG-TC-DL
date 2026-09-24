"""Cấu hình ánh xạ trường dựng từ Phụ lục A ĐÃ DUYỆT (P3) — Sprint 7."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from db.models import (
    Base,
    Document,
    DocumentType,
    Extraction,
    ExtractionStatus,
    Procedure,
    ProcedureFact,
)
from db.views import create_all_approved_views
from records.template import (
    HeaderField,
    MappingConfig,
    ResultTable,
    TemplateError,
    derive_mapping_config,
    slugify,
    validate_mapping_config,
)

STEM = "QTKD_1.061_2021_ND_V2"


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        create_all_approved_views(connection)
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = factory()
    db.add(
        Document(
            id=STEM,
            file_stem=STEM,
            display_name=f"{STEM}.docx",
            ext="DOCX",
            doc_type=DocumentType.QTKD,
            sha256="0" * 64,
            size_bytes=1,
        )
    )
    db.add(Procedure(number="1.061", document_id=STEM))
    db.commit()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def _procedure(session) -> Procedure:
    return session.query(Procedure).filter(Procedure.number == "1.061").one()


def _add_appendix_fact(
    session,
    *,
    label: str,
    value_text: str | None = None,
    role: str = "header",
    status: ExtractionStatus = ExtractionStatus.APPROVED,
) -> int:
    procedure = _procedure(session)
    extraction = Extraction(
        document_id=STEM,
        section_path="Phụ lục A",
        quote=f"{label}: {value_text or ''}",
        extractor="rule:phuluc_a.v1",
        extractor_version="v1",
        confidence=0.9,
        status=status,
    )
    session.add(extraction)
    session.flush()
    session.add(
        ProcedureFact(
            extraction_id=extraction.id,
            procedure_id=procedure.id,
            fact_kind="appendix_field",
            label=label,
            value_text=value_text,
            condition_text=role,
        )
    )
    session.commit()
    return extraction.id


def test_slugify_strips_vietnamese_diacritics():
    assert slugify("Số hiệu") == "so_hieu"
    assert slugify("Nơi (hãng) sản xuất") == "noi_hang_san_xuat"
    assert slugify("Bảng A.1 - Xác định sai số") == "bang_a_1_xac_dinh_sai_so"


def test_derive_config_from_approved_facts(session):
    _add_appendix_fact(session, label="Số hiệu")
    _add_appendix_fact(session, label="Ngày kiểm định", value_text="15/01/2024")
    _add_appendix_fact(
        session,
        label="Bảng A.1 - Xác định sai số và độ chênh áp",
        value_text=json.dumps(
            {
                "title": "Bảng A.1",
                "columns": ["Lần kiểm tra", "Áp suất", "Sai số", "Ghi chú"],
                "header_rows": [],
            },
            ensure_ascii=False,
        ),
        role="table",
    )

    procedure = _procedure(session)
    config = derive_mapping_config(session, procedure_id=procedure.id, procedure_number="1.061")

    assert config.procedure_number == "1.061"
    assert {item.key for item in config.header_fields} == {"so_hieu", "ngay_kiem_dinh"}
    assert [table.key for table in config.result_tables] == [
        "bang_a_1_xac_dinh_sai_so_va_do_chenh_ap"
    ]
    assert config.result_tables[0].columns == [
        "Lần kiểm tra",
        "Áp suất",
        "Sai số",
        "Ghi chú",
    ]
    # P1: mỗi trường giữ fact_id và nguyên văn.
    assert all(item.fact_id > 0 for item in config.header_fields)
    assert config.header_fields[0].quote


def test_pending_appendix_facts_are_hidden(session):
    _add_appendix_fact(session, label="Số hiệu")
    _add_appendix_fact(session, label="Kết luận", status=ExtractionStatus.PENDING)

    procedure = _procedure(session)
    config = derive_mapping_config(session, procedure_id=procedure.id)
    labels = {item.label for item in config.header_fields}
    assert labels == {"Số hiệu"}  # dòng pending không lộ ra (P3)


def test_derive_without_approved_facts_raises(session):
    procedure = _procedure(session)
    with pytest.raises(TemplateError):
        derive_mapping_config(session, procedure_id=procedure.id)


def test_validate_rejects_duplicate_keys():
    config = MappingConfig(
        procedure_id=1,
        procedure_number="1.061",
        header_fields=[
            HeaderField(key="so_hieu", label="Số hiệu", fact_id=1),
            HeaderField(key="so_hieu", label="Serial", fact_id=2),
        ],
        result_tables=[],
    )
    with pytest.raises(TemplateError):
        validate_mapping_config(config)


def test_validate_rejects_empty_config():
    with pytest.raises(TemplateError):
        validate_mapping_config(
            MappingConfig(procedure_id=1, procedure_number=None, header_fields=[], result_tables=[])
        )


def test_validate_rejects_table_without_columns():
    config = MappingConfig(
        procedure_id=1,
        procedure_number=None,
        header_fields=[],
        result_tables=[ResultTable(key="bang", title="Bảng", columns=[], fact_id=3)],
    )
    with pytest.raises(TemplateError):
        validate_mapping_config(config)


def test_appendix_rule_extracts_fields_and_measurement_table(repo_root):
    from knowledge.rules import extract_appendix

    text = (repo_root / "build" / "spike_a" / f"{STEM}.md").read_text(encoding="utf-8")
    hits = extract_appendix(text)

    labels = {hit.label for hit in hits if hit.condition_text == "header"}
    assert "Số hiệu" in labels
    assert "Ngày kiểm định" in labels or "Phương pháp kiểm định" in labels

    tables = [hit for hit in hits if hit.condition_text == "table"]
    assert tables, "Phải nhận diện được bảng kết quả đo"
    assert all("Lần kiểm tra" in hit.value_text for hit in tables)


def test_appendix_facts_must_be_approved_before_config(session, repo_root):
    from knowledge.extract import extract_appendix_and_store

    document = session.query(Document).filter(Document.id == STEM).one()
    text = (repo_root / "build" / "spike_a" / f"{STEM}.md").read_text(encoding="utf-8")
    summary = extract_appendix_and_store(session, document, text)
    session.commit()
    assert summary.facts > 0

    procedure = _procedure(session)
    # P3: dữ kiện mới đang pending → chưa dựng được cấu hình.
    with pytest.raises(TemplateError):
        derive_mapping_config(session, procedure_id=procedure.id)

    # Duyệt toàn bộ dữ kiện Phụ lục A rồi mới dựng được.
    for extraction in session.query(Extraction).filter(Extraction.extractor == "rule:phuluc_a.v1"):
        extraction.status = ExtractionStatus.APPROVED
    session.commit()

    config = derive_mapping_config(session, procedure_id=procedure.id)
    assert config.header_fields
    assert config.result_tables
