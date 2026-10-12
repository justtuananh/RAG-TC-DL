"""Fixture + helper cho bộ test corpus tổng hợp (``tests/data/knowledge_corpus``).

Chỉ giữ phần còn dùng sau khi gỡ luồng trích xuất tri thức: nạp manifest, đường
dẫn tệp corpus, Markdown nhóm A/B/F và một session SQLite tối thiểu cho
``ingestion.jobs``. KHÔNG import ``db.views`` / ``records`` / ``knowledge.extract``
(những phần đã bị xóa).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from db.models import Base
from ingestion import spike_a

# Đường dẫn corpus
CORPUS_ROOT = Path(__file__).parent.parent.parent / "data" / "knowledge_corpus"
MANIFEST_FILE = CORPUS_ROOT / "manifest.jsonl"
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
def corpus_file_paths() -> dict[str, Path]:
    """Fixture: trả map tên file -> Path; nạp từ FILES_DIR."""
    file_map = {}
    if FILES_DIR.exists():
        for path in FILES_DIR.iterdir():
            if path.is_file():
                file_map[path.name] = path
    return file_map


def _safe_stem(name: str) -> str:
    """Làm sạch tên file: bỏ extension, thay ký tự lạ bằng _ (khớp spike_a._safe)."""
    stem = name.rsplit(".", 1)[0] if "." in name else name
    return "".join(c if c.isalnum() or c in "-._" else "_" for c in stem)


@pytest.fixture(scope="session")
def corpus_markdown(tmp_path_factory, corpus_manifest, corpus_file_paths) -> dict[str, str]:
    """Fixture: chạy ``ingestion.spike_a.process_one`` cho mỗi A/B/F .docx."""

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
def session():
    """SQLite in-memory tối thiểu cho ``ingestion.jobs`` (chỉ bảng ``db.models.Base``)."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = factory()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()
