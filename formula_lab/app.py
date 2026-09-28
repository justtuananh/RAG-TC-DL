"""Run: python -m uvicorn formula_lab.app:app --port 8091"""
import copy
import hashlib
import json
import secrets
from threading import Lock
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from .provider import ROOT, CONFIG, RUNTIME
from .strategies import SOURCES, select, prepare, canonical_fingerprint, CONDITION_LABELS, source_valid
from .engine import calculate, Invalid
from .retrieval import Retriever

app=FastAPI(title='DOCX Formula Lab')
app.mount('/static', StaticFiles(directory=ROOT/'formula_lab/static'), name='static')
sessions={};lock=Lock();retriever=None
class PrepareRequest(BaseModel):
    question:str=Field(min_length=1,max_length=2000)
class CalculateRequest(BaseModel):
    session_id:str
    revision:str
    inputs:dict
    confirmations:dict=Field(default_factory=dict)
    request_id:str=''

@app.get('/')
def home(): return FileResponse(ROOT/'formula_lab/static/index.html')
@app.get('/api/lab/info')
def info(): return {'strategy':CONFIG['strategy'],'examples':[c['title'] for c in SOURCES],'conditions':CONDITION_LABELS}
@app.post('/api/lab/prepare')
def form(req:PrepareRequest):
    global retriever
    try:
        with lock:
            if retriever is None: retriever=Retriever()
            hits=retriever.search(req.question)
        result=prepare(select(req.question,hits))
    except Exception as e:
        raise HTTPException(503,detail={'error_type':type(e).__name__})
    if result['status']=='ready':
        id=secrets.token_urlsafe(24)
        with lock:
            if len(sessions)>=500: sessions.pop(next(iter(sessions)))
            sessions[id]=copy.deepcopy(result)
        result['session_id']=id
    return result
@app.post('/api/lab/calculate')
def compute(req:CalculateRequest):
    with lock: session=copy.deepcopy(sessions.get(req.session_id))
    if not session: raise HTTPException(409,'Phiên tính hết hạn; hãy mở lại công thức.')
    if session['spec']['revision']!=req.revision: raise HTTPException(409,'Phiên bản đã thay đổi.')
    current=next((c for c in SOURCES if c['id']==session['spec']['id']),None)
    if current is None or not source_valid(current) or canonical_fingerprint(current)!=canonical_fingerprint(session['source']): raise HTTPException(409,'Nguồn đã thay đổi.')
    try: result=calculate(session['spec'],req.inputs,req.confirmations)
    except Invalid as e: return {'status':'invalid','message':str(e),'request_id':req.request_id}
    result.update(request_id=req.request_id,source=session['source']['file'],source_hash=session['source']['docx_sha256'],strategy=CONFIG['strategy'])
    with lock:
        with (RUNTIME/'calculations.jsonl').open('a') as out: out.write(json.dumps({'inputs':req.inputs,'confirmations':req.confirmations,**result},ensure_ascii=False)+'\n')
    return result
