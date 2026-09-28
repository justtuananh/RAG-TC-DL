# Kế hoạch: trích xuất dữ liệu và tri thức từ toàn bộ TC_DL (QTKĐ, biên bản Excel, hồ sơ NAS)

Ngày: 2026-09-28.
Nhánh: `feature/knowledge-management-sprints-3-9`.
Người thực thi phần dễ/lặp: `opencode-go/deepseek-v4.1-flash`; Claude làm phần khó, review và nghiệm thu E2E.
Phạm vi do người dùng chốt: KHÔNG xử lý `mau_bien_ban/*.docx`; xử lý các tệp trong `TC_DL/` để phục vụ chatbot hỏi đáp và tra cứu tay.

## 1. Hiện trạng TC_DL (đo 2026-09-28)

| Nhóm | Tệp | Hiện trạng |
|---|---|---|
| QTKĐ | 7 `.docx` (1.061, 1.062, 1.063, 1.071, 1.159, 1.160, 1.190) | Đã nhúng Qdrant; tri thức lõi đã trích (124 dữ kiện chờ duyệt, 28 của 1.159 đã duyệt); Phụ lục A mới trích cho 1.159. |
| Biên bản | 20 `.xlsx` áp kế pittông QTKĐ 1.159 | Đã đọc, duyệt, tra cứu được (tab Dữ liệu + chat nhánh số liệu). |
| NAS | `4. Bieu 1 ... .doc` (lĩnh vực KĐ/HC: 46 dòng) | Chưa đọc được (định dạng `.doc` cũ). |
| NAS | `6. Bieu 3 Danh muc chuan mau ... .xls` (chuẩn mẫu: 87 dòng) | Chưa đọc được (`.xls` cũ); đang phân loại `khac`. |
| NAS | `7. Biểu 4 Danh mục QT ... .doc` (tiêu chuẩn/quy trình: 77 dòng) | Chưa đọc được. |
| NAS | `10. Bieu 7 Danh sách KĐV ... .doc` (kiểm định viên: 8 người) | Chưa đọc được. |

Điểm yếu đã đo: bộ chia chunk gộp CẢ một bảng Markdown thành một chunk; bảng 77-87 dòng thành một chunk làm truy hồi một dòng cụ thể (một chuẩn, một quy trình) kém.

## 2. Mục tiêu nghiệm thu

1. Mọi tệp trong `TC_DL/` upload/xử lý được qua UI, không lỗi; bản gốc không bị sửa.
2. Chatbot trả lời có trích dẫn đúng dòng cho câu hỏi về 4 hồ sơ NAS (ví dụ ở mục 5).
3. Tra cứu tay: tab Tài liệu xem được nội dung đã trích của 4 hồ sơ NAS; tab Dữ liệu có danh mục có cấu trúc (chuẩn mẫu, kiểm định viên, danh mục quy trình, lĩnh vực công nhận) tìm kiếm/lọc được, mỗi ô có xuất xứ (P1), chỉ hiện bản đã duyệt (P3).
4. Không lùi: `make check`, gate frontend, `eval.run_eval` (recall@5 ≥ 0,85), `intent_eval --live` và tập giữ kín của Claude ≥ 0,90.

## 3. Các pha

### Pha K1: đọc được `.doc`/`.xls` (DeepSeek)

- Chuyển đổi tự động bằng LibreOffice headless khi xử lý (`.doc` → `.docx`, `.xls` → `.xlsx`) vào thư mục dựng (`build/converted/`), KHÔNG sửa bản gốc trong `TC_DL/`; có timeout, lỗi chuyển đổi hiện rõ trên UI.
- `.doc` đi tiếp đường trích Markdown như `.docx`; bảng tính loại danh mục (không phải biên bản) có bộ trích Markdown riêng (mỗi sheet một mục, bảng thành bảng Markdown, xử lý ô gộp của tiêu đề).
- Upload nhận `.doc`/`.xls`; phân loại: "Biểu n/CN", "danh mục", "danh muc", "danh sách kiểm định viên/KĐV" → `danh_muc`.
- Chốt chặn B10 (tỉ lệ công thức) vẫn áp dụng.

### Pha K2: chia chunk bảng lớn theo nhóm dòng (Claude)

- Bảng dài hơn ngưỡng được chia thành nhiều chunk con, mỗi chunk lặp lại dòng tiêu đề cột và mang theo dòng đề mục nhóm gần nhất (ví dụ "IV | PHƯƠNG TIỆN ĐO ÁP SUẤT") để một dòng đứng riêng vẫn đủ ngữ cảnh.
- Bảng ngắn giữ nguyên hành vi cũ; chạy lại `eval.run_eval` trên corpus QTKĐ để chắc không lùi.

### Pha D1: danh mục có cấu trúc (Claude thiết kế + bộ đọc; DeepSeek làm migration, API, UI)

Bốn thực thể mới, đi đúng hàng đợi duyệt như hồ sơ (mỗi lần đọc một `extraction` `pending`, bản cũ `superseded` khi đọc lại):

| Thực thể | Nguồn | Trường chính |
|---|---|---|
| `lab_standard` (chuẩn mẫu, PTĐ, PTTN) | Biểu 3 | tên, ký hiệu, số hiệu, đặc tính đo lường (nguyên văn + phạm vi/CCX tách được), chu kỳ KĐ/HC (tháng), lần KĐ/HC gần nhất (tháng/năm + nơi), hạn kế tiếp (dẫn xuất, có cờ), lĩnh vực sử dụng |
| `inspector` (kiểm định viên) | Biểu 7 | họ tên, năm sinh, cấp bậc/chức vụ, trình độ, chuyên ngành, các lĩnh vực được chứng nhận (danh sách), số thẻ, ngày cấp |
| `procedure_catalog` (danh mục tiêu chuẩn, quy trình) | Biểu 4 | nhóm lĩnh vực, số hiệu (chuẩn hóa để khớp `procedure.number` nếu có), tên, cấp ban hành, năm |
| `capability` (lĩnh vực KĐ/HC được công nhận) | Biểu 1 | nhóm (IV, V...), tên đại lượng/trang bị, tham số đo lường (từng dải/CCX), quy trình áp dụng (danh sách, liên kết `procedure_catalog`), số KĐV, hình thức công nhận |

Luật đọc chung: "nt"/"Nt" (như trên) lấy giá trị ô cùng cột dòng trên, giữ nguyên văn "nt" trong quote và đánh dấu đã kế thừa; dòng đề mục nhóm (chỉ có số La Mã + tên) là ngữ cảnh, không phải bản ghi; dòng trống bị bỏ; KHÔNG tính lại số (P2), chỉ tách số từ chính ô.

### Pha D2: chat số liệu cho danh mục (DeepSeek, Claude đo tập giữ kín)

- Intent mới: tra chuẩn mẫu (theo tên/ký hiệu/số hiệu/dải đo, hạn hiệu chuẩn), tra kiểm định viên (theo tên/lĩnh vực), tra danh mục quy trình (theo số hiệu/tên thiết bị), tra lĩnh vực công nhận (theo loại thiết bị).
- Cổng: tập vàng + tập giữ kín của Claude ≥ 0,90, không lạc nhánh, 0 số không nguồn.

### Pha E: E2E

Xử lý 4 hồ sơ NAS qua UI, duyệt, chạy bộ câu hỏi mục 5 qua chat, soát UI tab Tài liệu/Dữ liệu.
Trích Phụ lục A cho 6 QTKĐ còn lại (để chờ duyệt) để hệ thống sẵn sàng đọc biên bản của các quy trình đó.

## 4. Chia việc

| Việc | Ai |
|---|---|
| K1 chuyển đổi `.doc`/`.xls`, trích Markdown bảng tính, phân loại | DeepSeek |
| K2 chia chunk bảng lớn + eval truy hồi | Claude |
| D1 thiết kế lược đồ + bộ đọc 4 biểu | Claude |
| D1 migration, view, hàng đợi duyệt, API, UI tab Dữ liệu | DeepSeek (sau khi Claude chốt lược đồ) |
| D2 intent + tập vàng | DeepSeek; Claude đo tập giữ kín |
| E2E, review, nghiệm thu | Claude |

## 5. Câu hỏi nghiệm thu (dự kiến)

1. Chuẩn MΠ-6 số hiệu 5393 có chu kỳ hiệu chuẩn bao lâu, hiệu chuẩn gần nhất khi nào?
2. Phòng có những áp kế píttông chuẩn nào?
3. Chuẩn nào dùng cho lĩnh vực Biểu 1 mục IV.1?
4. Kiểm định viên nào được chứng nhận phương tiện đo nhiệt độ?
5. Số thẻ kiểm định viên của Phạm Văn Hà?
6. QTKĐ 1.019 : 2014 là quy trình gì, cấp nào ban hành?
7. Phòng được công nhận kiểm định áp kế píttông với dải đo và cấp chính xác nào, theo quy trình nào?
8. Có bao nhiêu kiểm định viên thực hiện kiểm định van an toàn?
9. Quy trình kiểm định nhiệt kế thủy tinh chất lỏng là gì?
10. Liệt kê các quy trình thuộc lĩnh vực dung tích, lưu lượng.

## 6. Nhật ký

- 2026-09-28: lập kế hoạch sau khi khảo sát 4 hồ sơ NAS (chuyển đổi thử bằng LibreOffice trong scratchpad).
- 2026-09-28, K1 xong (`bb5c6ff`, `0883cd6`):
  `.doc`/`.xls` được chuyển đổi bằng LibreOffice headless, cache theo sha256 trong `build/converted/`, bản gốc không bị sửa.
  4 hồ sơ NAS xử lý qua API thật đều về trạng thái `ready`; fidelity công thức vẫn 351/351.
- 2026-09-28, K2 xong (`c82727e`, `3bd1a2b`):
  bảng dài hơn 15 dòng được chia nhóm 8 dòng, lặp tiêu đề cột và đề mục nhóm La Mã.
  `eval.run_eval` giữ nguyên recall@5 0,982 và MRR 0,870 trước và sau khi chia.
  Ô bảng Word nhiều đoạn được nối bằng " / " thay vì dính chữ.
- 2026-09-28, D1 xong (`253481f`, `0531331`, `90d7f35`, `9083006`):
  bộ đọc 4 biểu cho 84 chuẩn mẫu, 8 kiểm định viên, 70 tiêu chuẩn/quy trình, 39 lĩnh vực công nhận trên fixture thật.
  Mỗi lần đọc tạo một extraction `catalog:*` chờ duyệt đúng số dòng; sau khi duyệt, tab Dữ liệu tìm kiếm/lọc được, mỗi ô mở được dòng nguyên văn (P1), chỉ hiện bản đã duyệt (P3).
  "nt" kế thừa dòng trên và được đánh dấu; chu kỳ ghi trơn "1" không bị đoán số tháng, người duyệt thấy 12 cảnh báo.
- 2026-09-28, D2 xong (`ae96f50`, `add1991`, `3640630`):
  4 intent danh mục (`lab_standard_lookup`, `inspector_lookup`, `procedure_catalog_lookup`, `capability_lookup`) với bộ gỡ nhầm tất định trong `query/signals.py`.
  RAG văn bản thuần chỉ đúng 2/10 câu danh mục vì qwen2.5:3b đọc bảng dài sai, nên danh mục đi nhánh số liệu có cấu trúc.
  Bảng số liệu rỗng rơi về câu trả lời văn bản thay vì để người dùng không có câu trả lời.
  `3640630` sửa 3 lỗi định tuyến còn lại: liệt kê chuẩn theo loại ("những áp kế píttông chuẩn nào"), ký hiệu chuẩn bị coi là loại thiết bị (Fluke 7302 số 1274), và mục sử dụng Biểu 1 bị đưa vào `standards_for`.
  Đo với qwen2.5:3b thật: `intent_eval` 102/102, tập giữ kín của Claude (ngoài repo) 16/16, cả 10 câu mục 5 đều đúng intent và ra bảng có xuất xứ.
- 2026-09-28, E2E:
  chat thật qua `/api/chat/stream` đạt 12/12 câu (10 câu danh mục, 1 câu lịch sử thiết bị, 1 câu văn bản), trước bản sửa `3640630` là 10/12.
  `make check` 1522 passed; gate frontend (typecheck, lint, 103/103 test, build) xanh ở `9083006` và từ đó không đổi frontend.
  Phụ lục A của 6 QTKĐ còn lại đã trích, 124 + 109 dữ kiện tri thức đang chờ người dùng duyệt ở tab Tri thức.
  Tài khoản test tạm `e2e_claude` đã tắt (`is_active=0`, giữ lại vì là người duyệt trong audit).
- Còn mở, chưa làm:
  câu từ chối tính toán đang dùng chung câu "Không tìm thấy thông tin...", nên có câu riêng "Hệ thống chỉ tra cứu, không tính toán".
  Số thập phân hiển thị dấu chấm thay vì dấu phẩy kiểu Việt trên toàn app.
  Câu không nêu QTKĐ ("Thời gian quay tự do tối thiểu cho phép") đang trích 1.071 thay vì 1.159.
  Bảng 2 (phương tiện chuẩn) của 1.159 chưa duyệt nên `standards_for` trả rỗng, đúng theo P3.
