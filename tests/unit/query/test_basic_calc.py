from query.basic_calc import try_basic_calc


def source(text):
    return [{"payload": {"text": text, "file_stem": "qtkd", "section_path": "6.3"}}]


def test_unit_conversion_never_calls_model():
    out = try_basic_calc('Quy đổi 700 bar sang MPa.', lambda q: [])
    assert '70 MPa' in out[0]


def test_thousands_separator_is_not_dropped():
    # Lỗi cũ: "1 400 bar" bị đọc thành "400 bar" nên ra 40 MPa.
    for q in ('Đổi 1 400 bar sang MPa.', 'Đổi 1.400 bar sang MPa.', 'Đổi 1400 bar sang MPa.'):
        answer = try_basic_calc(q, lambda q: [])[0]
        assert '1400 bar = **140 MPa**' in answer, q


def test_reading_error_without_units():
    # Câu #24 của bộ kiểm tra: không có đơn vị nên trước đây không nhận được.
    answer, refs = try_basic_calc(
        'Một thiết bị chỉ 100,5 trong khi giá trị chuẩn là 100,0. Tính sai số tuyệt đối và sai số tương đối.',
        lambda q: [],
    )
    assert 'Sai số tuyệt đối: **0,5**' in answer
    assert 'Sai số tương đối: **0,5 %**' in answer
    assert refs == []


def test_reading_error_with_units_and_either_order():
    answer, _ = try_basic_calc(
        'Giá trị chuẩn là 10,0 bar, áp kế chỉ 10,2 bar. Tính sai số tuyệt đối và sai số tương đối.',
        lambda q: [],
    )
    assert 'Sai số tuyệt đối: **0,2 bar**' in answer and 'Sai số tương đối: **2 %**' in answer


def test_reading_error_keeps_sign_and_thousands():
    answer, _ = try_basic_calc(
        'Thiết bị chỉ 1 399,5 và giá trị chuẩn là 1 400. Tính sai số tuyệt đối và tương đối.', lambda q: []
    )
    assert '**-0,5**' in answer and '**-0,0357 %**' in answer


def test_reading_error_rounds_long_quotients():
    answer, _ = try_basic_calc(
        'Thiết bị chỉ 3,2 còn giá trị chuẩn là 3. Tính sai số tuyệt đối và sai số tương đối.', lambda q: []
    )
    assert '**6,6667 %**' in answer


def test_reading_error_zero_reference_is_refused():
    answer, _ = try_basic_calc(
        'Thiết bị chỉ 0,5 và giá trị chuẩn là 0. Tính sai số tuyệt đối và sai số tương đối.', lambda q: []
    )
    assert 'Không tính được' in answer


def test_reading_error_needs_error_request_and_both_numbers():
    assert try_basic_calc('Thiết bị chỉ 100,5, giá trị chuẩn là 100,0.', lambda q: []) is None
    assert try_basic_calc('Tính sai số tuyệt đối của thiết bị chỉ 100,5.', lambda q: []) is None


FC9531_LIMIT = (
    'Kết quả đo đạt yêu cầu nếu sai số đo được nằm trong giới hạn cho phép ± 1 % giá trị đọc.'
)


def test_reading_compliance_uses_limit_from_source():
    # Câu #28 của bộ kiểm tra: trước đây bị từ chối "không tìm thấy" dù nguồn có giới hạn.
    answer, refs = try_basic_calc(
        'Thiết bị FC9531 chỉ 200 L/h, hệ thống chuẩn chỉ 197 L/h. Có đạt yêu cầu sai số không?',
        lambda q: source(FC9531_LIMIT),
    )
    assert '**3**' in answer and '±1 % giá trị đọc' in answer and '±2' in answer
    assert '**Không đạt**' in answer and refs


def test_reading_compliance_within_limit_is_ok():
    answer, _ = try_basic_calc(
        'Thiết bị FC9531 chỉ 200 L/h, hệ thống chuẩn chỉ 199 L/h. Có đạt yêu cầu sai số không?',
        lambda q: source(FC9531_LIMIT),
    )
    assert '**Đạt**' in answer


def test_reading_compliance_percent_of_reference():
    answer, _ = try_basic_calc(
        'Giá trị chuẩn là 100 bar, áp kế chỉ 100,6 bar. Sai số có đạt không?',
        lambda q: source('Sai số cho phép ± 0,5 % giá trị chuẩn.'),
    )
    assert '±0,5 bar' in answer and '**Không đạt**' in answer


def test_reading_compliance_never_invents_a_limit():
    answer, refs = try_basic_calc(
        'Thiết bị FC9531 chỉ 200 L/h, hệ thống chuẩn chỉ 197 L/h. Có đạt yêu cầu sai số không?',
        lambda q: [],
    )
    assert 'Chưa đủ nguồn' in answer and '**3**' in answer and refs == []
    assert 'Đạt' not in answer.replace('đạt/không đạt', '')


def test_reading_compliance_ignores_unrelated_source_limit():
    answer, _ = try_basic_calc(
        'Thiết bị chỉ 200, chuẩn chỉ 197. Có đạt yêu cầu sai số không?',
        lambda q: source('Độ tụt áp không vượt quá 5 % giới hạn áp suất làm việc tối đa.'),
    )
    assert 'Chưa đủ nguồn' in answer


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


def test_percentage_of_a_quantity_without_the_word_tinh():
    # Bộ kiểm tra hệ thống: "7 % của 150 bar là bao nhiêu?" từng bị từ chối "không tìm thấy".
    answer, refs = try_basic_calc('7 % của 150 bar là bao nhiêu?', lambda q: [])
    assert '7 % × 150 bar = **10,5 bar**' in answer
    assert refs == []


def test_difference_between_two_plain_numbers():
    answer, refs = try_basic_calc('Chênh lệch giữa 100,5 và 99,8 là bao nhiêu?', lambda q: [])
    assert '**0,7**' in answer
    assert refs == []


def test_difference_keeps_units_and_is_absolute():
    answer, _ = try_basic_calc('Hiệu giữa 9,5 bar và 10 bar là bao nhiêu?', lambda q: [])
    assert '**0,5 bar**' in answer


def test_difference_with_mismatched_units_is_not_guessed():
    assert try_basic_calc('Chênh lệch giữa 5 bar và 3 L là bao nhiêu?', lambda q: []) is None
