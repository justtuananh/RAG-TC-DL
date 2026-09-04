"""Spike A runner — prove we can extract structure + every formula.

Walks the corpus, and for each .docx:
  * writes clean Markdown (headings + tables + ⟦Fxxx⟧ formula placeholders),
  * dumps each formula's OLE (.bin) and rendered image (.wmf/.emf/.png) to
    build/spike_a/assets/<file>/,
  * analyzes the MTEF stream to confirm the formula is recoverable.

For each .pdf: writes Markdown via Marker (local Surya/Texify OCR, selective
per-page force_ocr — see extract_pdf_marker.py for why and pdf_math_scan.py
for the page-routing heuristic). Requires the separate .venv-pdf environment
(requirements-pdf.txt); raises MarkerNotConfigured with setup instructions
if that environment isn't found.

Legacy .doc/.xls are reported but skipped (they need LibreOffice conversion
first — that is Spike B).

Run:  python -m ingestion.spike_a [SRC_DIR] [OUT_DIR]
"""
from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

from .extract_docx import extract_docx
from .extract_pdf_marker import extract_pdf_marker
from .mtef import analyze
from .mtef_to_latex import mtef_bin_to_latex

SRC_DEFAULT = "TC_DL"
OUT_DEFAULT = "build/spike_a"


def _safe(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-._" else "_" for c in name)


def _dump_asset(z: zipfile.ZipFile, part: str | None, dest: Path) -> int:
    if not part:
        return 0
    try:
        data = z.read(part)
    except KeyError:
        return 0
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return len(data)


def process_one(f: Path, out_dir: Path) -> dict:
    """Extract one .docx -> writes out_dir/<stem>.md + assets, returns its report entry.

    Entry shape matches what run() appends to report["files"]; totals across
    many entries are recomputed by totals_from_entries(), so a single upload
    can be extracted without re-processing the rest of the corpus.
    """
    assets_root = out_dir / "assets"
    ext = f.suffix.lower()
    if ext == ".pdf":
        return _process_pdf(f, out_dir)
    if ext != ".docx":
        return {
            "file": f.name, "status": "skipped-legacy",
            "note": "needs LibreOffice .doc/.xls -> .docx (Spike B)",
        }

    res = extract_docx(str(f))
    stem = _safe(f.stem)

    per_formula = []
    n_ole = n_omml = 0
    with zipfile.ZipFile(f) as z:
        for fm in res.formulas:
            if fm.kind == "omml":
                n_omml += 1
                per_formula.append({
                    "fid": fm.fid, "kind": "omml", "section": fm.section,
                    "in_table": fm.in_table, "latex": fm.latex,
                })
                continue
            # OLE / MathType: dump assets + analyze MTEF
            n_ole += 1
            a_dir = assets_root / stem
            ole_dst = a_dir / f"{fm.fid}.bin"
            ole_n = _dump_asset(z, fm.ole_target, ole_dst)
            img_ext = Path(fm.img_target).suffix if fm.img_target else ".img"
            img_dst = a_dir / f"{fm.fid}{img_ext}"
            img_n = _dump_asset(z, fm.img_target, img_dst)
            mt = analyze(str(ole_dst)) if ole_n else None
            latex = mtef_bin_to_latex(str(ole_dst)) if ole_n else None
            if latex:
                fm.latex = latex
            per_formula.append({
                "fid": fm.fid, "kind": "ole", "section": fm.section,
                "in_table": fm.in_table, "latex": latex,
                "ole": fm.ole_target, "ole_bytes": ole_n,
                "img": fm.img_target, "img_bytes": img_n,
                "mtef": (None if mt is None else {
                    "ok": mt.ok, "reason": mt.reason,
                    "version": mt.mtef_version, "bytes": mt.mtef_bytes,
                }),
            })
    # Replace ⟦Fxxx⟧ placeholders with $LaTeX$ in Markdown
    md = res.markdown
    for fm in res.formulas:
        if fm.kind == "ole":
            replacement = f"${fm.latex}$" if fm.latex else "[công thức không đọc được]"
            md = md.replace(f"⟦{fm.fid}⟧", replacement)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{stem}.md").write_text(md, encoding="utf-8")

    return {
        "file": f.name, "status": "ok",
        "headings": res.n_headings, "tables": res.n_tables,
        "paragraphs": res.n_paragraphs,
        "media_parts": len(res.media), "embedded_ole": len(res.embeddings),
        "formulas_found": len(res.formulas),
        "formulas_ole": n_ole, "formulas_omml": n_omml,
        "formula_detail": per_formula,
    }


def _process_pdf(f: Path, out_dir: Path) -> dict:
    """Extract one .pdf -> writes out_dir/<stem>.md via Marker (see extract_pdf_marker.py).

    formulas_found/formulas_ole/formulas_omml/formula_detail stay in the
    same inert shape the .docx path uses (0/0/0/[]) so totals_from_entries()
    keeps working unchanged — the real PDF formula-fidelity signal lives in
    the pdf_* fields instead (not consumed by totals_from_entries, but kept
    in extraction_report.json for manual review, same spirit as .docx's
    formula_detail).
    """
    res = extract_pdf_marker(str(f))
    stem = _safe(f.stem)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{stem}.md").write_text(res.markdown, encoding="utf-8")

    return {
        "file": f.name, "status": "ok", "source_format": "pdf",
        "headings": res.n_headings, "tables": res.n_tables, "paragraphs": 0,
        "media_parts": 0, "embedded_ole": 0,
        "formulas_found": 0, "formulas_ole": 0, "formulas_omml": 0,
        "formula_detail": [],
        "pdf_pages": res.n_pages, "pdf_pages_ocr": res.n_pages_ocr,
        "pdf_equation_blocks": res.n_equation_blocks,
        "pdf_math_spans": res.n_math_spans,
        "pdf_unnormalized_tags": res.n_unnormalized_tags,
        "pdf_elapsed_seconds": res.elapsed_seconds,
        "pdf_runs": res.runs,
    }


def totals_from_entries(entries: list[dict]) -> dict:
    """Recompute report["totals"] from a list of process_one()-shaped entries."""
    tot_formulas = tot_ole = tot_omml = tot_with_img = tot_mtef_ok = tot_omml_ok = 0
    tot_ole_latex_ok = 0
    tot_docx = tot_legacy = 0

    for entry in entries:
        if entry["status"] == "skipped-legacy":
            tot_legacy += 1
            continue
        tot_docx += 1
        tot_formulas += entry["formulas_found"]
        for fd in entry["formula_detail"]:
            if fd["kind"] == "omml":
                tot_omml += 1
                if fd["latex"]:
                    tot_omml_ok += 1
            else:
                tot_ole += 1
                if fd.get("img"):
                    tot_with_img += 1
                if fd["latex"]:
                    tot_ole_latex_ok += 1
                mt = fd.get("mtef")
                if mt and mt.get("ok"):
                    tot_mtef_ok += 1

    ole_mtef_rate = round(tot_mtef_ok / tot_ole, 4) if tot_ole else None
    ole_latex_rate = round(tot_ole_latex_ok / tot_ole, 4) if tot_ole else None
    omml_rate = round(tot_omml_ok / tot_omml, 4) if tot_omml else None
    latex_total = tot_ole_latex_ok + tot_omml_ok
    return {
        "docx_processed": tot_docx,
        "legacy_skipped": tot_legacy,
        "formulas_found": tot_formulas,
        "formulas_ole_mathtype": tot_ole,
        "formulas_omml_native": tot_omml,
        "ole_with_image": tot_with_img,
        "ole_mtef_recoverable": tot_mtef_ok,
        "ole_mtef_rate": ole_mtef_rate,
        "ole_latex_converted": tot_ole_latex_ok,
        "ole_latex_rate": ole_latex_rate,
        "omml_latex_converted": tot_omml_ok,
        "omml_latex_rate": omml_rate,
        "formulas_latex_total": latex_total,
        "latex_rate_total": round(latex_total / tot_formulas, 4) if tot_formulas else None,
    }


def run(src_dir: str, out_dir: str) -> dict:
    src = Path(src_dir)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    files = sorted(src.iterdir())
    report = {"source": str(src), "files": [process_one(f, out) for f in files], "totals": {}}
    report["totals"] = totals_from_entries(report["files"])

    (out / "extraction_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    src = sys.argv[1] if len(sys.argv) > 1 else SRC_DEFAULT
    out = sys.argv[2] if len(sys.argv) > 2 else OUT_DEFAULT
    rep = run(src, out)
    t = rep["totals"]
    print("=== Spike A — extraction report ===")
    print(f"  docx processed       : {t['docx_processed']}")
    print(f"  legacy skipped       : {t['legacy_skipped']}  (.doc/.xls -> Spike B)")
    print(f"  formulas found       : {t['formulas_found']}")
    print(f"   - OLE (MathType)    : {t['formulas_ole_mathtype']}"
          f"   ->LaTeX {t['ole_latex_converted']} ({t['ole_latex_rate']})")
    print(f"   - OMML (Word math)  : {t['formulas_omml_native']}"
          f"   ->LaTeX {t['omml_latex_converted']} ({t['omml_latex_rate']})")
    print(f"  LaTeX total          : {t['formulas_latex_total']}"
          f"/{t['formulas_found']}  ({t['latex_rate_total']})")
    print(f"  -> {OUT_DEFAULT}/extraction_report.json")


if __name__ == "__main__":
    main()
