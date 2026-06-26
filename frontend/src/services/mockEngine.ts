import type { DocBlock, Message, RelLevel } from "../types";
import { SOURCES } from "../store/seed";

// ── Lớp mô phỏng (mock) — port 1:1 từ DCLogic trong `design/kiemdinh.html`.
//    Ranh giới sạch: sau này thay bằng gọi backend RAG thật mà không đụng UI. ──

/** Mốc thời gian (ms) — giữ y hệt mockup */
export const TIMING = {
  procStep: 850, // bước i hiện sau 850*i ms
  procDone: 850 * 4, // câu trả lời hiện sau 3400 ms
  docProgress: 430, // +16% mỗi 430 ms
  llmTest: 1600,
  toast: 2200,
} as const;

export const ZOOM = 0.88;

export interface ResponderResult {
  primaryCite: string;
  msg: Message;
}

/** Định tuyến theo từ khoá → 3 câu trả lời cố định (đúng mockup) */
export function responder(q: string): ResponderResult {
  const s = (q || "").toLowerCase();

  if (s.indexOf("sai số") >= 0 || s.indexOf("cấp") >= 0) {
    return {
      primaryCite: "3",
      msg: {
        role: "bot",
        followups: [
          "Thời gian quay tự do tối thiểu của pít tông áp kế là bao lâu?",
          "Công thức hiệu chỉnh nhiệt độ cho thời gian quay tự do?",
        ],
        blocks: [
          { summary: "Đã tham khảo 8 đoạn trong 24 tài liệu · trích dẫn 1 nguồn" },
          {
            p: [
              ["t", "Đối với áp kế pít tông "],
              ["b", "cấp chính xác 0,05"],
              ["t", ", sai số cho phép "],
              ["b", "không vượt quá ± 0,05 %"],
              ["t", " giá trị đo "],
              ["c", "3"],
              ["t", "."],
            ],
          },
          { p: [["t", "Giá trị sai số cho từng cấp chính xác được tra theo Bảng A.1 trong Phụ lục A."]] },
          { cites: ["3"] },
        ],
      },
    };
  }

  if (
    s.indexOf("công thức") >= 0 ||
    s.indexOf("nhiệt độ") >= 0 ||
    s.indexOf("hiệu chỉnh") >= 0 ||
    s.indexOf("giãn nở") >= 0 ||
    s.indexOf("hệ số") >= 0
  ) {
    return {
      primaryCite: "2",
      msg: {
        role: "bot",
        followups: [
          "Thời gian quay tự do tối thiểu của pít tông áp kế là bao lâu?",
          "Sai số cho phép của áp kế pít tông cấp 0,05 là bao nhiêu?",
        ],
        blocks: [
          { summary: "Đã tham khảo 10 đoạn trong 24 tài liệu · trích dẫn 2 nguồn" },
          {
            p: [
              ["t", "Thời gian quay tự do được hiệu chỉnh về điều kiện chuẩn (20 °C) theo công thức sau "],
              ["c", "2"],
              ["t", ":"],
            ],
          },
          { formula: "t₀ = t · [ 1 + β · (θ − 20) ]" },
          {
            p: [
              ["t", "Trong đó "],
              ["b", "t"],
              ["t", " là thời gian đo thực tế (giây), "],
              ["b", "θ"],
              ["t", " là nhiệt độ môi trường (°C), "],
              ["b", "β"],
              ["t", " là hệ số giãn nở của dầu kiểm định — với dầu tiêu chuẩn β = 7,0 × 10⁻⁴ /°C "],
              ["c", "1"],
              ["t", "."],
            ],
          },
          { cites: ["2", "1"] },
        ],
      },
    };
  }

  return {
    primaryCite: "1",
    msg: {
      role: "bot",
      followups: [
        "Công thức hiệu chỉnh nhiệt độ cho thời gian quay tự do?",
        "Sai số cho phép của áp kế pít tông cấp 0,05 là bao nhiêu?",
      ],
      blocks: [
        { summary: "Đã tham khảo 10 đoạn trong 24 tài liệu · trích dẫn 2 nguồn" },
        {
          p: [
            ["t", "Theo quy trình, thời gian quay tự do tối thiểu của pít tông áp kế chuẩn phải đạt "],
            ["b", "≥ 3 phút"],
            ["t", " trong điều kiện chuẩn (nhiệt độ 20 °C) "],
            ["c", "1"],
            ["t", "."],
          ],
        },
        {
          p: [
            ["t", "Nếu nhỏ hơn 3 phút, pít tông chưa đạt yêu cầu và cần được làm sạch, bôi trơn lại trước khi kiểm định tiếp. Khi nhiệt độ môi trường khác 20 °C, thời gian được hiệu chỉnh theo công thức "],
            ["c", "2"],
            ["t", "."],
          ],
        },
        { cites: ["1", "2"] },
      ],
    },
  };
}

/** Chọn câu hỏi mô phỏng khi mở lại một hội thoại cũ (theo tiêu đề) */
export function questionForConversation(title: string): string {
  const t = (title || "").toLowerCase();
  if (t.indexOf("sai số") >= 0 || t.indexOf("cấp") >= 0)
    return "Sai số cho phép của áp kế pít tông cấp 0,05 là bao nhiêu?";
  if (t.indexOf("giãn nở") >= 0 || t.indexOf("nhiệt") >= 0 || t.indexOf("hệ số") >= 0)
    return "Công thức hiệu chỉnh nhiệt độ cho thời gian quay tự do?";
  return "Thời gian quay tự do tối thiểu của pít tông áp kế là bao lâu?";
}

/** Các bước "tiến trình xử lý" hiển thị khi đang trả lời */
export const PROC_DEFS: { a: string; d: string }[] = [
  { a: "Đang tìm trong tài liệu…", d: "Đã tìm trong 24 tài liệu" },
  { a: "Đang lọc các đoạn liên quan…", d: "Tìm được 10 đoạn liên quan" },
  { a: "Đang đọc & đối chiếu nguồn…", d: "Đã đối chiếu 3 nguồn tin cậy" },
  { a: "Đang tổng hợp câu trả lời…", d: "Soạn xong câu trả lời" },
];

export function relLevel(rel: number): RelLevel {
  if (rel >= 0.7) return { t: "Cao", c: "#15803D", bg: "#DCFCE7" };
  if (rel >= 0.4) return { t: "Trung bình", c: "#B45309", bg: "#FEF3C7" };
  return { t: "Thấp", c: "#64748B", bg: "#EEF2F0" };
}

export function extColor(ext: string): string {
  return ext === "PDF" ? "#DC2626" : ext === "DOCX" ? "#2563EB" : ext === "XLSX" ? "#15803D" : "#64748B";
}

/** Nội dung tài liệu chung (khi xem tệp không nằm trong 3 nguồn mẫu) */
export function genericBlocks(): DocBlock[] {
  return [
    { h: "1   PHẠM VI ÁP DỤNG" },
    { p: "Tài liệu này quy định trình tự, thủ tục và yêu cầu kỹ thuật áp dụng cho công tác kiểm định, hiệu chuẩn phương tiện đo theo quy định hiện hành." },
    { h: "2   PHƯƠNG TIỆN & ĐIỀU KIỆN" },
    { p: "Các chuẩn đo lường và phương tiện phụ trợ phải còn trong thời hạn hiệu lực của giấy chứng nhận kiểm định/hiệu chuẩn và phù hợp với phạm vi đo của phương tiện cần kiểm định." },
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

export function codeOf(id: string): string {
  const s = SOURCES.find((x) => x.id === id);
  return s ? s.code : "";
}
