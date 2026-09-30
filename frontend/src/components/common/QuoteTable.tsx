import type { CSSProperties } from "react";
import { COLOR } from "../../theme";
import { parseQuoteRows } from "./quoteRows";

// Khi không vẽ được lưới ô gốc, dựng trích dẫn "a | b | c" thành bảng để người đọc
// thấy ranh giới từng ô thay vì chuỗi có dấu "|".

const norm = (text: string) => text.replace(/\s+/g, " ").trim();

const cellStyle: CSSProperties = {
  border: `1px solid ${COLOR.border}`,
  padding: "6px 10px",
  verticalAlign: "top",
  whiteSpace: "pre-wrap",
  color: COLOR.textPrimary,
};
const markedCell: CSSProperties = {
  background: COLOR.highlight,
  boxShadow: `inset 0 0 0 2px ${COLOR.highlightStrong}`,
  fontWeight: 700,
};

/** Bảng dựng từ trích dẫn; ô trùng (hoặc chứa) `value` được tô sáng. */
export default function QuoteTable({ quote, value, maxHeight = 340 }: { quote: string; value?: string | null; maxHeight?: number }) {
  const groups = parseQuoteRows(quote);
  const wanted = value ? norm(value) : "";
  const isMarked = (cell: string) => Boolean(wanted) && norm(cell).includes(wanted);
  const single = groups.length === 1 && groups[0].rows.length === 1;
  return (
    <div style={{ maxHeight, overflow: "auto" }}>
      {groups.map((group, gi) => {
        const width = Math.max(1, ...group.rows.map((row) => row.length));
        return (
          <div key={gi} style={{ marginTop: gi ? 12 : 0 }}>
            {group.sheet && <div style={{ fontSize: 11.5, fontWeight: 700, color: COLOR.textSecondary, margin: "0 0 5px" }}>Sheet {group.sheet}</div>}
            <table
              style={{ borderCollapse: "collapse", fontFamily: "'Be Vietnam Pro', sans-serif", fontSize: 12.5, lineHeight: 1.45, background: COLOR.surface }}
            >
              <tbody>
                {group.rows.map((row, ri) => (
                  <tr key={ri} style={single ? { background: COLOR.highlight } : undefined}>
                    {row.map((cell, ci) => (
                      <td
                        key={ci}
                        colSpan={ci === row.length - 1 && row.length < width ? width - row.length + 1 : undefined}
                        style={{ ...cellStyle, ...(isMarked(cell) ? markedCell : null) }}
                      >
                        {cell}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      })}
    </div>
  );
}
