"""Danh mục trường biên bản + nhận diện trường được hỏi trong câu hỏi (Pha R).

Câu hỏi "A0 của áp kế 1045 là bao nhiêu" cần biết "A0" là trường nào của biên
bản. Danh mục KHÔNG hardcode theo một mẫu biên bản: nó dựng từ dữ liệu đã duyệt

- nhãn các trường đầu mục có trong ``v_record_field`` (sinh từ Phụ lục A đã duyệt
  của từng QTKĐ, cộng dòng nhãn tự do như ``U(p)``);
- tiêu đề các bảng kết quả Phụ lục A đã duyệt (``Bảng A.2 - Thời gian quay tự do``)
  và tên cột RIÊNG của từng bảng trong ``v_measurement_detail.cells``;

rồi cộng một bảng bí danh nhỏ cho ký hiệu và cách nói thường gặp (``A0``,
``uCmax``, ``U(p)``, "hãng", "điều kiện môi trường"). Nhận diện là tất định: một
nhãn khớp khi mọi từ mang nghĩa của nó có trong câu hỏi. Từ tiếng Việt giữ dấu
để "độ" và "đo" không lẫn nhau. Chỉ đọc view đã duyệt (P3).
"""

from __future__ import annotations

import json
import logging
import re
import threading
import time
import unicodedata
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Từ không mang nghĩa phân biệt trong nhãn / tiêu đề bảng.
_STOPWORDS = frozenset(
    {"của", "và", "các", "là", "có", "được", "trong", "cho", "khi", "theo", "với", "tại", "bảng"}
)
# Các biến thể viết "píttông" gộp về một token.
_PISTON_FORMS = frozenset({"píttông", "pittông", "pitông", "pittong", "píttong", "piston"})
_WORD_RE = re.compile(r"\w+", re.UNICODE)
_TABLE_TITLE_RE = re.compile(
    r"^\s*Bảng\s+(?P<code>[A-Z]?\.?\d+(?:\.\d+)*)\s*[-–—:]\s*(?P<rest>.+)$",
    re.IGNORECASE | re.DOTALL,
)
_RESULT_PREFIX_RE = re.compile(r"^\s*kết\s+quả\s+", re.IGNORECASE)
_PARENS_RE = re.compile(r"\([^()]*\)")

# Trường định danh luôn hiện ở cột đầu bảng kết quả; không cần "được hỏi".
IDENTITY_KEYS = frozenset({"so", "so_hieu", "ky_hieu", "ten_trang_bi_dl_tn", "ngay_kiem_dinh"})
VERDICT_KEY = "ket_luan"

# Cách nói thường gặp → tiền tố khóa trường (khớp mọi khóa bắt đầu bằng tiền tố).
_PHRASE_ALIASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("dải đo", ("pham_vi_do",)),
    ("ccx", ("cap_chinh_xac",)),
    ("hãng", ("nuoc_hang_san_xuat", "hang_san_xuat", "nha_san_xuat", "noi_hang_san_xuat")),
    ("nước sản xuất", ("nuoc_hang_san_xuat", "nuoc_san_xuat")),
    ("đơn vị nào", ("don_vi_su_dung",)),
    ("cho đơn vị", ("don_vi_su_dung",)),
    ("đơn vị sử dụng", ("don_vi_su_dung",)),
    ("điều kiện môi trường", ("nhiet_do", "do_am")),
    ("điều kiện kiểm định", ("nhiet_do", "do_am")),
    ("kết luận", (VERDICT_KEY,)),
    ("không đạt", (VERDICT_KEY,)),
    ("có đạt", (VERDICT_KEY,)),
    ("đạt không", (VERDICT_KEY,)),
    ("đạt hay", (VERDICT_KEY,)),
    ("vì sao", (VERDICT_KEY,)),
    ("lý do", (VERDICT_KEY,)),
    ("chuẩn", ("phuong_tien_kiem_dinh",)),
    ("mở rộng", ("u_p",)),
)
# Ký hiệu → tiền tố khóa trường.
_SYMBOL_ALIASES: tuple[tuple[re.Pattern[str], tuple[str, ...]], ...] = (
    (re.compile(r"\ba\s*[0o]\b", re.IGNORECASE), ("dien_tich_hieu_dung",)),
    (re.compile(r"\bu\s*c\s*max\b|\bu\s*c\b", re.IGNORECASE), ("do_khong_dam_bao_do",)),
    (re.compile(r"\bu\s*\(\s*p\s*\)", re.IGNORECASE), ("u_p",)),
)
# Trường luôn đi cùng nhau trên biên bản: hỏi một thì trả cả nhóm (phương tiện kiểm
# định + phương pháp; uCmax + độ không đảm bảo đo mở rộng U(p)).
RELATED_PREFIXES: dict[str, tuple[str, ...]] = {
    "phuong_tien_kiem_dinh": ("phuong_phap_kiem_dinh",),
    "do_khong_dam_bao_do": ("u_p",),
}
_CATALOG_TTL_SECONDS = 30.0
# Tiêu đề bảng khớp khi câu hỏi chứa phần lớn từ của nó ("quay tự do" ↔ "Thời gian quay
# tự do"); nhãn trường vẫn phải khớp trọn vì nhãn ngắn và dễ trùng nhau.
_TITLE_MIN_WORDS = 3
_TITLE_MIN_SHARE = 0.6


def tokens(text_value: str | None) -> list[str]:
    """Từ viết thường GIỮ dấu; gộp "pít tông"/"píttông"/"pittông" thành ``pittong``."""
    words = _WORD_RE.findall(unicodedata.normalize("NFC", (text_value or "").casefold()))
    merged: list[str] = []
    index = 0
    while index < len(words):
        word = words[index]
        if (
            word in ("pít", "pit")
            and index + 1 < len(words)
            and words[index + 1] in ("tông", "tong")
        ):
            merged.append("pittong")
            index += 2
            continue
        merged.append("pittong" if word in _PISTON_FORMS else word)
        index += 1
    return merged


def content_tokens(text_value: str | None) -> frozenset[str]:
    return frozenset(token for token in tokens(text_value) if token not in _STOPWORDS)


def normalize_phrase(text_value: str | None) -> str:
    return " ".join(tokens(text_value))


@dataclass(frozen=True)
class FieldEntry:
    key: str
    label: str
    words: frozenset[str]


@dataclass(frozen=True)
class TableEntry:
    """Một bảng kết quả Phụ lục A của MỘT QTKĐ (mã bảng lặp lại giữa các QTKĐ)."""

    step_code: str
    title: str
    words: frozenset[str]
    # Tên cột RIÊNG của bảng (không bảng nào khác có), dạng tập từ.
    columns: tuple[frozenset[str], ...] = ()
    procedure_id: int | None = None


@dataclass(frozen=True)
class FieldCatalog:
    fields: tuple[FieldEntry, ...] = ()
    tables: tuple[TableEntry, ...] = ()

    def field_label(self, key: str) -> str:
        return next((entry.label for entry in self.fields if entry.key == key), key)

    def table_title(self, step_code: str, procedure_id: int | None = None) -> str:
        """Tiêu đề bảng của đúng QTKĐ khi biết; không thì tiêu đề đầu tiên có mã đó."""
        tables = [table for table in self.tables if table.step_code == step_code]
        own = [table for table in tables if table.procedure_id == procedure_id]
        return (own or tables)[0].title if (own or tables) else step_code

    def keys_with_prefix(self, prefix: str) -> list[str]:
        return [entry.key for entry in self.fields if entry.key.startswith(prefix)]

    def related(self, key: str) -> list[str]:
        """Trường đi kèm ``key`` có trong danh mục."""
        return [
            related
            for prefix in RELATED_PREFIXES.get(key, ())
            for related in self.keys_with_prefix(prefix)
        ]


@dataclass(frozen=True)
class Targets:
    """Trường đầu mục và bảng kết quả mà câu hỏi nhắc tới."""

    fields: tuple[str, ...] = ()
    steps: tuple[str, ...] = ()
    # QTKĐ sở hữu các bảng khớp: cực trị theo bảng chỉ so trong các QTKĐ này.
    procedures: tuple[int, ...] = ()

    @property
    def specific_fields(self) -> tuple[str, ...]:
        """Trường ngoài định danh và kết luận (thứ khiến câu hỏi là tra một biên bản)."""
        return tuple(key for key in self.fields if key not in IDENTITY_KEYS | {VERDICT_KEY})


_CATALOG_CACHE: dict[str, tuple[float, FieldCatalog]] = {}
_CATALOG_LOCK = threading.Lock()


def label_words(label: str) -> frozenset[str]:
    """Từ mang nghĩa của nhãn; bỏ phần đơn vị sau dấu phẩy và phần trong ngoặc."""
    head = _PARENS_RE.sub(" ", label.split(",")[0])
    return frozenset(token for token in content_tokens(head) if len(token) > 1)


def _title_words(title: str) -> frozenset[str]:
    match = _TABLE_TITLE_RE.match(title or "")
    rest = match.group("rest") if match else title
    rest = _RESULT_PREFIX_RE.sub("", _PARENS_RE.sub(" ", rest or ""))
    return frozenset(token for token in content_tokens(rest) if len(token) > 1)


def _step_code(title: str, fallback: str) -> str:
    match = _TABLE_TITLE_RE.match(title or "")
    return (match.group("code") if match else fallback)[:32]


def load_cells(value: Any) -> list[dict[str, str]]:
    """``cells`` từ view (JSON đã giải mã trên PostgreSQL, chuỗi trên SQLite)."""
    if value is None:
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return []
    return [cell for cell in value if isinstance(cell, dict)]


TableKey = tuple[Any, str]


def _distinctive_columns(session: Session) -> dict[TableKey, tuple[frozenset[str], ...]]:
    """Tên cột theo từng (QTKĐ, bảng); chỉ giữ cột chỉ một bảng có ("Áp suất khí quyển")."""
    by_step: dict[TableKey, set[frozenset[str]]] = {}
    rows = session.execute(
        text(
            # Không DISTINCT: kiểu ``json`` của PostgreSQL không so sánh bằng được.
            "SELECT procedure_id, step_code, cells FROM v_measurement_detail "
            "WHERE cells IS NOT NULL AND step_code IS NOT NULL"
        )
    ).all()
    for procedure_id, step_code, cells in rows:
        for cell in load_cells(cells):
            words = label_words(str(cell.get("column") or ""))
            if len(words) >= 3:
                by_step.setdefault((procedure_id, step_code), set()).add(words)
    counts: dict[frozenset[str], int] = {}
    for columns in by_step.values():
        for words in columns:
            counts[words] = counts.get(words, 0) + 1
    return {
        step: tuple(words for words in columns if counts[words] == 1)
        for step, columns in by_step.items()
    }


def build_catalog(session: Session) -> FieldCatalog:
    """Dựng danh mục từ view đã duyệt; thất bại DB → danh mục rỗng."""
    try:
        field_rows = session.execute(
            text("SELECT field_key, MIN(label) FROM v_record_field GROUP BY field_key")
        ).all()
        # Mã bảng (A.1, A.2...) lặp lại giữa các QTKĐ: tiêu đề phải khóa theo QTKĐ và
        # chỉ lấy QTKĐ có số liệu đo đã duyệt ở bảng đó.
        title_rows = session.execute(
            text(
                "SELECT DISTINCT f.procedure_id, f.label FROM v_procedure_fact f "
                "WHERE f.fact_kind = 'appendix_field' AND f.condition_text = 'table'"
            )
        ).all()
        used = {
            (row[0], row[1])
            for row in session.execute(
                text("SELECT DISTINCT procedure_id, step_code FROM v_measurement_detail")
            ).all()
        }
        columns = _distinctive_columns(session)
    except SQLAlchemyError as exc:
        # DB chưa lên migration 012 (thiếu view) thì không có danh mục; lỗi khác vẫn ghi log
        # vì danh mục rỗng làm tắt lớp định tuyến tất định.
        logger.warning("Không dựng được danh mục trường biên bản: %s", exc)
        return FieldCatalog()
    fields = tuple(
        FieldEntry(key=str(key), label=str(label), words=label_words(str(label)))
        for key, label in field_rows
        if key
    )
    tables: list[TableEntry] = []
    for procedure_id, title in title_rows:
        code = _step_code(str(title), str(title))
        if (procedure_id, code) in used:
            tables.append(
                TableEntry(
                    code,
                    str(title),
                    _title_words(str(title)),
                    columns.get((procedure_id, code), ()),
                    procedure_id,
                )
            )
    return FieldCatalog(fields=fields, tables=tuple(tables))


def _cache_key(session: Session) -> str | None:
    try:
        engine = session.get_bind()
        return f"{engine.url}#{id(engine)}"
    except Exception:  # noqa: BLE001 - cache chỉ là tối ưu
        return None


def field_catalog(session: Session) -> FieldCatalog:
    """Danh mục có cache ngắn hạn (dữ liệu đã duyệt đổi chậm)."""
    key = _cache_key(session)
    if key is None:
        return build_catalog(session)
    with _CATALOG_LOCK:
        cached = _CATALOG_CACHE.get(key)
        if cached is not None and time.monotonic() - cached[0] < _CATALOG_TTL_SECONDS:
            return cached[1]
        catalog = build_catalog(session)
        _CATALOG_CACHE[key] = (time.monotonic(), catalog)
        return catalog


def _title_matches(title: frozenset[str], words: frozenset[str]) -> bool:
    if not title:
        return False
    shared = len(title & words)
    needed = max(min(_TITLE_MIN_WORDS, len(title)), _TITLE_MIN_SHARE * len(title))
    return shared >= needed


def _negated_alias(alias: str, phrase: str) -> bool:
    """ "chuẩn" trong "tiêu chuẩn"/"chuẩn mẫu của phòng" không phải phương tiện của biên bản."""
    return alias == "chuẩn" and (" tiêu chuẩn " in phrase or " chuẩn mẫu " in phrase)


def _ordered(keys: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(keys))


def detect_targets(question: str, catalog: FieldCatalog) -> Targets:
    """Trường + bảng mà câu hỏi nhắc tới (tất định, không gọi LLM)."""
    words = frozenset(tokens(question))
    # Đệm khoảng trắng để bí danh chỉ khớp trọn từ ("chuẩn" không khớp "tiêu chuẩn").
    phrase = f" {normalize_phrase(question)} "
    keys: list[str] = []
    for entry in catalog.fields:
        # Nhãn một từ ("Số") quá chung để tự khớp; ký hiệu đi qua bảng bí danh.
        if len(entry.words) >= 2 and entry.words <= words:
            keys.append(entry.key)
    for alias, prefixes in _PHRASE_ALIASES:
        if f" {normalize_phrase(alias)} " in phrase and not _negated_alias(alias, phrase):
            keys.extend(key for prefix in prefixes for key in catalog.keys_with_prefix(prefix))
    for pattern, prefixes in _SYMBOL_ALIASES:
        if pattern.search(question or ""):
            keys.extend(key for prefix in prefixes for key in catalog.keys_with_prefix(prefix))
    keys.extend(related for key in list(keys) for related in catalog.related(key))
    matched = [
        table
        for table in catalog.tables
        if _title_matches(table.words, words) or any(column <= words for column in table.columns)
    ]
    return Targets(
        fields=_ordered(keys),
        steps=_ordered([table.step_code for table in matched]),
        procedures=_ordered([t.procedure_id for t in matched if t.procedure_id is not None]),
    )
