FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
ENV FORMULA_REGISTRY_DB=/app/.formula-registry/registry.sqlite3

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

# API, ingestion, formula registry and legacy Gradio dependencies.
COPY requirements-app.txt requirements-app.lock ./
RUN pip install --no-cache-dir -r requirements-app.lock && pip check

# Copy source (TC_DL/ and build/spike_a/ are mounted as volumes at runtime)
COPY app.py .
COPY api_server.py .
COPY generation.py .
COPY latex.py .
COPY ingestion_jobs.py .
COPY retrieval/ retrieval/
COPY index/ index/
COPY ingestion/ ingestion/
COPY formula_registry/ formula_registry/
COPY formula_lab/__init__.py formula_lab/engine.py formula_lab/
COPY formula_lab/data/ formula_lab/data/
COPY eval/ eval/
COPY vendor/ vendor/

RUN mkdir -p /app/.formula-registry /app/TC_DL /app/build/spike_a
EXPOSE 8080 7861

# Legacy Gradio remains available with an explicit `python app.py` command.
CMD ["uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8080"]
