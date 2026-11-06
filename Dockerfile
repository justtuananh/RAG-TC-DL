FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
ENV FORMULA_REGISTRY_DB=/app/.formula-registry/registry.sqlite3

# System libs needed by lxml + Ruby (Stage 1 formula extraction, now runs
# inside the api container for uploaded documents - see ingestion/jobs.py)
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

# LibreOffice headless: ingestion/convert_legacy.py chuyển .doc/.xls cũ sang .docx/.xlsx.
# Đặt sau pip install để thêm lớp này không làm mất cache của lớp cài thư viện Python.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice-writer libreoffice-calc fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Toàn bộ code backend; .dockerignore loại TC_DL/, build/, frontend/, venv, dữ liệu Qdrant.
COPY . .

RUN mkdir -p /app/.formula-registry /app/TC_DL /app/build/spike_a
# Container api chạy bằng UID của người dùng host (docker-compose.yml `user:`),
# nên thư mục log (config/logging.yaml: logs/app.log) phải ghi được với mọi UID.
RUN mkdir -p /app/logs && chmod 1777 /app/logs
# Bản .docx/.xlsx chuyển từ .doc/.xls cũ (ingestion/convert_legacy.py CONVERTED_DIR) là bộ nhớ đệm
# tạo lại được, không gắn ra host: thư mục cha /app/build thuộc root nên phải ghi được với mọi UID.
RUN mkdir -p /app/build/converted && chmod 1777 /app/build/converted
EXPOSE 8080 7861

# Default: run the Gradio chat app
# Override with: docker compose run --rm indexer python -m vectorstore.index --force
CMD ["python", "-m", "ui.gradio_app"]
