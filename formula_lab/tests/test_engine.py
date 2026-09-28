import copy
import json
from decimal import Decimal
import pytest
from formula_lab.engine import calculate,expression,number,Invalid
from formula_lab.provider import DATA
from formula_lab.strategies import prepare,select,SOURCES

CASES=json.loads((DATA/'ucs.json').read_text())
REG=json.loads((DATA/'registry.json').read_text())

@pytest.mark.parametrize('text',["__import__('os').system('true')",'x.__class__','x[0]','2**100000','sum(x)','[x for x in range(10)]'])
def test_no_code_execution(text):
    with pytest.raises(Invalid): expression(text,{'x':Decimal(2)})

@pytest.mark.parametrize('value',['NaN','Infinity','1,234','','1e999','1;1',True,1])
def test_number_validation(value):
    with pytest.raises(Invalid): number(value)

def test_unit_normalization():
    result=calculate(REG['valve'],{'pm':{'value':'103','unit':'kPa'},'pcd':{'value':'1','unit':'bar'}},{})
    assert Decimal(result['value'])==3000

def test_registry_dev_cases():
    for c in CASES:
        if c['split']!='dev' or c['group'] not in ('valid','input','boundary'): continue
        if c['expect']=='invalid':
            with pytest.raises(Invalid): calculate(REG[c['formula']],c['inputs'],c['confirmations'])
        else:
            r=calculate(REG[c['formula']],c['inputs'],c['confirmations'])
            assert abs(Decimal(r['value'])-Decimal(c['result']))<=Decimal(c['tolerance'])

def test_source_binding():
    c=copy.deepcopy(SOURCES[0]);c['formulas'][0]['latex']='P=1'
    assert prepare(c,'registry')['status']=='blocked'

def test_ambiguous_query(): assert select('Công thức sai số là gì?') is None

def test_ast_zero_division():
    with pytest.raises(Invalid): expression('a/b',{'a':Decimal(1),'b':Decimal(0)})
