import type { BackendSource, DocItem } from "../types";

// ── Client gọi backend RAG thật (api_server.py, FastAPI + SSE) ──
// Port từ frontend-legacy/src/utils/{api.js,latex.js}, có thêm AbortSignal + health.

export interface SseEvent {
  type: "status" | "sources" | "delta" | "done" | "error";
  text?: string;
  answer?: string;
  sources?: BackendSource[];
}

export interface HistoryTurn {
  role: "user" | "assistant";
  content: string;
}

/** SSE generator: POST {message, history} → yield từng event đã parse. */
export async function* streamChat(message: string, history: HistoryTurn[], signal?: AbortSignal): AsyncGenerator<SseEvent> {
  const response = await fetch("/api/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, history }),
    signal,
  });

  if (!response.ok || !response.body) {
    const text = await response.text().catch(() => response.statusText);
    throw new Error(`HTTP ${response.status}: ${text}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      try {
        yield JSON.parse(line.slice(6)) as SseEvent;
      } catch {
        /* bỏ dòng hỏng */
      }
    }
  }
}

export async function fetchExamples(): Promise<string[]> {
  try {
    const res = await fetch("/api/examples");
    if (!res.ok) return [];
    const data = await res.json();
    return data.examples ?? [];
  } catch {
    return [];
  }
}

export async function pingHealth(): Promise<boolean> {
  try {
    const res = await fetch("/api/health");
    return res.ok;
  } catch {
    return false;
  }
}

// ── Tài liệu thật: upload → xử lý → xem/xoá/đổi tên (api_server.py /api/documents/*) ──

async function _json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function fetchDocuments(): Promise<DocItem[]> {
  const res = await fetch("/api/documents");
  const data = await _json<{ documents: DocItem[] }>(res);
  return data.documents;
}

export async function uploadDocument(file: File): Promise<DocItem> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch("/api/documents/upload", { method: "POST", body: form });
  return _json<DocItem>(res);
}

export async function processDocument(fileStem: string): Promise<void> {
  const res = await fetch(`/api/documents/${encodeURIComponent(fileStem)}/process`, { method: "POST" });
  await _json(res);
}

export async function fetchDocumentMarkdown(fileStem: string): Promise<string> {
  const res = await fetch(`/api/documents/${encodeURIComponent(fileStem)}/markdown`);
  const data = await _json<{ markdown: string }>(res);
  return data.markdown;
}

/** URL tệp gốc (.docx/.pdf) thô — dùng để hiển thị "tài liệu gốc", không phải Markdown đã trích xuất/embed. */
export function documentFileUrl(fileStem: string): string {
  return `/api/documents/${encodeURIComponent(fileStem)}/file`;
}

export async function deleteDocument(fileStem: string): Promise<void> {
  const res = await fetch(`/api/documents/${encodeURIComponent(fileStem)}`, { method: "DELETE" });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail || `HTTP ${res.status}`);
  }
}

export async function renameDocument(fileStem: string, name: string): Promise<DocItem> {
  const res = await fetch(`/api/documents/${encodeURIComponent(fileStem)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  return _json<DocItem>(res);
}

/** Chuẩn hoá LaTeX từ LLM để KaTeX/remark-math render được (port app.py _fix_latex). */
export function fixLatex(text: string): string {
  if (!text) return "";
  text = text.replace(/`(\$[^`]+?\$)`/g, "$1");
  text = text.replace(/\\\[([\s\S]+?)\\\]/g, (_, m) => "$$" + m.replace(/\\\\/g, "\\") + "$$");
  text = text.replace(/\\\(([\s\S]+?)\\\)/g, (_, m) => "$" + m.replace(/\\\\/g, "\\") + "$");
  text = text.replace(/\$\$([\s\S]+?)\$\$/g, (_, m) => "$$" + m.replace(/\\\\/g, "\\") + "$$");
  text = text.replace(/(?<!\$)\$([^\n$]+?)\$(?!\$)/g, (_, m) => "$" + m.replace(/\\\\/g, "\\") + "$");
  return text;
}
