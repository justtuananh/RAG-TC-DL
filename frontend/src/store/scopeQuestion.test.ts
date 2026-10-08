import { describe, expect, it } from "vitest";
import { scopeQuestion } from "./scopeQuestion";

describe("scopeQuestion", () => {
  const prefix = "Theo QTKĐ 1.159:2021, ";

  it("bản nháp trống: chỉ tiền tố, sẵn sàng gõ tiếp", () => {
    expect(scopeQuestion(prefix, "")).toBe(prefix);
  });

  it("giữ câu hỏi đang soạn, đặt phạm vi lên trước", () => {
    expect(scopeQuestion(prefix, "chu kỳ kiểm định là bao lâu?")).toBe("Theo QTKĐ 1.159:2021, chu kỳ kiểm định là bao lâu?");
  });

  it("thay phạm vi của QTKĐ trước, không chồng hai tiền tố", () => {
    expect(scopeQuestion(prefix, "Theo QTKĐ 1.061:2021, chu kỳ?")).toBe("Theo QTKĐ 1.159:2021, chu kỳ?");
  });

  it("bấm lại cùng QTKĐ không đổi câu hỏi", () => {
    expect(scopeQuestion(prefix, "Theo QTKĐ 1.159:2021, chu kỳ?")).toBe("Theo QTKĐ 1.159:2021, chu kỳ?");
  });
});
