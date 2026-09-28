"""Aggregate immutable worktree artifacts; select only measured eligible strategies."""
import collections
import hashlib
import json
from pathlib import Path
import shutil
from statistics import median

ROOT=Path(__file__).resolve().parent.parent
WORKTREES=ROOT.parent/'RAG-TC-DL-worktrees'

def main():
    compared={}; hashes=set();source_hashes=set()
    for name in ['llm','parser','registry']:
        src=WORKTREES/name/'formula_lab/reports'/name/'holdout'
        manifest=json.loads((src/'manifest.json').read_text());hashes.add(manifest['uc_hash']);source_hashes.add(manifest['source_hash'])
        rows=json.loads((src/'results.json').read_text());end=[r for r in rows if r['mode']=='e2e']
        per_id=collections.defaultdict(list)
        for r in end: per_id[r['id']].append(r)
        totals=json.loads((src/'summary.json').read_text())
        usage=[];latencies=[]
        for f in src.glob('round-*/definitions.json'):
            for d in json.loads(f.read_text()):
                latencies.append(d.get('prepare_seconds',0))
                if d.get('metadata'): usage.append(d['metadata'])
        complete=len(per_id)==60 and all(len(v)==3 for v in per_id.values()) and len(end)==180
        cost_values=[u.get('response_cost') for u in usage if u.get('response_cost') is not None]
        x={'commit':manifest['commit'],'complete':complete,**totals,'stable_pass_unique':sum(all(r['pass'] for r in v) for v in per_id.values()),
           'unstable_unique':sum(len({r['pass'] for r in v})>1 for v in per_id.values()),
           'valid_pass':sum(r['pass'] for r in end if r['expected']=='ok'),
           'valid_total':sum(r['expected']=='ok' for r in end),
           'definition_calls':len(usage),'reported_cost_usd':sum(cost_values) if cost_values else None,
           'tokens':sum(u.get('usage',{}).get('total_tokens',0) for u in usage),
           'median_prepare_seconds':median(latencies),
           'failures':[{'id':r['id'],'round':r['round'],'unsafe':r.get('unsafe',False),'actual':r['actual'],'browser':r.get('browser')} for r in end if not r['pass']]}
        x['eligible']=complete and x['e2e']['unsafe']==0 and x['e2e']['infrastructure']==0
        compared[name]=x
        dst=ROOT/'formula_lab/reports'/name/'holdout';shutil.copytree(src,dst,dirs_exist_ok=True)
    assert len(hashes)==len(source_hashes)==1, 'Different datasets: comparison invalid'
    eligible=sorted((n for n in compared if compared[n]['eligible']),key=lambda n:compared[n]['e2e']['passed'],reverse=True)
    winner=eligible[0] if eligible else None
    if len(eligible)>1 and (compared[eligible[0]]['e2e']['passed']-compared[eligible[1]]['e2e']['passed'])/180<.05:
        winner=None; decision='Need 30 new tie-break UC; no winner yet.'
    else: decision='Highest eligible pass rate with zero observed unsafe outputs.' if winner else 'No eligible strategy.'
    report={'dataset_sha256':next(iter(hashes)),'winner':winner,'decision':decision,'strategies':compared}
    dest=ROOT/'formula_lab/reports';(dest/'comparison.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    lines=['# DOCX formula experiment results','',f'Selected strategy: **{winner or "none"}**. {decision}','',
           '60 unique held-out UC × 3 runs per strategy. Repeated runs are not independent new cases. 60 development UC were excluded from the selection score.','',
           '| Strategy | E2E pass | Unsafe outputs | Valid UC pass | Stable pass / 60 | Eligible |',
           '|---|---:|---:|---:|---:|---|']
    for n,x in compared.items():
        e=x['e2e'];lines.append(f"| {n} | {e['passed']}/{e['total']} ({100*e['passed']/e['total']:.1f}%) | {e['unsafe']} | {x['valid_pass']}/{x['valid_total']} | {x['stable_pass_unique']} | {x['eligible']} |")
    lines+=['','## By group','','| Group | LLM | Parser | Registry |','|---|---:|---:|---:|']
    for g in compared['registry']['e2e']['groups']:
        cells=[f"{compared[n]['e2e']['groups'][g]['passed']}/30" for n in ['llm','parser','registry']]
        lines.append('| '+g+' | '+' | '.join(cells)+' |')
    lines+=['','## Reproducibility and limits','',
            '- Models: Qwen3 30B A3B Instruct 2507 and text-embedding-3-small through LiteLLM/OpenRouter. Embedding dimension 1536. Reranker disabled for all strategies.',
            '- All seven DOCX are indexed (141 text windows). Six curated calculators from three DOCX are the evaluated scope. The rest of the corpus acts as retrieval distractors.',
            '- This is a controlled calculator-definition study, not a benchmark of general free-form chat or independent end-to-end DOCX extraction. Candidate formula identification and source excerpts are curated/shared. A full-corpus dense/BM25 retrieval gate checks that the source document is retrieved; section/formula selection is a common rule-based router.',
            '- Isolated rows bypass retrieval. E2E rows include live retrieval; browser assertions replay definitions produced in that round and call the real calculator ASGI endpoint. They do not re-call the LLM for each click.',
            '- Registry expressions were technically checked against original DOCX XML/rendered pages, not approved by a metrology specialist. Hand preparation effort and small known-formula coverage are the trade-off for its result.',
            '- Source-corruption UC are synthetic fault injections. They test behavior when a plausible but unapproved formula arrives; they do not measure the frequency of actual ingestion errors.',
            '- User declarations of conditions are trusted; physically plausible mistyped input cannot be reliably detected. No pass/fail metrology decision is implemented.',
            '- Formula-source templates, unit vocabulary, input policies and preparer prompts were frozen before held-out evaluation. Gold numeric answers use independent Decimal arithmetic. All strategies share the bounded calculation engine.',
            '- Rates apply only to these cases, model/provider configuration and document versions. Zero observed unsafe outputs is not a guarantee of correctness on unseen formulas.',
            '', '## LLM usage (definition preparation only)','']
    for n,x in compared.items(): lines.append(f"- {n}: {x['definition_calls']} calls; {x['tokens']} tokens; provider-reported cost {x['reported_cost_usd']}; median prepare time {x['median_prepare_seconds']:.3f}s.")
    lines+=['','Embedding and development-call costs are not included in the usage subtotal. Detailed manifests, generated definitions, screenshots and per-UC results are retained in each strategy folder.','', '## Failure examples','']
    for n,x in compared.items():
        seen=set()
        for f in x['failures']:
            if f['id'] in seen: continue
            seen.add(f['id'])
            lines.append(f"- {n} / {f['id']}: unsafe={f['unsafe']}; actual={json.dumps(f['actual'],ensure_ascii=False)}")
            if len(seen)>=5: break
    (dest/'COMPARISON.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'winner':winner,'scores':{n:x['e2e'] for n,x in compared.items()}},ensure_ascii=False))
if __name__=='__main__':main()
