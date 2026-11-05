"""Kiểm số liệu tất định: số trong câu trả lời phải có trong nguồn đã đưa cho model.

Model 7B thỉnh thoảng bịa số gần giống nguồn ("(65 ± 10) %" thay cho "(65 ± 15) %"). Hai loại
biểu thức được kiểm, đều tách biệt khỏi số hiệu mục ("6.3.1") và mã QTKĐ ("1.061"):
- ``a ± b``: cả cụm phải xuất hiện liền nhau trong ngữ cảnh (sau chuẩn hóa);
- ``số + đơn vị``: số phải xuất hiện trong ngữ cảnh (số viết bằng chữ như "ba lần" nằm ngoài
  phạm vi, nên đơn vị "lần" không được kiểm).
Chỉ là hàm thuần trên chuỗi, không import tầng khác.
"""

from __future__ import annotations

import re

_NUM = r"\d+(?:\.\d+)?"
_UNIT = (
    r"(?:mm/min|mm/s|r/min|mbar|bar|MPa|kPa|Pa|mm|cm|mL|ml|min|phút|giờ|giây|tháng|năm|ngày"
    r"|oC|°C|℃|kg|%|[hsLm])"
)
_PM = re.compile(rf"({_NUM})\s*±\s*({_NUM})")
_NUM_UNIT = re.compile(rf"(?<![\w.])({_NUM})\s*{_UNIT}(?![A-Za-zÀ-ỹ])")
_CITATION = re.compile(r"\[\d+\]")
_LATEX_CMD = re.compile(r"\\(?:left|right|text|mathrm|,|;|!)")


def _clean(text: str) -> str:
    """Bỏ LaTeX, đổi dấu phẩy thập phân thành dấu chấm, ghép nhóm nghìn ("1 400" -> "1400")."""
    t = text.replace("\\pm", "±").replace("\\%", "%").replace("\\times", "×")
    t = _LATEX_CMD.sub("", t).replace("$", "").replace("{", "").replace("}", "").replace(" ", " ")
    t = re.sub(r"(?<=\d),(?=\d)", ".", t)
    t = re.sub(r"(?<=\d) (?=\d{3}(?!\d))", "", t)
    return t


def _canon(num: str) -> str:
    """'01' -> '1', '2.50' -> '2.5' để so số không phụ thuộc cách viết."""
    try:
        f = float(num)
    except ValueError:
        return num
    return str(int(f)) if f == int(f) else repr(f)


def unsupported(answer: str, context: str) -> list[str]:
    """Biểu thức số trong ``answer`` KHÔNG có trong ``context`` (rỗng = ổn)."""
    body = _clean(_CITATION.sub("", answer))
    ctx = _clean(context)
    ctx_nums = {_canon(m) for m in re.findall(rf"(?<![\d.]){_NUM}", ctx)}
    ctx_pm = {f"{_canon(a)}±{_canon(b)}" for a, b in _PM.findall(ctx)}
    bad: list[str] = []
    pm_spans: list[tuple[int, int]] = []
    for m in _PM.finditer(body):
        pm_spans.append(m.span())
        if f"{_canon(m.group(1))}±{_canon(m.group(2))}" not in ctx_pm:
            bad.append(re.sub(r"\s+", " ", m.group(0)).strip())
    for m in _NUM_UNIT.finditer(body):
        if any(a <= m.start() < b for a, b in pm_spans):
            continue
        if _canon(m.group(1)) not in ctx_nums:
            bad.append(re.sub(r"\s+", " ", m.group(0)).strip())
    seen: set[str] = set()
    return [b for b in bad if not (b in seen or seen.add(b))]
