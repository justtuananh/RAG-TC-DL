"""Lưới bảng OOXML dùng chung cho docx→Markdown và bộ đọc hồ sơ (K07).

Một ``w:tc`` có thể chiếm nhiều khe cột (``w:gridSpan``) và có thể là ô tiếp nối
của một ô gộp dọc (``w:vMerge`` thiếu ``w:val`` hoặc ``w:val="continue"``). Hai nơi
dựng lưới bảng (``ingestion.extract_docx`` và ``records.docx_reader``) phải mở
rộng ô gộp GIỐNG NHAU, nếu không số cột và tiêu đề hai tầng sẽ lệch.

Module này chỉ phụ thuộc ``lxml`` và không import tầng nào khác, để cả hai phía
dùng chung mà không tạo vòng import.
"""

from __future__ import annotations

from dataclasses import dataclass

_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_TC = f"{{{_W_NS}}}tc"
_TCPR = f"{{{_W_NS}}}tcPr"
_GRIDSPAN = f"{{{_W_NS}}}gridSpan"
_VMERGE = f"{{{_W_NS}}}vMerge"
_VAL = f"{{{_W_NS}}}val"


@dataclass(frozen=True)
class GridSlot:
    """Một ô vật lý của hàng cùng số khe cột nó chiếm và cờ ô tiếp nối."""

    cell: object
    span: int = 1
    continues: bool = False


def grid_slots(tr) -> list[GridSlot]:
    """Trả các khe cột của một ``w:tr`` theo thứ tự, đã tính ``gridSpan``/``vMerge``.

    ``span`` tối thiểu 1. ``continues=True`` nghĩa là ô tiếp nối của một ô gộp dọc
    nên nội dung phải để trống; ô ``vMerge`` khởi tạo (``val="restart"``) giữ nội
    dung bình thường.
    """
    slots: list[GridSlot] = []
    for tc in tr.findall(_TC):
        span = 1
        continues = False
        tcpr = tc.find(_TCPR)
        if tcpr is not None:
            grid_span = tcpr.find(_GRIDSPAN)
            if grid_span is not None:
                try:
                    span = max(1, int(grid_span.get(_VAL) or "1"))
                except ValueError:
                    span = 1
            vmerge = tcpr.find(_VMERGE)
            if vmerge is not None:
                value = vmerge.get(_VAL)
                continues = value is None or value == "continue"
        slots.append(GridSlot(cell=tc, span=span, continues=continues))
    return slots
