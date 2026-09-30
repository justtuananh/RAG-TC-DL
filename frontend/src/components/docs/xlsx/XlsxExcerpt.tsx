import type { ReactNode } from "react";
import type { SourceLocation } from "../../../types";
import { COLOR } from "../../../theme";
import { sliceRows } from "./sheetModel";
import XlsxSheetTable from "./XlsxSheetTable";
import { useWorkbook } from "./useWorkbook";

// Số dòng hiện thêm phía trên/dưới dòng nguồn để người đọc thấy ngữ cảnh (tiêu đề bảng, nhãn).
const CONTEXT_ROWS = 4;

/**
 * Trích đoạn lưới ô gốc quanh dòng sinh ra con số (P1): đúng font/viền/gộp ô của
 * biên bản, dòng nguồn tô nền, ô chứa giá trị viền đậm. Không tải/đọc được tệp thì
 * hiện `fallback` (bảng dựng từ trích dẫn đã lưu).
 */
export default function XlsxExcerpt({ fileUrl, location, fallback }: { fileUrl: string; location: SourceLocation; fallback: ReactNode }) {
  const state = useWorkbook(fileUrl);
  if (state.status === "error") return <>{fallback}</>;
  if (state.status === "loading") {
    return <div style={{ padding: "12px 2px", fontSize: 12.5, color: COLOR.textMuted }}>Đang dựng lưới ô gốc…</div>;
  }
  const sheet = state.model.sheets.find((item) => item.name === location.sheet);
  if (!sheet) return <>{fallback}</>;
  const excerpt = sliceRows(sheet, location.row - CONTEXT_ROWS, location.row + CONTEXT_ROWS);
  if (!excerpt.rows.some((row) => row.index === location.row)) return <>{fallback}</>;

  return (
    <div>
      <div style={{ fontSize: 11.5, color: COLOR.textMuted, marginBottom: 6 }}>
        Sheet <strong style={{ color: COLOR.textSecondary }}>{location.sheet}</strong> · dòng {location.row + 1}
      </div>
      <div style={{ maxHeight: 340, overflow: "auto", border: `1px solid ${COLOR.border}`, borderRadius: 8, background: COLOR.surface }}>
        <XlsxSheetTable sheet={excerpt} highlight={{ row: location.row, cols: location.highlight_cols }} scrollToHighlight />
      </div>
    </div>
  );
}
