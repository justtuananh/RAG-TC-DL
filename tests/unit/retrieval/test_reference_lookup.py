from types import SimpleNamespace

from retrieval import reference_lookup


def corpus(tmp_path, monkeypatch):
    monkeypatch.setattr(
        reference_lookup,
        'get_settings',
        lambda: SimpleNamespace(paths=SimpleNamespace(markdown_dir=tmp_path)),
    )
    return tmp_path


def test_historical_code_looks_up_explicit_replacement_statement(tmp_path, monkeypatch):
    root = corpus(tmp_path, monkeypatch)
    (root / 'QTKD_8.765_2025.md').write_text(
        'QTKĐ 8.765 : 2025\n\nThiết bị thử\n\nQUY TRÌNH KIỂM ĐỊNH\n\n'
        'Lời nói đầu\n\nQuy trình QTKĐ 8.765 : 2025 thay thế QTKĐ 8.123 : 2010.\n'
    )
    hits = reference_lookup.lookup(
        'QTKĐ 8.123 đã được thay bằng quy trình nào?', {'QTKD_8.765_2025'}
    )
    assert len(hits) == 1
    assert '8.765 : 2025 thay thế QTKĐ 8.123' in hits[0]['payload']['text']
    assert 'Thiết bị thử' in hits[0]['payload']['text']
    assert hits[0]['payload']['section_path'] == 'Lời nói đầu'


def test_unknown_replacement_does_not_guess(tmp_path, monkeypatch):
    corpus(tmp_path, monkeypatch)
    assert reference_lookup.lookup('QTKĐ 8.222 thay thế bằng gì?', {'missing'}) == []


def test_appendix_topic_survives_separate_regulatory_heading(tmp_path, monkeypatch):
    root = corpus(tmp_path, monkeypatch)
    (root / 'QTKD_8.765_2025.md').write_text(
        '# Phụ lục A\n\nMẫu giấy\n\n# Phụ lục D\n\n# (Quy định)\n\n'
        '# Đánh giá kết quả\n\nD.1 Sai số\n\nNội dung.\n\n# Phụ lục E\n\nMục khác.'
    )
    hits = reference_lookup.lookup('Phụ lục D của QTKĐ 8.765 có nội dung gì?', {'QTKD_8.765_2025'})
    assert len(hits) == 1
    assert 'Đánh giá kết quả' in hits[0]['payload']['text']
    assert 'Mục khác' not in hits[0]['payload']['text']


def test_other_question_does_not_trigger_document_scan(monkeypatch):
    monkeypatch.setattr(reference_lookup, 'get_settings', lambda: 1 / 0)
    assert reference_lookup.lookup('Sai số cho phép là bao nhiêu?', {'A'}) == []


def test_change_of_temperature_is_not_a_replacement_request():
    assert not reference_lookup.is_reference_query(
        'Theo QTKĐ 8.765, thay đổi nhiệt độ cho phép là bao nhiêu?'
    )


def test_multiple_appendix_letters_fall_back_to_normal_retrieval():
    assert not reference_lookup.is_reference_query(
        'Phụ lục D và Phụ lục E của QTKĐ 8.765 có nội dung gì?'
    )


def test_missing_requested_document_does_not_return_partial_reference(tmp_path, monkeypatch):
    root = corpus(tmp_path, monkeypatch)
    (root / 'QTKD_8.765.md').write_text(
        '# Phụ lục D\n\n# (Quy định)\n\nĐánh giá kết quả.\n\nNội dung khác.'
    )
    assert (
        reference_lookup.lookup(
            'Phụ lục D của QTKĐ 8.765 và QTKĐ 8.222 có nội dung gì?', {'QTKD_8.765'}
        )
        == []
    )


def test_appendix_topic_returns_complete_title_without_arbitrary_body_cut(tmp_path, monkeypatch):
    root = corpus(tmp_path, monkeypatch)
    (root / 'QTKD_8.765.md').write_text(
        '# Phụ lục D\n\n# (Quy định)\n\n# Đánh giá kết quả\n\nD.1 Sai số\n\n| A | B |\n| --- | --- |\n'
    )
    hit = reference_lookup.lookup('Phụ lục D của QTKĐ 8.765 có nội dung gì?', {'QTKD_8.765'})[0]
    assert 'Đánh giá kết quả' in hit['payload']['text']
    assert '| A |' not in hit['payload']['text']


MODE_TABLE = (
    '| TT | Tên phép kiểm định | Theo điều | Chế độ kiểm định |  |  |\n'
    '| --- | --- | --- | --- | --- | --- |\n'
    '|  |  |  | Ban đầu | Định kỳ | Sau sửa chữa |\n'
    '| 1 | Kiểm tra bên ngoài | 5.1 | + | + | + |\n'
    '| 2 | Kiểm tra kỹ thuật | 5.2 | + |  | + |'
)


def test_exact_mode_and_row_lookup_preserves_blank_without_inventing_meaning(tmp_path, monkeypatch):
    root = corpus(tmp_path, monkeypatch)
    (root / 'QTKD_8.765.md').write_text('# 2 Các phép kiểm định\n\nBảng 1\n\n' + MODE_TABLE)
    hits = reference_lookup.lookup(
        'QTKĐ 8.765, kiểm tra kỹ thuật có phải thực hiện khi kiểm định định kỳ không?',
        {'QTKD_8.765'},
    )
    assert len(hits) == 1 and hits[0]['reference_match']
    body = hits[0]['payload']['text']
    assert MODE_TABLE in body
    assert 'Kiểm tra kỹ thuật' in body and 'Định kỳ: không đánh dấu áp dụng (ô trống)' in body
    assert 'không áp dụng' not in body


def test_mode_lookup_requires_every_named_document(tmp_path, monkeypatch):
    root = corpus(tmp_path, monkeypatch)
    (root / 'QTKD_8.765.md').write_text(MODE_TABLE)
    assert (
        reference_lookup.lookup(
            'QTKĐ 8.765 và QTKĐ 8.222, kiểm tra kỹ thuật có phải thực hiện khi kiểm định định kỳ không?',
            {'QTKD_8.765'},
        )
        == []
    )


def test_mode_lookup_rejects_mixed_intent_and_multiple_rows(tmp_path, monkeypatch):
    root = corpus(tmp_path, monkeypatch)
    (root / 'QTKD_8.765.md').write_text(MODE_TABLE)
    for question in [
        'QTKĐ 8.765 kiểm tra kỹ thuật khi định kỳ có áp dụng không và áp suất bao nhiêu?',
        'QTKĐ 8.765 kiểm tra kỹ thuật và kiểm tra bên ngoài khi định kỳ có áp dụng không?',
        'QTKĐ 8.765 kiểm tra kỹ thuật khi ban đầu và định kỳ có áp dụng không?',
        'QTKĐ 8.765 kiểm tra kỹ thuật khi định kỳ có áp dụng không và thực hiện thế nào?',
    ]:
        assert reference_lookup.lookup(question, {'QTKD_8.765'}) == []


def test_mode_lookup_rejects_ambiguous_headers_symbols_and_repeated_tables(tmp_path, monkeypatch):
    root = corpus(tmp_path, monkeypatch)
    for text in [
        MODE_TABLE.replace('| + |  | + |', '| + | ? | + |'),
        MODE_TABLE.replace('Sau sửa chữa', 'Định kỳ'),
        MODE_TABLE + '\n\nBảng 2\n\n' + MODE_TABLE,
    ]:
        (root / 'QTKD_8.765.md').write_text(text)
        assert (
            reference_lookup.lookup(
                'QTKĐ 8.765 kiểm tra kỹ thuật khi định kỳ có áp dụng không?', {'QTKD_8.765'}
            )
            == []
        )


def test_mode_lookup_requires_explicit_document_reference():
    assert not reference_lookup.is_reference_query(
        'Ở mức 8.765 MPa, kiểm tra kỹ thuật định kỳ có áp dụng không?'
    )


def test_blank_cell_gets_negative_meaning_only_from_explicit_source_declaration(
    tmp_path, monkeypatch
):
    root = corpus(tmp_path, monkeypatch)
    declaration = '* Đối với trường hợp kiểm định định kỳ: không áp dụng kiểm tra kỹ thuật.'
    (root / 'QTKD_8.765.md').write_text(MODE_TABLE + '\n\n# 5.2\n\n' + declaration)
    hits = reference_lookup.lookup(
        'QTKĐ 8.765 kiểm tra kỹ thuật định kỳ có áp dụng không?', {'QTKD_8.765'}
    )
    assert len(hits) == 1
    assert declaration in hits[0]['payload']['text']
