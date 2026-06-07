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
