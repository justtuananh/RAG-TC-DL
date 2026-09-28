"""Quy đổi đơn vị SI dùng chung cho bề mặt tra cứu dữ liệu (P2).

Trước đây ``query/records.py`` và ``query/router.py`` mỗi bên giữ một bản
``_from_si`` gần giống nhau; hai bản dễ trôi khỏi nhau. Một bản duy nhất ở đây
là nguồn sự thật, chỉ đọc view ``v_unit`` nên không vi phạm P3.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


def unit_defs_by_id(session: Session) -> dict[int, dict[str, Any]]:
    """Mã đơn vị + hệ số quy đổi SI theo id (đọc ``v_unit``)."""
    rows = (
        session.execute(text("SELECT id, code, factor_to_si, offset_to_si FROM v_unit"))
        .mappings()
        .all()
    )
    return {int(row["id"]): dict(row) for row in rows}


def from_si(value: Any, unit: dict[str, Any] | None) -> Any:
    """Đổi một giá trị SI về đơn vị gốc của dữ kiện.

    ``unit`` là một dòng ``v_unit`` (``factor_to_si``/``offset_to_si``); ``None``
    nghĩa là không có đơn vị gốc nên giữ nguyên giá trị SI. Hệ số 0 (dữ liệu lỗi)
    cũng giữ nguyên thay vì chia cho 0. Làm tròn 9 chữ số có nghĩa để bỏ nhiễu
    dấu phẩy động.
    """
    if value is None or unit is None:
        return value
    factor = unit.get("factor_to_si")
    if not factor:
        return value
    offset = unit.get("offset_to_si") or 0.0
    converted = (float(value) - offset) / factor
    return float(f"{converted:.9g}")
