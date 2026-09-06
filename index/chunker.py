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
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class Chunk:
    chunk_id: str        # sha256[:16] of (file+section+text)
    parent_id: Optional[str]   # None for parent chunks
    is_parent: bool
    kind: str            # "section" | "paragraph" | "table" | "formula"
    text: str            # actual content (with heading prefix for parents)
    section_path: str    # e.g. "3 Các phép kiểm định > 3.1 Phép đo"
    file_stem: str       # source .md file stem (= docx name)


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")
_TABLE_ROW_RE = re.compile(r"^\|")
_FORMULA_ONLY_RE = re.compile(r"^\s*\$[^$]+\$\s*$")

# Window size for synthetic sections (see _synthesize_sections) — keeps both
# the parent (section) and its child chunks well inside any embedding
# model's context, whether the source has real paragraph breaks or (as seen
# with MarkItDown's PDF output on multi-column layouts) almost none at all.
_SYNTH_SECTION_CHARS = 4000


def _make_id(file_stem: str, section: str, text: str) -> str:
    raw = f"{file_stem}\x00{section}\x00{text}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _is_blank(line: str) -> bool:
    return line.strip() == ""


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
        cid = _make_id(file_stem, section_path, text)
        children.append(Chunk(
            chunk_id=cid,
            parent_id=parent_id,
            is_parent=False,
            kind=kind,
            text=text,
            section_path=section_path,
            file_stem=file_stem,
        ))
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

    Break the raw text into fixed-size windows (at whitespace boundaries so
    words aren't split) and prefix each with a synthetic heading, turning an
    unbounded blob into a bounded number of indexable sections."""
    windows: list[str] = []
    n = len(text)
    start = 0
    while start < n:
        end = min(start + _SYNTH_SECTION_CHARS, n)
        if end < n:
            ws = text.rfind(" ", start, end)
            if ws > start:
                end = ws
        window = text[start:end].strip()
        if window:
            windows.append(window)
        start = end
    return "\n\n".join(
        f"# {file_stem} (phần {i})\n\n{w}" for i, w in enumerate(windows, 1)
    )


def parse_file(md_path: Path) -> list[Chunk]:
    """Parse one Markdown file → list of parent + child Chunks."""
    text = md_path.read_text(encoding="utf-8")
    file_stem = md_path.stem
    if not any(_HEADING_RE.match(line) for line in text.split("\n")):
        text = _synthesize_sections(text, file_stem)
    lines = text.split("\n")

    chunks: list[Chunk] = []

    # Track current section
    current_level: int = 0
    current_heading: str = ""
    current_body_lines: list[str] = []
    section_stack: list[str] = []   # heading texts by level

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
        chunks.append(Chunk(
            chunk_id=parent_id,
            parent_id=None,
            is_parent=True,
            kind="section",
            text=full_text,
            section_path=section_path,
            file_stem=file_stem,
        ))

        # Child chunks
        if body:
            children = _split_body_into_children(
                body, section_path, file_stem, parent_id
            )
            chunks.extend(children)

        current_body_lines.clear()

    for line in lines:
        m = _HEADING_RE.match(line)
        if m:
            flush_section()
            level = len(m.group(1))
            heading_text = m.group(2).strip()
            current_level = level
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
