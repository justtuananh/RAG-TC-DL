from retrieval.query_expansion import expand_query


def test_unaccented_reinspection_maps_to_periodic_inspection_vocabulary():
    assert 'chu kỳ kiểm định' in expand_query('bao lau thi kiem dinh lai?')


def test_accented_and_decomposed_triggers_work():
    import unicodedata
    question = 'điều kiện môi trường'
    assert 'nhiệt độ' in expand_query(unicodedata.normalize('NFD', question))


def test_unrelated_question_is_unchanged():
    assert expand_query('một lời chào') == 'một lời chào'
