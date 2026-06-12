# Harness QA/Test — RAG_TC_DL

Harness phủ mọi tầng: **backend** (retrieval/index/inference), **LLM** (prompt/stream),
**frontend** (Gradio handlers), **eval** (metric), **QA** (fidelity/đồng bộ hằng số).
Tự chứa trong repo này — **không** phụ thuộc `../kotaemon`.

## Chiến lược: mock-default + integration-opt-in

| Tầng | Ở đâu | Cần gì | Khi nào chạy |
|------|-------|--------|--------------|
| **unit** | `tests/unit/` | Không gì (mock toàn bộ HTTP/Qdrant) | mọi nơi, kể cả CI |
| **integration** | `tests/integration/` | Docker stack (`make up`) | opt-in, KHÔNG ở CI |
| **ruby** | `tests/ruby/` | Ruby + gem `mathtype_to_mathml` | opt-in, KHÔNG ở CI |

Marker tự gán theo thư mục (xem `tests/conftest.py`). Unit test có **guard mạng**:
mọi kết nối socket thật bị chặn → quên mock sẽ fail tức thì thay vì treo theo timeout.

## Cài đặt (một lần)

```bash
python3.11 -m venv .venv-dev
.venv-dev/bin/python -m pip install -r requirements-app.txt -r requirements-dev.txt
```

`requirements-dev.txt` ghim hai phiên bản tương thích mà `requirements-app.txt` để hở
(xem mục Lưu ý). Không cần `requirements.txt` cho test (scikit-image nặng, không dùng).

## Lệnh (Makefile — `PY ?= .venv-dev/bin/python`, override được)

```bash
make check       # CỔNG = lint + fidelity + test-unit (đúng những gì CI chạy)
make test-unit   # chỉ unit (mock, nhanh ~2s)
make fidelity    # guard độ trung thực công thức (đọc build/spike_a, không cần service)
make lint        # ruff check + format-check trên tests/ + scripts/
make fmt         # ruff tự sửa + định dạng tests/ + scripts/
make lint-all    # (tuỳ chọn) quét toàn repo lỗi pyflakes — có thể lộ lỗi sẵn có

# Cần `make up` trước (Docker stack):
make test-int    # healthcheck → toàn bộ integration test
make smoke       # healthcheck → 1 câu end-to-end qua cả LLM
make eval        # eval chuẩn 55 câu (recall@5 ≥ 0.85) — KHÔNG đổi, vẫn là gate gốc
```

Integration test **tự skip** (không fail) khi service chưa lên.

## CI

`.github/workflows/ci.yml` chạy `make check PY=python` trên push/PR vào `main` — chỉ
tầng cloud-feasible. Cố tình loại trừ integration/eval/ruby/model-thật (cần Docker/GPU/
Ruby, dự án offline). Fidelity guard chạy được vì `build/spike_a/` đã commit.

Pre-commit (tuỳ chọn): `.venv-dev/bin/pre-commit install` — ruff chỉ trên `tests/`+`scripts/`.

## Lưu ý: hai pin tương thích phát hiện khi dựng harness

`requirements-app.txt` để hở hai phụ thuộc, khiến **build mới sẽ vỡ**:

1. `huggingface_hub` — gradio 4.x cần `HfFolder` (bị xoá ở hub 1.0) → ghim `<1.0`.
2. `qdrant-client` — code gọi `.search()` (bị xoá ở client ≥1.14; server là 1.10.1) → ghim `==1.10.1`.

Đang ghim trong `requirements-dev.txt`. **Nên ghim luôn trong `requirements-app.txt`**
để build Docker tái lập được.
