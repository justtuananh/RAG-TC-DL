"""KaTeX delimiters + observer — hợp đồng để công thức inline $...$ render được.

Gradio 4.x mặc định chỉ bật $$...$$ (block); app phải khai cả $...$ (inline) và
chèn MutationObserver re-render KaTeX cho .qtkd-viewer.
"""

import app


def test_latex_delimiters_enable_inline_and_block():
    assert {"left": "$$", "right": "$$", "display": True} in app.LATEX_DELIMITERS
    assert {"left": "$", "right": "$", "display": False} in app.LATEX_DELIMITERS


def test_katex_observer_targets_viewer():
    assert ".qtkd-viewer" in app._JS_KATEX_OBSERVER
    assert "renderMathInElement" in app._JS_KATEX_OBSERVER
