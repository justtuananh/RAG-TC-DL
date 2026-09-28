import { useCallback, useEffect, useRef, useState } from "react";
import type { CatalogGroup, CatalogKind, CatalogRow } from "../../types";
import { COLOR } from "../../theme";
import { IcRefresh, IcTable } from "../common/icons";
import { fetchCatalogRows } from "../../services/dataApi";
import { CATALOG_TAB_LABELS } from "./catalogFormat";
import CatalogTable from "./CatalogTable";
import CatalogSourceModal from "./CatalogSourceModal";

// Một bảng danh mục NAS: tự nạp trang, tìm không dấu, lọc nhóm, phân trang và mở
// nguồn nguyên văn. Chỉ đọc `/api/data/catalogs/*` (P3).

const PAGE_SIZE = 25;

export default function CatalogsView({ kind }: { kind: CatalogKind }) {
  const [rows, setRows] = useState<CatalogRow[]>([]);
  const [groups, setGroups] = useState<CatalogGroup[]>([]);
  const [total, setTotal] = useState(0);
  const [q, setQ] = useState("");
  const [group, setGroup] = useState("");
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sourceRow, setSourceRow] = useState<CatalogRow | null>(null);
  const requestSeq = useRef(0);

  // Đổi loại danh mục: trả bộ lọc và trang về mặc định.
  useEffect(() => {
    setQ("");
    setGroup("");
    setOffset(0);
  }, [kind]);

  const load = useCallback(async () => {
    const seq = ++requestSeq.current;
    setLoading(true);
    setError(null);
    try {
      const page = await fetchCatalogRows(kind, {
        q: q || undefined,
        group: group || undefined,
        limit: PAGE_SIZE,
        offset,
      });
      if (seq !== requestSeq.current) return;
      setRows(page.items);
      setTotal(page.total);
      setGroups(page.groups ?? []);
    } catch (e) {
      if (seq === requestSeq.current) setError(e instanceof Error ? e.message : "Không tải được danh mục.");
    } finally {
      if (seq === requestSeq.current) setLoading(false);
    }
  }, [kind, q, group, offset]);

  useEffect(() => {
    const timer = setTimeout(() => void load(), 220);
    return () => clearTimeout(timer);
  }, [load]);

  const pageStart = total === 0 ? 0 : offset + 1;
  const pageEnd = Math.min(offset + PAGE_SIZE, total);

  return (
    <div style={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "column", background: COLOR.bg }}>
      <div style={barStyle}>
        <span style={{ display: "inline-flex", alignItems: "center", gap: 7, fontWeight: 700, fontSize: "14px", color: COLOR.textPrimary }}>
          <IcTable size={15} style={{ color: COLOR.accent }} /> {CATALOG_TAB_LABELS[kind]}
        </span>
        <span className="tabular-nums" style={countBadge}>
          {total} dòng đã duyệt
        </span>
        <div style={{ flex: 1 }} />
        <button type="button" onClick={() => void load()} disabled={loading} style={ghostButton}>
          <IcRefresh size={14} /> Tải lại
        </button>
      </div>

      <CatalogTable
        kind={kind}
        rows={rows}
        groups={groups}
        q={q}
        group={group}
        loading={loading}
        error={error}
        onSearch={(value) => {
          setQ(value);
          setOffset(0);
        }}
        onGroup={(value) => {
          setGroup(value);
          setOffset(0);
        }}
        onOpenSource={setSourceRow}
      />

      <nav aria-label="Phân trang danh mục" style={pagerStyle}>
        <span style={{ fontSize: "12px", color: COLOR.textSecondary }} className="tabular-nums">
          {pageStart}–{pageEnd} / {total}
        </span>
        <div style={{ display: "flex", gap: 8 }}>
          <button type="button" onClick={() => setOffset((value) => Math.max(0, value - PAGE_SIZE))} disabled={offset === 0 || loading} style={ghostButton}>
            Trang trước
          </button>
          <button type="button" onClick={() => setOffset((value) => value + PAGE_SIZE)} disabled={pageEnd >= total || loading} style={ghostButton}>
            Trang sau
          </button>
        </div>
      </nav>

      <CatalogSourceModal row={sourceRow} onClose={() => setSourceRow(null)} />
    </div>
  );
}

const barStyle: React.CSSProperties = {
  flexShrink: 0,
  display: "flex",
  alignItems: "center",
  gap: 12,
  flexWrap: "wrap",
  padding: "11px 20px",
  background: COLOR.surface,
  borderBottom: `1px solid ${COLOR.border}`,
};
const countBadge: React.CSSProperties = {
  fontSize: "11.5px",
  fontWeight: 700,
  background: COLOR.accentSoft,
  color: COLOR.accentDark,
  padding: "3px 10px",
  borderRadius: 9999,
};
const ghostButton: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: 6,
  height: 34,
  padding: "0 12px",
  borderRadius: 9,
  border: `1px solid ${COLOR.border}`,
  background: COLOR.surface,
  color: COLOR.textSecondary,
  fontWeight: 600,
  fontSize: "12.5px",
  cursor: "pointer",
};
const pagerStyle: React.CSSProperties = {
  flexShrink: 0,
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  padding: "8px 16px",
  borderTop: `1px solid ${COLOR.border}`,
  background: COLOR.surface,
};
