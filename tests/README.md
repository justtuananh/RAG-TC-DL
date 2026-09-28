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
.venv-dev/bin/python -m pip install -r requirements-app.lock -r requirements-dev.txt
```

`requirements-app.txt` khai báo runtime dùng Pydantic 2 và Qdrant query_points; file dev chỉ khai báo công cụ kiểm thử. Không cần `requirements.txt` cho test (scikit-image nặng, không dùng).

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


## Registry và React

```bash
make test-formula PY=.venv-dev/bin/python
make check-frontend
```

Các test registry dùng SQLite/DOCX tạm, kiểm phiên bản, phê duyệt, chặn tính, cấu trúc payload và phục hồi nguồn. FE có test HTTP contract và workflow components. Playwright cần thêm Chromium (`python -m playwright install chromium`) hoặc Chrome đã cài. `formula_lab/tests` là suite thí nghiệm riêng cần môi trường lab; không giả định mọi thư viện LLM/SymPy có trong runtime API.

## Tính khách quan

Test do dev viết và tự chạy lại bởi agent khác vẫn là **hồi quy**, không trở thành holdout. Lượt audit giữ riêng khóa đáp án/tolerance trước chạy, không sửa mã hoặc ngưỡng giữa lượt. Ca đã lộ chỉ dùng làm hồi quy sau này. Không gộp tỷ lệ test qua, năng lực trích xuất và sẵn sàng nghiệp vụ thành một điểm chất lượng.

[Báo cáo audit bias](../build/formula-review/BIAS_AUDIT.md) ghi riêng lỗi implementation và lỗi harness; số96% cũ không dùng như nghiệm thu khách quan.
