from retrieval.normalize import semantic_query


def test_reference_names_do_not_dominate_multi_document_topic():
    query = 'Môi trường theo QTKĐ 8.765 (thiết bị A) và 8.123 (thiết bị B) là gì?'
    result = semantic_query(query)
    assert '8.765' not in result
    assert 'thiết bị A' in result
    assert 'Môi trường' in result and 'là gì' in result


def test_non_reference_measurement_values_are_preserved():
    query = 'Giới hạn 0,02 % và 7 MPa là gì?'
    assert semantic_query(query) == query


def test_decimal_point_values_and_parenthetical_conditions_survive():
    query = 'Sai số 0.001 MPa theo QTKĐ 8.765 (khi dùng khí) và QTKĐ 8.123?'
    result = semantic_query(query)
    assert '0.001 MPa' in result and '(khi dùng khí)' in result
