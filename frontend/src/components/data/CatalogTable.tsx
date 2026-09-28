import type { CatalogGroup, CatalogKind, CatalogRow } from "../../types";
import { COLOR } from "../../theme";
import { IcAlert, IcLink } from "../common/icons";
import {
  CATALOG_TABLE_TITLES,
  formatCatalogDate,
  formatNextDue,
  isInherited,
  isOverdue,
  joinList,
  recognitionLabel,
} from "./catalogFormat";

// Bảng danh mục NAS (Pha D1). Thuần trình bày để test bằng renderToStaticMarkup:
// nhận rows + bộ lọc, phát callback; mỗi dòng có nút mở nguồn nguyên văn (P1).
//
// Chuẩn mẫu hiện "Hạn KĐ/HC kế tiếp (ước tính)" và nhãn "Quá hạn" khi hạn trước
// tháng hiện tại; trường kế thừa từ "nt" có dấu nhỏ với tooltip "như trên".

export interface CatalogTableProps {
  kind: CatalogKind;
  rows: CatalogRow[];
  groups: CatalogGroup[];
  q: string;
  group: string;
  loading: boolean;
  error?: string | null;
  onSearch: (value: string) => void;
  onGroup: (value: string) => void;
  onOpenSource: (row: CatalogRow) => void;
}

const HEADERS: Record<CatalogKind, string[]> = {
  lab_standard: [
    "TT",
    "Tên chuẩn mẫu",
    "Ký hiệu",
    "Số hiệu",
    "Đặc tính đo lường",
    "Chu kỳ KĐ/HC",
    "KĐ/HC gần nhất",
    "Hạn KĐ/HC kế tiếp (ước tính)",
    "Lĩnh vực sử dụng",
    "Nguồn",
  ],
  inspector: [
    "TT",
    "Họ và tên",
    "Năm sinh",
    "Cấp bậc",
    "Chức vụ",
    "Trình độ",
    "Chuyên ngành",
    "Lĩnh vực được chứng nhận",
    "Số thẻ",
    "Ngày cấp",
    "Nguồn",
  ],
  procedure_catalog: [
    "TT",
    "Nhóm",
    "Số hiệu",
    "Tên tiêu chuẩn, quy trình",
    "Cấp ban hành",
    "Năm",
    "QTKĐ trong kho",
    "Nguồn",
  ],
  capability: [
    "TT",
    "Nhóm",
    "Tên đại lượng, trang bị",
    "Tham số đo lường",
    "Quy trình áp dụng",
    "Số KĐV",
    "Công nhận",
    "Nguồn",
  ],
};

const NEEDS_GROUP: Record<CatalogKind, boolean> = {
  lab_standard: false,
  inspector: false,
  procedure_catalog: true,
  capability: true,
};

function InheritedMark() {
  return (
    <sup title="như trên" aria-label="như trên" style={inheritedStyle}>
      nt
    </sup>
  );
}

function text(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  return String(value);
}

function SourceCell({ row, onOpenSource }: { row: CatalogRow; onOpenSource: (row: CatalogRow) => void }) {
  return (
    <td style={tdStyle}>
      <button
        type="button"
        className="prov-cell"
        title={`Xem nguồn: ${row.display_name ?? row.file_stem ?? ""}`}
        aria-label={`Xem nguồn dòng ${row.ord ?? row.id}`}
        onClick={() => onOpenSource(row)}
        style={sourceButton}
      >
        Nguồn
        <IcLink size={10} style={{ opacity: 0.7 }} />
      </button>
    </td>
  );
}

function NextDueCell({ row }: { row: CatalogRow }) {
  const overdue = isOverdue(row);
  return (
    <td style={tdStyle}>
      <span style={numericStyle}>{formatNextDue(row)}</span>
      {overdue && <span style={overdueBadge}>Quá hạn</span>}
    </td>
  );
}

function LabStandardCells({ row, onOpenSource }: { row: CatalogRow; onOpenSource: (row: CatalogRow) => void }) {
  return (
    <>
      <td style={tdStyle}>{text(row.ord)}</td>
      <td style={tdStyle}>{text(row.name)}</td>
      <td style={tdStyle}>{text(row.model)}</td>
      <td style={tdStyle}>{text(row.serial)}</td>
      <td style={{ ...tdStyle, maxWidth: 320, whiteSpace: "normal" }}>{text(row.characteristics)}</td>
      <td style={tdStyle}>
        {text(row.interval_text)}
        {isInherited(row, "interval") && <InheritedMark />}
      </td>
      <td style={tdStyle}>
        {text(row.last_cal_text)}
        {isInherited(row, "last_calibration") && <InheritedMark />}
      </td>
      <NextDueCell row={row} />
      <td style={tdStyle}>
        {text(row.usage_text)}
        {isInherited(row, "usage") && <InheritedMark />}
      </td>
      <SourceCell row={row} onOpenSource={onOpenSource} />
    </>
  );
}

function InspectorCells({ row, onOpenSource }: { row: CatalogRow; onOpenSource: (row: CatalogRow) => void }) {
  return (
    <>
      <td style={tdStyle}>{text(row.ord)}</td>
      <td style={tdStyle}>{text(row.name)}</td>
      <td style={tdStyle}>{text(row.birth_year)}</td>
      <td style={tdStyle}>{text(row.rank)}</td>
      <td style={tdStyle}>{text(row.position)}</td>
      <td style={tdStyle}>{text(row.education)}</td>
      <td style={tdStyle}>{text(row.specialization)}</td>
      <td style={{ ...tdStyle, maxWidth: 320, whiteSpace: "normal" }}>{joinList(row.fields)}</td>
      <td style={tdStyle}>{text(row.card_no)}</td>
      <td style={tdStyle}>{formatCatalogDate(row.card_date)}</td>
      <SourceCell row={row} onOpenSource={onOpenSource} />
    </>
  );
}

function ProcedureCells({ row, onOpenSource }: { row: CatalogRow; onOpenSource: (row: CatalogRow) => void }) {
  const link = row.procedure_link;
  return (
    <>
      <td style={tdStyle}>{text(row.ord)}</td>
      <td style={tdStyle}>{text(row.group_code)}</td>
      <td style={tdStyle}>{text(row.code_text)}</td>
      <td style={{ ...tdStyle, maxWidth: 360, whiteSpace: "normal" }}>{text(row.title)}</td>
      <td style={tdStyle}>
        {text(row.issuer)}
        {isInherited(row, "issuer") && <InheritedMark />}
      </td>
      <td style={tdStyle}>{text(row.year_issued)}</td>
      <td style={tdStyle}>
        {link ? (
          <span title={`Đã có QTKĐ ${link.number} trong kho`} style={linkBadge}>
            {link.number}
          </span>
        ) : (
          <span style={numericStyle}>—</span>
        )}
      </td>
      <SourceCell row={row} onOpenSource={onOpenSource} />
    </>
  );
}

function CapabilityCells({ row, onOpenSource }: { row: CatalogRow; onOpenSource: (row: CatalogRow) => void }) {
  const procedures = (row.procedure_codes ?? []).map((code) => code.normalized).join("; ");
  return (
    <>
      <td style={tdStyle}>{text(row.ord)}</td>
      <td style={tdStyle}>{text(row.group_code)}</td>
      <td style={tdStyle}>{text(row.name)}</td>
      <td style={{ ...tdStyle, maxWidth: 360, whiteSpace: "normal" }}>{joinList(row.parameters)}</td>
      <td style={{ ...tdStyle, maxWidth: 300, whiteSpace: "normal" }}>{procedures || "—"}</td>
      <td style={tdStyle}>{text(row.inspector_count)}</td>
      <td style={tdStyle}>{recognitionLabel(row.recognition)}</td>
      <SourceCell row={row} onOpenSource={onOpenSource} />
    </>
  );
}

function RowCells({ kind, row, onOpenSource }: { kind: CatalogKind; row: CatalogRow; onOpenSource: (row: CatalogRow) => void }) {
  if (kind === "lab_standard") return <LabStandardCells row={row} onOpenSource={onOpenSource} />;
  if (kind === "inspector") return <InspectorCells row={row} onOpenSource={onOpenSource} />;
  if (kind === "procedure_catalog") return <ProcedureCells row={row} onOpenSource={onOpenSource} />;
  return <CapabilityCells row={row} onOpenSource={onOpenSource} />;
}

export default function CatalogTable(props: CatalogTableProps) {
  const { kind, rows, groups, q, group, loading, error, onSearch, onGroup, onOpenSource } = props;
  const headers = HEADERS[kind];
  const showGroup = NEEDS_GROUP[kind] && groups.length > 0;

  return (
    <div style={{ display: "flex", flexDirection: "column", minHeight: 0, flex: 1 }}>
      <div style={toolbarStyle}>
        <input
          type="search"
          value={q}
          onChange={(event) => onSearch(event.target.value)}
          placeholder="Tìm không dấu theo tên, ký hiệu, số hiệu, mã…"
          aria-label="Tìm trong danh mục"
          style={searchInput}
        />
        {showGroup && (
          <select
            value={group}
            onChange={(event) => onGroup(event.target.value)}
            aria-label="Lọc theo nhóm lĩnh vực"
            style={groupSelect}
          >
            <option value="">Mọi nhóm lĩnh vực</option>
            {groups.map((item) => (
              <option key={item.code} value={item.code}>
                {item.code} - {item.title ?? ""}
              </option>
            ))}
          </select>
        )}
        <div style={{ flex: 1 }} />
        <span style={captionStyle}>{CATALOG_TABLE_TITLES[kind]} — chỉ hiện bản đã duyệt</span>
      </div>

      {error && (
        <div role="alert" style={alertStyle}>
          <IcAlert size={14} /> {error}
        </div>
      )}

      <div style={{ flex: 1, minHeight: 0, overflow: "auto" }}>
        <table role="table" style={{ width: "100%", borderCollapse: "collapse", fontSize: "12.5px" }}>
          <caption style={visuallyHidden}>
            {CATALOG_TABLE_TITLES[kind]}. Hạn KĐ/HC kế tiếp là giá trị ước tính từ chu kỳ và lần
            KĐ/HC gần nhất. Mỗi dòng có nút mở nguồn nguyên văn.
          </caption>
          <thead style={{ position: "sticky", top: 0, zIndex: 2, background: COLOR.surfaceAlt }}>
            <tr>
              {headers.map((label) => (
                <th key={label} scope="col" style={thStyle}>
                  {label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading && rows.length === 0 ? (
              <tr>
                <td colSpan={headers.length} style={emptyTd}>
                  Đang tải danh mục…
                </td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={headers.length} style={emptyTd}>
                  Không có dòng đã duyệt khớp bộ lọc.
                </td>
              </tr>
            ) : (
              rows.map((row) => (
                <tr key={row.id}>
                  <RowCells kind={kind} row={row} onOpenSource={onOpenSource} />
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

const toolbarStyle: React.CSSProperties = {
  flexShrink: 0,
  display: "flex",
  alignItems: "center",
  gap: 10,
  flexWrap: "wrap",
  padding: "9px 16px",
  borderBottom: `1px solid ${COLOR.border}`,
  background: COLOR.surface,
};
const searchInput: React.CSSProperties = {
  width: 300,
  maxWidth: "100%",
  height: 32,
  padding: "0 10px",
  borderRadius: 8,
  border: `1px solid ${COLOR.border}`,
  background: COLOR.surface,
  color: COLOR.textPrimary,
  fontSize: "12.5px",
  fontFamily: "inherit",
};
const groupSelect: React.CSSProperties = {
  height: 32,
  padding: "0 10px",
  borderRadius: 8,
  border: `1px solid ${COLOR.border}`,
  background: COLOR.surface,
  color: COLOR.textSecondary,
  fontSize: "12.5px",
  fontFamily: "inherit",
};
const thStyle: React.CSSProperties = {
  textAlign: "left",
  padding: "7px 9px",
  borderBottom: `1px solid ${COLOR.border}`,
  color: COLOR.textSecondary,
  fontWeight: 700,
  whiteSpace: "nowrap",
};
const tdStyle: React.CSSProperties = {
  padding: "7px 9px",
  borderBottom: `1px solid ${COLOR.surfaceAlt}`,
  color: COLOR.textPrimary,
  whiteSpace: "nowrap",
};
const numericStyle: React.CSSProperties = { fontVariantNumeric: "tabular-nums", color: COLOR.textPrimary };
const inheritedStyle: React.CSSProperties = { marginLeft: 3, fontSize: "9.5px", fontWeight: 700, color: COLOR.accentDark, cursor: "help" };
const overdueBadge: React.CSSProperties = {
  marginLeft: 6,
  fontSize: "10px",
  fontWeight: 700,
  background: COLOR.dangerBg,
  color: COLOR.danger,
  border: `1px solid ${COLOR.dangerBorder}`,
  padding: "1px 6px",
  borderRadius: 9999,
};
const linkBadge: React.CSSProperties = {
  fontSize: "11px",
  fontWeight: 700,
  background: COLOR.successBg,
  color: COLOR.success,
  border: `1px solid ${COLOR.successBorder}`,
  padding: "1px 7px",
  borderRadius: 9999,
};
const sourceButton: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: 4,
  border: `1px solid ${COLOR.accentSoftBorder}`,
  background: COLOR.accentSoft,
  color: COLOR.accentDark,
  borderRadius: 7,
  padding: "1px 7px",
  fontSize: "11.5px",
  fontWeight: 700,
  cursor: "pointer",
};
const captionStyle: React.CSSProperties = { fontSize: "11.5px", color: COLOR.textMuted };
const alertStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 8,
  padding: "8px 14px",
  background: COLOR.dangerBg,
  color: COLOR.danger,
  borderBottom: `1px solid ${COLOR.dangerBorder}`,
  fontSize: "12.5px",
  fontWeight: 600,
};
const emptyTd: React.CSSProperties = { padding: "30px 12px", textAlign: "center", color: COLOR.textSecondary, fontSize: "13px" };
const visuallyHidden: React.CSSProperties = {
  position: "absolute",
  width: 1,
  height: 1,
  padding: 0,
  margin: -1,
  overflow: "hidden",
  clip: "rect(0 0 0 0)",
  whiteSpace: "nowrap",
  border: 0,
};
