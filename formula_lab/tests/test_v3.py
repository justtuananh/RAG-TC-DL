import copy
import json
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from formula_lab.engine import calculate, Invalid
from formula_lab import strategies
from formula_lab.v3.catalog import build, DATA

REG = json.loads((DATA/'registry.json').read_text())
CASES = json.loads((DATA/'dev-ucs.json').read_text())


@pytest.mark.parametrize('uc', CASES, ids=lambda uc:uc['id'])
def test_new_calculators_and_http_results(uc):
    from formula_lab.app import app, sessions
    card = strategies.select(uc['question'])
    assert card and card['id'] == uc['formula']
    ready = strategies.prepare(card, 'registry')
    assert ready['status'] == 'ready'
    sid = 'v3-'+uc['id']
    sessions[sid] = ready
    try:
        with TestClient(app) as client:
            response = client.post('/api/lab/calculate', json=dict(
                session_id=sid, revision='3', inputs=uc['inputs'],
                confirmations={key:True for key in ready['spec']['conditions']}))
        assert response.status_code == 200
        result = response.json()
        assert result['status'] == 'ok'
        assert abs(Decimal(result['value'])-Decimal(uc['expected'])) <= max(
            Decimal(uc['absolute_tolerance']), abs(Decimal(uc['expected']))*Decimal(uc['relative_tolerance']))
        assert (result['formula_id'],result['unit'],result['source_hash']) == (uc['formula'],uc['unit'],card['docx_sha256'])
    finally:
        sessions.pop(sid,None)


@pytest.mark.parametrize('card', strategies.V3_SOURCES, ids=lambda c:c['id'])
def test_scoped_ids_titles_evidence_and_source_tampering(card):
    for query in [card['title'], 'Công thức '+card['title']+' là gì?',
                  'QTKĐ '+card['procedure']+': '+card['formulas'][0]['fid']]:
        assert strategies.select(query)['id'] == card['id']
        assert strategies.select(query,[]) is None
        assert strategies.select(query,[{'formula_id':card['id'],'stem':card['stem']}])['id'] == card['id']
    changed=copy.deepcopy(card)
    changed['formulas'][0]['latex'] += '+1'
    assert strategies.prepare(changed,'registry')['status']=='blocked'


@pytest.mark.parametrize('query', [
    'QTKĐ 1.160: F008 trung bình chỉ thị', 'QTKĐ 1.190: F008 hệ số góc hồi quy',
    'DPI 610 QTKĐ 1.160: hệ số góc hồi quy', 'H3000 QTKĐ 1.159: sai số tuyệt đối',
    'QTKĐ 1.160: F033 và F034', 'QTKĐ 1.160: độ phân giải',
    'QTKĐ 1.159: F049', 'QTKĐ 1.190: F040', 'QTKĐ 1.190: F044',
    'QTKĐ 1.062: P001 P002', 'QTKĐ 1.061: P999', 'áp suất tuyệt đối tại đáy',
    'DPI 610: độ lặp lại', 'DPI 610: độ lặp lại chiều tăng và độ lặp lại chiều giảm',
])
def test_ambiguity_and_wrong_procedure_are_not_calculated(query):
    assert strategies.select(query) is None


@pytest.mark.parametrize('uc',CASES[::2],ids=lambda uc:uc['formula'])
def test_conditions_units_and_missing_inputs(uc):
    spec=REG[uc['formula']]
    with pytest.raises(Invalid): calculate(spec,uc['inputs'],{})
    confirms={key:True for key in spec['conditions']}
    bad=copy.deepcopy(uc['inputs']); bad.pop(next(iter(bad)))
    with pytest.raises(Invalid): calculate(spec,bad,confirms)
    bad=copy.deepcopy(uc['inputs']);bad[next(iter(bad))]['unit']='s' if spec['unit']!='s' else 'kg'
    with pytest.raises(Invalid): calculate(spec,bad,confirms)


@pytest.mark.parametrize('mu',['10','10.01','-1'])
def test_absolute_pressure_residual_bound(mu):
    spec=REG['qtkd159_f031']
    with pytest.raises(Invalid):
        calculate(spec,{'ps':{'value':'1500','unit':'Pa'},'mu':{'value':mu,'unit':'Pa'}},dict.fromkeys(spec['conditions'],True))


@pytest.mark.parametrize('pressure,expected',[('2','15000'),('5','15000'),('10','30000')])
def test_valve_tolerance_floor(pressure,expected):
    spec=REG['qtkd061_p002']
    assert Decimal(calculate(spec,{'pcd':{'value':pressure,'unit':'bar'}},dict.fromkeys(spec['conditions'],True))['value'])==Decimal(expected)


def test_builder_is_reproducible_and_refuses_mutation_before_writes(tmp_path):
    from formula_lab.v3 import catalog
    cards,reg,reviews,evidence=build(draft=True)
    assert reg==REG
    assert reviews==json.loads((DATA/'review_approvals.json').read_text())
    old_specs=catalog.specs()
    changed=[(code,n,title,expr+'+1',vs,unit,cs,aliases) for code,n,title,expr,vs,unit,cs,aliases in old_specs]
    with patch.object(catalog,'specs',return_value=changed),patch.object(catalog,'REPORT',tmp_path),pytest.raises(ValueError,match='technical review'):
        build()
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize('filename',['registry.json','conditions.json'])
def test_definition_and_condition_changes_block_prepare(filename):
    original=Path.read_text
    card=strategies.V3_SOURCES[0]
    def altered(path,*args,**kwargs):
        raw=original(path,*args,**kwargs)
        if path==DATA/filename:
            value=json.loads(raw)
            if filename=='registry.json':value[card['id']]['expression']='rho*g*h+1'
            else:value['v3_height_sign']='Automatically applicable'
            return json.dumps(value)
        return raw
    with patch.object(Path,'read_text',altered):
        assert strategies.prepare(card,'registry')['status']=='blocked'
