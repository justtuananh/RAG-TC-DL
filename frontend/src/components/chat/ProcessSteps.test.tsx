import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { StepList } from "./ProcessSteps";

// Các pha luôn đọc từ trên xuống: pha trước xong mới tới pha sau, pha chưa tới thì ẩn.
function phases(step: number): { phase: string; done: string }[] {
  const html = renderToStaticMarkup(<StepList proc={{ step, passages: 5, docs: 2 }} />);
  return [...html.matchAll(/data-phase="(\d)" data-done="(true|false)"/g)].map((m) => ({ phase: m[1], done: m[2] }));
}

describe("StepList", () => {
  it("chỉ có pha đầu đang chạy khi mới gửi", () => {
    expect(phases(0)).toEqual([{ phase: "0", done: "false" }]);
  });

  it("pha giữa đang chạy thì pha đầu đã xong, pha cuối chưa hiện", () => {
    expect(phases(1)).toEqual([
      { phase: "0", done: "true" },
      { phase: "1", done: "false" },
    ]);
  });

  it("pha cuối đang chạy thì mọi pha trước đã xong", () => {
    expect(phases(2)).toEqual([
      { phase: "0", done: "true" },
      { phase: "1", done: "true" },
      { phase: "2", done: "false" },
    ]);
  });

  it("dùng số đoạn và số tài liệu thật", () => {
    expect(renderToStaticMarkup(<StepList proc={{ step: 1, passages: 5, docs: 2 }} />)).toContain("Tìm được 5 đoạn liên quan trong 2 tài liệu");
  });
});
