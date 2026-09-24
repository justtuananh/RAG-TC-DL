import { describe, expect, it } from "vitest";
import { COLOR } from "../../theme";
import { contrastRatio, meetsAA } from "./contrast";

// Kiểm tra tương phản WCAG 2.1 AA cho đúng các cặp màu dùng ở tab Dữ liệu.
// Chữ thường yêu cầu ≥ 4.5:1; chỉ báo dạng badge đặc (chữ trắng trên nền đậm)
// cũng phải ≥ 4.5:1 vì là văn bản phải đọc.

const NORMAL_TEXT: Array<[string, string, string]> = [
  ["Chữ chính trên nền trắng", COLOR.textPrimary, COLOR.surface],
  ["Chữ chính trên dải lọc", COLOR.textPrimary, COLOR.surfaceAlt],
  ["Chữ phụ trên nền trắng", COLOR.textSecondary, COLOR.surface],
  ["Chữ phụ trên dải lọc", COLOR.textSecondary, COLOR.surfaceAlt],
  ["Liên kết/nút xuất xứ trên nền trắng", COLOR.accentDark, COLOR.surface],
  ["Nút xuất xứ trên nền chip", COLOR.accentDark, COLOR.accentSoft],
  ["Nút chính (chữ trắng trên accent)", COLOR.textOnDark, COLOR.accent],
  ["Badge Đạt", COLOR.textOnDark, COLOR.success],
  ["Badge Không đạt", COLOR.textOnDark, COLOR.danger],
  ["Badge cảnh báo", COLOR.textOnDark, COLOR.warning],
  ["Chữ lỗi trên nền lỗi", COLOR.textOnDark, COLOR.danger],
];

describe("Tương phản bảng màu tab Dữ liệu đạt WCAG AA", () => {
  it.each(NORMAL_TEXT)("%s ≥ 4.5:1", (_label, fg, bg) => {
    const ratio = contrastRatio(fg, bg);
    expect(ratio).toBeGreaterThanOrEqual(4.5);
    expect(meetsAA(fg, bg)).toBe(true);
  });

  it("lớp meta dùng màu đủ tương phản cho nhãn phụ", () => {
    // Nhãn phụ (muted) vẫn được kiểm để không rơi dưới ngưỡng chữ lớn 3:1.
    expect(contrastRatio(COLOR.textMuted, COLOR.surface)).toBeGreaterThanOrEqual(3);
  });
});
