"""Recheck the existing 30-DOCX synthetic corpus and actual source coverage."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from unittest.mock import patch
from ingestion.extract_docx import extract_docx
from formula_lab import strategies

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'formula_lab/reports/registry-v2'

def run():
    docs=json.loads((ROOT/'formula_lab/reports/expanded-registry/corpus-manifest.json').read_text())
    rows=[];parsed={}
    for doc in docs:
        path=ROOT/doc['path']; assert hashlib.sha256(path.read_bytes()).hexdigest()==doc['sha256']
        result=extract_docx(str(path))
        parsed[doc['id']]={'math_objects':len(result.formulas),'omml':[f.latex for f in result.formulas if f.kind=='omml'], 'ole':sum(f.kind=='ole' for f in result.formulas)}
    originals={d['source']:parsed[d['id']] for d in docs if d['variant']=='original'}
    pool=[s for d in docs if d['variant']=='original' for s in parsed[d['id']]['omml']]
    for doc in docs:
        actual=parsed[doc['id']]; original=originals[doc['source']]
        if doc['variant'] in ('original','layout'): ok=actual==original
        elif doc['variant']=='missing_math':ok=actual['math_objects']==0
        elif doc['variant']=='injected':ok=actual['omml']==['P=999999']+original['omml']
        else:ok=actual['omml']==pool
        rows.append({'group':'ingestion','id':doc['id'],'pass':ok})
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp);(root/'TC_DL').mkdir()
        with patch.object(strategies,'ROOT',root):
            for doc in docs:
                shutil.copyfile(ROOT/doc['path'],root/'TC_DL'/doc['source'])
                cards=[c for c in strategies.SOURCES if c['file']==doc['source']]
                if not cards:cards=[{'id':'unregistered:'+doc['id']}]
                for card in cards:
                    expected='ready' if doc['variant']=='original' and not card['id'].startswith('unregistered') else 'blocked'
                    result=strategies.prepare(copy.deepcopy(card),'registry')
                    rows.append({'group':'source_binding','id':doc['id']+'/'+card['id'],'pass':result['status']==expected,'expected':expected,'actual':result['status']})
    inventory=json.loads((ROOT/'formula_lab/reports/expanded-registry/formula-inventory.json').read_text())
    covered=[]
    for eq in inventory:
        ids=[c['id'] for c in strategies.SOURCES if c['file']==eq['file'] and any(f['fid']==eq['fid'] for f in c['formulas'])]
        covered.append({'file':eq['file'],'fid':eq['fid'],'calculator_ids':ids,'available':bool(ids)})
    result={'original_documents':7,'synthetic_documents':23,'new_calculators':20,'total_calculators':len(strategies.SOURCES),
        'equation_occurrences':len(covered),'covered_occurrences':sum(c['available'] for c in covered),
        'coverage_fraction':sum(c['available'] for c in covered)/len(covered),
        'groups':{g:{'passed':sum(r['pass'] for r in rows if r['group']==g),'total':sum(r['group']==g for r in rows)} for g in ['ingestion','source_binding']},
        'rows':rows,'coverage':covered,'limitations':'7 independent documents; descendants do not expand formula families. OLE conversion not rerun. Occurrence coverage is not mathematical-family coverage.'}
    (OUT/'corpus-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('rows','coverage')},ensure_ascii=False,indent=2))

if __name__=='__main__':run()
