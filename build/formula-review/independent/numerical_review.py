import os,sys,json,hashlib,copy,tempfile
from pathlib import Path
from decimal import Decimal
sys.path.insert(0,str(Path.cwd()))
from fastapi import FastAPI
from fastapi.testclient import TestClient
from formula_registry.store import Registry
from formula_registry.api import router
out=Path('build/formula-review/independent'); source=Path('/tmp/formula-independent/independent.docx'); tmp=Path(tempfile.mkdtemp(prefix='independent-numeric-'));os.environ['FORMULA_REGISTRY_DB']=str(tmp/'registry.sqlite3')
r=Registry();app=FastAPI();app.include_router(router);client=TestClient(app); results=[];approved=[]
def check(name,ok,actual):
 results.append(dict(name=name,passed=bool(ok),actual=actual))
def request(method,id,suffix='',**kw):return getattr(client,method)('/api/formula-drafts/'+id+suffix,**kw)
for row in json.loads((out/'numerical_cases.json').read_text()):
 variables=[]
 for data in row['variables']:
  v=dict(key=data[0],label='Independent input '+data[0],unit=data[1],kind=data[2] if len(data)>2 else 'scalar')
  if v['kind']=='series':v.update(min_items=2,max_items=6)
  if len(data)>3:v.update(min=data[3],max=data[4])
  variables.append(v)
 p=dict(title=row['id'],expression=row['expression'],unit=row['unit'],variables=variables,conditions=[dict(key='checked',label='Synthetic independent reference checked')],test_cases=[dict(inputs=row['inputs'],expected=row['expected'],unit=row['unit'])])
 r.add(source,'numeric',hashlib.sha256(source.read_bytes()).hexdigest(),[dict(source=dict(fid=row['id'],section='independent',context='Synthetic only',latex=row['expression']),proposal=p,warnings=[])])
 d=next(d for d in r.list('numeric') if d['source']['fid']==row['id']);a=request('post',d['id'],'/approve',json=dict(revision=1,reviewer='Independent synthetic tester',note='Answer fixed in JSON before invocation',confirmed=True));assert a.status_code==200,a.text;d=a.json();approved.append(d)
 calc=request('post',d['id'],'/calculate',json=dict(revision=d['revision'],inputs=row['inputs'],confirmations={'checked':True})); actual=calc.json();check(row['id'],calc.status_code==200 and Decimal(actual['value'])==Decimal(row['expected']),actual)
d=approved[0];base=dict(revision=d['revision'],inputs={'a':{'value':'7','unit':'Pa'},'b':{'value':'3','unit':'Pa'}},confirmations={'checked':True})
for label,mut in [('nan',lambda p:p['inputs']['a'].update(value='NaN')),('infinity',lambda p:p['inputs']['a'].update(value='Infinity')),('oversized',lambda p:p['inputs']['a'].update(value='1e31')),('numeric_json',lambda p:p['inputs']['a'].update(value=3)),('wrong_unit',lambda p:p['inputs']['a'].update(unit='mL')),('missing_variable',lambda p:p['inputs'].pop('b')),('extra_variable',lambda p:p['inputs'].update(c={'value':'1','unit':'Pa'})),('condition_false',lambda p:p.update(confirmations={'checked':False})),('condition_string',lambda p:p.update(confirmations={'checked':'true'})),('forged_status',lambda p:p.update(status='approved')),('old_revision',lambda p:p.update(revision=1))]:
 payload=copy.deepcopy(base);mut(payload);res=request('post',d['id'],'/calculate',json=payload);check('block_'+label,res.status_code in [409,422],res.status_code)
for idx,label,inputs in [(5,'slope_constant',{'x':{'value':['2','2'],'unit':'1'},'y':{'value':['1','3'],'unit':'1'}}),(7,'negative_sqrt',{'a':{'value':'-1','unit':'1'}}),(12,'below_min',{'a':{'value':'-4.001','unit':'1'}}),(13,'above_max',{'a':{'value':'9.001','unit':'1'}}),(3,'series_empty',{'x':{'value':[],'unit':'mm'}})]:
 target=approved[idx];res=request('post',target['id'],'/calculate',json=dict(revision=target['revision'],inputs=inputs,confirmations={'checked':True}));check('block_'+label,res.status_code==422,res.status_code)
for expr in ['__import__("os").system("id")','a.__class__','sum([a,b])','a**9']:
 p=copy.deepcopy(d['proposal']);p['expression']=expr;check('block_expression_'+expr,bool(__import__('formula_registry.validation',fromlist=['validate']).validate(p)),None)
check('restart_persists',Registry().get(d['id'])['status']=='approved',None)
oldrev=d['revision'];edited=request('put',d['id'],json={'revision':oldrev,'proposal':d['proposal']});check('edit_revokes',edited.json()['status']=='pending_review',None)
check('pending_blocked',request('post',d['id'],'/calculate',json={**base,'revision':edited.json()['revision']}).status_code==409,None)
check('old_write_conflict',request('put',d['id'],json={'revision':oldrev,'proposal':d['proposal']}).status_code==409,None)
rej=request('post',d['id'],'/reject',json=dict(revision=edited.json()['revision'],reviewer='Independent',note='Synthetic rejection',confirmed=False));check('rejection_audit',rej.json()['review']['note']=='Synthetic rejection',None)
check('rejected_blocked',request('post',d['id'],'/calculate',json={**base,'revision':rej.json()['revision']}).status_code==409,None)
(out/'numerical_results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2));print(json.dumps({'passed':sum(x['passed'] for x in results),'total':len(results),'failures':[x for x in results if not x['passed']]}))
