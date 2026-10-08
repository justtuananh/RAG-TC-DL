/**
 * Bảng màu / token thiết kế dùng chung cho toàn bộ giao diện.
 * Chủ đề: "Xanh quân đội" — xanh ô liu đậm làm màu chủ đạo trên nền trắng ngà hơi ấm
 * (không lạnh như slate), điểm nhấn vàng sao và đỏ cờ dùng rất tiết kiệm.
 * Cảm giác hướng tới: nghiêm, chắc, kỷ luật, dễ đọc lâu; không loè loẹt, không họa tiết rằn ri.
 * Một theme sáng duy nhất trên toàn app — không chuyển đổi sáng/tối theo section.
 */
export const COLOR = {
  // Nền & bề mặt trung tính hơi ấm (ô liu nhạt)
  bg: "#F4F5EF",
  surface: "#FFFFFF",
  surfaceAlt: "#F0F2E9",
  surfaceMuted: "#E6E9DC",
  border: "#DADFCC",
  borderStrong: "#BEC6AC",

  // Chữ
  textPrimary: "#1A1F14",
  textSecondary: "#4C5442",
  textMuted: "#767E6C",
  textOnDark: "#FFFFFF",

  // Sidebar (khối tối cố định) — ô liu rất đậm cùng tông với accent, không dùng đen thuần
  sidebarBg: "#1E2814",
  sidebarBgAlt: "#2A3720",
  sidebarBorder: "rgba(255,255,255,.08)",
  sidebarText: "rgba(255,255,255,.66)",
  sidebarTextMuted: "rgba(255,255,255,.52)",
  sidebarHover: "rgba(255,255,255,.07)",

  // Accent chính — xanh quân đội (ô liu)
  accent: "#4B5E27",
  accentDark: "#34431A",
  accentSoft: "#EDF1E1",
  accentSoftBorder: "#CFD9B5",
  // Biến thể sáng hơn của accent/danger — dùng trên nền tối (sidebar) để đủ tương phản
  accentOnDark: "#C3D69A",
  dangerOnDark: "#FF8A8A",

  // Trạng thái
  success: "#1C7A47",
  successBg: "#E6F4EC",
  successBorder: "#B9E0C9",
  warning: "#A6510A",
  warningBg: "#FFF8E6",
  warningBorder: "#F5D58A",
  danger: "#C8102E",
  dangerBg: "#FDF0F1",
  dangerBorder: "#F5C2C9",
  neutral: "#6B7262",
  neutralBg: "#F1F2EC",
  neutralBorder: "#DDE0D3",

  // Đánh dấu / highlight (đoạn trích được chọn trong tài liệu)
  highlight: "#FFF3C4",
  highlightBorder: "#E5C04A",
  highlightStrong: "#E5B700",

  // Trang trí nghi lễ: vàng sao (mục đang chọn ở sidebar, icon logo) và đỏ cờ (vạch dưới logo)
  star: "#E5B700",
  flagRed: "#DA251D",

  // Lớp phủ & bóng dùng chung (thay các mã viết cứng rải rác trong .tsx)
  overlay: "rgba(26,31,20,.55)",
  overlayMedium: "rgba(26,31,20,.45)",
  overlaySoft: "rgba(26,31,20,.35)",
  shadowStrong: "rgba(26,31,20,.25)",
  shadowPage: "rgba(26,31,20,.16)",
  shadowPageSoft: "rgba(26,31,20,.18)",
  shadowDark: "rgba(0,0,0,.5)",
  shadowToast: "rgba(0,0,0,.4)",
  brandShadow: "rgba(75,94,39,.35)",
  brandShadowSoft: "rgba(75,94,39,.22)",
  brandShadowHover: "rgba(75,94,39,.24)",
  brandShadowLg: "rgba(75,94,39,.5)",
  successShadow: "rgba(28,122,71,.3)",
  whiteSoft: "rgba(255,255,255,.14)",
  whiteFaint: "rgba(255,255,255,.25)",
  dangerSoft: "rgba(200,16,46,.18)",
  dropOverlay: "rgba(237,241,225,.92)",
} as const;

export const RADIUS = {
  sm: 8,
  md: 10,
  lg: 14,
  pill: 9999,
} as const;

export const SHADOW = {
  sm: "0 1px 2px rgba(26,31,20,.06)",
  md: "0 2px 10px rgba(26,31,20,.10)",
  lg: "0 10px 28px rgba(26,31,20,.16)",
  sidebar: "0 2px 8px rgba(0,0,0,.35)",
} as const;
