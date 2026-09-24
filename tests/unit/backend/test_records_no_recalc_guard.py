"""Guard P2: tầng ``records/`` không bao giờ tính lại số liệu nguồn.

Sai số, giá trị đo trong hồ sơ phải đọc nguyên trạng (spec P2). Bộ guard quét mã
nguồn ``records/`` và fail nếu bắt gặp phép trừ ``measured``/``nominal`` hoặc gán
``error`` từ hai giá trị đó. Ngoại lệ duy nhất được phép là ``expires_at`` dẫn
xuất từ dữ kiện chu kỳ (nằm ngoài phép quét này).
"""

from __future__ import annotations

import re
from pathlib import Path

# Phép trừ giữa measured và nominal (bất kể thứ tự) — nguồn sai số bị cấm.
_SUBTRACTION_RE = re.compile(
    r"\b(?:measured|nominal)[a-z_]*\b\s*-\s*\b(?:measured|nominal)[a-z_]*\b"
)
# Gán error_value = ... có dính measured/nominal.
_ERROR_ASSIGN_RE = re.compile(r"\berror[a-z_]*\s*=\s*[^=\n]*(?:measured|nominal)", re.IGNORECASE)


def _records_files(repo_root: Path) -> list[Path]:
    root = repo_root / "records"
    return sorted(path for path in root.rglob("*.py") if path.is_file())


def test_records_layer_never_subtracts_measured_and_nominal(repo_root):
    violations: list[str] = []
    for path in _records_files(repo_root):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if _SUBTRACTION_RE.search(line) or _ERROR_ASSIGN_RE.search(line):
                violations.append(f"{path}:{lineno}: {line.strip()}")
    assert violations == [], "Phát hiện tính lại số liệu nguồn trong records/:\n" + "\n".join(
        violations
    )
