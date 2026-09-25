"""Kiểu dữ liệu dùng chung + ghi specs/gold/manifest tất định.

``FileRecord`` là mô tả đầy đủ MỘT file đầu ra: đủ để ``build.py`` vừa ghi file
nhị phân, vừa ghi spec JSON, vừa góp dòng vào gold/manifest -- một nguồn duy
nhất, tránh lặp giữa các bước (spec Pha 2: "gold suy ra từ spec").
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT / "tests" / "data" / "knowledge_corpus"
SPECS_DIR = DATA_DIR / "specs"
FILES_DIR = DATA_DIR / "files"
GOLD_DIR = DATA_DIR / "gold"
# Nguồn TĨNH cho ``known_behaviors``: builder KHÔNG được chạy code sản phẩm để đo
# hành vi lúc build (làm vậy thì rebuild sau khi sửa lỗi sẽ ghi đè ``current`` và
# xoá cờ ``fixed``). File này chép nguyên văn từ manifest trước khi sửa.
KNOWN_BEHAVIORS_FILE = DATA_DIR / "known_behaviors.json"


def load_known_behaviors() -> dict[str, list[dict]]:
    """Nạp bản đồ ``id`` -> danh sách hành vi đã biết từ file tĩnh."""
    return json.loads(KNOWN_BEHAVIORS_FILE.read_text(encoding="utf-8"))


def known_behaviors_for(record_id: str) -> list[dict]:
    """Danh sách ``known_behaviors`` của một file đầu ra; bản sao để tránh sửa
    nhầm nguồn tĩnh."""
    return [dict(item) for item in load_known_behaviors().get(record_id, [])]


@dataclass
class FileRecord:
    """Một file đầu ra của bộ dữ liệu test + mọi thứ suy ra được từ nó."""

    id: str
    file: str
    group: str
    expected_doc_type: str
    expected_ingest: str
    procedure_number: str | None
    purpose: str
    spec: dict
    known_behaviors: list[dict] = field(default_factory=list)
    extract_golden: list[dict] = field(default_factory=list)
    section6_golden: list[dict] = field(default_factory=list)
    records_golden: dict | None = None

    def manifest_row(self) -> dict:
        return {
            "id": self.id,
            "file": self.file,
            "group": self.group,
            "expected_doc_type": self.expected_doc_type,
            "expected_ingest": self.expected_ingest,
            "procedure_number": self.procedure_number,
            "purpose": self.purpose,
            "known_behaviors": self.known_behaviors,
        }


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(row, ensure_ascii=False) for row in rows]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def write_outputs(records: list[FileRecord]) -> None:
    """Ghi specs/*.json, manifest.jsonl, gold/*.jsonl từ danh sách ``FileRecord``."""
    SPECS_DIR.mkdir(parents=True, exist_ok=True)
    for record in records:
        spec_path = SPECS_DIR / f"{record.id}.json"
        spec_path.write_text(
            json.dumps(record.spec, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
            encoding="utf-8",
        )

    _write_jsonl(DATA_DIR / "manifest.jsonl", [r.manifest_row() for r in records])

    extract_golden = [row for r in records for row in r.extract_golden]
    section6_golden = [row for r in records for row in r.section6_golden]
    records_golden = [r.records_golden for r in records if r.records_golden is not None]
    _write_jsonl(GOLD_DIR / "extract_golden.jsonl", extract_golden)
    _write_jsonl(GOLD_DIR / "extract_golden_section6.jsonl", section6_golden)
    _write_jsonl(GOLD_DIR / "records_golden.jsonl", records_golden)
