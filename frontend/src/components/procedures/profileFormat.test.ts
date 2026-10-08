import { describe, expect, it } from "vitest";
import type { ProcedureProfile, ProcedureStep } from "../../types";
import { cellLines, formulaMarkdown, knowledgeTotal, procedureCode, stepsForMode } from "./profileFormat";

function step(label: string, modes: Partial<ProcedureStep["modes"]> = {}): ProcedureStep {
  return {
    fact_id: 1,
    label,
    section_ref: null,
    depth: 0,
    modes: { ban_dau: false, dinh_ky: false, sau_sua_chua: false, ...modes },
  };
}

describe("procedureCode", () => {
  it("ghép số hiệu với năm ban hành", () => {
    expect(procedureCode({ number: "1.061", year: 2021 })).toBe("QTKĐ 1.061:2021");
  });
  it("bỏ năm khi không có", () => {
    expect(procedureCode({ number: "1.190", year: null })).toBe("QTKĐ 1.190");
  });
});

describe("stepsForMode", () => {
  const steps = [step("A", { ban_dau: true, dinh_ky: true }), step("B", { ban_dau: true }), step("C")];
  it("trả mọi bước khi chọn tất cả chế độ", () => {
    expect(stepsForMode(steps, "all").map((s) => s.label)).toEqual(["A", "B", "C"]);
  });
  it("chỉ giữ bước có đánh dấu chế độ được chọn", () => {
    expect(stepsForMode(steps, "dinh_ky").map((s) => s.label)).toEqual(["A"]);
  });
});

describe("formulaMarkdown", () => {
  it("giữ nguyên chuỗi đã có dấu $", () => {
    expect(formulaMarkdown("$\\delta = p$")).toBe("$\\delta = p$");
  });
  it("bọc LaTeX trần thành khối công thức, không đổi nội dung", () => {
    expect(formulaMarkdown("\\Delta = p_s - p")).toBe("$$\n\\Delta = p_s - p\n$$");
  });
  it("rỗng khi không có công thức", () => {
    expect(formulaMarkdown(null)).toBe("");
  });
});

describe("knowledgeTotal", () => {
  it("cộng mọi loại tri thức đã duyệt, không tính biên bản", () => {
    const profile = {
      parameters: [{ kind: "working_range", label: "Phạm vi đo", items: [{}, {}] }],
      conditions: [{}],
      steps: [{}, {}, {}],
      formulas: [],
      standards: [{}],
      terms: [{}, {}],
      records: { total: 9 },
    } as unknown as ProcedureProfile;
    expect(knowledgeTotal(profile)).toBe(9);
  });
});

describe("cellLines", () => {
  it("tách ô nhiều dòng của bảng nguồn (nối bằng ' / ') về từng dòng", () => {
    expect(cellLines("Nhiệt độ: Từ 18 oC / Độ ẩm: Từ 20 %RH")).toEqual(["Nhiệt độ: Từ 18 oC", "Độ ẩm: Từ 20 %RH"]);
  });
  it("giữ dấu / không có khoảng trắng hai bên (píttông/xylanh, 1/4)", () => {
    expect(cellLines("Nhiệt kế píttông/xylanh, 1/4 sai số")).toEqual(["Nhiệt kế píttông/xylanh, 1/4 sai số"]);
  });
  it("rỗng khi không có nội dung", () => {
    expect(cellLines(null)).toEqual([]);
  });
});
