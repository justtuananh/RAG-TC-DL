"""Exact typed-field lookups; no formula evaluation or unit guessing."""

import pytest

from query import table_lookup

TABLE = (
    'Thời gian quay tự do phải lớn hơn hoặc bằng Bảng 7.\n\n'
    'Bảng 7 - Giá trị nhỏ nhất của thời gian quay tự do\n\nĐơn vị: min\n\n'
    '| Giới hạn đo, / MPa | Cấp chính xác (%) |  |\n'
    '| --- | --- | --- |\n|  | 0,02 | 0,1 |\n'
    '| Từ -0,1 đến 6 | 3 | 2 |\n| Lớn hơn 6 | 5 | 3 |'
)


def hit(text=TABLE, stem='QTKD_8.765'):
    return {'payload': {'file_stem': stem, 'section_path': 'Thời gian quay tự do', 'text': text}}


def question(cls='0,02', limit='5', unit='MPa'):
    return f'Thời gian quay tự do với cấp chính xác {cls}, giới hạn đo trên {limit} {unit} ít nhất bao nhiêu phút?'


@pytest.mark.parametrize(
    'cls,limit,value',
    [
        ('0,02', '5', '3'),
        ('0,1', '5', '2'),
        ('0,02', '7', '5'),
        ('0,02', '6', '3'),
        ('0,02', '-0,1', '3'),
    ],
)
def test_lookup_binds_class_and_range_fields(cls, limit, value):
    body = table_lookup.answer(question(cls, limit), [hit()])
    assert f'**{value} min**' in body
    assert 'Bảng 7' in body and '[1]' in body and '| Từ -0,1 đến 6 |' in body


@pytest.mark.parametrize(
    'q',
    [
        'Thời gian quay tự do cấp chính xác 0,02 khi vận hành ở áp suất 5 MPa bao nhiêu phút?',
        'Thời gian quay tự do giới hạn đo trên 5 MPa bao nhiêu phút?',
        question(unit='bar'),
        question(limit='-0,2'),
        question(cls='0,05'),
        question() + ' và cấp chính xác 0,1?',
        question() + ' và giới hạn đo trên 7 MPa?',
        'Tốc độ hạ với cấp chính xác 0,02, giới hạn đo trên 5 MPa bao nhiêu phút?',
        question().replace('phút', 'giây'),
    ],
)
def test_missing_mismatched_or_ambiguous_query_fields_fall_back(q):
    assert table_lookup.answer(q, [hit()]) is None


def test_unrelated_pressure_and_document_codes_are_not_used_as_lookup_fields():
    body = table_lookup.answer(
        question() + ' QTKĐ 8.765, áp suất vận hành 99 MPa, năm 2025.', [hit()]
    )
    assert '**3 min**' in body


def test_multiple_matching_documents_or_tables_fall_back_even_same_value():
    assert table_lookup.answer(question(), [hit(), hit(stem='QTKD_8.123')]) is None
    assert table_lookup.answer(question(), [hit(TABLE + '\n\n' + TABLE)]) is None


def test_repeated_hit_for_same_parent_keeps_original_source_index():
    body = table_lookup.answer(question(), [hit('Thông tin không liên quan.'), hit(), hit()])
    assert '**3 min**' in body and '[2]' in body


@pytest.mark.parametrize(
    'text',
    [
        TABLE.replace('0,1 |\n| Từ', '0,020 |\n| Từ'),
        TABLE.replace('Lớn hơn 6', 'Từ 6 đến 10'),
        TABLE.replace('| Từ -0,1 đến 6 | 3 |', '| Từ -0,1 đến 6 | ? |'),
        TABLE.replace('Đơn vị: min', 'Không ghi đơn vị'),
        TABLE.replace('Cấp chính xác (%)', 'Thông số khác (%)'),
    ],
)
def test_unrecognized_or_ambiguous_source_structure_falls_back(text):
    assert table_lookup.answer(question(limit='6'), [hit(text)]) is None


def test_explicit_document_scope_cannot_be_replaced_by_routed_fallback():
    assert table_lookup.answer(question() + ' theo QTKĐ 8.123', [hit()]) is None
    assert table_lookup.answer(question() + ' theo QTKĐ 8.123 và QTKĐ 8.765', [hit()]) is None
    assert (
        table_lookup.answer(question() + ' theo QTKĐ 8.123', [hit(), hit(stem='QTKD_8.123')])
        is not None
    )


def test_range_unit_case_is_preserved_from_source_header():
    assert '**5 MPa**' in table_lookup.answer(question(), [hit()])


def test_unrecognized_range_cannot_be_ignored_when_deciding_uniqueness():
    assert (
        table_lookup.answer(question(), [hit(TABLE.replace('Lớn hơn 6', 'Điều kiện khác'))]) is None
    )


def test_supported_source_units_are_matched_exactly_without_conversion():
    assert '**3 min**' in table_lookup.answer(
        question(unit='bar'), [hit(TABLE.replace('/ MPa', '/ bar'))]
    )
    assert '**3 s**' in table_lookup.answer(
        question().replace('phút', 'giây'), [hit(TABLE.replace('Đơn vị: min', 'Đơn vị: s'))]
    )


@pytest.mark.parametrize(
    'query_unit,source_unit',
    [('mPa', 'MPa'), ('Pa', 'MPa'), ('MPa', 'mPa'), ('MPa', 'Pa'), ('mpa', 'MPa')],
)
def test_si_prefix_case_never_changes_the_physical_unit(query_unit, source_unit):
    assert (
        table_lookup.answer(
            question(unit=query_unit), [hit(TABLE.replace('/ MPa', '/ ' + source_unit))]
        )
        is None
    )
