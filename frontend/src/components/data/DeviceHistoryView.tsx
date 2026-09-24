import type { DataCellRef, DeviceHistory, DeviceHistoryRecord } from "../../types";
import { COLOR } from "../../theme";
import { IcArrowLeft, IcExternal, IcLink } from "../common/icons";
import ErrorTrendChart from "./ErrorTrendChart";
import { formatDate, verdictTone } from "./format";

// Trang thiết bị: định danh, dòng thời gian kiểm định, biểu đồ diễn biến sai số.

function TimelineItem({
  record,
  onOpenProvenance,
}: {
  record: DeviceHistoryRecord;
  onOpenProvenance: (ref: DataCellRef) => void;
}) {
  const tone = verdictTone(record.verdict, record.verdict_label);
  const dateRef = record.provenance.find((cell) => cell.field === "calibrated_at") ?? null;
  return (
    <li style={{ display: "flex", gap: 12, padding: "10px 0", borderBottom: `1px solid ${COLOR.surfaceAlt}` }}>
      <div style={{ flexShrink: 0, width: 96 }}>
        {dateRef ? (
          <button
            type="button"
            className="prov-cell"
            data-prov-kind={dateRef.kind}
            data-prov-id={dateRef.id}
            data-prov-field={dateRef.field}
            aria-label={`Xem nguồn ngày kiểm định ${formatDate(record.calibrated_at)}`}
            onClick={() => onOpenProvenance(dateRef)}
            style={linkButton}
          >
            {formatDate(record.calibrated_at)}
            <IcLink size={10} style={{ opacity: 0.7 }} />
          </button>
        ) : (
          <span style={{ fontSize: "12px", color: COLOR.textPrimary }}>{formatDate(record.calibrated_at)}</span>
        )}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <span style={{ fontWeight: 700, fontSize: "13px", color: COLOR.textPrimary }}>
            QTKĐ {record.procedure_number ?? "—"}
          </span>
          <span style={{ fontSize: "11px", fontWeight: 700, color: tone.fg, background: tone.bg, padding: "2px 8px", borderRadius: 9999 }}>
            {tone.label}
          </span>
          <span style={{ fontSize: "11.5px", color: COLOR.textMuted }}>{record.mode_label ?? "—"}</span>
          {record.cert_no && <span style={{ fontSize: "11.5px", color: COLOR.textMuted }}>GCN {record.cert_no}</span>}
        </div>
        <div style={{ fontSize: "12px", color: COLOR.textSecondary, marginTop: 3 }}>
          {record.measurement_count ?? 0} điểm đo · hạn hiệu lực {formatDate(record.expires_at)}
          {record.procedure_title ? ` · ${record.procedure_title}` : ""}
        </div>
      </div>
      {record.file_stem && (
        <a
          href={`/api/documents/${encodeURIComponent(record.file_stem)}/file`}
          target="_blank"
          rel="noreferrer"
          style={fileLink}
          aria-label={`Tải hồ sơ gốc của lần kiểm định ${formatDate(record.calibrated_at)}`}
        >
          <IcExternal size={12} /> Hồ sơ gốc
        </a>
      )}
    </li>
  );
}

export default function DeviceHistoryView({
  history,
  loading,
  error,
  onBack,
  onOpenProvenance,
}: {
  history: DeviceHistory | null;
  loading: boolean;
  error: string | null;
  onBack: () => void;
  onOpenProvenance: (ref: DataCellRef) => void;
}) {
  const device = history?.device;
  return (
    <div style={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "column" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "12px 20px", borderBottom: `1px solid ${COLOR.border}`, background: COLOR.surface }}>
        <button type="button" onClick={onBack} aria-label="Quay lại bảng dữ liệu" style={backButton}>
          <IcArrowLeft size={15} /> Quay lại bảng
        </button>
        <span style={{ fontWeight: 700, fontSize: "14.5px", color: COLOR.textPrimary }}>
          {device ? `Thiết bị ${device.serial_no ?? "(không số hiệu)"}` : "Trang thiết bị"}
        </span>
      </div>

      <div style={{ flex: 1, minHeight: 0, overflowY: "auto", padding: 20 }}>
        {loading && <div style={{ fontSize: "13px", color: COLOR.textSecondary }}>Đang tải lịch sử thiết bị…</div>}
        {error && (
          <div role="alert" style={{ fontSize: "13px", color: COLOR.danger }}>{error}</div>
        )}
        {history && device && (
          <div style={{ maxWidth: 1000, margin: "0 auto", display: "flex", flexDirection: "column", gap: 16 }}>
            <section style={cardStyle}>
              <h2 style={{ margin: "0 0 10px", fontSize: "14px", color: COLOR.textPrimary }}>Định danh thiết bị</h2>
              <dl style={{ display: "grid", gridTemplateColumns: "150px 1fr 150px 1fr", gap: "6px 12px", margin: 0, fontSize: "12.5px" }}>
                <dt style={dtStyle}>Số hiệu</dt>
                <dd style={ddStyle}>{device.serial_no ?? "—"}</dd>
                <dt style={dtStyle}>Loại thiết bị</dt>
                <dd style={ddStyle}>{device.device_type_name ?? "—"}</dd>
                <dt style={dtStyle}>Đại lượng</dt>
                <dd style={ddStyle}>{device.quantity_name ?? "—"}</dd>
                <dt style={dtStyle}>Ký hiệu/Model</dt>
                <dd style={ddStyle}>{device.model_code ?? "—"}</dd>
                <dt style={dtStyle}>Hãng sản xuất</dt>
                <dd style={ddStyle}>{device.manufacturer ?? "—"}</dd>
                <dt style={dtStyle}>Đơn vị sử dụng</dt>
                <dd style={ddStyle}>{device.owner_org ?? "—"}</dd>
                <dt style={dtStyle}>Số lần kiểm định</dt>
                <dd style={ddStyle}>{device.record_count}</dd>
              </dl>
            </section>

            <section style={cardStyle}>
              <h2 style={{ margin: "0 0 4px", fontSize: "14px", color: COLOR.textPrimary }}>Dòng thời gian kiểm định</h2>
              {history.records.length === 0 ? (
                <div style={{ fontSize: "12.5px", color: COLOR.textSecondary }}>Chưa có lần kiểm định nào được duyệt.</div>
              ) : (
                <ol style={{ listStyle: "none", margin: 0, padding: 0 }}>
                  {history.records.map((record) => (
                    <TimelineItem key={record.id} record={record} onOpenProvenance={onOpenProvenance} />
                  ))}
                </ol>
              )}
            </section>

            <section style={cardStyle}>
              <h2 style={{ margin: "0 0 10px", fontSize: "14px", color: COLOR.textPrimary }}>Diễn biến sai số theo mốc đo</h2>
              <ErrorTrendChart series={history.trend} onOpenProvenance={onOpenProvenance} />
            </section>
          </div>
        )}
      </div>
    </div>
  );
}

const cardStyle: React.CSSProperties = { background: COLOR.surface, border: `1px solid ${COLOR.border}`, borderRadius: 13, padding: "16px 18px" };
const dtStyle: React.CSSProperties = { fontWeight: 700, color: COLOR.textSecondary };
const ddStyle: React.CSSProperties = { margin: 0, color: COLOR.textPrimary };
const backButton: React.CSSProperties = { display: "inline-flex", alignItems: "center", gap: 6, height: 32, padding: "0 12px", borderRadius: 9, border: `1px solid ${COLOR.border}`, background: COLOR.surface, color: COLOR.textSecondary, fontWeight: 700, fontSize: "12.5px", cursor: "pointer" };
const linkButton: React.CSSProperties = { display: "inline-flex", alignItems: "center", gap: 4, border: "none", background: "transparent", padding: 0, color: COLOR.accentDark, fontSize: "12.5px", fontWeight: 700, cursor: "pointer", fontVariantNumeric: "tabular-nums" };
const fileLink: React.CSSProperties = { flexShrink: 0, alignSelf: "center", display: "inline-flex", alignItems: "center", gap: 5, fontSize: "12px", color: COLOR.accentDark, fontWeight: 600, textDecoration: "none" };
