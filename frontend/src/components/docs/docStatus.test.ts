import { describe, expect, it } from "vitest";
import { STATUS_STYLE, STATUS_TAB_LABEL, statusLabel } from "./docStatus";

// Trạng thái "superseded" (QTKĐ cũ đã có phiên bản mới hơn): nhãn rõ ràng,
// tô màu trung tính như "pending" và không bị coi là lỗi.

describe("statusLabel", () => {
  it('trả "Đã thay thế" cho superseded', () => {
    expect(statusLabel({ status: "superseded", progress: 0, error: "Đã có phiên bản mới hơn" })).toBe("Đã thay thế");
  });

  it('trả "Đã sẵn sàng" cho ready', () => {
    expect(statusLabel({ status: "ready", progress: 0 })).toBe("Đã sẵn sàng");
  });

  it('trả "Lỗi xử lý" cho error (case tường minh, không rơi vào default)', () => {
    expect(statusLabel({ status: "error", progress: 0, error: "Hỏng tệp" })).toBe("Lỗi xử lý");
  });
});

describe("trạng thái superseded", () => {
  it("có nhãn tab Đã thay thế", () => {
    expect(STATUS_TAB_LABEL.superseded).toBe("Đã thay thế");
  });

  it("dùng bộ màu trung tính giống pending, không phải danger", () => {
    expect(STATUS_STYLE.superseded).toEqual(STATUS_STYLE.pending);
    expect(STATUS_STYLE.superseded.color).not.toBe(STATUS_STYLE.error.color);
    expect(STATUS_STYLE.superseded.bg).not.toBe(STATUS_STYLE.error.bg);
  });
});
