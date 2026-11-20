"""Đối tượng kiểm định ngoài phạm vi các QTKĐ."""

import pytest

from core.settings_loader import get_settings
from query import object_scope as osc

CFG = get_settings().object_scope
OBJECTS = [
    "ÁP KẾ PÍTTÔNG CÓ PHẠM VI ĐO (-1 ĐẾN 5 000) bar, CẤP CHÍNH XÁC ĐẾN 0,01",
    "ÁP KẾ CHUẨN HIỆN SỐ VÀ LÒ XO CÓ PHẠM VI ĐO (-1 ĐẾN 5 000) bar",
    "VAN AN TOÀN",
    "áp kế pít tông",
]
SCOPES = ["Quy trình này áp dụng để kiểm định ban đầu, định kỳ áp kế đo áp suất."]


@pytest.mark.parametrize(
    "q",
    [
        "Quy trình kiểm định thiết bị đo tốc độ vòng quay gồm những phép kiểm định nào?",
        "Điều kiện môi trường khi kiểm định tốc độ kế là gì?",
        "Chu kỳ kiểm định nhiệt kế là bao lâu?",  # chỉ được nhắc như thiết bị kiểm định, không phải đối tượng
    ],
)
def test_out_of_scope(q):
    assert osc.is_out_of_scope(q, OBJECTS, SCOPES, CFG)


@pytest.mark.parametrize(
    "q",
    [
        "Điều kiện môi trường khi kiểm định áp kế pít tông là gì?",
        "Quy trình kiểm định áp kế lò xo gồm những phép nào?",
        "Chu kỳ kiểm định van an toàn là bao lâu?",
        "Quy trình kiểm định thiết bị đo áp suất gồm những phép nào?",
        "Chu kỳ kiểm định là bao lâu?",
        "Quy trình kiểm định này gồm những phép nào?",
        "Điều kiện kiểm định định kỳ là gì?",
        "Áp kế pít tông có phạm vi đo bao nhiêu?",  # không nêu "kiểm định <đối tượng>"
        # Câu so sánh: từ "khác/giống/so với" không thuộc tên đối tượng (câu #30 của bộ kiểm tra).
        "Chu kỳ kiểm định áp kế píttông khác chu kỳ kiểm định áp kế chuẩn hiện số và lò xo như thế nào?",
        "Chu kỳ kiểm định áp kế píttông so với áp kế lò xo thì khác gì?",
        "Chu kỳ kiểm định áp kế píttông giống áp kế lò xo không?",
    ],
)
def test_in_scope_or_not_applicable(q):
    assert not osc.is_out_of_scope(q, OBJECTS, SCOPES, CFG)


def test_comparison_keeps_refusing_unknown_object():
    q = "Chu kỳ kiểm định nhiệt kế khác chu kỳ kiểm định tốc độ kế như thế nào?"
    assert osc.is_out_of_scope(q, OBJECTS, SCOPES, CFG)


def test_disabled():
    cfg = CFG.model_copy(update={"enabled": False})
    assert not osc.is_out_of_scope("Chu kỳ kiểm định nhiệt kế là bao lâu?", OBJECTS, [], cfg)
