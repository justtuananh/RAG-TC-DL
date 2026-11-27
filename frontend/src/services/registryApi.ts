import { AuthError, authFetch } from "./auth";

/** Sổ đăng ký danh mục 877 (api/routes/registry.py): nạp file danh mục, xem báo cáo lỗi, duyệt. */
export type RegistryKind = "procedure" | "capability_kd" | "capability_hc" | "standard";
export type RegistryStatus = "draft" | "approved" | "rejected" | "replaced";
export type IssueLevel = "error" | "warning" | "info";

export interface RegistryIssue {
  level: IssueLevel;
  row: number | null;
  message: string;
}

export interface RegistryChanges {
  base_id: number | null;
  added: string[];
  removed: string[];
  changed: string[];
}

export interface RegistrySource {
  id: number;
  kind: RegistryKind;
  kind_label: string;
  file_name: string;
  title: string | null;
  status: RegistryStatus;
  row_count: number;
  issues: RegistryIssue[];
  revision: number;
  uploaded_at: string | null;
  reviewed_at: string | null;
  review_note: string | null;
  /** Chỉ có trong danh sách: số mục cần xem, gồm cả đối chiếu chéo với danh mục quy trình. */
  attention?: number;
  /** Chỉ có khi đọc chi tiết một bản. */
  cross_issues?: RegistryIssue[];
  changes?: RegistryChanges;
}

export interface RegistryGap {
  code: string;
  title: string;
  row: number;
}

const INVALID = "Máy chủ trả dữ liệu danh mục không hợp lệ. Vui lòng tải lại.";
const BASE = "/api/registry";
const isRecord = (value: unknown): value is Record<string, unknown> => value !== null && typeof value === "object" && !Array.isArray(value);
const isIssue = (value: unknown): value is RegistryIssue =>
  isRecord(value) && typeof value.message === "string" && typeof value.level === "string" && (value.row === null || Number.isInteger(value.row));

export function isRegistrySource(value: unknown): value is RegistrySource {
  return (
    isRecord(value) &&
    Number.isInteger(value.id) &&
    Number.isInteger(value.revision) &&
    Number.isInteger(value.row_count) &&
    ["kind", "kind_label", "file_name", "status"].every((key) => typeof value[key] === "string") &&
    Array.isArray(value.issues) &&
    value.issues.every(isIssue)
  );
}

async function send(url: string, init: RequestInit = {}): Promise<unknown> {
  const response = await authFetch(url, init);
  const data = response.status === 204 ? null : await response.json().catch(() => null);
  if (response.status === 401) throw new AuthError("Vui lòng đăng nhập để thực hiện thao tác này.", 401);
  if (!response.ok) {
    const detail = isRecord(data) && typeof data.detail === "string" ? data.detail : `Yêu cầu thất bại (HTTP ${response.status}). Vui lòng thử lại.`;
    throw new Error(detail);
  }
  return data;
}

function source(data: unknown): RegistrySource {
  if (!isRecord(data) || !isRegistrySource(data.source)) throw new Error(INVALID);
  return data.source;
}

export async function listRegistrySources(): Promise<RegistrySource[]> {
  const data = await send(`${BASE}/sources`);
  if (!isRecord(data) || !Array.isArray(data.sources) || !data.sources.every(isRegistrySource)) throw new Error(INVALID);
  return data.sources;
}

export async function getRegistrySource(id: number): Promise<RegistrySource> {
  return source(await send(`${BASE}/sources/${id}`));
}

export async function uploadRegistrySource(file: File): Promise<RegistrySource> {
  const form = new FormData();
  form.append("file", file);
  return source(await send(`${BASE}/sources`, { method: "POST", body: form }));
}

export async function decideRegistrySource(id: number, revision: number, approve: boolean, note: string): Promise<RegistrySource> {
  const action = approve ? "approve" : "reject";
  return source(
    await send(`${BASE}/sources/${id}/${action}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ revision, note }),
    }),
  );
}

export async function deleteRegistrySource(id: number): Promise<void> {
  await send(`${BASE}/sources/${id}`, { method: "DELETE" });
}

export async function getRegistryGaps(): Promise<{ missing: RegistryGap[]; total: number }> {
  const data = await send(`${BASE}/gaps`);
  if (!isRecord(data) || !Array.isArray(data.missing) || !Number.isInteger(data.total)) throw new Error(INVALID);
  return { missing: data.missing as RegistryGap[], total: data.total as number };
}
