# Spike C — UI Framework Bake-off: Kết quả và Tài liệu Tích hợp

> Ngày thực hiện: 2026-06-06  
> Môi trường: MacBook Pro M3 Pro, 18GB RAM, macOS 14.x (mac dev — KHÔNG phải prod)  
> Prod target: Windows + RTX 5060 8GB GDDR7

---

## 1. Kết quả nhanh (TL;DR)

| Hạng mục | Kết quả |
|---|---|
| Ollama | **INSTALLED** — v0.24.0, đang chạy trên port 11434 |
| Model kéo được | **qwen2.5:1.5b** (940MB) — test dev; prod target: qwen2.5:7b-instruct-q4_K_M |
| Model embedding | **nomic-embed-text** (274MB) — 768 dims, hoạt động |
| kotaemon | **RUNNING** — http://localhost:7860, HTTP 200 OK |
| kotaemon ingest .md | **NATIVE SUPPORT** — `.md` được map sang `TxtReader()` trong `KH_DEFAULT_FILE_EXTRACTORS` |
| LaTeX rendering | **PARTIAL** — Gradio 4.39.0 `gr.Chatbot` dùng KaTeX, nhưng mặc định CHỈ render `$$...$$` (block), KHÔNG render `$...$` (inline) — cần patch |
| NexusRAG | **CLONED** — 316 stars, kiến trúc phức tạp hơn (React + FastAPI + Docker), không test chạy |

**Verdict:** kotaemon là lựa chọn phù hợp cho dự án này. Cần 1 patch nhỏ để bật inline `$...$` rendering.

---

## 2. Ollama — Cài đặt và Cấu hình

### 2.1 Kiểm tra / Cài đặt

```bash
# Kiểm tra
which ollama   # /usr/local/bin/ollama (đã có sẵn)
ollama --version  # 0.24.0

# Nếu chưa có, cài qua Homebrew:
brew install ollama

# Khởi động service
ollama serve   # hoặc mở app Ollama.app trên macOS
```

Trên macOS, Ollama.app chạy ngầm và bind port 11434. Khi dùng script `ollama serve` sẽ gặp "address already in use" nếu app đang chạy — bình thường, không ảnh hưởng.

### 2.2 Pull Model

```bash
# Model nhỏ nhất để test UI flow (dev mac, không cần GPU):
ollama pull qwen2.5:1.5b           # 940MB — đủ test Vietnamese QA

# Model target cho prod (RTX 5060 8GB):
ollama pull qwen2.5:7b-instruct-q4_K_M  # ~5GB — cần ~4.7GB VRAM

# Embedding (cả dev lẫn prod):
ollama pull nomic-embed-text        # 274MB, 768 dims

# Kiểm tra
ollama list
```

### 2.3 Test nhanh

```bash
# Test Vietnamese
ollama run qwen2.5:1.5b "Xin chào, bạn có thể trả lời tiếng Việt không?" --nowordwrap

# Test OpenAI-compat API (cách kotaemon gọi)
curl http://localhost:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen2.5:1.5b","messages":[{"role":"user","content":"Xin chào!"}],"max_tokens":50}'

# Test embedding API
curl http://localhost:11434/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{"model":"nomic-embed-text","input":"Kiểm định van an toàn"}'
# → trả về vector 768 chiều
```

**Kết quả test:** qwen2.5:1.5b trả lời tiếng Việt chính xác. API OpenAI-compat hoạt động đúng.

---

## 3. kotaemon — Clone và Setup

### 3.1 Clone

```bash
cd /Users/mac/Desktop/AI4TA
git clone https://github.com/Cinnamon/kotaemon.git
cd kotaemon
```

**Repo stats:** ~25k stars, Apache-2.0, Python + Gradio.

### 3.2 Yêu cầu hệ thống

- **Python 3.10+** (kotaemon yêu cầu chính xác)
- Trên M3 Pro không có Python 3.10 sẵn → cài qua `uv`:
  ```bash
  uv python install 3.10  # tải cpython-3.10.20-macos-aarch64-none, ~5s
  ```
- Docker: tùy chọn (không dùng trong spike này)

### 3.3 Cài dependencies

```bash
cd /Users/mac/Desktop/AI4TA/kotaemon
uv sync --python 3.10
# Tạo .venv với Python 3.10, cài toàn bộ deps (~5-10 phút lần đầu)
```

Deps quan trọng được cài: `gradio==4.39.0`, `chromadb`, `lancedb`, `llama-index`, `unstructured`, `tiktoken`, v.v.

### 3.4 Tạo file .env

Tạo `/Users/mac/Desktop/AI4TA/kotaemon/.env` (từ `.env.example`):

```bash
# Bắt buộc: Local Ollama LLM
LOCAL_MODEL=qwen2.5:1.5b           # dev; prod: qwen2.5:7b-instruct-q4_K_M
LOCAL_MODEL_EMBEDDINGS=nomic-embed-text

# Ollama URL (mặc định)
KH_OLLAMA_URL=http://localhost:11434/v1/

# Nếu KHÔNG dùng OpenAI (để trống hoặc dummy key)
OPENAI_API_KEY=sk-dummy-key-not-used
```

**Lưu ý:** File `.env` chỉ được đọc lần đầu khởi động (để populate DB). Sau lần đầu, cấu hình model được lưu trong SQLite và quản lý qua UI tab "Resources".

### 3.5 Khởi động

```bash
cd /Users/mac/Desktop/AI4TA/kotaemon
source .venv/bin/activate   # hoặc dùng uv run
python app.py
```

Hoặc không cần activate:
```bash
.venv/bin/python app.py
```

- App khởi động trong ~5-10 giây
- Truy cập: http://localhost:7860/
- Login mặc định: `admin` / `admin`

---

## 4. Cấu hình Ollama trong kotaemon

### 4.1 Cơ chế hoạt động

kotaemon đọc biến `LOCAL_MODEL` từ `.env` và tự động cấu hình 2 LLM trong `flowsettings.py`:

```python
# flowsettings.py (tự động từ .env)
KH_LLMS["ollama"] = {
    "spec": {
        "__type__": "kotaemon.llms.ChatOpenAI",
        "base_url": "http://localhost:11434/v1/",   # KH_OLLAMA_URL
        "model": "qwen2.5:1.5b",                     # LOCAL_MODEL
        "api_key": "ollama",
    }
}
KH_LLMS["ollama-long-context"] = {
    "spec": {
        "__type__": "kotaemon.llms.LCOllamaChat",
        "base_url": "http://localhost:11434/",
        "model": "qwen2.5:1.5b",
        "num_ctx": 8192,
    }
}
```

### 4.2 Cấu hình qua UI

Sau khi login:
1. Tab **Resources** → **LLMs and Embeddings**
2. Chọn model `ollama` hoặc `ollama-long-context` làm default
3. Tab **Resources** → **Embedding Models** → chọn `ollama` embedding (nomic-embed-text)

---

## 5. Ingest File Markdown từ Pipeline Tùy chỉnh

### 5.1 Hỗ trợ .md trong kotaemon

kotaemon hỗ trợ `.md` **natively** qua `TxtReader`:

```python
# libs/kotaemon/kotaemon/indices/ingests/files.py
KH_DEFAULT_FILE_EXTRACTORS: dict[str, BaseReader] = {
    ".txt": TxtReader(),
    ".md": TxtReader(),     # <-- có sẵn
    ".pdf": PDFThumbnailReader(),
    ".docx": unstructured,
    # ...
}
```

`TxtReader` đọc file UTF-8 nguyên văn và trả về 1 `Document` object. Toàn bộ nội dung (kể cả bảng Markdown và `$LaTeX$` inline) được giữ nguyên.

### 5.2 Cách nạp file Markdown từ pipeline ingest của ta

**Phương án 1 (đơn giản nhất): Upload qua UI**

1. Vào tab **Chat** → click icon upload / `+`
2. Chọn file `.md` từ `build/spike_a/` (VD: `QTKD_1.061_2021_ND_V2.md`)
3. kotaemon tự động: đọc → chunk (1024 tokens, overlap 20) → embed (nomic-embed-text) → lưu vào ChromaDB
4. Chat với tài liệu

**Phương án 2: Batch ingest qua Files tab**

1. Tab **Files** → Index Management → New Index
2. Upload nhiều `.md` cùng lúc

**Phương án 3 (tích hợp pipeline — RECOMMENDED cho prod)**

Từ script Python ingest của ta, sau khi xuất ra Markdown sạch, gọi trực tiếp API của kotaemon:

```python
# Sử dụng kotaemon như library
from kotaemon.indices.ingests.files import DocumentIngestor
from kotaemon.embeddings import OpenAIEmbeddings  # hoặc Ollama

ingestor = DocumentIngestor(
    override_file_extractors={".md": TxtReader()}
)
docs = ingestor("path/to/QTKD_1.061_2021_ND_V2.md")
```

Hoặc đơn giản hơn: **symlink hoặc copy** các file `.md` vào thư mục mà kotaemon theo dõi (nếu bật Directory Watch).

### 5.3 Test ingest thực tế

File test: `build/spike_a/QTKD_1.061_2021_ND_V2.md` (392 dòng, QTKĐ 1.061:2021 về van an toàn).

Chưa thực hiện được test ingest hoàn chỉnh trong Spike C do cần cấu hình model mặc định qua UI (yêu cầu tương tác browser). Test sẽ hoàn thành trong Task 3.

---

## 6. Vấn đề LaTeX Rendering — QUAN TRỌNG

### 6.1 Phát hiện

Gradio 4.39.0 `gr.Chatbot` dùng **KaTeX** để render math, nhưng cấu hình mặc định:

```python
# Mặc định của Gradio (nếu không truyền latex_delimiters):
latex_delimiters = [{"left": "$$", "right": "$$", "display": True}]
# CHỈ render block math $$...$$, KHÔNG render inline $...$
```

Trong kotaemon, `ChatPanel` tạo `gr.Chatbot` **không truyền `latex_delimiters`**:

```python
# libs/ktem/ktem/pages/chat/chat_panel.py
self.chatbot = gr.Chatbot(
    label=self._app.app_name,
    # latex_delimiters không được set!
    ...
)
```

### 6.2 Hệ quả

Pipeline ingest của ta xuất công thức dạng `$...$` (inline). Khi LLM trích dẫn nguyên văn công thức trong câu trả lời, chúng sẽ hiển thị dưới dạng **text thuần** (VD: `$F = ma$`) thay vì công thức đẹp.

### 6.3 Fix (1 dòng)

```python
# libs/ktem/ktem/pages/chat/chat_panel.py — sửa dòng 27-35
self.chatbot = gr.Chatbot(
    label=self._app.app_name,
    placeholder=PLACEHOLDER_TEXT,
    show_label=False,
    elem_id="main-chat-bot",
    show_copy_button=True,
    likeable=True,
    bubble_full_width=False,
    latex_delimiters=[
        {"left": "$$", "right": "$$", "display": True},   # block math
        {"left": "$", "right": "$", "display": False},     # inline math — THÊM DÒNG NÀY
    ],
)
```

Đây là fix **bắt buộc** trước khi deploy.

---

## 7. Đánh giá RAM / CPU khi chạy

### 7.1 Mac M3 Pro 18GB (dev)

| Thành phần | RAM sử dụng |
|---|---|
| Ollama service (idle, model chưa load) | ~33MB |
| Ollama + qwen2.5:1.5b loaded | ~1.08GB (RSS); model nằm trong unified memory |
| nomic-embed-text | ~300MB khi active |
| kotaemon (Python/Gradio, idle) | ~105MB |
| Tổng hệ thống khi chạy spike | ~17GB used / 18GB (máy đang dùng nhiều app khác) |

### 7.2 Ước tính cho prod (RTX 5060 8GB GDDR7)

| Thành phần | VRAM | RAM CPU |
|---|---|---|
| qwen2.5:7b-instruct-q4_K_M | ~4.7GB | - |
| nomic-embed-text (via TEI hoặc Ollama, chạy CPU) | 0 VRAM | ~2.3GB RAM |
| bge-reranker-v2-m3 (CPU) | 0 VRAM | ~2.3GB RAM |
| kotaemon + ChromaDB overhead | ~0.2GB VRAM | ~500MB RAM |
| **Tổng VRAM** | **~4.9GB** | |
| **Tổng RAM** | | **~5.5GB** |

→ VRAM còn ~3GB buffer cho context window. Phù hợp với RTX 5060 8GB.

---

## 8. So sánh kotaemon vs NexusRAG

| Tiêu chí | kotaemon | NexusRAG |
|---|---|---|
| **Stars GitHub** | ~25k | ~316 |
| **License** | Apache-2.0 | MIT |
| **UI Framework** | Gradio (Python) | React 19 + FastAPI |
| **Deployment** | `python app.py` — đơn giản | Docker Compose (multi-container) |
| **Ollama support** | Có, native (OpenAI-compat) | Có |
| **Ingest .md** | **Có sẵn** (`TxtReader`) | Có (qua Docling/Marker) |
| **Hybrid retrieval** | Có (dense + BM25 + rerank) | Có (vector + KG + rerank) |
| **LaTeX rendering** | Có (KaTeX), cần patch inline | Không rõ (React UI, cần check) |
| **Knowledge Graph** | Tùy chọn (LightRAG/NanoGraphRAG) | Built-in (LightRAG) |
| **Customizability** | Cao (Python, có thể fork) | Trung bình (React frontend phức tạp hơn) |
| **Tài liệu** | Tốt, có User Guide + Dev Guide | Cơ bản (README) |
| **Maturity** | Cao (active, nhiều contrib) | Thấp (1 tác giả, ~316 stars) |
| **Setup complexity** | **Thấp** — 1 lệnh `uv sync` + `python app.py` | **Cao** — Docker Compose, multi-service |
| **Phù hợp dự án QTKĐ** | **Phù hợp tốt** — dễ tích hợp, dễ patch | Phù hợp nhưng overhead lớn hơn |

**Verdict: Chọn kotaemon.**

Lý do:
1. Setup đơn giản nhất (1 lệnh)
2. Native `.md` support — khớp với output pipeline ingest của ta
3. Dễ patch LaTeX inline rendering (1 dòng code)
4. Cộng đồng lớn, tài liệu tốt
5. Gradio đủ mạnh cho use case nội bộ (không cần UX phức tạp như React)
6. Hybrid retrieval (dense + BM25) có sẵn — đúng yêu cầu

NexusRAG có KG built-in nhưng overhead cài đặt cao và community nhỏ — không phù hợp giai đoạn đầu.

---

## 9. Các Vấn đề Gặp phải và Giải quyết

| Vấn đề | Giải pháp |
|---|---|
| Python 3.10 không có sẵn trên M3 | `uv python install 3.10` — tải và cài tự động trong ~5s |
| Ollama "address already in use" khi chạy `ollama serve` | Ollama.app đã chạy rồi — bình thường, không cần làm gì thêm |
| `.env` chỉ đọc lần đầu | Lần đầu: delete `ktem_app_data/` để reset DB nếu cần thay đổi model |
| Inline `$...$` không render | Patch `latex_delimiters` trong `chat_panel.py` (xem §6.3) |

---

## 10. Các Bước Tiếp Theo (Task 3)

1. **Áp dụng LaTeX patch** vào `chat_panel.py` trước khi test QA
2. **Ingest toàn bộ 7 file .md** từ `build/spike_a/` vào kotaemon
3. **Cấu hình embedding model** (nomic-embed-text) qua Resources UI
4. **Test 5 câu hỏi mẫu** về nội dung QTKĐ, kiểm tra citation đúng mục/điều khoản
5. **Prod deployment checklist:**
   - Cài Python 3.10 trên Windows prod
   - `uv sync --python 3.10`
   - Set `LOCAL_MODEL=qwen2.5:7b-instruct-q4_K_M` trong `.env`
   - Verify CUDA 12.8+ cho RTX 5060 Blackwell (Spike D)
   - Chạy `python app.py`, truy cập http://localhost:7860/

---

## Phụ lục: Cấu trúc Key Files kotaemon

```
kotaemon/
├── app.py                          # Entry point
├── flowsettings.py                 # Main config (Ollama URL, model, DB, ...)
├── .env                            # User config (LOCAL_MODEL, API keys)
├── libs/
│   ├── kotaemon/kotaemon/
│   │   ├── loaders/
│   │   │   ├── txt_loader.py       # TxtReader — đọc .txt và .md
│   │   │   └── ...
│   │   └── indices/ingests/
│   │       └── files.py            # KH_DEFAULT_FILE_EXTRACTORS (map ext → reader)
│   └── ktem/ktem/
│       ├── pages/chat/
│       │   └── chat_panel.py       # gr.Chatbot — CẦN PATCH latex_delimiters
│       └── index/file/
│           └── pipelines.py        # IndexDocumentPipeline, chunking logic
└── ktem_app_data/                  # Runtime data (ChromaDB, LanceDB, SQLite)
    └── user_data/
        ├── sql.db                  # User/session management
        ├── vectorstore/            # ChromaDB
        └── docstore/               # LanceDB
```
