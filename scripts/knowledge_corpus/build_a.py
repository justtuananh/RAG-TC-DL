"""Dựng nhóm A: 12 QTKĐ docx sạch -- đường cơ sở cho precision/recall (Pha 2 §2)."""

from __future__ import annotations

from ingestion.spike_a import _safe
from scripts.knowledge_corpus import gold_a
from scripts.knowledge_corpus import ooxml as ox
from scripts.knowledge_corpus.devices_a import DEVICES
from scripts.knowledge_corpus.qtkd_doc import build_qtkd_blocks
from scripts.knowledge_corpus.specs_io import FILES_DIR, FileRecord


def _slug_no_diacritics(text: str) -> str:
    import unicodedata

    normalized = unicodedata.normalize("NFD", text)
    stripped = "".join(c for c in normalized if unicodedata.category(c) != "Mn")
    return stripped.replace("đ", "d").replace("Đ", "D")


def device_filename(dev: dict) -> str:
    short = _slug_no_diacritics(dev["short"]).replace(" ", " ")
    return f"QTKĐ {dev['number']} 2026 {short}.docx"


def build_group_a() -> list[FileRecord]:
    """Trả danh sách ``FileRecord`` nhóm A (gold suy trực tiếp từ spec, R1)."""
    records: list[FileRecord] = []
    for i, dev in enumerate(DEVICES, start=1):
        file_id = f"A{i:02d}"
        filename = device_filename(dev)
        path = FILES_DIR / filename
        blocks = build_qtkd_blocks(dev)
        ox.write_docx(path, blocks)
        stem = _safe(path.stem)

        extract_golden = gold_a.golden_rows_for_doc(stem, dev)
        section6_golden = gold_a.section6_golden_rows_for_doc(stem, dev)

        records.append(
            FileRecord(
                id=file_id,
                file=filename,
                group="A",
                expected_doc_type="qtkd",
                expected_ingest="ok",
                procedure_number=dev["number"],
                purpose=f"QTKĐ sạch cho {dev['short']} ({dev['title']}) -- đường cơ sở nhóm A.",
                spec={"kind": "qtkd", "device": dev, "doc_stem": stem},
                extract_golden=extract_golden,
                section6_golden=section6_golden,
            )
        )
    return records
