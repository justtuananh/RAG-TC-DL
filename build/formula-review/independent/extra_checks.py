from pathlib import Path
import requests,json,yaml,shutil
out=Path('build/formula-review/independent');b='http://127.0.0.1:8081';results={}
r=requests.post(b+'/api/chat/stream',json={'message':'Tính áp suất với a=12 Pa và b=4 Pa'});results['chat']={'status':r.status_code,'sse':r.text,'guidance_only':('Công thức và phê duyệt' in r.text and 'formula_id' not in r.text)}
config=yaml.safe_load(Path('docker-compose.yml').read_text());results['docker']={'yaml_parsed':isinstance(config,dict),'cli_available':shutil.which('docker'),'executed_container':False,'formula_volumes':[x for s in config['services'].values() for x in s.get('volumes',[]) if isinstance(x,str) and 'formula' in x]}
# Explicitly use fake PDF: endpoint must decline unsupported extraction without executing it.
u=requests.post(b+'/api/documents/upload',files={'file':('unsupported.pdf',b'%PDF-1.4\n%%EOF')});doc=u.json()['id'];r=requests.post(b+f'/api/documents/{doc}/formula-drafts/generate');results['pdf']={'status':r.status_code,'body':r.json()}
(out/'extra-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2));print(json.dumps(results,ensure_ascii=False))
