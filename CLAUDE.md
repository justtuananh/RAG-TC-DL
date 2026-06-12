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

## Architecture: a one-way pipeline in three stages

Each stage's output is the next stage's stable input. Keep this boundary — formula accuracy
is owned by `ingestion/`, not by any RAG framework.

```
TC_DL/*.docx                          ← source corpus (read-only; never modify)
   │  ingestion/  (project .venv)
   ▼
build/spike_a/*.md  + assets/ + extraction_report.json   ← clean Markdown, $LaTeX$ inline
   │  index/  (kotaemon/.venv → Docker services)
   ▼
Qdrant collection `qtkd_rag`          ← parent (section) + child (para/table/formula) chunks
   │  retrieval/ + app.py  (kotaemon/.venv → Docker services)
   ▼
Gradio web UI on :7861                ← hybrid search → rerank → Ollama answer + citations
```

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

### Stage 2 — `index/` (chunking + embedding)
- `chunker.py` — **parent-document retrieval**. Each heading section becomes a PARENT chunk
  (full text, stored for context expansion, `is_parent=True`); paragraphs / tables / formula
  blocks within it become CHILD chunks (`is_parent=False`) carrying their `parent_id`. Children
  are what gets embedded and searched; parents are returned to give the LLM full context.
  `chunk_id = sha256(file + section + text)[:16]` (hex), converted to a uint64 for the Qdrant
  point ID. This hashing makes re-indexing idempotent.
- `embed_store.py` — embeds chunks via the embedding service and upserts to Qdrant. Skips
  files already indexed (by `file_stem`) unless `--force`.

### Stage 3 — `retrieval/` + `app.py`
- `bm25_index.py` — in-memory BM25 (`rank_bm25`) built lazily by scrolling child chunks out
  of Qdrant. Its tokenizer **deliberately keeps technical codes/units intact** (e.g.
  `1.061:2021`, `MPa`, `bar`) — dense embeddings blur these, so BM25 is required for symbol/code
  precision. The corpus text for each chunk includes `file_stem` + `section_path` so BM25 can
  match QTKĐ numbers.
- `retriever.py` — full hybrid pipeline: `embed_query` → `dense_search` (children only) +
  `bm25_search` → `rrf_fuse` (Reciprocal Rank Fusion, k=60) → noise filter → `rerank_hits`
  (cross-encoder) → `fetch_parent` (return the full section). Boilerplate template sections
  ("Mẫu biên bản", "(Quy định)", …) are filtered out before reranking — `_NOISE_PATH_MARKERS`
  is duplicated in both `retriever.py` and `bm25_index.py`; keep them in sync.
- `app.py` — Gradio 4.x UI on **:7861**. Left = streaming chat (KaTeX, inline `$...$` enabled
  via `LATEX_DELIMITERS`), right = source-document viewer with the retrieved child passage
  `<mark>`-highlighted inside its parent section. System prompt forces context-only answers,
  verbatim LaTeX (no recompute), Vietnamese, and `[n]` citations; falls back to "không tìm
  thấy" when context lacks the answer.
- `eval/run_eval.py` — Spike E regression harness. Computes recall@k + MRR for hybrid vs
  dense-only against `eval/eval_set.jsonl` (question → expected file_stem + section_path). Run
  this after any retrieval change. Pass goal is recall@5 ≥ 0.85.

## Two virtualenvs — this matters

- **Project `.venv`** (`requirements.txt`: `olefile`, `lxml`, `scikit-image`) runs Stage 1
  ingestion only.
- **`kotaemon/.venv`** (sibling repo `../kotaemon`) provides `qdrant-client`, `gradio`,
  `rank-bm25`, `requests` for Stages 2–3. `app.py`'s docstring expects to be launched as
  `/path/to/kotaemon/.venv/bin/python app.py`. The Stage 2/3 deps are NOT in this repo's
  `requirements.txt` (they're commented out there).

## Local services (all Docker, must be running for Stages 2–3)

| Service    | Port  | Model / detail                                   |
|------------|-------|--------------------------------------------------|
| Embedding  | 8010  | OpenAI-compat `/v1/embeddings`, **1024-dim** (bge-m3) |
| Reranker   | 8011  | `/v1/rerank` (bge-reranker-v2-m3)                |
| Qdrant     | 6333  | collection `qtkd_rag` (cosine, 1024 dims)        |
| Ollama     | 11434 | **native `/api/chat`** (generation.py tự map từ env OLLAMA_URL dạng `/v1`), model `qwen2.5:1.5b` (dev; prod target qwen2.5:7b). KHÔNG quay lại `/v1/chat/completions`: endpoint đó BỎ QUA `options` → num_ctx/num_predict không có hiệu lực (đo 2026-06-11). |

Note: ports/models are **hardcoded** as module-level constants in `app.py`, `retriever.py`,
`bm25_index.py`, `embed_store.py` — change them in all relevant files together. The PLAN doc
proposes BGE-M3 for embeddings, but the code currently runs bge-large-en-v1.5 at 1024 dims;
trust the code. `VECTOR_SIZE = 1024` in `embed_store.py` must match the embedding service.

## Commands

```bash
# Stage 1 — extract formulas + build clean Markdown (project .venv; needs Ruby + mathtype_to_mathml gem)
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
python -m ingestion.spike_a                      # reads TC_DL/, writes build/spike_a/
python -m ingestion.spike_a SRC_DIR OUT_DIR      # custom paths

# Stage 2 — index into Qdrant (kotaemon/.venv; Docker services up)
python -m index.embed_store                      # incremental; skips already-indexed files
python -m index.embed_store --force              # re-index everything
python -m index.embed_store --query "phạm vi van an toàn 1400 bar"   # smoke-test query

# Stage 3 — run the chatbot UI (→ http://localhost:7861)
/path/to/kotaemon/.venv/bin/python app.py

# Eval — retrieval regression (run after any retrieval change)
python -m eval.run_eval                          # hybrid vs dense, recall@k + MRR
python -m eval.run_eval --mode hybrid -v
```

There is no test suite, linter, or build step — verification is `extraction_report.json`
(Stage 1) and `eval/run_eval.py` (Stage 3).

## Conventions

- All user-facing strings, prompts, comments-about-domain, and doc-section names are in
  Vietnamese; keep that.
- `build/` is generated output — safe to delete and regenerate; don't hand-edit.
- `⟦Fxxx⟧` is the formula placeholder contract between `extract_docx.py` and `spike_a.py`.
- Never recompute or rewrite a formula's LaTeX downstream — it is indexed verbatim and the
  whole point is that the user can trust it against the source image.
