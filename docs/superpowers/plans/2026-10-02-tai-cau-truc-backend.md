# Tái cấu trúc backend theo tầng + cấu hình tập trung Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tổ chức lại backend thành các package tách bạch (`api`, `config`, `core`, `embedding`, `evaluation`, `ingestion`, `llm`, `qdrant_storage`, `reranking`, `retrieval`, `scoring`, `tests`, `vectorstore`) và gom mọi tham số vận hành + tên model về một file `config/settings.yaml`, KHÔNG đổi hành vi.

**Architecture:** Pipeline một chiều giữ nguyên ranh giới: `ingestion` (docx → Markdown → Chunk) → `embedding` + `vectorstore` (Qdrant + BM25) → `retrieval` (hybrid + `reranking`) → `llm` (prompt + sinh) → `api`.
`core` là tầng đáy: nạp cấu hình, logging, schema dùng chung, khởi động; không import package nào khác của dự án.
Mỗi tham số được đọc tại thời điểm gọi qua `get_settings()`, không đọc lúc import, nên test thay được cấu hình mà không monkeypatch hằng số module.

**Tech Stack:** Python 3.11, FastAPI, pydantic v2, PyYAML, qdrant-client 1.10.1, rank-bm25, requests, pytest, ruff; Docker Compose.

**Spec:** Yêu cầu của người dùng (2026-10-02): "tổ chức có các folder api, config (settings.yaml, logging.yaml), core (logging_setup.py, schema.py, settings_loader.py, startup.py), embedding (batch_embed, embedder, sparse_embedder), evaluation, ingestion, llm (generator, prompt), qdrant_storage, reranking, retrieval (context_builder, hybrid_retriever, retriever), scoring, tests, vectorstore (hybrid_index, index, qdrant, upsert), settings.yaml để toàn bộ tham số cấu hình, model".
Nền: `CLAUDE.md` (kiến trúc 3 tầng, rủi ro công thức) và `docs/PLAN.md`.

## Global Constraints

- Thuần tái cấu trúc: không đổi hành vi truy hồi, prompt, câu trả lời, API (đường dẫn, method, schema request/response). Ngoại lệ duy nhất có chủ đích: Task 7 thống nhất `top_k` (quyết định 4).
- Rủi ro #1 không được chạm: logic của `ingestion/extract_docx.py`, `mtef.py`, `mtef_to_latex.py`, `omml.py`, `spike_a.py` giữ nguyên từng dòng; guard 351/351 (`make fidelity`, nằm trong `make check`) phải xanh sau mọi task.
- Không bao giờ sửa `TC_DL/`, không sửa tay `build/`, không sửa CHANGELOG hay file sinh tự động.
- Chuỗi hiển thị, prompt, chú thích nghiệp vụ, tên mục tài liệu: tiếng Việt.
- Không dùng ký tự em dash trong code, chú thích, tài liệu; dùng "-".
- Di chuyển file bằng `git mv` (giữ lịch sử); task có di chuyển tách tối thiểu hai commit: (a) `git mv` + sửa import, (b) đổi sang đọc settings / tách hàm.
- Commit sau mỗi phần, chỉ `git add` đúng file của phần đó, không push. Định dạng: `refactor: <mô tả>` (hoặc `feat`/`test`/`docs`/`chore` đúng loại).
- Sau mọi task: `make check` xanh với số test ≥ baseline (1709 passed, 1 skipped đo ngày 2026-10-02) cộng số test mới; không xóa test nào mà không có test thay thế tương đương.
- Chỉ `core/settings_loader.py` (và `core/logging_setup.py`, cùng cơ chế) đọc `os.environ` để lấy cấu hình. Ngoại lệ: `docker/inference/server.py` (image riêng, không chứa repo), `os.environ.copy()` để truyền env cho subprocess.
- Bí mật (`JWT_SECRET_KEY`, `POSTGRES_PASSWORD`, `DATABASE_URL`) chỉ được tham chiếu bằng `${BIẾN}` trong `settings.yaml`, không ghi giá trị thật.
- File điều phối import MODULE rồi gọi qua tên module (`from embedding import embedder` → `embedder.embed_query(...)`), để test chỉ cần patch một chỗ.
- `qdrant-client==1.10.1` giữ nguyên (khớp server 1.10.1).
- Quy ước hai venv giữ nguyên: Stage 1 dùng `.venv` (`requirements.txt`), Stage 2-3 dùng `requirements-app.txt`, test dùng `.venv-dev`. PyYAML + pydantic phải có trong cả ba.

---

## Bản đồ đích

```
config/
  settings.yaml          mọi tham số vận hành + tên model (nguồn sự thật duy nhất)
  logging.yaml           dictConfig cho logging
core/
  __init__.py            rỗng (import core.latex không kéo theo yaml/pydantic)
  schema.py              pydantic Settings (khớp settings.yaml) + Chunk dùng chung
  settings_loader.py     nạp YAML, thay ${VAR:-mặc_định}, kiểm schema, get_settings()
  logging_setup.py       configure_logging() từ logging.yaml
  startup.py             startup(): logging + kiểm cấu hình + kiểm service lúc khởi động
  latex.py               fix_latex (từ latex.py ở gốc)
embedding/
  embedder.py            embed_texts(), embed_query() (gộp bản trùng ở retriever + embed_store)
  batch_embed.py         embed_chunks_batched()
  sparse_embedder.py     tokenize(), sparse_document_text() (biểu diễn thưa cho BM25)
vectorstore/
  qdrant.py              get_client(), ensure_collection(), dense_search(), fetch_parent(), ...
  upsert.py              index_chunks(), upsert_points()
  index.py               index_directory(), CLI `python -m vectorstore.index`
  hybrid_index.py        chỉ mục BM25 trong bộ nhớ: bm25_search(), invalidate()
reranking/
  reranker.py            build_rerank_doc(), rerank_hits()
retrieval/
  noise.py               is_noise_path() (từ _constants.py)
  query_expansion.py     expand_query() + LEXICON
  router.py              định tuyến theo số QTKĐ (giữ, đọc settings)
  hybrid_retriever.py    rrf_fuse(), filter_noise(), merge_per_file(), search_both()
  retriever.py           retrieve(): điều phối toàn phễu
  context_builder.py     filter_by_confidence(), window(), build_context_and_citations()
llm/
  generator.py           native_chat_url(), stream_ollama()
  prompt.py              SYSTEM_TMPL, build_messages()
  guards.py              REFUSAL_SENTENCE, is_calculation_request(), enforce_refusal_stop()
api/
  main.py                create_app(), app, main()
  schemas.py             model pydantic của request
  errors.py              ánh xạ lỗi nghiệp vụ → HTTPException
  audit.py               ghi audit + snapshot tài liệu
  services/chat_stream.py  luồng SSE của chat (từ _chat_stream_gen)
  routes/{system,auth,chat,documents,extractions,records,data}.py
ingestion/
  (giữ nguyên Stage 1) + chunker.py (từ index/) + jobs.py (từ ingestion_jobs.py)
evaluation/              (đổi tên từ eval/, hết che builtin `eval`)
scoring/
  answer_scoring.py      (từ eval/scoring.py)
  retrieval_metrics.py   compute_metrics(), hit_rank(), matches() (từ eval/run_eval.py)
qdrant_storage/          dữ liệu Qdrant bind-mount (gitignored, chỉ README.md được track)
ui/gradio_app.py         (từ app.py, giao diện phụ)
tests/unit/<package>/    test soi gương cấu trúc package
```

Giữ nguyên vị trí (đã là package nghiệp vụ gọn): `query/`, `records/`, `catalogs/`, `knowledge/`, `review/`, `db/`, `auth/`, `scripts/`, `kotaemon_ext/`, `docker/`, `vendor/`, `frontend/`.
Các package này chỉ đổi import và đọc settings thay cho `os.getenv`.

## Quyết định (mặc định đã chọn, người dùng có thể đổi trước khi chạy)

1. `qdrant_storage/` là thư mục dữ liệu Qdrant bind-mount, thay cho named volume `hraesvelg_qdrant_storage` (lúc lập plan có 1646 point, 1024 chiều, Cosine). Code Qdrant nằm ở `vectorstore/qdrant.py`.
2. `sparse_embedder.py` chứa biểu diễn thưa đang có (tokenizer BM25 giữ nguyên mã/đơn vị). Chuyển sang sparse vector thật của Qdrant/bge-m3 là thay đổi hành vi, cần plan riêng.
3. `core/schema.py` chứa schema cấu hình (pydantic) và `Chunk`. Model request HTTP nằm ở `api/schemas.py`.
4. Thống nhất `top_k`: hiện API gọi `retrieve(top_k=50)` còn Gradio và eval gọi `top_k=20`, nghĩa là eval đang đo một phễu khác production. Sau Task 7 mọi nơi dùng `retrieval.top_k` (50, đúng như API). Số eval sẽ khác baseline top_k=20 và phải khớp baseline top_k=50 chụp ở Task 0.
5. Model chat mặc định là `qwen2.5:3b`, giá trị mọi đường chạy thật đang dùng (compose, run.sh, record-eval), thay cho mặc định `qwen2.5:1.5b` trong code cũ.
6. `models.llm_intent` / `models.llm_extraction` để trống thì dùng `models.llm_chat`. Code cũ chỉ cho extraction rơi về `qwen2.5:7b` khi `OLLAMA_MODEL` cũng không đặt, trường hợp không xảy ra với compose/run.sh.
7. `JWT_SECRET_KEY` không còn mặc định ghi cứng: thiếu ở `development` thì mỗi tiến trình sinh một khóa ngẫu nhiên và ghi cảnh báo; thiếu ở `production` thì dừng khởi động.
8. Gradio `app.py` chuyển sang `ui/gradio_app.py` (không xóa).
9. Container không còn mount từng file code. Image chứa toàn bộ code (`COPY . .` + `.dockerignore`). Lý do: Dockerfile hiện KHÔNG copy `query/`, `review/`, `records/`, `catalogs/` dù `api_server.py` import chúng, nên image `qtkd-api` có vẻ không import được app (Task 0 bước 5 xác nhận).

## Những gì KHÔNG đưa vào settings.yaml

Heuristic phân tích tài liệu (`_HEADER_SEARCH_ROWS`, namespace OOXML, `EXTRACTOR = "rule:..."`), quy tắc định dạng câu trả lời tất định (`MAX_CARDS`, `MAX_LINES`, `CITATION_CAP`), danh mục nghiệp vụ (`_LEXICON`, `_QTKD_TITLES`, `NOISE_PATH_MARKERS`), ngưỡng cổng eval (`PASS_RATE`).
Đó là code/dữ liệu nghiệp vụ có test riêng: đổi chúng là đổi hành vi, không phải đổi môi trường chạy.

---

### Task 0: Chuẩn bị và chụp baseline

**Files:**
- Không sửa file nào trong repo; baseline lưu ở `~/.cache/qtkd-refactor/` (ngoài repo).

- [ ] **Step 1: Xử lý thay đổi chưa commit của người dùng**

Lúc lập plan, `git status` có thay đổi chưa commit ở `docker-compose.yml`, `docker/inference/Dockerfile`, `docker/inference/server.py`, `run.sh`, cùng nhiều file chưa track (`*.xlsx`, `*.doc`, `test_chatbot/`, `run-dev.sh`).
Task 1, 10, 13 sửa đúng những file đó.
Đề nghị người dùng commit chúng thành commit riêng trước. Không tự stash hay commit hộ.

Run: `git status --short`
Expected: không còn dòng ` M` ở 4 file trên.

- [ ] **Step 2: Tạo nhánh**

```bash
git switch -c refactor/backend-layout
```

- [ ] **Step 3: Baseline cổng tự động**

```bash
mkdir -p ~/.cache/qtkd-refactor
make check 2>&1 | tail -3 | tee ~/.cache/qtkd-refactor/check.txt
(cd frontend && npm run typecheck && npm run lint && npm run test && npm run build) 2>&1 | tail -5 | tee ~/.cache/qtkd-refactor/frontend.txt
```
Expected: `1709 passed, 1 skipped` (hoặc con số hiện hành, ghi lại), frontend xanh.

- [ ] **Step 4: Chụp danh sách route và OpenAPI của API**

```bash
.venv-dev/bin/python -c "import json, api_server; print(json.dumps([[r.path, sorted(r.methods or [])] for r in api_server.app.routes], ensure_ascii=False, indent=1))" > ~/.cache/qtkd-refactor/routes.json
.venv-dev/bin/python -c "import json, api_server; print(json.dumps(api_server.app.openapi(), ensure_ascii=False, sort_keys=True))" > ~/.cache/qtkd-refactor/openapi.json
```
Expected: hai file JSON khác rỗng.

- [ ] **Step 5: Xác nhận lỗi image Docker hiện tại (quyết định 9)**

```bash
docker compose build api && docker compose run --rm --no-deps api python -c "import api_server" 2>&1 | tail -3 | tee ~/.cache/qtkd-refactor/docker.txt
```
Expected: `ModuleNotFoundError` (vd. `No module named 'review'`). Nếu import được thì ghi lại; quyết định 9 vẫn giữ (một nguồn code, không mount lẻ).

- [ ] **Step 6: Chụp kết quả truy hồi tất định (cần Qdrant + embedding + reranker đang chạy)**

Tạo `~/.cache/qtkd-refactor/snapshot_retrieval.py`:

```python
"""Chụp top-5 của retrieve() cho mọi câu trong eval set: dùng trước và sau tái cấu trúc."""
import json
import sys
from pathlib import Path

from retrieval.retriever import retrieve

eval_dir = Path("evaluation") if Path("evaluation/eval_set.jsonl").exists() else Path("eval")
top_k = int(sys.argv[1])
rows = []
for line in (eval_dir / "eval_set.jsonl").read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    item = json.loads(line)
    hits = retrieve(item["question"], top_k=top_k, top_n=5)
    rows.append({
        "q": item["question"],
        "hits": [
            [h["payload"]["file_stem"], h["payload"]["section_path"], round(h.get("rerank_score", 0.0), 4)]
            for h in hits
        ],
    })
print(json.dumps(rows, ensure_ascii=False, indent=1))
```

```bash
PYTHONPATH=. .venv-dev/bin/python ~/.cache/qtkd-refactor/snapshot_retrieval.py 50 > ~/.cache/qtkd-refactor/retrieval_k50.json
PYTHONPATH=. .venv-dev/bin/python ~/.cache/qtkd-refactor/snapshot_retrieval.py 20 > ~/.cache/qtkd-refactor/retrieval_k20.json
.venv-dev/bin/python -m eval.run_eval --mode hybrid | tee ~/.cache/qtkd-refactor/run_eval_k20.txt
```
Expected: hai file JSON có đủ số câu của `eval/eval_set.jsonl`; `run_eval` in recall@k + MRR. Nếu service chưa chạy: `docker compose up -d qdrant embedding reranker` trước.
Chạy thêm lần hai `snapshot_retrieval.py 50` và `diff` với lần một: phải giống hệt. Nếu khác (reranker không tất định), dùng so sánh theo `[file_stem, section_path]` và bỏ cột điểm ở các bước so sau.

---

### Task 1: Docker build lấy toàn bộ code (bỏ mount từng file)

Làm sớm để các lần `git mv` sau không phải sửa Dockerfile/compose từng dòng.

**Files:**
- Modify: `Dockerfile`
- Modify: `.dockerignore`
- Modify: `docker-compose.yml` (service `api`, `indexer`)

- [ ] **Step 1: Dockerfile copy toàn bộ code**

Thay khối từ `COPY app.py .` đến `COPY alembic.ini .` bằng:

```dockerfile
# Toàn bộ code backend; .dockerignore loại TC_DL/, build/, frontend/, venv, dữ liệu Qdrant.
COPY . .
```
Giữ nguyên các lệnh `RUN`, `EXPOSE`, `CMD` còn lại.

- [ ] **Step 2: Bổ sung .dockerignore**

Thêm vào cuối `.dockerignore`:

```
# Code/dữ liệu không thuộc image backend
frontend/
frontend-legacy/
design/
qdrant_storage/
logs/
tests/
.venv-dev/
.venv-pdf/
*.xlsx
*.doc
*.docx
```
Giữ `!requirements*.txt`. `*.md` đang bị loại không ảnh hưởng vì `config/` không có file `.md`.

- [ ] **Step 3: Bỏ mount code trong compose**

Service `api`: xóa các dòng mount code (`./api_server.py`, `./generation.py`, `./latex.py`, `./ingestion_jobs.py`, `./retrieval`, `./index`, `./ingestion`, `./db`, `./auth`, `./scripts`, `./alembic.ini`), giữ `./build/spike_a` và `./TC_DL`.
Service `indexer`: xóa `./index:/app/index:ro`.

- [ ] **Step 4: Kiểm image import được app**

```bash
docker compose build api && docker compose run --rm --no-deps api python -c "import api_server; print('ok')"
```
Expected: `ok`.

- [ ] **Step 5: Commit**

```bash
git add Dockerfile .dockerignore docker-compose.yml
git commit -m "fix(docker): build the api image from the whole backend instead of per-file copies"
```

---

### Task 2: `config/settings.yaml` + `core/schema.py` + `core/settings_loader.py`

**Files:**
- Create: `config/settings.yaml`
- Create: `core/__init__.py` (rỗng)
- Create: `core/schema.py`
- Create: `core/settings_loader.py`
- Modify: `requirements.txt`, `requirements-app.txt`, `requirements-dev.txt` (thêm `pyyaml>=6.0`, `pydantic>=2.5`)
- Modify: `tests/conftest.py` (fixture `settings_override`, tắt `.env` trong test)
- Test: `tests/unit/core/test_settings_loader.py`, `tests/unit/core/test_settings_values.py`

**Interfaces:**
- Produces:
  - `core.settings_loader.get_settings() -> core.schema.Settings` (cache; trả bản override nếu test đặt)
  - `core.settings_loader.load_settings(path: Path | None = None, env: Mapping[str, str] | None = None) -> Settings`
  - `core.settings_loader.load_yaml(path: Path, env: Mapping[str, str]) -> Any`
  - `core.settings_loader.interpolate(value: Any, env: Mapping[str, str]) -> Any`
  - `core.settings_loader.with_overrides(settings: Settings, overrides: Mapping[str, Any]) -> Settings` (khóa dạng `"retrieval.top_k"`)
  - `core.settings_loader.reset_settings() -> None`
  - `core.settings_loader.REPO_ROOT: Path`, `CONFIG_DIR: Path`, `SettingsError`
  - `core.settings_loader.main(argv: list[str] | None = None) -> int`; CLI `python -m core.settings_loader get <khóa.chấm>`
  - `core.schema.Settings` với các mục `app, paths, services, models, embedding, vectorstore, chunking, retrieval, reranking, llm, ingestion, database, auth, api, query`; `Settings.llm_model(role)`, `Settings.llm_url(role)`, `LlmSettings.total_context_chars`; `core.schema.LlmRole = Literal["chat", "intent", "extraction"]`
  - fixture pytest `settings_override(overrides: dict[str, Any]) -> Settings`

- [ ] **Step 1: Viết `config/settings.yaml`**

```yaml
# Cấu hình DUY NHẤT của backend QTKĐ RAG (đọc bởi core/settings_loader.py).
#
# ${TÊN:-mặc_định}: dùng biến môi trường TÊN nếu đặt và khác rỗng, không thì mặc_định.
# ${TÊN}: bắt buộc đặt biến môi trường; thiếu là dừng ngay lúc khởi động.
# Bí mật chỉ tham chiếu qua biến môi trường, không ghi giá trị thật vào file này.
# Đường dẫn tương đối tính từ thư mục gốc repo.

app:
  env: ${APP_ENV:-development}            # development | production
  startup_checks: ${QTKD_STARTUP_CHECKS:-true}

paths:
  source_dir: TC_DL                       # tài liệu QTKĐ gốc (chỉ đọc + tải lên)
  markdown_dir: build/spike_a             # Markdown + assets + extraction_report.json

services:
  embedding_url: ${EMBED_URL:-http://localhost:8010/v1/embeddings}
  rerank_url: ${RERANK_URL:-http://localhost:8011/v1/rerank}
  qdrant_url: ${QDRANT_URL:-http://localhost:6333}
  ollama_url: ${OLLAMA_URL:-http://localhost:11434/api/chat}   # native /api/chat, không dùng /v1

models:
  embedding:
    name: BAAI/bge-m3                     # phải khớp docker-compose service embedding
    vector_size: 1024                     # phải khớp chiều vector của collection
  reranker:
    name: BAAI/bge-reranker-v2-m3         # phải khớp docker-compose service reranker
    max_length: 1024
  llm_chat: ${OLLAMA_MODEL:-qwen2.5:3b}
  llm_intent: ${INTENT_LLM_MODEL:-}       # rỗng = llm_chat
  llm_extraction: ${SECTION6_LLM_MODEL:-} # rỗng = llm_chat

embedding:
  query_timeout_s: 120
  batch_size: 8                           # chunk mỗi request lúc index
  batch_timeout_s: 300

vectorstore:
  collection: qtkd_rag
  upsert_batch: 64

chunking:
  synth_section_chars: 4000
  max_table_rows: 15
  table_group_rows: 8

retrieval:
  top_k: 50                               # ứng viên mỗi nhánh dense / BM25
  top_n: 5                                # nguồn trả về sau rerank
  rerank_pool: 60                         # trần ứng viên vào cross-encoder sau RRF + lọc nhiễu
  rrf_k: 60
  min_routed_candidates: 6                # ít hơn thì bỏ lọc theo file, tìm toàn kho

reranking:
  timeout_s: 60
  doc_cap_chars: 1400
  doc_back_chars: 200

llm:
  chat:
    timeout_s: ${OLLAMA_TIMEOUT:-300}     # tới token đầu tiên; CPU nguội cần >120s
    num_ctx: 8192                         # phải khớp OLLAMA_CONTEXT_LENGTH của container
    max_new_tokens: 1024
    temperature: 0.1
    keep_alive: 30m
    history_turns: 3
  context:
    chars_per_token: 3
    prompt_reserve_tokens: 1200
    max_block_chars: 2400
    min_block_chars: 600
    source_abs_floor: 0.08
    source_rel_floor: 0.20
  intent:
    enabled: ${INTENT_ROUTER_ENABLED:-true}
    url: ${INTENT_OLLAMA_URL:-}           # rỗng = services.ollama_url
    timeout_s: ${INTENT_LLM_TIMEOUT:-60}
    num_ctx: ${INTENT_LLM_NUM_CTX:-8192}
    temperature: ${INTENT_LLM_TEMPERATURE:-0.0}
    keep_alive: 10m
  extraction:
    enabled: ${SECTION6_LLM_ENABLED:-false}
    url: ${SECTION6_OLLAMA_URL:-}
    timeout_s: ${SECTION6_LLM_TIMEOUT:-120}
    num_ctx: ${SECTION6_LLM_NUM_CTX:-8192}
    temperature: ${SECTION6_LLM_TEMPERATURE:-0.0}
    keep_alive: 10m

ingestion:
  soffice_bin: ${SOFFICE_BIN:-}           # rỗng = tìm `soffice` trên PATH
  convert_timeout_s: 120
  max_upload_bytes: 52428800              # 50 MiB
  marker_python: ${MARKER_PYTHON:-}

database:
  url: ${DATABASE_URL:-}                  # đặt thì thắng mọi trường bên dưới
  host: ${POSTGRES_HOST:-localhost}
  port: ${POSTGRES_PORT:-5432}
  name: ${POSTGRES_DB:-qtkd}
  user: ${POSTGRES_USER:-qtkd_user}
  password: ${POSTGRES_PASSWORD:-qtkd_password}   # mặc định chỉ cho dev; production bị chặn

auth:
  enabled: ${AUTH_ENABLED:-true}
  jwt_secret_key: ${JWT_SECRET_KEY:-}     # rỗng: dev sinh khóa tạm, production dừng
  jwt_algorithm: HS256
  jwt_expiration_hours: ${JWT_EXPIRATION_HOURS:-24}

api:
  host: ${API_HOST:-0.0.0.0}
  port: ${API_PORT:-8080}
  cors_origins:
    - http://localhost:5173
    - http://localhost:5174
    - http://localhost:3000
    - http://127.0.0.1:5173

query:
  list_limit_max: 200
  export_limit_max: 20000
  catalog_row_limit: 200
  trend_point_cap: 200
  cache_ttl_s: 30.0                       # cache danh mục / sổ cái / số hiệu
```

Trước khi chép, đối chiếu từng giá trị với nguồn hiện tại. Nếu lệch, giá trị trong code thắng và ghi chú vào commit message:
`generation.py:28-46,71-72`, `retrieval/retriever.py:15-24,109-110`, `index/embed_store.py:36-42`, `index/chunker.py:39-45`, `query/intents.py:745-783`, `knowledge/llm_extract.py:47-48,450-468`, `ingestion/convert_legacy.py:22,29`, `ingestion_jobs.py:52`, `db/config.py`, `auth/*.py`, `api_server.py:104-116,1069`, `query/records.py:37-38`, `query/catalogs.py:24,36`, `query/catalog_router.py:37`, `query/router.py:66`, `query/record_fields.py:87`, `query/record_signals.py:119`, `query/signals.py:85`.

- [ ] **Step 2: Viết test loader (RED)**

`tests/unit/core/test_settings_loader.py`:

```python
"""Nạp settings.yaml: thay biến môi trường, kiểm schema, override cho test."""

from pathlib import Path

import pytest

from core import settings_loader as SL


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "settings.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def _default_text() -> str:
    return (SL.CONFIG_DIR / "settings.yaml").read_text(encoding="utf-8")


def test_interpolate_uses_env_when_set():
    assert SL.interpolate("${A:-x}", {"A": "y"}) == "y"


def test_interpolate_falls_back_to_default_when_unset_or_empty():
    assert SL.interpolate("${A:-x}", {}) == "x"
    assert SL.interpolate("${A:-x}", {"A": ""}) == "x"


def test_interpolate_empty_default_gives_empty_string():
    assert SL.interpolate("${A:-}", {}) == ""


def test_interpolate_missing_required_variable_raises():
    with pytest.raises(SL.SettingsError, match="B"):
        SL.interpolate("${B}", {})


def test_interpolate_walks_nested_lists_and_dicts():
    raw = {"a": ["${X:-1}", {"b": "pre-${X:-1}-post"}], "n": 5}
    assert SL.interpolate(raw, {"X": "9"}) == {"a": ["9", {"b": "pre-9-post"}], "n": 5}


def test_default_file_loads_with_empty_env():
    assert SL.load_settings(env={}).vectorstore.collection == "qtkd_rag"


def test_unknown_key_is_rejected(tmp_path):
    path = _write(tmp_path, _default_text() + "\nkhoa_la: 1\n")
    with pytest.raises(SL.SettingsError, match="khoa_la"):
        SL.load_settings(path=path, env={})


def test_wrong_type_is_rejected(tmp_path):
    path = _write(tmp_path, _default_text().replace("top_k: 50", "top_k: nhiều", 1))
    with pytest.raises(SL.SettingsError, match="top_k"):
        SL.load_settings(path=path, env={})


def test_relative_paths_resolve_against_repo_root():
    assert SL.load_settings(env={}).paths.markdown_dir == SL.REPO_ROOT / "build" / "spike_a"


def test_env_overrides_model_and_url():
    settings = SL.load_settings(env={"OLLAMA_MODEL": "qwen2.5:7b", "QDRANT_URL": "http://qdrant:6333"})
    assert settings.models.llm_chat == "qwen2.5:7b"
    assert settings.services.qdrant_url == "http://qdrant:6333"


def test_with_overrides_returns_new_settings_and_keeps_original():
    base = SL.load_settings(env={})
    new = SL.with_overrides(base, {"retrieval.top_k": 7})
    assert new.retrieval.top_k == 7
    assert base.retrieval.top_k == 50


def test_with_overrides_unknown_key_raises():
    with pytest.raises(SL.SettingsError, match="retrieval.khong_co"):
        SL.with_overrides(SL.load_settings(env={}), {"retrieval.khong_co": 1})


def test_settings_override_fixture_reaches_get_settings(settings_override):
    settings_override({"retrieval.top_n": 3})
    assert SL.get_settings().retrieval.top_n == 3


def test_cli_get_prints_value(capsys):
    assert SL.main(["get", "vectorstore.collection"]) == 0
    assert capsys.readouterr().out.strip() == "qtkd_rag"
```

`tests/unit/core/test_settings_values.py` (sẽ thay `tests/unit/qa/test_config_constants.py`; file cũ xóa ở Task 7 khi các hằng biến mất):

```python
"""Giá trị mặc định mà eval và service phụ thuộc: đổi là phải chạy lại eval."""

from core.settings_loader import load_settings


def test_defaults_eval_depends_on():
    s = load_settings(env={})
    assert s.models.embedding.vector_size == 1024
    assert s.vectorstore.collection == "qtkd_rag"
    assert s.retrieval.rrf_k == 60
    assert s.retrieval.top_k == 50
    assert s.retrieval.rerank_pool == 60
    assert s.llm.chat.history_turns == 3
    assert s.llm.chat.num_ctx == 8192


def test_context_budget_formula_and_bounds():
    llm = load_settings(env={}).llm
    expected = (llm.chat.num_ctx - llm.context.prompt_reserve_tokens) * llm.context.chars_per_token
    assert llm.total_context_chars == expected
    assert llm.total_context_chars > 1800
    assert llm.context.min_block_chars < llm.context.max_block_chars < llm.total_context_chars


def test_intent_classifier_shares_chat_context_window():
    s = load_settings(env={})
    assert s.llm.intent.num_ctx == s.llm.chat.num_ctx  # Ollama không nạp lại model giữa hai lời gọi


def test_role_models_fall_back_to_chat_model():
    s = load_settings(env={"OLLAMA_MODEL": "m-chat"})
    assert s.llm_model("intent") == "m-chat"
    assert s.llm_model("extraction") == "m-chat"
    s2 = load_settings(env={"OLLAMA_MODEL": "m-chat", "SECTION6_LLM_MODEL": "m-ext"})
    assert s2.llm_model("extraction") == "m-ext"


def test_role_urls_fall_back_to_service_url():
    s = load_settings(env={"OLLAMA_URL": "http://o:11434/api/chat", "INTENT_OLLAMA_URL": "http://i/api/chat"})
    assert s.llm_url("chat") == "http://o:11434/api/chat"
    assert s.llm_url("intent") == "http://i/api/chat"
    assert s.llm_url("extraction") == "http://o:11434/api/chat"


def test_secrets_are_secretstr():
    s = load_settings(env={"JWT_SECRET_KEY": "k", "POSTGRES_PASSWORD": "p"})
    assert "'k'" not in repr(s.auth)
    assert s.auth.jwt_secret_key.get_secret_value() == "k"
    assert s.database.password.get_secret_value() == "p"
```

- [ ] **Step 3: Chạy test, xác nhận FAIL**

Run: `.venv-dev/bin/python -m pytest tests/unit/core -q`
Expected: FAIL với `ModuleNotFoundError: No module named 'core'`.

- [ ] **Step 4: Viết `core/schema.py`**

```python
"""Schema dùng chung của backend.

1. Cấu hình: mô hình pydantic khớp từng mục của config/settings.yaml. Khóa lạ hoặc
   sai kiểu làm dừng ngay lúc nạp (extra="forbid"), không chạy với cấu hình hỏng.
2. Dữ liệu đi giữa các tầng: Chunk (ingestion → embedding / vectorstore).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, SecretStr

LlmRole = Literal["chat", "intent", "extraction"]


def _blank_to_none(value: object) -> object:
    return None if isinstance(value, str) and not value.strip() else value


OptionalStr = Annotated[str | None, BeforeValidator(_blank_to_none)]
OptionalSecret = Annotated[SecretStr | None, BeforeValidator(_blank_to_none)]
Positive = Annotated[int, Field(gt=0)]
NonNegative = Annotated[int, Field(ge=0)]
PositiveFloat = Annotated[float, Field(gt=0)]
Temperature = Annotated[float, Field(ge=0)]


class _Section(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AppSettings(_Section):
    env: Literal["development", "production"]
    startup_checks: bool


class PathSettings(_Section):
    source_dir: Path
    markdown_dir: Path


class ServiceSettings(_Section):
    embedding_url: str
    rerank_url: str
    qdrant_url: str
    ollama_url: str


class EmbeddingModel(_Section):
    name: str
    vector_size: Positive


class RerankerModel(_Section):
    name: str
    max_length: Positive


class ModelSettings(_Section):
    embedding: EmbeddingModel
    reranker: RerankerModel
    llm_chat: str
    llm_intent: OptionalStr = None
    llm_extraction: OptionalStr = None


class EmbeddingSettings(_Section):
    query_timeout_s: PositiveFloat
    batch_size: Positive
    batch_timeout_s: PositiveFloat


class VectorStoreSettings(_Section):
    collection: str
    upsert_batch: Positive


class ChunkingSettings(_Section):
    synth_section_chars: Positive
    max_table_rows: Positive
    table_group_rows: Positive


class RetrievalSettings(_Section):
    top_k: Positive
    top_n: Positive
    rerank_pool: Positive
    rrf_k: Positive
    min_routed_candidates: NonNegative


class RerankingSettings(_Section):
    timeout_s: PositiveFloat
    doc_cap_chars: Positive
    doc_back_chars: NonNegative


class ChatLlmSettings(_Section):
    timeout_s: PositiveFloat
    num_ctx: Positive
    max_new_tokens: Positive
    temperature: Temperature
    keep_alive: str
    history_turns: NonNegative


class ContextSettings(_Section):
    chars_per_token: Positive
    prompt_reserve_tokens: Positive
    max_block_chars: Positive
    min_block_chars: Positive
    source_abs_floor: Annotated[float, Field(ge=0)]
    source_rel_floor: Annotated[float, Field(ge=0, le=1)]


class AuxLlmSettings(_Section):
    """Lời gọi LLM phụ (phân loại intent, trích xuất §6): URL rỗng = dùng URL chung."""

    enabled: bool
    url: OptionalStr = None
    timeout_s: PositiveFloat
    num_ctx: Positive
    temperature: Temperature
    keep_alive: str


class LlmSettings(_Section):
    chat: ChatLlmSettings
    context: ContextSettings
    intent: AuxLlmSettings
    extraction: AuxLlmSettings

    @property
    def total_context_chars(self) -> int:
        """Trần tổng ký tự ngữ cảnh: phần num_ctx còn lại sau prompt, quy ra ký tự."""
        return (self.chat.num_ctx - self.context.prompt_reserve_tokens) * self.context.chars_per_token


class IngestionSettings(_Section):
    soffice_bin: OptionalStr = None
    convert_timeout_s: PositiveFloat
    max_upload_bytes: Positive
    marker_python: OptionalStr = None


class DatabaseSettings(_Section):
    url: OptionalSecret = None
    host: str
    port: Positive
    name: str
    user: str
    password: SecretStr


class AuthSettings(_Section):
    enabled: bool
    jwt_secret_key: OptionalSecret = None
    jwt_algorithm: str
    jwt_expiration_hours: Positive


class ApiSettings(_Section):
    host: str
    port: Positive
    cors_origins: tuple[str, ...]


class QuerySettings(_Section):
    list_limit_max: Positive
    export_limit_max: Positive
    catalog_row_limit: Positive
    trend_point_cap: Positive
    cache_ttl_s: PositiveFloat


class Settings(_Section):
    app: AppSettings
    paths: PathSettings
    services: ServiceSettings
    models: ModelSettings
    embedding: EmbeddingSettings
    vectorstore: VectorStoreSettings
    chunking: ChunkingSettings
    retrieval: RetrievalSettings
    reranking: RerankingSettings
    llm: LlmSettings
    ingestion: IngestionSettings
    database: DatabaseSettings
    auth: AuthSettings
    api: ApiSettings
    query: QuerySettings

    def llm_model(self, role: LlmRole) -> str:
        """Model cho một vai trò; intent/extraction để trống thì dùng model chat."""
        specific = {"intent": self.models.llm_intent, "extraction": self.models.llm_extraction}
        return specific.get(role) or self.models.llm_chat

    def llm_url(self, role: LlmRole) -> str:
        """URL Ollama cho một vai trò; intent/extraction để trống thì dùng URL chung."""
        specific = {"intent": self.llm.intent.url, "extraction": self.llm.extraction.url}
        return specific.get(role) or self.services.ollama_url


@dataclass
class Chunk:
    """Một đơn vị index: section cha (ngữ cảnh) hoặc đoạn con (được nhúng + tìm)."""

    chunk_id: str               # sha256[:16] của (file + section + text)
    parent_id: str | None       # None với chunk cha
    is_parent: bool
    kind: str                   # "section" | "paragraph" | "table" | "formula"
    text: str                   # nội dung (chunk cha có tiền tố heading)
    section_path: str           # vd. "3 Các phép kiểm định > 3.1 Phép đo"
    file_stem: str              # stem của file .md nguồn (= tên docx)
```

`Chunk` chép NGUYÊN các trường từ `index/chunker.py:20-29`; Task 4 mới đổi chỗ dùng.

- [ ] **Step 5: Viết `core/settings_loader.py`**

```python
"""Nạp config/settings.yaml: thay ${VAR:-mặc_định} từ môi trường rồi kiểm schema.

Đây là chỗ DUY NHẤT trong backend đọc biến môi trường để lấy cấu hình. Code khác gọi
``get_settings()`` tại thời điểm dùng (không lưu vào hằng module lúc import), nên test
đổi cấu hình bằng fixture ``settings_override`` thay vì monkeypatch từng hằng số.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from pydantic import ValidationError

from core.schema import Settings

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = REPO_ROOT / "config"
SETTINGS_FILE_ENV = "QTKD_SETTINGS_FILE"
LOAD_DOTENV_ENV = "QTKD_LOAD_DOTENV"
_PATH_SECTION = "paths"
_ENV_REF_RE = re.compile(r"\$\{([A-Z][A-Z0-9_]*)(?::-([^}]*))?\}")

# Fixture settings_override đặt biến này; get_settings() trả nó nếu có.
_override: Settings | None = None


class SettingsError(RuntimeError):
    """settings.yaml sai cú pháp, thiếu biến môi trường bắt buộc hoặc sai schema."""


def interpolate(value: Any, env: Mapping[str, str]) -> Any:
    """Thay mọi ${VAR} / ${VAR:-mặc_định} trong chuỗi, đi đệ quy qua dict và list."""
    if isinstance(value, dict):
        return {key: interpolate(item, env) for key, item in value.items()}
    if isinstance(value, list):
        return [interpolate(item, env) for item in value]
    if isinstance(value, str):
        return _ENV_REF_RE.sub(lambda match: _resolve(match, env), value)
    return value


def _resolve(match: re.Match[str], env: Mapping[str, str]) -> str:
    name, default = match.group(1), match.group(2)
    value = env.get(name)
    if value:
        return value
    if default is None:
        raise SettingsError(f"Thiếu biến môi trường bắt buộc {name}")
    return default


def load_yaml(path: Path, env: Mapping[str, str]) -> Any:
    """Đọc một file YAML cấu hình và thay biến môi trường."""
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise SettingsError(f"Không đọc được {path}: {exc}") from exc
    return interpolate(raw, env)


def _absolute_paths(raw: dict[str, Any]) -> dict[str, Any]:
    paths = {
        key: str(value if Path(value).is_absolute() else REPO_ROOT / value)
        for key, value in (raw.get(_PATH_SECTION) or {}).items()
    }
    return {**raw, _PATH_SECTION: paths}


def _default_env() -> Mapping[str, str]:
    if os.environ.get(LOAD_DOTENV_ENV, "1") != "0":
        load_dotenv(REPO_ROOT / ".env", override=False)
    return os.environ


def load_settings(path: Path | None = None, env: Mapping[str, str] | None = None) -> Settings:
    """Nạp + kiểm settings. ``env=None`` dùng os.environ (sau khi đọc .env nếu có)."""
    source = _default_env() if env is None else env
    settings_path = path or Path(source.get(SETTINGS_FILE_ENV) or CONFIG_DIR / "settings.yaml")
    raw = load_yaml(settings_path, source)
    if not isinstance(raw, dict):
        raise SettingsError(f"{settings_path} phải là một mapping YAML")
    try:
        return Settings.model_validate(_absolute_paths(raw))
    except ValidationError as exc:
        raise SettingsError(f"{settings_path} không hợp lệ:\n{exc}") from exc


@lru_cache(maxsize=1)
def _cached() -> Settings:
    return load_settings()


def get_settings() -> Settings:
    """Settings của tiến trình (nạp một lần); test override qua fixture settings_override."""
    return _override if _override is not None else _cached()


def reset_settings() -> None:
    """Bỏ cache để lần gọi sau đọc lại file + môi trường."""
    _cached.cache_clear()


def with_overrides(settings: Settings, overrides: Mapping[str, Any]) -> Settings:
    """Bản sao settings với vài khóa đổi giá trị, khóa dạng "retrieval.top_k"."""
    data = settings.model_dump()
    for dotted, value in overrides.items():
        node = data
        *parents, leaf = dotted.split(".")
        for part in parents:
            if not isinstance(node.get(part), dict):
                raise SettingsError(f"Khóa cấu hình không tồn tại: {dotted}")
            node = node[part]
        if leaf not in node:
            raise SettingsError(f"Khóa cấu hình không tồn tại: {dotted}")
        node[leaf] = value
    try:
        return Settings.model_validate(data)
    except ValidationError as exc:
        raise SettingsError(f"Override không hợp lệ:\n{exc}") from exc


def _lookup(settings: Settings, dotted: str) -> Any:
    node: Any = settings
    for part in dotted.split("."):
        if not hasattr(node, part):
            raise SettingsError(f"Khóa cấu hình không tồn tại: {dotted}")
        node = getattr(node, part)
    return node


def main(argv: list[str] | None = None) -> int:
    """CLI cho shell/Makefile: ``python -m core.settings_loader get models.llm_chat``."""
    parser = argparse.ArgumentParser(prog="python -m core.settings_loader")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("get").add_argument("key")
    args = parser.parse_args(argv)
    print(_lookup(get_settings(), args.key))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

`model_dump()` trả `SecretStr` nguyên object, `model_validate` nhận lại được, nên override không làm lộ bí mật.
CLI in `SecretStr` thành `**********`: đúng ý (không lộ bí mật ra terminal).

- [ ] **Step 6: Fixture test trong `tests/conftest.py`**

Thêm NGAY sau các import của `tests/conftest.py`, trước mọi import module dự án:

```python
import os

# Test không phụ thuộc .env của máy dev và không gọi service lúc khởi động.
os.environ["QTKD_LOAD_DOTENV"] = "0"
os.environ["QTKD_STARTUP_CHECKS"] = "false"
```

Thêm fixture:

```python
@pytest.fixture(autouse=True)
def _fresh_settings():
    """Mỗi test bắt đầu với settings đọc lại từ file + môi trường hiện tại."""
    from core import settings_loader

    settings_loader.reset_settings()
    yield
    settings_loader.reset_settings()


@pytest.fixture
def settings_override(monkeypatch):
    """Đổi vài khóa cấu hình trong một test: settings_override({"retrieval.top_k": 5})."""
    from core import settings_loader

    def apply(overrides: dict):
        new = settings_loader.with_overrides(settings_loader.get_settings(), overrides)
        monkeypatch.setattr(settings_loader, "_override", new)
        return new

    return apply
```

- [ ] **Step 7: Thêm phụ thuộc**

`requirements.txt` và `requirements-app.txt` thêm:

```
pyyaml>=6.0        # đọc config/settings.yaml + logging.yaml (core/settings_loader.py)
pydantic>=2.5      # schema cấu hình (core/schema.py)
```
`requirements-dev.txt` thêm đúng hai dòng đó (file này tự khai đủ phụ thuộc như các khối khác của nó).
Cài vào `.venv-dev`: `.venv-dev/bin/python -m pip install -r requirements-dev.txt`.

- [ ] **Step 8: Chạy test, xác nhận PASS**

Run: `.venv-dev/bin/python -m pytest tests/unit/core -q`
Expected: PASS toàn bộ.

Run: `make check`
Expected: xanh, số test = baseline + số test mới.

- [ ] **Step 9: Commit**

```bash
git add config/settings.yaml core/__init__.py core/schema.py core/settings_loader.py \
  tests/conftest.py tests/unit/core requirements.txt requirements-app.txt requirements-dev.txt
git commit -m "feat(core): load every runtime setting and model name from config/settings.yaml"
```

---

### Task 3: `config/logging.yaml` + `core/logging_setup.py`

**Files:**
- Create: `config/logging.yaml`
- Create: `core/logging_setup.py`
- Modify: `.gitignore` (thêm `logs/*.log*`)
- Modify: `tests/conftest.py` (file log của test nằm ngoài repo)
- Test: `tests/unit/core/test_logging_setup.py`

**Interfaces:**
- Consumes: `core.settings_loader.load_yaml`, `CONFIG_DIR`, `REPO_ROOT`
- Produces: `core.logging_setup.configure_logging(path: Path | None = None, env: Mapping[str, str] | None = None) -> None` (gọi lại không nhân đôi handler)

- [ ] **Step 1: Viết `config/logging.yaml`**

```yaml
# Cấu hình logging (logging.config.dictConfig), nạp bởi core/logging_setup.py.
# Hỗ trợ ${TÊN:-mặc_định} như settings.yaml.
version: 1
disable_existing_loggers: false

formatters:
  console:
    format: "%(asctime)s %(levelname)-7s %(name)s - %(message)s"
    datefmt: "%H:%M:%S"
  file:
    format: "%(asctime)s %(levelname)s pid=%(process)d %(name)s - %(message)s"

handlers:
  console:
    class: logging.StreamHandler
    stream: ext://sys.stderr
    formatter: console
  file:
    class: logging.handlers.RotatingFileHandler
    filename: ${LOG_FILE:-logs/app.log}
    maxBytes: 10485760
    backupCount: 5
    encoding: utf-8
    formatter: file

loggers:
  httpx: {level: WARNING}
  httpcore: {level: WARNING}
  urllib3: {level: WARNING}
  qdrant_client: {level: WARNING}
  uvicorn.access: {level: "${LOG_LEVEL_ACCESS:-INFO}"}

root:
  level: "${LOG_LEVEL:-INFO}"
  handlers: [console, file]
```

- [ ] **Step 2: Viết test (RED)**

`tests/unit/core/test_logging_setup.py`:

```python
"""configure_logging: đọc logging.yaml, tạo thư mục log, gọi lại không nhân đôi handler."""

import logging

from core import logging_setup


def _flush():
    for handler in logging.getLogger().handlers:
        handler.flush()


def test_configure_logging_writes_to_configured_file(tmp_path):
    log_file = tmp_path / "sub" / "app.log"
    logging_setup.configure_logging(env={"LOG_FILE": str(log_file), "LOG_LEVEL": "INFO"})
    logging.getLogger("qtkd.test").info("xin chào")
    _flush()
    assert "xin chào" in log_file.read_text(encoding="utf-8")


def test_configure_logging_is_idempotent(tmp_path):
    env = {"LOG_FILE": str(tmp_path / "app.log")}
    logging_setup.configure_logging(env=env)
    first = len(logging.getLogger().handlers)
    logging_setup.configure_logging(env=env)
    assert len(logging.getLogger().handlers) == first


def test_level_comes_from_env(tmp_path):
    logging_setup.configure_logging(env={"LOG_FILE": str(tmp_path / "a.log"), "LOG_LEVEL": "WARNING"})
    assert logging.getLogger().level == logging.WARNING


def test_relative_log_file_resolves_against_repo_root(tmp_path, monkeypatch):
    monkeypatch.setattr(logging_setup, "REPO_ROOT", tmp_path)
    logging_setup.configure_logging(env={"LOG_FILE": "logs/x.log"})
    assert (tmp_path / "logs").is_dir()
```

- [ ] **Step 3: Chạy test, xác nhận FAIL**

Run: `.venv-dev/bin/python -m pytest tests/unit/core/test_logging_setup.py -q`
Expected: FAIL `cannot import name 'logging_setup'`.

- [ ] **Step 4: Viết `core/logging_setup.py`**

```python
"""Bật logging cho mọi entrypoint (API, CLI index, eval) từ config/logging.yaml."""

from __future__ import annotations

import logging
import logging.config
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from core.settings_loader import CONFIG_DIR, REPO_ROOT, load_yaml

LOGGING_FILE_ENV = "QTKD_LOGGING_FILE"


def _resolve_file_handlers(config: dict[str, Any]) -> dict[str, Any]:
    handlers = {}
    for name, handler in (config.get("handlers") or {}).items():
        filename = handler.get("filename")
        if filename:
            path = Path(filename)
            path = path if path.is_absolute() else REPO_ROOT / path
            path.parent.mkdir(parents=True, exist_ok=True)
            handler = {**handler, "filename": str(path)}
        handlers[name] = handler
    return {**config, "handlers": handlers}


def configure_logging(path: Path | None = None, env: Mapping[str, str] | None = None) -> None:
    """Áp logging.yaml; gọi lại an toàn (đóng handler cũ của root trước khi áp)."""
    source = os.environ if env is None else env
    config_path = path or Path(source.get(LOGGING_FILE_ENV) or CONFIG_DIR / "logging.yaml")
    config = _resolve_file_handlers(load_yaml(config_path, source))
    root = logging.getLogger()
    for handler in root.handlers[:]:
        root.removeHandler(handler)
        handler.close()
    logging.config.dictConfig(config)
```

- [ ] **Step 5: Log của test không ghi vào repo**

Trong `tests/conftest.py`, ngay dưới hai dòng `os.environ[...]` của Task 2:

```python
import tempfile

os.environ.setdefault("LOG_FILE", str(Path(tempfile.gettempdir()) / "qtkd-test.log"))
```
(`Path` đã được import sẵn trong `tests/conftest.py`.)

`.gitignore` thêm dưới khối `# Performance logs`:

```
logs/*.log*
```

- [ ] **Step 6: Chạy test, PASS + make check**

Run: `.venv-dev/bin/python -m pytest tests/unit/core -q && make check`
Expected: PASS, `make check` xanh.

- [ ] **Step 7: Commit**

```bash
git add config/logging.yaml core/logging_setup.py tests/unit/core/test_logging_setup.py tests/conftest.py .gitignore
git commit -m "feat(core): configure logging from config/logging.yaml"
```

---

### Task 4: `core/latex.py` + `Chunk` dùng chung

**Files:**
- Move: `latex.py` → `core/latex.py`
- Modify: `index/chunker.py` (bỏ định nghĩa `Chunk`, import từ `core.schema`)
- Modify importer của `latex`: `api_server.py`, `app.py`, `ingestion/extract_pdf.py`, test
- Move test: `tests/unit/llm/test_latex_fix.py` → `tests/unit/core/test_latex_fix.py`

**Interfaces:**
- Produces: `core.latex.fix_latex(text: str) -> str` (không đổi); `core.schema.Chunk` (có từ Task 2)

- [ ] **Step 1: Di chuyển**

```bash
git mv latex.py core/latex.py
git mv tests/unit/llm/test_latex_fix.py tests/unit/core/test_latex_fix.py
```

- [ ] **Step 2: Sửa import**

```bash
git grep -lE '^(from latex import|import latex$)' -- '*.py' | xargs sed -i -E 's/^from latex import/from core.latex import/; s/^import latex$/from core import latex/'
```
Trong `index/chunker.py`: xóa `@dataclass class Chunk ...` (dòng 20-29), xóa import `dataclass` / `Optional` nếu không còn dùng, thêm `from core.schema import Chunk`.
`index.chunker.Chunk` vẫn truy cập được vì tên đã được import vào module, nên `kotaemon_ext/reader.py`, `index/embed_store.py` và test chưa cần sửa ở task này.

- [ ] **Step 3: Kiểm**

Run: `git grep -nE '^(from latex |import latex$)' -- '*.py'`
Expected: không có dòng nào.

Run: `make check`
Expected: xanh. `test_latex_delimiters.py` và `test_doc_viewer.py` (import `app`) vẫn PASS.

- [ ] **Step 4: Commit**

```bash
git add -A core/latex.py latex.py index/chunker.py api_server.py app.py ingestion/extract_pdf.py tests/unit/core tests/unit/llm
git commit -m "refactor: move fix_latex and the Chunk schema into core"
```

---

### Task 5: `embedding/` (embedder, batch_embed, sparse_embedder)

**Files:**
- Create: `embedding/__init__.py` (rỗng), `embedding/embedder.py`, `embedding/batch_embed.py`, `embedding/sparse_embedder.py`
- Modify: `retrieval/retriever.py` (xóa `embed_query`, `EMBED_URL`, `EMBED_TIMEOUT`; gọi `embedder.embed_query`)
- Modify: `index/embed_store.py` (xóa `embed_texts`, `embed_chunks_batched` và hằng đi kèm; gọi `batch_embed`)
- Modify: `retrieval/bm25_index.py` (xóa `tokenize`, `_corpus_text`, `_SPLIT_RE`; dùng `sparse_embedder`)
- Modify: `eval/run_eval.py` (import `embed_query`)
- Test: `tests/unit/embedding/test_embedder.py` (mới); move `tests/unit/backend/test_bm25_tokenizer.py` → `tests/unit/embedding/test_sparse_embedder.py`; sửa test patch `embed_texts`/`embed_query`

**Interfaces:**
- Consumes: `get_settings().services.embedding_url`, `.embedding.*`, `.models.embedding.vector_size`; `core.schema.Chunk`
- Produces:
  - `embedding.embedder.embed_texts(texts: list[str], *, timeout: float | None = None) -> list[list[float]]` (mặc định `embedding.batch_timeout_s`)
  - `embedding.embedder.embed_query(text: str) -> list[float]` (timeout `embedding.query_timeout_s`)
  - `embedding.batch_embed.embed_chunks_batched(chunks: Sequence[Chunk]) -> list[list[float]]`
  - `embedding.sparse_embedder.tokenize(text: str) -> list[str]`
  - `embedding.sparse_embedder.sparse_document_text(payload: dict) -> str` (là `_corpus_text` cũ)

- [ ] **Step 1: Test embedder (RED)**

`tests/unit/embedding/test_embedder.py`:

```python
"""Client service embedding: một chỗ duy nhất gọi /v1/embeddings."""

import json

import responses

from embedding import embedder


@responses.activate
def test_embed_texts_orders_by_index_and_posts_to_configured_url(settings_override):
    settings_override({"services.embedding_url": "http://emb.test/v1/embeddings"})
    responses.post(
        "http://emb.test/v1/embeddings",
        json={"data": [{"index": 1, "embedding": [2.0]}, {"index": 0, "embedding": [1.0]}]},
    )
    assert embedder.embed_texts(["a", "b"]) == [[1.0], [2.0]]
    assert json.loads(responses.calls[0].request.body) == {"input": ["a", "b"], "model": "model"}


@responses.activate
def test_embed_query_returns_single_vector(settings_override):
    settings_override({"services.embedding_url": "http://emb.test/v1/embeddings"})
    responses.post("http://emb.test/v1/embeddings", json={"data": [{"index": 0, "embedding": [0.5, 0.5]}]})
    assert embedder.embed_query("câu hỏi") == [0.5, 0.5]
```

Run: `.venv-dev/bin/python -m pytest tests/unit/embedding -q`
Expected: FAIL `No module named 'embedding'`.

- [ ] **Step 2: Viết `embedding/embedder.py`**

```python
"""Client của service embedding (OpenAI-compat /v1/embeddings, bge-m3 1024 chiều).

Trước đây có hai bản sao (retrieval/retriever.embed_query + index/embed_store.embed_texts)
khác nhau mỗi timeout; nay là một client, timeout tách theo việc dùng.
"""

from __future__ import annotations

import requests

from core.settings_loader import get_settings

# Service chỉ phục vụ một model; trường "model" của giao thức OpenAI chỉ để request hợp lệ.
_PROTOCOL_MODEL_FIELD = "model"


def embed_texts(texts: list[str], *, timeout: float | None = None) -> list[list[float]]:
    """Nhúng một lô văn bản, trả vector theo đúng thứ tự đầu vào."""
    settings = get_settings()
    resp = requests.post(
        settings.services.embedding_url,
        json={"input": texts, "model": _PROTOCOL_MODEL_FIELD},
        timeout=timeout or settings.embedding.batch_timeout_s,
    )
    resp.raise_for_status()
    data = sorted(resp.json()["data"], key=lambda item: item["index"])
    return [item["embedding"] for item in data]


def embed_query(text: str) -> list[float]:
    """Nhúng một câu hỏi (timeout ngắn hơn lô index)."""
    return embed_texts([text], timeout=get_settings().embedding.query_timeout_s)[0]
```

- [ ] **Step 3: Viết `embedding/batch_embed.py`**

Chuyển NGUYÊN `_QTKD_TITLES`, `_QTKD_NUMBER_RE`, `_qtkd_prefix`, `embed_chunks_batched` từ `index/embed_store.py:52-122`, chỉ đổi:
- `BATCH_SIZE` → `settings.batch_size` với `settings = get_settings().embedding` đọc đầu hàm
- `VECTOR_SIZE` → `get_settings().models.embedding.vector_size`
- `embed_texts(...)` → `embedder.embed_texts(...)`
- `print(f"\n  [warn] ...")` → `logger.warning(...)` cùng nội dung; `print(f"  embedded ...", end="\r")` → `logger.info("embedded %d/%d", done, total)`; xóa `print()` cuối hàm.

Đầu file:

```python
"""Nhúng chunk theo lô cho bước index; lô lỗi HTTP 500 thì thử lại từng chunk."""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Sequence

import requests

from core.schema import Chunk
from core.settings_loader import get_settings
from embedding import embedder

logger = logging.getLogger(__name__)
```

- [ ] **Step 4: Viết `embedding/sparse_embedder.py`**

Chuyển NGUYÊN `_SPLIT_RE`, `tokenize`, `_corpus_text` từ `retrieval/bm25_index.py:19-54`; đổi tên `_corpus_text` → `sparse_document_text` (thành public vì `hybrid_index` dùng). Giữ nguyên chú thích giải thích vì sao tokenizer giữ mã/đơn vị.

```python
"""Biểu diễn thưa (bag-of-tokens) cho nhánh BM25 của truy hồi lai.

Tokenizer CỐ Ý giữ nguyên mã kỹ thuật và đơn vị (vd. `1.061:2021`, `MPa`): dense
embedding làm mờ chúng, BM25 là nhánh duy nhất khớp chính xác ký hiệu / số QTKĐ.
"""
```

- [ ] **Step 5: Cập nhật nơi dùng**

- `retrieval/retriever.py`: xóa `EMBED_URL`, `EMBED_TIMEOUT`, `def embed_query`; thêm `from embedding import embedder`; trong `retrieve()` đổi `embed_query(expanded)` → `embedder.embed_query(expanded)`.
- `index/embed_store.py`: xóa phần đã chuyển; thêm `from embedding import batch_embed`; `embed_chunks_batched(chunks)` → `batch_embed.embed_chunks_batched(chunks)`.
- `retrieval/bm25_index.py`: xóa phần đã chuyển; `from embedding.sparse_embedder import sparse_document_text, tokenize`; `_corpus_text(...)` → `sparse_document_text(...)`.
- `git mv tests/unit/backend/test_bm25_tokenizer.py tests/unit/embedding/test_sparse_embedder.py`, đổi import sang `embedding.sparse_embedder`.
- Test và eval còn dùng tên cũ:

Run: `git grep -nE 'embed_query|embed_texts|embed_chunks_batched|_corpus_text|BM\.tokenize|bm25_index import tokenize' -- tests eval scripts`
Đổi: `monkeypatch.setattr(R, "embed_query", f)` → `monkeypatch.setattr("embedding.embedder.embed_query", f)`; `monkeypatch.setattr(ES, "embed_texts", f)` → `monkeypatch.setattr("embedding.embedder.embed_texts", f)`; `eval/run_eval.py` import `embed_query` từ `retrieval.retriever` → `from embedding.embedder import embed_query`.

- [ ] **Step 6: Chạy test**

Run: `.venv-dev/bin/python -m pytest tests/unit/embedding tests/unit/backend/test_embed_store.py tests/unit/backend/test_retriever_pipeline.py -q && make check`
Expected: PASS, `make check` xanh.

Run: `git grep -nE 'def embed_(query|texts)' -- '*.py'`
Expected: chỉ `embedding/embedder.py`.

- [ ] **Step 7: Commit**

```bash
git add -A embedding retrieval/retriever.py retrieval/bm25_index.py index/embed_store.py eval/run_eval.py tests
git commit -m "refactor: extract the embedding package (one embedding client, batch and sparse embedders)"
```

---

### Task 6: `vectorstore/` (qdrant, upsert, index, hybrid_index) + `ingestion/chunker.py`

**Files:**
- Create: `vectorstore/__init__.py` (rỗng), `vectorstore/qdrant.py`, `vectorstore/upsert.py`
- Move: `index/embed_store.py` → `vectorstore/index.py` (rồi tách phần sang `qdrant.py`, `upsert.py`)
- Move: `retrieval/bm25_index.py` → `vectorstore/hybrid_index.py`
- Move: `index/chunker.py` → `ingestion/chunker.py`; xóa `index/` (gồm `__init__.py`)
- Modify: `retrieval/retriever.py` (xóa `_client`, `_get_client`, `dense_search`, `fetch_parent`, `COLLECTION`, `QDRANT_URL`)
- Modify: `retrieval/router.py` (dùng `qdrant.get_client()` + `qdrant.collection_name()`)
- Modify: `ingestion_jobs.py`, `kotaemon_ext/reader.py`, `eval/run_eval.py`, `Makefile` (`reindex`), `docker-compose.yml` (`indexer.command`), `run.sh` (`--index`)
- Modify: `tests/conftest.py` (`_SINGLETONS`)
- Move test: `test_embed_store.py` → `tests/unit/vectorstore/test_index.py`; `test_chunker.py` → `tests/unit/ingestion/test_chunker.py`
- Test: `tests/unit/vectorstore/test_qdrant.py` (mới)

**Interfaces:**
- Consumes: `get_settings().services.qdrant_url`, `.vectorstore.*`, `.models.embedding.vector_size`, `.chunking.*`, `.paths.markdown_dir`; `embedding.batch_embed`, `embedding.sparse_embedder`
- Produces:
  - `vectorstore.qdrant.get_client() -> QdrantClient` (singleton `_client`)
  - `vectorstore.qdrant.collection_name() -> str`
  - `vectorstore.qdrant.ensure_collection(client: QdrantClient) -> None`
  - `vectorstore.qdrant.indexed_files(client: QdrantClient) -> set[str]`
  - `vectorstore.qdrant.delete_file_chunks(client: QdrantClient, file_stem: str) -> None`
  - `vectorstore.qdrant.dense_search(vec: list[float], top_k: int | None = None, file_stem: str | None = None) -> list[dict]`
  - `vectorstore.qdrant.fetch_parent(parent_id_hex: str) -> dict | None`
  - `vectorstore.qdrant.scroll_child_payloads() -> list[dict]` (là `_scroll_child_chunks` cũ)
  - `vectorstore.qdrant.collection_vector_size(name: str) -> int | None` (None nếu chưa có collection; dùng ở Task 10)
  - `vectorstore.upsert.upsert_points(client: QdrantClient, points: list[PointStruct]) -> None`
  - `vectorstore.upsert.index_chunks(client: QdrantClient, chunks: list[Chunk]) -> int`
  - `vectorstore.index.index_directory(md_dir: Path | None = None, force: bool = False) -> dict`
  - `vectorstore.index.main() -> None`; CLI `python -m vectorstore.index [--force] [--query ...]`
  - `vectorstore.hybrid_index.bm25_search(query: str, top_k: int | None = None, file_stem: str | None = None) -> list[dict]`
  - `vectorstore.hybrid_index.invalidate() -> None`
  - `ingestion.chunker.parse_file(md_path: Path) -> list[Chunk]`, `parse_directory(md_dir: Path) -> list[Chunk]`

- [ ] **Step 1: Di chuyển (commit a)**

```bash
mkdir -p vectorstore tests/unit/vectorstore
touch vectorstore/__init__.py
git mv index/embed_store.py vectorstore/index.py
git mv retrieval/bm25_index.py vectorstore/hybrid_index.py
git mv index/chunker.py ingestion/chunker.py
git rm index/__init__.py
git mv tests/unit/backend/test_embed_store.py tests/unit/vectorstore/test_index.py
git mv tests/unit/backend/test_chunker.py tests/unit/ingestion/test_chunker.py
git grep -lE 'index\.embed_store|index\.chunker|retrieval\.bm25_index|from \.chunker import|from \.bm25_index import' -- '*.py' Makefile docker-compose.yml run.sh \
  | xargs sed -i -E 's/index\.embed_store/vectorstore.index/g; s/index\.chunker/ingestion.chunker/g; s/retrieval\.bm25_index/vectorstore.hybrid_index/g; s/from \.chunker import/from ingestion.chunker import/; s/from \.bm25_index import/from vectorstore.hybrid_index import/'
```
Sửa tay những dạng sed không bắt: `import index.embed_store as ES` → `import vectorstore.index as ES`; `retrieval/retriever.py` có `from .bm25_index import bm25_search` trong thân `retrieve()` (đã thành `from vectorstore.hybrid_index import bm25_search`, kiểm lại).
`tests/conftest.py` `_SINGLETONS`: `"retrieval.bm25_index"` → `"vectorstore.hybrid_index"`.

Run: `git grep -nE 'index\.embed_store|index\.chunker|bm25_index|^from index\b|^import index\b' -- ':!docs'`
Expected: không còn dòng nào.

Run: `make check`
Expected: xanh.

```bash
git add -A vectorstore ingestion/chunker.py index retrieval tests ingestion_jobs.py kotaemon_ext eval Makefile docker-compose.yml run.sh
git commit -m "refactor: move indexing, the BM25 index and the chunker into vectorstore/ and ingestion/"
```

- [ ] **Step 2: Test qdrant (RED)**

`tests/unit/vectorstore/test_qdrant.py`:

```python
"""Lớp truy cập Qdrant: client duy nhất, collection + URL lấy từ settings."""

from types import SimpleNamespace

from vectorstore import qdrant


class _FakeClient:
    def __init__(self):
        self.calls = []

    def query_points(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(points=[SimpleNamespace(id=1, score=0.9, payload={"text": "t"})])


def test_get_client_is_singleton_with_configured_url(monkeypatch, settings_override):
    settings_override({"services.qdrant_url": "http://q.test:6333"})
    created = []
    monkeypatch.setattr(qdrant, "QdrantClient", lambda url: created.append(url) or object())
    monkeypatch.setattr(qdrant, "_client", None)
    assert qdrant.get_client() is qdrant.get_client()
    assert created == ["http://q.test:6333"]


def test_dense_search_filters_children_and_file(monkeypatch, settings_override):
    settings_override({"vectorstore.collection": "c_test", "retrieval.top_k": 7})
    fake = _FakeClient()
    monkeypatch.setattr(qdrant, "get_client", lambda: fake)
    hits = qdrant.dense_search([0.0], file_stem="QTKD_1.159")
    call = fake.calls[0]
    assert call["collection_name"] == "c_test"
    assert call["limit"] == 7
    assert [c.key for c in call["query_filter"].must] == ["is_parent", "file_stem"]
    assert hits == [{"id": 1, "score": 0.9, "payload": {"text": "t"}}]


def test_collection_vector_size_none_when_missing(monkeypatch):
    fake = SimpleNamespace(get_collections=lambda: SimpleNamespace(collections=[]))
    monkeypatch.setattr(qdrant, "get_client", lambda: fake)
    assert qdrant.collection_vector_size("qtkd_rag") is None
```

Run: `.venv-dev/bin/python -m pytest tests/unit/vectorstore/test_qdrant.py -q`
Expected: FAIL `cannot import name 'qdrant'`.

- [ ] **Step 3: Viết `vectorstore/qdrant.py` (commit b)**

Gom vào đây, chuyển NGUYÊN thân hàm, chỉ thay hằng bằng settings và client bằng `get_client()`:
- `_client` + `_get_client` từ `retrieval/retriever.py:26-33` → `get_client()` dùng `get_settings().services.qdrant_url`
- `dense_search` từ `retrieval/retriever.py:48-65`; `top_k: int | None = None`, trong thân `top_k = top_k or get_settings().retrieval.top_k`
- `fetch_parent` từ `retrieval/retriever.py:200-217`
- `ensure_collection`, `_file_hash`, `indexed_files`, `delete_file_chunks` từ `vectorstore/index.py` (gốc `index/embed_store.py:127-180`); `VECTOR_SIZE` → `get_settings().models.embedding.vector_size`
- `_scroll_child_chunks` từ `vectorstore/hybrid_index.py` → `scroll_child_payloads()`
- Mọi `COLLECTION` trong file → `collection_name()`

```python
"""Truy cập Qdrant: một client cho cả index lẫn truy hồi, collection lấy từ settings."""

from __future__ import annotations

from qdrant_client import QdrantClient

from core.settings_loader import get_settings

_client: QdrantClient | None = None


def get_client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(url=get_settings().services.qdrant_url)
    return _client


def collection_name() -> str:
    return get_settings().vectorstore.collection


def collection_vector_size(name: str) -> int | None:
    """Số chiều vector của collection; None nếu collection chưa tồn tại."""
    client = get_client()
    if name not in {c.name for c in client.get_collections().collections}:
        return None
    return client.get_collection(name).config.params.vectors.size
```
Import thêm đúng các model (`Distance`, `FieldCondition`, `Filter`, `MatchValue`, `VectorParams`, `hashlib`, ...) mà thân hàm chuyển sang dùng; `ruff check` báo thiếu/thừa.

`retrieval/router.py`: thay `QDRANT_URL`, `COLLECTION`, `QdrantClient(url=QDRANT_URL)` bằng `qdrant.get_client()` / `qdrant.collection_name()` (`from vectorstore import qdrant`); xóa `import os` nếu hết dùng.

- [ ] **Step 4: Viết `vectorstore/upsert.py`**

Chuyển NGUYÊN `upsert` (→ `upsert_points`) và `index_chunks` từ `vectorstore/index.py`; `UPSERT_BATCH` → `get_settings().vectorstore.upsert_batch`; gọi `batch_embed.embed_chunks_batched`, `qdrant.collection_name()`.

```python
"""Ghi chunk đã nhúng vào Qdrant (point id = chunk_id hex → uint64, nên index lại là idempotent)."""
```

- [ ] **Step 5: Thu gọn `vectorstore/index.py`**

Chỉ còn `index_directory`, `query` (smoke test CLI), `main`; import `qdrant`, `upsert`, `parse_directory`.
`index_directory(md_dir: Path | None = None, force: bool = False)`: `md_dir = md_dir or get_settings().paths.markdown_dir`.
`main()`: gọi `core.logging_setup.configure_logging()` đầu hàm; `print(...)` báo tiến độ → `logger.info(...)`; riêng kết quả `--query` (đầu ra cho người dùng CLI) giữ `print`.
Docstring đầu file ghi lệnh: `python -m vectorstore.index [--force] [--query "..."]`.

- [ ] **Step 6: Thu gọn `vectorstore/hybrid_index.py`**

Xóa `QDRANT_URL`, `COLLECTION`, `_scroll_child_chunks`; `_ensure_index()` gọi `qdrant.scroll_child_payloads()`; `bm25_search(..., top_k: int | None = None, ...)` → `top_k = top_k or get_settings().retrieval.top_k`.
Docstring: "Nửa thưa của chỉ mục lai: BM25 trong bộ nhớ, dựng lười từ payload chunk con trong Qdrant."

- [ ] **Step 7: `ingestion/chunker.py` đọc settings**

`_SYNTH_SECTION_CHARS`, `_MAX_TABLE_ROWS`, `_TABLE_GROUP_ROWS` → `get_settings().chunking.*`, đọc trong hàm dùng chúng.
Chunker chạy cả ở venv Stage 1: `core.settings_loader` cần pyyaml + pydantic, đã có trong `requirements.txt` từ Task 2.

- [ ] **Step 8: Cập nhật nơi dùng và test**

- `retrieval/retriever.py`: `from vectorstore import hybrid_index, qdrant`; `dense_search(...)` → `qdrant.dense_search(...)`; `bm25_search(...)` → `hybrid_index.bm25_search(...)` (bỏ import trong thân hàm); `fetch_parent` → `qdrant.fetch_parent`.
- `tests/conftest.py` `_SINGLETONS`: `"retrieval.retriever": ["_client"]` → `"vectorstore.qdrant": ["_client"]`.
- Test patch cũ:

Run: `git grep -nE 'R, "(dense_search|fetch_parent|_get_client)"|"retrieval\.retriever\.(dense_search|fetch_parent|_get_client)"|ES\.(upsert|ensure_collection|indexed_files|delete_file_chunks|COLLECTION|VECTOR_SIZE)' -- tests`
Đổi: `monkeypatch.setattr(R, "dense_search", f)` → `monkeypatch.setattr("vectorstore.qdrant.dense_search", f)`; tương tự cho `fetch_parent`, các hàm Qdrant của `ES`.
`tests/unit/qa/test_config_constants.py`: xóa các assert `ES.VECTOR_SIZE`, `ES.COLLECTION`, `BM.COLLECTION`, `RT.COLLECTION` (đã có ở `tests/unit/core/test_settings_values.py`) và import `index.embed_store`/`bm25_index` tương ứng.

- [ ] **Step 9: Chạy test**

Run: `.venv-dev/bin/python -m pytest tests/unit/vectorstore tests/unit/ingestion tests/unit/backend/test_retriever_pipeline.py -q && make check`
Expected: PASS, xanh.

Run: `git grep -nE 'QdrantClient\(' -- '*.py' ':!tests'`
Expected: chỉ `vectorstore/qdrant.py`.

Run: `.venv-dev/bin/python -m vectorstore.index --query "phạm vi van an toàn 1400 bar"` (cần Qdrant + embedding)
Expected: kết quả giống `python -m index.embed_store --query ...` trước đây.

- [ ] **Step 10: Commit**

```bash
git add -A vectorstore ingestion/chunker.py retrieval tests
git commit -m "refactor: one settings-driven Qdrant access layer for indexing and retrieval"
```

---

### Task 7: `reranking/` + tách `retrieval/` (hybrid_retriever, retriever, noise, query_expansion)

**Files:**
- Create: `reranking/__init__.py`, `reranking/reranker.py`
- Create: `retrieval/hybrid_retriever.py`, `retrieval/query_expansion.py`
- Move: `retrieval/_constants.py` → `retrieval/noise.py`
- Modify: `retrieval/retriever.py` (chỉ còn điều phối)
- Modify: `app.py:200`, `api_server.py:347`, `eval/_pipeline.py`, `eval/arch_eval.py:78`, `eval/run_eval.py`
- Delete: `tests/unit/qa/test_config_constants.py`
- Move test: `test_rerank_doc.py` → `tests/unit/reranking/`; `test_rrf_fuse.py`, `test_filter_noise.py`, `test_merge_per_file.py`, `test_retriever_pipeline.py`, `test_router.py`, `test_router_aliases.py` → `tests/unit/retrieval/`; `tests/unit/qa/test_noise_markers_sync.py` → `tests/unit/retrieval/test_noise.py`

**Interfaces:**
- Consumes: `vectorstore.qdrant.dense_search/fetch_parent`, `vectorstore.hybrid_index.bm25_search`, `embedding.embedder.embed_query`
- Produces:
  - `reranking.reranker.build_rerank_doc(payload: dict, parent: dict | None) -> str` (là `_rerank_doc`)
  - `reranking.reranker.rerank_hits(query: str, hits: list[dict], top_n: int | None = None) -> list[dict]`
  - `retrieval.noise.is_noise_path(section_path: str) -> bool`, `NOISE_PATH_MARKERS`
  - `retrieval.query_expansion.expand_query(query: str) -> str` (là `_expand_query`), `LEXICON`
  - `retrieval.hybrid_retriever.rrf_fuse(dense_hits: list[dict], bm25_hits: list[dict], k: int | None = None) -> list[dict]`
  - `retrieval.hybrid_retriever.filter_noise(hits: list[dict]) -> list[dict]` (là `_filter_noise`)
  - `retrieval.hybrid_retriever.merge_per_file(reranked: list[dict], stems: frozenset[str], top_n: int) -> list[dict]` (là `_merge_per_file`)
  - `retrieval.hybrid_retriever.search_both(vec: list[float], expanded_query: str, *, top_k: int, file_stem: str | None = None) -> tuple[list[dict], list[dict]]`
  - `retrieval.retriever.retrieve(query: str, top_k: int | None = None, top_n: int | None = None) -> list[dict]` (đường dẫn import giữ nguyên)

- [ ] **Step 1: Di chuyển test + noise (commit a)**

```bash
mkdir -p tests/unit/reranking tests/unit/retrieval
git mv retrieval/_constants.py retrieval/noise.py
git mv tests/unit/backend/test_rerank_doc.py tests/unit/reranking/test_rerank_doc.py
for f in test_rrf_fuse test_filter_noise test_merge_per_file test_retriever_pipeline test_router test_router_aliases; do
  git mv tests/unit/backend/$f.py tests/unit/retrieval/$f.py
done
git mv tests/unit/qa/test_noise_markers_sync.py tests/unit/retrieval/test_noise.py
git grep -l 'retrieval\._constants' | xargs sed -i 's/retrieval\._constants/retrieval.noise/g'
```
Run: `make check` → xanh.

```bash
git add -A retrieval tests
git commit -m "refactor: group retrieval and reranking tests by package"
```

- [ ] **Step 2: Test cũ là lưới an toàn, đổi import trước (RED)**

Logic được chuyển nguyên nên không cần test mới cho nó; test cũ phải chạy với tên mới. Sửa import trong test TRƯỚC khi viết code:
- `rrf_fuse` → `from retrieval.hybrid_retriever import rrf_fuse`
- `_filter_noise` → `from retrieval.hybrid_retriever import filter_noise`
- `_merge_per_file` → `from retrieval.hybrid_retriever import merge_per_file`
- `_rerank_doc` → `from reranking.reranker import build_rerank_doc`; nếu test đổi `RERANK_DOC_CAP`/`RERANK_DOC_BACK` → `settings_override({"reranking.doc_cap_chars": ..., "reranking.doc_back_chars": ...})`
- `test_retriever_pipeline.py`: patch `R.rerank_hits` → `"reranking.reranker.rerank_hits"`; `"retrieval.router.route_files"` giữ nguyên.

Thêm vào `tests/unit/retrieval/test_rrf_fuse.py`:

```python
def test_rrf_k_comes_from_settings(settings_override):
    from retrieval.hybrid_retriever import rrf_fuse

    settings_override({"retrieval.rrf_k": 1})
    fused = rrf_fuse([{"id": 1, "score": 1.0, "payload": {"chunk_id": "a"}}], [])
    assert fused[0]["rrf_score"] == 1.0 / (1 + 0 + 1)  # 1/(k + rank + 1), rank từ 0
```

Run: `.venv-dev/bin/python -m pytest tests/unit/retrieval tests/unit/reranking -q`
Expected: FAIL `ModuleNotFoundError` cho `retrieval.hybrid_retriever` / `reranking`.

- [ ] **Step 3: Viết `reranking/reranker.py`**

Chuyển NGUYÊN `_rerank_doc` (→ `build_rerank_doc`, giữ nguyên docstring đo đạc Q12/Q18/Q22/Q39/Q48) và `rerank_hits` từ `retrieval/retriever.py:107-197`.
Thay: `RERANK_DOC_CAP`/`RERANK_DOC_BACK` → `get_settings().reranking.doc_cap_chars`/`doc_back_chars`; `RERANK_URL` → `settings.services.rerank_url`; `RERANK_TIMEOUT` → `settings.reranking.timeout_s`; `fetch_parent` → `qdrant.fetch_parent`; `import logging` trong khối `except` → `logger = logging.getLogger(__name__)` ở đầu module; `top_n: int | None = None` → `top_n = top_n or settings.retrieval.top_n`.

- [ ] **Step 4: Viết `retrieval/query_expansion.py`**

Chuyển NGUYÊN `_LEXICON` (→ `LEXICON`) và `_expand_query` (→ `expand_query`) từ `retrieval/retriever.py:67-106`, giữ mọi chú thích.

- [ ] **Step 5: Viết `retrieval/hybrid_retriever.py`**

Chuyển NGUYÊN `_filter_noise` (→ `filter_noise`), `rrf_fuse`, `_merge_per_file` (→ `merge_per_file`) từ `retrieval/retriever.py:219-293`; `k: int = 60` → `k: int | None = None`, trong thân `k = k or get_settings().retrieval.rrf_k`.
Thêm:

```python
def search_both(
    vec: list[float], expanded_query: str, *, top_k: int, file_stem: str | None = None
) -> tuple[list[dict], list[dict]]:
    """Một lượt dense + BM25 trên cùng phạm vi (toàn kho hoặc một file)."""
    dense = qdrant.dense_search(vec, top_k=top_k, file_stem=file_stem)
    sparse = hybrid_index.bm25_search(expanded_query, top_k=top_k, file_stem=file_stem)
    return dense, sparse
```

- [ ] **Step 6: Viết lại `retrieval/retriever.py`**

```python
"""Truy hồi lai đầy đủ: định tuyến → mở rộng truy vấn → dense + BM25 → RRF → lọc nhiễu
→ rerank (cross-encoder trên section cha) → trả chunk con kèm section cha.

Mỗi hit trả về có: payload (chunk con), rerank_score, rrf_score, parent_payload.
"""

from __future__ import annotations

from core.settings_loader import get_settings
from embedding import embedder
from reranking import reranker
from retrieval import hybrid_retriever as hybrid
from retrieval import router
from retrieval.query_expansion import expand_query


def retrieve(query: str, top_k: int | None = None, top_n: int | None = None) -> list[dict]:
    cfg = get_settings().retrieval
    top_k = top_k or cfg.top_k
    top_n = top_n or cfg.top_n
    expanded = expand_query(query)
    vec = embedder.embed_query(expanded)
    stems = router.route_files(query)
    if len(stems) >= 2:
        return _retrieve_per_file(query, vec, expanded, stems, top_k=top_k, top_n=top_n)
    file_stem = next(iter(stems)) if stems else None
    dense, sparse = hybrid.search_both(vec, expanded, top_k=top_k, file_stem=file_stem)
    # Định tuyến thu hẹp quá ít ứng viên: tìm lại toàn kho.
    if file_stem and len(dense) + len(sparse) < cfg.min_routed_candidates:
        dense, sparse = hybrid.search_both(vec, expanded, top_k=top_k)
    fused = hybrid.filter_noise(hybrid.rrf_fuse(dense, sparse))[: cfg.rerank_pool]
    return reranker.rerank_hits(query, fused, top_n=top_n)


def _retrieve_per_file(
    query: str, vec: list[float], expanded: str, stems: frozenset[str], *, top_k: int, top_n: int
) -> list[dict]:
    """Câu so sánh ≥2 thiết bị: chạy phễu RIÊNG cho từng file rồi rerank chung.

    Một phễu toàn kho bị cụm từ vựng áp đảo (3 file áp kế píttông) đè bẹp file thiểu
    số; đo Q115/Q116: top-5 mất hết chunk 'van an toàn' → model từ chối oan.
    """
    pool = max(top_n * 2, get_settings().retrieval.rerank_pool // len(stems))
    fused: list[dict] = []
    for stem in sorted(stems):
        dense, sparse = hybrid.search_both(vec, expanded, top_k=top_k, file_stem=stem)
        fused.extend(hybrid.filter_noise(hybrid.rrf_fuse(dense, sparse))[:pool])
    reranked = reranker.rerank_hits(query, fused, top_n=len(fused))
    return hybrid.merge_per_file(reranked, stems, top_n)
```

Trước khi xóa bản cũ, so từng nhánh với `retrieve()` cũ (`retrieval/retriever.py:295-335`): thứ tự gọi, ngưỡng 6, `RERANK_POOL // len(stems)`, `top_n * 2`, thứ tự `sorted(stems)`.
Test cũ patch `"retrieval.router.route_files"`: code mới gọi `router.route_files` qua module nên patch vẫn có hiệu lực.

- [ ] **Step 7: Thống nhất `top_k` (quyết định 4)**

- `api_server.py:347`: `retrieve(retrieval_query, top_k=50, top_n=5)` → `retrieve(retrieval_query)`
- `app.py:200`: `retrieve(query, top_k=20, top_n=5)` → `retrieve(query)`
- `eval/_pipeline.py`: xóa `TOP_K_PROD`; `production_retrieve(query, top_n=None)` gọi `retrieve(query, top_n=top_n)`; sửa docstring: eval đo đúng phễu của API.
- `eval/arch_eval.py:78`: `retrieve(question, top_k=50, top_n=5)` → `retrieve(question)`
- `eval/run_eval.py`: import `rrf_fuse`, `filter_noise`, ... từ module mới.
- `git rm tests/unit/qa/test_config_constants.py`: assert về `RET.TOP_K`, `RERANK_POOL`, `rrf_fuse k=60` đã có ở `tests/unit/core/test_settings_values.py`; assert `generation.*` cũng có ở đó (`test_context_budget_formula_and_bounds`, `test_defaults_eval_depends_on`).

- [ ] **Step 8: Chạy test + so snapshot truy hồi**

Run: `.venv-dev/bin/python -m pytest tests/unit/retrieval tests/unit/reranking -q && make check`
Expected: PASS, xanh.

Run (service đang chạy):
```bash
PYTHONPATH=. .venv-dev/bin/python ~/.cache/qtkd-refactor/snapshot_retrieval.py 50 > ~/.cache/qtkd-refactor/retrieval_k50_after.json
diff ~/.cache/qtkd-refactor/retrieval_k50.json ~/.cache/qtkd-refactor/retrieval_k50_after.json && echo GIONG_HET
```
Expected: `GIONG_HET`. Lệch dù chỉ một hit là lỗi chuyển code: so lại nhánh tương ứng, không chấp nhận "gần giống".

Run: `.venv-dev/bin/python -m eval.run_eval --mode hybrid | tee ~/.cache/qtkd-refactor/run_eval_after.txt`
Expected: số khác `run_eval_k20.txt` vì eval giờ đo top_k=50 như API. Ghi cả hai bộ số vào commit message.

- [ ] **Step 9: Commit**

```bash
git add -A reranking retrieval app.py api_server.py eval tests
git commit -m "refactor: split retrieval into hybrid retriever, reranking and orchestration; eval measures the API funnel"
```

---

### Task 8: `llm/` (generator, prompt, guards) + `retrieval/context_builder.py`; xóa `generation.py`

**Files:**
- Create: `llm/__init__.py`, `llm/generator.py`, `llm/prompt.py`, `llm/guards.py`, `retrieval/context_builder.py`
- Delete: `generation.py`
- Modify: `api_server.py`, `app.py`, `eval/answer_eval.py`, `eval/arch_eval.py`, `eval/scoring.py` (chú thích), `query/intents.py`, `knowledge/llm_extract.py`
- Move test: `tests/unit/llm/test_context_builder.py`, `test_source_filter.py` → `tests/unit/retrieval/`; `test_messages_builder.py` → `tests/unit/llm/test_prompt.py`; `test_ollama_stream.py` → `tests/unit/llm/test_generator.py`
- Test: `tests/unit/llm/test_guards.py` nếu chưa có test cho `is_calculation_request`/`enforce_refusal_stop` (tìm: `git grep -n 'is_calculation_request\|enforce_refusal_stop' tests`; nếu có ở file khác thì chuyển file đó vào `tests/unit/llm/`)

**Interfaces:**
- Consumes: `get_settings().llm.*`, `.llm_model(role)`, `.llm_url(role)`
- Produces:
  - `llm.generator.native_chat_url(url: str) -> str`
  - `llm.generator.stream_ollama(messages: list[dict], *, model: str | None = None) -> Iterator[str]`
  - `llm.prompt.SYSTEM_TMPL: str`, `llm.prompt.build_messages(query: str, context_str: str, prior: list[list], *, guidance: str | None = None) -> list[dict]`
  - `llm.guards.REFUSAL_SENTENCE: str`, `is_calculation_request(query: str) -> bool`, `enforce_refusal_stop(text: str) -> str`
  - `retrieval.context_builder.filter_by_confidence(results: list[dict]) -> list[dict]`, `window(parent: str, child: str, budget: int) -> str`, `build_context_and_citations(results: list[dict]) -> tuple[str, str]`
  - `query.intents.OllamaIntentConfig.from_settings(settings: Settings | None = None) -> OllamaIntentConfig`; `query.intents.intents_enabled() -> bool`
  - `knowledge.llm_extract.OllamaConfig.from_settings(settings: Settings | None = None) -> OllamaConfig`; `knowledge.llm_extract.llm_extraction_enabled() -> bool`

- [ ] **Step 1: Di chuyển test, sửa import test (RED)**

```bash
git mv tests/unit/llm/test_context_builder.py tests/unit/retrieval/test_context_builder.py
git mv tests/unit/llm/test_source_filter.py tests/unit/retrieval/test_source_filter.py
git mv tests/unit/llm/test_messages_builder.py tests/unit/llm/test_prompt.py
git mv tests/unit/llm/test_ollama_stream.py tests/unit/llm/test_generator.py
```
Trong test: `import generation` / `from generation import X` → import từ module mới theo bảng:

| Tên cũ trong `generation` | Đích mới |
|---|---|
| `filter_by_confidence`, `_window` (→ `window`), `build_context_and_citations` | `retrieval.context_builder` |
| `SOURCE_ABS_FLOOR`, `SOURCE_REL_FLOOR`, `MAX_BLOCK_CHARS`, `MIN_BLOCK_CHARS`, `CHARS_PER_TOKEN`, `PROMPT_RESERVE_TOKENS`, `TOTAL_CONTEXT_CHARS` | `settings.llm.context.*`, `settings.llm.total_context_chars` |
| `SYSTEM_TMPL`, `build_messages` | `llm.prompt` |
| `HISTORY_TURNS` | `settings.llm.chat.history_turns` |
| `REFUSAL_SENTENCE`, `is_calculation_request`, `enforce_refusal_stop` | `llm.guards` |
| `stream_ollama`, `_native_chat_url` (→ `native_chat_url`) | `llm.generator` |
| `OLLAMA_URL`, `OLLAMA_MODEL`, `NUM_CTX`, `MAX_NEW_TOKENS`, `OLLAMA_TIMEOUT` | `settings.llm_url("chat")`, `settings.llm_model("chat")`, `settings.llm.chat.*` |

Test đổi hằng module (vd. `monkeypatch.setattr(generation, "MAX_BLOCK_CHARS", 100)`) → `settings_override({"llm.context.max_block_chars": 100})`.
`test_generator.py`: `monkeypatch.setattr(generation.requests, "post", ...)` → `monkeypatch.setattr("llm.generator.requests.post", ...)`.

Thêm vào `tests/unit/llm/test_generator.py` (dùng lại `_FakeResp` sẵn có trong file; dòng JSON giả dùng đúng dạng các test cũ trong file đang dùng):

```python
def test_stream_ollama_uses_explicit_model_and_settings(monkeypatch, settings_override):
    from llm import generator

    settings_override({"services.ollama_url": "http://o.test/v1/chat/completions", "llm.chat.num_ctx": 4096})
    seen = {}

    def fake_post(url, json, stream, timeout):
        seen.update(url=url, body=json)
        return _FakeResp([b'{"message": {"content": "x"}, "done": true}'])

    monkeypatch.setattr(generator.requests, "post", fake_post)
    out = "".join(generator.stream_ollama([{"role": "user", "content": "q"}], model="m-test"))
    assert out == "x"
    assert seen["url"] == "http://o.test/api/chat"
    assert seen["body"]["model"] == "m-test"
    assert seen["body"]["options"]["num_ctx"] == 4096
```

Run: `.venv-dev/bin/python -m pytest tests/unit/llm tests/unit/retrieval/test_context_builder.py tests/unit/retrieval/test_source_filter.py -q`
Expected: FAIL `No module named 'llm'`.

- [ ] **Step 2: Viết các module mới**

Chuyển NGUYÊN thân hàm/chuỗi từ `generation.py`, giữ mọi chú thích đo đạc:
- `llm/prompt.py`: `SYSTEM_TMPL` (dòng 48-69), `build_messages` (166-189); `HISTORY_TURNS` → `get_settings().llm.chat.history_turns`.
- `llm/guards.py`: `REFUSAL_SENTENCE` (191), `_CALC_IMPERATIVE_RE`, `_CALC_WITH_VALUES_RE`, `_ASSIGNED_VALUE_RE`, `is_calculation_request`, `enforce_refusal_stop` (193-225). Chú thích "khớp `eval.scoring.REFUSAL_CORE`" → "khớp `scoring.answer_scoring.REFUSAL_CORE`" (đường dẫn sau Task 11).
- `llm/generator.py`: `_native_chat_url` → `native_chat_url`; `stream_ollama` (227 đến hết hàm). Phần dựng request:

```python
def stream_ollama(messages: list[dict], *, model: str | None = None) -> Iterator[str]:
    settings = get_settings()
    chat = settings.llm.chat
    resp = requests.post(
        native_chat_url(settings.llm_url("chat")),
        json={
            "model": model or settings.llm_model("chat"),
            "messages": messages,
            "stream": True,
            "keep_alive": chat.keep_alive,
            "options": {
                "num_ctx": chat.num_ctx,
                "num_predict": chat.max_new_tokens,
                "temperature": chat.temperature,
            },
        },
        stream=True,
        timeout=chat.timeout_s,
    )
```
phần đọc stream còn lại giữ nguyên. Giữ docstring "VÌ SAO không dùng /v1/chat/completions"; sửa câu "Đọc OLLAMA_MODEL module-global tại thời điểm gọi" thành "Model: tham số `model`, không có thì `models.llm_chat`". Bỏ `load_dotenv()` (đã ở `settings_loader`).
- `retrieval/context_builder.py`: `filter_by_confidence` (75-89), `_window` → `window` (91-115), `build_context_and_citations` (117-164); hằng → `settings.llm.context.*` và `settings.llm.total_context_chars`.

- [ ] **Step 3: Gộp `_native_chat_url` trùng lặp, cấu hình LLM phụ từ settings**

`query/intents.py` và `knowledge/llm_extract.py` mỗi file có một `_native_chat_url`: xóa, dùng `from llm.generator import native_chat_url`.

`query/intents.py`, thay `from_env` bằng:

```python
    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> OllamaIntentConfig:
        s = settings or get_settings()
        cfg = s.llm.intent
        return cls(
            url=s.llm_url("intent"),
            model=s.llm_model("intent"),
            timeout=int(cfg.timeout_s),
            num_ctx=cfg.num_ctx,
            temperature=cfg.temperature,
            keep_alive=cfg.keep_alive,
        )
```
Xóa `DEFAULT_OLLAMA_URL`, `DEFAULT_MODEL`, `_TRUTHY`; bỏ giá trị mặc định của các trường dataclass `OllamaIntentConfig` (bắt buộc truyền) để settings là nguồn duy nhất. `intents_enabled()` → `return get_settings().llm.intent.enabled` (bỏ tham số `env`).
`knowledge/llm_extract.OllamaConfig`: làm y hệt với role `"extraction"`; `llm_extraction_enabled()` → `get_settings().llm.extraction.enabled`.
Sửa chỗ gọi: `OllamaIntentClassifier.from_env(env)` / `OllamaClient.from_env(env)` → `from_settings(settings)`; `default_classifier()` / `default_client()` gọi `from_settings()`.
Test: `tests/unit/backend/test_llm_extract.py:336` (`OllamaConfig.from_env(env={...})`) → `OllamaConfig.from_settings(load_settings(env={...}))`; `tests/unit/backend/test_llm_extract_db.py:232` (`monkeypatch.setenv("SECTION6_LLM_ENABLED", "1")`) → `settings_override({"llm.extraction.enabled": True})`; mọi test gọi `intents_enabled(env=...)` / `llm_extraction_enabled(env=...)` → `settings_override(...)` rồi gọi không tham số.

Run: `git grep -nE 'from_env|INTENT_ROUTER_ENABLED|SECTION6_LLM_ENABLED|os\.environ' -- query knowledge tests`
Expected: không còn `from_env`; tên biến env không còn trong code Python (chỉ còn ở `config/settings.yaml`, `.env.example`).

- [ ] **Step 4: Cập nhật nơi dùng `generation`**

- `api_server.py`, `app.py`: import theo bảng Step 1.
- `eval/answer_eval.py:71`: xóa `generation.OLLAMA_MODEL = model`, gọi `stream_ollama(messages, model=model)`; dòng 47 `urlsplit(generation.OLLAMA_URL)` → `urlsplit(get_settings().services.ollama_url)`.
- `eval/arch_eval.py:143-145`: `os.environ.get("OLLAMA_URL", ...)` / `os.environ.get("OLLAMA_MODEL", ...)` → `native_chat_url(get_settings().llm_url("chat"))` / `get_settings().llm_model("chat")`.
- `git rm generation.py`

Run: `git grep -nwE 'generation' -- '*.py' Dockerfile docker-compose.yml | grep -vE 'generation\.(py)?\b.*#|"""'`
Expected: không còn import hay tham chiếu tới module `generation` (từ "generation" trong chú thích tiếng Anh không liên quan thì bỏ qua).

- [ ] **Step 5: Chạy test**

Run: `make check`
Expected: xanh (gồm `intent-eval`, `extract-section6-eval`, vốn dựng config qua `from_settings`).

- [ ] **Step 6: Commit**

```bash
git add -A llm retrieval/context_builder.py generation.py api_server.py app.py eval query/intents.py knowledge/llm_extract.py tests
git commit -m "refactor: extract llm/ (generator, prompt, guards) and the context builder; one Ollama URL mapper"
```

---

### Task 9: `ingestion/jobs.py` + db/auth/query/ingestion đọc settings

**Files:**
- Move: `ingestion_jobs.py` → `ingestion/jobs.py`
- Modify: `db/config.py`, `db/migrations/env.py`, `scripts/migrate.py`, `auth/security.py`, `auth/dependencies.py`, `ingestion/convert_legacy.py`, `ingestion/extract_pdf_marker.py`, `query/records.py`, `query/catalogs.py`, `query/catalog_router.py`, `query/router.py`, `query/record_fields.py`, `query/record_signals.py`, `query/signals.py`, `scripts/healthcheck.py`
- Modify importer `ingestion_jobs`: `api_server.py`, `query/source.py`, `records/backfill.py`, `records/ingest.py`, và các test (`git grep -l ingestion_jobs tests`)
- Modify: `tests/conftest.py` (`_fresh_settings` dọn cache khóa JWT)
- Test: `tests/unit/auth/test_jwt_secret.py` (mới)

**Interfaces:**
- Produces:
  - `ingestion.jobs` (giữ nguyên tên hàm public của `ingestion_jobs`); đường dẫn đọc `get_settings().paths.source_dir` / `.markdown_dir` lúc gọi (bỏ hằng `TC_DL_DIR`, `OUT_DIR`, `MAX_UPLOAD_BYTES`)
  - `db.config.get_database_url() -> str` (giữ tên)
  - `auth.security.jwt_secret() -> str` (có `cache_clear()`)

- [ ] **Step 1: Di chuyển (commit a)**

```bash
git mv ingestion_jobs.py ingestion/jobs.py
git grep -lE '\bingestion_jobs\b' -- '*.py' | xargs sed -i -E 's/^import ingestion_jobs$/from ingestion import jobs as ingestion_jobs/; s/^from ingestion_jobs import/from ingestion.jobs import/; s/"ingestion_jobs\./"ingestion.jobs./g'
```
Giữ bí danh `ingestion_jobs` ở nơi dùng để diff nhỏ; đổi tên biến không phải mục tiêu task này.

Run: `git grep -nE '^import ingestion_jobs$|^from ingestion_jobs' ; make check`
Expected: không còn dòng; xanh.

```bash
git add -A ingestion/jobs.py ingestion_jobs.py api_server.py query records tests
git commit -m "refactor: move ingestion_jobs into the ingestion package"
```

- [ ] **Step 2: Test khóa JWT (RED)**

`tests/unit/auth/test_jwt_secret.py`:

```python
"""Khóa JWT: lấy từ cấu hình; dev thiếu khóa thì sinh khóa tạm, ổn định trong tiến trình."""

from auth import security


def test_configured_secret_is_used(settings_override):
    settings_override({"auth.jwt_secret_key": "khoa-that"})
    security.jwt_secret.cache_clear()
    assert security.jwt_secret() == "khoa-that"


def test_missing_secret_in_development_is_random_but_stable(settings_override, caplog):
    settings_override({"auth.jwt_secret_key": None, "app.env": "development"})
    security.jwt_secret.cache_clear()
    first = security.jwt_secret()
    assert len(first) >= 32
    assert security.jwt_secret() == first
    assert "JWT_SECRET_KEY" in caplog.text
```

Run: `.venv-dev/bin/python -m pytest tests/unit/auth -q`
Expected: FAIL `has no attribute 'jwt_secret'`.

- [ ] **Step 3: Đổi sang settings (commit b)**

- `auth/security.py`: xóa `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `JWT_EXPIRATION_HOURS`; thêm

```python
@lru_cache(maxsize=1)
def jwt_secret() -> str:
    """Khóa ký JWT. Thiếu ở development: sinh khóa tạm (token mất hiệu lực khi khởi động lại)."""
    configured = get_settings().auth.jwt_secret_key
    if configured is not None:
        return configured.get_secret_value()
    logger.warning("JWT_SECRET_KEY chưa đặt: dùng khóa tạm cho tiến trình này (chỉ hợp lệ khi dev)")
    return secrets.token_urlsafe(48)
```
`create_access_token` / hàm decode dùng `jwt_secret()`, `get_settings().auth.jwt_algorithm`, `get_settings().auth.jwt_expiration_hours`.
Chặn production thiếu khóa nằm ở `core/startup.py` (Task 10), không ở đây.
`tests/conftest.py` `_fresh_settings`: sau `reset_settings()` thêm

```python
    security = sys.modules.get("auth.security")
    if security is not None:
        security.jwt_secret.cache_clear()
```
(thêm `import sys` nếu chưa có).
- `auth/dependencies.py`: `AUTH_ENABLED` → `get_settings().auth.enabled` đọc trong thân dependency. Test đang patch `AUTH_ENABLED` (`git grep -n AUTH_ENABLED tests`) → `settings_override({"auth.enabled": False})`.
- `db/config.py`: `get_database_url()` đọc `get_settings().database`; có `url` thì trả `url.get_secret_value()`, không thì ghép từ các trường (password `.get_secret_value()`), đúng định dạng chuỗi cũ. `db/migrations/env.py:21` và `scripts/migrate.py:19` gọi `get_database_url()` thay vì đọc `DATABASE_URL`. Test migration dùng `monkeypatch.setenv("DATABASE_URL", url)`: fixture `_fresh_settings` đọc lại env đầu mỗi test, nhưng `setenv` xảy ra GIỮA test, nên thêm `settings_loader.reset_settings()` ngay sau `setenv` trong các test đó (12 chỗ ở `tests/unit/backend/test_migrations_*.py`).
- `ingestion/convert_legacy.py:22,29`: `SOFFICE` → hàm `_soffice_bin()` trả `get_settings().ingestion.soffice_bin or shutil.which("soffice") or "/usr/bin/soffice"`; `TIMEOUT_SECONDS` → `get_settings().ingestion.convert_timeout_s`.
- `ingestion/extract_pdf_marker.py:84`: `os.environ.get("MARKER_PYTHON")` → `get_settings().ingestion.marker_python`.
- `ingestion/jobs.py`: `TC_DL_DIR`, `OUT_DIR`, `MAX_UPLOAD_BYTES` → hàm `_source_dir()`, `_out_dir()` và `get_settings().ingestion.max_upload_bytes`, đọc lúc gọi. Test đang `monkeypatch.setattr(ingestion_jobs, "OUT_DIR", tmp)` / `TC_DL_DIR` (12 chỗ: `git grep -n 'OUT_DIR\|TC_DL_DIR' tests`) → `settings_override({"paths.markdown_dir": str(tmp_out), "paths.source_dir": str(tmp_src)})`.
- `query/*`: `LIST_LIMIT_MAX` (records, catalogs), `EXPORT_LIMIT_MAX`, `_ROW_LIMIT` (catalog_router), `TREND_POINT_CAP`, bốn hằng `*_TTL_SECONDS` → `get_settings().query.*`, đọc lúc dùng. Test patch các hằng này (`git grep -nE 'LIMIT_MAX|_ROW_LIMIT|TREND_POINT_CAP|TTL_SECONDS' tests`) → `settings_override`.
- `scripts/healthcheck.py:35-40`: URL lấy từ `get_settings().services.*`.

- [ ] **Step 4: Kiểm không còn đọc env rải rác**

Run: `git grep -nE 'os\.(environ|getenv)' -- '*.py' ':!tests' ':!core/settings_loader.py' ':!core/logging_setup.py' ':!docker/inference/server.py'`
Expected: chỉ còn `os.environ.copy()` ở `ingestion/mtef_to_latex.py:66`. Chỗ nào khác thì chuyển nốt sang settings.

Run: `.venv-dev/bin/python -m pytest tests/unit/auth -q && make check`
Expected: PASS, xanh.

- [ ] **Step 5: Commit**

```bash
git add -A auth db ingestion query scripts tests
git commit -m "refactor: database, auth, ingestion and query limits read config/settings.yaml"
```

---

### Task 10: `core/startup.py` + tách `api/`; xóa `api_server.py`

**Files:**
- Create: `core/startup.py`
- Create: `api/__init__.py`, `api/main.py`, `api/schemas.py`, `api/errors.py`, `api/audit.py`, `api/services/__init__.py`, `api/services/chat_stream.py`, `api/routes/__init__.py`, `api/routes/system.py`, `api/routes/auth.py`, `api/routes/chat.py`, `api/routes/documents.py`, `api/routes/extractions.py`, `api/routes/records.py`, `api/routes/data.py`
- Delete: `api_server.py`
- Modify: `docker-compose.yml` (`api.command`), `run.sh`, `run_all.bat`, `run_api.bat`
- Modify test: các file import `api_server` (`git grep -l api_server tests`), chuyển vào `tests/unit/api/`
- Test: `tests/unit/core/test_startup.py`, `tests/unit/api/test_routes_snapshot.py`, `tests/unit/api/routes_snapshot.json`

**Interfaces:**
- Consumes: mọi package trước; `core.logging_setup.configure_logging`; `vectorstore.qdrant.collection_vector_size`
- Produces:
  - `core.startup.VectorSizeProbe = Callable[[str], int | None]`
  - `core.startup.StartupError(RuntimeError)`
  - `core.startup.validate_security(settings: Settings) -> None`
  - `core.startup.check_services(settings: Settings) -> dict[str, bool]`
  - `core.startup.check_vector_size(settings: Settings, probe: VectorSizeProbe) -> None`
  - `core.startup.startup(*, vector_size_probe: VectorSizeProbe | None = None, check_services_now: bool | None = None) -> Settings`
  - `api.main.create_app() -> FastAPI`, `api.main.app`, `api.main.main() -> None`
  - `api.services.chat_stream.chat_stream_events(req: ChatRequest, db: Session | None = None) -> Iterator[str]` (là `_chat_stream_gen`)
  - Bảng route giống hệt `~/.cache/qtkd-refactor/routes.json`

- [ ] **Step 1: Test startup (RED)**

`tests/unit/core/test_startup.py`:

```python
"""startup(): bật logging, chặn cấu hình nguy hiểm ở production, kiểm service không bắt buộc."""

import pytest

from core import startup
from core.settings_loader import load_settings, with_overrides


def _prod(**overrides):
    base = load_settings(
        env={"APP_ENV": "production", "JWT_SECRET_KEY": "k" * 40, "POSTGRES_PASSWORD": "mat-khau-that"}
    )
    return with_overrides(base, overrides)


def test_production_requires_jwt_secret():
    with pytest.raises(startup.StartupError, match="JWT_SECRET_KEY"):
        startup.validate_security(_prod(**{"auth.jwt_secret_key": None}))


def test_production_rejects_default_db_password():
    with pytest.raises(startup.StartupError, match="POSTGRES_PASSWORD"):
        startup.validate_security(_prod(**{"database.password": "qtkd_password"}))


def test_production_with_real_secrets_passes():
    startup.validate_security(_prod())


def test_development_allows_defaults():
    startup.validate_security(load_settings(env={}))


def test_check_services_reports_down_without_raising(monkeypatch):
    def down(*args, **kwargs):
        raise OSError("down")

    monkeypatch.setattr(startup.requests, "get", down)
    status = startup.check_services(load_settings(env={}))
    assert set(status) == {"embedding", "reranker", "qdrant", "ollama"}
    assert not any(status.values())


def test_vector_size_mismatch_is_fatal():
    with pytest.raises(startup.StartupError, match="768"):
        startup.check_vector_size(load_settings(env={}), probe=lambda name: 768)


def test_missing_collection_is_not_fatal():
    startup.check_vector_size(load_settings(env={}), probe=lambda name: None)
```

Run: `.venv-dev/bin/python -m pytest tests/unit/core/test_startup.py -q`
Expected: FAIL `cannot import name 'startup'`.

- [ ] **Step 2: Viết `core/startup.py`**

```python
"""Khởi động chung cho API và CLI: logging, kiểm cấu hình, kiểm service.

Service chưa lên chỉ cảnh báo (compose có thể bật API trước Qdrant/Ollama). Lệch chiều
vector giữa settings và collection thì dừng: truy hồi sẽ hỏng âm thầm. core không biết
Qdrant: nơi gọi truyền vào hàm đo số chiều (vector_size_probe).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from urllib.parse import urlsplit

import requests

from core.logging_setup import configure_logging
from core.schema import Settings
from core.settings_loader import get_settings

logger = logging.getLogger(__name__)

VectorSizeProbe = Callable[[str], int | None]
_DEV_DB_PASSWORD = "qtkd_password"
_PROBE_TIMEOUT_S = 2.0


class StartupError(RuntimeError):
    """Cấu hình không an toàn hoặc không khớp hạ tầng; không được chạy tiếp."""


def validate_security(settings: Settings) -> None:
    if settings.app.env != "production":
        return
    if settings.auth.enabled and settings.auth.jwt_secret_key is None:
        raise StartupError("production cần JWT_SECRET_KEY")
    uses_default_password = settings.database.password.get_secret_value() == _DEV_DB_PASSWORD
    if settings.database.url is None and uses_default_password:
        raise StartupError("production không được dùng POSTGRES_PASSWORD mặc định")


def _root(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"


def check_services(settings: Settings) -> dict[str, bool]:
    """Thử gọi từng service; trả trạng thái, cảnh báo service không phản hồi."""
    s = settings.services
    probes = {
        "embedding": _root(s.embedding_url) + "/health",
        "reranker": _root(s.rerank_url) + "/health",
        "qdrant": _root(s.qdrant_url),
        "ollama": _root(s.ollama_url),
    }
    status = {}
    for name, url in probes.items():
        try:
            status[name] = requests.get(url, timeout=_PROBE_TIMEOUT_S).ok
        except (OSError, requests.RequestException):
            status[name] = False
        if not status[name]:
            logger.warning("Service %s chưa phản hồi ở %s", name, url)
    return status


def check_vector_size(settings: Settings, probe: VectorSizeProbe) -> None:
    size = probe(settings.vectorstore.collection)
    expected = settings.models.embedding.vector_size
    if size is not None and size != expected:
        raise StartupError(
            f"Collection {settings.vectorstore.collection} có {size} chiều, settings khai {expected}"
        )


def startup(
    *, vector_size_probe: VectorSizeProbe | None = None, check_services_now: bool | None = None
) -> Settings:
    """Gọi một lần ở đầu mọi entrypoint (API lifespan, CLI)."""
    configure_logging()
    settings = get_settings()
    validate_security(settings)
    should_check = settings.app.startup_checks if check_services_now is None else check_services_now
    if should_check:
        status = check_services(settings)
        if vector_size_probe is not None and status.get("qdrant"):
            check_vector_size(settings, vector_size_probe)
    logger.info("Khởi động: env=%s, model chat=%s", settings.app.env, settings.llm_model("chat"))
    return settings
```

Run: `.venv-dev/bin/python -m pytest tests/unit/core/test_startup.py -q`
Expected: PASS.

- [ ] **Step 3: Test snapshot route (RED)**

`tests/unit/api/test_routes_snapshot.py`:

```python
"""Tách api_server.py thành router không được đổi đường dẫn, method hay thứ tự khớp route."""

import json
from pathlib import Path

from api.main import app

_SNAPSHOT = Path(__file__).with_name("routes_snapshot.json")


def test_routes_match_snapshot():
    actual = [[r.path, sorted(r.methods or [])] for r in app.routes]
    assert actual == json.loads(_SNAPSHOT.read_text(encoding="utf-8"))
```

```bash
mkdir -p tests/unit/api
cp ~/.cache/qtkd-refactor/routes.json tests/unit/api/routes_snapshot.json
```
Run: `.venv-dev/bin/python -m pytest tests/unit/api/test_routes_snapshot.py -q`
Expected: FAIL `No module named 'api'`.

- [ ] **Step 4: Tách `api_server.py`**

Phân bổ (số dòng theo `api_server.py` lúc lập plan; dời NGUYÊN thân hàm):

| Đích | Nội dung |
|---|---|
| `api/schemas.py` | `ChatMessage`, `ChatRequest`, `RenameRequest`, `LoginRequest`, `ApproveRequest`, `RejectRequest`, `EditApproveRequest`, `BulkApproveRequest`, `IngestRecordRequest` (130-190) |
| `api/audit.py` | `_audit` → `record_audit`, `_document_snapshot` → `document_snapshot` (196-227) |
| `api/errors.py` | `_review_http` → `review_http_error`, `_data_http` → `data_http_error` (614-620, 811-817) |
| `api/services/chat_stream.py` | `_sse`, `_history_to_prior`, `_build_sources_payload`, `_detect_device_ambiguity`, `_chat_stream_gen` → `chat_stream_events` (192-420) |
| `api/routes/system.py` | `EXAMPLES` (117-124), `/api/health`, `/api/examples` (422-430); health trả `get_settings().models.llm_chat` |
| `api/routes/auth.py` | `/api/auth/*` (432-467) |
| `api/routes/chat.py` | `/api/chat/stream` (469-483) |
| `api/routes/documents.py` | `/api/documents*` (485-612) |
| `api/routes/extractions.py` | `/api/extractions*` (622-747) |
| `api/routes/records.py` | `/api/records*` (749-809) |
| `api/routes/data.py` | `/api/data/*` (819-1067) |

Mỗi file route:

```python
from fastapi import APIRouter

router = APIRouter()


@router.get("/api/health")
def health(): ...
```
Giữ đường dẫn đầy đủ trong decorator (không dùng `prefix`) để so với bản cũ dễ đọc, và GIỮ THỨ TỰ hàm trong từng file như bản cũ (vd. `/api/data/records/export.xlsx` đứng trước `/api/data/records/{record_id}`).

`chat_stream_events` dài khoảng 140 dòng: tách thành các hàm dưới 50 dòng theo đúng các pha đang có trong thân (định tuyến intent → nhánh data → nhánh text: retrieve, dựng context, stream LLM → sự kiện done), không đổi thứ tự hay nội dung event SSE.
File này import module để test patch được: `from retrieval import retriever`, `from llm import generator`; gọi `retriever.retrieve(...)`, `generator.stream_ollama(...)`.

`api/main.py`:

```python
"""Ứng dụng FastAPI cho frontend React: ghép router, CORS, vòng đời khởi động.

Chạy: python -m api.main  (hoặc uvicorn api.main:app)
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import auth, chat, data, documents, extractions, records, system
from core.settings_loader import get_settings
from core.startup import startup
from vectorstore import qdrant

_ROUTERS = (system, auth, chat, documents, extractions, records, data)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    startup(vector_size_probe=qdrant.collection_vector_size)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="QTKĐ RAG API", version="1.0.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.api.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    for module in _ROUTERS:
        app.include_router(module.router)
    return app


app = create_app()


def main() -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run("api.main:app", host=settings.api.host, port=settings.api.port)


if __name__ == "__main__":
    main()
```
Thứ tự `_ROUTERS` phải tái tạo đúng thứ tự route cũ; snapshot lệch thứ tự thì sắp lại `_ROUTERS`, không sửa snapshot.
Xóa `sys.path.insert(0, ...)` của bản cũ (pythonpath / WORKDIR đã lo).

- [ ] **Step 5: Cập nhật test + entrypoint**

```bash
for f in $(git grep -l 'api_server' tests); do git mv "$f" tests/unit/api/$(basename "$f"); done
git rm api_server.py
```
Trong test: `from api_server import app` / `import api_server` → `from api.main import app`; `monkeypatch.setattr(api_server, "retrieve", f)` → `monkeypatch.setattr("retrieval.retriever.retrieve", f)`; `monkeypatch.setattr(api_server, "stream_ollama", f)` → `monkeypatch.setattr("llm.generator.stream_ollama", f)`; helper private (`_build_sources_payload`, ...) → `api.services.chat_stream` với tên mới.
Entrypoint:
- `docker-compose.yml` `api.command`: `["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080"]`
- `run.sh`: `"$PY" "$ROOT/api_server.py"` → `"$PY" -m api.main`; chú thích "api_server.py" → "api.main"
- `run_all.bat`, `run_api.bat`: `python api_server.py` → `python -m api.main`

Run: `git grep -n 'api_server' -- ':!docs'`
Expected: không còn.

- [ ] **Step 6: Kiểm**

Run: `make check`
Expected: xanh, `test_routes_snapshot` PASS.

Run:
```bash
.venv-dev/bin/python -c "import json; from api.main import app; print(json.dumps(app.openapi(), ensure_ascii=False, sort_keys=True))" > ~/.cache/qtkd-refactor/openapi_after.json
diff <(python3 -m json.tool ~/.cache/qtkd-refactor/openapi.json) <(python3 -m json.tool ~/.cache/qtkd-refactor/openapi_after.json)
```
Expected: không khác, hoặc chỉ khác `operationId` sinh tự động theo tên hàm; mọi khác biệt về path, tham số, body, schema phải sửa code.

- [ ] **Step 7: Commit**

```bash
git add -A api core/startup.py api_server.py tests docker-compose.yml run.sh run_all.bat run_api.bat
git commit -m "refactor: split api_server.py into the api package with a shared startup routine"
```

---

### Task 11: `evaluation/` + `scoring/`

**Files:**
- Move: `eval/` → `evaluation/` (gồm `*.jsonl`, `__init__.py`)
- Move: `evaluation/scoring.py` → `scoring/answer_scoring.py`
- Move: `evaluation/_pipeline.py` → `evaluation/pipeline.py`
- Create: `scoring/__init__.py`, `scoring/retrieval_metrics.py`
- Modify: `evaluation/run_eval.py`, `Makefile`, `.pre-commit-config.yaml`, `pyproject.toml` (chú thích), `llm/guards.py` (chú thích đã trỏ sẵn)
- Move test: `tests/unit/qa/test_answer_scoring.py` → `tests/unit/scoring/`; `test_eval_metrics.py` → `tests/unit/scoring/test_retrieval_metrics.py`; `test_fidelity_report.py` → `tests/unit/evaluation/`

**Interfaces:**
- Produces:
  - `scoring.answer_scoring.*` (tên của `eval/scoring.py` giữ nguyên)
  - `scoring.retrieval_metrics.matches(result_payload: dict, expected: dict) -> bool` (là `_matches`), `hit_rank(results: list[dict], expected_list: list[dict]) -> int | None` (là `_hit_rank`), `compute_metrics(ranks: list[int | None], ks: list[int]) -> dict`
  - `evaluation.pipeline.production_retrieve(query: str, top_n: int | None = None) -> list[dict]`
  - Lệnh: `python -m evaluation.{run_eval,answer_eval,intent_eval,record_query_eval,extract_eval,extract_section6_eval,arch_eval}`

- [ ] **Step 1: Di chuyển**

```bash
git mv eval evaluation
mkdir -p scoring tests/unit/scoring tests/unit/evaluation
touch scoring/__init__.py
git mv evaluation/scoring.py scoring/answer_scoring.py
git mv evaluation/_pipeline.py evaluation/pipeline.py
git mv tests/unit/qa/test_answer_scoring.py tests/unit/scoring/test_answer_scoring.py
git mv tests/unit/qa/test_eval_metrics.py tests/unit/scoring/test_retrieval_metrics.py
git mv tests/unit/qa/test_fidelity_report.py tests/unit/evaluation/test_fidelity_report.py
git grep -lE '\beval\.(scoring|_pipeline)\b' | xargs sed -i -E 's/\beval\.scoring\b/scoring.answer_scoring/g; s/\beval\._pipeline\b/evaluation.pipeline/g'
git grep -lE '(-m |from |import )eval\.|(^|[ "(])eval/' -- '*.py' Makefile '*.yaml' '*.yml' '*.toml' '*.sh' \
  | xargs sed -i -E 's/(-m |from |import )eval\./\1evaluation./g; s#(^|[ "(])eval/#\1evaluation/#g'
```
Kiểm tay kết quả sed: `Makefile` (chỉ đổi `-m eval.` → `-m evaluation.`, đường dẫn venv kotaemon giữ nguyên), `evaluation/arch_eval.py:17` (chú thích lệnh), `.github` không có trong repo.

- [ ] **Step 2: Tách số đo truy hồi**

Chuyển NGUYÊN `_matches` (→ `matches`), `_hit_rank` (→ `hit_rank`), `compute_metrics` từ `evaluation/run_eval.py:39-60,112-128` sang `scoring/retrieval_metrics.py`; `run_eval.py` import lại từ đó. `test_retrieval_metrics.py` đổi import tương ứng.

Run: `git grep -nE '\beval\.[a-z_]+|from eval\b|import eval\b' -- ':!docs'`
Expected: không còn.

Run: `make check`
Expected: xanh (target `extract-eval`, `extract-section6-eval`, `intent-eval` chạy dưới tên mới).

- [ ] **Step 3: Commit**

```bash
git add -A eval evaluation scoring tests Makefile .pre-commit-config.yaml pyproject.toml
git commit -m "refactor: rename eval/ to evaluation/ and extract the scoring package"
```

---

### Task 12: Gradio `app.py` → `ui/gradio_app.py`

**Files:**
- Move: `app.py` → `ui/gradio_app.py`; Create: `ui/__init__.py`
- Modify: `Dockerfile` (`CMD`), `.pre-commit-config.yaml` (nếu liệt kê `app.py`), `tests/unit/frontend/*`, `tests/integration/test_smoke_answer.py`

- [ ] **Step 1: Di chuyển và đọc settings**

```bash
mkdir -p ui && touch ui/__init__.py
git mv app.py ui/gradio_app.py
git grep -lE '^(import app$|from app import)' -- tests | xargs sed -i -E 's/^import app$/from ui import gradio_app as app/; s/^from app import/from ui.gradio_app import/'
```
Trong `ui/gradio_app.py`: khối `# ── Config` (`OLLAMA_URL`, `OLLAMA_MODEL`, `OLLAMA_TIMEOUT`, `HISTORY_TURNS`, `MAX_CONTEXT_CHARS`): với từng tên, `grep` trong file; còn dùng thì thay bằng settings, không dùng thì xóa. Xóa `sys.path.insert`.
Docstring: lệnh chạy `python -m ui.gradio_app`; danh sách service/model thay bằng "xem config/settings.yaml".
`if __name__ == "__main__":` gọi `core.startup.startup()` trước `build_ui().launch(...)`.
`Dockerfile`: `CMD ["python", "-m", "ui.gradio_app"]`.

- [ ] **Step 2: Kiểm**

Run: `make check`
Expected: xanh (`tests/unit/frontend/test_doc_viewer.py`, `test_latex_delimiters.py` PASS).

Run: `.venv-dev/bin/python -m ui.gradio_app` (nền), mở `http://localhost:7861`
Expected: giao diện hiện; hỏi "Thời gian quay tự do tối thiểu của píttông áp kế là bao lâu?" ra câu trả lời có trích dẫn `[n]` và panel nguồn tô sáng. Dừng tiến trình sau khi kiểm.

- [ ] **Step 3: Commit**

```bash
git add -A ui app.py Dockerfile tests .pre-commit-config.yaml
git commit -m "refactor: move the Gradio UI into ui/gradio_app.py"
```

---

### Task 13: `qdrant_storage/` bind mount + guard compose khớp settings + dọn cảnh báo

**Files:**
- Create: `qdrant_storage/README.md`
- Modify: `docker-compose.yml` (volume Qdrant, env `api`), `.gitignore`
- Modify: `docker/inference/server.py` (`/health` trả tên model), `core/startup.py` (so tên model)
- Modify: `alembic.ini` (`path_separator = os`)
- Modify: `Makefile` (`pull-model` đọc model từ settings), `run.sh` (mặc định model/URL lấy từ settings)
- Test: `tests/unit/qa/test_compose_matches_settings.py`, bổ sung `tests/unit/core/test_startup.py`

- [ ] **Step 1: Test compose khớp settings (RED)**

`tests/unit/qa/test_compose_matches_settings.py`:

```python
"""Compose không đọc được settings.yaml: tên model/độ dài/num_ctx lặp ở compose, test giữ khớp."""

import yaml

from core.settings_loader import REPO_ROOT, load_settings

_COMPOSE = yaml.safe_load((REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8"))["services"]


def test_embedding_service_model_matches_settings():
    svc = _COMPOSE["embedding"]
    name = load_settings(env={}).models.embedding.name
    assert svc["build"]["args"]["EMBEDDING_MODEL"] == name
    assert svc["environment"]["EMBEDDING_MODEL"] == name


def test_reranker_service_model_matches_settings():
    svc = _COMPOSE["reranker"]
    model = load_settings(env={}).models.reranker
    assert svc["build"]["args"]["RERANKER_MODEL"] == model.name
    assert svc["environment"]["RERANKER_MODEL"] == model.name
    assert int(svc["environment"]["RERANKER_MAX_LENGTH"]) == model.max_length


def test_ollama_context_length_matches_chat_num_ctx():
    env = _COMPOSE["ollama"]["environment"]
    assert int(env["OLLAMA_CONTEXT_LENGTH"]) == load_settings(env={}).llm.chat.num_ctx


def test_qdrant_data_lives_in_repo_qdrant_storage():
    assert "./qdrant_storage:/qdrant/storage" in _COMPOSE["qdrant"]["volumes"]


def test_api_does_not_pin_a_model_default():
    # Mặc định model nằm ở settings.yaml; compose chỉ chuyển tiếp biến nếu người dùng đặt.
    assert _COMPOSE["api"]["environment"]["OLLAMA_MODEL"] == "${OLLAMA_MODEL:-}"
```

Run: `.venv-dev/bin/python -m pytest tests/unit/qa/test_compose_matches_settings.py -q`
Expected: FAIL ở hai test cuối (volume, OLLAMA_MODEL). Nếu ba test đầu FAIL, compose và settings đang lệch: sửa `settings.yaml` cho khớp model ĐANG được bake trong image, không đổi model đang chạy.

- [ ] **Step 2: Đổi compose + README + gitignore**

- `qdrant.volumes`: `qdrant_storage:/qdrant/storage` → `./qdrant_storage:/qdrant/storage`; xóa `qdrant_storage:` khỏi khối `volumes:` cuối file.
- `api.environment.OLLAMA_MODEL`: `${OLLAMA_MODEL:-qwen2.5:3b}` → `${OLLAMA_MODEL:-}`.
- Thêm `APP_ENV: ${APP_ENV:-development}` vào `api.environment`.

`qdrant_storage/README.md`:

```markdown
# qdrant_storage

Dữ liệu của Qdrant (collection `qtkd_rag`), bind-mount vào container `qtkd-qdrant` tại `/qdrant/storage`.
Thư mục do Qdrant ghi; không sửa tay, không commit nội dung.
Dựng lại từ đầu: dừng Qdrant, xóa nội dung thư mục (giữ README.md), bật lại rồi chạy `python -m vectorstore.index --force`.
```

`.gitignore` thêm:

```
# Dữ liệu Qdrant bind-mount (docker-compose.yml)
qdrant_storage/*
!qdrant_storage/README.md
```

- [ ] **Step 3: Chuyển dữ liệu từ named volume (không xóa volume cũ)**

```bash
docker inspect qtkd-qdrant --format '{{range .Mounts}}{{.Name}}{{end}}'
curl -s localhost:6333/collections/qtkd_rag | python3 -c "import json,sys; print(json.load(sys.stdin)['result']['points_count'])" | tee ~/.cache/qtkd-refactor/points_before.txt
docker compose stop qdrant
docker run --rm -v hraesvelg_qdrant_storage:/from:ro -v "$PWD/qdrant_storage":/to alpine sh -c 'cp -a /from/. /to/'
docker compose up -d qdrant
until curl -sf localhost:6333/collections/qtkd_rag >/dev/null; do sleep 1; done
curl -s localhost:6333/collections/qtkd_rag | python3 -c "import json,sys; print(json.load(sys.stdin)['result']['points_count'])"
```
Expected: lệnh đầu in `hraesvelg_qdrant_storage` (nếu tên khác, dùng tên đó trong lệnh `docker run`); số point sau bằng `points_before.txt` (1646 lúc lập plan).
Không chạy `docker volume rm`: báo người dùng volume cũ vẫn còn để họ tự xóa khi đã yên tâm.
Chạy lại snapshot truy hồi (như Task 7 Step 8) → `GIONG_HET`.

- [ ] **Step 4: `/health` của inference trả tên model + startup so tên model**

`docker/inference/server.py`:

```python
@app.get("/health")
def health():
    model = RERANKER_MODEL if MODE == "reranker" else EMBEDDING_MODEL
    return {"status": "ok", "mode": MODE, "model": model}
```
`core/startup.check_services`: với `embedding` / `reranker` trả lời `ok`, đọc `resp.json().get("model")`; khác `settings.models.embedding.name` / `settings.models.reranker.name` thì `logger.error("Service %s chạy model %s, settings khai %s", ...)`. Không raise: model chạy được nhưng sai so với cấu hình là lỗi vận hành cần thấy rõ, không chặn API.
Thêm vào `tests/unit/core/test_startup.py`:

```python
def test_model_mismatch_is_logged(monkeypatch, caplog):
    class _Resp:
        ok = True

        @staticmethod
        def json():
            return {"status": "ok", "model": "model-khac"}

    monkeypatch.setattr(startup.requests, "get", lambda *args, **kwargs: _Resp())
    startup.check_services(load_settings(env={}))
    assert "model-khac" in caplog.text
```
Rebuild để image có `/health` mới: `docker compose build embedding reranker && docker compose up -d embedding reranker` (layer tải model không bị build lại vì `COPY server.py` nằm sau).

- [ ] **Step 5: Một nguồn cho model Ollama ở Makefile/run.sh**

`Makefile`:

```make
pull-model:
	docker compose exec ollama ollama pull $$($(PY) -m core.settings_loader get models.llm_chat)
```
`run.sh`: chuyển dòng `OLLAMA_MODEL="${OLLAMA_MODEL:-qwen2.5:3b}"` xuống SAU bước chọn `$PY`, thành `OLLAMA_MODEL="${OLLAMA_MODEL:-$("$PY" -m core.settings_loader get models.llm_chat)}"`.
Xóa các dòng `export EMBED_URL=...`, `RERANK_URL`, `QDRANT_URL`, `OLLAMA_URL` mặc định (settings có cùng giá trị); `$QDRANT_URL` dùng trong `services_up` lấy bằng `QDRANT_URL="${QDRANT_URL:-$("$PY" -m core.settings_loader get services.qdrant_url)}"` đặt cạnh dòng model.
Kiểm: `bash -n run.sh` và `./run.sh --no-docker` khởi động được API.

- [ ] **Step 6: Dọn cảnh báo alembic**

`alembic.ini`, mục `[alembic]`, thêm `path_separator = os`.

Run: `make check 2>&1 | grep -c 'path_separator'`
Expected: `0` (baseline có DeprecationWarning này ở mọi test migration).

- [ ] **Step 7: Kiểm + commit**

Run: `make check`
Expected: xanh.

```bash
git add qdrant_storage/README.md .gitignore docker-compose.yml docker/inference/server.py core/startup.py tests Makefile run.sh alembic.ini
git commit -m "chore: keep Qdrant data in ./qdrant_storage and guard compose against settings drift"
```

---

### Task 14: Sắp lại `tests/` + guard kiến trúc

**Files:**
- Move: các test còn lại trong `tests/unit/backend/` vào thư mục theo package nguồn; `tests/unit/backend/conftest.py` → `tests/unit/conftest.py`
- Modify: `tests/conftest.py` (docstring), `Makefile` (`lint`, `fmt`)
- Test: `tests/unit/qa/test_architecture.py`

**Interfaces:**
- Produces: `tests/unit/<package>/` cho `api, auth, catalogs, core, db, embedding, evaluation, ingestion, knowledge, llm, query, records, reranking, retrieval, review, scoring, scripts, vectorstore`; `tests/unit/qa/` chỉ còn guard xuyên dự án

- [ ] **Step 1: Chia test theo package**

Liệt kê package nguồn chính của từng file còn trong `tests/unit/backend/`:

```bash
for f in tests/unit/backend/test_*.py; do
  pkg=$(grep -m1 -oE '^(from|import) (query|records|catalogs|knowledge|review|db|auth|ingestion|vectorstore|retrieval|scripts)\b' "$f" | awk '{print $2}')
  echo "${pkg:-?} $f"
done | sort
```
`git mv` mỗi file vào `tests/unit/<pkg>/`; file `test_migrations_*` vào `tests/unit/db/`.
File `?` (không import trực tiếp package nào): đọc file, chọn theo đối tượng được test.
`git mv tests/unit/backend/conftest.py tests/unit/conftest.py` (fixture `data_factory`, `data_db` được nhiều package dùng). Thư mục `tests/unit/backend/` phải rỗng và biến mất.

Run: `.venv-dev/bin/python -m pytest -m unit tests/unit -q --co | tail -1`
Expected: số test thu thập bằng số trước khi chia.

Nếu pytest báo `import file mismatch` (hai thư mục có file cùng tên, vd. `test_router.py` ở `retrieval/` và `query/`): thêm `__init__.py` rỗng vào MỌI thư mục `tests/unit/*` (một quy tắc nhất quán, không đổi tên file lẻ tẻ).

- [ ] **Step 2: Guard kiến trúc (RED)**

`tests/unit/qa/test_architecture.py`:

```python
"""Guard cấu trúc: cấu hình chỉ ở settings, tầng dưới không import tầng trên."""

import ast
import re
from pathlib import Path

from core.settings_loader import REPO_ROOT

_BACKEND = [
    "api", "auth", "catalogs", "core", "db", "embedding", "evaluation", "ingestion", "knowledge",
    "llm", "query", "records", "reranking", "retrieval", "review", "scoring", "scripts", "ui", "vectorstore",
]
_ENV_ALLOWED = {"core/settings_loader.py", "core/logging_setup.py"}
# Tầng → các package nó KHÔNG được import (pipeline một chiều, core là đáy).
_FORBIDDEN = {
    "core": {"api", "embedding", "vectorstore", "reranking", "retrieval", "llm", "ingestion", "query", "evaluation", "ui"},
    "embedding": {"api", "vectorstore", "reranking", "retrieval", "llm", "evaluation", "ui"},
    "vectorstore": {"api", "reranking", "retrieval", "llm", "evaluation", "ui"},
    "reranking": {"api", "retrieval", "llm", "evaluation", "ui"},
    "retrieval": {"api", "llm", "evaluation", "ui"},
    "llm": {"api", "retrieval", "vectorstore", "embedding", "evaluation", "ui"},
    "scoring": {"api", "evaluation", "ui"},
}
_HARDCODED = re.compile(r"localhost:(6333|8010|8011|11434)|qwen2\.5:\d|BAAI/bge-")


def _sources():
    for pkg in _BACKEND:
        yield from (REPO_ROOT / pkg).rglob("*.py")


def _rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def test_only_settings_loader_reads_environment():
    offenders = []
    for path in _sources():
        if _rel(path) in _ENV_ALLOWED:
            continue
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"os\.(getenv|environ)(?!\.copy\(\))", text):
            offenders.append(f"{_rel(path)}:{text[: match.start()].count(chr(10)) + 1}")
    assert offenders == []


def test_no_hardcoded_service_urls_or_model_names():
    offenders = [_rel(p) for p in _sources() if _HARDCODED.search(p.read_text(encoding="utf-8"))]
    assert offenders == []


def _imported_packages(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split(".")[0])
    return names


def test_layers_do_not_import_upward():
    violations = []
    for layer, forbidden in _FORBIDDEN.items():
        for path in (REPO_ROOT / layer).rglob("*.py"):
            bad = _imported_packages(path) & forbidden
            if bad:
                violations.append(f"{_rel(path)} -> {sorted(bad)}")
    assert violations == []


def test_root_has_no_backend_modules_left():
    leftovers = ["api_server.py", "generation.py", "latex.py", "ingestion_jobs.py", "app.py"]
    assert [name for name in leftovers if (REPO_ROOT / name).exists()] == []
```

Run: `.venv-dev/bin/python -m pytest tests/unit/qa/test_architecture.py -q`
Expected lần đầu: có thể FAIL kèm danh sách vi phạm thật, vd. docstring nhắc `localhost:8010` hay `qwen2.5:1.5b`, ví dụ trong prompt hoặc script.
Sửa NGUỒN: chú thích/docstring đổi thành "xem config/settings.yaml" thay vì lặp giá trị; script cần giá trị thì đọc settings. Không nới regex hay thêm ngoại lệ để lách.
Dữ liệu eval (`*.jsonl`) không bị quét vì guard chỉ quét `*.py`.

- [ ] **Step 3: Cập nhật `tests/conftest.py` + lint**

Docstring đầu `tests/conftest.py`: thay "retrieval/ index/ app / eval.run_eval / scripts" bằng danh sách package mới.
`_SINGLETONS`: kiểm từng khóa còn trỏ đúng module (`vectorstore.qdrant`, `vectorstore.hybrid_index`, `retrieval.router`).
`Makefile`:

```make
LINT_PATHS = tests scripts query evaluation core api embedding vectorstore reranking retrieval llm scoring ui

lint:
	$(PY) -m ruff check $(LINT_PATHS)
	$(PY) -m ruff format --check $(LINT_PATHS)

fmt:
	$(PY) -m ruff format $(LINT_PATHS)
	$(PY) -m ruff check --fix $(LINT_PATHS)
```
Nếu `ruff format --check` báo file mới chưa định dạng: `make fmt`, kiểm diff chỉ là định dạng, commit riêng `style: format the new packages`.

- [ ] **Step 4: Kiểm + commit**

Run: `make check`
Expected: xanh.

```bash
git add -A tests Makefile
git commit -m "test: mirror the package layout in tests/ and guard layering and configuration"
```
(Thêm vào `git add` đúng các file nguồn đã sửa ở Step 2 để guard xanh.)

---

### Task 15: Tài liệu + kiểm thử E2E

**Files:**
- Modify: `CLAUDE.md`, `README.md`, `frontend/README.md`, `tests/README.md`, `.env.example`, `docs/PLAN.md` (chỉ mục lệnh/đường dẫn nếu có)

- [ ] **Step 1: Cập nhật tài liệu**

- `CLAUDE.md`: thay sơ đồ "Architecture", các mục "Stage 2" / "Stage 3", "Local services", "Commands" theo package mới. Xóa câu "ports/models are hardcoded as module-level constants ... change them in all relevant files together" và câu "`_NOISE_PATH_MARKERS` is duplicated" (đều đã sai). Thêm mục "Cấu hình": `config/settings.yaml` là nguồn duy nhất, override bằng biến môi trường `${...}`, `python -m core.settings_loader get <khóa>`. Sửa câu "the code currently runs bge-large-en-v1.5": compose và settings đang dùng `BAAI/bge-m3`.
- `.env.example`: thêm dòng đầu "Mọi biến ở đây override config/settings.yaml; không đặt thì dùng mặc định trong file đó."; thay `JWT_SECRET_KEY=dev-secret-key-please-change-in-production` bằng `# JWT_SECRET_KEY=` + chú thích lệnh sinh khóa: `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
- Lệnh trong mọi README: `python -m index.embed_store` → `python -m vectorstore.index`; `python app.py` → `python -m ui.gradio_app`; `api_server.py` → `python -m api.main`; `python -m eval.X` → `python -m evaluation.X`.
- Markdown dài: mỗi câu một dòng.

Run: `git grep -nE 'index\.embed_store|api_server|generation\.py|ingestion_jobs|python app\.py|-m eval\.' -- '*.md' ':!docs/superpowers/plans'`
Expected: không còn (các plan cũ trong `docs/superpowers/plans/` là lịch sử, giữ nguyên).

- [ ] **Step 2: E2E backend thật**

```bash
docker compose up -d --build postgres qdrant embedding reranker ollama api frontend
docker compose logs api | grep -E 'Khởi động|ERROR|Traceback'
curl -s localhost:8080/api/health
```
Expected: log `Khởi động: env=development, model chat=qwen2.5:3b`, không có Traceback; health trả `{"status":"ok","model":"qwen2.5:3b"}`.

- [ ] **Step 3: E2E giao diện như người dùng (React :3000)**

Mở `http://localhost:3000` bằng trình duyệt (chrome-devtools MCP hoặc thủ công), đăng nhập, rồi:
1. Hỏi "Thời gian quay tự do tối thiểu của píttông áp kế là bao lâu?": câu trả lời tiếng Việt, chip `[n]` bấm được, panel nguồn tô sáng đoạn con trong section cha, công thức KaTeX hiển thị đúng.
2. Hỏi một câu số liệu trong `Bo_20_cau.xlsx` (vd. "Biên bản nào có thời gian quay tự do trung bình thấp nhất?"): đi nhánh data, bảng `DataResultTable` hiện, câu trả lời là một câu tất định.
3. Tab Tài liệu: mở một `.docx` và một `.xlsx`, bản xem trước hiển thị.
4. Tải lên một `.docx` nhỏ từ `tests/data/` (không lấy từ `TC_DL/`), chờ xử lý xong, rồi xóa nó.
Chụp màn hình từng bước và soi lệch pixel (căn lề, chữ tràn, thanh cuộn ngang). Lỗi giao diện thấy được dù không do task này gây ra thì ghi lại, nhỏ thì sửa luôn trong commit riêng.

- [ ] **Step 4: So số đo cuối**

```bash
PYTHONPATH=. .venv-dev/bin/python ~/.cache/qtkd-refactor/snapshot_retrieval.py 50 > ~/.cache/qtkd-refactor/retrieval_k50_final.json
diff ~/.cache/qtkd-refactor/retrieval_k50.json ~/.cache/qtkd-refactor/retrieval_k50_final.json && echo GIONG_HET
.venv-dev/bin/python -m evaluation.run_eval --mode hybrid
make check
(cd frontend && npm run typecheck && npm run lint && npm run test && npm run build)
```
Expected: `GIONG_HET`; `run_eval` bằng `run_eval_after.txt` của Task 7; `make check` xanh; frontend xanh.
Cổng dự án là recall@5 ≥ 0,85. Nếu baseline đã dưới cổng, ghi rõ đó là tình trạng có từ trước, không do tái cấu trúc.
Nếu Ollama đang chạy: `make record-eval` đạt ≥ 0,90 như trước.

- [ ] **Step 5: Commit + báo cáo**

```bash
git add CLAUDE.md README.md frontend/README.md tests/README.md .env.example docs/PLAN.md
git commit -m "docs: describe the package layout and config/settings.yaml"
```
Báo người dùng: danh sách commit; số test trước/sau; kết quả diff truy hồi; số eval với top_k 20 và 50; named volume `hraesvelg_qdrant_storage` cũ còn đó chờ họ xóa; các lỗi có sẵn phát hiện dọc đường (image Docker thiếu package, eval đo khác phễu của API, model mặc định lệch nhau giữa code/compose/run.sh, khóa JWT ghi cứng).

---

## Self-review

- Phủ yêu cầu: `api` (T10); `config/settings.yaml` + `logging.yaml` (T2, T3); `core/logging_setup.py`, `schema.py`, `settings_loader.py`, `startup.py` (T2, T3, T10); `embedding/batch_embed, embedder, sparse_embedder` (T5); `evaluation` (T11); `ingestion` (T6, T9); `llm/generator, prompt` (T8); `qdrant_storage` (T13); `reranking` (T7); `retrieval/context_builder, hybrid_retriever, retriever` (T7, T8); `scoring` (T11); `tests` (mọi task + T14); `vectorstore/hybrid_index, index, qdrant, upsert` (T6); "settings.yaml chứa toàn bộ tham số cấu hình và model" (T2, khóa bằng guard ở T13 và T14).
- Rủi ro và lưới an toàn: chuyển code sai → diff snapshot truy hồi từng hit (T7, T13, T15); API đổi ngầm → snapshot route + diff OpenAPI (T10); cấu hình trôi → guard compose (T13) + guard env / giá trị ghi cứng / chiều import giữa tầng (T14); mất dữ liệu Qdrant → copy, không xóa volume cũ (T13); công thức → `make fidelity` trong `make check` ở mọi task.
- Tên nhất quán giữa các task: `get_settings`, `settings_override`, `with_overrides`, `collection_vector_size` (T6 định nghĩa, T10 dùng), `startup(vector_size_probe=..., check_services_now=...)`, `stream_ollama(messages, *, model=None)`, `retrieve(query, top_k=None, top_n=None)`, `build_rerank_doc`, `filter_noise`, `merge_per_file`, `sparse_document_text`.
