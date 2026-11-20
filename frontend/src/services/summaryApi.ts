import { AuthError, authFetch } from "./auth";

export type SummaryStatus = "generating" | "draft" | "approved" | "rejected" | "error";

/** Bản tóm tắt tài liệu do LLM viết lúc nạp; chat chỉ dùng bản đã phê duyệt. */
export interface DocSummary {
  document_id: string;
  status: SummaryStatus;
  text: string;
  generated_text: string;
  warnings: string[];
  model: string | null;
  error: string | null;
  revision: number;
  generated_at: string | null;
  edited_by: string | null;
  edited_at: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  review_note: string | null;
  stale: boolean;
}

const STATUSES: SummaryStatus[] = ["generating", "draft", "approved", "rejected", "error"];
const isRecord = (value: unknown): value is Record<string, unknown> => value !== null && typeof value === "object" && !Array.isArray(value);
const nullableString = (value: unknown) => value === null || typeof value === "string";

export function isDocSummary(value: unknown): value is DocSummary {
  return (
    isRecord(value) &&
    STATUSES.includes(value.status as SummaryStatus) &&
    typeof value.text === "string" &&
    typeof value.generated_text === "string" &&
    Array.isArray(value.warnings) &&
    value.warnings.every((w) => typeof w === "string") &&
    Number.isInteger(value.revision) &&
    typeof value.stale === "boolean" &&
    ["model", "error", "generated_at", "edited_by", "edited_at", "reviewed_by", "reviewed_at", "review_note"].every((key) => nullableString(value[key]))
  );
}

async function request(url: string, method = "GET", body?: unknown): Promise<unknown> {
  const response = await authFetch(url, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await response.json().catch(() => null);
  if (response.status === 401) throw new AuthError("Vui lòng đăng nhập để thực hiện thao tác này.", 401);
  if (!response.ok) {
    const detail = typeof data?.detail === "string" ? data.detail : `Yêu cầu thất bại (HTTP ${response.status}). Vui lòng thử lại.`;
    throw new Error(detail);
  }
  return data;
}

const INVALID = "Máy chủ trả dữ liệu tóm tắt không hợp lệ. Vui lòng tải lại.";

function summaryOf(data: unknown): DocSummary | null {
  if (!isRecord(data) || !("summary" in data)) throw new Error(INVALID);
  if (data.summary === null) return null;
  if (!isDocSummary(data.summary)) throw new Error(INVALID);
  return data.summary;
}

function requiredSummary(data: unknown): DocSummary {
  const summary = summaryOf(data);
  if (summary === null) throw new Error(INVALID);
  return summary;
}

const base = (documentId: string) => `/api/documents/${encodeURIComponent(documentId)}/summary`;

/** `queued`: tài liệu đang chờ hoặc đang được sinh trên máy chủ. */
export interface SummaryState {
  summary: DocSummary | null;
  queued: boolean;
}

export async function getSummary(documentId: string): Promise<SummaryState> {
  const data = await request(base(documentId));
  const summary = summaryOf(data);
  return { summary, queued: isRecord(data) && data.queued === true };
}

export const generateSummary = async (documentId: string) => {
  await request(`${base(documentId)}/generate`, "POST");
};

export const editSummary = async (documentId: string, revision: number, text: string) =>
  requiredSummary(await request(base(documentId), "PUT", { revision, text }));

export const decideSummary = async (documentId: string, decision: "approve" | "reject", revision: number, note: string) =>
  requiredSummary(await request(`${base(documentId)}/${decision}`, "POST", { revision, note }));
