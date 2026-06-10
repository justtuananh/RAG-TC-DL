"""QTKĐ file-stem router — retrieval.router.route + _NUMBER_RE.

Ưu tiên: số QTKĐ rõ ràng (1.061) > alias thiết bị (van an toàn). Không tín hiệu → None.
Mapping number→stem được set thẳng (bỏ qua bước scroll Qdrant).
"""

import pytest

import retrieval.router as router_mod
from retrieval.router import _NUMBER_RE, route


@pytest.fixture
def mapping(monkeypatch):
    m = {
        "1.061": "QTKD_1.061_2021_ND_V2",
        "1.063": "QTKD_1.063_2021_BPL",
        "1.160": "QTKD_1.160_2021_ND_FINAL",
        "1.190": "2023._QTKD_1.190_2023_DPI_610_ND_24.01.24",
    }
    monkeypatch.setattr(router_mod, "_number_to_stem", m)
    return m


def test_explicit_number(mapping):
    assert route("phạm vi của 1.061 là gì") == mapping["1.061"]
    assert route("1.160 quy định gì") == mapping["1.160"]


def test_device_alias(mapping):
    assert route("kiểm định van an toàn") == mapping["1.061"]
    assert route("akkđ là gì") == mapping["1.160"]
    assert route("dpi 610") == mapping["1.190"]
    assert route("dpi610") == mapping["1.190"]


def test_number_beats_alias(mapping):
    # Có cả alias "van an toàn"(1.061) lẫn số 1.063 → số thắng.
    assert route("van an toàn theo 1.063") == mapping["1.063"]


def test_no_signal_returns_none(mapping):
    assert route("1400 bar") is None
    assert route("sai số 0.05") is None
    assert route("câu hỏi chung không có mã hay tên thiết bị") is None


def test_number_present_but_not_in_mapping(mapping):
    # 9.999 khớp regex nhưng không có trong mapping → None (không alias) .
    assert route("tiêu chuẩn 9.999") is None


def test_number_re_pattern():
    assert _NUMBER_RE.search("1.061").group(1) == "1.061"
    assert _NUMBER_RE.search("mã 1.160 đây").group(1) == "1.160"
    assert _NUMBER_RE.search("6.3") is None  # chỉ 1 chữ số sau dấu chấm
    assert _NUMBER_RE.search("0.05") is None  # chỉ 2 chữ số
    assert _NUMBER_RE.search("1400") is None  # không có dấu chấm
