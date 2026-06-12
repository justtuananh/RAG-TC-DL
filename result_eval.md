# Eval Log — RAG QTKĐ

---

## 2026-06-11 — Đợt R1–R6 (retrieval) + G1–G3 (generation) + sửa thước đo: recall@5 1.000, mọi cổng answer chính ĐẠT

**Phương pháp:** cause-map đo LIVE trên từng câu trượt (per-stage rank + rerank-score
+ fact-in-context) → mỗi đòn bẩy nhắm một CƠ CHẾ đo được, mỗi lever một commit, cổng
`run_eval`/`answer_eval` chạy tại từng commit (checkout detached); eval↔prod đồng bộ
tự động (run_eval → `production_retrieve`, import chung `rerank_hits`/predicate noise).

### Retrieval (55 câu) — per-lever, đo tại từng commit

| Bước | recall@5 | recall@10 | recall@1 | nDCG@5 | MRR |
|---|---|---|---|---|---|
| Baseline 2026-06-07 (tái lập đúng) | 0.909 | 0.982 | 0.655 | 0.799 | 0.771 |
| **R1** chặn "Phụ lục X" trần (honeypot form) | 0.927 | 0.982 | 0.691 | 0.826 | 0.799 |
| **R2** lexicon "điều kiện kiểm định"→body | 0.927 | **1.000** | 0.691 | 0.826 | 0.802 |
| **R3** doc rerank = breadcrumb + cửa sổ neo child | **1.000** | 1.000 | 0.745 | 0.894 | 0.858 |
| **R4** router gom đa tín hiệu + alias "píttông" | 1.000 | 1.000 | **0.782** | **0.908** | **0.876** |
| **R5** heading guard (câu/caption) + re-index 1.071 | 1.000 | 1.000 | 0.782 | 0.908 | 0.876 |
| **R6** phễu RIÊNG từng file cho câu đa-thiết-bị | 1.000 | 1.000 | 0.782 | 0.908 | 0.876 |

Per-file recall@5: **7/7 file = 1.00** — QTKD_1.063 từ 0.67 → 1.00 (mục tiêu DoD).
Bộ gold MỞ RỘNG 10 câu (Xử lý chung/chu kỳ ×5, phụ lục nội-dung-thật, mục dài k=2,
tài liệu viện dẫn, bảng phép kiểm định — verify từ build/spike_a, KHÔNG dùng để tune):
recall@5 = 1.000, MRR 0.925; pipeline CŨ cũng đạt 1.000 trên bộ này → vai trò của nó
là **guard chống lọc-oan/quá-khớp** (đặc biệt sau luật noise mới), không phải bằng chứng tăng.

**Cơ chế từng lever (tóm tắt bằng số đo):**
- **R1:** form MẪU BIÊN BẢN/GIẤY CHỨNG NHẬN ở 1.061/62/63 nằm trong BODY heading trần
  `# Phụ lục A/B` → thoát marker path, chứa đủ từ khoá mục lục + tên thiết bị → cross-encoder
  chấm rank 1–2 (Q12/Q18/Q22). Predicate `is_noise_path` dùng chung dense+BM25.
- **R2:** hỏi bằng ĐÚNG tiêu đề mục ("Điều kiện kiểm định") nhưng body chỉ là bullet đơn vị
  → Q18 dense=36/bm25=22, không lọt phễu top_k=20.
- **R3:** (a) mục tiêu-đề-đúng không nhắc tên thiết bị trong body thua mục anh em giàu chữ
  (4.1 = 0.32 vs 0.87) → tiền tố `file — mục` cân bằng tín hiệu (Q12/Q18: 8→2); (b) server
  reranker cắt 512 token → mục dài bị chấm mù phần chứa đáp án (6.3.3 ≈ 7,6k ký tự; công
  thức Q48 ở ký tự 1857) → cửa sổ 1400 neo theo child (Q39: 9→1, Q48: 7→1).
- **R4:** câu so sánh "van an toàn (1.061) và áp kế píttông (1.159)" bị tín-hiệu-đầu-thắng
  ghim 1 file → nửa kia không bao giờ được retrieve (= 2–3 wrong_refusal cross_file).
  Thêm biến thể chính tả "píttông"/"pittông áp kế" (Q116 mất tín hiệu vì khác dấu í).
- **R5:** 2 dòng body mang style Heading thật trong .docx ("# Sai số tương đối của H3000
  không được vượt quá ± 0,1 %." — tiêu chí chấp nhận bị hoisted khỏi mục 5.3; caption Hình 1)
  → guard text mở rộng; re-extract: **351/351 span $LaTeX$ byte-identical từng file**,
  conversion rate 1.0 không đổi; purge điểm cũ 1.071 rồi re-index riêng file đó (1665 points).
- **R6:** sau khi bỏ ghim, MỘT phễu toàn-kho bị cụm từ vựng áp đảo (3 file áp kế píttông)
  đè bẹp file thiểu số — Q115/Q116 top-5 không còn chunk 1.061 → fact vắng khỏi ngữ cảnh.
  Phễu dense+BM25+RRF **riêng từng file** → rerank chung → quota đại diện mỗi file.
  Đo fact-in-context sau R6: Q115 (20±5 ✓ 23±5 ✓), Q116 (65±15 ✓ 80% ✓), Q117 (cả 2 công thức ✓).

### Chất lượng câu trả lời (29 câu khó, qwen2.5:7b)

**Hạ tầng đo:** (i) endpoint OpenAI-compat `/v1/chat/completions` của Ollama **BỎ QUA
trường `options`** — bằng chứng sống: `/api/ps` báo `context_length=4096` trong lúc eval
gửi `num_ctx=8192`; prompt ~4,3k token bị cắt TỪ ĐẦU (mất system prompt + nguồn [1][2]) —
đúng cơ chế của citation hỏng, "budget lớn làm hại" và 500 cận biên đã ghi nhận trước đây
→ **G1**: `stream_ollama` chuyển sang native `/api/chat` (options + keep_alive có hiệu lực
thật; xác minh model nạp đúng 8192). (ii) 7b trong Docker-VM bị OOM-kill khi (re)load
(42–88 lần 500 "signal: killed"/giờ; VM 13,6GB còn ~4,8GB trống do container dự án khác)
→ đo chuẩn trên **Ollama native Metal** (:11435, cùng blob model, 27,8 tok/s, 0 lỗi hạ tầng
suốt 4 lần chạy 29 câu); harness retry/warm-up chỉ là lưới an toàn. (iii) **Sửa thước đo**
scoring sau khi *gold-self-test* phát hiện scorer phạt CHÍNH gold answer (Q113/Q121 '2 phút'):
`°C`≡`oC`, `min`≡`phút`, và số đứng riêng trong Ô BẢNG (đơn vị ở tiêu đề cột) được tính là
có nguồn; sau sửa gold-self-test SẠCH 0/29 — định nghĩa ảo giác cho số văn xuôi giữ nguyên.

**Bảng chuẩn (CÙNG backend native, CÙNG scorer đã sửa, cùng 29 câu — BEFORE′ = pipeline
gốc + /v1 + server ctx 4096, grounding chấm theo ngữ cảnh mới nên ưu ái BEFORE′):**

| Metric | BEFORE′ | sau R1–R6+G1 | **FINAL (+G2′+G3)** | Cổng DoD |
|---|---|---|---|---|
| coverage | 0.725 | 0.877 | **0.877** | ▲ rõ rệt ✅ |
| citation_strict | 0.806 | 0.810 | **0.857** | ≥ 0.85 ✅ |
| citation_lenient | 0.889 | 0.905 | **0.905** | — |
| refusal_acc (out_of_scope) | 1.000 | 1.000 | **1.000** | không tăng miss ✅ |
| wrong_refusal | 4 | 1 | **1** | → 0 ⚠ còn 1 (Q116) |
| hallucination_rate | 0.069 | 0.034 | **0.034** | ≤ 0.08 ✅ |

Per-category FINAL: lookup cov 1.000 (cite_s 0.875), formula 1.000, cross_file 0.667
(từ 0.167), paraphrase 0.833, multi_section 0.722. So với BEFORE chạy trên container CPU
(scorer cũ): coverage 0.659→, citation 0.765→, halluc 0.172→ — cùng chiều, biên độ lớn hơn.

**Generation levers:**
- **G1** `/api/chat` + `keep_alive=30m` (trên): nguồn [1][2] và LUẬT trong system prompt
  không còn bị cắt → coverage 0.725→0.877, wrong_refusal 4→1 (3 câu cross_file hết bị
  "không tìm thấy" oan nhờ R6 đưa fact vào ngữ cảnh + G1 giữ ngữ cảnh nguyên vẹn).
- **G2′** (2 chỉnh prompt GIỮ LẠI sau khi gate bác bản đầu): [n] cho TỪNG dòng gạch đầu
  dòng nêu số liệu; hỏi giá trị → NÊU GIÁ TRỊ (không tham chiếu điều khoản suông)
  → citation_strict 0.810→0.857, Q108 0.5→1.0. **Bản G2 đầu bị HOÀN NGUYÊN một phần
  theo cổng §6.4:** viết lại quy tắc 5 (từ chối) làm coverage 0.877→0.768 và refusal
  0.833 (Q121 từ chối oan MỚI, Q126 bỏ từ chối mà tính thẳng) → trả quy tắc 5 về nguyên
  bản; câu chữ "không tự chèn \times" vô tác dụng (Q111/Q122 vẫn chèn) → bỏ.
- **G3** lookup-only TẤT ĐỊNH: (a) `enforce_refusal_stop` cắt mọi thứ sau câu từ chối
  chuẩn (Q126 từng từ-chối-xong-vẫn-thay-số); (b) `is_calculation_request` chặn yêu cầu
  tính toán có số liệu cho sẵn TRƯỚC khi retrieve/gọi LLM (mẫu hẹp: "tính giúp/hộ…" hoặc
  "tính" + "X = <số>"; "Công thức tính…?" vẫn là tra cứu hợp lệ — có test pin). Áp ở cả
  `app.py` lẫn `answer_eval` (mirror) → refusal_acc 1.000 không phụ thuộc phương sai model.

**Tồn đọng (trung thực):** Q116 vẫn từ chối oan (1/29) dù cả 2 fact ĐÃ trong ngữ cảnh —
model-bound với câu so sánh độ ẩm, 2 mục liên quan nằm cuối ngữ cảnh; Q122 cov=0 vì model
quen tay chèn `\times`/`\[...\]` vào công thức (đã thử nhắc trong prompt — đo vô tác dụng);
Q121 còn 1 câu cờ ảo giác ('50/65 mm' — model gắn đơn vị mm vào giá trị DN trần của bảng);
multi_section 0.722 (ngân sách 2400/nguồn cắt mục dài — nới budget đã ĐO là phản tác dụng).

**Đã thử và BÁC theo cổng đo:** (1) G2 bản đầu — viết lại quy tắc từ-chối (hại, số ở trên);
(2) nhắc "không chèn \times" trong prompt (vô tác dụng); (3) bộ ext 10 câu làm "bằng chứng
tăng" (pipeline cũ cũng 1.000 — chỉ dùng làm guard). **Flag ngoài repo:** service reranker
LIVE :8011 thuộc compose `opencode` vẫn `max_length=512` — sau R3 doc rerank ≤ ~1,5k ký tự
nên 512 không còn cắt nội dung chính; stack tự build của repo này đã nhận env
`RERANKER_MAX_LENGTH` (mặc định 1024). **Scale-debt giữ nguyên flag:** BM25 in-memory
rebuild-by-scroll chưa đổi (hướng Qdrant-native sparse, plan-7 §4); phễu R6 thêm
~(n_file−1) lần search khi câu hỏi nêu ≥2 thiết bị (hiếm, chấp nhận).

**Guardrail & cổng cuối:** 351/351 span $LaTeX$ byte-identical (sha từng file khớp HEAD),
extraction_report rate 1.0 không đổi; `make check` 143 unit + fidelity XANH; eval gold gốc
(55 + 29) KHÔNG sửa — chỉ THÊM 2 file ext mới (10 + 3 câu, verify từ corpus).

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
