// Hằng số UI dùng chung (mockup 1:1).
// Phần "mock chat" đã được thay bằng backend RAG thật (services/liveApi.ts).

/** Mốc thời gian (ms) — mô phỏng xử lý tài liệu + toast */
export const TIMING = {
  docProgress: 430, // +16% mỗi 430 ms
  llmTest: 1600,
  toast: 2200,
} as const;

/** Toàn app thu nhỏ 0.88 (khớp mockup) */
export const ZOOM = 0.88;

export function extColor(ext: string): string {
  // .doc/.xls cũ cùng màu với bản mới của Word/Excel: người dùng nhận ra loại tệp theo ứng dụng.
  if (ext === "PDF") return "#DC2626";
  if (ext === "DOCX" || ext === "DOC") return "#2563EB";
  if (ext === "XLSX" || ext === "XLS") return "#15803D";
  return "#64748B";
}
