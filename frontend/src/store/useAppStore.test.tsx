import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useAppStore } from "./useAppStore";
import * as api from "../services/liveApi";
import type { DocItem, DocStatus } from "../types";

vi.mock("../services/liveApi");
let store: ReturnType<typeof useAppStore>;
let root: Root;
let host: HTMLDivElement;
function Harness() {
  store = useAppStore();
  return null;
}
const documentItem = (status: DocStatus, id = "uploaded"): DocItem => ({
  id,
  name: `${id}.docx`,
  ext: "DOCX",
  size: "2 KB",
  pages: "—",
  date: "2026-09-28",
  status,
});
beforeEach(async () => {
  vi.resetAllMocks();
  localStorage.clear();
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  vi.mocked(api.fetchExamples).mockResolvedValue([]);
  vi.mocked(api.fetchDocuments).mockResolvedValue([]);
  vi.mocked(api.pingHealth).mockResolvedValue(false);
  vi.mocked(api.documentFileUrl).mockImplementation((id) => `/api/documents/${id}/file`);
  vi.mocked(api.fetchDocumentMarkdown).mockRejectedValue(new Error("Chưa có markdown"));
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  await act(async () => {
    root.render(<Harness />);
  });
});
afterEach(async () => {
  await act(async () => {
    root.unmount();
  });
  host.remove();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("view uploaded source independently of ingestion readiness", () => {
  it.each(["pending", "processing", "error", "ready"] as const)("opens DOCX in status %s even without extracted markdown", async (status) => {
    const doc = documentItem(status);
    await act(async () => {
      store.actions.viewDoc(doc);
    });
    expect(store.state.viewingDoc).toMatchObject({ code: doc.id, ext: "DOCX", status, fileUrl: `/api/documents/${doc.id}/file` });
    expect(store.state.toast).toBeNull();
  });
  it("does not attach delayed markdown to a different document opened meanwhile", async () => {
    let resolveFirst!: (text: string) => void;
    vi.mocked(api.fetchDocumentMarkdown).mockImplementation((id) =>
      id === "first"
        ? new Promise((resolve) => {
            resolveFirst = resolve;
          })
        : Promise.resolve("Second source"),
    );
    await act(async () => {
      store.actions.viewDoc(documentItem("processing", "first"));
    });
    await act(async () => {
      store.actions.viewDoc(documentItem("error", "second"));
    });
    await act(async () => {
      resolveFirst("First source");
    });
    expect(store.state.viewingDoc).toMatchObject({ code: "second", markdown: "Second source" });
  });
});

describe("unsaved formula navigation", () => {
  it.each(["guide", "chat", "close", "new", "document", "conversation"])("cancels %s without changing state", async (target) => {
    await act(async () => {
      store.actions.go("docs");
      store.actions.viewDoc(documentItem("ready"));
    });
    store.actions.setFormulaDirty(true);
    const before = store.state;
    const confirm = vi.fn(() => false);
    vi.stubGlobal("confirm", confirm);
    await act(async () => {
      if (target === "guide" || target === "chat") store.actions.go(target);
      else if (target === "close") store.actions.closeViewer();
      else if (target === "new") store.actions.newChat();
      else if (target === "document") store.actions.viewDoc(documentItem("ready", "other"));
      else store.actions.openConv({ id: "another" } as Parameters<typeof store.actions.openConv>[0]);
    });
    expect(confirm).toHaveBeenCalledOnce();
    expect(store.state).toBe(before);
  });
  it("allows confirmed navigation and skips confirmation for a clean editor or the same tab", async () => {
    await act(async () => {
      store.actions.go("docs");
    });
    store.actions.setFormulaDirty(true);
    const confirm = vi.fn(() => true);
    vi.stubGlobal("confirm", confirm);
    await act(async () => {
      store.actions.go("docs");
    });
    expect(confirm).not.toHaveBeenCalled();
    await act(async () => {
      store.actions.go("guide");
    });
    expect(confirm).toHaveBeenCalledOnce();
    expect(store.state.tab).toBe("guide");
    store.actions.setFormulaDirty(false);
    await act(async () => {
      store.actions.go("chat");
    });
    expect(confirm).toHaveBeenCalledOnce();
  });
});
