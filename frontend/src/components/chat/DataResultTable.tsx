import type { ChatDataPayload, DataCellPayload, DataCellRef } from "../../types";
import { COLOR } from "../../theme";
import { IcExternal, IcLink, IcTable } from "../common/icons";

// Bảng kết quả số liệu cho chat lai (Sprint 9).
//
// Nguyên tắc: KHÔNG nhét số vào văn xuôi. Mỗi con số là một ô trong bảng; ô có
// tham chiếu xuất xứ là một <button> mở đúng đoạn nguyên văn (P1). Ô định danh
// thiết bị mở trang thiết bị trong tab "Dữ liệu". Trích dẫn sổ cái hiển thị tách
// bạch với trích dẫn QTKĐ của câu trả lời văn bản.

const DEVICE_COLUMNS = new Set(["serial_no", "device_id"]);

function CellView({
  column,
  cell,
  onOpenProvenance,
  onOpenDevice,
}: {
  column: string;
  cell: DataCellPayload | undefined;
  onOpenProvenance: (ref: DataCellRef) => void;
  onOpenDevice: (deviceId: number) => void;
}) {
  if (!cell) return <span style={mutedStyle}>—</span>;

  if (DEVICE_COLUMNS.has(column) && cell.device_id != null) {
    return (
      <button
        type="button"
        className="prov-cell"
        data-prov-kind="device"
        data-prov-id={cell.device_id}
        aria-label={`Xem lịch sử thiết bị ${cell.text}`}
        title="Xem trang thiết bị"
        onClick={() => onOpenDevice(cell.device_id as number)}
        style={deviceButton}
      >
        {cell.text}
        <IcExternal size={10} style={{ opacity: 0.7 }} />
      </button>
    );
  }

  if (cell.provenance) {
    return (
      <button
        type="button"
        className="prov-cell"
        data-prov-kind={cell.provenance.kind}
        data-prov-id={cell.provenance.id}
        data-prov-field={cell.provenance.field}
        aria-label={`Xem nguồn: ${cell.text}`}
        title="Xem đoạn nguyên văn sinh ra số này"
        onClick={() => onOpenProvenance(cell.provenance as DataCellRef)}
        style={cell.numeric ? provNumberButton : provTextButton}
      >
        {cell.text}
        <IcLink size={10} style={{ opacity: 0.7 }} />
      </button>
    );
  }

  return <span style={cell.numeric ? numberStyle : plainStyle}>{cell.text}</span>;
}

export default function DataResultTable({
  payload,
  onOpenProvenance,
  onOpenDevice,
}: {
  payload: ChatDataPayload;
  onOpenProvenance: (ref: DataCellRef) => void;
  onOpenDevice: (deviceId: number) => void;
}) {
  return (
    <section aria-label="Kết quả số liệu từ sổ cái" style={wrapperStyle}>
      <header style={headerStyle}>
        <IcTable size={15} style={{ color: COLOR.accent }} />
        <span style={{ fontWeight: 700, fontSize: "13px", color: COLOR.textPrimary }}>{payload.title}</span>
        <span style={ledgerBadge}>Sổ cái đã duyệt</span>
      </header>
      <p style={noteStyle}>{payload.note}</p>

      {payload.empty && <div style={emptyStyle}>Không có dữ liệu đã duyệt phù hợp.</div>}

      {payload.tables.map((table, tableIndex) => (
        <div key={tableIndex} style={{ overflowX: "auto" }}>
          <table role="table" style={tableStyle}>
            <caption style={captionStyle}>
              {table.title}
              {table.total != null ? ` — ${table.total} dòng` : ""}. Mỗi ô số bấm để mở đoạn nguyên văn nguồn.
            </caption>
            <thead>
              <tr>
                {table.columns.map((column) => (
                  <th key={column.key} scope="col" style={thStyle}>
                    {column.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {table.rows.map((row, rowIndex) => (
                <tr key={rowIndex}>
                  {table.columns.map((column) => (
                    <td key={column.key} style={tdStyle}>
                      <CellView
                        column={column.key}
                        cell={row[column.key]}
                        onOpenProvenance={onOpenProvenance}
                        onOpenDevice={onOpenDevice}
                      />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}

      {payload.citations.length > 0 && (
        <details style={citationsStyle}>
          <summary style={citationsSummary}>
            Trích dẫn sổ cái ({payload.citations.length}) — tách biệt với nguồn QTKĐ
          </summary>
          <ul style={citationList}>
            {payload.citations.map((citation, index) => (
              <li key={index} style={citationItem}>
                <span style={citationDoc}>
                  {citation.display_name ?? citation.file_stem ?? citation.document_id ?? "—"}
                  {citation.section_path ? ` • ${citation.section_path}` : ""}
                </span>
                {citation.quote && <span style={citationQuote}>“{citation.quote}”</span>}
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}

const wrapperStyle: React.CSSProperties = {
  width: "100%",
  border: `1px solid ${COLOR.border}`,
  borderRadius: 12,
  background: COLOR.surface,
  padding: "12px 14px",
  display: "flex",
  flexDirection: "column",
  gap: 8,
};
const headerStyle: React.CSSProperties = { display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" };
const ledgerBadge: React.CSSProperties = {
  fontSize: "10.5px",
  fontWeight: 700,
  color: COLOR.accentDark,
  background: COLOR.accentSoft,
  border: `1px solid ${COLOR.accentSoftBorder}`,
  padding: "2px 8px",
  borderRadius: 9999,
};
const noteStyle: React.CSSProperties = { margin: 0, fontSize: "11.5px", color: COLOR.textMuted, lineHeight: 1.5 };
const emptyStyle: React.CSSProperties = { fontSize: "12.5px", color: COLOR.textSecondary, padding: "6px 0" };
const tableStyle: React.CSSProperties = { width: "100%", borderCollapse: "collapse", fontSize: "12.5px" };
const captionStyle: React.CSSProperties = { textAlign: "left", padding: "4px 0 6px", color: COLOR.textSecondary, fontSize: "11.5px" };
const thStyle: React.CSSProperties = {
  textAlign: "left",
  padding: "6px 9px",
  borderBottom: `1px solid ${COLOR.border}`,
  color: COLOR.textSecondary,
  fontWeight: 700,
  whiteSpace: "nowrap",
};
const tdStyle: React.CSSProperties = { padding: "6px 9px", borderBottom: `1px solid ${COLOR.surfaceAlt}`, whiteSpace: "nowrap" };
const plainStyle: React.CSSProperties = { color: COLOR.textPrimary };
const mutedStyle: React.CSSProperties = { color: COLOR.textMuted };
const numberStyle: React.CSSProperties = { color: COLOR.textPrimary, fontVariantNumeric: "tabular-nums" };
const provNumberButton: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: 4,
  border: `1px solid ${COLOR.accentSoftBorder}`,
  background: COLOR.accentSoft,
  color: COLOR.accentDark,
  borderRadius: 7,
  padding: "1px 7px",
  fontSize: "12px",
  fontWeight: 700,
  cursor: "pointer",
  fontVariantNumeric: "tabular-nums",
};
const provTextButton: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: 4,
  border: "none",
  background: "transparent",
  color: COLOR.accentDark,
  padding: 0,
  fontSize: "12.5px",
  fontWeight: 600,
  cursor: "pointer",
  textDecoration: "underline dotted",
};
const deviceButton: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: 4,
  border: "none",
  background: "transparent",
  color: COLOR.accentDark,
  padding: 0,
  fontSize: "12.5px",
  fontWeight: 700,
  cursor: "pointer",
  textDecoration: "underline dotted",
};
const citationsStyle: React.CSSProperties = { borderTop: `1px solid ${COLOR.border}`, paddingTop: 6 };
const citationsSummary: React.CSSProperties = { cursor: "pointer", fontSize: "11.5px", fontWeight: 700, color: COLOR.textSecondary };
const citationList: React.CSSProperties = { listStyle: "none", margin: "6px 0 0", padding: 0, display: "flex", flexDirection: "column", gap: 5 };
const citationItem: React.CSSProperties = { fontSize: "11.5px", color: COLOR.textSecondary, display: "flex", flexDirection: "column", gap: 2 };
const citationDoc: React.CSSProperties = { fontWeight: 600, color: COLOR.textPrimary };
const citationQuote: React.CSSProperties = { color: COLOR.textMuted, fontStyle: "italic" };
