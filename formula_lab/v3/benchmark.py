"""Public regression through live retrieval, HTTP and Chromium; never a blind holdout."""
import argparse
import copy
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[2]
DATA=ROOT/'formula_lab/data/v3'


def matches(case,result):
    return (result.get('status')=='ok' and result.get('formula_id')==case['formula']
            and result.get('unit')==case['unit']
            and abs(Decimal(result['value'])-Decimal(case['expected']))<=max(
                Decimal(case['absolute_tolerance']),abs(Decimal(case['expected']))*Decimal(case['relative_tolerance'])))


def run(url):
    health=requests.get(url+'/api/lab/info',timeout=10)
    health.raise_for_status()
    assert health.json()['strategy']=='registry'
    assert len(health.json()['documents'])==7 and len(health.json()['examples'])==47
    raw=(DATA/'dev-ucs.json').read_bytes()
    assert hashlib.sha256(raw).hexdigest()==json.loads((DATA/'UC-FREEZE.json').read_text())['sha256']
    cases=json.loads(raw)
    output=ROOT/'formula_lab/reports/registry-v3/live'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    output.mkdir(parents=True)
    rows=[]
    def record(group,id,ok,**details):
        row=dict(group=group,id=id,passed=bool(ok),**details)
        rows.append(row)
        with (output/'results.jsonl').open('a') as file:file.write(json.dumps(row,ensure_ascii=False)+'\n')
    def post(path,body):
        try:
            response=requests.post(url+path,json=body,timeout=180)
            response.raise_for_status()
            return response.json()
        except (requests.RequestException,ValueError) as exc:
            return {'status':'infrastructure_error','error_type':type(exc).__name__}
    prepared={}
    for case in cases:
        id=case['formula']
        if id not in prepared:
            prepared[id]=post('/api/lab/prepare',{'question':case['question']})
            form=prepared[id]
            record('selection',id,form.get('status')=='ready' and form['spec']['id']==id,result=form)
        form=prepared[id]
        if form.get('status')!='ready' or form['spec']['id']!=id:
            record('calculation',case['id'],False,result={'status':form.get('status'),'reason':'no_correct_form'})
            continue
        payload=dict(session_id=form['session_id'],revision=form['spec']['revision'],inputs=case['inputs'],
                     confirmations=dict.fromkeys(form['spec']['conditions'],True))
        result=post('/api/lab/calculate',payload)
        record('calculation',case['id'],matches(case,result) and result.get('source_hash')==form['source']['docx_sha256'],result=result)
        if case['id'].endswith('/anchor'):
            bad=copy.deepcopy(payload);bad['confirmations']={}
            result=post('/api/lab/calculate',bad)
            record('missing_conditions',id,result.get('status')=='invalid',result=result)
    for question in ['QTKĐ 1.160: độ phân giải','DPI 610: F040','DPI 610: F044','QTKĐ 1.159: F049',
                     'DPI 610 QTKĐ 1.160: F008','QTKĐ 1.062: P001 và P002','QTKĐ 1.063: P999']:
        result=post('/api/lab/prepare',{'question':question})
        record('unsupported_or_ambiguous',question,result.get('status') in ('clarify','blocked'),result=result)
    with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path='/usr/bin/google-chrome',headless=True,args=['--no-sandbox'])
        saved_sources=set()
        for case in cases[::2]:
            page=browser.new_page(viewport={'width':1280,'height':1000})
            errors=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            try:
                form=prepared[case['formula']]
                assert form.get('status')=='ready', 'No correct HTTP form'
                page.goto(url,wait_until='networkidle')
                page.locator('#document-filter option').nth(7).wait_for(state='attached')
                page.locator('#document-filter').select_option(form['source']['file'])
                page.locator('#examples button',has_text=form['spec']['title']).click()
                page.locator('#card').wait_for(state='visible',timeout=180000)
                assert page.locator('#title').inner_text()==form['spec']['title']
                assert page.locator('#rendered-formula .katex').count()==len(form['source']['formulas'])
                for key,entry in case['inputs'].items():
                    value=entry['value']
                    page.locator('#v-'+key).fill('\n'.join(value) if isinstance(value,list) else value)
                    page.locator('#u-'+key).fill(entry['unit'])
                for key in form['spec']['conditions']:page.locator('#c-'+key).check()
                with page.expect_response('**/api/lab/calculate') as reply:page.locator('#compute').click()
                result=reply.value.json()
                assert matches(case,result)
                page.wait_for_function("document.querySelector('#result').textContent.includes('source_hash')")
                if form['source']['file'] not in saved_sources:
                    page.screenshot(path=str(output/(case['formula']+'.png')),full_page=True)
                    saved_sources.add(form['source']['file'])
                page.locator('#v-'+next(iter(case['inputs']))).fill('7')
                assert 'cần tính lại' in page.locator('#result').inner_text()
                assert not errors
                record('browser',case['formula'],True)
            except Exception as exc:
                record('browser',case['formula'],False,error_type=type(exc).__name__,message=str(exc)[:500])
            finally:page.close()
        browser.close()
    groups={group:{'passed':sum(r['passed'] for r in rows if r['group']==group),'total':sum(r['group']==group for r in rows)}
            for group in sorted({r['group'] for r in rows})}
    runtime_files=['formula_lab/app.py','formula_lab/engine.py','formula_lab/strategies.py','formula_lab/retrieval.py',
                   'formula_lab/static/index.html','formula_lab/data/v3/sources.json','formula_lab/data/v3/registry.json',
                   'formula_lab/data/v3/conditions.json','formula_lab/data/v3/review_approvals.json']
    summary=dict(role='public_development_regression_not_independent_holdout',groups=groups,
                 original_documents=7,new_definitions=21,questions=21,numeric_cases=42,
                 cases_sha256=hashlib.sha256(raw).hexdigest(),
                 runtime_sha256={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in runtime_files},
                 incorrect_numeric_outputs=sum(r['group']=='calculation' and not r['passed'] and r.get('result',{}).get('status')=='ok' for r in rows),
                 infrastructure_records=sum(r.get('result',{}).get('status')=='infrastructure_error' for r in rows))
    (output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(output,flush=True)
    print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)
    return all(row['passed'] for row in rows)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--url',default='http://127.0.0.1:8093')
    args=parser.parse_args()
    raise SystemExit(0 if run(args.url) else 1)
