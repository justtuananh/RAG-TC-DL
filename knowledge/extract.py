"""Chạy bộ luật và ghi kết quả vào sổ cái ở trạng thái ``pending`` (spec §5.3, §5.4).

Cầu nối giữa bộ luật thuần hàm (``knowledge.rules``) và DB:

- chạy luật trên văn bản Markdown QTKĐ;
- quy đổi ``value_min``/``value_max`` về SI nếu đơn vị nhận diện chắc chắn; đơn
  vị lạ → để trống số, giữ ``value_text``, hạ điểm tin cậy (spec §6);
- khi nạp lại, extraction cũ của tài liệu chuyển sang ``superseded`` chứ không
  bị xóa (lịch sử duyệt là dữ liệu nghiệp vụ), và extraction mới trỏ
  ``supersedes_id`` về bản cũ cùng luật + mục;
- mọi bản ghi mới đều ``pending`` — P3 chỉ lộ dữ liệu đã duyệt qua view.

Không commit trong đây; tầng gọi (``ingestion_jobs`` hoặc script) quyết định.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import or_

from db.models import (
    DeviceType,
    Extraction,
    ExtractionStatus,
    Procedure,
    ProcedureFact,
    ProcedureStandard,
    Term,
    Unit,
)
from knowledge import llm_extract
from knowledge import units as units_module
from knowledge.procedure import infer_device_type, parse_edition, parse_procedure_header
from knowledge.reference import device_type_aliases
from knowledge.rules import RuleHit, extract_all
from knowledge.rules import extract_appendix as rules_extract_appendix
from knowledge.seed_data import KNOWN_PROCEDURE_DEVICE_TYPES

EXTRACTOR_VERSION = "v1"
# Điểm tin cậy trần cho dòng có đơn vị không nhận diện được (spec §6).
UNRESOLVED_UNIT_CONFIDENCE = 0.6

_SUPERSEDE_STATUSES = (ExtractionStatus.PENDING, ExtractionStatus.APPROVED)


@dataclass
class ExtractionSummary:
    """Kết quả một lần trích xuất; phục vụ log và test."""

    facts: int = 0
    standards: int = 0
    terms: int = 0
    superseded: int = 0
    by_fact_kind: dict[str, int] = field(default_factory=dict)

    @property
    def total(self) -> int:
        return self.facts + self.standards + self.terms

    def as_dict(self) -> dict:
        return {
            "facts": self.facts,
            "standards": self.standards,
            "terms": self.terms,
            "total": self.total,
            "superseded": self.superseded,
            "by_fact_kind": dict(self.by_fact_kind),
        }


def ensure_procedure(session, document, text: str) -> Procedure | None:
    """Tìm procedure của tài liệu; tạo mới từ đầu mục Markdown nếu chưa có.

    Giữ ``procedure.document_id`` để truy nguyên P1. Trả ``None`` nếu văn bản
    không có mã QTKĐ — khi đó dữ kiện vẫn được ghi với ``procedure_id`` rỗng.
    """
    procedure = session.query(Procedure).filter(Procedure.document_id == document.id).one_or_none()
    if procedure is not None:
        return procedure

    header = parse_procedure_header(text)
    if header is None:
        return None

    procedure = session.query(Procedure).filter(Procedure.number == header.number).one_or_none()
    if procedure is None:
        procedure = Procedure(number=header.number)
        session.add(procedure)
    procedure.year = header.year
    procedure.title = header.title
    procedure.document_id = document.id
    procedure.edition = parse_edition(document.file_stem)

    candidates = [
        (item.name_vi, device_type_aliases(item)) for item in session.query(DeviceType).all()
    ]
    device_type_name = infer_device_type(header.title, candidates)
    if device_type_name is None:
        device_type_name = KNOWN_PROCEDURE_DEVICE_TYPES.get(header.number)
    device_type = (
        session.query(DeviceType).filter(DeviceType.name_vi == device_type_name).one_or_none()
        if device_type_name
        else None
    )
    procedure.device_type_id = device_type.id if device_type is not None else None
    session.flush()
    return procedure


def _supersede_previous(
    session, document, *, extractor_prefix: str | None = None
) -> tuple[dict[tuple[str, str | None], int], int]:
    """Chuyển extraction cũ (pending/approved) sang ``superseded``.

    Trả ``(bản đồ (extractor, section_path) → id mới nhất, số dòng đã chuyển)``.
    Bản đồ dùng để gắn ``supersedes_id`` cho bản mới cùng luật + mục.

    ``extractor_prefix`` giới hạn phạm vi (ví dụ ``"llm:"``) để bước trích xuất
    §6 bằng LLM không vô hiệu hóa các dòng luật vừa ghi trong cùng lần nạp.
    """
    query = session.query(Extraction).filter(
        Extraction.document_id == document.id,
        Extraction.status.in_(_SUPERSEDE_STATUSES),
    )
    if extractor_prefix:
        query = query.filter(Extraction.extractor.like(f"{extractor_prefix}%"))
    previous = query.order_by(Extraction.id).all()
    latest: dict[tuple[str, str | None], int] = {}
    for row in previous:
        latest[(row.extractor, row.section_path)] = row.id
        row.status = ExtractionStatus.SUPERSEDED
    return latest, len(previous)


def extract_and_store(
    session,
    document,
    text: str,
    *,
    procedure: Procedure | None = None,
    supersede: bool = True,
) -> ExtractionSummary:
    """Chạy luật và ghi extraction + bảng dữ kiện ``pending``; trả tổng kết."""
    hits = extract_all(text)
    summary = ExtractionSummary()
    if not hits:
        return summary

    if procedure is None:
        procedure = ensure_procedure(session, document, text)

    previous = _supersede_previous(session, document) if supersede else ({}, 0)
    supersedes_map, summary.superseded = previous

    unit_defs = units_module.load_unit_defs(session)
    unit_rows = {row.code: row for row in session.query(Unit).all()}

    for hit in hits:
        confidence = hit.confidence
        unit_id: int | None = None
        si_min: float | None = None
        si_max: float | None = None

        if hit.kind == "fact" and (hit.unit or hit.unit_min or hit.unit_max):
            min_text = hit.unit_min or hit.unit
            max_text = hit.unit_max or hit.unit
            min_def = units_module.resolve_unit(min_text, unit_defs) if min_text else None
            max_def = units_module.resolve_unit(max_text, unit_defs) if max_text else None
            if (min_text and min_def is None) or (max_text and max_def is None):
                confidence = min(confidence, UNRESOLVED_UNIT_CONFIDENCE)
            if hit.value_min is not None and min_def is not None:
                si_min = units_module.to_si(hit.value_min, min_def)
            if hit.value_max is not None and max_def is not None:
                si_max = units_module.to_si(hit.value_max, max_def)
            codes = {defn.code for defn in (min_def, max_def) if defn is not None}
            if len(codes) == 1:
                row = unit_rows.get(next(iter(codes)))
                unit_id = row.id if row is not None else None

        extraction = Extraction(
            document_id=document.id,
            section_path=hit.section_path,
            quote=hit.quote,
            char_start=hit.char_start,
            char_end=hit.char_end,
            extractor=hit.extractor,
            extractor_version=EXTRACTOR_VERSION,
            confidence=confidence,
            status=ExtractionStatus.PENDING,
            supersedes_id=supersedes_map.get((hit.extractor, hit.section_path)),
        )
        session.add(extraction)
        session.flush()

        if hit.kind == "fact":
            session.add(
                ProcedureFact(
                    extraction_id=extraction.id,
                    procedure_id=procedure.id if procedure is not None else None,
                    fact_kind=hit.fact_kind,
                    label=hit.label,
                    rel_op=hit.rel_op,
                    value_min=si_min,
                    value_max=si_max,
                    unit_id=unit_id,
                    value_text=hit.value_text,
                    condition_text=hit.condition_text,
                )
            )
            summary.facts += 1
            key = hit.fact_kind or ""
            summary.by_fact_kind[key] = summary.by_fact_kind.get(key, 0) + 1
        elif hit.kind == "standard":
            session.add(
                ProcedureStandard(
                    extraction_id=extraction.id,
                    procedure_id=procedure.id if procedure is not None else None,
                    ord=hit.ord,
                    name_vi=hit.name_vi,
                    range_text=hit.range_text,
                    accuracy_text=hit.accuracy_text,
                    note=hit.note,
                )
            )
            summary.standards += 1
        elif hit.kind == "term":
            session.add(
                Term(
                    extraction_id=extraction.id,
                    procedure_id=procedure.id if procedure is not None else None,
                    term_vi=hit.term_vi,
                    term_en=hit.term_en,
                    definition=hit.definition,
                )
            )
            summary.terms += 1

    session.flush()
    return summary


def run_rules(text: str) -> list[RuleHit]:
    """Tiện lợi cho test/eval: chạy luật mà không cần DB."""
    return extract_all(text)


# ── Sprint 5: trích xuất §6 bằng LLM, ghi ở trạng thái ``pending`` ────────────
# LLM chỉ đề xuất; hàng rào xác minh quote nằm ở ``knowledge.llm_extract``. Ở đây
# chỉ ánh xạ dữ kiện ĐÃ XÁC MINH sang ``extraction`` + ``procedure_fact``. Mọi
# bản ghi đều ``pending`` nên P3 vẫn chỉ lộ dữ liệu đã duyệt qua view.


def _working_range_si(
    session, procedure: Procedure | None
) -> tuple[float | None, float | None] | None:
    """Phạm vi đo SI của QTKĐ từ dữ kiện ``working_range`` đã ghi (P1)."""
    if procedure is None:
        return None
    row = (
        session.query(ProcedureFact)
        .filter(
            ProcedureFact.procedure_id == procedure.id,
            ProcedureFact.fact_kind == "working_range",
            or_(ProcedureFact.value_min.isnot(None), ProcedureFact.value_max.isnot(None)),
        )
        .order_by(ProcedureFact.id.desc())
        .first()
    )
    if row is None:
        return None
    return (row.value_min, row.value_max)


def _convert_claim(
    claim: llm_extract.NumericClaim,
    unit_defs,
    unit_rows: dict[str, Unit],
) -> tuple[float | None, int | None]:
    """Quy đổi một con số §6 về SI; đơn vị lạ → để trống số, giữ ``value_text``."""
    unit_def = units_module.resolve_unit(claim.unit, unit_defs) if claim.unit else None
    if unit_def is None:
        return None, None
    si_value = units_module.to_si(claim.value, unit_def)
    row = unit_rows.get(unit_def.code)
    return si_value, (row.id if row is not None else None)


def _section6_fact_rows(
    fact: llm_extract.Section6Fact,
    unit_defs,
    unit_rows: dict[str, Unit],
) -> list[dict]:
    """Ánh xạ một dữ kiện §6 đã xác minh sang các dòng ``procedure_fact``.

    Dữ kiện sai số có thể sinh HAI dòng liên kết cùng một extraction: giới hạn
    chính và giá trị sàn (spec §5.4, ví dụ "± 3% ... nhưng không nhỏ hơn ± 0,15
    bar"). Công thức sinh một dòng ``formula`` với nguyên văn LaTeX.
    """
    if fact.fact_kind == llm_extract.FORMULA_KIND:
        return [
            {
                "fact_kind": llm_extract.FORMULA_KIND,
                "label": fact.label or "Công thức",
                "rel_op": None,
                "value_min": None,
                "value_max": None,
                "unit_id": None,
                "value_text": fact.formula,
                "condition_text": None,
            }
        ]

    rows: list[dict] = []
    if fact.limit is not None:
        si_value, unit_id = _convert_claim(fact.limit, unit_defs, unit_rows)
        rows.append(
            {
                "fact_kind": llm_extract.MAX_ERROR_KIND,
                "label": fact.label or "Giới hạn sai số cho phép",
                "rel_op": fact.rel_op or "=",
                "value_min": si_value,
                "value_max": si_value,
                "unit_id": unit_id,
                "value_text": fact.value_text or fact.limit.quote,
                "condition_text": fact.condition_text,
            }
        )
    if fact.floor is not None:
        si_value, unit_id = _convert_claim(fact.floor, unit_defs, unit_rows)
        label = f"{fact.label} (giá trị sàn)" if fact.label else "Giá trị sàn"
        rows.append(
            {
                "fact_kind": llm_extract.MAX_ERROR_KIND,
                "label": label,
                "rel_op": "±",
                "value_min": si_value,
                "value_max": si_value,
                "unit_id": unit_id,
                "value_text": fact.floor.quote,
                "condition_text": None,
            }
        )
    return rows


def extract_section6_and_store(
    session,
    document,
    text: str,
    *,
    procedure: Procedure | None = None,
    client=None,
    supersede: bool = True,
    unit_defs=None,
    working_range_si: tuple[float | None, float | None] | None = None,
) -> ExtractionSummary:
    """Chạy LLM trích xuất §6 và ghi extraction + dữ kiện ``pending``.

    Thất bại an toàn: Ollama chưa lên/model chưa pull/JSON hỏng → không ghi gì,
    trả tổng kết rỗng. Không commit; tầng gọi quyết định. ``supersede`` chỉ áp
    cho các extraction do LLM sinh (tiền tố ``llm:``), không đụng dòng luật.
    """
    summary = ExtractionSummary()
    client = client or llm_extract.default_client()
    if procedure is None:
        procedure = ensure_procedure(session, document, text)
    if unit_defs is None:
        unit_defs = units_module.load_unit_defs(session)
    if working_range_si is None:
        working_range_si = _working_range_si(session, procedure)

    model_name = getattr(client, "model_name", None) or "unknown"
    result = llm_extract.extract_section6(
        text,
        client,
        unit_defs=unit_defs,
        working_range_si=working_range_si,
        model_name=model_name,
    )
    if not result.facts:
        return summary

    extractor = f"llm:{model_name}"
    if supersede:
        supersedes_map, summary.superseded = _supersede_previous(
            session, document, extractor_prefix="llm:"
        )
    else:
        supersedes_map = {}

    unit_rows = {row.code: row for row in session.query(Unit).all()}
    for verified in result.facts:
        extraction = Extraction(
            document_id=document.id,
            section_path=verified.section_path,
            quote=verified.fact.quote,
            char_start=verified.char_start,
            char_end=verified.char_end,
            extractor=extractor,
            extractor_version=EXTRACTOR_VERSION,
            confidence=verified.confidence,
            status=ExtractionStatus.PENDING,
            supersedes_id=supersedes_map.get((extractor, verified.section_path)),
        )
        session.add(extraction)
        session.flush()

        for row in _section6_fact_rows(verified.fact, unit_defs, unit_rows):
            session.add(
                ProcedureFact(
                    extraction_id=extraction.id,
                    procedure_id=procedure.id if procedure is not None else None,
                    **row,
                )
            )
            summary.facts += 1
            key = row["fact_kind"]
            summary.by_fact_kind[key] = summary.by_fact_kind.get(key, 0) + 1

    session.flush()
    return summary


# ── Sprint 7: Phụ lục A (sơ đồ trường biên bản) ───────────────────────────────
# Bước riêng giống §6: không nằm trong `extract_all` nên không đổi số dòng của
# luật lõi. Kết quả vẫn là `procedure_fact` loại `appendix_field` ở trạng thái
# `pending`; `records.template` chỉ đọc bản đã duyệt để dựng cấu hình đọc hồ sơ.


def extract_appendix_and_store(
    session,
    document,
    text: str,
    *,
    procedure: Procedure | None = None,
    supersede: bool = True,
) -> ExtractionSummary:
    """Rút trường Phụ lục A và ghi ``procedure_fact`` ``pending``; không commit."""
    hits = rules_extract_appendix(text)
    summary = ExtractionSummary()
    if not hits:
        return summary

    if procedure is None:
        procedure = ensure_procedure(session, document, text)

    supersedes_map: dict[tuple[str, str | None], int] = {}
    if supersede:
        supersedes_map, summary.superseded = _supersede_previous(
            session, document, extractor_prefix="rule:phuluc_a"
        )

    for hit in hits:
        extraction = Extraction(
            document_id=document.id,
            section_path=hit.section_path,
            quote=hit.quote,
            char_start=hit.char_start,
            char_end=hit.char_end,
            extractor=hit.extractor,
            extractor_version=EXTRACTOR_VERSION,
            confidence=hit.confidence,
            status=ExtractionStatus.PENDING,
            supersedes_id=supersedes_map.get((hit.extractor, hit.section_path)),
        )
        session.add(extraction)
        session.flush()
        session.add(
            ProcedureFact(
                extraction_id=extraction.id,
                procedure_id=procedure.id if procedure is not None else None,
                fact_kind=hit.fact_kind,
                label=hit.label,
                rel_op=hit.rel_op,
                value_min=None,
                value_max=None,
                unit_id=None,
                value_text=hit.value_text,
                condition_text=hit.condition_text,
            )
        )
        summary.facts += 1
        key = hit.fact_kind or ""
        summary.by_fact_kind[key] = summary.by_fact_kind.get(key, 0) + 1

    session.flush()
    return summary
