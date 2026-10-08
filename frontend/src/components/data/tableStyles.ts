import type { CSSProperties } from "react";
import { COLOR } from "../../theme";

// Style bảng dùng chung cho tab Dữ liệu: RecordsTable, CatalogTable, RecordDetailPanel,
// DeviceHistoryView cùng import, không chép lại.
//
// Nền khi hover do lớp `.data-table` trong `src/index.css` đảm nhiệm (không sọc dòng: chỉ một
// vạch mảnh giữa các dòng cho đỡ rối mắt), còn ô số bấm mở nguồn dùng lớp `.prov-cell`
// (số thường, nền và icon liên kết hiện khi hover/focus).

export const DATA_TABLE_CLASS = "data-table";
export const PROV_CELL_CLASS = "prov-cell";

export const tableStyle: CSSProperties = { width: "100%", borderCollapse: "collapse", fontSize: "13.5px" };

/** Đầu bảng dính trên cùng; đặt trên <thead>. */
export const headRowStyle: CSSProperties = { position: "sticky", top: 0, zIndex: 2, background: COLOR.surface };

export const thStyle: CSSProperties = {
  textAlign: "left",
  padding: "10px 12px",
  borderBottom: `1px solid ${COLOR.border}`,
  color: COLOR.textMuted,
  fontWeight: 600,
  whiteSpace: "nowrap",
  fontSize: "12px",
};

export const tdStyle: CSSProperties = {
  height: 56,
  padding: "8px 12px",
  borderBottom: `1px solid ${COLOR.border}`,
  color: COLOR.textPrimary,
  verticalAlign: "middle",
};

export const numericStyle: CSSProperties = { fontVariantNumeric: "tabular-nums", color: COLOR.textPrimary };

/** Cột gồm hai dòng: dòng chính + dòng phụ màu mờ. */
export const cellStackStyle: CSSProperties = { display: "flex", flexDirection: "column", gap: 2, minWidth: 0 };
export const sublineStyle: CSSProperties = {
  fontSize: "12px",
  color: COLOR.textMuted,
  whiteSpace: "nowrap",
  overflow: "hidden",
  textOverflow: "ellipsis",
};

/** Ẩn khỏi mắt nhưng trình đọc màn hình vẫn đọc (caption, tiêu đề cột chỉ có icon). */
export const visuallyHidden: CSSProperties = {
  position: "absolute",
  width: 1,
  height: 1,
  padding: 0,
  margin: -1,
  overflow: "hidden",
  clip: "rect(0 0 0 0)",
  whiteSpace: "nowrap",
  border: 0,
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
