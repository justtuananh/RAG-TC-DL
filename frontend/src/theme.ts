/**
 * Bảng màu / token thiết kế dùng chung cho toàn bộ giao diện.
 * Chủ đề: "Signal Blue" — nền slate lạnh trung tính + một accent xanh cobalt duy nhất,
 * gợi cảm giác chính xác/kỹ thuật phù hợp với công cụ tra cứu quy trình kiểm định.
 * Một theme sáng, nhất quán trên toàn app — không chuyển đổi sáng/tối theo section.
 */
export const COLOR = {
  // Nền & bề mặt trung tính (slate lạnh)
  bg: "#F3F5F8",
  surface: "#FFFFFF",
  surfaceAlt: "#F1F4F9",
  surfaceMuted: "#E8ECF2",
  border: "#DEE3EA",
  borderStrong: "#C6CDD8",

  // Chữ
  textPrimary: "#101828",
  textSecondary: "#475467",
  textMuted: "#7C8896",
  textOnDark: "#FFFFFF",

  // Sidebar (khối tối cố định) — xanh navy đậm cùng tông với accent, không dùng đen thuần
  sidebarBg: "#0F1B36",
  sidebarBgAlt: "#16264A",
  sidebarBorder: "rgba(255,255,255,.08)",
  sidebarText: "rgba(255,255,255,.62)",
  sidebarTextMuted: "rgba(255,255,255,.50)",
  sidebarHover: "rgba(255,255,255,.07)",

  // Accent duy nhất — xanh cobalt "Signal Blue"
  accent: "#2454E0",
  accentDark: "#173CAE",
  accentSoft: "#E9EFFF",
  accentSoftBorder: "#C9D8FF",
  // Biến thể sáng hơn của accent/danger — dùng trên nền tối (sidebar) để đủ tương phản
  accentOnDark: "#8FA8FF",
  dangerOnDark: "#FF8A8A",

  // Trạng thái
  success: "#12805C",
  successBg: "#E7F6EF",
  successBorder: "#BEE7D3",
  warning: "#B45309",
  warningBg: "#FFFBEB",
  warningBorder: "#FDE68A",
  danger: "#DC2626",
  dangerBg: "#FEF2F2",
  dangerBorder: "#FECACA",
  neutral: "#667085",
  neutralBg: "#F1F4F8",
  neutralBorder: "#DCE2E9",

  // Đánh dấu / highlight (đoạn trích được chọn trong tài liệu)
  highlight: "#FFF3C4",
  highlightBorder: "#F5CB5C",
  highlightStrong: "#F3B429",
} as const;

export const RADIUS = {
  sm: 8,
  md: 10,
  lg: 14,
  pill: 9999,
} as const;

export const SHADOW = {
  sm: "0 1px 2px rgba(16,24,40,.06)",
  md: "0 2px 10px rgba(16,24,40,.10)",
  lg: "0 10px 28px rgba(16,24,40,.16)",
  sidebar: "0 2px 8px rgba(0,0,0,.35)",
} as const;
