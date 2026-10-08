/**
 * Bảng màu / token thiết kế dùng chung cho toàn bộ giao diện.
 * Chủ đề: "Xanh quân đội hiện đại" - xanh rừng đậm (forest) làm accent duy nhất trên nền
 * trung tính sạch hơi lạnh; sidebar xanh rêu gần đen, mục đang chọn sáng màu mint.
 * Vàng sao chỉ dùng cho icon logo. Một theme sáng duy nhất, không đổi sáng/tối theo section.
 */
export const COLOR = {
  // Nền & bề mặt trung tính hơi lạnh
  bg: "#F5F7F6",
  surface: "#FFFFFF",
  surfaceAlt: "#F3F6F4",
  surfaceMuted: "#E9EEEB",
  border: "#E1E7E3",
  borderStrong: "#C7D1CB",

  // Chữ
  textPrimary: "#0F1A14",
  textSecondary: "#46524B",
  textMuted: "#6B7770",
  textOnDark: "#FFFFFF",

  // Sidebar (khối tối cố định) - xanh rêu gần đen cùng tông với accent, không dùng đen thuần
  sidebarBg: "#0E1A13",
  sidebarBgAlt: "#16261C",
  sidebarBorder: "rgba(255,255,255,.08)",
  sidebarText: "rgba(255,255,255,.66)",
  sidebarTextMuted: "rgba(255,255,255,.52)",
  sidebarHover: "rgba(255,255,255,.07)",
  // Mục đang chọn: nền mint trong suốt thay cho khối accent đặc
  sidebarActive: "rgba(139,211,166,.13)",

  // Accent chính - xanh quân đội (forest)
  accent: "#2D6A43",
  accentDark: "#1E4D30",
  accentSoft: "#E8F3EC",
  accentSoftBorder: "#BFDCC9",
  // Biến thể sáng hơn của accent/danger - dùng trên nền tối (sidebar) để đủ tương phản
  accentOnDark: "#8BD3A6",
  dangerOnDark: "#FF8A8A",

  // Trạng thái
  success: "#167A4E",
  successBg: "#E6F4EC",
  successBorder: "#B9E0C9",
  warning: "#B45309",
  warningBg: "#FFF7E8",
  warningBorder: "#F5D58A",
  danger: "#C8102E",
  dangerBg: "#FDF0F1",
  dangerBorder: "#F5C2C9",
  neutral: "#64706A",
  neutralBg: "#F1F4F2",
  neutralBorder: "#DDE4E0",

  // Đánh dấu / highlight (đoạn trích được chọn trong tài liệu)
  highlight: "#FFF3C4",
  highlightBorder: "#E9C75A",
  highlightStrong: "#F2C230",

  // Vàng sao: icon logo
  star: "#F2C230",

  // Lớp phủ & bóng dùng chung (thay các mã viết cứng rải rác trong .tsx)
  overlay: "rgba(15,26,20,.55)",
  overlayMedium: "rgba(15,26,20,.45)",
  overlaySoft: "rgba(15,26,20,.35)",
  shadowStrong: "rgba(15,26,20,.25)",
  shadowPage: "rgba(15,26,20,.16)",
  shadowPageSoft: "rgba(15,26,20,.18)",
  shadowDark: "rgba(0,0,0,.5)",
  shadowToast: "rgba(0,0,0,.4)",
  brandShadow: "rgba(45,106,67,.35)",
  brandShadowSoft: "rgba(45,106,67,.22)",
  brandShadowHover: "rgba(45,106,67,.24)",
  brandShadowLg: "rgba(45,106,67,.5)",
  successShadow: "rgba(22,122,78,.3)",
  whiteSoft: "rgba(255,255,255,.14)",
  whiteFaint: "rgba(255,255,255,.25)",
  dangerSoft: "rgba(200,16,46,.18)",
  dropOverlay: "rgba(232,243,236,.92)",
} as const;

export const RADIUS = {
  sm: 8,
  md: 10,
  lg: 14,
  pill: 9999,
} as const;

export const SHADOW = {
  sm: "0 1px 2px rgba(15,26,20,.06)",
  md: "0 2px 10px rgba(15,26,20,.10)",
  lg: "0 10px 28px rgba(15,26,20,.16)",
  sidebar: "0 2px 8px rgba(0,0,0,.35)",
} as const;
