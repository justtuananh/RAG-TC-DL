"""Guard ngôn ngữ: loại chữ Hán/CJK khỏi câu trả lời, tất định, không phụ thuộc model.

Qwen đôi khi lẫn CJK vào câu trả lời tiếng Việt. Đo trên bộ 52 câu QTKĐ có hai dạng:
  A. Đuôi dịch: model dịch lại cả câu sang tiếng Trung ("... ứng với范例翻译：根据...。[1]").
  B. Thế từ: ký tự Hán chen giữa từ ("đơn位帕斯卡").
Tài liệu nguồn là tiếng Việt nên không có CJK hợp lệ trong câu trả lời.

``strip_cjk``: lọc văn bản cuối (dạng A cắt đuôi, giữ trích dẫn không lặp; dạng B xoá cụm
Hán và bật ``needs_regen`` vì xoá không khôi phục được từ bị thay). Nếu cả câu là chữ Hán
(người dùng yêu cầu trả lời tiếng Trung) thì ``empty=True``: dùng ``LANGUAGE_FALLBACK``.
``CjkStreamGuard``: lọc ngay trong luồng SSE để người dùng không thấy chữ Hán nhấp nháy;
khi phát hiện đuôi dịch thì ngừng phát và (khi đã thấy trích dẫn) báo ngắt luồng Ollama.
"""

from __future__ import annotations

import re
from typing import NamedTuple

_CJK_RANGES = (
    "⺀-鿿㐀-䶿가-힯豈-﫿＀-￯　-〿"
)
CJK_CHAR = re.compile(f"[{_CJK_RANGES}]")
CJK_RUN = re.compile(f"[{_CJK_RANGES}]+")

# Dấu câu toàn chiều rộng -> ASCII. KHÔNG đụng “ ” ‘ ’ (tiếng Việt dùng hợp lệ).
_FULLWIDTH = str.maketrans(
    {"。": ".", "，": ",", "：": ":", "；": ";", "（": "(", "）": ")", "！": "!", "？": "?", "、": ","}
)

_VI_DIACRITIC = re.compile(
    r"[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]", re.I
)
_CITE_TAIL = re.compile(r"((?:\s*\[\d+(?:\s*[,\-–]\s*\d+)*\])+)\s*$")
_CITES = re.compile(r"\[\d+(?:\s*[,\-–]\s*\d+)*\]")
_LATIN_LETTER = re.compile(r"[A-Za-zÀ-ỹ]")
_DANGLING = re.compile(
    r"(?:[,;:\-–(]|\b(?:ứng với|tức là|nghĩa là|dịch là|bản dịch|translation|tiếng trung|trung văn))\s*$",
    re.I,
)

LANGUAGE_FALLBACK = "Hệ thống chỉ trả lời bằng tiếng Việt. Vui lòng đặt câu hỏi bằng tiếng Việt."
_MIN_LATIN_LETTERS = 8  # dưới ngưỡng này sau khi lọc = câu trả lời gần như toàn chữ Hán

# Đuôi dịch thật: nhiều chữ Hán, chiếm tỉ lệ lớn của đuôi, không còn chữ Việt có dấu.
# Ngưỡng thấp hơn ở bước lọc cuối; cao hơn ở bước quyết định ngắt luồng sớm.
MIN_TAIL_CJK = 6
MIN_TAIL_CJK_ABORT = 10
MIN_TAIL_CJK_RATIO = 0.4
MAX_TAIL_CJK = 120  # chữ Hán chạy lan quá mức: ngắt luồng dù chưa thấy trích dẫn
POST_CJK_CHARS_TO_STOP = 24


class Stripped(NamedTuple):
    text: str
    needs_regen: bool  # dạng B: từ bị thay đã mất, nên sinh lại nếu có thể
    fixed: bool  # có thay đổi so với đầu vào
    empty: bool = False  # lọc xong không còn nội dung (cả câu là chữ Hán): dùng LANGUAGE_FALLBACK


def to_ascii_punct(text: str) -> str:
    return text.translate(_FULLWIDTH)


def _is_empty(text: str) -> bool:
    return len(_LATIN_LETTER.findall(_CITES.sub("", text))) < _MIN_LATIN_LETTERS


def _looks_like_translation(tail_body: str, min_cjk: int) -> bool:
    n_cjk = len(CJK_CHAR.findall(tail_body))
    n_all = len(re.sub(r"\s", "", tail_body)) or 1
    return (
        n_cjk >= min_cjk
        and n_cjk / n_all >= MIN_TAIL_CJK_RATIO
        and not _VI_DIACRITIC.search(tail_body)
    )


def strip_cjk(text: str) -> Stripped:
    if not CJK_CHAR.search(text):
        return Stripped(text, False, False)
    text = to_ascii_punct(text)
    first = CJK_CHAR.search(text)
    if first is None:  # chỉ có dấu câu toàn chiều rộng
        return Stripped(text, False, True)
    head, tail = text[: first.start()], text[first.start() :]
    cite = _CITE_TAIL.search(tail)
    tail_body = tail[: cite.start()] if cite else tail
    if _looks_like_translation(tail_body, MIN_TAIL_CJK):
        head = head.rstrip()
        prev = None
        while prev != head:  # bỏ liên từ treo cuối câu ("ứng với", dấu phẩy...)
            prev = head
            head = _DANGLING.sub("", head).rstrip()
        if head and head[-1] not in ".!?:)]%":
            head += "."
        cite_txt = cite.group(1).strip() if cite else ""
        if _CITE_TAIL.search(head):  # phần đầu đã có trích dẫn: không lặp lại của đuôi dịch
            cite_txt = ""
        out = head + (" " + cite_txt if cite_txt else "")
        return Stripped(out, False, True, _is_empty(out))
    clean = re.sub(r"[ \t]{2,}", " ", CJK_RUN.sub("", text))
    return Stripped(clean, True, True, _is_empty(clean))


class CjkStreamGuard:
    """Lọc luồng delta. ``feed`` trả (văn bản được phát, có nên ngắt luồng nguồn).

    Delta không có CJK đi qua nguyên vẹn. Từ ký tự Hán đầu tiên, ngừng phát (chỉ phát
    phần trước ký tự đó); văn bản cuối do ``strip_cjk(guard.raw)`` quyết định và được
    gửi trong sự kiện ``done`` (frontend thay thế phần đã stream).
    """

    def __init__(self) -> None:
        self.raw = ""
        self._tail_start: int | None = None

    @property
    def held(self) -> bool:
        return self._tail_start is not None

    def feed(self, delta: str) -> tuple[str, bool]:
        delta = to_ascii_punct(delta)
        if self._tail_start is not None:
            self.raw += delta
            return "", self._should_stop()
        m = CJK_CHAR.search(delta)
        if m is None:
            self.raw += delta
            return delta, False
        self._tail_start = len(self.raw) + m.start()
        self.raw += delta
        return delta[: m.start()], self._should_stop()

    def _should_stop(self) -> bool:
        tail = self.raw[self._tail_start :]
        cite = _CITE_TAIL.search(tail)
        body = tail[: cite.start()] if cite else tail
        if len(CJK_CHAR.findall(body)) >= MAX_TAIL_CJK:
            return True
        if not _looks_like_translation(body, MIN_TAIL_CJK_ABORT):
            return False
        last_cjk_end = max(m.end() for m in CJK_RUN.finditer(tail))
        return bool(cite) or len(tail) - last_cjk_end >= POST_CJK_CHARS_TO_STOP
