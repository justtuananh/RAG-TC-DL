import sys,os
from pathlib import Path
sys.path.insert(0,'/root/RAG-TC-DL')
root=Path('/tmp/formula-blind-audit/runtime');root.mkdir(exist_ok=True)
os.environ['FORMULA_REGISTRY_DB']=str(root/'registry.sqlite3')
import ingestion_jobs
ingestion_jobs.TC_DL_DIR=root
ingestion_jobs.OUT_DIR=root/'extracted'
import api_server,uvicorn
uvicorn.run(api_server.app,host='127.0.0.1',port=8082)
