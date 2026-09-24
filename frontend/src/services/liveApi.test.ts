import { afterEach, describe, expect, it, vi } from "vitest";
import { deleteDocument, fetchDocuments, fixLatex, streamChat, uploadDocument } from "./liveApi";
import { TOKEN_KEY } from "./auth";

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

// ── Route đọc công khai, route ghi gắn bearer token (Sprint 1) ──
function mockFetch(impl: () => Promise<Response>) {
  return vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => impl());
}

describe("liveApi — đọc công khai / ghi có xác thực", () => {
  afterEach(() => {
    localStorage.clear();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("fetchDocuments không gắn Authorization (đọc được khi chưa đăng nhập)", async () => {
    const spy = mockFetch(async () => new Response(JSON.stringify({ documents: [] }), { status: 200, headers: { "Content-Type": "application/json" } }));
    vi.stubGlobal("fetch", spy);

    await fetchDocuments();

    expect(spy.mock.calls[0][1]).toBeUndefined();
  });

  it("deleteDocument gắn Authorization: Bearer", async () => {
    localStorage.setItem(TOKEN_KEY, "header.payload.sig");
    const spy = mockFetch(async () => new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", spy);

    await deleteDocument("stem");

    const init = spy.mock.calls[0][1] as RequestInit;
    expect((init.headers as Headers).get("Authorization")).toBe("Bearer header.payload.sig");
  });

  it("uploadDocument gắn Authorization: Bearer", async () => {
    localStorage.setItem(TOKEN_KEY, "header.payload.sig");
    const doc = { id: "a", name: "a.docx", ext: "DOCX", size: "1 KB", pages: "—", date: "2026-01-01", status: "pending" };
    const spy = mockFetch(async () => new Response(JSON.stringify(doc), { status: 200, headers: { "Content-Type": "application/json" } }));
    vi.stubGlobal("fetch", spy);

    const out = await uploadDocument(new File(["x"], "a.docx"));

    const init = spy.mock.calls[0][1] as RequestInit;
    expect((init.headers as Headers).get("Authorization")).toBe("Bearer header.payload.sig");
    expect(out.id).toBe("a");
  });

  it("streamChat phân tích event data của chat lai (Sprint 9)", async () => {
    const payload = {
      intent: "latest_record",
      branch: "data",
      title: "Lần kiểm định gần nhất",
      note: "sổ cái",
      empty: false,
      tables: [],
      citations: [],
    };
    const sse =
      [
        `data: ${JSON.stringify({ type: "data", data: payload })}`,
        `data: ${JSON.stringify({ type: "done", answer: "Kết quả tra cứu:", sources: [], branch: "data", data: payload })}`,
        "",
      ].join("\n\n") + "\n\n";
    vi.stubGlobal(
      "fetch",
      mockFetch(async () => new Response(sse, { status: 200, headers: { "Content-Type": "text/event-stream" } })),
    );

    const events = [];
    for await (const ev of streamChat("Lần kiểm định gần nhất của SN-1?", [])) events.push(ev);

    expect(events[0].type).toBe("data");
    expect(events[0].data?.intent).toBe("latest_record");
    expect(events[1].branch).toBe("data");
    expect(events[1].data?.branch).toBe("data");
  });
});
