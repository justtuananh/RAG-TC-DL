# React UI — Trợ lý Kiểm định

React 18 + TypeScript + Tailwind, **đã nối API thật**. Chat SSE, tài liệu gốc, upload/xử lý, nguồn trích dẫn và luồng đăng ký nháp → phê duyệt → tính toán đều gọi package `api/` (`api/main.py`).

> **Hiện trạng: đã nối backend thật.** Chat streaming (SSE), tài liệu và xác thực đi qua
> `src/services/liveApi.ts` + `src/services/auth.ts` tới package `api/` (`python -m api.main`,
> FastAPI + SSE). `src/services/mockEngine.ts` chỉ còn hằng số UI (TIMING/ZOOM/extColor).
> Bản React cũ nằm ở `../frontend-legacy/`.

Dùng Node 24, phiên bản gợi ý trong `.nvmrc`; npm lock được commit.

```bash
npm ci
npm run dev       # http://localhost:5173; proxy /api sang localhost:8080
npm run typecheck
npm test -- --maxWorkers=2
npm run lint
npm run build
npm run preview
```

Backend chạy ở8080. Khi cần đổi cổng API, đặt `API_PORT` khi khởi động Vite/preview. Không có backend thì UI hiển thị lỗi tải dữ liệu, không thay bằng kết quả mock. Font Be Vietnam Pro/Lora được đóng gói qua `@fontsource`, không tải font ngoài khi chạy.

## Công thức

```
src/
  main.tsx, App.tsx          # điểm vào + khung app (zoom 0.88, định tuyến tab, overlay)
  index.css                  # @fontsource + reset + thanh cuộn
  types.ts                   # kiểu dữ liệu (Message, Source, DocItem, LlmConfig, AppState…)
  store/
    seed.ts                  # dữ liệu mẫu (SAMPLES, FAQS, SOURCES, DOCUMENTS)
    useAppStore.ts           # state + actions — port từ class DCLogic (useReducer kiểu setState)
    persistence.ts           # lưu/khôi phục hội thoại localStorage (bỏ trường luồng số liệu cũ)
  services/
    liveApi.ts               # client backend thật (chat SSE, documents); route ghi dùng bearer token
    auth.ts                  # phiên đăng nhập: token localStorage, giải mã JWT, authFetch, login/logout/me/refresh
    mockEngine.ts            # hằng số UI (TIMING/ZOOM/extColor)
  components/
    layout/                  # Sidebar (điều hướng + lịch sử), TopBar, AccountMenu (đăng nhập/vai trò/đăng xuất)
    chat/                    # ChatTab, ChatColumn, MessageBubble, ProcessSteps, SourcePanel
    docs/                    # DocsTab, DocRow, DocTableRow, DocViewerPanel, DocContentPane, xlsx/
    guide/                   # GuideTab
    modals/                  # DocViewerModal, LlmConfigModal, ConfirmDialog, LoginModal
    common/                  # icons.tsx (SVG path 1:1 từ mockup), Markdown, Toast, DocPage (trang tài liệu serif)
```

## Xác thực & phân quyền (Sprint 1)

Backend package `api/` (`python -m api.main`) đã có `/api/auth/*` và bọc route ghi bằng vai trò technician/admin.
Frontend nối vào đó:

- `src/services/auth.ts` — lưu token JWT ở localStorage (`qtkd.auth.token`), giải mã payload để
  biết vai trò/hạn, `authFetch` gắn `Authorization: Bearer`, và API `login/logout/me/refresh`.
- `src/components/modals/LoginModal.tsx` — form đăng nhập (username + password).
- `src/components/layout/AccountMenu.tsx` — nút tài khoản/đăng xuất trên TopBar.
- Route **đọc/chat** công khai (không cần token). Route **ghi** (upload/process/delete/rename)
  dùng bearer token; chưa đăng nhập thì mở màn hình đăng nhập rồi chạy lại thao tác đang chờ.
- Token hết hạn/401 khi gọi route ghi → xoá token và mở lại màn hình đăng nhập.
- Vai trò `viewer`/`approver` bị chặn tại UI; `technician`/`admin` mới thao tác ghi được.

Test: `npm test` (Vitest) — `src/services/auth.test.ts` phủ lưu/đọc token, hạn token, ma trận quyền,
`authFetch` 401, login/me/refresh/logout.

## Hệ thiết kế (token trong `tailwind.config.ts`)

Backend quyết định quyền tính; disable nút chỉ hỗ trợ trải nghiệm. Sửa định nghĩa thu hồi duyệt. FE kiểm cấu trúc phản hồi để dữ liệu lỗi không làm trắng ứng dụng, giữ bản sửa khi API lỗi và cảnh báo trước những thao tác bỏ bản sửa trong màn hình rà soát. Tên người duyệt hiện tự nhập, chưa phải danh tính được xác thực.

## Cấu trúc và thiết kế

- `src/services/liveApi.ts`, `formulaApi.ts`: HTTP/SSE và hợp đồng dữ liệu.
- `src/store/useAppStore.ts`: trạng thái, hành động, dữ liệu tài liệu/chat.
- `src/components/docs/FormulaReviewPanel.tsx`: editor, phê duyệt và form tính.
- `DocViewerPanel.tsx`: tab nguồn gốc/công thức trong cùng màn hình.
- `src/components/layout/Sidebar.tsx`: điều hướng, thu gọn trên viewport nhỏ.
- `src/theme.ts`, `tailwind.config.ts`: token **Signal Blue**, nền slate/navy, trạng thái có chữ và màu; Be Vietnam Pro cho UI, Lora cho nội dung tài liệu.

Dùng token hiện có cho màu, viền, bo góc, focus, nút và field; không tạo theme riêng cho tính năng công thức. Test thành phần không thay thế kiểm tra trình duyệt/khả năng tiếp cận đầy đủ.

## Docker

| Service | Port (host) | Vai trò |
|---|---|---|
| `frontend` | **3000** → 80 | nginx serve bản build này; proxy `/api` sang `api` |
| `api` | 8080 | `python -m api.main` (package `api/`, FastAPI + SSE) - **backend RAG thật** |

Dev: `vite.config.ts` proxy `/api` → `http://localhost:8080` (chạy `python -m api.main` trên host nếu
muốn thử kèm backend).

## Nối backend thật

UI gọi backend thật qua `src/services/liveApi.ts` (`streamChat` SSE, `fetchExamples`, `pingHealth`,
tài liệu, xác thực) tới package `api/` (`python -m api.main`).
`mockEngine.ts` chỉ giữ hằng số UI (TIMING/ZOOM/extColor).
Bản cũ tham khảo ở `../frontend-legacy/src/utils/api.js` (`streamChat`).
