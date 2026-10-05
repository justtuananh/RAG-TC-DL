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


# Công thức thật của QTKĐ 1.159 mà gem 0.0.7 chuyển sai; vendor/mathtype_to_mathml/patch.rb
# vá khi chạy. Kỳ vọng đối chiếu với ảnh WMF gốc của từng công thức.
_FIXTURES = _ROOT / "tests" / "fixtures" / "mtef"


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        # Căn thức (tmROOT) từng bị bỏ: "\frac{U(t)}{}".
        (
            "qtkd1159_F076_sqrt",
            r"u_{5}(p) = p \times (\alpha_{p,s} + \alpha_{c,s}) \times \frac{U(t)}{\sqrt{2}}",
        ),
        # Ngoặc lồng nhau từng ghép sai: "(U)(p)^{2}".
        ("qtkd1159_F131_nested_paren", r"\delta = \frac{\sqrt{(\Delta p)^{2} + (U(p))^{2}}}{p}"),
        # Chỉ số "đứng trước" ở cuối slot từng ra "A0t".
        ("qtkd1159_F130_dangling_presub", r"\Delta p = \frac{M}{A_{0t}} \times (g_{s} - g)"),
        # Chữ kiểu Text (đơn vị) từng bị bỏ: "\rho_{f},^{}".
        ("qtkd1159_F168_text_unit", r"\rho_{f},\text{kg/}\text{m}^{\text{3}}"),
    ],
)
def test_gem_patch_matches_the_source_image(sample_bin, name, expected):
    assert mtef_bin_to_latex(str(_FIXTURES / f"{name}.bin")) == expected
