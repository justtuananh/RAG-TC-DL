"""Dựng đoạn nguyên văn an toàn để tô sáng xuất xứ (P1, spec §5.7).

Hàm thuần giá trị: nhận các trường đã lưu của một extraction (mục, trích dẫn, vị
trí ký tự) và trả về mục văn bản kèm vị trí tương đối của ``quote`` trong đó. Dùng
chung cho hàng đợi duyệt (``review.queue``) và bề mặt tra cứu (``query/``) nên P1
chỉ được cài đặt một lần.

Mọi trường trả về là văn bản THUẦN; client PHẢI render bằng text node (không nhúng
HTML) nên bề mặt này an toàn với tô sáng. Nếu không dựng được khoảng chính xác,
hàm tìm ``quote`` trong văn bản mục; vẫn không thấy thì để vị trí rỗng.

Tệp Excel (biên bản) không có Markdown: thay cho mục văn bản, ``source_location``
chỉ ra sheet/dòng/ô sinh ra ``quote`` (``query.sheet_locate``) để giao diện vẽ lại
đúng lưới ô gốc và tô ô chứa ``value``; ``sheet_quote`` (cả dòng chứa ô) được ưu
tiên để định vị khi ``quote`` chỉ là giá trị một ô; ``sheet_value_part`` là vị trí ô
nguồn trong dòng đó để không tô nhầm ô khác cùng chữ.
"""

from __future__ import annotations

from typing import Any


def build_source_view(
    *,
    file_stem: str | None,
    section_path: str | None,
    quote: str | None,
    char_start: int | None = None,
    char_end: int | None = None,
    chunk_id: str | None = None,
    value: str | None = None,
    sheet_quote: str | None = None,
    sheet_value_part: int | None = None,
) -> dict[str, Any]:
    """Trả ``{section_path, chunk_id, quote, char_*, section_text, quote_*, source_location}``."""
    view: dict[str, Any] = {
        "section_path": section_path,
        "chunk_id": chunk_id,
        "quote": quote,
        "char_start": char_start,
        "char_end": char_end,
        "section_text": None,
        "quote_start": None,
        "quote_end": None,
        "source_location": None,
    }

    markdown: str | None = None
    if file_stem:
        try:
            from ingestion import jobs as ingestion_jobs

            markdown = ingestion_jobs.get_markdown(file_stem)
        except Exception:  # noqa: BLE001 - nguồn chỉ để hiển thị, không chặn tra cứu
            markdown = None
    if not markdown:
        view["source_location"] = _sheet_location(
            file_stem, sheet_quote or quote, value, sheet_value_part
        )
        return view

    from knowledge.rules.sections import split_sections

    sections = split_sections(markdown)
    section = next((item for item in sections if item.path == section_path), None)
    text = section.body if section is not None else markdown
    base_offset = section.body_start if section is not None else 0

    start: int | None = None
    end: int | None = None
    if char_start is not None and char_end is not None:
        start = char_start - base_offset
        end = char_end - base_offset
    if start is None or end is None or not (0 <= start <= end <= len(text)):
        index = text.find(quote) if quote else -1
        if index >= 0:
            start, end = index, index + len(quote or "")
        else:
            start = end = None

    view.update({"section_text": text, "quote_start": start, "quote_end": end})
    return view


_SHEET_SUFFIXES = (".xlsx", ".xls")


def _sheet_location(
    file_stem: str | None, quote: str | None, value: str | None, value_part: int | None
) -> dict | None:
    """Toạ độ sheet/dòng/ô của ``quote`` khi nguồn là tệp Excel; ngược lại ``None``."""
    if not file_stem or not quote:
        return None
    try:
        from ingestion import jobs as ingestion_jobs
        from query.sheet_locate import locate_in_file

        source = ingestion_jobs.get_source_path(file_stem)
        if source is None or source.suffix.lower() not in _SHEET_SUFFIXES:
            return None
        preview = ingestion_jobs.get_preview_path(file_stem)
    except Exception:  # noqa: BLE001 - nguồn chỉ để hiển thị, không chặn tra cứu
        return None
    return locate_in_file(preview, quote, value, value_part) if preview is not None else None
