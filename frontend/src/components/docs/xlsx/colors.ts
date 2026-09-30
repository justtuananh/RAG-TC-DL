// ── Màu ô Excel → CSS: ARGB, màu theme (+ tint), bảng màu indexed cũ ──
// ExcelJS trả màu nguyên dạng OOXML ({argb} | {theme, tint} | {indexed}); tầng này
// dịch về "#RRGGBB" đúng như Excel vẽ, để bản xem giữ màu chữ/nền/viền của tệp gốc.

export interface ExcelColor {
  argb?: string;
  theme?: number;
  tint?: number;
  indexed?: number;
}

/** Bảng màu Office mặc định (2013+) theo THỨ TỰ CHỈ SỐ theme của ô: lt1, dk1, lt2, dk2, accent1..6, hlink, folHlink. */
export const DEFAULT_THEME: readonly string[] = [
  "#FFFFFF",
  "#000000",
  "#E7E6E6",
  "#44546A",
  "#4472C4",
  "#ED7D31",
  "#A5A5A5",
  "#FFC000",
  "#5B9BD5",
  "#70AD47",
  "#0563C1",
  "#954F72",
];

// Bảng màu indexed chuẩn của Excel (0..63); 64 = màu chữ hệ thống, 65 = nền hệ thống.
const INDEXED: readonly string[] = [
  "000000",
  "FFFFFF",
  "FF0000",
  "00FF00",
  "0000FF",
  "FFFF00",
  "FF00FF",
  "00FFFF",
  "000000",
  "FFFFFF",
  "FF0000",
  "00FF00",
  "0000FF",
  "FFFF00",
  "FF00FF",
  "00FFFF",
  "800000",
  "008000",
  "000080",
  "808000",
  "800080",
  "008080",
  "C0C0C0",
  "808080",
  "9999FF",
  "993366",
  "FFFFCC",
  "CCFFFF",
  "660066",
  "FF8080",
  "0066CC",
  "CCCCFF",
  "000080",
  "FF00FF",
  "FFFF00",
  "00FFFF",
  "800080",
  "800000",
  "008080",
  "0000FF",
  "00CCFF",
  "CCFFFF",
  "CCFFCC",
  "FFFF99",
  "99CCFF",
  "FF99CC",
  "CC99FF",
  "FFCC99",
  "3366FF",
  "33CCCC",
  "99CC00",
  "FFCC00",
  "FF9900",
  "FF6600",
  "666699",
  "969696",
  "003366",
  "339966",
  "003300",
  "333300",
  "993300",
  "993366",
  "333399",
  "333333",
].map((hex) => `#${hex}`);
const SYSTEM_FOREGROUND = 64;
const SYSTEM_BACKGROUND = 65;

/** Thứ tự phần tử trong `<a:clrScheme>`; ô tham chiếu theme theo chỉ số đã hoán dk/lt. */
const SCHEME_ORDER = ["dk1", "lt1", "dk2", "lt2", "accent1", "accent2", "accent3", "accent4", "accent5", "accent6", "hlink", "folHlink"];
const INDEX_ORDER = ["lt1", "dk1", "lt2", "dk2", "accent1", "accent2", "accent3", "accent4", "accent5", "accent6", "hlink", "folHlink"];

/** Đọc bảng màu từ `xl/theme/theme1.xml`; thiếu/hỏng thì dùng bảng Office mặc định. */
export function parseThemeColors(themeXml: string | undefined | null): string[] {
  if (!themeXml || typeof DOMParser === "undefined") return [...DEFAULT_THEME];
  const doc = new DOMParser().parseFromString(themeXml, "application/xml");
  const scheme = doc.getElementsByTagNameNS("*", "clrScheme")[0];
  if (!scheme) return [...DEFAULT_THEME];
  const byName: Record<string, string> = {};
  for (const name of SCHEME_ORDER) {
    const node = scheme.getElementsByTagNameNS("*", name)[0];
    const rgb = node?.getElementsByTagNameNS("*", "srgbClr")[0]?.getAttribute("val");
    const sys = node?.getElementsByTagNameNS("*", "sysClr")[0]?.getAttribute("lastClr");
    const hex = rgb || sys;
    if (hex && /^[0-9A-Fa-f]{6}$/.test(hex)) byName[name] = `#${hex.toUpperCase()}`;
  }
  return INDEX_ORDER.map((name, i) => byName[name] ?? DEFAULT_THEME[i]);
}

function hexToRgb(hex: string): [number, number, number] {
  const n = parseInt(hex.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function rgbToHex([r, g, b]: [number, number, number]): string {
  const channel = (v: number) =>
    Math.round(Math.max(0, Math.min(255, v)))
      .toString(16)
      .padStart(2, "0");
  return `#${channel(r)}${channel(g)}${channel(b)}`.toUpperCase();
}

function rgbToHsl([r, g, b]: [number, number, number]): [number, number, number] {
  const [rn, gn, bn] = [r / 255, g / 255, b / 255];
  const max = Math.max(rn, gn, bn);
  const min = Math.min(rn, gn, bn);
  const l = (max + min) / 2;
  if (max === min) return [0, 0, l];
  const d = max - min;
  const s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
  const h = max === rn ? (gn - bn) / d + (gn < bn ? 6 : 0) : max === gn ? (bn - rn) / d + 2 : (rn - gn) / d + 4;
  return [h / 6, s, l];
}

function hslToRgb([h, s, l]: [number, number, number]): [number, number, number] {
  if (s === 0) return [l * 255, l * 255, l * 255];
  const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
  const p = 2 * l - q;
  const channel = (t: number) => {
    const x = t < 0 ? t + 1 : t > 1 ? t - 1 : t;
    if (x < 1 / 6) return p + (q - p) * 6 * x;
    if (x < 1 / 2) return q;
    if (x < 2 / 3) return p + (q - p) * (2 / 3 - x) * 6;
    return p;
  };
  return [channel(h + 1 / 3) * 255, channel(h) * 255, channel(h - 1 / 3) * 255];
}

/** Tint của OOXML: âm làm tối (L × (1 + tint)), dương làm sáng (L × (1 − tint) + tint). */
export function applyTint(hex: string, tint: number | undefined): string {
  if (!tint) return hex;
  const [h, s, l] = rgbToHsl(hexToRgb(hex));
  const lum = tint < 0 ? l * (1 + tint) : l * (1 - tint) + tint;
  return rgbToHex(hslToRgb([h, s, lum]));
}

/** Màu CSS của một màu Excel; `undefined` khi không xác định (để CSS mặc định lo). */
export function resolveColor(color: ExcelColor | undefined, theme: readonly string[]): string | undefined {
  if (!color) return undefined;
  const argb = color.argb ?? "";
  if (/^[0-9A-Fa-f]{8}$/.test(argb)) return applyTint(`#${argb.slice(2).toUpperCase()}`, color.tint);
  if (/^[0-9A-Fa-f]{6}$/.test(argb)) return applyTint(`#${argb.toUpperCase()}`, color.tint);
  if (color.theme !== undefined) {
    const base = theme[color.theme];
    return base ? applyTint(base, color.tint) : undefined;
  }
  if (color.indexed !== undefined) {
    if (color.indexed === SYSTEM_FOREGROUND) return "#000000";
    if (color.indexed === SYSTEM_BACKGROUND) return "#FFFFFF";
    return INDEXED[color.indexed];
  }
  return undefined;
}
