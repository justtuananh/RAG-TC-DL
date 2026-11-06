import type { BackendSource, DocItem } from "../types";
import { AuthError, authFetch } from "./auth";

// ── Client gọi backend RAG thật (package api/, FastAPI + SSE) ──
// Port từ frontend-legacy/src/utils/{api.js,latex.js}, có thêm AbortSignal + health.
// Mọi route trừ /api/health đều cần đăng nhập nên đi qua authFetch (bearer token).

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
  const response = await authFetch("/api/chat/stream", {
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
    const res = await authFetch("/api/examples");
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

// ── Tài liệu thật: upload → xử lý → xem/xoá/đổi tên (api/routes/documents.py /api/documents/*) ──

async function _json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const message = body?.detail || `HTTP ${res.status}`;
    // 401 = token thiếu/hết hạn → nơi gọi (store) mở màn hình đăng nhập thay vì báo lỗi chung.
    if (res.status === 401) throw new AuthError(message, 401);
    throw new Error(message);
  }
  return res.json();
}

export async function fetchDocuments(): Promise<DocItem[]> {
  const res = await authFetch("/api/documents");
  const data = await _json<{ documents: DocItem[] }>(res);
  return data.documents;
}

export async function uploadDocument(file: File): Promise<DocItem> {
  const form = new FormData();
  form.append("file", file);
  const res = await authFetch("/api/documents/upload", { method: "POST", body: form });
  return _json<DocItem>(res);
}

export async function processDocument(fileStem: string): Promise<void> {
  const res = await authFetch(`/api/documents/${encodeURIComponent(fileStem)}/process`, { method: "POST" });
  await _json(res);
}

export async function fetchDocumentMarkdown(fileStem: string): Promise<string> {
  const res = await authFetch(`/api/documents/${encodeURIComponent(fileStem)}/markdown`);
  const data = await _json<{ markdown: string }>(res);
  return data.markdown;
}

/** URL tệp gốc (.docx/.pdf) thô — dùng để hiển thị "tài liệu gốc", không phải Markdown đã trích xuất/embed. */
export function documentFileUrl(fileStem: string): string {
  return `/api/documents/${encodeURIComponent(fileStem)}/file`;
}

/** Bản xem trên trình duyệt: .doc/.xls cũ được backend trả dưới dạng .docx/.xlsx đã chuyển. */
export function documentPreviewUrl(fileStem: string): string {
  return `/api/documents/${encodeURIComponent(fileStem)}/preview`;
}

/**
 * Đọc tên tệp từ Content-Disposition: ưu tiên `filename*=UTF-8''…` (tên tiếng Việt),
 * rồi `filename="…"`; không có thì dùng `fallback`.
 */
export function filenameFromDisposition(header: string | null, fallback: string): string {
  if (!header) return fallback;
  const star = /filename\*\s*=\s*(?:UTF-8|utf-8)''([^;]+)/.exec(header);
  if (star) {
    try {
      return decodeURIComponent(star[1].trim());
    } catch {
      /* mã hoá hỏng → thử filename thường */
    }
  }
  const plain = /filename\s*=\s*"?([^";]+)"?/.exec(header);
  return plain ? plain[1].trim() : fallback;
}

/** Lưu một Blob thành tệp tải xuống của trình duyệt. */
function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
  // Trì hoãn thu hồi để trình duyệt kịp bắt đầu tải.
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/**
 * Tải xuống tệp gốc đúng định dạng đã tải lên (.docx/.doc/.pdf/.xlsx/.xls).
 * Cần token nên không dùng được thẻ <a href> trần: tải qua authFetch rồi lưu Blob.
 * Trả về tên tệp đã lưu.
 */
export async function downloadDocument(fileStem: string): Promise<string> {
  const res = await authFetch(`/api/documents/${encodeURIComponent(fileStem)}/download`);
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const message = body?.detail || `HTTP ${res.status}`;
    if (res.status === 401) throw new AuthError(message, 401);
    throw new Error(message);
  }
  const filename = filenameFromDisposition(res.headers.get("content-disposition"), fileStem);
  saveBlob(await res.blob(), filename);
  return filename;
}

export async function deleteDocument(fileStem: string): Promise<void> {
  const res = await authFetch(`/api/documents/${encodeURIComponent(fileStem)}`, { method: "DELETE" });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const message = body?.detail || `HTTP ${res.status}`;
    if (res.status === 401) throw new AuthError(message, 401);
    throw new Error(message);
  }
}

export async function renameDocument(fileStem: string, name: string): Promise<DocItem> {
  const res = await authFetch(`/api/documents/${encodeURIComponent(fileStem)}`, {
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
