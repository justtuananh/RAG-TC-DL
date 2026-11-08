# Typed source-cell lookup — D13 checkpoint

2026-11-07. Branch `fix/accuracy95`, after B14 checkpoint `10de723f`. Work remained isolated on port 18081; no merge, push, production deployment, shared service/index changes or formula approvals.

## Observed result

Root independently graded r14 D13 **correct**. Verified normalized answer hash: `c6a15ba58cca95c6`. The final answer explicitly selects **3 min** from QTKĐ 1.159 for accuracy class 0.02 and upper range 5 MPa, identifies the -0.1 to 6 MPa row and preserves the complete source section. The caption and normative sentence establish that this is a minimum, and ±10 s remains visibly a measurement error rather than a minimum duration.

Historical distinct successes among the initial 33 failed DEV IDs are now **18** (17 independently reviewed, D05 locally author-graded). This is a ledger across revisions, not a fresh 18/33 measurement or a whole-benchmark score. Earlier correct questions were skipped, so later changes do not freshly reverify those successes. No >95% claim is made.

Five noncalculation failures remain: B02, B04, B18, G06, G09. Ten calculation failures remain behind formula approval: E02, E06, E07, E11, E15, E17, E18, E19, Q48, Q52. No formula status changed.

## Root cause and implementation

The correct source parent and complete duration table were already retrieved. Candidate selection favored measurement-error/initial-speed fragments; presenting the table alone also failed to choose the applicable row and column. Further confidence changes would not establish a reliable field-to-cell relation.

Added `query/table_lookup.py`, limited to explicitly named accuracy-class and upper-range query fields and recognized two-level duration tables. It checks:

- Exact class-column binding and interval-row membership, including inclusive bounds and strictly greater ranges.
- Source range-unit spelling and case, source duration units and requested duration units; no conversions.
- A source caption that matches the requested quantity, unique class headers and recognized row labels.
- One applicable cell across supplied source sections. Different documents/tables with matching cells remain ambiguous even if values coincide. Repeated hits for the same source section are deduplicated without changing citation indices.
- Explicit document scope: a named QTKĐ cannot be replaced by a fallback hit from another document; multiple named documents fall back conservatively.

The API uses the result only when extraction is enabled and existing calculation/approval guards have already passed. A uniquely applicable cell answers directly with its original source section and citation, before an otherwise unnecessary generic-device clarification. Missing fields, operating-pressure-only inputs, mismatched units, unsupported structures and ambiguity retain the existing answer path. This is table lookup, not formula evaluation.

## Review findings fixed before final measurement

Root found an important document-scope gap: a named QTKĐ could initially be replaced by a different fallback document. The repro was observed RED, then fixed with conservative scope checks.

Root also found that linguistic case folding could equate mPa and MPa. The repro was observed RED; numeric-unit tokens now preserve case during query and source extraction and compare exactly. MPa, Pa and mPa are distinct; display preserves source spelling. A separate regression prevents ignoring an unrecognized source interval when deciding uniqueness.

r13 preserves the earlier canonical-input answer and pre-SI-review variant. It is not counted as final evidence; r14 was rerun after these safeguards. No previously correct question was rerun.

## Verification

Final full unit suite: **994 passed, 1 skipped, 0 failures, 0 errors** (995 collected), 67.50 s; 129 warnings retained in the log. Targeted parser/API/architecture checks: 49 passed.

Generalized parser tests cover different classes/ranges/units, both interval bounds, missing/duplicate fields, operating pressures and dates that must not become lookup fields, source-unit case, explicit document mismatch, ambiguous documents/tables/headers and unrecognized source rows. The API regression uses different fixture values and confirms the exact cell is returned in both streamed and final answers without generation or ambiguity boilerplate. Positive resolver, API, scope and SI-prefix tests were observed RED before their fixes, then GREEN.

Ruff check, Ruff format and `git diff --check` passed. The API reported healthy with unchanged `qwen2.5:7b-instruct` model before r14. The single D13 request took 2.565 s; this is not a whole-benchmark latency measurement.

## Evidence and integrity

Under `/home/hiennt/projects/aime-eval/vong_fix/rounds/`:

- `accuracy95-design/trace-d13-current.json`: retrieved parents, confidence filtering and evidence scores before the cell resolver.
- `accuracy95-failures-r13`: retained pre-SI-review variant.
- `accuracy95-failures-r14`: failed-only input, filtered unchanged gold, raw answer and root independent grading.
- `accuracy95-design/failure-ledger.json`: latest observed results and grading provenance.
- `accuracy95-design/unit-r14.log` and XML: final full-unit verification.
- `accuracy95-design/d13-report.md`: this report. Earlier reports remain historical snapshots.

Question-set, split and scorer hashes remain unchanged against `baseline-hashes.json`. No holdout contents were inspected and no full200 run was performed.
