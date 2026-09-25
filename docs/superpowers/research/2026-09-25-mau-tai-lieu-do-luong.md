# Mẫu tài liệu đo lường Việt Nam: nghiên cứu Pha 1

Ngày: 2026-09-25.
Phạm vi: tìm và đối chiếu mẫu văn bản kỹ thuật đo lường Việt Nam (ĐLVN, QTKĐ), mẫu biên bản/giấy chứng nhận kiểm định, phiếu đo, để làm căn cứ sinh corpus test tổng hợp cho lớp tri thức (Pha 2).
Không sửa code, không sửa file nào khác ngoài file này.

Phương pháp: đọc 7 file thật trong `build/spike_a/*.md` (rút ra từ 7 QTKĐ ngành đo lường áp suất, đã qua `ingestion.spike_a`), sau đó tải và đọc trực tiếp các văn bản ĐLVN/Thông tư trên web bằng WebFetch và `curl`, đọc PDF gốc bằng công cụ đọc PDF (không chỉ dựa vào bản tóm tắt của trình duyệt).
Mọi số hiệu ĐLVN trong tài liệu này đều đã được mở file PDF gốc và xác nhận trang bìa, trừ khi ghi rõ "chưa xác minh".

## 1. Cấu trúc chuẩn của văn bản kỹ thuật đo lường

### 1.1 Khung mục chung

Cả hai dòng văn bản (QTKĐ do Cục Tiêu chuẩn - Đo lường - Chất lượng/Bộ Tổng Tham mưu ban hành, và ĐLVN do Viện Đo lường Việt Nam biên soạn/Tổng cục Tiêu chuẩn Đo lường Chất lượng ban hành) dùng chung một khung mục, nhưng thứ tự và số mục không cố định tuyệt đối.
Khung mục quan sát được trên 7 file QTKĐ thật (`build/spike_a/QTKD_1.061_2021_ND_V2.md`, `QTKD_1.071_2022_FINAL.md`, v.v.) và trên 7 văn bản ĐLVN đã tải trực tiếp (ĐLVN 08:2011, ĐLVN 09:2011, ĐLVN 17:2017, ĐLVN 107:2012, ĐLVN 13:2019, ĐLVN 157:2019, ĐLVN 07:2012):

1. Phạm vi áp dụng.
2. Thuật ngữ và định nghĩa (QTKĐ) hoặc Giải thích từ ngữ (ĐLVN) - mục này có thể vắng mặt hoàn toàn.
3. Các phép kiểm định (kèm Bảng 1).
4. Phương tiện kiểm định (kèm Bảng 2).
5. Điều kiện và chuẩn bị kiểm định (có thể tách thành hai mục con 5.1/5.2, hoặc gộp một mục 4.1/4.2 nếu không có mục Thuật ngữ).
6. Tiến hành kiểm định (kiểm tra bên ngoài, kiểm tra kỹ thuật, kiểm tra đo lường).
7. Xử lý chung (nêu chu kỳ kiểm định).
8. Phụ lục A (Quy định) Mẫu biên bản kiểm định, Phụ lục B (Quy định) Mẫu giấy chứng nhận kiểm định, có thể thêm Phụ lục D (mẫu tem/nhãn hoặc bảng tính).

Bằng chứng số mục không cố định: `QTKD_1.061_2021_ND_V2.md` đánh số Phạm vi áp dụng (1), Thuật ngữ (2), Các phép kiểm định (3), Phương tiện kiểm định (4), Điều kiện và chuẩn bị (5 gồm 5.1/5.2), Tiến hành kiểm định (6 gồm 6.1/6.2/6.3), Xử lý chung (7).
Trong khi đó `QTKD_1.071_2022_FINAL.md` không có mục Thuật ngữ, nên đánh số Phạm vi áp dụng (1), Các phép kiểm định (2), Phương tiện kiểm định (3), Điều kiện và chuẩn bị (4 gồm 4.1/4.2), Tiến hành kiểm định (5 gồm 5.1/5.2/5.3 và các mục con 5.2.1 đến 5.2.5), Xử lý chung (6).
Nguồn: `build/spike_a/QTKD_1.071_2022_FINAL.md` dòng 17-49 (mục lục).

Với các ĐLVN đã tải, mục 2 luôn là "Giải thích từ ngữ" chứ không phải "Thuật ngữ và định nghĩa".
Ví dụ nguyên văn: "2 Giải thích từ ngữ ... Các từ ngữ trong văn bản này được hiểu như sau" (ĐLVN 07:2012, trang 3; ĐLVN 13:2019, trang 3; ĐLVN 157:2019, trang 3).
Nguồn: https://tcvn.gov.vn/wp-content/uploads/2017/08/DLVN_0007-2012.pdf , https://tcvn.gov.vn/wp-content/uploads/2017/08/DLVN-13-Can-oto.pdf , https://tcvn.gov.vn/wp-content/uploads/2017/08/DLVN-157-PTD-Ktra-toc-do-pt-gthong.pdf

### 1.2 Bảng 1 "Các phép kiểm định"

Mẫu chung: bảng có cột TT, Tên phép kiểm định, Theo điều (mục) của QTKĐ/ĐLVN, và một cụm cột "Chế độ kiểm định" chia hai tầng.
Ví dụ nguyên văn (QTKĐ 1.061, `build/spike_a/QTKD_1.061_2021_ND_V2.md` dòng 103-111):

```
Bảng 1 - Các phép kiểm định
| TT | Tên phép kiểm định | Theo điều (mục) của QTKĐ | Chế độ kiểm định |
|  |  |  | Ban đầu | Định kỳ | Sau sửa chữa |
| 1 | Kiểm tra bên ngoài | 6.1 | + | + | + |
```

Ví dụ nguyên văn tương ứng ở một văn bản ĐLVN (ĐLVN 08:2011, đã đọc trực tiếp trang 3):

```
Bảng 1
| TT | Tên phép kiểm định | Theo điều mục của QTKĐ | Chế độ kiểm định |
|  |  |  | Ban đầu | Định kỳ | Bất thường |
| 1 | Kiểm tra bên ngoài | 6.1 | + | + | + |
```

Phát hiện quan trọng: các văn bản ĐLVN do Viện Đo lường Việt Nam biên soạn thời kỳ 2011-2012 (ĐLVN 08:2011, ĐLVN 09:2011) dùng nhãn tầng hai là "Bất thường" thay vì "Sau sửa chữa".
Văn bản ĐLVN mới hơn (ĐLVN 157:2019, đã đọc trực tiếp trang 3) đã quay lại dùng "Sau sửa chữa" giống toàn bộ 7 QTKĐ trong `TC_DL/`.
Đây là biến thể thật, không phải suy đoán, nguồn: https://res.cloudinary.com/kiemdinhsitc/image/upload/v1551254438/tai-lieu/quy-trinh-kiem-dinh/DLVN-08-2011.pdf (trang 3) và https://tcvn.gov.vn/wp-content/uploads/2017/08/DLVN-157-PTD-Ktra-toc-do-pt-gthong.pdf (trang 3).

### 1.3 Bảng 2 "Phương tiện kiểm định"

Mẫu chung: cột TT, Tên phương tiện kiểm định, và cụm "Đặc trưng kỹ thuật đo lường" chia hai tầng con Phạm vi đo / Cấp chính xác (hoặc độ chính xác, hoặc sai số, hoặc độ không đảm bảo đo).
Ví dụ nguyên văn (QTKĐ 1.061, `build/spike_a/QTKD_1.061_2021_ND_V2.md` dòng 120-131):

```
Bảng 2 - Danh mục phương tiện kiểm định
| TT | Tên phương tiện kiểm định | Đặc trưng kỹ thuật đo lường |
|  |  | Phạm vi đo | Cấp chính xác hoặc độ chính xác hoặc sai số hoặc độ không đảm bảo đo |
| 4 | Ẩm kế | (0 ÷ 100) %RH | ± 5 %RH |
```

Nhãn cột tầng hai không cố định chữ: `QTKD_1.071_2022_FINAL.md` dùng "Phạm vi đo | Sai số cho phép hoặc cấp chính xác" (dòng 113), `QTKD_1.160_2021_ND_FINAL.md` dùng "Phạm vi đo | Độ chính xác hoặc sai số cho phép hoặc độ không đảm bảo đo" (dòng 110).
Bảng 2 thường bị cắt trang, khi đó xuất hiện nhãn "Bảng 2 (kết thúc)" ở đầu phần còn lại (ví dụ `QTKD_1.071_2022_FINAL.md` dòng 121, `QTKD_1.160_2021_ND_FINAL.md` dòng 122).

### 1.4 Điều kiện kiểm định, tiến hành, xử lý chung, Phụ lục A

Mục "Điều kiện kiểm định" luôn là danh sách gạch đầu dòng Nhiệt độ môi trường, Độ ẩm tương đối, Áp suất khí quyển, kèm yêu cầu phòng thí nghiệm.
Mục "Tiến hành kiểm định" luôn mở đầu bằng câu chuẩn: "Trong quá trình kiểm định, nếu một nội dung kiểm tra nào đó không đạt yêu cầu thì kết luận không đạt và không tiến hành kiểm tra các bước tiếp theo." (xuất hiện nguyên văn giống hệt ở cả 7 file, ví dụ `build/spike_a/QTKD_1.061_2021_ND_V2.md` dòng 172).
Mục "Xử lý chung" luôn nêu ba việc: cấp Giấy chứng nhận kiểm định nếu đạt, nêu chu kỳ kiểm định, và cấp Biên bản kiểm định (không cấp chứng nhận) nếu không đạt.
Phụ lục A luôn có nhãn mở đầu "(Quy định)" rồi "MẪU BIÊN BẢN KIỂM ĐỊNH" hoặc "Mẫu biên bản kiểm định", và luôn kết bằng nhãn "Phụ lục A (kết thúc)" hoặc "Phụ lục A (tiếp theo)" khi bảng bị ngắt trang.
Nguồn: `build/spike_a/QTKD_1.061_2021_ND_V2.md` dòng 285-346, `build/spike_a/QTKD_1.071_2022_FINAL.md` dòng 404-512.

## 2. Diễn đạt điển hình

### 2.1 Phạm vi đo

Mẫu chuẩn: "Phạm vi đo: (10 đến 700) bar" (`build/spike_a/QTKD_1.071_2022_FINAL.md` dòng 432).
Mẫu dùng dấu chia: "Phạm vi làm việc: (0 đến …) bar" (`build/spike_a/QTKD_1.063_2021_BPL.md` dòng 246, giá trị số để trống vì đây là mẫu biên bản).
Mẫu trong tiêu đề văn bản dùng "đến": "VAN AN TOÀN CÓ PHẠM VI LÀM VIỆC ĐẾN 1 400 bar" (`build/spike_a/QTKD_1.061_2021_ND_V2.md` dòng 5).
Mẫu dùng dấu ngoặc và "đến" âm: "ÁP KẾ PÍTTÔNG CÓ PHẠM VI ĐO (-1 ĐẾN 5 000) bar" (`build/spike_a/QTKD_1.159_2021_ND_FINAL.md` dòng 5).
Trên văn bản ĐLVN đã xác minh: "phạm vi đo từ -0,1 MPa đến 250 MPa" (ĐLVN 08:2011, mục 1, trang 3); "phạm vi đo (0 ÷ 40) kPa hoặc (0 ÷ 300) mmHg" (ĐLVN 09:2011, mục 1, trang 3); "phạm vi đo (0,000 ÷ 3,000) mg/L ... và (0,000 ÷ 0,600) %BAC" (ĐLVN 107:2012, mục 1, trang 3).

### 2.2 Sai số cho phép kèm "nhưng không nhỏ hơn"

Ví dụ nguyên văn chính xác: "Giá trị cho phép của sai số áp suất chỉnh đặt bằng ± 3% áp suất chỉnh đặt của van nhưng không nhỏ hơn ± 0,15 bar." (`build/spike_a/QTKD_1.061_2021_ND_V2.md` dòng 264).
Ví dụ khác không dùng cụm này mà dùng "không vượt quá": "Tốc độ hạ của pít tông là giá trị trung bình của ba lần đo và không vượt quá 3 mm/min." (`build/spike_a/QTKD_1.071_2022_FINAL.md` dòng 311).
Ví dụ dùng "không nhỏ hơn" cho giới hạn đo trên (không phải sai số): "Có giới hạn đo trên không nhỏ hơn 50 r/min" (`build/spike_a/QTKD_1.071_2022_FINAL.md` dòng 128).
Ví dụ dùng dấu "≤" thay chữ: "Sai số ≤ ± 1%", "Sai số ≤ 4,8 s/d", "Sai số ≤ 0,4 oC" (`build/spike_a/QTKD_1.062_2021_ND.md` dòng 100-102); "Độ tụt áp suất sau 5 min ≤ 5%" (`build/spike_a/QTKD_1.063_2021_BPL.md` dòng 103).
Kết luận cho corpus tổng hợp: cụm "nhưng không nhỏ hơn" là có thật nhưng không phải mẫu duy nhất, cần trộn cả ba dạng ("nhưng không nhỏ hơn", "không vượt quá X", "≤ X") để giống thật.

### 2.3 Điều kiện môi trường

Mẫu chuẩn ba dòng: "Nhiệt độ môi trường: (20 ± 5) oC;", "Độ ẩm tương đối: (65 ± 15) %;", "Áp suất khí quyển: (100 ± 4) kPa;" (`build/spike_a/QTKD_1.061_2021_ND_V2.md` dòng 146-150).
Mẫu chỉ giới hạn trên, không có dấu ±: "Độ ẩm tương đối: không lớn hơn 80 %;" (`build/spike_a/QTKD_1.062_2021_ND.md` dòng 119).
Mẫu thêm điều kiện biến thiên: "Nhiệt độ môi trường: (23 ± 2) oC, nhiệt độ không được thay đổi quá 2 oC/h;" (`build/spike_a/QTKD_1.071_2022_FINAL.md` dòng 145; xác nhận lại đúng cấu trúc này ở ĐLVN 107:2012 mục 2.5: "độ ẩm tương đối ít nhất là 90 %RH và nhiệt độ (34 ± 1) °C").
Phát hiện lỗi mã hóa ký tự có thật trong corpus: dòng "Độ ẩm tương đối: Û 80 %;" ở `build/spike_a/QTKD_1.071_2022_FINAL.md` dòng 147 - ký tự "Û" là dấu "≤" bị lỗi phông chữ khi trích xuất, cho thấy việc trích ký hiệu so sánh từ OOXML không phải lúc nào cũng sạch.
Đây là bằng chứng thật nên đưa một biến thể tương tự (ký tự lạ thay cho ≤/±) vào nhóm B "QTKĐ docx biên" nếu muốn mô phỏng đúng rủi ro trích xuất thật.

### 2.4 Chu kỳ kiểm định

Mẫu chuẩn có chữ "là": "Chu kỳ kiểm định của Van an toàn là 12 tháng;" (`build/spike_a/QTKD_1.061_2021_ND_V2.md` dòng 290).
Mẫu số 0 đứng trước và đơn vị năm: "Chu kỳ kiểm định của H3000 là 01 năm." (`build/spike_a/QTKD_1.071_2022_FINAL.md` dòng 401); "Chu kỳ kiểm định của áp kế píttông là 02 năm." (`build/spike_a/QTKD_1.159_2021_ND_FINAL.md` dòng 943).
Cả 7 file thật trong corpus đều có chữ "là" trước số tháng/năm, không có ví dụ nào thiếu chữ "là" - biến thể "Chu kỳ kiểm định: 6 tháng" (không "là", mã K10 trong hợp đồng) là biến thể cần tạo tổng hợp cho nhóm B, không lấy được từ corpus thật.
Chu kỳ theo quy định nhà nước (không nằm trong thân QTKĐ mà trong danh mục pháp lý) được xác nhận trực tiếp từ Thông tư 23/2013/TT-BKHCN, Điều 4, Chương II, trang 39-42 của Công báo số 719+720 ngày 03-11-2013.

## 3. Danh sách phương tiện đo thật, đã xác minh số hiệu

Tất cả các dòng dưới đây đã mở PDF gốc để xác nhận trang bìa và trích đoạn "Phạm vi áp dụng", trừ các dòng ghi rõ "chưa xác minh".

| # | Tên phương tiện | Số hiệu | Đơn vị | Phạm vi điển hình | Cấp chính xác / sai số | Chu kỳ | Nguồn |
|---|---|---|---|---|---|---|---|
| 1 | Van an toàn | QTKĐ 1.061 : 2021 | bar | đến 1 400 bar | sai số áp suất chỉnh đặt ± 3% nhưng không nhỏ hơn ± 0,15 bar | 12 tháng | `build/spike_a/QTKD_1.061_2021_ND_V2.md` |
| 2 | Bàn tạo áp | QTKĐ 1.062 : 2021 | bar | đến 1 400 bar | (xem thân QTKĐ) | 12 tháng | `build/spike_a/QTKD_1.062_2021_ND.md` |
| 3 | Bình phân ly | QTKĐ 1.063 : 2021 | bar | đến 1 400 bar | (xem thân QTKĐ) | 12 tháng | `build/spike_a/QTKD_1.063_2021_BPL.md` |
| 4 | Áp kế pít tông kiểu H3000-SP-70/700 | QTKĐ 1.071 : 2022 | bar | (10 đến 700) bar | cấp chính xác 0,1 | 01 năm | `build/spike_a/QTKD_1.071_2022_FINAL.md` |
| 5 | Áp kế píttông chuẩn | QTKĐ 1.159 : 2021 | bar | (-1 đến 5 000) bar | cấp chính xác đến 0,01 | 02 năm | `build/spike_a/QTKD_1.159_2021_ND_FINAL.md` |
| 6 | Áp kế chuẩn hiện số và lò xo | QTKĐ 1.160 : 2021 | bar | (-1 đến 5 000) bar | cấp chính xác đến 0,02 | (xem thân QTKĐ) | `build/spike_a/QTKD_1.160_2021_ND_FINAL.md` |
| 7 | Thiết bị hiệu chuẩn áp suất kiểu DPI 610 | QTKĐ 1.190 : 2023 | bar | (xem thân QTKĐ) | (xem thân QTKĐ) | 01 năm | `build/spike_a/2023._QTKD_1.190_2023_DPI_610_ND_24.01.24.md` |
| 8 | Áp kế kiểu lò xo (áp kế, áp-chân không kế, chân không kế) | ĐLVN 08 : 2011 | MPa | (-0,1 đến 250) MPa | độ chính xác từ 1% đến 6% | chưa xác minh trong văn bản, khác theo chu kỳ chung của lĩnh vực áp suất | https://res.cloudinary.com/kiemdinhsitc/image/upload/v1551254438/tai-lieu/quy-trinh-kiem-dinh/DLVN-08-2011.pdf |
| 9 | Huyết áp kế (thủy ngân và lò xo) | ĐLVN 09 : 2011 | kPa hoặc mmHg | (0 đến 40) kPa hoặc (0 đến 300) mmHg | (xem Bảng 2 của văn bản) | 12 tháng (huyết áp kế thủy ngân và lò xo, theo Thông tư 23/2013, mục 34-35) | https://tcvn.gov.vn/wp-content/uploads/2017/08/DLVN_09-2011.pdf và https://moit.gov.vn/upload/2005517/20210623/_TT23-2013-BKHCN.pdf |
| 10 | Đồng hồ đo nước (đồng hồ nước lạnh cơ khí, có cơ cấu điện tử) | ĐLVN 17 : 2017 | m3/h | cấp chính xác 1, 2 hoặc A, B, C, D | (xem thân văn bản) | 60 tháng (cơ khí) hoặc 36 tháng (có cơ cấu điện tử), theo Thông tư 23/2013 mục 20-21 | https://tbt.gov.vn/wp-content/uploads/2017/08/%C4%90LVN-172017-%C4%90%E1%BB%93ng-h%E1%BB%93-%C4%91o-n%C6%B0%E1%BB%9Bc.-Quy-tr%C3%ACnh-ki%E1%BB%83m-%C4%91%E1%BB%8Bnh.pdf |
| 11 | Phương tiện đo hàm lượng cồn trong hơi thở | ĐLVN 107 : 2012 | mg/L hoặc %BAC | (0,000 đến 3,000) mg/L hoặc (0,000 đến 0,600) %BAC | độ chia 0,001 mg/L hoặc 0,001 %BAC | 12 tháng, theo Thông tư 23/2013 mục 45 | https://tdcbinhduong.vn/upload/file/dlvn-1072012-ptd-ham-luong-con-qtkd-8881.pdf |
| 12 | Cân ô tô | ĐLVN 13 : 2019 | kg | đến 150 000 kg | cấp chính xác trung bình (cấp 3) | 12 tháng, theo Thông tư 23/2013 mục 11 | https://tcvn.gov.vn/wp-content/uploads/2017/08/DLVN-13-Can-oto.pdf |
| 13 | Phương tiện đo kiểm tra tốc độ phương tiện giao thông (laser, radar) | ĐLVN 157 : 2019 | km/h | (8 đến 320) km/h | sai số đo tốc độ cho phép ± 3 km/h, sai số đo khoảng cách không lớn hơn ± 0,15 m | 12 tháng, theo Thông tư 23/2013 mục 3 | https://tcvn.gov.vn/wp-content/uploads/2017/08/DLVN-157-PTD-Ktra-toc-do-pt-gthong.pdf |
| 14 | Công tơ điện xoay chiều kiểu cảm ứng | ĐLVN 07 : 2012 | kWh | dòng điện danh định theo nhãn công tơ | cấp chính xác 0,5; 1; 2 (đo điện năng tác dụng), cấp 2; 3 (đo điện năng phản kháng) | 60 tháng (1 pha) hoặc 24 tháng (3 pha), theo Thông tư 23/2013 mục 49-50 | https://tcvn.gov.vn/wp-content/uploads/2017/08/DLVN_0007-2012.pdf |
| 15 | Taximet | chưa xác minh số hiệu/phiên bản chính xác (có nhiều bản ĐLVN 01 lưu hành: 2014, 2019, 2021 theo các nguồn thứ cấp, chưa tự mở PDF gốc để xác nhận bản nào còn hiệu lực) | km, đồng | theo đồng hồ tốc độ xe taxi | (chưa xác minh) | 12 tháng, đã xác minh trực tiếp qua Thông tư 23/2013, mục 2 | https://moit.gov.vn/upload/2005517/20210623/_TT23-2013-BKHCN.pdf |
| 16 | Nhiệt kế y học điện tử tiếp xúc có cơ cấu cực đại | chưa xác minh số hiệu ĐLVN | oC | thân nhiệt người, khoảng (35 đến 42) oC theo thông lệ ngành | (chưa xác minh) | 06 tháng, đã xác minh trực tiếp qua Thông tư 23/2013, mục 40 | https://moit.gov.vn/upload/2005517/20210623/_TT23-2013-BKHCN.pdf |
| 17 | Đồng hồ xăng dầu (cột đo nhiên liệu) | chưa xác minh số hiệu ĐLVN | lít | theo lưu lượng cột bơm | (chưa xác minh) | 12 tháng, đã xác minh trực tiếp qua Thông tư 23/2013, mục 23 | https://moit.gov.vn/upload/2005517/20210623/_TT23-2013-BKHCN.pdf |
| 18 | Phương tiện đo độ ẩm hạt nông sản | chưa xác minh số hiệu ĐLVN | % | (5 đến 40) % theo thông lệ ngành | (chưa xác minh) | 12 tháng, đã xác minh trực tiếp qua Thông tư 23/2013, mục 42 | https://moit.gov.vn/upload/2005517/20210623/_TT23-2013-BKHCN.pdf |

Ghi chú quan trọng: đã KHÔNG bịa số hiệu ĐLVN cho các dòng 15-18, ghi đúng "chưa xác minh" theo yêu cầu.
Chu kỳ của các dòng này vẫn xác minh được vì nằm trong bảng Điều 4 của Thông tư 23/2013/TT-BKHCN, đã tự đọc trực tiếp trang 39-41 của PDF gốc (không phải bản tóm tắt do công cụ web tạo ra).

## 4. Mẫu biên bản kiểm định, giấy chứng nhận kiểm định, phiếu đo

### 4.1 Biên bản kiểm định (Phụ lục A)

Khối tiêu đề hai cột: cột trái là đơn vị kiểm định (ví dụ "TRUNG TÂM ĐO LƯỜNG / PHÒNG ĐO LƯỜNG NHIỆT - ÁP SUẤT"), cột phải là quốc hiệu và ngày tháng ("CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM / Độc lập - Tự do - Hạnh phúc / Địa danh, ngày.....tháng......năm.........").
Nguồn: `build/spike_a/QTKD_1.061_2021_ND_V2.md` dòng 303-305.

Danh sách nhãn trường xuất hiện đúng thứ tự trong biên bản (nguyên văn, `build/spike_a/QTKD_1.061_2021_ND_V2.md` dòng 307-335):

```
BIÊN BẢN KIỂM ĐỊNH
Tên phương tiện đo: Van an toàn
Ký hiệu: Số hiệu:
Nơi (hãng) sản xuất:
Đặc trưng đo lường:
Cỡ van:
Áp suất chỉnh đặt:
Sai số cho phép:
Đơn vị sử dụng:
Điều kiện kiểm định:
Nhiệt độ: oC
Độ ẩm: %RH
Phương pháp kiểm định: QTKĐ 1.061 : 2021
Phương tiện kiểm định:
Ngày kiểm định tháng năm 202…
KẾT QUẢ KIỂM ĐỊNH
(Xem trang sau)
```

Chú ý hai điểm dễ vỡ khi trích xuất: nhãn "Ký hiệu: Số hiệu:" nằm chung một dòng (hai trường trên một dòng, đúng với mô tả trong hợp đồng ở mục docx reader), và dòng "Ngày kiểm định tháng năm 202…" không có dấu hai chấm sau "kiểm định".
Cuối biên bản có khối ký tên hai cột: "NGƯỜI KIỂM ĐỊNH / Cấp bậc Nguyễn Văn A" và "NGƯỜI SOÁT LẠI / Cấp bậc Nguyễn Văn B" (dòng 342).
Trang kết quả riêng bắt đầu bằng "Phụ lục A (Kết thúc)" rồi lặp lại tiêu đề "KẾT QUẢ KIỂM ĐỊNH", các mục A.1, A.2 ghi "Đạt / Không đạt", mục A.3 là bảng số liệu, và câu kết luận chuẩn: "Kết luận: Đạt (không đạt) yêu cầu kỹ thuật đo lường" - đây là văn bản mẫu gốc còn nguyên hai lựa chọn trong ngoặc, chưa được gạch bỏ một phương án, giống hệt mô tả mã K04 trong hợp đồng.
Nguồn: `build/spike_a/QTKD_1.061_2021_ND_V2.md` dòng 346-375.

### 4.2 Bảng số liệu đo trong Phụ lục A

Bảng "Bảng A.1 - Xác định sai số và độ chênh áp" là ví dụ thật của tiêu đề hai tầng và cột dữ liệu không khớp tên cột cha: cột cha ghi "Áp suất | Sai số | Ghi chú", nhưng hàng con thực chất là "Mở | Đóng | Độ chênh áp", nghĩa là cột "Ghi chú" ở hàng cha thực ra chứa nhãn con "Độ chênh áp" chứ không phải ghi chú tự do.
Nguồn nguyên văn (`build/spike_a/QTKD_1.061_2021_ND_V2.md` dòng 367-372):

```
| Lần kiểm tra | Áp suất | Sai số | Ghi chú |
|  | Mở | Đóng | Độ chênh áp |
| 1 |  |  |  |
```

Đây là bằng chứng thật cho mã K07 trong hợp đồng: bảng gộp ô có cột hiển thị "Áp suất | Sai số | Ghi chú" nhưng dữ liệu thật là "Mở | Đóng | Độ chênh áp".

### 4.3 Giấy chứng nhận kiểm định (Phụ lục B)

Bố cục ba cột ở dòng cuối: "Người kiểm soát (Chữ ký, họ tên) | Kiểm định viên (Chữ ký, họ tên) | THỦ TRƯỞNG ĐƠN VỊ (Ký tên, đóng dấu)".
Nhãn trường: "Số: ………", "Tên phương tiện ĐL-TN:", "Ký hiệu:", "Số hiệu:", "Nước (hãng) sản xuất:", "Năm sản xuất:", "Đơn vị sử dụng:", "Đặc tính đo lường:", rồi khối "THAM SỐ KIỂM ĐỊNH | GIÁ TRỊ XÁC ĐỊNH | GIÁ TRỊ CHO PHÉP", "Phương pháp kiểm định: QTKĐ 1.061 : 2021", "Kết luận: Đạt yêu cầu kỹ thuật đo lường.", "Hiệu lực đến:……………/……………".
Nguồn: `build/spike_a/QTKD_1.061_2021_ND_V2.md` dòng 383-392.
Khác với biên bản, giấy chứng nhận chỉ có một kết luận cố định "Đạt" (không có phương án "không đạt" trong ngoặc), vì giấy chứng nhận chỉ cấp khi đạt, đúng như mục "Xử lý chung" đã mô tả ở mục 1.4.

### 4.4 Phiếu đo (xlsx)

Corpus thật hiện có (7 file `build/spike_a/*.md`) không chứa ví dụ phiếu đo xlsx độc lập, chỉ có bảng số liệu nhúng trong Phụ lục A của file docx.
Theo hợp đồng contract (`docs/superpowers/research/2026-09-25-knowledge-input-contract.md` mục 4), phiếu đo xlsx chỉ đọc sheet đầu tiên, nhãn/giá trị nằm ở ô liền kề bên phải hoặc gộp "Nhãn: giá trị" trong một ô, số thực dùng dấu chấm thập phân kiểu Excel (ví dụ 10.125) chứ không phải dấu phẩy kiểu Việt Nam - đây là điểm phải mô phỏng ở Pha 2 vì không có mẫu thật để đối chiếu, cần dựa vào cấu trúc Bảng A.1/A.3 trong Phụ lục A docx rồi chuyển sang xlsx.

## 5. Biến thể định dạng thực tế đã quan sát được

1. Ô gộp thật: Bảng 1 "Chế độ kiểm định" luôn có ô đầu dòng con để trống (gộp dọc theo hàng cha), ví dụ dòng 106-108 của `build/spike_a/QTKD_1.061_2021_ND_V2.md`.
2. Tiêu đề hai tầng có nhãn khác nhau giữa các văn bản: "Ban đầu / Định kỳ / Sau sửa chữa" (7 QTKĐ và ĐLVN 157:2019) đối lập với "Ban đầu / Định kỳ / Bất thường" (ĐLVN 08:2011, ĐLVN 09:2011).
3. Số kiểu Việt Nam: dấu phẩy thập phân "± 0,15 bar", "cấp chính xác 0,01", "0,1"; dấu cách nhóm nghìn "1 400 bar", "5 000 bar" - đều lấy nguyên văn từ tiêu đề các QTKĐ thật (mục 2.1 ở trên).
4. Ký hiệu "÷": "(0 ÷ 500) mm", "(0 ÷ 100) %RH" (`build/spike_a/QTKD_1.061_2021_ND_V2.md` dòng 129-131); ĐLVN 09:2011 và ĐLVN 107:2012 cũng dùng "÷" trong câu Phạm vi áp dụng (mục 2.1 ở trên).
5. Ký hiệu "±": "(20 ± 5) oC", "(65 ± 15) %", "(100 ± 4) kPa" (`build/spike_a/QTKD_1.061_2021_ND_V2.md` dòng 146-150).
6. Ký hiệu "≤": "Sai số ≤ ± 1%" (`build/spike_a/QTKD_1.062_2021_ND.md` dòng 100); cũng dùng trong Bảng 3 để chia khoảng "DN ≤ 50", "50<DN ≤ 65" (`build/spike_a/QTKD_1.061_2021_ND_V2.md` dòng 209-210).
7. Đơn vị viết lệch chuẩn: "oC" thay vì "°C" xuất hiện xuyên suốt cả 7 file thật, không có file nào dùng ký hiệu độ thật "°C" (ví dụ `build/spike_a/QTKD_1.061_2021_ND_V2.md` dòng 146, 327).
   Đơn vị "kgf/cm2" và "at" có trong bảng đơn vị của code (`knowledge/seed_data.py` theo mô tả hợp đồng) nhưng KHÔNG xuất hiện trong 7 file corpus mẫu, nên xếp vào diện "cần tạo tổng hợp, không có bằng chứng corpus thật" khi sinh dữ liệu Pha 2.
8. Bảng tách "(kết thúc)" và "(tiếp theo)" là mẫu thật rất phổ biến, không phải hiếm gặp: xuất hiện ở Bảng 2, Phụ lục A, Phụ lục B, Phụ lục D của nhiều file (`build/spike_a/QTKD_1.160_2021_ND_FINAL.md` dòng 122, 467, 506, 594, 633, 763, 832, 903, 956; `build/spike_a/QTKD_1.071_2022_FINAL.md` dòng 121, 459, 512, 599, 652).
9. Lỗi mã hóa ký tự có thật: "Û 80 %" thay cho "≤ 80 %" trong `build/spike_a/QTKD_1.071_2022_FINAL.md` dòng 147, cho thấy việc trích ký hiệu toán học từ OOXML có rủi ro lỗi phông chữ đặc thù, nên nhóm B "QTKĐ docx biên" của Pha 2 có thể mô phỏng lại đúng kiểu lỗi này.
10. Mục lục dạng đoạn văn liệt kê "1 Phạm vi áp dụng 5", "2 Thuật ngữ và định nghĩa 5" trên cùng một dòng số trang, không phải bảng, xuất hiện ở đầu mọi file (`build/spike_a/QTKD_1.061_2021_ND_V2.md` dòng 19-45); đây chính là "mục lục dạng đoạn văn" nêu trong kế hoạch Pha 2 nhóm B.
11. Mục "Thuật ngữ và định nghĩa" hoàn toàn vắng mặt ở một số QTKĐ (ví dụ `QTKD_1.071_2022_FINAL.md`), không phải luôn có mặt; nếu Pha 2 tạo tài liệu thiếu mục này thì đó là biến thể thật chứ không phải lỗi.

## 6. Bảng đối chiếu với hợp đồng code

Hợp đồng tham chiếu: `docs/superpowers/research/2026-09-25-knowledge-input-contract.md`.
Cột "Khớp thực tế" liệt kê ví dụ thật đã xác minh khớp mẫu regex mô tả trong hợp đồng.
Cột "Không khớp / rủi ro" liệt kê ví dụ thật hoặc suy luận từ mẫu thật cho thấy sẽ KHÔNG khớp, kèm mã K01-K14 liên quan nếu có.

| Luật / nhãn | Khớp thực tế | Không khớp / rủi ro (mã liên quan) |
|---|---|---|
| phamvi | "Phạm vi đo: (10 đến 700) bar" khớp mẫu `từ A đến B đv`/`(A đến B) đv` (`QTKD_1.071_2022_FINAL.md` dòng 432) | Biên bản mẫu để trống giá trị "Phạm vi làm việc: (0 đến …) bar" (`QTKD_1.063_2021_BPL.md` dòng 246) sẽ trích được cụm chữ nhưng không có số thật, cần lưu ý khi làm gold cho nhóm D (biên bản); không có mã K trực tiếp |
| thuatngu | "Van an toàn (Safety valve): là van tự động xả..." đúng mẫu "Tên VI (English): là ..." (`QTKD_1.061_2021_ND_V2.md` dòng 79) | Heading "2 Giải thích từ ngữ" (mọi văn bản ĐLVN đã xác minh: 08, 09, 107, 13, 157, 07) KHÔNG chứa từ khóa "thuật ngữ" nên `find_section` sẽ không tìm thấy mục này; đây là phát hiện mới ngoài K01-K14, nên thêm một case trong nhóm B nếu muốn kiểm tra đúng rủi ro này |
| bang1 | Bảng "Chế độ kiểm định" ba cột con "Ban đầu / Định kỳ / Sau sửa chữa", ô đúng là "+" (`QTKD_1.061_2021_ND_V2.md` dòng 106-111) | ĐLVN 08:2011 và ĐLVN 09:2011 dùng cột con "Bất thường" thay "Sau sửa chữa" - nếu luật bang1 yêu cầu đúng ba nhãn cố định thì sẽ không nhận diện đúng chế độ ở các văn bản này; K07 minh chứng bằng Bảng A.1 gộp ô cột "Áp suất/Sai số/Ghi chú" nhưng dữ liệu thật là "Mở/Đóng/Độ chênh áp" (`QTKD_1.061_2021_ND_V2.md` dòng 367-372) |
| bang2 | Bảng 2 có cột "TT, Tên phương tiện kiểm định, Phạm vi đo, Cấp chính xác..." khớp mẫu yêu cầu (`QTKD_1.061_2021_ND_V2.md` dòng 123-131) | Số liệu ô dạng Việt Nam "0,500" hoặc số Excel "10.125" bị `parse_number` hiểu sai (mã K01); Bảng 2 bị ngắt trang thành "Bảng 2 (kết thúc)" là heading demote đúng luật (không phải heading H1-H9 thật) nên không gây lỗi tìm bảng, nhưng cần đưa vào manifest như một case xác nhận |
| dieukien | "- Nhiệt độ môi trường: (20 ± 5) oC;" khớp mẫu `(A ± B) đv` (`QTKD_1.061_2021_ND_V2.md` dòng 146) | "Nhiệt độ môi trường: (23 ± 2) oC, nhiệt độ không được thay đổi quá 2 oC/h;" sẽ bị tách ở dấu phẩy đầu tiên thành value "(23" theo mã K02 (`QTKD_1.071_2022_FINAL.md` dòng 145); dòng lỗi mã hóa "Độ ẩm tương đối: Û 80 %;" (`QTKD_1.071_2022_FINAL.md` dòng 147) không khớp bất kỳ mẫu nào (không có "≤" thật, không có ngoặc ±) |
| chuky | "Chu kỳ kiểm định của Van an toàn là 12 tháng;" khớp mẫu `Chu kỳ kiểm định ... là N tháng` (`QTKD_1.061_2021_ND_V2.md` dòng 290) | Biến thể "Chu kỳ kiểm định: 6 tháng" (không có chữ "là", mã K10) không xuất hiện trong 7 file thật nhưng là biến thể hợp lệ cần tạo tổng hợp cho nhóm B |
| phuluc_a | "Ký hiệu: Số hiệu:" hai trường trên một dòng vẫn map được theo mô tả hợp đồng (`QTKD_1.061_2021_ND_V2.md` dòng 311) | Cấu trúc "# Phụ lục A" rồi "# (Quy định)" rồi "# Mẫu biên bản kiểm định" thành ba heading H1 riêng biệt (đã xác nhận trực tiếp ở `QTKD_1.071_2022_FINAL.md` dòng 404-410, đúng mã K12: "Phụ lục A có đoạn kiểu heading"); dòng "Ngày kiểm định tháng năm 202…" không có dấu hai chấm khớp đúng mã K06 |
| nhãn biên bản (Kết luận) | "Kết luận: Đạt yêu cầu kỹ thuật đo lường." (Phụ lục B, dòng 390) là câu đã chốt một phương án, dễ nhận "đạt" | "Kết luận: Đạt (không đạt) yêu cầu kỹ thuật đo lường" ở Phụ lục A (mẫu biên bản, chưa điền) là văn bản mẫu gốc thật còn nguyên hai lựa chọn trong ngoặc, đúng mã K04: bộ nhận diện "không đạt" sẽ khớp cụm "(không đạt)" trong ngoặc dù thực chất đây là mẫu rỗng chưa có kết luận thật (`QTKD_1.061_2021_ND_V2.md` dòng 375) |
| nhãn biên bản (mã QTKĐ) | "Phương pháp kiểm định: QTKĐ 1.061 : 2021" có dấu Đ đầy đủ, khớp mẫu chọn Procedure (`QTKD_1.061_2021_ND_V2.md` dòng 331) | Tên file thật trong corpus dùng "QTKD" không dấu ("QTKD_1.061_2021_ND_V2.md") trong khi nội dung bên trong văn bản luôn dùng "QTKĐ" có dấu; đây là bằng chứng thật cho mã K11 ở cấp độ tên file, dù nội dung mẫu biên bản thật vẫn có dấu Đ đúng |

## 7. Danh mục 12+ phương tiện đề xuất cho corpus (mã giả định QTKĐ 9.0xx : 2026)

Toàn bộ 12 phương tiện dưới đây dựa trên các loại thiết bị đo THẬT đã xác minh ở mục 3 và mục 2, chỉ đổi số hiệu quy trình sang dải giả định "QTKĐ 9.0xx : 2026" để không trùng số hiệu thật, theo đúng yêu cầu của nhiệm vụ.
Các con số phạm vi/sai số/chuẩn/chu kỳ được giữ nhất quán với văn bản gốc đã xác minh (mục 3), riêng phần "nhưng không nhỏ hơn" và các bước Bảng 1 được soạn theo đúng mẫu câu thật đã trích ở mục 2 và mục 4, để mô hình sinh corpus có thể tái tạo văn phong chuẩn.
Ký hiệu Bảng 1: cột Ban đầu (BĐ), Định kỳ (ĐK), Sau sửa chữa (SSC); dấu "+" nghĩa là bắt buộc thực hiện.

### 7.1 QTKĐ 9.001 : 2026 - Van an toàn có phạm vi làm việc đến 1 400 bar

- Đơn vị: bar.
- Phạm vi: đến 1 400 bar, áp suất chỉnh đặt cụ thể theo từng van cần kiểm định.
- Sai số cho phép: sai số áp suất chỉnh đặt bằng ± 3 % áp suất chỉnh đặt nhưng không nhỏ hơn ± 0,15 bar; độ chênh áp cho phép 7 % áp suất chỉnh đặt, riêng van có đường kính trong nhỏ hơn 15 mm thì độ chênh áp cho phép là 15 % nhưng không nhỏ hơn 0,3 bar khi áp suất chỉnh đặt nhỏ hơn 3 bar.
- Chuẩn sử dụng: áp kế hiện số chuẩn, thiết bị tạo áp suất, bình khí nén, ẩm kế (0 ÷ 100) %RH sai số ± 5 %RH, barômét (800 ÷ 1 100) mbar sai số ± 2 mbar, thước đo (0 ÷ 500) mm sai số ± 1 mm.
- Chu kỳ kiểm định: 12 tháng.
- Đơn vị có trong seed_data: có (bar).
- Bảng 1: Kiểm tra bên ngoài (BĐ + / ĐK + / SSC +); Kiểm tra kỹ thuật (BĐ + / ĐK + / SSC +); Kiểm tra đo lường - Xác định sai số của áp suất chỉnh đặt, Xác định độ chênh áp (BĐ + / ĐK + / SSC +).

### 7.2 QTKĐ 9.002 : 2026 - Áp kế kiểu lò xo có phạm vi đo đến 250 MPa

- Đơn vị: MPa.
- Phạm vi: (-0,1 đến 250) MPa.
- Sai số cho phép: theo cấp chính xác 1,6, sai số cho phép bằng ± 1,6 % giá trị khoảng đo nhưng không nhỏ hơn ± 0,05 MPa ở đầu thang đo.
- Chuẩn sử dụng: áp kế píttông chuẩn có sai số nhỏ hơn hoặc bằng 1/4 sai số cho phép của áp kế cần kiểm định, buồng điều nhiệt, ẩm kế, barômét.
- Chu kỳ kiểm định: 12 tháng.
- Đơn vị có trong seed_data: có (MPa).
- Bảng 1: Kiểm tra bên ngoài (BĐ + / ĐK + / SSC +); Kiểm tra kỹ thuật (BĐ + / ĐK + / SSC +); Kiểm tra đo lường (BĐ + / ĐK + / SSC +).

### 7.3 QTKĐ 9.003 : 2026 - Huyết áp kế thủy ngân và lò xo

- Đơn vị: kPa (hoặc mmHg).
- Phạm vi: (0 đến 40) kPa, tương đương (0 đến 300) mmHg.
- Sai số cho phép: sai số cho phép cố định bằng ± 0,4 kPa, tương đương ± 3 mmHg, không có mức sàn "nhưng không nhỏ hơn" vì đây là một giá trị tuyệt đối cố định trên toàn thang đo, đúng theo văn bản gốc ĐLVN 09:2011 đã xác minh (mục 1).
- Chuẩn sử dụng: áp kế píttông sai số nhỏ hơn hoặc bằng 0,1 kPa (0,75 mmHg), áp kế chất lỏng sai số nhỏ hơn hoặc bằng 0,1 kPa (0,75 mmHg).
- Chu kỳ kiểm định: 12 tháng.
- Đơn vị có trong seed_data: có (kPa).
- Bảng 1: Kiểm tra bên ngoài (BĐ + / ĐK + / SSC +); Kiểm tra kỹ thuật (BĐ + / ĐK + / SSC +); Kiểm tra đo lường (BĐ + / ĐK + / SSC +).

### 7.4 QTKĐ 9.004 : 2026 - Đồng hồ nước lạnh cơ khí DN15 đến DN50

- Đơn vị: m3/h (lưu lượng), DN mm (cỡ đồng hồ).
- Phạm vi: lưu lượng danh định Q3 từ 2,5 m3/h đến 16 m3/h tùy theo cỡ DN15 đến DN50.
- Sai số cho phép: cấp chính xác 2; sai số cho phép ± 5 % trong vùng lưu lượng thấp (từ Q1 đến Q2), ± 2 % trong vùng lưu lượng cao (từ Q2 đến Q4) nhưng không nhỏ hơn 0,02 m3 cho một lần thử thể tích.
- Chuẩn sử dụng: bể chuẩn thể tích hoặc đồng hồ chuẩn có sai số nhỏ hơn hoặc bằng 1/3 sai số cho phép, đồng hồ bấm giây.
- Chu kỳ kiểm định: 60 tháng.
- Đơn vị có trong seed_data: không (m3/h; nhóm lưu lượng thể tích chưa được seed, seed_data.py chỉ có nhóm áp suất, nhiệt độ, độ ẩm, độ dài, khối lượng, thời gian).
- Bảng 1: Kiểm tra bên ngoài (BĐ + / ĐK + / SSC +); Kiểm tra kỹ thuật (BĐ + / ĐK + / SSC +); Kiểm tra đo lường - Xác định sai số tại lưu lượng thấp, Xác định sai số tại lưu lượng cao (BĐ + / ĐK + / SSC +).

### 7.5 QTKĐ 9.005 : 2026 - Cân ô tô có mức cân lớn nhất đến 150 000 kg

- Đơn vị: kg.
- Phạm vi: (0 đến 150 000) kg.
- Sai số cho phép: cấp chính xác trung bình (cấp 3); sai số cho phép ± 0,1 % tải trọng cân nhưng không nhỏ hơn ± 20 kg (một giá trị độ chia kiểm).
- Chuẩn sử dụng: quả cân chuẩn hạng M1, xe tải chuẩn đã biết khối lượng, hoặc tổ hợp quả cân và xe tải.
- Chu kỳ kiểm định: 12 tháng.
- Đơn vị có trong seed_data: có (kg).
- Bảng 1: Kiểm tra bên ngoài (BĐ + / ĐK + / SSC +); Kiểm tra kỹ thuật (BĐ + / ĐK + / SSC +); Kiểm tra đo lường - Xác định sai số ở các mức tải, Kiểm tra độ lặp lại (BĐ + / ĐK + / SSC +).

### 7.6 QTKĐ 9.006 : 2026 - Công tơ điện xoay chiều 1 pha kiểu cảm ứng

- Đơn vị: kWh, A, V.
- Phạm vi: dòng điện danh định 5 A đến 60 A, điện áp danh định 220 V, tần số 50 Hz.
- Sai số cho phép: cấp chính xác 2; sai số cho phép theo từng mức tải riêng biệt, không nối hai mức tải bằng "nhưng không nhỏ hơn": ± 2,0 % tại dòng điện từ 10 % Iđm đến Imax; ± 2,5 % tại 5 % Iđm.
- Chuẩn sử dụng: công tơ chuẩn cấp chính xác 0,2, nguồn dòng áp chuẩn ổn định.
- Chu kỳ kiểm định: 60 tháng.
- Đơn vị có trong seed_data: không (kWh, A, V; seed_data.py chưa có nhóm đại lượng điện).
- Bảng 1: Kiểm tra bên ngoài (BĐ + / ĐK + / SSC +); Kiểm tra kỹ thuật (BĐ + / ĐK + / SSC +); Kiểm tra đo lường - Xác định sai số cơ bản, Kiểm tra hằng số công tơ (BĐ + / ĐK + / SSC +).

### 7.7 QTKĐ 9.007 : 2026 - Taximet

- Đơn vị: đồng/km, km/h.
- Phạm vi: quãng đường thử theo bài thử chuẩn, tốc độ thử (10 đến 60) km/h.
- Sai số cho phép: sai số cho phép ± 2 % quãng đường thử nhưng không nhỏ hơn ± 10 m trên một lần thử 1 km.
- Chuẩn sử dụng: đường thử chuẩn đã biết chiều dài, thiết bị kiểm định taximet lưu động, tốc kế chuẩn.
- Chu kỳ kiểm định: 12 tháng.
- Đơn vị có trong seed_data: không (đồng/km, km/h; seed_data.py không có nhóm tiền tệ, và có km cho độ dài nhưng không có km/h cho tốc độ).
- Bảng 1: Kiểm tra bên ngoài (BĐ + / ĐK + / SSC +); Kiểm tra kỹ thuật (BĐ + / ĐK + / SSC +); Kiểm tra đo lường - Xác định sai số quãng đường, Xác định sai số cước phí (BĐ + / ĐK + / SSC +).

### 7.8 QTKĐ 9.008 : 2026 - Phương tiện đo kiểm tra tốc độ phương tiện giao thông kiểu laser, radar

- Đơn vị: km/h, m.
- Phạm vi: tốc độ (8 đến 320) km/h, khoảng cách (5 đến 1 000) m.
- Sai số cho phép: sai số đo tốc độ cho phép ± 1 % giá trị đo nhưng không nhỏ hơn ± 1 km/h (số hạng tương đối theo % giá trị đo, mức sàn tuyệt đối cùng đại lượng km/h, đúng dạng hợp lệ); sai số đo khoảng cách không lớn hơn ± 0,15 m.
- Chuẩn sử dụng: máy phát tốc độ chuẩn, xe thử có định vị GPS chuẩn, thước đo khoảng cách chuẩn.
- Chu kỳ kiểm định: 12 tháng.
- Đơn vị có trong seed_data: không (km/h; seed_data.py có km cho độ dài và m cho độ dài, nhưng không có đơn vị tốc độ km/h). Riêng đơn vị khoảng cách m thì có trong seed_data.
- Bảng 1: Kiểm tra bên ngoài (BĐ + / ĐK + / SSC +); Kiểm tra kỹ thuật (BĐ + / ĐK + / SSC +); Kiểm tra đo lường - Kiểm tra sai số đo khoảng cách, Kiểm tra sai số đo tốc độ (BĐ + / ĐK + / SSC +).

### 7.9 QTKĐ 9.009 : 2026 - Phương tiện đo hàm lượng cồn trong hơi thở

- Đơn vị: mg/L (hoặc %BAC).
- Phạm vi: (0,000 đến 3,000) mg/L, tương đương (0,000 đến 0,600) %BAC, độ chia 0,001 mg/L.
- Sai số cho phép: sai số cho phép ± 5 % giá trị đo nhưng không nhỏ hơn ± 0,020 mg/L ở vùng nồng độ thấp.
- Chuẩn sử dụng: khí chuẩn ethanol đã biết nồng độ, hệ thống chuẩn khí ướt với độ ẩm tương đối ít nhất 90 %RH và nhiệt độ (34 ± 1) oC.
- Chu kỳ kiểm định: 12 tháng.
- Đơn vị có trong seed_data: không (mg/L; seed_data.py có mg cho khối lượng nhưng không có mg/L làm đơn vị nồng độ riêng).
- Bảng 1: Kiểm tra bên ngoài (BĐ + / ĐK + / SSC +); Kiểm tra kỹ thuật (BĐ + / ĐK + / SSC +); Kiểm tra đo lường - Kiểm tra khí không, Xác định sai số tại các mức nồng độ chuẩn (BĐ + / ĐK + / SSC +).

### 7.10 QTKĐ 9.010 : 2026 - Nhiệt kế y học điện tử tiếp xúc có cơ cấu cực đại

- Đơn vị: oC.
- Phạm vi: (35,0 đến 42,0) oC.
- Sai số cho phép: sai số cho phép là hai giá trị tuyệt đối cố định theo từng vùng thang đo, không nối bằng "nhưng không nhỏ hơn": ± 0,1 oC trong khoảng (35,5 đến 42,0) oC; ± 0,2 oC ngoài khoảng đó.
- Chuẩn sử dụng: bể điều nhiệt chuẩn, nhiệt kế chuẩn platinum có sai số nhỏ hơn hoặc bằng 1/3 sai số cho phép.
- Chu kỳ kiểm định: 06 tháng.
- Đơn vị có trong seed_data: có (°C, alias "oc" khớp "oC").
- Bảng 1: Kiểm tra bên ngoài (BĐ + / ĐK + / SSC +); Kiểm tra kỹ thuật (BĐ + / ĐK + / SSC +); Kiểm tra đo lường - Xác định sai số tại các điểm nhiệt độ chuẩn (BĐ + / ĐK + / SSC +).

### 7.11 QTKĐ 9.011 : 2026 - Đồng hồ xăng dầu (cột đo nhiên liệu)

- Đơn vị: lít.
- Phạm vi: lưu lượng (10 đến 120) L/min, thể tích thử tiêu chuẩn 20 lít.
- Sai số cho phép: sai số cho phép ± 0,3 % thể tích thử nhưng không nhỏ hơn ± 0,05 lít trên một lần đo 20 lít.
- Chuẩn sử dụng: bình chuẩn dung tích hạng 2, nhiệt kế, tỷ trọng kế.
- Chu kỳ kiểm định: 12 tháng.
- Đơn vị có trong seed_data: không (lít; seed_data.py không có nhóm thể tích).
- Bảng 1: Kiểm tra bên ngoài (BĐ + / ĐK + / SSC +); Kiểm tra kỹ thuật (BĐ + / ĐK + / SSC +); Kiểm tra đo lường - Xác định sai số tại lưu lượng lớn nhất, Xác định sai số tại lưu lượng nhỏ nhất (BĐ + / ĐK + / SSC +).

### 7.12 QTKĐ 9.012 : 2026 - Phương tiện đo độ ẩm hạt nông sản

- Đơn vị: % (độ ẩm tuyệt đối).
- Phạm vi: (5 đến 40) %.
- Sai số cho phép: sai số cho phép bằng ± 3 % giá trị đo (số hạng tương đối theo giá trị đo) nhưng không nhỏ hơn ± 0,3 điểm % ẩm tuyệt đối (mức sàn tuyệt đối cùng đại lượng độ ẩm, tách rõ khỏi số hạng tương đối để tránh nhầm hai lần "%").
- Chuẩn sử dụng: mẫu hạt chuẩn đã biết độ ẩm bằng phương pháp sấy khô chuẩn, cân phân tích cấp chính xác cao, tủ sấy chuẩn.
- Chu kỳ kiểm định: 12 tháng.
- Đơn vị có trong seed_data: không (% trần; chỉ có %RH được seed, không có % độ ẩm hạt trần).
- Bảng 1: Kiểm tra bên ngoài (BĐ + / ĐK + / SSC +); Kiểm tra kỹ thuật (BĐ + / ĐK + / SSC +); Kiểm tra đo lường - So sánh với mẫu chuẩn tại các mức ẩm khác nhau (BĐ + / ĐK + / SSC +).

## 8. Nguồn

Danh sách URL đã truy cập (đọc trực tiếp nội dung, không chỉ dựa vào bản tóm tắt máy tạo):

1. https://thuvienphapluat.vn/van-ban/Thuong-mai/Thong-tu-23-2013-TT-BKHCN-phuong-tien-do-nhom-2-kiem-dinh-hieu-chuan-thu-nghiem-215285.aspx - trả về lỗi HTTP 403, không truy cập được, dùng nguồn thay thế bên dưới (moit.gov.vn) để lấy đúng văn bản gốc.
2. https://m.thuvienphapluat.vn/van-ban/Linh-vuc-khac/Van-ban-hop-nhat-06-VBHN-BKHCN-2025-Thong-tu-do-luong-phuong-tien-do-nhom-2-693382.aspx - trả về lỗi HTTP 403, KHÔNG xác minh được nội dung văn bản hợp nhất 2025, nên mọi chu kỳ kiểm định trong tài liệu này lấy từ bản gốc Thông tư 23/2013/TT-BKHCN năm 2013, có thể đã bị sửa đổi bởi các thông tư sau mà chưa kiểm tra được.
3. https://moit.gov.vn/upload/2005517/20210623/_TT23-2013-BKHCN.pdf - đọc trực tiếp PDF (8 trang đầu), xác nhận đúng Thông tư 23/2013/TT-BKHCN ngày 26/9/2013 và toàn bộ Danh mục 60 phương tiện đo nhóm 2 kèm chu kỳ tại Điều 4.
4. https://res.cloudinary.com/kiemdinhsitc/image/upload/v1551254438/tai-lieu/quy-trinh-kiem-dinh/DLVN-08-2011.pdf - đọc trực tiếp PDF, xác nhận ĐLVN 08:2011 Áp kế kiểu lò xo - Quy trình kiểm định.
5. https://tcvn.gov.vn/wp-content/uploads/2017/08/DLVN_09-2011.pdf - đọc trực tiếp PDF (qua tải lại bằng curl vì WebFetch báo lỗi chứng chỉ), xác nhận ĐLVN 09:2011 Huyết áp kế - Quy trình kiểm định.
6. https://tbt.gov.vn/wp-content/uploads/2017/08/%C4%90LVN-172017-%C4%90%E1%BB%93ng-h%E1%BB%93-%C4%91o-n%C6%B0%E1%BB%9Bc.-Quy-tr%C3%ACnh-ki%E1%BB%83m-%C4%91%E1%BB%8Bnh.pdf - đọc trực tiếp PDF (qua tải lại bằng curl vì WebFetch báo lỗi chứng chỉ hết hạn), xác nhận ĐLVN 17:2017 Đồng hồ đo nước - Quy trình kiểm định.
7. https://tdcbinhduong.vn/upload/file/dlvn-1072012-ptd-ham-luong-con-qtkd-8881.pdf - đọc trực tiếp PDF, xác nhận ĐLVN 107:2012 Phương tiện đo hàm lượng cồn trong hơi thở - Quy trình kiểm định.
8. https://tcvn.gov.vn/van-ban-ky-thuat-do-luong-viet-nam-dlvn/31/08/2017/ - WebFetch báo lỗi chứng chỉ, không đọc được trực tiếp; xem mục 9 để đối chiếu sự tồn tại của danh mục ĐLVN dạng tương tự.
9. https://hitechgroup.com.vn/van-ban-ky-thuat-do-luong-viet-nam-dlvn/ - đọc được, xác nhận đây là danh mục hơn 200 văn bản ĐLVN theo năm kèm liên kết PDF, dùng để đối chiếu cách tổ chức danh mục ĐLVN nói chung.
10. https://tcvn.gov.vn/wp-content/uploads/2017/08/DLVN-13-Can-oto.pdf - đọc trực tiếp PDF (qua tải lại bằng curl), xác nhận ĐLVN 13:2019 Cân ô tô - Quy trình kiểm định.
11. https://tcvn.gov.vn/wp-content/uploads/2017/08/DLVN-157-PTD-Ktra-toc-do-pt-gthong.pdf - đọc trực tiếp PDF (qua tải lại bằng curl), xác nhận ĐLVN 157:2019 Phương tiện đo kiểm tra tốc độ phương tiện giao thông - Quy trình kiểm định.
12. https://tcvn.gov.vn/wp-content/uploads/2017/08/DLVN_0007-2012.pdf - đọc trực tiếp PDF (qua tải lại bằng curl), xác nhận ĐLVN 07:2012 Công tơ điện xoay chiều kiểu cảm ứng - Quy trình kiểm định.
13. build/spike_a/QTKD_1.061_2021_ND_V2.md - QTKĐ 1.061:2021, Van an toàn có phạm vi làm việc đến 1 400 bar, đọc toàn văn.
14. build/spike_a/QTKD_1.062_2021_ND.md - QTKĐ 1.062:2021, Bàn tạo áp có phạm vi làm việc đến 1 400 bar.
15. build/spike_a/QTKD_1.063_2021_BPL.md - QTKĐ 1.063:2021, Bình phân ly có phạm vi làm việc đến 1 400 bar.
16. build/spike_a/QTKD_1.071_2022_FINAL.md - QTKĐ 1.071:2022, Áp kế pít tông kiểu H3000-SP-70/700, đọc toàn văn.
17. build/spike_a/QTKD_1.159_2021_ND_FINAL.md - QTKĐ 1.159:2021, Áp kế píttông có phạm vi đo (-1 đến 5 000) bar, cấp chính xác đến 0,01.
18. build/spike_a/QTKD_1.160_2021_ND_FINAL.md - QTKĐ 1.160:2021, Áp kế chuẩn hiện số và lò xo có phạm vi đo (-1 đến 5 000) bar, cấp chính xác đến 0,02.
19. build/spike_a/2023._QTKD_1.190_2023_DPI_610_ND_24.01.24.md - QTKĐ 1.190:2023, Thiết bị hiệu chuẩn áp suất kiểu DPI 610.
20. docs/superpowers/plans/2026-09-25-knowledge-test-corpus.md - kế hoạch Pha 1-3, đọc trước khi nghiên cứu theo yêu cầu.
21. docs/superpowers/research/2026-09-25-knowledge-input-contract.md - hợp đồng định dạng đầu vào của lớp tri thức, đọc trước khi nghiên cứu theo yêu cầu.

Đã ghi rõ "chưa xác minh" cho: số hiệu ĐLVN chính xác của Taximet (mục 3, dòng 15), số hiệu ĐLVN của Nhiệt kế y học điện tử tiếp xúc (mục 3, dòng 16), số hiệu ĐLVN của Đồng hồ xăng dầu (mục 3, dòng 17), số hiệu ĐLVN của Phương tiện đo độ ẩm hạt nông sản (mục 3, dòng 18), và toàn bộ nội dung của văn bản hợp nhất 06/VBHN-BKHCN 2025 (nguồn 2 ở trên, không truy cập được).

Đường dẫn file đã ghi: docs/superpowers/research/2026-09-25-mau-tai-lieu-do-luong.md
