"""Phiên bản và URL của các thành phần tải về khi dựng gói cài Windows.

Một chỗ duy nhất để nâng cấp: sửa phiên bản, dựng lại gói, chạy thử trên máy sạch.
Qdrant/Postgres giữ đúng phiên bản docker-compose đang dùng để dữ liệu cũ (nếu có)
mở được bằng bản native.
"""

from __future__ import annotations

# Python 3.12 (python-build-standalone, bản Windows x86_64, có pip/venv).
PYTHON_VERSION = "3.12.16"
PYTHON_URL = (
    "https://github.com/astral-sh/python-build-standalone/releases/download/20261124/"
    "cpython-3.12.16+20261124-x86_64-pc-windows-msvc-install_only.tar.gz"
)

# Khớp docker-compose.yml (qdrant/qdrant:v1.10.1).
QDRANT_VERSION = "1.10.1"
QDRANT_URL = (
    "https://github.com/qdrant/qdrant/releases/download/v1.10.1/qdrant-x86_64-pc-windows-msvc.zip"
)

# Khớp postgres:16-alpine.
POSTGRES_VERSION = "16.4-1"
POSTGRES_URL = "https://get.enterprisedb.com/postgresql/postgresql-16.4-1-windows-x64-binaries.zip"

OLLAMA_VERSION = "0.40.18"
OLLAMA_URL = "https://github.com/ollama/ollama/releases/download/v0.40.18/ollama-windows-amd64.zip"

# Ruby portable + gem chuyển MathType OLE sang MathML (Stage 1). Chọn nhánh 3.3 vì
# nokogiri (phụ thuộc native của gem) có wheel x64-mingw-ucrt sẵn cho Ruby 3.3,
# không cần DevKit/MSYS2 trên máy đích.
RUBY_VERSION = "3.3.14-1"
RUBY_URL = (
    "https://github.com/oneclick/rubyinstaller2/releases/download/"
    "RubyInstaller-3.3.14-1/rubyinstaller-3.3.14-1-x64.exe"
)
MATHTYPE_GEM_VERSION = "0.0.7"

TORCH_INDEX_URL = "https://download.pytorch.org/whl/cu128"

# Model LLM tải ở lần cài đầu (embedding/reranker lấy tên từ config/settings.yaml).
OLLAMA_MODEL = "qwen2.5:7b-instruct"
