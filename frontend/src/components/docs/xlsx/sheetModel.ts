// ── Worksheet (ExcelJS) → mô hình lưới ô để render như Excel ──
// Giữ đúng: gộp ô, dòng/cột ẩn, độ rộng cột/chiều cao dòng, font/nền/viền/căn lề,
// kẻ lưới, chữ tràn sang ô trống bên cạnh. Số KHÔNG BAO GIỜ bị cắt cụt âm thầm:
// như Excel, số General quá rộng được làm tròn bớt chữ số hiển thị, số định dạng
// cố định không vừa ô thì hiện "###" (giá trị đầy đủ nằm ở tooltip của ô).

import type { CSSProperties } from "react";
import type { Border, Cell, CellValue, Row, Workbook, Worksheet } from "exceljs";
import { parseThemeColors } from "./colors";
import {
  alignmentStyle,
  borderCss,
  DEFAULT_FONT_PT,
  cellDisplay,
  fillColor,
  fontFamily,
  fontPx,
  fontStyle,
  sideBorder,
  type BorderSide,
  type CellDisplay,
  type HorizontalAlign,
} from "./cellStyle";
import { formatGeneral } from "./numfmt";

export interface CellModel {
  /** chỉ số Excel 0-based */
  row: number;
  col: number;
  rowSpan: number;
  colSpan: number;
  display: CellDisplay;
  /** giá trị đầy đủ khi chuỗi hiển thị bị rút gọn/thay bằng ### */
  title?: string;
  style: CSSProperties;
  /** cạnh trên (viền của ô hoặc cạnh dưới ô phía trên) - cho dòng đầu của một trích đoạn */
  topBorder: string;
  contentStyle: CSSProperties;
}

export interface RowModel {
  index: number;
  height: number;
  cells: CellModel[];
}

export interface ColModel {
  index: number;
  width: number;
}

export interface SheetModel {
  name: string;
  hidden: boolean;
  showGridLines: boolean;
  cols: ColModel[];
  rows: RowModel[];
  /** sheet lớn hơn giới hạn hiển thị: chỉ vẽ phần đầu */
  truncated: boolean;
}

export interface WorkbookModel {
  sheets: SheetModel[];
}

export type MeasureText = (text: string, font: string) => number;

export interface BuildOptions {
  measure?: MeasureText;
  maxRows?: number;
  maxCols?: number;
}

const MAX_ROWS = 2000;
const MAX_COLS = 120;
const DEFAULT_ROW_PT = 15;
const DEFAULT_COL_WIDTH = 9.140625; // 8,43 ký tự hiển thị = 64 px
const MAX_DIGIT_WIDTH = 7; // px, Calibri 11 - đơn vị độ rộng cột của Excel
export const CELL_PADDING = 3; // px mỗi bên
export const GRIDLINE = "1px solid #DADCE0";

/** Độ rộng cột Excel (đơn vị ký tự) → px, công thức của ECMA-376 §18.3.1.13. */
export function columnWidthPx(width: number): number {
  return Math.trunc(((256 * width + Math.trunc(128 / MAX_DIGIT_WIDTH)) / 256) * MAX_DIGIT_WIDTH);
}

/** Chỉ số cột 0-based → tên cột Excel (0 → A, 26 → AA). */
export function columnLetter(index: number): string {
  let n = index + 1;
  let out = "";
  while (n > 0) {
    const rem = (n - 1) % 26;
    out = String.fromCharCode(65 + rem) + out;
    n = Math.floor((n - 1) / 26);
  }
  return out;
}

let canvasContext: CanvasRenderingContext2D | null | undefined;

/** Đo chữ bằng canvas (trình duyệt); không có canvas thì ước lượng theo cỡ chữ. */
export const measureWithCanvas: MeasureText = (text, font) => {
  if (canvasContext === undefined) {
    try {
      canvasContext = typeof document !== "undefined" ? document.createElement("canvas").getContext("2d") : null;
    } catch {
      canvasContext = null;
    }
  }
  if (canvasContext) {
    canvasContext.font = font;
    const width = canvasContext.measureText(text).width;
    if (width > 0 || !text) return width;
  }
  const px = Number(/(\d+(?:\.\d+)?)px/.exec(font)?.[1] ?? 14.67);
  return text.length * px * 0.52;
};

// ── vùng gộp ô ──

interface Merge {
  r0: number;
  c0: number;
  r1: number;
  c1: number;
}

function decodeAddress(address: string): [number, number] | null {
  const match = /^\$?([A-Z]+)\$?(\d+)$/i.exec(address.trim());
  if (!match) return null;
  let col = 0;
  for (const ch of match[1].toUpperCase()) col = col * 26 + (ch.charCodeAt(0) - 64);
  return [Number(match[2]) - 1, col - 1];
}

function parseMerges(ranges: readonly string[] | undefined): Merge[] {
  const merges: Merge[] = [];
  for (const range of ranges ?? []) {
    const [start, end = start] = range.split(":");
    const a = decodeAddress(start);
    const b = decodeAddress(end);
    if (a && b) merges.push({ r0: Math.min(a[0], b[0]), c0: Math.min(a[1], b[1]), r1: Math.max(a[0], b[0]), c1: Math.max(a[1], b[1]) });
  }
  return merges;
}

// ── bố cục: phạm vi có dữ liệu, cột/dòng nhìn thấy ──

/** Ô có nghĩa (giá trị, viền hoặc nền) - để cắt bỏ vùng trống cuối sheet. */
function hasContent(cell: Cell): boolean {
  const value = cell.value as CellValue;
  if (value !== null && value !== undefined && value !== "") return true;
  const border = cell.style?.border;
  if (border && (border.top?.style || border.left?.style || border.bottom?.style || border.right?.style)) return true;
  const fill = cell.style?.fill;
  return Boolean(fill && !(fill.type === "pattern" && fill.pattern === "none"));
}

function sheetExtent(ws: Worksheet, merges: Merge[]): { rows: number; cols: number } {
  let rows = 0;
  let cols = 0;
  ws.eachRow({ includeEmpty: true }, (row: Row, rowNumber: number) => {
    row.eachCell({ includeEmpty: true }, (cell: Cell, colNumber: number) => {
      if (!hasContent(cell)) return;
      rows = Math.max(rows, rowNumber);
      cols = Math.max(cols, colNumber);
    });
  });
  for (const merge of merges) {
    rows = Math.max(rows, merge.r1 + 1);
    cols = Math.max(cols, merge.c1 + 1);
  }
  return { rows, cols };
}

interface Layout {
  rowCount: number;
  colCount: number;
  colWidth: number[]; // 0 = cột ẩn
  rowVisible: boolean[];
  rowHeight: number[];
  truncated: boolean;
}

function buildLayout(ws: Worksheet, merges: Merge[], options: BuildOptions): Layout {
  const extent = sheetExtent(ws, merges);
  const maxRows = options.maxRows ?? MAX_ROWS;
  const maxCols = options.maxCols ?? MAX_COLS;
  const rowCount = Math.min(extent.rows, maxRows);
  const colCount = Math.min(extent.cols, maxCols);
  const defaultColWidth = ws.properties?.defaultColWidth ?? DEFAULT_COL_WIDTH;
  const defaultRowPt = ws.properties?.defaultRowHeight ?? DEFAULT_ROW_PT;
  const colWidth = Array.from({ length: colCount }, (_, c) => {
    const column = ws.getColumn(c + 1);
    return column.hidden ? 0 : columnWidthPx(column.width ?? defaultColWidth);
  });
  const rows = Array.from({ length: rowCount }, (_, r) => ws.findRow(r + 1));
  return {
    rowCount,
    colCount,
    colWidth,
    rowVisible: rows.map((row) => !row?.hidden),
    rowHeight: rows.map((row) => Math.round(((row?.height ?? defaultRowPt) * 96) / 72)),
    truncated: extent.rows > maxRows || extent.cols > maxCols,
  };
}

function stepVisible(visible: (i: number) => boolean, count: number, from: number, direction: 1 | -1): number {
  for (let i = from + direction; i >= 0 && i < count; i += direction) if (visible(i)) return i;
  return -1;
}

// ── ô nháp: giá trị hiển thị + kích thước ──

interface Draft {
  row: number;
  col: number;
  rowSpan: number;
  colSpan: number;
  lastRow: number;
  lastCol: number;
  cell: Cell | undefined;
  display: CellDisplay;
  title?: string;
  isNumber: boolean;
  align: HorizontalAlign;
  alignStyle: CSSProperties;
  wrap: boolean;
  font: string;
  width: number;
  spillLeft: number;
  spillRight: number;
  /** < 1 khi cỡ chữ được thu cho vừa ô (shrinkToFit, hoặc sai khác metric font nhỏ) */
  fontScale: number;
}

function cssFont(cell: Cell | undefined): string {
  const font = cell?.style?.font;
  return `${font?.italic ? "italic " : ""}${font?.bold ? "700 " : ""}${fontPx(font)}px ${fontFamily(font?.name)}`;
}

function numericValue(value: CellValue): number | null {
  if (typeof value === "number") return value;
  if (value && typeof value === "object" && !(value instanceof Date) && "result" in value && typeof value.result === "number") return value.result;
  return null;
}

/** Như Excel: số General quá rộng → bớt chữ số có nghĩa; vẫn không vừa (hoặc định dạng cố định) → "###". */
function fitNumber(
  value: number,
  numFmt: string | undefined,
  text: string,
  available: number,
  font: string,
  measure: MeasureText,
): { text: string; title?: string } {
  if (measure(text, font) <= available) return { text };
  const isGeneral = !numFmt || /^general$/i.test(numFmt.trim());
  if (isGeneral && Math.abs(value) < 1e11 && Math.abs(value) >= 1e-4) {
    for (let digits = 9; digits >= 1; digits--) {
      const candidate = formatGeneral(Number(value.toPrecision(digits)));
      if (measure(candidate, font) <= available) return { text: candidate, title: text };
    }
  }
  const hashWidth = Math.max(1, measure("#", font));
  return { text: "#".repeat(Math.max(1, Math.floor(available / hashWidth))), title: text };
}

interface Grid {
  ws: Worksheet;
  theme: readonly string[];
  layout: Layout;
  measure: MeasureText;
  colVisible: (c: number) => boolean;
  findCell: (r: number, c: number) => Cell | undefined;
}

function makeDraft(grid: Grid, r: number, c: number, merge: Merge | undefined): Draft {
  const { layout, theme, measure } = grid;
  const lastRow = Math.min(merge?.r1 ?? r, layout.rowCount - 1);
  const lastCol = Math.min(merge?.c1 ?? c, layout.colCount - 1);
  let rowSpan = 0;
  for (let i = r; i <= lastRow; i++) if (layout.rowVisible[i]) rowSpan++;
  let colSpan = 0;
  let width = 0;
  for (let j = c; j <= lastCol; j++) {
    if (!grid.colVisible(j)) continue;
    colSpan++;
    width += layout.colWidth[j];
  }
  const cell = grid.findCell(r, c);
  const value = cell?.value as CellValue;
  let display = cellDisplay(value, cell?.numFmt, theme);
  const { style: alignStyle, align, wrap } = alignmentStyle(cell?.style?.alignment, display.naturalAlign);
  const font = cssFont(cell);
  const number = numericValue(value);
  let title: string | undefined;
  if (number !== null && display.text) {
    const fitted = fitNumber(number, cell?.numFmt, display.text, width - 2 * CELL_PADDING, font, measure);
    title = fitted.title;
    display = { ...display, text: fitted.text };
  }
  return {
    row: r,
    col: c,
    rowSpan,
    colSpan,
    lastRow,
    lastCol,
    cell,
    display,
    title,
    isNumber: number !== null,
    align,
    alignStyle,
    wrap,
    font,
    width,
    spillLeft: 0,
    spillRight: 0,
    fontScale: 1,
  };
}

function draftCells(grid: Grid, merges: Merge[]): Map<string, Draft> {
  const masterOf = new Map<string, Merge>();
  const covered = new Set<string>();
  for (const merge of merges) {
    masterOf.set(`${merge.r0},${merge.c0}`, merge);
    for (let r = merge.r0; r <= merge.r1; r++) {
      for (let c = merge.c0; c <= merge.c1; c++) if (r !== merge.r0 || c !== merge.c0) covered.add(`${r},${c}`);
    }
  }
  const drafts = new Map<string, Draft>();
  for (let r = 0; r < grid.layout.rowCount; r++) {
    if (!grid.layout.rowVisible[r]) continue;
    for (let c = 0; c < grid.layout.colCount; c++) {
      if (!grid.colVisible(c) || covered.has(`${r},${c}`)) continue;
      drafts.set(`${r},${c}`, makeDraft(grid, r, c, masterOf.get(`${r},${c}`)));
    }
  }
  return drafts;
}

// ── chữ tràn: chữ không xuống dòng lấn sang ô TRỐNG kề bên như Excel ──

/**
 * Chữ rộng hơn ô vẫn vừa nếu chỉ lệch chút ít: đó là sai khác metric giữa GDI của
 * Excel và font trình duyệt (Liberation Serif thay Times New Roman), không phải ý
 * người soạn - thu nhỏ vừa khít thay vì cắt mất chữ. Lệch nhiều hơn thì cắt như Excel.
 */
const METRIC_TOLERANCE = 0.9;

/** Tính phần tràn/thu cỡ chữ; trả tập cạnh phải (khóa "r,c") không kẻ lưới vì có chữ tràn qua. */
function applyOverflow(grid: Grid, drafts: Map<string, Draft>): Set<string> {
  const { layout, colVisible, measure } = grid;
  const suppressed = new Set<string>();
  const isFree = (r: number, c: number) => {
    const d = drafts.get(`${r},${c}`);
    return Boolean(d && !d.display.text && d.rowSpan === 1 && d.colSpan === 1);
  };
  for (const d of drafts.values()) {
    if (d.wrap || d.isNumber || !d.display.text) continue;
    const textWidth = measure(d.display.text, d.font);
    const overflow = textWidth + 2 * CELL_PADDING - d.width;
    if (overflow <= 0) continue;
    const shrink = Boolean(d.cell?.style?.alignment?.shrinkToFit);
    const spread = (direction: 1 | -1, need: number): number => {
      let gained = 0;
      let c = direction > 0 ? d.lastCol : d.col;
      while (gained < need) {
        const n = stepVisible(colVisible, layout.colCount, c, direction);
        if (n < 0 || !isFree(d.row, n)) break;
        suppressed.add(`${d.row},${direction > 0 ? c : n}`);
        gained += layout.colWidth[n];
        c = n;
      }
      return gained;
    };
    // Ô gộp và ô shrinkToFit không tràn sang ô bên cạnh (Excel cũng vậy).
    if (!shrink && d.rowSpan === 1 && d.colSpan === 1) {
      if (d.align === "right") d.spillLeft = spread(-1, overflow);
      else if (d.align === "center") {
        d.spillLeft = spread(-1, overflow / 2);
        d.spillRight = spread(1, overflow / 2);
      } else d.spillRight = spread(1, overflow);
    }
    const available = d.width - 2 * CELL_PADDING + d.spillLeft + d.spillRight;
    const ratio = available / textWidth;
    if (ratio < 1 && (shrink || ratio >= METRIC_TOLERANCE)) d.fontScale = Math.max(0.1, ratio);
  }
  return suppressed;
}

const scalePt = (size: CSSProperties["fontSize"], scale: number): string | undefined => {
  const pt = typeof size === "string" ? parseFloat(size) : undefined;
  return pt ? `${(pt * scale).toFixed(2)}pt` : undefined;
};

/** Thu cỡ chữ của ô (và từng đoạn rich text) theo `fontScale`. */
function scaledDisplay(d: Draft, baseSize: CSSProperties["fontSize"]): { display: CellDisplay; fontSize?: string } {
  if (d.fontScale >= 1) return { display: d.display };
  const runs = d.display.runs?.map((run) => ({ ...run, style: { ...run.style, fontSize: scalePt(run.style?.fontSize ?? baseSize, d.fontScale) } }));
  return { display: { ...d.display, runs }, fontSize: scalePt(baseSize, d.fontScale) };
}

// ── kiểu CSS: mỗi ô vẽ cạnh phải + dưới (dòng/cột đầu vẽ thêm trên/trái) ──

const BORDER_WEIGHT = (border: Partial<Border>) =>
  border.style === "thick" || border.style === "double" ? 3 : String(border.style).startsWith("medium") ? 2 : 1;

/** Cạnh chung của hai ô: viền rõ ràng của một bên thắng; cả hai có viền thì viền dày hơn thắng. */
function pickBorder(a: Partial<Border> | undefined, b: Partial<Border> | undefined): Partial<Border> | undefined {
  if (!a?.style) return b?.style ? b : undefined;
  if (!b?.style) return a;
  return BORDER_WEIGHT(b) > BORDER_WEIGHT(a) ? b : a;
}

function styleCell(grid: Grid, d: Draft, suppressed: Set<string>, first: { row: number; col: number }): CellModel {
  const { theme, layout, findCell, colVisible } = grid;
  const showGrid = grid.ws.views?.[0]?.showGridLines !== false;
  const borderAt = (r: number, c: number, side: BorderSide) => sideBorder(findCell(r, c)?.style?.border, side);
  const filled = (r: number, c: number) => Boolean(fillColor(findCell(r, c)?.style?.fill, theme));
  const edge = (explicit: Partial<Border> | undefined, gridAllowed: boolean) => borderCss(explicit, theme) ?? (showGrid && gridAllowed ? GRIDLINE : "none");
  const style = d.cell?.style;
  const background = fillColor(style?.fill, theme);
  const right = stepVisible(colVisible, layout.colCount, d.lastCol, 1);
  const rowVisible = (i: number) => layout.rowVisible[i];
  const below = stepVisible(rowVisible, layout.rowCount, d.lastRow, 1);
  const above = stepVisible(rowVisible, layout.rowCount, d.row, -1);
  const rightGrid = !background && !(right >= 0 && filled(d.row, right)) && !suppressed.has(`${d.row},${d.lastCol}`);
  const bottomGrid = !background && !(below >= 0 && filled(below, d.col));
  const css: CSSProperties = {
    ...fontStyle(style?.font, theme),
    ...d.alignStyle,
    background,
    borderRight: edge(pickBorder(borderAt(d.row, d.lastCol, "right"), right >= 0 ? borderAt(d.row, right, "left") : undefined), rightGrid),
    borderBottom: edge(pickBorder(borderAt(d.lastRow, d.col, "bottom"), below >= 0 ? borderAt(below, d.col, "top") : undefined), bottomGrid),
  };
  const topBorder = edge(
    pickBorder(borderAt(d.row, d.col, "top"), above >= 0 ? borderAt(above, d.col, "bottom") : undefined),
    !background && !(above >= 0 && filled(above, d.col)),
  );
  if (d.row === first.row) css.borderTop = topBorder;
  if (d.col === first.col) css.borderLeft = edge(borderAt(d.row, d.col, "left"), !background);
  const { display, fontSize } = scaledDisplay(d, css.fontSize ?? `${DEFAULT_FONT_PT}pt`);
  const contentStyle: CSSProperties = { whiteSpace: d.wrap ? "pre-wrap" : "pre", overflowWrap: d.wrap ? "anywhere" : undefined, overflow: "hidden", fontSize };
  if (d.spillLeft || d.spillRight) {
    contentStyle.position = "relative";
    contentStyle.left = -d.spillLeft;
    contentStyle.width = d.width - 2 * CELL_PADDING + d.spillLeft + d.spillRight;
    contentStyle.zIndex = 1;
  }
  return { row: d.row, col: d.col, rowSpan: d.rowSpan, colSpan: d.colSpan, display, title: d.title, style: css, topBorder, contentStyle };
}

export function buildSheetModel(ws: Worksheet, theme: readonly string[], options: BuildOptions = {}): SheetModel {
  const merges = parseMerges(ws.model?.merges);
  const layout = buildLayout(ws, merges, options);
  const colVisible = (c: number) => c >= 0 && c < layout.colCount && layout.colWidth[c] > 0;
  const grid: Grid = {
    ws,
    theme,
    layout,
    measure: options.measure ?? measureWithCanvas,
    colVisible,
    findCell: (r, c) => ws.findRow(r + 1)?.findCell(c + 1),
  };
  const drafts = draftCells(grid, merges);
  const suppressed = applyOverflow(grid, drafts);
  const first = { row: layout.rowVisible.indexOf(true), col: layout.colWidth.findIndex((w) => w > 0) };
  const rows: RowModel[] = [];
  for (let r = 0; r < layout.rowCount; r++) {
    if (!layout.rowVisible[r]) continue;
    const cells: CellModel[] = [];
    for (let c = 0; c < layout.colCount; c++) {
      const d = drafts.get(`${r},${c}`);
      if (d) cells.push(styleCell(grid, d, suppressed, first));
    }
    rows.push({ index: r, height: layout.rowHeight[r], cells });
  }
  return {
    name: ws.name,
    hidden: ws.state === "hidden" || ws.state === "veryHidden",
    showGridLines: ws.views?.[0]?.showGridLines !== false,
    cols: layout.colWidth.flatMap((width, index) => (width > 0 ? [{ index, width }] : [])),
    rows,
    truncated: layout.truncated,
  };
}

/** Toàn bộ workbook; bảng màu lấy từ theme của chính tệp. */
export function buildWorkbookModel(wb: Workbook, options: BuildOptions = {}): WorkbookModel {
  const themes = (wb as unknown as { _themes?: Record<string, string> })._themes;
  const theme = parseThemeColors(themes?.theme1);
  const sheets: SheetModel[] = [];
  wb.eachSheet((ws) => sheets.push(buildSheetModel(ws, theme, options)));
  return { sheets };
}

/**
 * Cửa sổ dòng [from, to] (chỉ số Excel) để trích đoạn trong ngăn xuất xứ. Ô gộp bắt
 * đầu phía trên cửa sổ được dời xuống dòng đầu cửa sổ (rowSpan rút lại) và ô gộp
 * tràn quá đáy cửa sổ bị cắt, để lưới không hụt/thừa ô.
 */
export function sliceRows(sheet: SheetModel, from: number, to: number): SheetModel {
  const position = new Map(sheet.rows.map((row, i) => [row.index, i]));
  const inside = sheet.rows.filter((row) => row.index >= from && row.index <= to);
  if (!inside.length) return { ...sheet, rows: [] };
  const top = position.get(inside[0].index) ?? 0;
  const bottom = position.get(inside[inside.length - 1].index) ?? top;
  const clamp = (cell: CellModel, start: number, pos: number): CellModel => ({ ...cell, rowSpan: Math.min(pos + cell.rowSpan - 1, bottom) - start + 1 });
  const carried = sheet.rows
    .slice(0, top)
    .flatMap((row, pos) => row.cells.filter((cell) => pos + cell.rowSpan - 1 >= top).map((cell) => ({ ...clamp(cell, top, pos), row: inside[0].index })));
  return {
    ...sheet,
    rows: inside.map((row, i) => {
      const cells = row.cells.map((cell) => clamp(cell, top + i, top + i));
      return i === 0 ? { ...row, cells: [...carried, ...cells].sort((a, b) => a.col - b.col) } : { ...row, cells };
    }),
  };
}
