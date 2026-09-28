"""Bề mặt tra cứu danh mục NAS — chỉ đọc view đã duyệt (P3, Pha D1).

Cung cấp bảng tìm kiếm không dấu, lọc nhóm, phân trang cho bốn danh mục (chuẩn
mẫu, kiểm định viên, danh mục tiêu chuẩn/quy trình, lĩnh vực công nhận) và số
dòng đã duyệt mỗi loại. Mỗi dòng trả kèm xuất xứ P1 (tài liệu + nguyên văn).

Mọi câu SQL ở đây chỉ chạm các view ``v_*``; bộ guard ``db.views.scan_query_source``
quét thư mục ``query/`` và fail nếu bắt gặp tên bảng gốc.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from catalogs.labels import CATALOG_KINDS
from catalogs.text import fold
from query.records import QueryError

LIST_LIMIT_MAX = 200
VIEWS: dict[str, str] = {kind: f"v_{kind}" for kind in CATALOG_KINDS}
# Chỉ danh mục quy trình và lĩnh vực công nhận có cột nhóm để lọc.
GROUP_COLUMNS: dict[str, str] = {
    "procedure_catalog": "group_code",
    "capability": "group_code",
}
# Cột nội bộ (bản không dấu) không lộ ra API.
_ROW_EXCLUDE = {"search_text"}


def _where(conditions: list[str]) -> str:
    return f" WHERE {' AND '.join(conditions)}" if conditions else ""


def _require_kind(kind: str) -> str:
    view = VIEWS.get(kind)
    if view is None:
        raise QueryError(f"Loại danh mục không hợp lệ: {kind!r}.")
    return view


def _serialize(row: Any) -> dict[str, Any]:
    """Một dòng view thành dict, kèm xuất xứ P1 (tài liệu, extraction, nguyên văn)."""
    item = {key: row[key] for key in row.keys() if key not in _ROW_EXCLUDE}
    item["provenance"] = {
        "document_id": item.get("document_id"),
        "display_name": item.get("display_name"),
        "file_stem": item.get("file_stem"),
        "extraction_id": item.get("extraction_id"),
        "quote": item.get("quote"),
    }
    return item


def _procedure_links(session: Session, numbers: list[str]) -> dict[str, dict[str, Any]]:
    """Map số QTKĐ → QTKĐ trong kho (chỉ bản có tài liệu), đọc ``v_procedure`` (P3)."""
    if not numbers:
        return {}
    params = {f"n{index}": number for index, number in enumerate(numbers)}
    placeholders = ", ".join(f":{key}" for key in params)
    rows = (
        session.execute(
            text(
                "SELECT id, number, title, year, document_id FROM v_procedure "
                f"WHERE number IN ({placeholders}) AND document_id IS NOT NULL"
            ),
            params,
        )
        .mappings()
        .all()
    )
    return {
        row["number"]: {
            "procedure_id": row["id"],
            "number": row["number"],
            "title": row["title"],
            "year": row["year"],
            "document_id": row["document_id"],
        }
        for row in rows
    }


def _attach_procedure_links(session: Session, items: list[dict[str, Any]]) -> None:
    """Gắn cờ/liên kết QTKĐ cho các dòng danh mục quy trình khớp số hiệu trong kho."""
    numbers = sorted({item["procedure_number"] for item in items if item.get("procedure_number")})
    links = _procedure_links(session, numbers)
    for item in items:
        item["procedure_link"] = links.get(item.get("procedure_number"))


def list_catalog(
    session: Session,
    kind: str,
    *,
    q: str | None = None,
    group: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """Trang danh mục đã duyệt + tổng số dòng khớp bộ lọc (P3)."""
    view = _require_kind(kind)
    conditions: list[str] = []
    params: dict[str, Any] = {}
    if q and q.strip():
        conditions.append("search_text LIKE :q")
        params["q"] = f"%{fold(q)}%"
    group_column = GROUP_COLUMNS.get(kind)
    if group and group.strip() and group_column:
        conditions.append(f"{group_column} = :group")
        params["group"] = group.strip()
    where = _where(conditions)

    total = session.execute(text(f"SELECT COUNT(*) FROM {view}{where}"), params).scalar_one()
    safe_limit = max(1, min(int(limit), LIST_LIMIT_MAX))
    safe_offset = max(0, int(offset))
    rows = (
        session.execute(
            text(
                f"SELECT * FROM {view}{where} "
                "ORDER BY ord IS NULL, ord, id LIMIT :limit OFFSET :offset"
            ),
            {**params, "limit": safe_limit, "offset": safe_offset},
        )
        .mappings()
        .all()
    )
    items = [_serialize(row) for row in rows]
    if kind == "procedure_catalog":
        _attach_procedure_links(session, items)
    return items, int(total)


def catalog_counts(session: Session) -> dict[str, int]:
    """Số dòng đã duyệt của từng loại danh mục (luôn đọc qua view)."""
    return {
        kind: session.execute(text(f"SELECT COUNT(*) FROM {VIEWS[kind]}")).scalar_one()
        for kind in CATALOG_KINDS
    }


def catalog_groups(session: Session, kind: str) -> list[dict[str, Any]]:
    """Nhóm lĩnh vực phân biệt của một loại danh mục (rỗng nếu không có cột nhóm)."""
    view = _require_kind(kind)
    if kind not in GROUP_COLUMNS:
        return []
    rows = (
        session.execute(
            text(
                f"SELECT DISTINCT group_code AS code, group_title AS title FROM {view} "
                "WHERE group_code IS NOT NULL ORDER BY code"
            )
        )
        .mappings()
        .all()
    )
    return [{"code": row["code"], "title": row["title"]} for row in rows]
