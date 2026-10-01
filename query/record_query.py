"""Truy vấn biên bản có cấu trúc cho chat số liệu (Pha R, spec §8).

Resolver ``record_lookup`` (một / vài biên bản cụ thể); ``records_summary`` ở
``query.record_summary``. Mọi câu SQL do người viết, tham số luôn được bind, chỉ đọc
view đã duyệt (``v_record_detail``, ``v_record_field``, ``v_measurement_detail``) — P3.

Mỗi câu hỏi trả MỘT câu trả lời tất định ghép từ đúng các ô của bảng đi kèm
(``query.record_answer_lookup``) + bảng của điều được hỏi.

Bất biến:
- P1: mỗi ô mang tham chiếu xuất xứ (``record`` + khóa trường, hoặc ``measurement``).
- P2: giá trị luôn hiển thị NGUYÊN VĂN biên bản; không tính ra số mới.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from query.answer_phrases import cert
from query.record_answer import extreme_answer
from query.record_answer_lookup import StepResult, identity_answer, lookup_answer, record_parts
from query.record_cells import (
    IDENTITY_COLUMNS,
    VALUE_TOLERANCE,
    field_cell,
    fields_by_record,
    find_records,
    identity_cells,
    load_points,
    point_cell,
    record_cell,
    verdict_cell,
)
from query.record_fields import (
    IDENTITY_KEYS,
    VERDICT_KEY,
    FieldCatalog,
    content_tokens,
    field_catalog,
    label_words,
    load_cells,
)
from query.record_intents import RecordLookupParams, RecordsSummaryParams
from query.record_summary import _rank_tables, resolve_records_summary, summary_records
from query.table_model import (
    LEDGER_NOTE,
    Cell,
    Column,
    DataPayload,
    DataTable,
    _citations_for_tables,
    empty_payload,
    make_payload,
)
from records.columns import role_for_column

__all__ = [
    "RECORD_RESOLVERS",
    "_rank_tables",
    "extreme_answer",
    "resolve_record_lookup",
    "resolve_records_summary",
    "summary_records",
]

MAX_CARDS = 3
_MIN_REASON_OVERLAP = 3
_FALLBACK_POINT_COLUMNS = ("Thông số", "Danh nghĩa", "Giá trị xác định", "Giá trị cho phép")
# Trường định danh → tham số dùng nó làm BỘ CHỌN. Trường định danh câu hỏi nhắc tới mà
# không phải bộ chọn ("… ngày 10/07/2024 có số biên bản là bao nhiêu?", "biên bản 011/2024
# kiểm định ngày nào?") là điều được hỏi: trả định danh của biên bản, không cả phiếu.
_IDENTITY_SELECTORS = {
    "so": "cert_no",
    "ngay_kiem_dinh": "calibrated_on",
    "so_hieu": "serial",
    "ky_hieu": "model_code",
}
_CERT_KEY = "so"
_DEVICE_NAME_KEY = "ten_trang_bi_dl_tn"


# ── Bảng trường đầu mục ───────────────────────────────────────────────────────


def _fields_table(
    records: list[dict], fields: dict[int, dict[str, dict]], keys: list[str], catalog: FieldCatalog
) -> DataTable:
    columns = [*IDENTITY_COLUMNS]
    columns += [Column(key, catalog.field_label(key)) for key in keys if key != VERDICT_KEY]
    if VERDICT_KEY in keys:
        columns.append(Column(VERDICT_KEY, "Kết luận"))
    rows = []
    for record in records:
        own = fields.get(record["id"], {})
        row = identity_cells(record)
        for key in keys:
            if key == VERDICT_KEY:
                row[key] = verdict_cell(record, own)
            else:
                row[key] = field_cell(record, own.get(key))
        rows.append(row)
    return DataTable(
        title="Thông tin biên bản",
        columns=columns,
        rows=rows,
        total=len(rows),
        note="Giá trị nguyên văn biên bản đã duyệt; bấm vào ô để mở dòng nguồn.",
    )


def _identity_table(records: list[dict]) -> DataTable:
    rows = [
        {
            **identity_cells(record),
            "owner": record_cell(record, record.get("owner_org"), "don_vi_su_dung"),
        }
        for record in records
    ]
    return DataTable(
        title="Thông tin biên bản",
        columns=[*IDENTITY_COLUMNS, Column("owner", "Đơn vị sử dụng")],
        rows=rows,
        total=len(rows),
        note="Giá trị nguyên văn biên bản đã duyệt; bấm vào ô để mở dòng nguồn.",
    )


def _record_cards(records: list[dict], fields: dict[int, dict[str, dict]]) -> list[DataTable]:
    tables = []
    for record in records[:MAX_CARDS]:
        rows = [
            {"label": Cell(text=row["label"]), "value": field_cell(record, row)}
            for row in fields.get(record["id"], {}).values()
        ]
        tables.append(
            DataTable(
                title=f"Biên bản {cert(record)} · số hiệu {record.get('serial_no') or '—'}",
                columns=[Column("label", "Trường"), Column("value", "Giá trị")],
                rows=rows,
                total=len(rows),
            )
        )
    return tables


# ── Bảng kết quả ──────────────────────────────────────────────────────────────


def _cell_map(point: dict) -> dict[str, str]:
    return {
        (str(cell.get("column") or "").strip() or "—"): cell.get("text")
        for cell in load_cells(point.get("cells"))
    }


def _asked_columns(names: list[str], focus: frozenset[str]) -> frozenset[str]:
    """Cột câu hỏi nhắc tới ("áp suất khí quyển"): mọi từ mang nghĩa của nhãn có trong câu."""
    return frozenset(
        name for name in names if len(label_words(name)) >= 2 and label_words(name) <= focus
    )


def _cell_columns(points: list[dict], focus: frozenset[str] = frozenset()) -> list[str]:
    """Tên cột theo thứ tự biên bản; cột câu hỏi nhắc tới đưa lên sau cột đầu (STT)."""
    names: list[str] = []
    for point in points:
        for name in _cell_map(point):
            if name not in names:
                names.append(name)
    if not focus or len(names) < 2:
        return names
    asked = _asked_columns(names, focus)
    # Cột STT và cột giá trị danh nghĩa giữ ở đầu để dòng vẫn đọc được là điểm đo nào.
    head = names[:1] + [name for name in names[1:] if "danh nghĩa" in name.casefold()]
    rest = [name for name in names if name not in head]
    return head + [name for name in rest if name in asked] + [n for n in rest if n not in asked]


def _step_rows(points: list[dict], names: list[str]) -> list[dict[str, Cell]]:
    rows = []
    for point in points:
        cells = _cell_map(point)
        if cells:
            rows.append(
                {
                    f"c{index}": point_cell(point, cells.get(name))
                    for index, name in enumerate(names)
                }
            )
            continue
        rows.append(
            {
                "c0": Cell(text=point.get("label") or "—"),
                "c1": point_cell(point, point.get("nominal_text")),
                "c2": point_cell(point, point.get("measured_text")),
                "c3": point_cell(point, point.get("limit_text")),
            }
        )
    return rows


def _filter_nominal(points: list[dict], nominal: float | None) -> tuple[list[dict], bool]:
    """Chỉ dòng có giá trị danh nghĩa bằng giá trị được hỏi; không dòng nào thì giữ cả bảng."""
    if nominal is None:
        return points, False
    tolerance = VALUE_TOLERANCE * max(1.0, abs(nominal))
    matched = [
        point
        for point in points
        if point.get("nominal_value") is not None
        and abs(float(point["nominal_value"]) - nominal) <= tolerance
    ]
    return (matched, True) if matched else (points, False)


def _step_results(
    session: Session,
    records: list[dict],
    steps: list[str],
    catalog: FieldCatalog,
    nominal: float | None,
    focus: frozenset[str] = frozenset(),
) -> list[StepResult]:
    """Dòng của từng bảng được hỏi trong từng biên bản, đúng thứ tự và cột sẽ hiển thị."""
    points = load_points(session, [record["id"] for record in records], steps)
    results = []
    for record in records:
        for step in steps:
            own = [p for p in points if p["record_id"] == record["id"] and p["step_code"] == step]
            own, filtered = _filter_nominal(own, nominal)
            if not own:
                continue
            names = _cell_columns(own, focus) or list(_FALLBACK_POINT_COLUMNS)
            results.append(
                StepResult(
                    record_id=record["id"],
                    title=catalog.table_title(step, record.get("procedure_id")),
                    points=tuple(own),
                    names=tuple(names),
                    asked=_asked_columns(names, focus),
                    filtered=filtered,
                )
            )
    return results


def _step_table(result: StepResult, record: dict) -> DataTable:
    note = "Nguyên văn từng ô của bảng trong biên bản."
    if result.filtered:
        note = "Chỉ dòng có giá trị danh nghĩa được hỏi. " + note
    names = list(result.names)
    return DataTable(
        title=f"{result.title} · biên bản {cert(record)}",
        columns=[Column(f"c{index}", name) for index, name in enumerate(names)],
        rows=_step_rows(list(result.points), names),
        total=len(result.points),
        note=note,
    )


def _covered_by_columns(
    keys: list[str], results: list[StepResult], catalog: FieldCatalog
) -> list[str]:
    """Trường đầu mục mà cột được hỏi của dòng đã lọc đã trả lời.

    "Tại điểm đo 2 500, nhiệt độ và độ ẩm môi trường là bao nhiêu" hỏi ô của DÒNG đó,
    không phải điều kiện môi trường ghi ở đầu biên bản.
    """
    words = frozenset().union(
        *(label_words(name) for result in results if result.filtered for name in result.asked)
    )
    return [
        key
        for key in keys
        if key != VERDICT_KEY and words and label_words(catalog.field_label(key)) <= words
    ]


def _row_word(points: list[dict]) -> str:
    """ "điểm" cho bảng theo điểm danh nghĩa (Bảng A.5), "dòng" cho bảng khác."""
    for point in points:
        for cell in load_cells(point.get("cells")):
            if role_for_column(str(cell.get("column") or "")) == "nominal":
                return "điểm"
    return "dòng"


def _across_records(
    session: Session, records: list[dict], steps: list[str], catalog: FieldCatalog
) -> str | None:
    """ "Bảng A.5 … có 10 điểm ở cả 20 biên bản đã duyệt" (đếm dòng, không tính số liệu)."""
    procedures = {record.get("procedure_id") for record in records}
    everyone = [
        record
        for record in summary_records(session, RecordsSummaryParams())
        if record.get("procedure_id") in procedures
    ]
    points = load_points(session, [record["id"] for record in everyone], steps)
    sentences = []
    for step in steps:
        own = [point for point in points if point["step_code"] == step]
        counts: dict[int, int] = {}
        for point in own:
            counts[point["record_id"]] = counts.get(point["record_id"], 0) + 1
        if not counts:
            continue
        title = catalog.table_title(step, next(iter(procedures)))
        word = _row_word(own)
        by_size: dict[int, int] = {}
        for size in counts.values():
            by_size[size] = by_size.get(size, 0) + 1
        if len(by_size) == 1:
            size = next(iter(by_size))
            sentences.append(f"{title} có {size} {word} ở cả {len(counts)} biên bản đã duyệt.")
        else:
            spread = "; ".join(
                f"{size} {word} ở {count} biên bản" for size, count in sorted(by_size.items())
            )
            sentences.append(f"{title}: {spread}.")
    return " ".join(sentences) or None


# ── Căn cứ kết luận không đạt ────────────────────────────────────────────────


def _reason_points(points: list[dict], reason: str, catalog: FieldCatalog) -> list[dict]:
    """Dòng số liệu mà kết luận "không đạt" viện dẫn (so từ ngữ, không so số)."""
    words = content_tokens(reason)
    titles = {(table.procedure_id, table.step_code): table.words for table in catalog.tables}
    chosen = []
    for point in points:
        key = (point.get("procedure_id"), point.get("step_code") or "")
        title_words = titles.get(key, frozenset())
        own_words = content_tokens(point.get("label"))
        if (title_words and title_words <= words) or len(own_words & words) >= _MIN_REASON_OVERLAP:
            chosen.append(point)
    return chosen


def _failure_points(
    session: Session, records: list[dict], fields: dict[int, dict[str, dict]], catalog: FieldCatalog
) -> dict[int, list[dict]]:
    failed = [record for record in records if record.get("verdict") == "khong_dat"]
    points = load_points(session, [record["id"] for record in failed])
    result = {}
    for record in failed:
        reason = (fields.get(record["id"], {}).get(VERDICT_KEY) or {}).get("value_text") or ""
        own = [point for point in points if point["record_id"] == record["id"]]
        chosen = _reason_points(own, reason, catalog)
        if chosen:
            result[record["id"]] = chosen
    return result


def _point_label(point: dict) -> str:
    """Nhãn dòng; bảng không có cột nhãn (Bảng A.2) thì tên cột giá trị ("Giá trị trung bình, s")."""
    if point.get("label"):
        return str(point["label"])
    for cell in load_cells(point.get("cells")):
        if role_for_column(str(cell.get("column") or "")) == "measured":
            return str(cell.get("column"))
    return "—"


def _failure_table(record: dict, chosen: list[dict], catalog: FieldCatalog) -> DataTable:
    rows = [
        {
            "table": Cell(
                text=catalog.table_title(point.get("step_code") or "", point.get("procedure_id"))
            ),
            "label": Cell(text=_point_label(point)),
            "measured": point_cell(point, point.get("measured_text")),
            "limit": point_cell(point, point.get("limit_text")),
        }
        for point in chosen
    ]
    return DataTable(
        title=f"Căn cứ kết luận không đạt · biên bản {cert(record)}",
        columns=[
            Column("table", "Bảng"),
            Column("label", "Thông số"),
            Column("measured", "Giá trị xác định"),
            Column("limit", "Giá trị cho phép"),
        ],
        rows=rows,
        total=len(rows),
        note="Dòng số liệu mà kết luận của biên bản nhắc tới; người đọc tự đối chiếu.",
    )


# ── record_lookup ─────────────────────────────────────────────────────────────


def _no_match(session: Session, params: RecordLookupParams) -> DataPayload:
    """Không có biên bản khớp: liệt kê biên bản hiện có của thiết bị (nếu biết số hiệu)."""
    title = "Tra cứu biên bản"
    if not params.serial:
        return empty_payload(
            "record_lookup", title, "Không tìm thấy biên bản đã duyệt khớp yêu cầu."
        )
    records = find_records(session, RecordLookupParams(serial=params.serial))
    if not records:
        return empty_payload(
            "record_lookup",
            title,
            f"Không có biên bản đã duyệt của thiết bị số hiệu {params.serial}.",
        )
    fields = fields_by_record(session, [record["id"] for record in records])
    table = _fields_table(records, fields, [VERDICT_KEY], field_catalog(session))
    table.title = f"Biên bản đã duyệt của thiết bị số hiệu {params.serial}"
    table.note = "Không có biên bản khớp số biên bản/ngày được hỏi; đây là các biên bản hiện có."
    certs = ", ".join(cert(record) for record in records)
    return make_payload(
        intent="record_lookup",
        title=title,
        note=LEDGER_NOTE,
        tables=[table],
        citations=_citations_for_tables(session, [table]),
        answer=(
            "Không có biên bản đã duyệt khớp số biên bản / ngày được hỏi của thiết bị số "
            f"hiệu {params.serial}; các biên bản hiện có: {certs}."
        ),
    )


def _lookup_tables(
    records: list[dict],
    fields: dict[int, dict[str, dict]],
    keys: list[str],
    catalog: FieldCatalog,
    results: list[StepResult],
    failures: dict[int, list[dict]],
    *,
    identity: bool,
) -> list[DataTable]:
    by_id = {record["id"]: record for record in records}
    tables: list[DataTable] = []
    if keys:
        tables.append(_fields_table(records, fields, keys, catalog))
    elif identity:
        tables.append(_identity_table(records))
    elif not results:
        tables.extend(_record_cards(records, fields))
    tables.extend(_step_table(result, by_id[result.record_id]) for result in results)
    tables.extend(_failure_table(by_id[rid], chosen, catalog) for rid, chosen in failures.items())
    return tables or [_fields_table(records, fields, [VERDICT_KEY], catalog)]


def resolve_record_lookup(session: Session, params: RecordLookupParams) -> DataPayload:
    """Biên bản cụ thể: trường được hỏi, bảng được hỏi, căn cứ kết luận không đạt."""
    records = find_records(session, params)
    if not records:
        return _no_match(session, params)
    catalog = field_catalog(session)
    fields = fields_by_record(session, [record["id"] for record in records])
    steps = list(params.steps)
    results = _step_results(
        session, records, steps, catalog, params.nominal, frozenset(params.focus_words)
    )
    # "Tên trang bị ĐL-TN" là trường định danh nhưng không bao giờ là bộ chọn: hỏi tới thì
    # trả như một trường thường.
    keys = [
        key
        for key in dict.fromkeys(params.fields)
        if key not in IDENTITY_KEYS or key == _DEVICE_NAME_KEY
    ]
    covered = _covered_by_columns(keys, results, catalog)
    keys = [key for key in keys if key not in covered]
    failures = _failure_points(session, records, fields, catalog) if VERDICT_KEY in keys else {}
    asked_identity = [
        key
        for key in params.fields
        if key in _IDENTITY_SELECTORS and not getattr(params, _IDENTITY_SELECTORS[key])
    ]
    identity = not keys and not steps and bool(asked_identity)
    tables = _lookup_tables(records, fields, keys, catalog, results, failures, identity=identity)

    if identity:
        answer: str | None = identity_answer(records, cert_first=_CERT_KEY in asked_identity)
    else:
        parts = {
            record["id"]: record_parts(
                record,
                fields.get(record["id"], {}),
                keys,
                catalog,
                results,
                failures.get(record["id"], []),
            )
            for record in records
        }
        answer = lookup_answer(records, parts)
    if params.across_records and steps:
        overview = _across_records(session, records, steps, catalog)
        if overview:
            answer = f"{overview}\n\n{answer}" if answer else overview
    subject = params.cert_no or params.serial or params.model_code
    return make_payload(
        intent="record_lookup",
        title=f"Biên bản {subject}" if subject else "Tra cứu biên bản",
        note=LEDGER_NOTE,
        tables=tables,
        citations=_citations_for_tables(session, tables),
        answer=answer,
    )


RECORD_RESOLVERS: dict[str, Any] = {
    "record_lookup": resolve_record_lookup,
    "records_summary": resolve_records_summary,
}
