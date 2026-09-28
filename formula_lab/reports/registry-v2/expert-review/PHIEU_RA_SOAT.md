# Phiếu rà soát chuyên môn — registry v2

Ngày chuẩn bị: 28/09/2026. Trạng thái: **chờ chuyên gia**, 0/20 định nghĩa được phê duyệt chuyên môn trong bộ phiếu này.

Biểu thức, miền đầu vào và điều kiện dưới đây được chép từ triển khai để kiểm tra; không phải kết luận chuyên môn. Cần mở DOCX gốc và đọc đủ mục liên quan. Trích đoạn tự động có thể mất ký hiệu hoặc thiếu định nghĩa biến; ưu tiên DOCX hiển thị và XML OMML.

Mỗi phiếu cần người rà soát, ngày, vị trí nguồn, kết luận và lý do. Chọn: chấp nhận / cần sửa / không đủ căn cứ. Ghi rõ mọi đề xuất sửa cùng căn cứ. Phiếu này không tự cập nhật manifest phê duyệt kỹ thuật hay bật bộ tính.

Hash tham chiếu: [BASELINE.json](BASELINE.json). Điểm chưa triển khai: [PENDING.md](PENDING.md).

## F001 — Bù áp suất do chênh cao cột chất lỏng — QTKĐ 1.190 / DPI 610

- Registry ID: `dpi190_f001`; revision: `2`.
- Nguồn: [DOCX gốc](../../../../TC_DL/2023.%20QTKD%201.190%202023%20DPI%20610%20ND%2024.01.24.docx) — 4 Điều kiện và chuẩn bị kiểm định > 4.2 Chuẩn bị kiểm định > 4.2.1 Yêu cầu lắp đặt / F001.
- Bằng chứng: [XML OMML](../source-review/F001.xml).
- SHA-256 DOCX: `0646012c8f3e44046865d38ee48db80eeb74a7e4e7e3c2f62a1cd6e0c27133ab`.
- SHA-256 định nghĩa: `832a225659c82bb52a399ea0919f8c5d4c63d86e5b3625e13ef529dbfd707c62`.
- Biểu thức đang chạy: `rho*g*h`; đơn vị kết quả: `Pa`.

```latex
∆P_{0}=ρ×g×h (1)
```

### Biến và ràng buộc đang triển khai

| Biến | Ý nghĩa | Đơn vị | Ràng buộc |
|---|---|---|---|
| `rho` | Khối lượng riêng môi trường | `kg/m3` | `{"min": 0, "exclusive_min": true}` |
| `g` | Gia tốc trọng trường | `m/s2` | `{"min": 0, "exclusive_min": true}` |
| `h` | Chênh cao có dấu theo quy ước | `m` | `{"min": null, "exclusive_min": false}` |

### Điều kiện cần đối chiếu

- `height_sign`: Đã đối chiếu quy ước dấu chênh cao với vị trí chuẩn và thiết bị.

### Ngữ cảnh trích xuất để định vị

```text
- Khi lắp DPI 610 và chuẩn vào vị trí làm việc chú ý lắp ráp sao cho cùng nằm trên một độ cao.
Chú ý: Nếu có chênh lệch chiều cao cột chất lỏng thì phải tính bù áp suất theo công thức (1): 
∆P0=ρ×g×h                                                                                (1)
trong đó: 
ΔP0 là áp suất do chênh lệch chiều cao cột chất lỏng gây ra, Pa;
ρ là khối lượng riêng của môi trường truyền áp suất, kg/m3;
g là giá trị gia tốc tại nơi kiểm định, m/s2;
```

### Kết luận của chuyên gia

- Người rà soát / chuyên môn: ____________________
- Ngày và phiên bản nguồn đã mở: ____________________
- Vị trí nguồn đã kiểm tra (mục/trang/đoạn): ____________________
- Biểu thức, dấu, chỉ số và ký hiệu: ____________________
- Ý nghĩa biến, đơn vị và đổi đơn vị: ____________________
- Miền dữ liệu, số loạt đo, điều kiện vật lý và tương quan: ____________________
- Ca tính đối chứng độc lập và cách tính: ____________________
- Kết luận (chấp nhận / cần sửa / không đủ căn cứ): **chưa có**
- Căn cứ, nội dung cần sửa và giới hạn sử dụng: ____________________

## F005 — Sai số gồm độ lệch và độ không đảm bảo mở rộng — QTKĐ 1.190 / DPI 610

- Registry ID: `dpi190_f005`; revision: `2`.
- Nguồn: [DOCX gốc](../../../../TC_DL/2023.%20QTKD%201.190%202023%20DPI%20610%20ND%2024.01.24.docx) — 5 Tiến hành kiểm định > 5.3 Kiểm tra đo lường > 5.3.2 Xác định sai số / F005.
- Bằng chứng: [XML OMML](../source-review/F005.xml).
- SHA-256 DOCX: `0646012c8f3e44046865d38ee48db80eeb74a7e4e7e3c2f62a1cd6e0c27133ab`.
- SHA-256 định nghĩa: `eb4d5e1ecc5f3adc101abc59096b92377db4cfaf1cfc52a2cde647efd320f5d2`.
- Biểu thức đang chạy: `abs(bias)+u`; đơn vị kết quả: `Pa`.

```latex
∆P=\left| ρ \right|+U (5)
```

### Biến và ràng buộc đang triển khai

| Biến | Ý nghĩa | Đơn vị | Ràng buộc |
|---|---|---|---|
| `bias` | Độ lệch rho | `Pa` | `{"min": null, "exclusive_min": false}` |
| `u` | Độ không đảm bảo đo mở rộng U | `Pa` | `{"min": 0, "exclusive_min": false}` |

### Điều kiện cần đối chiếu

- `expanded_k2`: U nhập là độ không đảm bảo mở rộng với k=2, P=95% theo mục 5.3.2.

### Ngữ cảnh trích xuất để định vị

```text
Pc là giá trị áp suất đọc được trên AKC, Pa;
Sai số được xác định bằng công thức (5):
∆P=ρ+U                                                                      (5)
trong đó:
∆P là sai số, Pa;
U là độ không đảm bảo đo mở rộng (k = 2, P = 95 %), Pa.
Sai số của DPI 610 không được vượt quá sai số cơ bản cho phép.
```

### Kết luận của chuyên gia

- Người rà soát / chuyên môn: ____________________
- Ngày và phiên bản nguồn đã mở: ____________________
- Vị trí nguồn đã kiểm tra (mục/trang/đoạn): ____________________
- Biểu thức, dấu, chỉ số và ký hiệu: ____________________
- Ý nghĩa biến, đơn vị và đổi đơn vị: ____________________
- Miền dữ liệu, số loạt đo, điều kiện vật lý và tương quan: ____________________
- Ca tính đối chứng độc lập và cách tính: ____________________
- Kết luận (chấp nhận / cần sửa / không đủ căn cứ): **chưa có**
- Căn cứ, nội dung cần sửa và giới hạn sử dụng: ____________________

## F006 — Chỉ thị dự đoán theo quan hệ tuyến tính — QTKĐ 1.190 / DPI 610

- Registry ID: `dpi190_f006`; revision: `2`.
- Nguồn: [DOCX gốc](../../../../TC_DL/2023.%20QTKD%201.190%202023%20DPI%20610%20ND%2024.01.24.docx) — Đánh giá độ không đảm bảo đo / F006.
- Bằng chứng: [XML OMML](../source-review/F006.xml).
- SHA-256 DOCX: `0646012c8f3e44046865d38ee48db80eeb74a7e4e7e3c2f62a1cd6e0c27133ab`.
- SHA-256 định nghĩa: `fdc89493e3d0f1118e72136e49d5d3aa00648a9be41d1481700c4debb8a646b6`.
- Biểu thức đang chạy: `a+b*x`; đơn vị kết quả: `Pa`.

```latex
Y=a+b×X
```

### Biến và ràng buộc đang triển khai

| Biến | Ý nghĩa | Đơn vị | Ràng buộc |
|---|---|---|---|
| `a` | Hệ số chặn a | `Pa` | `{"min": null, "exclusive_min": false}` |
| `b` | Hệ số góc b | `1` | `{"min": null, "exclusive_min": false}` |
| `x` | Áp suất chuẩn X | `Pa` | `{"min": null, "exclusive_min": false}` |

### Điều kiện cần đối chiếu

- `linear_fit`: Hệ số và các giá trị trung bình lấy từ cùng bộ dữ liệu, cùng đơn vị áp suất.

### Ngữ cảnh trích xuất để định vị

```text
Lấy trục Y biểu thị tập hợp các giá trị chỉ thị trên áp kế kiểm (Yi), trục X biểu thị tập hợp các giá trị áp suất chỉ thị trên chuẩn đo lường (Xi), thì tập hợp các điểm đo sẽ là (Xi ,Yi), số lần đo (quan trắc) là n.
Vì X và Y có mối quan hệ tuyến tính nên công thức thể hiện mối tương quan là:
Y=a+b×X
Giá trị của hệ số a, b được tìm bằng phương pháp bình phương cực tiểu:
x=xiny=yinb=xi-xyi-yxi-x2a=y-b×x
D.2 Ước lượng độ không đảm bảo đo
D.2.1 Độ không đảm bảo đo kiểu A: ua
```

### Kết luận của chuyên gia

- Người rà soát / chuyên môn: ____________________
- Ngày và phiên bản nguồn đã mở: ____________________
- Vị trí nguồn đã kiểm tra (mục/trang/đoạn): ____________________
- Biểu thức, dấu, chỉ số và ký hiệu: ____________________
- Ý nghĩa biến, đơn vị và đổi đơn vị: ____________________
- Miền dữ liệu, số loạt đo, điều kiện vật lý và tương quan: ____________________
- Ca tính đối chứng độc lập và cách tính: ____________________
- Kết luận (chấp nhận / cần sửa / không đủ căn cứ): **chưa có**
- Căn cứ, nội dung cần sửa và giới hạn sử dụng: ____________________

## F007 — Trung bình các giá trị áp suất chuẩn — QTKĐ 1.190 / DPI 610

- Registry ID: `dpi190_f007`; revision: `2`.
- Nguồn: [DOCX gốc](../../../../TC_DL/2023.%20QTKD%201.190%202023%20DPI%20610%20ND%2024.01.24.docx) — Đánh giá độ không đảm bảo đo / F007.
- Bằng chứng: [XML OMML](../source-review/F007.xml).
- SHA-256 DOCX: `0646012c8f3e44046865d38ee48db80eeb74a7e4e7e3c2f62a1cd6e0c27133ab`.
- SHA-256 định nghĩa: `43abcdc45769f31e4db2c9ea13d0ee2d263646fee8b6edacb8e538cbce04e7fd`.
- Biểu thức đang chạy: `mean(readings)`; đơn vị kết quả: `Pa`.

```latex
\overline{x}=\frac{\sum{x_{i}}}{n}
```

### Biến và ràng buộc đang triển khai

| Biến | Ý nghĩa | Đơn vị | Ràng buộc |
|---|---|---|---|
| `readings` | Các giá trị X_i | `Pa` | `{"min": null, "exclusive_min": false, "kind": "series", "min_items": 1, "max_items": 100}` |

### Điều kiện cần đối chiếu

- `same_series`: Các giá trị thuộc cùng tập số liệu cần lấy trung bình.

### Ngữ cảnh trích xuất để định vị

```text
Y=a+b×X
Giá trị của hệ số a, b được tìm bằng phương pháp bình phương cực tiểu:
x=xiny=yinb=xi-xyi-yxi-x2a=y-b×x
D.2 Ước lượng độ không đảm bảo đo
D.2.1 Độ không đảm bảo đo kiểu A: ua
Dùng phương pháp bình phương cực tiểu để lập biểu thức tính toán độ không đảm bảo đo kiểu A
Độ không đảm bảo đo kiểu A tại điểm đo thứ i được tính theo công thức:
```

### Kết luận của chuyên gia

- Người rà soát / chuyên môn: ____________________
- Ngày và phiên bản nguồn đã mở: ____________________
- Vị trí nguồn đã kiểm tra (mục/trang/đoạn): ____________________
- Biểu thức, dấu, chỉ số và ký hiệu: ____________________
- Ý nghĩa biến, đơn vị và đổi đơn vị: ____________________
- Miền dữ liệu, số loạt đo, điều kiện vật lý và tương quan: ____________________
- Ca tính đối chứng độc lập và cách tính: ____________________
- Kết luận (chấp nhận / cần sửa / không đủ căn cứ): **chưa có**
- Căn cứ, nội dung cần sửa và giới hạn sử dụng: ____________________

## F009 — Hệ số góc hồi quy bình phương tối thiểu — QTKĐ 1.190 / DPI 610

- Registry ID: `dpi190_f009`; revision: `2`.
- Nguồn: [DOCX gốc](../../../../TC_DL/2023.%20QTKD%201.190%202023%20DPI%20610%20ND%2024.01.24.docx) — Đánh giá độ không đảm bảo đo / F009.
- Bằng chứng: [XML OMML](../source-review/F009.xml).
- SHA-256 DOCX: `0646012c8f3e44046865d38ee48db80eeb74a7e4e7e3c2f62a1cd6e0c27133ab`.
- SHA-256 định nghĩa: `b820035237c0d55cf2e7d3763f572b3ab0d5ba053df51316569377995398865c`.
- Biểu thức đang chạy: `slope(xs,ys)`; đơn vị kết quả: `1`.

```latex
b=\frac{\sum{\left( x_{i}-\overline{x} \right)\left( y_{i}-\overline{y} \right)}}{\sum{\left( x_{i}-\overline{x} \right)^{2}}}
```

### Biến và ràng buộc đang triển khai

| Biến | Ý nghĩa | Đơn vị | Ràng buộc |
|---|---|---|---|
| `xs` | Các áp suất chuẩn X_i | `Pa` | `{"min": null, "exclusive_min": false, "kind": "series", "min_items": 2, "max_items": 100}` |
| `ys` | Các chỉ thị Y_i tương ứng | `Pa` | `{"min": null, "exclusive_min": false, "kind": "series", "min_items": 2, "max_items": 100}` |

### Điều kiện cần đối chiếu

- `paired_readings`: Hai danh sách cùng số phần tử, ghép đúng từng cặp X_i/Y_i và có ít nhất hai X khác nhau.

### Ngữ cảnh trích xuất để định vị

```text
Y=a+b×X
Giá trị của hệ số a, b được tìm bằng phương pháp bình phương cực tiểu:
x=xiny=yinb=xi-xyi-yxi-x2a=y-b×x
D.2 Ước lượng độ không đảm bảo đo
D.2.1 Độ không đảm bảo đo kiểu A: ua
Dùng phương pháp bình phương cực tiểu để lập biểu thức tính toán độ không đảm bảo đo kiểu A
Độ không đảm bảo đo kiểu A tại điểm đo thứ i được tính theo công thức:
```

### Kết luận của chuyên gia

- Người rà soát / chuyên môn: ____________________
- Ngày và phiên bản nguồn đã mở: ____________________
- Vị trí nguồn đã kiểm tra (mục/trang/đoạn): ____________________
- Biểu thức, dấu, chỉ số và ký hiệu: ____________________
- Ý nghĩa biến, đơn vị và đổi đơn vị: ____________________
- Miền dữ liệu, số loạt đo, điều kiện vật lý và tương quan: ____________________
- Ca tính đối chứng độc lập và cách tính: ____________________
- Kết luận (chấp nhận / cần sửa / không đủ căn cứ): **chưa có**
- Căn cứ, nội dung cần sửa và giới hạn sử dụng: ____________________

## F010 — Hệ số chặn hồi quy — QTKĐ 1.190 / DPI 610

- Registry ID: `dpi190_f010`; revision: `2`.
- Nguồn: [DOCX gốc](../../../../TC_DL/2023.%20QTKD%201.190%202023%20DPI%20610%20ND%2024.01.24.docx) — Đánh giá độ không đảm bảo đo / F010.
- Bằng chứng: [XML OMML](../source-review/F010.xml).
- SHA-256 DOCX: `0646012c8f3e44046865d38ee48db80eeb74a7e4e7e3c2f62a1cd6e0c27133ab`.
- SHA-256 định nghĩa: `1fe1518b52dc201299ae1f34cb1a4a9753a9c6d652f351160cdc773a44d16079`.
- Biểu thức đang chạy: `y_mean-b*x_mean`; đơn vị kết quả: `Pa`.

```latex
a=\overline{y}-b×\overline{x}
```

### Biến và ràng buộc đang triển khai

| Biến | Ý nghĩa | Đơn vị | Ràng buộc |
|---|---|---|---|
| `y_mean` | Trung bình Y | `Pa` | `{"min": null, "exclusive_min": false}` |
| `b` | Hệ số góc b | `1` | `{"min": null, "exclusive_min": false}` |
| `x_mean` | Trung bình X | `Pa` | `{"min": null, "exclusive_min": false}` |

### Điều kiện cần đối chiếu

- `linear_fit`: Hệ số và các giá trị trung bình lấy từ cùng bộ dữ liệu, cùng đơn vị áp suất.

### Ngữ cảnh trích xuất để định vị

```text
Y=a+b×X
Giá trị của hệ số a, b được tìm bằng phương pháp bình phương cực tiểu:
x=xiny=yinb=xi-xyi-yxi-x2a=y-b×x
D.2 Ước lượng độ không đảm bảo đo
D.2.1 Độ không đảm bảo đo kiểu A: ua
Dùng phương pháp bình phương cực tiểu để lập biểu thức tính toán độ không đảm bảo đo kiểu A
Độ không đảm bảo đo kiểu A tại điểm đo thứ i được tính theo công thức:
```

### Kết luận của chuyên gia

- Người rà soát / chuyên môn: ____________________
- Ngày và phiên bản nguồn đã mở: ____________________
- Vị trí nguồn đã kiểm tra (mục/trang/đoạn): ____________________
- Biểu thức, dấu, chỉ số và ký hiệu: ____________________
- Ý nghĩa biến, đơn vị và đổi đơn vị: ____________________
- Miền dữ liệu, số loạt đo, điều kiện vật lý và tương quan: ____________________
- Ca tính đối chứng độc lập và cách tính: ____________________
- Kết luận (chấp nhận / cần sửa / không đủ căn cứ): **chưa có**
- Căn cứ, nội dung cần sửa và giới hạn sử dụng: ____________________

## F016 — Độ không đảm bảo của áp suất chuẩn u_ch1 — QTKĐ 1.190 / DPI 610

- Registry ID: `dpi190_f016`; revision: `2`.
- Nguồn: [DOCX gốc](../../../../TC_DL/2023.%20QTKD%201.190%202023%20DPI%20610%20ND%2024.01.24.docx) — Đánh giá độ không đảm bảo đo / F016.
- Bằng chứng: [XML OMML](../source-review/F016.xml).
- SHA-256 DOCX: `0646012c8f3e44046865d38ee48db80eeb74a7e4e7e3c2f62a1cd6e0c27133ab`.
- SHA-256 định nghĩa: `233f7230056f871b82e44be9808e1de64951cdf3f8853e38df6d3c06b1a74b3e`.
- Biểu thức đang chạy: `u/k`; đơn vị kết quả: `Pa`.

```latex
u_{ch1}=\frac{U_{ch1}}{k}
```

### Biến và ràng buộc đang triển khai

| Biến | Ý nghĩa | Đơn vị | Ràng buộc |
|---|---|---|---|
| `u` | U_ch1 từ chứng nhận | `Pa` | `{"min": 0, "exclusive_min": false}` |
| `k` | Hệ số phủ k theo chứng nhận | `1` | `{"min": 0, "exclusive_min": true}` |

### Điều kiện cần đối chiếu

- `certificate`: U và k lấy từ cùng chứng nhận hiệu chuẩn; không tự mặc định k=2.

### Ngữ cảnh trích xuất để định vị

```text
- Độ không đảm bảo đo của áp suất chuẩn: uch1
Thành phần này được lấy trong giấy chứng nhận hiệu chuẩn, tính từ độ không đảm bảo đo mở rộng Uch1, tính theo công thức:
uch1=Uch1k
 - Độ không đảm bảo đo của phương tiện đo áp suất khí quyển: uamb
Áp dụng khi sử dụng chuẩn đo áp suất tương đối và thiết bị đo áp suất khí quyển (Bảng 2) để kiểm định các áp kế đo áp suất tuyệt đối. Thành phần này được lấy trong giấy chứng nhận hiệu chuẩn, tính từ độ không đảm bảo đo mở rộng Uamb, tính theo công thức:
uamb=Uambk
- Độ không đảm bảo đo do độ ổn định của chuẩn: ustability
```

### Kết luận của chuyên gia

- Người rà soát / chuyên môn: ____________________
- Ngày và phiên bản nguồn đã mở: ____________________
- Vị trí nguồn đã kiểm tra (mục/trang/đoạn): ____________________
- Biểu thức, dấu, chỉ số và ký hiệu: ____________________
- Ý nghĩa biến, đơn vị và đổi đơn vị: ____________________
- Miền dữ liệu, số loạt đo, điều kiện vật lý và tương quan: ____________________
- Ca tính đối chứng độc lập và cách tính: ____________________
- Kết luận (chấp nhận / cần sửa / không đủ căn cứ): **chưa có**
- Căn cứ, nội dung cần sửa và giới hạn sử dụng: ____________________

## F017 — Độ không đảm bảo phương tiện đo khí quyển u_amb — QTKĐ 1.190 / DPI 610

- Registry ID: `dpi190_f017`; revision: `2`.
- Nguồn: [DOCX gốc](../../../../TC_DL/2023.%20QTKD%201.190%202023%20DPI%20610%20ND%2024.01.24.docx) — Đánh giá độ không đảm bảo đo / F017.
- Bằng chứng: [XML OMML](../source-review/F017.xml).
- SHA-256 DOCX: `0646012c8f3e44046865d38ee48db80eeb74a7e4e7e3c2f62a1cd6e0c27133ab`.
- SHA-256 định nghĩa: `d180eb26c7bd423b25ed11fef21e3e581b6d5f10571fce876d7810b4ffe57e41`.
- Biểu thức đang chạy: `u/k`; đơn vị kết quả: `Pa`.

```latex
u_{amb}=\frac{U_{amb}}{k}
```

### Biến và ràng buộc đang triển khai

| Biến | Ý nghĩa | Đơn vị | Ràng buộc |
|---|---|---|---|
| `u` | U_amb từ chứng nhận | `Pa` | `{"min": 0, "exclusive_min": false}` |
| `k` | Hệ số phủ k theo chứng nhận | `1` | `{"min": 0, "exclusive_min": true}` |

### Điều kiện cần đối chiếu

- `certificate`: U và k lấy từ cùng chứng nhận hiệu chuẩn; không tự mặc định k=2.
- `absolute_from_gauge`: Đang dùng chuẩn áp suất tương đối cùng thiết bị đo khí quyển để kiểm định áp kế tuyệt đối.

### Ngữ cảnh trích xuất để định vị

```text
 - Độ không đảm bảo đo của phương tiện đo áp suất khí quyển: uamb
Áp dụng khi sử dụng chuẩn đo áp suất tương đối và thiết bị đo áp suất khí quyển (Bảng 2) để kiểm định các áp kế đo áp suất tuyệt đối. Thành phần này được lấy trong giấy chứng nhận hiệu chuẩn, tính từ độ không đảm bảo đo mở rộng Uamb, tính theo công thức:
uamb=Uambk
- Độ không đảm bảo đo do độ ổn định của chuẩn: ustability
Thành phần này lấy từ thực nghiệm để có được độ tái lặp lại của chuẩn:
ustability=driffvalue3
- Độ không đảm bảo đo chuẩn liên hợp của tổ hợp chuẩn: uch
```

### Kết luận của chuyên gia

- Người rà soát / chuyên môn: ____________________
- Ngày và phiên bản nguồn đã mở: ____________________
- Vị trí nguồn đã kiểm tra (mục/trang/đoạn): ____________________
- Biểu thức, dấu, chỉ số và ký hiệu: ____________________
- Ý nghĩa biến, đơn vị và đổi đơn vị: ____________________
- Miền dữ liệu, số loạt đo, điều kiện vật lý và tương quan: ____________________
- Ca tính đối chứng độc lập và cách tính: ____________________
- Kết luận (chấp nhận / cần sửa / không đủ căn cứ): **chưa có**
- Căn cứ, nội dung cần sửa và giới hạn sử dụng: ____________________

## F018 — Độ không đảm bảo do độ ổn định chuẩn — QTKĐ 1.190 / DPI 610

- Registry ID: `dpi190_f018`; revision: `2`.
- Nguồn: [DOCX gốc](../../../../TC_DL/2023.%20QTKD%201.190%202023%20DPI%20610%20ND%2024.01.24.docx) — Đánh giá độ không đảm bảo đo / F018.
- Bằng chứng: [XML OMML](../source-review/F018.xml).
- SHA-256 DOCX: `0646012c8f3e44046865d38ee48db80eeb74a7e4e7e3c2f62a1cd6e0c27133ab`.
- SHA-256 định nghĩa: `080b0531edeab0b00d7ba7fa9e0b52664cdca68ff5fa82ea2a9a77659cf7b333`.
- Biểu thức đang chạy: `drift/sqrt(3)`; đơn vị kết quả: `Pa`.

```latex
u_{stability}=\frac{driffvalue}{\sqrt{3}}
```

### Biến và ràng buộc đang triển khai

| Biến | Ý nghĩa | Đơn vị | Ràng buộc |
|---|---|---|---|
| `drift` | Độ trôi driffvalue từ thực nghiệm | `Pa` | `{"min": 0, "exclusive_min": false}` |

### Điều kiện cần đối chiếu

- `experimental_drift`: Giá trị độ trôi được xác định từ thực nghiệm phù hợp.

### Ngữ cảnh trích xuất để định vị

```text
- Độ không đảm bảo đo do độ ổn định của chuẩn: ustability
Thành phần này lấy từ thực nghiệm để có được độ tái lặp lại của chuẩn:
ustability=driffvalue3
- Độ không đảm bảo đo chuẩn liên hợp của tổ hợp chuẩn: uch
uch=uch12+uamb2+ustability2
D.2.2.2 Độ không đảm bảo đo của chuẩn đối với trường hợp chuẩn được sử dụng là áp kế pít tông chuẩn, các thành phần độ không đảm bảo đo của chuẩn bao gồm:
- Độ không đảm bảo đo do độ ổn định của giá trị áp suất chuẩn: u1
```

### Kết luận của chuyên gia

- Người rà soát / chuyên môn: ____________________
- Ngày và phiên bản nguồn đã mở: ____________________
- Vị trí nguồn đã kiểm tra (mục/trang/đoạn): ____________________
- Biểu thức, dấu, chỉ số và ký hiệu: ____________________
- Ý nghĩa biến, đơn vị và đổi đơn vị: ____________________
- Miền dữ liệu, số loạt đo, điều kiện vật lý và tương quan: ____________________
- Ca tính đối chứng độc lập và cách tính: ____________________
- Kết luận (chấp nhận / cần sửa / không đủ căn cứ): **chưa có**
- Căn cứ, nội dung cần sửa và giới hạn sử dụng: ____________________

## F019 — Độ không đảm bảo liên hợp của tổ hợp chuẩn — QTKĐ 1.190 / DPI 610

- Registry ID: `dpi190_f019`; revision: `2`.
- Nguồn: [DOCX gốc](../../../../TC_DL/2023.%20QTKD%201.190%202023%20DPI%20610%20ND%2024.01.24.docx) — Đánh giá độ không đảm bảo đo / F019.
- Bằng chứng: [XML OMML](../source-review/F019.xml).
- SHA-256 DOCX: `0646012c8f3e44046865d38ee48db80eeb74a7e4e7e3c2f62a1cd6e0c27133ab`.
- SHA-256 định nghĩa: `937069b106963939f7e06599d78d3ebcef86298e904c37e7197269a6fbaac9df`.
- Biểu thức đang chạy: `sqrt(u_ch1**2+u_amb**2+u_stability**2)`; đơn vị kết quả: `Pa`.

```latex
u_{ch}=\sqrt{u_{ch1}^{2}+u_{amb}^{2}+u_{stability}^{2}}
```

### Biến và ràng buộc đang triển khai

| Biến | Ý nghĩa | Đơn vị | Ràng buộc |
|---|---|---|---|
| `u_ch1` | u_ch1 | `Pa` | `{"min": 0, "exclusive_min": false}` |
| `u_amb` | u_amb | `Pa` | `{"min": 0, "exclusive_min": false}` |
| `u_stability` | u_stability | `Pa` | `{"min": 0, "exclusive_min": false}` |

### Điều kiện cần đối chiếu

- `rss_applicable`: Đã xác nhận mô hình cộng bình phương này áp dụng, không cần thêm số hạng tương quan.

### Ngữ cảnh trích xuất để định vị

```text
ustability=driffvalue3
- Độ không đảm bảo đo chuẩn liên hợp của tổ hợp chuẩn: uch
uch=uch12+uamb2+ustability2
D.2.2.2 Độ không đảm bảo đo của chuẩn đối với trường hợp chuẩn được sử dụng là áp kế pít tông chuẩn, các thành phần độ không đảm bảo đo của chuẩn bao gồm:
- Độ không đảm bảo đo do độ ổn định của giá trị áp suất chuẩn: u1
Được lấy từ giấy chứng nhận hiệu chuẩn hoặc lấy từ tính toán thực nghiệm cho từng điểm đo:
u1=a+b×p
```

### Kết luận của chuyên gia

- Người rà soát / chuyên môn: ____________________
- Ngày và phiên bản nguồn đã mở: ____________________
- Vị trí nguồn đã kiểm tra (mục/trang/đoạn): ____________________
- Biểu thức, dấu, chỉ số và ký hiệu: ____________________
- Ý nghĩa biến, đơn vị và đổi đơn vị: ____________________
- Miền dữ liệu, số loạt đo, điều kiện vật lý và tương quan: ____________________
- Ca tính đối chứng độc lập và cách tính: ____________________
- Kết luận (chấp nhận / cần sửa / không đủ căn cứ): **chưa có**
- Căn cứ, nội dung cần sửa và giới hạn sử dụng: ____________________

## F022 — Thành phần độ không đảm bảo do diện tích hiệu dụng u2 — QTKĐ 1.190 / DPI 610

- Registry ID: `dpi190_f022`; revision: `2`.
- Nguồn: [DOCX gốc](../../../../TC_DL/2023.%20QTKD%201.190%202023%20DPI%20610%20ND%2024.01.24.docx) — Đánh giá độ không đảm bảo đo / F022.
- Bằng chứng: [XML OMML](../source-review/F022.xml).
- SHA-256 DOCX: `0646012c8f3e44046865d38ee48db80eeb74a7e4e7e3c2f62a1cd6e0c27133ab`.
- SHA-256 định nghĩa: `a28298c13b3cfe6898879d41c214e27db3aaea0351b0b7abf9bcb3eef67e6405`.
- Biểu thức đang chạy: `p/area*ua/k`; đơn vị kết quả: `Pa`.

```latex
u_{2}=\frac{p}{A_{0,c}}×\frac{U_{A_{0,c}}}{k}
```

### Biến và ràng buộc đang triển khai

| Biến | Ý nghĩa | Đơn vị | Ràng buộc |
|---|---|---|---|
| `p` | Áp suất p | `Pa` | `{"min": null, "exclusive_min": false}` |
| `area` | Diện tích hiệu dụng A_0,c | `m2` | `{"min": 0, "exclusive_min": true}` |
| `ua` | U_A0,c | `m2` | `{"min": 0, "exclusive_min": false}` |
| `k` | Hệ số phủ k theo chứng nhận | `1` | `{"min": 0, "exclusive_min": true}` |

### Điều kiện cần đối chiếu

- `certificate`: U và k lấy từ cùng chứng nhận hiệu chuẩn; không tự mặc định k=2.
- `piston_standard`: Chuẩn sử dụng là áp kế pít tông theo mục D.2.2.2.

### Ngữ cảnh trích xuất để định vị

```text
- Độ không đảm bảo đo của diện tích hiệu dụng: u2
Thành phần này được lấy trong giấy chứng nhận hiệu chuẩn, tính từ độ không đảm bảo đo mở rộng UA0,c, tính theo công thức:
u2=pA0,c×UA0,ck
- Độ không đảm bảo đo của hệ số dãn nở áp suất: u3
Thành phần này được lấy trong giấy chứng nhận hiệu chuẩn, tính từ độ không đảm bảo đo mở rộng Uλc, tính theo công thức:
u3=-p2×Uλck
Phụ lục D (tiếp theo)
```

### Kết luận của chuyên gia

- Người rà soát / chuyên môn: ____________________
- Ngày và phiên bản nguồn đã mở: ____________________
- Vị trí nguồn đã kiểm tra (mục/trang/đoạn): ____________________
- Biểu thức, dấu, chỉ số và ký hiệu: ____________________
- Ý nghĩa biến, đơn vị và đổi đơn vị: ____________________
- Miền dữ liệu, số loạt đo, điều kiện vật lý và tương quan: ____________________
- Ca tính đối chứng độc lập và cách tính: ____________________
- Kết luận (chấp nhận / cần sửa / không đủ căn cứ): **chưa có**
- Căn cứ, nội dung cần sửa và giới hạn sử dụng: ____________________

## F024 — Thành phần có dấu do hệ số giãn nở áp suất u3 — QTKĐ 1.190 / DPI 610

- Registry ID: `dpi190_f024`; revision: `2`.
- Nguồn: [DOCX gốc](../../../../TC_DL/2023.%20QTKD%201.190%202023%20DPI%20610%20ND%2024.01.24.docx) — Đánh giá độ không đảm bảo đo / F024.
- Bằng chứng: [XML OMML](../source-review/F024.xml).
- SHA-256 DOCX: `0646012c8f3e44046865d38ee48db80eeb74a7e4e7e3c2f62a1cd6e0c27133ab`.
- SHA-256 định nghĩa: `7ae7643bdb3e8cd0d3b982971695b613ef198765a1a8525c58155b965b99bab9`.
- Biểu thức đang chạy: `-p**2*ulambda/k`; đơn vị kết quả: `Pa`.

```latex
u_{3}=-p^{2}×\frac{U_{λ_{c}}}{k}
```

### Biến và ràng buộc đang triển khai

| Biến | Ý nghĩa | Đơn vị | Ràng buộc |
|---|---|---|---|
| `p` | Áp suất p | `Pa` | `{"min": null, "exclusive_min": false}` |
| `ulambda` | U_lambda,c | `1/Pa` | `{"min": 0, "exclusive_min": false}` |
| `k` | Hệ số phủ k theo chứng nhận | `1` | `{"min": 0, "exclusive_min": true}` |

### Điều kiện cần đối chiếu

- `certificate`: U và k lấy từ cùng chứng nhận hiệu chuẩn; không tự mặc định k=2.
- `piston_standard`: Chuẩn sử dụng là áp kế pít tông theo mục D.2.2.2.
- `signed_component`: Giữ dấu âm của u3 theo biểu thức nguồn; đây là thành phần có dấu, không phải độ không đảm bảo tổng hợp.

### Ngữ cảnh trích xuất để định vị

```text
- Độ không đảm bảo đo của hệ số dãn nở áp suất: u3
Thành phần này được lấy trong giấy chứng nhận hiệu chuẩn, tính từ độ không đảm bảo đo mở rộng Uλc, tính theo công thức:
u3=-p2×Uλck
Phụ lục D (tiếp theo)
- Độ không đảm bảo đo của khối lượng quả cân pít tông chuẩn: u4
Thành phần này được lấy trong giấy chứng nhận hiệu chuẩn, tính từ độ không đảm bảo đo mở rộng UMc, tính theo công thức:
u4=pMc×UMck
```

### Kết luận của chuyên gia

- Người rà soát / chuyên môn: ____________________
- Ngày và phiên bản nguồn đã mở: ____________________
- Vị trí nguồn đã kiểm tra (mục/trang/đoạn): ____________________
- Biểu thức, dấu, chỉ số và ký hiệu: ____________________
- Ý nghĩa biến, đơn vị và đổi đơn vị: ____________________
- Miền dữ liệu, số loạt đo, điều kiện vật lý và tương quan: ____________________
- Ca tính đối chứng độc lập và cách tính: ____________________
- Kết luận (chấp nhận / cần sửa / không đủ căn cứ): **chưa có**
- Căn cứ, nội dung cần sửa và giới hạn sử dụng: ____________________

## F026 — Thành phần độ không đảm bảo do khối lượng u4 — QTKĐ 1.190 / DPI 610

- Registry ID: `dpi190_f026`; revision: `2`.
- Nguồn: [DOCX gốc](../../../../TC_DL/2023.%20QTKD%201.190%202023%20DPI%20610%20ND%2024.01.24.docx) — Đánh giá độ không đảm bảo đo / F026.
- Bằng chứng: [XML OMML](../source-review/F026.xml).
- SHA-256 DOCX: `0646012c8f3e44046865d38ee48db80eeb74a7e4e7e3c2f62a1cd6e0c27133ab`.
- SHA-256 định nghĩa: `958306e39d06f43640ef1d65c755a4bdb10f5a801ea7cc9a25942d025e0bcf3e`.
- Biểu thức đang chạy: `p/mass*um/k`; đơn vị kết quả: `Pa`.

```latex
u_{4}=\frac{p}{M_{c}}×\frac{U_{M_{c}}}{k}
```

### Biến và ràng buộc đang triển khai

| Biến | Ý nghĩa | Đơn vị | Ràng buộc |
|---|---|---|---|
| `p` | Áp suất p | `Pa` | `{"min": null, "exclusive_min": false}` |
| `mass` | Khối lượng M_c | `kg` | `{"min": 0, "exclusive_min": true}` |
| `um` | U_Mc | `kg` | `{"min": 0, "exclusive_min": false}` |
| `k` | Hệ số phủ k theo chứng nhận | `1` | `{"min": 0, "exclusive_min": true}` |

### Điều kiện cần đối chiếu

- `certificate`: U và k lấy từ cùng chứng nhận hiệu chuẩn; không tự mặc định k=2.
- `piston_standard`: Chuẩn sử dụng là áp kế pít tông theo mục D.2.2.2.

### Ngữ cảnh trích xuất để định vị

```text
- Độ không đảm bảo đo của khối lượng quả cân pít tông chuẩn: u4
Thành phần này được lấy trong giấy chứng nhận hiệu chuẩn, tính từ độ không đảm bảo đo mở rộng UMc, tính theo công thức:
u4=pMc×UMck
- Độ không đảm bảo đo của nhiệt độ pít tông/xylanh chuẩn: u5
Nhiệt độ pít tông/xylanh được đo trực tiếp với điều kiện nhiệt độ duy trì trong khoảng  1 oC và độ không đảm bảo đo có thể được lấy bằng Ut = 2 oC, tính theo công thức:
u5=p×αp,c+αc,c×Ut2
- Độ không đảm bảo đo của hệ số dãn nở nhiệt: u6
```

### Kết luận của chuyên gia

- Người rà soát / chuyên môn: ____________________
- Ngày và phiên bản nguồn đã mở: ____________________
- Vị trí nguồn đã kiểm tra (mục/trang/đoạn): ____________________
- Biểu thức, dấu, chỉ số và ký hiệu: ____________________
- Ý nghĩa biến, đơn vị và đổi đơn vị: ____________________
- Miền dữ liệu, số loạt đo, điều kiện vật lý và tương quan: ____________________
- Ca tính đối chứng độc lập và cách tính: ____________________
- Kết luận (chấp nhận / cần sửa / không đủ căn cứ): **chưa có**
- Căn cứ, nội dung cần sửa và giới hạn sử dụng: ____________________

## F031 — Thành phần độ không đảm bảo do chênh cao u9 — QTKĐ 1.190 / DPI 610

- Registry ID: `dpi190_f031`; revision: `2`.
- Nguồn: [DOCX gốc](../../../../TC_DL/2023.%20QTKD%201.190%202023%20DPI%20610%20ND%2024.01.24.docx) — Đánh giá độ không đảm bảo đo / F031.
- Bằng chứng: [XML OMML](../source-review/F031.xml).
- SHA-256 DOCX: `0646012c8f3e44046865d38ee48db80eeb74a7e4e7e3c2f62a1cd6e0c27133ab`.
- SHA-256 định nghĩa: `a200748660b93915f1ffef2ed10489f14dd539da18b5bc4f4c35f54c55c6c8d4`.
- Biểu thức đang chạy: `rho*g*uh/k`; đơn vị kết quả: `Pa`.

```latex
u_{9}=ρ_{f}×g×\frac{U_{∆h}}{k}
```

### Biến và ràng buộc đang triển khai

| Biến | Ý nghĩa | Đơn vị | Ràng buộc |
|---|---|---|---|
| `rho` | Khối lượng riêng chất lỏng | `kg/m3` | `{"min": 0, "exclusive_min": true}` |
| `g` | Gia tốc trọng trường | `m/s2` | `{"min": 0, "exclusive_min": true}` |
| `uh` | U_delta_h | `m` | `{"min": 0, "exclusive_min": false, "max": "0.002"}` |
| `k` | Hệ số phủ k theo chứng nhận | `1` | `{"min": 0, "exclusive_min": true}` |

### Điều kiện cần đối chiếu

- `piston_standard`: Chuẩn sử dụng là áp kế pít tông theo mục D.2.2.2.

### Ngữ cảnh trích xuất để định vị

```text
- Độ không đảm bảo đo của chênh lệch chiều cao cột chất lỏng: u9 
Độ không đảm bảo đo của chênh lệch chiều cao cột chất lỏng tối đa bằng Uh = 2 mm, tính theo công thức:
u9=ρf×g×U∆hk
Phụ lục D (tiếp theo)
- Độ không đảm bảo đo của lực tác dụng theo phương thẳng đứng: u10
Lực tác dụng theo phương thẳng đứng: F’ = F  cos. Trong trường hợp khi  < 0,5’ độ không đảm bảo đo theo   được ước lượng bằng: U = 5,82.10-4 rad và lấy theo phân bố hình chữ nhật, tính theo công thức:
u10=p×sinθc×Uθc3
```

### Kết luận của chuyên gia

- Người rà soát / chuyên môn: ____________________
- Ngày và phiên bản nguồn đã mở: ____________________
- Vị trí nguồn đã kiểm tra (mục/trang/đoạn): ____________________
- Biểu thức, dấu, chỉ số và ký hiệu: ____________________
- Ý nghĩa biến, đơn vị và đổi đơn vị: ____________________
- Miền dữ liệu, số loạt đo, điều kiện vật lý và tương quan: ____________________
- Ca tính đối chứng độc lập và cách tính: ____________________
- Kết luận (chấp nhận / cần sửa / không đủ căn cứ): **chưa có**
- Căn cứ, nội dung cần sửa và giới hạn sử dụng: ____________________

## F033 — Tổng hợp mười thành phần chuẩn pít tông — QTKĐ 1.190 / DPI 610

- Registry ID: `dpi190_f033`; revision: `2`.
- Nguồn: [DOCX gốc](../../../../TC_DL/2023.%20QTKD%201.190%202023%20DPI%20610%20ND%2024.01.24.docx) — Đánh giá độ không đảm bảo đo / F033.
- Bằng chứng: [XML OMML](../source-review/F033.xml).
- SHA-256 DOCX: `0646012c8f3e44046865d38ee48db80eeb74a7e4e7e3c2f62a1cd6e0c27133ab`.
- SHA-256 định nghĩa: `f23d5319f06f080d2bce1d0293b4096025cdc0e917720466fbf748e96246f09c`.
- Biểu thức đang chạy: `rss(components)`; đơn vị kết quả: `Pa`.

```latex
u_{c}=\sqrt{u_{1}^{2}+u_{2}^{2}+…+u_{10}^{2}}
```

### Biến và ràng buộc đang triển khai

| Biến | Ý nghĩa | Đơn vị | Ràng buộc |
|---|---|---|---|
| `components` | u1 đến u10 theo thứ tự; giữ nguyên dấu | `Pa` | `{"min": null, "exclusive_min": false, "kind": "series", "min_items": 10, "max_items": 10}` |

### Điều kiện cần đối chiếu

- `piston_standard`: Chuẩn sử dụng là áp kế pít tông theo mục D.2.2.2.
- `rss_applicable`: Đã xác nhận mô hình cộng bình phương này áp dụng, không cần thêm số hạng tương quan.

### Ngữ cảnh trích xuất để định vị

```text
u10=p×sinθc×Uθc3
- Độ không đảm bảo đo chuẩn liên hợp của tổ hợp chuẩn: uch
uc=u12+u22+…+u102
D.2.3 Độ không đảm bảo đo của áp kế kiểm: ubk
D.2.3.1 Độ không đảm bảo đo do độ phân giải: ur
- Đối với các áp kế kiểm kiểu chỉ thị tương tự: Độ phân giải (r) của áp kế kiểm kiểu chỉ thị tương tự là khoảng cách nh nhất giữa hai vạch chia liền kề có thể chia một cách ước lượng để xác định kim chỉ của chỉ thị chỉ vào giá trị nào. Đối với áp kế chỉ thị tương tự độ phân giải có thể được lấy bằng 1/2 hoặc 1/5 giá trị áp suất giữa hai vạch chia liền kề. Trường hợp khoảng cách giữa hai vạch chia liền kề lớn hơn hoặc bằng 2,5 mm độ phân giải có thể được lấy bằng 1/10 giá trị áp suất của khoảng cách đó . Đối với các cơ cấu chỉ thị kim, dạng của phân bố là hình tam giác. Đối với cơ cấu chỉ thị vạch dạng thước, dạng của phân bố là hình chữ nhật.
- Đối với các áp kế kiểm kiểu chỉ thị số: Độ phân giải (r) của áp kế kiểm kiểu chỉ thị số là giá trị tương ứng với một bước nhảy nhỏ nhất, dạng của phân bố là hình chữ nhật. Đối với các áp kế kiểm có các bước nhảy khác nhau trong toàn thang đo thì độ phân giải được chọn là giá trị lớn nhất.
```

### Kết luận của chuyên gia

- Người rà soát / chuyên môn: ____________________
- Ngày và phiên bản nguồn đã mở: ____________________
- Vị trí nguồn đã kiểm tra (mục/trang/đoạn): ____________________
- Biểu thức, dấu, chỉ số và ký hiệu: ____________________
- Ý nghĩa biến, đơn vị và đổi đơn vị: ____________________
- Miền dữ liệu, số loạt đo, điều kiện vật lý và tương quan: ____________________
- Ca tính đối chứng độc lập và cách tính: ____________________
- Kết luận (chấp nhận / cần sửa / không đủ căn cứ): **chưa có**
- Căn cứ, nội dung cần sửa và giới hạn sử dụng: ____________________

## F034 — Độ phân giải theo phân bố tam giác — QTKĐ 1.190 / DPI 610

- Registry ID: `dpi190_f034`; revision: `2`.
- Nguồn: [DOCX gốc](../../../../TC_DL/2023.%20QTKD%201.190%202023%20DPI%20610%20ND%2024.01.24.docx) — Đánh giá độ không đảm bảo đo / F034.
- Bằng chứng: [XML OMML](../source-review/F034.xml).
- SHA-256 DOCX: `0646012c8f3e44046865d38ee48db80eeb74a7e4e7e3c2f62a1cd6e0c27133ab`.
- SHA-256 định nghĩa: `a85305232fbe0f92f631081e358292d1531bbabb99ae43a81ab2158e126dc676`.
- Biểu thức đang chạy: `r/sqrt(6)`; đơn vị kết quả: `Pa`.

```latex
u_{r}=\frac{r}{\sqrt{6}}
```

### Biến và ràng buộc đang triển khai

| Biến | Ý nghĩa | Đơn vị | Ràng buộc |
|---|---|---|---|
| `r` | Độ phân giải r theo loại chỉ thị | `Pa` | `{"min": 0, "exclusive_min": false}` |

### Điều kiện cần đối chiếu

- `triangular_distribution`: Cơ cấu chỉ thị áp dụng phân bố tam giác.
- `resolution_definition`: r đã được xác định đúng theo loại chỉ thị và tình trạng dao động mô tả ở D.2.3.1.

### Ngữ cảnh trích xuất để định vị

```text
- Đối với các áp kế kiểm chỉ thị có dao động thăng giáng bất thường: Nếu các áp kế kiểm chỉ thị có dao động thăng giáng bất thường thì độ phân giải (r) sẽ tính bằng 1/2 khoảng dao động đối với các áp kế kiểm kiểu chỉ thị tương tự, và bằng 1/2 khoảng dao động cộng với một bước nhảy nhỏ nhất về giá trị đối với áp kế kiểm kiểu chị thị số.
- Đối với cơ cấu chỉ thị có dạng phân bố là hình tam giác công thức tính độ không đảm bảo đo ur như sau:
ur=r6
- Đối với cơ cấu chỉ thị có dạng phân bố là hình chữ nhật công thức tính độ không đảm bảo đo ur như sau:
ur=r3
D.2.3.2 Độ không đảm bảo đo do độ lệch “0”: uf0
Độ lệch “0” cần được xác định với mỗi chu kỳ đo bao gồm cả chu trình đo khi tăng và giảm áp suất. Các giá trị độ lệch “0” được tính như sau:
```

### Kết luận của chuyên gia

- Người rà soát / chuyên môn: ____________________
- Ngày và phiên bản nguồn đã mở: ____________________
- Vị trí nguồn đã kiểm tra (mục/trang/đoạn): ____________________
- Biểu thức, dấu, chỉ số và ký hiệu: ____________________
- Ý nghĩa biến, đơn vị và đổi đơn vị: ____________________
- Miền dữ liệu, số loạt đo, điều kiện vật lý và tương quan: ____________________
- Ca tính đối chứng độc lập và cách tính: ____________________
- Kết luận (chấp nhận / cần sửa / không đủ căn cứ): **chưa có**
- Căn cứ, nội dung cần sửa và giới hạn sử dụng: ____________________

## F035 — Độ phân giải theo phân bố chữ nhật — QTKĐ 1.190 / DPI 610

- Registry ID: `dpi190_f035`; revision: `2`.
- Nguồn: [DOCX gốc](../../../../TC_DL/2023.%20QTKD%201.190%202023%20DPI%20610%20ND%2024.01.24.docx) — Đánh giá độ không đảm bảo đo / F035.
- Bằng chứng: [XML OMML](../source-review/F035.xml).
- SHA-256 DOCX: `0646012c8f3e44046865d38ee48db80eeb74a7e4e7e3c2f62a1cd6e0c27133ab`.
- SHA-256 định nghĩa: `44e49cb867df02ddeaf6b16453cedb4a6f45b71c22d88c06593599d0ec9f1266`.
- Biểu thức đang chạy: `r/sqrt(3)`; đơn vị kết quả: `Pa`.

```latex
u_{r}=\frac{r}{\sqrt{3}}
```

### Biến và ràng buộc đang triển khai

| Biến | Ý nghĩa | Đơn vị | Ràng buộc |
|---|---|---|---|
| `r` | Độ phân giải r theo loại chỉ thị | `Pa` | `{"min": 0, "exclusive_min": false}` |

### Điều kiện cần đối chiếu

- `rectangular_distribution`: Cơ cấu chỉ thị áp dụng phân bố chữ nhật.
- `resolution_definition`: r đã được xác định đúng theo loại chỉ thị và tình trạng dao động mô tả ở D.2.3.1.

### Ngữ cảnh trích xuất để định vị

```text
ur=r6
- Đối với cơ cấu chỉ thị có dạng phân bố là hình chữ nhật công thức tính độ không đảm bảo đo ur như sau:
ur=r3
D.2.3.2 Độ không đảm bảo đo do độ lệch “0”: uf0
Độ lệch “0” cần được xác định với mỗi chu kỳ đo bao gồm cả chu trình đo khi tăng và giảm áp suất. Các giá trị độ lệch “0” được tính như sau:
f0=maxx2,0-x1,0,x4,0-x3,0,x6,0-x5,0
Các chỉ số của giá trị đo đọc tại điểm “0” của một loạt đo M1 đến M6
```

### Kết luận của chuyên gia

- Người rà soát / chuyên môn: ____________________
- Ngày và phiên bản nguồn đã mở: ____________________
- Vị trí nguồn đã kiểm tra (mục/trang/đoạn): ____________________
- Biểu thức, dấu, chỉ số và ký hiệu: ____________________
- Ý nghĩa biến, đơn vị và đổi đơn vị: ____________________
- Miền dữ liệu, số loạt đo, điều kiện vật lý và tương quan: ____________________
- Ca tính đối chứng độc lập và cách tính: ____________________
- Kết luận (chấp nhận / cần sửa / không đủ căn cứ): **chưa có**
- Căn cứ, nội dung cần sửa và giới hạn sử dụng: ____________________

## F036 — Độ lệch điểm không qua ba chu kỳ — QTKĐ 1.190 / DPI 610

- Registry ID: `dpi190_f036`; revision: `2`.
- Nguồn: [DOCX gốc](../../../../TC_DL/2023.%20QTKD%201.190%202023%20DPI%20610%20ND%2024.01.24.docx) — Đánh giá độ không đảm bảo đo / F036.
- Bằng chứng: [XML OMML](../source-review/F036.xml).
- SHA-256 DOCX: `0646012c8f3e44046865d38ee48db80eeb74a7e4e7e3c2f62a1cd6e0c27133ab`.
- SHA-256 định nghĩa: `0adbabc97150621049e9f9b0b075336e81387bb750a8441a0defd75e4e0b8652`.
- Biểu thức đang chạy: `max(abs(x2-x1),abs(x4-x3),abs(x6-x5))`; đơn vị kết quả: `Pa`.

```latex
f_{0}=max\left\{ \left| x_{2,0}-x_{1,0} \right|,\left| x_{4,0}-x_{3,0} \right|,\left| x_{6,0}-x_{5,0} \right| \right\}
```

### Biến và ràng buộc đang triển khai

| Biến | Ý nghĩa | Đơn vị | Ràng buộc |
|---|---|---|---|
| `x1` | Chỉ thị tại điểm 0 của loạt M1 | `Pa` | `{"min": null, "exclusive_min": false}` |
| `x2` | Chỉ thị tại điểm 0 của loạt M2 | `Pa` | `{"min": null, "exclusive_min": false}` |
| `x3` | Chỉ thị tại điểm 0 của loạt M3 | `Pa` | `{"min": null, "exclusive_min": false}` |
| `x4` | Chỉ thị tại điểm 0 của loạt M4 | `Pa` | `{"min": null, "exclusive_min": false}` |
| `x5` | Chỉ thị tại điểm 0 của loạt M5 | `Pa` | `{"min": null, "exclusive_min": false}` |
| `x6` | Chỉ thị tại điểm 0 của loạt M6 | `Pa` | `{"min": null, "exclusive_min": false}` |

### Điều kiện cần đối chiếu

- `zero_cycles`: Sáu giá trị là chỉ thị điểm 0 từ M1 đến M6 đúng thứ tự chu trình tăng/giảm.

### Ngữ cảnh trích xuất để định vị

```text
D.2.3.2 Độ không đảm bảo đo do độ lệch “0”: uf0
Độ lệch “0” cần được xác định với mỗi chu kỳ đo bao gồm cả chu trình đo khi tăng và giảm áp suất. Các giá trị độ lệch “0” được tính như sau:
f0=maxx2,0-x1,0,x4,0-x3,0,x6,0-x5,0
Các chỉ số của giá trị đo đọc tại điểm “0” của một loạt đo M1 đến M6
Phụ lục D (kết thúc)
Công thức tính độ không đảm bảo đo uf0 như sau:
uf0=f023
```

### Kết luận của chuyên gia

- Người rà soát / chuyên môn: ____________________
- Ngày và phiên bản nguồn đã mở: ____________________
- Vị trí nguồn đã kiểm tra (mục/trang/đoạn): ____________________
- Biểu thức, dấu, chỉ số và ký hiệu: ____________________
- Ý nghĩa biến, đơn vị và đổi đơn vị: ____________________
- Miền dữ liệu, số loạt đo, điều kiện vật lý và tương quan: ____________________
- Ca tính đối chứng độc lập và cách tính: ____________________
- Kết luận (chấp nhận / cần sửa / không đủ căn cứ): **chưa có**
- Căn cứ, nội dung cần sửa và giới hạn sử dụng: ____________________

## F037 — Độ không đảm bảo do độ lệch điểm không u_f0 — QTKĐ 1.190 / DPI 610

- Registry ID: `dpi190_f037`; revision: `2`.
- Nguồn: [DOCX gốc](../../../../TC_DL/2023.%20QTKD%201.190%202023%20DPI%20610%20ND%2024.01.24.docx) — Đánh giá độ không đảm bảo đo / F037.
- Bằng chứng: [XML OMML](../source-review/F037.xml).
- SHA-256 DOCX: `0646012c8f3e44046865d38ee48db80eeb74a7e4e7e3c2f62a1cd6e0c27133ab`.
- SHA-256 định nghĩa: `6ae3abf9d3deaf8096b7f1c94fb11e945d942a38bb4af63265914af2daaf10a0`.
- Biểu thức đang chạy: `f0/(2*sqrt(3))`; đơn vị kết quả: `Pa`.

```latex
u_{f0}=\frac{f_{0}}{2\sqrt{3}}
```

### Biến và ràng buộc đang triển khai

| Biến | Ý nghĩa | Đơn vị | Ràng buộc |
|---|---|---|---|
| `f0` | Độ lệch điểm không f0 đã xác định từ M1 đến M6 | `Pa` | `{"min": 0, "exclusive_min": false}` |

### Điều kiện cần đối chiếu

- `zero_shift_reviewed`: f0 đã được xác định đúng theo ba cặp M2-M1, M4-M3, M6-M5 theo D.2.3.2.

### Ngữ cảnh trích xuất để định vị

```text
Phụ lục D (kết thúc)
Công thức tính độ không đảm bảo đo uf0 như sau:
uf0=f023
D.2.3.3 Độ không đảm bảo đo do độ lặp lại: ub’
Độ không đảm bảo đo do độ lặp lại được xác định như sau:
b'up,j=x3,j-x3,0-x1,j-x1,0b'down,j=x4,j-x4,0-x2,j-x2,0b'mean,j=maxb'up,j-b'down,j
Với j là số thứ tự của điểm đo.
```

### Kết luận của chuyên gia

- Người rà soát / chuyên môn: ____________________
- Ngày và phiên bản nguồn đã mở: ____________________
- Vị trí nguồn đã kiểm tra (mục/trang/đoạn): ____________________
- Biểu thức, dấu, chỉ số và ký hiệu: ____________________
- Ý nghĩa biến, đơn vị và đổi đơn vị: ____________________
- Miền dữ liệu, số loạt đo, điều kiện vật lý và tương quan: ____________________
- Ca tính đối chứng độc lập và cách tính: ____________________
- Kết luận (chấp nhận / cần sửa / không đủ căn cứ): **chưa có**
- Căn cứ, nội dung cần sửa và giới hạn sử dụng: ____________________

## F050 — Độ không đảm bảo đo mở rộng U_c — QTKĐ 1.190 / DPI 610

- Registry ID: `dpi190_f050`; revision: `2`.
- Nguồn: [DOCX gốc](../../../../TC_DL/2023.%20QTKD%201.190%202023%20DPI%20610%20ND%2024.01.24.docx) — Đánh giá độ không đảm bảo đo / F050.
- Bằng chứng: [XML OMML](../source-review/F050.xml).
- SHA-256 DOCX: `0646012c8f3e44046865d38ee48db80eeb74a7e4e7e3c2f62a1cd6e0c27133ab`.
- SHA-256 định nghĩa: `b4348f75ad4d957de56f6386e5a5438616bca8098e25211aebc975e4d1356694`.
- Biểu thức đang chạy: `k*uc`; đơn vị kết quả: `Pa`.

```latex
U_{c}=k×u_{c}
```

### Biến và ràng buộc đang triển khai

| Biến | Ý nghĩa | Đơn vị | Ràng buộc |
|---|---|---|---|
| `k` | Hệ số phủ k theo chứng nhận | `1` | `{"min": 0, "exclusive_min": true}` |
| `uc` | Độ không đảm bảo liên hợp đã được xác định | `Pa` | `{"min": 0, "exclusive_min": false}` |

### Điều kiện cần đối chiếu

- `combined_reviewed`: u_c đã được xác định bằng mô hình liên hợp được đối chiếu; không tự sử dụng biểu thức F049 còn mâu thuẫn.

### Ngữ cảnh trích xuất để định vị

```text
uc=ua2+uc2+ubk2
D.2.5 Độ không đảm bảo đo mở rộng: Uc
Uc=k×uc
122364535242500

```

### Kết luận của chuyên gia

- Người rà soát / chuyên môn: ____________________
- Ngày và phiên bản nguồn đã mở: ____________________
- Vị trí nguồn đã kiểm tra (mục/trang/đoạn): ____________________
- Biểu thức, dấu, chỉ số và ký hiệu: ____________________
- Ý nghĩa biến, đơn vị và đổi đơn vị: ____________________
- Miền dữ liệu, số loạt đo, điều kiện vật lý và tương quan: ____________________
- Ca tính đối chứng độc lập và cách tính: ____________________
- Kết luận (chấp nhận / cần sửa / không đủ căn cứ): **chưa có**
- Căn cứ, nội dung cần sửa và giới hạn sử dụng: ____________________
