"""Convert OOXML math (OMML, ``<m:oMath>``) to LaTeX.

OMML is native Word math stored as structured XML *text* — the easy, lossless
formula case (no OCR, no MTEF parsing). This is a compact recursive converter
covering the constructs that appear in the QTKĐ corpus: runs, fractions,
sub/superscripts, radicals, n-ary operators (∑ ∫ ∏), delimiters, functions,
accents, bars, and matrices. Anything unrecognised falls back to its text
content, so output degrades gracefully rather than dropping symbols.

For 100% construct coverage in production, pandoc or the Microsoft OMML2MML +
xsltml XSLT chain can be swapped in; this keeps the dependency footprint at zero
and proves the route works on the real documents.
"""
from __future__ import annotations

M = "http://schemas.openxmlformats.org/officeDocument/2006/math"


def _ln(el) -> str:
    return el.tag.rsplit("}", 1)[-1] if isinstance(el.tag, str) else ""


def _val(el, child) -> str | None:
    c = el.find(f"{{{M}}}{child}")
    return c.get(f"{{{M}}}val") if c is not None else None


def _child(el, name):
    return el.find(f"{{{M}}}{name}")

# Common n-ary / accent operator characters -> LaTeX command.
_NARY = {"∑": r"\sum", "∫": r"\int", "∏": r"\prod",
         "∬": r"\iint", "∭": r"\iiint", "∐": r"\coprod",
         "⋃": r"\bigcup", "⋂": r"\bigcap"}
_ACC = {"̂": r"\hat", "̃": r"\tilde", "̄": r"\bar",
        "̇": r"\dot", "⃗": r"\vec", "̆": r"\breve"}


def _seq(el) -> str:
    """Convert the math children of an element in order."""
    return "".join(_node(c) for c in el)


def _grp(el, name) -> str:
    c = _child(el, name)
    return _seq(c) if c is not None else ""


def _node(el) -> str:  # noqa: C901 - a flat dispatch is clearest here
    tag = _ln(el)
    if tag == "t":              # run text
        return el.text or ""
    if tag in ("r", "e", "num", "den", "sup", "sub", "deg", "fName", "lim"):
        return _seq(el)
    if tag == "f":              # fraction
        return rf"\frac{{{_grp(el,'num')}}}{{{_grp(el,'den')}}}"
    if tag == "sSup":
        return f"{_grp(el,'e')}^{{{_grp(el,'sup')}}}"
    if tag == "sSub":
        return f"{_grp(el,'e')}_{{{_grp(el,'sub')}}}"
    if tag == "sSubSup":
        return f"{_grp(el,'e')}_{{{_grp(el,'sub')}}}^{{{_grp(el,'sup')}}}"
    if tag == "rad":
        deg = _grp(el, "deg")
        body = _grp(el, "e")
        return rf"\sqrt[{deg}]{{{body}}}" if deg else rf"\sqrt{{{body}}}"
    if tag == "d":              # delimiter ( ) [ ] etc.
        dpr = _child(el, "dPr")
        beg, end = "(", ")"
        if dpr is not None:
            beg = _val(dpr, "begChr") or "("
            end = _val(dpr, "endChr") or ")"
        inner = "".join(_seq(c) for c in el if _ln(c) == "e")
        return rf"\left{beg} {inner} \right{end}"
    if tag == "nary":           # ∑ ∫ ∏ with limits
        npr = _child(el, "naryPr")
        chr_ = _val(npr, "chr") if npr is not None else None
        op = _NARY.get(chr_, _NARY["∫"] if chr_ is None else (chr_ or r"\int"))
        sub, sup = _grp(el, "sub"), _grp(el, "sup")
        body = _grp(el, "e")
        s = op
        if sub:
            s += f"_{{{sub}}}"
        if sup:
            s += f"^{{{sup}}}"
        return f"{s}{{{body}}}" if body else s
    if tag == "func":           # named function (sin, lim, ...)
        return f"{_grp(el,'fName')}{_grp(el,'e')}"
    if tag == "acc":            # accent
        accpr = _child(el, "accPr")
        chr_ = _val(accpr, "chr") if accpr is not None else "̂"
        cmd = _ACC.get(chr_, r"\hat")
        return rf"{cmd}{{{_grp(el,'e')}}}"
    if tag == "bar":
        return rf"\overline{{{_grp(el,'e')}}}"
    if tag == "groupChr":
        return _grp(el, "e")
    if tag == "limLow":
        return f"{_grp(el,'e')}_{{{_grp(el,'lim')}}}"
    if tag == "limUpp":
        return f"{_grp(el,'e')}^{{{_grp(el,'lim')}}}"
    if tag == "m":              # matrix
        rows = []
        for mr in el:
            if _ln(mr) == "mr":
                rows.append(" & ".join(_grp(c, "e") for c in mr if _ln(c) == "e"))
        body = r" \\ ".join(rows)
        return rf"\begin{{matrix}} {body} \end{{matrix}}"
    if tag in ("oMath", "oMathPara", "box", "borderBox"):
        return _seq(el)
    # Containers we descend through silently; leaf props we ignore.
    if tag.endswith("Pr") or tag in ("ctrlPr", "begChr", "endChr", "chr"):
        return ""
    return _seq(el)  # unknown: keep children's content


def omml_to_latex(omath_el) -> str:
    """Convert an <m:oMath> element to a LaTeX string."""
    latex = _seq(omath_el)
    # tidy whitespace
    return " ".join(latex.split())
