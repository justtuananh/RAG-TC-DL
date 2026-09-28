"""Live HTTP + real Chromium registry evaluation. No replay/mocked retrieval responses."""
import argparse
import copy
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import requests
from formula_lab.strategies import SOURCES,prepare

ROOT=Path(__file__).resolve().parents[2]
DATA=ROOT/'formula_lab/data/v2'

def matches(uc,result):
    if result.get('status')!='ok' or result.get('formula_id')!=uc['formula'] or result.get('unit')!=uc['unit']: return False
    return abs(Decimal(result['value'])-Decimal(uc['expected']))<=max(Decimal(uc['absolute_tolerance']),abs(Decimal(uc['expected']))*Decimal(uc['relative_tolerance']))

def run(split,url,regression=False):
    # Abort before recording model/registry scores when the server is still starting.
    health=requests.get(url+'/api/lab/info',timeout=10)
    health.raise_for_status()
    assert health.json()['strategy']=='registry' and len(health.json()['examples'])==26
    cases=json.loads((DATA/(split+'-ucs.json')).read_text())
    frozen=json.loads((DATA/'UC-FREEZE.json').read_text())
    assert hashlib.sha256((DATA/(split+'-ucs.json')).read_bytes()).hexdigest()==frozen['hashes'][split+'-ucs.json']
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out=ROOT/'formula_lab/reports/registry-v2'/(split+'-regression' if regression else split)/stamp;out.mkdir(parents=True)
    rows=[]; prepared={}
    def record(group,id,passed,**data):rows.append({'group':group,'id':id,'pass':bool(passed),**data})
    def post(path,payload):
        try:
            response=requests.post(url+path,json=payload,timeout=180)
            try: data=response.json()
            except ValueError: data={'status':'infrastructure_error'}
            if response.status_code>=500: data={'status':'infrastructure_error','http_status':response.status_code}
            return data
        except requests.RequestException as e:return {'status':'infrastructure_error','error_type':type(e).__name__}
    for uc in cases:
        id=uc['formula']
        if id not in prepared:
            pr=post('/api/lab/prepare',{'question':uc['question']});prepared[id]=pr
            record('retrieval_and_selection',id,pr.get('status')=='ready' and pr.get('spec',{}).get('id')==id,
                   question=uc['question'],status=pr.get('status'),selected=pr.get('spec',{}).get('id'),hits=pr.get('retrieval_evidence',[]),
                   wrong_ready=pr.get('status')=='ready' and pr.get('spec',{}).get('id')!=id)
        pr=prepared[id]
        if pr.get('status')!='ready' or pr.get('spec',{}).get('id')!=id:
            record('valid_calculation',uc['id'],False,status='infrastructure_error' if pr.get('status')=='infrastructure_error' else 'no_correct_form',unsafe=False);continue
        body={'session_id':pr['session_id'],'revision':pr['spec']['revision'],'inputs':uc['inputs'],
              'confirmations':{c:True for c in pr['spec']['conditions']},'request_id':uc['id']}
        result=post('/api/lab/calculate',body)
        ok=matches(uc,result)
        record('valid_calculation',uc['id'],ok,expected=uc['expected'],result=result,unsafe=result.get('status')=='ok' and not ok)
        if uc['id'].endswith('-00'):
            key=next(iter(uc['inputs'])); faults=[]
            missing=copy.deepcopy(body);del missing['inputs'][key];faults.append(('missing',missing))
            blank=copy.deepcopy(body);blank['inputs'][key]['value']='';faults.append(('blank',blank))
            unit=copy.deepcopy(body);unit['inputs'][key]['unit']='invalid';faults.append(('unit',unit))
            malformed=copy.deepcopy(body);malformed['inputs'][key]['unit']={};faults.append(('unit_type',malformed))
            cond=copy.deepcopy(body);cond['confirmations']={};faults.append(('conditions',cond))
            injection=copy.deepcopy(body);injection['inputs'][key]['value']='__import__("os")';faults.append(('injection',injection))
            spec=pr['spec']
            for v in spec['variables']:
                if v.get('exclusive_min'):
                    bad=copy.deepcopy(body);bad['inputs'][v['key']]={'value':'0','unit':v['unit']};faults.append(('zero_'+v['key'],bad))
                if v.get('kind')=='series':
                    bad=copy.deepcopy(body);bad['inputs'][v['key']]['value']=[];faults.append(('empty_'+v['key'],bad))
                    bad=copy.deepcopy(body);bad['inputs'][v['key']]['value']=['1']*101;faults.append(('long_'+v['key'],bad))
            if id=='dpi190_f009':
                bad=copy.deepcopy(body);bad['inputs']['xs']['value']=['1','1','1'];faults.append(('constant_x',bad))
                bad=copy.deepcopy(body);bad['inputs']['ys']['value']=['1','2'];faults.append(('unequal_pairs',bad))
            if id=='dpi190_f033':
                bad=copy.deepcopy(body);bad['inputs']['components']['value']=['1']*9;faults.append(('missing_component',bad))
            for label,payload in faults:
                result=post('/api/lab/calculate',payload)
                record('invalid_input',id+'/'+label,result.get('status')=='invalid',result=result,unsafe=result.get('status')=='ok')
            card=copy.deepcopy(next(c for c in SOURCES if c['id']==id))
            card['formulas'][0]['latex']+=' + 1'
            result=prepare(card,'registry')
            record('source_mutation_isolated',id,result['status']=='blocked',result=result)
    unsupported=[
        'QTKĐ 1.190: độ phân giải', 'DPI 610: u_r',
        'DPI 610: độ phân giải tam giác và độ phân giải chữ nhật',
        'QTKĐ 1.190: F014', 'QTKĐ 1.190: F049', 'QTKĐ 1.190: F040',
        'QTKĐ 1.160: độ phân giải tam giác', 'QTKĐ 1.159: u_ch1',
        'Tính hệ số góc hồi quy', 'DPI 610 theo QTKĐ 1.071: u_amb',
        'QTKĐ 1.190: F034 và F035', 'DPI 610: F999',
    ]
    for i,q in enumerate(unsupported):
        result=post('/api/lab/prepare',{'question':q})
        record('ambiguous_or_unsupported',f'R{i:02}',result.get('status') in ('clarify','blocked'),question=q,status=result.get('status'),wrong_ready=result.get('status')=='ready')
    # Real browser -> live HTTP server -> live retrieval -> registry -> calculator.
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path='/usr/bin/google-chrome',headless=True,args=['--no-sandbox'])
        for uc in cases[::10]:
            page=browser.new_page(); errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            try:
                page.goto(url,wait_until='networkidle');page.locator('#question').fill(uc['question'])
                with page.expect_response('**/api/lab/prepare',timeout=180000) as response:page.locator('#ask').click()
                pr=response.value.json()
                assert pr.get('status')=='ready' and pr['spec']['id']==uc['formula'], 'Wrong/no calculator'
                page.locator('#card').wait_for(state='visible')
                assert page.locator('#rendered-formula .katex').count()==len(pr['source']['formulas']), 'Formula display fallback'
                for v in pr['spec']['variables']:
                    item=uc['inputs'][v['key']]; raw=item['value']
                    page.locator('#v-'+v['key']).fill('\n'.join(raw) if isinstance(raw,list) else raw)
                    page.locator('#u-'+v['key']).fill(item['unit'])
                for cond in pr['spec']['conditions']:page.locator('#c-'+cond).check()
                with page.expect_response('**/api/lab/calculate') as response:page.locator('#compute').click()
                result=response.value.json();assert matches(uc,result),'Wrong numerical result'
                assert result['source_hash']==pr['source']['docx_sha256']
                page.wait_for_function("document.querySelector('#result').textContent.includes('source_hash')")
                if uc['formula'] in ('dpi190_f009','dpi190_f033','dpi190_f034','dpi190_f005'):
                    page.screenshot(path=str(out/(uc['formula']+'.png')),full_page=True)
                first=pr['spec']['variables'][0]['key'];page.locator('#v-'+first).fill('7')
                assert 'cần tính lại' in page.locator('#result').inner_text()
                page.locator('#restore').click()
                stored=uc['inputs'][first]['value'];expected='\n'.join(stored) if isinstance(stored,list) else stored
                assert page.locator('#v-'+first).input_value()==expected
                assert all(not page.locator('#c-'+c).is_checked() for c in pr['spec']['conditions'])
                assert not errors
                record('browser_e2e',uc['formula'],True)
            except Exception as exc:
                record('browser_e2e',uc['formula'],False,error=type(exc).__name__+': '+str(exc)[:300])
            finally:page.close()
        browser.close()
    groups={g:{'passed':sum(r['pass'] for r in rows if r['group']==g),'total':sum(r['group']==g for r in rows)} for g in sorted({r['group'] for r in rows})}
    valid=[r for r in rows if r['group']=='valid_calculation']
    selection=[r for r in rows if r['group']=='retrieval_and_selection']
    summary={'split':split,'evaluation_role':'regression_on_seen_cases' if regression else 'initial_evaluation',
        'groups':groups,'total':len(rows),'passed':sum(r['pass'] for r in rows),
        'supported_formula_selection_rate':sum(r['pass'] for r in selection)/len(selection),
        'useful_answer_rate':sum(r['pass'] for r in valid)/len(valid),
        'false_refusals':sum(r.get('status')=='no_correct_form' or r.get('result',{}).get('status') in ('invalid','blocked','clarify') for r in valid),
        'unsafe_numeric_outputs':sum(bool(r.get('unsafe')) for r in rows),
        'wrong_ready_forms':sum(bool(r.get('wrong_ready')) for r in rows),
        'infrastructure_affected_cases':sum(r.get('status')=='infrastructure_error' or r.get('result',{}).get('status')=='infrastructure_error' for r in rows),
        'uc_hash':frozen['hashes'][split+'-ucs.json'],
        'runtime_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['formula_lab/engine.py','formula_lab/strategies.py','formula_lab/retrieval.py','formula_lab/app.py','formula_lab/static/index.html','formula_lab/data/v2/registry.json']},
        'scope':'Actual HTTP and Chromium with OpenRouter embedding retrieval; deterministic registry, no chat LLM. Source mutation cases are isolated.'}
    (out/'results.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
    (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(str(out));print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--split',choices=['dev','holdout'],required=True);parser.add_argument('--url',default='http://127.0.0.1:8093')
    parser.add_argument('--regression',action='store_true',help='Label a rerun after inspecting failures as regression, not fresh holdout')
    args=parser.parse_args();run(args.split,args.url,args.regression)
