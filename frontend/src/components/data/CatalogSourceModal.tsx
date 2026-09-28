import type { CatalogRow } from "../../types";
import { COLOR } from "../../theme";
import { IcFile, IcX } from "../common/icons";

// Hộp xem nguồn nguyên văn của một dòng danh mục NAS (P1): tên tài liệu + quote
// cả dòng nguồn. Thuần trình bày; đóng khi bấm nền hoặc nút X.

export default function CatalogSourceModal({
  row,
  onClose,
}: {
  row: CatalogRow | null;
  onClose: () => void;
}) {
  if (!row) return null;
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Nguồn nguyên văn dòng danh mục"
      style={overlayStyle}
      onClick={onClose}
    >
      <div style={panelStyle} onClick={(event) => event.stopPropagation()}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
          <IcFile size={15} style={{ color: COLOR.accent }} />
          <span style={{ fontWeight: 700, fontSize: "14px", color: COLOR.textPrimary }}>
            {row.display_name ?? row.file_stem ?? row.document_id}
          </span>
          <span style={badgeStyle}>extraction #{row.extraction_id}</span>
          <div style={{ flex: 1 }} />
          <button type="button" onClick={onClose} aria-label="Đóng nguồn" style={closeButton}>
            <IcX size={16} />
          </button>
        </div>
        <div style={{ fontSize: "11.5px", color: COLOR.textMuted, marginBottom: 8 }}>
          Nguyên văn dòng nguồn (P1) — đối chiếu trước khi tin dữ liệu.
        </div>
        <pre style={quoteStyle}>{row.quote}</pre>
      </div>
    </div>
  );
}

const overlayStyle: React.CSSProperties = {
  position: "fixed",
  inset: 0,
  zIndex: 60,
  background: "rgba(16,24,40,.45)",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  padding: 20,
};
const panelStyle: React.CSSProperties = {
  width: 720,
  maxWidth: "100%",
  maxHeight: "85vh",
  display: "flex",
  flexDirection: "column",
  background: COLOR.surface,
  border: `1px solid ${COLOR.border}`,
  borderRadius: 13,
  padding: 18,
};
const badgeStyle: React.CSSProperties = {
  fontSize: "10.5px",
  fontWeight: 700,
  background: COLOR.surfaceAlt,
  color: COLOR.textSecondary,
  padding: "2px 8px",
  borderRadius: 9999,
};
const closeButton: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  width: 30,
  height: 30,
  border: `1px solid ${COLOR.border}`,
  borderRadius: 8,
  background: COLOR.surface,
  color: COLOR.textSecondary,
  cursor: "pointer",
};
const quoteStyle: React.CSSProperties = {
  margin: 0,
  padding: "12px 14px",
  overflow: "auto",
  background: COLOR.accentSoft,
  border: `1px solid ${COLOR.accentSoftBorder}`,
  borderRadius: 9,
  fontFamily: "'Lora', Georgia, serif",
  fontSize: "13px",
  lineHeight: 1.6,
  color: COLOR.textPrimary,
  whiteSpace: "pre-wrap",
  wordBreak: "break-word",
};
