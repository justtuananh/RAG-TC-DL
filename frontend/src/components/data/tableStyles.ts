import type { CSSProperties } from "react";
import { COLOR } from "../../theme";

// Style bảng dùng chung cho tab Dữ liệu: RecordsTable, CatalogTable, RecordDetailPanel,
// DeviceHistoryView cùng import, không chép lại.
//
// Sọc dòng chẵn và nền khi hover do lớp `.data-table` trong `src/index.css` đảm nhiệm,
// còn ô số bấm mở nguồn dùng lớp `.prov-cell` (gạch chân chấm, icon hiện khi hover/focus).

export const DATA_TABLE_CLASS = "data-table";
export const PROV_CELL_CLASS = "prov-cell";

export const tableStyle: CSSProperties = { width: "100%", borderCollapse: "collapse", fontSize: "12.5px" };

/** Đầu bảng dính trên cùng; đặt trên <thead>. */
export const headRowStyle: CSSProperties = { position: "sticky", top: 0, zIndex: 2, background: COLOR.surfaceAlt };

export const thStyle: CSSProperties = {
  textAlign: "left",
  padding: "8px 10px",
  borderBottom: `1px solid ${COLOR.borderStrong}`,
  color: COLOR.textSecondary,
  fontWeight: 700,
  whiteSpace: "nowrap",
  fontSize: "12px",
};

export const tdStyle: CSSProperties = {
  height: 44,
  padding: "6px 10px",
  borderBottom: `1px solid ${COLOR.border}`,
  color: COLOR.textPrimary,
  verticalAlign: "top",
};

export const numericStyle: CSSProperties = { fontVariantNumeric: "tabular-nums", color: COLOR.textPrimary };

/** Cột gồm hai dòng: dòng chính + dòng phụ màu mờ. */
export const cellStackStyle: CSSProperties = { display: "flex", flexDirection: "column", gap: 2, minWidth: 0 };
export const sublineStyle: CSSProperties = {
  fontSize: "11px",
  color: COLOR.textMuted,
  whiteSpace: "nowrap",
  overflow: "hidden",
  textOverflow: "ellipsis",
};

export const emptyCellStyle: CSSProperties = { padding: "40px 12px", textAlign: "center", color: COLOR.textSecondary, fontSize: "13px" };

export const alertStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 8,
  padding: "9px 14px",
  background: COLOR.dangerBg,
  color: COLOR.danger,
  borderBottom: `1px solid ${COLOR.dangerBorder}`,
  fontSize: "12.5px",
  fontWeight: 600,
};
