import type { ViewingDoc } from "../../types";
import { COLOR } from "../../theme";
import { STATUS_STYLE, STATUS_TAB_LABEL } from "./docStatus";
import { IcCheck, IcClock, IcFile } from "../common/icons";

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", gap: 10, padding: "8px 0", borderBottom: `1px solid ${COLOR.border}` }}>
      <span style={{ fontSize: "12px", color: COLOR.textMuted }}>{label}</span>
      <span style={{ fontSize: "12.5px", fontWeight: 600, color: COLOR.textPrimary, textAlign: "right" }}>{value}</span>
    </div>
  );
}

/** Panel "Thông tin tệp" — chỉ hiện các trường có dữ liệu thật (không suy diễn). */
export default function DocInfoPanel({ viewingDoc }: { viewingDoc: ViewingDoc }) {
  const st = viewingDoc.status ? STATUS_STYLE[viewingDoc.status] : null;
  const hasInfo = Boolean(viewingDoc.ext || viewingDoc.size || viewingDoc.date || viewingDoc.status || viewingDoc.kind);
  if (!hasInfo) return null;

  return (
    <aside style={{ flexShrink: 0, width: 250, overflowY: "auto", background: COLOR.surface, padding: 18 }}>
      <div style={{ fontSize: "12px", fontWeight: 700, color: COLOR.textPrimary, marginBottom: 6, display: "flex", alignItems: "center", gap: 6 }}>
        <IcFile size={13} style={{ color: COLOR.accent }} /> Thông tin tệp
      </div>
      {viewingDoc.ext && <InfoRow label="Loại" value={viewingDoc.ext} />}
      {viewingDoc.size && <InfoRow label="Kích thước" value={viewingDoc.size} />}
      {viewingDoc.date && <InfoRow label="Ngày cập nhật" value={viewingDoc.date} />}
      {viewingDoc.status && (
        <div style={{ display: "flex", justifyContent: "space-between", gap: 10, padding: "8px 0" }}>
          <span style={{ fontSize: "12px", color: COLOR.textMuted }}>Trạng thái</span>
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 5,
              padding: "3px 9px",
              borderRadius: 9999,
              fontSize: "11px",
              fontWeight: 600,
              background: st?.bg,
              color: st?.color,
              border: `1px solid ${st?.border}`,
            }}
          >
            {viewingDoc.status === "ready" && <IcCheck size={10} strokeWidth={2.5} />}
            {viewingDoc.status === "pending" && <IcClock size={10} />}
            {STATUS_TAB_LABEL[viewingDoc.status]}
          </span>
        </div>
      )}
      {viewingDoc.kind && <InfoRow label="Nội dung" value={viewingDoc.kind} />}
    </aside>
  );
}
