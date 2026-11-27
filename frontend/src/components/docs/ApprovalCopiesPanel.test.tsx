import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import type { UserRole } from "../../types";
import ApprovalCopiesPanel from "./ApprovalCopiesPanel";

const COPY = {
  id: "a".repeat(32),
  name: "ban-ky-duyet.pdf",
  ext: ".pdf",
  media_type: "application/pdf",
  size: 2048,
  uploaded_at: "2026-11-27T08:00:00.000000+00:00",
  uploaded_by: "approver",
};

let host: HTMLDivElement;
let root: Root;

beforeEach(() => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  URL.createObjectURL = vi.fn(() => "about:blank");
  URL.revokeObjectURL = vi.fn();
});

afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
  vi.unstubAllGlobals();
});

async function render(role: UserRole | null) {
  await act(async () => {
    root.render(<ApprovalCopiesPanel documentId="doc" role={role} />);
  });
}

function stubServer(copies: () => unknown[], upload: () => Response = () => new Response(JSON.stringify(COPY), { status: 201 })) {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith("/file")) return new Response(new Blob(["%PDF-"]));
    if (init?.method === "POST") return upload();
    if (init?.method === "DELETE") return new Response(null, { status: 204 });
    return new Response(JSON.stringify({ copies: copies() }));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

async function pick(file: File) {
  const input = host.querySelector<HTMLInputElement>('[data-testid="approval-copy-input"]')!;
  Object.defineProperty(input, "files", { value: [file], configurable: true });
  await act(async () => {
    input.dispatchEvent(new Event("change", { bubbles: true }));
  });
}

it("shows the newest copy in the viewer and says the chatbot does not read it", async () => {
  stubServer(() => [COPY]);
  await render("viewer");
  expect(host.textContent).toContain("Chatbot không đọc các tệp này");
  expect(host.textContent).toContain("ban-ky-duyet.pdf");
  expect(host.textContent).toContain("2 KB");
  expect(host.querySelector("iframe")?.getAttribute("src")).toBe("about:blank");
});

it("hides upload and delete from viewers", async () => {
  stubServer(() => [COPY]);
  await render("viewer");
  expect(host.textContent).not.toContain("Tải lên PDF hoặc ảnh");
  expect(host.querySelector('[aria-label="Xoá ban-ky-duyet.pdf"]')).toBeNull();
});

it("uploads a picked file as multipart and shows it", async () => {
  let stored: unknown[] = [];
  const fetchMock = stubServer(
    () => stored,
    () => {
      stored = [COPY];
      return new Response(JSON.stringify(COPY), { status: 201 });
    },
  );
  await render("technician");
  expect(host.textContent).toContain("Chưa có bản phê duyệt nào");
  const file = new File(["%PDF-"], "ban-ky-duyet.pdf", { type: "application/pdf" });
  await pick(file);
  const post = fetchMock.mock.calls.find(([, init]) => init?.method === "POST");
  expect(post?.[0]).toBe("/api/documents/doc/approval-copies");
  expect((post?.[1]?.body as FormData).get("file")).toBe(file);
  expect(host.textContent).toContain("ban-ky-duyet.pdf");
});

it("shows the server's reason when an upload is rejected", async () => {
  stubServer(
    () => [],
    () => new Response(JSON.stringify({ detail: "Chỉ nhận tệp PDF, PNG, JPG hoặc WEBP." }), { status: 400 }),
  );
  await render("admin");
  await pick(new File(["x"], "a.docx"));
  expect(host.querySelector('[role="alert"]')?.textContent).toContain("a.docx: Chỉ nhận tệp PDF, PNG, JPG hoặc WEBP.");
});

it("deletes a copy only after confirmation", async () => {
  const fetchMock = stubServer(() => [COPY]);
  const confirm = vi.fn(() => false);
  vi.stubGlobal("confirm", confirm);
  await render("technician");
  const del = host.querySelector<HTMLButtonElement>('[aria-label="Xoá ban-ky-duyet.pdf"]')!;
  await act(async () => del.click());
  expect(fetchMock.mock.calls.some(([, init]) => init?.method === "DELETE")).toBe(false);
  confirm.mockReturnValue(true);
  await act(async () => del.click());
  expect(fetchMock.mock.calls.some(([url, init]) => init?.method === "DELETE" && url === `/api/documents/doc/approval-copies/${COPY.id}`)).toBe(true);
});
