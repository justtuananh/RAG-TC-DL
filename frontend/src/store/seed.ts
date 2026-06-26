import type { DocItem, FaqItem, Source } from "../types";

// ── Dữ liệu khởi tạo — transcribe 1:1 từ mockup `design/kiemdinh.html` ──

export const SAMPLES: string[] = [
  "Thời gian quay tự do tối thiểu của pít tông áp kế là bao lâu?",
  "Công thức hiệu chỉnh nhiệt độ cho thời gian quay tự do?",
  "Sai số cho phép của áp kế pít tông cấp 0,05 là bao nhiêu?",
  "Điều kiện môi trường khi kiểm định áp kế là gì?",
];

export const FAQS: FaqItem[] = [
  {
    q: "Trợ lý lấy thông tin từ đâu?",
    a: "Mọi câu trả lời đều dựa trên các tài liệu quy trình đã được tải lên hệ thống. Mỗi câu trả lời đều kèm số trích dẫn [1], [2]… — bấm vào để xem đúng đoạn trong tài liệu gốc.",
  },
  {
    q: "Làm sao biết câu trả lời có đáng tin không?",
    a: "Bấm vào số trích dẫn màu xanh trong câu trả lời. Hệ thống sẽ mở tài liệu gốc và tô sáng đúng đoạn được dùng để trả lời, kèm mức “độ tin cậy” của đoạn đó.",
  },
  {
    q: "Tôi tải tài liệu mới lên bằng cách nào?",
    a: "Vào tab Tài liệu, kéo thả tệp PDF hoặc Word vào khung tải lên, hoặc bấm để chọn tệp. Hệ thống xử lý trong giây lát; khi trạng thái chuyển “Đã sẵn sàng”, bạn có thể hỏi về tài liệu đó.",
  },
  {
    q: "Cuộc trò chuyện có được lưu lại không?",
    a: "Có. Mọi cuộc trò chuyện được lưu ở thanh Lịch sử bên trái. Bạn có thể tìm kiếm, đổi tên hoặc ghim các hội thoại quan trọng để mở lại nhanh. Bấm nút thu gọn để ẩn hoặc hiện thanh này.",
  },
  {
    q: "Tôi nên đặt câu hỏi thế nào cho hiệu quả?",
    a: "Hỏi ngắn gọn, đúng trọng tâm như đang hỏi một đồng nghiệp. Ví dụ: “Thời gian quay tự do tối thiểu là bao nhiêu?”. Nếu chưa rõ, cứ hỏi tiếp — trợ lý sẽ hỏi lại cho rõ.",
  },
];

export const SOURCES: Source[] = [
  {
    id: "1",
    code: "QTKĐ 1.061",
    file: "QTKĐ 1.061:2019 — Áp kế pít tông.pdf",
    path: "QTKĐ 1.061  ›  Mục 5  ›  5.3 Kiểm tra thời gian quay tự do",
    page: 3,
    pages: 12,
    rel: 0.92,
    blocks: [
      { h: "5   KIỂM TRA KỸ THUẬT" },
      { sub: "5.3   Kiểm tra thời gian quay tự do của pít tông" },
      {
        p: "Đặt pít tông ở vị trí cân bằng trong xi lanh. Truyền cho pít tông một chuyển động quay nhẹ quanh trục thẳng đứng rồi thả tự do. Dùng đồng hồ bấm giây đo khoảng thời gian từ lúc thả đến khi pít tông dừng hẳn.",
      },
      {
        p: "Thời gian quay tự do tối thiểu của pít tông áp kế chuẩn phải đạt ≥ 3 phút trong điều kiện chuẩn (nhiệt độ 20 °C). Nếu thời gian nhỏ hơn 3 phút, pít tông không đạt yêu cầu và phải được làm sạch, bôi trơn lại trước khi kiểm định tiếp.",
        highlight: true,
      },
      {
        p: "Khi nhiệt độ môi trường khác 20 °C, thời gian đo được hiệu chỉnh về điều kiện chuẩn theo công thức nêu tại QTKĐ 1.063, Mục 4.2.",
      },
      {
        note: "Ghi kết quả kiểm tra vào biên bản kiểm định theo Mẫu BB-01 kèm theo quy trình này.",
      },
    ],
  },
  {
    id: "2",
    code: "QTKĐ 1.063",
    file: "QTKĐ 1.063:2019 — Điều kiện môi trường.pdf",
    path: "QTKĐ 1.063  ›  Mục 4  ›  4.2 Hiệu chỉnh theo nhiệt độ",
    page: 2,
    pages: 8,
    rel: 0.78,
    blocks: [
      { h: "4   ĐIỀU KIỆN MÔI TRƯỜNG & HIỆU CHỈNH" },
      { sub: "4.2   Hiệu chỉnh thời gian theo nhiệt độ" },
      {
        p: "Phép đo thời gian quay tự do được thực hiện ở nhiệt độ môi trường ổn định. Khi nhiệt độ khác điều kiện chuẩn 20 °C, kết quả phải được quy đổi để bảo đảm tính so sánh giữa các lần kiểm định.",
      },
      {
        p: "Thời gian quay tự do hiệu chỉnh về điều kiện chuẩn được xác định theo công thức:",
        highlight: true,
        formula: "t₀ = t · [ 1 + β · (θ − 20) ]",
      },
      {
        p: "trong đó t là thời gian đo thực tế (giây), θ là nhiệt độ môi trường (°C) và β là hệ số giãn nở của dầu kiểm định. Với dầu kiểm định tiêu chuẩn, lấy β = 7,0 × 10⁻⁴ /°C (tra Bảng 2).",
      },
    ],
  },
  {
    id: "3",
    code: "QTKĐ 1.071",
    file: "QTKĐ 1.071:2020 — Sai số cho phép.pdf",
    path: "QTKĐ 1.071  ›  Phụ lục A  ›  Bảng A.1 Sai số cho phép",
    page: 9,
    pages: 15,
    rel: 0.46,
    blocks: [
      { h: "PHỤ LỤC A   SAI SỐ CHO PHÉP" },
      { sub: "Bảng A.1   Sai số cho phép theo cấp chính xác" },
      {
        table: {
          head: ["Cấp chính xác", "Sai số cho phép", "Phạm vi áp dụng"],
          rows: [
            ["0,02", "± 0,02 %", "Áp kế chuẩn đầu"],
            ["0,05", "± 0,05 %", "Áp kế chuẩn công tác"],
            ["0,1", "± 0,1 %", "Kiểm định hiện trường"],
            ["0,2", "± 0,2 %", "Áp kế thông dụng"],
          ],
          highlightRow: 1,
        },
      },
      {
        p: "Đối với cấp chính xác 0,05, sai số cho phép không vượt quá ± 0,05 % giá trị đo. Giá trị này áp dụng cho áp kế pít tông chuẩn công tác dùng trong kiểm định định kỳ.",
      },
    ],
  },
];


export const DOCUMENTS: DocItem[] = [
  { id: "d1", name: "QTKĐ 1.061:2019 — Áp kế pít tông.pdf", ext: "PDF", size: "2,4 MB", pages: 12, date: "20/06/2026", status: "ready" },
  { id: "d2", name: "QTKĐ 1.063:2019 — Điều kiện môi trường.pdf", ext: "PDF", size: "1,1 MB", pages: 8, date: "20/06/2026", status: "ready" },
  { id: "d3", name: "QTKĐ 1.071:2020 — Sai số cho phép.pdf", ext: "PDF", size: "0,9 MB", pages: 15, date: "18/06/2026", status: "ready" },
  { id: "d4", name: "Thông tư 23/2013 — Đo lường.docx", ext: "DOCX", size: "3,7 MB", pages: 42, date: "15/06/2026", status: "ready" },
  { id: "d5", name: "Hướng dẫn vận hành áp kế chuẩn.pdf", ext: "PDF", size: "5,2 MB", pages: "—", date: "12/06/2026", status: "pending", progress: 0 },
  { id: "d6", name: "QTKĐ 1.052:2018 — Cân không tự động.pdf", ext: "PDF", size: "1,9 MB", pages: 18, date: "11/06/2026", status: "ready" },
  { id: "d7", name: "QTKĐ 2.014:2021 — Công tơ điện xoay chiều.pdf", ext: "PDF", size: "2,1 MB", pages: 22, date: "09/06/2026", status: "ready" },
  { id: "d8", name: "QTKĐ 1.025:2017 — Cột đo nhiên liệu.pdf", ext: "PDF", size: "1,4 MB", pages: 16, date: "06/06/2026", status: "ready" },
  { id: "d9", name: "ĐLVN 18:2009 — Phương tiện đo nhóm 2.pdf", ext: "PDF", size: "3,2 MB", pages: 35, date: "02/06/2026", status: "ready" },
  { id: "d10", name: "Biên bản kiểm định mẫu BB-01.docx", ext: "DOCX", size: "0,4 MB", pages: 3, date: "30/05/2026", status: "ready" },
  { id: "d11", name: "Quy trình hiệu chuẩn nhiệt kế thủy ngân.pdf", ext: "PDF", size: "1,2 MB", pages: 14, date: "28/05/2026", status: "ready" },
  { id: "d12", name: "Sổ tay chất lượng phòng kiểm định.pdf", ext: "PDF", size: "4,6 MB", pages: 52, date: "24/05/2026", status: "ready" },
  { id: "d13", name: "QTKĐ 1.080:2022 — Lưu lượng kế.pdf", ext: "PDF", size: "2,7 MB", pages: 26, date: "20/05/2026", status: "ready" },
  { id: "d14", name: "Danh mục thiết bị chuẩn 2026.xlsx", ext: "XLSX", size: "0,8 MB", pages: 6, date: "15/05/2026", status: "ready" },
];
