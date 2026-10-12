# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Offline RAG chatbot for **looking up and citing** Vietnamese metrology calibration
procedures (QTKĐ — Quy trình Kiểm định) from the documents in `TC_DL/`. Users ask in
Vietnamese; the bot answers with exact passages + formulas + source citations (file,
section). The chat itself never calculates and runs **fully offline** — every model
is local, no cloud API calls.
Calculation lives only in the separate reviewed-formula flow (`formula_registry/`, see below): a human approves each formula before it can be used. Target prod hardware is a single RTX 5060 8GB box; it must
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
  Headings come from Word heading styles; a direct `w:outlineLvl` counts only when the text starts with a section number of that depth (QTKĐ 1.159 "6.3.2").
- `mtef.py` — parses the MathType "Equation Native" (MTEF) stream from the OLE via `olefile`
  to confirm a formula is recoverable.
- `mtef_to_latex.py` — converts OLE `.bin` → LaTeX via **`mathtype_to_mathml` (a Ruby gem,
  invoked as a subprocess)** → MathML → LaTeX (pure-Python lxml tree walk with a Unicode→LaTeX
  table). Returns `None` on any failure. **Requires Ruby + the gem installed**; `_GEM_PATHS`
  is hardcoded for macOS system Ruby 2.6. `vendor/xsltml/mml2tex.xsl` is a vendored XSLT
  fallback for MathML→LaTeX.
  `vendor/mathtype_to_mathml/patch.rb` patches the gem at runtime (square roots it drops, nested parentheses, dangling prescripts, read-only OLE); regression fixtures are in `tests/fixtures/mtef/` (`make test-ruby`).
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
  After the first build, ingestion updates BM25 per file (`hybrid_index.refresh_files`) instead of re-scrolling the whole collection.
- `retrieval/router.py` - pins a query to a file by QTKĐ number or device alias.
  The number → file map comes from the `procedure` table (the number is read from the document header, not the file name), with a deterministic Qdrant file-name scan only when Postgres is unreachable.
- `ingestion/jobs.py` - upload accepts only `.docx`/`.doc`/`.pdf` (QTKĐ); older `.xlsx`/`.xls` already in the store stay viewable.
  A document whose Markdown header carries a QTKĐ code is treated as `qtkd` even when its file name does not say so.
  Each QTKĐ number keeps exactly one version in the index: the newer issue year wins (same year: the one processed later), the older one becomes `superseded` (removed from Qdrant, source file + Markdown kept), and deleting the current version re-indexes the newest superseded one.
- `retrieval/retriever.py` - full hybrid pipeline: `embed_query` → `dense_search` (children only) +
  `bm25_search` → `rrf_fuse` (Reciprocal Rank Fusion, k=60) → noise filter → `rerank_hits`
  (cross-encoder) → `fetch_parent` (return the full section). `retrieval/hybrid_retriever.py` holds
  `rrf_fuse`/`filter_noise`/`merge_per_file`/`search_both`; `reranking/reranker.py` holds the
  cross-encoder call. Boilerplate template sections ("Mẫu biên bản", "(Quy định)", …) are filtered
  out before reranking; `NOISE_PATH_MARKERS` now lives once in `vectorstore/noise.py`, and both
  `retrieval/hybrid_retriever.py` and `vectorstore/hybrid_index.py` import it.
  RRF weights each branch by `retrieval.rrf_weight_dense` / `rrf_weight_bm25` (only their ratio matters; default 1:1).
  `python -m evaluation.fusion_sweep` grid-searches the ratio and `rrf_k` through the real `retrieve()`.
  The 2026-10-02 sweep kept 1:1, see `docs/experiments/2026-10-02-weighted-rrf.md`.
  A question routed to N ≥ 2 files gets `max(top_n, retrieval.top_n_per_file × N)` sources, so each file keeps its own budget.
- `ui/gradio_app.py` - Gradio UI on **:7861** (original / alternative UI), run with `python -m ui.gradio_app`.
  Left = streaming chat (Gradio's built-in KaTeX, inline `$...$` enabled via `LATEX_DELIMITERS`).
  Right = source-document viewer with the retrieved child passage `<mark>`-highlighted inside its parent section.
  Gradio does not expose KaTeX to custom HTML, so the viewer loads KaTeX auto-render from `ui/static/katex/` (vendored, offline) through `launch(head=...)`.
  `llm/prompt.py` forces context-only answers, verbatim LaTeX (no recompute), Vietnamese, and `[n]` citations; it falls back to "không tìm thấy" when context lacks the answer.
- `api/` - **FastAPI + SSE backend** for the React frontend, on **:8080** (run with `python -m api.main`,
  or `uvicorn api.main:app`). `api/main.py` builds the app, `api/routes/` holds the route modules,
  `api/services/chat_stream.py` is the SSE stream. Endpoints `GET /api/health`, `GET /api/examples`,
  `POST /api/chat/stream` (SSE). Reuses the SAME pipeline as `ui/gradio_app.py`
  (`retrieval.retriever` + `llm/`: `guards.is_calculation_request` → `retrieve` →
  `prompt.build_messages` → `generator.stream_ollama`).
  Each SSE source carries `quote` (`retrieval/quote.py`): its matched children plus the formula each one refers to (a "trong đó" definition line brings the formula above it, a lead-in ending in ":" the formula after it), shown in the panel's "Đoạn trả lời" box.
- `api/services/chat_stream.py` — **chat chỉ còn nhánh văn bản**: câu hỏi đi thẳng
  `retrieve` → `build_messages` → `stream_ollama`, không còn bộ phân loại intent hay
  nhánh `data`/`mixed`. SSE event: `status` | `sources` | `delta` | `done{answer,sources}` |
  `error`. Câu hỏi nêu tên chung của nhiều loại thiết bị ("áp kế pít tông" → kiểu H3000 /
  tiêu chuẩn) được nhận diện ở `query/device_ambiguity.py`: câu trả lời liệt kê từng loại và
  trả lời riêng từng QTKĐ thay vì chọn một loại làm câu chung.
  Ngữ cảnh LLM của một mục dài (`retrieval.context_builder.window`) dựng từ
  khối trọn quanh MỌI đoạn con khớp của mục trong pool rerank (`anchor_texts`, theo thứ hạng
  RRF): mỗi đoạn neo kéo công thức nó nói tới và danh sách "trong đó" của công thức (mô hình
  khối của `retrieval/quote.py`), lần lượt tới hết ngân sách, phần dư mở rộng quanh các đoạn
  neo; không dành chỗ cố định cho đầu mục. Panel nguồn chỉ trích `llm.context.quote_anchors`
  đoạn khớp nhất. Ngân sách chia theo thứ hạng nguồn trong `total_context_chars` (đã trừ câu
  trả lời, 2,5 ký tự/token đo thật): nguồn trên lấy trước, nguồn dưới giữ chỗ
  `min_block_chars`, trần `max_block_chars` không áp cho nguồn top. Ngữ cảnh vượt num_ctx thì
  Ollama cắt prompt.
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
  (`ingestion/jobs.py` `get_preview_path`). The source-excerpt viewer renders through
  `components/common/SourceExcerpt.tsx`: Markdown section with the quote highlighted by
  source offset (no `rehype-raw`).
  `frontend-legacy/` is the earlier plain-JS React prototype, kept for reference. Quick local
  run of the api + Vite together: `./run.sh`. See `frontend/README.md`.
- `core/latex.py` - shared `fix_latex` normalizer (strip backticks around `$…$`; `\[…\]`/`\(…\)` →
  `$$…$$`/`$…$`; collapse `\\` → `\`) imported by **both** `ui/gradio_app.py` and the `api/`
  package (was duplicated); mirrored in the frontend as `liveApi.fixLatex`.
  Regression: `tests/unit/core/test_latex_fix.py`.
  `core.latex.restore_formulas(answer, context)` runs after `fix_latex` in the api, Gradio and `answer_eval`: it puts back the context's verbatim LaTeX when the model only changed a formula's form (qwen2.5:7b adds or drops `\left \right`, adds `\tag`), see `docs/experiments/2026-10-05-7b-answer-fixes.md`.
- `formula_registry/` - reviewed formula registry (PR #3), see `docs/FORMULA_DRAFT_APPROVAL.md`.
  `ingestion/jobs.py` registers one pending draft per extracted formula before embedding (`_register_formula_drafts`); a draft is never approved or executed automatically.
  Router `formula_registry/api.py` is mounted in `api/main.py`: technician/admin create and edit drafts, approver/admin approve or reject (the recorded reviewer is the signed-in account), anyone can calculate with an approved formula.
  Calculation uses the bounded Decimal engine `formula_lab/engine.py`; changing or deleting the source document invalidates its formulas.
  The SQLite store is `paths.formula_registry_db` (`FORMULA_REGISTRY_DB`); back it up together with `TC_DL/`.
  The chat answers a calculation request with `llm.guards.CALCULATION_GUIDE`, pointing to the form instead of computing.
  `formula_lab/` holds the experiments and benchmarks that chose this approach (`TC_DL/TIEN_DO_NGHIEN_CUU_CONG_THUC.md`); only `engine.py` and `data/` are runtime code.
- `evaluation/run_eval.py` - Spike E regression harness. Computes recall@k + MRR for hybrid vs
  dense-only against `evaluation/eval_set.jsonl` (question → expected file_stem + section_path).
  Run this after any retrieval change. Pass goal is recall@5 ≥ 0.85.
- `evaluation/answer_eval.py` - answer-quality harness (coverage / citation / refusal / hallucination)
  against `evaluation/answer_set.jsonl`; `make answer-eval` needs Ollama + services.

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
| Ollama     | 11434 | **native `/api/chat`** (`llm/generator.py` maps a `/v1` `OLLAMA_URL` to it); model `models.llm_chat` (default `qwen2.5:7b-instruct`). KHÔNG quay lại `/v1/chat/completions`: endpoint đó BỎ QUA `options` → num_ctx/num_predict không có hiệu lực (đo 2026-06-11). |
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

`core/startup.py` runs once at every entrypoint (API lifespan, Gradio, CLI).
With `APP_ENV=production` it refuses to start when `JWT_SECRET_KEY` is missing, is a placeholder the repo used to ship, or is shorter than 32 bytes, or when `POSTGRES_PASSWORD` is the dev default.
In development a missing `JWT_SECRET_KEY` gives a random per-process key (tokens die on restart).
It also warns about services that do not answer and logs an error when the embedding / reranker service runs a different model than settings.

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
