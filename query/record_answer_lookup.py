"""Câu trả lời tất định cho ``record_lookup`` (một / vài biên bản cụ thể).

Câu hỏi về một biên bản cần đúng điều được hỏi, không phải cả phiếu:

    Biên bản 013/2024 của áp kế píttông tiêu chuẩn МП-2500 số hiệu 0391, ngày 19/11/2024:
    phạm vi đo (50 đến 2 500) kgf/cm2; cấp chính xác 0,05.

Ghép từ nguyên văn các ô đã đưa vào bảng (cùng dữ liệu, cùng thứ tự), qua
``query.answer_phrases``. Nhiều biên bản khớp (một thiết bị kiểm định nhiều lần): phần
giống nhau ở mọi biên bản nêu một lần ở câu dẫn, phần khác nhau nêu theo từng biên bản.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from query.answer_phrases import (
    cert,
    clean_value,
    date_text,
    device_name,
    filled_cells,
    has_measured,
    lower_first,
    point_clause,
    record_head,
    row_clause,
    strip_unit,
    upper_first,
    with_unit,
)
from query.record_fields import VERDICT_KEY, FieldCatalog
from records.columns import role_for_column, unit_from_header

MAX_RECORD_LINES = 12
# Bảng nhiều dòng có giá trị đo ("Bảng A.1": vuông góc, độ kín): kể từng dòng nếu ít.
MAX_POINT_CLAUSES = 4
_TITLE_PREFIX_RE = re.compile(r"^\s*Bảng\s+\S+\s*[-–—:]\s*", re.IGNORECASE)


@dataclass(frozen=True)
class StepResult:
    """Các dòng của MỘT bảng kết quả trong MỘT biên bản, đúng như bảng hiển thị."""

    record_id: int
    title: str
    points: tuple[dict, ...]
    names: tuple[str, ...]
    asked: frozenset[str]
    filtered: bool


def short_title(title: str) -> str:
    """ "Bảng A.2 – Thời gian quay tự do" → "thời gian quay tự do"."""
    return lower_first(_TITLE_PREFIX_RE.sub("", title).strip())


def _nominal_span(step: StepResult) -> str | None:
    """ "áp suất danh nghĩa từ 6,0 đến 60,0 kG/cm2": dòng đầu và dòng cuối của bảng.

    Đọc đúng thứ tự bảng trong biên bản (P2: không sắp, không tính bước nhảy).
    """
    nominal = next((name for name in step.names if role_for_column(name) == "nominal"), None)
    if nominal is None:
        return None
    values = [dict(filled_cells(point)).get(nominal) for point in step.points]
    values = [value for value in values if value]
    if len(values) < 2:
        return None
    unit = unit_from_header(nominal)
    label = lower_first(strip_unit(nominal, unit))
    return f"{label} từ {values[0]} đến {with_unit(values[-1], unit)}"


def step_clause(record: dict, step: StepResult) -> str:
    """Một bảng kết quả của một biên bản, đúng điều câu hỏi nhắm tới."""
    title = short_title(step.title)
    points = list(step.points)
    if step.filtered or (len(points) == 1 and not has_measured(points[0])):
        rows = [row_clause(point, list(step.names), step.asked) for point in points]
        return f"{title} {'; '.join(rows)}"
    if len(points) == 1:
        return point_clause(record, points[0], step.title, subject=title)
    if all(has_measured(point) for point in points) and len(points) <= MAX_POINT_CLAUSES:
        return f"{title}: " + "; ".join(point_clause(record, point, step.title) for point in points)
    span = _nominal_span(step)
    if span:
        return f"{title}: {len(points)} điểm, {span}"
    return f"{title}: {len(points)} dòng (xem bảng)"


def _field_parts(row_fields: dict[str, dict], keys: list[str], catalog: FieldCatalog) -> list[str]:
    parts = []
    for key in keys:
        if key == VERDICT_KEY:
            continue
        row = row_fields.get(key)
        label = lower_first(catalog.field_label(key))
        parts.append(
            f"{label} {clean_value(row.get('value_text'))}"
            if row is not None
            else f"{label}: biên bản không ghi"
        )
    return parts


def _verdict_parts(
    record: dict, row_fields: dict[str, dict], failures: list[dict], catalog: FieldCatalog
) -> list[str]:
    row = row_fields.get(VERDICT_KEY)
    # "kết luận đạt yêu cầu …" (không dấu ":" để dòng liệt kê "- 015/2025 ngày …: …" không
    # có hai dấu hai chấm).
    parts = [f"kết luận {lower_first(clean_value(row.get('value_text')))}"] if row else []
    for point in failures:
        title = catalog.table_title(point.get("step_code") or "", point.get("procedure_id"))
        clause = point_clause(record, point, title, subject=short_title(title), conclude=False)
        parts.append(f"căn cứ: {clause}")
    return parts


def record_parts(
    record: dict,
    row_fields: dict[str, dict],
    keys: list[str],
    catalog: FieldCatalog,
    steps: list[StepResult],
    failures: list[dict],
) -> list[str]:
    """Các vế trả lời của một biên bản theo thứ tự: trường, bảng, kết luận + căn cứ."""
    parts = _field_parts(row_fields, keys, catalog)
    parts += [step_clause(record, step) for step in steps if step.record_id == record["id"]]
    if VERDICT_KEY in keys:
        parts += _verdict_parts(record, row_fields, failures, catalog)
    return parts


def identity_answer(records: list[dict], *, cert_first: bool = True) -> str:
    """Câu hỏi chỉ hỏi định danh của biên bản.

    ``cert_first``: hỏi số biên bản ("… ngày 10/07/2024 có số biên bản là bao nhiêu?") →
    "Số biên bản là 011/2024 (…)"; hỏi ngày / số hiệu / ký hiệu → câu định danh đầy đủ.
    """
    lines = []
    for record in records[:MAX_RECORD_LINES]:
        owner = record.get("owner_org")
        if cert_first:
            lines.append(
                f"Số biên bản là {cert(record)} ({device_name(record)}, ngày "
                f"{date_text(record.get('calibrated_at'))}"
                + (f"; đơn vị sử dụng: {owner}" if owner else "")
                + ")."
            )
        else:
            lines.append(
                record_head(record) + (f" (đơn vị sử dụng: {owner})" if owner else "") + "."
            )
    if len(lines) == 1:
        return lines[0]
    return "\n".join([f"Có {len(records)} biên bản khớp:", "", *(f"- {line}" for line in lines)])


def lookup_answer(records: list[dict], parts_by_record: dict[int, list[str]]) -> str | None:
    """Ghép câu trả lời: một biên bản → một câu; nhiều biên bản → câu dẫn + từng biên bản."""
    if not records or not any(parts_by_record.values()):
        return None
    if len(records) == 1:
        record = records[0]
        return f"{record_head(record)}: {'; '.join(parts_by_record[record['id']])}."
    all_parts = [parts_by_record.get(record["id"], []) for record in records]
    shared = [part for part in all_parts[0] if all(part in parts for parts in all_parts[1:])]
    lead = (
        f"{upper_first(device_name(records[0]))} có {len(records)} biên bản đã duyệt"
        if len({record.get("device_id") for record in records}) == 1
        else f"Có {len(records)} biên bản khớp"
    )
    listed = records[:MAX_RECORD_LINES]
    varying = {
        record["id"]: [p for p in parts_by_record.get(record["id"], []) if p not in shared]
        for record in listed
    }
    if not any(varying.values()):
        dates = "; ".join(
            f"{cert(record)} ngày {date_text(record.get('calibrated_at'))}" for record in listed
        )
        return f"{lead} ({dates}), cùng ghi {'; '.join(shared)}."
    head = f"{lead}; {'; '.join(shared)}:" if shared else f"{lead}:"
    lines = [
        f"- {cert(record)} ngày {date_text(record.get('calibrated_at'))}: "
        f"{'; '.join(varying[record['id']]) or 'như trên'}"
        for record in listed
    ]
    if len(records) > len(listed):
        lines.append(f"- … và {len(records) - len(listed)} biên bản khác (xem bảng)")
    return "\n".join([head, "", *lines])
