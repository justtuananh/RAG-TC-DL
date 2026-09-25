"""Dựng nhóm B: 8 QTKĐ docx biên, mỗi file nhắm một mã hành vi K0x (Pha 2 §2).

Redo R1: gold suy TRỰC TIẾP từ ``dev`` spec (``gold_a.golden_rows_for_doc``,
giống nhóm A) -- KHÔNG bao giờ từ việc chạy luật. ``known_behaviors`` lấy từ
nguồn TĨNH ``known_behaviors.json`` (``specs_io.known_behaviors_for``): builder
hoàn toàn KHÔNG chạy code sản phẩm, nên rebuild không ghi đè hành vi cũ.
"""

from __future__ import annotations

from ingestion.spike_a import _safe
from scripts.knowledge_corpus import content_b as cb
from scripts.knowledge_corpus import gold_a
from scripts.knowledge_corpus import ooxml as ox
from scripts.knowledge_corpus.specs_io import FILES_DIR, FileRecord, known_behaviors_for

_PURPOSES = {
    "B01": "Mã QTKD không dấu Đ trong dòng đầu mục và Phụ lục A (K11).",
    "B02": "Đoạn \"(Quy định)\" trong Phụ lục A bị gán style heading, cắt mục (K12).",
    "B03": "Bảng Phụ lục A gộp ô hai tầng (Mở/Đóng/Độ chênh áp) đúng mẫu ĐLVN thật; "
    "dùng làm nguồn cho biên bản K07 (D13).",
    "B04": "\"Chu kỳ kiểm định: 6 tháng\" không có chữ \"là\" (K10).",
    "B05": "Điều kiện môi trường \"(20,5 ± 2) °C\" bị tách sai ở dấu phẩy thập phân (K02).",
    "B06": "Mục \"7 Tiến hành kiểm định\" dùng style heading bản địa hoá, không nhận diện được (K13).",
    "B07": "Bảng 2 tách làm hai bảng bằng \"Bảng 2 (kết thúc)\" -- kiểm tra gộp đúng.",
    "B08": "Số kiểu Việt hợp lệ \"0,500\" và \"1 000\" trong phạm vi đo -- không phải lỗi.",
    "B09": "Câu phạm vi kết thúc ngay sau đơn vị bằng dấu chấm câu (\"...bar.\") -- văn phong hợp lệ (K15).",
}


def build_group_b() -> list[FileRecord]:
    records: list[FileRecord] = []
    for case_id, number, fn, filename, kcode in cb.CASES:
        dev, blocks = fn(number)
        path = FILES_DIR / filename
        ox.write_docx(path, blocks)
        stem = _safe(path.stem)

        rows = gold_a.golden_rows_for_doc(stem, dev)
        section6_golden = (
            gold_a.section6_golden_rows_for_doc(stem, dev) if dev.get("section6") else []
        )
        known_behaviors = known_behaviors_for(case_id)

        records.append(
            FileRecord(
                id=case_id,
                file=filename,
                group="B",
                expected_doc_type="qtkd",
                expected_ingest="ok",
                procedure_number=number,
                purpose=_PURPOSES[case_id],
                spec={"kind": "qtkd_edge", "case": case_id, "target_kcode": kcode, "device": dev},
                known_behaviors=known_behaviors,
                extract_golden=rows,
                section6_golden=section6_golden,
            )
        )
    return records
