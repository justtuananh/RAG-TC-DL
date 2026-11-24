"""Split QTKĐ Markdown files into parent + child chunks for indexing.

Strategy (parent-document retrieval):
  - PARENT: each heading section (full text, stored in payload for context expansion)
  - CHILD: paragraphs / tables / formula blocks within a section (embedded & searched)

Each child carries its parent_id so the retriever can fetch the full section.

Output: list[Chunk] per file, with is_parent=True|False.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from core import outline
from core.schema import Chunk
from core.settings_loader import get_settings

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")
_TABLE_ROW_RE = re.compile(r"^\|")
_FORMULA_ONLY_RE = re.compile(r"^\s*\$[^$]+\$\s*$")

# Window size for synthetic sections (see _synthesize_sections) — keeps both
# the parent (section) and its child chunks well inside any embedding
# model's context, whether the source has real paragraph breaks or (as seen
# with MarkItDown's PDF output on multi-column layouts) almost none at all.
# Ngưỡng đọc từ settings.chunking.synth_section_chars.

# Bảng dài (danh mục chuẩn, danh mục quy trình... hàng chục dòng) nếu để nguyên
# một chunk thì một dòng cụ thể bị "loãng" trong embedding. Bảng vượt ngưỡng được
# chia theo nhóm dòng; mỗi nhóm lặp lại tiêu đề cột và mang đề mục nhóm gần nhất.
# Ngưỡng đọc từ settings.chunking.max_table_rows / table_group_rows.
_TABLE_SEPARATOR_RE = re.compile(r"^\|\s*:?-{3,}")
_GROUP_HEADING_RE = re.compile(r"^\|\s*[IVXLC]+\s*\|")


def _make_id(file_stem: str, section: str, text: str) -> str:
    raw = f"{file_stem}\x00{section}\x00{text}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _is_blank(line: str) -> bool:
    return line.strip() == ""


def _split_table(text: str) -> list[str]:
    """Chia bảng dài thành các nhóm dòng; bảng ngắn/không chuẩn trả nguyên bảng.

    Mỗi nhóm = dòng tiêu đề + dòng phân cách + (đề mục nhóm đang hiệu lực, nếu
    nhóm bắt đầu giữa chừng một nhóm) + tối đa ``_TABLE_GROUP_ROWS`` dòng dữ liệu.
    Dòng đề mục (ô đầu là số La Mã: "| IV | PHƯƠNG TIỆN ĐO ÁP SUẤT |") là ngữ
    cảnh, không tính vào số dòng dữ liệu.
    """
    rows = text.split("\n")
    if len(rows) < 3 or not _TABLE_SEPARATOR_RE.match(rows[1]):
        return [text]
    chunking = get_settings().chunking
    header, body = rows[:2], rows[2:]
    data_rows = sum(not _GROUP_HEADING_RE.match(row) for row in body)
    if data_rows <= chunking.max_table_rows and len(text) <= chunking.table_group_chars:
        return [text]
    header_chars = sum(len(row) + 1 for row in header)
    groups: list[list[str]] = []
    current: list[str] = []
    heading: str | None = None
    count = 0
    size = header_chars
    for row in body:
        if _GROUP_HEADING_RE.match(row):
            heading = row
            current.append(row)
            size += len(row) + 1
            continue
        # Bảng nhiều chữ (bộ hỏi đáp): nhóm đầy theo ký tự trước khi đủ số dòng.
        too_long = count > 0 and size + len(row) + 1 > chunking.table_group_chars
        if count == chunking.table_group_rows or too_long:
            groups.append(current)
            current = [heading] if heading else []
            count = 0
            size = header_chars + sum(len(r) + 1 for r in current)
        current.append(row)
        size += len(row) + 1
        count += 1
    if current:
        groups.append(current)
    return ["\n".join(header + group) for group in groups]


def _split_body_into_children(
    body: str,
    section_path: str,
    file_stem: str,
    parent_id: str,
) -> list[Chunk]:
    """Split section body into paragraph / table / formula child chunks."""
    children: list[Chunk] = []
    lines = body.split("\n")

    buffer: list[str] = []
    in_table = False

    def flush(kind: str = "paragraph") -> None:
        text = "\n".join(buffer).strip()
        if not text:
            return
        if kind == "paragraph" and _FORMULA_ONLY_RE.match(text):
            kind = "formula"
        parts = _split_table(text) if kind == "table" else [text]
        for part in parts:
            children.append(
                Chunk(
                    chunk_id=_make_id(file_stem, section_path, part),
                    parent_id=parent_id,
                    is_parent=False,
                    kind=kind,
                    text=part,
                    section_path=section_path,
                    file_stem=file_stem,
                )
            )
        buffer.clear()

    for line in lines:
        is_table_row = bool(_TABLE_ROW_RE.match(line))

        if in_table:
            if is_table_row or _is_blank(line):
                if is_table_row:
                    buffer.append(line)
                else:
                    flush("table")
                    in_table = False
            else:
                flush("table")
                in_table = False
                buffer.append(line)
        else:
            if is_table_row:
                if buffer:
                    flush()
                in_table = True
                buffer.append(line)
            elif _is_blank(line):
                if buffer:
                    flush()
            else:
                buffer.append(line)

    if buffer:
        flush("table" if in_table else "paragraph")

    return children


def _synthesize_sections(text: str, file_stem: str) -> str:
    """Fallback for Markdown with zero headings (e.g. MarkItDown's PDF output,
    which never infers heading levels — unlike extract_docx.py, which always
    emits at least one). Without a heading, flush_section() below has no
    section to attach the body to and silently drops it, so parse_file()
    returns zero chunks for the whole file.

    Break the raw text into windows of about ``synth_section_chars`` on line
    boundaries, so a table row is never cut in half; a window that starts
    inside a table repeats the table's header rows (otherwise its rows are no
    longer a Markdown table and cannot be split into row groups). Only a single
    line longer than a window (PDF text without line breaks) is cut, at
    whitespace, and prefix each window with a synthetic heading."""
    size = get_settings().chunking.synth_section_chars
    windows: list[list[str]] = []
    current: list[str] = []
    current_size = 0
    table_header: list[str] = []
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if not _TABLE_ROW_RE.match(line):
            table_header = []
        elif not table_header and i + 1 < len(lines) and _TABLE_SEPARATOR_RE.match(lines[i + 1]):
            table_header = [line, lines[i + 1]]
        for piece in _wrap_long_line(line, size):
            if current and current_size + len(piece) + 1 > size:
                windows.append(current)
                in_table_body = table_header and piece not in table_header
                current = list(table_header) if in_table_body else []
                current_size = sum(len(row) + 1 for row in current)
            current.append(piece)
            current_size += len(piece) + 1
    if current:
        windows.append(current)
    texts = [w for w in ("\n".join(window).strip() for window in windows) if w]
    return "\n\n".join(f"# {file_stem} (phần {i})\n\n{w}" for i, w in enumerate(texts, 1))


def _wrap_long_line(line: str, size: int) -> list[str]:
    """A line longer than ``size`` is cut at whitespace (words stay whole); others stay as is."""
    pieces: list[str] = []
    while len(line) > size:
        cut = line.rfind(" ", 0, size)
        if cut <= 0:
            cut = size
        pieces.append(line[:cut])
        line = line[cut:].lstrip(" ")
    pieces.append(line)
    return pieces


_OVERSIZED_SECTION_FACTOR = 3  # mục suy ra dài hơn (bảng thuật ngữ TCVN 6165) chia thành "(phần i)"


def parse_file(md_path: Path) -> list[Chunk]:
    """Parse one Markdown file → list of parent + child Chunks."""
    text = md_path.read_text(encoding="utf-8")
    file_stem = md_path.stem
    if not any(_HEADING_RE.match(line) for line in text.split("\n")):
        window = get_settings().chunking.synth_section_chars
        promoted = outline.promote_numbered_headings(
            text, split_limit=window * _OVERSIZED_SECTION_FACTOR, split_window=window
        )
        text = promoted or _synthesize_sections(text, file_stem)
    lines = text.split("\n")

    chunks: list[Chunk] = []

    # Track current section
    current_heading: str = ""
    current_body_lines: list[str] = []
    section_stack: list[str] = []  # heading texts by level

    def flush_section() -> None:
        nonlocal current_heading, current_body_lines
        if not current_heading:
            current_body_lines.clear()
            return

        body = "\n".join(current_body_lines).strip()
        section_path = " > ".join(s for s in section_stack if s)
        full_text = f"{current_heading}\n\n{body}" if body else current_heading

        parent_id = _make_id(file_stem, section_path, full_text)

        # Parent chunk (full section, for context expansion)
        chunks.append(
            Chunk(
                chunk_id=parent_id,
                parent_id=None,
                is_parent=True,
                kind="section",
                text=full_text,
                section_path=section_path,
                file_stem=file_stem,
            )
        )

        # Child chunks
        if body:
            children = _split_body_into_children(body, section_path, file_stem, parent_id)
            chunks.extend(children)

        current_body_lines.clear()

    for line in lines:
        m = _HEADING_RE.match(line)
        if m:
            flush_section()
            level = len(m.group(1))
            heading_text = m.group(2).strip()
            current_heading = line.strip()

            # Maintain section stack by level
            while len(section_stack) < level:
                section_stack.append("")
            section_stack = section_stack[: level - 1]
            section_stack.append(heading_text)
        else:
            current_body_lines.append(line)

    flush_section()
    return chunks


def parse_directory(md_dir: Path) -> list[Chunk]:
    """Parse all *.md files in a directory."""
    all_chunks: list[Chunk] = []
    for md_path in sorted(md_dir.glob("*.md")):
        file_chunks = parse_file(md_path)
        all_chunks.extend(file_chunks)
        parents = sum(1 for c in file_chunks if c.is_parent)
        children = sum(1 for c in file_chunks if not c.is_parent)
        print(f"  {md_path.name}: {parents} sections, {children} children")
    return all_chunks


if __name__ == "__main__":
    import sys

    md_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("build/spike_a")
    chunks = parse_directory(md_dir)
    parents = [c for c in chunks if c.is_parent]
    children = [c for c in chunks if not c.is_parent]
    print(f"\nTotal: {len(chunks)} chunks ({len(parents)} parents, {len(children)} children)")
    kinds = {}
    for c in children:
        kinds[c.kind] = kinds.get(c.kind, 0) + 1
    print(f"Child kinds: {kinds}")
