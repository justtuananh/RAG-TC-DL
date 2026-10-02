"""Panel nguồn của Gradio UI render công thức bằng KaTeX auto-render chạy OFFLINE.

Gradio chỉ đóng gói CSS + font KaTeX, không để lộ ``window.renderMathInElement``; thiếu hai
script này thì mọi ``$...$`` trong panel nguồn hiện nguyên văn (đo 2026-10-02).
"""

from ui import gradio_app as app


def test_katex_scripts_are_vendored():
    for name in ("katex.min.js", "auto-render.min.js"):
        path = app.KATEX_DIR / name
        assert path.is_file() and path.stat().st_size > 0, path


def test_head_loads_katex_before_auto_render_from_local_files():
    head = app.katex_head()
    katex_at = head.index("katex.min.js")
    assert katex_at < head.index("auto-render.min.js")  # auto-render cần window.katex
    assert "http://" not in head and "https://" not in head  # không CDN: hệ chạy offline
