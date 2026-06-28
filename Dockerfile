FROM python:3.11-slim

WORKDIR /app

# System libs needed by lxml
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2 libxslt1.1 \
    && rm -rf /var/lib/apt/lists/*

# Stage 2-3 Python deps (index + retrieval + Gradio)
COPY requirements-app.txt .
RUN pip install --no-cache-dir -r requirements-app.txt

# Copy source (TC_DL/ and build/spike_a/ are mounted as volumes at runtime)
COPY app.py .
COPY api_server.py .
COPY generation.py .
COPY latex.py .
COPY retrieval/ retrieval/
COPY index/ index/
COPY eval/ eval/
COPY vendor/ vendor/

EXPOSE 7861

# Default: run the Gradio chat app
# Override with: docker compose run --rm indexer python -m index.embed_store --force
CMD ["python", "app.py"]
