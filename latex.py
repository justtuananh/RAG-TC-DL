"""Chuẩn hoá LaTeX từ output LLM để KaTeX/markdown render được.

Tách từ `app.py` + `api_server.py` (trước đây trùng y hệt) về 1 nguồn dùng chung.
"""
from __future__ import annotations

import re

_RE_DISPLAY = re.compile(r'\$\$(.*?)\$\$', re.DOTALL)
_RE_INLINE = re.compile(r'(?<!\$)\$(?!\$)((?:[^$\n\\]|\\.)*)(?<!\$)\$(?!\$)')
_RE_CODE_MATH = re.compile(r'`(\$.*?\$)`')
_RE_BACKSLASH_DISP = re.compile(r'\\\[(.*?)\\\]', re.DOTALL)          # \[...\] display
_RE_BACKSLASH_INLINE = re.compile(r'\\\((.*?)\\\)')                    # \(...\) inline
_RE_BRACKET_DISP = re.compile(r'(?m)^\[$\n(.*?)\n^\]$', re.DOTALL)     # [ \n ... \n ] display


def fix_latex(text: str) -> str:
    """Sửa các mẫu LaTeX hỏng của model local cho KaTeX:
    bỏ backtick quanh ``$...$``; ``[\\n...\\n]`` / ``\\[...\\]`` → ``$$...$$``;
    ``\\(...\\)`` → ``$...$``; gộp ``\\\\`` → ``\\`` bên trong ``$$...$$`` và ``$...$``.
    """
    text = _RE_CODE_MATH.sub(r'\1', text)
    text = _RE_BRACKET_DISP.sub(lambda m: '$$\n' + m.group(1).replace('\\\\', '\\') + '\n$$', text)
    text = _RE_BACKSLASH_DISP.sub(lambda m: '$$' + m.group(1).replace('\\\\', '\\') + '$$', text)
    text = _RE_BACKSLASH_INLINE.sub(lambda m: '$' + m.group(1).replace('\\\\', '\\') + '$', text)
    text = _RE_DISPLAY.sub(lambda m: '$$' + m.group(1).replace('\\\\', '\\') + '$$', text)
    text = _RE_INLINE.sub(lambda m: '$' + m.group(1).replace('\\\\', '\\') + '$', text)
    return text
