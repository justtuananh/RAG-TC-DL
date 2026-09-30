import { useState } from "react";
import { COLOR } from "../../../theme";
import XlsxSheetTable from "./XlsxSheetTable";
import { useWorkbook } from "./useWorkbook";

/** Trình xem tệp Excel gốc (.xlsx, .xls đã chuyển) ngay trong trình duyệt: lưới ô + tab sheet ở đáy như Excel. */
export default function XlsxFilePreview({ fileUrl, downloadUrl, name }: { fileUrl: string; downloadUrl: string; name: string }) {
  const state = useWorkbook(fileUrl);
  const [active, setActive] = useState(0);

  if (state.status !== "ready") {
    return (
      <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", padding: 20, color: COLOR.textMuted, fontSize: 13 }}>
        {state.status === "loading" ? (
          "Đang tải tệp gốc…"
        ) : (
          <span>
            Không hiển thị được tệp gốc ({state.message}).{" "}
            <a href={downloadUrl} download={name} style={{ color: COLOR.accent, fontWeight: 600 }}>
              Tải xuống để xem
            </a>
            .
          </span>
        )}
      </div>
    );
  }

  const sheets = state.model.sheets.filter((sheet) => !sheet.hidden);
  const sheet = sheets[Math.min(active, sheets.length - 1)];
  if (!sheet) {
    return <div style={{ flex: 1, padding: 20, textAlign: "center", color: COLOR.textMuted, fontSize: 13 }}>Tệp Excel không có sheet nào để hiển thị.</div>;
  }

  return (
    <div style={{ flex: 1, minWidth: 0, minHeight: 0, display: "flex", flexDirection: "column", background: COLOR.surface }}>
      <div style={{ flex: 1, minHeight: 0, overflow: "auto", background: COLOR.surfaceAlt }} tabIndex={0} aria-label={`Sheet ${sheet.name}`}>
        {sheet.rows.length ? (
          <XlsxSheetTable key={sheet.name} sheet={sheet} />
        ) : (
          <div style={{ padding: 20, color: COLOR.textMuted, fontSize: 13 }}>Sheet trống.</div>
        )}
        {sheet.truncated && (
          <div style={{ padding: "10px 14px", fontSize: 12, color: COLOR.textSecondary }}>
            Sheet quá lớn - chỉ hiển thị phần đầu. Tải tệp gốc để xem toàn bộ.
          </div>
        )}
      </div>
      <div
        role="tablist"
        aria-label="Các sheet"
        style={{
          flexShrink: 0,
          display: "flex",
          gap: 2,
          padding: "0 10px",
          overflowX: "auto",
          borderTop: `1px solid ${COLOR.border}`,
          background: COLOR.surface,
        }}
      >
        {sheets.map((item, index) => {
          const selected = item === sheet;
          return (
            <button
              key={item.name}
              role="tab"
              aria-selected={selected}
              onClick={() => setActive(index)}
              style={{
                flexShrink: 0,
                height: 32,
                padding: "0 14px",
                border: "none",
                borderBottom: `2px solid ${selected ? COLOR.accent : "transparent"}`,
                background: selected ? COLOR.accentSoft : "transparent",
                color: selected ? COLOR.accentDark : COLOR.textSecondary,
                fontFamily: "'Be Vietnam Pro', sans-serif",
                fontSize: 12.5,
                fontWeight: selected ? 700 : 500,
                cursor: "pointer",
                whiteSpace: "nowrap",
              }}
            >
              {item.name}
            </button>
          );
        })}
      </div>
    </div>
  );
}
