FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
# Tên tệp QTKĐ có chữ "Đ": locale ASCII làm đường dẫn/print văng UnicodeEncodeError ('ascii' codec).
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONUTF8=1 PYTHONIOENCODING=utf-8
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

# Marker (PDF -> Markdown + công thức), venv riêng với torch bản CPU (chạy bằng CPU/RAM, không dùng GPU): ingestion/extract_pdf_marker.py
# gọi marker_single qua MARKER_PYTHON. Đặt SAU các lớp trên và TRƯỚC `COPY . .` để sửa code
# không cài lại; chỉ requirements-pdf.txt đổi mới dựng lại lớp này. Cache pip giữ wheel đã tải.
# Mô hình (Surya/Texify) tải sẵn vào image: chạy offline, không tải lúc upload PDF.
COPY requirements-pdf.txt ./
ENV MARKER_PYTHON=/opt/venv-pdf/bin/python XDG_CACHE_HOME=/opt/cache
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m venv /opt/venv-pdf \
    && /opt/venv-pdf/bin/pip install torch==2.11.0 torchvision==0.26.0 \
        --index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.org/simple \
    && /opt/venv-pdf/bin/pip install -r requirements-pdf.txt
# Font của Marker mặc định tải vào site-packages lúc chạy (container chạy UID host, không ghi được).
RUN TORCH_DEVICE=cpu /opt/venv-pdf/bin/python -c "from marker.models import create_model_dict; from marker.util import download_font; create_model_dict(); download_font()" \
    && chmod -R a+rX /opt/cache /opt/venv-pdf

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
