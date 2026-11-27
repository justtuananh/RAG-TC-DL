"""Khớp câu hỏi với sổ đăng ký danh mục 877 và nối danh mục với tài liệu trong kho.

Tầng 1 của kiến trúc "tra mục lục trước, đọc sách sau" (docs/KIEN_TRUC_DANH_MUC_877.md mục 5.4, 6):

- Chỉ mục tên trong bộ nhớ, dựng từ bản danh mục ĐÃ DUYỆT: tên phương tiện, tên quy trình, tên chuẩn
  mẫu kèm alias (``registry.aliases``), model và số hiệu chuẩn.
- Khớp theo thứ tự: mã tường minh (QTKĐ/ĐLVN/QTHC...), model + số hiệu chuẩn, tên bỏ dấu và bỏ khoảng
  trắng ("ta khô met" = "takhomet"), rồi gần đúng khi gõ sai chính tả.
- Liên kết danh mục → tài liệu trong kho KHÔNG lưu cứng: tính theo mã (tiền tố + số + năm) và tên từ hồ
  sơ tài liệu mỗi khi kho đổi (``router.invalidate``), nên tải lên / thay / xoá tài liệu tự cập nhật.

Không đọc được Postgres hoặc chưa duyệt bản danh mục nào thì mọi hàm trả kết quả rỗng: chat chạy như cũ.
"""

from __future__ import annotations

import difflib
import logging
import re
import threading
import time
from dataclasses import dataclass, field

from core.settings_loader import get_settings
from knowledge import registry
from knowledge.catalog_codes import CatalogCode, parse_codes, stem_codes
from knowledge.catalog_units import QUANTITY_LABELS, CatalogRange, Quantity
from knowledge.procedure import same_subject
from knowledge.registry import CapabilityEntry, ProcedureEntry, RegistryData, StandardEntry
from retrieval import doc_profile
from retrieval.normalize import fold

logger = logging.getLogger(__name__)

# Chữ Hy Lạp / Kirin trông như chữ Latinh trong model chuẩn (MΠ-600, ΠКУ-M, ИВД): người dùng gõ Latinh.
_HOMOGLYPHS = str.maketrans("πβμтнаеоросхкмвиіпудг", "pbuthaeopocxkmbiipudg")
_SUBJECT_SPLIT_RE = re.compile(r"\s+-\s+|,|\s+có phạm vi|\s+cấp chính xác|\s+có dải", re.IGNORECASE)
_FUZZY_MIN_CHARS = 8
_SHADOW_MARGIN = 0.15

Entry = ProcedureEntry | CapabilityEntry | StandardEntry


def words(text: str | None) -> list[str]:
    """Từ đã bỏ dấu, chữ thường, đổi chữ Hy Lạp/Kirin giống Latinh; bỏ dấu câu."""
    return re.findall(r"[a-z0-9]+", fold(text or "").translate(_HOMOGLYPHS))


def compact(text: str | None) -> str:
    return "".join(words(text))


# ── Ảnh chụp danh mục + chỉ mục tên ──────────────────────────────────────────


@dataclass(frozen=True)
class _Alt:
    """Một cách gọi của một dòng danh mục: các từ, chuỗi liền (bỏ khoảng trắng) và vị trí cuối từng từ."""

    entry: Entry
    words: tuple[str, ...]
    squashed: str
    ends: tuple[int, ...]


@dataclass(frozen=True)
class _CorpusDoc:
    stem: str
    codes: tuple[CatalogCode, ...]
    title: str
    squashed: str
    tokens: frozenset[str]


@dataclass
class _Snapshot:
    data: RegistryData
    alts: tuple[_Alt, ...]
    corpus: tuple[_CorpusDoc, ...] | None = None
    links: dict = field(default_factory=dict)


_lock = threading.Lock()
_snapshot: _Snapshot | None = None
_loaded_generation = -1
_loaded_at = 0.0


def _alt(entry: Entry, text: str) -> _Alt | None:
    tokens = tuple(words(text))
    if not tokens:
        return None
    ends: list[int] = []
    total = 0
    for token in tokens:
        total += len(token)
        ends.append(total)
    return _Alt(entry=entry, words=tokens, squashed="".join(tokens), ends=tuple(ends))


def _names(entry: Entry) -> list[str]:
    if isinstance(entry, CapabilityEntry):
        return [entry.name, re.sub(r"\(.*?\)", " ", entry.name), *entry.name.split(",")]
    if isinstance(entry, ProcedureEntry):
        subject = re.split(r"\s+-\s+", entry.title)[0]
        return [entry.title, subject, _SUBJECT_SPLIT_RE.split(subject)[0]]
    return [entry.name, re.sub(r"\(.*?\)", " ", entry.name)]


def _aliases(entry: Entry) -> list[str]:
    name = fold(entry.title if isinstance(entry, ProcedureEntry) else entry.name)
    result: list[str] = []
    for item in get_settings().registry.aliases:
        if fold(item.name) in name:
            result.extend(item.aliases)
    return result


def _build_alts(data_: RegistryData) -> tuple[_Alt, ...]:
    result: list[_Alt] = []
    for entry in (*data_.capabilities, *data_.procedures, *data_.standards):
        seen: set[str] = set()
        for text in (*_names(entry), *_aliases(entry)):
            alt = _alt(entry, text)
            if alt is not None and alt.squashed not in seen:
                seen.add(alt.squashed)
                result.append(alt)
    return tuple(result)


def invalidate() -> None:
    """Kho tài liệu đổi (nạp / xoá): bỏ liên kết danh mục → tài liệu; lần gọi sau tính lại."""
    with _lock:
        if _snapshot is not None:
            _snapshot.corpus = None
            _snapshot.links = {}


def reload() -> None:
    """Bản danh mục đã duyệt đổi: đọc lại ở lần gọi sau."""
    global _loaded_generation
    with _lock:
        _loaded_generation = -1


def _current() -> _Snapshot | None:
    global _snapshot, _loaded_generation, _loaded_at
    cfg = get_settings().registry
    if not cfg.enabled:
        return None
    with _lock:
        generation = registry.generation()
        fresh = _loaded_generation == generation and time.monotonic() - _loaded_at < cfg.cache_ttl_s
        if _snapshot is not None and fresh:
            return _snapshot
        try:
            loaded = registry.load_approved()
        except Exception as e:  # noqa: BLE001 - không có Postgres / chưa migrate: chat chạy như cũ
            logger.warning("Không đọc được sổ đăng ký danh mục: %s", e)
            loaded = _snapshot.data if _snapshot is not None else RegistryData()
        _snapshot = _Snapshot(data=loaded, alts=_build_alts(loaded))
        _loaded_generation = generation
        _loaded_at = time.monotonic()
        return _snapshot


def data() -> RegistryData:
    snapshot = _current()
    return snapshot.data if snapshot is not None else RegistryData()


# ── Khớp câu hỏi ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class NameHit:
    entry: Entry
    start: int
    end: int
    coverage: float
    full: bool


@dataclass(frozen=True)
class RegistryMatch:
    """Các dòng danh mục câu hỏi nói tới, theo thứ tự trong file danh mục."""

    capabilities: tuple[CapabilityEntry, ...] = ()
    procedures: tuple[ProcedureEntry, ...] = ()
    standards: tuple[StandardEntry, ...] = ()
    codes: tuple[CatalogCode, ...] = ()  # mã nêu tường minh trong câu hỏi
    coverage: float = 0.0  # độ khớp tên tốt nhất (1.0 khi khớp mã, model, số hiệu hay trọn tên)
    explicit: bool = False  # khớp bằng mã / model / số hiệu, không phải đoán theo tên

    @property
    def empty(self) -> bool:
        return not (self.capabilities or self.procedures or self.standards)

    @property
    def entries(self) -> tuple[Entry, ...]:
        return (*self.capabilities, *self.procedures, *self.standards)


def _prefix_match(qwords: list[str], start: int, alt: _Alt) -> tuple[int, int]:
    """Số ký tự đầu tên khớp liên tiếp từ từ ``start`` của câu hỏi, dừng đúng ranh giới từ hai bên."""
    position = 0
    best = (0, start)
    index = start
    while index < len(qwords) and position < len(alt.squashed):
        token = qwords[index]
        if not alt.squashed.startswith(token, position):
            break
        position += len(token)
        index += 1
        if position in alt.ends:
            best = (position, index)
    return best


def _accept(alt: _Alt, chars: int) -> tuple[float, bool] | None:
    cfg = get_settings().registry
    if chars < cfg.min_match_chars:
        return None
    matched = alt.words[: sum(1 for end in alt.ends if end <= chars)]
    if all(word in cfg.generic_words for word in matched):
        return None
    full = chars == len(alt.squashed)
    if not full and len(matched) < 2:
        return None
    return chars / len(alt.squashed), full


def _name_hits(qwords: list[str], alts: tuple[_Alt, ...]) -> list[NameHit]:
    hits: dict[int, NameHit] = {}
    for alt in alts:
        for start in range(len(qwords)):
            if not alt.squashed.startswith(qwords[start][:1]):
                continue
            chars, end = _prefix_match(qwords, start, alt)
            accepted = _accept(alt, chars) if chars else None
            if accepted is None:
                continue
            coverage, full = accepted
            key = id(alt.entry)
            if key not in hits or coverage > hits[key].coverage:
                hits[key] = NameHit(alt.entry, start, end, coverage, full)
    return list(hits.values())


def _fuzzy_hits(qwords: list[str], alts: tuple[_Alt, ...]) -> list[NameHit]:
    """Gõ sai chính tả ("nhiet ke thuy tin"): so cửa sổ cùng số từ với tên, tỉ lệ giống ≥ ngưỡng."""
    threshold = get_settings().registry.fuzzy_min_ratio
    hits: dict[int, NameHit] = {}
    for alt in alts:
        if len(alt.words) < 2 or len(alt.squashed) < _FUZZY_MIN_CHARS:
            continue
        size = len(alt.words)
        for start in range(max(len(qwords) - size + 1, 0)):
            window = "".join(qwords[start : start + size])
            if abs(len(window) - len(alt.squashed)) > 3 or window[:1] != alt.squashed[:1]:
                continue
            ratio = difflib.SequenceMatcher(None, window, alt.squashed).ratio()
            key = id(alt.entry)
            if ratio >= threshold and (key not in hits or ratio > hits[key].coverage):
                hits[key] = NameHit(alt.entry, start, start + size, ratio, True)
    return list(hits.values())


def _drop_shadowed(hits: list[NameHit]) -> list[NameHit]:
    """Bỏ khớp nằm gọn trong một khớp dài hơn, và khớp kém hẳn khớp tốt nhất cùng chỗ trong câu."""
    kept: list[NameHit] = []
    for hit in hits:
        shadowed = any(
            other is not hit
            and other.start <= hit.start
            and hit.end <= other.end
            and (other.end - other.start) > (hit.end - hit.start)
            for other in hits
        )
        if shadowed:
            continue
        best = max(o.coverage for o in hits if o.start < hit.end and hit.start < o.end)
        if hit.coverage >= best - _SHADOW_MARGIN:
            kept.append(hit)
    return kept


def _standard_hits(question: str, standards: tuple[StandardEntry, ...]) -> list[StandardEntry]:
    """Chuẩn nêu bằng model và/hoặc số hiệu ("MΠ-600 số 994", "Fluke 7302"). Model chỉ toàn chữ số
    ("681") quá chung nên phải đi kèm số hiệu."""
    q_compact = compact(question)
    q_tokens = set(words(question))
    by_serial = [
        s for s in standards if s.serial and len(compact(s.serial)) >= 3 and compact(s.serial) in q_tokens
    ]
    by_model = [
        s
        for s in standards
        if (model := compact(s.model))
        and len(model) >= 4
        and re.search(r"[a-z]", model)
        and re.search(r"\d", model)
        and model in q_compact
    ]
    if by_serial and by_model:
        both = [s for s in by_serial if s in by_model]
        return both or by_serial
    return by_serial or by_model


def _code_hits(codes: list[CatalogCode], data_: RegistryData) -> list[ProcedureEntry]:
    result: list[ProcedureEntry] = []
    for code in codes:
        for entry in data_.procedures:
            if entry.code is None or entry.code.base != code.base:
                continue
            if code.year is None or entry.code.year is None or entry.code.year == code.year:
                result.append(entry)
    return result


def _shares_code(capability: CapabilityEntry, code: CatalogCode) -> bool:
    return any(
        c.base == code.base and (code.year is None or c.year in (None, code.year)) for c in capability.codes
    )


def _ordered(entries, kind) -> tuple:
    unique = {id(e): e for e in entries if isinstance(e, kind)}
    return tuple(sorted(unique.values(), key=lambda e: (e.source_file, e.row)))


def match(question: str) -> RegistryMatch:
    """Các dòng danh mục mà câu hỏi nói tới; rỗng khi không khớp gì hoặc chưa có danh mục đã duyệt."""
    snapshot = _current()
    if snapshot is None or snapshot.data.empty:
        return RegistryMatch()
    data_ = snapshot.data
    codes = [c for c in parse_codes(question) if c.prefix]
    by_code = _code_hits(codes, data_)
    by_standard = _standard_hits(question, data_.standards)
    if by_code or by_standard:
        capabilities = [c for c in data_.capabilities if any(_shares_code(c, code) for code in codes)]
        return RegistryMatch(
            capabilities=_ordered(capabilities, CapabilityEntry),
            procedures=_ordered(by_code, ProcedureEntry),
            standards=_ordered(by_standard, StandardEntry),
            codes=tuple(codes),
            coverage=1.0,
            explicit=True,
        )
    qwords = words(question)
    hits = _name_hits(qwords, snapshot.alts) or _fuzzy_hits(qwords, snapshot.alts)
    if not hits:
        return RegistryMatch(codes=tuple(codes))
    # Câu nói về chuẩn mẫu chỉ giữ chuẩn; câu khác chỉ giữ chuẩn khi không khớp gì khác ("tủ vi khí hậu" là
    # quy trình hiệu chuẩn QTHC 1.024, không phải chuẩn "Tủ vi khí hậu (Italia)" của phòng).
    standards = [h for h in hits if isinstance(h.entry, StandardEntry)]
    others = [h for h in hits if not isinstance(h.entry, StandardEntry)]
    if re.search(get_settings().registry.standard_pattern, fold(question)):
        hits = standards or hits
    else:
        hits = others or hits
    hits = _drop_shadowed(hits)
    entries = [h.entry for h in hits]
    return RegistryMatch(
        capabilities=_ordered(entries, CapabilityEntry),
        procedures=_ordered(entries, ProcedureEntry),
        standards=_ordered(entries, StandardEntry),
        codes=tuple(codes),
        coverage=max(h.coverage for h in hits),
    )


# ── Lọc theo lĩnh vực và dải đo ──────────────────────────────────────────────


def _field_values(entry: Entry) -> list[str]:
    """Lĩnh vực của một dòng. Năng lực và quy trình dùng đúng cột lĩnh vực ("Sten kiểm tra đồng hồ xe tăng"
    có dải áp suất nhưng thuộc lĩnh vực tốc độ vòng quay); chuẩn mẫu không có cột này nên suy từ dải đo."""
    if isinstance(entry, StandardEntry):
        return [entry.field, *(QUANTITY_LABELS.get(r.quantity, "") for r in entry.ranges)]
    return [entry.field]


def field_terms(question: str) -> set[str]:
    """Lĩnh vực nêu trong câu hỏi ("áp suất", "nhiệt độ"), lấy từ chính cột lĩnh vực của danh mục."""
    snapshot = _current()
    if snapshot is None:
        return set()
    values = [v for e in (*snapshot.data.capabilities, *snapshot.data.procedures) for v in _field_values(e)]
    values += list(QUANTITY_LABELS.values())
    q = " ".join(words(question))
    terms: set[str] = set()
    for value in values:
        for part in re.split(r",|\bva\b", " ".join(words(value))):
            term = re.sub(r"^(?:phuong tien do|phuong tien|linh vuc)\s+", "", part.strip())
            if len(term) >= 4 and not term.isdigit() and re.search(rf"(?<!\w){re.escape(term)}(?!\w)", q):
                terms.add(term)
    return terms


def in_field(entry: Entry, terms: set[str]) -> bool:
    if not terms:
        return True
    haystack = " | ".join(" ".join(words(v)) for v in _field_values(entry))
    return any(re.search(rf"(?<!\w){re.escape(t)}(?!\w)", haystack) for t in terms)


def covering_ranges(ranges: tuple[CatalogRange, ...], quantities: list[Quantity]) -> list[CatalogRange] | None:
    """Dải chứa đại lượng cùng loại trong câu hỏi; ``None`` khi câu hỏi không nêu đại lượng loại này."""
    relevant = [q for q in quantities if any(r.quantity == q.quantity for r in ranges)]
    if not relevant:
        return None
    # Chỉ xét dải cùng đại lượng: dải lưu lượng không "chứa" 600 bar (all() trên tập rỗng luôn đúng).
    return [
        r
        for r in ranges
        if any(q.quantity == r.quantity for q in relevant)
        and all(r.contains(q.value_si) for q in relevant if q.quantity == r.quantity)
    ]


# ── Liên kết danh mục → tài liệu trong kho ───────────────────────────────────


@dataclass(frozen=True)
class DocLink:
    stem: str
    label: str
    note: str | None = None  # khác năm ban hành giữa danh mục và kho


def _corpus() -> tuple[_CorpusDoc, ...]:
    from retrieval import router

    docs: list[_CorpusDoc] = []
    for stem in sorted(router.known_files()):
        profile = doc_profile.profile_for(stem)
        codes = list(stem_codes(stem))
        title = ""
        if profile is not None:
            title = profile.title
            if profile.code is not None:
                code = profile.code
                codes.insert(0, CatalogCode(code.label, code.kind, code.number, code.year))
        docs.append(
            _CorpusDoc(
                stem=stem,
                codes=tuple(codes),
                title=title,
                squashed=compact(stem),
                tokens=frozenset(words(stem)),
            )
        )
    return tuple(docs)


def _snapshot_corpus(snapshot: _Snapshot) -> tuple[_CorpusDoc, ...]:
    if snapshot.corpus is None:
        try:
            snapshot.corpus = _corpus()
        except Exception as e:  # noqa: BLE001 - không liệt kê được kho: coi như chưa có văn bản
            logger.warning("Không dựng được danh sách tài liệu để liên kết danh mục: %s", e)
            return ()
    return snapshot.corpus


def _unique_links(links):
    seen: set[str] = set()
    result: list[DocLink] = []
    for link in links:
        if link.stem not in seen:
            seen.add(link.stem)
            result.append(link)
    return tuple(result)


def docs_for_code(code: CatalogCode, title: str | None = None) -> tuple[DocLink, ...]:
    """Tài liệu trong kho của một mã. Cùng năm thì chắc chắn; khác năm chỉ nhận khi cùng đối tượng
    (QTKĐ 1.017:2008 tủ sấy không được nối với QTKĐ 1.017:2014 chỉ thị nhiệt độ)."""
    snapshot = _current()
    if snapshot is None or not code.prefix:
        return ()
    key = (code.key, title)
    if key in snapshot.links:
        return snapshot.links[key]
    same_number = [(doc, c) for doc in _snapshot_corpus(snapshot) for c in doc.codes if c.base == code.base]
    links = [
        DocLink(doc.stem, code.key) for doc, c in same_number if code.year is not None and c.year == code.year
    ]
    if not links:
        for doc, c in same_number:
            if title and doc.title and not same_subject(title, doc.title):
                continue
            note = None
            if code.year and c.year and c.year != code.year:
                note = f"danh mục ghi {code.key}, kho có bản {c.key}"
            links.append(DocLink(doc.stem, c.key, note))
    result = _unique_links(links)
    snapshot.links[key] = result
    return result


def docs_for_standard(entry: StandardEntry) -> tuple[DocLink, ...]:
    """File hướng dẫn chuẩn (A_06_Ap_ke_pittong_MP_600_994) theo số hiệu và model trong tên tệp."""
    snapshot = _current()
    if snapshot is None:
        return ()
    serial = compact(entry.serial)
    model = compact(entry.model)
    if len(serial) < 3:
        return ()
    label = f"{entry.model} số {entry.serial}".strip()
    return _unique_links(
        DocLink(doc.stem, label)
        for doc in _snapshot_corpus(snapshot)
        if serial in doc.tokens and (not model or model in doc.squashed)
    )


def procedure_for(code: CatalogCode) -> ProcedureEntry | None:
    """Dòng danh mục quy trình của một mã (cùng năm; mã không ghi năm thì chỉ khi số đó là duy nhất)."""
    candidates = [e for e in data().procedures if e.code is not None and e.code.base == code.base]
    exact = [e for e in candidates if code.year is not None and e.code.year == code.year]
    if exact:
        return exact[0]
    return candidates[0] if len(candidates) == 1 and code.year is None else None


def docs_for(entry: Entry) -> tuple[DocLink, ...]:
    """Tài liệu trong kho để tìm sâu cho một dòng danh mục."""
    if isinstance(entry, StandardEntry):
        return docs_for_standard(entry)
    if isinstance(entry, ProcedureEntry):
        return docs_for_code(entry.code, entry.title) if entry.code else ()
    links: list[DocLink] = []
    for code in entry.codes:
        catalog = procedure_for(code)
        links.extend(docs_for_code(code, catalog.title if catalog else entry.name))
    return _unique_links(links)


def codes_of(entry: Entry) -> tuple[CatalogCode, ...]:
    if isinstance(entry, CapabilityEntry):
        return entry.codes
    if isinstance(entry, ProcedureEntry):
        return (entry.code,) if entry.code else ()
    return ()
