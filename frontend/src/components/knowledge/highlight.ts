// ── Tách đoạn nguyên văn để tô sáng AN TOÀN (Sprint 6) ──
// Trả ba phần dạng chuỗi thuần; component render bằng text node của React nên
// không có đường nào để nguồn chèn HTML/script. Vị trí do backend tính theo
// `char_start`/`char_end`; khi thiếu thì tìm nguyên văn trong mục.

export interface HighlightParts {
  before: string;
  match: string;
  after: string;
}

/** Cắt `text` tại [start, end); khoảng không hợp lệ trả về toàn bộ ở `before`. */
export function splitHighlight(
  text: string,
  start: number | null | undefined,
  end: number | null | undefined,
): HighlightParts {
  if (start == null || end == null) return { before: text, match: "", after: "" };
  const from = Math.max(0, Math.min(start, text.length));
  const to = Math.max(from, Math.min(end, text.length));
  if (from >= to) return { before: text, match: "", after: "" };
  return { before: text.slice(0, from), match: text.slice(from, to), after: text.slice(to) };
}

/** Ưu tiên khoảng ký tự; nếu không có thì tìm `quote` nguyên văn trong `text`. */
export function locateQuote(
  text: string,
  quote: string | null | undefined,
  start: number | null | undefined,
  end: number | null | undefined,
): HighlightParts {
  const parts = splitHighlight(text, start, end);
  if (parts.match || !quote) return parts;
  const index = text.indexOf(quote);
  if (index < 0) return parts;
  return splitHighlight(text, index, index + quote.length);
}
