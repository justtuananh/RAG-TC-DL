"""Tính trong chat bằng công thức ĐÃ DUYỆT (``formula_registry``).

Chat không tự tính: model 7B tính nhẩm sai và không kiểm đơn vị. Ở đây phép tính luôn do bộ tính
Decimal ``formula_lab.engine`` thực hiện trên công thức mà người duyệt đã phê duyệt đúng phiên bản
hiện tại; công thức nháp không bao giờ được dùng. Model chỉ làm một việc hẹp: đọc số liệu có sẵn
trong câu hỏi (JSON), và mỗi số trích ra phải xuất hiện NGUYÊN VĂN trong câu hỏi.

Kết quả của ``try_calc``:
- ``None``: không phải yêu cầu tính, hoặc chưa có công thức đã duyệt khớp -> luồng chat như cũ.
- ``ask``: khớp công thức nhưng thiếu số liệu -> hỏi lại đúng đại lượng còn thiếu.
- ``invalid``: bộ tính từ chối (đơn vị không tương thích, ngoài miền giá trị) -> nêu lý do.
- ``answer``: đã tính -> khối "KẾT QUẢ TÍNH" đưa vào ngữ cảnh để model diễn đạt và so với giới hạn.
Điều kiện áp dụng của công thức được nêu trong kết quả để người dùng tự đối chiếu.
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal

from core.settings_loader import get_settings
from formula_lab.engine import UNITS, Invalid
from formula_registry.store import Registry
from llm import generator

logger = logging.getLogger(__name__)

_UNIT_ALIASES = {"phút": "min", "giây": "s", "giờ": "h"}
_UNITS_BY_LOWER = {k.lower(): k for k in UNITS} | {k: v for k, v in _UNIT_ALIASES.items() if v in UNITS}
_UNIT_ALT = "|".join(re.escape(u) for u in sorted(_UNITS_BY_LOWER, key=len, reverse=True))
_QTY = re.compile(rf"(?<![\w.,])(\d+(?:[.,]\d+)?)\s*({_UNIT_ALT})(?![A-Za-zÀ-ỹ/])", re.IGNORECASE)
_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
# Từ chức năng tiếng Việt: không dùng để khớp tên đại lượng.
_STOP = frozenset(
    "la cua va hay hoac co khong duoc bi bao nhieu gi nao the nhu sao nhung cac mot nay do khi thi "
    "ma de trong theo voi cho tu den ve can phai bang tai o neu rat hoi toi ban tinh cua".split()
)


@dataclass
class CalcOutcome:
    kind: str  # "answer" | "ask" | "invalid"
    text: str = ""  # trả lời tất định cho ask / invalid
    block: str = ""  # khối KẾT QUẢ TÍNH cho ngữ cảnh LLM (answer)
    summary: str = ""  # cùng nội dung không kèm dòng hướng dẫn: câu trả lời tất định khi model diễn đạt sai số
    results: list[dict] = field(default_factory=list)


def _fold(text: str) -> str:
    t = unicodedata.normalize("NFD", text.lower().replace("đ", "d"))
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", _fold(text)) if len(t) >= 2 and t not in _STOP}


def _norm_unit(raw: object) -> str | None:
    if not isinstance(raw, str):
        return None
    u = raw.strip()
    return _UNITS_BY_LOWER.get(u.lower()) if u else None


def _fmt(d: Decimal) -> str:
    """Số kiểu Việt (dấu phẩy thập phân), tối đa 6 chữ số thập phân, không dạng mũ."""
    if d == d.to_integral_value():
        return format(d.to_integral_value(), "f")
    q = Decimal(10) ** (-6 if abs(d) >= 1 else -8)
    return format(d.quantize(q), "f").rstrip("0").rstrip(".").replace(".", ",")


def _rank(message: str, formulas: list[dict], cfg) -> list[dict]:
    """Công thức đã duyệt mà câu hỏi nhắc tới các biến của nó (nhãn hoặc ký hiệu)."""
    msg = _tokens(message)
    scored = []
    for f in formulas:
        p = f["proposal"]
        variables = p.get("variables") or []
        if not variables:
            continue
        per_var = []
        for v in variables:
            label = _tokens(v.get("label", ""))
            hit = len(label & msg) / len(label) if label else 0.0
            key = _fold(v.get("key", "")).replace("_", "")
            if len(key) >= 2 and key in msg:
                hit = 1.0
            per_var.append(hit)
        coverage = sum(per_var) / len(per_var)
        title = _tokens(p.get("title", ""))
        title_hit = len(title & msg) / len(title) if title else 0.0
        if coverage >= cfg.min_variable_coverage:
            scored.append((coverage, title_hit, len(variables), f))
    scored.sort(key=lambda x: (x[0], x[1], x[2]), reverse=True)
    return [f for *_, f in scored[: cfg.max_formulas]]


def _extract(message: str, cands: list[dict], cfg) -> dict[str, dict[str, tuple[str, str]]]:
    """{id công thức: {biến: (số, đơn vị chuẩn)}} từ số liệu NGUYÊN VĂN trong câu hỏi."""
    lines = []
    for n, f in enumerate(cands, 1):
        p = f["proposal"]
        vs = "; ".join(f'{v["key"]} = "{v.get("label", "")}" (đơn vị {v["unit"]})' for v in p["variables"])
        lines.append(f'F{n} — {p["title"]}: {vs}')
    prompt = (
        f"Câu hỏi: {message}\n\nCông thức:\n" + "\n".join(lines) + "\n\n"
        'Trả về JSON dạng {"F1": {"<biến>": {"value": "<số>", "unit": "<đơn vị>"}}}. Mỗi biến: lấy số và đơn vị '
        "NGUYÊN VĂN trong câu hỏi cho đúng đại lượng đó; không suy đoán, không tính; không có thì null."
    )
    raw = generator.chat_once(
        [
            {"role": "system", "content": "Bạn chỉ trích số liệu có sẵn trong câu hỏi và trả về JSON hợp lệ."},
            {"role": "user", "content": prompt},
        ],
        num_predict=cfg.num_predict,
        timeout_s=cfg.timeout_s,
        json_mode=True,
    )
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    msg_numbers = {n.replace(",", ".") for n in _NUMBER.findall(message)}
    out: dict[str, dict[str, tuple[str, str]]] = {}
    for n, f in enumerate(cands, 1):
        got = data.get(f"F{n}") if isinstance(data, dict) else None
        if not isinstance(got, dict):
            continue
        keep: dict[str, tuple[str, str]] = {}
        for v in f["proposal"]["variables"]:
            e = got.get(v["key"])
            if not isinstance(e, dict):
                continue
            value = str(e.get("value", "")).strip().replace(",", ".")
            unit = _norm_unit(e.get("unit")) or (v["unit"] if v["unit"] == "1" else None)
            if value in msg_numbers and unit:
                keep[v["key"]] = (value, unit)
        out[f["id"]] = keep
    return out


def _constraint(v: dict) -> str:
    lo, hi = v.get("min"), v.get("max")
    parts = []
    if lo is not None:
        parts.append(("> " if v.get("exclusive_min") else "≥ ") + str(lo))
    if hi is not None:
        parts.append(("< " if v.get("exclusive_max") else "≤ ") + str(hi))
    return f" (miền cho phép: {', '.join(parts)} {v['unit']})" if parts else ""


def _explain(err: Invalid, f: dict, inputs: dict) -> str:
    msg = str(err)
    for v in f["proposal"]["variables"]:
        if msg.endswith(": " + v["key"]):
            return f"{msg.split(':')[0]} đối với «{v.get('label', v['key'])}»{_constraint(v)}"
    return msg


def _alt_units(value: Decimal, unit: str) -> str:
    cat = UNITS.get(unit, ("",))[0]
    if cat != "pressure":
        return ""
    base = value * Decimal(UNITS[unit][1])
    alts = [f"{_fmt(base / Decimal(UNITS[u][1]))} {u}" for u in ("bar", "MPa") if u != unit]
    return " (= " + " = ".join(alts) + ")"


def try_calc(message: str, *, registry: Registry | None = None) -> CalcOutcome | None:
    cfg = get_settings().calc
    if not cfg.enabled or not re.search(cfg.intent_pattern, message, re.IGNORECASE):
        return None
    if not _QTY.search(message):
        return None
    try:
        formulas = (registry or Registry()).approved()
    except Exception as exc:  # noqa: BLE001 - không đọc được kho công thức thì chat như cũ
        logger.warning("Không đọc được kho công thức: %s", exc)
        return None
    cands = _rank(message, formulas, cfg) if formulas else []
    if not cands:
        return None
    try:
        extracted = _extract(message, cands, cfg)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Không trích được số liệu để tính: %s", exc)
        return None

    reg = registry or Registry()
    done: list[dict] = []
    errors: list[str] = []
    partial: tuple[int, dict, list[dict]] | None = None
    for f in cands:
        p = f["proposal"]
        got = extracted.get(f["id"], {})
        missing = [v for v in p["variables"] if v["key"] not in got]
        if missing:
            if got and (partial is None or len(got) > partial[0]):
                partial = (len(got), f, missing)
            continue
        inputs = {k: {"value": val, "unit": unit} for k, (val, unit) in got.items()}
        try:
            res = reg.compute(f["id"], f["revision"], inputs, {c["key"]: True for c in p["conditions"]})
        except Invalid as exc:
            errors.append(f"«{p['title']}»: {_explain(exc, f, inputs)}")
            continue
        except Exception as exc:  # noqa: BLE001 - công thức hết hiệu lực, v.v.
            logger.warning("Không tính được công thức %s: %s", f["id"], exc)
            continue
        done.append({"formula": f, "inputs": got, "result": res})

    if done:
        lines = [
            "KẾT QUẢ TÍNH (bộ tính Decimal, công thức đã được người duyệt phê duyệt; dùng đúng các số này, không tự tính lại):"
        ]
        for d in done:
            f, res = d["formula"], d["result"]
            val = Decimal(res["value"])
            ins = "; ".join(f"{k} = {_fmt(Decimal(v))} {u}" for k, (v, u) in d["inputs"].items())
            conds = "; ".join(c["label"] for c in f["proposal"]["conditions"] if c.get("label"))
            lines.append(
                f"• {f['proposal']['title']} — {f['source']['file']} ({f['source'].get('section', '')}): "
                f"{f['proposal']['expression']} với {ins} → kết quả = {_fmt(val)} {res['unit']}"
                f"{_alt_units(val, res['unit'])}."
                + (f" Điều kiện áp dụng (người dùng tự đối chiếu): {conds}" if conds else "")
            )
        if errors:
            lines.append("Không tính được: " + " | ".join(errors))
        return CalcOutcome("answer", block="\n".join(lines), summary="\n".join(lines[1:]), results=done)
    if errors:
        return CalcOutcome("invalid", text="Không tính được vì số liệu không hợp lệ: " + " | ".join(errors) + ". Vui lòng kiểm tra lại số liệu.")
    if partial is not None:
        _, f, missing = partial
        items = "\n".join(f"- {v.get('label', v['key'])} ({v['key']}), đơn vị {v['unit']}" for v in missing)
        return CalcOutcome(
            "ask",
            text=(
                f"Chưa đủ số liệu để tính theo công thức «{f['proposal']['title']}» "
                f"({f['source']['file']}). Còn thiếu:\n{items}\n"
                "Vui lòng cho biết các giá trị này (kèm đơn vị) rồi hỏi lại."
            ),
        )
    return None
