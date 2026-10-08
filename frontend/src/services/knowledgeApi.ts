import type { ProcedurePage, ProcedureProfile } from "../types";
import { authFetch } from "./auth";

// ── Hồ sơ QTKĐ: /api/knowledge/procedures* ──
// Bề mặt đọc (mọi vai trò đã đăng nhập). Backend chỉ trả tri thức ĐÃ DUYỆT (P3);
// mỗi dòng kèm id để mở nguyên văn qua /api/data/provenance (P1).

async function parse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const message = (body as { detail?: string } | null)?.detail || `HTTP ${res.status}`;
    throw new Error(message);
  }
  return res.json() as Promise<T>;
}

export async function fetchProcedures(params: { q?: string; limit?: number; offset?: number } = {}): Promise<ProcedurePage> {
  const search = new URLSearchParams();
  if (params.q?.trim()) search.set("q", params.q.trim());
  if (params.limit !== undefined) search.set("limit", String(params.limit));
  if (params.offset !== undefined) search.set("offset", String(params.offset));
  const qs = search.toString();
  const res = await authFetch(`/api/knowledge/procedures${qs ? `?${qs}` : ""}`);
  return parse<ProcedurePage>(res);
}

export async function fetchProcedureProfile(id: number): Promise<ProcedureProfile> {
  const res = await authFetch(`/api/knowledge/procedures/${id}`);
  return parse<ProcedureProfile>(res);
}
