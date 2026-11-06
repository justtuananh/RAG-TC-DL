import { afterEach, describe, expect, it, vi } from "vitest";
import { deleteDocument, downloadDocument, fetchDocuments, filenameFromDisposition, fixLatex, streamChat, uploadDocument } from "./liveApi";
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

// ── Đăng nhập bắt buộc: mọi route (đọc lẫn ghi, trừ health) gắn bearer token ──
function mockFetch(impl: () => Promise<Response>) {
  return vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => impl());
}

describe("liveApi - mọi route dữ liệu có xác thực", () => {
  afterEach(() => {
    localStorage.clear();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("fetchDocuments gắn Authorization: Bearer", async () => {
    localStorage.setItem(TOKEN_KEY, "header.payload.sig");
    const spy = mockFetch(async () => new Response(JSON.stringify({ documents: [] }), { status: 200, headers: { "Content-Type": "application/json" } }));
    vi.stubGlobal("fetch", spy);

    await fetchDocuments();

    const init = spy.mock.calls[0][1] as RequestInit;
    expect((init.headers as Headers).get("Authorization")).toBe("Bearer header.payload.sig");
  });

  it("streamChat gắn Authorization: Bearer", async () => {
    localStorage.setItem(TOKEN_KEY, "header.payload.sig");
    const spy = mockFetch(async () => new Response("\n", { status: 200, headers: { "Content-Type": "text/event-stream" } }));
    vi.stubGlobal("fetch", spy);

    for await (const _ev of streamChat("câu hỏi", [])) {
      /* không có event */
    }

    const init = spy.mock.calls[0][1] as RequestInit;
    expect((init.headers as Headers).get("Authorization")).toBe("Bearer header.payload.sig");
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

  it("streamChat phân tích chuỗi event văn bản (sources + done)", async () => {
    const source = {
      index: 1,
      file_stem: "QTKD_1.159_2021",
      section_path: "6.3.2",
      kind: "paragraph",
      snippet: "…",
      rerank_score: 0.7,
      parent_text: "…",
      child_text: "…",
    };
    const sse =
      [
        `data: ${JSON.stringify({ type: "sources", sources: [source] })}`,
        `data: ${JSON.stringify({ type: "done", answer: "Tối thiểu 10 s [1].", sources: [source] })}`,
        "",
      ].join("\n\n") + "\n\n";
    vi.stubGlobal(
      "fetch",
      mockFetch(async () => new Response(sse, { status: 200, headers: { "Content-Type": "text/event-stream" } })),
    );

    const events = [];
    for await (const ev of streamChat("Thời gian quay tự do tối thiểu?", [])) events.push(ev);

    expect(events[0].type).toBe("sources");
    expect(events[0].sources?.[0].file_stem).toBe("QTKD_1.159_2021");
    expect(events[1].type).toBe("done");
    // done mang câu trả lời cuối của server (đã sửa LaTeX, chèn lời dẫn mơ hồ thiết bị)
    expect(events[1].answer).toBe("Tối thiểu 10 s [1].");
  });
});

describe("filenameFromDisposition", () => {
  it("ưu tiên filename* (UTF-8, tên tiếng Việt)", () => {
    const header = "attachment; filename*=utf-8''QTK%C4%90%201.159.docx";
    expect(filenameFromDisposition(header, "x")).toBe("QTKĐ 1.159.docx");
  });
  it("đọc filename thường", () => {
    expect(filenameFromDisposition('attachment; filename="QTKD_1.061.pdf"', "x")).toBe("QTKD_1.061.pdf");
  });
  it("không có header → tên dự phòng", () => {
    expect(filenameFromDisposition(null, "QTKD_1.062")).toBe("QTKD_1.062");
  });
});

describe("downloadDocument", () => {
  afterEach(() => {
    localStorage.clear();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("tải qua /download có token và lưu đúng tên tệp gốc", async () => {
    localStorage.setItem(TOKEN_KEY, "header.payload.sig");
    const spy = mockFetch(
      async () =>
        new Response(new Blob(["docx"]), {
          status: 200,
          headers: { "Content-Disposition": "attachment; filename*=utf-8''QTK%C4%90%201.159.docx" },
        }),
    );
    vi.stubGlobal("fetch", spy);
    const createUrl = vi.fn(() => "blob:mock");
    vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: createUrl, revokeObjectURL: vi.fn() }));
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});

    const name = await downloadDocument("QTKD_1.159");

    expect(spy.mock.calls[0][0]).toBe("/api/documents/QTKD_1.159/download");
    const init = spy.mock.calls[0][1] as RequestInit;
    expect((init.headers as Headers).get("Authorization")).toBe("Bearer header.payload.sig");
    expect(name).toBe("QTKĐ 1.159.docx");
    expect(createUrl).toHaveBeenCalledOnce();
    expect(click).toHaveBeenCalledOnce();
  });

  it("báo lỗi chi tiết từ máy chủ khi không tải được", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetch(
        async () => new Response(JSON.stringify({ detail: "Không tìm thấy tệp gốc." }), { status: 404, headers: { "Content-Type": "application/json" } }),
      ),
    );
    await expect(downloadDocument("x")).rejects.toThrow("Không tìm thấy tệp gốc.");
  });
});
