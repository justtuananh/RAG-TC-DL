from types import SimpleNamespace

from query import extractive, multi_document


def hit(stem, text):
    return {'payload': {'file_stem': stem, 'section_path': '4 Điều kiện', 'text': text}}


def setup(monkeypatch, **overrides):
    cfg = dict(
        extractive_enabled=True,
        evidence_per_document=3,
        evidence_candidates_per_source=12,
        evidence_max_candidates=96,
        evidence_min_score=0.35,
        evidence_relative_floor=0.35,
    )
    cfg.update(overrides)
    monkeypatch.setattr(
        extractive,
        'get_settings',
        lambda: SimpleNamespace(llm=SimpleNamespace(multi_document=SimpleNamespace(**cfg))),
    )
    monkeypatch.setattr(extractive.doc_titles, 'title_for', lambda stem: stem)


def test_units_keep_table_header_conditions_and_all_rows():
    text = 'Áp dụng khi dùng dầu.\n\n| Cấp | mm/min |\n| --- | --- |\n| 0,1 | 2 |\n| 0,2 | 4 |\n\nKhông áp dụng cho khí.'
    units = extractive.evidence_units(text)
    table = next(u for u in units if '| Cấp |' in u)
    assert 'Áp dụng khi dùng dầu.' in table
    assert '| 0,1 | 2 |' in table and '| 0,2 | 4 |' in table
    assert 'Không áp dụng cho khí.' in table


def test_units_keep_formula_and_definition_together():
    text = 'Hiệu chỉnh được tính theo:\n\n$$p = a+b$$\n\nTrong đó a là áp suất chuẩn.'
    units = extractive.evidence_units(text)
    assert any('$$p = a+b$$' in u and 'Trong đó a' in u for u in units)


def test_table_title_does_not_separate_applicability_condition():
    text = 'Chỉ áp dụng cho dầu.\n\n# Bảng 1\n\n| Cấp | bar |\n| --- | --- |\n| 1 | 2 |\n\nKhông áp dụng cho khí.'
    table = next(unit for unit in extractive.evidence_units(text) if '| Cấp |' in unit)
    assert 'Chỉ áp dụng cho dầu.' in table and 'Không áp dụng cho khí.' in table


def test_missing_document_evidence_is_explicit(monkeypatch):
    setup(monkeypatch)
    monkeypatch.setattr(extractive.reranker, 'score_documents', lambda *a: [0.9, 0.01])
    body = extractive.answer(
        'So sánh?',
        [hit('A', 'Giá trị A.'), hit('B', 'Giá trị B.')],
        multi_document.group_by_document(['A', 'B']),
    )
    assert '**B**' in body and 'Chưa tìm thấy đủ bằng chứng' in body


def test_answer_preserves_document_and_reference_without_numeric_merge(monkeypatch):
    setup(monkeypatch)
    results = [hit('A', 'Giới hạn 8 bar khi dùng dầu.'), hit('B', 'Giới hạn 8 MPa khi dùng khí.')]
    monkeypatch.setattr(extractive.reranker, 'score_documents', lambda q, docs: [0.9] * len(docs))
    body = extractive.answer('Giới hạn?', results, multi_document.group_by_document(['A', 'B']))
    assert '**A**' in body and '**B**' in body
    assert 'Giới hạn 8 bar khi dùng dầu. [1]' in body
    assert 'Giới hạn 8 MPa khi dùng khí. [2]' in body


def test_low_scores_or_service_error_use_existing_path(monkeypatch):
    setup(monkeypatch)
    results = [hit('A', 'Chu kỳ 8 tháng.'), hit('B', 'Chu kỳ 9 tháng.')]
    groups = multi_document.group_by_document(['A', 'B'])
    monkeypatch.setattr(extractive.reranker, 'score_documents', lambda q, docs: [0.01] * len(docs))
    assert extractive.answer('Chu kỳ?', results, groups) is None

    def fail(*args):
        raise RuntimeError('unavailable')

    monkeypatch.setattr(extractive.reranker, 'score_documents', fail)
    assert extractive.answer('Chu kỳ?', results, groups) is None


def test_candidates_bounded_and_distributed_across_documents(monkeypatch):
    setup(monkeypatch, evidence_max_candidates=4)
    results = [
        hit(stem, '\n\n'.join(f'Đoạn {i} cho {stem}.' for i in range(20))) for stem in ['A', 'B']
    ]
    calls = []

    def score(q, docs):
        calls.append(docs)
        return [0.8] * len(docs)

    monkeypatch.setattr(extractive.reranker, 'score_documents', score)
    body = extractive.answer('Đoạn?', results, multi_document.group_by_document(['A', 'B']))
    assert len(calls) == 1 and len(calls[0]) <= 4
    assert '**A**' in body and '**B**' in body


def test_disabled_does_not_call_reranker(monkeypatch):
    setup(monkeypatch, extractive_enabled=False)
    monkeypatch.setattr(extractive.reranker, 'score_documents', lambda *args: 1 / 0)
    assert extractive.answer('hỏi', [], []) is None


def test_reference_answer_keeps_the_appendix_title_and_replacement_device():
    results = [
        hit('A', '# Phụ lục K\n\n# Đánh giá sai số'),
        hit('B', 'Thiết bị B\n\nThay thế quy trình cũ.'),
    ]
    for result in results:
        result['reference_match'] = True
    body = extractive.reference_answer(results)
    assert 'Đánh giá sai số' in body and 'Thiết bị B' in body
    assert '[1]' in body and '[2]' in body


def test_single_document_refusal_fallback_requires_explicit_opt_in(monkeypatch):
    setup(monkeypatch)
    results = [hit('A', 'Thay chất lỏng tương đương chủng loại do nhà sản xuất quy định.')]
    groups = multi_document.group_by_document(['A'])
    monkeypatch.setattr(extractive.reranker, 'score_documents', lambda *a: [0.9])
    assert extractive.answer('Thay chất lỏng?', results, groups) is None
    body = extractive.answer('Thay chất lỏng?', results, groups, allow_single=True)
    assert 'nhà sản xuất quy định.' in body


def test_matched_child_late_in_parent_is_not_lost_to_candidate_cap(monkeypatch):
    setup(monkeypatch, evidence_candidates_per_source=2)
    results = [hit('A', 'Nội dung liên quan ở cuối.'), hit('B', 'Thông tin khác.')]
    results[0]['parent_payload'] = {
        'text': '\n\n'.join(
            [f'Đoạn mở đầu {i}.' for i in range(20)] + ['Nội dung liên quan ở cuối.']
        )
    }
    calls = []

    def score(query, docs):
        calls.extend(docs)
        return [0.9] * len(docs)

    monkeypatch.setattr(extractive.reranker, 'score_documents', score)
    body = extractive.answer('Nội dung?', results, multi_document.group_by_document(['A', 'B']))
    assert any('Nội dung liên quan ở cuối.' in doc for doc in calls)
    assert 'Nội dung liên quan ở cuối. [1]' in body


def test_paragraph_keeps_following_note_qualification():
    text = (
        '- Nếu chất lỏng bị bẩn thì thay chất lỏng khác.\n\n'
        'CHÚ THÍCH: Chất lỏng thay mới phải tương đương do nhà sản xuất quy định.\n\n'
        '# 5 Tiến hành kiểm định\n\nKhông tiến hành bước sau nếu không đạt.'
    )
    unit = next(u for u in extractive.evidence_units(text) if 'bị bẩn' in u)
    assert 'CHÚ THÍCH: Chất lỏng thay mới phải tương đương' in unit
    assert '# 5' not in unit


def test_list_items_keep_introductory_quantity_context():
    text = (
        'Sai số cho phép của các phép đo đối với:\n\n'
        '- Thời gian quay tự do: ± 10 s;\n\n'
        '- Nhiệt độ môi trường: ± 0,5 oC;\n\n'
        '- Vận tốc góc ban đầu: ± 1,5 r/min.\n\n'
        'Thời gian quay tự do phải lớn hơn 3 min.'
    )
    units = extractive.evidence_units(text)
    for term in ['± 10 s', '± 0,5 oC', '± 1,5 r/min']:
        assert all('Sai số cho phép của các phép đo đối với:' in u for u in units if term in u)
    assert 'Sai số cho phép' not in units[-1]


def test_qualification_enrichment_does_not_change_ranking_input(monkeypatch):
    setup(monkeypatch)
    original = '- Nếu chất lỏng bị bẩn thì thay chất lỏng khác.'
    note = 'CHÚ THÍCH: Chất lỏng thay mới phải tương đương do nhà sản xuất quy định.'
    results = [hit('A', original + '\n\n' + note)]
    scored = []

    def score(query, docs):
        scored.extend(docs)
        return [0.9 if doc.endswith(original) else 0.01 for doc in docs]

    monkeypatch.setattr(extractive.reranker, 'score_documents', score)
    body = extractive.answer(
        'Thay chất lỏng?', results, multi_document.group_by_document(['A']), allow_single=True
    )
    assert any(doc.endswith(original) for doc in scored)
    assert note in body


def test_table_ranking_focuses_component_but_quote_keeps_full_table(monkeypatch):
    setup(monkeypatch)
    text = (
        '| TT | Tên phương tiện | Phạm vi |\n| --- | --- | --- |\n'
        '| 1 | Áp kế chuẩn | 500 bar |\n'
        '| 2 | Đồng hồ bấm giây điện tử | 24 h |'
    )
    results = [hit('A', text)]
    seen = []

    def score(query, docs):
        seen.extend(docs)
        return [0.9] * len(docs)

    monkeypatch.setattr(extractive.reranker, 'score_documents', score)
    body = extractive.answer(
        'Đồng hồ bấm giây?', results, multi_document.group_by_document(['A']), allow_single=True
    )
    assert all('Áp kế chuẩn' not in doc for doc in seen)
    assert 'Áp kế chuẩn' in body and 'Đồng hồ bấm giây điện tử' in body


def test_formula_and_symbol_definitions_form_one_candidate():
    text = (
        'Tốc độ được tính theo:\n\n$$V=V_t \\eta_t/\\eta$$\n\ntrong đó:\n\n'
        '$V$ là tốc độ tiêu chuẩn;\n\n$V_t$ là tốc độ đo;\n\n'
        '$\\eta$ là độ nhớt tiêu chuẩn;\n\n$\\eta_t$ là độ nhớt đo.\n\n'
        'Tốc độ là trung bình ba lần và không vượt quá Bảng 4.'
    )
    formulas = [unit for unit in extractive.evidence_units(text) if '$' in unit]
    assert len(formulas) == 1
    assert '$V=V_t' in formulas[0] and '$\\eta_t$ là độ nhớt đo.' in formulas[0]
    assert 'trung bình ba lần' not in formulas[0]


def test_selected_table_reference_keeps_its_same_section_table_and_units(monkeypatch):
    setup(monkeypatch, evidence_candidates_per_source=1)
    statement = 'Tốc độ là trung bình ba lần, không vượt quá 5 % giá trị tại Bảng 4.'
    text = (
        statement
        + '\n\nBảng 4 - Tốc độ cho phép\n\nĐơn vị: mm/min\n\n| Cấp | Tốc độ |\n| --- | --- |\n| 0,02 | 1,5 |'
    )
    results = [hit('A', statement)]
    results[0]['parent_payload'] = {'text': text}
    monkeypatch.setattr(extractive.reranker, 'score_documents', lambda q, docs: [0.9] * len(docs))
    body = extractive.answer(
        'Tốc độ?', results, multi_document.group_by_document(['A']), allow_single=True
    )
    assert statement in body
    assert 'Bảng 4 - Tốc độ cho phép' in body and 'Đơn vị: mm/min' in body
    assert '| 0,02 | 1,5 |' in body


def test_limit_quote_keeps_explicit_measurement_conditions_in_same_section(monkeypatch):
    setup(monkeypatch, evidence_candidates_per_source=1)
    limit = 'Tốc độ hạ là trung bình ba lần đo và không vượt quá 3 mm/min.'
    text = (
        'Tốc độ hạ được xác định trong các điều kiện sau:\n\n- Ở áp suất 700 bar;\n\n- Ở nhiệt độ tiêu chuẩn;\n\n'
        + limit
    )
    results = [hit('A', limit)]
    results[0]['parent_payload'] = {'text': text}
    monkeypatch.setattr(extractive.reranker, 'score_documents', lambda q, docs: [0.9] * len(docs))
    body = extractive.answer(
        'Tốc độ?', results, multi_document.group_by_document(['A']), allow_single=True
    )
    assert 'Ở áp suất 700 bar' in body and 'Ở nhiệt độ tiêu chuẩn' in body
    assert limit in body
