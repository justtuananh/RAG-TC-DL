"""Extract a .pdf into Markdown via Marker (local Surya/Texify OCR), with
inline-math fidelity that extract_pdf.py's plain PyMuPDF read cannot provide.

Requires a separate, heavyweight environment (Marker + CUDA torch) that is
NOT part of this repo's lightweight ingestion .venv — see requirements-pdf.txt
for setup. Point MARKER_PYTHON at that venv's python executable, or accept
the default of .venv-pdf next to this repo.

Why this exists (see CLAUDE.md, "risk #1" — formula fidelity):
  - Marker's *displayed* equations (a standalone block the layout model crops
    as an image and OCRs with a dedicated math model) come out correct
    regardless of extraction mode.
  - Marker's *inline* math is only recognized correctly when the whole page
    is OCR'd (`--force_ocr`); on a page it instead reads via the PDF's native
    text layer (the default, much faster path), subscript/superscript
    positioning is silently discarded — see pdf_math_scan.py's docstring.
  - Running --force_ocr on every page is ~10x slower than the native-text
    path (measured: 181s/page vs 18s/page on an RTX 5060 8GB). This module
    uses pdf_math_scan.py to force OCR only on pages that actually need it.

Validated end-to-end on a 193-page real-world PDF (branch
experiment/pdf-formula-marker): selective OCR cut total extraction time by
~64% versus force_ocr on every page, with no accuracy loss observed on the
OCR'd pages (spot-checked against the source images) and no missed inline
math observed on the pages left on the fast path.

Known residual issue this module cleans up: Marker's force_ocr output mixes
`$LaTeX$` spans with raw `<sub>`/`<sup>` HTML for what is semantically the
same kind of content (e.g. `capture<sub>L</sub>` next to `$3DGS_L$` in the
same sentence) — see _normalize_sub_sup(). This is a formatting
inconsistency, not data loss: the subscript text itself is intact either
way, just not uniformly `$LaTeX$` as the rest of this project's pipeline
assumes.
"""
from __future__ import annotations

import os
import re
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from .pdf_math_scan import flags_to_runs, scan_pdf_pages

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_VENV = _REPO_ROOT / ".venv-pdf"

_WORD_SUB_RE = re.compile(r"(\w+)<sub>(\w+)</sub>")
_WORD_SUP_RE = re.compile(r"(\w+)<sup>(\w+)</sup>")
_BARE_SUB_RE = re.compile(r"<sub>(\w+)</sub>")
_BARE_SUP_RE = re.compile(r"<sup>(\w+)</sup>")
_MATH_SPAN_RE = re.compile(r"\$[^$]+\$")
_EQUATION_TAG_RE = re.compile(r"\\tag\{")
_HEADING_RE = re.compile(r"^#{1,6}\s", re.MULTILINE)
_TABLE_SEP_RE = re.compile(r"^\|[\s:|-]+\|$", re.MULTILINE)


class MarkerNotConfigured(RuntimeError):
    """Raised when no usable Marker Python environment can be found.

    Deliberately not swallowed into a fallback to the lossy extract_pdf.py
    path: silently degrading formula fidelity is worse than a loud, fixable
    setup error (see CLAUDE.md, "risk #1").
    """


@dataclass
class PdfMarkerResult:
    markdown: str
    n_pages: int
    n_pages_ocr: int
    n_headings: int
    n_tables: int
    n_equation_blocks: int
    n_math_spans: int
    n_unnormalized_tags: int
    elapsed_seconds: float
    runs: list[dict] = field(default_factory=list)


def _marker_python(marker_python: str | None) -> str:
    candidate = marker_python or os.environ.get("MARKER_PYTHON")
    if candidate:
        if not Path(candidate).exists():
            raise MarkerNotConfigured(f"MARKER_PYTHON points at a missing file: {candidate}")
        return candidate
    scripts_dir = "Scripts" if os.name == "nt" else "bin"
    exe_name = "python.exe" if os.name == "nt" else "python"
    default = _DEFAULT_VENV / scripts_dir / exe_name
    if default.exists():
        return str(default)
    raise MarkerNotConfigured(
        "No Marker Python environment found. Set MARKER_PYTHON to a venv "
        f"python with marker-pdf installed (see requirements-pdf.txt), or "
        f"create one at {_DEFAULT_VENV} (`uv venv --python 3.12 {_DEFAULT_VENV.name}`)."
    )


def _marker_single_exe(python_exe: str) -> str:
    scripts_dir = Path(python_exe).parent
    name = "marker_single.exe" if os.name == "nt" else "marker_single"
    exe = scripts_dir / name
    if not exe.exists():
        raise MarkerNotConfigured(
            f"marker_single not found next to {python_exe} — "
            f"install marker-pdf into that environment (see requirements-pdf.txt)."
        )
    return str(exe)


def _run_timeout(start: int, end: int, force_ocr: bool) -> int:
    """Generous per-run budget, not a tight one: this only exists to catch a
    genuinely stuck subprocess (e.g. GPU memory held by another orphaned
    Marker process — hit exactly this during development) rather than to cap
    normal-but-slow runs. Padded well above the worst per-page time observed
    in testing (~250s/page for a force_ocr page with heavy tables/figures).
    """
    n_pages = end - start + 1
    per_page = 600 if force_ocr else 90
    return 600 + n_pages * per_page


def _run_marker(marker_exe: str, pdf_path: str, page_range: str, out_dir: Path, force_ocr: bool) -> str:
    cmd = [
        marker_exe, pdf_path,
        "--page_range", page_range,
        "--output_dir", str(out_dir),
        "--output_format", "markdown",
    ]
    if force_ocr:
        cmd.append("--force_ocr")
    start, end = (int(p) for p in (page_range.split("-") if "-" in page_range else [page_range, page_range]))
    timeout = _run_timeout(start, end, force_ocr)
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(
            f"Marker didn't finish pages {page_range} within {timeout}s — likely stuck "
            f"(common cause: another Marker/torch process still holding GPU memory; "
            f"check `nvidia-smi` for orphaned python.exe/marker_single.exe processes)."
        ) from e

    stem = Path(pdf_path).stem
    md_path = out_dir / stem / f"{stem}.md"
    return md_path.read_text(encoding="utf-8")


def _normalize_sub_sup(md: str) -> tuple[str, int]:
    """`capture<sub>L</sub>` -> `$capture_L$`; bare `<sub>x</sub>` -> `$_{x}$`.

    Returns (normalized_markdown, tags_normalized) so callers can report how
    much cleanup happened — a large count is a signal the OCR output leaned
    heavily on raw HTML instead of LaTeX and may be worth a closer look.
    """
    count = 0

    def word_sub(m: re.Match) -> str:
        nonlocal count
        count += 1
        return f"${m.group(1)}_{{{m.group(2)}}}$"

    def word_sup(m: re.Match) -> str:
        nonlocal count
        count += 1
        return f"${m.group(1)}^{{{m.group(2)}}}$"

    def bare_sub(m: re.Match) -> str:
        nonlocal count
        count += 1
        return f"$_{{{m.group(1)}}}$"

    def bare_sup(m: re.Match) -> str:
        nonlocal count
        count += 1
        return f"$^{{{m.group(1)}}}$"

    md = _WORD_SUB_RE.sub(word_sub, md)
    md = _WORD_SUP_RE.sub(word_sup, md)
    md = _BARE_SUB_RE.sub(bare_sub, md)
    md = _BARE_SUP_RE.sub(bare_sup, md)
    return md, count


def extract_pdf_marker(pdf_path: str, marker_python: str | None = None) -> PdfMarkerResult:
    """Extract pdf_path to Markdown, OCR-ing only pages the heuristic flags.

    Marker's own per-run scratch output (images, metadata) is written to a
    temp directory that is cleaned up before returning — callers only see
    the combined Markdown and the summary counts.
    """
    python_exe = _marker_python(marker_python)
    marker_exe = _marker_single_exe(python_exe)

    flags = scan_pdf_pages(pdf_path)
    runs = flags_to_runs(flags)
    n_flagged = sum(1 for is_ocr, _, _ in runs if is_ocr)
    print(
        f"[pdf-marker] {Path(pdf_path).name}: {len(flags)} pages, {sum(flags)} flagged "
        f"for OCR, {len(runs)} runs ({n_flagged} need --force_ocr) — this can take a "
        f"long time on a large PDF (~180s/page for OCR runs, ~18s/page for fast runs, "
        f"measured on an RTX 5060 8GB)",
        flush=True,
    )

    t0 = time.monotonic()
    parts: list[str] = []
    run_reports: list[dict] = []
    n_pages_ocr = 0
    with tempfile.TemporaryDirectory(prefix="pdf_marker_") as work_dir:
        for i, (is_ocr, start, end) in enumerate(runs, 1):
            page_range = str(start) if start == end else f"{start}-{end}"
            out_dir = Path(work_dir) / f"run_{start}_{end}_{'ocr' if is_ocr else 'fast'}"
            run_t0 = time.monotonic()
            print(
                f"[pdf-marker] run {i}/{len(runs)}: pages {page_range} "
                f"({'force_ocr' if is_ocr else 'fast'})...",
                flush=True,
            )
            md = _run_marker(marker_exe, pdf_path, page_range, out_dir, force_ocr=is_ocr)
            run_elapsed = time.monotonic() - run_t0
            print(f"[pdf-marker] run {i}/{len(runs)} done in {run_elapsed:.1f}s", flush=True)
            parts.append(md)
            run_reports.append({"pages": page_range, "force_ocr": is_ocr, "chars": len(md)})
            if is_ocr:
                n_pages_ocr += end - start + 1
    elapsed = time.monotonic() - t0
    print(f"[pdf-marker] {Path(pdf_path).name}: done in {elapsed:.1f}s total", flush=True)

    combined = "\n\n".join(parts)
    combined, n_unnormalized = _normalize_sub_sup(combined)

    return PdfMarkerResult(
        markdown=combined,
        n_pages=len(flags),
        n_pages_ocr=n_pages_ocr,
        n_headings=len(_HEADING_RE.findall(combined)),
        n_tables=len(_TABLE_SEP_RE.findall(combined)),
        n_equation_blocks=len(_EQUATION_TAG_RE.findall(combined)),
        n_math_spans=len(_MATH_SPAN_RE.findall(combined)),
        n_unnormalized_tags=n_unnormalized,
        elapsed_seconds=round(elapsed, 1),
        runs=run_reports,
    )
