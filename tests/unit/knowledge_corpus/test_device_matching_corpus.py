"""T8: kiểm tra gộp thiết bị (``records.matching.find_or_create_device``) khi nạp
toàn bộ hồ sơ nhóm D/E vào MỘT CSDL dùng chung (fixture ``records_db``, module
scope — khác T7 vốn cô lập từng hồ sơ để test đúng giá trị TRƯỜNG của riêng nó).
"""

from __future__ import annotations

import json

from db.models import Device
from tests.unit.knowledge_corpus.conftest import CORPUS_ROOT, load_manifest

_MANIFEST = load_manifest()
_GOLD_FILE = CORPUS_ROOT / "gold" / "records_golden.jsonl"


def _load_gold_records() -> list[dict]:
    rows = []
    with open(_GOLD_FILE, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                rows.append(json.loads(line))
    return rows


_GOLD_RECORDS = _load_gold_records()


def test_d04_d05_same_device_despite_serial_casing(records_db):
    """D04 (``sn-2026-201``) và D05 (``SN-2026-201``), cùng QTKĐ 9.002, phải cùng
    một ``Device`` (khóa gộp bỏ qua hoa/thường của serial)."""
    d04 = records_db["results"]["D04"]
    d05 = records_db["results"]["D05"]
    assert d04.device_id is not None
    assert d04.device_id == d05.device_id


def test_missing_serial_records_each_create_own_device(records_db):
    """D03 và D09 (thiếu số hiệu) mỗi cái tạo một thiết bị MỚI, không gộp chung,
    và đều bật ``needs_identification``."""
    d03 = records_db["results"]["D03"]
    d09 = records_db["results"]["D09"]
    assert d03.needs_identification is True
    assert d09.needs_identification is True
    assert d03.device_id != d09.device_id

    session = records_db["session"]
    device_d03 = session.get(Device, d03.device_id)
    device_d09 = session.get(Device, d09.device_id)
    assert device_d03.needs_identification == 1
    assert device_d09.needs_identification == 1
    assert device_d03.serial_norm is None
    assert device_d09.serial_norm is None


def test_final_device_count_matches_expected(records_db):
    """Số thiết bị cuối cùng = số cặp (QTKĐ áp dụng, serial chuẩn hoá) khác nhau
    tính từ ``records_golden`` (đại diện cho "loại phương tiện" — trong corpus này
    serial không bao giờ trùng giữa hai QTKĐ khác nhau) + số hồ sơ thiếu serial
    (mỗi hồ sơ đó luôn tạo thiết bị tạm riêng, không gộp)."""
    distinct_pairs: set[tuple[str, str]] = set()
    missing_serial_count = 0
    for row in _GOLD_RECORDS:
        serial = row["fields"]["serial"]
        if serial is None:
            missing_serial_count += 1
            continue
        norm = " ".join(serial.split()).casefold()
        distinct_pairs.add((row["procedure_number"], norm))
    expected_count = len(distinct_pairs) + missing_serial_count

    session = records_db["session"]
    actual_count = session.query(Device).count()
    assert actual_count == expected_count, (
        f"Số thiết bị thực tế {actual_count} != kỳ vọng {expected_count} "
        f"({len(distinct_pairs)} serial khác nhau + {missing_serial_count} hồ sơ thiếu serial)"
    )
