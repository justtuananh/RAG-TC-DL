import { describe, expect, it } from "vitest";
import { formatDate, formatGeneral, formatNumber, formatText } from "./numfmt";

// Các mẫu numFmt thật trong biên bản TC_DL/*.xlsx: 0.00000, 0.0, 0.000, #,##0.00000,
// #,##0.000, General, dựng sẵn 2 (0.00), 11 (0.00E+00), 14 (ngày), 0.000%.

describe("formatGeneral - kiểu General của Excel (vùng VN)", () => {
  it("số nguyên và thập phân dùng dấu phẩy", () => {
    expect(formatGeneral(1045)).toBe("1045");
    expect(formatGeneral(0.067571)).toBe("0,067571");
    expect(formatGeneral(-2.5)).toBe("-2,5");
  });

  it("cắt còn 10 chữ số có nghĩa như ô Excel mặc định", () => {
    expect(formatGeneral(67.5680034394153)).toBe("67,56800344");
    expect(formatGeneral(891279.013561178)).toBe("891279,0136");
  });

  it("số rất nhỏ/rất lớn chuyển dạng mũ", () => {
    expect(formatGeneral(9.97962912921334e-5)).toBe("9,97963E-05");
    expect(formatGeneral(1e12)).toBe("1E+12");
  });
});

describe("formatNumber - mẫu số", () => {
  it("số chữ số thập phân cố định", () => {
    expect(formatNumber(67.5707, "0.00000")).toBe("67,57070");
    expect(formatNumber(2.3, "0.0")).toBe("2,3");
    expect(formatNumber(15, "0.0")).toBe("15,0");
    expect(formatNumber(0.0045, "0.000")).toBe("0,005");
    expect(formatNumber(1.005, "0.00")).toBe("1,01");
  });

  it("nhóm nghìn bằng dấu chấm", () => {
    expect(formatNumber(16893.58119, "#,##0.00000")).toBe("16.893,58119");
    expect(formatNumber(1234567.8, "#,##0.000")).toBe("1.234.567,800");
    expect(formatNumber(12, "#,##0")).toBe("12");
  });

  it("phần trăm và dạng mũ", () => {
    expect(formatNumber(0.00005, "0.000%")).toBe("0,005%");
    expect(formatNumber(0.00009979, "0.00E+00")).toBe("9,98E-05");
  });

  it("chữ kèm mẫu và phần âm riêng", () => {
    expect(formatNumber(5, '0.0" kPa"')).toBe("5,0 kPa");
    expect(formatNumber(-3, "0.0;(0.0)")).toBe("(3,0)");
    expect(formatNumber(-3, "0.0")).toBe("-3,0");
    expect(formatNumber(-0.0001, "0.0")).toBe("0,0");
  });

  it("General/rỗng rơi về kiểu General", () => {
    expect(formatNumber(0.067571, "General")).toBe("0,067571");
    expect(formatNumber(0.067571, undefined)).toBe("0,067571");
  });

  it("số serial mang mẫu ngày hiển thị thành ngày", () => {
    expect(formatNumber(45097, "dd/mm/yyyy")).toBe("20/06/2023");
    expect(formatNumber(45097, "mm-dd-yy")).toBe("20/06/2023");
  });
});

describe("formatDate", () => {
  const date = new Date(Date.UTC(2023, 5, 20, 14, 5, 9));

  it("mẫu dựng sẵn 14 hiển thị theo vùng Việt Nam", () => {
    expect(formatDate(date, "mm-dd-yy")).toBe("20/06/2023");
  });

  it("m sau giờ là phút, không phải tháng", () => {
    expect(formatDate(date, "d/m/yyyy h:mm")).toBe("20/6/2023 14:05");
    expect(formatDate(date, "hh:mm:ss")).toBe("14:05:09");
  });

  it("chữ trong ngoặc kép giữ nguyên", () => {
    expect(formatDate(date, '"ngày" dd "tháng" mm "năm" yyyy')).toBe("ngày 20 tháng 06 năm 2023");
  });
});

describe("formatText", () => {
  it("phần @ ghép chữ trước/sau", () => {
    expect(formatText("1045", '"SN: "@')).toBe("SN: 1045");
    expect(formatText("abc", "0.00")).toBe("abc");
  });
});
