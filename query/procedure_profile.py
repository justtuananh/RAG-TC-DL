"""Hồ sơ QTKĐ: trang tri thức ghép mọi dữ kiện ĐÃ DUYỆT của một quy trình.

Tri thức trích từ QTKĐ (thông số, điều kiện, Bảng 1 các phép kiểm định, Bảng 2
phương tiện, công thức §6, thuật ngữ §2) nằm rải ở nhiều bảng; trang này gom
chúng thành một hồ sơ có cấu trúc, mỗi dòng giữ ``extraction_id``/``id`` để giao
diện mở đúng đoạn nguyên văn (P1). Chỉ đọc view đã duyệt (P3), không tính lại số
nào (P2): ô gộp của Bảng 1 chỉ được tách lại thành các dòng gốc của nó.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from catalogs.text import fold
from query.records import NotFoundError, iso_datetime

__all__ = ["NotFoundError", "list_procedures", "procedure_profile"]

# Nhóm "Thông số" theo thứ tự hiển thị; nhóm vắng vẫn được trả để giao diện nói rõ
# "chưa có dữ kiện đã duyệt" thay vì lặng lẽ bỏ qua.
PARAMETER_KINDS: tuple[tuple[str, str], ...] = (
    ("working_range", "Phạm vi đo"),
    ("accuracy_class", "Cấp chính xác"),
    ("max_permissible_error", "Sai số cho phép lớn nhất"),
    ("calibration_interval", "Chu kỳ kiểm định"),
)
ENV_KIND = "env_condition"
STEP_KIND = "inspection_step"
FORMULA_KIND = "formula"
# Trường mẫu biên bản (Phụ lục A) là khung hồ sơ, không phải tri thức của QTKĐ.
EXCLUDED_KINDS: tuple[str, ...] = ("appendix_field",)

# Chế độ kiểm định theo cột Bảng 1, khớp nhãn luật ``rule:bang1`` ghi vào
# ``condition_text`` ("Chế độ: Ban đầu, Định kỳ, Sau sửa chữa").
MODES: tuple[tuple[str, str], ...] = (
    ("ban_dau", "Ban đầu"),
    ("dinh_ky", "Định kỳ"),
    ("sau_sua_chua", "Sau sửa chữa"),
)
_MODE_PREFIX = "che do:"
# Ô gộp nhiều dòng của Bảng 1 được nối bằng " / "; dòng con mở đầu bằng gạch đầu dòng.
_PART_SEPARATOR = " / "
_BULLET_RE = re.compile(r"^[-–•]\s*")
_SECTION_REF_RE = re.compile(r"^\d+(?:\.\d+)*$")

RECENT_RECORDS = 5

_FACT_SQL = (
    "SELECT f.id AS id, f.extraction_id AS extraction_id, f.fact_kind AS fact_kind, "
    "f.label AS label, f.rel_op AS rel_op, f.value_min AS value_min, "
    "f.value_max AS value_max, f.value_text AS value_text, "
    "f.condition_text AS condition_text, u.code AS unit_code, "
    "e.section_path AS section_path "
    "FROM v_procedure_fact f "
    "LEFT JOIN v_unit u ON u.id = f.unit_id "
    "LEFT JOIN v_extraction e ON e.id = f.extraction_id "
    "WHERE f.procedure_id = :procedure_id AND f.fact_kind NOT IN :excluded "
    "ORDER BY f.id"
)
_FACT_COUNT_SQL = (
    "SELECT procedure_id, COUNT(*) FROM v_procedure_fact "
    "WHERE procedure_id IN :ids AND fact_kind NOT IN :excluded GROUP BY procedure_id"
)
_COUNT_SQL = (
    "SELECT procedure_id, COUNT(*) FROM {view} WHERE procedure_id IN :ids GROUP BY procedure_id"
)


def _expanding(sql: str, *names: str):
    return text(sql).bindparams(*(bindparam(name, expanding=True) for name in names))


def _number_key(number: str | None) -> tuple:
    """Sắp "1.9" trước "1.10": so từng phần số, phần chữ xếp sau."""
    parts = re.split(r"[.:]", number or "")
    return tuple((0, int(part), "") if part.isdigit() else (1, 0, part) for part in parts)


def _counts(session: Session, procedure_ids: list[int]) -> dict[str, dict[int, int]]:
    """Số tri thức đã duyệt của các QTKĐ trong trang, mỗi loại một truy vấn gộp.

    Chỉ đếm trong trang đang xem: ``v_record_detail`` nặng (truy vấn con theo từng hồ sơ)
    nên không quét toàn sổ cái cho mỗi lần gõ tìm kiếm.
    """
    if not procedure_ids:
        return {"facts": {}, "standards": {}, "terms": {}, "records": {}}
    params = {"ids": procedure_ids, "excluded": list(EXCLUDED_KINDS)}
    fact_sql = _expanding(_FACT_COUNT_SQL, "ids", "excluded")
    counts = {"facts": dict(session.execute(fact_sql, params).all())}
    for name, view in (
        ("standards", "v_procedure_standard"),
        ("terms", "v_term"),
        ("records", "v_record_detail"),
    ):
        sql = _expanding(_COUNT_SQL.format(view=view), "ids")
        counts[name] = dict(session.execute(sql, {"ids": procedure_ids}).all())
    return counts


def _procedure_summary(row: Any, counts: dict[str, dict[int, int]]) -> dict[str, Any]:
    procedure_id = row["id"]
    return {
        "id": procedure_id,
        "number": row["number"],
        "year": row["year"],
        "title": row["title"],
        "edition": row["edition"],
        "device_type_name": row["device_type_name"],
        "quantity_name": row["quantity_name"],
        "has_document": row["document_id"] is not None,
        "counts": {name: by_id.get(procedure_id, 0) for name, by_id in counts.items()},
    }


def list_procedures(
    session: Session, *, q: str | None = None, limit: int = 200, offset: int = 0
) -> tuple[list[dict[str, Any]], int]:
    """QTKĐ kèm số tri thức đã duyệt; tìm không dấu theo số hiệu, tên, loại thiết bị."""
    rows = session.execute(text("SELECT * FROM v_procedure")).mappings().all()
    needle = fold(q)
    if needle:
        rows = [
            row
            for row in rows
            if needle in fold(f"{row['number']} {row['title']} {row['device_type_name']}")
        ]
    rows = sorted(rows, key=lambda row: _number_key(row["number"]))
    start = max(0, offset)
    page = rows[start : start + max(1, limit)]
    counts = _counts(session, [row["id"] for row in page])
    return [_procedure_summary(row, counts) for row in page], len(rows)


def _facts(session: Session, procedure_id: int) -> list[dict[str, Any]]:
    params = {"procedure_id": procedure_id, "excluded": list(EXCLUDED_KINDS)}
    rows = session.execute(_expanding(_FACT_SQL, "excluded"), params).mappings().all()
    return [dict(row) for row in rows]


def _modes(condition_text: str | None) -> dict[str, bool]:
    """Cờ chế độ từ ``condition_text`` của luật Bảng 1; thiếu chế độ → mọi cờ False."""
    condition = fold(condition_text)
    listed: set[str] = set()
    if condition.startswith(_MODE_PREFIX):
        listed = {part.strip() for part in condition[len(_MODE_PREFIX) :].split(",")}
    return {key: fold(label) in listed for key, label in MODES}


def _split_step(label: str, section_ref: str | None) -> list[tuple[str, str | None]]:
    """Tách ô gộp "A / - B / - C" | "6.3 / 6.3.1 / 6.3.2" về các dòng gốc.

    Chỉ tách khi số phần của tên và của mục bằng nhau và mọi phần mục đều là số mục;
    ngược lại giữ nguyên văn cả ô (thà hiển thị gộp còn hơn ghép sai dòng).
    """
    if section_ref and _PART_SEPARATOR in section_ref:
        refs = [part.strip() for part in section_ref.split(_PART_SEPARATOR)]
        names = [part.strip() for part in label.split(_PART_SEPARATOR)]
        if len(refs) == len(names) and all(_SECTION_REF_RE.match(ref) for ref in refs):
            return [(_BULLET_RE.sub("", name), ref) for name, ref in zip(names, refs, strict=True)]
    # Gạch đầu dòng chỉ là dấu liệt kê của ô nguồn; cấp lùi đã thể hiện bằng số mục.
    return [(_BULLET_RE.sub("", label), section_ref)]


def _depth(section_ref: str | None) -> int:
    return section_ref.count(".") if section_ref and _SECTION_REF_RE.match(section_ref) else 0


def _steps(facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ma trận Bảng 1: một dòng mỗi phép, cấp lùi theo số mục, cờ theo chế độ.

    Dòng con bóc từ một ô gộp dùng chung cờ chế độ của dòng bảng đó: luật Bảng 1 đọc
    dấu "+" theo DÒNG bảng, nên một ô gộp chỉ có đúng một bộ chế độ trong nguồn.
    """
    rows: list[dict[str, Any]] = []
    for fact in facts:
        modes = _modes(fact["condition_text"])
        ref = (fact["value_text"] or "").strip() or None
        for label, section_ref in _split_step((fact["label"] or "").strip(), ref):
            rows.append(
                {
                    "fact_id": fact["id"],
                    "label": label,
                    "section_ref": section_ref,
                    "modes": dict(modes),
                    "depth": _depth(section_ref),
                }
            )
    numbered = [row["depth"] for row in rows if row["section_ref"]]
    base = min(numbered) if numbered else 0
    return [{**row, "depth": max(0, row["depth"] - base)} for row in rows]


def _rows(session: Session, sql: str, procedure_id: int) -> list[dict[str, Any]]:
    result = session.execute(text(sql), {"procedure_id": procedure_id}).mappings().all()
    return [dict(row) for row in result]


def _standards(session: Session, procedure_id: int) -> list[dict[str, Any]]:
    return _rows(
        session,
        "SELECT id, extraction_id, ord, name_vi, range_text, accuracy_text, note "
        "FROM v_procedure_standard WHERE procedure_id = :procedure_id "
        "ORDER BY COALESCE(ord, id), id",
        procedure_id,
    )


def _terms(session: Session, procedure_id: int) -> list[dict[str, Any]]:
    return _rows(
        session,
        "SELECT id, extraction_id, term_vi, term_en, definition FROM v_term "
        "WHERE procedure_id = :procedure_id ORDER BY id",
        procedure_id,
    )


def _records(session: Session, procedure_id: int) -> dict[str, Any]:
    """Tóm tắt biên bản đã duyệt theo QTKĐ: tổng, kết luận, thiết bị, vài biên bản mới."""
    summary = (
        session.execute(
            text(
                "SELECT COUNT(*) AS total, COUNT(DISTINCT device_id) AS devices, "
                "MAX(calibrated_at) AS latest_at, "
                "SUM(CASE WHEN verdict = 'dat' THEN 1 ELSE 0 END) AS dat, "
                "SUM(CASE WHEN verdict = 'khong_dat' THEN 1 ELSE 0 END) AS khong_dat "
                "FROM v_record_detail WHERE procedure_id = :procedure_id"
            ),
            {"procedure_id": procedure_id},
        )
        .mappings()
        .one()
    )
    recent = session.execute(
        text(
            "SELECT id, device_id, serial_no, device_type_name, calibrated_at, verdict, "
            "mode, cert_no FROM v_record_detail WHERE procedure_id = :procedure_id "
            # Biên bản không ghi ngày xếp cuối trên cả SQLite lẫn Postgres (Postgres để
            # NULL đầu tiên khi DESC).
            "ORDER BY (calibrated_at IS NULL), calibrated_at DESC, id DESC LIMIT :limit"
        ),
        {"procedure_id": procedure_id, "limit": RECENT_RECORDS},
    ).mappings()
    return {
        "total": summary["total"] or 0,
        "devices": summary["devices"] or 0,
        "latest_at": iso_datetime(summary["latest_at"]),
        "verdicts": {"dat": summary["dat"] or 0, "khong_dat": summary["khong_dat"] or 0},
        "recent": [{**row, "calibrated_at": iso_datetime(row["calibrated_at"])} for row in recent],
    }


_HEADER_KEYS = (
    "id",
    "number",
    "year",
    "title",
    "edition",
    "device_type_id",
    "device_type_name",
    "quantity_name",
)


def _header(row: Any) -> tuple[dict[str, Any], dict[str, Any] | None]:
    procedure = {key: row[key] for key in _HEADER_KEYS}
    if row["document_id"] is None:
        return procedure, None
    document = {
        "id": row["document_id"],
        "file_stem": row["document_file_stem"],
        "display_name": row["document_name"],
    }
    return procedure, document


def procedure_profile(session: Session, procedure_id: int) -> dict[str, Any]:
    """Hồ sơ đầy đủ của một QTKĐ từ dữ kiện đã duyệt; ``NotFoundError`` nếu không có."""
    row = (
        session.execute(text("SELECT * FROM v_procedure WHERE id = :id"), {"id": procedure_id})
        .mappings()
        .first()
    )
    if row is None:
        raise NotFoundError(f"Không tìm thấy QTKĐ {procedure_id}.")
    procedure, document = _header(row)
    by_kind: dict[str, list[dict[str, Any]]] = {}
    for fact in _facts(session, procedure_id):
        by_kind.setdefault(fact["fact_kind"], []).append(fact)
    return {
        "procedure": procedure,
        "document": document,
        "parameters": [
            {"kind": kind, "label": label, "items": by_kind.get(kind, [])}
            for kind, label in PARAMETER_KINDS
        ],
        "conditions": by_kind.get(ENV_KIND, []),
        "modes": [{"key": key, "label": label} for key, label in MODES],
        "steps": _steps(by_kind.get(STEP_KIND, [])),
        "formulas": by_kind.get(FORMULA_KIND, []),
        "standards": _standards(session, procedure_id),
        "terms": _terms(session, procedure_id),
        "records": _records(session, procedure_id),
    }
