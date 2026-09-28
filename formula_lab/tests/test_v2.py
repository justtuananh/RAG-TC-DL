import copy
import json
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
import pytest
from formula_lab.engine import calculate, expression, Invalid
from formula_lab.strategies import prepare,select,V2_SOURCES,V2_DATA

REG=json.loads((V2_DATA/'registry.json').read_text())
DEV=json.loads((V2_DATA/'dev-ucs.json').read_text())

def test_twenty_catalog_titles_select_correctly():
    for c in V2_SOURCES:
        selected=select('Công thức '+c['title']+' là gì?')
        assert selected and selected['id']==c['id']
        assert prepare(selected,'registry')['status']=='ready'

@pytest.mark.parametrize('question,id',[
    ('QTKĐ 1.190: f0 qua sáu loạt đọc tại điểm 0.','dpi190_f036'),
    ('QTKĐ 1.190: độ không đảm bảo do độ lệch điểm không từ f0.','dpi190_f037'),
    ('DPI 610: u_f0 với f0','dpi190_f037'),
    ('DPI 610: u_ch từ u_ch1','dpi190_f019'),
])
def test_quantity_symbols_and_input_mentions(question,id):
    assert select(question)['id']==id

def test_separate_quantity_requests_remain_ambiguous():
    assert select('QTKĐ 1.190: tính f0 và u_f0') is None

@pytest.mark.parametrize('uc',DEV,ids=lambda c:c['id'])
def test_new_numeric_dev(uc):
    spec=REG[uc['formula']]
    r=calculate(spec,uc['inputs'],{c:True for c in spec['conditions']})
    tolerance=max(Decimal(uc['absolute_tolerance']),abs(Decimal(uc['expected']))*Decimal(uc['relative_tolerance']))
    assert abs(Decimal(r['value'])-Decimal(uc['expected']))<=tolerance
    assert r['unit']==uc['unit']

@pytest.mark.parametrize('query',[
    'QTKĐ 1.190: u_r', 'DPI 610: độ phân giải',
    'DPI 610: độ phân giải tam giác và độ phân giải chữ nhật',
    'QTKĐ 1.159: độ phân giải tam giác',
    'QTKĐ 1.190: F014', 'QTKĐ 1.190: F049', 'QTKĐ 1.190: F004',
    'QTKĐ 1.190: F034 F035', 'DPI 610 theo QTKĐ 1.071: u_ch1',
    'Công thức trung bình áp suất chuẩn',
    'DPI 610: độ lệch điểm không và độ không đảm bảo do độ lệch điểm không',
])
def test_ambiguous_unsupported_or_cross_source(query): assert select(query) is None

@pytest.mark.parametrize('text,values',[
    ('sqrt(-1)',{}),('mean(x)',{'x':[]}),('mean(x)',{'x':[Decimal(1)]*101}),
    ('slope(x,y)',{'x':[Decimal(1)]*2,'y':[Decimal(2),Decimal(3)]}),
    ('slope(x,y)',{'x':[Decimal(1),Decimal(2)],'y':[Decimal(2)]}),
    ('sqrt(x=4)',{}),('max(*x)',{'x':[Decimal(1)]}),
    ('open(x)',{'x':Decimal(1)}),('x[0]',{'x':[Decimal(1)]}),
    ('mean(x)+x',{'x':[Decimal(1)]}),('sqrt(1,2)',{}),
])
def test_bounded_functions(text,values):
    with pytest.raises(Invalid): expression(text,values)

@pytest.mark.parametrize('id,bad',[(7,[]),(7,['1,2']),(7,['1']*101),(33,['1']*9),(33,['1']*11)])
def test_series_validation(id,bad):
    spec=REG[f'dpi190_f{id:03}']; key=spec['variables'][0]['key']
    with pytest.raises(Invalid): calculate(spec,{key:{'value':bad,'unit':'Pa'}},{c:True for c in spec['conditions']})

def test_conversions_and_signed_component():
    cases=[(22,{'p':('1','kPa'),'area':('2000','mm2'),'ua':('4','mm2'),'k':('2','1')},'1'),
           (24,{'p':('0.01','bar'),'ulambda':('0.2','1/bar'),'k':('2','1')},'-1'),
           (26,{'p':('1','kPa'),'mass':('10000','g'),'um':('20','g'),'k':('2','1')},'1'),
           (31,{'rho':('1000','kg/m3'),'g':('9.8','m/s2'),'uh':('1','mm'),'k':('2','1')},'4.9')]
    for n,data,gold in cases:
        spec=REG[f'dpi190_f{n:03}']
        result=calculate(spec,{k:{'value':v,'unit':u} for k,(v,u) in data.items()},{c:True for c in spec['conditions']})
        assert Decimal(result['value'])==Decimal(gold)

def test_height_bound_uses_normalized_units():
    spec=REG['dpi190_f031'];uc=next(x for x in DEV if x['formula']==spec['id'])
    data=copy.deepcopy(uc['inputs']);data['uh']={'value':'2.01','unit':'mm'}
    with pytest.raises(Invalid): calculate(spec,data,{c:True for c in spec['conditions']})

def test_missing_applicability_is_rejected():
    for uc in DEV[::10]:
        with pytest.raises(Invalid): calculate(REG[uc['formula']],uc['inputs'],{})

def test_registry_spec_change_cannot_bypass_review():
    original=Path.read_text
    def altered(path,*a,**kw):
        raw=original(path,*a,**kw)
        if path==V2_DATA/'registry.json':
            data=json.loads(raw);data['dpi190_f001']['expression']='rho*g*h+1';return json.dumps(data)
        return raw
    with patch.object(Path,'read_text',altered):
        assert prepare(V2_SOURCES[0],'registry')['status']=='blocked'

def test_builder_rejects_changed_definition_before_writing():
    from formula_lab.v2 import catalog
    before=(V2_DATA/'registry.json').read_bytes()
    old=catalog.specs()
    changed=[(n,title,expr+'+1',vs,u,cs,al) if n==1 else (n,title,expr,vs,u,cs,al) for n,title,expr,vs,u,cs,al in old]
    with patch.object(catalog,'specs',return_value=changed),pytest.raises(ValueError,match='new technical review'):
        catalog.build()
    assert (V2_DATA/'registry.json').read_bytes()==before
