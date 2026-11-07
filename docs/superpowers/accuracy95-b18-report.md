# Catalog title context — B18 checkpoint

2026-11-07, branch `fix/accuracy95`, after `40fb10f4`. No merge, push, production deployment, shared service/index changes or formula approvals. Only the isolated API on port 18081 was restarted.

Root independently graded r15 B18 **correct**, hash `feee74e1486521a7` verified. The answer includes both required sequences with their normal-operation condition:1.071 at350 then700bar;1.159 at50 then100% of upper range. No previously correct question was rerun.

The source paragraph was already retrieved. Diagnostic scoring showed its H3000 abbreviation did not expose the generic device words in the question: the correct350→700bar paragraph scored0.5600 and lost to detached700bar text at0.9212. Applying each document's own catalog title consistently to every evidence candidate changed the correct paragraph to0.9738 (rank1), while the detached fragment scored0.9376. Parent retrieval already had the correct section at0.9683, so the final change is limited to evidence ranking.

The implementation prefixes bounded ranking inputs with each source's own title, resolved once per document; missing titles retain the previous input. Original quotations, candidate caps, confidence floors and source indices remain unchanged. This is uniform source metadata, not a question/benchmark rule. A generalized regression was observed RED, then GREEN, and verifies that both documents retain their own title and exact quoted source references.

Final full unit suite: **995 passed, 1 skipped, 0 failures, 0 errors** (996 collected),67.92s,129warnings retained.38targeted extraction/API/architecture checks passed. Changed-file Ruffcheck/Ruffformat and `git diff --check` passed. API health wasok with unchanged `qwen2.5:7b-instruct` model before r15; B18 took2.646s (single failed question only).

Historical distinct successes among the initial33failedDEV IDs now total **19** (18independently reviewed plus locally author-gradedD05). This is a ledger across revisions, not a fresh19/33 measurement or a whole-benchmark score. Earlier correct cases remain untested on later revisions by user instruction; no>95% claim is made. Four noncalculation failures remain:B02,B04,G06,G09. Ten calculation failures remain pending formula approval:E02,E06,E07,E11,E15,E17,E18,E19,Q48,Q52.

Evidence under `/home/hiennt/projects/aime-eval/vong_fix/rounds/`: `accuracy95-failures-r15` retains failed-only input, filtered gold, raw run and independent root labels; `accuracy95-design/trace-b18-title-counterfactual.json` preserves baseline/counterfactual scoring; `unit-r15.log` and `unit-r15.xml` preserve final verification; `failure-ledger.json` records latest observed results; `b18-report.md` is this report. Questions, split and scorer hashes remain unchanged against `baseline-hashes.json`. No holdout was inspected or full200 run performed.
