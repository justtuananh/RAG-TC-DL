"""Dựng nhóm C (QTKĐ pdf), F (trùng/phiên bản) và G (legacy .doc/.xls)."""

from __future__ import annotations

import copy
import hashlib
import shutil
import subprocess
import tempfile
from pathlib import Path

from scripts.knowledge_corpus import ooxml as ox
from scripts.knowledge_corpus.devices_a import DEVICES
from scripts.knowledge_corpus.qtkd_doc import build_qtkd_blocks
from scripts.knowledge_corpus.specs_io import (
    FILES_DIR,
    FileRecord,
    known_behaviors_for,
)

SOFFICE = "/usr/bin/soffice"
_C_NUMBERS = ["9.001", "9.002", "9.003"]


def _soffice_convert(src: Path, out_ext: str) -> Path | None:
    try:
        subprocess.run(
            [SOFFICE, "--headless", "--convert-to", out_ext, "--outdir", str(src.parent), str(src)],
            check=True,
            capture_output=True,
            timeout=60,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as exc:
        print(f"  [soffice] bỏ qua chuyển {src.name} -> {out_ext}: {exc}")
        return None
    return src.with_suffix(f".{out_ext}")


def build_group_c(a_records: list, run_soffice: bool) -> list[FileRecord]:
    """PDF sinh trực tiếp cạnh nguồn trong ``FILES_DIR`` (không có bản trung gian).

    Chỉ thêm vào manifest khi PDF THỰC SỰ tồn tại sau khi chuyển đổi, để
    ``files/`` và manifest luôn khớp nhau ở cả hai chế độ ``--no-soffice``.
    """
    if not run_soffice:
        return []
    records: list[FileRecord] = []
    by_number = {r.procedure_number: r for r in a_records}
    for i, number in enumerate(_C_NUMBERS, start=1):
        src_file = by_number[number]
        src_path = FILES_DIR / src_file.file
        pdf_path = _soffice_convert(src_path, "pdf")
        if pdf_path is None or not pdf_path.exists():
            continue
        records.append(
            FileRecord(
                id=f"C{i:02d}",
                file=pdf_path.name,
                group="C",
                expected_doc_type="qtkd",
                expected_ingest="ok",
                procedure_number=number,
                purpose=f"Bản PDF (soffice) của {src_file.file} -- có lớp văn bản.",
                spec={"kind": "qtkd_pdf", "source_file": src_file.file, "procedure_number": number},
            )
        )
    return records


def build_group_f(a_records: list) -> list[FileRecord]:
    records: list[FileRecord] = []
    dev0 = a_records[0]
    src_path = FILES_DIR / dev0.file

    # F1: trùng hash -- copy byte-for-byte dưới tên khác.
    dup_name = "Danh muc QTKD 9.001 sao luu.docx"
    dup_path = FILES_DIR / dup_name
    shutil.copyfile(src_path, dup_path)
    same_hash = (
        hashlib.sha256(src_path.read_bytes()).hexdigest()
        == hashlib.sha256(dup_path.read_bytes()).hexdigest()
    )
    records.append(
        FileRecord(
            id="F01",
            file=dup_name,
            group="F",
            expected_doc_type="qtkd",
            expected_ingest="duplicate",
            procedure_number="9.001",
            purpose=f"Trùng byte-for-byte với {dev0.file} (tên khác) -- kiểm tra chặn theo sha256.",
            spec={"kind": "duplicate", "source_file": dev0.file, "sha256_equal": same_hash},
        )
    )

    # F2: QTKĐ 9.001 phiên bản 2 -- cùng số hiệu, nội dung sửa đổi.
    dev_v2 = copy.deepcopy(DEVICES[0])
    dev_v2["interval_months"] = 6
    dev_v2["range"] = dict(dev_v2["range"], value_text="đến 1 600 bar")
    blocks_v2 = build_qtkd_blocks(dev_v2)
    v2_name = "QTKĐ 9.001 2026 Van an toan Phien ban 2.docx"
    ox.write_docx(FILES_DIR / v2_name, blocks_v2)
    records.append(
        FileRecord(
            id="F02",
            file=v2_name,
            group="F",
            expected_doc_type="qtkd",
            expected_ingest="ok",
            procedure_number="9.001",
            purpose="QTKĐ 9.001 phiên bản 2 (nội dung sửa đổi) -- phải thay thế phiên bản 1 khi nạp.",
            spec={"kind": "qtkd_version2", "device": dev_v2, "supersedes_file": dev0.file},
            known_behaviors=known_behaviors_for("F02"),
        )
    )

    # F3: tên chứa cả "QTKD" và "biên bản" -> vẫn phân loại là qtkd (thứ tự ưu tiên).
    dev_f3 = copy.deepcopy(DEVICES[0])
    blocks_f3 = build_qtkd_blocks(dev_f3)
    f3_name = "QTKD 9.001 2026 biên bản kiểm định mẫu.docx"
    ox.write_docx(FILES_DIR / f3_name, blocks_f3)
    records.append(
        FileRecord(
            id="F03",
            file=f3_name,
            group="F",
            expected_doc_type="qtkd",
            expected_ingest="ok",
            procedure_number="9.001",
            purpose='Tên file chứa cả "QTKD" và "biên bản" -- phải phân loại "qtkd" (ưu tiên theo classify.py).',
            spec={"kind": "qtkd_name_ambiguous", "device": dev_f3},
        )
    )
    return records


def _convert_via_temp(src_path: Path, dest_name: str, out_ext: str) -> bool:
    """Copy ``src_path`` vào thư mục tạm, chuyển đổi ở đó, rồi chỉ chép KẾT QUẢ
    (``.doc``/``.xls``) vào ``FILES_DIR`` dưới ``dest_name`` -- bản trung gian
    ``.docx``/``.xlsx`` không bao giờ chạm ``FILES_DIR`` nên không thể rò rỉ."""
    with tempfile.TemporaryDirectory(prefix="knowledge_corpus_legacy_") as tmp:
        tmp_src = Path(tmp) / src_path.name
        shutil.copyfile(src_path, tmp_src)
        converted = _soffice_convert(tmp_src, out_ext)
        if converted is None or not converted.exists():
            return False
        shutil.copyfile(converted, FILES_DIR / dest_name)
        return True


def build_group_g(a_records: list, e_records: list, run_soffice: bool) -> list[FileRecord]:
    """Chỉ thêm vào manifest khi file legacy THỰC SỰ tồn tại sau chuyển đổi."""
    records: list[FileRecord] = []
    if not run_soffice:
        return records

    dev0_path = FILES_DIR / a_records[0].file
    g1_name = "QTKĐ 9.099 2026 Van an toan cu.doc"
    if dev0_path.exists() and _convert_via_temp(dev0_path, g1_name, "doc"):
        records.append(
            FileRecord(
                id="G01",
                file=g1_name,
                group="G",
                expected_doc_type="qtkd",
                expected_ingest="skipped-legacy",
                procedure_number="9.001",
                purpose="Định dạng .doc cũ (qua soffice) -- spike_a báo skipped-legacy.",
                spec={"kind": "legacy_doc", "source_procedure": "9.001"},
            )
        )

    e01 = next((r for r in e_records if r.id == "E01"), None)
    if e01 is not None:
        src_xlsx = FILES_DIR / e01.file
        g2_name = "Phieu do Van an toan SN-2026-111 legacy.xls"
        if _convert_via_temp(src_xlsx, g2_name, "xls"):
            records.append(
                FileRecord(
                    id="G02",
                    file=g2_name,
                    group="G",
                    expected_doc_type="phieu_do",
                    expected_ingest="skipped-legacy",
                    procedure_number="9.001",
                    purpose="Định dạng .xls cũ (qua soffice) -- spike_a báo skipped-legacy.",
                    spec={"kind": "legacy_xls", "source_file": e01.file},
                )
            )
    return records
