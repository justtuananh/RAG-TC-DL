import { describe, expect, it } from "vitest";
import { originalUnitHint, siFieldLabel } from "./siUnit";

const CELSIUS = { code: "°C", si_code: "K", factor_to_si: 1, offset_to_si: 273.15 };
const MBAR = { code: "mbar", si_code: "Pa", factor_to_si: 100, offset_to_si: 0 };
const PERCENT = { code: "%", si_code: "%", factor_to_si: 1, offset_to_si: 0 };

describe("siFieldLabel", () => {
  it("names the SI unit next to the field", () => {
    expect(siFieldLabel("Giá trị nhỏ nhất", CELSIUS)).toBe("Giá trị nhỏ nhất (SI, K)");
  });

  it("falls back to a bare SI tag when the fact has no unit", () => {
    expect(siFieldLabel("Giá trị nhỏ nhất", null)).toBe("Giá trị nhỏ nhất (SI)");
    expect(siFieldLabel("Giá trị nhỏ nhất", { ...CELSIUS, si_code: null })).toBe("Giá trị nhỏ nhất (SI)");
  });
});

describe("originalUnitHint", () => {
  it("converts an SI value back to the source unit", () => {
    expect(originalUnitHint("291.15", CELSIUS)).toBe("= 18 °C");
    expect(originalUnitHint("104000", MBAR)).toBe("= 1040 mbar");
  });

  it("accepts a decimal comma", () => {
    expect(originalUnitHint("301,15", CELSIUS)).toBe("= 28 °C");
  });

  it("stays silent when there is nothing to convert", () => {
    expect(originalUnitHint("", CELSIUS)).toBeNull();
    expect(originalUnitHint("abc", CELSIUS)).toBeNull();
    expect(originalUnitHint("291.15", null)).toBeNull();
    expect(originalUnitHint("65", PERCENT)).toBeNull();
    expect(originalUnitHint("5", { ...MBAR, factor_to_si: 0 })).toBeNull();
  });
});
