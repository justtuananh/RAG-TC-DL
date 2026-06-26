# frontend — Trợ lý Kiểm định (React + TypeScript + Tailwind)

Giao diện web của hệ thống RAG tra cứu QTKĐ. Đây là bản **dựng lại 1:1** từ mockup thiết kế
`design/kiemdinh.html`, viết bằng **React 18 + TypeScript + Vite + Tailwind CSS**.

> ⚠️ **Hiện trạng: MOCK-ONLY.** Mọi câu trả lời / tiến trình xử lý / tải tài liệu / kiểm tra LLM
> đều được **mô phỏng bằng timer** (xem `src/services/mockEngine.ts`), KHÔNG gọi backend.
> Backend RAG thật là `../api_server.py` (FastAPI + SSE); bản React **đã từng** nối backend nằm ở
> `../frontend-legacy/`. Bước tiếp theo khi cần: nối UI mới này vào `api_server.py` (xem cuối file).

## Chạy

```bash
cd frontend
npm install
npm run dev        # → http://localhost:5173
npm run build      # → dist/  (typecheck riêng: npm run typecheck)
npm run preview     # xem thử bản build
```

Yêu cầu: Node ≥ 18. Không cần internet khi chạy — **font tự host** qua `@fontsource`
(Be Vietnam Pro + Lora) nên app chạy **offline** đúng tinh thần dự án.

## Cấu trúc

```
src/
  main.tsx, App.tsx          # điểm vào + khung app (zoom 0.88, định tuyến tab, overlay)
  index.css                  # @fontsource + reset + thanh cuộn
  types.ts                   # kiểu dữ liệu (Message, Source, DocItem, LlmConfig, AppState…)
  store/
    seed.ts                  # dữ liệu mẫu (SAMPLES, FAQS, SOURCES, CONVERSATIONS, DOCUMENTS)
    useAppStore.ts           # state + actions — port từ class DCLogic (useReducer kiểu setState)
  services/
    mockEngine.ts            # responder() định tuyến từ khoá + mốc thời gian timer (RANH GIỚI để thay backend)
  components/
    Header.tsx               # logo + 3 tab + nút trạng thái LLM
    chat/                    # ChatTab, HistorySidebar, HistoryRail, ChatColumn, MessageBubble, ProcessSteps, SourcePanel
    docs/                    # DocsTab, DocRow
    guide/                   # GuideTab
    modals/                  # DocViewerModal, LlmConfigModal, ConfirmDialog
    common/                  # icons.tsx (SVG path 1:1 từ mockup), Toast, DocPage (trang tài liệu serif)
```

## Hệ thiết kế (token trong `tailwind.config.ts`)

- Màu nhấn xanh `#16A34A` (hover `#15803D`), nền app `#ECF1EE`, panel trắng, slate cho chữ/viền;
  highlight nguồn hổ phách `#FEF6DD`/`#F59E0B`.
- Font: **Be Vietnam Pro** cho UI, **Lora** (serif) cho "trang tài liệu" — để trông như trang in.
- Toàn app `zoom: 0.88` (cảm giác đặc, gọn) — khớp mockup.
- Quy ước style: **inline `style` cho nội dung tĩnh** (giá trị px chính xác), **Tailwind class cho
  phần tương tác** (để `hover:`/`focus:` hoạt động). Giá trị px lẻ dùng arbitrary value `[13.5px]`.

## Tính năng (mọi tương tác hoạt động, mô phỏng bằng timer)

3 tab **Trò chuyện / Tài liệu / Hướng dẫn**; thanh Lịch sử thu/phóng (tìm, ghim, đổi tên inline,
xoá có xác nhận); chat ghim câu hỏi lên đầu + thẻ tiến trình 4 bước → câu trả lời kèm trích dẫn
`[n]` bấm được (nhảy + tô sáng đúng đoạn ở cột nguồn), thanh thao tác, gợi ý câu hỏi; cột nguồn kéo
giãn được; tab Tài liệu (kéo-thả tải lên → "Xử lý" → tiến trình, tìm, 5/10/100, phân trang); modal
Cấu hình LLM (tương thích OpenAI), Trình xem tài liệu; toast góc trên-phải.

## Triển khai (Docker)

`Dockerfile` (multi-stage: `npm run build` → nginx serve `dist/`) + `nginx.conf` (SPA fallback +
proxy `/api` → `http://api:8080`). Trong `../docker-compose.yml`:

| Service | Port (host) | Vai trò |
|---|---|---|
| `frontend` | **3000** → 80 | nginx serve bản build này; proxy `/api` sang `api` |
| `api` | 8080 | `api_server.py` (FastAPI + SSE) — **backend RAG thật** |

Dev: `vite.config.ts` proxy `/api` → `http://localhost:8080` (chạy `api_server.py` trên host nếu
muốn thử kèm backend).

## Nối backend thật (bước sau)

UI mới hiện đọc dữ liệu từ `mockEngine.ts`. Để dùng RAG thật, thay phần đó bằng gọi
`api_server.py` (endpoint `GET /api/examples`, `POST /api/chat/stream` SSE) — tham khảo cách bản cũ
làm tại `../frontend-legacy/src/utils/api.js` (`streamChat`). Ranh giới đã tách sẵn ở
`services/mockEngine.ts` + actions trong `store/useAppStore.ts` nên không phải sửa component UI.
