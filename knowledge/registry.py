"""Sổ đăng ký danh mục 877 trong Postgres: nạp bản nháp, duyệt, đọc bản đã duyệt.

Luồng giống bản tóm tắt và công thức: nạp file → bản nháp kèm báo cáo lỗi → người duyệt phê duyệt →
chat mới dùng. Mỗi loại danh mục chỉ có MỘT bản đã duyệt đang dùng; duyệt bản mới thì bản cũ chuyển
``replaced`` (giữ lại để đối chiếu). File gốc lưu ở ``paths.registry_dir``, không vào kho ``TC_DL/`` và
không vào Qdrant: câu hỏi chung được trả lời chính xác hơn từ bảng.

``load_approved`` trả ảnh chụp bất biến cho tầng truy hồi; ``generation()`` tăng mỗi khi bản đã duyệt đổi
để bộ nhớ đệm phía truy hồi tự dựng lại.
"""

from __future__ import annotations

import hashlib
import re
import threading
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from core.settings_loader import get_settings
from knowledge.catalog_codes import CatalogCode, parse_code, parse_codes
from knowledge.catalog_units import CatalogRange

_SAFE_NAME_RE = re.compile(r"[^\w.\- ]+", re.UNICODE)
_lock = threading.Lock()
_generation = 0


class RegistryError(Exception):
    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.status = status


# ── Ảnh chụp bản đã duyệt (bất biến, dùng cho truy hồi) ──────────────────────


@dataclass(frozen=True)
class ProcedureEntry:
    id: int
    source_file: str
    row: int
    code_raw: str
    code: CatalogCode | None
    title: str
    issuer: str
    field: str
    kind: str


@dataclass(frozen=True)
class CapabilityEntry:
    id: int
    source_file: str
    row: int
    kind: str
    name: str
    field: str
    params_raw: str
    procedures_raw: str
    codes: tuple[CatalogCode, ...]
    ranges: tuple[CatalogRange, ...]


@dataclass(frozen=True)
class StandardEntry:
    id: int
    source_file: str
    row: int
    name: str
    model: str
    serial: str
    characteristics_raw: str
    interval_raw: str
    interval_months: int | None
    field: str
    ranges: tuple[CatalogRange, ...]


@dataclass(frozen=True)
class RegistryData:
    procedures: tuple[ProcedureEntry, ...] = ()
    capabilities: tuple[CapabilityEntry, ...] = ()
    standards: tuple[StandardEntry, ...] = ()

    @property
    def empty(self) -> bool:
        return not (self.procedures or self.capabilities or self.standards)


def generation() -> int:
    return _generation


def _bump() -> None:
    global _generation
    with _lock:
        _generation += 1


def _session():
    from db import SessionLocal

    return SessionLocal()


def _range(row) -> CatalogRange:
    return CatalogRange(
        label=row.label or "",
        quantity=row.quantity,
        min_si=Decimal(row.min_si) if row.min_si is not None else None,
        max_si=Decimal(row.max_si),
        text=row.text,
    )


def _approved_sources(session) -> dict[str, object]:
    from db.models import CatalogSource, CatalogSourceStatus

    rows = (
        session.query(CatalogSource)
        .filter(CatalogSource.status == CatalogSourceStatus.APPROVED.value)
        .order_by(CatalogSource.reviewed_at.desc())
        .all()
    )
    result: dict[str, object] = {}
    for source in rows:
        result.setdefault(source.kind, source)
    return result


def _procedures(session, source) -> tuple[ProcedureEntry, ...]:
    from db.models import CatalogProcedure

    rows = (
        session.query(CatalogProcedure)
        .filter(CatalogProcedure.source_id == source.id)
        .order_by(CatalogProcedure.row)
    )
    return tuple(
        ProcedureEntry(
            id=r.id,
            source_file=source.file_name,
            row=r.row,
            code_raw=r.code_raw,
            code=parse_code(r.code_raw),
            title=r.title or "",
            issuer=r.issuer or "",
            field=r.field or "",
            kind=r.kind,
        )
        for r in rows
    )


def _capabilities(session, source) -> tuple[CapabilityEntry, ...]:
    from db.models import Capability

    rows = session.query(Capability).filter(Capability.source_id == source.id).order_by(Capability.row)
    return tuple(
        CapabilityEntry(
            id=r.id,
            source_file=source.file_name,
            row=r.row,
            kind=r.kind,
            name=r.name,
            field=r.field or "",
            params_raw=r.params_raw or "",
            procedures_raw=r.procedures_raw or "",
            codes=tuple(code for p in r.procedures if (code := parse_code(p.code_raw)) is not None),
            ranges=tuple(_range(x) for x in r.ranges),
        )
        for r in rows
    )


def _standards(session, source) -> tuple[StandardEntry, ...]:
    from db.models import ReferenceStandard

    rows = (
        session.query(ReferenceStandard)
        .filter(ReferenceStandard.source_id == source.id)
        .order_by(ReferenceStandard.row)
    )
    return tuple(
        StandardEntry(
            id=r.id,
            source_file=source.file_name,
            row=r.row,
            name=r.name,
            model=r.model or "",
            serial=r.serial or "",
            characteristics_raw=r.characteristics_raw or "",
            interval_raw=r.interval_raw or "",
            interval_months=r.interval_months,
            field=r.field or "",
            ranges=tuple(_range(x) for x in r.ranges),
        )
        for r in rows
    )


def load_approved(session=None) -> RegistryData:
    """Mọi dòng của bản ĐÃ DUYỆT mới nhất mỗi loại danh mục (rỗng nếu chưa duyệt bản nào)."""
    own = session is None
    session = session or _session()
    try:
        sources = _approved_sources(session)
        procedures: tuple[ProcedureEntry, ...] = ()
        capabilities: list[CapabilityEntry] = []
        standards: tuple[StandardEntry, ...] = ()
        if "procedure" in sources:
            procedures = _procedures(session, sources["procedure"])
        for kind in ("capability_kd", "capability_hc"):
            if kind in sources:
                capabilities.extend(_capabilities(session, sources[kind]))
        if "standard" in sources:
            standards = _standards(session, sources["standard"])
        return RegistryData(procedures=procedures, capabilities=tuple(capabilities), standards=standards)
    finally:
        if own:
            session.close()


# ── Nạp bản nháp ─────────────────────────────────────────────────────────────


def _store_file(file_name: str, data: bytes, sha256: str) -> Path:
    directory = Path(get_settings().paths.registry_dir)
    directory.mkdir(parents=True, exist_ok=True)
    safe = _SAFE_NAME_RE.sub("_", Path(file_name).name).strip() or "danh_muc.docx"
    path = directory / f"{sha256[:12]}_{safe}"
    if not path.exists():
        path.write_bytes(data)
    return path


def _range_row(model, ordinal: int, value: CatalogRange):
    return model(
        ord=ordinal,
        label=value.label,
        quantity=value.quantity,
        min_si=value.min_si,
        max_si=value.max_si,
        text=value.text,
    )


def _add_procedures(session, source, parsed) -> None:
    from db.models import CatalogProcedure

    for item in parsed.procedures:
        code = item.code
        session.add(
            CatalogProcedure(
                source_id=source.id,
                row=item.row,
                code_raw=item.code_raw,
                code_key=code.key if code else None,
                prefix=code.prefix if code else None,
                number=code.number if code else None,
                year=code.year if code else None,
                title=item.title,
                issuer=item.issuer,
                field=item.field,
                kind=item.kind,
            )
        )


def _add_capabilities(session, source, parsed) -> None:
    from db.models import Capability, CapabilityProcedure, CapabilityRange

    for item in parsed.capabilities:
        capability = Capability(
            source_id=source.id,
            row=item.row,
            kind=item.kind,
            name=item.name,
            field=item.field,
            params_raw=item.params_raw,
            procedures_raw=item.procedures_raw,
        )
        capability.ranges = [_range_row(CapabilityRange, i, r) for i, r in enumerate(item.ranges)]
        capability.procedures = [
            CapabilityProcedure(ord=i, code_raw=code.raw, code_key=code.key) for i, code in enumerate(item.codes)
        ]
        session.add(capability)


def _add_standards(session, source, parsed) -> None:
    from db.models import ReferenceStandard, StandardRange

    for item in parsed.standards:
        standard = ReferenceStandard(
            source_id=source.id,
            row=item.row,
            name=item.name,
            model=item.model,
            serial=item.serial,
            characteristics_raw=item.characteristics_raw,
            interval_raw=item.interval_raw,
            interval_months=item.interval_months,
            field=item.field,
        )
        standard.ranges = [_range_row(StandardRange, i, r) for i, r in enumerate(item.ranges)]
        session.add(standard)


def import_file(file_name: str, data: bytes, user=None) -> dict:
    """Nạp một file danh mục thành bản NHÁP; trả thông tin nguồn kèm báo cáo lỗi."""
    from db.models import CatalogSource, CatalogSourceStatus
    from ingestion.registry_import import KIND_LABELS, parse_catalog

    if not file_name.lower().endswith(".docx"):
        raise RegistryError("Danh mục phải là file Word .docx.", 415)
    parsed = parse_catalog(data)
    sha256 = hashlib.sha256(data).hexdigest()
    session = _session()
    try:
        duplicate = (
            session.query(CatalogSource)
            .filter(
                CatalogSource.sha256 == sha256,
                CatalogSource.status.in_([CatalogSourceStatus.DRAFT.value, CatalogSourceStatus.APPROVED.value]),
            )
            .first()
        )
        if duplicate is not None:
            raise RegistryError(
                f"File này đã được nạp ({KIND_LABELS[duplicate.kind]}, trạng thái {duplicate.status}).", 409
            )
        path = _store_file(file_name, data, sha256)
        source = CatalogSource(
            kind=parsed.kind,
            file_name=Path(file_name).name,
            stored_path=str(path),
            sha256=sha256,
            title=parsed.title,
            status=CatalogSourceStatus.DRAFT.value,
            row_count=parsed.row_count,
            issues=[issue.as_dict() for issue in parsed.issues],
            revision=1,
            uploaded_by=getattr(user, "id", None),
        )
        session.add(source)
        session.flush()
        _add_procedures(session, source, parsed)
        _add_capabilities(session, source, parsed)
        _add_standards(session, source, parsed)
        session.commit()
        return _source_dict(source)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ── Duyệt ────────────────────────────────────────────────────────────────────


def _replace_approved(session, source) -> None:
    from db.models import CatalogSource, CatalogSourceStatus

    previous = (
        session.query(CatalogSource)
        .filter(
            CatalogSource.kind == source.kind,
            CatalogSource.status == CatalogSourceStatus.APPROVED.value,
            CatalogSource.id != source.id,
        )
        .all()
    )
    for old in previous:
        old.status = CatalogSourceStatus.REPLACED.value
        old.revision += 1


def decide(source_id: int, revision: int, *, approve: bool, note: str, user=None) -> dict:
    """Phê duyệt hoặc từ chối một bản nháp. Duyệt thì bản đã duyệt trước đó cùng loại thành ``replaced``."""
    from db.models import CatalogSource, CatalogSourceStatus

    session = _session()
    try:
        source = session.get(CatalogSource, source_id, with_for_update=True)
        if source is None:
            raise RegistryError("Không tìm thấy bản danh mục.", 404)
        if source.revision != revision:
            raise RegistryError("Bản danh mục đã được người khác thay đổi, hãy tải lại.", 409)
        if source.status != CatalogSourceStatus.DRAFT.value:
            raise RegistryError("Chỉ duyệt hoặc từ chối được bản nháp.", 409)
        if approve and any(issue.get("level") == "error" for issue in source.issues or []):
            raise RegistryError("Bản nháp còn lỗi mức nghiêm trọng, cần sửa file rồi nạp lại.", 422)
        if approve:
            _replace_approved(session, source)
        source.status = (CatalogSourceStatus.APPROVED if approve else CatalogSourceStatus.REJECTED).value
        source.reviewed_by = getattr(user, "id", None)
        source.reviewed_at = datetime.utcnow()
        source.review_note = note or None
        source.revision += 1
        session.commit()
        result = _source_dict(source)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    if approve:
        _bump()
    return result


def delete_source(source_id: int) -> None:
    """Xoá bản nháp / bị từ chối / đã thay thế. Bản đang dùng phải được thay bằng bản duyệt mới."""
    from db.models import CatalogSource, CatalogSourceStatus

    session = _session()
    try:
        source = session.get(CatalogSource, source_id)
        if source is None:
            raise RegistryError("Không tìm thấy bản danh mục.", 404)
        if source.status == CatalogSourceStatus.APPROVED.value:
            raise RegistryError("Không xoá được bản đang dùng; hãy nạp và duyệt bản mới để thay.", 409)
        session.delete(source)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ── Xem ──────────────────────────────────────────────────────────────────────


def _source_dict(source) -> dict:
    from ingestion.registry_import import KIND_LABELS

    return {
        "id": source.id,
        "kind": source.kind,
        "kind_label": KIND_LABELS.get(source.kind, source.kind),
        "file_name": source.file_name,
        "title": source.title,
        "status": source.status,
        "row_count": source.row_count,
        "issues": list(source.issues or []),
        "revision": source.revision,
        "uploaded_at": source.uploaded_at.isoformat() if source.uploaded_at else None,
        "reviewed_at": source.reviewed_at.isoformat() if source.reviewed_at else None,
        "review_note": source.review_note,
    }


def list_sources() -> list[dict]:
    from db.models import CatalogSource

    session = _session()
    try:
        rows = (
            session.query(CatalogSource)
            .order_by(CatalogSource.uploaded_at.desc(), CatalogSource.id.desc())
            .all()
        )
        result = []
        for row in rows:
            item = _source_dict(row)
            # Số mục cần người duyệt xem: lỗi/cảnh báo trong file + đối chiếu chéo với danh mục quy trình.
            issues = item["issues"] + cross_issues(session, row)
            item["attention"] = sum(1 for issue in issues if issue.get("level") != "info")
            result.append(item)
        return result
    finally:
        session.close()


def _row_keys(session, source) -> dict[str, str]:
    """Khoá nghiệp vụ → nội dung nguyên văn của từng dòng, để so bản nháp với bản đang dùng."""
    if source.kind == "procedure":
        return {
            (e.code.key if e.code else e.code_raw): f"{e.code_raw} | {e.title} | {e.issuer} | {e.field}"
            for e in _procedures(session, source)
        }
    if source.kind == "standard":
        return {
            f"{e.model} số {e.serial}".strip(): f"{e.name} | {e.characteristics_raw} | {e.interval_raw}"
            for e in _standards(session, source)
        }
    return {e.name: f"{e.params_raw} | {e.procedures_raw} | {e.field}" for e in _capabilities(session, source)}


def _changes(session, source) -> dict:
    current = _approved_sources(session).get(source.kind)
    if current is None or current.id == source.id:
        return {"base_id": None, "added": [], "removed": [], "changed": []}
    new, old = _row_keys(session, source), _row_keys(session, current)
    return {
        "base_id": current.id,
        "added": sorted(set(new) - set(old)),
        "removed": sorted(set(old) - set(new)),
        "changed": sorted(k for k in set(new) & set(old) if new[k] != old[k]),
    }


def get_source(source_id: int) -> dict:
    """Một bản danh mục: báo cáo lỗi trong file, đối chiếu chéo và thay đổi so với bản đang dùng."""
    from db.models import CatalogSource

    session = _session()
    try:
        source = session.get(CatalogSource, source_id)
        if source is None:
            raise RegistryError("Không tìm thấy bản danh mục.", 404)
        result = _source_dict(source)
        result["cross_issues"] = cross_issues(session, source)
        result["changes"] = _changes(session, source)
        return result
    finally:
        session.close()


def _procedure_catalog(session, source) -> tuple[ProcedureEntry, ...]:
    """Danh mục quy trình để đối chiếu: bản đang xem nếu là danh mục quy trình, không thì bản đã duyệt."""
    if source.kind == "procedure":
        return _procedures(session, source)
    approved = _approved_sources(session).get("procedure")
    return _procedures(session, approved) if approved is not None else ()


def cross_issues(session, source) -> list[dict]:
    """Lỗi chỉ thấy khi đối chiếu file năng lực với danh mục quy trình (mục 10.2 tài liệu kiến trúc):
    mã không có trong danh mục, năm ban hành lệch giữa hai file."""
    if source.kind not in ("capability_kd", "capability_hc"):
        return []
    catalog = [e.code for e in _procedure_catalog(session, source) if e.code is not None]
    if not catalog:
        return [{"level": "warning", "row": None, "message": "Chưa có danh mục quy trình đã duyệt để đối chiếu mã."}]
    keys = {code.key for code in catalog}
    by_base: dict[str, list[CatalogCode]] = {}
    for code in catalog:
        by_base.setdefault(code.base, []).append(code)
    issues: list[dict] = []
    for capability in _capabilities(session, source):
        for code in capability.codes or tuple(parse_codes(capability.procedures_raw)):
            if code.key in keys:
                continue
            same_number = by_base.get(code.base, [])
            if same_number:
                listed = ", ".join(c.key for c in same_number)
                message = f"«{capability.name}»: ghi «{code.key}», danh mục quy trình ghi «{listed}» (lệch năm ban hành)"
            else:
                message = f"«{capability.name}»: mã «{code.key}» không có trong danh mục quy trình"
            issues.append({"level": "warning", "row": capability.row, "message": message})
    return issues
