"""Tầng Ruby: OLE .bin → LaTeX qua gem mathtype_to_mathml (marker ruby, KHÔNG vào CI).

Tự skip nếu Ruby/gem không khả dụng (thử convert 1 .bin đã commit). Đây là nửa còn
lại của pipeline công thức mà tầng unit không chạm tới (unit chỉ test MathML→LaTeX).
"""

from pathlib import Path

import pytest

from ingestion.mtef_to_latex import _bin_to_mathml, mtef_bin_to_latex

_ROOT = Path(__file__).resolve().parents[2]
_BINS = sorted((_ROOT / "build" / "spike_a" / "assets").rglob("*.bin"))


@pytest.fixture(scope="module")
def sample_bin() -> Path:
    if not _BINS:
        pytest.skip(
            "Không có .bin trong build/spike_a/assets — chạy `python -m ingestion.spike_a`."
        )
    b = _BINS[0]
    if _bin_to_mathml(str(b)) is None:
        pytest.skip("Ruby + gem mathtype_to_mathml không khả dụng — bỏ qua tầng ruby.")
    return b


def test_bin_converts_to_nonempty_latex(sample_bin):
    latex = mtef_bin_to_latex(str(sample_bin))
    assert isinstance(latex, str) and latex.strip(), "Gem không trả về LaTeX"


def test_missing_bin_returns_none_without_raising():
    assert mtef_bin_to_latex("/khong/ton/tai/F999.bin") is None
