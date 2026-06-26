import { describe, it, expect } from "vitest";
import { DOCUMENTS, FAQS, SAMPLES, SOURCES } from "./seed";

describe("seed", () => {
  it("SAMPLES là danh sách câu hỏi không rỗng", () => {
    expect(SAMPLES.length).toBeGreaterThan(0);
    expect(typeof SAMPLES[0]).toBe("string");
  });
  it("FAQS có q + a", () => {
    expect(FAQS[0]).toHaveProperty("q");
    expect(FAQS[0]).toHaveProperty("a");
  });
  it("SOURCES có id/code + blocks", () => {
    expect(SOURCES[0]).toMatchObject({ id: expect.any(String), code: expect.any(String) });
    expect(Array.isArray(SOURCES[0].blocks)).toBe(true);
  });
  it("DOCUMENTS có ext hợp lệ", () => {
    expect(DOCUMENTS.every((d) => ["PDF", "DOCX", "XLSX"].includes(d.ext))).toBe(true);
  });
});
