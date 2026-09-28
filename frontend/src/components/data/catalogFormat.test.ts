import { describe, expect, it } from "vitest";
import type { CatalogRow } from "../../types";
import { formatCatalogDate, formatNextDue, isInherited, isOverdue, joinList, recognitionLabel } from "./catalogFormat";

// Hàm hiển thị danh mục: hạn kế tiếp "ước tính", nhãn "Quá hạn", dấu kế thừa "nt".

function makeRow(overrides: Partial<CatalogRow> = {}): CatalogRow {
  return {
    id: 1,
    ord: 1,
    document_id: "bieu3",
    extraction_id: 5,
    quote: "1 | Áp kế | nt",
    display_name: "bieu3.xlsx",
    file_stem: "bieu3",
    provenance: {
      document_id: "bieu3",
      display_name: "bieu3.xlsx",
      file_stem: "bieu3",
      extraction_id: 5,
      quote: "1 | Áp kế | nt",
    },
    ...overrides,
  };
}

describe("formatNextDue / isOverdue", () => {
  it("trả MM/YYYY khi có giá trị dẫn xuất", () => {
    const row = makeRow({ next_due_year: 2025, next_due_month: 9, next_due_derived: 1 });
    expect(formatNextDue(row)).toBe("09/2025");
    expect(isOverdue(row, new Date(2024, 0, 15))).toBe(false);
  });

  it("đánh dấu quá hạn khi hạn trước tháng hiện tại", () => {
    const row = makeRow({ next_due_year: 2024, next_due_month: 12, next_due_derived: 1 });
    expect(isOverdue(row, new Date(2025, 0, 5))).toBe(true);
    // Cùng tháng thì chưa quá hạn.
    expect(isOverdue(row, new Date(2024, 11, 31))).toBe(false);
  });

  it("không có giá trị dẫn xuất thì để trống", () => {
    const row = makeRow({ next_due_year: null, next_due_month: null, next_due_derived: 0 });
    expect(formatNextDue(row)).toBe("—");
    expect(isOverdue(row)).toBe(false);
  });
});

describe("trường kế thừa và định dạng khác", () => {
  it("nhận diện khóa kế thừa từ nt", () => {
    const row = makeRow({ inherited: ["interval", "usage"] });
    expect(isInherited(row, "interval")).toBe(true);
    expect(isInherited(row, "issuer")).toBe(false);
  });

  it("định dạng ngày và danh sách", () => {
    expect(formatCatalogDate("2019-10-30")).toBe("30/10/2019");
    expect(formatCatalogDate(null)).toBe("—");
    expect(joinList(["a", "b"])).toBe("a; b");
    expect(joinList([])).toBe("—");
    expect(recognitionLabel("duy_tri")).toBe("Duy trì");
    expect(recognitionLabel(null)).toBe("—");
  });
});
