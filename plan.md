# Kế hoạch thiết kế lại giao diện: theme xanh quân đội + tab Dữ liệu

Ngày lập: 2026-10-08.
Phạm vi: chỉ `frontend/` (React + Vite + Tailwind).
Không sửa backend, API, kiểu dữ liệu trả về hay hành vi nghiệp vụ.

Thứ tự làm: Pha 1 (theme) xong và đạt cổng kiểm tra rồi mới sang Pha 2 (tab Dữ liệu).

## 0. Hiện trạng (đo ngày 2026-10-08, màn 1440 px)

- Theme hiện tại là "Signal Blue": token ở `frontend/src/theme.ts` (`COLOR`, `RADIUS`, `SHADOW`), bản sao token cho Tailwind ở `frontend/tailwind.config.ts`.
- Nhiều màu xanh vẫn viết cứng ngoài `theme.ts`: `src/index.css` (29 chỗ), `DocsTab.tsx`, `KnowledgeTab.tsx`, `DocRow.tsx`, `DocActionsMenu.tsx`, `MessageBubble.tsx`, `Sidebar.tsx` (bóng `rgba(36,84,224,.3)`), `LoginModal.tsx`, `LlmConfigModal.tsx`, `DocTableRow.tsx`, `TopBar.tsx`, `AccountMenu.tsx`, `SourcePanel.tsx`, `ConfirmDialog.tsx`, `DocViewerModal.tsx`, `GuideTab.tsx`, `ChatColumn.tsx`, `ProvenanceDrawer.tsx`, `CatalogSourceModal.tsx`, `Toast.tsx`, `Markdown.tsx`, `HighlightedMarkdown.tsx`, `DocPage.tsx`, `DocViewerPanel.tsx`, `DocContentPane.tsx`.
- Lớp Tailwind dùng token: `bg-brand`, `text-brand`, `border-brand` (khoảng 50 chỗ), `bg-primary`, `border-line`, `bg-line`.
- Tab Dữ liệu (`src/components/data/`):
  - Bảng hồ sơ có 13 cột, phải cuộn ngang; cột quan trọng nhất "Kết luận" nằm ngoài màn hình.
  - Panel chi tiết bên phải luôn chiếm 430 px kể cả khi chưa chọn hồ sơ, chỉ hiện một dòng chữ.
  - Mọi ô số (ngày, phạm vi đo, cấp chính xác, nhiệt độ, độ ẩm, số điểm đo) là chip nền xanh có icon liên kết, nên cả bảng thành một mảng xanh, mắt không biết nhìn vào đâu.
  - Cột "Loại thiết bị", "Đại lượng", "QTKĐ" lặp y hệt nhau ở mọi dòng, chiếm gần nửa chiều ngang.
  - Hàng bộ lọc nằm lẫn trong `<thead>`, các ô lọc chật, ô ngày hiện "mm/dd/yyyy".
  - Không có sọc dòng, khó dò theo hàng ngang; dòng "Không đạt" không nổi bật.
  - Chọn loại dữ liệu (hồ sơ / chuẩn mẫu / kiểm định viên / danh mục / lĩnh vực) bị giấu trong một `<select>`.

## 1. Pha 1: Theme "Xanh quân đội"

### 1.1 Ý tưởng

Lấy cảm hứng từ quân phục Quân đội nhân dân Việt Nam: xanh ô liu đậm làm màu chủ đạo, nền trung tính hơi ấm (không lạnh như slate), điểm nhấn vàng sao và đỏ cờ dùng rất tiết kiệm.
Cảm giác cần đạt: nghiêm, chắc, kỷ luật, dễ đọc lâu; không loè loẹt, không họa tiết rằn ri.
Vẫn một theme sáng duy nhất như hiện nay, không thêm chế độ tối.

### 1.2 Bảng màu (đã kiểm tương phản WCAG 2.1)

Thay toàn bộ giá trị trong `COLOR` của `src/theme.ts` (giữ nguyên tên khoá để không phải sửa nơi dùng):

| Khoá | Giá trị mới | Ghi chú |
|---|---|---|
| `bg` | `#F4F5EF` | nền app, trắng ngà hơi xanh |
| `surface` | `#FFFFFF` | |
| `surfaceAlt` | `#F0F2E9` | đầu bảng, sọc dòng |
| `surfaceMuted` | `#E6E9DC` | |
| `border` | `#DADFCC` | |
| `borderStrong` | `#BEC6AC` | |
| `textPrimary` | `#1A1F14` | 16.8:1 trên trắng |
| `textSecondary` | `#4C5442` | 7.9:1 trên trắng |
| `textMuted` | `#767E6C` | 4.2:1 trên trắng (chỉ nhãn phụ) |
| `textOnDark` | `#FFFFFF` | |
| `sidebarBg` | `#1E2814` | ô liu rất đậm |
| `sidebarBgAlt` | `#2A3720` | |
| `sidebarBorder` | `rgba(255,255,255,.08)` | giữ |
| `sidebarText` | `rgba(255,255,255,.66)` | |
| `sidebarTextMuted` | `rgba(255,255,255,.52)` | |
| `sidebarHover` | `rgba(255,255,255,.07)` | giữ |
| `accent` | `#4B5E27` | xanh quân đội; chữ trắng trên nền này 7.2:1 |
| `accentDark` | `#34431A` | 10.7:1 trên trắng |
| `accentSoft` | `#EDF1E1` | |
| `accentSoftBorder` | `#CFD9B5` | |
| `accentOnDark` | `#C3D69A` | 9.8:1 trên `sidebarBg` |
| `dangerOnDark` | `#FF8A8A` | giữ |
| `success` | `#1C7A47` | lục ngả lam để không lẫn với accent ô liu; chữ trắng 5.35:1 |
| `successBg` | `#E6F4EC` | |
| `successBorder` | `#B9E0C9` | |
| `warning` | `#A6510A` | chữ trắng 5.5:1 |
| `warningBg` | `#FFF8E6` | |
| `warningBorder` | `#F5D58A` | |
| `danger` | `#C8102E` | đỏ cờ; chữ trắng 5.9:1 |
| `dangerBg` | `#FDF0F1` | |
| `dangerBorder` | `#F5C2C9` | |
| `neutral` | `#6B7262` | |
| `neutralBg` | `#F1F2EC` | |
| `neutralBorder` | `#DDE0D3` | |
| `highlight` | `#FFF3C4` | giữ (đánh dấu đoạn trích) |
| `highlightBorder` | `#E5C04A` | |
| `highlightStrong` | `#E5B700` | vàng sao |

Thêm hai khoá mới:

- `star: "#E5B700"` (vàng sao) dùng cho vạch chỉ báo mục đang chọn ở sidebar và icon logo.
- `flagRed: "#DA251D"` (đỏ cờ) chỉ dùng trang trí (một vạch mảnh dưới logo); không dùng cho chữ.

`SHADOW` đổi màu bóng sang `rgba(26,31,20,…)` thay cho `rgba(16,24,40,…)`.
Cập nhật chú thích đầu file `theme.ts` mô tả theme mới (tiếng Việt).

### 1.3 Áp theme ra toàn app

1. `tailwind.config.ts`: đổi mọi màu trong `theme.extend.colors` khớp bảng trên (`primary` = `brand` = accent, `brand-dark` = accentDark, `sidebar` = sidebarBg, `row-hover` = accentSoft, `app`/`background` = bg, `line`/`outline-variant` = border, `surface-container-*` theo dải `surfaceAlt` → `surfaceMuted` → `border` → `accentSoftBorder`).
   Sửa chú thích "Signal Blue".
2. `src/index.css`: thay các mã màu viết cứng bằng biến CSS khai báo một lần ở `:root` (`--c-accent`, `--c-text`, `--c-border`, …) với giá trị đúng bảng trên; thanh cuộn, `.md-answer`, bảng Markdown, KaTeX, `mark` đều dùng biến.
3. Mọi file `.tsx` trong danh sách ở mục 0: thay mã màu viết cứng bằng `COLOR.*`.
   Nếu thiếu khoá phù hợp thì thêm khoá vào `COLOR`, không viết cứng mã mới.
4. Sidebar (`layout/Sidebar.tsx`):
   - Nền `sidebarBg`, mục đang chọn nền `accent` kèm vạch dọc 3 px màu `star` ở mép trái.
   - Logo: ô vuông nền gradient `accent` → `accentDark`, icon màu `star`; dưới tên app một vạch mảnh 2 px màu `flagRed` dài 24 px.
   - Nút "Hội thoại mới": nền `accent`, bóng `rgba(75,94,39,.35)`.
5. TopBar, AccountMenu, modal, toast, chip trích dẫn `[n]` trong câu trả lời, panel nguồn: dùng accent mới.
6. KHÔNG đổi: `src/components/docs/xlsx/colors.ts`, `xlsx/cellStyle.ts`, `xlsx/sheetModel.ts`, phần màu lấy từ file Excel gốc trong `XlsxSheetTable.tsx` (đó là màu của tài liệu nguồn, không phải màu giao diện); màu loại tệp trong `services/mockEngine.ts` (PDF đỏ, DOCX xanh dương, XLSX lục là quy ước nhận diện định dạng).
7. `index.html`: thêm `<meta name="theme-color" content="#1E2814">`.

### 1.4 Kiểm thử Pha 1

- `src/components/data/accessibility.test.ts`: thêm các cặp sidebar (`accentOnDark` / `sidebarBg`, `textOnDark` / `sidebarBg`, `textOnDark` / `accent`) và cặp `textSecondary` / `bg`; tất cả ≥ 4.5:1.
- Thêm test `src/theme.test.ts` khẳng định không còn mã xanh cũ: đọc mọi file `src/**/*.{ts,tsx,css}` (trừ thư mục `xlsx/`, `mockEngine.ts`, file test) và không được chứa các chuỗi `#2454E0`, `#173CAE`, `#E9EFFF`, `#C9D8FF`, `#0F1B36`, `#16264A`, `#8FA8FF`, `36,84,224` (không phân biệt hoa thường).
- Cổng: `cd frontend && npm run typecheck && npm run lint && npm run test && npm run build` đều xanh.
- Chụp màn hình 1440×900 cả 5 tab (Trò chuyện, Tài liệu, Tri thức, Dữ liệu, Hướng dẫn) và mở một modal; không còn chỗ nào xanh dương cũ, không có chữ mờ khó đọc.

## 2. Pha 2: Thiết kế lại tab Dữ liệu

Nguyên tắc: người dùng mở tab để dò nhanh "thiết bị nào, kiểm khi nào, còn hạn không, đạt hay không".
Bốn câu đó phải đọc được ngay trên một màn 1366 px mà không cuộn ngang.
Mọi số vẫn bấm được để mở nguồn (P1); chỉ đổi cách trình bày, không bỏ khả năng truy xuất.

### 2.1 Thanh đầu tab (`DataTab.tsx`)

- Thay `<select>` loại dữ liệu bằng thanh tab ngang: "Hồ sơ kiểm định", "Chuẩn mẫu (84)", "Kiểm định viên (8)", "Danh mục tiêu chuẩn, quy trình (70)", "Lĩnh vực công nhận (39)" (số đếm lấy từ `catalogCounts` như hiện nay).
  Dùng `role="tablist"` / `role="tab"` / `aria-selected`, điều hướng bằng phím mũi tên trái/phải.
  Tab đang chọn: chữ `accentDark`, gạch chân 2 px `accent`.
- Bên phải giữ "Xoá lọc" và "Xuất Excel" (chỉ hiện khi đang ở "Hồ sơ kiểm định").
- Huy hiệu "20 hồ sơ đã duyệt" chuyển xuống thanh lọc (mục 2.2).

### 2.2 Thanh lọc (tách khỏi `<thead>`)

Thành phần mới `src/components/data/RecordFilterBar.tsx`, đặt ngay trên bảng, nền `surface`, viền dưới `border`.

- Hàng 1:
  - Ô tìm kiếm rộng (≥ 280 px) có icon kính lúp, placeholder "Tìm số hiệu, model, QTKĐ…", giữ `aria-label="Lọc theo số hiệu, model, QTKĐ"`.
  - Nhóm chip chọn một cho kết luận: "Tất cả" cộng các mục của `options.verdicts`, gắn vào `filters.verdict`.
  - Khoảng ngày kiểm định: hai ô ngày có nhãn "Từ" / "Đến".
  - Nút "Bộ lọc khác" mở/đóng hàng 2, có số đếm bộ lọc đang bật trong hàng 2.
- Hàng 2 (thu gọn mặc định, tự mở nếu có bộ lọc của hàng 2 đang bật): loại thiết bị, đại lượng, QTKĐ, phạm vi đo (min, max, đơn vị), cấp chính xác.
- Dưới hai hàng: dải chip các bộ lọc đang bật, mỗi chip có nút "×" gỡ riêng (aria-label "Bỏ lọc …"), cuối dải là chữ "20 hồ sơ đã duyệt" (tabular-nums).
- Giữ nguyên mọi `aria-label` của các ô lọc hiện có (test dựa vào chúng).
- Xoá hàng lọc trong `<thead>` của `RecordsTable.tsx`.

### 2.3 Bảng hồ sơ (`RecordsTable.tsx`)

Cột mới (8 cột, trái sang phải):

| Cột | Nội dung | Ghi chú |
|---|---|---|
| Số hiệu | số hiệu đậm (nút mở lịch sử thiết bị như cũ), dòng phụ nhỏ màu `textMuted`: model nếu có | sort `serial_no` |
| Thiết bị | loại thiết bị; dòng phụ: đại lượng · tag "QTKĐ 1.159" (chip `neutralBg`) | sort `device_type_name` |
| Ngày kiểm định | ngày, nút xuất xứ | sort `calibrated_at` |
| Hiệu lực | ngày hết hiệu lực (nút xuất xứ) + nhãn trạng thái nhỏ: "Còn hạn" (`success`), "Sắp hết hạn" khi còn ≤ 60 ngày (`warning`), "Hết hạn" (`danger`) | sort `expires_at`; hàm tính trạng thái đặt ở `format.ts`, ngưỡng là hằng `EXPIRY_WARNING_DAYS = 60`, có unit test |
| Phạm vi đo | phạm vi đo (nút xuất xứ), căn phải | |
| CCX | cấp chính xác (nút xuất xứ), căn phải | |
| Kết luận | badge đặc như cũ (Đạt / Không đạt) | sort `verdict` |
| (không tiêu đề) | icon mũi tên phải, nút "Xem chi tiết hồ sơ …" | |

- Nhiệt độ, độ ẩm, số điểm đo bỏ khỏi bảng; chúng đã có trong `RecordDetailPanel` kèm nút xuất xứ (kiểm lại số điểm đo; nếu panel chưa có thì thêm vào, kèm nút xuất xứ).
- Nút xuất xứ trong ô (`ProvCell`): bỏ nền chip và viền; hiển thị số thường màu `textPrimary`, gạch chân chấm 1 px màu `borderStrong`; icon liên kết chỉ hiện khi hover hoặc focus; hover thì chữ `accentDark` và nền `accentSoft`.
  Giữ nguyên `aria-label="Xem nguồn: …"` và `title`.
- Dòng: cao 44 px, sọc chẵn nền `surfaceAlt`, hover nền `accentSoft`, dòng đang chọn có viền trái 3 px `accent` và nền `accentSoft`.
- Dòng "Không đạt": viền trái 3 px `danger` (khi không được chọn).
- Đầu bảng: dính trên cùng, nền `surfaceAlt`, chữ 12 px đậm `textSecondary`, viền dưới `borderStrong`.
- Ở 1366 px với panel chi tiết đóng, bảng không được cuộn ngang.
  Khi panel mở mà vẫn chật, cột "Thiết bị" rút gọn bằng `text-overflow: ellipsis` kèm `title` đầy đủ, không cuộn ngang.
- Trạng thái rỗng: icon + "Không có hồ sơ khớp bộ lọc" + nút "Xoá lọc".
  Đang tải: 8 dòng skeleton.
  Lỗi: hộp `dangerBg` như cũ.
- Bàn phím: giữ hành vi hiện có; thêm phím mũi tên lên/xuống chuyển dòng chọn khi focus nằm trong bảng.

### 2.4 Panel chi tiết (`RecordDetailPanel.tsx`)

- Chỉ hiện khi đã chọn hồ sơ; chưa chọn thì bảng chiếm hết chiều ngang (bỏ dòng "Chọn một hồ sơ…").
- Rộng 440 px, trượt vào từ phải (translateX 160 ms, tắt khi `prefers-reduced-motion`), nút đóng "×" và phím Esc đóng.
- Phần đầu: số hiệu cỡ 18 px đậm, badge kết luận, dòng phụ loại thiết bị · QTKĐ.
- Nhóm thông tin thành các khối có tiêu đề nhỏ: "Thời hạn" (ngày kiểm định, hiệu lực + trạng thái), "Đặc tính đo" (phạm vi đo, cấp chính xác), "Điều kiện môi trường" (nhiệt độ, độ ẩm), "Điểm đo" (bảng điểm đo hiện có, sọc dòng như bảng chính).
- Nút "Xem lịch sử thiết bị" ở cuối panel, kiểu nút phụ.

### 2.5 Phân trang

- Trái: "Hiển thị 1–20 trong 20 hồ sơ".
- Phải: "Trang trước" / "Trang sau" như cũ, thêm chữ "Trang 1 / 1" ở giữa.

### 2.6 Bảng danh mục (`CatalogsView.tsx`, `CatalogTable.tsx`) và lịch sử thiết bị (`DeviceHistoryView.tsx`)

- Tách style bảng dùng chung (đầu bảng, ô, sọc dòng, hover, nút xuất xứ dạng gạch chân chấm) ra `src/components/data/tableStyles.ts`; `RecordsTable`, `CatalogTable`, `RecordDetailPanel`, `DeviceHistoryView` cùng import, không chép lại.
- Nếu bảng danh mục đã có ô tìm kiếm thì đổi sang kiểu ô tìm mới (có icon, rộng ≥ 280 px).

### 2.7 Kiểm thử Pha 2

- Cập nhật `RecordsTable.test.tsx`, `RecordDetailPanel.test.tsx`, `CatalogTable.test.tsx` theo cấu trúc mới; không xoá assert về `aria-sort`, `aria-label="Xem nguồn:`, caption, nút xuất xứ.
- Test mới:
  - `RecordFilterBar.test.tsx`: chip kết luận gọi `onFilterChange({ verdict })`; chip bộ lọc đang bật có nút gỡ; hàng 2 tự mở khi có bộ lọc của hàng 2.
  - Trạng thái hiệu lực trong `format.ts`: đã hết hạn, còn đúng 60 ngày, còn 61 ngày, ngày rỗng.
  - Thanh tab loại dữ liệu: có `role="tablist"`, đúng `aria-selected`.
- Cổng: `npm run typecheck && npm run lint && npm run test && npm run build` đều xanh.
- E2E trên app thật (Vite :5173 + api :8080), chụp 1440×900 và 1366×768 cho:
  (a) tab Dữ liệu chưa chọn dòng,
  (b) đã chọn một dòng "Không đạt",
  (c) đã bật 2 bộ lọc,
  (d) tab "Chuẩn mẫu",
  (e) trang lịch sử thiết bị,
  (f) ngăn xuất xứ mở từ một ô số.
  Không có cuộn ngang ở (a); cột "Kết luận" thấy được ở cả (a) và (b).

## 3. Không làm

- Không thêm chế độ tối, không thêm thư viện UI hay thư viện icon mới.
- Không đổi API, `services/dataApi.ts`, `types.ts` (trừ khi chỉ thêm kiểu cho UI).
- Không đổi nội dung chữ của câu trả lời, prompt, tên trường dữ liệu.
- Không đổi màu trong phần hiển thị tệp Excel gốc.

## 4. Giao việc

- Thực thi: opencode `deepseek-v4.1-flash` qua `logs/opencode/run_with_resume.sh`, prompt `logs/opencode/ui_army_prompt.md`.
- Claude nghiệm thu độc lập từng pha (đọc diff, chạy cổng, chụp màn hình so với mục 1.4 và 2.7), rồi commit mỗi pha một commit:
  - `feat(frontend): army green theme`
  - `feat(frontend): redesign the data tab for scanning`
