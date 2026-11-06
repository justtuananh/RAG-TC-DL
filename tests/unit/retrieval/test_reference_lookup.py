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
