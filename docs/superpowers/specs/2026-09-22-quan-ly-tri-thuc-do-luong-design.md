# Thiết kế: Hệ thống quản lý tri thức và dữ liệu đo lường Việt Nam

Ngày: 2026-09-22
Trạng thái: chờ duyệt
Phạm vi: nâng RAG-TC-DL từ chatbot tra cứu QTKĐ thành ứng dụng quản lý tri thức + dữ liệu đo lường.

## 1. Mục tiêu

Hôm nay hệ thống chỉ trả về đoạn văn bản.
Đích đến là: người dùng upload một tài liệu bất kỳ trong nghiệp vụ đo lường, hệ thống tự nhận diện loại tài liệu, trích xuất tri thức có cấu trúc và dữ liệu đo, đưa vào một sổ cái quan hệ, rồi cho phép tra cứu, lọc, xem lịch sử theo thiết bị và hỏi đáp trên cả văn bản lẫn số liệu.

Ba năng lực bắt buộc ở phiên bản đầu:

1. Tra cứu và lọc dữ liệu có cấu trúc (theo loại thiết bị, phạm vi đo, cấp chính xác, QTKĐ áp dụng, kết luận đạt hoặc không đạt).
2. Lịch sử theo thiết bị: một trang cho mỗi thiết bị theo số serial, gồm dòng thời gian các lần kiểm định và diễn biến sai số.
3. Chat trả lời được cả câu hỏi văn bản lẫn câu hỏi số liệu.

## 2. Quyết định đã chốt

| Quyết định | Lựa chọn | Hệ quả |
|---|---|---|
| Loại dữ liệu quản lý | Dữ liệu tham chiếu trong QTKĐ + hồ sơ kiểm định thực tế + dữ liệu đo thô | Cần ba luồng nạp khác nhau trên cùng một sổ cái |
| Vai trò hệ thống | Kho tri thức và tra cứu, đọc là chính | Không làm màn hình nhập liệu kiểm định, không xuất biên bản |
| Định dạng hồ sơ | Word và Excel theo mẫu cố định | Đọc bằng luật, không cần OCR, không cần LLM cho hồ sơ |
| Độ tin cậy dữ liệu trích xuất | Bắt buộc người duyệt trước khi dùng | Cần bảng trạng thái duyệt, hàng đợi duyệt, UI duyệt, nhật ký |
| Quy mô người dùng | Nhiều người, có đăng nhập và vai trò | Cần Postgres, xác thực, phân quyền, audit log |
| Kiến trúc lưu trữ | Postgres làm sổ cái, Qdrant giữ văn bản | Thêm một service, thêm migration |

Ngoài phạm vi phiên bản này: màn hình cảnh báo hạn kiểm định, danh mục tài sản phòng đo (các Biểu 1, 3, 4, 7), nhập liệu kiểm định trực tiếp, xuất biên bản, OCR bản scan.
Lưu ý: hạn hiệu lực vẫn được tính và lưu ở mục 5.5 vì nó thuộc dữ liệu của hồ sơ, chỉ có màn hình cảnh báo và thông báo là để lại cho phiên bản sau.

## 3. Nguyên tắc bất biến

Ba nguyên tắc dưới đây ràng buộc mọi thiết kế chi tiết về sau.
Vi phạm một trong ba là lỗi chặn merge.

**P1. Mọi giá trị có cấu trúc phải truy ngược được về nguyên văn.**
Không có dòng dữ liệu nào tồn tại mà không kèm định danh tài liệu, đường dẫn mục, định danh chunk và đoạn trích nguyên văn đã sinh ra nó.
Đây là phiên bản mở rộng của nguyên tắc độ trung thực công thức đang có: người dùng tin con số vì đối chiếu được với nguồn, không phải vì hệ thống nói vậy.

**P2. Không bao giờ tính lại số liệu của nguồn.**
Sai số, độ chênh áp, giá trị đo trong hồ sơ được đọc nguyên trạng từ tài liệu.
Hệ thống không tự tính chúng, kể cả khi có đủ công thức.
Ngoại lệ duy nhất là dữ liệu lịch trình dẫn xuất (ví dụ hạn hiệu lực bằng ngày kiểm định cộng chu kỳ), và loại này phải được gắn nhãn là giá trị dẫn xuất kèm dữ kiện nguồn đã dùng.

**P3. Chỉ dữ liệu đã duyệt mới lộ ra bề mặt sử dụng.**
Bảng tra cứu, trang thiết bị, chat số liệu, báo cáo chỉ đọc từ các khung nhìn đã lọc trạng thái duyệt.
Ràng buộc này đặt ở tầng cơ sở dữ liệu bằng view, không phải ở tầng ứng dụng.

## 4. Kiến trúc đích

```
                   upload (docx / pdf / xlsx)
                            │
                   ┌────────▼────────┐
                   │ nhận diện loại  │  qtkd | ho_so | phieu_do | khac
                   └────────┬────────┘
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
      ingestion/        readers/       readers/
      (đang có)         record         sheet
      docx,pdf → md     docx mẫu       xlsx mẫu
              │             │             │
    ┌─────────┴───┐         └──────┬──────┘
    ▼             ▼                ▼
index/ chunker  knowledge/      records →
  → Qdrant      extract         device / calibration_record
  (văn bản)     (luật + LLM)    / measurement_point
                     │
                     ▼
               extraction (chờ duyệt)
                     │  người duyệt
                     ▼
              ┌──────────────┐
              │  PostgreSQL  │  sổ cái: tri thức + dữ liệu + người dùng + nhật ký
              └──────┬───────┘
                     │
      ┌──────────────┼──────────────┬───────────────┐
      ▼              ▼              ▼               ▼
  bảng tra cứu   trang thiết bị  hàng đợi duyệt   chat lai
                 và lịch sử                       văn bản + số liệu
```

Qdrant giữ nguyên vai trò và nguyên pipeline hybrid hiện tại.
Thay đổi duy nhất ở Qdrant là payload có thêm `document_id` để liên kết ngược về Postgres.
Không đụng vào `retrieval/retriever.py`, `bm25_index.py`, `chunker.py` ở phần logic tìm kiếm.

Module mới:

| Thư mục | Trách nhiệm |
|---|---|
| `db/` | Kết nối, session, migration Alembic, các model SQLAlchemy |
| `auth/` | Xác thực, vai trò, nhật ký thao tác |
| `knowledge/` | Trích xuất tri thức từ QTKĐ: bộ luật theo mục, bộ trích xuất LLM, bộ chuẩn hóa đơn vị |
| `records/` | Đọc hồ sơ kiểm định và phiếu đo theo mẫu, đối sánh thiết bị |
| `query/` | Danh mục truy vấn có tham số phục vụ chat số liệu và bảng tra cứu |

## 5. Mô hình dữ liệu

### 5.1 Khung khái niệm đo lường

Bốn bảng nền, được seed sẵn, người dùng không nhập.

`quantity` là đại lượng đo: áp suất, nhiệt độ, khối lượng, độ dài, độ ẩm, thời gian.
Cột: `id`, `code`, `name_vi`, `si_unit_code`.

`unit` là đơn vị đo kèm hệ số quy đổi tuyến tính về đơn vị SI theo công thức `si = factor * x + offset`.
Cột: `id`, `code`, `name_vi`, `quantity_id`, `factor_to_si`, `offset_to_si`, `aliases`.
Offset tồn tại để xử lý độ C sang K.
Seed tối thiểu cho áp suất: `Pa`, `kPa`, `MPa`, `bar`, `mbar`, `psi`, `kgf/cm2`, `at`, `mmHg`, `mmH2O`.

`device_type` là loại phương tiện đo: van an toàn, bàn tạo áp, bình phân ly, áp kế píttông tiêu chuẩn, thiết bị đo áp suất số.
Cột: `id`, `name_vi`, `aliases`, `quantity_id`.
Bảng này thay thế hằng số `_DEVICE_ALIASES` đang hardcode trong `retrieval/router.py`.
Router sẽ đọc alias từ DB, nhờ đó thêm một QTKĐ mới không phải sửa code.

`procedure` là một QTKĐ.
Cột: `id`, `document_id`, `number` ví dụ `1.061`, `year`, `title`, `device_type_id`, `edition`.

### 5.2 Tài liệu

`document` thay thế hoàn toàn `build/spike_a/doc_meta.json` và việc quét thư mục trong `ingestion_jobs.list_documents()`.
Cột: `id`, `file_stem`, `display_name`, `ext`, `doc_type`, `sha256`, `size_bytes`, `uploaded_by`, `uploaded_at`, `ingest_status`, `ingest_error`.
`doc_type` nhận một trong: `qtkd`, `ho_so_kiem_dinh`, `phieu_do`, `danh_muc`, `khac`.
`sha256` chặn upload trùng và cho phép phát hiện tài liệu bị thay nội dung.

### 5.3 Tầng trích xuất và duyệt

`extraction` là nơi duy nhất giữ xuất xứ và trạng thái duyệt.
Mọi bảng dữ kiện đều tham chiếu tới nó, nhờ đó hàng đợi duyệt, nhật ký và ràng buộc P3 chỉ phải cài đặt một lần.

Cột: `id`, `document_id`, `section_path`, `chunk_id`, `quote`, `char_start`, `char_end`, `extractor`, `extractor_version`, `confidence`, `status`, `reviewed_by`, `reviewed_at`, `review_note`, `supersedes_id`, `created_at`.
`extractor` ghi rõ nguồn gốc: `rule:phamvi.v1`, `rule:bang2.v1`, `llm:qwen2.5:7b`.
`status` nhận: `pending`, `approved`, `rejected`, `superseded`.

Khi một tài liệu được nạp lại, các extraction cũ của tài liệu đó chuyển sang `superseded` chứ không bị xóa.
Lịch sử duyệt là dữ liệu nghiệp vụ, không phải rác.

### 5.4 Tri thức trích xuất từ QTKĐ

`procedure_fact` giữ các dữ kiện vô hướng hoặc dạng khoảng.
Cột: `id`, `extraction_id`, `procedure_id`, `fact_kind`, `label`, `rel_op`, `value_min`, `value_max`, `unit_id`, `value_text`, `condition_text`.

`fact_kind` nhận: `working_range`, `accuracy_class`, `max_permissible_error`, `calibration_interval`, `env_condition`, `inspection_step`, `formula`.

Hai cột `value_min` và `value_max` được chuẩn hóa về đơn vị SI ngay lúc ghi, đồng thời `value_text` giữ nguyên chuỗi gốc.
Chuẩn hóa để lọc được, giữ nguyên văn để hiển thị đúng như tài liệu.
Đây là chỗ dễ sai nhất trong toàn bộ thiết kế và có gate riêng ở Sprint 3.

`condition_text` giữ phần điều kiện mà con số không diễn tả hết.
Ví dụ với câu "bằng ± 3% áp suất chỉnh đặt nhưng không nhỏ hơn ± 0,15 bar", hệ thống sinh hai dòng fact liên kết cùng một extraction, và `condition_text` ghi rõ ràng buộc sàn.

`procedure_standard` giữ Bảng 2 Phương tiện kiểm định, vốn có dạng bảng nhiều dòng.
Cột: `id`, `extraction_id`, `procedure_id`, `ord`, `name_vi`, `range_text`, `accuracy_text`, `note`.
Giữ dạng text vì Bảng 2 thường mô tả bằng quan hệ chứ không bằng số, ví dụ "lớn hơn áp suất chỉnh đặt của van đồng thời nhỏ hơn 1,5 lần áp suất chỉnh đặt".
Ép các câu này thành số là nguồn sai lệch, không phải tính năng.

`term` giữ mục §2 Thuật ngữ và định nghĩa.
Cột: `id`, `extraction_id`, `procedure_id`, `term_vi`, `term_en`, `definition`.
Bảng này có giá trị riêng: nó là từ điển đo lường tra cứu được, và về sau dùng để mở rộng truy vấn trong BM25.

### 5.5 Thiết bị, hồ sơ và số liệu đo

`device` là một phương tiện đo vật lý.
Cột: `id`, `device_type_id`, `serial_no`, `model_code`, `manufacturer`, `owner_org`, `attrs`, `created_at`.
Khóa nhận dạng là cặp `device_type_id` và `serial_no`.
Khi hồ sơ không có serial, hệ thống tạo thiết bị tạm gắn cờ `needs_identification` thay vì gộp nhầm hai thiết bị khác nhau.

`calibration_record` là một lần kiểm định.
Cột: `id`, `document_id`, `extraction_id`, `device_id`, `procedure_id`, `mode`, `calibrated_at`, `expires_at`, `expires_from_fact_id`, `verdict`, `cert_no`, `inspector_name`, `reviewer_name`, `lab_name`, `env_temp_c`, `env_humidity_pct`, `created_at`.
`mode` nhận: `ban_dau`, `dinh_ky`, `sau_sua_chua`.
`verdict` nhận: `dat`, `khong_dat`.
`expires_at` là giá trị dẫn xuất theo ngoại lệ của P2, và `expires_from_fact_id` trỏ tới dữ kiện chu kỳ đã dùng để tính.

`measurement_point` là một dòng số liệu đo.
Cột: `id`, `record_id`, `ord`, `step_code`, `label`, `nominal_value`, `measured_value`, `error_value`, `unit_id`, `limit_value`, `within_limit`, `note`.
`step_code` ánh xạ về mục của QTKĐ, ví dụ `6.3.1`, nhờ đó số liệu nối được với công thức và giới hạn tương ứng.
`error_value` luôn đọc từ tài liệu theo P2.
`within_limit` là cờ đối chiếu, chỉ được điền khi cả `error_value` lẫn `limit_value` đều có nguồn, và luôn hiển thị kèm cả hai để người dùng tự kiểm.

### 5.6 Người dùng và nhật ký

`app_user`: `id`, `username`, `full_name`, `password_hash`, `role`, `is_active`, `created_at`.
Vai trò: `viewer` chỉ xem, `technician` upload và chạy trích xuất, `approver` duyệt dữ kiện, `admin` quản trị người dùng và khung khái niệm.

`audit_log`: `id`, `actor_id`, `action`, `entity_type`, `entity_id`, `before`, `after`, `at`.
Ghi bắt buộc cho: upload, xóa tài liệu, duyệt, từ chối, sửa giá trị đã duyệt, đổi vai trò.

### 5.7 Khung nhìn thực thi P3

```sql
CREATE VIEW v_procedure_fact AS
  SELECT f.* FROM procedure_fact f
  JOIN extraction e ON e.id = f.extraction_id
  WHERE e.status = 'approved';
```

Tương tự cho `v_procedure_standard`, `v_term`, `v_calibration_record`.
Mọi truy vấn của tầng `query/` chỉ được đọc từ các view này.
Có một test bảo vệ quét mã nguồn `query/` và fail nếu bắt gặp tên bảng gốc.

## 6. Chuẩn hóa số và đơn vị

Đây là rủi ro kỹ thuật lớn nhất của phần dữ liệu, ngang với rủi ro công thức của phần ingestion.

Tài liệu đo lường Việt Nam viết số theo quy ước riêng:
dấu phẩy là dấu thập phân (`0,15`), dấu cách là dấu phân nhóm hàng nghìn (`1 400`), khoảng được viết bằng `÷` trong ngoặc (`(0 ÷ 100) %RH`), và đơn vị có thể dính hoặc tách khỏi số.
Ký tự phân nhóm đôi khi là khoảng trắng hẹp không ngắt chứ không phải khoảng trắng thường.

Module `knowledge/vnnum.py` chịu trách nhiệm duy nhất cho việc này:
chuyển chuỗi Việt sang số thực, nhận diện khoảng, nhận diện sai số dạng `±`, tách đơn vị.
Nó không phụ thuộc DB, thuần hàm, và có bộ test bảng liệt kê mọi biến thể gặp trong corpus.

Module `knowledge/units.py` quy đổi về SI dựa trên bảng `unit`.
Quy tắc: quy đổi chỉ chạy khi đơn vị được nhận diện chắc chắn.
Đơn vị lạ thì `value_min` và `value_max` để trống, `value_text` vẫn giữ nguyên, và extraction bị hạ điểm tin cậy để người duyệt chú ý.
Thà thiếu dữ liệu lọc còn hơn lọc ra kết quả sai đơn vị.

## 7. Chiến lược trích xuất theo mục QTKĐ

Cấu trúc ĐLVN ổn định cho phép trích xuất bằng luật ở hầu hết các mục.
LLM chỉ dùng ở đúng chỗ luật không với tới.

| Mục | Dữ kiện lấy ra | Cách làm | Độ tin cậy kỳ vọng |
|---|---|---|---|
| §1 Phạm vi áp dụng | `device_type`, `working_range` | Luật: mẫu "đến X đv", "(A ÷ B) đv", "từ A đến B" | Cao |
| §2 Thuật ngữ | `term` | Luật: mẫu "Tên (english): là ..." | Cao |
| §3 Bảng 1 | `inspection_step` kèm chế độ kiểm định | Đọc bảng Markdown, header hai tầng | Cao |
| §4 Bảng 2 | `procedure_standard` | Đọc bảng Markdown, header hai tầng | Cao |
| §5.1 Điều kiện | `env_condition` | Luật: "Nhiệt độ: (A ÷ B) °C", "Độ ẩm: ..." | Cao |
| §6 Tiến hành | `max_permissible_error`, `formula` | LLM có schema, kèm bắt buộc trích nguyên văn | Trung bình |
| §7 Xử lý chung | `calibration_interval` | Luật: "Chu kỳ kiểm định ... là N tháng" | Cao |
| Phụ lục A | Sơ đồ trường của biên bản | Luật, dùng để sinh cấu hình đọc hồ sơ | Cao |

Điểm thiết kế đáng chú ý ở dòng cuối: Phụ lục A của mỗi QTKĐ chính là mẫu biên bản kiểm định tương ứng.
Thay vì hardcode một bộ đọc cho mỗi mẫu, hệ thống sinh cấu hình ánh xạ trường từ chính Phụ lục A đã trích xuất, rồi người duyệt xác nhận cấu hình đó một lần cho mỗi QTKĐ.
Thêm một QTKĐ mới kéo theo khả năng đọc hồ sơ của nó mà không phải viết thêm mã.

Ràng buộc với bộ trích xuất LLM ở §6:
đầu ra là JSON theo schema pydantic, mọi trường số bắt buộc đi kèm trường `quote` chứa nguyên văn chứa con số đó, và hệ thống từ chối dòng nào có `quote` không tìm thấy trong văn bản mục.
Đây là hàng rào chống bịa số, độc lập với việc người duyệt có đọc kỹ hay không.

## 8. Chat lai văn bản và số liệu

Thêm `query/intents.py` định nghĩa một danh mục truy vấn có tham số.
LLM chỉ làm đúng một việc: chọn intent và điền tham số dưới dạng JSON, được pydantic kiểm tra.
Không có text-to-SQL tự do.
Toàn bộ SQL do người viết, mỗi intent một câu.

Danh mục khởi đầu:

| Intent | Tham số | Trả về |
|---|---|---|
| `device_history` | serial | Dòng thời gian các lần kiểm định của một thiết bị |
| `latest_record` | serial | Lần kiểm định gần nhất kèm kết luận |
| `records_by_period` | từ ngày, đến ngày, kết luận | Danh sách hồ sơ |
| `procedure_params` | số QTKĐ hoặc loại thiết bị | Bộ thông số tham chiếu đã duyệt |
| `devices_by_range` | đại lượng, min, max | Thiết bị có phạm vi đo nằm trong khoảng |
| `standards_for` | số QTKĐ | Bảng 2 phương tiện kiểm định |
| `error_trend` | serial, mã mục | Diễn biến sai số qua các lần kiểm |

Tầng định tuyến `query/router.py` phân câu hỏi thành ba nhánh.
Nhánh `text` đi đúng pipeline RAG hiện tại, không đổi gì.
Nhánh `data` gọi intent rồi trả về bảng kèm liên kết tới hồ sơ gốc.
Nhánh `mixed` chạy cả hai và ghép: phần quy định lấy từ QTKĐ, phần số liệu lấy từ sổ cái, mỗi phần giữ trích dẫn riêng.

Khi không chắc chắn, mặc định rơi về nhánh `text`.
Trả lời thiếu số liệu nhưng đúng nguồn tốt hơn trả lời số liệu sai nhánh.

## 9. Lộ trình sprint

Mười sprint, mỗi sprint hai tuần, mỗi sprint kết thúc bằng một cổng kiểm chứng chạy được.
Không sprint nào để lại nhánh dở dang: mỗi sprint merge được vào `main` và hệ thống vẫn chạy.

### Sprint 0 - Nền cơ sở dữ liệu

Mục tiêu: có Postgres chạy cạnh stack hiện tại mà không ảnh hưởng gì tới chat đang hoạt động.

Việc:
- Thêm service `postgres` vào `docker-compose.yml` kèm volume bền vững và healthcheck.
- Tạo `db/` với engine, session factory, cấu hình qua biến môi trường.
- Đưa Alembic vào, tạo migration khởi tạo rỗng.
- Thêm script backup và restore vào `scripts/`.
- Bổ sung `make db-upgrade`, `make db-backup` vào Makefile.

Cổng: `make check` xanh, `docker compose up` lên đủ service, migration chạy đi và lùi được, khôi phục từ bản backup ra đúng dữ liệu.
Rủi ro: chiếm cổng trùng. Chốt cổng 5432 nội bộ, không publish ra host ở chế độ Docker.

### Sprint 1 - Danh tính và phân quyền

Mục tiêu: hệ thống biết ai đang thao tác.

Việc:
- Bảng `app_user`, `audit_log` và migration.
- `auth/` với băm mật khẩu, đăng nhập cấp token, phụ thuộc FastAPI kiểm vai trò.
- Bọc các route ghi hiện có (`upload`, `process`, `delete`, `rename`) bằng kiểm quyền.
- Ghi `audit_log` cho mọi thao tác ghi.
- Màn hình đăng nhập ở frontend, lưu token, tự chuyển hướng khi hết hạn.
- Lệnh tạo tài khoản quản trị đầu tiên.

Cổng: test đơn cho băm mật khẩu và ma trận quyền, test tích hợp xác nhận route ghi trả 401 khi không token và 403 khi sai vai trò, nhật ký ghi đúng chủ thể.
Rủi ro: khóa chính mình ra khỏi hệ thống đang dùng. Giảm bằng biến môi trường cho phép tắt xác thực ở môi trường dev, mặc định bật ở Docker.

### Sprint 2 - Sổ tài liệu chuyển về cơ sở dữ liệu

Mục tiêu: `document` thành nguồn sự thật thay cho việc quét thư mục.

Việc:
- Bảng `document` và migration.
- Script chuyển đổi: quét `TC_DL/` và `build/spike_a/`, dựng bản ghi cho toàn bộ tài liệu đang có, tính `sha256`.
- Viết lại `ingestion_jobs.list_documents` và các hàm liên quan để đọc ghi qua DB, giữ nguyên hình dạng JSON mà frontend đang dùng.
- Bộ nhận diện loại tài liệu `ingestion/classify.py`: dựa vào tên tệp, sự hiện diện của các tiêu đề đặc trưng và bảng, trả về `doc_type` kèm điểm tin cậy; người dùng sửa được nhãn.
- Thêm `document_id` vào payload Qdrant, chạy lại index.
- Bỏ `build/spike_a/doc_meta.json`.

Cổng: test đơn cho bộ nhận diện trên corpus hiện có, tab Tài liệu ở frontend hiển thị y hệt trước và sau khi chuyển đổi, xóa tài liệu dọn sạch cả DB lẫn Qdrant.
Rủi ro: chuyển đổi làm hỏng kho đang chạy. Giảm bằng chạy thử trên bản sao, script có chế độ khô, và chỉ xóa `doc_meta.json` sau khi đối chiếu khớp.

### Sprint 3 - Khung khái niệm và chuẩn hóa đơn vị

Mục tiêu: có nền ngữ nghĩa để dữ kiện bám vào, và số liệu quy đổi được.

Việc:
- Bảng `quantity`, `unit`, `device_type`, `procedure` và migration.
- Dữ liệu seed cho đại lượng và đơn vị đo lường Việt Nam, trước hết đầy đủ nhóm áp suất, nhiệt độ, độ ẩm, độ dài.
- `knowledge/vnnum.py`: phân tích số kiểu Việt, khoảng, sai số `±`, tách đơn vị.
- `knowledge/units.py`: quy đổi về SI, từ chối rõ ràng khi đơn vị lạ.
- Chuyển `_DEVICE_ALIASES` của `retrieval/router.py` sang đọc từ `device_type`, có bộ nhớ đệm.
- Sinh bản ghi `procedure` cho các QTKĐ đang có.

Cổng: bộ test bảng cho `vnnum` phủ mọi biến thể số gặp trong corpus, gồm khoảng trắng hẹp không ngắt; test quy đổi hai chiều cho từng đơn vị áp suất; eval truy hồi hiện tại không tụt sau khi router đổi nguồn alias.
Rủi ro: đây là nơi sai lặng lẽ nhất. Giảm bằng quy tắc thà bỏ trống còn hơn đoán, và bằng test đối xứng quy đổi.

### Sprint 4 - Trích xuất bằng luật

Mục tiêu: rút được phần lớn tri thức QTKĐ mà không cần LLM.

Việc:
- Bảng `extraction`, `procedure_fact`, `procedure_standard`, `term`, các view đã duyệt, và migration.
- `knowledge/rules/` với một mô đun cho mỗi mục: `phamvi.py` (§1), `thuatngu.py` (§2), `bang1.py` (§3), `bang2.py` (§4), `dieukien.py` (§5.1), `chuky.py` (§7).
- Bộ đọc bảng Markdown xử lý được header hai tầng như Bảng 1 và Bảng 2.
- Nối vào `ingestion_jobs`: sau bước nhúng, chạy trích xuất cho tài liệu loại `qtkd`, ghi ra trạng thái `pending`.
- `eval/extract_eval.py` và tập vàng gán tay cho toàn bộ QTKĐ hiện có.

Cổng: độ chính xác từ 0,95 trở lên và độ phủ từ 0,80 trở lên trên tập vàng, tính riêng từng loại dữ kiện.
Độ chính xác được ưu tiên hơn độ phủ vì có người duyệt ở sau: thiếu thì bổ sung tay, sai thì làm hỏng niềm tin.
Rủi ro: một QTKĐ lệch chuẩn ĐLVN làm luật vỡ. Giảm bằng việc mỗi luật trả về rỗng thay vì đoán khi không khớp mẫu, và ghi lại mục không trích được để rà.

### Sprint 5 - Trích xuất bằng LLM cho mục 6

Mục tiêu: lấy được giới hạn sai số nằm trong văn xuôi.

Việc:
- `knowledge/llm_extract.py`: nhắc theo schema, chạy trên Ollama nội bộ, mỗi lần một mục.
- Schema pydantic buộc mọi trường số đi kèm `quote`.
- Bộ xác minh: từ chối dòng có `quote` không khớp nguyên văn trong mục, chuẩn hóa dấu cách trước khi so.
- Chấm điểm tin cậy dựa trên: khớp nguyên văn, đơn vị nhận diện được, giá trị nằm trong khoảng hợp lý so với phạm vi đo của chính QTKĐ đó.
- Mở rộng tập vàng sang các dữ kiện của §6.

Cổng: không có dòng nào lọt qua với `quote` không khớp nguồn, độ chính xác từ 0,90 trở lên trên tập vàng §6, và tỷ lệ bịa số bằng 0 trên toàn bộ tập kiểm.
Rủi ro: mô hình 1.5b yếu cho việc này. Giảm bằng chạy trích xuất trên mô hình lớn hơn theo lô ngoài giờ, vì đây là tác vụ nạp chứ không phải tác vụ tương tác.

### Sprint 6 - Hàng đợi duyệt

Mục tiêu: người duyệt có chỗ làm việc, và P3 có hiệu lực thật.

Việc:
- API: liệt kê extraction chờ duyệt kèm lọc theo tài liệu, loại dữ kiện, điểm tin cậy; duyệt; từ chối kèm lý do; sửa giá trị rồi duyệt; duyệt hàng loạt cho các dòng cùng luật.
- Tab mới "Tri thức" ở frontend: danh sách chờ duyệt bên trái, giá trị đã trích bên phải, nguyên văn mục bên dưới với đoạn trích được tô sáng, dùng lại thành phần tô sáng của `SourcePanel`.
- Phím tắt duyệt và từ chối để xử lý nhanh theo lô.
- Nhật ký hiển thị được: ai duyệt gì, khi nào, sửa từ giá trị nào sang giá trị nào.

Cổng: test quét mã nguồn `query/` không cho phép truy cập bảng gốc; test tích hợp xác nhận dữ kiện chưa duyệt không xuất hiện ở bất kỳ bề mặt nào; kiểm thử tay duyệt trọn một QTKĐ.
Rủi ro: khối lượng duyệt quá lớn gây nản. Giảm bằng duyệt hàng loạt theo luật và sắp xếp theo điểm tin cậy tăng dần để người duyệt gặp việc khó trước khi mệt.

### Sprint 7 - Nạp hồ sơ kiểm định và phiếu đo

Mục tiêu: dữ liệu đo thực tế vào được sổ cái.

Việc:
- Bảng `device`, `calibration_record`, `measurement_point` và migration.
- `records/template.py`: sinh cấu hình ánh xạ trường từ Phụ lục A đã trích xuất, người duyệt xác nhận một lần cho mỗi QTKĐ.
- `records/docx_reader.py`: đọc biên bản Word theo cấu hình, lấy trường đầu mục và bảng kết quả.
- `records/xlsx_reader.py`: đọc phiếu đo Excel, nhận diện dải bảng và tiêu đề cột.
- `records/matching.py`: đối sánh thiết bị theo loại và serial, tạo thiết bị mới khi chưa có, gắn cờ khi thiếu serial.
- Tính `expires_at` từ dữ kiện chu kỳ đã duyệt, lưu kèm tham chiếu dữ kiện nguồn.
- Bộ đọc cũng đi qua hàng đợi duyệt trước khi vào sổ cái.

Cổng: test đơn cho hai bộ đọc trên tệp mẫu đặt trong `tests/data/`; test xác nhận không có trường số nào bị hệ thống tự tính; đối sánh thiết bị không gộp nhầm hai serial khác nhau và không tách đôi cùng một serial viết khác kiểu hoa thường.
Rủi ro: chưa có tệp hồ sơ thật trong repo để thử. Việc đầu tiên của sprint này là thu thập ít nhất ba biên bản thật và một phiếu đo thật cho mỗi QTKĐ chính, đã làm sạch thông tin nhạy cảm, đưa vào `tests/data/`.
Nếu không thu thập được, sprint này dừng và ưu tiên đổi chỗ cho Sprint 8.

### Sprint 8 - Bề mặt tra cứu và lịch sử thiết bị

Mục tiêu: hai trong ba năng lực bắt buộc của phiên bản đầu chạy được.

Việc:
- `query/` với các truy vấn có tham số phục vụ bảng tra cứu.
- API phân trang, sắp xếp, lọc theo loại thiết bị, đại lượng, khoảng phạm vi đo, cấp chính xác, QTKĐ, kết luận, khoảng thời gian.
- Tab "Dữ liệu": bảng dày, lọc ở đầu cột, mỗi ô số bấm vào mở đúng đoạn nguyên văn đã sinh ra nó.
- Trang thiết bị: thông tin nhận dạng, dòng thời gian các lần kiểm định, biểu đồ diễn biến sai số theo mốc đo, liên kết tải hồ sơ gốc.
- Xuất Excel cho kết quả lọc hiện tại, kèm cột xuất xứ.

Cổng: bảng lọc trả đúng trên tập dữ liệu dựng sẵn; mọi ô số đều mở được nguồn; đo thời gian phản hồi dưới 500 mili giây với 10 nghìn hồ sơ dựng giả; kiểm tra tương phản và điều hướng bàn phím theo WCAG 2.1 AA như `PRODUCT.md` yêu cầu.
Rủi ro: bảng dày dễ trở thành tường số. Giảm bằng bám đúng nguyên tắc "mật độ là tính năng" đã có trong `PRODUCT.md`, và thử với người dùng thật trước khi khóa bố cục.

### Sprint 9 - Chat lai văn bản và số liệu

Mục tiêu: hoàn tất năng lực bắt buộc thứ ba.

Việc:
- `query/intents.py` với danh mục intent ở mục 8 và schema tham số.
- `query/router.py` phân ba nhánh, mặc định rơi về nhánh văn bản khi không chắc.
- Ghép câu trả lời hỗn hợp: phần quy định trích từ QTKĐ, phần số liệu trích từ sổ cái, hai khối trích dẫn tách bạch.
- Frontend hiển thị kết quả số liệu dưới dạng bảng có thể bấm sang trang thiết bị, không nhét số vào văn xuôi.
- Mở rộng `eval/` thêm tập câu hỏi số liệu, đo độ chính xác chọn intent và độ đúng của tham số.

Cổng: độ chính xác chọn intent từ 0,90 trở lên; không có trường hợp nào nhánh số liệu trả về con số không truy được nguồn; eval truy hồi văn bản hiện tại không tụt.
Rủi ro: định tuyến sai làm hỏng trải nghiệm đang tốt. Giảm bằng quy tắc mặc định rơi về nhánh văn bản, và bằng việc nhánh số liệu luôn hiển thị rõ nó đang đọc từ sổ cái chứ không từ tài liệu.

## 10. Thứ tự và phụ thuộc

```
S0 ──► S1 ──► S2 ──► S3 ──► S4 ──► S5 ──► S6 ──┬──► S7 ──┐
                                               │         ├──► S8 ──► S9
                                               └─────────┘
```

Chuỗi S0 tới S6 là tuyến tính, mỗi sprint cần đầu ra của sprint trước.
S7 cần S6 (hàng đợi duyệt) và S4 (dữ kiện chu kỳ để tính hạn hiệu lực).
S8 cần S6 và S7 để có đủ hai nguồn dữ liệu.
S9 cần S8.

Nếu tới đầu S7 mà chưa thu thập được hồ sơ thật, hoán đổi S7 và S8, và S8 chạy trước chỉ với dữ liệu tham chiếu.

## 11. Cổng kiểm chứng toàn hệ thống

Các cổng hiện có được giữ nguyên và không được phép tụt:
`make check` gồm lint, guard độ trung thực công thức 351 trên 351, và test đơn;
`make test-int` cho tầng tích hợp;
`python -m eval.run_eval` với recall@5 từ 0,85 trở lên.

Cổng mới:
`make db-check` chạy migration đi và lùi trên cơ sở dữ liệu sạch;
`python -m eval.extract_eval` cho độ chính xác và độ phủ trích xuất;
một test bảo vệ quét `query/` cấm truy cập bảng chưa lọc duyệt;
một test bảo vệ cấm mọi phép tính lại số liệu nguồn trong `records/`.

## 12. Rủi ro toàn dự án

| Rủi ro | Ảnh hưởng | Giảm thiểu |
|---|---|---|
| Chuẩn hóa đơn vị sai lặng lẽ | Bảng lọc trả sai, người dùng mất niềm tin | Quy tắc thà bỏ trống còn hơn đoán, test đối xứng quy đổi, luôn hiển thị nguyên văn cạnh giá trị đã chuẩn hóa |
| Không có hồ sơ thật để thử | S7 không kiểm chứng được | Thu thập mẫu là việc đầu tiên của S7, có phương án hoán đổi sprint |
| Khối lượng duyệt quá lớn | Dữ liệu kẹt ở trạng thái chờ, hệ thống vô dụng | Duyệt hàng loạt theo luật, sắp xếp theo điểm tin cậy, đo thời gian duyệt trung bình mỗi QTKĐ |
| QTKĐ lệch chuẩn ĐLVN | Luật trích xuất vỡ | Luật trả rỗng thay vì đoán, ghi lại mục không trích được |
| Thêm Postgres làm phức tạp vận hành offline | Khó triển khai tại chỗ | Đóng gói trong cùng `docker-compose.yml`, có backup và restore một lệnh, tài liệu hóa trong README |
| Phình phạm vi sang LIMS | Không bao giờ xong | Ranh giới đọc là chính đã chốt ở mục 2, mọi đề xuất nhập liệu phải là quyết định riêng |

## 13. Việc phải làm ngay trước Sprint 0

- Thu thập và làm sạch ít nhất ba biên bản kiểm định thật và một phiếu đo thật cho mỗi QTKĐ chính, phục vụ S7.
- Chốt danh sách đơn vị đo cần seed cho nhóm áp suất, nhiệt độ, độ ẩm, độ dài.
- Chốt danh sách vai trò và ai thuộc vai trò nào.
