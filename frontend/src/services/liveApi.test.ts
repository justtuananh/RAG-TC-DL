import { describe, it, expect } from "vitest";
import { fixLatex } from "./liveApi";

describe("fixLatex", () => {
  it("giữ nguyên text thường", () => {
    expect(fixLatex("Thời gian quay tự do ≥ 3 phút")).toBe("Thời gian quay tự do ≥ 3 phút");
  });
  it("chuỗi rỗng → rỗng", () => {
    expect(fixLatex("")).toBe("");
  });
  it("bỏ backtick quanh công thức", () => {
    expect(fixLatex("`$x$`")).toBe("$x$");
  });
  it("\\(...\\) → $...$ (inline)", () => {
    expect(fixLatex("\\(a+b\\)")).toBe("$a+b$");
  });
  it("\\[...\\] → $$...$$ (display)", () => {
    expect(fixLatex("\\[a\\]")).toBe("$$a$$");
  });
  it("gộp \\\\ thành \\ trong $$...$$", () => {
    expect(fixLatex("$$\\\\frac{a}{b}$$")).toBe("$$\\frac{a}{b}$$");
  });
});
