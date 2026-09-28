import os,sys,json,hashlib,datetime,copy,requests,traceback,sqlite3,time,subprocess
from pathlib import Path
from zipfile import ZipFile
from decimal import Decimal,localcontext
from concurrent.futures import ThreadPoolExecutor
from playwright.sync_api import sync_playwright
ROOT=Path('/tmp/formula-blind-audit'); runtime=ROOT/'runtime';runtime.mkdir(exist_ok=True);os.environ['FORMULA_REGISTRY_DB']=str(runtime/'registry.sqlite3');sys.path.insert(0,'/root/RAG-TC-DL')
from formula_registry.store import Registry
from formula_registry.drafts import generate_from_docx
manifest=json.loads((ROOT/'manifest.json').read_text());seal=json.loads((ROOT/'seal.json').read_text());assert hashlib.sha256((ROOT/'manifest.json').read_bytes()).hexdigest()==seal['manifest_sha256']
assert not (ROOT/'results.json').exists(),'Refuse overwrite existing results'
results=[];started=datetime.datetime.now(datetime.timezone.utc).isoformat();b='http://127.0.0.1:8082';r=Registry()
def make_doc(path,before='HOLDOUT BEFORE alpha sentinel',after='HOLDOUT AFTER omega sentinel',expr='Z=a-b'):
 with ZipFile(path,'w') as z:
  z.writestr('[Content_Types].xml','<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
  z.writestr('_rels/.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
  z.writestr('word/document.xml',f'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"><w:body><w:p><w:r><w:t>{before}</w:t></w:r></w:p><w:p><m:oMath><m:r><m:t>{expr}</m:t></m:r></m:oMath></w:p><w:p><w:r><w:t>{after}</w:t></w:r></w:p></w:body></w:document>')
source=runtime/'audit_ui.docx';make_doc(source);raw=source.read_bytes();source_hash=hashlib.sha256(raw).hexdigest()
proc=subprocess.Popen(['/root/RAG-TC-DL/.venv-formula/bin/python',str(ROOT/'server.py')],cwd='/root/RAG-TC-DL',stdout=(ROOT/'server.log').open('w'),stderr=subprocess.STDOUT)
for _ in range(60):
 try:
  if requests.get(b+'/api/health',timeout=1).status_code==200:break
 except requests.RequestException:pass
 time.sleep(.25)
else:raise RuntimeError('Harness server unavailable')
def api(method,path,payload=None):return requests.request(method,b+'/api/'+path,json=payload,timeout=20)
def make_spec(tag,expression='a',variables=None,unit='Pa',inputs=None,expected='19',conditions=None,sourcepath=source,document='holdout_numeric'):
 variables=variables or [dict(key='a',label='Synthetic pressure',unit=unit)];inputs=inputs or {'a':{'value':'19','unit':unit}};conditions=conditions or [dict(key='check_a',label='Synthetic condition A'),dict(key='check_b',label='Synthetic condition B')]
 p=dict(title=tag,expression=expression,unit=unit,variables=variables,conditions=conditions,test_cases=[dict(inputs=inputs,expected=expected,unit=unit)])
 r.add(sourcepath,document,hashlib.sha256(sourcepath.read_bytes()).hexdigest(),[dict(source=dict(fid=tag,kind='synthetic',latex=expression,section='Synthetic holdout',context='Synthetic source used only for testing'),proposal=p,warnings=[])])
 return next(x for x in r.list(document) if x['source']['fid']==tag and x['status']!='stale')
def approve(d):return api('POST','formula-drafts/'+d['id']+'/approve',dict(revision=d['revision'],reviewer='Blind holdout synthetic',note='Oracle fixed before run; synthetic only',confirmed=True))
def calc(d,inputs,checks=None):return api('POST','formula-drafts/'+d['id']+'/calculate',dict(revision=d['revision'],inputs=inputs,confirmations=checks if checks is not None else {'check_a':True,'check_b':True}))
def record(id,passed,actual=None,error=None):results.append(dict(id=id,passed=bool(passed),actual=actual,harness_error=error,at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat()))
for c in manifest['cases'][:16]:
 try:
  d=make_spec(c['id'],c['expression'],c['variables'],c['unit'],c['inputs'],c['expected']);ap=approve(d)
  if ap.status_code!=200:record(c['id'],False,{'stage':'approval','status':ap.status_code,'body':ap.json()});continue
  response=calc(ap.json(),c['inputs']);body=response.json()
  with localcontext() as ctx:
   ctx.prec=100;delta=abs(Decimal(body['value'])-Decimal(c['expected'])) if response.status_code==200 else None;tolerance=abs(Decimal(c['expected']))*Decimal(c['tolerance']['relative']);ok=response.status_code==200 and delta<=tolerance
  record(c['id'],ok,{'status':response.status_code,'body':body,'absolute_error':str(delta),'threshold':str(tolerance)})
 except Exception:record(c['id'],False,error=traceback.format_exc())
for c in manifest['cases'][16:24]:
 try:
  id=c['id'];variables=None;unit='Pa';inputs=None;expected='19'
  if id=='B01':variables=[dict(key='a',label='Pressure',unit='kPa',min='3',exclusive_min=True)];unit='kPa';inputs={'a':{'value':'4','unit':'kPa'}};expected='4'
  if id=='B02':variables=[dict(key='a',label='Length',unit='m',max='2')];unit='m';inputs={'a':{'value':'1','unit':'m'}};expected='1'
  if id=='B08':
   d=make_spec(id,'a+b',[dict(key='a',label='Pressure',unit='Pa'),dict(key='b',label='Length',unit='m')],'Pa',{'a':{'value':'1','unit':'Pa'},'b':{'value':'2','unit':'m'}},'3');res=approve(d);record(id,res.status_code==422,{'status':res.status_code,'body':res.json()});continue
  d=make_spec(id,variables=variables,unit=unit,inputs=inputs,expected=expected)
  if id in ['B05','B06','B07']:
   p=copy.deepcopy(d['proposal']);revision=d['revision']
   if id=='B05':p['variables'][0]['key']=['a']
   if id=='B06':p['test_cases'][0]['inputs']['a']['value']=['19',None]
   if id=='B07':revision=True
   res=api('PUT','formula-drafts/'+d['id'],dict(revision=revision,proposal=p));current=r.get(d['id']);ok=res.status_code==422 and current['revision']==d['revision'] and current['proposal']==d['proposal']
  else:
   ap=approve(d);assert ap.status_code==200,ap.text;d=ap.json();checks={'check_a':True,'check_b':True};testinputs={'a':{'value':'19','unit':'Pa'}}
   if id=='B01':testinputs={'a':{'value':'3000','unit':'Pa'}}
   if id=='B02':testinputs={'a':{'value':'2000','unit':'mm'}}
   if id=='B03':checks['check_a']=1
   if id=='B04':checks.pop('check_b')
   res=calc(d,testinputs,checks);ok=res.status_code==c['expected_http'] and (id!='B02' or Decimal(res.json()['value'])==2)
  record(id,ok,{'status':res.status_code,'body':res.json()})
 except Exception:record(c['id'],False,error=traceback.format_exc())
# Lifecycle four independent experiments
for c in manifest['cases'][24:28]:
 try:
  id=c['id']
  if id=='L01':
   gen=api('POST','documents/audit_ui/formula-drafts/generate');ds=api('GET','documents/audit_ui/formula-drafts').json()['drafts'];d=ds[0];ok=gen.status_code==200 and d['source']['sha256']==source_hash and d['source']['fid']=='F001' and 'HOLDOUT BEFORE alpha sentinel' in d['source']['context'] and 'HOLDOUT AFTER omega sentinel' in d['source']['context'] and d['status']=='pending_review' and d['review'] is None;actual=d
  elif id=='L02':
   path=runtime/'source_change.docx';path.write_bytes(raw);d=make_spec(id,sourcepath=path,document='source_change');d=approve(d).json();path.write_bytes(raw+b'new version');res=calc(d,{'a':{'value':'19','unit':'Pa'}});ok=res.status_code==409 and r.get(d['id'])['status']=='stale';actual={'status':res.status_code,'public_status':r.get(d['id'])['status']}
  elif id=='L03':
   path=runtime/'version_cycle.docx';path.write_bytes(raw);a=make_spec(id,sourcepath=path,document='version_cycle');a=approve(a).json();path.write_bytes(raw+b'B');bb=make_spec(id,sourcepath=path,document='version_cycle');bb=approve(bb).json();path.write_bytes(raw);aa=make_spec(id,sourcepath=path,document='version_cycle');res=calc(aa,{'a':{'value':'19','unit':'Pa'}});ok=aa['status']=='pending_review' and aa['review'] is None and res.status_code==409 and r.get(bb['id'])['status']=='stale';actual={'restored':aa,'compute_status':res.status_code,'other_status':r.get(bb['id'])['status']}
  else:
   d=make_spec(id);p1=copy.deepcopy(d['proposal']);p2=copy.deepcopy(p1);p1['title']='Concurrent winner A';p2['title']='Concurrent winner B'
   def update(p):return api('PUT','formula-drafts/'+d['id'],{'revision':d['revision'],'proposal':p})
   with ThreadPoolExecutor(2) as pool:responses=list(pool.map(update,[p1,p2]))
   winner=next((z.json() for z in responses if z.status_code==200),None);current=r.get(d['id']);ok=sorted(z.status_code for z in responses)==[200,409] and current['proposal']==winner['proposal'];actual={'statuses':[z.status_code for z in responses],'current_title':current['proposal']['title']}
  record(id,ok,actual)
 except Exception:record(c['id'],False,error=traceback.format_exc())
# UI same isolated real API, no response mocks; only target URL redirect.
try:
 with sync_playwright() as pw:
  browser=pw.chromium.launch(executable_path='/usr/bin/google-chrome',headless=True,args=['--no-sandbox']);page=browser.new_page(viewport={'width':1280,'height':900});errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.route('**/api/**',lambda route:route.continue_(url=route.request.url.replace('http://127.0.0.1:5173',b)));page.goto('http://127.0.0.1:5173',wait_until='networkidle');page.get_by_role('button',name='Tài liệu',exact=True).click();page.get_by_role('button',name='audit_ui.docx',exact=True).click();page.get_by_role('tab',name='Công thức và phê duyệt',exact=True).click();page.get_by_label('Tên công thức',exact=True).wait_for();record('U01',not errors,{'browser_errors':errors.copy()})
  page.get_by_label('Tên công thức',exact=True).fill('Unsaved holdout delta');dialogs=[]
  def cancel(d):dialogs.append(d.message);d.dismiss()
  page.on('dialog',cancel);page.get_by_role('tab').filter(has_text='Tài liệu gốc').click();ok=bool(dialogs) and page.get_by_label('Tên công thức',exact=True).input_value()=='Unsaved holdout delta';record('U02',ok,{'dialogs':dialogs,'title':page.get_by_label('Tên công thức',exact=True).input_value()});page.remove_listener('dialog',cancel)
  d=api('GET','documents/audit_ui/formula-drafts').json()['drafts'][0];proposal=copy.deepcopy(d['proposal']);proposal['title']='Remote holdout edit';remote=api('PUT','formula-drafts/'+d['id'],{'revision':d['revision'],'proposal':proposal});assert remote.status_code==200
  with page.expect_response(lambda z:z.request.method=='PUT' and '/formula-drafts/' in z.url) as response:page.get_by_role('button',name='Lưu bản nháp',exact=True).click()
  page.get_by_role('alert').wait_for();record('U03',response.value.status==409 and page.get_by_label('Tên công thức',exact=True).input_value()=='Unsaved holdout delta',{'status':response.value.status,'error':page.get_by_role('alert').inner_text(),'title':page.get_by_label('Tên công thức',exact=True).input_value()})
  page.set_viewport_size({'width':390,'height':844});page.get_by_label('Tên công thức',exact=True).focus();page.keyboard.press('Tab');metrics=page.evaluate('({width:innerWidth,scroll:document.documentElement.scrollWidth})');focus=page.get_by_label('Biểu thức tính',exact=True).evaluate('(e)=>e===document.activeElement');record('U04',metrics['scroll']<=390 and focus,{'metrics':metrics,'focus_expression':focus});page.screenshot(path=str(ROOT/'ui-mobile.png'));browser.close()
except Exception:
 error=traceback.format_exc()
 for c in manifest['cases'][28:]:
  if not any(x['id']==c['id'] for x in results):record(c['id'],False,error=error)
finally:
 proc.terminate();proc.wait(timeout=15)
actual_hashes={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in json.loads((ROOT/'implementation-before.json').read_text())};(ROOT/'implementation-after.json').write_text(json.dumps(actual_hashes,indent=2));unchanged=actual_hashes==json.loads((ROOT/'implementation-before.json').read_text());frozen={'started_utc':started,'finished_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'manifest_sha256':seal['manifest_sha256'],'implementation_unchanged':unchanged,'results':results};rawresult=json.dumps(frozen,ensure_ascii=False,indent=2).encode();(ROOT/'results.json').write_bytes(rawresult);(ROOT/'result-seal.json').write_text(json.dumps({'sha256':hashlib.sha256(rawresult).hexdigest(),'frozen_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()},indent=2));print(json.dumps({'count':len(results),'passed':sum(x['passed'] for x in results),'failed':[x['id'] for x in results if not x['passed'] and not x['harness_error']],'harness_errors':[x['id'] for x in results if x['harness_error']],'implementation_unchanged':unchanged}))
