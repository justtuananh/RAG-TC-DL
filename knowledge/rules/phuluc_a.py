"""Phụ lục A → ``appendix_field`` — sơ đồ trường của biên bản (spec §7).

Phụ lục A của mỗi QTKĐ là mẫu biên bản kiểm định. Luật này rút ra:

- các trường đầu mục dạng ``Nhãn: giá trị`` (Số hiệu, Ngày kiểm định…);
- mỗi bảng kết quả kèm tiêu đề và danh sách cột đã gộp từ header nhiều tầng.

Đầu ra là dữ kiện ``appendix_field`` ở trạng thái ``pending``; người duyệt xác
nhận (và sửa nếu cần) một lần cho mỗi QTKĐ. ``records.template`` chỉ đọc bản ĐÃ
DUYỆT để dựng cấu hình đọc hồ sơ — không bao giờ dựng từ bản ``pending``.

Luật này KHÔNG nằm trong ``extract_all`` mặc định: nó là bước riêng giống trích
xuất §6, để không làm thay đổi số dòng dữ kiện của luật lõi. Không khớp mẫu →
rỗng, không đoán.
"""

from __future__ import annotations

import json
import re

from knowledge.rules.markdown_tables import parse_tables
from knowledge.rules.sections import find_section, split_sections
from knowledge.rules.types import RuleHit

EXTRACTOR = "rule:phuluc_a.v1"
FACT_KIND = "appendix_field"
ROLE_HEADER = "header"
ROLE_TABLE = "table"

# Nhãn trường: không chứa chữ số (loại "QTKĐ 1.061"), không quá dài.
_LABEL_RE = re.compile(r"([^\s:|][^:|]{0,58}?)\s*:")
_TITLE_RE = re.compile(r"^(?:Bảng\s+[A-Z]?\.?\d|KẾT QUẢ)", re.IGNORECASE)
# Bảng chỉ được coi là bảng kết quả đo nếu tiêu đề/cột có tín hiệu đo lường —
# loại bỏ bảng tiêu đề cơ quan và bảng chữ ký ở mẫu biên bản.
_MEASUREMENT_HINTS = (
    "sai số",
    "độ chênh",
    "giá trị",
    "lần kiểm tra",
    "mở",
    "đóng",
)


def _clean_label(label: str) -> str | None:
    text = label.strip()
    if not text or any(char.isdigit() for char in text):
        return None
    return text


def _header_fields(section, text: str) -> list[RuleHit]:
    hits: list[RuleHit] = []
    offset = section.body_start
    for line in section.body.split("\n"):
        stripped = line.strip()
        if not stripped or "|" in stripped:
            offset += len(line) + 1
            continue
        matches = list(_LABEL_RE.finditer(stripped))
        for index, match in enumerate(matches):
            label = _clean_label(match.group(1))
            if label is None:
                continue
            start = match.end()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(stripped)
            value = stripped[start:end].lstrip(" :").strip()
            if index + 1 < len(matches):
                value = value.rstrip(" :").strip()
            leading = len(line) - len(line.lstrip())
            hits.append(
                RuleHit(
                    kind="fact",
                    extractor=EXTRACTOR,
                    section_path=section.path,
                    quote=stripped,
                    char_start=offset + leading,
                    char_end=offset + leading + len(stripped),
                    confidence=0.9,
                    fact_kind=FACT_KIND,
                    label=label,
                    value_text=value or None,
                    condition_text=ROLE_HEADER,
                )
            )
        offset += len(line) + 1
    return hits


def _table_title(text: str, start: int) -> str:
    """Tiêu đề bảng: dòng ngay trên dòng header, nếu giống caption."""
    prefix = text[:start].rstrip("\n")
    if not prefix:
        return "Bảng kết quả"
    last_line = prefix.split("\n")[-1].strip()
    if _TITLE_RE.match(last_line):
        return last_line
    return "Bảng kết quả"


def _table_fields(section, text: str) -> list[RuleHit]:
    hits: list[RuleHit] = []
    for table in parse_tables(section.body, base_offset=section.body_start):
        columns = [header for header in table.headers if header.strip()]
        if not columns:
            continue
        line_end = text.find("\n", table.start)
        header_line = text[table.start : line_end if line_end != -1 else len(text)]
        title = _table_title(text, table.start)
        joined = " ".join(columns).casefold()
        if not _TITLE_RE.match(title) and not any(
            hint in joined for hint in _MEASUREMENT_HINTS
        ):
            continue
        hits.append(
            RuleHit(
                kind="fact",
                extractor=EXTRACTOR,
                section_path=section.path,
                quote=header_line.strip(),
                char_start=table.start,
                char_end=table.start + len(header_line),
                confidence=0.85,
                fact_kind=FACT_KIND,
                label=title,
                value_text=json.dumps(
                    {"title": title, "columns": columns, "header_rows": []},
                    ensure_ascii=False,
                ),
                condition_text=ROLE_TABLE,
            )
        )
    return hits


def extract(text: str) -> list[RuleHit]:
    """Rút trường đầu mục + bảng kết quả từ Phụ lục A; rỗng nếu không có."""
    sections = split_sections(text)
    section = find_section(sections, "phụ lục a")
    if section is None:
        return []
    return _header_fields(section, text) + _table_fields(section, text)
