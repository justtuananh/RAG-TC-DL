import type { AuditEntry, ExtractionData, ExtractionItem } from "../types";
import { AuthError, authFetch } from "./auth";

// ── Hàng đợi duyệt tri thức (Sprint 6) — api_server.py /api/extractions/* ──
// Mọi route đều cần token và vai trò approver/admin, nên dùng authFetch.
// Response là dữ liệu chưa duyệt (bề mặt làm việc của người duyệt), KHÔNG phải
// bề mặt tra cứu công khai.

export interface QueueFilters {
  document_id?: string;
  fact_kind?: string;
  extractor?: string;
  min_confidence?: number;
  max_confidence?: number;
  status?: string;
  limit?: number;
  offset?: number;
}

export interface QueuePage {
  items: ExtractionItem[];
  total: number;
}

async function parse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const message = (body as { detail?: string } | null)?.detail || `HTTP ${res.status}`;
    if (res.status === 401) throw new AuthError(message, 401);
    throw new Error(message);
  }
  return res.json() as Promise<T>;
}

function query(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}

export async function fetchExtractionQueue(filters: QueueFilters = {}): Promise<QueuePage> {
  const res = await authFetch(`/api/extractions${query({ ...filters })}`);
  return parse<QueuePage>(res);
}

export async function fetchExtraction(id: number): Promise<ExtractionItem> {
  const res = await authFetch(`/api/extractions/${id}`);
  return parse<ExtractionItem>(res);
}

export async function fetchExtractionAudit(id: number): Promise<AuditEntry[]> {
  const res = await authFetch(`/api/extractions/${id}/audit`);
  const data = await parse<{ entries: AuditEntry[] }>(res);
  return data.entries;
}

export async function approveExtraction(id: number, note?: string): Promise<ExtractionItem> {
  const res = await authFetch(`/api/extractions/${id}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ note: note ?? null }),
  });
  return parse<ExtractionItem>(res);
}

export async function rejectExtraction(id: number, reason: string): Promise<ExtractionItem> {
  const res = await authFetch(`/api/extractions/${id}/reject`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason }),
  });
  return parse<ExtractionItem>(res);
}

export async function editApproveExtraction(id: number, edits: Partial<ExtractionData>): Promise<ExtractionItem> {
  const res = await authFetch(`/api/extractions/${id}/edit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(edits),
  });
  return parse<ExtractionItem>(res);
}

export interface BulkApproveArgs {
  extractor: string;
  section_path?: string;
  document_id?: string;
}

export async function bulkApproveExtractions(args: BulkApproveArgs): Promise<{ approved_count: number; ids: number[] }> {
  const res = await authFetch("/api/extractions/bulk-approve", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(args),
  });
  return parse<{ approved_count: number; ids: number[] }>(res);
}
