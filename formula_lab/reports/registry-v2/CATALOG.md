# 20 bộ tính mới trong registry

Nguồn: QTKĐ 1.190 / DPI 610. Đối chiếu kỹ thuật bằng XML gốc; chưa phải duyệt chuyên gia. F004 được giữ lại chờ kiểm tra điều kiện đo.

| ID nguồn | Công thức / đại lượng | Biểu thức chạy | Đầu vào và đơn vị |
|---|---|---|---|
| F001 | Bù áp suất do chênh cao cột chất lỏng | `rho*g*h` | rho (kg/m3); g (m/s2); h (m) |
| F005 | Sai số gồm độ lệch và độ không đảm bảo mở rộng | `abs(bias)+u` | bias (Pa); u (Pa) |
| F006 | Chỉ thị dự đoán theo quan hệ tuyến tính | `a+b*x` | a (Pa); b (1); x (Pa) |
| F007 | Trung bình các giá trị áp suất chuẩn | `mean(readings)` | readings[] (Pa) |
| F009 | Hệ số góc hồi quy bình phương tối thiểu | `slope(xs,ys)` | xs[] (Pa); ys[] (Pa) |
| F010 | Hệ số chặn hồi quy | `y_mean-b*x_mean` | y_mean (Pa); b (1); x_mean (Pa) |
| F016 | Độ không đảm bảo của áp suất chuẩn u_ch1 | `u/k` | u (Pa); k (1) |
| F017 | Độ không đảm bảo phương tiện đo khí quyển u_amb | `u/k` | u (Pa); k (1) |
| F018 | Độ không đảm bảo do độ ổn định chuẩn | `drift/sqrt(3)` | drift (Pa) |
| F019 | Độ không đảm bảo liên hợp của tổ hợp chuẩn | `sqrt(u_ch1**2+u_amb**2+u_stability**2)` | u_ch1 (Pa); u_amb (Pa); u_stability (Pa) |
| F022 | Thành phần độ không đảm bảo do diện tích hiệu dụng u2 | `p/area*ua/k` | p (Pa); area (m2); ua (m2); k (1) |
| F024 | Thành phần có dấu do hệ số giãn nở áp suất u3 | `-p**2*ulambda/k` | p (Pa); ulambda (1/Pa); k (1) |
| F026 | Thành phần độ không đảm bảo do khối lượng u4 | `p/mass*um/k` | p (Pa); mass (kg); um (kg); k (1) |
| F031 | Thành phần độ không đảm bảo do chênh cao u9 | `rho*g*uh/k` | rho (kg/m3); g (m/s2); uh (m); k (1) |
| F033 | Tổng hợp mười thành phần chuẩn pít tông | `rss(components)` | components[] (Pa) |
| F034 | Độ phân giải theo phân bố tam giác | `r/sqrt(6)` | r (Pa) |
| F035 | Độ phân giải theo phân bố chữ nhật | `r/sqrt(3)` | r (Pa) |
| F036 | Độ lệch điểm không qua ba chu kỳ | `max(abs(x2-x1),abs(x4-x3),abs(x6-x5))` | x1 (Pa); x2 (Pa); x3 (Pa); x4 (Pa); x5 (Pa); x6 (Pa) |
| F037 | Độ không đảm bảo do độ lệch điểm không u_f0 | `f0/(2*sqrt(3))` | f0 (Pa) |
| F050 | Độ không đảm bảo đo mở rộng U_c | `k*uc` | k (1); uc (Pa) |

Với danh sách, n được lấy từ độ dài đầu vào. Hệ số góc yêu cầu ghép cặp đúng, cùng số phần tử và các X không trùng hết. Tổng hợp u1…u10 yêu cầu đúng 10 phần tử. Các trường áp suất có thể nhận Pa/kPa/MPa/bar; đầu vào chiều dài, diện tích, khối lượng và nghịch đảo áp suất có chuyển đổi theo schema.

Các điều kiện cụ thể và nhánh áp dụng được hiển thị bằng checkbox. Việc đánh dấu xác nhận không tự chứng minh điều kiện vật lý là đúng.
