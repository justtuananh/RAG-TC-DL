"""Câu trả lời tất định cho ``records_summary`` (đếm / liệt kê) và ``device_history``.

    6 thiết bị có phạm vi đo ghi theo đơn vị bar:
    - CPB5800 SN 1A0043219 (1 đến 1 200) bar
    - ...

    Sổ cái có 20 biên bản đã duyệt của 12 thiết bị (theo số hiệu); 2 biên bản không
    đạt: 010/2024 (МП-60 SN 1045, độ kín: …) và 020/2026 (CPB5800 SN 1A0043219, …).

Đếm là đếm hồ sơ / thiết bị (không phải phép tính trên số liệu đo); mọi giá trị khác
là nguyên văn sổ cái. Danh sách dài hơn ``MAX_LINES`` chỉ nêu số lượng, bảng bên dưới
giữ đủ dòng.
"""

from __future__ import annotations

from typing import Any

from query.answer_phrases import (
    cert,
    clean_value,
    date_text,
    device_name,
    join_vi,
    lower_first,
    upper_first,
    verdict_reason,
    verdict_short,
)
from query.record_fields import VERDICT_KEY
from query.record_intents import RecordsSummaryParams

MAX_LINES = 12


def _verdict_text(fields: dict[int, dict[str, dict]], record: dict) -> str | None:
    row = fields.get(record["id"], {}).get(VERDICT_KEY)
    return row.get("value_text") if row else None


def _model_serial(record: dict, separator: str = " ") -> str:
    """ "CPB5800 SN 1A0043219" (hoặc "МП-600, SN 2218" trong ngoặc của danh sách)."""
    serial = f"SN {record['serial_no']}" if record.get("serial_no") else ""
    parts = (record.get("model_code") or "", serial)
    return separator.join(part for part in parts if part) or "—"


def _period(params: RecordsSummaryParams) -> str:
    if params.date_from and params.date_to:
        return f" từ {date_text(params.date_from)} đến {date_text(params.date_to)}"
    if params.date_from:
        return f" từ {date_text(params.date_from)}"
    if params.date_to:
        return f" đến {date_text(params.date_to)}"
    return ""


def filter_phrase(params: RecordsSummaryParams) -> str:
    """Bộ lọc của câu hỏi bằng lời, nối sau "N biên bản" / "N thiết bị"."""
    parts = []
    if params.verdict:
        parts.append(" không đạt" if params.verdict == "khong_dat" else " đạt")
    if params.inspector:
        parts.append(f" do kiểm định viên {params.inspector} thực hiện")
    if params.reviewer:
        parts.append(f" do {params.reviewer} kiểm soát")
    if params.owner_org:
        parts.append(f" của {params.owner_org}")
    if params.model_code:
        parts.append(f" của thiết bị ký hiệu {params.model_code}")
    if params.range_unit:
        parts.append(f" có phạm vi đo ghi theo đơn vị {params.range_unit}")
    return "".join(parts) + _period(params)


def _unfiltered(params: RecordsSummaryParams) -> bool:
    """Không lọc gì ngoài khoảng ngày: câu hỏi về toàn bộ sổ cái."""
    return not any(
        (
            params.serial,
            params.model_code,
            params.inspector,
            params.reviewer,
            params.owner_org,
            params.verdict,
            params.range_unit,
            params.procedure_ids,
        )
    )


def is_overview(params: RecordsSummaryParams) -> bool:
    """Đếm trên toàn sổ cái ("toàn bộ hồ sơ có bao nhiêu biên bản…"): nêu số lượng + biên
    bản không đạt, không kể cả sổ cái. Đếm có bộ lọc vẫn kể từng biên bản khớp."""
    return params.measure == "count" and params.subject == "records" and _unfiltered(params)


def _asked(record: dict, fields: dict[int, dict[str, dict]], labels: dict[str, str]) -> str:
    """ "; đơn vị sử dụng Công ty …" cho trường câu hỏi hỏi kèm."""
    own = fields.get(record["id"], {})
    parts = [
        f"{lower_first(label)} {clean_value(own[key].get('value_text'))}"
        for key, label in labels.items()
        if own.get(key) is not None
    ]
    return "".join(f"; {part}" for part in parts)


def _with_list(lead: str, lines: list[str]) -> str:
    if len(lines) > MAX_LINES:
        return f"{lead} (xem bảng bên dưới)."
    return "\n".join([f"{lead}:", "", *(f"- {line}" for line in lines)])


def devices_answer(
    records: list[dict],
    fields: dict[int, dict[str, dict]],
    params: RecordsSummaryParams,
    labels: dict[str, str],
) -> str:
    """ "6 thiết bị có phạm vi đo ghi theo đơn vị bar:" + ký hiệu, số hiệu, phạm vi đo."""
    latest: dict[Any, dict] = {}
    for record in records:
        latest[record.get("device_id")] = record
    lines = [
        (
            f"{_model_serial(record)} {clean_value(record.get('range_text'))}"
            if record.get("range_text")
            else _model_serial(record)
        )
        + _asked(record, fields, labels)
        for record in latest.values()
    ]
    return _with_list(f"{len(latest)} thiết bị{filter_phrase(params)}", lines)


def _failed_items(records: list[dict], fields: dict[int, dict[str, dict]]) -> list[str]:
    items = []
    for record in records:
        if record.get("verdict") != "khong_dat":
            continue
        reason = verdict_reason(_verdict_text(fields, record))
        detail = f"{_model_serial(record)}, {reason}" if reason else _model_serial(record)
        items.append(f"{cert(record)} ({detail})")
    return items


def count_answer(
    records: list[dict], fields: dict[int, dict[str, dict]], params: RecordsSummaryParams
) -> str:
    """ "Sổ cái có 20 biên bản đã duyệt của 12 thiết bị (theo số hiệu); 2 không đạt: …"."""
    devices = {record.get("device_id") for record in records if record.get("device_id")}
    lead = (
        f"Sổ cái có {len(records)} biên bản đã duyệt{_period(params)} "
        f"của {len(devices)} thiết bị (theo số hiệu)"
    )
    failed = _failed_items(records, fields)
    if not failed:
        return f"{lead}; không có biên bản không đạt."
    tail = f": {join_vi(failed)}" if len(failed) <= MAX_LINES else ""
    return f"{lead}; {len(failed)} biên bản không đạt{tail}."


def list_answer(
    records: list[dict],
    fields: dict[int, dict[str, dict]],
    params: RecordsSummaryParams,
    labels: dict[str, str] | None = None,
) -> str:
    """Liệt kê biên bản: số lượng + từng biên bản (số, thiết bị, ngày, kết luận)."""
    one_device = bool(params.serial) and len({r.get("device_id") for r in records}) == 1
    if one_device:
        lead = f"{upper_first(device_name(records[0]))} có {len(records)} biên bản đã duyệt"
    else:
        lead = f"{len(records)} biên bản"
    lead += filter_phrase(params)
    lines = []
    for record in records:
        verdict = verdict_short(record, _verdict_text(fields, record))
        day = date_text(record.get("calibrated_at"))
        asked = _asked(record, fields, labels or {})
        if one_device:
            lines.append(f"{cert(record)} ngày {day}: {verdict}{asked}")
        else:
            lines.append(
                f"{cert(record)} ({_model_serial(record, ', ')}), ngày {day}: {verdict}{asked}"
            )
    return _with_list(lead, lines)


def summary_answer(
    records: list[dict],
    fields: dict[int, dict[str, dict]],
    params: RecordsSummaryParams,
    labels: dict[str, str] | None = None,
) -> str:
    if params.subject == "devices":
        return devices_answer(records, fields, params, labels or {})
    if is_overview(params):
        return count_answer(records, fields, params)
    return list_answer(records, fields, params, labels)


def history_answer(history: dict[str, Any]) -> str | None:
    """ "Thiết bị số hiệu 1045 có 3 lần kiểm định đã duyệt: …" (dòng thời gian sổ cái)."""
    records = history.get("records") or []
    if not records:
        return None
    serial = (history.get("device") or {}).get("serial_no") or "(không số hiệu)"
    lines = [
        date_text(record.get("calibrated_at"))
        + (f" (biên bản {record['cert_no']})" if record.get("cert_no") else "")
        + f": {str(record.get('verdict_label') or record.get('verdict') or '—').lower()}"
        for record in records
    ]
    return _with_list(f"Thiết bị số hiệu {serial} có {len(records)} lần kiểm định đã duyệt", lines)
