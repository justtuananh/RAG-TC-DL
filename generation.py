"""Lớp sinh câu trả lời QTKĐ — tách khỏi UI (app.py) để eval tái dùng được.

Chứa toàn bộ logic LLM thuần (không Gradio): system prompt, dựng ngữ cảnh + trích
dẫn, dựng messages, và stream SSE từ Ollama. `app.py` import lại các hàm này cho UI;
`eval/answer_eval.py` import chúng để chạy đúng đường sinh của production mà không kéo
theo Gradio.

Services (local Docker):
  Ollama : POST http://localhost:11434/v1/chat/completions  (qwen2.5:1.5b dev / 7b prod)

Đổi model lúc chạy: set `generation.OLLAMA_MODEL = "..."` trước khi gọi stream_ollama
(stream_ollama đọc biến module này tại thời điểm gọi).
"""
from __future__ import annotations

import json
import os

import requests

# ── Config LLM ────────────────────────────────────────────────────────────────
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/v1/chat/completions")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b")
# Read-timeout tới token ĐẦU TIÊN: trên CPU, prompt-eval 4–5k token mất >120s khi
# model nguội → 120 gây "Read timed out" giả. GPU prod không bị ảnh hưởng (vài giây).
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "300"))
HISTORY_TURNS = 3

# Ngân sách ngữ cảnh: ĐO THỰC NGHIỆM (answer_eval) cho thấy nhồi ngữ cảnh lớn phản tác
# dụng — context ~18–20k ký tự CHÔN VÙI fact ("lost-in-the-middle") làm tụt coverage và
# đẩy Ollama tới 500 khi gần num_ctx. Nên CAP mỗi nguồn ở mức vừa phải và có trần tổng;
# nguồn ngắn nhường phần dư cho nguồn sau nhưng KHÔNG nguồn nào vượt MAX_BLOCK_CHARS.
NUM_CTX = 8192
# Chặn sinh chạy loạn (baseline từng có 1 câu out-of-scope sinh ~29 phút / 500+ token rác).
MAX_NEW_TOKENS = 1024
CHARS_PER_TOKEN = 3            # tiếng Việt ~3 ký tự/token (ước lượng thận trọng)
PROMPT_RESERVE_TOKENS = 1200   # system prompt + câu hỏi + chỗ cho câu trả lời
TOTAL_CONTEXT_CHARS = (NUM_CTX - PROMPT_RESERVE_TOKENS) * CHARS_PER_TOKEN  # ≈ 20 976 (trần an toàn)
MAX_BLOCK_CHARS = 2400         # cap mỗi nguồn — đủ chứa 1 section vừa, không chôn vùi fact
MIN_BLOCK_CHARS = 600          # sàn mỗi nguồn

SYSTEM_TMPL = """Bạn là trợ lý tra cứu quy trình kiểm định đo lường (QTKĐ) của Cục Tiêu chuẩn Đo lường Chất lượng Việt Nam.

NHIỆM VỤ: Trả lời câu hỏi DỰA HOÀN TOÀN vào NGỮ CẢNH bên dưới. Tuyệt đối không bịa thông tin ngoài ngữ cảnh, không suy đoán, không tự tính toán.

QUY TẮC:
1. Dẫn nguồn bằng ký hiệu [1], [2], ... NGAY SAU mỗi thông tin, ứng với số nguồn trong ngữ cảnh. Mỗi con số hoặc dữ kiện phải kèm ít nhất một trích dẫn [n]; trong danh sách gạch đầu dòng, MỖI dòng nêu số liệu phải có [n] của đúng nguồn chứa số liệu đó.
2. Trích NGUYÊN VĂN mọi con số, đơn vị, mã hiệu và công thức từ nguồn — không làm tròn, không đổi đơn vị, không viết lại, không tính toán. Công thức LaTeX: chép đúng dạng inline $...$ như trong nguồn, không thêm hay bớt ký hiệu (không tự chèn \\times), không đổi sang \\[...\\].
3. Nếu câu hỏi cần thông tin từ NHIỀU nguồn hoặc gồm nhiều phần, hãy tổng hợp đầy đủ và trả lời lần lượt từng phần, nêu rõ [n] cho từng ý — không bỏ sót phần nào. Khi câu hỏi hỏi giá trị cụ thể, NÊU RÕ giá trị (số + đơn vị) lấy từ nguồn, không chỉ tham chiếu số điều khoản.
4. Trả lời bằng tiếng Việt, ngắn gọn, chính xác, đúng trọng tâm câu hỏi.
5. Nếu KHÔNG nguồn nào chứa thông tin liên quan, hoặc câu hỏi nằm ngoài phạm vi tài liệu QTKĐ, hoặc câu hỏi yêu cầu tính toán: trả lời ĐÚNG MỘT CÂU "Không tìm thấy thông tin này trong các tài liệu QTKĐ được cung cấp." và DỪNG LẠI — tuyệt đối không viết thêm gì sau câu đó. Nếu nguồn chỉ chứa MỘT PHẦN thông tin được hỏi: trả lời phần tìm được (kèm [n]) và nêu rõ phần còn lại không có trong nguồn — KHÔNG từ chối toàn bộ.

NGỮ CẢNH:
{context}"""


# ── Builder ngữ cảnh + trích dẫn ──────────────────────────────────────────────

def build_context_and_citations(results: list[dict]) -> tuple[str, str]:
    """Dựng (context_str cho system prompt, citations_md cho UI) từ kết quả retrieve.

    Context dùng PARENT text (đủ ngữ cảnh) với NGÂN SÁCH ĐỘNG: mỗi nguồn được quota
    `TOTAL_CONTEXT_CHARS / số nguồn`; nguồn ngắn nhường phần dư cho nguồn sau; có sàn
    MIN_BLOCK_CHARS. Citations dùng snippet CHILD (cap 220). Đánh số [n] khớp 1:1 giữa
    hai phần và với results[n-1].
    """
    ctx_parts: list[str] = []
    cite_parts: list[str] = []

    n = len(results) or 1
    # Quota mỗi nguồn: chia đều theo trần tổng, nhưng KẸP trong [MIN, MAX].
    per_block = min(MAX_BLOCK_CHARS, max(MIN_BLOCK_CHARS, TOTAL_CONTEXT_CHARS // n))
    carried = 0  # phần quota dư từ các nguồn ngắn, nhường cho nguồn sau

    for i, r in enumerate(results, 1):
        p = r["payload"]
        pp = r.get("parent_payload")
        file_stem = p["file_stem"]
        section_path = p["section_path"]
        child_text = p["text"]

        ctx_text = pp["text"] if pp else child_text
        budget = min(MAX_BLOCK_CHARS, per_block + carried)  # không nguồn nào vượt cap
        if len(ctx_text) > budget:
            ctx_text = ctx_text[:budget] + "…"
            carried = 0
        else:
            carried = budget - len(ctx_text)

        ctx_parts.append(
            f"[{i}] Nguồn: {file_stem} — {section_path}\n---\n{ctx_text}"
        )

        snippet = child_text[:220].replace("\n", " ")
        if len(child_text) > 220:
            snippet += "…"
        cite_parts.append(
            f"**[{i}]** `{file_stem}` • {section_path}\n> {snippet}"
        )

    context_str = "\n\n---\n\n".join(ctx_parts)
    citations_md = (
        "\n\n---\n\n**📎 Nguồn tham khảo:**\n\n" + "\n\n".join(cite_parts)
    )
    return context_str, citations_md


def build_messages(query: str, context_str: str, prior: list[list]) -> list[dict]:
    """Dựng list messages: system (ngữ cảnh) + tối đa HISTORY_TURNS lượt cũ + query.

    Cắt block citations khỏi câu trả lời assistant cũ trước khi đưa vào lịch sử.
    """
    msgs: list[dict] = [
        {"role": "system", "content": SYSTEM_TMPL.format(context=context_str)}
    ]
    for turn in prior[-HISTORY_TURNS:]:
        user_msg, bot_msg = turn[0], turn[1]
        if user_msg:
            msgs.append({"role": "user", "content": user_msg})
        if bot_msg:
            clean = bot_msg.split("\n\n---\n\n")[0].strip()
            msgs.append({"role": "assistant", "content": clean})
    msgs.append({"role": "user", "content": query})
    return msgs


def _native_chat_url(url: str) -> str:
    """Map URL OpenAI-compat (.../v1/chat/completions) → Ollama native /api/chat.

    Giữ nguyên host từ env cũ (.env / docker-compose đặt OLLAMA_URL dạng /v1);
    URL đã là /api/chat thì giữ nguyên.
    """
    return url.replace("/v1/chat/completions", "/api/chat")


def stream_ollama(messages: list[dict]):
    """Stream từ Ollama NATIVE /api/chat (JSON lines), yield từng content delta.

    VÌ SAO không dùng /v1/chat/completions: endpoint OpenAI-compat BỎ QUA trường
    "options" → num_ctx=8192/num_predict=1024 chưa bao giờ tới server; model chạy
    ctx mặc định 4096 (xác nhận qua /api/ps trong lúc eval đang gửi 8192). Prompt
    ~4,3k token bị Ollama CẮT TỪ ĐẦU — mất system prompt + nguồn [1][2] → citation
    hỏng, fact đầu ngữ cảnh biến mất, 500 cận biên. /api/chat tôn trọng options
    per-request. Đọc OLLAMA_MODEL module-global tại thời điểm gọi.
    """
    resp = requests.post(
        _native_chat_url(OLLAMA_URL),
        json={
            "model": OLLAMA_MODEL,
            "messages": messages,
            "stream": True,
            # Giữ model trong RAM giữa các request — mặc định 5m hay bị evict giữa
            # phiên/lô dài; mỗi lần reload 7b dưới áp lực RAM là một cửa sổ dễ bị
            # OOM-kill → Ollama 500 (đo: 42 lần 500/4h, log 'signal: killed').
            "keep_alive": "30m",
            "options": {
                "num_ctx": NUM_CTX,
                "num_predict": MAX_NEW_TOKENS,
                "temperature": 0.1,
            },
        },
        stream=True,
        timeout=OLLAMA_TIMEOUT,
    )
    resp.raise_for_status()
    for line in resp.iter_lines():
        if not line:
            continue
        try:
            chunk = json.loads(line.decode("utf-8"))
        except json.JSONDecodeError:
            continue
        delta = (chunk.get("message") or {}).get("content", "")
        if delta:
            yield delta
        if chunk.get("done"):
            break
