import requests,json,copy,hashlib
from pathlib import Path
from playwright.sync_api import sync_playwright
out=Path('build/formula-review/independent')
files=list(Path('formula_registry').glob('*.py'))+[Path(x) for x in ['api_server.py','ingestion_jobs.py','formula_lab/engine.py','frontend/src/components/docs/FormulaReviewPanel.tsx','frontend/src/components/docs/DocViewerPanel.tsx','frontend/src/services/formulaApi.ts','frontend/src/components/layout/Sidebar.tsx','frontend/src/store/useAppStore.ts']]
(out/'snapshot-round1.json').write_text(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},indent=2))
b='http://127.0.0.1:8081'; source=Path('/tmp/formula-review-e2e/e2e_demo.docx')
u=requests.post(b+'/api/documents/upload',files={'file':('independent.docx',source.read_bytes())});print(u.status_code,u.text)
doc=u.json().get('id') or u.json().get('file_stem');print(doc)
r=requests.post(b+f'/api/documents/{doc}/formula-drafts/generate');print(r.status_code,r.text[:150])
d=requests.get(b+f'/api/documents/{doc}/formula-drafts').json()['drafts'][0]
(out/'initial-draft.json').write_text(json.dumps(d,ensure_ascii=False,indent=2))
p=copy.deepcopy(d['proposal']);p['variables']=None
r=requests.put(b+'/api/formula-drafts/'+d['id'],json={'revision':d['revision'],'proposal':p}); print(r.status_code,r.text[:250])
with sync_playwright() as pw:
 br=pw.chromium.launch(executable_path='/usr/bin/google-chrome',args=['--no-sandbox']);page=br.new_page(viewport={'width':1440,'height':1000});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.route('**/api/**',lambda route:route.continue_(url=route.request.url.replace('http://127.0.0.1:5173',b)))
 page.goto('http://127.0.0.1:5173',wait_until='networkidle');page.get_by_role('button',name='Tài liệu',exact=True).click();page.get_by_role('button',name='independent.docx',exact=True).click();page.get_by_role('tab',name='Công thức và phê duyệt',exact=True).click();page.wait_for_timeout(1500);page.screenshot(path=str(out/'malformed-crash.png'))
 evidence={'put_status':r.status_code,'body':r.json(),'browser_errors':errors,'body_text':page.locator('body').inner_text()};(out/'malformed-repro.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2));print(json.dumps(evidence,ensure_ascii=False)[:1200]);br.close()
# restore temporary record for later UI work
current=requests.get(b+'/api/formula-drafts/'+d['id']).json();requests.put(b+'/api/formula-drafts/'+d['id'],json={'revision':current['revision'],'proposal':d['proposal']})
