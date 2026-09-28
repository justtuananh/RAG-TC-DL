"""Identical full-corpus dense/BM25/RRF for all worktrees, local Qdrant."""
import hashlib
import json
import re
from pathlib import Path
from qdrant_client import QdrantClient, models
from rank_bm25 import BM25Okapi
from .provider import ROOT, DATA, RUNTIME, CONFIG, embeddings

class Retriever:
    def __init__(self):
        self.cards=json.loads((DATA/'sources.json').read_text())
        self.docs=[]
        for p in sorted((ROOT/'build/spike_a').glob('*.md')):
            # Sliding text windows avoid relying on malformed headings in the old extraction.
            text=p.read_text()
            for start in range(0,len(text),1200):
                self.docs.append({'text':p.stem+'\n'+text[start:start+1800],'stem':p.stem})
        self.bm=BM25Okapi([self.tokens(x['text']) for x in self.docs])
        self.client=QdrantClient(path=str(RUNTIME/'qdrant'))
        self.collection='formula_docx_v1'
    @staticmethod
    def tokens(s): return re.findall(r'\w+',s.lower())
    def embed(self,texts):
        cache=RUNTIME/'embedding-cache';cache.mkdir(exist_ok=True)
        out=[]
        for text in texts:
            key=hashlib.sha256((CONFIG['embedding_model']+'\0'+text).encode()).hexdigest()
            p=cache/(key+'.json')
            if p.exists(): v=json.loads(p.read_text())
            else:
                v=embeddings([text])[0]; p.write_text(json.dumps(v))
            out.append(v)
        return out
    def index(self):
        fingerprint=hashlib.sha256(json.dumps([CONFIG['embedding_model'],self.docs],ensure_ascii=False).encode()).hexdigest()
        marker=RUNTIME/'index.json'
        if marker.exists() and json.loads(marker.read_text())['fingerprint']==fingerprint and self.client.collection_exists(self.collection): return
        cache=RUNTIME/'embedding-cache';cache.mkdir(exist_ok=True)
        # Batch missing vectors; cache immutable vectors, rebuild local DB independently.
        vectors=[]
        for start in range(0,len(self.docs),32):
            texts=[d['text'] for d in self.docs[start:start+32]]
            paths=[cache/(hashlib.sha256((CONFIG['embedding_model']+'\0'+t).encode()).hexdigest()+'.json') for t in texts]
            missing=[i for i,p in enumerate(paths) if not p.exists()]
            if missing:
                vs=embeddings([texts[i] for i in missing])
                for i,v in zip(missing,vs): paths[i].write_text(json.dumps(v))
            vectors.extend(json.loads(p.read_text()) for p in paths)
        dim=len(vectors[0])
        if self.client.collection_exists(self.collection): self.client.delete_collection(self.collection)
        self.client.create_collection(self.collection,vectors_config=models.VectorParams(size=dim,distance=models.Distance.COSINE))
        for start in range(0,len(vectors),64):
            self.client.upsert(self.collection,[models.PointStruct(id=i,vector=vectors[i],payload=self.docs[i]) for i in range(start,min(start+64,len(vectors)))])
        marker.write_text(json.dumps({'fingerprint':fingerprint,'dimensions':dim,'chunks':len(vectors)}))
    def search(self,q):
        self.index()
        dense=self.client.query_points(self.collection,query=self.embed([q])[0],limit=20).points
        scores={}
        for rank,h in enumerate(dense): scores[h.id]=1/(60+rank+1)
        b=self.bm.get_scores(self.tokens(q))
        for rank,i in enumerate(sorted(range(len(b)),key=lambda i:b[i],reverse=True)[:20]): scores[i]=scores.get(i,0)+1/(60+rank+1)
        ids=sorted(scores,key=scores.get,reverse=True)[:5]
        return [self.docs[i] for i in ids]

if __name__=='__main__':
    r=Retriever(); r.index(); print((RUNTIME/'index.json').read_text());r.client.close()
