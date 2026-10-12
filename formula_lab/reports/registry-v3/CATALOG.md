# 21 bộ tính mới và số liệu demo

Dữ liệu phát triển công khai; chưa phải bộ đánh giá độc lập. ID Pxxx là quy tắc từ lời văn, không phải mã phương trình nguồn. Định nghĩa nguồn ở [source-review/REVIEW.md](source-review/REVIEW.md).

## Bù áp suất do chênh cao cột chất lỏng — QTKĐ 1.160

- ID: `qtkd160_f001`.
- Câu hỏi: `QTKĐ 1.160: bù áp suất do chênh cao`.
- Biểu thức: `rho*g*h`.
- Dữ liệu mẫu:

```json
{
  "rho": {
    "value": "1000",
    "unit": "kg/m3"
  },
  "g": {
    "value": "9.8",
    "unit": "m/s2"
  },
  "h": {
    "value": "-20",
    "unit": "mm"
  }
}
```

- Kết quả đối chiếu: `-196 Pa`.
- Điều kiện: xem form và `data/v3/conditions.json`; chỉ xác nhận khi phù hợp phép đo.

## Chỉ thị dự đoán theo quan hệ tuyến tính — QTKĐ 1.160

- ID: `qtkd160_f005`.
- Câu hỏi: `QTKĐ 1.160: chỉ thị dự đoán`.
- Biểu thức: `a+b*x`.
- Dữ liệu mẫu:

```json
{
  "a": {
    "value": "-2",
    "unit": "Pa"
  },
  "b": {
    "value": "1.5",
    "unit": "1"
  },
  "x": {
    "value": "10",
    "unit": "Pa"
  }
}
```

- Kết quả đối chiếu: `13 Pa`.
- Điều kiện: xem form và `data/v3/conditions.json`; chỉ xác nhận khi phù hợp phép đo.

## Trung bình các giá trị áp suất chuẩn — QTKĐ 1.160

- ID: `qtkd160_f006`.
- Câu hỏi: `QTKĐ 1.160: trung bình áp suất chuẩn`.
- Biểu thức: `mean(readings)`.
- Dữ liệu mẫu:

```json
{
  "readings": {
    "value": [
      "-3",
      "0",
      "6"
    ],
    "unit": "Pa"
  }
}
```

- Kết quả đối chiếu: `1 Pa`.
- Điều kiện: xem form và `data/v3/conditions.json`; chỉ xác nhận khi phù hợp phép đo.

## Trung bình chỉ thị áp kế kiểm — QTKĐ 1.160

- ID: `qtkd160_f007`.
- Câu hỏi: `QTKĐ 1.160: trung bình chỉ thị`.
- Biểu thức: `mean(readings)`.
- Dữ liệu mẫu:

```json
{
  "readings": {
    "value": [
      "2",
      "5",
      "8"
    ],
    "unit": "Pa"
  }
}
```

- Kết quả đối chiếu: `5 Pa`.
- Điều kiện: xem form và `data/v3/conditions.json`; chỉ xác nhận khi phù hợp phép đo.

## Hệ số góc hồi quy bình phương tối thiểu — QTKĐ 1.160

- ID: `qtkd160_f008`.
- Câu hỏi: `QTKĐ 1.160: hệ số góc hồi quy`.
- Biểu thức: `slope(xs,ys)`.
- Dữ liệu mẫu:

```json
{
  "xs": {
    "value": [
      "1",
      "2",
      "3"
    ],
    "unit": "Pa"
  },
  "ys": {
    "value": [
      "2",
      "5",
      "8"
    ],
    "unit": "Pa"
  }
}
```

- Kết quả đối chiếu: `3 1`.
- Điều kiện: xem form và `data/v3/conditions.json`; chỉ xác nhận khi phù hợp phép đo.

## Hệ số chặn hồi quy — QTKĐ 1.160

- ID: `qtkd160_f009`.
- Câu hỏi: `QTKĐ 1.160: hệ số chặn hồi quy`.
- Biểu thức: `y_mean-b*x_mean`.
- Dữ liệu mẫu:

```json
{
  "y_mean": {
    "value": "5",
    "unit": "Pa"
  },
  "b": {
    "value": "3",
    "unit": "1"
  },
  "x_mean": {
    "value": "2",
    "unit": "Pa"
  }
}
```

- Kết quả đối chiếu: `-1 Pa`.
- Điều kiện: xem form và `data/v3/conditions.json`; chỉ xác nhận khi phù hợp phép đo.

## Độ phân giải theo phân bố tam giác — QTKĐ 1.160

- ID: `qtkd160_f033`.
- Câu hỏi: `QTKĐ 1.160: độ phân giải tam giác`.
- Biểu thức: `r/sqrt(6)`.
- Dữ liệu mẫu:

```json
{
  "r": {
    "value": "6",
    "unit": "Pa"
  }
}
```

- Kết quả đối chiếu: `2.449489742783178098197284074705892 Pa`.
- Điều kiện: xem form và `data/v3/conditions.json`; chỉ xác nhận khi phù hợp phép đo.

## Độ phân giải theo phân bố chữ nhật — QTKĐ 1.160

- ID: `qtkd160_f034`.
- Câu hỏi: `QTKĐ 1.160: độ phân giải chữ nhật`.
- Biểu thức: `r/sqrt(3)`.
- Dữ liệu mẫu:

```json
{
  "r": {
    "value": "3",
    "unit": "Pa"
  }
}
```

- Kết quả đối chiếu: `1.732050807568877293527446341505872 Pa`.
- Điều kiện: xem form và `data/v3/conditions.json`; chỉ xác nhận khi phù hợp phép đo.

## Trung bình chỉ thị áp kế kiểm — QTKĐ 1.190

- ID: `dpi190_f008`.
- Câu hỏi: `DPI 610: trung bình chỉ thị`.
- Biểu thức: `mean(readings)`.
- Dữ liệu mẫu:

```json
{
  "readings": {
    "value": [
      "-6",
      "0",
      "3"
    ],
    "unit": "Pa"
  }
}
```

- Kết quả đối chiếu: `-1 Pa`.
- Điều kiện: xem form và `data/v3/conditions.json`; chỉ xác nhận khi phù hợp phép đo.

## Độ lặp lại chiều tăng — QTKĐ 1.190

- ID: `dpi190_f038`.
- Câu hỏi: `DPI 610: độ lặp lại chiều tăng`.
- Biểu thức: `abs((x3_j-x3_0)-(x1_j-x1_0))`.
- Dữ liệu mẫu:

```json
{
  "x3_j": {
    "value": "100",
    "unit": "Pa"
  },
  "x3_0": {
    "value": "3",
    "unit": "Pa"
  },
  "x1_j": {
    "value": "102",
    "unit": "Pa"
  },
  "x1_0": {
    "value": "1",
    "unit": "Pa"
  }
}
```

- Kết quả đối chiếu: `4 Pa`.
- Điều kiện: xem form và `data/v3/conditions.json`; chỉ xác nhận khi phù hợp phép đo.

## Độ lặp lại chiều giảm — QTKĐ 1.190

- ID: `dpi190_f039`.
- Câu hỏi: `DPI 610: độ lặp lại chiều giảm`.
- Biểu thức: `abs((x4_j-x4_0)-(x2_j-x2_0))`.
- Dữ liệu mẫu:

```json
{
  "x4_j": {
    "value": "98",
    "unit": "Pa"
  },
  "x4_0": {
    "value": "-2",
    "unit": "Pa"
  },
  "x2_j": {
    "value": "97",
    "unit": "Pa"
  },
  "x2_0": {
    "value": "1",
    "unit": "Pa"
  }
}
```

- Kết quả đối chiếu: `4 Pa`.
- Điều kiện: xem form và `data/v3/conditions.json`; chỉ xác nhận khi phù hợp phép đo.

## Độ tái lặp lại chiều tăng — QTKĐ 1.190

- ID: `dpi190_f042`.
- Câu hỏi: `DPI 610: độ tái lặp lại chiều tăng`.
- Biểu thức: `abs((x5_j-x5_0)-(x1_j-x1_0))`.
- Dữ liệu mẫu:

```json
{
  "x5_j": {
    "value": "-100",
    "unit": "Pa"
  },
  "x5_0": {
    "value": "-3",
    "unit": "Pa"
  },
  "x1_j": {
    "value": "-90",
    "unit": "Pa"
  },
  "x1_0": {
    "value": "-2",
    "unit": "Pa"
  }
}
```

- Kết quả đối chiếu: `9 Pa`.
- Điều kiện: xem form và `data/v3/conditions.json`; chỉ xác nhận khi phù hợp phép đo.

## Độ tái lặp lại chiều giảm — QTKĐ 1.190

- ID: `dpi190_f043`.
- Câu hỏi: `DPI 610: độ tái lặp lại chiều giảm`.
- Biểu thức: `abs((x6_j-x6_0)-(x2_j-x2_0))`.
- Dữ liệu mẫu:

```json
{
  "x6_j": {
    "value": "100",
    "unit": "Pa"
  },
  "x6_0": {
    "value": "5",
    "unit": "Pa"
  },
  "x2_j": {
    "value": "99",
    "unit": "Pa"
  },
  "x2_0": {
    "value": "4",
    "unit": "Pa"
  }
}
```

- Kết quả đối chiếu: `0 Pa`.
- Điều kiện: xem form và `data/v3/conditions.json`; chỉ xác nhận khi phù hợp phép đo.

## Áp suất thử độ kín và chịu tải van — QTKĐ 1.061

- ID: `qtkd061_p001`.
- Câu hỏi: `QTKĐ 1.061: áp suất thử độ kín`.
- Biểu thức: `1.5*pmax`.
- Dữ liệu mẫu:

```json
{
  "pmax": {
    "value": "100",
    "unit": "bar"
  }
}
```

- Kết quả đối chiếu: `15000000 Pa`.
- Điều kiện: xem form và `data/v3/conditions.json`; chỉ xác nhận khi phù hợp phép đo.

## Độ lớn sai số áp suất chỉnh đặt cho phép — QTKĐ 1.061

- ID: `qtkd061_p002`.
- Câu hỏi: `QTKĐ 1.061: giới hạn sai số van`.
- Biểu thức: `max(0.03*pcd,15000)`.
- Dữ liệu mẫu:

```json
{
  "pcd": {
    "value": "2",
    "unit": "bar"
  }
}
```

- Kết quả đối chiếu: `15000 Pa`.
- Điều kiện: xem form và `data/v3/conditions.json`; chỉ xác nhận khi phù hợp phép đo.

## Mức áp suất bơm phụ một phần mười — QTKĐ 1.062

- ID: `qtkd062_p001`.
- Câu hỏi: `QTKĐ 1.062: mức áp suất bơm phụ`.
- Biểu thức: `pmax/10`.
- Dữ liệu mẫu:

```json
{
  "pmax": {
    "value": "100",
    "unit": "bar"
  }
}
```

- Kết quả đối chiếu: `1000000 Pa`.
- Điều kiện: xem form và `data/v3/conditions.json`; chỉ xác nhận khi phù hợp phép đo.

## Giới hạn áp suất kiểm tra van bảo vệ bơm phụ — QTKĐ 1.062

- ID: `qtkd062_p002`.
- Câu hỏi: `QTKĐ 1.062: giới hạn van bơm phụ`.
- Biểu thức: `0.2*pmax`.
- Dữ liệu mẫu:

```json
{
  "pmax": {
    "value": "100",
    "unit": "bar"
  }
}
```

- Kết quả đối chiếu: `2000000 Pa`.
- Điều kiện: xem form và `data/v3/conditions.json`; chỉ xác nhận khi phù hợp phép đo.

## Giới hạn độ tụt áp sau năm phút — QTKĐ 1.062

- ID: `qtkd062_p003`.
- Câu hỏi: `QTKĐ 1.062: độ tụt áp cho phép`.
- Biểu thức: `0.05*pmax`.
- Dữ liệu mẫu:

```json
{
  "pmax": {
    "value": "100",
    "unit": "bar"
  }
}
```

- Kết quả đối chiếu: `500000 Pa`.
- Điều kiện: xem form và `data/v3/conditions.json`; chỉ xác nhận khi phù hợp phép đo.

## Giới hạn độ tụt áp bình phân ly sau năm phút — QTKĐ 1.063

- ID: `qtkd063_p001`.
- Câu hỏi: `QTKĐ 1.063: giới hạn độ tụt áp bình phân ly`.
- Biểu thức: `0.05*pmax`.
- Dữ liệu mẫu:

```json
{
  "pmax": {
    "value": "200",
    "unit": "bar"
  }
}
```

- Kết quả đối chiếu: `1000000 Pa`.
- Điều kiện: xem form và `data/v3/conditions.json`; chỉ xác nhận khi phù hợp phép đo.

## Sai số tuyệt đối trung bình hai lần đo — QTKĐ 1.071

- ID: `qtkd071_f013`.
- Câu hỏi: `H3000: sai số tuyệt đối trung bình`.
- Biểu thức: `((p-pc1)+(p-pc2))/2`.
- Dữ liệu mẫu:

```json
{
  "p": {
    "value": "100",
    "unit": "bar"
  },
  "pc1": {
    "value": "101",
    "unit": "bar"
  },
  "pc2": {
    "value": "103",
    "unit": "bar"
  }
}
```

- Kết quả đối chiếu: `-2 bar`.
- Điều kiện: xem form và `data/v3/conditions.json`; chỉ xác nhận khi phù hợp phép đo.

## Áp suất tuyệt đối tại đáy pít tông — QTKĐ 1.159

- ID: `qtkd159_f031`.
- Câu hỏi: `QTKĐ 1.159: áp suất tuyệt đối tại đáy`.
- Biểu thức: `ps+mu`.
- Dữ liệu mẫu:

```json
{
  "ps": {
    "value": "1500",
    "unit": "Pa"
  },
  "mu": {
    "value": "5",
    "unit": "Pa"
  }
}
```

- Kết quả đối chiếu: `1505 Pa`.
- Điều kiện: xem form và `data/v3/conditions.json`; chỉ xác nhận khi phù hợp phép đo.
