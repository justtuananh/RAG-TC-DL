import type { DataCellRef, DataRecordRow } from "../../types";
import { COLOR } from "../../theme";
import { IcAlert, IcChevronDown, IcChevronUp, IcSearch } from "../common/icons";
import RecordRow from "./RecordRow";
import { DATA_TABLE_CLASS, alertStyle, emptyCellStyle, headRowStyle, tableStyle, tdStyle, thStyle, visuallyHidden } from "./tableStyles";

// Bảng hồ sơ kiểm định: 8 cột đọc nhanh "thiết bị nào, kiểm khi nào, còn hạn không, đạt hay không".
// Bộ lọc đã tách sang RecordFilterBar. Mỗi ô số vẫn là nút mở đúng đoạn nguyên văn (P1).
//
// Dùng table-layout: fixed để không cuộn ngang ở 1366 px; cột "Thiết bị" tự rút gọn ellipsis.

export interface RecordsTableProps {
  rows: DataRecordRow[];
  sort: string;
  order: "asc" | "desc";
  loading: boolean;
  error?: string | null;
  selectedId: number | null;
  onSort: (column: string) => void;
  onOpenRecord: (row: DataRecordRow) => void;
  onOpenDevice: (row: DataRecordRow) => void;
  onOpenProvenance: (ref: DataCellRef) => void;
  /** Xoá mọi bộ lọc (dùng ở trạng thái rỗng). */
  onReset: () => void;
}

const SORT_LABEL: Record<string, string> = {
  calibrated_at: "Ngày kiểm định",
  serial_no: "Số hiệu",
  verdict: "Kết luận",
  expires_at: "Hiệu lực",
  device_type_name: "Loại thiết bị",
};

const COLUMNS: { label: string; sort?: string; align?: "right"; hidden?: boolean }[] = [
  { label: "Số hiệu", sort: "serial_no" },
  { label: "Thiết bị", sort: "device_type_name" },
  { label: "Ngày kiểm định", sort: "calibrated_at" },
  { label: "Hiệu lực", sort: "expires_at" },
  { label: "Phạm vi đo", align: "right" },
  { label: "CCX", align: "right" },
  { label: "Kết luận", sort: "verdict" },
  // Cột nút mũi tên: tiêu đề chỉ cho trình đọc màn hình, không chiếm chỗ hiển thị.
  { label: "Chi tiết", hidden: true },
];

const COL_WIDTHS = ["14%", "21%", "13%", "14%", "15%", "9%", "14%", "44px"];

function SortHeader({
  label,
  hidden,
  column,
  sort,
  order,
  onSort,
}: {
  label: string;
  hidden?: boolean;
  column?: string;
  sort: string;
  order: "asc" | "desc";
  onSort: (column: string) => void;
}) {
  const active = column !== undefined && sort === column;
  const ariaSort = active ? (order === "asc" ? "ascending" : "descending") : "none";
  return (
    <th scope="col" aria-sort={ariaSort} style={headerCellStyle}>
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
      ) : hidden ? (
        <span style={visuallyHidden}>{label}</span>
      ) : (
        label
      )}
    </th>
  );
}

function SkeletonRow() {
  return (
    <tr aria-hidden>
      {COL_WIDTHS.map((_width, i) => (
        <td key={i} style={tdStyle}>
          <span style={{ display: "block", height: 10, borderRadius: 9999, background: COLOR.surfaceMuted, width: i === 1 ? "80%" : "60%" }} />
        </td>
      ))}
    </tr>
  );
}

export default function RecordsTable(props: RecordsTableProps) {
  const { rows, sort, order, loading, error, selectedId, onSort, onOpenRecord, onOpenDevice, onOpenProvenance, onReset } = props;
  const showSkeleton = loading && rows.length === 0;

  // Bàn phím: mũi tên lên/xuống chuyển dòng đang chọn khi tiêu điểm nằm trong bảng.
  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    if (rows.length === 0) return;
    e.preventDefault();
    const current = rows.findIndex((row) => row.id === selectedId);
    const next = current < 0 ? 0 : e.key === "ArrowDown" ? Math.min(rows.length - 1, current + 1) : Math.max(0, current - 1);
    onOpenRecord(rows[next]);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", minHeight: 0, flex: 1 }}>
      {error && (
        <div role="alert" style={alertStyle}>
          <IcAlert size={14} /> {error}
        </div>
      )}
      <div style={{ flex: 1, minHeight: 0, overflow: "auto" }} onKeyDown={onKeyDown}>
        <table role="table" className={DATA_TABLE_CLASS} style={{ ...tableStyle, tableLayout: "fixed" }}>
          <caption style={captionStyle}>Hồ sơ kiểm định đã duyệt. Bấm vào một con số để xem đoạn nguyên văn sinh ra nó.</caption>
          <colgroup>
            {COL_WIDTHS.map((width, i) => (
              <col key={i} style={{ width }} />
            ))}
          </colgroup>
          <thead style={headRowStyle}>
            <tr>
              {COLUMNS.map((col, i) => (
                <SortHeader key={i} label={col.label} hidden={col.hidden} column={col.sort} sort={sort} order={order} onSort={onSort} />
              ))}
            </tr>
          </thead>
          <tbody>
            {showSkeleton ? (
              Array.from({ length: 8 }, (_, i) => <SkeletonRow key={i} />)
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={COLUMNS.length} style={emptyCellStyle}>
                  <div style={emptyBoxStyle}>
                    <IcSearch size={22} style={{ color: COLOR.borderStrong }} />
                    <div style={{ fontWeight: 600, color: COLOR.textPrimary }}>Không có hồ sơ khớp bộ lọc</div>
                    <button type="button" onClick={onReset} style={resetButton}>
                      Xoá lọc
                    </button>
                  </div>
                </td>
              </tr>
            ) : (
              rows.map((row) => (
                <RecordRow
                  key={row.id}
                  row={row}
                  selected={row.id === selectedId}
                  onOpenRecord={onOpenRecord}
                  onOpenDevice={onOpenDevice}
                  onOpenProvenance={onOpenProvenance}
                />
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// Cột chia theo % (table-layout: fixed): khi panel chi tiết mở, tiêu đề dài phải xuống dòng
// thay vì tràn đè sang cột bên cạnh.
const headerCellStyle: React.CSSProperties = { ...thStyle, whiteSpace: "normal", lineHeight: 1.3, verticalAlign: "bottom" };
const sortButton: React.CSSProperties = {
  textAlign: "left",
  display: "inline-flex",
  alignItems: "center",
  gap: 4,
  border: "none",
  background: "transparent",
  padding: 0,
  color: "inherit",
  fontWeight: 700,
  fontSize: "12px",
  cursor: "pointer",
  fontFamily: "inherit",
};
const captionStyle: React.CSSProperties = { textAlign: "left", padding: "10px 12px 4px", color: COLOR.textMuted, fontSize: "12px" };
const emptyBoxStyle: React.CSSProperties = { display: "flex", flexDirection: "column", alignItems: "center", gap: 8 };
const resetButton: React.CSSProperties = {
  height: 30,
  padding: "0 12px",
  borderRadius: 8,
  border: `1px solid ${COLOR.border}`,
  background: COLOR.surface,
  color: COLOR.textSecondary,
  fontWeight: 600,
  fontSize: "12px",
  cursor: "pointer",
};
