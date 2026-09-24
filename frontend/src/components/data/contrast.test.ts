import { describe, expect, it } from "vitest";
import { contrastRatio, meetsAA, parseHex, relativeLuminance } from "./contrast";

describe("contrast — WCAG 2.1", () => {
  it("parse được hex 3 và 6 ký tự", () => {
    expect(parseHex("#fff")).toEqual({ r: 255, g: 255, b: 255 });
    expect(parseHex("#101828")).toEqual({ r: 16, g: 24, b: 40 });
  });

  it("từ chối hex không hợp lệ", () => {
    expect(() => parseHex("nope")).toThrow();
  });

  it("đen trên trắng = 21:1, trắng trên trắng = 1:1", () => {
    expect(contrastRatio("#000000", "#FFFFFF")).toBeCloseTo(21, 1);
    expect(contrastRatio("#FFFFFF", "#FFFFFF")).toBeCloseTo(1, 5);
  });

  it("luminance tăng theo độ sáng", () => {
    expect(relativeLuminance("#000000")).toBeLessThan(relativeLuminance("#FFFFFF"));
  });

  it("meetsAA phân biệt chữ thường và chữ lớn", () => {
    // Xám #949494 trên trắng ≈ 3.0 — đạt AA chữ lớn, trượt chữ thường.
    expect(meetsAA("#949494", "#FFFFFF", true)).toBe(true);
    expect(meetsAA("#949494", "#FFFFFF", false)).toBe(false);
  });
});
