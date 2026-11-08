# Accuracy95 continuation: evidence preserved through ranking

2026-11-06. Worktree `/home/hiennt/stg/accuracy95-work`, branch `fix/accuracy95`, continuation after `f20fe2d3`. No merge, push, production deployment, shared service restart or formula approval was performed. Only the isolated API on18081 was restarted.

## Observed progress

Root independently reviewed static answers against unchanged gold/rubric, separately from this implementation agent:

- **G18 correct in r7**: all required stopwatch ranges, resolution and errors appear under the correct six documents. Correct1.159/1.160 equipment sections had previously been discarded because long table prefixes hid the stopwatch row from the reranker.
- **G11 correct in r10**: H3000 operating condition700bar, mean of3measurements and3mm/min;1.159 mean of3measurements,5% clause, complete Bảng4 with units and conditional1.5/1.5/1.5/3/3 row are all present and correctly attributed.
- r8 produced **no additional correct answers** (B02,B14,G06,G09). r9 D13 remained wrong and G11 partial. These failures and raw answers are retained. The answer remains verbose and repeats some context.

Historical distinct successes among the initial33failedDEV IDs now total **16**:13prior independently graded, D05 locally author-graded, and G18/G11 independently reviewed by root. This is a ledger across revisions, **not a fresh16/33 accuracy measurement**. No earlier correct ID was rerun after it was graded correct, so later changes have not reverified those successes. There is no new200question score and no demonstrated>95% claim.

Remaining known failures: B02, B04, B14, B18, D13, E02, E06, E07, E11, E15, E17, E18, E19, Q48, Q52, G06, G09. Seven noncalculation failures remain (B02,B04,B14,B18,D13,G06,G09);10calculation failures remain behind approval. The isolated registry still has180pending-review formulas and no approved formulas; approval safeguards were not bypassed.

## Root causes and final changes

1. **Long equipment tables exceeded the reranker's input window.** Added `core/table_focus.py`, a pure ranking-only view selecting equipment rows by a shared consecutive3word name phrase. It keeps headers, every cell and continuation rows. Malformed/unsupported tables or unmatched queries retain original text. Both parent retrieval ranking and evidence ranking use it; displayed quotations/sourcepayloads preserve full original tables. This fixed G18 in r7. A shared helper was placed in core after the architecture test caught an upward import; the failed test log is retained.
2. **RRF candidate pool counted children while ranking deduplicated parents later.** ActualG06 trace: first8children covered only2parents;1.159 equipment section first appeared at childposition25. Pools now cap distinct parentsections and retain every matched childanchor within the bounded sections. The generalized regression passed. r8 did not establish an answer-quality gain for this correction; it is retained as a bounded-recall accounting fix, without claiming benchmark improvement.
3. **Any inline dollar symbol was treated as a complete formula.** Symbol definitions became overlapping sliding candidatewindows and consumed all3quotation slots. Explicit equations and their adjacent variable definitions now form one source-bound unit; unrelated limitparagraphs remain separate.
4. **Quoted limits lost their dependencies.** When an explicitly referenced BảngN exists in the same parentsection, displayed evidence includes its caption, units and table. Explicit measurement conditionlists remain attached to subsequent quoted values within thatsection. Compact ranking inputs remain separate from displayed qualifications. These changes fixed G11 in r10.

No thresholds were reduced. No gold answers or per-question canned responses were added. Formula grouping only preserves quotations; it does not calculate or approve formulas.

## Verification

- Final full unit suite: **948passed, 6skipped, 0failures, 0errors** (954collected),59.35s;128warnings are preserved in the log.
- New regressions were observed RED before the corresponding fixes, then GREEN. Final extraction tests:18passed.
- Ruffcheck, Ruffformat on all8changed/new Python files and `git diff --check`: passed.
- API health before each inference batch:statusok, unchanged `qwen2.5:7b-instruct` model.
- Independent root label hashes for every r7–r10 answer match the unchanged scorer normalization.
- questions200_v1_1.json,split.json,score.py SHA256 values still match `baseline-hashes.json`. No holdout contents were inspected.

Latency observations apply only to the newly tested failed subsets:

| Round | Questions | Median total | Maximum total |
| --- | --- | --- | --- |
| r7 | 2 | 2.28s | 2.65s |
| r8 | 4 | 2.51s | 3.25s |
| r9 | 2 | 2.80s | 2.93s |
| r10 | 1 | 3.77s | 3.77s |

## Artifacts

All paths are under `/home/hiennt/projects/aime-eval/vong_fix/rounds/`:

- `accuracy95-failures-r7` through `accuracy95-failures-r10`: input.json, filtered gold, raw run.jsonl and labels-independent-root.json.
- `accuracy95-design/trace-next.json`: diagnostic retrieval/confidence/evidence scores for5stillfailedquestions; no full benchmark inference.
- `accuracy95-design/failure-ledger.json`: latest per-ID observed result and grader provenance.
- `accuracy95-design/unit-r7.log` / `unit-r7.xml`: retained architecture failure. r8/r9/r10 logs and XML retain subsequent passing checks, with r10 final.
- `accuracy95-design/continuation-report.md`: this report. Earlier `final-report.md` remains a snapshot of the previous commit.
