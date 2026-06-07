"""
Inference server — OpenAI-compatible embedding + reranking.

Endpoints:
  GET  /health
  POST /v1/embeddings   — input: str | list[str], model: str
  POST /v1/rerank       — query: str, documents: list[str], top_n: int, model: str

Env:
  EMBEDDING_MODEL   default: BAAI/bge-large-en-v1.5
  RERANKER_MODEL    default: BAAI/bge-reranker-v2-m3
  PORT              default: 8000
"""

import os
import time
import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer, CrossEncoder

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-en-v1.5")
RERANKER_MODEL  = os.getenv("RERANKER_MODEL",  "BAAI/bge-reranker-v2-m3")
MODE            = os.getenv("MODE", "embedding")   # "embedding" | "reranker"

_embedder: SentenceTransformer | None = None
_reranker: CrossEncoder | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _embedder, _reranker
    if MODE == "reranker":
        log.info("Loading reranker: %s", RERANKER_MODEL)
        _reranker = CrossEncoder(RERANKER_MODEL, max_length=512)
        log.info("Reranker ready")
    else:
        log.info("Loading embedding model: %s", EMBEDDING_MODEL)
        _embedder = SentenceTransformer(EMBEDDING_MODEL)
        log.info("Embedding model ready (dim=%d)", _embedder.get_sentence_embedding_dimension())
    yield


app = FastAPI(title="secai-inference", lifespan=lifespan)


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "mode": MODE}


# ── Embeddings ────────────────────────────────────────────────────────────────

class EmbeddingRequest(BaseModel):
    input: str | list[str]
    model: str = EMBEDDING_MODEL
    encoding_format: str = "float"


class EmbeddingObject(BaseModel):
    object: str = "embedding"
    index: int
    embedding: list[float]


class EmbeddingResponse(BaseModel):
    object: str = "list"
    model: str
    data: list[EmbeddingObject]
    usage: dict[str, Any] = {}


@app.post("/v1/embeddings", response_model=EmbeddingResponse)
def embed(req: EmbeddingRequest):
    if _embedder is None:
        raise HTTPException(503, "Embedding model not loaded (wrong MODE?)")
    texts = [req.input] if isinstance(req.input, str) else req.input
    vecs = _embedder.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    data = [EmbeddingObject(index=i, embedding=v.tolist()) for i, v in enumerate(vecs)]
    return EmbeddingResponse(model=req.model, data=data, usage={"prompt_tokens": sum(len(t.split()) for t in texts)})


# ── Rerank ────────────────────────────────────────────────────────────────────

class RerankRequest(BaseModel):
    query: str
    documents: list[str]
    top_n: int | None = None
    model: str = RERANKER_MODEL
    return_documents: bool = False


class RerankResult(BaseModel):
    index: int
    relevance_score: float
    document: dict[str, str] | None = None


class RerankResponse(BaseModel):
    model: str
    results: list[RerankResult]
    usage: dict[str, Any] = {}


@app.post("/v1/rerank", response_model=RerankResponse)
def rerank(req: RerankRequest):
    if _reranker is None:
        raise HTTPException(503, "Reranker model not loaded (wrong MODE?)")
    if not req.documents:
        return RerankResponse(model=req.model, results=[])

    pairs = [(req.query, doc) for doc in req.documents]
    scores = _reranker.predict(pairs, show_progress_bar=False).tolist()

    top_n = req.top_n if req.top_n and req.top_n > 0 else len(req.documents)
    ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:top_n]

    results = [
        RerankResult(
            index=idx,
            relevance_score=float(score),
            document={"text": req.documents[idx]} if req.return_documents else None,
        )
        for idx, score in ranked
    ]
    return RerankResponse(model=req.model, results=results)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
