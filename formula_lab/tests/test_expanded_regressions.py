"""Regressions discovered by the expanded DOCX registry evaluation."""
import copy
import pytest
from fastapi.testclient import TestClient
from formula_lab.app import app, sessions
from formula_lab.strategies import prepare, select

@pytest.mark.parametrize('question', [
    'Công thức sai số tương đối theo QTKĐ 1.190 của DPI 610?',
    'Sai số tương đối theo QTKĐ 1.160?',
    'Hiệu chỉnh gia tốc theo QTKĐ 1.159?',
    'Dung tích bình phân ly theo QTKĐ 1.190?',
    'Thời gian quay DPI 610?',
    'Tốc độ hạ theo QTKĐ 1.160?',
])
def test_explicit_different_procedure_is_not_routed(question):
    assert select(question) is None

@pytest.mark.parametrize('question,id', [
    ('Sai số tương đối H3000 theo QTKĐ 1.071?', 'error'),
    ('Dung tích bình phân ly theo QTKĐ 1.063?', 'volume'),
    ('Sai số van an toàn theo QTKĐ 1.061?', 'valve'),
])
def test_matching_procedure_keeps_calculator(question,id):
    assert select(question)['id'] == id

@pytest.mark.parametrize('bad_unit', [{}, [], None, True, 123])
def test_malformed_unit_returns_validation_response(bad_unit):
    prepared=prepare(select('Sai số van an toàn'), 'registry')
    sid='expanded-malformed-unit'
    sessions[sid]=copy.deepcopy(prepared)
    try:
        with TestClient(app) as client:
            response=client.post('/api/lab/calculate', json={
                'session_id':sid, 'revision':prepared['spec']['revision'],
                'inputs':{'pm':{'value':'103000','unit':bad_unit},'pcd':{'value':'100000','unit':'Pa'}},
                'confirmations':{},
            })
        assert response.status_code == 200
        assert response.json()['status'] == 'invalid'
    finally:
        sessions.pop(sid,None)
