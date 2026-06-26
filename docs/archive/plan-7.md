# Plan‑7 — Đường tới recall@5 ≥ 0.85 (đã CHẨN ĐOÁN), kế hoạch 2026‑06‑07

> Tài liệu thực thi cho đợt cải tiến retrieval. Tự‑chứa. Dùng `docs/PLAN.md` làm bối cảnh kiến trúc tổng thể.

## Context (vì sao có plan này)

Sau khi swap embedding sang **BGE‑M3**, recall@5 (hybrid) chững ở **0.709 (39/55)** — vẫn dưới mục tiêu
**0.85 (47/55)**. Người dùng đề xuất thử **GraphRAG / LightRAG / nano‑GraphRAG** (có sẵn trong kotaemon).

Đã chạy **workflow nghiên cứu đa tác tử** (5 nhóm kỹ thuật + hội đồng chấm điểm + tổng hợp); một agent
**đo trực tiếp rank của từng câu MISS trên pipeline live** (Qdrant/embed/rerank đang chạy), biến việc
đoán mò thành **bản đồ nguyên nhân**. Các phát hiện then chốt đã được **tự kiểm chứng** (grep corpus,
đếm span LaTeX). Kết quả: điểm chững **KHÔNG phải lỗi model/embedding**, mà là **3 cơ chế cơ học tách
biệt** (1 trong số đó là **bug ingest**); router đang đúng **9/9**. Có đường rõ ràng tới **~0.87 (48/55)**.

**Outcome mong muốn:** recall@5 ≥ 0.85 trên eval 55 câu, không hồi quy recall@10/MRR, **giữ nguyên rủi
ro #1 — công thức `$LaTeX$` verbatim** (351 span, không được viết lại/cắt/tóm tắt), thuần offline, thay
đổi khu trú trong pipeline standalone (`retrieval/*`, `index/*`, `ingestion/*`, `eval/*`).

**Quyết định phạm vi (người dùng chốt 2026‑06‑07):** thực thi **trọn Phase 0→3**. Mỗi phase qua cổng
hồi quy `python -m eval.run_eval`; recall tụt so với bước trước → dừng. **Phase 4 HOÃN.**

---

## 0. Kết luận về GraphRAG / LightRAG / nano‑GraphRAG: **TỪ CHỐI** (điểm 12/100 — thấp nhất)

Không thuộc đường tới 0.85; chỉ là experiment offline (gần như chắc thất bại). Khớp với `docs/PLAN.md`
§10 (GraphRAG đã liệt out‑of‑scope). 5 lý do định lượng:

1. **Sai lớp bài toán.** Graph RAG dành cho câu hỏi tổng hợp/đa bước xuyên kho. Cả 9 MISS đều là **tra
   cứu cục bộ 1 file/1 mục** ("mục 5.1 ghi (20±5)°C") — không có quan hệ nào để traverse.
2. **Không chấm được bằng eval, dễ làm tụt điểm.** Query graph trả bảng entity/relationship/community
   **không có `section_path`**; `run_eval._matches()` chấm theo `(file_stem, section_path)` của đoạn con
   verbatim. Một entity "điều kiện môi trường" hoàn hảo vẫn không tính là trúng "5.1 Điều kiện kiểm định".
3. **Vi phạm rủi ro #1 (công thức verbatim).** Index graph đẩy mọi chunk qua LLM trích xuất+tóm tắt →
   diễn giải lại **351 span `$LaTeX$`** thành mô tả văn xuôi; qwen2.5:1.5b/7b chắc chắn làm hỏng
   `\frac{}{}`, chỉ số dưới, đơn vị. Phá vỡ "không bao giờ viết lại LaTeX downstream".
4. **Bất khả thi với phần cứng.** README LightRAG **bắt buộc ≥32B tham số + ≥32KB ctx**, cảnh báo tránh
   model nhỏ; 32B không vừa 8GB. GitHub issue #749: Ollama local chỉ trích được 8 entity/7 quan hệ.
5. **Phá vỡ ràng buộc scale.** ~3–6 LLM call/chunk, đắt gấp 20–100× embedding → ước tính **~24 GPU‑ngày
   cho 1000 file, ~120+ cho 5000 file** trên 1 GPU 8GB, chạy lại mỗi lần sửa tài liệu. Cấu trúc mục đồng
   nhất (lợi thế cho phương án rẻ) lại thành "bùng nổ entity trùng lặp" cho graph.

> Góc hấp dẫn duy nhất của graph (entity chuẩn hoá các bullet môi trường thành khái niệm "điều kiện môi
> trường") chính là thứ một **lexicon tĩnh 5 dòng** (Phase 2) làm được với độ chắc chắn 100%, 0 trễ, 0
> ảo giác, 0 rủi ro công thức.

---

## 1. Bản đồ nguyên nhân 9 MISS (đo live, đã tự kiểm chứng)

Định tuyến (router) **9/9 ĐÚNG** — không cần chỉnh. 9 MISS chia **3 cơ chế TÁCH BIỆT**:

| Lớp | Câu | Đo được (rank) | Cơ chế thật | Phương án |
|---|---|---|---|---|
| **A. Rerank sai đơn vị** | Q5, Q28, Q30, Q52, Q55 | có trong pool fused (rank 1–23) nhưng cross‑encoder loại | reranker chấm **child 1 dòng** ("Nhiệt độ môi trường: (20±5)°C") thua các chunk anh em giàu chữ hơn | rerank trên **PARENT** |
| **B. Lệch từ vựng** | Q12, Q18 | rerank‑parent vẫn chỉ tới rank 10 | query "điều kiện môi trường" ≠ body "Nhiệt độ/Độ ẩm/Áp suất" (mọi mục "Điều kiện kiểm định" đều chứa các bullet này — grep 7/7 file) | **lexicon expansion** tất định |
| **C. Bug ingest** | Q26, Q29 | dense=None, bm25=None, fused=None | **bug `extract_docx.py`**: trong `QTKD_1.071`, bullet/câu bị render thành heading `### -` / `##` → mục 5.2.1/5.2.5 RỖNG, đáp án lạc `section_path` rác | sửa ingest + re‑index |

**Số đo rank then chốt (live):** Q5 dense=24 bm25=11 fused=23; Q28 dense=13 bm25=1 fused=1; Q30 dense=23
bm25=1 fused=7; Q52 dense=10 bm25=4 fused=5; Q55 dense=7 bm25=3 fused=5 → đều trong pool, là vấn đề
rerank. Q26/Q29: dense=None/bm25=None → đáp án **không nằm trong chunk nào đúng path** → bug ingest.

**Tự kiểm chứng (2026‑06‑07):** chỉ `QTKD_1.071` có dòng `### -` (6 file khác = 0); dòng 330 — đáp án
Q26 ("…áp suất 70 bar… 290 mg") — bị biến thành `## heading`; tổng span `$LaTeX$` corpus = **351**
(mốc checksum cho guardrail công thức).

> ⚠️ Lưu ý không cộng dồn: Phase 1 (parent‑rerank) cũng cứu Q5/Q28/Q30; Phase 2 (lexicon) cũng chạm
> Q5/Q28/Q30. Đóng góp **riêng** của Phase 2 trên nền Phase 1 = đúng **Q12 + Q18**. Dùng `--debug-miss`
> để quy đóng góp đúng cho từng phase.

---

## 2. Kế hoạch theo giai đoạn (rẻ‑an‑toàn trước; mỗi bước qua cổng `run_eval`)

| Phase | Việc | recall@5 kỳ vọng | Re‑index? | Rủi ro công thức |
|---|---|---|---|---|
| **0** | `--debug-miss` trong `run_eval.py` (read‑only) | 0.709 (mốc) | không | không |
| **1** | **Rerank trên PARENT** + `reranker_max_length≥1024` | **→ ~0.80 (44/55)** | không | không |
| **2** | **Lexicon domain tất định** (mở rộng query cho embed+bm25, rerank query GỐC) | **→ ~0.836 (46/55)** | không | không |
| **3** | **Sửa bug heading `extract_docx.py`** + re‑index | **→ ~0.87 (48/55) ✅** | có | **🛡️ guardrail 351 span** |
| **4** *(HOÃN)* | Qdrant native sparse (fix scale) + heading breadcrumb | ~+0–2pp | có | thấp |

### Phase 0 — Công cụ chẩn đoán `--debug-miss` (cổng đo cho mọi bước)
- **File:** `eval/run_eval.py`.
- **Việc:** thêm cờ `--debug-miss`; với mỗi câu, in rank kỳ vọng ở **dense‑only / bm25‑only / fused
  (trước rerank) / sau rerank** + `route(q)` so với `expected.file_stem` (hit/miss). Tái dùng helper đã
  import sẵn (`embed_query, dense_search, bm25_search, rrf_fuse, _filter_noise, rerank_hits, route,
  _hit_rank`). In dòng tóm tắt mỗi câu + footer router hit‑rate.
- **Đảm bảo:** read‑only tuyệt đối; không gọi model ngoài stack embed/bm25/rerank hiện có.
- **Tác động:** 0pp (thước đo). Chốt baseline 0.709 / recall@10 0.836 / MRR 0.483 + bản đồ 9 MISS.
- **Verify:** `python -m eval.run_eval --debug-miss --mode hybrid` tái hiện đúng bản đồ §1 (route ok 9/9;
  Q26/Q29 = None ở mọi tầng; Q5/Q28/Q30/Q52/Q55 fused≤23; Q12/Q18 fused~26–28).

### Phase 1 — Rerank trên PARENT (đòn bẩy lớn nhất)
- **File:** `retrieval/retriever.py` + **mirror** `eval/run_eval.py` (`run_hybrid`).
- **Việc:** sau `fused = _filter_noise(rrf_fuse(...))[:RERANK_POOL]` → **khử trùng pool theo
  `parent_id`** (giữ child RRF tốt nhất mỗi parent); `fetch_parent()` từng parent; **rerank trên text
  của PARENT** thay vì child (thêm tham số `documents=`/`doc_text_fn` vào `rerank_hits` để input là
  parent text nhưng hit trả về vẫn mang payload child + `parent_payload`). Vẫn trả **child** để
  `app.py` `<mark>` highlight. Nâng `reranker_max_length` server **≥1024** (mặc định 512 cắt mục dài);
  cân nhắc tăng `RERANK_TIMEOUT`.
- **Đo live:** cứu Q5→3, Q28→4, Q30→5, Q52→1, Q55→2; **không hồi quy** Q1–Q10. **→ ~0.80 (44/55).**
- **Rủi ro công thức:** **0** — rerank chỉ CHỌN đoạn đã index, không tạo/viết lại text.
- **Verify:** `python -m eval.run_eval --mode hybrid` → recall@5 tăng (~0.80), recall@10 không tụt;
  `--debug-miss` xác nhận 5 câu trên rerank≤5 và **không câu đang‑đậu nào rớt khỏi top‑5**.

### Phase 2 — Lexicon domain tất định (cầu nối từ vựng)
- **File:** `retrieval/retriever.py` + **mirror** `eval/run_eval.py`.
- **Việc:** dict tĩnh + `expand(query)->str` (vd "điều kiện môi trường" → nối "điều kiện kiểm định nhiệt
  độ độ ẩm áp suất khí quyển"). Trong `retrieve()`: gọi `expand()` **sau** `route(query)`; đưa text MỞ
  RỘNG vào `embed_query` + `bm25_search`. **Rerank vẫn dùng query GỐC** (arXiv 2311.09175: text mở rộng
  làm hại cross‑encoder mạnh). Router cũng dùng query gốc (không pha loãng số/alias). Giữ lexicon nhỏ,
  keyed theo khung mục chung → khái quát cho hàng nghìn file.
- **Tác động:** fix DUY NHẤT cho **Q12 + Q18** (parent‑rerank bỏ lại rank 10). **→ ~0.836 (46/55).**
- **Rủi ro công thức:** **0** — thuần query‑side.
- **Verify:** recall@5 ~0.836, không hồi quy vs Phase 1; `--debug-miss` thấy Q12/Q18 ≤5; xác nhận chỉ
  các câu env‑conditions có text mở rộng khác (blast radius khu trú), không câu nào bị giáng.

### Phase 3 — Sửa bug heading ingest + re‑index (cách DUY NHẤT chạm Q26/Q29)
- **File:** `ingestion/extract_docx.py` (sửa heuristic), `ingestion/spike_a.py` (re‑run),
  `index/embed_store.py` (chạy `--force`, không sửa code).
- **Việc:** sửa heuristic nhận diện heading để **bullet/câu thường KHÔNG bị emit thành `###`/`##`** (chỉ
  reclassify bullet‑paragraph; **KHÔNG** đụng chèn placeholder `⟦Fxxx⟧` hay heading thật). Chạy lại
  `python -m ingestion.spike_a` → xác nhận 5.2.1/5.2.5 mang body; rồi `python -m index.embed_store
  --force` (chunk_id idempotent → chỉ chunk `QTKD_1.071` đổi). Chạy lại `--debug-miss` xác nhận Q26/Q29
  vào dense/bm25/fused đúng `section_path`.
- **Tác động:** +2 câu (Q26, Q29). **→ ~0.87 (48/55) ✅ vượt 0.85** (dư 1 câu).
- **🛡️ GUARDRAIL #1 (rủi ro công thức):** sau re‑extract, **span `$LaTeX$` toàn corpus PHẢI vẫn = 351**
  byte‑for‑byte (per‑file không đổi trừ chỗ thật sự re‑extract) **TRƯỚC** khi re‑index. Lệch count → CHẶN.
- **Verify:** (1) `grep -oE '\$[^$]+\$' build/spike_a/*.md | wc -l` = 351 và 0 dòng `### -` trong
  `QTKD_1.071`. (2) `python -m eval.run_eval --mode hybrid` → recall@5 ~0.87 (≥0.85 PASS), không hồi quy
  46 câu đang đậu; `--debug-miss` thấy Q26/Q29 rerank≤5.

### Phase 4 — HOÃN (sau khi đạt 0.85; track scale/hardening, KHÔNG trên critical path)
- (a) **Qdrant native sparse** (BGE‑M3 lexical_weights / FastEmbed + `Modifier.IDF` + RRF server‑side)
  thay `rank_bm25` in‑memory → fix scale thật (bỏ scroll‑toàn‑corpus + rebuild cold‑start vỡ ở hàng
  nghìn file). recall ~+0–2pp. **Migration breaking:** collection hiện dùng vector **không tên** → phải
  recreate + re‑embed. (b) **Heading breadcrumb** ("5 > 5.2 > 5.2.5" prefix vào child khi embed; KHÔNG
  vào `payload.text`) → bền vững cho mục con sâu ở quy mô. Cả hai buộc re‑embed → tách khỏi sprint recall.

---

## 3. Phương án BỊ LOẠI (đã đo/chiếu — có hại hoặc vô ích)

- **Weighted RRF thiên dense:** BẪY — BM25 xếp đúng mục **CAO HƠN** dense ở chính các câu terminology
  (Q5 bm25=11/dense=24; Q28 bm25=1/dense=13; Q30 bm25=1/dense=23) nhờ `section_path` trong corpus BM25.
- **Multi‑query fan‑out:** qwen2.5:1.5b trả 3 paraphrase gần trùng, GIỮ nguyên cụm sai, thêm 0 từ vựng.
- **Đổi embedding tiếng Việt** (halong / AITeamVN / bi‑encoder): hồi quy VN‑MTEB (bge‑m3 39.84 > tất cả).
- **Đổi reranker** (Qwen3‑Reranker‑0.6B Apache‑2.0 khả thi; jina‑v3 mạnh nhất nhưng CC‑BY‑NC = chặn):
  không sửa cơ chế sai‑đơn‑vị → chỉ thử SAU Phase 1 nếu cần.
- **HyDE/query2doc:** chỉ là fallback cho lớp mục con sâu NẾU Phase 3 trượt (ảo giác số liệu;
  +3–6s/query trên 7b; cross‑encoder mạnh trung hoà phần lớn lợi ích).

---

## 4. Triển vọng, file đụng tới, nợ kỹ thuật

**Triển vọng:** recall@5 **~0.87 (48/55)** sau Phase 1–3 — vượt 0.85 với 1 câu dư. Sàn nếu Phase 3
trượt: ~0.836 (chỉ Phase 1+2, thuần retrieval, 0 re‑index). Tin cậy: **CAO** (Phase 1 đo live) /
**TRUNG‑CAO** (Phase 2–3 đã grep xác nhận từ vựng & bug ingest đơn lẻ).

**File đụng tới:** `eval/run_eval.py` (P0,P1,P2,P3‑verify), `retrieval/retriever.py` (P1,P2),
`ingestion/extract_docx.py` + `ingestion/spike_a.py` + `index/embed_store.py --force` (P3).
`retrieval/bm25_index.py` + `index/chunker.py` chỉ ở **P4 (hoãn)**. **KHÔNG đụng** `TC_DL/` (chỉ đọc).
**Cấu hình ngoài repo:** `reranker_max_length≥1024` nằm ở repo Docker `opencode` (service reranker).

**Nợ kỹ thuật cần nhớ:** `run_eval.run_hybrid()` là **bản COPY tay** của `retrieve()` → mọi sửa P1/P2
phải **mirror cả 2 file cùng commit**, nếu không eval đo sai thứ app làm. `--debug-miss` là cross‑check.

---

## 5. Verification (cổng hồi quy chung)

- [ ] **Sau mỗi phase:** `python -m eval.run_eval --mode hybrid` → recall@5 **strictly tăng** (Phase 4:
      không tụt) so với bước ngay trước; `--debug-miss` xác nhận đúng các câu phase đó nhắm vào top‑5,
      không câu đang‑đậu nào rớt.
- [ ] **Mục tiêu cuối:** recall@5 ≥ 0.85 (PASS ở Phase 3, kỳ vọng ~0.87); recall@10/MRR không hồi quy.
- [ ] **Guardrail công thức (Phase 3):** span `$LaTeX$` corpus = 351; conversion rate trong
      `extraction_report.json` không đổi → mới được re‑index.
- [ ] **Offline:** rút mạng → `app.py` vẫn hỏi‑đáp (mọi service Docker local).
- [ ] **Đối chiếu thủ công:** vài câu công thức (Q24/Q32/Q35/Q36/Q48…) render KaTeX khớp ảnh gốc.
