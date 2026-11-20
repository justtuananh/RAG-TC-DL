import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import type { UserRole } from "../../types";
import SummaryReviewPanel from "./SummaryReviewPanel";

const DRAFT = {
  document_id: "doc",
  status: "draft",
  text: "- **Đối tượng:** van an toàn đến 1 400 bar.",
  generated_text: "- **Đối tượng:** van an toàn đến 1 400 bar.",
  warnings: ["Số liệu không thấy trong tài liệu: 12"],
  model: "qwen",
  error: null,
  revision: 3,
  generated_at: "2026-11-20T10:00:00",
  edited_by: null,
  edited_at: null,
  reviewed_by: null,
  reviewed_at: null,
  review_note: null,
  stale: false,
};

let host: HTMLDivElement;
let root: Root;

beforeEach(() => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
});

afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
  vi.unstubAllGlobals();
});

async function render(role: UserRole | null) {
  await act(async () => {
    root.render(<SummaryReviewPanel documentId="doc" role={role} />);
  });
}

const buttons = () => [...host.querySelectorAll("button")].map((b) => b.textContent);

it("shows the draft, its number warnings and only the actions the role allows", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(JSON.stringify({ summary: DRAFT }))),
  );
  await render("viewer");
  expect(host.textContent).toContain("Chờ phê duyệt");
  expect(host.textContent).toContain("Số liệu không thấy trong tài liệu: 12");
  expect(host.textContent).toContain("van an toàn đến 1 400 bar");
  expect(buttons()).toEqual([]);
});

it("lets an approver approve the current revision", async () => {
  const approved = { ...DRAFT, status: "approved", revision: 4, reviewed_by: "duyet", reviewed_at: "2026-11-20T11:00:00" };
  const fetcher = vi.fn(async (_url: string, init?: RequestInit) => new Response(JSON.stringify({ summary: init?.method === "POST" ? approved : DRAFT })));
  vi.stubGlobal("fetch", fetcher);
  await render("approver");
  expect(buttons()).not.toContain("Sinh lại bằng LLM");
  const approve = [...host.querySelectorAll("button")].find((b) => b.textContent === "Phê duyệt")!;
  await act(async () => approve.click());
  const [url, init] = fetcher.mock.calls[fetcher.mock.calls.length - 1];
  expect(url).toBe("/api/documents/doc/summary/approve");
  expect(JSON.parse(String(init?.body))).toEqual({ revision: 3, note: "" });
  expect(host.textContent).toContain("Đã phê duyệt. Chatbot dùng bản tóm tắt này từ bây giờ.");
  expect(buttons()).toContain("Thu hồi phê duyệt");
});

it("offers generation to a technician when there is no summary yet", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(JSON.stringify({ summary: null }))),
  );
  await render("technician");
  expect(host.textContent).toContain("Tài liệu chưa có bản tóm tắt.");
  expect(buttons()).toEqual(["Sinh bản tóm tắt"]);
});

it("keeps polling while the server says the document is queued, then shows the result", async () => {
  vi.useFakeTimers();
  try {
    const replies = [
      { summary: null, queued: true },
      { summary: { ...DRAFT, status: "generating" }, queued: true },
      { summary: DRAFT, queued: false },
    ];
    const fetcher = vi.fn(async () => new Response(JSON.stringify(replies.shift() ?? { summary: DRAFT, queued: false })));
    vi.stubGlobal("fetch", fetcher);
    await render("technician");
    expect(buttons()).toEqual(["Đang sinh…"]);
    await act(async () => vi.advanceTimersByTime(4000));
    expect(buttons()).toEqual(["Đang sinh…"]);
    await act(async () => vi.advanceTimersByTime(4000));
    expect(host.textContent).toContain("Chờ phê duyệt");
    expect(buttons()).toContain("Sinh lại bằng LLM");
    const calls = fetcher.mock.calls.length;
    await act(async () => vi.advanceTimersByTime(12000));
    expect(fetcher.mock.calls.length).toBe(calls); // hết hàng đợi thì thôi hỏi lại
  } finally {
    vi.useRealTimers();
  }
});

it("lets a technician regenerate a summary whose generation was interrupted", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(JSON.stringify({ summary: { ...DRAFT, status: "generating" }, queued: false }))),
  );
  await render("technician");
  expect(host.textContent).toContain("Lần sinh trước bị gián đoạn");
  const regenerate = [...host.querySelectorAll("button")].find((b) => b.textContent === "Sinh lại bằng LLM")!;
  expect(regenerate.disabled).toBe(false);
});
