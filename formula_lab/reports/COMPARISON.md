# DOCX formula experiment results

Selected strategy: **registry**. Highest eligible pass rate with zero observed unsafe outputs.

60 unique held-out UC × 3 runs per strategy. Repeated runs are not independent new cases. 60 development UC were excluded from the selection score.

| Strategy | E2E pass | Unsafe outputs | Valid UC pass | Stable pass / 60 | Eligible |
|---|---:|---:|---:|---:|---|
| llm | 118/180 (65.6%) | 20 | 51/84 | 38 | False |
| parser | 174/180 (96.7%) | 6 | 84/84 | 58 | False |
| registry | 180/180 (100.0%) | 0 | 84/84 | 60 | True |

## By group

| Group | LLM | Parser | Registry |
|---|---:|---:|---:|
| boundary | 16/30 | 30/30 | 30/30 |
| input | 30/30 | 30/30 | 30/30 |
| selection | 21/30 | 30/30 | 30/30 |
| source | 15/30 | 24/30 | 30/30 |
| ui | 18/30 | 30/30 | 30/30 |
| valid | 18/30 | 30/30 | 30/30 |

## Reproducibility and limits

- Models: Qwen3 30B A3B Instruct 2507 and text-embedding-3-small through LiteLLM/OpenRouter. Embedding dimension 1536. Reranker disabled for all strategies.
- All seven DOCX are indexed (141 text windows). Six curated calculators from three DOCX are the evaluated scope. The rest of the corpus acts as retrieval distractors.
- This is a controlled calculator-definition study, not a benchmark of general free-form chat or independent end-to-end DOCX extraction. Candidate formula identification and source excerpts are curated/shared. A full-corpus dense/BM25 retrieval gate checks that the source document is retrieved; section/formula selection is a common rule-based router.
- Isolated rows bypass retrieval. E2E rows include live retrieval; browser assertions replay definitions produced in that round and call the real calculator ASGI endpoint. They do not re-call the LLM for each click.
- Registry expressions were technically checked against original DOCX XML/rendered pages, not approved by a metrology specialist. Hand preparation effort and small known-formula coverage are the trade-off for its result.
- Source-corruption UC are synthetic fault injections. They test behavior when a plausible but unapproved formula arrives; they do not measure the frequency of actual ingestion errors.
- User declarations of conditions are trusted; physically plausible mistyped input cannot be reliably detected. No pass/fail metrology decision is implemented.
- Formula-source templates, unit vocabulary, input policies and preparer prompts were frozen before held-out evaluation. Gold numeric answers use independent Decimal arithmetic. All strategies share the bounded calculation engine.
- Rates apply only to these cases, model/provider configuration and document versions. Zero observed unsafe outputs is not a guarantee of correctness on unseen formulas.

## LLM usage (definition preparation only)

- llm: 36 calls; 43255 tokens; provider-reported cost 0.0041299274; median prepare time 1.687s.
- parser: 0 calls; 0 tokens; provider-reported cost None; median prepare time 0.003s.
- registry: 0 calls; 0 tokens; provider-reported cost None; median prepare time 0.002s.

Embedding and development-call costs are not included in the usage subtotal. Detailed manifests, generated definitions, screenshots and per-UC results are retained in each strategy folder.

## Failure examples

- llm / selection-12: unsafe=False; actual={"status": "invalid", "message": "Cần xác nhận đủ điều kiện áp dụng."}
- llm / selection-15: unsafe=False; actual={"status": "invalid", "message": "Cần xác nhận đủ điều kiện áp dụng."}
- llm / selection-18: unsafe=False; actual={"status": "invalid", "message": "Cần xác nhận đủ điều kiện áp dụng."}
- llm / valid-12: unsafe=False; actual={"status": "invalid", "message": "Cần xác nhận đủ điều kiện áp dụng."}
- llm / valid-15: unsafe=False; actual={"status": "invalid", "message": "Cần xác nhận đủ điều kiện áp dụng."}
- parser / source-11: unsafe=True; actual={"status": "ok", "value": "-107.8217821782178217821782178217822", "unit": "bar", "normalized": {"p0": "110", "gd": "9.9", "g0": "10.1"}, "expression": "-gd*p0/g0", "revision": "1", "formula_id": "gravity"}
- parser / source-16: unsafe=True; actual={"status": "ok", "value": "-14.04347826086956521739130434782609", "unit": "mm/min", "normalized": {"vt": "17", "eta_t": "0.95", "eta": "1.15", "dt": "3.15"}, "expression": "-eta_t*vt/eta", "revision": "1", "formula_id": "fall"}
