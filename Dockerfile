FROM python:3.11-slim

WORKDIR /app

# System libs needed by lxml + Ruby (Stage 1 formula extraction, now runs
# inside the api container for uploaded documents — see ingestion_jobs.py)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2 libxslt1.1 ruby-full build-essential \
    && rm -rf /var/lib/apt/lists/*

# MathType OLE -> MathML converter (see ingestion/mtef_to_latex.py). Installed
# system-wide (no --user-install) so the default `gem environment` path finds
# it without needing a platform-specific GEM_PATH override. `pry` is required
# at load time by mathtype_to_mathml's own lib code but isn't pulled in as a
# gem dependency automatically — install it explicitly (confirmed by testing
# `require 'mathtype_to_mathml'` inside the built image, which raised
# LoadError: cannot load such file -- pry, without this).
RUN gem install mathtype_to_mathml pry

# Stage 0-3 Python deps (database, auth, index + retrieval + Gradio)
COPY requirements.txt requirements-app.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-app.txt

# Copy source (TC_DL/ and build/spike_a/ are mounted as volumes at runtime)
COPY app.py .
COPY api_server.py .
COPY generation.py .
COPY latex.py .
COPY ingestion_jobs.py .
COPY retrieval/ retrieval/
COPY index/ index/
COPY ingestion/ ingestion/
COPY knowledge/ knowledge/
COPY eval/ eval/
COPY vendor/ vendor/
COPY db/ db/
COPY auth/ auth/
COPY scripts/ scripts/
COPY alembic.ini .

EXPOSE 7861

# Default: run the Gradio chat app
# Override with: docker compose run --rm indexer python -m index.embed_store --force
CMD ["python", "app.py"]
