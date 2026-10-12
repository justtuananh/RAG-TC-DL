import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import Toast from "./Toast";

// Toast mang `kind`: thành công dùng dấu tích + màu xanh, lỗi dùng icon cảnh báo
// + màu `COLOR.danger`; nền toast giữ nguyên.

const CHECK = 'points="20 6 9 17 4 12"';
const ALERT = 'cx="12" cy="12" r="10"';

describe("Toast - icon theo loại", () => {
  it("loại success: dấu tích, màu thành công", () => {
    const html = renderToStaticMarkup(<Toast toast={{ message: "Đã xoá tài liệu", kind: "success" }} />);
    expect(html).toContain(CHECK);
    expect(html).not.toContain(ALERT);
    expect(html).toContain("#B9E0C9"); // COLOR.successBorder
    expect(html).not.toContain("#C8102E"); // COLOR.danger
  });

  it("loại error: icon cảnh báo, màu nguy hiểm", () => {
    const html = renderToStaticMarkup(<Toast toast={{ message: "Chỉ hỗ trợ quy trình kiểm định dạng Word...", kind: "error" }} />);
    expect(html).toContain(ALERT);
    expect(html).not.toContain(CHECK);
    expect(html).toContain("#C8102E"); // COLOR.danger
    expect(html).toContain("Chỉ hỗ trợ quy trình kiểm định dạng Word...");
  });

  it("không có toast thì không render gì", () => {
    expect(renderToStaticMarkup(<Toast toast={null} />)).toBe("");
  });
});
