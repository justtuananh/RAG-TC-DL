"""Sinh bộ dữ liệu test lớp tri thức (Pha 2). Chạy: ``python -m scripts.knowledge_corpus.build``.

Tất định: gọi lại nhiều lần cho ra docx/xlsx giống hệt byte (pdf/doc/xls qua
soffice được phép khác byte -- xem ``docs/superpowers/plans/2026-09-25-knowledge-test-corpus.md``).
"""

from __future__ import annotations

import argparse
import shutil
import sys

from scripts.knowledge_corpus.build_a import build_group_a
from scripts.knowledge_corpus.build_b import build_group_b
from scripts.knowledge_corpus.build_cfg import build_group_c, build_group_f, build_group_g
from scripts.knowledge_corpus.build_de import build_group_d_e
from scripts.knowledge_corpus.specs_io import DATA_DIR, FILES_DIR, write_outputs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sinh bộ dữ liệu test knowledge_corpus")
    parser.add_argument("--no-soffice", action="store_true", help="Bỏ qua bước chuyển pdf/doc/xls")
    args = parser.parse_args(argv)

    if FILES_DIR.exists():
        shutil.rmtree(FILES_DIR)
    FILES_DIR.mkdir(parents=True, exist_ok=True)

    a_records = build_group_a()
    b_records = build_group_b()
    c_records = build_group_c(a_records, run_soffice=not args.no_soffice)
    de_records = build_group_d_e()
    d_records = [r for r in de_records if r.group == "D"]
    e_records = [r for r in de_records if r.group == "E"]
    f_records = build_group_f(a_records)
    g_records = build_group_g(a_records, e_records, run_soffice=not args.no_soffice)

    all_records = a_records + b_records + c_records + d_records + e_records + f_records + g_records
    write_outputs(all_records)
    _check_files_match_manifest(all_records)

    counts: dict[str, int] = {}
    for r in all_records:
        counts[r.group] = counts.get(r.group, 0) + 1
    print("Số file theo nhóm:", counts)
    print("Tổng:", len(all_records))
    print("Đã ghi vào:", DATA_DIR)
    return 0


def _check_files_match_manifest(records: list) -> None:
    """``files/`` phải chứa ĐÚNG tập tên trong manifest -- không thừa, không thiếu."""
    manifest_names = {r.file for r in records}
    actual_names = {p.name for p in FILES_DIR.iterdir() if p.is_file()}
    extra = sorted(actual_names - manifest_names)
    missing = sorted(manifest_names - actual_names)
    if extra or missing:
        raise SystemExit(
            "files/ không khớp manifest.jsonl:\n"
            f"  thừa (có file, không có trong manifest): {extra}\n"
            f"  thiếu (có trong manifest, không có file): {missing}"
        )


if __name__ == "__main__":
    sys.exit(main())
