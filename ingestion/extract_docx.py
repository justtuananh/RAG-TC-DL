"""Extract a .docx into clean Markdown + a formula inventory.

The hard part of this project: formulas are embedded as MathType OLE objects
(`word/embeddings/oleObject*.bin`, MTEF) plus a rendered WMF image
(`word/media/image*.wmf`) — they are NOT text. A naive text extraction drops
every formula. This module walks `word/document.xml` in document order so we:

  * keep the heading hierarchy (for parent-document retrieval later),
  * keep tables as Markdown,
  * insert a placeholder token  ⟦Fxxx⟧  at the exact position of each formula,
  * and record, for each formula, the OLE (.bin) and image (.wmf/.emf/.png)
    assets so a later stage can convert them to LaTeX.

No heavy dependencies — only lxml. MTEF parsing lives in `mtef.py`.
"""
from __future__ import annotations

import posixpath
import re
import zipfile
from dataclasses import dataclass, field

from lxml import etree

from .omml import omml_to_latex

# ---- OOXML namespaces -------------------------------------------------------
NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "o": "urn:schemas-microsoft-com:office:office",
    "v": "urn:schemas-microsoft-com:vml",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
    "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}


def _q(tag: str) -> str:
    """'w:t' -> '{namespace}t' for ElementTree comparisons."""
    prefix, local = tag.split(":")
    return f"{{{NS[prefix]}}}{local}"


def _local(tag) -> str:
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


# Precompute fully-qualified tag names we test against in the hot loop.
T_T = _q("w:t")
T_TAB = _q("w:tab")
T_BR = _q("w:br")
T_CR = _q("w:cr")
T_OLE = _q("o:OLEObject")
T_IMAGEDATA = _q("v:imagedata")
T_BLIP = _q("a:blip")
T_OMATH = _q("m:oMath")
R_ID = f"{{{NS['r']}}}id"
R_EMBED = f"{{{NS['r']}}}embed"


@dataclass
class Formula:
    fid: str
    kind: str               # "ole" (MathType MTEF) or "omml" (native Word math)
    section: str            # heading path the formula sits under
    ole_target: str | None = None  # e.g. word/embeddings/oleObject1.bin
    img_target: str | None = None  # e.g. word/media/image2.wmf
    latex: str | None = None       # filled now for OMML; later for OLE
    in_table: bool = False


@dataclass
class DocResult:
    markdown: str
    formulas: list[Formula] = field(default_factory=list)
    n_headings: int = 0
    n_tables: int = 0
    n_paragraphs: int = 0
    media: list[str] = field(default_factory=list)        # all media parts
    embeddings: list[str] = field(default_factory=list)   # all embedded ole parts


def _load_rels(z: zipfile.ZipFile) -> dict[str, str]:
    """Map relationship id -> absolute part path (e.g. word/embeddings/x.bin)."""
    rels: dict[str, str] = {}
    try:
        xml = z.read("word/_rels/document.xml.rels")
    except KeyError:
        return rels
    root = etree.fromstring(xml)
    for rel in root.findall(_q("rel:Relationship")):
        rid = rel.get("Id")
        target = rel.get("Target")
        mode = rel.get("TargetMode", "Internal")
        if rid and target and mode != "External":
            # Targets are relative to the word/ folder.
            rels[rid] = posixpath.normpath(posixpath.join("word", target))
    return rels


def _heading_level(p) -> int | None:
    """Return 1..9 if the paragraph is a heading style, else None.

    Only trusts explicit Word heading styles (heading1..heading9).
    The outlineLvl attribute is intentionally NOT used as a fallback because
    it is also set on list-item paragraphs in some QTKD files, causing body
    text to be misclassified as headings (QTKD_1.071 bug: 3 bullet lines
    emitted as ### headings, making sections 5.2.1 and 5.2.5 appear empty).
    """
    ppr = p.find(_q("w:pPr"))
    if ppr is None:
        return None
    pstyle = ppr.find(_q("w:pStyle"))
    if pstyle is None:
        return None
    val = (pstyle.get(_q("w:val")) or "").lower()
    m = re.match(r"heading(\d)", val)
    if m:
        return int(m.group(1))
    if val.startswith("toc") or val in {"tieude", "title"}:
        return None  # skip table-of-contents entries / cover title
    return None


_CAPTION_RE = re.compile(r"(?:Hình|Bảng)\s+\d")


def _is_body_masquerading_as_heading(text: str) -> bool:
    """Đoạn văn bị tác giả gán style Heading trong .docx nhưng thực chất là body.

    Bốn dấu hiệu (đối chiếu 0 false-positive trên toàn bộ heading thật của 7 file):
      - bullet ("- ", "– ");
      - câu dài có dấu chấm giữa chừng;
      - KẾT THÚC bằng "." / ";" — heading thật không bao giờ (bắt câu tiêu chí
        "Sai số tương đối của H3000 không được vượt quá ± 0,1 %." từng bị hoisted
        khỏi mục 5.3 thành heading riêng → fact ±0,1 % biến mất khỏi parent 5.3);
      - caption "Hình N…"/"Bảng N…" ("Hình 1. Sơ đồ kết nối AKC và H3000…").
    """
    t = text.strip()
    return (
        t.startswith("- ")
        or t.startswith("– ")
        or (len(t) > 80 and ". " in t)
        or t.endswith(".")
        or t.endswith(";")
        or bool(_CAPTION_RE.match(t))
    )


def _inline(el, rels, formulas, section_path, *, in_table=False, counter=None):
    """Render the inline content of a paragraph/cell in document order.

    Appends discovered formulas to `formulas` and returns the text with
    ⟦Fxxx⟧ placeholders at the formula positions.
    """
    out: list[str] = []
    skip_until: list = []  # subtrees already consumed (OMML) — don't re-emit text
    for node in el.iter():
        if skip_until:
            # Drop descendants of an already-converted OMML zone.
            anc = node.getparent()
            while anc is not None:
                if anc is skip_until[0]:
                    break
                anc = anc.getparent()
            if anc is not None:
                continue
            skip_until.pop()
        tag = node.tag
        if tag == T_OMATH:
            counter[0] += 1
            fid = f"F{counter[0]:03d}"
            latex = omml_to_latex(node)
            formulas.append(Formula(fid, "omml",
                                    " > ".join(section_path) or "(root)",
                                    latex=latex, in_table=in_table))
            out.append(f" $ {latex} $ ")
            skip_until.append(node)  # don't let .iter() re-emit its m:t runs
        elif tag == T_T:
            out.append(node.text or "")
        elif tag in (T_TAB,):
            out.append(" ")
        elif tag in (T_BR, T_CR):
            out.append(" ")
        elif tag == T_OLE:
            counter[0] += 1
            fid = f"F{counter[0]:03d}"
            ole_target = rels.get(node.get(R_ID))
            # The rendered image lives in the same <w:object> wrapper.
            img_target = None
            parent = node.getparent()
            if parent is not None:
                imagedata = parent.find(f".//{T_IMAGEDATA}")
                if imagedata is not None:
                    img_target = rels.get(imagedata.get(R_ID))
            formulas.append(Formula(fid, "ole",
                                    " > ".join(section_path) or "(root)",
                                    ole_target=ole_target, img_target=img_target,
                                    in_table=in_table))
            out.append(f" ⟦{fid}⟧ ")
    text = "".join(out)
    # collapse runaway whitespace but keep single spaces
    return re.sub(r"[ \t]{2,}", " ", text).strip()


def _table_md(tbl, rels, formulas, section_path, counter) -> str:
    rows: list[list[str]] = []
    for tr in tbl.findall(_q("w:tr")):
        cells = []
        for tc in tr.findall(_q("w:tc")):
            cells.append(_inline(tc, rels, formulas, section_path,
                                 in_table=True, counter=counter).replace("|", "\\|"))
        if cells:
            rows.append(cells)
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    lines = ["| " + " | ".join(rows[0]) + " |",
             "| " + " | ".join(["---"] * width) + " |"]
    for r in rows[1:]:
        lines.append("| " + " | ".join(r) + " |")
    return "\n".join(lines)


def extract_docx(path: str) -> DocResult:
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        rels = _load_rels(z)
        doc_xml = z.read("word/document.xml")
        media = sorted(n for n in names if n.startswith("word/media/"))
        embeddings = sorted(n for n in names if n.startswith("word/embeddings/"))

    root = etree.fromstring(doc_xml)
    body = root.find(_q("w:body"))
    if body is None:
        return DocResult("", media=media, embeddings=embeddings)

    md: list[str] = []
    formulas: list[Formula] = []
    counter = [0]
    section_path: list[str] = []
    n_headings = n_tables = n_paragraphs = 0

    for child in body:
        tag = child.tag
        if tag == _q("w:p"):
            n_paragraphs += 1
            level = _heading_level(child)
            text = _inline(child, rels, formulas, section_path, counter=counter)
            # Guard: body text accidentally formatted with a heading style
            # (bullet / câu / caption) — see _is_body_masquerading_as_heading.
            if level is not None and _is_body_masquerading_as_heading(text):
                level = None
            if level is not None and text:
                n_headings += 1
                section_path[:] = section_path[: level - 1]
                while len(section_path) < level - 1:
                    section_path.append("")
                section_path.append(text)
                md.append(f"\n{'#' * min(level, 6)} {text}\n")
            elif text:
                md.append(text)
        elif tag == _q("w:tbl"):
            n_tables += 1
            tbl_md = _table_md(child, rels, formulas, section_path, counter)
            if tbl_md:
                md.append("\n" + tbl_md + "\n")

    return DocResult(
        markdown="\n\n".join(md).strip() + "\n",
        formulas=formulas,
        n_headings=n_headings,
        n_tables=n_tables,
        n_paragraphs=n_paragraphs,
        media=media,
        embeddings=embeddings,
    )
