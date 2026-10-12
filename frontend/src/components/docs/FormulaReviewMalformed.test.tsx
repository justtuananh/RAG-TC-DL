import { act } from "react";
import { createRoot } from "react-dom/client";
import { expect, it, vi } from "vitest";
import FormulaReviewPanel from "./FormulaReviewPanel";

it("shows a recoverable error instead of crashing when the real service receives an old malformed record", async () => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  const fetcher = vi.fn().mockImplementation(async () => new Response(JSON.stringify({ drafts: [{ proposal: { variables: null } }], units: ["Pa"] })));
  vi.stubGlobal("fetch", fetcher);
  const host = document.createElement("div");
  document.body.append(host);
  const root = createRoot(host);
  try {
    await act(async () => {
      root.render(<FormulaReviewPanel documentId="old-record" isDocx />);
    });
    expect(host.querySelector('[role="alert"]')?.textContent).toContain("không đúng cấu trúc");
    expect(host.querySelector('[aria-label="Tên công thức"]')).toBeNull();
    fetcher.mockImplementation(async () => new Response(JSON.stringify({ drafts: [], units: ["Pa"] })));
    const retry = [...host.querySelectorAll("button")].find((b) => b.textContent === "Tải lại danh sách")!;
    expect(retry.disabled).toBe(false);
    await act(async () => {
      retry.click();
    });
    expect(host.querySelector('[role="alert"]')).toBeNull();
    expect(host.textContent).toContain("Chưa có bản nháp");
  } finally {
    await act(async () => {
      root.unmount();
    });
    host.remove();
    vi.unstubAllGlobals();
  }
});
