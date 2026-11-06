from query.basic_calc import try_basic_calc


def source(text):
    return [{"payload": {"text": text, "file_stem": "qtkd", "section_path": "6.3"}}]


def test_unit_conversion_never_calls_model():
    out = try_basic_calc('Quy đổi 700 bar sang MPa.', lambda q: [])
    assert '70 MPa' in out[0]


def test_incompatible_conversion():
    assert 'Không đổi được' in try_basic_calc('Quy đổi 700 bar sang L.', lambda q: [])[0]


def test_supplied_relative_tolerance():
    answer, _ = try_basic_calc(
        'Áp kế H3000 tại điểm 500 bar có sai số tương đối cho phép ± 0,1 %, vậy sai số tuyệt đối cho phép là bao nhiêu bar?',
        lambda q: [],
    )
    assert '± 0,5 bar' in answer


def test_van_difference_and_decision_from_source():
    answer, refs = try_basic_calc(
        'Tính sai số áp suất chỉnh đặt của van an toàn khi áp suất mở van Pm = 42 bar và áp suất chỉnh đặt Pcd = 40 bar.',
        lambda q: source(
            'Giá trị cho phép của sai số áp suất chỉnh đặt bằng ± 3% áp suất chỉnh đặt của van nhưng không nhỏ hơn ± 0,15 bar.'
        ),
    )
    assert '2 bar' in answer and '5 %' in answer and 'Không đạt' in answer and refs


def test_van_implicit_labels_decimal_comma():
    answer, _ = try_basic_calc(
        'Van an toàn chỉnh đặt 100 bar mở ở 102,5 bar thì sai số tương đối là bao nhiêu phần trăm và có đạt không?',
        lambda q: source(
            'Giá trị cho phép của sai số áp suất chỉnh đặt bằng ± 3% áp suất chỉnh đặt của van nhưng không nhỏ hơn ± 0,15 bar.'
        ),
    )
    assert '2,5 %' in answer and 'Đạt' in answer


def test_missing_source_does_not_invent_limit():
    answer, _ = try_basic_calc(
        'Van an toàn chỉnh đặt 100 bar mở ở 102,5 bar thì sai số tương đối là bao nhiêu phần trăm và có đạt không?',
        lambda q: [],
    )
    assert '2,5 %' in answer and 'Chưa đủ' in answer


def test_ban_uses_only_grounded_percent():
    q = 'Bàn tạo áp có giới hạn làm việc tối đa 1400 bar, độ tụt áp cho phép sau 5 phút là bao nhiêu bar?'
    answer, refs = try_basic_calc(
        q,
        lambda q: source(
            'Độ tụt áp sau 5 phút không được vượt quá 5% giới hạn áp suất làm việc tối đa của bàn tạo áp.'
        ),
    )
    assert '70 bar' in answer and refs
    assert 'Chưa tìm thấy' in try_basic_calc(q, lambda q: [])[0]


def test_low_pressure_van_uses_absolute_floor():
    answer, _ = try_basic_calc(
        'Van an toàn chỉnh đặt 1 bar mở ở 1,1 bar thì sai số tương đối là bao nhiêu phần trăm và có đạt không?',
        lambda q: source(
            'Sai số áp suất chỉnh đặt bằng ± 3% áp suất chỉnh đặt nhưng không nhỏ hơn ± 0,15 bar.'
        ),
    )
    assert 'Đạt' in answer and '0,15 bar' in answer


def test_bad_values_cannot_crash_chat():
    for q in [
        'Quy đổi ' + '9' * 80 + ' bar sang MPa.',
        'Sai số tương đối -1 % tại 500 bar tính sai số tuyệt đối?',
    ]:
        answer, _ = try_basic_calc(q, lambda q: [])
        assert 'Không tính được' in answer


def test_conversion_never_falls_back_to_llm():
    answer, _ = try_basic_calc('Quy đổi 700 bar sang L.', lambda q: [])
    assert 'Không đổi được' in answer
