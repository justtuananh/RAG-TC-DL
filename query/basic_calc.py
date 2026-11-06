"""Phép tính phổ thông trong chat; giới hạn nghiệp vụ phải lấy từ nguồn truy hồi.

Không phê duyệt hay thực thi công thức nháp. Chỉ đổi đơn vị, hiệu và tỷ lệ
bằng Decimal; không cho mô hình ngôn ngữ tự tính hay tự chọn ngưỡng.
"""

from __future__ import annotations

import re
import unicodedata
from decimal import Decimal

from formula_lab.engine import UNITS, Invalid, expression, number

_NUM = r"[+-]?\d+(?:[.,]\d+)?"
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
    quantities = [
        (number(m[1].replace(',', '.')), _UNITS[m[2].lower()], m.start())
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
            return (number(match[1].replace(',', '.')), _UNITS[match[2]]) if match else None

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
            rate, floor = [number(x.replace(',', '.')) for x in rule.groups()]
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
    if tolerance and len(quantities) == 1 and ('sai so tuyet doi' in text or 'tinh' in text):
        val, unit, _ = quantities[0]
        rate = number(tolerance[1].replace(',', '.'))
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
        rate = number(match[1].replace(',', '.'))
        value, unit = pressure[0]
        if value <= 0 or rate < 0:
            return 'Không tính được: giới hạn áp suất phải dương và tỷ lệ không âm.', []
        result = expression('x*r/100', {'x': value, 'r': rate})
        return (
            f"Theo nguồn, độ tụt áp không vượt quá {_fmt(rate)} % giới hạn áp suất làm việc tối đa [1].\n\n{_fmt(rate)} % × {_fmt(value)} {unit} = **{_fmt(result)} {unit}**.",
            refs,
        )
    return None
