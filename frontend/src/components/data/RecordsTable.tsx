import type { DataCellRef, DataRecordRow, FilterOptions } from "../../types";
import type { RecordFilters } from "../../services/dataApi";
import { COLOR } from "../../theme";
import { IcAlert, IcChevronDown, IcChevronUp, IcLink } from "../common/icons";
import { formatDate, formatNumber, formatRange, verdictTone } from "./format";

// Bảng dày cho tab Dữ liệu. Thuần trình bày (nhận rows + callback) để test được
// bằng renderToStaticMarkup: kiểm vai trò, aria, nút xuất xứ và điều hướng bàn phím.
//
// Mỗi ô số là một <button> mở đúng đoạn nguyên văn sinh ra nó (P1). Bảng dùng
// <caption>, <th scope>, aria-sort và aria-label cho mọi điều khiển.

export interface RecordsTableProps {
  rows: DataRecordRow[];
  options: FilterOptions | null;
  filters: RecordFilters;
  sort: string;
  order: "asc" | "desc";
  loading: boolean;
  error?: string | null;
  selectedId: number | null;
  onFilterChange: (patch: Partial<RecordFilters>) => void;
  onSort: (column: string) => void;
  onOpenRecord: (row: DataRecordRow) => void;
  onOpenDevice: (row: DataRecordRow) => void;
  onOpenProvenance: (ref: DataCellRef) => void;
}

function cellRefFor(row: DataRecordRow, field: string): DataCellRef | null {
  return row.provenance.find((cell) => cell.field === field) ?? null;
}

const SORT_LABEL: Record<string, string> = {
  calibrated_at: "Ngày kiểm định",
  serial_no: "Số hiệu",
  verdict: "Kết luận",
  procedure_number: "QTKĐ",
  device_type_name: "Loại thiết bị",
};

function SortHeader({
  label,
  column,
  sort,
  order,
  onSort,
}: {
  label: string;
  column?: string;
  sort: string;
  order: "asc" | "desc";
  onSort: (column: string) => void;
}) {
  const active = column !== undefined && sort === column;
  const ariaSort = active ? (order === "asc" ? "ascending" : "descending") : "none";
  return (
    <th scope="col" aria-sort={ariaSort} style={thStyle}>
      {column ? (
        <button
          type="button"
          onClick={() => onSort(column)}
          aria-label={`Sắp xếp theo ${SORT_LABEL[column] ?? label}${active ? (order === "asc" ? ", giảm dần" : ", tăng dần") : ""}`}
          style={sortButton}
        >
          {label}
          {active && (order === "asc" ? <IcChevronUp size={11} /> : <IcChevronDown size={11} />)}
        </button>
      ) : (
        label
      )}
    </th>
  );
}

function ProvCell({
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
      onClick={() => onOpenProvenance(ref)}
      style={provButton}
    >
      {text}
      <IcLink size={10} style={{ opacity: 0.7 }} />
    </button>
  );
}

export default function RecordsTable(props: RecordsTableProps) {
  const { rows, options, filters, sort, order, loading, error, selectedId, onFilterChange, onSort, onOpenRecord, onOpenDevice, onOpenProvenance } = props;
  const verdictChoices = options?.verdicts ?? [];

  return (
    <div style={{ display: "flex", flexDirection: "column", minHeight: 0, flex: 1 }}>
      {error && (
        <div role="alert" style={alertStyle}>
          <IcAlert size={14} /> {error}
        </div>
      )}
      <div style={{ flex: 1, minHeight: 0, overflow: "auto" }}>
        <table role="table" style={{ width: "100%", borderCollapse: "collapse", fontSize: "12.5px" }}>
          <caption style={captionStyle}>
            Bảng hồ sơ kiểm định đã duyệt — mỗi ô số bấm để mở đoạn nguyên văn nguồn.
          </caption>
          <thead style={{ position: "sticky", top: 0, zIndex: 2, background: COLOR.surfaceAlt }}>
            <tr>
              <SortHeader label="Số hiệu" column="serial_no" sort={sort} order={order} onSort={onSort} />
              <SortHeader label="Loại thiết bị" column="device_type_name" sort={sort} order={order} onSort={onSort} />
              <th scope="col" style={thStyle}>Đại lượng</th>
              <SortHeader label="QTKĐ" column="procedure_number" sort={sort} order={order} onSort={onSort} />
              <SortHeader label="Ngày kiểm định" column="calibrated_at" sort={sort} order={order} onSort={onSort} />
              <SortHeader label="Hết hiệu lực" column="expires_at" sort={sort} order={order} onSort={onSort} />
              <th scope="col" style={thStyle}>Phạm vi đo</th>
              <th scope="col" style={thStyle}>Cấp chính xác</th>
              <th scope="col" style={thStyle}>Nhiệt độ</th>
              <th scope="col" style={thStyle}>Độ ẩm</th>
              <th scope="col" style={thStyle}>Số điểm đo</th>
              <SortHeader label="Kết luận" column="verdict" sort={sort} order={order} onSort={onSort} />
              <th scope="col" style={thStyle}>Chi tiết</th>
            </tr>
            <tr>
              <th scope="col" style={filterThStyle}>
                <input
                  type="search"
                  value={filters.search ?? ""}
                  onChange={(e) => onFilterChange({ search: e.target.value })}
                  placeholder="Tìm số hiệu…"
                  aria-label="Lọc theo số hiệu, model, QTKĐ"
                  style={filterInput}
                />
              </th>
              <th scope="col" style={filterThStyle}>
                <select
                  value={filters.device_type_id ?? ""}
                  onChange={(e) => onFilterChange({ device_type_id: e.target.value ? Number(e.target.value) : undefined })}
                  aria-label="Lọc theo loại thiết bị"
                  style={filterInput}
                >
                  <option value="">Mọi loại</option>
                  {(options?.device_types ?? []).map((choice) => (
                    <option key={choice.value} value={choice.value}>{choice.label}</option>
                  ))}
                </select>
              </th>
              <th scope="col" style={filterThStyle}>
                <select
                  value={filters.quantity_id ?? ""}
                  onChange={(e) => onFilterChange({ quantity_id: e.target.value ? Number(e.target.value) : undefined })}
                  aria-label="Lọc theo đại lượng"
                  style={filterInput}
                >
                  <option value="">Mọi đại lượng</option>
                  {(options?.quantities ?? []).map((choice) => (
                    <option key={choice.value} value={choice.value}>{choice.label}</option>
                  ))}
                </select>
              </th>
              <th scope="col" style={filterThStyle}>
                <select
                  value={filters.procedure_id ?? ""}
                  onChange={(e) => onFilterChange({ procedure_id: e.target.value ? Number(e.target.value) : undefined })}
                  aria-label="Lọc theo QTKĐ"
                  style={filterInput}
                >
                  <option value="">Mọi QTKĐ</option>
                  {(options?.procedures ?? []).map((choice) => (
                    <option key={choice.value} value={choice.value}>{choice.label}</option>
                  ))}
                </select>
              </th>
              <th scope="col" style={filterThStyle}>
                <div style={{ display: "flex", gap: 3 }}>
                  <input
                    type="date"
                    value={filters.date_from ?? ""}
                    onChange={(e) => onFilterChange({ date_from: e.target.value || undefined })}
                    aria-label="Lọc từ ngày kiểm định"
                    style={filterInput}
                  />
                  <input
                    type="date"
                    value={filters.date_to ?? ""}
                    onChange={(e) => onFilterChange({ date_to: e.target.value || undefined })}
                    aria-label="Lọc đến ngày kiểm định"
                    style={filterInput}
                  />
                </div>
              </th>
              <th scope="col" style={filterThStyle} />
              <th scope="col" style={filterThStyle}>
                <div style={{ display: "flex", gap: 3 }}>
                  <input
                    type="number"
                    value={filters.range_min ?? ""}
                    onChange={(e) => onFilterChange({ range_min: e.target.value === "" ? undefined : Number(e.target.value) })}
                    placeholder="Min"
                    aria-label="Phạm vi đo nhỏ nhất"
                    style={filterInput}
                  />
                  <input
                    type="number"
                    value={filters.range_max ?? ""}
                    onChange={(e) => onFilterChange({ range_max: e.target.value === "" ? undefined : Number(e.target.value) })}
                    placeholder="Max"
                    aria-label="Phạm vi đo lớn nhất"
                    style={filterInput}
                  />
                  <input
                    type="text"
                    value={filters.range_unit ?? ""}
                    onChange={(e) => onFilterChange({ range_unit: e.target.value || undefined })}
                    placeholder="ĐV"
                    aria-label="Đơn vị phạm vi đo"
                    style={{ ...filterInput, minWidth: 44 }}
                  />
                </div>
              </th>
              <th scope="col" style={filterThStyle}>
                <input
                  type="text"
                  value={filters.accuracy ?? ""}
                  onChange={(e) => onFilterChange({ accuracy: e.target.value || undefined })}
                  placeholder="Cấp chính xác…"
                  aria-label="Lọc theo cấp chính xác"
                  style={filterInput}
                />
              </th>
              <th scope="col" style={filterThStyle} />
              <th scope="col" style={filterThStyle} />
              <th scope="col" style={filterThStyle} />
              <th scope="col" style={filterThStyle}>
                <select
                  value={filters.verdict ?? ""}
                  onChange={(e) => onFilterChange({ verdict: e.target.value || undefined })}
                  aria-label="Lọc theo kết luận"
                  style={filterInput}
                >
                  <option value="">Mọi kết luận</option>
                  {verdictChoices.map((choice) => (
                    <option key={choice.value} value={choice.value}>{choice.label}</option>
                  ))}
                </select>
              </th>
              <th scope="col" style={filterThStyle} />
            </tr>
          </thead>
          <tbody>
            {loading && rows.length === 0 ? (
              <tr>
                <td colSpan={13} style={emptyTd}>Đang tải dữ liệu…</td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={13} style={emptyTd}>Không có hồ sơ đã duyệt khớp bộ lọc.</td>
              </tr>
            ) : (
              rows.map((row) => {
                const active = row.id === selectedId;
                const tone = verdictTone(row.verdict, row.verdict_label);
                return (
                  <tr
                    key={row.id}
                    aria-selected={active}
                    onClick={() => onOpenRecord(row)}
                    style={{ background: active ? COLOR.accentSoft : "transparent", cursor: "pointer" }}
                  >
                    <td style={tdStyle}>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          onOpenDevice(row);
                        }}
                        aria-label={`Xem lịch sử thiết bị ${row.serial_no ?? "(không số hiệu)"}`}
                        style={deviceButton}
                      >
                        {row.serial_no ?? "(không số hiệu)"}
                      </button>
                    </td>
                    <td style={tdStyle}>{row.device_type_name ?? "—"}</td>
                    <td style={tdStyle}>{row.quantity_name ?? "—"}</td>
                    <td style={tdStyle}>{row.procedure_number ?? "—"}</td>
                    <td style={tdStyle}>
                      <ProvCell row={row} field="calibrated_at" text={formatDate(row.calibrated_at)} onOpenProvenance={onOpenProvenance} />
                    </td>
                    <td style={tdStyle}>
                      {row.expires_at ? (
                        <ProvCell row={row} field="expires_at" text={formatDate(row.expires_at)} onOpenProvenance={onOpenProvenance} />
                      ) : (
                        <span style={numericStyle}>—</span>
                      )}
                    </td>
                    <td style={tdStyle}>
                      <ProvCell
                        row={row}
                        field="range_min"
                        text={formatRange(row.range_min, row.range_max, row.range_unit_code)}
                        onOpenProvenance={onOpenProvenance}
                      />
                    </td>
                    <td style={tdStyle}>
                      {row.accuracy_text ? (
                        <ProvCell row={row} field="accuracy_text" text={row.accuracy_text} onOpenProvenance={onOpenProvenance} />
                      ) : (
                        <span style={numericStyle}>—</span>
                      )}
                    </td>
                    <td style={tdStyle}>
                      {row.env_temp_c !== null && row.env_temp_c !== undefined ? (
                        <ProvCell row={row} field="env_temp_c" text={formatNumber(row.env_temp_c, 1)} onOpenProvenance={onOpenProvenance} />
                      ) : (
                        <span style={numericStyle}>—</span>
                      )}
                    </td>
                    <td style={tdStyle}>
                      {row.env_humidity_pct !== null && row.env_humidity_pct !== undefined ? (
                        <ProvCell row={row} field="env_humidity_pct" text={formatNumber(row.env_humidity_pct, 1)} onOpenProvenance={onOpenProvenance} />
                      ) : (
                        <span style={numericStyle}>—</span>
                      )}
                    </td>
                    <td style={{ ...tdStyle, textAlign: "right" }}>
                      {row.measurement_count !== null && row.measurement_count !== undefined ? (
                        <ProvCell row={row} field="measurement_count" text={formatNumber(row.measurement_count, 0)} onOpenProvenance={onOpenProvenance} />
                      ) : (
                        <span style={numericStyle}>—</span>
                      )}
                    </td>
                    <td style={tdStyle}>
                      <span style={{ fontSize: "11px", fontWeight: 700, color: tone.fg, background: tone.bg, padding: "2px 8px", borderRadius: 9999 }}>
                        {tone.label}
                      </span>
                    </td>
                    <td style={tdStyle}>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          onOpenRecord(row);
                        }}
                        aria-label={`Xem chi tiết hồ sơ ${row.serial_no ?? row.id}`}
                        style={detailButton}
                      >
                        Xem
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

const thStyle: React.CSSProperties = { textAlign: "left", padding: "7px 9px", borderBottom: `1px solid ${COLOR.border}`, color: COLOR.textSecondary, fontWeight: 700, whiteSpace: "nowrap" };
const filterThStyle: React.CSSProperties = { padding: "4px 6px", borderBottom: `1px solid ${COLOR.border}`, background: COLOR.surfaceAlt, verticalAlign: "top" };
const filterInput: React.CSSProperties = { width: "100%", minWidth: 60, height: 26, padding: "0 6px", borderRadius: 6, border: `1px solid ${COLOR.border}`, background: COLOR.surface, color: COLOR.textPrimary, fontSize: "11.5px", fontFamily: "inherit" };
const tdStyle: React.CSSProperties = { padding: "7px 9px", borderBottom: `1px solid ${COLOR.surfaceAlt}`, color: COLOR.textPrimary, whiteSpace: "nowrap" };
const numericStyle: React.CSSProperties = { fontVariantNumeric: "tabular-nums", color: COLOR.textPrimary };
const provButton: React.CSSProperties = { display: "inline-flex", alignItems: "center", gap: 4, border: `1px solid ${COLOR.accentSoftBorder}`, background: COLOR.accentSoft, color: COLOR.accentDark, borderRadius: 7, padding: "1px 7px", fontSize: "11.5px", fontWeight: 700, cursor: "pointer", fontVariantNumeric: "tabular-nums" };
const deviceButton: React.CSSProperties = { border: "none", background: "transparent", padding: 0, color: COLOR.accentDark, fontWeight: 700, fontSize: "12.5px", cursor: "pointer", textDecoration: "underline dotted" };
const detailButton: React.CSSProperties = { height: 24, padding: "0 9px", borderRadius: 7, border: `1px solid ${COLOR.border}`, background: COLOR.surface, color: COLOR.textSecondary, fontSize: "11.5px", fontWeight: 700, cursor: "pointer" };
const sortButton: React.CSSProperties = { display: "inline-flex", alignItems: "center", gap: 4, border: "none", background: "transparent", padding: 0, color: "inherit", fontWeight: 700, fontSize: "12.5px", cursor: "pointer", fontFamily: "inherit" };
const captionStyle: React.CSSProperties = { textAlign: "left", padding: "6px 9px", color: COLOR.textSecondary, fontSize: "11.5px" };
const alertStyle: React.CSSProperties = { display: "flex", alignItems: "center", gap: 8, padding: "8px 14px", background: COLOR.dangerBg, color: COLOR.danger, borderBottom: `1px solid ${COLOR.dangerBorder}`, fontSize: "12.5px", fontWeight: 600 };
const emptyTd: React.CSSProperties = { padding: "30px 12px", textAlign: "center", color: COLOR.textSecondary, fontSize: "13px" };
