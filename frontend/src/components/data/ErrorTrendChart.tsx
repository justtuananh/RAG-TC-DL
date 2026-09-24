import type { DataCellRef, TrendSeries } from "../../types";
import { COLOR } from "../../theme";
import { IcChart } from "../common/icons";
import { formatDate, formatNumber, withinLimitTone } from "./format";

// Biểu đồ diễn biến sai số theo mốc đo + bảng số liệu truy cập được bằng bàn phím.
// SVG chỉ mang tính thị giác (role="img"); dữ liệu và nút xuất xứ nằm trong bảng
// thật nên người dùng bàn phím/trình đọc màn hình vẫn mở được từng ô số (P1).

const WIDTH = 640;
const HEIGHT = 200;
const PAD_X = 36;
const PAD_Y = 22;

function pointRef(pointId: number): DataCellRef {
  return { field: "error", kind: "measurement", id: pointId };
}

function Chart({ series }: { series: TrendSeries }) {
  const values: number[] = [];
  for (const point of series.points) {
    if (point.error_value !== null && point.error_value !== undefined) values.push(point.error_value);
    if (point.limit_value !== null && point.limit_value !== undefined) {
      values.push(point.limit_value, -point.limit_value);
    }
  }
  if (values.length === 0) return <div style={{ fontSize: "12.5px", color: COLOR.textSecondary }}>Không có giá trị sai số.</div>;

  const maxAbs = Math.max(...values.map((value) => Math.abs(value)), 1e-9);
  const yMax = maxAbs * 1.15;
  const count = series.points.length;
  const stepX = count > 1 ? (WIDTH - 2 * PAD_X) / (count - 1) : 0;
  const yOf = (value: number) => HEIGHT - PAD_Y - ((value + yMax) / (2 * yMax)) * (HEIGHT - 2 * PAD_Y);
  const xOf = (index: number) => PAD_X + index * stepX;

  const coordinates = series.points
    .map((point, index) =>
      point.error_value === null || point.error_value === undefined
        ? null
        : `${xOf(index)},${yOf(point.error_value)}`,
    )
    .filter((value): value is string => value !== null)
    .join(" ");

  const firstLimit = series.points.find((point) => point.limit_value !== null && point.limit_value !== undefined)?.limit_value ?? null;
  const unit = series.unit_code ? ` ${series.unit_code}` : "";
  const description = `Diễn biến sai số mốc ${series.step_code ?? series.label ?? series.key}: ${series.points
    .map((point) => `${formatDate(point.calibrated_at)} ${formatNumber(point.error_value)}${unit}`)
    .join(", ")}.`;

  return (
    <svg
      role="img"
      aria-label={description}
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      width="100%"
      height={HEIGHT}
      style={{ display: "block" }}
    >
      <title>Diễn biến sai số theo mốc đo</title>
      <desc>{description}</desc>
      <line x1={PAD_X} y1={yOf(0)} x2={WIDTH - PAD_X} y2={yOf(0)} stroke={COLOR.borderStrong} strokeWidth={1} />
      {firstLimit !== null && (
        <>
          <line x1={PAD_X} y1={yOf(firstLimit)} x2={WIDTH - PAD_X} y2={yOf(firstLimit)} stroke={COLOR.dangerBorder} strokeDasharray="5 4" strokeWidth={1.4} />
          <line x1={PAD_X} y1={yOf(-firstLimit)} x2={WIDTH - PAD_X} y2={yOf(-firstLimit)} stroke={COLOR.dangerBorder} strokeDasharray="5 4" strokeWidth={1.4} />
        </>
      )}
      {coordinates && <polyline points={coordinates} fill="none" stroke={COLOR.accent} strokeWidth={2} />}
      {series.points.map((point, index) =>
        point.error_value === null || point.error_value === undefined ? null : (
          <circle
            key={point.point_id}
            cx={xOf(index)}
            cy={yOf(point.error_value)}
            r={4}
            fill={point.within_limit === false ? COLOR.danger : COLOR.accent}
            stroke={COLOR.surface}
            strokeWidth={1.5}
          />
        ),
      )}
    </svg>
  );
}

export default function ErrorTrendChart({
  series,
  onOpenProvenance,
}: {
  series: TrendSeries[];
  onOpenProvenance: (ref: DataCellRef) => void;
}) {
  if (series.length === 0) {
    return <div style={{ fontSize: "12.5px", color: COLOR.textSecondary }}>Chưa có điểm đo để dựng diễn biến sai số.</div>;
  }
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      {series.map((item) => (
        <section key={item.key} style={{ border: `1px solid ${COLOR.border}`, borderRadius: 12, padding: "12px 14px", background: COLOR.surface }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
            <IcChart size={15} style={{ color: COLOR.accent }} />
            <span style={{ fontWeight: 700, fontSize: "13px", color: COLOR.textPrimary }}>
              Mốc {item.step_code ?? item.label ?? item.key}
            </span>
            {item.unit_code && <span style={{ fontSize: "11.5px", color: COLOR.textMuted }}>đơn vị {item.unit_code}</span>}
          </div>
          <Chart series={item} />
          <details style={{ marginTop: 8 }}>
            <summary style={{ cursor: "pointer", fontSize: "12.5px", fontWeight: 600, color: COLOR.accentDark }}>
              Bảng số liệu ({item.points.length} điểm)
            </summary>
            <table style={{ width: "100%", borderCollapse: "collapse", marginTop: 8, fontSize: "12px" }}>
              <caption style={{ textAlign: "left", color: COLOR.textSecondary, paddingBottom: 4 }}>
                Số liệu diễn biến sai số mốc {item.step_code ?? item.label ?? item.key}
              </caption>
              <thead>
                <tr>
                  {["Ngày", "Sai số", "Giới hạn", "Đối chiếu", "Nguồn"].map((heading) => (
                    <th key={heading} scope="col" style={thStyle}>
                      {heading}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {item.points.map((point) => {
                  const tone = withinLimitTone(point.within_limit);
                  return (
                    <tr key={point.point_id}>
                      <td style={tdStyle}>{formatDate(point.calibrated_at)}</td>
                      <td style={{ ...tdStyle, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                        {formatNumber(point.error_value)}
                        {point.unit_code ? ` ${point.unit_code}` : ""}
                      </td>
                      <td style={{ ...tdStyle, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                        {formatNumber(point.limit_value)}
                      </td>
                      <td style={tdStyle}>
                        <span style={{ fontSize: "11px", fontWeight: 700, color: tone.fg, background: tone.bg, padding: "2px 8px", borderRadius: 9999 }}>
                          {tone.label}
                        </span>
                      </td>
                      <td style={tdStyle}>
                        <button
                          type="button"
                          onClick={() => onOpenProvenance(pointRef(point.point_id))}
                          aria-label={`Mở nguồn sai số ${formatNumber(point.error_value)} ngày ${formatDate(point.calibrated_at)}`}
                          style={provButton}
                        >
                          Nguồn
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </details>
        </section>
      ))}
    </div>
  );
}

const thStyle: React.CSSProperties = { textAlign: "left", color: COLOR.textSecondary, borderBottom: `1px solid ${COLOR.border}`, padding: "5px 8px", fontWeight: 700 };
const tdStyle: React.CSSProperties = { padding: "5px 8px", borderBottom: `1px solid ${COLOR.surfaceAlt}`, color: COLOR.textPrimary };
const provButton: React.CSSProperties = {
  border: `1px solid ${COLOR.accentSoftBorder}`,
  background: COLOR.accentSoft,
  color: COLOR.accentDark,
  borderRadius: 7,
  padding: "2px 9px",
  fontSize: "11.5px",
  fontWeight: 700,
  cursor: "pointer",
};
