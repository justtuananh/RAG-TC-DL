"""Extract a .pdf into Markdown via PyMuPDF (best-effort, no formula recovery).

spike_a.py uses extract_pdf_marker.py instead, which recovers formulas at the
cost of a much heavier dependency (Marker + CUDA torch, see
requirements-pdf.txt). This module stays as the lightweight fallback for
callers that don't need formula fidelity or don't have that environment set up.

Unlike .docx (MathType OLE objects recovered losslessly by extract_docx.py +
mtef_to_latex.py — see CLAUDE.md, "risk #1"), a PDF carries no embedded formula
object we can parse: formulas are just glyphs baked into the page, so any
formula comes through as plain text (or is lost/garbled), never as verified
LaTeX. Treat PDF ingestion as a lower-fidelity path, not a substitute for the
.docx pipeline.

Was MarkItDown (pdfminer.six backend) until real-world testing showed it
mangling text into space-less runs with `(cid:0)` artifacts on some pages —
a known pdfminer failure mode for PDFs with broken per-glyph width tables in
their embedded font. PyMuPDF renders via the font program itself instead of
trusting content-stream width metrics, so it doesn't hit that failure.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import pymupdf

_HEADING_RE = re.compile(r"^#{1,6}\s", re.MULTILINE)
_TABLE_SEP_RE = re.compile(r"^\|[\s:|-]+\|$", re.MULTILINE)


@dataclass
class PdfExtractResult:
    markdown: str
    n_headings: int
    n_tables: int


def extract_pdf(path: str) -> PdfExtractResult:
    doc = pymupdf.open(path)
    try:
        # sort=True orders text by reading position (top-to-bottom,
        # left-to-right per block) instead of raw content-stream order,
        # which otherwise interleaves badly on multi-column pages.
        pages = [page.get_text("text", sort=True).strip() for page in doc]
    finally:
        doc.close()
    md = "\n\n".join(p for p in pages if p)
    return PdfExtractResult(
        markdown=md,
        n_headings=len(_HEADING_RE.findall(md)),
        n_tables=len(_TABLE_SEP_RE.findall(md)),
    )
