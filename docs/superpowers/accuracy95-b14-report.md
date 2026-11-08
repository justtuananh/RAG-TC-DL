# Verification-mode source lookup — B14 checkpoint

2026-11-07. Branch `fix/accuracy95`, continuation after `bd1a86e8`. Only the isolated API on port18081 was restarted. No merge, push, production deployment, shared indexing/database changes or formula approvals.

## Observed result

Root independently graded r12 B14 **correct** against unchanged gold and rubric. Normalized answer hash `4fbe5f38967669a4` was verified. The final answer shows technical inspection applicable in all three modes for QTKĐ1.061/1.062; QTKĐ1.063 retains its blank periodic cell and separately quotes the explicit source declaration that periodic technical inspection does not apply. No blank-cell negation was invented.

Historical distinct successes among the initial33failed DEV IDs are now17 (16independently graded, D05 locally author-graded). This is a ledger across revisions, not a fresh17/33 measurement or a whole-benchmark score. Previously correct questions were skipped, so subsequent changes do not freshly reverify their correctness. No>95% claim is made.

Six noncalculation failures remain: B02,B04,B18,D13,G06,G09. Ten calculation failures remain pending formula approval: E02,E06,E07,E11,E15,E17,E18,E19,Q48,Q52. No formula status was changed.

## Trace and architectural ruling

All three B14 source tables entered parent ranking. Their hierarchical headers and symbolic cells were represented faithfully, yet exact1.061/1.063 evidence scored0.02671/0.03365 and dropped before the final per-file results.1.062 scored0.74614 but lost evidence slots to procedural details.

A minimal natural-language cell-label variant (r11) preserved symbols/blank cells but still scored1.0610.05156/1.0630.03912 against unrelated procedural text above0.95; its answer remained wrong. Raw r11 is retained, not counted as progress.

Root explicitly approved a structural lookup within the existing exact-source retrieval scope instead of arbitrary confidence overrides: resolve a requested catalog document, one recognized verification mode and one exact source row; require coverage for every named document; fall back for mixed intent, multiple matching rows/tables, unknown symbols or ambiguous headers. This preserves original complete headers/row context and verbatim symbols. A blank is labelled only “ô trống/không đánh dấu”; a negative meaning is quoted only from an explicit source declaration.

## Changes and safeguards

- Recognize supported verification-mode tables and render their +/blank cells under the actual column labels.
- Extend exact reference lookup only for explicitly labelled QTKĐ requests with one mode and one unambiguous source row. Read only catalog-loaded Markdown files.
- Return source-bound summaries together with each full original table; retain explicit matching source declarations verbatim.
- Unknown/mixed requests and partial document coverage retain normal retrieval. No threshold reductions, benchmark-ID rules or canned gold answers.
- Generalized tests cover positive resolution, preserved blanks, explicit negative declarations, complete named-document coverage, multiple rows/modes/tables, mixed intent, unknown symbols, ambiguous headers and numeric measurements mistaken for document references. Positive feature tests and explicit-document guard were observed RED before implementation, then GREEN.

## Verification

Fresh full unit suite: **962 passed, 1 skipped, 0 failures, 0 errors** (963 collected),72.05s;128warnings retained in the log.

Changed-file Ruffcheck/Ruffformat and `git diff --check` passed.55targeted parser/extraction/reference/architecture checks passed before the final full suite. r12 B14 total request time was0.2166s (single failed question only; not representative of whole-benchmark latency). The API health wasok with unchanged `qwen2.5:7b-instruct` model before inference.

## Evidence

Under `/home/hiennt/projects/aime-eval/vong_fix/rounds/`:

- `accuracy95-failures-r11`: rejected verbalization-only variant.
- `accuracy95-failures-r12`: raw answer/input, gold filtered to B14 and `labels-independent-root.json`.
- `accuracy95-design/trace-b14.json`, `trace-b14-parent-scores.json`, `trace-b14-r11-parent.json`: stage-by-stage evidence loss.
- `accuracy95-design/failure-ledger.json`: latest observed results and grading provenance.
- `accuracy95-design/unit-b14-final.log` and XML: fresh final unit verification.
- `accuracy95-design/b14-report.md`: this report. Earlier reports remain historical snapshots.
