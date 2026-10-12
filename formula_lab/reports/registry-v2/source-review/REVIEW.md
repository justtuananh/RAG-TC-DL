# Đối chiếu kỹ thuật 20 định nghĩa mới

Đối chiếu bởi trợ lý trong phiên làm việc, dựa vào XML OMML và văn bản DOCX gốc. **Không phải chứng nhận hoặc phê duyệt của chuyên gia đo lường.** Chỉ dùng trong formula lab thử nghiệm.

Nguồn: `TC_DL/2023. QTKD 1.190 2023 DPI 610 ND 24.01.24.docx`, SHA-256 `0646012c8f3e44046865d38ee48db80eeb74a7e4e7e3c2f62a1cd6e0c27133ab`.

Chọn F001, F005, F006, F007, F009, F010, F016, F017, F018, F019, F022, F024, F026, F031, F033, F034, F035, F036, F037, F050. Mỗi công thức có XML nguyên gốc tại đây và context trong `data/v2/sources.json`. 20 định nghĩa theo ngữ cảnh; không phải 20 dạng đại số hoàn toàn khác nhau: F016/F017 cùng U/k nhưng khác phạm vi áp dụng, các phép tổng bình phương cũng có quan hệ.

Đã đối chiếu:

- F001: tích rho*g*h; Pa = kg/m³ × m/s² × m. h có dấu, xác nhận quy ước trước khi áp dụng.
- F004: đã đưa về chờ kiểm tra điều kiện áp dụng. Bảng 3 nêu 3 loạt chiều tăng + 3 loạt chiều giảm, trong khi đoạn ngay sau nói M1–M4 và thêm M5–M6 khi cần tái lặp. Biểu thức trung bình đọc được nhưng chưa tự chốt điều kiện đủ loạt đo. Bản catalog/UC trước rà soát được giữ trong `data/v2/pre-procedure-review`; không dùng các kết quả cũ để kết luận cho catalog cuối.
- F005: trị tuyệt đối độ lệch cộng U. Văn bản yêu cầu U với k=2 và P=95%; thêm xác nhận riêng, không mặc định các trường hợp U/k khác cũng có k=2.
- F006/F007/F009/F010: X,Y là áp suất chuẩn/chỉ thị cùng đơn vị. a có đơn vị áp suất, b không thứ nguyên. Dấu thanh ngang của giá trị trung bình trong OMML là U+0305; converter cũ xuất nhầm hat, đã sửa thành overline. Hệ số góc đối chiếu cấu trúc tử sum[(xi-xmean)(yi-ymean)] và mẫu sum[(xi-xmean)^2]. Hai danh sách cùng độ dài, ít nhất hai X khác nhau.
- F016/F017: U/k, U>=0, k>0 theo cùng chứng nhận. F017 chỉ áp dụng trường hợp chuẩn tương đối + đo khí quyển để kiểm định áp kế tuyệt đối.
- F018: drift/sqrt(3), drift là độ lớn từ thực nghiệm. Không tự suy ra drift từ dữ liệu thiếu.
- F019: căn tổng bình phương ba thành phần, xác nhận mô hình không cần số hạng tương quan. Xác nhận này là chính sách áp dụng của lab, không phải câu nguyên văn trong tài liệu.
- F022: p/A0 * UA0/k, A0>0, UA0>=0, cùng đơn vị diện tích.
- F024: **giữ dấu âm** -p²*Ulambda/k theo XML. Đặt tên là thành phần có dấu; không diễn giải kết quả âm như độ không đảm bảo tổng hợp âm. Ulambda có đơn vị nghịch đảo áp suất.
- F026: p/M * UM/k, M>0, UM>=0.
- F031: rho*g*Udh/k; Udh là độ lớn, tối đa 2 mm theo văn bản. Không nhầm 2 mm thành 2 m.
- F033: XML ghi u1²+u2²+…+u10². Mở rộng thành đúng 10 phần tử, giữ dấu từng thành phần trước khi bình phương. Chưa tự tính toàn bộ chuỗi u1...u10 từ chứng nhận.
- F034/F035: sqrt(6) với phân bố tam giác; sqrt(3) với phân bố chữ nhật. Bắt buộc chọn đúng nhánh và xác nhận cách xác định r theo loại chỉ thị/dao động.
- F036: max ba trị tuyệt đối của chênh lệch điểm 0, đúng cặp M2-M1, M4-M3, M6-M5. Converter đã sửa escape dấu ngoặc nhọn để biểu thức hiển thị KaTeX được.
- F037: f0/(2*sqrt(3)); XML mẫu số gồm số 2 nhân căn 3, không phải sqrt(6). f0 không âm và phải lấy đúng từ sáu loạt đọc theo F036.
- F050: k*uc với k>0, uc>=0. Nhập uc đã xác định riêng; không ghép công thức F049 còn mâu thuẫn.

Giữ lại chưa duyệt: F002 (nhiều hệ số và phạm vi), F003 (hệ số/đơn vị cần kiểm tra thêm), F011–F015 (các thành phần hồi quy, F014 không thấy số mũ bình phương trong nguồn), F040/F044 (max một hiệu chưa rõ), F046 (chỉ số và số chu kỳ), F049 (uc xuất hiện cả hai vế, mâu thuẫn ký hiệu). Không thay bằng công thức sách giáo khoa mà không đối chiếu nguồn.

Định nghĩa/runtime được ràng buộc bằng fingerprint card, SHA-256 DOCX và SHA-256 spec tại `data/v2/review_approvals.json`. Builder từ chối tái tạo khi nguồn hoặc định nghĩa thay đổi. Registry không lấy công thức do mô hình tự tạo để chạy.
