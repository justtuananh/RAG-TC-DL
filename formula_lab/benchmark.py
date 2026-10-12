"""Frozen UC harness. No LLM judge; independent Decimal gold and browser assertions."""
import argparse
import copy
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import time
from .provider import DATA, ROOT, RUNTIME, CONFIG
from .strategies import SOURCES, select, prepare
from .engine import calculate, Invalid
from .retrieval import Retriever


def mutated(card,kind):
    c=copy.deepcopy(card)
    if kind=='operator':
        old=c['formulas'][0]['latex'];rhs=old.split('=',1)[1]
        new=old.replace('=', '= -(',1)+')'
        c['formulas'][0]['latex']=new;c['context']=c['context'].replace(old,new)
    elif kind=='missing_definition': c['context']='\n'.join(f['latex'] for f in c['formulas'])
    elif kind=='version': c['revision']='999'
    elif kind=='wrong_source': c['docx_sha256']='0'*64
    elif kind=='missing_formula':
        for f in c['formulas']: c['context']=c['context'].replace(f['latex'],'[công thức không đọc được]')
        c['formulas']=[]
    return c


def score(uc,prepared):
    if prepared['status']=='infrastructure_error': return {'pass':False,'infrastructure':True,'actual':prepared}
    expected=uc['expect']
    if prepared['status']!='ready':
        ok=(expected=='clarify' and prepared['status']=='clarify') or (expected=='blocked' and prepared['status']=='blocked')
        return {'pass':ok,'unsafe':False,'actual':prepared}
    try: actual=calculate(prepared['spec'],uc['inputs'],uc['confirmations'])
    except (Invalid,KeyError,TypeError) as e: actual={'status':'invalid','message':str(e)}
    ok=False
    if expected=='invalid': ok=actual['status']=='invalid'
    elif expected=='ok' and actual['status']=='ok':
        ok=(actual['formula_id']==uc['formula'] and actual['unit']==uc['unit']
            and abs(Decimal(actual['value'])-Decimal(uc['result']))<=Decimal(uc['tolerance']))
    elif expected=='blocked': ok=False # must reject corrupted source during preparation
    return {'pass':ok,'unsafe':actual['status']=='ok' and not ok,'actual':actual}


def browser_cases(items,prepared_map,report_dir):
    """Real Chromium UI + actual ASGI calculate endpoint. Prep responses replay THIS run's live definitions.
    Network/routing and definition generation are independently measured in e2e rows.
    """
    from playwright.sync_api import sync_playwright
    from fastapi.testclient import TestClient
    from .app import app,sessions
    with TestClient(app) as client, sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path='/usr/bin/google-chrome',headless=True,args=['--no-sandbox'])
        results={}
        for uc in items:
            prepared=prepared_map[uc['id']]
            if prepared['status']!='ready': results[uc['id']]={'pass':False,'reason':'no_form'};continue
            sid=uc['id'];sessions[sid]=copy.deepcopy(prepared)
            response={**prepared,'session_id':sid}
            page=browser.new_page();held=[]
            def route(r):
                path=r.request.url.split('http://lab.test',1)[-1]
                body=r.request.post_data_json if r.request.method=='POST' else None
                if path=='/api/lab/prepare': r.fulfill(json=response);return
                if path=='/api/lab/calculate' and uc['ui_action']=='late_response':
                    held.append((r,body));return
                resp=client.request(r.request.method,path,json=body) if body else client.get(path)
                r.fulfill(status=resp.status_code,body=resp.content,headers={'content-type':resp.headers.get('content-type','application/json')})
            page.route('http://lab.test/**',route)
            try:
                page.goto('http://lab.test/')
                page.locator('#question').fill(uc['question']);page.locator('#ask').click()
                page.locator('#card').wait_for(state='visible')
                for v in prepared['spec']['variables']:
                    x=uc['inputs'].get(v['key'])
                    if not x: raise AssertionError('Form has an unexpected variable')
                    page.locator('#v-'+v['key']).fill(x['value']);page.locator('#u-'+v['key']).fill(x['unit'])
                for cond in prepared['spec'].get('conditions',[]):
                    if uc['confirmations'].get(cond): page.locator('#c-'+cond).check()
                first=prepared['spec']['variables'][0]['key']
                action=uc['ui_action']
                if action=='revision': sessions[sid]['spec']['revision']='changed'
                page.locator('#compute').click()
                if action=='late_response':
                    page.wait_for_timeout(100)
                    page.locator('#v-'+first).fill('7')
                    if not held: raise AssertionError('No calculation request')
                    for r,body in held:
                        resp=client.post('/api/lab/calculate',json=body)
                        r.fulfill(status=resp.status_code,body=resp.content,headers={'content-type':'application/json'})
                    page.wait_for_timeout(50)
                    assert 'cần tính lại' in page.locator('#result').inner_text()
                elif action=='revision':
                    page.wait_for_function("document.querySelector('#result').textContent.includes('Phiên bản')")
                else:
                    page.wait_for_function("document.querySelector('#result').textContent !== 'Đang tính…'")
                    raw=page.locator('#result').inner_text();actual=json.loads(raw)
                    assert actual['status']=='ok' and actual['formula_id']==uc['formula']
                    assert abs(Decimal(actual['value'])-Decimal(uc['result']))<=Decimal(uc['tolerance'])
                    assert actual['unit']==uc['unit']
                    if action=='edit_invalidates':
                        page.locator('#v-'+first).fill('7'); assert 'cần tính lại' in page.locator('#result').inner_text()
                    elif action=='restore':
                        page.locator('#v-'+first).fill('7');page.locator('#restore').click()
                        assert page.locator('#v-'+first).input_value()==uc['inputs'][first]['value']
                        assert 'cần tính lại' in page.locator('#result').inner_text()
                    elif action=='source_binding':
                        assert actual['source_hash']==prepared['source']['docx_sha256']
                        assert prepared['source']['file'] in page.locator('#source').inner_text()
                if not (report_dir/'ui.png').exists(): page.screenshot(path=str(report_dir/'ui.png'),full_page=True)
                results[uc['id']]={'pass':True}
            except Exception as e: results[uc['id']]={'pass':False,'reason':type(e).__name__+': '+str(e)[:180]}
            finally: page.close();sessions.pop(sid,None)
        browser.close()
        return results


def run(split,rounds):
    all_cases=json.loads((DATA/'ucs.json').read_text())
    cases=[c for c in all_cases if c['split']==split]
    out=ROOT/'formula_lab/reports'/CONFIG['strategy']/split;out.mkdir(parents=True,exist_ok=True)
    uc_hash=hashlib.sha256((DATA/'ucs.json').read_bytes()).hexdigest()
    manifest={'config':CONFIG,'uc_hash':uc_hash,'source_hash':hashlib.sha256((DATA/'sources.json').read_bytes()).hexdigest(),
              'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
              'packages':{n:importlib.metadata.version(n) for n in ['litellm','sympy','qdrant-client','fastapi','playwright']},
              'split':split,'rounds':rounds,'policy':'No answer cache across rounds; definitions reused within a round for identical source payloads.'}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2))
    retriever=Retriever();retriever.index()
    # Freeze actual dense/BM25 retrieval results, shared across strategies through vector cache only.
    queries={q:retriever.search(q) for q in sorted({c['question'] for c in cases})}
    retriever.client.close()
    rows=[]
    for repeat in range(1,rounds+1):
        jobs={};bindings={}
        for mode in ['isolated','e2e']:
            for uc in cases:
                card=select(uc['question'],queries[uc['question']] if mode=='e2e' else None)
                if uc.get('mutation') and card: card=mutated(card,uc['mutation'])
                key=json.dumps(card,sort_keys=True,ensure_ascii=False)
                jobs[key]=card;bindings[(mode,uc['id'])]=key
        def job(kv):
            key,card=kv;start=time.monotonic()
            result=prepare(card);result['prepare_seconds']=time.monotonic()-start
            return key,result
        with ThreadPoolExecutor(max_workers=3 if CONFIG['strategy']=='llm' else 1) as pool:
            prepared=dict(pool.map(job,jobs.items()))
        round_dir=out/f'round-{repeat}';round_dir.mkdir(exist_ok=True)
        (round_dir/'definitions.json').write_text(json.dumps(list(prepared.values()),ensure_ascii=False,indent=2))
        for mode in ['isolated','e2e']:
            for uc in cases:
                result=prepared[bindings[(mode,uc['id'])]]
                row={'id':uc['id'],'group':uc['group'],'mode':mode,'round':repeat,'expected':uc['expect'],**score(uc,result)}
                rows.append(row)
        ui=browser_cases([c for c in cases if c['group']=='ui'],{c['id']:prepared[bindings[('e2e',c['id'])]] for c in cases},round_dir)
        for row in rows:
            if row['round']==repeat and row['mode']=='e2e' and row['group']=='ui':
                row['browser']=ui[row['id']];row['pass']=row['pass'] and ui[row['id']]['pass']
        (out/'results.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
        print(json.dumps({'strategy':CONFIG['strategy'],'split':split,'round':repeat,'done':True}),flush=True)
    summary={}
    for mode in ['isolated','e2e']:
        subset=[r for r in rows if r['mode']==mode]
        summary[mode]={'passed':sum(r['pass'] for r in subset),'total':len(subset),
                       'unsafe':sum(r.get('unsafe',False) for r in subset),
                       'infrastructure':sum(r.get('infrastructure',False) for r in subset),
                       'groups':{g:{'passed':sum(r['pass'] for r in subset if r['group']==g),'total':sum(r['group']==g for r in subset)} for g in sorted({r['group'] for r in subset})}}
    (out/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--split',choices=['dev','holdout'],default='dev');p.add_argument('--rounds',type=int,default=1)
    a=p.parse_args();run(a.split,a.rounds)
