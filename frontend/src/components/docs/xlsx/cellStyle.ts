// ── Kiểu ô Excel (font, nền, viền, căn lề) và giá trị ô → CSS + chuỗi hiển thị ──
// Thuần hàm trên kiểu của ExcelJS; không đụng DOM. Giá trị ô KHÔNG bị tính lại:
// công thức dùng kết quả đã lưu trong tệp, số chỉ đổi cách viết theo numFmt.

import type { CSSProperties } from "react";
import type { Alignment, Border, Borders, CellValue, Fill, Font, RichText } from "exceljs";
import { resolveColor, type ExcelColor } from "./colors";
import { formatDate, formatNumber, formatText } from "./numfmt";

export type HorizontalAlign = "left" | "center" | "right" | "justify";

export interface CellRun {
  text: string;
  style?: CSSProperties;
}

export interface CellDisplay {
  text: string;
  runs?: CellRun[];
  /** căn lề mặc định của Excel theo KIỂU giá trị (số phải, chữ trái, logic/lỗi giữa) */
  naturalAlign: HorizontalAlign;
}

// Ký tự vùng riêng (U+F0xx) do Word/Excel chèn từ font Wingdings: trình duyệt không
// có font này nên đổi sang ký tự Unicode tương đương để ô đánh dấu hiện đúng hình.
const SYMBOL_GLYPHS: Record<string, string> = {
  "": "☑",
  "": "☒",
  "": "☒",
  "": "✓",
  "": "✗",
  "": "☐",
  "": "☐",
  "": "☐",
  "": "❑",
  "": "•",
  "": "●",
};

export function mapSymbolGlyphs(text: string): string {
  return /[-]/.test(text) ? text.replace(/[-]/g, (ch) => SYMBOL_GLYPHS[ch] ?? ch) : text;
}

const PT_TO_PX = 96 / 72;
export const DEFAULT_FONT_PT = 11;
const DEFAULT_FONT_NAME = "Calibri";

/** Họ font CSS: tên font gốc trước, rồi font thay thế cùng nhóm có trên máy. */
export function fontFamily(name: string | undefined): string {
  const font = name || DEFAULT_FONT_NAME;
  const serif = /times|cambria|georgia|garamond|serif|vni-times|\.vntime/i.test(font);
  const fallback = serif ? "'Times New Roman', 'Liberation Serif', Tinos, Georgia, serif" : "Calibri, Carlito, 'Liberation Sans', Arial, sans-serif";
  return `'${font.replace(/'/g, "")}', ${fallback}`;
}

/** Cỡ font px (Excel dùng pt). */
export function fontPx(font: Partial<Font> | undefined): number {
  return (font?.size || DEFAULT_FONT_PT) * PT_TO_PX;
}

export function fontStyle(font: Partial<Font> | undefined, theme: readonly string[]): CSSProperties {
  if (!font) return {};
  const style: CSSProperties = {};
  if (font.name) style.fontFamily = fontFamily(font.name);
  if (font.size) style.fontSize = `${font.size}pt`;
  if (font.bold) style.fontWeight = 700;
  if (font.italic) style.fontStyle = "italic";
  const decorations: string[] = [];
  if (font.underline && font.underline !== "none") decorations.push("underline");
  if (font.strike) decorations.push("line-through");
  if (decorations.length) style.textDecoration = decorations.join(" ");
  if (font.underline === "double" || font.underline === "doubleAccounting") style.textDecorationStyle = "double";
  if (font.vertAlign === "superscript") style.verticalAlign = "super";
  if (font.vertAlign === "subscript") style.verticalAlign = "sub";
  const color = resolveColor(font.color as ExcelColor | undefined, theme);
  if (color) style.color = color;
  return style;
}

/** Nền ô: mẫu tô `solid` và các mẫu chấm (xấp xỉ bằng màu trước), gradient lấy màu đầu. */
export function fillColor(fill: Fill | undefined, theme: readonly string[]): string | undefined {
  if (!fill) return undefined;
  if (fill.type === "pattern") {
    if (fill.pattern === "none") return undefined;
    return resolveColor(fill.fgColor as ExcelColor | undefined, theme) ?? resolveColor(fill.bgColor as ExcelColor | undefined, theme);
  }
  return resolveColor(fill.stops?.[0]?.color as ExcelColor | undefined, theme);
}

const BORDER_CSS: Record<string, [number, string]> = {
  hair: [1, "dotted"],
  thin: [1, "solid"],
  dotted: [1, "dotted"],
  dashed: [1, "dashed"],
  dashDot: [1, "dashed"],
  dashDotDot: [1, "dotted"],
  medium: [2, "solid"],
  mediumDashed: [2, "dashed"],
  mediumDashDot: [2, "dashed"],
  mediumDashDotDot: [2, "dotted"],
  slantDashDot: [2, "dashed"],
  thick: [3, "solid"],
  double: [3, "double"],
};

/** Một cạnh viền Excel → giá trị CSS `border-*`; `undefined` khi cạnh không có viền. */
export function borderCss(border: Partial<Border> | undefined, theme: readonly string[]): string | undefined {
  if (!border?.style) return undefined;
  const [width, style] = BORDER_CSS[border.style] ?? [1, "solid"];
  const color = resolveColor(border.color as ExcelColor | undefined, theme) ?? "#000000";
  return `${width}px ${style} ${color}`;
}

export type BorderSide = "top" | "left" | "bottom" | "right";

export function sideBorder(borders: Partial<Borders> | undefined, side: BorderSide): Partial<Border> | undefined {
  return (borders as Partial<Record<BorderSide, Partial<Border>>> | undefined)?.[side];
}

export interface AlignmentResult {
  style: CSSProperties;
  align: HorizontalAlign;
  wrap: boolean;
}

function horizontalOf(alignment: Partial<Alignment> | undefined, natural: HorizontalAlign): HorizontalAlign {
  switch (alignment?.horizontal) {
    case "center":
    case "centerContinuous":
    case "distributed":
      return "center";
    case "right":
      return "right";
    case "left":
    case "fill":
      return "left";
    case "justify":
      return "justify";
    default:
      return natural;
  }
}

/** Căn lề ô: ngang/dọc, xuống dòng, thụt lề, xoay chữ đứng. */
export function alignmentStyle(alignment: Partial<Alignment> | undefined, natural: HorizontalAlign): AlignmentResult {
  const align = horizontalOf(alignment, natural);
  const vertical = alignment?.vertical;
  const style: CSSProperties = {
    textAlign: align,
    verticalAlign: vertical === "top" ? "top" : vertical && vertical !== "bottom" ? "middle" : "bottom",
  };
  const indent = alignment?.indent ?? 0;
  if (indent > 0) style[align === "right" ? "paddingRight" : "paddingLeft"] = indent * 9 + 3;
  const rotation = alignment?.textRotation;
  if (rotation === "vertical" || rotation === 255) style.writingMode = "vertical-rl";
  const wrap = Boolean(alignment?.wrapText) || align === "justify" || vertical === "justify" || vertical === "distributed";
  return { style, align, wrap };
}

type RichValue = { richText: RichText[] };
type FormulaValue = { result?: CellValue };
type ErrorValue = { error: string };
type LinkValue = { text: string | RichValue };

const EMPTY: CellDisplay = { text: "", naturalAlign: "left" };

/** Chuỗi hiển thị của giá trị ô (kết quả công thức đã lưu, số theo numFmt, rich text giữ kiểu từng đoạn). */
export function cellDisplay(value: CellValue, numFmt: string | undefined, theme: readonly string[]): CellDisplay {
  if (value === null || value === undefined) return EMPTY;
  if (typeof value === "number") return { text: formatNumber(value, numFmt), naturalAlign: "right" };
  if (typeof value === "string") return { text: mapSymbolGlyphs(formatText(value, numFmt)), naturalAlign: "left" };
  if (typeof value === "boolean") return { text: value ? "TRUE" : "FALSE", naturalAlign: "center" };
  if (value instanceof Date) return { text: formatDate(value, numFmt || "dd/mm/yyyy"), naturalAlign: "right" };
  if ("richText" in value) {
    const runs = (value as RichValue).richText.map((run) => ({ text: mapSymbolGlyphs(run.text ?? ""), style: fontStyle(run.font, theme) }));
    return { text: runs.map((run) => run.text).join(""), runs, naturalAlign: "left" };
  }
  if ("error" in value) return { text: (value as ErrorValue).error, naturalAlign: "center" };
  if ("formula" in value || "sharedFormula" in value) {
    const result = (value as FormulaValue).result;
    return result === undefined ? EMPTY : cellDisplay(result, numFmt, theme);
  }
  if ("hyperlink" in value) {
    const text = (value as LinkValue).text;
    return typeof text === "string" ? { text: mapSymbolGlyphs(text), naturalAlign: "left" } : cellDisplay(text as CellValue, numFmt, theme);
  }
  return EMPTY;
}
