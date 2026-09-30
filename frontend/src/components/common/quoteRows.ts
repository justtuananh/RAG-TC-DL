// Trích dẫn của hồ sơ lưu các ô KHÔNG RỖNG của một dòng nối bằng " | " (nhiều dòng
// thì xuống dòng, "[Sheet: X]" mở đầu mỗi sheet) - khớp `records/xlsx_reader.py`.

const SEPARATOR = " | ";
const SHEET_RE = /^\[Sheet: (.*)\]$/;

export interface QuoteGroup {
  sheet: string | null;
  rows: string[][];
}

/** Nhóm dòng theo sheet; mỗi dòng tách thành các ô (bỏ ô rỗng như lúc lưu trích dẫn). */
export function parseQuoteRows(quote: string): QuoteGroup[] {
  const groups: QuoteGroup[] = [];
  let current: QuoteGroup = { sheet: null, rows: [] };
  for (const line of quote.split("\n")) {
    const sheet = SHEET_RE.exec(line.trim());
    if (sheet) {
      if (current.rows.length || current.sheet) groups.push(current);
      current = { sheet: sheet[1], rows: [] };
      continue;
    }
    const cells = line
      .split(SEPARATOR)
      .map((cell) => cell.trim())
      .filter(Boolean);
    if (cells.length) current.rows.push(cells);
  }
  if (current.rows.length || current.sheet) groups.push(current);
  return groups;
}

/**
 * Một dòng xem nhanh cho thẻ danh sách: các ô nối bằng " · " thay vì dấu "|" thô
 * (cả dòng bảng Markdown "| 1 | Kiểm tra | 5.1 |" lẫn trích dẫn hồ sơ "a | b");
 * dòng đánh dấu "[Sheet: X]" bị bỏ vì thẻ xem nhanh chỉ cần nội dung.
 */
export function quotePreview(quote: string): string {
  return quote
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => !SHEET_RE.test(line))
    .flatMap((line) => (line.includes("|") ? line.split("|") : [line]))
    .map((cell) => cell.trim())
    .filter((cell) => cell && !/^-{3,}$/.test(cell))
    .join(" · ");
}
