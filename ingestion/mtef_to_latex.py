"""Convert MathType OLE (.bin) files to LaTeX via:

    MTEF binary  →  gem mathtype_to_mathml (Ruby)  →  MathML  →  LaTeX (Python)

Route:
  1. Call the ``mathtype_to_mathml`` Ruby gem as a subprocess (takes a file path,
     returns MathML XML on stdout).
  2. Parse the MathML with lxml.
  3. Walk the MathML element tree with a compact recursive Python converter that
     handles the element types observed in the QTKĐ corpus:
       mi, mn, mo, mtext, mrow, mfrac, msqrt, mroot, msup, msub, msubsup,
       mmultiscripts, mover, munder, munderover, mfenced, mtable/mtr/mtd,
       math (root)
     Unicode codepoints are mapped to LaTeX commands via a lookup table; anything
     unknown passes through as-is so output degrades gracefully.
  4. Return a bare LaTeX string (no $$…$$ delimiters — caller wraps as needed).

The Ruby gem is invoked with GEM_PATH set so user-installed gems are visible.
All exceptions are caught; the function returns None on any failure.
"""
from __future__ import annotations

import os
import subprocess
import sys
from typing import Optional

from lxml import etree

# ---------------------------------------------------------------------------
# 1. Ruby gem invocation
# ---------------------------------------------------------------------------

_GEM_PATHS = [
    os.path.expanduser("~/.gem/ruby/2.6.0"),
    "/Library/Ruby/Gems/2.6.0",
    "/System/Library/Frameworks/Ruby.framework/Versions/2.6/usr/lib/ruby/gems/2.6.0",
]
_GEM_PATH_ENV = ":".join(_GEM_PATHS)

_RUBY_SNIPPET = r"""
require 'mathtype_to_mathml'
puts MathTypeToMathML::Converter.new(ARGV[0]).convert
"""


def _bin_to_mathml(bin_path: str, timeout: int = 15) -> Optional[str]:
    """Run Ruby gem and return MathML string, or None on error."""
    env = os.environ.copy()
    env["GEM_PATH"] = _GEM_PATH_ENV
    try:
        result = subprocess.run(
            ["ruby", "-e", _RUBY_SNIPPET, "--", bin_path],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        if result.returncode != 0:
            return None
        mathml = result.stdout.strip()
        return mathml if mathml else None
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None


# ---------------------------------------------------------------------------
# 2. MathML → LaTeX  (pure Python, lxml element-tree walk)
# ---------------------------------------------------------------------------

MML_NS = "http://www.w3.org/1998/Math/MathML"


def _tag(el) -> str:
    """Local tag name, stripping any namespace."""
    t = el.tag
    if isinstance(t, str) and "}" in t:
        return t.split("}", 1)[1]
    return t if isinstance(t, str) else ""


def _text(el) -> str:
    return (el.text or "").strip()


def _children(el):
    return list(el)


def _seq(el) -> str:
    return "".join(_node(c) for c in _children(el))


# Unicode → LaTeX command mapping (covers what the QTKĐ corpus produces)
_UNI_TO_LATEX: dict[str, str] = {
    # Greek lowercase
    "α": r"\alpha", "β": r"\beta", "γ": r"\gamma",
    "δ": r"\delta", "ε": r"\varepsilon", "ζ": r"\zeta",
    "η": r"\eta", "θ": r"\theta", "ι": r"\iota",
    "κ": r"\kappa", "λ": r"\lambda", "μ": r"\mu",
    "ν": r"\nu", "ξ": r"\xi", "π": r"\pi",
    "ρ": r"\rho", "σ": r"\sigma", "τ": r"\tau",
    "υ": r"\upsilon", "φ": r"\varphi", "χ": r"\chi",
    "ψ": r"\psi", "ω": r"\omega",
    # Greek uppercase
    "Α": r"\Alpha", "Β": r"\Beta", "Γ": r"\Gamma",
    "Δ": r"\Delta", "Ε": r"\Epsilon", "Ζ": r"\Zeta",
    "Η": r"\Eta", "Θ": r"\Theta", "Ι": r"\Iota",
    "Κ": r"\Kappa", "Λ": r"\Lambda", "Μ": r"\Mu",
    "Ν": r"\Nu", "Ξ": r"\Xi", "Π": r"\Pi",
    "Ρ": r"\Rho", "Σ": r"\Sigma", "Τ": r"\Tau",
    "Υ": r"\Upsilon", "Φ": r"\Phi", "Χ": r"\Chi",
    "Ψ": r"\Psi", "Ω": r"\Omega",
    # Operators / relations
    "×": r"\times", "÷": r"\div",
    "−": r"-",      "±": r"\pm",  "∓": r"\mp",
    "≠": r"\neq",   "≤": r"\leq", "≥": r"\geq",
    "≪": r"\ll",    "≫": r"\gg",
    "≈": r"\approx","∼": r"\sim", "≃": r"\simeq",
    "∝": r"\propto","∞": r"\infty",
    "∂": r"\partial","∇": r"\nabla",
    "∫": r"\int",   "∬": r"\iint","∭": r"\iiint",
    "∏": r"\prod",  "∑": r"\sum",
    "√": r"\sqrt",
    "∈": r"\in",    "∉": r"\notin",
    "⊂": r"\subset","⊃": r"\supset",
    "⊆": r"\subseteq","⊇": r"\supseteq",
    "∪": r"\cup",   "∩": r"\cap",
    "∀": r"\forall","∃": r"\exists",
    "¬": r"\neg",   "∧": r"\wedge","∨": r"\vee",
    "⇒": r"\Rightarrow","⇔": r"\Leftrightarrow",
    "→": r"\rightarrow","←": r"\leftarrow",
    "↔": r"\leftrightarrow",
    "⋅": r"\cdot",  "·": r"\cdot",
    "…": r"\ldots", "⋯": r"\cdots","⋮": r"\vdots",
    "⋱": r"\ddots",
    "≡": r"\equiv", "≍": r"\asymp",
    "°": r"^{\circ}",
    "²": r"^{2}",   "³": r"^{3}",
    "⁰": r"^{0}",
    "½": r"\frac{1}{2}",
    "∞": r"\infty",
    # Misc math
    "∅": r"\emptyset","ℝ": r"\mathbb{R}",
    "ℤ": r"\mathbb{Z}","ℕ": r"\mathbb{N}",
    "ℚ": r"\mathbb{Q}","ℂ": r"\mathbb{C}",
    "ℓ": r"\ell",
    # Fence chars used in mfenced
    "(": "(", ")": ")", "[": "[", "]": "]",
    "{": r"\{", "}": r"\}",
    "|": r"|",  "‖": r"\|",
    "⟨": r"\langle", "⟩": r"\rangle",
    "⌊": r"\lfloor", "⌋": r"\rfloor",
    "⌈": r"\lceil",  "⌉": r"\rceil",
}


def _uni_to_latex(s: str) -> str:
    """Replace each character that has a LaTeX mapping, pass rest through."""
    out = []
    for ch in s:
        out.append(_UNI_TO_LATEX.get(ch, ch))
    return "".join(out)


def _brace(s: str) -> str:
    """Wrap in braces if more than one token, else return as-is."""
    s = s.strip()
    if len(s) == 1:
        return s
    return "{" + s + "}"


def _node(el) -> str:  # noqa: C901
    tag = _tag(el)

    # --- leaf text nodes ---
    if tag in ("mi", "mn", "mtext"):
        return _uni_to_latex(_text(el))

    if tag == "mo":
        raw = _text(el)
        mapped = _uni_to_latex(raw)
        # Add thin spaces around binary operators for readability
        if mapped in ("+", "-", r"\pm", r"\mp", r"\times", r"\div",
                      "=", r"\neq", r"\leq", r"\geq", "<", ">",
                      r"\approx", r"\sim", r"\equiv", r"\propto"):
            return f" {mapped} "
        return mapped

    if tag == "mspace":
        return r"\,"

    # --- grouping ---
    if tag in ("mrow", "math", "mstyle", "mpadded", "merror"):
        return _seq(el)

    # --- fraction ---
    if tag == "mfrac":
        kids = _children(el)
        num = _node(kids[0]) if len(kids) > 0 else ""
        den = _node(kids[1]) if len(kids) > 1 else ""
        return rf"\frac{{{num}}}{{{den}}}"

    # --- square root ---
    if tag == "msqrt":
        return rf"\sqrt{{{_seq(el)}}}"

    # --- nth root ---
    if tag == "mroot":
        kids = _children(el)
        base = _node(kids[0]) if len(kids) > 0 else ""
        idx  = _node(kids[1]) if len(kids) > 1 else ""
        return rf"\sqrt[{idx}]{{{base}}}"

    # --- sub / sup ---
    if tag == "msub":
        kids = _children(el)
        base = _node(kids[0]) if len(kids) > 0 else ""
        sub  = _node(kids[1]) if len(kids) > 1 else ""
        return f"{base}_{{{sub}}}"

    if tag == "msup":
        kids = _children(el)
        base = _node(kids[0]) if len(kids) > 0 else ""
        sup  = _node(kids[1]) if len(kids) > 1 else ""
        return f"{base}^{{{sup}}}"

    if tag == "msubsup":
        kids = _children(el)
        base = _node(kids[0]) if len(kids) > 0 else ""
        sub  = _node(kids[1]) if len(kids) > 1 else ""
        sup  = _node(kids[2]) if len(kids) > 2 else ""
        return f"{base}_{{{sub}}}^{{{sup}}}"

    # --- over / under (accents, limits) ---
    if tag == "mover":
        kids = _children(el)
        base = _node(kids[0]) if len(kids) > 0 else ""
        acc  = _node(kids[1]) if len(kids) > 1 else ""
        # common accent operators
        _OVER = {
            r"\rightarrow": r"\vec", "^": r"\hat", "~": r"\tilde",
            r"-": r"\bar", ".": r"\dot", "..": r"\ddot",
        }
        if acc in _OVER:
            return rf"{_OVER[acc]}{{{base}}}"
        if acc in ("→", "→"):
            return rf"\vec{{{base}}}"
        if acc in ("̅", "¯"):
            return rf"\overline{{{base}}}"
        return rf"\overset{{{acc}}}{{{base}}}"

    if tag == "munder":
        kids = _children(el)
        base = _node(kids[0]) if len(kids) > 0 else ""
        acc  = _node(kids[1]) if len(kids) > 1 else ""
        if acc == "_":
            return rf"\underline{{{base}}}"
        return rf"\underset{{{acc}}}{{{base}}}"

    if tag == "munderover":
        kids = _children(el)
        base = _node(kids[0]) if len(kids) > 0 else ""
        under= _node(kids[1]) if len(kids) > 1 else ""
        over = _node(kids[2]) if len(kids) > 2 else ""
        return f"{base}_{{{under}}}^{{{over}}}"

    # --- mmultiscripts (pre-scripts) ---
    if tag == "mmultiscripts":
        # Simplified: base + postscripts only (pre-scripts uncommon in corpus)
        kids = _children(el)
        if not kids:
            return ""
        base = _node(kids[0])
        out = base
        i = 1
        while i < len(kids):
            ek = _tag(kids[i])
            if ek == "mprescripts":
                break
            sub_el = kids[i] if i < len(kids) else None
            sup_el = kids[i+1] if i+1 < len(kids) else None
            if sub_el is not None:
                sv = _node(sub_el)
                if sv and sv not in ("", "none"):
                    out += f"_{{{sv}}}"
            if sup_el is not None:
                sv = _node(sup_el)
                if sv and sv not in ("", "none"):
                    out += f"^{{{sv}}}"
            i += 2
        return out

    # --- fenced (parentheses, brackets) ---
    if tag == "mfenced":
        open_c  = _uni_to_latex(el.get("open",  "("))
        close_c = _uni_to_latex(el.get("close", ")"))
        sep     = el.get("separators", ",")
        kids = _children(el)
        inner_parts = [_node(k) for k in kids]
        # Use first separator char between parts (MathML spec)
        sep_char = sep[0] if sep else ","
        inner = f" {sep_char} ".join(inner_parts)
        return rf"\left{open_c} {inner} \right{close_c}"

    # --- table (matrix, cases, …) ---
    if tag == "mtable":
        rows = []
        for tr in _children(el):
            if _tag(tr) in ("mtr", "mlabeledtr"):
                cells = [_node(td) for td in _children(tr) if _tag(td) == "mtd"]
                rows.append(" & ".join(cells))
        body = r" \\ ".join(rows)
        return rf"\begin{{matrix}} {body} \end{{matrix}}"

    if tag in ("mtr", "mlabeledtr"):
        cells = [_node(td) for td in _children(el) if _tag(td) == "mtd"]
        return " & ".join(cells)

    if tag == "mtd":
        return _seq(el)

    # --- phantom, menclose, etc. ---
    if tag == "mphantom":
        return rf"\phantom{{{_seq(el)}}}"

    if tag == "menclose":
        notation = el.get("notation", "box")
        inner = _seq(el)
        if "box" in notation:
            return rf"\boxed{{{inner}}}"
        if "radical" in notation:
            return rf"\sqrt{{{inner}}}"
        return inner

    if tag == "msqrt":
        return rf"\sqrt{{{_seq(el)}}}"

    if tag in ("none", "mprescripts"):
        return ""

    # --- fallback: descend into children ---
    return _seq(el)


def mathml_to_latex(mathml_str: str) -> Optional[str]:
    """Parse MathML XML string and return a LaTeX string."""
    try:
        root = etree.fromstring(mathml_str.encode("utf-8"))
        latex = _node(root).strip()
        # Normalise whitespace
        return " ".join(latex.split()) if latex else None
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------------------
# 3. Public API
# ---------------------------------------------------------------------------

def mtef_bin_to_latex(bin_path: str) -> Optional[str]:
    """Convert a MathType OLE .bin file to a LaTeX string.

    Returns None on any failure (gem crash, parse error, empty output).
    Never raises.
    """
    try:
        mathml = _bin_to_mathml(bin_path)
        if not mathml:
            return None
        return mathml_to_latex(mathml)
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------------------
# 4. CLI smoke-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import glob

    asset_root = os.path.join(
        os.path.dirname(__file__),
        "..", "build", "spike_a", "assets"
    )
    bins = sorted(glob.glob(os.path.join(asset_root, "**", "*.bin"), recursive=True))
    print(f"Found {len(bins)} .bin files\n")

    gem_ok = 0
    latex_ok = 0
    fails = []
    samples = []

    for i, b in enumerate(bins):
        mathml = _bin_to_mathml(b)
        if mathml:
            gem_ok += 1
            latex = mathml_to_latex(mathml)
            if latex:
                latex_ok += 1
                if len(samples) < 5:
                    samples.append((os.path.basename(b), latex))
            else:
                fails.append((b, "mathml-to-latex-failed"))
        else:
            fails.append((b, "gem-failed"))

        if (i + 1) % 20 == 0:
            print(f"  {i+1}/{len(bins)}  gem_ok={gem_ok}  latex_ok={latex_ok}",
                  flush=True)

    print(f"\nTotal : {len(bins)}")
    print(f"gem OK: {gem_ok}")
    print(f"LaTeX : {latex_ok}")
    print(f"Fails : {len(fails)}")

    print("\nSample outputs:")
    for name, latex in samples:
        print(f"  {name}: {latex}")

    if fails[:5]:
        print("\nFirst failures:")
        for p, reason in fails[:5]:
            print(f"  {os.path.basename(p)}: {reason}")
