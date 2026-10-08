import { useEffect } from "react";
import type { DataCellRef, DataMeasurement, DataRecordRow } from "../../types";
import { COLOR } from "../../theme";
import { IcArrowRight, IcClock, IcLink, IcX } from "../common/icons";
import { expiryStatus, formatDate, formatNumber, rangeLabel, verdictTone, withinLimitTone } from "./format";
import { DATA_TABLE_CLASS, tableStyle, tdStyle, thStyle } from "./tableStyles";

// Panel chi tiết một hồ sơ: chỉ hiện khi đã chọn hồ sơ, trượt vào từ phải.
// Thông tin nhóm thành các khối (Thời hạn / Đặc tính đo / Điều kiện môi trường / Điểm đo).
// Mỗi ô số là nút mở xuất xứ (P1).

const PANEL_WIDTH = 400;

function ProvButton({ label, cellRef, onOpen }: { label: string; cellRef: DataCellRef | null; onOpen: (ref: DataCellRef) => void }) {
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
    >
      {label}
      <IcLink size={10} />
    </button>
  );
}

function InfoRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={infoRow}>
      <span style={infoLabel}>{label}</span>
      <span style={infoValue}>{children}</span>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h3 style={sectionTitle}>{title}</h3>
      <div style={{ display: "flex", flexDirection: "column" }}>{children}</div>
    </section>
  );
}

function measurementRef(point: DataMeasurement, field: string): DataCellRef | null {
  return point.provenance.find((cell) => cell.field === field) ?? null;
}

/** Nhãn mốc đo "mục đo · nhãn" (ví dụ "A.4 · 5"), khớp khóa ở ``_build_trend``. */
function measurementLabel(point: DataMeasurement): string {
  const parts = [point.step_code, point.label].filter((part): part is string => Boolean(part));
  return parts.length > 0 ? parts.join(" · ") : "—";
}

/** Giá trị kèm đơn vị; giá trị trống trả "—" KHÔNG kèm đơn vị (M2). */
function valueWithUnit(value: number | null, unit: string | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `${formatNumber(value)}${unit ? ` ${unit}` : ""}`;
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
  // Phím Esc đóng panel (chỉ khi có hồ sơ đang xem).
  useEffect(() => {
    if (!record) return;
    const handler = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !event.defaultPrevented) onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [record, onClose]);

  if (!record) {
    if (!loading) return null;
    return (
      <aside aria-label="Chi tiết hồ sơ" className="data-panel-in" style={panelStyle}>
        <div style={{ padding: 20, color: COLOR.textSecondary, fontSize: "13px" }}>Đang tải chi tiết…</div>
      </aside>
    );
  }

  const tone = verdictTone(record.verdict, record.verdict_label);
  const status = expiryStatus(record.expires_at);
  const ref = (field: string) => record.provenance.find((cell) => cell.field === field) ?? null;

  return (
    <aside aria-label={`Chi tiết hồ sơ ${record.serial_no ?? record.id}`} className="data-panel-in" style={panelStyle}>
      <header style={headerStyle}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            <span style={{ fontWeight: 700, fontSize: "18px", color: COLOR.textPrimary }}>{record.serial_no ?? "(không số hiệu)"}</span>
            <span style={{ ...verdictBadge, color: tone.fg, background: tone.bg }}>{tone.label}</span>
          </div>
          <div style={{ fontSize: "12px", color: COLOR.textMuted, marginTop: 3 }}>
            {record.device_type_name ?? "—"} · QTKĐ {record.procedure_number ?? "—"}
          </div>
        </div>
        <button type="button" onClick={onClose} aria-label="Đóng chi tiết" style={iconButton}>
          <IcX size={15} />
        </button>
      </header>

      <div style={bodyStyle}>
        <Section title="Định danh">
          <InfoRow label="Ký hiệu/Model">{record.model_code ?? "—"}</InfoRow>
          <InfoRow label="Hãng sản xuất">{record.manufacturer ?? "—"}</InfoRow>
          <InfoRow label="Đại lượng">{record.quantity_name ?? "—"}</InfoRow>
          <InfoRow label="Đơn vị sử dụng">{record.owner_org ?? "—"}</InfoRow>
        </Section>

        <Section title="Thời hạn">
          <InfoRow label="Ngày kiểm định">
            <ProvButton label={formatDate(record.calibrated_at)} cellRef={ref("calibrated_at")} onOpen={onOpenProvenance} />
          </InfoRow>
          <InfoRow label="Hiệu lực">
            {record.expires_at ? (
              <span style={{ display: "inline-flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                <ProvButton label={formatDate(record.expires_at)} cellRef={ref("expires_at")} onOpen={onOpenProvenance} />
                <span style={{ ...statusBadge, color: status.fg, background: status.bg }}>{status.label}</span>
              </span>
            ) : (
              "—"
            )}
          </InfoRow>
          <InfoRow label="Chế độ">{record.mode_label ?? "—"}</InfoRow>
          <InfoRow label="Số biên bản">{record.cert_no ?? "—"}</InfoRow>
        </Section>

        <Section title="Đặc tính đo">
          <InfoRow label="Phạm vi đo">
            <ProvButton label={rangeLabel(record)} cellRef={ref("range_min")} onOpen={onOpenProvenance} />
          </InfoRow>
          <InfoRow label="Cấp chính xác">
            <ProvButton label={record.accuracy_text ?? "—"} cellRef={ref("accuracy_text")} onOpen={onOpenProvenance} />
          </InfoRow>
          <InfoRow label="Số điểm đo">
            {record.measurement_count != null ? (
              <ProvButton label={formatNumber(record.measurement_count, 0)} cellRef={ref("measurement_count")} onOpen={onOpenProvenance} />
            ) : (
              "—"
            )}
          </InfoRow>
        </Section>

        <Section title="Điều kiện môi trường">
          <InfoRow label="Nhiệt độ">
            {record.env_temp_c != null ? (
              <ProvButton label={`${formatNumber(record.env_temp_c, 1)} °C`} cellRef={ref("env_temp_c")} onOpen={onOpenProvenance} />
            ) : (
              "—"
            )}
          </InfoRow>
          <InfoRow label="Độ ẩm">
            {record.env_humidity_pct != null ? (
              <ProvButton label={`${formatNumber(record.env_humidity_pct, 1)} %RH`} cellRef={ref("env_humidity_pct")} onOpen={onOpenProvenance} />
            ) : (
              "—"
            )}
          </InfoRow>
        </Section>

        <Section title={`Điểm đo (${record.measurements?.length ?? 0})`}>
          <div style={{ overflowX: "auto" }}>
            <table className={DATA_TABLE_CLASS} style={tableStyle}>
              <caption style={{ textAlign: "left", color: COLOR.textSecondary, fontSize: "11.5px", paddingBottom: 4 }}>
                Điểm đo của hồ sơ: mỗi ô số bấm để mở nguồn.
              </caption>
              <thead>
                <tr>
                  {["Mốc", "Danh nghĩa", "Đo được", "Sai số", "Giới hạn", "Đối chiếu"].map((heading) => (
                    <th key={heading} scope="col" style={measureTh}>
                      {heading}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(record.measurements ?? []).length === 0 ? (
                  <tr>
                    <td colSpan={6} style={{ ...measureTd, color: COLOR.textSecondary, textAlign: "center" }}>
                      Hồ sơ không có điểm đo.
                    </td>
                  </tr>
                ) : (
                  (record.measurements ?? []).map((point) => {
                    const limitTone = withinLimitTone(point.within_limit);
                    const errorUnit = point.error_unit_code ?? point.unit_code;
                    return (
                      <tr key={point.id}>
                        <td style={{ ...measureTd, whiteSpace: "nowrap" }}>{measurementLabel(point)}</td>
                        <td style={measureTd}>
                          <ProvButton label={formatNumber(point.nominal_value)} cellRef={measurementRef(point, "nominal")} onOpen={onOpenProvenance} />
                        </td>
                        <td style={measureTd}>
                          <ProvButton label={formatNumber(point.measured_value)} cellRef={measurementRef(point, "measured")} onOpen={onOpenProvenance} />
                        </td>
                        <td style={measureTd}>
                          <ProvButton label={valueWithUnit(point.error_value, errorUnit)} cellRef={measurementRef(point, "error")} onOpen={onOpenProvenance} />
                        </td>
                        <td style={measureTd}>
                          <ProvButton label={valueWithUnit(point.limit_value, errorUnit)} cellRef={measurementRef(point, "limit")} onOpen={onOpenProvenance} />
                        </td>
                        <td style={measureTd}>
                          <span style={{ ...limitBadge, color: limitTone.fg, background: limitTone.bg }}>{limitTone.label}</span>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </Section>

        <Section title="Nguồn">
          <InfoRow label="Phòng đo">{record.lab_name ?? "—"}</InfoRow>
          <InfoRow label="Mục nguồn">{record.extraction_section_path ?? "—"}</InfoRow>
          <InfoRow label="Chunk nguồn">{record.extraction_chunk_id ?? "—"}</InfoRow>
        </Section>

        <button type="button" onClick={() => onOpenDevice(record)} style={{ ...ghostButton, alignSelf: "flex-start" }}>
          <IcClock size={14} style={{ color: COLOR.accent }} /> Xem lịch sử thiết bị <IcArrowRight size={13} />
        </button>
      </div>
    </aside>
  );
}

const panelStyle: React.CSSProperties = {
  width: PANEL_WIDTH,
  flexShrink: 0,
  borderLeft: `1px solid ${COLOR.border}`,
  background: COLOR.surface,
  display: "flex",
  flexDirection: "column",
  minHeight: 0,
};
const headerStyle: React.CSSProperties = { display: "flex", alignItems: "flex-start", gap: 8, padding: "13px 16px", borderBottom: `1px solid ${COLOR.border}` };
const bodyStyle: React.CSSProperties = {
  flex: 1,
  minHeight: 0,
  overflowY: "auto",
  padding: "14px 16px 18px",
  display: "flex",
  flexDirection: "column",
  gap: 16,
};
const sectionTitle: React.CSSProperties = {
  margin: "0 0 4px",
  fontSize: "11px",
  fontWeight: 700,
  letterSpacing: ".04em",
  textTransform: "uppercase",
  color: COLOR.textMuted,
};
const infoRow: React.CSSProperties = { display: "grid", gridTemplateColumns: "120px 1fr", gap: 8, padding: "4px 0", alignItems: "baseline" };
const infoLabel: React.CSSProperties = { fontSize: "12px", fontWeight: 700, color: COLOR.textSecondary };
const infoValue: React.CSSProperties = { fontSize: "12.5px", color: COLOR.textPrimary, wordBreak: "break-word" };
const mono: React.CSSProperties = { fontVariantNumeric: "tabular-nums" };
const verdictBadge: React.CSSProperties = { fontSize: "11px", fontWeight: 700, padding: "2px 8px", borderRadius: 9999, whiteSpace: "nowrap" };
const statusBadge: React.CSSProperties = { fontSize: "10.5px", fontWeight: 700, padding: "1px 7px", borderRadius: 9999, whiteSpace: "nowrap" };
const limitBadge: React.CSSProperties = { fontSize: "10.5px", fontWeight: 700, padding: "2px 7px", borderRadius: 9999, whiteSpace: "nowrap" };
const iconButton: React.CSSProperties = {
  width: 28,
  height: 28,
  flexShrink: 0,
  borderRadius: 8,
  border: `1px solid ${COLOR.border}`,
  background: COLOR.surface,
  color: COLOR.textSecondary,
  cursor: "pointer",
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
};
const ghostButton: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: 6,
  height: 34,
  padding: "0 13px",
  borderRadius: 9,
  border: `1px solid ${COLOR.accentSoftBorder}`,
  background: COLOR.surface,
  color: COLOR.accentDark,
  fontWeight: 700,
  fontSize: "12.5px",
  cursor: "pointer",
};
const measureTh: React.CSSProperties = { ...thStyle, padding: "5px 8px" };
const measureTd: React.CSSProperties = { ...tdStyle, height: "auto", padding: "5px 8px" };
