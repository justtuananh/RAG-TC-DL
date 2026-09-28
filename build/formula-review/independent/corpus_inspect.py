import sqlite3,json,collections,hashlib
from pathlib import Path
p=Path('.formula-registry/registry.sqlite3'); before=hashlib.sha256(p.read_bytes()).hexdigest();db=sqlite3.connect('file:'+str(p)+'?mode=ro',uri=True); records=[json.loads(row[0]) for row in db.execute('select record from formulas')];db.close();summary={}
for r in records:
 k=r['source']['file'];s=summary.setdefault(k,{'total':0,'statuses':{},'with_expression':0,'without_latex':0});s['total']+=1;s['statuses'][r['status']]=s['statuses'].get(r['status'],0)+1;s['with_expression']+=bool(r['proposal'].get('expression'));s['without_latex']+=not bool(r['source'].get('latex'))
result={'files':summary,'total':len(records),'before_sha256':before,'after_sha256':hashlib.sha256(p.read_bytes()).hexdigest()};Path('build/formula-review/independent/corpus.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False))
