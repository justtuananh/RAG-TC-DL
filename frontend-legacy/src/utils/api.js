/**
 * SSE streaming client for /api/chat/stream
 * Sends POST with {message, history}, yields parsed SSE events.
 */
export async function* streamChat(message, history) {
  const response = await fetch("/api/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, history }),
  });

  if (!response.ok) {
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
        yield JSON.parse(line.slice(6));
      } catch {
        // skip malformed line
      }
    }
  }
}

export async function fetchExamples() {
  const res = await fetch("/api/examples");
  if (!res.ok) return [];
  const data = await res.json();
  return data.examples ?? [];
}
