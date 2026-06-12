"""Guard độ trung thực công thức (rủi ro #1 của dự án) — chỉ dùng thư viện chuẩn.

Đọc các artifact ĐÃ commit trong build/spike_a/ và khẳng định các bất biến:

  1. Tỉ lệ chuyển đổi trong extraction_report.json đều = 1.0
     (ole_mtef_rate, ole_latex_rate, omml_latex_rate, latex_rate_total)
     và formulas_latex_total == formulas_found (không công thức nào bị mất).
  2. Tổng số span `$...$` trong tất cả *.md == totals.formulas_latex_total
     (kiểm tra nội-nhất-quán; KHÔNG hard-code con số nên tự cập nhật khi corpus
     lớn lên hợp lệ). Hiện tại là 351.
  3. LaTeX mỗi công thức cân đối về cấu trúc (KHÔNG tính lại / viết lại):
     dấu {} cân bằng, không có `$` lạ bên trong, \\left/\\right cân bằng.
  4. Không file .md nào còn sentinel "[công thức không đọc được]".

Chạy:
    python scripts/check_fidelity.py [--build-dir build/spike_a]

Exit 0 nếu mọi bất biến đạt; exit 1 + in danh sách vấn đề (tiếng Việt) nếu không.
Hàm check_fidelity() trả về list[str] (rỗng = OK) để test gọi trực tiếp.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_BUILD = _ROOT / "build" / "spike_a"

# Sentinel mà ingestion/spike_a.py phát ra khi một công thức OLE không convert được.
_SENTINEL = "[công thức không đọc được]"

# Một span công thức inline: $...$ (nội dung không chứa $). Đếm theo từng dòng để
# khớp hành vi `grep -oE '\$[^$]+\$'` (không khớp vắt qua nhiều dòng).
_SPAN_RE = re.compile(r"\$[^$]+\$")

# \left / \right như lệnh delimiter — KHÔNG tính \leftarrow, \rightarrow, ...
_LEFT_RE = re.compile(r"\\left(?![a-zA-Z])")
_RIGHT_RE = re.compile(r"\\right(?![a-zA-Z])")

# Các tỉ lệ phải bằng 1.0 (hoặc None nếu không có loại công thức đó).
_RATE_KEYS = ("ole_mtef_rate", "ole_latex_rate", "omml_latex_rate", "latex_rate_total")


def _count_spans(md_text: str) -> int:
    return sum(len(_SPAN_RE.findall(line)) for line in md_text.splitlines())


def _brace_problem(latex: str) -> str | None:
    """Trả mô tả lỗi nếu {} không cân bằng (bỏ qua \\{ \\} đã escape), else None."""
    depth = 0
    i = 0
    n = len(latex)
    while i < n:
        ch = latex[i]
        if ch == "\\":  # bỏ qua ký tự được escape (\\{, \\}, \\\\, ...)
            i += 2
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth < 0:
                return "dấu '}' thừa"
        i += 1
    if depth != 0:
        return f"còn {depth} dấu '{{' chưa đóng"
    return None


def _latex_problem(latex: str) -> str | None:
    """Kiểm tra cấu trúc một chuỗi LaTeX (không tính lại). None nếu hợp lệ."""
    if "$" in latex:
        return "chứa ký tự '$' lạ (LaTeX trong report phải ở dạng trần)"
    b = _brace_problem(latex)
    if b:
        return b
    n_left = len(_LEFT_RE.findall(latex))
    n_right = len(_RIGHT_RE.findall(latex))
    if n_left != n_right:
        return f"\\left ({n_left}) ≠ \\right ({n_right})"
    return None


def check_fidelity(build_dir: Path = _DEFAULT_BUILD) -> list[str]:
    """Trả về danh sách vấn đề (rỗng nghĩa là mọi bất biến đạt)."""
    problems: list[str] = []

    report_path = build_dir / "extraction_report.json"
    if not report_path.exists():
        return [f"Không tìm thấy {report_path} (chạy `python -m ingestion.spike_a` trước)."]

    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        return [f"Không đọc được {report_path}: {e}"]

    totals = report.get("totals", {})

    # ── (1) Tỉ lệ chuyển đổi ──────────────────────────────────────────────────
    for key in _RATE_KEYS:
        rate = totals.get(key)
        if rate is not None and abs(rate - 1.0) > 1e-9:
            problems.append(
                f"totals.{key} = {rate} (kỳ vọng 1.0) — có công thức không convert được."
            )

    found = totals.get("formulas_found")
    latex_total = totals.get("formulas_latex_total")
    if found is None or latex_total is None:
        problems.append("totals thiếu formulas_found / formulas_latex_total.")
    elif found != latex_total:
        problems.append(
            f"formulas_latex_total ({latex_total}) ≠ formulas_found ({found}) "
            f"— {found - latex_total} công thức bị mất khi chuyển LaTeX."
        )

    # ── (2) Bất biến số span $...$ trong Markdown ─────────────────────────────
    md_files = sorted(build_dir.glob("*.md"))
    if not md_files:
        problems.append(f"Không có file .md nào trong {build_dir}.")
    total_spans = 0
    for md in md_files:
        text = md.read_text(encoding="utf-8")
        total_spans += _count_spans(text)
        if _SENTINEL in text:  # ── (4) sentinel ──
            problems.append(f"{md.name}: còn sentinel '{_SENTINEL}' (công thức chưa resolve).")

    if latex_total is not None and md_files and total_spans != latex_total:
        problems.append(
            f"Tổng span $...$ trong *.md = {total_spans} ≠ formulas_latex_total = {latex_total} "
            f"— số công thức trong Markdown lệch với report."
        )

    # ── (3) Cấu trúc LaTeX từng công thức (chỉ file status==ok) ────────────────
    for f in report.get("files", []):
        if f.get("status") != "ok":  # bỏ qua mục legacy (chỉ có file/status/note)
            continue
        for fm in f.get("formula_detail", []):
            latex = fm.get("latex")
            if not latex:
                continue
            prob = _latex_problem(latex)
            if prob:
                problems.append(
                    f"{f.get('file')} [{fm.get('fid')}] {fm.get('section')}: LaTeX lỗi — {prob}"
                )

    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Guard độ trung thực công thức QTKĐ")
    parser.add_argument(
        "--build-dir",
        default=str(_DEFAULT_BUILD),
        help="Thư mục chứa extraction_report.json + *.md (mặc định build/spike_a)",
    )
    args = parser.parse_args(argv)

    build_dir = Path(args.build_dir)
    problems = check_fidelity(build_dir)

    if problems:
        print(f"❌ FIDELITY FAIL — {len(problems)} vấn đề:", file=sys.stderr)
        for p in problems:
            print(f"  • {p}", file=sys.stderr)
        return 1

    # Báo cáo gọn khi đạt.
    report = json.loads((build_dir / "extraction_report.json").read_text(encoding="utf-8"))
    total = report.get("totals", {}).get("formulas_latex_total")
    print(
        f"✅ FIDELITY OK — {total}/{total} công thức, latex_rate_total=1.0, span $...$ khớp report."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
