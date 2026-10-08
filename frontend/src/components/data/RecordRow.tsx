import type { DataCellRef, DataRecordRow } from "../../types";
import { COLOR } from "../../theme";
import { IcArrowRight, IcLink } from "../common/icons";
import { expiryStatus, formatDate, formatRange, verdictTone } from "./format";
import { cellStackStyle, numericStyle, sublineStyle, tdStyle } from "./tableStyles";

// Một dòng của bảng hồ sơ: số hiệu (mở lịch sử thiết bị), thiết bị, mốc thời gian,
// phạm vi đo, cấp chính xác, kết luận và nút mở chi tiết. Mỗi ô số là nút mở nguồn (P1).
// Tách khỏi RecordsTable để giữ file bảng dưới 400 dòng.

function cellRefFor(row: DataRecordRow, field: string): DataCellRef | null {
  return row.provenance.find((cell) => cell.field === field) ?? null;
}

export function ProvCell({
  row,
  field,
  text,
  onOpenProvenance,
}: {
  row: DataRecordRow;
  field: string;
  text: string;
  onOpenProvenance: (ref: DataCellRef) => void;
}) {
  const ref = cellRefFor(row, field);
  if (!ref) return <span style={numericStyle}>{text}</span>;
  return (
    <button
      type="button"
      className="prov-cell"
      data-prov-kind={ref.kind}
      data-prov-id={ref.id}
      data-prov-field={field}
      title="Xem đoạn nguyên văn sinh ra số này"
      aria-label={`Xem nguồn: ${text}`}
      onClick={(e) => {
        // Không để cú bấm lan lên dòng: mở xuất xứ không được mở luôn panel chi tiết.
        e.stopPropagation();
        onOpenProvenance(ref);
      }}
    >
      {text}
      <IcLink size={10} />
    </button>
  );
}

export default function RecordRow({
  row,
  selected,
  onOpenRecord,
  onOpenDevice,
  onOpenProvenance,
}: {
  row: DataRecordRow;
  selected: boolean;
  onOpenRecord: (row: DataRecordRow) => void;
  onOpenDevice: (row: DataRecordRow) => void;
  onOpenProvenance: (ref: DataCellRef) => void;
}) {
  const tone = verdictTone(row.verdict, row.verdict_label);
  const status = expiryStatus(row.expires_at);
  const rejected = row.verdict === "khong_dat";

  // Đánh dấu dòng đang chọn bằng vạch trái accent; dòng "Không đạt" (khi không chọn) bằng vạch đỏ.
  const marker = selected ? COLOR.accent : rejected ? COLOR.danger : null;

  return (
    <tr
      aria-selected={selected}
      onClick={() => onOpenRecord(row)}
      style={{
        cursor: "pointer",
        background: selected ? COLOR.accentSoft : undefined,
        boxShadow: marker ? `inset 3px 0 0 ${marker}` : undefined,
      }}
    >
      <td style={tdStyle}>
        <div style={cellStackStyle}>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onOpenDevice(row);
            }}
            aria-label={`Xem lịch sử thiết bị ${row.serial_no ?? "(không số hiệu)"}`}
            style={serialButton}
          >
            {row.serial_no ?? "(không số hiệu)"}
          </button>
          {row.model_code ? <span style={sublineStyle}>{row.model_code}</span> : null}
        </div>
      </td>

      <td style={tdStyle}>
        <div style={cellStackStyle}>
          <span title={row.device_type_name ?? undefined} style={ellipsisStrong}>
            {row.device_type_name ?? "—"}
          </span>
          <span style={sublineStyle}>
            {row.quantity_name ?? "—"}
            {row.procedure_number ? (
              <>
                {" · "}
                <span style={qtdkChip}>QTKĐ {row.procedure_number}</span>
              </>
            ) : null}
          </span>
        </div>
      </td>

      <td style={tdStyle}>
        <ProvCell row={row} field="calibrated_at" text={formatDate(row.calibrated_at)} onOpenProvenance={onOpenProvenance} />
      </td>

      <td style={tdStyle}>
        <div style={cellStackStyle}>
          {row.expires_at ? (
            <ProvCell row={row} field="expires_at" text={formatDate(row.expires_at)} onOpenProvenance={onOpenProvenance} />
          ) : (
            <span style={numericStyle}>—</span>
          )}
          <span style={{ ...statusBadge, color: status.fg, background: status.bg }}>{status.label}</span>
        </div>
      </td>

      <td style={{ ...tdStyle, textAlign: "right" }}>
        <ProvCell
          row={row}
          field="range_min"
          text={formatRange(row.range_min_display, row.range_max_display, row.range_unit_code)}
          onOpenProvenance={onOpenProvenance}
        />
      </td>

      <td style={{ ...tdStyle, textAlign: "right" }}>
        {row.accuracy_text ? (
          <ProvCell row={row} field="accuracy_text" text={row.accuracy_text} onOpenProvenance={onOpenProvenance} />
        ) : (
          <span style={numericStyle}>—</span>
        )}
      </td>

      <td style={tdStyle}>
        <span style={{ ...verdictBadge, color: tone.fg, background: tone.bg }}>{tone.label}</span>
      </td>

      <td style={{ ...tdStyle, textAlign: "right" }}>
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onOpenRecord(row);
          }}
          aria-label={`Xem chi tiết hồ sơ ${row.serial_no ?? row.id}`}
          title="Xem chi tiết hồ sơ"
          style={detailButton}
        >
          <IcArrowRight size={15} />
        </button>
      </td>
    </tr>
  );
}

const serialButton: React.CSSProperties = {
  border: "none",
  background: "transparent",
  padding: 0,
  textAlign: "left",
  color: COLOR.accentDark,
  fontWeight: 700,
  fontSize: "12.5px",
  cursor: "pointer",
  textDecoration: "underline dotted",
  whiteSpace: "nowrap",
  overflow: "hidden",
  textOverflow: "ellipsis",
};
const ellipsisStrong: React.CSSProperties = {
  fontWeight: 600,
  fontSize: "12.5px",
  whiteSpace: "nowrap",
  overflow: "hidden",
  textOverflow: "ellipsis",
};
const qtdkChip: React.CSSProperties = {
  display: "inline-block",
  background: COLOR.neutralBg,
  color: COLOR.textSecondary,
  border: `1px solid ${COLOR.neutralBorder}`,
  borderRadius: 9999,
  padding: "0 6px",
  fontSize: "10.5px",
  fontWeight: 700,
  verticalAlign: "baseline",
};
const verdictBadge: React.CSSProperties = { fontSize: "11px", fontWeight: 700, padding: "2px 8px", borderRadius: 9999, whiteSpace: "nowrap" };
const statusBadge: React.CSSProperties = { alignSelf: "flex-start", fontSize: "10.5px", fontWeight: 700, padding: "1px 7px", borderRadius: 9999, whiteSpace: "nowrap" };
const detailButton: React.CSSProperties = {
  width: 26,
  height: 26,
  borderRadius: 7,
  border: `1px solid ${COLOR.border}`,
  background: COLOR.surface,
  color: COLOR.textSecondary,
  cursor: "pointer",
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
};
