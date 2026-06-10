"""QTKĐ RAG Chatbot — Gradio 4.x, KaTeX formulas + doc viewer with passage highlight.

Run:
  /path/to/kotaemon/.venv/bin/python app.py

Layout:
  Left  (60%): chat + input + examples
  Right (40%): source document viewer with highlighted retrieved passages

Services (all local Docker, already running):
  Embedding : localhost:8010   (bge-m3, 1024 dims)
  Reranker  : localhost:8011   (bge-reranker-v2-m3)
  Qdrant    : localhost:6333   collection: qtkd_rag
  Ollama    : localhost:11434  model: qwen2.5:1.5b
"""
from __future__ import annotations

import html as html_mod
import sys
from pathlib import Path

import gradio as gr
import markdown as _md

sys.path.insert(0, str(Path(__file__).parent))
from retrieval.retriever import retrieve
from generation import (
    build_context_and_citations as _build_context_and_citations,
    build_messages as _build_messages,
    enforce_refusal_stop as _enforce_refusal_stop,
    stream_ollama as _stream_ollama,
)


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
    _PANEL_OPEN
    + "<div class='doc-empty'>Kết quả tìm kiếm sẽ hiển thị ở đây.</div>"
    + _PANEL_CLOSE
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

        score_color = (
            "#16a34a" if score > 0.3 else "#d97706" if score > 0.1 else "#6b7280"
        )

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

def user_fn(user_message: str, history: list) -> tuple[str, list]:
    return "", history + [[user_message, None]]


def bot_fn(history: list):
    """Generator → yields (chatbot_history, doc_viewer_html)."""
    if not history or history[-1][0] is None:
        yield history, gr.update()
        return

    query = history[-1][0]
    prior = history[:-1]

    # 1. Embedding + BM25 + RRF + rerank (hybrid pipeline)
    history[-1][1] = "*⏳ Đang nhúng câu hỏi (embedding)…*"
    yield history, gr.update()

    history[-1][1] = "*🔍 Đang tìm kiếm trong tài liệu QTKĐ (hybrid)…*"
    yield history, gr.update()
    try:
        results = retrieve(query, top_k=20, top_n=5)
    except Exception as e:
        history[-1][1] = f"❌ Lỗi tìm kiếm: {e}"
        yield history, gr.update()
        return

    if not results:
        history[-1][1] = "Không tìm thấy thông tin liên quan trong tài liệu QTKĐ."
        yield history, build_doc_viewer_html([])
        return

    # Build doc viewer HTML immediately (show sources while LLM streams)
    doc_html = build_doc_viewer_html(results)
    context_str, citations_md = _build_context_and_citations(results)
    messages = _build_messages(query, context_str, prior)

    history[-1][1] = "*💭 Đang tổng hợp câu trả lời…*"
    yield history, doc_html  # ← sources appear here

    # 3. Stream LLM
    partial = ""
    try:
        for delta in _stream_ollama(messages):
            partial += delta
            history[-1][1] = partial
            yield history, gr.update()
    except Exception as e:
        history[-1][1] = (partial or "") + f"\n\n❌ Lỗi LLM: {e}"
        yield history, gr.update()
        return

    # 4. Cắt phần "tính tiếp" sau câu từ chối chuẩn (nếu có) rồi gắn citations
    partial = _enforce_refusal_stop(partial)
    history[-1][1] = partial + citations_md
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
"""

LATEX_DELIMITERS = [
    {"left": "$$", "right": "$$", "display": True},
    {"left": "$", "right": "$", "display": False},
]

# MutationObserver: re-run KaTeX auto-render whenever .qtkd-viewer content changes
_JS_KATEX_OBSERVER = """
() => {
    function renderViewer() {
        const el = document.querySelector('.qtkd-viewer');
        if (el && window.renderMathInElement) {
            window.renderMathInElement(el, {
                delimiters: [
                    {left: '$$', right: '$$', display: true},
                    {left: '$',  right: '$',  display: false}
                ],
                throwOnError: false,
                ignoredTags: ['script','noscript','style','textarea','code']
            });
        }
    }
    new MutationObserver(renderViewer)
        .observe(document.body, {childList: true, subtree: true});
}
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
    with gr.Blocks(
        title="QTKĐ Chatbot",
        css=CSS,
        js=_JS_KATEX_OBSERVER,
        theme=gr.themes.Soft(primary_hue="blue", secondary_hue="slate"),
    ) as demo:

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
                    elem_id="qtkd-chat",
                    height=480,
                    show_copy_button=True,
                    bubble_full_width=False,
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
                clear_btn = gr.Button(
                    "🗑 Xóa lịch sử", size="sm", variant="secondary"
                )

            # ── Right: document viewer (40%) ─────────────────────────────
            with gr.Column(scale=4):
                doc_viewer = gr.HTML(value=_EMPTY_VIEWER, label="")

        # ── Examples below the main row ───────────────────────────────────
        gr.Examples(examples=EXAMPLES, inputs=txt, label="Câu hỏi mẫu")

        # ── Events ───────────────────────────────────────────────────────
        txt.submit(
            user_fn, [txt, chatbot], [txt, chatbot], queue=False
        ).then(bot_fn, [chatbot], [chatbot, doc_viewer])

        btn.click(
            user_fn, [txt, chatbot], [txt, chatbot], queue=False
        ).then(bot_fn, [chatbot], [chatbot, doc_viewer])

        clear_btn.click(clear_all, outputs=[chatbot, doc_viewer], queue=False)

    return demo


if __name__ == "__main__":
    app = build_ui()
    app.queue()
    app.launch(
        server_name="0.0.0.0",
        server_port=7861,
        share=False,
        show_error=True,
    )
