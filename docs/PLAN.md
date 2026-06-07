# Plan: Chatbot RAG tra cứu tài liệu Đo lường (QTKĐ) — chạy offline trên máy RTX 5060 8GB

> Tài liệu này là **kế hoạch nghiên cứu + thiết kế kiến trúc** để bạn kiểm tra trước khi bắt tay code.
> Gồm: (1) Bối cảnh, (2) Phát hiện về dữ liệu, (3) Ràng buộc đã chốt, (4) Kiến trúc đề xuất,
> (5) So sánh GitHub framework, (6) So sánh model (LLM/embedding/OCR), (7) Kế hoạch tìm hiểu chi tiết
> (các spike để bạn kiểm chứng), (8) Các Task theo mẫu chuẩn, (9) Edge cases & rủi ro, (10) Out of scope, (11) Verification.

---

## 1. Context (Bối cảnh)

- **Mục tiêu:** Xây hệ thống chatbot **tra cứu & trích dẫn** nội dung từ kho tài liệu Quy trình Kiểm định (QTKĐ) của Cục Tiêu chuẩn–Đo lường–Chất lượng. Người dùng hỏi bằng tiếng Việt → bot trả lời kèm **trích đoạn chính xác + công thức + dẫn nguồn** (tên file, mục/điều khoản).
- **Tại sao khó:** Tài liệu là tài liệu chuyên ngành đo lường, **dày đặc công thức và ký hiệu**. Sai một ký hiệu = sai nghiệp vụ. Đây là yêu cầu "chính xác tối đa" mà bạn nhấn mạnh.
- **Outcome mong muốn:** Một hệ thống có giao diện web, chạy **hoàn toàn offline** trên 1 máy bàn (RTX 5060 8GB), ingest được kho tài liệu hiện tại và **mở rộng dần lên hàng trăm–nghìn QTKĐ**, trả lời đúng và dẫn nguồn được.

## 2. Phát hiện về dữ liệu (đã kiểm tra trực tiếp 11 file trong `TC_DL/`)

| Phát hiện | Chi tiết | Hệ quả thiết kế |
|---|---|---|
| **Công thức KHÔNG phải text** | Trong `.docx`, công thức được nhúng dưới dạng **OLE object MathType 6.0 / Equation.DSMT4** (`word/embeddings/oleObject*.bin`) **+ ảnh WMF** (`word/media/image*.wmf`). Kiểm tra `m:oMath` (OMML) = **0** → không có công thức dạng text. | **Trích text thông thường sẽ MẤT TOÀN BỘ công thức.** Đây là rủi ro #1, phải giải quyết ở tầng ingest (xem §4 + Spike A). |
| **Cấu trúc mục nhất quán** | Mọi QTKĐ có cùng khung: `1 Phạm vi áp dụng` → `2 Thuật ngữ và định nghĩa` → `3 Các phép kiểm định` → … (có TOC sẵn). | Tận dụng **cây mục có sẵn** cho retrieval phân cấp (parent-document / PageIndex-style) thay vì tự chia chunk mù. |
| **Định dạng hỗn hợp** | `.docx` (zip, hiện đại) + `.doc` & `.xls` (OLE nhị phân cũ). | Cần **chuẩn hóa** legacy `.doc/.xls` (LibreOffice headless) trước khi parse. |
| **Nhiều bảng** | Các biểu (Biểu 1/3/4, danh mục chuẩn, danh sách KĐV) là **bảng**, nhiều ở `.xls`. | Bảng phải giữ cấu trúc (mỗi bảng = 1 đơn vị chunk), không flatten thành text rời. |
| **Tiếng Việt + ký hiệu/đơn vị** | "bar", ký hiệu đo lường, mã thiết bị, số hiệu QTKĐ (vd `1.061:2021`). | **BM25/sparse là bắt buộc** — embedding dense hay làm nhòe ký hiệu/mã/đơn vị chính xác. |

## 3. Ràng buộc đã chốt (từ bạn)

- **Phần cứng (yếu tố quyết định):** Máy bàn Thánh Gióng — i5‑14600KF · 32GB DDR4‑3200 · **NVIDIA RTX 5060 8GB GDDR7** · SSD 512GB · PSU 750W.
  → Trần thực tế cho LLM chạy mượt GPU là **model 7–8B (lượng tử hóa Q4)**. 8GB VRAM rất hẹp.
  → ⚠️ RTX 5060 là kiến trúc **Blackwell (sm_120)** → cần driver/CUDA mới (CUDA 12.8+) và bản Ollama/llama.cpp mới. (Rủi ro setup, xem §9.)
- **Bảo mật:** **Hoàn toàn offline / on‑prem.** Không gọi API cloud (kể cả lúc OCR công thức). Mọi model phải chạy local.
- **Chức năng:** **Tra cứu & trích dẫn** (KHÔNG tự tính toán). → Không cần tầng tính toán/tool‑use. LLM chỉ cần **tổng hợp + trình bày + dẫn nguồn** từ chunk đã chứa công thức dạng LaTeX sẵn → **7–8B là đủ**.
- **Quy mô:** Sẽ mở rộng **hàng trăm–nghìn QTKĐ** → bắt buộc có **vector DB + pipeline ingest tự động, chuẩn hóa**. (PageIndex thuần LLM‑tree không đủ ở quy mô này → dùng làm lớp router tùy chọn, xem §4.)

## 4. Kiến trúc đề xuất

**Nguyên tắc cốt lõi:** Tách bài toán khó (trích công thức chính xác) ra khỏi framework. Ta tự xây **pipeline ingest** xuất ra **Markdown sạch** (công thức `$LaTeX$` inline + bảng có cấu trúc + metadata cây mục) **một lần**, rồi nạp Markdown sạch đó vào framework RAG. Như vậy độ chính xác công thức do *ta* kiểm soát, không phụ thuộc parser của framework (không framework nào xử lý MathType OLE trong Word).

```
  File gốc (.docx/.doc/.xls)
        │
        ▼  [Tầng 0: Chuẩn hóa]  LibreOffice headless: .doc/.xls → .docx/.xlsx
        │
        ▼  [Tầng 1: Cấu trúc]   Docling/python-docx → cây mục (heading) + bảng (Markdown/HTML)
        │
        ▼  [Tầng 2: Công thức - CHÍNH]  unzip → oleObject*.bin (MTEF) → MathML → LaTeX
        │                                (mathtype_to_mathml, MIT) → chèn $...$ đúng vị trí
        │
        ▼  [Tầng 3: Công thức - DỰ PHÒNG]  OLE lỗi → render WMF→PNG → math-OCR local
        │                                  (pix2tex/texify; hoặc Qwen2.5-VL-7B nạp tạm lúc ingest)
        │
        ▼  [Tầng 4: QA gate]    Render LaTeX→ảnh, diff với WMF gốc → cờ "cần review" cho ca lệch
        │
        ▼  Markdown sạch + metadata (file, mục, loại: text/bảng/công thức)
        │
        ▼  [Index]  chia child-chunk nhỏ (mỗi bảng / mỗi công thức + chú giải ký hiệu / mỗi đoạn)
        │           Embedding BGE-M3 (dense+sparse) + (tùy chọn) Contextual blurb mỗi chunk
        │           Lưu vào Vector DB; giữ liên kết child → parent (mục cha)
        │
        ▼  [Query]  Hybrid search (dense + BM25) → rerank (bge-reranker-v2-m3)
        │           → trả PARENT (cả mục/bảng) làm ngữ cảnh, KHÔNG chỉ child
        │
        ▼  [Generate]  Qwen2.5-7B/Qwen3-8B Q4 (Ollama) → trả lời tiếng Việt + dẫn nguồn + công thức verbatim
        │
        ▼  [UI]  Web chat có trích dẫn inline (kotaemon)
```

### 4.1 Kỹ thuật RAG (tổng hợp nghiên cứu, đối chiếu ví dụ PageIndex của bạn)
- **Xương sống: Parent-Document / "small‑to‑big"** trên **cây mục có sẵn** của tài liệu. Index child nhỏ (công thức, bảng, đoạn) để bắt trúng; **trả về mục cha** để LLM có đủ ngữ cảnh và trình bày công thức không sai.
- **Hybrid dense + BM25 + rerank** — *bắt buộc* cho độ chính xác ký hiệu/đơn vị/mã. (Dense một mình sẽ trượt "1.061:2021", "bar", ký hiệu.)
- **Contextual Retrieval** (Anthropic): chèn blurb định vị mỗi chunk lúc ingest (chạy local, 1 lần) để phân biệt các mục **gần như trùng nhau** giữa các QTKĐ (do dùng chung khung mẫu). Phương án rẻ hơn: *late chunking*.
- **PageIndex (tùy chọn, Phase 2):** dùng làm **router lý luận** ở trên cùng cho câu hỏi "quy trình nào / mục nào", rồi mới drill xuống hybrid+rerank để lấy công thức chính xác. Không dùng PageIndex thuần làm tầng duy nhất (granularity ở mức *mục*, không trúng từng công thức; tốn token/độ trễ mỗi query).
- **Bỏ qua:** GraphRAG (thừa, đắt — query của ta là tra cứu trong từng quy trình, không phải tổng hợp đồ thị xuyên kho). RAPTOR chỉ dùng cho câu "tóm tắt cả quy trình", **không bao giờ** lấy summary làm nguồn cho công thức/số.

### 4.2 Stack model cho RTX 5060 8GB (offline)
| Vai trò | Model đề xuất | VRAM/Chạy ở đâu | Ghi chú |
|---|---|---|---|
| **Sinh câu trả lời** | **Qwen2.5‑7B‑Instruct** *hoặc* **Qwen3‑8B**, Q4_K_M | ~4.7–5GB **GPU** (Ollama) | VN + suy luận tốt nhất ở cỡ 7–8B. Đủ cho tra cứu+trích dẫn. Thay thế VN: SEA‑LION‑8B. |
| **Embedding** | **BGE‑M3** (dense+sparse+ColBERT) | ~2.3GB, **CPU** (TEI) | Đa ngữ, hybrid 1 model. Có thể thêm `halong_embedding` (top VN‑MTEB) để tăng tiếng Việt. |
| **Rerank** | **bge‑reranker‑v2‑m3** (hoặc **ViRanker** VN) | ~2.3GB, **CPU** | Cross‑encoder, bắt buộc cho chính xác. |
| **OCR công thức (chỉ lúc ingest)** | **pix2tex/texify** (CPU) → khó thì **Qwen2.5‑VL‑7B** Q4 nạp tạm | GPU lúc ingest (LLM unload) | Ingest là batch offline → chậm cũng chấp nhận. |

> **Phân bổ VRAM lúc query:** LLM 7–8B Q4 (~5GB) trên GPU + KV cache (~2GB) ≈ 7GB; **embedding & rerank chạy CPU** (RAM 32GB dư). Vừa khít 8GB. License sạch: Qwen (community license — kiểm tra điều khoản), BGE‑M3 & reranker (MIT/Apache), pix2tex (MIT).

## 5. So sánh GitHub framework (đã có UI, deploy nhanh)

| Framework | Sao/License | UI | Parser công thức/bảng | Offline + LLM local | Hợp với ta? |
|---|---|---|---|---|---|
| **kotaemon** (Cinnamon) | ~25k · Apache‑2.0 | Gradio, đa người dùng, trích dẫn | Docling (local), hybrid+rerank, GraphRAG tùy chọn | ✅ (bản Docker kèm Ollama) | **#1 — nhẹ, dễ cắm pipeline `.py` riêng của ta**, hợp 8GB/32GB |
| **NexusRAG** (LeDat98) | ~315 · MIT | Chat agentic, trích dẫn inline | Docling/Marker **giữ công thức** + caption ảnh/bảng | ✅ (Ollama / sentence‑transformers) | **#2 — gần như đo ni cho ta, ĐÃ test tiếng Việt+Anh.** Rủi ro: dự án nhỏ, 1 maintainer → dùng làm **bản tham chiếu/fork** |
| **RAGFlow** (infiniflow) | ~82k · Apache‑2.0 | Rất hoàn chỉnh | **MinerU/Docling** cắm được (mạnh nhất nhóm turnkey) | ✅ | #3 — parser tốt nhất nhưng **nặng** (Elasticsearch + nhiều service) → rủi ro trên 32GB RAM khi chạy kèm LLM |
| **Open WebUI** | ~100k · MIT* | Chat đẹp nhất | Cắm Docling/Tika ngoài | ✅ Ollama‑native | #4 — UI tốt nhưng kiểm soát RAG yếu hơn |
| AnythingLLM / Onyx / Dify | MIT / MIT / Apache* | Tốt | **Không** chuyên công thức | ✅ | Loại — parser không đạt độ chính xác công thức |

**Khuyến nghị:** Bắt đầu với **kotaemon** + **pipeline ingest tự xây** (xuất Markdown sạch). Học pattern tiếng Việt + giữ công thức từ **NexusRAG**. Quyết định cuối chốt sau **bake‑off** (Task 1) chạy thử chính tài liệu thật.

## 6. Bảng tổng hợp model (chi tiết để bạn kiểm tra)

**LLM sinh (ưu tiên cho 8GB, tiếng Việt + suy luận):** Qwen2.5‑7B‑Instruct (Apache‑2.0) ≈ Qwen3‑8B > SEA‑LION‑8B (VN tốt) > Vistral‑7B (VN mượt nhưng yếu toán → không nên làm chính). Tránh model VN‑native cũ (PhoGPT/VinaLLaMA) cho nội dung kỹ thuật.
**Embedding VN:** BGE‑M3 (MIT) làm mặc định; bổ sung/đổi `halong_embedding` (top VN‑MTEB). Tránh jina‑v3 (license CC‑BY‑NC).
**Rerank:** bge‑reranker‑v2‑m3 (mặc định) hoặc ViRanker (VN‑tuned).
**Trích công thức từ MathType OLE:** `mathtype_to_mathml` (MIT, MTEF→MathML) → MathML→LaTeX (XSLT/pandoc) — **đường sạch license, tự động hóa được**. Fallback ảnh: pix2tex/texify; khó thì vision‑LLM local (Qwen2.5‑VL).

## 7. Kế hoạch TÌM HIỂU chi tiết (các Spike để BẠN kiểm chứng trước khi build)

> Mục tiêu: **de‑risk** trước khi cam kết. Làm tuần tự; Spike A là sống‑còn.

- **Spike A — Tính khả thi trích công thức (RỦI RO #1).** Trên 11 file: bóc `oleObject*.bin` → MTEF → MathML → LaTeX bằng `mathtype_to_mathml`; với ca lỗi thì render WMF→PNG→pix2tex. **Đo tỉ lệ công thức ra LaTeX đúng** (mắt thường + render‑diff). → *Tiêu chí đạt: ≥90% công thức ra LaTeX trung thực; phần còn lại có cờ review.*
- **Spike B — Legacy `.doc/.xls`.** Cài LibreOffice headless, convert `.doc→.docx` & `.xls→.xlsx`; kiểm tra **font/encoding tiếng Việt** và **cấu trúc bảng** giữ nguyên.
- **Spike C — Bake‑off framework.** Đưa cùng tài liệu sạch vào **kotaemon vs RAGFlow vs NexusRAG**; so độ chính xác parse + UI + mức ngốn RAM/VRAM trên máy thật. Chốt framework.
- **Spike D — Model trên 8GB thật.** Chạy Qwen2.5‑7B Q4 (Ollama) + BGE‑M3 + reranker (CPU) trên đúng máy RTX 5060; **đo VRAM, độ trễ trả lời, tok/s**. Kiểm tra Blackwell/CUDA 12.8+ chạy được.
- **Spike E — Bộ đánh giá chất lượng.** Tự soạn ~30–50 cặp (câu hỏi → mục/công thức nguồn đúng) từ 11 file; đo **recall@k / precision** của hybrid+rerank. Làm thước đo hồi quy cho mọi thay đổi sau này.

## 8. Các Task chuẩn theo mẫu (sau khi Spike đạt)

### Task 1: Spike trích xuất công thức + chuẩn hóa định dạng
**1. Goal:** Pipeline CLI nhận 11 file `TC_DL/`, xuất mỗi file thành 1 `.md` sạch (công thức `$LaTeX$` inline đúng vị trí, bảng dạng Markdown, heading giữ phân cấp) + báo cáo `extraction_report.json` (số công thức, số ca fallback, số cờ review). Đo được: ≥90% công thức trung thực.
**2. Context:** Đây là rủi ro #1 (công thức = OLE/ảnh, không phải text). Phải chứng minh khả thi trước khi xây phần còn lại. Không phụ thuộc task nào.
**3. Scope:**
- Files tạo mới: `ingestion/normalize.py` (LibreOffice convert), `ingestion/extract_formula.py` (MTEF→MathML→LaTeX + fallback OCR), `ingestion/docx_to_markdown.py`, `ingestion/qa_diff.py` (render‑diff gate), `requirements.txt`.
- Files KHÔNG chạm: dữ liệu gốc trong `TC_DL/` (chỉ đọc, không sửa).
**4. Implementation Steps:**
1. LibreOffice headless: `.doc/.xls → .docx/.xlsx`.
2. Unzip `.docx`, đọc `word/document.xml` lấy text+heading+bảng; định vị các điểm có OLE/ảnh công thức.
3. Bóc `word/embeddings/oleObject*.bin`, bỏ 28‑byte OLE header → MTEF → MathML (`mathtype_to_mathml`) → LaTeX.
4. Fallback: OLE lỗi → render `image*.wmf`→PNG → pix2tex/texify → LaTeX.
5. QA gate: render LaTeX→ảnh, so khác biệt với WMF gốc → gắn cờ `needs_review`.
6. Ghép thành Markdown sạch + metadata, xuất `extraction_report.json`.
> NOTE: nếu MTEF parse kém, cân nhắc đường docx→PDF (LibreOffice)→MinerU làm phương án B.
**5. Edge Cases:** OLE rỗng/hỏng → fallback OCR; công thức trong bảng → giữ ô; ký hiệu Unicode hiếm → kiểm bảng font MT Extra/Symbol; `.xls` nhiều sheet → mỗi sheet 1 khối.
**6. Verification:**
- [ ] Chạy pipeline trên 11 file không lỗi, sinh đủ 11 `.md`.
- [ ] Đối chiếu thủ công ≥3 công thức/file: LaTeX khớp ảnh gốc.
- [ ] `extraction_report.json`: tỉ lệ trung thực ≥90%; mọi ca <90% có cờ review.
**7. Out of Scope:** Embedding, retrieval, UI, LLM (các task sau).

### Task 2: Pipeline ingest + index hybrid (parent‑document)
**1. Goal:** Nạp Markdown sạch (Task 1) vào Vector DB: child‑chunk (công thức/bảng/đoạn) với BGE‑M3 dense+sparse, giữ liên kết parent (mục), sẵn sàng hybrid search. Idempotent, có log; ingest lại không nhân đôi.
**2. Context:** Biến tài liệu sạch thành tri thức truy hồi được; nền cho retrieval. Phụ thuộc Task 1. Phải mở rộng được lên hàng nghìn QTKĐ.
**3. Scope:** mới: `index/chunker.py`, `index/embed_store.py` (BGE‑M3 + Vector DB), `index/contextual.py` (blurb tùy chọn). KHÔNG chạm: `ingestion/*` (đầu vào ổn định).
**4. Implementation Steps:** 1) chunk theo cây mục (mỗi bảng/công thức = 1 unit + chú giải ký hiệu); 2) embed BGE‑M3 (CPU/GPU batch); 3) lưu child+parent+metadata (file, mục, loại); 4) (tùy chọn) Contextual blurb; 5) khóa idempotent theo hash file.
**5. Edge Cases:** file cập nhật lại → reindex theo hash; chunk công thức quá ngắn → kèm câu mô tả; bảng lớn → chia theo nhóm hàng giữ header.
**6. Verification:**
- [ ] `count(chunks) > 0`, mỗi child có parent hợp lệ, không orphan.
- [ ] Truy vấn mẫu ("phạm vi van an toàn 1400 bar") trả đúng mục QTKĐ 1.061.
- [ ] Ingest lại 1 file không tăng số chunk.
**7. Out of Scope:** Rerank, LLM, UI.

### Task 3: Truy hồi (hybrid + rerank) + tầng trả lời + UI
**1. Goal:** Người dùng hỏi tiếng Việt trên web → hybrid search + bge‑reranker → Qwen2.5‑7B (Ollama) trả lời + **dẫn nguồn (file, mục) + công thức verbatim**. Chạy offline trên RTX 5060.
**2. Context:** Hoàn thiện vòng tra cứu end‑to‑end. Phụ thuộc Task 2.
**3. Scope:** Triển khai/ cấu hình **kotaemon** (hoặc framework chốt ở Spike C) trỏ vào Vector DB Task 2; cấu hình Ollama + TEI; prompt buộc trích dẫn + không bịa công thức. KHÔNG chạm: logic ingest/index.
**4. Implementation Steps:** 1) dựng Ollama (Qwen2.5‑7B Q4) + TEI (embed/rerank) bằng docker‑compose; 2) nối retriever hybrid→rerank→parent; 3) prompt system tiếng Việt: chỉ trả lời từ ngữ cảnh, luôn dẫn nguồn, giữ nguyên LaTeX; 4) bật trích dẫn inline trên UI.
**5. Edge Cases:** không tìm thấy → trả lời "không có trong tài liệu" (chống bịa); câu hỏi đa quy trình → liệt kê nguồn từng quy trình; công thức trong câu trả lời → render hiển thị.
**6. Verification:**
- [ ] Chạy bộ eval Spike E: recall@5 đạt ngưỡng đã chốt.
- [ ] 10 câu hỏi mẫu: câu trả lời dẫn đúng nguồn + công thức khớp ảnh gốc.
- [ ] Đo trên máy thật: VRAM < 8GB, độ trễ chấp nhận được.
**7. Out of Scope:** Tính toán theo công thức (ngoài phạm vi dự án); PageIndex router (Phase 2).

## 9. Edge Cases & Rủi ro toàn dự án
- **RTX 5060 Blackwell:** cần CUDA 12.8+ / Ollama mới → xác minh sớm (Spike D). Nếu kẹt: chạy LLM qua llama.cpp build mới hoặc tạm dùng GPU khác để ingest.
- **8GB VRAM hẹp:** nếu cần model lớn hơn → offload CPU (chậm) hoặc nâng GPU. Tra cứu+trích dẫn thì 7–8B đủ.
- **MTEF parse không đạt 90%:** chuyển phương án B (docx→PDF→MinerU) cho phần lỗi.
- **Mục gần trùng giữa các QTKĐ:** bật Contextual Retrieval để phân biệt.
- **Bịa công thức (hallucination):** chỉ index LaTeX verbatim; prompt cấm chế; luôn dẫn nguồn để người dùng đối chiếu.

## 10. Out of Scope
- Tự **tính toán** theo công thức (nhập số đo → ra kết quả) — bạn đã chốt chỉ tra cứu.
- Gọi API cloud (offline tuyệt đối).
- GraphRAG; PageIndex thuần làm tầng duy nhất.
- Fine‑tune LLM (dùng model có sẵn).

## 11. Verification (toàn hệ thống)
- [ ] Spike A–E đều đạt tiêu chí trước khi build chính thức.
- [ ] End‑to‑end offline: rút mạng vẫn hỏi‑đáp được.
- [ ] Bộ eval (Spike E) đạt ngưỡng recall/precision đã chốt; là test hồi quy.
- [ ] Đối chiếu công thức trong câu trả lời với ảnh gốc trên mẫu ngẫu nhiên — khớp.
- [ ] Đo tài nguyên trên RTX 5060: VRAM < 8GB, RAM < 32GB, độ trễ chấp nhận được.

---
### Quyết định còn mở (sẽ chốt ở Spike, không chặn việc bắt đầu)
1. **Framework cuối:** kotaemon (khuyến nghị) vs fork NexusRAG vs RAGFlow → chốt sau Bake‑off (Spike C).
2. **Đường trích công thức:** MTEF→MathML→LaTeX (chính) vs docx→PDF→MinerU (dự phòng) → chốt sau Spike A.
3. **Embedding:** BGE‑M3 đơn vs thêm halong_embedding cho tiếng Việt → chốt sau Spike E.
