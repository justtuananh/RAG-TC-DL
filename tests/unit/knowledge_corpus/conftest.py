"""Các fixture và helper dùng chung cho bộ test lớp tri thức trên corpus tổng hợp."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

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
)
from db.views import create_all_approved_views
from ingestion import spike_a
from knowledge.extract import ensure_procedure, extract_appendix_and_store
from knowledge.seed_data import seed_reference_data
from records.docx_reader import read_docx
from records.store import store_record_draft
from records.template import derive_mapping_config
from records.xlsx_reader import read_xlsx

# QTKĐ nguồn (nhóm A/B) cung cấp Phụ lục A đã duyệt cho từng số QTKĐ dùng trong
# hồ sơ nhóm D/E. B03 (9.015) là nguồn cho D13 (K07, bảng gộp ô).
PROC_SOURCE: dict[str, str] = {
    "9.001": "A01",
    "9.002": "A02",
    "9.003": "A03",
    "9.005": "A05",
    "9.015": "B03",
}

# Đường dẫn corpus
CORPUS_ROOT = Path(__file__).parent.parent.parent / "data" / "knowledge_corpus"
MANIFEST_FILE = CORPUS_ROOT / "manifest.jsonl"
KNOWN_BEHAVIORS_FILE = CORPUS_ROOT / "known_behaviors.json"
GOLD_EXTRACT_FILE = CORPUS_ROOT / "gold" / "extract_golden.jsonl"
GOLD_SECTION6_FILE = CORPUS_ROOT / "gold" / "extract_golden_section6.jsonl"
GOLD_RECORDS_FILE = CORPUS_ROOT / "gold" / "records_golden.jsonl"
FILES_DIR = CORPUS_ROOT / "files"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Nạp JSONL file; raise FileNotFoundError nếu file không tồn tại."""
    if not path.exists():
        raise FileNotFoundError(f"Corpus file not found: {path}")
    result = []
    with open(path) as f:
        for line in f:
            if line.strip():
                result.append(json.loads(line))
    return result


def load_manifest() -> dict[str, dict[str, Any]]:
    """Nạp manifest.jsonl; trả map id -> metadata. Raise nếu file thiếu."""
    manifest = {}
    if not MANIFEST_FILE.exists():
        raise FileNotFoundError(f"Corpus manifest not found: {MANIFEST_FILE}")
    for row in _read_jsonl(MANIFEST_FILE):
        manifest[row["id"]] = row
    return manifest


@pytest.fixture(scope="session")
def corpus_manifest() -> dict[str, dict[str, Any]]:
    """Fixture: nạp toàn bộ manifest (session-scoped)."""
    return load_manifest()


@pytest.fixture(scope="session")
def corpus_gold_extract() -> list[dict[str, Any]]:
    """Fixture: nạp toàn bộ extract_golden.jsonl (session-scoped)."""
    return _read_jsonl(GOLD_EXTRACT_FILE)


@pytest.fixture(scope="session")
def corpus_gold_section6() -> list[dict[str, Any]]:
    """Fixture: nạp toàn bộ extract_golden_section6.jsonl (session-scoped)."""
    return _read_jsonl(GOLD_SECTION6_FILE)


@pytest.fixture(scope="session")
def corpus_gold_records() -> list[dict[str, Any]]:
    """Fixture: nạp toàn bộ records_golden.jsonl (session-scoped)."""
    return _read_jsonl(GOLD_RECORDS_FILE)


@pytest.fixture(scope="session")
def corpus_file_paths() -> dict[str, Path]:
    """Fixture: trả map tên file -> Path; nạp từ FILES_DIR."""
    file_map = {}
    if FILES_DIR.exists():
        for path in FILES_DIR.iterdir():
            if path.is_file():
                file_map[path.name] = path
    return file_map


def _safe_stem(name: str) -> str:
    """Làm sạch tên file: bỏ extension, thay khoảng trắng bằng _."""
    stem = name.rsplit(".", 1)[0] if "." in name else name
    return "".join(c if c.isalnum() or c in "-._" else "_" for c in stem)


@pytest.fixture(scope="session")
def corpus_markdown(tmp_path_factory, corpus_manifest, corpus_file_paths) -> dict[str, str]:
    """Fixture: chạy ingestion.spike_a.process_one cho mỗi A/B/F .docx; trả map id -> markdown_text."""
    md_dir = tmp_path_factory.mktemp("corpus_md")
    result = {}

    for obj in corpus_manifest.values():
        manifest_id = obj["id"]
        group = obj["group"]
        file_name = obj["file"]

        # Chỉ process A/B/F docx files
        if group not in ["A", "B", "F"] or not file_name.lower().endswith(".docx"):
            continue

        file_path = corpus_file_paths[file_name]
        processed = spike_a.process_one(file_path, out_dir=md_dir)

        # Nạp Markdown được tạo
        if processed and processed.get("status") == "ok":
            stem = _safe_stem(file_name)
            markdown_path = md_dir / f"{stem}.md"
            if markdown_path.exists():
                result[manifest_id] = markdown_path.read_text(encoding="utf-8")

    return result


@pytest.fixture
def engine():
    """Fixture: engine SQLite in-memory."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        create_all_approved_views(connection)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def session_factory(engine):
    """Fixture: session factory."""
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


@pytest.fixture
def session(session_factory):
    """Fixture: session với seed reference data."""
    db = session_factory()
    seed_reference_data(db)
    try:
        yield db
    finally:
        db.close()


def _build_qtkd_config(session, corpus_manifest, corpus_markdown, source_id: str):
    """Dựng Document QTKĐ nguồn + duyệt hết ``appendix_field`` + trả MappingConfig.

    Chạy pipeline thật: ``extract_appendix_and_store`` (luật) rồi duyệt (APPROVED)
    toàn bộ extraction Phụ lục A của tài liệu, sau đó ``derive_mapping_config``
    (chỉ đọc view đã duyệt, đúng P3) — y hệt luồng thật ``records/ingest.py`` dùng.
    """
    obj = corpus_manifest[source_id]
    md_text = corpus_markdown[source_id]
    document = Document(
        id=source_id,
        file_stem=source_id,
        display_name=obj["file"],
        ext="DOCX",
        doc_type=DocumentType.QTKD,
        sha256=hashlib.sha256(source_id.encode()).hexdigest(),
        size_bytes=1,
    )
    session.add(document)
    session.flush()

    extract_appendix_and_store(session, document, md_text)
    session.flush()
    for extraction in session.query(Extraction).filter(Extraction.document_id == document.id).all():
        extraction.status = ExtractionStatus.APPROVED
    session.flush()

    procedure = ensure_procedure(session, document, md_text)
    config = derive_mapping_config(
        session, procedure_id=procedure.id, procedure_number=procedure.number
    )
    return procedure, config


def _build_all_configs(session, corpus_manifest, corpus_markdown):
    """Dựng MappingConfig cho mọi QTKĐ nguồn trong ``PROC_SOURCE``; trả
    ``(procedures, configs)``, cả hai khoá theo ``procedure_number``."""
    configs: dict[str, Any] = {}
    procedures: dict[str, Any] = {}
    for procedure_number, source_id in PROC_SOURCE.items():
        procedure, config = _build_qtkd_config(session, corpus_manifest, corpus_markdown, source_id)
        configs[procedure_number] = config
        procedures[procedure_number] = procedure
    session.commit()
    return procedures, configs


def _ingest_one_de_record(session, corpus_file_paths, manifest_id, obj, procedure, config):
    """Đọc + ghi MỘT hồ sơ D/E vào ``session`` đang mở; trả ``(draft, result)``."""
    file_path = corpus_file_paths[obj["file"]]
    reader = read_docx if file_path.suffix.lower() == ".docx" else read_xlsx
    draft = reader(file_path, config)

    doc_type = DocumentType.HO_SO_KIEM_DINH if obj["group"] == "D" else DocumentType.PHIEU_DO
    document = Document(
        id=manifest_id,
        file_stem=manifest_id,
        display_name=obj["file"],
        ext=file_path.suffix.lstrip(".").upper(),
        doc_type=doc_type,
        sha256=hashlib.sha256(manifest_id.encode()).hexdigest(),
        size_bytes=1,
    )
    session.add(document)
    session.flush()
    result = store_record_draft(session, document=document, draft=draft, procedure=procedure)
    return draft, result


@pytest.fixture(scope="module")
def records_db(corpus_manifest, corpus_markdown, corpus_file_paths):
    """Nạp toàn bộ hồ sơ nhóm D/E vào MỘT CSDL SQLite in-memory dùng chung.

    Pipeline thật cho từng QTKĐ nguồn (A01/A02/A03/A05/B03): trích Phụ lục A bằng
    luật, duyệt, dựng ``MappingConfig``. Rồi với mỗi file D/E: đọc bằng
    ``read_docx``/``read_xlsx`` theo config của đúng QTKĐ áp dụng
    (``procedure_number`` trong manifest), ghi bằng ``store_record_draft``.

    Trả dict: ``session``, ``results`` (id -> ``StoreResult``),
    ``drafts`` (id -> ``RecordDraft``), ``configs`` (procedure_number -> config).
    Scope ``module`` — dựng một lần, dùng lại cho mọi test tham số hoá trong cùng
    file test (T7/T8 dùng module riêng nên không chia sẻ giữa hai file).
    """
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        create_all_approved_views(connection)
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = factory()
    seed_reference_data(session)

    procedures, configs = _build_all_configs(session, corpus_manifest, corpus_markdown)

    drafts: dict[str, Any] = {}
    results: dict[str, Any] = {}
    for manifest_id, obj in sorted(corpus_manifest.items()):
        if obj["group"] not in ("D", "E"):
            continue
        procedure_number = obj["procedure_number"]
        draft, result = _ingest_one_de_record(
            session,
            corpus_file_paths,
            manifest_id,
            obj,
            procedures[procedure_number],
            configs[procedure_number],
        )
        drafts[manifest_id] = draft
        results[manifest_id] = result
    session.commit()

    try:
        yield {
            "session": session,
            "configs": configs,
            "procedures": procedures,
            "drafts": drafts,
            "results": results,
        }
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def known_behavior_entry(
    manifest: dict, code: str, *, manifest_id: str | None = None
) -> dict | None:
    """Trả entry ``known_behaviors`` khớp mã K; ``None`` nếu không có.

    Nếu ``manifest_id`` được cho, ưu tiên entry của CHÍNH file đó (để lý do xfail
    phản ánh đúng file đang kiểm, ví dụ K05 xuất hiện ở cả D04 lẫn E07 với giá trị
    "current"/"expected" khác nhau); nếu không có ở đó (hoặc không truyền), lấy
    entry đầu tiên tìm thấy trong toàn manifest.
    """
    if manifest_id is not None:
        for behavior in manifest.get(manifest_id, {}).get("known_behaviors", []):
            if behavior["code"] == code:
                return behavior
    for obj in manifest.values():
        for behavior in obj.get("known_behaviors", []):
            if behavior["code"] == code:
                return behavior
    return None


def xfail_for(
    manifest: dict,
    code: str,
    *,
    fallback: str | None = None,
    manifest_id: str | None = None,
) -> pytest.MarkDecorator:
    """``pytest.mark.xfail(strict=True)`` với lý do lấy từ ``known_behaviors``.

    ``fallback`` dùng cho các mã hành vi toàn cục (ví dụ K09) không gắn vào một
    file cụ thể trong manifest — lý do vẫn phải chứa mã K (yêu cầu nghiệm thu).
    ``manifest_id``: xem ``known_behavior_entry``.

    Nếu mã đã có ``fixed`` trong manifest, hàm ném ``AssertionError`` để chặn
    xfail cũ sót lại sau khi sửa.
    """
    entry = known_behavior_entry(manifest, code, manifest_id=manifest_id)
    if entry is not None and entry.get("fixed"):
        raise AssertionError(
            f"Mã {code} đã được sửa ({entry['fixed']}) nhưng vẫn còn xfail; hãy gỡ xfail của mã này"
        )
    if entry is not None:
        reason = f"{code}: {entry['current']} -> {entry['expected']}"
    elif fallback is not None:
        reason = f"{code}: {fallback}"
    else:  # pragma: no cover - lỗi cấu hình test, không phải hành vi sản phẩm
        raise AssertionError(f"Không tìm thấy mã {code} trong manifest và không có fallback")
    return pytest.mark.xfail(strict=True, reason=reason)
