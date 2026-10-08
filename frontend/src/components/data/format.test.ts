import { describe, expect, it } from "vitest";
import { EXPIRY_WARNING_DAYS, expiryStatus } from "./format";

// Trạng thái hiệu lực hồ sơ: hết hạn, sắp hết hạn (≤ 60 ngày), còn hạn, ngày rỗng.

const NOW = new Date("2026-01-01T00:00:00Z");
const daysFromNow = (days: number) => new Date(NOW.getTime() + days * 24 * 60 * 60 * 1000).toISOString();

describe("expiryStatus", () => {
  it("đã hết hạn", () => {
    const status = expiryStatus(daysFromNow(-1), NOW);
    expect(status.state).toBe("expired");
    expect(status.label).toBe("Hết hạn");
  });

  it("còn đúng ngưỡng 60 ngày là sắp hết hạn", () => {
    expect(EXPIRY_WARNING_DAYS).toBe(60);
    const status = expiryStatus(daysFromNow(60), NOW);
    expect(status.state).toBe("warning");
    expect(status.label).toBe("Sắp hết hạn");
  });

  it("còn 61 ngày là còn hạn", () => {
    expect(expiryStatus(daysFromNow(61), NOW).state).toBe("valid");
    expect(expiryStatus(daysFromNow(61), NOW).label).toBe("Còn hạn");
  });

  it("ngày rỗng trả không rõ hạn", () => {
    const status = expiryStatus(null, NOW);
    expect(status.state).toBe("unknown");
    expect(status.days).toBeNull();
  });

  it("ngày không hợp lệ trả không rõ hạn", () => {
    expect(expiryStatus("khong-phai-ngay", NOW).state).toBe("unknown");
  });
});
