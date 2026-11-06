"""Hội thoại nhiều lượt: viết lại câu hỏi tiếp theo thành câu độc lập trước khi truy hồi.

Truy hồi chỉ nhìn một câu, nên "Còn áp suất khí quyển?" hay "Đổi sang DPI 610 thì sao?" mất
thiết bị/chủ đề đang nói tới và kéo nguồn của tài liệu khác (đo: 4/8 ca nhiều lượt sai, câu
trả lời lấy số của QTKĐ 1.061 cho bàn tạo áp). Một lần gọi model nhỏ, nhiệt độ 0, chỉ khi
đã có lịch sử; mọi nghi ngờ (lỗi, rỗng, quá dài, thêm số lạ) thì giữ nguyên câu gốc.
"""

from __future__ import annotations

import logging
import re

from core.settings_loader import get_settings
from llm import generator

logger = logging.getLogger(__name__)

_SYSTEM = (
    "Bạn viết lại câu hỏi tra cứu quy trình kiểm định. Cho lịch sử hội thoại và CÂU HỎI CUỐI, "
    "hãy viết lại câu hỏi cuối thành MỘT câu hỏi đầy đủ, tự đứng được, tiếng Việt: thêm tên thiết bị, "
    "mã QTKĐ hoặc chủ đề từ lịch sử nếu câu cuối thiếu; nếu câu cuối đổi sang thiết bị/chủ đề khác "
    "thì theo câu cuối và chỉ lấy từ lịch sử phần chủ đề còn thiếu. Giữ nguyên mọi số, đơn vị, mã, "
    "ký hiệu của câu cuối; không trả lời, không thêm thông tin mới. Chỉ in ra câu hỏi đã viết lại."
)
_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


def standalone_query(message: str, prior: list[list[str]]) -> str:
    """Câu hỏi độc lập cho truy hồi; ``prior`` là [[user, assistant], ...]. Lỗi/nghi ngờ -> ``message``."""
    cfg = get_settings().llm.rewrite
    if not cfg.enabled or not prior:
        return message
    turns = prior[-cfg.max_history_turns :]
    lines: list[str] = []
    for user, bot in turns:
        lines.append(f"Người dùng: {user}")
        clean = (bot or "").split("\n\n---\n\n")[0].strip().replace("\n", " ")
        lines.append(f"Trợ lý: {clean[: cfg.answer_chars]}")
    prompt = "Lịch sử:\n" + "\n".join(lines) + f"\n\nCÂU HỎI CUỐI: {message}\n\nCâu hỏi viết lại:"
    try:
        out = generator.chat_once(
            [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": prompt}],
            num_predict=cfg.num_predict,
            timeout_s=cfg.timeout_s,
        )
    except Exception as exc:  # noqa: BLE001 - viết lại chỉ là tối ưu, lỗi thì dùng câu gốc
        logger.warning("Không viết lại được câu hỏi tiếp theo: %s", exc)
        return message
    rewritten = out.strip().splitlines()[0].strip().strip('"“”') if out.strip() else ""
    rewritten = re.sub(r"^(câu hỏi (viết lại|độc lập)\s*:\s*)", "", rewritten, flags=re.IGNORECASE)
    if not rewritten or len(rewritten) > cfg.max_query_chars:
        return message
    allowed = {n.replace(",", ".") for n in _NUMBER.findall(message + " " + " ".join(u for u, _ in turns))}
    if any(n.replace(",", ".") not in allowed for n in _NUMBER.findall(rewritten)):
        return message
    return rewritten
