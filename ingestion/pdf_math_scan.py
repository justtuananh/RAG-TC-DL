"""Heuristic page scan: flag PDF pages whose inline math a native text-layer
read would corrupt, so callers can route only those pages through the
expensive OCR-based extractor (see extract_pdf_marker.py) and leave the rest
on the fast path.

Root cause this works around: a born-digital PDF's text layer stores glyph
codepoints in content-stream order with no notion of "this run is a
subscript" — sub/superscripts are typeset by shrinking the font and shifting
the baseline, and that positioning is discarded by any tool that just reads
characters back out (marker's pdftext path included). Standalone/displayed
equations don't have this problem: Marker's layout model crops them as an
image and runs a dedicated math-OCR pass regardless of extraction mode. Only
inline math embedded in ordinary prose is at risk, which is what this scan
targets.

No ML models involved — reads font metadata already embedded in the PDF.
Validated on a 193-page LaTeX-produced PDF (see extraction_report from
branch experiment/pdf-formula-marker): flagged pages matched the document's
actual math-heavy chapters, with no false negatives found in spot-checks.
The math-font-name signal is LaTeX-specific and won't fire on Word-exported
PDFs (the QTKD corpus's real case) — the size-variance and Unicode signals
are format-agnostic and carry the real weight there. Re-validate on a real
QTKD PDF sample before relying on this for production routing.
"""
from __future__ import annotations

import re

import pymupdf

_MATH_FONT_RE = re.compile(
    r"cmmi|cmsy|cmex|cmbsy|msam|msbm|euler|eufm|lmmi|lmsy|lmex|"
    r"txmi|txsy|stix.*math|cambria.*math|asana|latin.*modern.*math|"
    r"xits.*math|mathtime|nimbusromno9l-medi",
    re.IGNORECASE,
)
_MATH_SYMBOL_RE = re.compile("[∀-⋿∂∇√∞∑∏∫≤≥≠±→≡α-ωΑ-Ω]")
_SIZE_RATIO_THRESHOLD = 0.85


def page_needs_ocr(page: pymupdf.Page) -> bool:
    """True if this page likely has inline math a plain text-layer read would corrupt."""
    for block in page.get_text("dict").get("blocks", []):
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            if not spans:
                continue
            sizes = [round(s["size"], 1) for s in spans]
            dominant = max(set(sizes), key=sizes.count)
            for s in spans:
                if _MATH_FONT_RE.search(s["font"]):
                    return True
                if _MATH_SYMBOL_RE.search(s["text"]):
                    return True
                if len(set(sizes)) > 1 and round(s["size"], 1) < dominant * _SIZE_RATIO_THRESHOLD:
                    return True
    return False


def scan_pdf_pages(path: str) -> list[bool]:
    """Per-page OCR-needed flags, in page order (index == 0-based page number)."""
    doc = pymupdf.open(path)
    try:
        return [page_needs_ocr(page) for page in doc]
    finally:
        doc.close()


def flags_to_runs(flags: list[bool]) -> list[tuple[bool, int, int]]:
    """[F,F,T,T,F] -> [(False,0,1), (True,2,3), (False,4,4)] (needs_ocr, start, end).

    Grouping into contiguous runs (rather than one "all flagged" + one "all
    unflagged" batch) keeps every run in original page order, so a caller can
    just concatenate each run's output and get the document back in order —
    no separate merge/interleave step needed.
    """
    if not flags:
        return []
    runs = []
    start = 0
    for i in range(1, len(flags) + 1):
        if i == len(flags) or flags[i] != flags[start]:
            runs.append((flags[start], start, i - 1))
            start = i
    return runs
