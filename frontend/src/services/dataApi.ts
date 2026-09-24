import type {
  DataCellRef,
  DataRecordRow,
  DataRecordsPage,
  DeviceHistory,
  DeviceSummary,
  FilterOptions,
  ProvenanceSource,
} from "../types";
import { authFetch } from "./auth";

// ── Bề mặt tra cứu dữ liệu (Sprint 8) — api_server.py /api/data/* ──
// Mọi route cần token (mọi vai trò đã đăng nhập đều đọc được; đây là bề mặt đọc).
// Backend chỉ trả dữ liệu ĐÃ DUYỆT (P3); mỗi ô số kèm tham chiếu xuất xứ (P1).

export interface RecordFilters {
  device_type_id?: number;
  quantity_id?: number;
  procedure_id?: number;
  verdict?: string;
  date_from?: string;
  date_to?: string;
  range_min?: number;
  range_max?: number;
  range_unit?: string;
  accuracy?: string;
  serial?: string;
  search?: string;
  sort?: string;
  order?: "asc" | "desc";
  limit?: number;
  offset?: number;
}

function query(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "" && value !== null) search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}

async function parse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const message = (body as { detail?: string } | null)?.detail || `HTTP ${res.status}`;
    throw new Error(message);
  }
  return res.json() as Promise<T>;
}

export async function fetchRecords(filters: RecordFilters = {}): Promise<DataRecordsPage> {
  const res = await authFetch(`/api/data/records${query({ ...filters })}`);
  return parse<DataRecordsPage>(res);
}

export async function fetchRecord(recordId: number): Promise<DataRecordRow> {
  const res = await authFetch(`/api/data/records/${recordId}`);
  return parse<DataRecordRow>(res);
}

export async function fetchFilterOptions(): Promise<FilterOptions> {
  const res = await authFetch("/api/data/filters");
  return parse<FilterOptions>(res);
}

export async function fetchDevices(params: {
  q?: string;
  device_type_id?: number;
  limit?: number;
  offset?: number;
} = {}): Promise<{ items: DeviceSummary[]; total: number }> {
  const res = await authFetch(`/api/data/devices${query({ ...params })}`);
  return parse<{ items: DeviceSummary[]; total: number }>(res);
}

export async function fetchDeviceHistory(deviceId: number): Promise<DeviceHistory> {
  const res = await authFetch(`/api/data/devices/${deviceId}/history`);
  return parse<DeviceHistory>(res);
}

export async function fetchDeviceHistoryBySerial(serial: string): Promise<DeviceHistory> {
  const res = await authFetch(`/api/data/devices/by-serial/${encodeURIComponent(serial)}`);
  return parse<DeviceHistory>(res);
}

/** Dựng tham số truy vấn xuất xứ từ tham chiếu ô số. */
export function provenanceParams(ref: DataCellRef): Record<string, string | number | undefined> {
  if (ref.kind === "measurement") return { measurement_id: ref.id, field: ref.field };
  if (ref.kind === "fact") return { fact_id: ref.id };
  if (ref.kind === "extraction") return { extraction_id: ref.id };
  return { record_id: ref.id };
}

export async function fetchProvenance(ref: DataCellRef): Promise<ProvenanceSource> {
  const res = await authFetch(`/api/data/provenance${query(provenanceParams(ref))}`);
  return parse<ProvenanceSource>(res);
}

export async function exportRecords(filters: RecordFilters = {}): Promise<Blob> {
  const res = await authFetch(`/api/data/records/export.xlsx${query({ ...filters })}`);
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error((body as { detail?: string } | null)?.detail || `HTTP ${res.status}`);
  }
  return res.blob();
}

/** Tải một blob về máy (dùng cho xuất Excel). */
export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export function exportFilename(): string {
  const now = new Date();
  const stamp = `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, "0")}${String(now.getDate()).padStart(2, "0")}`;
  return `du-lieu-kiem-dinh-${stamp}.xlsx`;
}
