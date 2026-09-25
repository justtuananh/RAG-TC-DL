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

from knowledge.record_labels import all_labels
from knowledge.rules.markdown_tables import parse_tables
from knowledge.rules.sections import find_appendix_section
from knowledge.rules.types import RuleHit

EXTRACTOR = "rule:phuluc_a.v1"
FACT_KIND = "appendix_field"
ROLE_HEADER = "header"
ROLE_TABLE = "table"

# Nhãn trường: không chứa chữ số (loại "QTKĐ 1.061"), không quá dài.
_LABEL_RE = re.compile(r"([^\s:|][^:|]{0,58}?)\s*:")
# K06: dòng bắt đầu bằng một nhãn hồ sơ đã biết mà không có ':' vẫn là trường
# đầu mục (mẫu "Ngày kiểm định tháng năm 2026").
_KNOWN_LABEL_RE = re.compile(
    "|".join(re.escape(label) for label in all_labels()), re.IGNORECASE
)
# Chữ mẫu còn lại trong dòng nhãn trống: "tháng", "năm", "ngày", dấu chấm/dấu
# chấm lửng, và mẩu số DÍNH LIỀN dấu chấm lửng ("202…", "20..") của năm mẫu.
# Số đứng riêng không có dấu chấm lửng (ví dụ "2026") vẫn là giá trị thật.
_TEMPLATE_WORDS_RE = re.compile(
    r"\b(?:tháng|năm|ngày)\b|\d+(?:…|\.{2,})|[.…]+", re.IGNORECASE
)
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


def _known_label_hit(stripped: str, offset: int, leading: int, section) -> RuleHit | None:
    """Trường header từ dòng mở đầu bằng nhãn đã biết nhưng KHÔNG có dấu ':'.

    Giá trị là phần còn lại sau khi bỏ chữ mẫu ("tháng", "năm", dấu chấm lửng);
    dòng chỉ có nhãn (hoặc chỉ còn chữ mẫu) cho ``value_text`` rỗng.
    """
    match = _KNOWN_LABEL_RE.match(stripped)
    if match is None:
        return None
    rest = stripped[match.end() :]
    if rest and (rest[0].isalnum() or rest[0] == "_"):
        return None  # dính chữ liền sau: không phải nhãn trọn vẹn
    label = match.group(0).strip()
    cleaned = _clean_label(label)
    if cleaned is None:
        return None
    value = " ".join(_TEMPLATE_WORDS_RE.sub(" ", rest).split())
    return RuleHit(
        kind="fact",
        extractor=EXTRACTOR,
        section_path=section.path,
        quote=stripped,
        char_start=offset + leading,
        char_end=offset + leading + len(stripped),
        confidence=0.9,
        fact_kind=FACT_KIND,
        label=cleaned,
        value_text=value or None,
        condition_text=ROLE_HEADER,
    )


def _header_fields(section, text: str) -> list[RuleHit]:
    hits: list[RuleHit] = []
    offset = section.body_start
    for line in section.body.split("\n"):
        stripped = line.strip()
        if not stripped or "|" in stripped:
            offset += len(line) + 1
            continue
        leading = len(line) - len(line.lstrip())
        matches = list(_LABEL_RE.finditer(stripped))
        if not matches:
            # K06: không có dấu ':' nhưng mở đầu bằng nhãn hồ sơ đã biết.
            known = _known_label_hit(stripped, offset, leading, section)
            if known is not None:
                hits.append(known)
            offset += len(line) + 1
            continue
        for index, match in enumerate(matches):
            label = _clean_label(match.group(1))
            if label is None:
                continue
            start = match.end()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(stripped)
            value = stripped[start:end].lstrip(" :").strip()
            if index + 1 < len(matches):
                value = value.rstrip(" :").strip()
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
    section = find_appendix_section(text)
    if section is None:
        return []
    return _header_fields(section, text) + _table_fields(section, text)
