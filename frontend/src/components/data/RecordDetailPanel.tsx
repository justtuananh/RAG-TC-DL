import type { DataCellRef, DataMeasurement, DataRecordRow } from "../../types";
import { COLOR } from "../../theme";
import { IcArrowRight, IcClock, IcFile, IcLink, IcX } from "../common/icons";
import { formatDate, formatNumber, verdictTone, withinLimitTone } from "./format";

// Bảng chi tiết một hồ sơ: các trường đầu mục + điểm đo. Mỗi ô số là nút mở xuất xứ.

function ProvButton({
  label,
  cellRef,
  onOpen,
}: {
  label: string;
  cellRef: DataCellRef | null;
  onOpen: (ref: DataCellRef) => void;
}) {
  if (!cellRef) return <span style={mono}>{label}</span>;
  return (
    <button
      type="button"
      className="prov-cell"
      data-prov-kind={cellRef.kind}
      data-prov-id={cellRef.id}
      data-prov-field={cellRef.field}
      title="Xem đoạn nguyên văn"
      aria-label={`Xem nguồn: ${label}`}
      onClick={() => onOpen(cellRef)}
      style={provButton}
    >
      {label}
      <IcLink size={10} style={{ opacity: 0.7 }} />
    </button>
  );
}

function measurementRef(point: DataMeasurement, field: string): DataCellRef | null {
  return point.provenance.find((cell) => cell.field === field) ?? null;
}

export default function RecordDetailPanel({
  record,
  loading,
  onClose,
  onOpenProvenance,
  onOpenDevice,
}: {
  record: DataRecordRow | null;
  loading: boolean;
  onClose: () => void;
  onOpenProvenance: (ref: DataCellRef) => void;
  onOpenDevice: (record: DataRecordRow) => void;
}) {
  if (!record) {
    return (
      <aside aria-label="Chi tiết hồ sơ" style={panelStyle}>
        <div style={{ padding: 20, color: COLOR.textSecondary, fontSize: "13px" }}>
          {loading ? "Đang tải chi tiết…" : "Chọn một hồ sơ trong bảng để xem điểm đo và xuất xứ."}
        </div>
      </aside>
    );
  }

  const tone = verdictTone(record.verdict, record.verdict_label);
  const ref = (field: string) => record.provenance.find((cell) => cell.field === field) ?? null;

  return (
    <aside aria-label={`Chi tiết hồ sơ ${record.serial_no ?? record.id}`} style={panelStyle}>
      <header style={{ display: "flex", alignItems: "center", gap: 8, padding: "12px 16px", borderBottom: `1px solid ${COLOR.border}` }}>
        <IcFile size={15} style={{ color: COLOR.accent }} />
        <span style={{ fontWeight: 700, fontSize: "14px", color: COLOR.textPrimary }}>{record.serial_no ?? "(không số hiệu)"}</span>
        <span style={{ fontSize: "11px", fontWeight: 700, color: tone.fg, background: tone.bg, padding: "2px 8px", borderRadius: 9999 }}>{tone.label}</span>
        <div style={{ flex: 1 }} />
        <button type="button" onClick={onClose} aria-label="Đóng chi tiết" style={iconButton}>
          <IcX size={15} />
        </button>
      </header>

      <div style={{ flex: 1, minHeight: 0, overflowY: "auto", padding: "14px 16px", display: "flex", flexDirection: "column", gap: 14 }}>
        <dl style={gridStyle}>
          <dt style={dtStyle}>Loại thiết bị</dt>
          <dd style={ddStyle}>{record.device_type_name ?? "—"}</dd>
          <dt style={dtStyle}>Đại lượng</dt>
          <dd style={ddStyle}>{record.quantity_name ?? "—"}</dd>
          <dt style={dtStyle}>Ký hiệu/Model</dt>
          <dd style={ddStyle}>{record.model_code ?? "—"}</dd>
          <dt style={dtStyle}>Hãng sản xuất</dt>
          <dd style={ddStyle}>{record.manufacturer ?? "—"}</dd>
          <dt style={dtStyle}>Đơn vị sử dụng</dt>
          <dd style={ddStyle}>{record.owner_org ?? "—"}</dd>
          <dt style={dtStyle}>QTKĐ</dt>
          <dd style={ddStyle}>{record.procedure_number ?? "—"}</dd>
          <dt style={dtStyle}>Chế độ</dt>
          <dd style={ddStyle}>{record.mode_label ?? "—"}</dd>
          <dt style={dtStyle}>Ngày kiểm định</dt>
          <dd style={ddStyle}>
            <ProvButton label={formatDate(record.calibrated_at)} cellRef={ref("calibrated_at")} onOpen={onOpenProvenance} />
          </dd>
          <dt style={dtStyle}>Hạn hiệu lực</dt>
          <dd style={ddStyle}>
            {record.expires_at ? <ProvButton label={formatDate(record.expires_at)} cellRef={ref("expires_at")} onOpen={onOpenProvenance} /> : "—"}
          </dd>
          <dt style={dtStyle}>Nhiệt độ</dt>
          <dd style={ddStyle}>
            {record.env_temp_c != null ? (
              <ProvButton label={`${formatNumber(record.env_temp_c, 1)} °C`} cellRef={ref("env_temp_c")} onOpen={onOpenProvenance} />
            ) : "—"}
          </dd>
          <dt style={dtStyle}>Độ ẩm</dt>
          <dd style={ddStyle}>
            {record.env_humidity_pct != null ? (
              <ProvButton label={`${formatNumber(record.env_humidity_pct, 1)} %RH`} cellRef={ref("env_humidity_pct")} onOpen={onOpenProvenance} />
            ) : "—"}
          </dd>
          <dt style={dtStyle}>Phạm vi đo</dt>
          <dd style={ddStyle}>
            <ProvButton
              label={record.range_min == null && record.range_max == null ? "—" : `${formatNumber(record.range_min)} – ${formatNumber(record.range_max)}${record.range_unit_code ? ` ${record.range_unit_code}` : ""}`}
              cellRef={ref("range_min")}
              onOpen={onOpenProvenance}
            />
          </dd>
          <dt style={dtStyle}>Cấp chính xác</dt>
          <dd style={ddStyle}>
            <ProvButton label={record.accuracy_text ?? "—"} cellRef={ref("accuracy_text")} onOpen={onOpenProvenance} />
          </dd>
          <dt style={dtStyle}>Số giấy chứng nhận</dt>
          <dd style={ddStyle}>{record.cert_no ?? "—"}</dd>
          <dt style={dtStyle}>Phòng đo</dt>
          <dd style={ddStyle}>{record.lab_name ?? "—"}</dd>
          <dt style={dtStyle}>Mục nguồn</dt>
          <dd style={ddStyle}>{record.extraction_section_path ?? "—"}</dd>
          <dt style={dtStyle}>Chunk nguồn</dt>
          <dd style={ddStyle}>{record.extraction_chunk_id ?? "—"}</dd>
        </dl>

        <button
          type="button"
          onClick={() => onOpenDevice(record)}
          style={{ ...ghostButton, alignSelf: "flex-start" }}
        >
          Xem lịch sử thiết bị <IcArrowRight size={13} />
        </button>

        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 7, marginBottom: 6 }}>
            <IcClock size={14} style={{ color: COLOR.accent }} />
            <span style={{ fontWeight: 700, fontSize: "13px", color: COLOR.textPrimary }}>
              Điểm đo ({record.measurements?.length ?? 0})
            </span>
          </div>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "12px" }}>
            <caption style={{ textAlign: "left", color: COLOR.textSecondary, fontSize: "11.5px", paddingBottom: 4 }}>
              Điểm đo của hồ sơ — mỗi ô số bấm để mở nguồn.
            </caption>
            <thead>
              <tr>
                {["Mốc", "Danh nghĩa", "Đo được", "Sai số", "Giới hạn", "Đối chiếu"].map((heading) => (
                  <th key={heading} scope="col" style={thStyle}>{heading}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(record.measurements ?? []).length === 0 ? (
                <tr>
                  <td colSpan={6} style={{ ...tdStyle, color: COLOR.textSecondary, textAlign: "center" }}>
                    Hồ sơ không có điểm đo.
                  </td>
                </tr>
              ) : (
                (record.measurements ?? []).map((point) => {
                  const limitTone = withinLimitTone(point.within_limit);
                  return (
                    <tr key={point.id}>
                      <td style={tdStyle}>{point.step_code ?? point.label ?? "—"}</td>
                      <td style={tdStyle}><ProvButton label={formatNumber(point.nominal_value)} cellRef={measurementRef(point, "nominal")} onOpen={onOpenProvenance} /></td>
                      <td style={tdStyle}><ProvButton label={formatNumber(point.measured_value)} cellRef={measurementRef(point, "measured")} onOpen={onOpenProvenance} /></td>
                      <td style={tdStyle}><ProvButton label={`${formatNumber(point.error_value)}${point.unit_code ? ` ${point.unit_code}` : ""}`} cellRef={measurementRef(point, "error")} onOpen={onOpenProvenance} /></td>
                      <td style={tdStyle}><ProvButton label={formatNumber(point.limit_value)} cellRef={measurementRef(point, "limit")} onOpen={onOpenProvenance} /></td>
                      <td style={tdStyle}>
                        <span style={{ fontSize: "10.5px", fontWeight: 700, color: limitTone.fg, background: limitTone.bg, padding: "2px 7px", borderRadius: 9999 }}>
                          {limitTone.label}
                        </span>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </aside>
  );
}

const panelStyle: React.CSSProperties = { width: 430, flexShrink: 0, borderLeft: `1px solid ${COLOR.border}`, background: COLOR.surface, display: "flex", flexDirection: "column", minHeight: 0 };
const gridStyle: React.CSSProperties = { display: "grid", gridTemplateColumns: "130px 1fr", gap: "5px 10px", margin: 0, fontSize: "12.5px" };
const dtStyle: React.CSSProperties = { fontWeight: 700, color: COLOR.textSecondary };
const ddStyle: React.CSSProperties = { margin: 0, color: COLOR.textPrimary, wordBreak: "break-word" };
const mono: React.CSSProperties = { fontVariantNumeric: "tabular-nums" };
const provButton: React.CSSProperties = { display: "inline-flex", alignItems: "center", gap: 4, border: `1px solid ${COLOR.accentSoftBorder}`, background: COLOR.accentSoft, color: COLOR.accentDark, borderRadius: 7, padding: "1px 7px", fontSize: "11.5px", fontWeight: 700, cursor: "pointer", fontVariantNumeric: "tabular-nums" };
const ghostButton: React.CSSProperties = { display: "inline-flex", alignItems: "center", gap: 6, height: 32, padding: "0 12px", borderRadius: 9, border: `1px solid ${COLOR.accentSoftBorder}`, background: COLOR.surface, color: COLOR.accentDark, fontWeight: 700, fontSize: "12.5px", cursor: "pointer" };
const iconButton: React.CSSProperties = { width: 28, height: 28, borderRadius: 8, border: `1px solid ${COLOR.border}`, background: COLOR.surface, color: COLOR.textSecondary, cursor: "pointer", display: "inline-flex", alignItems: "center", justifyContent: "center" };
const thStyle: React.CSSProperties = { textAlign: "left", color: COLOR.textSecondary, borderBottom: `1px solid ${COLOR.border}`, padding: "5px 7px", fontWeight: 700 };
const tdStyle: React.CSSProperties = { padding: "5px 7px", borderBottom: `1px solid ${COLOR.surfaceAlt}`, color: COLOR.textPrimary };
