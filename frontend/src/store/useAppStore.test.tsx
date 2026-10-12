import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { AppState, DocItem } from "../types";
import type { Actions } from "./useAppStore";
import { useAppStore } from "./useAppStore";

// Store tài liệu: sau khi xoá thành công phải NẠP LẠI danh sách (backend có thể
// khôi phục một tài liệu khác về xử lý), và toast báo lỗi phải mang loại "error".

const mocks = vi.hoisted(() => ({
  fetchDocuments: vi.fn(),
  fetchExamples: vi.fn(),
  pingHealth: vi.fn(),
  deleteDocument: vi.fn(),
  uploadDocument: vi.fn(),
}));

vi.mock("../services/liveApi", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../services/liveApi")>();
  return { ...actual, ...mocks };
});

// Cố định người dùng đã đăng nhập (đủ quyền ghi) để thao tác xoá/upload chạy được.
vi.mock("../services/auth", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../services/auth")>();
  return {
    ...actual,
    fetchMe: async () => ({ user: { id: 1, username: "ktv", full_name: "KTV", role: "technician" as const }, authEnabled: true }),
  };
});

(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

function doc(partial: Partial<DocItem> & Pick<DocItem, "id" | "status">): DocItem {
  return { name: `${partial.id}.docx`, ext: "DOCX", size: "1 MB", pages: 1, date: "01/01/2026", ...partial };
}

let latest!: { state: AppState; actions: Actions };

function Harness() {
  latest = useAppStore();
  return null;
}

const flush = () => new Promise((resolve) => setTimeout(resolve, 0));

describe("useAppStore - tài liệu (live)", () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(async () => {
    container = document.createElement("div");
    document.body.appendChild(container);
    mocks.fetchDocuments.mockReset();
    mocks.fetchExamples.mockReset().mockResolvedValue([]);
    mocks.pingHealth.mockReset().mockResolvedValue(true);
    mocks.deleteDocument.mockReset().mockResolvedValue(undefined);
    mocks.uploadDocument.mockReset();
    mocks.fetchDocuments.mockResolvedValue([doc({ id: "d1", status: "ready" })]);

    await act(async () => {
      root = createRoot(container);
      root.render(createElement(Harness));
      await flush();
    });
    await act(flush);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  it("xoá xong thì nạp lại danh sách (tài liệu được khôi phục về processing)", async () => {
    expect(latest.state.auth.user).not.toBeNull();
    expect(latest.state.documents.map((d) => d.id)).toEqual(["d1"]);

    // Backend trả về danh sách mới: d1 đã biến mất, d2 được khôi phục về xử lý.
    mocks.fetchDocuments.mockResolvedValue([doc({ id: "d2", status: "processing", progress: 10 })]);

    await act(async () => {
      latest.actions.deleteDoc("d1");
      await flush();
    });
    await act(flush);

    expect(mocks.deleteDocument).toHaveBeenCalledWith("d1");
    // Gọi lại /api/documents (lần mount + lần sau xoá).
    expect(mocks.fetchDocuments.mock.calls.length).toBeGreaterThanOrEqual(2);
    expect(latest.state.documents.map((d) => d.id)).toEqual(["d2"]);
    expect(latest.state.documents[0].status).toBe("processing");
  });

  it("upload thất bại báo toast loại error", async () => {
    const message = "Chỉ hỗ trợ quy trình kiểm định dạng Word (.docx/.doc) và PDF.";
    mocks.uploadDocument.mockRejectedValue(new Error(message));

    await act(async () => {
      latest.actions.uploadDoc(new File(["x"], "bảng.xlsx"));
      await flush();
    });

    expect(latest.state.toast).toEqual({ message, kind: "error" });
  });
});
