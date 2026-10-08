/// <reference types="vite/client" />
import { describe, expect, it } from "vitest";

// Theme "Xanh quân đội": bảo đảm không còn sót mã xanh dương "Signal Blue" cũ
// rải rác trong mã nguồn. Đọc mọi file nguồn, trừ màu tệp Excel gốc (xlsx/) và
// màu nhận diện định dạng tệp demo (mockEngine.ts), cùng chính các file test.

const FORBIDDEN = ["#2454E0", "#173CAE", "#E9EFFF", "#C9D8FF", "#0F1B36", "#16264A", "#8FA8FF", "36,84,224"];

// import.meta.glob của Vite: nạp thô toàn bộ nguồn dưới src/ khi test chạy.
const sources = import.meta.glob("./**/*.{ts,tsx,css}", {
  query: "?raw",
  import: "default",
  eager: true,
}) as Record<string, string>;

function excluded(path: string): boolean {
  return path.includes("/xlsx/") || path.endsWith("/mockEngine.ts") || /\.test\.tsx?$/.test(path);
}

const entries = Object.entries(sources).filter(([path]) => !excluded(path));

describe("theme Xanh quân đội — hết mã xanh dương cũ", () => {
  it("có file nguồn để quét", () => {
    expect(entries.length).toBeGreaterThan(0);
  });

  it.each(entries)("%s không còn mã xanh dương cũ", (_path, content) => {
    const lower = content.toLowerCase();
    for (const needle of FORBIDDEN) {
      expect(lower).not.toContain(needle.toLowerCase());
    }
  });
});
