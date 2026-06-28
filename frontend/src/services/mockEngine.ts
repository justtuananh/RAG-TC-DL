import type { DocBlock } from "../types";
import { SOURCES } from "../store/seed";

// Hằng số UI + dữ liệu demo cho tab Tài liệu (trình xem).
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
  return ext === "PDF" ? "#DC2626" : ext === "DOCX" ? "#2563EB" : ext === "XLSX" ? "#15803D" : "#64748B";
}

/** Nội dung tài liệu chung (khi xem tệp không nằm trong 3 nguồn mẫu) */
export function genericBlocks(): DocBlock[] {
  return [
    { h: "1   PHẠM VI ÁP DỤNG" },
    { p: "Tài liệu này quy định trình tự, thủ tục và yêu cầu kỹ thuật áp dụng cho công tác kiểm định, hiệu chuẩn phương tiện đo theo quy định hiện hành." },
    { h: "2   PHƯƠNG TIỆN & ĐIỀU KIỆN" },
    {
      p: "Các chuẩn đo lường và phương tiện phụ trợ phải còn trong thời hạn hiệu lực của giấy chứng nhận kiểm định/hiệu chuẩn và phù hợp với phạm vi đo của phương tiện cần kiểm định.",
    },
    { p: "Điều kiện môi trường tại nơi kiểm định phải ổn định: nhiệt độ (20 ± 5) °C, độ ẩm không vượt quá 80 % RH." },
    { h: "3   TIẾN HÀNH KIỂM ĐỊNH" },
    { p: "3.1  Kiểm tra bên ngoài: phương tiện đo phải có nhãn mác, thang đo rõ ràng, không có hư hỏng ảnh hưởng đến đặc tính kỹ thuật đo lường." },
    { p: "3.2  Kiểm tra kỹ thuật: thực hiện theo trình tự nêu trong các bảng kiểm tra kèm theo và ghi nhận kết quả vào biên bản." },
    { p: "3.3  Kiểm tra đo lường: xác định sai số tại các điểm đo quy định và so sánh với sai số cho phép tương ứng." },
    { note: "Kết quả kiểm định được lập thành biên bản; phương tiện đạt yêu cầu được dán tem và cấp giấy chứng nhận kiểm định." },
  ];
}

export function docInfo(name: string): { blocks: DocBlock[]; code: string; pages: number | null } {
  const s = SOURCES.find((x) => (name || "").indexOf(x.code) >= 0);
  return s ? { blocks: s.blocks, code: s.code, pages: s.pages } : { blocks: genericBlocks(), code: "TÀI LIỆU", pages: null };
}
