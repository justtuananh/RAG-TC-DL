"""Phép tính phổ thông trong chat; giới hạn nghiệp vụ phải lấy từ nguồn truy hồi.

Không phê duyệt hay thực thi công thức nháp. Chỉ đổi đơn vị, hiệu và tỷ lệ
bằng Decimal; không cho mô hình ngôn ngữ tự tính hay tự chọn ngưỡng.
"""

from __future__ import annotations

import re
import unicodedata
from decimal import Decimal

from formula_lab.engine import UNITS, Invalid, expression, number
from query.numbers import NUMBER, normalize

_NUM = rf"[+-]?{NUMBER}"
_UNITS = {u.lower(): u for u in UNITS}
_QTY = re.compile(rf"({_NUM})\s*(MPa|kPa|Pa|bar|mL|L|mm|m|kg|g|s|min)(?![\w/])", re.I)


def _fold(s):
    return ''.join(
        c
        for c in unicodedata.normalize('NFD', s.lower().replace('đ', 'd'))
        if unicodedata.category(c) != 'Mn'
    )


def _fmt(v):
    return (
        format(v, 'f').rstrip('0').rstrip('.').replace('.', ',')
        if '.' in format(v, 'f')
        else format(v, 'f')
    )


_ROUND = Decimal('0.0001')
_UNIT_TOKEN = '|'.join(re.escape(u) for u in sorted(_UNITS, key=len, reverse=True) if u.isalpha())
_MEASURED = r'(?:chi thi|chi|do duoc|doc duoc|so chi|gia tri do)'
_REFERENCE = r'(?:gia tri chuan|gia tri that|gia tri thuc|gia tri dung|chuan)'


_LIMIT = rf'±\s*({_NUM})\s*%\s*(gia tri doc|gia tri do|gia tri chuan)'
_BASIS_LABEL = {'gia tri doc': 'giá trị đọc', 'gia tri do': 'giá trị đo', 'gia tri chuan': 'giá trị chuẩn'}


def _labeled_number(text, labels):
    # "(?<!chuan )": trong "hệ thống chuẩn chỉ 197" số 197 là của giá trị chuẩn, không phải số chỉ.
    return re.search(
        rf'(?<!chuan )\b{labels}\b\s*(?:chi\s+|la\s+|bang\s+|[=:]\s*)?({_NUM})'
        rf'(?:\s*({_UNIT_TOKEN})(?![\w/]))?',
        text,
    )


def _reading_pair(text):
    """(số chỉ, giá trị chuẩn, đơn vị chung) người dùng đưa; None nếu thiếu hoặc lệch đơn vị."""
    measured, reference = _labeled_number(text, _MEASURED), _labeled_number(text, _REFERENCE)
    if not measured or not reference:
        return None
    units = {m[2] for m in (measured, reference) if m[2]}
    if len(units) > 1:
        return None
    unit = f' {_UNITS[units.pop()]}' if units else ''
    return number(normalize(measured[1])), number(normalize(reference[1])), unit


def _reading_error(text):
    """Sai số tuyệt đối/tương đối giữa số chỉ và giá trị chuẩn người dùng đưa, đơn vị là tùy chọn.

    Δ = số chỉ − giá trị chuẩn; δ = Δ / giá trị chuẩn × 100 (cùng cách tính với công thức trong QTKĐ).
    """
    if 'sai so' not in text or 'van an toan' in text or not re.search(r'tuyet doi|tuong doi|phan tram', text):
        return None
    pair = _reading_pair(text)
    if not pair:
        return None
    measured, reference, unit = pair
    diff = expression('a-b', {'a': measured, 'b': reference})
    percent = expression('d/p*100', {'d': diff, 'p': reference})
    percent = percent.quantize(_ROUND) or Decimal(0)
    return (
        f"Sai số tuyệt đối: **{_fmt(diff)}{unit}**.\n\nSai số tương đối: **{_fmt(percent)} %**.\n\n"
        'Δ = số chỉ − giá trị chuẩn; δ = Δ / giá trị chuẩn × 100.',
        [],
    )


def _reading_compliance(text, question, retrieve):
    """Đạt/không đạt cho số chỉ so với giá trị chuẩn; giới hạn "± X % giá trị đọc/chuẩn" phải lấy từ nguồn."""
    if 'sai so' not in text or 'van an toan' in text or not re.search(r'\bdat\b', text):
        return None
    pair = _reading_pair(text)
    if not pair:
        return None
    measured, reference, unit = pair
    diff = expression('a-b', {'a': measured, 'b': reference})
    answer = f'Sai số Δ = số chỉ − giá trị chuẩn = **{_fmt(diff)}{unit}**.'
    rule, refs = _rule(question, retrieve, _LIMIT)
    if not rule:
        return answer + '\n\nChưa đủ nguồn xác định giới hạn cho phép để kết luận đạt/không đạt.', []
    rate = number(normalize(rule[1]))
    basis = reference if rule[2] == 'gia tri chuan' else measured
    limit = expression('v*r/100', {'v': abs(basis), 'r': rate})
    verdict = 'Đạt' if abs(diff) <= limit else 'Không đạt'
    return (
        f'{answer}\n\nGiới hạn: ±{_fmt(rate)} % {_BASIS_LABEL[rule[2]]} [1]; tại điểm này là ±{_fmt(limit)}{unit}. **{verdict}**.',
        refs,
    )


def _text(hit):
    return (hit.get('parent_payload') or hit['payload']).get('text', '')


def _rule(question, retrieve, pattern):
    try:
        hits = retrieve(question)
    except Exception:
        return None, []
    for hit in hits:
        match = re.search(pattern, _fold(_text(hit)))
        if match:
            return match, [hit]
    return None, []


_DIFFERENCE = re.compile(
    rf'\b(?:chenh lech|hieu)\s+(?:giua\s+)?({_NUM})\s*({_UNIT_TOKEN})?(?![\w/])'
    rf'\s+(?:va|voi)\s+({_NUM})\s*({_UNIT_TOKEN})?(?![\w/])'
)


def _difference(text):
    """Câu trả lời cho "chênh lệch giữa A và B" (trị tuyệt đối); None nếu đơn vị hai số lệch nhau."""
    match = _DIFFERENCE.search(text)
    if not match:
        return None
    first, first_unit, second, second_unit = match.groups()
    if first_unit != second_unit:
        return None
    a, b = number(normalize(first)), number(normalize(second))
    unit = f' {_UNITS[first_unit]}' if first_unit else ''
    result = expression('abs(a-b)', {'a': a, 'b': b})
    return f'Chênh lệch giữa {_fmt(a)}{unit} và {_fmt(b)}{unit}: **{_fmt(result)}{unit}**.'


def try_basic_calc(message, retrieve):
    try:
        return _try_basic_calc(message, retrieve)
    except (Invalid, ArithmeticError, ValueError):
        return (
            'Không tính được: số liệu không hợp lệ hoặc ngoài miền tính toán. Vui lòng kiểm tra số và đơn vị.',
            [],
        )


def _try_basic_calc(message, retrieve):
    """(câu trả lời, nguồn truy hồi) hoặc None nếu ngoài phép tính hỗ trợ."""
    text = _fold(message)
    reading = _reading_error(text) or _reading_compliance(text, message, retrieve)
    if reading:
        return reading
    difference = _difference(text)
    if difference:
        return difference, []
    quantities = [
        (number(normalize(m[1])), _UNITS[m[2].lower()], m.start())
        for m in _QTY.finditer(message)
    ]
    if not quantities:
        return None
    if re.search(r'\b(quy doi|chuyen doi|doi\s+.+?\s+sang)\b', text):
        target = re.search(r'\b(?:sang|thanh)\s+(\w+)\b', text)
        if target and target[1] in _UNITS and len(quantities) == 1:
            value, unit, _ = quantities[0]
            dst = _UNITS[target[1]]
            if UNITS[unit][0] == UNITS[dst][0]:
                result = expression(
                    'x*a/b', {'x': value, 'a': Decimal(UNITS[unit][1]), 'b': Decimal(UNITS[dst][1])}
                )
                return (
                    f"{_fmt(value)} {unit} = **{_fmt(result)} {dst}**.",
                    [],
                )
        return 'Không đổi được: đơn vị chưa hỗ trợ hoặc không cùng đại lượng.', []
    if 'van an toan' in text and ('sai so' in text or 'co dat' in text):
        # Nhãn gắn với từng số, không phụ thuộc thứ tự mở van/chỉnh đặt.
        def labeled(pattern):
            match = re.search(
                rf'{pattern}\s*(?:[a-z_]+\s*)?(?:=\s*)?({_NUM})\s*(mpa|kpa|pa|bar)\b', text
            )
            return (number(normalize(match[1])), _UNITS[match[2]]) if match else None

        opened = labeled(r'(?:ap suat mo van|mo o|pm)')
        setpoint = labeled(r'(?:ap suat chinh dat|chinh dat|pcd)')
        if not opened or not setpoint:
            return None
        pm, pu = opened
        pcd, cu = setpoint
        if pcd <= 0 or pm < 0:
            return (
                'Không tính được: áp suất chỉnh đặt phải lớn hơn 0 và áp suất mở van không âm.',
                [],
            )
        pm = expression('x*a/b', {'x': pm, 'a': Decimal(UNITS[pu][1]), 'b': Decimal(UNITS[cu][1])})
        diff = expression('a-b', {'a': pm, 'b': pcd})
        percent = expression('d/p*100', {'d': diff, 'p': pcd})
        answer = f"Sai số áp suất chỉnh đặt: **{_fmt(diff)} {cu}**.\n\nSai số tương đối: **{_fmt(percent)} %**."
        rule, refs = _rule(
            'Theo QTKĐ 1.061 sai số áp suất chỉnh đặt van an toàn cho phép không nhỏ hơn',
            retrieve,
            rf'sai so ap suat chinh dat[^\n]*?±\s*({_NUM})\s*%[^\n]*?khong nho hon\s*±\s*({_NUM})\s*bar',
        )
        if rule:
            rate, floor = [number(normalize(x)) for x in rule.groups()]
            limit = max(
                expression('p*r/100', {'p': pcd, 'r': rate}),
                expression(
                    'f*a/b', {'f': floor, 'a': Decimal(UNITS['bar'][1]), 'b': Decimal(UNITS[cu][1])}
                ),
            )
            verdict = 'Đạt' if abs(diff) <= limit else 'Không đạt'
            answer += f"\n\nGiới hạn: ±{_fmt(rate)} % áp suất chỉnh đặt, nhưng không nhỏ hơn ±{_fmt(floor)} bar [1]; tại điểm này là ±{_fmt(limit)} {cu}. **{verdict}**."
        else:
            answer += '\n\nChưa đủ nguồn xác định giới hạn cho phép để kết luận đạt/không đạt.'
        return answer, refs
    tolerance = re.search(rf'({_NUM})\s*%', text)
    percent_of = re.search(rf'{_NUM}\s*%\s*cua\b', text)
    if tolerance and len(quantities) == 1 and ('sai so tuyet doi' in text or 'tinh' in text or percent_of):
        val, unit, _ = quantities[0]
        rate = number(normalize(tolerance[1]))
        if val < 0 or rate < 0:
            return 'Không tính được: giá trị và tỷ lệ sai số phải không âm.', []
        result = expression('x*r/100', {'x': val, 'r': rate})
        sign = '± ' if 'sai so' in text else ''
        return (
            f"{_fmt(rate)} % × {_fmt(val)} {unit} = **{sign}{_fmt(result)} {unit}**.",
            [],
        )
    if 'ban tao ap' in text and 'tut ap' in text:
        pressure = [(v, u) for v, u, _ in quantities if UNITS[u][0] == 'pressure']
        if len(pressure) != 1:
            return None
        match, refs = _rule(
            'Theo QTKĐ 1.062 độ tụt áp sau 5 phút không vượt quá giới hạn áp suất làm việc tối đa',
            retrieve,
            rf'(?:do )?tut ap[^\n]*?khong (?:duoc )?vuot qua\s*({_NUM})\s*%[^\n]*?gioi han ap suat lam viec toi da',
        )
        if not match:
            return (
                'Chưa tìm thấy nguồn xác nhận tỷ lệ độ tụt áp cho phép. Vui lòng cung cấp tỷ lệ hoặc tài liệu phù hợp.',
                [],
            )
        rate = number(normalize(match[1]))
        value, unit = pressure[0]
        if value <= 0 or rate < 0:
            return 'Không tính được: giới hạn áp suất phải dương và tỷ lệ không âm.', []
        result = expression('x*r/100', {'x': value, 'r': rate})
        return (
            f"Theo nguồn, độ tụt áp không vượt quá {_fmt(rate)} % giới hạn áp suất làm việc tối đa [1].\n\n{_fmt(rate)} % × {_fmt(value)} {unit} = **{_fmt(result)} {unit}**.",
            refs,
        )
    return None
