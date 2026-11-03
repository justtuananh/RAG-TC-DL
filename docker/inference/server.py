"""
Inference server — OpenAI-compatible embedding + reranking.

Endpoints:
  GET  /health
  POST /v1/embeddings   — input: str | list[str], model: str
  POST /v1/rerank       — query: str, documents: list[str], top_n: int, model: str

Env:
  EMBEDDING_MODEL      default: BAAI/bge-large-en-v1.5
  RERANKER_MODEL       default: BAAI/bge-reranker-v2-m3
  EMBEDDING_GPU_MIN_FREE_MB default: 2048 — VRAM trống tối thiểu để embedding lên GPU,
                       thiếu thì chạy CPU (GPU ưu tiên cho Ollama; reranker luôn CPU)
  RERANKER_MAX_LENGTH  default: 1024 — token cap của cross-encoder; 512 cắt mất
                       nội dung section dài (đo được Q39/Q48 bị giáng hạng vì vậy)
  PORT                 default: 8000
"""

import os
import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer, CrossEncoder

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

EMBEDDING_MODEL     = os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-en-v1.5")
RERANKER_MODEL      = os.getenv("RERANKER_MODEL",  "BAAI/bge-reranker-v2-m3")
RERANKER_MAX_LENGTH = int(os.getenv("RERANKER_MAX_LENGTH", "1024"))
MODE                = os.getenv("MODE", "embedding")

_embedder: SentenceTransformer | None = None
_reranker: CrossEncoder | None = None


# Chia GPU 8 GB: Ollama nạp trước và chiếm trọn phần nó cần (docker-compose cho
# embedding chờ Ollama healthy = model đã nằm trên GPU). Embedding chỉ dùng phần
# VRAM còn dư; reranker luôn chạy CPU (chỉ chấm top-k ứng viên mỗi câu hỏi).
# bge-m3 fp16 ~1,1 GB trọng số + CUDA context + activation: dưới 2 GB trống thì chạy CPU.
EMBEDDING_GPU_MIN_FREE_MB = int(os.getenv("EMBEDDING_GPU_MIN_FREE_MB", "2048"))
# Chừa lại cho CUDA context của tiến trình này (nằm ngoài allocator của PyTorch).
_VRAM_SAFETY_MARGIN_BYTES = 512 * 1024**2


def choose_device(mode: str, free_vram_bytes: int | None) -> str:
    """Thiết bị chạy model: reranker luôn CPU; embedding lên GPU khi VRAM còn đủ."""
    if mode == "reranker" or free_vram_bytes is None:
        return "cpu"
    return "cuda" if free_vram_bytes >= EMBEDDING_GPU_MIN_FREE_MB * 1024**2 else "cpu"


def vram_fraction(free_vram_bytes: int, total_vram_bytes: int) -> float:
    """Trần VRAM cho allocator PyTorch: phần còn trống trừ biên an toàn, không lấn Ollama."""
    return max(free_vram_bytes - _VRAM_SAFETY_MARGIN_BYTES, 0) / total_vram_bytes


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _embedder, _reranker
    import torch
    cuda = torch.cuda.is_available()
    free, total = torch.cuda.mem_get_info() if cuda else (None, None)
    device = choose_device(MODE, free)
    if cuda:
        log.info("GPU: %s, VRAM trống %.2f / %.2f GB -> %s chạy trên %s",
                 torch.cuda.get_device_name(0), free / 1024**3, total / 1024**3, MODE, device)
    if device == "cuda":
        torch.cuda.set_per_process_memory_fraction(vram_fraction(free, total))
    elif MODE != "reranker":
        log.warning("Embedding chạy CPU: VRAM trống không đủ %d MB (Ollama được ưu tiên GPU)",
                    EMBEDDING_GPU_MIN_FREE_MB)
    # fp16 trên GPU: giảm ~một nửa VRAM so với fp32 mặc định của sentence-transformers.
    model_kwargs = {"torch_dtype": torch.float16} if device == "cuda" else None
    if MODE == "reranker":
        log.info("Loading reranker: %s on %s (max_length=%d)", RERANKER_MODEL, device, RERANKER_MAX_LENGTH)
        _reranker = CrossEncoder(RERANKER_MODEL, max_length=RERANKER_MAX_LENGTH, device=device, model_kwargs=model_kwargs)
        log.info("Reranker ready")
    else:
        log.info("Loading embedding model: %s on %s (fp16=%s)", EMBEDDING_MODEL, device, device == "cuda")
        _embedder = SentenceTransformer(EMBEDDING_MODEL, device=device, model_kwargs=model_kwargs)
        log.info("Embedding model ready (dim=%d)", _embedder.get_sentence_embedding_dimension())
    yield


app = FastAPI(title="secai-inference", lifespan=lifespan)


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    model = RERANKER_MODEL if MODE == "reranker" else EMBEDDING_MODEL
    return {"status": "ok", "mode": MODE, "model": model}


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
