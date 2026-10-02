"""QTKĐ RAG Chatbot - Gradio, KaTeX formulas + doc viewer with passage highlight.

Run:
  python -m ui.gradio_app

Layout:
  Left  (60%): chat + input + examples
  Right (40%): source document viewer with highlighted retrieved passages

Service/model: xem config/settings.yaml.
"""

from __future__ import annotations

import html as html_mod
from pathlib import Path

import gradio as gr
import markdown as _md

from core.latex import fix_latex
from llm.generator import stream_ollama as _stream_ollama
from llm.guards import (
    REFUSAL_SENTENCE as _REFUSAL_SENTENCE,
)
from llm.guards import (
    enforce_refusal_stop as _enforce_refusal_stop,
)
from llm.guards import (
    is_calculation_request as _is_calculation_request,
)
from llm.prompt import build_messages as _build_messages
from retrieval.context_builder import (
    build_context_and_citations as _build_context_and_citations,
)
from retrieval.context_builder import (
    filter_by_confidence as _filter_by_confidence,
)
from retrieval.retriever import retrieve

# ── Markdown → HTML renderer (for doc viewer) ─────────────────────────────────

_MD_EXTS = ["tables"]


def _md_to_html(text: str) -> str:
    """Markdown → HTML: tables become <table>, $...$ passes through for KaTeX."""
    return _md.markdown(text, extensions=_MD_EXTS)


# ── Document viewer HTML builder ───────────────────────────────────────────────

_KIND_ICON = {"formula": "∑", "table": "⊞", "paragraph": "¶", "section": "§"}
_PANEL_OPEN = (
    '<div class="doc-panel-wrap">'
    '<div class="doc-panel-hdr">📄 Tài liệu nguồn</div>'
    '<div class="qtkd-viewer">'
)
_PANEL_CLOSE = "</div></div>"

_EMPTY_VIEWER = (
    _PANEL_OPEN + "<div class='doc-empty'>Kết quả tìm kiếm sẽ hiển thị ở đây.</div>" + _PANEL_CLOSE
)


def _highlight_child_in_parent(parent_html: str, child_html: str, child_raw: str) -> str:
    """Inline-highlight child text in Markdown-rendered parent HTML.

    Tables (child_raw starts with '|') go straight to the fallback so the
    rendered <table> is shown below rather than attempting a broken pipe-char match.
    """
    if not child_raw.startswith("|"):
        needle = html_mod.escape(child_raw.strip())
        if needle and needle in parent_html:
            return parent_html.replace(
                needle,
                f'<mark class="qtkd-hl">{needle}</mark>',
                1,
            )
    # Fallback: append rendered child as its own highlighted block
    return (
        parent_html
        + '<div class="doc-hl-sep">▼ Đoạn được truy xuất:</div>'
        + f'<div class="qtkd-hl doc-hl-block">{child_html}</div>'
    )


def build_doc_viewer_html(results: list[dict]) -> str:
    if not results:
        return _EMPTY_VIEWER

    cards: list[str] = []
    for i, r in enumerate(results, 1):
        p = r["payload"]
        pp = r.get("parent_payload")
        file_stem = p["file_stem"]
        section_path = p["section_path"]
        child_text = p["text"]
        kind = p["kind"]
        score = r.get("rerank_score", 0.0)

        display_text = pp["text"] if pp else child_text
        parent_html = _md_to_html(display_text)
        child_html = _md_to_html(child_text)
        highlighted = _highlight_child_in_parent(parent_html, child_html, child_text)

        section_html = html_mod.escape(section_path.replace(" > ", " › "))
        file_html = html_mod.escape(file_stem)
        kind_icon = _KIND_ICON.get(kind, "·")

        score_color = "#16a34a" if score > 0.3 else "#d97706" if score > 0.1 else "#6b7280"

        cards.append(f"""<div class="doc-card">
  <div class="doc-card-hdr">
    <span class="doc-num">[{i}]</span>
    <code class="doc-file">{file_html}</code>
    <span class="doc-kind">{kind_icon} {kind}</span>
    <span class="doc-score" style="color:{score_color}">▲ {score:.3f}</span>
  </div>
  <div class="doc-section">📁 {section_html}</div>
  <div class="doc-body">{highlighted}</div>
</div>""")

    return _PANEL_OPEN + "".join(cards) + _PANEL_CLOSE


# ── Gradio event handlers ──────────────────────────────────────────────────────


def _history_to_prior(history: list) -> list[list[str]]:
    """Convert Gradio-5 dict history → [[user, assistant], ...] cho build_messages."""
    prior: list[list[str]] = []
    i = 0
    while i + 1 < len(history):
        user_turn, bot_turn = history[i], history[i + 1]
        if isinstance(user_turn, dict) and isinstance(bot_turn, dict):
            if user_turn.get("role") == "user" and bot_turn.get("role") == "assistant":
                prior.append([user_turn.get("content", ""), bot_turn.get("content", "")])
        i += 2
    return prior


def user_fn(user_message: str, history: list) -> tuple[str, list]:
    return "", history + [{"role": "user", "content": user_message}]


def bot_fn(history: list):
    """Generator → yields (chatbot_history, doc_viewer_html)."""
    if not history or history[-1].get("role") != "user":
        yield history, gr.update()
        return

    raw = history[-1]["content"]
    query = (
        raw
        if isinstance(raw, str)
        else " ".join(
            p if isinstance(p, str) else (p.get("text", "") if isinstance(p, dict) else "")
            for p in raw
        )
    )
    prior = _history_to_prior(history[:-1])

    # 0. Lookup-only: yêu cầu tính toán với số liệu cho sẵn → từ chối tất định,
    #    không retrieve, không gọi LLM (7b lúc chịu từ chối lúc thay số tính tiếp).
    if _is_calculation_request(query):
        history[-1]["content"] = _REFUSAL_SENTENCE
        yield history, gr.update()
        return

    history = history + [{"role": "assistant", "content": "*⏳ Đang nhúng câu hỏi (embedding)…*"}]
    yield history, gr.update()

    history[-1]["content"] = "*🔍 Đang tìm kiếm trong tài liệu QTKĐ (hybrid)…*"
    yield history, gr.update()
    try:
        results = retrieve(query)
    except Exception as e:
        history[-1]["content"] = f"❌ Lỗi tìm kiếm: {e}"
        yield history, gr.update()
        return

    if not results:
        history[-1]["content"] = "Không tìm thấy thông tin liên quan trong tài liệu QTKĐ."
        yield history, build_doc_viewer_html([])
        return

    # Cắt đuôi nguồn điểm thấp → chỉ hiện + nhồi ngữ cảnh các nguồn uy tín ([n] khớp).
    results = _filter_by_confidence(results)
    # Build doc viewer HTML immediately (show sources while LLM streams)
    doc_html = build_doc_viewer_html(results)
    context_str, citations_md = _build_context_and_citations(results)
    messages = _build_messages(query, context_str, prior)

    history[-1]["content"] = "*💭 Đang tổng hợp câu trả lời…*"
    yield history, doc_html  # ← sources appear here

    # Stream LLM
    partial = ""
    try:
        for delta in _stream_ollama(messages):
            partial += delta
            history[-1]["content"] = partial
            yield history, gr.update()
    except Exception as e:
        history[-1]["content"] = (partial or "") + f"\n\n❌ Lỗi LLM: {e}"
        yield history, gr.update()
        return

    history[-1]["content"] = fix_latex(partial) + citations_md
    # 4. Cắt phần "tính tiếp" sau câu từ chối chuẩn (nếu có) rồi gắn citations
    partial = _enforce_refusal_stop(partial)
    history[-1]["content"] = partial + citations_md
    yield history, gr.update()


def clear_all():
    return [], _EMPTY_VIEWER


# ── CSS ───────────────────────────────────────────────────────────────────────

CSS = """
/* ── Chat bubble ── */
#qtkd-chat .message-bubble-border { border-left: 3px solid #2563eb !important; }
#qtkd-chat .prose blockquote {
    background: #f1f5f9; border-left: 3px solid #94a3b8;
    border-radius: 0 4px 4px 0; margin: 4px 0; padding: 4px 10px;
    color: #475569; font-size: 0.9em;
}
/* Gradio tô chữ <p> theo theme: con của blockquote phải theo màu blockquote, không thì
   chữ sáng của dark theme nằm trên nền sáng ở trên và không đọc được. */
#qtkd-chat .prose blockquote * { color: inherit; }
.dark #qtkd-chat .prose blockquote {
    background: #1e293b; border-left-color: #64748b; color: #cbd5e1;
}
#qtkd-chat .prose code {
    background: #dbeafe; color: #1e40af; padding: 1px 5px;
    border-radius: 3px; font-weight: 500;
}
.katex { font-size: 1.05em !important; }
.katex-display { overflow-x: auto; }
hr { border-color: #e2e8f0; margin: 10px 0; }

/* ── Document panel wrapper (matches left column height visually) ── */
.doc-panel-wrap {
    height: 576px;             /* chatbot(480) + input(52) + gap(8) + btn(36) */
    display: flex;
    flex-direction: column;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    overflow: hidden;
    background: #fff;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}
.doc-panel-hdr {
    padding: 10px 14px;
    font-weight: 600;
    font-size: 0.95em;
    color: #1e293b;
    background: #f8faff;
    border-bottom: 1px solid #e2e8f0;
    flex-shrink: 0;
    letter-spacing: 0.01em;
}
.qtkd-viewer {
    flex: 1;
    overflow-y: auto;
    padding: 8px;
    display: flex;
    flex-direction: column;
    gap: 8px;
}
.doc-empty {
    color: #9ca3af; text-align: center; padding: 60px 20px;
    font-style: italic; font-size: 0.9em;
}

/* ── Source cards ── */
.doc-card {
    background: #fafafa; border: 1px solid #e9edf2;
    border-radius: 7px; padding: 10px 12px;
    flex-shrink: 0;
}
.doc-card-hdr {
    display: flex; align-items: center; gap: 8px;
    flex-wrap: wrap; margin-bottom: 4px;
}
.doc-num  { font-weight: 700; color: #2563eb; font-size: 0.92em; }
.doc-file {
    background: #dbeafe; color: #1e40af; padding: 1px 6px;
    border-radius: 4px; font-family: monospace; font-size: 0.8em;
    font-weight: 600; border: none;
}
.doc-kind { color: #6b7280; font-size: 0.78em; }
.doc-score { margin-left: auto; font-weight: 600; font-size: 0.82em; }
.doc-section {
    font-size: 0.78em; color: #475569; margin-bottom: 6px;
    font-style: italic; word-break: break-word;
}
.doc-body {
    color: #1e293b; line-height: 1.6; font-size: 0.85em;
    word-break: break-word;
}
mark.qtkd-hl {
    background: #0d9488; color: #fff;
    border-radius: 2px; padding: 0 2px;
}
.doc-hl-block { display: block; padding: 4px 6px; border-radius: 4px; margin-top: 6px; }
.doc-hl-sep {
    font-size: 0.75em; color: #6b7280; margin-top: 8px; margin-bottom: 2px;
}

/* ── Tables in doc viewer ── */
.doc-body table {
    border-collapse: collapse; width: 100%;
    font-size: 0.82em; margin: 6px 0; line-height: 1.4;
}
.doc-body th, .doc-body td {
    border: 1px solid #d1d5db; padding: 4px 8px;
    text-align: left; word-break: break-word; vertical-align: top;
}
.doc-body th { background: #f1f5f9; font-weight: 600; color: #334155; }
.doc-body tr:nth-child(even) { background: #f8fafc; }
.doc-body p { margin: 4px 0; }
.doc-body ul, .doc-body ol { margin: 4px 0; padding-left: 18px; }
/* Gradio tô <p>/<li> theo theme: con của panel theo màu panel (giống blockquote ở trên). */
.doc-body * { color: inherit; }

/* ── Dark theme: panel nguồn không giữ nền sáng (chữ sáng của Gradio sẽ chìm) ── */
.dark .doc-panel-wrap { background: #111827; border-color: #374151; }
.dark .qtkd-viewer { color-scheme: dark; }  /* thanh cuộn tối theo panel */
.dark .doc-panel-hdr { background: #1f2937; color: #e5e7eb; border-bottom-color: #374151; }
.dark .doc-card { background: #1f2937; border-color: #374151; }
.dark .doc-body { color: #e5e7eb; }
.dark .doc-section, .dark .doc-kind, .dark .doc-hl-sep { color: #9ca3af; }
.dark .doc-num { color: #60a5fa; }
.dark .doc-body th, .dark .doc-body td { border-color: #4b5563; }
.dark .doc-body th { background: #374151; color: #f3f4f6; }
.dark .doc-body tr:nth-child(even) { background: #182030; }
.dark hr { border-color: #374151; }
"""

LATEX_DELIMITERS = [
    {"left": "$$", "right": "$$", "display": True},
    {"left": "\\[", "right": "\\]", "display": True},
    {"left": "$", "right": "$", "display": False},
    {"left": "\\(", "right": "\\)", "display": False},
]

# KaTeX auto-render cho panel nguồn, phục vụ từ máy (hệ chạy offline, không CDN). Gradio chỉ
# đóng gói CSS + font KaTeX cho chatbot, không để lộ window.renderMathInElement. Bản 0.16.47
# chép từ frontend/node_modules/katex (cùng bản React UI dùng); cập nhật thì chép lại cả hai.
KATEX_DIR = Path(__file__).resolve().parent / "static" / "katex"


def katex_head() -> str:
    """Thẻ <script> nạp KaTeX, auto-render (cần window.katex có trước) rồi observer của panel."""
    scripts = "".join(
        f'<script defer src="/gradio_api/file={KATEX_DIR / name}"></script>'
        for name in ("katex.min.js", "auto-render.min.js")
    )
    return scripts + _KATEX_OBSERVER_SCRIPT


# Re-render KaTeX mỗi khi nội dung .qtkd-viewer đổi. Chạy từ <head> (không qua js= của
# launch(): tham số đó thực thi chuỗi như code, một arrow function chỉ được định nghĩa
# chứ không được gọi). Gradio chèn <head> SAU khi trang tải xong, nên không chờ
# DOMContentLoaded nếu nó đã qua; KaTeX nạp bất đồng bộ nên mỗi lần chạy đều kiểm lại.
_KATEX_OBSERVER_SCRIPT = """
<script>
(() => {
    function renderViewer() {
        const el = document.querySelector(".qtkd-viewer");
        if (el && window.renderMathInElement) {
            window.renderMathInElement(el, {
                delimiters: [
                    {left: "$$", right: "$$", display: true},
                    {left: "\\\\[", right: "\\\\]", display: true},
                    {left: "$", right: "$", display: false},
                    {left: "\\\\(", right: "\\\\)", display: false}
                ],
                throwOnError: false,
                ignoredTags: ["script", "noscript", "style", "textarea", "code"]
            });
        }
    }
    function start() {
        new MutationObserver(renderViewer).observe(document.body, {childList: true, subtree: true});
        renderViewer();
    }
    if (document.readyState === "loading") {
        window.addEventListener("DOMContentLoaded", start);
    } else {
        start();
    }
})();
</script>
"""

EXAMPLES = [
    "Thời gian quay tự do tối thiểu của píttông áp kế là bao lâu?",
    "Công thức hiệu chỉnh nhiệt độ cho thời gian quay tự do?",
    "Sai số cho phép khi kiểm tra van an toàn là bao nhiêu?",
    "Điều kiện môi trường khi tiến hành kiểm định áp suất?",
    "Thiết bị chuẩn cần thiết để kiểm định đồng hồ áp suất?",
    "Số lần đo tối thiểu khi kiểm tra đồng hồ áp suất?",
]


# ── UI ────────────────────────────────────────────────────────────────────────


def build_ui() -> gr.Blocks:
    with gr.Blocks(title="QTKĐ Chatbot") as demo:
        gr.Markdown(
            "# 📐 QTKĐ Chatbot — Tra cứu Quy trình Kiểm định\n"
            "Hỏi bằng tiếng Việt · Kết quả kèm trích dẫn nguồn + công thức LaTeX\n\n"
            "*Nguồn: QTKĐ 1.061 / 1.062 / 1.063 / 1.071 / 1.159 / 1.160 / 1.190*"
        )

        with gr.Row():
            # ── Left: chat (60%) ─────────────────────────────────────────
            with gr.Column(scale=6):
                chatbot = gr.Chatbot(
                    label="Chat",
                    show_label=False,  # nhãn nổi đè lên dòng chat đầu tiên khi cuộn
                    elem_id="qtkd-chat",
                    height=480,
                    latex_delimiters=LATEX_DELIMITERS,
                    placeholder=(
                        "Bắt đầu bằng cách nhập câu hỏi về quy trình kiểm định.\n\n"
                        "*Ví dụ: Sai số cho phép của áp kế cấp chính xác 0.6 là bao nhiêu?*"
                    ),
                )
                with gr.Row():
                    txt = gr.Textbox(
                        placeholder="Nhập câu hỏi về quy trình kiểm định…",
                        container=False,
                        scale=9,
                        autofocus=True,
                    )
                    btn = gr.Button("Gửi ➤", variant="primary", scale=1, min_width=90)
                clear_btn = gr.Button("🗑 Xóa lịch sử", size="sm", variant="secondary")

            # ── Right: document viewer (40%) ─────────────────────────────
            with gr.Column(scale=4):
                doc_viewer = gr.HTML(value=_EMPTY_VIEWER, label="")

        # ── Examples below the main row ───────────────────────────────────
        gr.Examples(examples=EXAMPLES, inputs=txt, label="Câu hỏi mẫu")

        # ── Events ───────────────────────────────────────────────────────
        txt.submit(user_fn, [txt, chatbot], [txt, chatbot], queue=False).then(
            bot_fn, [chatbot], [chatbot, doc_viewer]
        )

        btn.click(user_fn, [txt, chatbot], [txt, chatbot], queue=False).then(
            bot_fn, [chatbot], [chatbot, doc_viewer]
        )

        clear_btn.click(clear_all, outputs=[chatbot, doc_viewer], queue=False)

    return demo


if __name__ == "__main__":
    from core.startup import startup

    startup()
    gr.set_static_paths(paths=[KATEX_DIR])
    app = build_ui()
    app.queue()
    app.launch(
        server_name="0.0.0.0",
        server_port=7861,
        share=False,
        show_error=True,
        theme=gr.themes.Soft(primary_hue="blue", secondary_hue="slate"),
        css=CSS,
        head=katex_head(),
    )
