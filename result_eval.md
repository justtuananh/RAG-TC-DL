# Eval Log — RAG QTKĐ

---

## 2026-06-07 — Phase 0→3 hoàn tất

**Thay đổi áp dụng:**
- Phase 1: Rerank trên PARENT text (thay child text)
- Phase 2: Lexicon expansion — "điều kiện môi trường" → "…nhiệt độ độ ẩm áp suất"
- Phase 3: Sửa bug `_heading_level()` (outlineLvl + text guard) → re-extract → re-index (1674 points)

**Kết quả hybrid (55 câu):**

| Metric | Giá trị |
|--------|---------|
| recall@5 | **0.909** (50/55) ✅ |
| recall@10 | 0.982 (54/55) |
| nDCG@5 | 0.799 |
| MRR | 0.771 |
| MISS | 1 (Q39) |

**Per-file recall@5:**

| File | Kết quả |
|------|---------|
| QTKD_1.061 | 9/9 (1.00) |
| QTKD_1.062 | 6/7 (0.86) |
| QTKD_1.063 | 4/6 (0.67) |
| QTKD_1.071 | 8/8 (1.00) |
| QTKD_1.159 | 9/10 (0.90) |
| QTKD_1.160 | 6/6 (1.00) |
| QTKD_1.190 | 8/9 (0.89) |

**Goal:** recall@5 ≥ 0.85 → **PASS**

---

## 2026-06-07 — Baseline sau BGE-M3 (Phase 2 bị tắt)

**Kết quả hybrid (55 câu):** recall@5 = 0.709 (39/55) ❌

---

## 2026-06-10 — Thêm tầng ĐO CHẤT LƯỢNG CÂU TRẢ LỜI + nâng backend tập trung

**Vì sao:** eval cũ chỉ đo retrieval (recall@5=0.909) → mù với chất lượng câu trả lời
thực tế (long/hard answer kém). Thêm `eval/answer_eval.py` + `eval/scoring.py` +
`eval/answer_set.jsonl` (29 câu khó: lookup/formula/multi_section/cross_file/paraphrase/
out_of_scope, gold + key-facts verify từ source). Chấm tất định: coverage / citation /
refusal / hallucination. Chạy ĐÚNG đường production; so 1.5b vs 7b.

**Retrieval (anti-drift):** `run_eval.run_hybrid` nay gọi `production_retrieve` (top_k=20,
== app.py) thay vì phễu riêng top_k=50. Recall@5 vẫn **0.909** ✅ (không hồi quy); lexicon
mở rộng 1→12 entry không hại recall.

**Answer quality — qwen2.5:1.5b (29 câu), BEFORE → AFTER (Phase C: ngân sách ngữ cảnh động
+ prompt tổng-hợp/verbatim/refusal mạnh + num_predict=1024):**

| Metric | BEFORE | AFTER | |
|--------|--------|-------|---|
| coverage | 0.638 | 0.572 | ▼ (1.5b bị rối prompt phức tạp, chọn nhầm special-case) |
| citation_strict | 0.059 | 0.000 | ▼ (1.5b hầu như KHÔNG bao giờ ghi [n] dù được yêu cầu) |
| citation_lenient | 0.971 | 0.933 | ~ (fact CÓ trong passage đã retrieve → lỗi prompt, không phải retrieval) |
| refusal_acc (out_of_scope) | 0.500 | 0.667 | ▲ |
| hallucination_rate | 0.310 | 0.207 | ▲ (giảm; +num_predict chặn 1 ca sinh loạn ~29 phút) |

**qwen2.5:7b AFTER (cùng 29 câu, Phase C ngân sách 20k):**

| Metric | 1.5b AFTER | 7b AFTER | Ghi chú |
|--------|-----------|----------|---------|
| coverage | 0.572 | 0.507* | *bị tụt do (a) ~5 câu Ollama trả RỖNG tạm thời khi tải 45′; (b) ngữ cảnh 18k chôn fact |
| citation_strict | 0.000 | **0.808** | 7b ghi [n] đáng tin; 1.5b gần như KHÔNG → citation là lỗi MODEL, fix bằng 7b |
| hallucination | 0.207 | **0.103** | 7b bịa ít hơn hẳn |
| refusal_acc | 0.667 | 0.667 | wrong_refusal 7b = 2 (prompt refusal hơi quá tay) |

**PHÁT HIỆN QUAN TRỌNG (eval bác bỏ giả thuyết của plan):** Tăng ngân sách ngữ cảnh
(1800→~20k) LÀM HẠI: câu Q107 phình **18 288 ký tự** → 7b không thấy fact (lost-in-middle)
+ **Ollama 500**. Bản 1800/nguồn cũ cho coverage 1.5b CAO NHẤT (0.638). → **CAP lại
mỗi nguồn = 2 400 ký tự** (`MAX_BLOCK_CHARS`), giữ các cải tiến khác (prompt citation/refusal,
lexicon 12 entry, num_predict=1024, anti-drift).

**1.5b với cap 2400 (CHỐT) — so baseline:**

| Metric (1.5b) | baseline | budget 20k | **cap 2400** |
|--------|----------|-----------|--------------|
| coverage | 0.638 | 0.572 | **0.667** ▲ |
| formula coverage | — | 0.333 | **1.000** ▲ |
| refusal_acc | 0.500 | 0.667 | **0.667** ▲ |
| hallucination | 0.310 | 0.207 | **0.241** ▲ |
| citation_strict | 0.059 | 0.000 | 0.000 (trần model 1.5b) |

→ cap 2400 hồi phục coverage VƯỢT baseline; mọi metric 1.5b cải thiện trừ citation (model).

**Kết luận:**
- Retrieval tốt (recall@5=0.909); citation/coverage kém **chủ yếu do model 1.5b** (không ghi
  [n], lẫn special-case) — 7b sửa citation 0.00→0.81, hallucination 0.31→0.10.
- → **Prod nên chạy qwen2.5:7b** (đúng mục tiêu plan). 1.5b chỉ để dev.
- Backend giữ: prompt mạnh + lexicon + num_predict + cap ngữ cảnh 2400 + eval↔prod đồng bộ.
- 7b trên CPU không ổn định khi chạy lô dài (trả rỗng/500) → đo chuẩn trên GPU prod.

---
