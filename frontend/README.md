# React UI — Trợ lý Kiểm định

React 18 + TypeScript + Tailwind, **đã nối API thật**. Chat SSE, tài liệu gốc, upload/xử lý, nguồn trích dẫn và luồng đăng ký nháp → phê duyệt → tính toán đều gọi `api_server.py`.

## Chạy và kiểm tra

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

Mở **Tài liệu → chọn DOCX → Công thức và phê duyệt**:

- Tạo/lấy nháp; xem công thức nguồn, ngữ cảnh, hash và lịch sử.
- Sửa biểu thức, biến/đơn vị/miền, điều kiện và ca đối chứng.
- Lưu rồi duyệt hoặc từ chối với tên người rà soát và nhận xét.
- Công thức đã duyệt mới có form nhập số liệu và xác nhận điều kiện để tính.

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

Dockerfile dùng Node để `npm ci`, typecheck và build; nginx phục vụ `dist/` ở cổng3000 của host và proxy `/api/` sang `api:8080`. SSE không buffering; giới hạn upload50MB. Chỉ cần build lại `api frontend` khi cập nhật luồng phê duyệt, không cần tải lại model.

[API và vòng đời phê duyệt](../docs/FORMULA_DRAFT_APPROVAL.md) · [Kiểm tra bias](../build/formula-review/BIAS_AUDIT.md)
