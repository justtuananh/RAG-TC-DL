# Đối chiếu kỹ thuật 21 định nghĩa bổ sung trên bảy DOCX

Ngày: 28/09/2026. Đối chiếu bởi trợ lý bằng XML OMML và ngữ cảnh DOCX gốc. **Chưa có phê duyệt chuyên gia đo lường; chỉ dùng thử nghiệm.** Không tự động duyệt công thức từ tài liệu minh hoạ.

Nguồn và SHA-256:

- QTKD 1.160 2021 ND FINAL.docx: `d31461da01922c798853b19291d07f076ff6e3b5962f3416e80a7993bcb8a6ed`.
- 2023. QTKD 1.190 2023 DPI 610 ND 24.01.24.docx: `0646012c8f3e44046865d38ee48db80eeb74a7e4e7e3c2f62a1cd6e0c27133ab`.

Mỗi XML lưu theo registry ID để tránh nhầm F008 của 1.160 (hệ số góc) với F008 của 1.190 (trung bình Y). `data/v3/sources.json` giữ ngữ cảnh định vị. Đã kiểm tra cấu trúc tử/mẫu, số mũ, dấu trung bình và cặp chỉ số; không suy diễn từ chuỗi văn bản mất định dạng.

| Nguồn / ID | Biểu thức và quyết định kỹ thuật |
|---|---|
| 1.160 F001 | `rho*g*h`; rho>0, g>0, h có dấu. Pa = kg/m³ × m/s² × m. Đọc đủ định nghĩa h tại 4.2.1; yêu cầu xác nhận quy ước dấu. |
| 1.160 F005 | `a+b*x`; Y là chỉ thị áp kế kiểm, X là chuẩn; a có đơn vị áp suất, b không thứ nguyên. |
| 1.160 F006 | `mean(readings)` cho X; n lấy từ danh sách 1–100 số, giới hạn 100 là chính sách lab. Không dùng nó thay trung bình các loạt đo trong F004. |
| 1.160 F007; 1.190 F008 | `mean(readings)` cho Y; đối chiếu dấu trung bình OMML. Hai nguồn có cùng dạng đại số nhưng giữ ID và hash riêng. |
| 1.160 F008 | Tử tổng tích độ lệch X/Y, mẫu tổng bình phương độ lệch X. Hai danh sách ghép cặp, n≥2 và có ít nhất hai X khác nhau; đơn vị đầu ra 1. |
| 1.160 F009 | `y_mean-b*x_mean`; các đại lượng từ cùng bộ hồi quy, cùng đơn vị áp suất. |
| 1.160 F033 | `r/sqrt(6)`; phân bố tam giác tại D.2.3.1. r≥0, chọn đúng cách xác định r theo loại chỉ thị và dao động. |
| 1.160 F034 | `r/sqrt(3)`; phân bố chữ nhật tại D.2.3.1. Không mặc định nhánh khi chỉ hỏi “độ phân giải”. |
| 1.190 F038 | `abs((x3_j-x3_0)-(x1_j-x1_0))`: độ lặp lại chiều tăng, cặp M3/M1. |
| 1.190 F039 | `abs((x4_j-x4_0)-(x2_j-x2_0))`: độ lặp lại chiều giảm, cặp M4/M2. |
| 1.190 F042 | `abs((x5_j-x5_0)-(x1_j-x1_0))`: độ tái lặp lại chiều tăng, cặp M5/M1. |
| 1.190 F043 | `abs((x6_j-x6_0)-(x2_j-x2_0))`: độ tái lặp lại chiều giảm, cặp M6/M2. |

Bốn định nghĩa cuối giữ trị tuyệt đối bao ngoài hai hiệu đã trừ điểm 0 của chính loạt đó. Chỉ thị áp suất có thể âm; không đặt min=0 lên số đọc. Yêu cầu cùng điểm j, cùng chiều đo và đúng loạt. Đầu ra là độ lệch từng chiều, **không phải độ không đảm bảo tổng hợp**, không đi qua F040/F044 đang nghi vấn. Chưa tính chuỗi F041/F045 hoặc F049.

Chưa mở 1.160 F002–F004, F010–F032, F035–F049 trong đợt này. Việc biểu thức có vẻ tương tự tài liệu khác không đủ để tự duyệt. Đặc biệt F013 thiếu số mũ, F039/F043 có `max` một hiệu và F048 có ký hiệu tự tham chiếu cần rà soát riêng.

Miền dữ liệu, yêu cầu ghép cặp và checkbox là ràng buộc thử nghiệm; checkbox không chứng minh điều kiện đo thực tế. Snapshot kỹ thuật pin hash DOCX, card, spec và nội dung điều kiện trong `data/v3/review_approvals.json`. Builder đọc và kiểm tra toàn bộ trước khi ghi, không tự thay manifest khi có sai khác.

## Bổ sung theo yêu cầu mở rộng trên cả bảy nguồn

Tám định nghĩa dưới đây được đối chiếu riêng. Sáu quy tắc từ lời văn dùng mã **Pxxx do lab đặt**, không gọi là phương trình OMML/OLE và không cộng vào độ phủ 174 lần xuất hiện phương trình cũ.

| Nguồn / ID | Căn cứ và quyết định |
|---|---|
| 1.061 P001 | Mục 6.2.2 ghi áp suất thử bằng 1,5 lần áp suất lớn nhất theo thiết kế → `1.5*pmax`. Chỉ trả mức thử, không kết luận chịu tải/độ kín. |
| 1.061 P002 | Mục 6.3.1 ghi ±3% áp suất chỉnh đặt, không nhỏ hơn ±0,15 bar → độ lớn giới hạn `max(0.03*pcd,15000)` Pa. Giữ phân biệt với sai số đo thực tế. |
| 1.062 P001 | Mục 5.2.1 và 5.2.2 nêu 1/10 giới hạn áp suất cho bơm phụ → `pmax/10`. Chỉ nhánh có bơm phụ. |
| 1.062 P002 | Mục 5.2.1 không tăng quá 20% giới hạn áp suất khi kiểm van bảo vệ bơm phụ → `0.2*pmax`. Đây là mức trần, không phải yêu cầu đạt mức này. |
| 1.062 P003 | Mục 5.3 quy định độ tụt áp sau 5 min không quá 5% giới hạn → `0.05*pmax`. Nhập độ lớn dương; không suy rộng thành nhánh tăng áp của chân không. |
| 1.063 P001 | Mục 5.3 quy định độ tụt áp bình phân ly trong 5 min không quá 5% → `0.05*pmax`. Giữ riêng điều kiện duy trì 15 min, điều chỉnh và lặp phép đo; không tự quyết định dấu công thức độ tụt áp trong lời văn. |
| 1.071 F013+F014+F015 | Đã xem bản DOCX xuất PDF bằng LibreOffice, trang PDF 10, số trang in 10. Ba phương trình xác nhận `((p-pc1)+(p-pc2))/2` bar. “Sai số tuyệt đối” là sai số có đơn vị, **vẫn giữ dấu**; không dùng `abs`. P đã hiệu chỉnh gia tốc. |
| 1.159 F031 | Đã xem bản DOCX xuất PDF, trang PDF 13, số trang in 14: `P_abs=P_s,i+mu`, cả hai đầu vào Pa. mu là áp suất dư trong buồng chân không, không phải áp suất khí quyển. Nhánh 5.2 yêu cầu dưới 10 Pa: `0 <= mu < 10`; P_s,i được xác định riêng, chưa bù chênh cao. |

Ảnh trang đã kiểm tra: `qtkd159-page14.png`, `qtkd071-page10.png`. Lưu XML đoạn/bảng gốc và WMF/OLE của từng phương trình; hash cả DOCX trong card/manifest. Các SHA-256 nguồn bổ sung:

- 1.061: `e015e7615952b6aa5b9e48772536adce395efe5409d378dcd2c7412d69e838f5`.
- 1.062: `f848b5ecf6c2efd64e968966e9b285329c23f1db97d8709a7ed2c4c312a85bc3`.
- 1.063: `88a6b7c26022b6985b3cd55392b6dacf8adfc156a46cec7b13dc5e228f09fe15`.
- 1.071: `7efe8f1f99d82d3dccca6c8197c69415242b4228963d15dc1af33b63ff5291fc`.
- 1.159: `8a86f0df5b45a9cd12a74578ed3fc67aabb0f8315ce43623605ee4f04c3c5eb0`.

Chưa kiểm tra lại hàng loạt công thức OLE còn lại; đặc biệt không tự điền mẫu số hoặc vế phải bị thiếu trong artifact cũ. Không tạo bản sao DOCX để làm tăng số nguồn độc lập.
