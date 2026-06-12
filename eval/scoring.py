"""Chấm chất lượng câu trả lời QTKĐ — TẤT ĐỊNH, thuần, KHÔNG network, KHÔNG LLM-judge.

Vì hệ chạy offline + domain đo lường (số liệu/công thức phải chính xác), ta chấm bằng
"key-fact coverage": mỗi câu hỏi khai báo các fact bắt buộc (số, đơn vị, mã, công thức,
thuật ngữ) cùng các biến thể (aliases); câu trả lời đạt nếu chứa fact sau khi chuẩn hoá
khoan dung tiếng Việt + đo lường. Ngoài ra kiểm:
  - citation_correctness: fact có nằm trong passage ĐÃ retrieve không, và [n] có được dẫn;
  - is_refusal: câu ngoài-phạm-vi phải từ chối đúng câu mẫu;
  - hallucination_flags: số-kèm-đơn-vị nêu trong câu trả lời nhưng không có trong ngữ cảnh.

Module này được unit-test dưới guard chặn mạng → tuyệt đối không import gì chạm mạng.
"""
from __future__ import annotations

import re
import unicodedata

# ── Hằng số ───────────────────────────────────────────────────────────────────

# Câu từ chối chuẩn (phải khớp byte-for-byte với SYSTEM_TMPL trong generation.py).
REFUSAL_CORE = "không tìm thấy thông tin"

_NBSP = "    "  # các loại space "dính"

# Đơn vị đo lường (dài/đặc thù xếp trước để alternation không khớp nhầm phần đầu).
_UNIT_ALT = (
    r"%rh|%|°c|°|oc|mbar|mpa|kpa|hpa|bar|pa|mm|cst|kg|"
    r"phút|tháng|lần|s|h|min|r/min"
)

# Số (có thể kèm ±, dấu thập phân, nhóm nghìn) đi liền một đơn vị → "claim đo lường".
NUMBER_UNIT_RE = re.compile(
    r"[±+\-]?\d[\d.,]*(?:\s\d{3})*\s*(?:" + _UNIT_ALT + r")",
    re.IGNORECASE,
)


# ── Chuẩn hoá ─────────────────────────────────────────────────────────────────

def normalize_text(s: str) -> str:
    """NFC → bỏ NBSP → lower → ',' giữa số thành '.' → bỏ space nhóm nghìn → dính
    số với đơn vị → gọn khoảng trắng. Idempotent. Dùng cho fact type code/term và
    cho so khớp chung."""
    if not s:
        return ""
    t = unicodedata.normalize("NFC", s)
    for ch in _NBSP:
        t = t.replace(ch, " ")
    t = t.lower()
    # Chính tả đơn vị tương đương trong corpus: docx ghi "oC" (chữ o thượng tiêu
    # bị phẳng hoá), model hay viết "°C"; "min" (tiêu đề bảng) ≡ "phút". Không
    # gộp thì câu trả lời đúng-nguyên-văn bị chấm sai (đo Q108: '2 °C' bị cờ ảo
    # giác dù nguồn ghi '2 oC/h'; gold Q113/Q121 tự bị cờ '2 phút').
    t = t.replace("°c", "oc")
    t = re.sub(r"\bmin\b", "phút", t)
    # "0,15" → "0.15" (chỉ dấu phẩy GIỮA hai chữ số)
    t = re.sub(r"(?<=\d),(?=\d)", ".", t)
    # "1 400" → "1400" (gộp nhóm 3 chữ số)
    t = re.sub(r"(?<=\d)\s+(?=\d{3}\b)", "", t)
    # "40 bar" → "40bar", "3 %" → "3%"
    t = re.sub(r"(?<=\d)\s+(?=(?:" + _UNIT_ALT + r"))", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def normalize_number(s: str) -> str:
    """Dạng chuẩn cứng cho fact number/unit: normalize_text + bỏ HẾT space + bỏ '±'
    đầu chuỗi → '± 3 %' / '3%' / '3 %' đều về '3%'. Giữ token đơn vị."""
    t = normalize_text(s)
    t = re.sub(r"\s+", "", t)
    t = t.lstrip("±+-")  # bỏ dấu ±/+/- đầu chuỗi → khoan dung dấu
    return t


def normalize_latex(s: str) -> str:
    """Dạng chuẩn cho fact formula: bỏ $...$, bỏ HẾT whitespace, bỏ mọi { } →
    '\\Delta P_{cd}' và '\\DeltaP_{cd}' và '\\DeltaP_cd' về cùng một chuỗi. Giữ
    phân biệt hoa/thường (LaTeX nhạy case)."""
    if not s:
        return ""
    t = s.strip()
    # bỏ $$...$$ hoặc $...$ bao ngoài
    t = t.strip("$").strip()
    t = re.sub(r"\s+", "", t)
    t = t.replace("{", "").replace("}", "")
    return t


# ── Khớp một fact ─────────────────────────────────────────────────────────────

def _candidates(fact: dict) -> list[str]:
    cands = [fact.get("text", "")] + list(fact.get("aliases", []) or [])
    return [c for c in cands if c]


def fact_present(fact: dict, answer: str) -> bool:
    """True nếu text HOẶC alias của fact xuất hiện trong answer (substring) sau khi
    chuẩn hoá theo type: number/unit→normalize_number, formula→normalize_latex,
    code/term→normalize_text."""
    ftype = fact.get("type", "term")
    cands = _candidates(fact)
    if not cands:
        return False
    if ftype in ("number", "unit"):
        na = normalize_number(answer)
        return any(normalize_number(c) in na for c in cands)
    if ftype == "formula":
        na = normalize_latex(answer)
        return any(normalize_latex(c) in na for c in cands)
    na = normalize_text(answer)
    return any(normalize_text(c) in na for c in cands)


def fact_coverage(required_facts: list[dict], answer: str) -> tuple[float, list[bool]]:
    """(tỉ lệ fact xuất hiện, list bool theo từng fact). Rỗng → (1.0, [])."""
    if not required_facts:
        return 1.0, []
    flags = [fact_present(f, answer) for f in required_facts]
    return sum(flags) / len(flags), flags


# ── Khớp nguồn (mirror eval.run_eval._matches) ────────────────────────────────

def _source_retrieved(file_stem: str, section_path: str, src: dict) -> bool:
    """Section của hit có khớp 'source' của fact: cùng file_stem VÀ section_path là
    chính nó hoặc con của nó (prefix). Giữ chung định nghĩa với run_eval._matches."""
    if file_stem != src.get("file_stem"):
        return False
    exp = src.get("section_path", "")
    return section_path == exp or section_path.startswith(exp)


def _passages(retrieved: list[dict]) -> list[tuple[int, str, str, str]]:
    """(số thứ tự 1-based, file_stem, section_path, text mà LLM thực sự thấy)."""
    out: list[tuple[int, str, str, str]] = []
    for i, h in enumerate(retrieved, 1):
        p = h.get("payload", {})
        pp = h.get("parent_payload")
        text = (pp or {}).get("text") or p.get("text", "")
        out.append((i, p.get("file_stem", ""), p.get("section_path", ""), text))
    return out


def citation_correctness(required_facts: list[dict], answer: str, retrieved: list[dict]) -> dict:
    """Với mỗi fact ĐÃ xuất hiện trong answer + có 'source': kiểm fact có thực sự
    nằm trong một passage đã retrieve (lenient) và [n] của passage đó có được dẫn
    (strict). Trả accuracy_lenient/strict, số grounded, và list fact chưa grounded."""
    passages = _passages(retrieved)
    cited = {int(n) for n in re.findall(r"\[(\d+)\]", answer)}

    checkable = [f for f in required_facts if fact_present(f, answer) and f.get("source")]
    if not checkable:
        return {
            "present_with_source": 0,
            "grounded_lenient": 0,
            "grounded_strict": 0,
            "accuracy_lenient": 1.0,
            "accuracy_strict": 1.0,
            "ungrounded": [],
        }

    g_lenient = g_strict = 0
    ungrounded: list[str] = []
    for f in checkable:
        src = f["source"]
        hit_idxs = {i for (i, fs, sp, _t) in passages if _source_retrieved(fs, sp, src)}
        # fact phải nằm trong text của passage đã retrieve khớp source
        in_passage = [i for (i, _fs, _sp, t) in passages if i in hit_idxs and fact_present(f, t)]
        if in_passage:
            g_lenient += 1
            if any(i in cited for i in in_passage):
                g_strict += 1
            else:
                ungrounded.append(f"{f.get('text')} (không dẫn [n])")
        else:
            ungrounded.append(f"{f.get('text')} (không có trong nguồn đã retrieve)")

    n = len(checkable)
    return {
        "present_with_source": n,
        "grounded_lenient": g_lenient,
        "grounded_strict": g_strict,
        "accuracy_lenient": g_lenient / n,
        "accuracy_strict": g_strict / n,
        "ungrounded": ungrounded,
    }


# ── Từ chối + ảo giác ─────────────────────────────────────────────────────────

def is_refusal(answer: str) -> bool:
    """True nếu câu trả lời chứa lõi câu từ chối chuẩn."""
    return normalize_text(REFUSAL_CORE) in normalize_text(answer)


def _grounded_as_table_cell(token_norm: str, raw_context: str) -> bool:
    """Số trong bảng Markdown đứng RIÊNG trong ô ('| 2 |'), đơn vị nằm ở TIÊU ĐỀ
    cột ('…, min') — phép dán số-liền-đơn-vị không bao giờ khớp được. Gold tự bị
    cờ ('2 phút' của Q113/Q121) ⇒ đây là lỗi thước đo. Chỉ chấp nhận khi phần số
    của claim xuất hiện như MỘT Ô BẢNG trọn vẹn (giữ precision với số trong văn
    xuôi)."""
    m = re.match(r"[\d.,]+", token_norm)
    if not m:
        return False
    num = m.group(0)
    for variant in {num, num.replace(".", ",")}:
        if re.search(rf"\|\s*{re.escape(variant)}\s*\|", raw_context):
            return True
    return False


def hallucination_flags(required_facts: list[dict], answer: str, retrieved: list[dict]) -> dict:
    """Heuristic thận trọng (ưu tiên precision): tách các 'claim đo lường' (số kèm
    đơn vị) trong answer; cái nào KHÔNG có trong toàn bộ ngữ cảnh đã retrieve → cờ
    'số bịa' — lớp ảo giác nguy hiểm nhất cho bot tra cứu."""
    context = " ".join(t for (_i, _fs, _sp, t) in _passages(retrieved))
    ctx_norm = normalize_number(context)
    # bỏ marker trích dẫn [1],[2] để khỏi bắt nhầm chỉ số nguồn là "số".
    clean = re.sub(r"\[\d+\]", " ", answer)
    flagged: list[str] = []
    for m in NUMBER_UNIT_RE.finditer(clean):
        token = m.group(0)
        tnorm = normalize_number(token)
        if tnorm and tnorm not in ctx_norm and not _grounded_as_table_cell(tnorm, context):
            flagged.append(token.strip())
    return {"count": len(flagged), "flagged": flagged}


# ── Gộp một câu ───────────────────────────────────────────────────────────────

def score_question(item: dict, answer: str, retrieved: list[dict]) -> dict:
    """Gộp toàn bộ chấm cho một câu eval thành một record. out_of_scope: coverage=None
    (không tính), thứ đáng giá là refusal_correct + hallucination phải 0."""
    cat = item.get("category", "lookup")
    must_refuse = bool(item.get("must_refuse", False)) or cat == "out_of_scope"
    rf = item.get("required_facts", []) or []

    refused = is_refusal(answer)
    cov, flags = fact_coverage(rf, answer)
    cite = citation_correctness(rf, answer, retrieved)
    hall = hallucination_flags(rf, answer, retrieved)

    return {
        "id": item.get("id"),
        "category": cat,
        "difficulty": item.get("difficulty"),
        "coverage": None if must_refuse else cov,
        "facts_present": flags,
        "n_facts": len(rf),
        "citation": cite,
        "refused": refused,
        "expected_refusal": must_refuse,
        "refusal_correct": refused == must_refuse,
        "hallucination": hall,
    }
