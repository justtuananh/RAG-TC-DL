import { useCallback, useEffect, useRef, useState } from "react";
import type { AppState, DataCellRef, DataRecordRow, DeviceHistory, FilterOptions } from "../../types";
import type { Actions } from "../../store/useAppStore";
import type { RecordFilters } from "../../services/dataApi";
import {
  downloadBlob,
  exportFilename,
  exportRecords,
  fetchDeviceHistory,
  fetchFilterOptions,
  fetchRecord,
  fetchRecords,
} from "../../services/dataApi";
import { COLOR } from "../../theme";
import { IcDownload, IcLock, IcRefresh, IcTable } from "../common/icons";
import RecordsTable from "./RecordsTable";
import RecordDetailPanel from "./RecordDetailPanel";
import DeviceHistoryView from "./DeviceHistoryView";
import ProvenanceDrawer from "./ProvenanceDrawer";

// Tab "Dữ liệu": bảng dày + lọc ở đầu cột + xuất xứ từng ô số + trang thiết bị.
// Chỉ đọc dữ liệu ĐÃ DUYỆT từ `/api/data/*` (P3). Cần đăng nhập (mọi vai trò đọc).

const PAGE_SIZE = 25;

const DEFAULT_FILTERS: RecordFilters = {
  sort: "calibrated_at",
  order: "desc",
};

export default function DataTab({ state, actions }: { state: AppState; actions: Actions }) {
  const user = state.auth.user;

  const [filters, setFilters] = useState<RecordFilters>(DEFAULT_FILTERS);
  const [rows, setRows] = useState<DataRecordRow[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [options, setOptions] = useState<FilterOptions | null>(null);

  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<DataRecordRow | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const [view, setView] = useState<"table" | "device">("table");
  const [deviceHistory, setDeviceHistory] = useState<DeviceHistory | null>(null);
  const [deviceLoading, setDeviceLoading] = useState(false);
  const [deviceError, setDeviceError] = useState<string | null>(null);

  const [provenanceRef, setProvenanceRef] = useState<DataCellRef | null>(null);
  const [exporting, setExporting] = useState(false);

  const requestSeq = useRef(0);

  const loadRecords = useCallback(async () => {
    const seq = ++requestSeq.current;
    setLoading(true);
    setError(null);
    try {
      const page = await fetchRecords({ ...filters, limit: PAGE_SIZE, offset });
      if (seq !== requestSeq.current) return;
      setRows(page.items);
      setTotal(page.total);
      setSelectedId((prev) => (page.items.some((row) => row.id === prev) ? prev : null));
    } catch (e) {
      if (seq === requestSeq.current) setError(e instanceof Error ? e.message : "Không tải được dữ liệu.");
    } finally {
      if (seq === requestSeq.current) setLoading(false);
    }
  }, [filters, offset]);

  // Nạp bảng — debounce nhẹ để gõ bộ lọc không bắn quá nhiều request.
  useEffect(() => {
    if (!user) return;
    const timer = setTimeout(() => void loadRecords(), 220);
    return () => clearTimeout(timer);
  }, [user, loadRecords]);

  useEffect(() => {
    if (!user) return;
    fetchFilterOptions().then(setOptions).catch(() => setOptions(null));
  }, [user]);

  useEffect(() => {
    if (selectedId == null) {
      setDetail(null);
      return;
    }
    let cancelled = false;
    setDetailLoading(true);
    fetchRecord(selectedId)
      .then((record) => {
        if (!cancelled) setDetail(record);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : "Không tải được chi tiết.");
      })
      .finally(() => {
        if (!cancelled) setDetailLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedId]);

  const patchFilters = useCallback((patch: Partial<RecordFilters>) => {
    setFilters((prev) => ({ ...prev, ...patch }));
    setOffset(0);
  }, []);

  const onSort = useCallback((column: string) => {
    setFilters((prev) => {
      if (prev.sort === column) {
        return { ...prev, order: prev.order === "asc" ? "desc" : "asc" };
      }
      return { ...prev, sort: column, order: column === "calibrated_at" || column === "expires_at" ? "desc" : "asc" };
    });
    setOffset(0);
  }, []);

  const resetFilters = () => {
    setFilters(DEFAULT_FILTERS);
    setOffset(0);
  };

  const openDevice = useCallback(async (record: DataRecordRow) => {
    if (record.device_id == null) return;
    setView("device");
    setDeviceLoading(true);
    setDeviceError(null);
    setDeviceHistory(null);
    try {
      setDeviceHistory(await fetchDeviceHistory(record.device_id));
    } catch (e) {
      setDeviceError(e instanceof Error ? e.message : "Không tải được lịch sử thiết bị.");
    } finally {
      setDeviceLoading(false);
    }
  }, []);

  // Mở thẳng trang thiết bị khi được yêu cầu từ bảng kết quả chat (Sprint 9).
  useEffect(() => {
    const deviceId = state.pendingDeviceId;
    if (deviceId == null || !user) return;
    actions.clearPendingDevice();
    setView("device");
    setDeviceLoading(true);
    setDeviceError(null);
    setDeviceHistory(null);
    fetchDeviceHistory(deviceId)
      .then(setDeviceHistory)
      .catch((e) => setDeviceError(e instanceof Error ? e.message : "Không tải được lịch sử thiết bị."))
      .finally(() => setDeviceLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.pendingDeviceId, user]);

  const doExport = async () => {
    if (exporting) return;
    setExporting(true);
    setError(null);
    try {
      const blob = await exportRecords(filters);
      downloadBlob(blob, exportFilename());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Không xuất được tệp Excel.");
    } finally {
      setExporting(false);
    }
  };

  if (!user) {
    return (
      <main aria-label="Dữ liệu" style={centered}>
        <div style={noticeCard}>
          <IcLock size={26} style={{ color: COLOR.borderStrong }} />
          <div style={{ fontWeight: 700, fontSize: "15px", color: COLOR.textPrimary }}>Cần đăng nhập để tra cứu dữ liệu</div>
          <div style={{ fontSize: "13px", color: COLOR.textSecondary, lineHeight: 1.55 }}>
            Bảng dữ liệu kiểm định chỉ dành cho người dùng đã đăng nhập; mọi dữ liệu hiển thị đều đã được duyệt.
          </div>
          <button type="button" onClick={() => actions.openLogin("Vui lòng đăng nhập để tra cứu dữ liệu.")} style={primaryButton}>
            Đăng nhập
          </button>
        </div>
      </main>
    );
  }

  if (view === "device") {
    return (
      <main aria-label="Dữ liệu" style={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "column", background: COLOR.bg }}>
        <DeviceHistoryView
          history={deviceHistory}
          loading={deviceLoading}
          error={deviceError}
          onBack={() => setView("table")}
          onOpenProvenance={setProvenanceRef}
        />
        <ProvenanceDrawer cellRef={provenanceRef} onClose={() => setProvenanceRef(null)} />
      </main>
    );
  }

  const pageStart = total === 0 ? 0 : offset + 1;
  const pageEnd = Math.min(offset + PAGE_SIZE, total);

  return (
    <main aria-label="Dữ liệu" style={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "column", background: COLOR.bg }}>
      <div style={{ flexShrink: 0, display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", padding: "11px 20px", background: COLOR.surface, borderBottom: `1px solid ${COLOR.border}` }}>
        <span style={{ display: "inline-flex", alignItems: "center", gap: 7, fontWeight: 700, fontSize: "14.5px", color: COLOR.textPrimary }}>
          <IcTable size={16} style={{ color: COLOR.accent }} /> Dữ liệu kiểm định
        </span>
        <span className="tabular-nums" style={{ fontSize: "11.5px", fontWeight: 700, background: COLOR.accentSoft, color: COLOR.accentDark, padding: "3px 10px", borderRadius: 9999 }}>
          {total} hồ sơ đã duyệt
        </span>
        <div style={{ flex: 1 }} />
        <button type="button" onClick={resetFilters} style={ghostButton}>
          <IcRefresh size={14} /> Xoá lọc
        </button>
        <button type="button" onClick={() => void doExport()} disabled={exporting} style={ghostButton}>
          <IcDownload size={14} /> {exporting ? "Đang xuất…" : "Xuất Excel"}
        </button>
      </div>

      <div style={{ flex: 1, minHeight: 0, display: "flex" }}>
        <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column" }}>
          <RecordsTable
            rows={rows}
            options={options}
            filters={filters}
            sort={filters.sort ?? "calibrated_at"}
            order={(filters.order as "asc" | "desc") ?? "desc"}
            loading={loading}
            error={error}
            selectedId={selectedId}
            onFilterChange={patchFilters}
            onSort={onSort}
            onOpenRecord={(row) => setSelectedId(row.id)}
            onOpenDevice={(row) => void openDevice(row)}
            onOpenProvenance={setProvenanceRef}
          />
          <nav aria-label="Phân trang" style={pagerStyle}>
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
        </div>

        <RecordDetailPanel
          record={detail}
          loading={detailLoading}
          onClose={() => setSelectedId(null)}
          onOpenProvenance={setProvenanceRef}
          onOpenDevice={(row) => void openDevice(row)}
        />
      </div>

      <ProvenanceDrawer cellRef={provenanceRef} onClose={() => setProvenanceRef(null)} />
    </main>
  );
}

const centered: React.CSSProperties = { flex: 1, minHeight: 0, display: "flex", alignItems: "center", justifyContent: "center", background: COLOR.bg };
const noticeCard: React.CSSProperties = { maxWidth: 420, padding: "28px 26px", textAlign: "center", display: "flex", flexDirection: "column", alignItems: "center", gap: 8, background: COLOR.surface, border: `1px solid ${COLOR.border}`, borderRadius: 13 };
const primaryButton: React.CSSProperties = { display: "inline-flex", alignItems: "center", gap: 7, height: 38, padding: "0 16px", marginTop: 4, borderRadius: 9, border: "none", background: COLOR.accent, color: COLOR.textOnDark, fontWeight: 700, fontSize: "13px", cursor: "pointer" };
const ghostButton: React.CSSProperties = { display: "inline-flex", alignItems: "center", gap: 6, height: 34, padding: "0 12px", borderRadius: 9, border: `1px solid ${COLOR.border}`, background: COLOR.surface, color: COLOR.textSecondary, fontWeight: 600, fontSize: "12.5px", cursor: "pointer" };
const pagerStyle: React.CSSProperties = { flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "space-between", padding: "8px 16px", borderTop: `1px solid ${COLOR.border}`, background: COLOR.surface };
