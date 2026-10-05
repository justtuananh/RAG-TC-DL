"""Chuẩn hoá LaTeX từ output LLM để KaTeX/markdown render được.

Gộp về 1 nguồn dùng chung cho mọi entrypoint (trước đây Gradio UI và tầng API trùng nhau).
"""

from __future__ import annotations

import re

_RE_DISPLAY = re.compile(r'\$\$(.*?)\$\$', re.DOTALL)
_RE_INLINE = re.compile(r'(?<!\$)\$(?!\$)((?:[^$\n\\]|\\.)*)(?<!\$)\$(?!\$)')
_RE_CODE_MATH = re.compile(r'`(\$.*?\$)`')
_RE_BACKSLASH_DISP = re.compile(r'\\\[(.*?)\\\]', re.DOTALL)  # \[...\] display
_RE_BACKSLASH_INLINE = re.compile(r'\\\((.*?)\\\)')  # \(...\) inline
_RE_BRACKET_DISP = re.compile(r'(?m)^\[$\n(.*?)\n^\]$', re.DOTALL)  # [ \n ... \n ] display


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


_RE_MATH = re.compile(r'\$\$(.+?)\$\$|\$([^$\n]+?)\$', re.DOTALL)
_RE_TAG = re.compile(r'\\tag\{[^}]*\}')
# \left / \right, lệnh giãn cách (\, \; \: \! "\ ") và khoảng trắng: chỉ đổi hình thức.
_RE_COSMETIC = re.compile(r'\\left(?![a-zA-Z])|\\right(?![a-zA-Z])|\\[,;:! ]|\s+')
_RE_SINGLE_BRACE = re.compile(r'\{(\\[A-Za-z]+|[A-Za-z0-9])\}')


def _math_spans(text: str) -> list[str]:
    return [(m.group(1) or m.group(2)).strip() for m in _RE_MATH.finditer(text)]


def _formula_key(latex: str) -> str:
    """Khoá so khớp bỏ qua khác biệt hình thức: \\tag, \\left/\\right, giãn cách,
    khoảng trắng, × với \\times, ngoặc nhọn quanh một ký hiệu ({2} = 2)."""
    key = _RE_COSMETIC.sub('', _RE_TAG.sub('', latex).replace('×', '\\times'))
    previous = None
    while previous != key:
        previous, key = key, _RE_SINGLE_BRACE.sub(r'\1', key)
    return key


def restore_formulas(answer: str, context: str) -> str:
    """Thay mỗi công thức của câu trả lời bằng bản NGUYÊN VĂN trong ngữ cảnh khi hai
    bản chỉ khác hình thức (model 7b thêm/bỏ \\left \\right, thêm \\tag, đổi ^{2} → ^2).

    Chạy SAU ``fix_latex`` (cần dấu ``$``). Công thức không có trong nguồn, hoặc khớp
    với hai công thức nguồn khác nhau, được giữ nguyên: không đoán.
    """
    sources: dict[str, set[str]] = {}
    for span in _math_spans(context or ''):
        sources.setdefault(_formula_key(span), set()).add(span)

    def _sub(m: re.Match) -> str:
        span = (m.group(1) or m.group(2)).strip()
        found = sources.get(_formula_key(span), set())
        if len(found) != 1:
            return m.group(0)
        source = next(iter(found))
        if source == span:
            return m.group(0)
        return f'$${source}$$' if m.group(1) is not None else f'${source}$'

    return _RE_MATH.sub(_sub, answer)
