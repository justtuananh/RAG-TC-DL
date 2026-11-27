# Kiến trúc tra cứu dựa trên 4 file danh mục 877

Tài liệu đề xuất, ngày 2026-11-27.
Đối tượng đọc: người vận hành và người phát triển chatbot QTKĐ.

---

## Mục lục

1. [Tóm tắt trong một trang](#1-tóm-tắt-trong-một-trang)
2. [4 file danh mục chứa gì](#2-4-file-danh-mục-chứa-gì)
3. [Chatbot hiện tại đang tìm thế nào và vướng ở đâu](#3-chatbot-hiện-tại-đang-tìm-thế-nào-và-vướng-ở-đâu)
4. [Ý tưởng chính: tra mục lục trước, đọc sách sau](#4-ý-tưởng-chính-tra-mục-lục-trước-đọc-sách-sau)
5. [Kiến trúc lưu trữ](#5-kiến-trúc-lưu-trữ)
6. [Kiến trúc truy xuất](#6-kiến-trúc-truy-xuất)
7. [Ví dụ đi từng bước](#7-ví-dụ-đi-từng-bước)
8. [Hỏi tiếp nhiều lượt](#8-hỏi-tiếp-nhiều-lượt)
9. [Các trường hợp đặc biệt](#9-các-trường-hợp-đặc-biệt)
10. [Lỗi dữ liệu đã phát hiện trong 4 file](#10-lỗi-dữ-liệu-đã-phát-hiện-trong-4-file)
11. [Kế hoạch triển khai](#11-kế-hoạch-triển-khai)
12. [Giải thích thuật ngữ](#12-giải-thích-thuật-ngữ)

---

## 1. Tóm tắt trong một trang

**Vấn đề.**
Hiện nay mỗi câu hỏi, chatbot tìm trong toàn bộ kho tài liệu.
Với câu hỏi chung ("phòng kiểm định được những gì?") nó trả lời kém vì không có tài liệu nào chứa sẵn câu trả lời tổng hợp.
Với câu hỏi sâu mà người dùng gọi tên thiết bị khác với tên trong tiêu đề quy trình, nó dễ tìm nhầm tài liệu.

**Giải pháp.**
Biến 4 file danh mục thành một **"sổ đăng ký"** có cấu trúc, giống mục lục của thư viện.
Mỗi câu hỏi đều tra sổ đăng ký trước:

- Nếu là **câu hỏi chung** (có không, bao nhiêu, liệt kê, dải đo, chu kỳ, dùng quy trình nào), chatbot trả lời ngay từ sổ đăng ký, chính xác và có trích dẫn dòng.
- Nếu là **câu hỏi sâu** (cách làm, điều kiện, công thức, giới hạn sai số), sổ đăng ký chỉ ra đúng những tài liệu liên quan, rồi chatbot chỉ tìm sâu bên trong các tài liệu đó.

**Không bắt buộc hỏi câu chung trước.**
Người dùng có thể hỏi thẳng một câu sâu ngay từ đầu.
Bước tra sổ đăng ký chạy ngầm bên trong mỗi câu hỏi, người dùng không thấy.

**Hỏi tiếp được.**
Sau một câu trả lời, chatbot nhớ những tài liệu vừa nhắc tới.
Câu tiếp theo như "còn cái thứ hai thì sao?" sẽ tìm trong đúng những tài liệu đó.

---

## 2. 4 file danh mục chứa gì

| File | Mỗi dòng là | Các cột | Số dòng có dữ liệu |
|---|---|---|---|
| DANH MỤC QUY TRÌNH | Một quy trình (QTKĐ, ĐLVN, QTHC...) | Ký hiệu, tên quy trình, cấp ban hành, lĩnh vực, loại (kiểm định / hiệu chuẩn) | khoảng 73 |
| NĂNG LỰC KIỂM ĐỊNH NAS | Một loại phương tiện đo phòng được phép kiểm định | Tên phương tiện, tham số đo lường (dải đo, cấp chính xác), các quy trình áp dụng, lĩnh vực | khoảng 41 |
| NĂNG LỰC HIỆU CHUẨN NAS | Một loại phương tiện đo phòng được phép hiệu chuẩn | Tên phương tiện, quy trình áp dụng, lĩnh vực | 7 |
| DANH MỤC CHUẨN MẪU NAS | Một chuẩn mẫu cụ thể của phòng | Tên, ký hiệu (model), số hiệu, đặc tính đo lường, chu kỳ kiểm định/hiệu chuẩn | 95 |

### Các file nối với nhau thế nào

```
 NĂNG LỰC KIỂM ĐỊNH / HIỆU CHUẨN                DANH MỤC QUY TRÌNH                 Kho tài liệu TC_DL/
 ┌─────────────────────────────┐   ký hiệu   ┌──────────────────────┐   mã số   ┌────────────────────────┐
 │ Van an toàn                 │────────────►│ QTKĐ 1.023 : 2021    │──────────►│ (file QTKĐ 1.023 nếu   │
 │ Dải đo 0-140 MPa, CCX 0,5   │             │ Van an toàn ... 1400 │           │  đã có trong kho)      │
 └─────────────────────────────┘             └──────────────────────┘           └────────────────────────┘

 DANH MỤC CHUẨN MẪU                                                     Kho tài liệu TC_DL/
 ┌─────────────────────────────┐            model + số hiệu            ┌────────────────────────────────────┐
 │ Áp kế pittông Fluke 7302    │──────────────────────────────────────►│ A_01_Ap_ke_pittong_Fluke_7302_1274 │
 │ số hiệu 1274, chu kỳ ...    │                                       └────────────────────────────────────┘
 └─────────────────────────────┘
```

Nói ngắn gọn:

- **Phương tiện đo** (trong file năng lực) trỏ tới **quy trình** bằng ký hiệu quy trình.
- **Quy trình** (trong danh mục quy trình) trỏ tới **file văn bản** trong kho bằng mã số.
- **Chuẩn mẫu** trỏ tới **file hướng dẫn A_xx** bằng model và số hiệu.

Chính những mũi tên này cho phép chatbot đi từ một câu hỏi chung chung xuống đúng tài liệu cần đọc sâu.

---

## 3. Chatbot hiện tại đang tìm thế nào và vướng ở đâu

Hiện nay, với mỗi câu hỏi, chatbot làm như sau:

1. Nếu câu hỏi có số QTKĐ, mã TCVN, hoặc tên thiết bị trùng với tiêu đề tài liệu, chatbot ghim vào tài liệu đó.
2. Nếu không, chatbot đoán nhóm tài liệu theo loại câu hỏi (áp suất, nhiệt độ...) rồi tìm trong nhóm đó.
3. Nếu vẫn không chắc, chatbot tìm trong toàn bộ kho.
4. Các đoạn văn tìm được được xếp hạng lại, rồi đưa cho mô hình ngôn ngữ viết câu trả lời.

Những chỗ vướng:

| Tình huống | Vì sao khó |
|---|---|
| "Phòng kiểm định được những phương tiện áp suất nào?" | Không có tài liệu QTKĐ nào chứa sẵn danh sách này. Mô hình phải ghép từ nhiều đoạn rời rạc, dễ thiếu hoặc thừa. |
| "Có bao nhiêu chuẩn mẫu lĩnh vực nhiệt độ?" | Đếm là việc mô hình ngôn ngữ 7B làm sai thường xuyên. |
| "Chuẩn nào tạo được 600 bar?" | Cần so sánh số và quy đổi đơn vị, tìm kiếm theo văn bản không làm được. |
| "Kiểm định đồng hồ đo độ cao cần điều kiện gì?" | Tên "đồng hồ đo độ cao" không nằm trong tiêu đề quy trình nào. Chỉ file năng lực mới cho biết nó dùng ĐLVN 135, ĐLVN 134, QTKĐ 1.061, QTKĐ 1.160. |
| Thiết bị phòng không có năng lực kiểm định | Chatbot vẫn cố tìm và có thể trả lời bằng một tài liệu không liên quan. |

---

## 4. Ý tưởng chính: tra mục lục trước, đọc sách sau

Hãy hình dung một thủ thư.
Khi được hỏi, thủ thư không đọc hết cả thư viện.
Họ tra mục lục trước, biết sách nào liên quan, rồi chỉ mở những cuốn đó.

Chatbot sẽ làm y như vậy, với 2 tầng:

```
                   ┌──────────────────────────────────────────┐
  Câu hỏi  ───────►│ TẦNG 1: TRA SỔ ĐĂNG KÝ (4 file danh mục) │
                   └──────────────────────────────────────────┘
                          │                         │
          câu hỏi chung   │                         │  câu hỏi sâu
                          ▼                         ▼
          ┌────────────────────────────┐  ┌──────────────────────────────────────┐
          │ Trả lời ngay từ sổ đăng ký  │  │ TẦNG 2: TÌM SÂU, CHỈ TRONG CÁC FILE   │
          │ (không cần mô hình ngôn ngữ)│  │ mà sổ đăng ký vừa chỉ ra             │
          └────────────────────────────┘  └──────────────────────────────────────┘
```

Điểm quan trọng:

- **Tầng 1 luôn chạy**, kể cả khi người dùng hỏi câu sâu ngay từ đầu.
- **Câu hỏi chung dừng ở tầng 1.**
- **Câu hỏi sâu đi tiếp xuống tầng 2**, trong cùng một lượt hỏi.
- Nếu sổ đăng ký không khớp được gì, chatbot quay về cách tìm như hiện nay. Không có gì bị mất đi.

---

## 5. Kiến trúc lưu trữ

Dữ liệu được lưu ở 3 lớp.
Mỗi lớp có một việc riêng.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ LỚP 0 - FILE GỐC                                                             │
│   TC_DL/*.docx                  : các QTKĐ, ĐLVN, hướng dẫn chuẩn A_xx       │
│   TC_DL/danh_muc/*.docx         : 4 file danh mục 877                         │
└──────────────────────────────────────────────────────────────────────────────┘
          │ trích xuất (đã có)                      │ nạp danh mục (mới)
          ▼                                         ▼
┌──────────────────────────────────┐    ┌──────────────────────────────────────┐
│ LỚP 2 - QDRANT (đã có)            │    │ LỚP 1 - SỔ ĐĂNG KÝ TRONG POSTGRES     │
│ Nội dung chi tiết của từng tài    │◄───│ Phương tiện, quy trình, chuẩn mẫu,   │
│ liệu, cắt thành đoạn để tìm sâu   │    │ dải đo, chu kỳ, và liên kết tới file │
└──────────────────────────────────┘    └──────────────────────────────────────┘
```

### 5.1. Lớp 0: file gốc

- Giữ nguyên như hiện nay cho các tài liệu QTKĐ.
- 4 file danh mục được upload như một **loại tài liệu mới: "danh mục"**.
- Khi phòng cập nhật danh mục (thêm chuẩn, đổi chu kỳ...), người dùng chỉ cần upload lại file mới.

### 5.2. Lớp 1: sổ đăng ký trong Postgres (phần mới)

Đây là phần cốt lõi.
Mỗi dòng trong 4 file trở thành một dòng trong bảng, có cột rõ ràng để lọc, đếm và so sánh.

#### Bảng `catalog_source`: theo dõi các file danh mục

| Cột | Ý nghĩa | Ví dụ |
|---|---|---|
| file | Tên file danh mục | DANH MỤC CHUẨN MẪU NAS ĐƯỢC CÔNG NHẬN THEO 877.docx |
| loại | Danh mục quy trình / năng lực KĐ / năng lực HC / chuẩn mẫu | chuẩn mẫu |
| sha256 | Dấu vân tay nội dung, để biết file đã đổi chưa | ... |
| trạng thái | Nháp / đã duyệt | đã duyệt |
| người duyệt, ngày duyệt | Ai xác nhận dữ liệu này đúng | ... |

#### Bảng `procedure`: quy trình (mở rộng bảng đã có)

| Cột | Ý nghĩa | Ví dụ |
|---|---|---|
| code_norm | Mã chuẩn hóa, dùng làm khóa | QTKĐ 1.023:2021 |
| prefix, số, năm | Tách riêng từng phần của mã | QTKĐ / 1.023 / 2021 |
| tên | Tên quy trình | Van an toàn có phạm vi làm việc đến 1400 bar - Quy trình kiểm định |
| cấp ban hành | | Cục TC - ĐL - CL |
| lĩnh vực | | Phương tiện đo áp suất |
| loại | Kiểm định hay hiệu chuẩn | Quy trình kiểm định |
| document_id | File văn bản trong kho. Để trống nếu kho chưa có | (id của file QTKĐ 1.023) |
| source_row | Dòng số mấy trong file danh mục, để trích dẫn | (số dòng) |

> **Thay đổi bắt buộc:** bảng `procedure` hiện coi **số** (ví dụ "1.017") là duy nhất.
> Nhưng danh mục có nhiều quy trình **trùng số, khác năm**, là những tài liệu hoàn toàn khác nhau:
>
> - QTKĐ 1.017:2008 là Tủ sấy, còn QTKĐ 1.017:2014 là Chỉ thị nhiệt độ.
> - QTKĐ 1.021:2009 là Bình chuẩn dung tích, còn QTKĐ 1.021:2014 là Cặp nhiệt điện.
> - QTKĐ 1.022:2009 và QTKĐ 1.022:2014 cũng vậy.
> - QTKĐ 1.005:2010 và QTKĐ 1.005:2013 cũng vậy.
>
> Vì vậy khóa phải gồm cả **prefix + số + năm**.
> Khi người dùng chỉ nói số mà không nói năm, chatbot xét tất cả các bản trùng số và để bước xếp hạng chọn.

#### Bảng `capability`: năng lực của phòng

| Cột | Ý nghĩa | Ví dụ |
|---|---|---|
| loại | Kiểm định hay hiệu chuẩn | kiểm định |
| tên phương tiện | | Đồng hồ đo độ cao |
| alias | Các cách gọi khác | đồng hồ độ cao, cao kế |
| lĩnh vực | | Áp suất |
| params_raw | Cột tham số **nguyên văn** | Dải đo: Từ 8 mmHg đến 800 mmHg; Sai số: Đến ± 0,1 mmHg |
| source_row | Dòng trong file năng lực | 5 |

#### Bảng `capability_range`: dải đo đã tách thành số

| Cột | Ý nghĩa | Ví dụ |
|---|---|---|
| capability_id | Thuộc năng lực nào | (Đồng hồ đo độ cao) |
| nhãn | Tên dải, nếu một phương tiện có nhiều dải | Dải đo |
| đại lượng | | áp suất |
| min_si, max_si | Giới hạn dải, **đã quy đổi về đơn vị SI** để so sánh | 1066,6 Pa ... 106 657 Pa |
| accuracy_raw | Độ chính xác nguyên văn | Sai số: Đến ± 0,1 mmHg |

Nhờ bảng này, câu hỏi "áp kế píttông 3000 bar" so được với dải "0 MPa đến 500 MPa", dù hai bên dùng đơn vị khác nhau.
Quy đổi đơn vị dùng bảng `unit` đã có sẵn, tính bằng số thập phân chính xác (Decimal).

#### Bảng `capability_procedure`: phương tiện dùng quy trình nào

| Cột | Ý nghĩa | Ví dụ |
|---|---|---|
| capability_id | | (Đồng hồ đo độ cao) |
| mã gốc | Mã đúng như ghi trong ô | QTKĐ 1.160.2021 |
| procedure_id | Quy trình đã khớp được. Để trống nếu không khớp, và đưa vào báo cáo lỗi | (QTKĐ 1.160:2021) |

Một phương tiện có thể dùng nhiều quy trình, ví dụ "Áp kế hiện số" dùng QTKĐ 1.016, ĐLVN 263 và QTKĐ 1.160.

#### Bảng `reference_standard` và `standard_range`: chuẩn mẫu

| Cột | Ý nghĩa | Ví dụ |
|---|---|---|
| tên | | Áp kế píttông (Nga) |
| model | Ký hiệu | MΠ-600 |
| số hiệu | | 994 |
| đặc tính_raw | Nguyên văn | Giá trị tạo áp suất: (10 đến 600) bar; CCX: 0,05 |
| chu kỳ_raw, chu kỳ_tháng | Nguyên văn và dạng số | "4 năm" / 48 |
| lĩnh vực | | Áp suất |
| document_id | File hướng dẫn A_xx nếu có | A_06_Ap_ke_pittong_MP_600_994 |
| source_row | Dòng trong file chuẩn mẫu | 6 |

`standard_range` giống hệt `capability_range`, dùng cho câu hỏi kiểu "chuẩn nào tạo được 600 bar".

#### Ba nguyên tắc của Lớp 1

1. **Luôn giữ nguyên văn.**
   Câu trả lời luôn trích nguyên văn từ file danh mục.
   Các cột số chỉ dùng để lọc và so sánh, không thay cho nguyên văn.
2. **Nháp trước, duyệt sau.**
   Giống cách công thức và bản tóm tắt đang được duyệt.
   Khi nạp file danh mục, hệ thống tạo bản nháp kèm báo cáo lỗi (xem [mục 10](#10-lỗi-dữ-liệu-đã-phát-hiện-trong-4-file)).
   Chỉ sau khi người có quyền duyệt, dữ liệu mới được chatbot dùng.
3. **Tự liên kết lại.**
   Khi upload, thay hoặc xóa một tài liệu QTKĐ, cột `document_id` được cập nhật tự động.
   Nhờ vậy sổ đăng ký luôn biết quy trình nào đã có văn bản trong kho.

### 5.3. Lớp 2: Qdrant (giữ nguyên, bổ sung nhỏ)

- Giữ nguyên cách cắt đoạn và tìm kiếm hiện tại.
- Thêm 2 thông tin vào mỗi đoạn: `procedure_code` và `field` (lĩnh vực), để lọc nhanh ngay trong Qdrant.
- 4 file danh mục **không** đưa vào tìm kiếm theo đoạn văn, vì câu hỏi chung đã được trả lời chính xác hơn từ Lớp 1.
  Chúng vẫn được chuyển sang Markdown để khung xem nguồn hiển thị và tô sáng đúng dòng được trích dẫn.

### 5.4. Chỉ mục tên (trong bộ nhớ)

Để biết câu hỏi đang nói tới dòng nào trong sổ đăng ký, chatbot cần một chỉ mục tên nhỏ, khoảng 250 tên (phương tiện, chuẩn mẫu, quy trình, kèm alias).
Chỉ mục này nằm trong bộ nhớ, dựng từ Lớp 1, và được dựng lại mỗi khi danh mục được duyệt lại.

Cách khớp tên, theo thứ tự ưu tiên:

1. Bỏ dấu, so khớp chính xác với tên hoặc alias.
2. So khớp gần đúng (BM25 / fuzzy), để "ta khô met", "takhomet", "tốc độ kế" vẫn khớp được.
3. So khớp theo nghĩa bằng embedding, chỉ dùng khi hai cách trên không ra kết quả.

---

## 6. Kiến trúc truy xuất

Mọi câu hỏi đi qua cùng một đường ống.

```
 Câu hỏi của người dùng  (+ "tiêu điểm" của lượt trước, nếu có)
   │
   ▼
 BƯỚC 1. Tìm mã tường minh
   Câu hỏi có ghi QTKĐ / ĐLVN / TCVN / QTHC, hoặc model + số hiệu chuẩn?
   │
   ▼
 BƯỚC 2. Khớp với sổ đăng ký
   Câu hỏi nói tới phương tiện / chuẩn / quy trình nào?
   Câu hỏi có con số + đơn vị nào không ("3000 bar", "200 °C")? Nếu có, lọc theo dải đo.
   Không khớp gì, và câu hỏi không nêu đối tượng? Dùng tiêu điểm của lượt trước.
   │
   ▼
 BƯỚC 3. Phân loại câu hỏi: chung hay sâu?
   │
   ├──► CÂU HỎI CHUNG ──► BƯỚC 4A. Trả lời từ sổ đăng ký
   │
   ├──► CÂU HỎI SÂU ────► BƯỚC 4B. Tìm sâu trong các file đã chỉ ra
   │
   └──► KHÔNG KHỚP GÌ ──► Cách tìm hiện tại (toàn kho, theo nhóm lĩnh vực)
   │
   ▼
 BƯỚC 5. Ghi nhớ tiêu điểm cho lượt sau
```

### Bước 1. Tìm mã tường minh

Nếu người dùng đã ghi rõ mã, đó là tín hiệu chắc chắn nhất.
Ví dụ "QTKĐ 1.159" hay "MΠ-600 số 994".
Mã tường minh luôn được ưu tiên hơn mọi suy đoán khác.

### Bước 2. Khớp với sổ đăng ký

Dùng chỉ mục tên (mục 5.4) để tìm các dòng liên quan.
Kết quả của bước này là một danh sách dòng, ví dụ:

```
Câu hỏi: "Kiểm định áp kế píttông 3000 bar"
Khớp:    capability "Áp kế píttông"
         ├─ dải 1: -0,1 MPa đến 0 MPa          → không chứa 3000 bar
         └─ dải 2: 0 MPa đến 500 MPa (5000 bar) → chứa 3000 bar  ✓
         Quy trình: QTKĐ 1.159:2021, QTKĐ 1.071:2022
```

Nếu câu hỏi có số và đơn vị, chatbot dùng bảng dải đo để chọn đúng dòng hoặc đúng quy trình.

### Bước 3. Phân loại câu hỏi

Dựa vào các mẫu câu cố định (cấu hình trong `settings.yaml`, giống cách `doc_catalog` đang làm):

| Loại | Dấu hiệu | Ví dụ |
|---|---|---|
| **Chung** | có ... không, những ... nào, bao nhiêu, liệt kê, dải đo, cấp chính xác, chu kỳ, dùng quy trình nào, dùng chuẩn nào | "Phòng có hiệu chuẩn tủ vi khí hậu không?" |
| **Sâu** | cách, thế nào, ra sao, điều kiện, các bước, công thức, sai số cho phép, xử lý kết quả, đánh giá | "Van an toàn kiểm tra độ kín thế nào?" |
| **Cả hai** | một câu hỏi có cả hai ý | "Van an toàn dùng quy trình nào và kiểm tra độ kín ra sao?" |

### Bước 4A. Trả lời câu hỏi chung

- Truy vấn bảng trong Lớp 1: lọc, đếm, so dải đo.
- Trả lời theo mẫu cố định, **trích nguyên văn**, kèm trích dẫn **[tên file danh mục, dòng n]**.
- **Không dùng mô hình ngôn ngữ**, nên không bịa, không sai số đếm, và trả lời gần như tức thì.

### Bước 4B. Tìm sâu

1. Từ các dòng đã khớp, lấy ra danh sách file: `procedure.document_id` hoặc `reference_standard.document_id`.
2. Tìm kiếm **chỉ trong các file đó**, mỗi file được chia một phần ngân sách để không file nào bị lấn át.
3. Xếp hạng lại các đoạn tìm được như hiện nay.
4. Nếu điểm xếp hạng quá thấp (các file đã chọn không chứa câu trả lời), mở rộng ra toàn kho.
   Cơ chế này giống `doc_scopes.fallback_min_score` đang có.
5. Đưa cho mô hình ngôn ngữ: một khối **"thông tin danh mục"** nguyên văn ở đầu, rồi các đoạn tìm được.
6. Quy trình nào có trong danh mục nhưng kho chưa có văn bản thì ghi chú một dòng ở cuối câu trả lời.

Các chức năng hiện có như trả lời nguyên văn một mục, hỏi lại tham số khi tra bảng giới hạn, trích công thức... vẫn chạy bình thường.
Điểm khác duy nhất là chúng làm việc trên danh sách file đã được thu hẹp.

### Bước 5. Ghi nhớ tiêu điểm

Sau mỗi câu trả lời, chatbot lưu lại **tiêu điểm**: danh sách có thứ tự các dòng danh mục và file vừa nhắc tới.
Tiêu điểm được gửi kèm câu hỏi tiếp theo (xem [mục 8](#8-hỏi-tiếp-nhiều-lượt)).

### Vị trí trong mã nguồn

Thứ tự xử lý trong `api/services/chat_stream.py` sẽ là:

```
sổ đăng ký (mới) → doc_catalog → doc_sections → doc_overview → retrieve (đã thu hẹp)
```

Các module dự kiến:

| Module | Việc |
|---|---|
| `ingestion/registry_import.py` | Đọc 4 file, tách ô, chuẩn hóa mã, tách dải đo, tạo bản nháp và báo cáo lỗi |
| `knowledge/registry.py` | Truy vấn sổ đăng ký: tìm theo tên, theo mã, theo dải đo, đếm, liệt kê |
| `retrieval/registry_match.py` | Chỉ mục tên trong bộ nhớ và bước khớp câu hỏi với sổ đăng ký |
| `query/registry_answer.py` | Phân loại câu hỏi, trả lời câu hỏi chung, trả danh sách file cho câu hỏi sâu |
| `api/routes/registry.py` | Màn hình duyệt bản nháp danh mục và xem báo cáo lỗi |
| `db/migrations/versions/017_registry.py` | Tạo các bảng mới, đổi khóa của `procedure` |

---

## 7. Ví dụ đi từng bước

### Ví dụ 1. Câu hỏi chung

> **Hỏi:** Phòng có hiệu chuẩn tủ vi khí hậu không?

| Bước | Diễn biến |
|---|---|
| 1. Mã tường minh | Không có |
| 2. Khớp sổ đăng ký | "tủ vi khí hậu" khớp quy trình QTHC 1.024:2021 (loại: hiệu chuẩn) |
| 3. Phân loại | "có ... không" nên là câu hỏi **chung** |
| 4A. Trả lời | "Có. Phòng hiệu chuẩn tủ vi khí hậu theo QTHC 1.024:2021 - Tủ vi khí hậu - QTHC, cấp ban hành Cục TC-ĐL-CL [DANH MỤC QUY TRÌNH, dòng n]." |

### Ví dụ 2. Câu hỏi sâu, hỏi thẳng từ đầu

> **Hỏi:** Kiểm định đồng hồ đo độ cao thì điều kiện môi trường thế nào?

| Bước | Diễn biến |
|---|---|
| 1. Mã tường minh | Không có |
| 2. Khớp sổ đăng ký | "đồng hồ đo độ cao" khớp năng lực KĐ, quy trình: ĐLVN 135:2004, ĐLVN 134:2004, QTKĐ 1.061:2016, QTKĐ 1.160:2021 |
| 3. Phân loại | "điều kiện ... thế nào" nên là câu hỏi **sâu** |
| 4B. Tìm sâu | Kiểm tra kho: QTKĐ 1.061 và QTKĐ 1.160 có văn bản, 2 quy trình ĐLVN chưa có. Chỉ tìm trong 2 file có văn bản, lấy mục "Điều kiện kiểm định". |
| Trả lời | Trích nguyên văn điều kiện môi trường từ từng quy trình, kèm [n]. Cuối câu ghi: "ĐLVN 135:2004 và ĐLVN 134:2004 có trong danh mục 877 nhưng kho chưa có văn bản." |

### Ví dụ 3. Câu hỏi có con số

> **Hỏi:** Áp kế píttông 3000 bar kiểm định theo quy trình nào, cần chuẩn gì?

| Bước | Diễn biến |
|---|---|
| 2. Khớp sổ đăng ký | "Áp kế píttông" có 2 quy trình. Dải 0-500 MPa chứa 3000 bar. |
| 3. Phân loại | Vế "quy trình nào" là chung, vế "cần chuẩn gì" là sâu |
| 4A + 4B | Trả lời vế chung từ danh mục (QTKĐ 1.159:2021, QTKĐ 1.071:2022), rồi tìm trong mục "Phương tiện kiểm định" của các file đó để trả lời vế sâu |

### Ví dụ 4. Câu hỏi về chuẩn mẫu

> **Hỏi:** Chuẩn nào tạo được 600 bar, chu kỳ bao lâu?

| Bước | Diễn biến |
|---|---|
| 2. Khớp sổ đăng ký | Lọc `standard_range`: các chuẩn có dải chứa 600 bar (60 MPa) |
| 3. Phân loại | **Chung** (chuẩn nào, chu kỳ) |
| 4A. Trả lời | Bảng các chuẩn thỏa mãn: tên, model, số hiệu, dải, chu kỳ, kèm dòng trích dẫn. Ví dụ Fluke 7302, MΠ-600, MΠ-2500, WIKA M2800, các áp kế hiện số 681 dải 700 bar và 1 400 bar... |

### Ví dụ 5. Câu hỏi về một chuẩn cụ thể

> **Hỏi:** Áp kế píttông MΠ-600 số 994 sử dụng thế nào?

| Bước | Diễn biến |
|---|---|
| 1. Mã tường minh | Model MΠ-600 + số hiệu 994 |
| 2. Khớp sổ đăng ký | Chuẩn mẫu dòng 6, liên kết tới file `A_06_Ap_ke_pittong_MP_600_994` |
| 3. Phân loại | "sử dụng thế nào" nên là câu hỏi **sâu** |
| 4B. Tìm sâu | Chỉ tìm trong file A_06 |

### Ví dụ 6. Thiết bị phòng không có năng lực

> **Hỏi:** Kiểm định cân ô tô thế nào?

| Bước | Diễn biến |
|---|---|
| 2. Khớp sổ đăng ký | Không có năng lực nào khớp "cân ô tô" |
| Kết quả | Chatbot tìm theo cách hiện tại. Nếu không tìm thấy, trả lời rõ: "Cân ô tô không có trong danh mục năng lực kiểm định 877 của phòng." Chatbot không lấy đại một tài liệu khác để trả lời. |

---

## 8. Hỏi tiếp nhiều lượt

Người dùng có thể hỏi chung trước rồi đào sâu, hoặc hỏi sâu rồi hỏi tiếp.
Cả hai đều dùng **tiêu điểm** của lượt trước.

```
Lượt 1  Hỏi: Phòng kiểm định được những phương tiện đo áp suất nào?
        Đáp: (danh sách 17 phương tiện, mỗi cái kèm quy trình)
        Tiêu điểm = [1. Áp kế píttông, 2. Áp kế hiện số, 3. Khí áp kế, ..., 10. Van an toàn, ...]

Lượt 2  Hỏi: Van an toàn kiểm tra độ kín thế nào?
        → "Van an toàn" khớp mục 10 trong tiêu điểm
        → chỉ tìm trong file của QTKĐ 1.023

Lượt 3  Hỏi: Còn cái thứ 2 thì dùng chuẩn gì?
        → "cái thứ 2" = mục 2 trong tiêu điểm của lượt 1 = Áp kế hiện số
        → chỉ tìm trong QTKĐ 1.016, QTKĐ 1.160 (và ĐLVN 263 nếu có văn bản)
```

Quy tắc dùng tiêu điểm, theo thứ tự ưu tiên:

1. Câu hỏi có mã hoặc tên thiết bị **mới**, nằm ngoài tiêu điểm: coi là chủ đề mới, tra sổ đăng ký lại từ đầu.
2. Câu hỏi nêu tên **khớp một mục trong tiêu điểm**: dùng mục đó.
3. Câu hỏi dùng **số thứ tự hoặc từ chỉ định** ("cái thứ 2", "quy trình đó", "chuẩn này"): lấy mục tương ứng. Nếu tiêu điểm chỉ có một mục thì lấy mục đó.
4. Câu hỏi **không nêu đối tượng**: tìm trong tất cả file của tiêu điểm.

Tiêu điểm bị xóa khi người dùng chuyển sang chủ đề mới hoặc bấm "Hội thoại mới".
Mỗi câu trả lời ở tầng 2 ghi rõ đang tìm trong những file nào, để người dùng biết phạm vi.

---

## 9. Các trường hợp đặc biệt

| Trường hợp | Cách xử lý |
|---|---|
| Quy trình có trong danh mục, kho chưa có văn bản | Câu hỏi chung vẫn trả lời được. Câu hỏi sâu thì báo rõ "chưa có văn bản để tra sâu". |
| Một phương tiện dùng nhiều quy trình | Tìm trong tất cả, mỗi file một phần ngân sách. Nếu câu hỏi có dải đo hoặc cấp chính xác thì dùng để chọn bớt. |
| Người dùng chỉ nói số, không nói năm ("QTKĐ 1.017") | Xét mọi bản trùng số (1.017:2008 tủ sấy, 1.017:2014 chỉ thị nhiệt độ). Nếu câu hỏi có tên thiết bị thì dùng tên để chọn. Nếu vẫn mơ hồ thì liệt kê và hỏi lại. |
| Danh mục ghi một năm, kho có bản năm khác | Dùng bản trong kho, và ghi chú sự khác biệt (ví dụ danh mục ghi 1.023:2009, kho có 1.023:2021). |
| Tên gọi khác nhau ("takhomet", "ta khô met", "tốc độ kế") | Chỉ mục tên khớp gần đúng, cộng với alias trong bảng `capability`. |
| Các file đã chọn không chứa câu trả lời | Điểm xếp hạng thấp thì mở rộng ra toàn kho, như cơ chế hiện có. |
| Danh mục được cập nhật | Upload file mới, hệ thống hiện phần thay đổi so với bản cũ, chờ duyệt, rồi mới thay thế. |

---

## 10. Lỗi dữ liệu đã phát hiện trong 4 file

Khi đọc 4 file, tôi đã thấy các lỗi dưới đây.
Bước nạp danh mục phải bắt được tất cả và đưa vào báo cáo cho người duyệt.
Nếu không xử lý, tầng 2 sẽ ghim nhầm file hoặc không tìm thấy file.

### 10.1. Lỗi cấu trúc (xử lý tự động khi nạp)

| Lỗi | Ví dụ | Cách xử lý |
|---|---|---|
| Nhiều mã dính liền trong một ô | "QTKĐ 1.159 : 2021QTKĐ 1.071 : 2022" | Tách theo từng đoạn văn trong ô Word |
| Ô gộp dọc làm xuất hiện dòng trống | File NĂNG LỰC HIỆU CHUẨN: 21 dòng nhưng chỉ 7 dòng có dữ liệu | Đọc thuộc tính gộp ô (`vMerge`) của Word |
| Chỉ số trên bị mất | "12 × 10-6" (đúng là 10⁻⁶), "10-3 đến 10-5 Ω" | Đọc định dạng chỉ số trên (`vertAlign`) khi trích xuất |
| Mã viết không thống nhất | "QTKĐ 1.160.2021", "QTKĐ 1.023 :2009", "23 QTKĐ 1.0017 : 2006", "ĐLVN 10: 2017" | Hàm chuẩn hóa mã dùng chung với router |

### 10.2. Lỗi nội dung (cần người duyệt xác nhận)

| Lỗi | Chi tiết |
|---|---|
| Năm ban hành lệch giữa các file | Van an toàn: năng lực ghi **QTKĐ 1.023:2009**, danh mục ghi **QTKĐ 1.023:2021** |
| | Nhiệt kế thủy tinh: năng lực ghi **ĐLVN 20:2017**, danh mục ghi **ĐLVN 20:2019** |
| Mã có trong năng lực, không có trong danh mục | QTKĐ 1.162:2021 (van an toàn) |
| Lĩnh vực ghi sai | Dòng "Phương tiện đo dung tích thí nghiệm bằng thuỷ tinh" ghi lĩnh vực là "03" |
| Thiếu quy trình | Dòng "Thiết bị kiểm tra khí tài lặn ΠКУ-M" để trống cột quy trình (danh mục có QTKĐ 1.141:2020 cho thiết bị này) |
| Cấp chính xác ghi sai | Áp kế lò xo chuẩn MO-1226 số 3777 ghi "CCX: 025" (có lẽ là 0,25) |

### 10.3. Khoảng trống giữa danh mục và kho

- Danh mục quy trình có khoảng **73 quy trình**.
- Kho `TC_DL/` có khoảng **40 tài liệu khác nhau** (nhiều file là bản trùng có đuôi `_2`).
- Nghĩa là khoảng một nửa số quy trình trong danh mục **chưa có văn bản** trong kho.

Đây không phải lỗi của chatbot, nhưng là thông tin hữu ích.
Chatbot sẽ nói rõ "có trong danh mục, chưa có văn bản" thay vì im lặng hoặc trả lời bằng tài liệu khác.
Báo cáo nạp danh mục cũng sẽ liệt kê danh sách này để phòng bổ sung tài liệu.

---

## 11. Kế hoạch triển khai

Nguyên tắc: **đo trước, làm sau, đo lại sau mỗi bước.**

| Bước | Việc | Kết quả kiểm chứng |
|---|---|---|
| 0 | Soạn bộ khoảng 40 câu hỏi thẳng (chung + sâu + hỏi tiếp), mỗi câu kèm dòng danh mục và file đúng | Đo hệ thống **hiện tại**: tỉ lệ ghim đúng file, recall@5. Đây là mốc so sánh. |
| 1 | Migration tạo bảng, đổi khóa `procedure`, importer 4 file, báo cáo lỗi, màn hình duyệt | Test trên chính 4 file: đủ số dòng, tách đúng mã, bắt đủ các lỗi ở mục 10 |
| 2 | Chỉ mục tên và bước khớp câu hỏi với sổ đăng ký | Tỉ lệ khớp đúng dòng trên bộ câu hỏi bước 0 |
| 3 | Trả lời câu hỏi chung | Câu trả lời đúng 100% so với file danh mục (vì là tất định) |
| 4 | Ghim file cho câu hỏi sâu | Tỉ lệ ghim đúng file tăng so với mốc. `run_eval` không giảm recall. |
| 5 | Tiêu điểm hội thoại nhiều lượt | Test hội thoại như ví dụ ở mục 8 |
| 6 | Bổ sung khoảng 30 câu vào `evaluation/answer_set.jsonl` | `make answer-eval` |

---

## 12. Giải thích thuật ngữ

| Thuật ngữ | Nghĩa trong tài liệu này |
|---|---|
| **Sổ đăng ký** | Dữ liệu của 4 file danh mục, lưu thành bảng trong Postgres để lọc, đếm, so sánh được |
| **Câu hỏi chung** | Câu hỏi trả lời được chỉ bằng 4 file danh mục |
| **Câu hỏi sâu** | Câu hỏi cần đọc nội dung bên trong một quy trình hoặc hướng dẫn |
| **Tầng 1 / tầng 2** | Tầng 1: tra sổ đăng ký. Tầng 2: tìm sâu trong các file mà tầng 1 chỉ ra. |
| **Ghim file** | Giới hạn việc tìm kiếm chỉ trong một số file nhất định |
| **Tiêu điểm** | Danh sách các dòng danh mục và file mà câu trả lời trước vừa nhắc tới, dùng cho câu hỏi tiếp theo |
| **Nguyên văn** | Chép đúng chữ trong tài liệu gốc, không diễn đạt lại |
| **Tất định** | Cùng câu hỏi luôn ra cùng kết quả, do chương trình tính chứ không do mô hình ngôn ngữ đoán |
| **Qdrant** | Cơ sở dữ liệu lưu các đoạn văn đã cắt nhỏ, dùng để tìm kiếm theo nội dung |
| **Postgres** | Cơ sở dữ liệu dạng bảng, dùng cho sổ đăng ký |
| **Xếp hạng lại (rerank)** | Bước chấm điểm lại các đoạn tìm được để chọn đoạn liên quan nhất |
| **Alias** | Tên gọi khác của cùng một thiết bị |
| **SI** | Hệ đơn vị chuẩn quốc tế (ví dụ áp suất về Pa), dùng để so sánh dải đo có đơn vị khác nhau |
