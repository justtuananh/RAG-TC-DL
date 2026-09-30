import { useEffect, useRef, type CSSProperties } from "react";
import { COLOR } from "../../../theme";
import { fontFamily } from "./cellStyle";
import { CELL_PADDING, columnLetter, type CellModel, type SheetModel } from "./sheetModel";

// Bảng sheet kiểu Excel: tiêu đề cột A, B, C… + số dòng dính mép, ô giữ nguyên
// font/nền/viền/gộp của tệp gốc. Dùng cho trình xem tài liệu và trích đoạn xuất xứ.

export interface SheetHighlight {
  row: number;
  cols: number[];
}

const HEADER_BORDER = "1px solid #D0D5DD";
const ROW_HEADER_WIDTH = 42;
const COL_HEADER_HEIGHT = 22;

const headerCell: CSSProperties = {
  background: "#F3F4F6",
  color: "#475467",
  fontFamily: "'Be Vietnam Pro', sans-serif",
  fontSize: 11,
  fontWeight: 500,
  textAlign: "center",
  borderRight: HEADER_BORDER,
  borderBottom: HEADER_BORDER,
  padding: 0,
  userSelect: "none",
};
const activeHeader: CSSProperties = { background: COLOR.accentSoft, color: COLOR.accentDark, fontWeight: 700 };

const TARGET_RING = `inset 0 0 0 2px ${COLOR.highlightStrong}`;

/** Ô có chữ tràn sang ô bên cạnh: vòng tô sáng bao cả phần chữ tràn, không chỉ riêng ô. */
const isSpilled = (cell: CellModel) => cell.contentStyle.width !== undefined;

function CellContent({ cell, target }: { cell: CellModel; target: boolean }) {
  const { display } = cell;
  // Vòng NGOÀI (không inset) để không đè lên chữ khi khung chữ ôm sát nội dung.
  const style = target && isSpilled(cell) ? { ...cell.contentStyle, boxShadow: `0 0 0 2px ${COLOR.highlightStrong}`, borderRadius: 2 } : cell.contentStyle;
  return (
    <div style={style}>
      {display.runs
        ? display.runs.map((run, i) => (
            <span key={i} style={run.style}>
              {run.text}
            </span>
          ))
        : display.text}
    </div>
  );
}

const covers = (cell: CellModel, highlight: SheetHighlight) =>
  highlight.row >= cell.row && highlight.row < cell.row + cell.rowSpan && highlight.cols.some((c) => c >= cell.col && c < cell.col + cell.colSpan);

interface Props {
  sheet: SheetModel;
  highlight?: SheetHighlight | null;
  /** cuộn vừa đủ để thấy ô được tô sáng (giữ cột nhãn bên trái khi có thể) */
  scrollToHighlight?: boolean;
}

export default function XlsxSheetTable({ sheet, highlight, scrollToHighlight = false }: Props) {
  const targetRef = useRef<HTMLTableCellElement | null>(null);
  const width = sheet.cols.reduce((sum, col) => sum + col.width, ROW_HEADER_WIDTH);
  const firstRow = sheet.rows[0]?.index;
  const target = highlight ? sheet.rows.flatMap((row) => row.cells).find((cell) => covers(cell, highlight)) : undefined;

  useEffect(() => {
    if (scrollToHighlight) targetRef.current?.scrollIntoView({ block: "nearest", inline: "nearest" });
  }, [scrollToHighlight, target]);

  return (
    <table
      style={{
        borderCollapse: "separate",
        borderSpacing: 0,
        tableLayout: "fixed",
        width,
        background: "#FFFFFF",
        color: "#000000",
        fontFamily: fontFamily("Calibri"),
        fontSize: "11pt",
        lineHeight: 1.2,
      }}
    >
      <colgroup>
        <col style={{ width: ROW_HEADER_WIDTH }} />
        {sheet.cols.map((col) => (
          <col key={col.index} style={{ width: col.width }} />
        ))}
      </colgroup>
      <thead>
        <tr style={{ height: COL_HEADER_HEIGHT }}>
          <th aria-label="Góc bảng" style={{ ...headerCell, position: "sticky", top: 0, left: 0, zIndex: 3 }} />
          {sheet.cols.map((col) => (
            <th
              key={col.index}
              scope="col"
              style={{ ...headerCell, position: "sticky", top: 0, zIndex: 2, ...(highlight?.cols.includes(col.index) ? activeHeader : null) }}
            >
              {columnLetter(col.index)}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {sheet.rows.map((row) => {
          const activeRow = highlight?.row === row.index;
          return (
            <tr key={row.index} style={{ height: row.height }}>
              <th scope="row" style={{ ...headerCell, position: "sticky", left: 0, zIndex: 2, ...(activeRow ? activeHeader : null) }}>
                {row.index + 1}
              </th>
              {row.cells.map((cell) => {
                const isTarget = highlight != null && covers(cell, highlight);
                const style: CSSProperties = {
                  ...cell.style,
                  padding: `0 ${CELL_PADDING}px`,
                  overflow: "visible",
                  ...(row.index === firstRow && !cell.style.borderTop ? { borderTop: cell.topBorder } : null),
                  ...(activeRow || isTarget ? { background: COLOR.highlight } : null),
                  ...(isTarget && !isSpilled(cell) ? { boxShadow: TARGET_RING } : null),
                };
                return (
                  <td
                    key={cell.col}
                    ref={cell === target ? targetRef : undefined}
                    rowSpan={cell.rowSpan > 1 ? cell.rowSpan : undefined}
                    colSpan={cell.colSpan > 1 ? cell.colSpan : undefined}
                    title={cell.title}
                    style={style}
                  >
                    <CellContent cell={cell} target={isTarget} />
                  </td>
                );
              })}
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
