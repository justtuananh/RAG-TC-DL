# DOCX Formula Lab

## Current registry extension (v2)

The `dev` branch now has **26 calculators: the original 6 plus 20 technically reviewed definitions from QTKĐ 1.190**. It supports bounded series inputs, square roots, absolute values, maximums and regression slope. See [v2 instructions](v2/README.md), [catalog](reports/registry-v2/CATALOG.md), and [v2 results](reports/registry-v2/KET_QUA.md). The v2 benchmark uses a live HTTP server and real browser requests, including actual embedding retrieval.

The remaining sections describe the **historical v1 comparison**. Its three worktrees and reports are preserved; the current expanded registry must not be compared to their six-calculator scores as if scope were unchanged. Production React/chatbot integration remains outside this research prototype.

## Historical v1 comparison

Research prototype comparing LLM-generated definitions, strict LaTeX parser and reviewed registry. Production RAG remains unchanged. All strategies use the same Decimal arithmetic engine, units, symbol glossary, six candidate calculators and retrieval. Only preparation/validation of the formula definition differs.

## Setup

Python 3.12, `python3 -m venv .venv-formula`, then `.venv-formula/bin/pip install -r formula_lab/requirements.lock`.
Set `OPENROUTER_API_KEY` in the environment or `~/.config/rag-formula/openrouter.env` (chmod 600). Never put it in frontend or Git. Model IDs and selected strategy are in `formula_lab/config.json`.

Index: `.venv-formula/bin/python -m formula_lab.retrieval`.
UI: `.venv-formula/bin/python -m uvicorn formula_lab.app:app --host 0.0.0.0 --port 8091`.
Tests: `.venv-formula/bin/python -m pytest formula_lab/tests`.
Benchmark: `.venv-formula/bin/python -m formula_lab.benchmark --split dev --rounds 1`, then `--split holdout --rounds 3` after freezing the implementation.

Browser tests use system `/usr/bin/google-chrome`, headless. Backend calculator is exercised using FastAPI TestClient; UI preparation replays the real definition generated during that benchmark round, not a fabricated correct answer. Live dense/BM25 retrieval and preparation are measured separately in every e2e row. This isolates browser interaction from repeated LLM latency.

## Data and methodology

`data/docx_inventory.json`: hashes and original XML paragraph text for 7 documents.
`data/sources.json`: curated excerpts and equation objects for six calculators drawn from three source documents; all seven documents are indexed as retrieval distractors.
`data/registry.json`: technically reviewed executable definitions, not specialist certification.
`data/ucs.json`: 120 use cases, 60 development and 60 holdout, 10 per category per split. Gold calculations are independent Decimal implementations in the dataset generator. Never pass UC answers to a strategy.
`reports/source-review/`: direct DOCX XML/render review evidence and limitations.

The study measures extraction-to-calculator robustness against frozen extracted equations plus injected faults. It does NOT independently rerun three complete DOCX extraction implementations. Source text/metadata are manually curated for all strategies, a material advantage compared with arbitrary unseen documents. No result should be generalized to all 351 math objects or unseen formulas.

Source mutations are intentional and documented; fixtures do not overwrite originals. They include a changed operator, absent definitions, revision drift, wrong document hash and missing formula. Registry blocks changes via reviewed content hash. Parser/LLM have original source access and common document hash checks but no preapproved expression comparison.

Definitions are reused only within a round for identical source payloads. LLM answers are regenerated between rounds. Record actual model, usage, package versions, Git commit, dataset hashes, errors and every score. No LLM judge. Provider failures are infrastructure failures, not correct refusals. No pass credit for skipped/incomplete runs.

Selection is a small explicit Vietnamese keyword router shared across all strategies, gated by full-corpus retrieval. Coverage outside the six calculators is not established. A safe refusal on a valid in-scope UC fails. Returned wrong numbers/provenance or computation for a forbidden input count as unsafe outputs. Browser rows additionally require interaction assertions.

Qdrant local and cache live in each worktree's `.formula-runtime`. Copy an immutable embedding cache to save cost, never share a writable Qdrant directory. Do not run UI and benchmark concurrently on the same local Qdrant path.

## Decision rule

Exclude any strategy returning an unsafe result or with incomplete/infrastructure-failed measurement. Among eligible strategies choose highest e2e pass rate; if within 5 percentage points, use 30 fresh cases, then provenance/maintenance/cost as tie-breakers. Do not select a winner if none qualifies. Rates are empirical on this small fixture set, not population accuracy guarantees.

## Selected result

The held-out comparison selected **registry**: 180/180 passes and zero observed unsafe outputs; parser 174/180 with 6 unsafe outputs; LLM 118/180 with 20. These are 60 unique UC repeated three times, limited to the six prepared calculators. See `reports/KET_QUA.md`, `reports/COMPARISON.md` and `reports/KNOWN_LIMITS.md`.

Run the selected demo with `./formula_lab/run.sh serve` (port 8093). The original React chatbot has not been changed.

Post-benchmark tooling guard: `build_data.py` now checks `data/review_approvals.json`. It cannot silently approve a changed source/formula when regenerating fixtures. Updating that manifest requires a new documented source review; the generator does not update it. This guard does not change the frozen runtime or the benchmark fixture contents.
