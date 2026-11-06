# Accuracy95 isolated branch report — 2026-11-06

Branch: `fix/accuracy95`, based on T12 `d53ae236`. Candidate code lives at `/home/hiennt/stg/accuracy95-work`. No merge, push or production deployment was performed. Only the isolated API on port18081 was restarted for this final round.

## Scope and measurement limits

The latest user instruction supersedes the original plan's full200 measurement: inspect/rerun only failed DEV questions, one repetition; skip correct questions; do not inspect holdout. No fresh full200 score exists and >95% has **not** been demonstrated. Historical improvements below are observations from different code revisions, not a fresh aggregate score or proof they all remain fixed.

Initial failed DEV list: 33. Historical independently graded successes: B09, B12, C06, D17, G07, G14, G15, G20, Q27 (r1); D10, B22, C09 (r3); D15 (r4). Final r6 D05 is author-graded correct, weaker evidence than an independent grade. These14 distinct observed successes leave19 previously failed IDs unresolved; none of the prior correct IDs was rerun in the final round.

Known remaining IDs: B02, B04, B14, B18, D13, E02, E06, E07, E11, E15, E17, E18, E19, Q48, Q52, G06, G09, G11, G18.

## Changes

- Added bounded document-scoped quotation selection with one batched reranker call. Preserve complete tables, column headers, qualifications, formulas and original source indices. Return explicit missing-evidence messages per document; retain generation fallback on no evidence/service failure.
- Added accent-insensitive device routing/query expansion and removal of explicitly labelled QTKĐ codes from semantic ranking questions, retaining decimal measurements and conditions.
- Added exact source-based appendix-topic and replacement-declaration lookup with safe intent and document coverage checks.
- Integrated quotations into ambiguity, multi-document and refusal paths. Wider bounded per-file coverage and opt-in validated settings support seven documents.
- Added optional secret-backed Qdrant authentication because the shared data service was secured during this session; no secrets are stored in committed files.
- Final grounded boundary fix appends an immediately following CHÚ THÍCH to a selected paragraph and prefixes list items with their introductory quantity/context. Compact ranking inputs are preserved separately from displayed qualified quotations.

## Final failed-only diagnosis and outcomes

r4 grading artifact already existed at takeover. All11 answer hashes match its labels under the unchanged scorer normalization. It reports D15 correct; D05/D13 and eight others partial or wrong. The artifact is retained as prior independent grading, not reauthored here.

Final boundary regressions were observed RED before implementation, then GREEN. An initial variant ranked enriched quotations directly (r5), which regressed D05/D13. Diagnostic reranker scores showed that adding context lowered D05 to0.33492 below the existing0.35 threshold and shifted D13 from the table toward operating conditions. That variant was rejected. Final code ranks the original compact units and enriches output only; thresholds were not reduced.

r6 reruns only D05 and D13:

- D05: **correct (local author grading)**. States replacement of dirty/contaminated fluid and includes the manufacturer-equivalent-fluid CHÚ THÍCH.
- D13: **partial (local author grading)**. Full relevant table is present, and ±10s now correctly carries its measurement-error introduction. Still does not explicitly select3min for accuracy0.02/5MPa and requests clarification. It is not counted as fixed.

Remaining noncalculation failures need further retrieval/selection work rather than more arbitrary threshold changes: B02, B04, B14, B18, D13, G06, G09, G11, G18. Ten calculation failures (E02,E06,E07,E11,E15,E17,E18,E19,Q48,Q52) remain behind formula approval. Isolated registry status counts: {'pending_review': 180}. No formulas were approved or approval safeguards bypassed. Expert preparation remains at `/home/hiennt/projects/aime-eval/DUYET_CONG_THUC_NHOM_E.md`.

The refusal fallback can replace an initially streamed refusal in the final done answer; raw r6 preserves both fields for review. This final round grades the final answer consistently with the existing benchmark.

## Verification

- Full unit suite: 939 passed, 6 skipped, 0 failures, 0 errors (945 collected),58.44s.128 warnings are recorded in the log (existing deprecations and unavailable network-version probe).
- Extraction tests:14 passed, including three new RED→GREEN boundary/selection regressions.
- Ruff check on every modified/new Python file: passed. Ruff formatting for final changed extraction files: passed. `git diff --check`: passed.
- Isolated API `/api/health`: statusok, unchanged model `qwen2.5:7b-instruct` before the final inference batch.

Latency observations (no full-system or whole-benchmark claims):

- accuracy95-failures-r4: n=11, median=2.05s, maximum=2.82s (only this failed-question subset).
- accuracy95-failures-r6: n=2, median=2.04s, maximum=2.64s (only this failed-question subset).

## Integrity and artifacts

Unchanged SHA256 values, verified against baseline:

- questions200_v1_1.json: `bb6acb47e7803fd2de831cfdc62beef121ff16d6eba2dfa56ba19db6f0bf6c46`
- split.json: `25ce73b0e578c56f7f1d3eadfdc57384227ce8d5b2fb2e8bbfd335ffa1be46ed`
- score.py: `cdd54e9daf59651dacfd66445195ab855d2e452bd597b36a9c80622b54e4e1a0`

Artifacts under `/home/hiennt/projects/aime-eval/vong_fix/rounds/`: r1/r3/r4 retain raw runs and prior independent labels; r5 preserves the rejected variant; r6 contains input.json, run.jsonl and explicitly labelled labels-local.json; accuracy95-design contains failure-ledger.json, unit-final.log, unit-final.xml and this report. The benchmark labels/scorer/gold were not modified.
