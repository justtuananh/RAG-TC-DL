FROM python:3.11-slim

WORKDIR /app

# Torch CUDA 12.8 (Blackwell sm_120, compute cap 12.0) — phải cài trước sentence-transformers
RUN pip install --no-cache-dir torch \
    --index-url https://download.pytorch.org/whl/cu128

RUN pip install --no-cache-dir \
    fastapi \
    uvicorn \
    sentence-transformers \
    pydantic

COPY server.py .

# Download model vào image layer (cache khi build, không tải lại khi restart)
ARG MODE=embedding
ARG EMBEDDING_MODEL=BAAI/bge-large-en-v1.5
ARG RERANKER_MODEL=BAAI/bge-reranker-v2-m3

ENV MODE=${MODE}
ENV EMBEDDING_MODEL=${EMBEDDING_MODEL}
ENV RERANKER_MODEL=${RERANKER_MODEL}

RUN python - <<'EOF'
import os
mode  = os.getenv("MODE", "embedding")
emb   = os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-en-v1.5")
rnk   = os.getenv("RERANKER_MODEL",  "BAAI/bge-reranker-v2-m3")
if mode == "reranker":
    from sentence_transformers import CrossEncoder
    CrossEncoder(rnk, max_length=512)
else:
    from sentence_transformers import SentenceTransformer
    SentenceTransformer(emb)
print("Model downloaded.")
EOF

EXPOSE 8000
CMD ["python", "server.py"]
