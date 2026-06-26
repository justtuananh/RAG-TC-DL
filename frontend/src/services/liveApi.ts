import type { BackendSource } from "../types";

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
export async function* streamChat(
  message: string,
  history: HistoryTurn[],
  signal?: AbortSignal,
): AsyncGenerator<SseEvent> {
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
