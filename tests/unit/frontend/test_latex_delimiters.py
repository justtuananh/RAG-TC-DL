"""KaTeX delimiters + observer - hợp đồng để công thức inline $...$ render được.

Gradio mặc định chỉ bật $$...$$ (block); app phải khai cả $...$ (inline) và
chèn MutationObserver re-render KaTeX cho .qtkd-viewer.
"""

from ui import gradio_app as app


def test_latex_delimiters_enable_inline_and_block():
    assert {"left": "$$", "right": "$$", "display": True} in app.LATEX_DELIMITERS
    assert {"left": "$", "right": "$", "display": False} in app.LATEX_DELIMITERS


def test_katex_observer_runs_from_head_after_library():
    # Tham số js= của launch() thực thi chuỗi như CODE: một arrow function chỉ được định
    # nghĩa, không được gọi, nên observer chưa từng chạy (đo 2026-10-02). Đặt trong <head>.
    head = app.katex_head()
    assert ".qtkd-viewer" in head and "renderMathInElement" in head
    assert head.index("auto-render.min.js") < head.index("MutationObserver")
    assert "DOMContentLoaded" in head  # body chưa có khi script trong <head> chạy
