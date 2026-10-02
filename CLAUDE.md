# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Offline RAG chatbot for **looking up and citing** Vietnamese metrology calibration
procedures (QTKĐ — Quy trình Kiểm định) from the documents in `TC_DL/`. Users ask in
Vietnamese; the bot answers with exact passages + formulas + source citations (file,
section). It is **lookup-only** (no calculation) and runs **fully offline** — every model
is local, no cloud API calls. Target prod hardware is a single RTX 5060 8GB box; it must
scale from the current handful of files to thousands of procedures.

`docs/PLAN.md` is the full design doc (Vietnamese). `docs/spike_c_ui_setup.md` records the
framework bake-off. Both are background; the running system is the code below.

## The central problem: formulas are not text

In the source `.docx`, formulas are **MathType OLE objects** (`word/embeddings/oleObject*.bin`,
binary MTEF format) plus a rendered WMF image — there are **zero** native OMML (`m:oMath`)
formulas. A naive text extraction drops every formula. The entire `ingestion/` layer exists
to recover them losslessly. This is risk #1 of the project; treat formula fidelity as the
top correctness concern in any ingestion change.

## Architecture: a one-way pipeline

Each stage's output is the next stage's stable input - keep this boundary.
Formula accuracy is owned by `ingestion/`, not by any RAG framework.
Every runtime parameter and model name comes from `config/settings.yaml` (see "Cấu hình" below).

```
TC_DL/*.docx                          ← source corpus (read-only; never modify)
   │  ingestion/  (Stage 1: extract_docx → MTEF/LaTeX → Markdown → Chunk)
   ▼
build/spike_a/*.md  + assets/ + extraction_report.json   ← clean Markdown, $LaTeX$ inline
   │  embedding/ + vectorstore/  (Qdrant + in-memory BM25)
   ▼
Qdrant collection `qtkd_rag`          ← parent (section) + child (para/table/formula) chunks
   │  retrieval/ + reranking/ + llm/  (hybrid search → cross-encoder → prompt → generate)
   ▼
answer + citations  ──►  UI (one of):
   • React frontend :3000  ← api/ (FastAPI + SSE) :8080      ← primary (newer)
   • ui/gradio_app.py Gradio :7861                           ← original / alt
```

`core/` sits at the bottom: it loads settings, configures logging, and holds the shared schema and startup routine.
`core/` imports no other project package.
Above it the layers go one way: `embedding` → `vectorstore` → `reranking` → `retrieval` → `llm` → `api`.
A lower layer never imports a higher one;
`tests/unit/qa/test_architecture.py` guards this and the "settings-only" rule.

### Stage 1 — `ingestion/` (formula extraction)
- `extract_docx.py` — walks `word/document.xml` **in document order**, preserving heading
  hierarchy and tables (as Markdown). At each formula it inserts a placeholder token
  `⟦Fxxx⟧` and records the OLE `.bin` + image asset. Only depends on `lxml`.
- `mtef.py` — parses the MathType "Equation Native" (MTEF) stream from the OLE via `olefile`
  to confirm a formula is recoverable.
- `mtef_to_latex.py` — converts OLE `.bin` → LaTeX via **`mathtype_to_mathml` (a Ruby gem,
  invoked as a subprocess)** → MathML → LaTeX (pure-Python lxml tree walk with a Unicode→LaTeX
  table). Returns `None` on any failure. **Requires Ruby + the gem installed**; `_GEM_PATHS`
  is hardcoded for macOS system Ruby 2.6. `vendor/xsltml/mml2tex.xsl` is a vendored XSLT
  fallback for MathML→LaTeX.
- `omml.py` — converts native Word OMML to LaTeX (present for completeness; corpus has none).
- `spike_a.py` — the runner. For each `.docx`: extracts, dumps every formula's `.bin`+`.wmf`
  to `build/spike_a/assets/<file>/`, converts to LaTeX, replaces `⟦Fxxx⟧` placeholders with
  `$LaTeX$`, writes `<file>.md`, and emits `extraction_report.json` (counts + per-formula
  detail + conversion rate — the verification artifact). Legacy `.doc`/`.xls` are **reported
  but skipped** (they need LibreOffice conversion first — "Spike B", not yet implemented).

### Stage 2 - `ingestion/` (chunker) + `embedding/` + `vectorstore/`
- `ingestion/chunker.py` - **parent-document retrieval**. Each heading section becomes a PARENT
  chunk (full text, stored for context expansion, `is_parent=True`); paragraphs / tables / formula
  blocks within it become CHILD chunks (`is_parent=False`) carrying their `parent_id`. Children
  are what gets embedded and searched; parents are returned to give the LLM full context.
  `chunk_id = sha256(file + section + text)[:16]` (hex), converted to a uint64 for the Qdrant
  point ID. This hashing makes re-indexing idempotent.
- `embedding/embedder.py` + `embedding/batch_embed.py` - the single client of the embedding
  service (`services.embedding_url`): `embed_texts()` (batched with `embedding.batch_size`) and
  `embed_query()`.
- `vectorstore/index.py` + `vectorstore/upsert.py` - embed chunks and upsert them to Qdrant via
  `vectorstore/qdrant.py`. Skips files already indexed (by `file_stem`) unless `--force`.
- `vectorstore/hybrid_index.py` - the in-memory BM25 half of the hybrid index (see Stage 3).

### Stage 3 - `retrieval/` + `reranking/` + `llm/` + `api/` + `ui/`
- `vectorstore/hybrid_index.py` - in-memory BM25 (`rank_bm25`) built lazily by scrolling child
  chunks out of Qdrant. Its tokenizer **deliberately keeps technical codes/units intact** (e.g.
  `1.061:2021`, `MPa`, `bar`) - dense embeddings blur these, so BM25 is required for symbol/code
  precision. The corpus text for each chunk includes `file_stem` + `section_path` so BM25 can
  match QTKĐ numbers. `embedding/sparse_embedder.py` owns `tokenize()` + `sparse_document_text()`.
- `retrieval/retriever.py` - full hybrid pipeline: `embed_query` → `dense_search` (children only) +
  `bm25_search` → `rrf_fuse` (Reciprocal Rank Fusion, k=60) → noise filter → `rerank_hits`
  (cross-encoder) → `fetch_parent` (return the full section). `retrieval/hybrid_retriever.py` holds
  `rrf_fuse`/`filter_noise`/`merge_per_file`/`search_both`; `reranking/reranker.py` holds the
  cross-encoder call. Boilerplate template sections ("Mẫu biên bản", "(Quy định)", …) are filtered
  out before reranking; `NOISE_PATH_MARKERS` now lives once in `vectorstore/noise.py`, and both
  `retrieval/hybrid_retriever.py` and `vectorstore/hybrid_index.py` import it.
- `ui/gradio_app.py` - Gradio 4.x UI on **:7861** (original / alternative UI). Left = streaming chat
  with **KaTeX vendored offline** under `ui/static/katex/` (inline `$...$`), right = source-document
  viewer with the retrieved child passage `<mark>`-highlighted inside its parent section.
  `llm/prompt.py` forces context-only answers, verbatim LaTeX (no recompute), Vietnamese, and `[n]`
  citations; falls back to "không tìm thấy" when context lacks the answer.
  Run with `python -m ui.gradio_app`.
- `api/` - **FastAPI + SSE backend** for the React frontend, on **:8080** (run with `python -m api.main`,
  or `uvicorn api.main:app`). `api/main.py` builds the app, `api/routes/` holds the route modules,
  `api/services/chat_stream.py` is the SSE stream. Endpoints `GET /api/health`, `GET /api/examples`,
  `POST /api/chat/stream` (SSE). Reuses the SAME pipeline as `ui/gradio_app.py`
  (`retrieval.retriever` + `llm/`: `guards.is_calculation_request` → `retrieve` →
  `prompt.build_messages` → `generator.stream_ollama`).
- `query/intents.py` + `query/router.py` — **chat lai văn bản + số liệu** (Sprint 9, spec §8).
  `intents.py` định nghĩa 7 intent tra cứu số liệu (`device_history`, `latest_record`,
  `records_by_period`, `procedure_params`, `devices_by_range`, `standards_for`, `error_trend`)
  với schema tham số pydantic; LLM chỉ chọn intent + điền tham số, **không có text-to-SQL**.
  `router.py` phân ba nhánh `text`/`data`/`mixed` và **mặc định rơi về `text`** khi không chắc.
  `device_ambiguity.py`: câu hỏi chỉ nêu tên chung của nhiều loại thiết bị ("áp kế pít tông" →
  kiểu H3000 / tiêu chuẩn) không được trả lời bằng một loại; nhánh text liệt kê từng loại và trả
  lời riêng từng QTKĐ, `_find_procedure` không chọn bừa khi tên khớp nhiều QTKĐ.
  Nhánh số liệu chỉ đọc view đã duyệt (P3) qua `query/records.py` + `query/approved.py`, trả mỗi
  con số kèm tham chiếu xuất xứ (P1) và trích dẫn sổ cái tách bạch với nguồn QTKĐ. Tích hợp ở
  `/api/chat/stream` (SSE event `data`, `done.branch`/`done.data`); bảng do frontend render
  (`components/chat/DataResultTable.tsx`), ô số bấm được để mở nguồn.
  Câu trả lời của intent sổ cái (`record_lookup`, `records_summary`, `device_history`) là MỘT
  câu tất định (`DataPayload.answer` → `done.answer`), không qua LLM, ghép từ NGUYÊN VĂN đúng
  các ô của bảng đi kèm (`query/answer_phrases.py` + `query/record_answer*.py`); chỉ thêm số
  đếm và chữ đối chiếu mức cho phép ("nên không đạt" chỉ khi kết luận biên bản cũng vậy).
  Bảng chỉ có điều được hỏi: cực trị → dòng thắng; đếm toàn sổ cái → tổng hợp + biên bản không
  đạt; đếm/liệt kê có lọc → biên bản khớp; đếm thiết bị → bảng thiết bị.
  `procedure_params` (dữ kiện đã duyệt của một QTKĐ) chỉ trả lời khi câu hỏi hỏi đúng loại dữ
  kiện (phạm vi đo, cấp chính xác, chu kỳ, nhiệt độ / độ ẩm…) VÀ mọi phần được hỏi đều có dữ
  kiện (`query/procedure_scope.py`); câu hỏi quy định khác (sai số, độ chênh áp, tốc độ hạ,
  công thức…) hoặc thiếu dữ kiện đi nhánh văn bản, vì model phân loại đưa mọi câu có số QTKĐ
  vào intent này. Ngữ cảnh LLM của một mục dài lấy cửa sổ quanh đoạn con được truy hồi
  (`retrieval.context_builder.window`), không cắt mất fact ở cuối mục.
- `query/record_*.py` — **tra cứu biên bản có cấu trúc** (Pha R). Hai intent `record_lookup`
  (một biên bản theo số hiệu / số biên bản / ngày: trường được hỏi, bảng kết quả, căn cứ kết
  luận không đạt) và `records_summary` (đếm / liệt kê / cực trị trên sổ cái, lọc theo người,
  đơn vị phạm vi đo, ngày). Trường đầu mục của biên bản nằm ở bảng `record_field` (view
  `v_record_field`), nguyên văn từng ô ở `measurement_point.cells`; `v_record_detail` lấy phạm
  vi đo của CHÍNH thiết bị. `record_fields.py` dựng danh mục trường từ nhãn Phụ lục A đã duyệt
  + bí danh ký hiệu (A0, uCmax, U(p)); `record_signals.py` sửa lựa chọn của LLM bằng định danh
  khớp đúng sổ cái (chạy sau `disambiguate_catalogs`), kể cả kiểu câu hỏi (`measure` đếm/liệt
  kê, `subject` biên bản/thiết bị, `across_records`). Cực trị chỉ so biên bản cùng một QTKĐ.
  `record_query.py` (tra biên bản) và `record_summary.py` (tổng hợp) đọc view qua
  `record_cells.py`. Gate: `make record-eval` chấm bộ `bo20` trên CÂU TRẢ LỜI (đủ "số liệu
  bắt buộc" của `Bo_20_cau.xlsx`, số khớp trọn), các bộ khác trên câu trả lời + bảng.
  Biên bản đã duyệt trước migration 012 được bổ sung bằng `python -m records.backfill`.
  Prompt phân loại ở `query/intent_prompt.py` (~4 000 token → bộ phân loại dùng `num_ctx` 8192).
- `frontend/` — **React 18 + TypeScript + Vite + Tailwind** web UI (Docker nginx on **:3000**,
  proxies `/api` → the `api/` package; dev server is Vite on **:5173**). A 1:1 rebuild of
  `design/kiemdinh.html`, now **wired to the real backend**: `src/services/liveApi.ts`
  (`streamChat` SSE, `fetchExamples`, `pingHealth`) drives the chat. Answers render through
  `src/components/common/Markdown.tsx` — `react-markdown` + **`remark-gfm`** (pipe tables) +
  `remark-math`/`rehype-katex` (verbatim `$LaTeX$`, lenient mode) + `rehype-raw` for clickable
  `[n]` citation chips; a live source panel highlights `child_text` inside `parent_text`.
  Conversation history persists in `localStorage` (`src/store/persistence.ts`) and prior turns
  are replayed as short-term LLM memory (`toHistory` in `src/store/useAppStore.ts`).
  `src/services/mockEngine.ts` now retains only demo data + timing for the Documents/Guide tabs.
  Document viewer (`components/docs/DocContentPane.tsx`) shows the ORIGINAL file in its own
  scroll area: `.docx`/`.doc` via `docx-preview`, `.xlsx`/`.xls` via an Excel-like renderer in
  `components/docs/xlsx/` (ExcelJS, lazy-loaded; merges, borders, fonts, VN number formats,
  never silently truncates a number). Legacy `.doc`/`.xls` come from
  `GET /api/documents/{id}/preview`, which serves the LibreOffice-converted copy
  (`ingestion/jobs.py` `get_preview_path`). The "Đoạn nguyên văn" (provenance drawer + review
  queue) renders through `components/common/SourceExcerpt.tsx`: Markdown section with the
  quote highlighted by source offset (no `rehype-raw`), or, for Excel records, the original
  cell grid around the row located by `query/sheet_locate.py` (`source_location`).
  `frontend-legacy/` is the earlier plain-JS React prototype, kept for reference. Quick local
  run of the api + Vite together: `./run.sh`. See `frontend/README.md`.
- `core/latex.py` - shared `fix_latex` normalizer (strip backticks around `$…$`; `\[…\]`/`\(…\)` →
  `$$…$$`/`$…$`; collapse `\\` → `\`) imported by **both** `ui/gradio_app.py` and the `api/`
  package (was duplicated); mirrored in the frontend as `liveApi.fixLatex`.
  Regression: `tests/unit/core/test_latex_fix.py`.
- `evaluation/run_eval.py` - Spike E regression harness. Computes recall@k + MRR for hybrid vs
  dense-only against `evaluation/eval_set.jsonl` (question → expected file_stem + section_path).
  Run this after any retrieval change. Pass goal is recall@5 ≥ 0.85.
- `evaluation/intent_eval.py` - Sprint 9 gate for the hybrid chat router: intent accuracy ≥ 0.90,
  parameter-validation fallback to `text`, zero untraceable numbers, and text questions never
  routed to the data branch. Runs a scripted classifier by default (no Ollama); `--live` measures
  the real model. Part of `make check` via `intent-eval`.
- `evaluation/record_query_eval.py` - `make record-eval`: bộ 20 câu `Bo_20_cau` + câu diễn đạt khác
  (`evaluation/record_query_set.jsonl`) chạy trên sổ cái thật (cần Postgres + Ollama, không nằm trong
  `make check`); đạt khi intent đúng và bảng chứa đủ số liệu bắt buộc. Cổng ≥ 0.90.

## Virtualenvs

- **Project `.venv`** (`requirements.txt`: `olefile`, `lxml`, `scikit-image`) runs Stage 1
  ingestion only (`python -m ingestion.spike_a`).
- **`.venv-dev`** (`requirements-app.txt` + `requirements-dev.txt`) is the harness venv for
  `make check` and every Stage 2-3 command (`vectorstore`, `api`, `ui`, `evaluation`).
  It is the Makefile's default `PY`; build it with
  `python3.11 -m venv .venv-dev && .venv-dev/bin/python -m pip install -r requirements-app.txt -r requirements-dev.txt`.
- `kotaemon/.venv` (sibling repo `../kotaemon`) is only for **Mode B**; this repo's Docker stack
  and harness do not need it. The Stage 2-3 deps live in `requirements-app.txt`, not `requirements.txt`.

## Local services (all Docker, must be running for Stages 2-3)

| Service    | Port  | Model / detail                                   |
|------------|-------|--------------------------------------------------|
| Embedding  | 8010  | OpenAI-compat `/v1/embeddings`, **1024-dim** (`BAAI/bge-m3`) |
| Reranker   | 8011  | `/v1/rerank` (`BAAI/bge-reranker-v2-m3`)         |
| Qdrant     | 6333  | collection `qtkd_rag` (cosine, 1024 dims), bind mount `./qdrant_storage/` |
| Ollama     | 11434 | **native `/api/chat`** (`llm/generator.py` maps a `/v1` `OLLAMA_URL` to it); model `models.llm_chat` (default `qwen2.5:3b`). KHÔNG quay lại `/v1/chat/completions`: endpoint đó BỎ QUA `options` → num_ctx/num_predict không có hiệu lực (đo 2026-06-11). |
| api        | 8080  | `python -m api.main` (FastAPI+SSE) - backend cho React frontend; same pipeline as `ui/gradio_app.py` |
| ui         | 7861  | `python -m ui.gradio_app` (Gradio, KaTeX vendored under `ui/static/katex/`) |
| frontend   | 3000 (Docker) / 5173 (Vite dev) | React UI (nginx, proxy `/api`→api:8080); **đã nối backend thật** (chat SSE + lịch sử/bộ nhớ) - xem `frontend/README.md` |

Service URLs, ports, and model names are **not** hardcoded in code: they come from
`config/settings.yaml` and are read at call time via `get_settings()` (see "Cấu hình" below).

## Cấu hình

`config/settings.yaml` is the single source of truth for every runtime parameter and model name.
Never hardcode a service URL, port, model name, or threshold in code - read it via
`core.settings_loader.get_settings()` at call time (not at import), so tests can override it.

Environment variables override the YAML with `${VAR:-default}` (or `${VAR}` for a required value).
`.env` is loaded once at startup; disable it in tests with `QTKD_LOAD_DOTENV=0`.
Inspect any effective value with the CLI:

```bash
python -m core.settings_loader get retrieval.top_k
```

`config/logging.yaml` configures logging.
The only code allowed to read `os.environ` is `core/settings_loader.py` and `core/logging_setup.py`.
`tests/unit/qa/test_architecture.py` guards both this rule and the layer direction.

## Commands

```bash
# Stage 1 — extract formulas + build clean Markdown (project .venv; needs Ruby + mathtype_to_mathml gem)
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
python -m ingestion.spike_a                      # reads TC_DL/, writes build/spike_a/
python -m ingestion.spike_a SRC_DIR OUT_DIR      # custom paths

# Stage 2 - index into Qdrant (.venv-dev; Docker services up)
python -m vectorstore.index                      # incremental; skips already-indexed files
python -m vectorstore.index --force              # re-index everything
python -m vectorstore.index --query "phạm vi van an toàn 1400 bar"   # smoke-test query

# Stage 3 — run the chatbot UI (→ http://localhost:7861)
python -m ui.gradio_app

# Stage 3 - run the API backend for the React frontend (→ http://localhost:8080)
python -m api.main

# Eval — retrieval regression (run after any retrieval change)
python -m evaluation.run_eval                    # hybrid vs dense, recall@k + MRR
python -m evaluation.run_eval --mode hybrid -v

# Eval — chat lai văn bản + số liệu (Sprint 9; tất định, không cần Ollama)
python -m evaluation.intent_eval                 # intent ≥ 0.90, 0 số không nguồn
python -m evaluation.intent_eval --live          # đo model phân loại thật
```

Verification gates: `extraction_report.json` (Stage 1 formula fidelity), `evaluation/run_eval.py`
(Stage 3 retrieval), and **`make check`** — backend unit tests + the 351/351 formula-fidelity
guard, no Docker needed. The `frontend/` has its own gate (ESLint + Prettier + Vitest were added
as the refactor safety net):

```bash
cd frontend && npm install
npm run typecheck && npm run lint && npm run test && npm run build
```

## Conventions

- All user-facing strings, prompts, comments-about-domain, and doc-section names are in
  Vietnamese; keep that.
- `build/` is generated output — safe to delete and regenerate; don't hand-edit.
- `⟦Fxxx⟧` is the formula placeholder contract between `extract_docx.py` and `spike_a.py`.
- Never recompute or rewrite a formula's LaTeX downstream — it is indexed verbatim and the
  whole point is that the user can trust it against the source image.
