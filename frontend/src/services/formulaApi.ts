export interface FormulaVariable {
  key: string;
  label: string;
  unit: string;
  kind?: "scalar" | "series";
  min?: string | number | null;
  max?: string | number | null;
  exclusive_min?: boolean;
  exclusive_max?: boolean;
  min_items?: number;
  max_items?: number;
}
export interface FormulaInput {
  value: string | string[];
  unit: string;
}
export interface FormulaCase {
  inputs: Record<string, FormulaInput>;
  expected: string;
  unit: string;
}
export interface FormulaProposal {
  title: string;
  expression: string;
  unit: string;
  variables: FormulaVariable[];
  conditions: { key: string; label: string }[];
  test_cases: FormulaCase[];
}
export interface FormulaDraft {
  id: string;
  revision: number;
  status: "pending_review" | "approved" | "rejected" | "stale";
  proposal: FormulaProposal;
  source: { document_id: string; file: string; sha256: string; fid: string; kind: string; section: string; latex: string; context: string };
  warnings: string[];
  validation_errors: string[];
  review: { reviewer: string; note: string; at: string; decision: string } | null;
  history: { action: string; revision: number; at: string; reviewer?: string; note?: string }[];
}

type JsonRecord = Record<string, unknown>;
const record = (value: unknown): value is JsonRecord => value !== null && typeof value === "object" && !Array.isArray(value);
const strings = (value: unknown): value is string[] => Array.isArray(value) && value.every((item) => typeof item === "string");
const fields = (value: JsonRecord, keys: string[]) => keys.every((key) => typeof value[key] === "string");
const optional = (value: JsonRecord, key: string, check: (item: unknown) => boolean) => value[key] === undefined || check(value[key]);
const finite = (value: unknown) => typeof value === "number" && Number.isFinite(value);
const inputShape = (value: unknown) => record(value) && typeof value.unit === "string" && (typeof value.value === "string" || strings(value.value));

// Validate only the response structure. Empty strings/arrays are valid incomplete
// drafts; semantic approval remains the backend's responsibility. Never repair or
// silently coerce a malformed record into an executable definition.
function draftShape(value: unknown): boolean {
  if (
    !record(value) ||
    typeof value.id !== "string" ||
    !Number.isInteger(value.revision) ||
    (value.revision as number) < 1 ||
    !["pending_review", "approved", "rejected", "stale"].includes(value.status as string)
  )
    return false;
  const proposal = value.proposal;
  if (
    !record(proposal) ||
    !fields(proposal, ["title", "expression", "unit"]) ||
    !Array.isArray(proposal.variables) ||
    !Array.isArray(proposal.conditions) ||
    !Array.isArray(proposal.test_cases)
  )
    return false;
  if (
    !proposal.variables.every(
      (v) =>
        record(v) &&
        fields(v, ["key", "label", "unit"]) &&
        optional(v, "kind", (x) => x === "scalar" || x === "series") &&
        ["min", "max"].every((key) => optional(v, key, (x) => x === null || typeof x === "string" || finite(x))) &&
        ["exclusive_min", "exclusive_max"].every((key) => optional(v, key, (x) => typeof x === "boolean")) &&
        ["min_items", "max_items"].every((key) => optional(v, key, (x) => Number.isInteger(x))),
    )
  )
    return false;
  if (!proposal.conditions.every((c) => record(c) && fields(c, ["key", "label"]))) return false;
  if (!proposal.test_cases.every((c) => record(c) && fields(c, ["expected", "unit"]) && record(c.inputs) && Object.values(c.inputs).every(inputShape)))
    return false;
  if (
    !record(value.source) ||
    !fields(value.source, ["document_id", "file", "sha256", "fid", "kind", "section", "latex", "context"]) ||
    !strings(value.warnings) ||
    !strings(value.validation_errors)
  )
    return false;
  if (value.review !== null && (!record(value.review) || !fields(value.review, ["reviewer", "note", "at", "decision"]))) return false;
  return (
    Array.isArray(value.history) &&
    value.history.every(
      (event) =>
        record(event) &&
        fields(event, ["action", "at"]) &&
        Number.isInteger(event.revision) &&
        ["reviewer", "note"].every((key) => optional(event, key, (x) => typeof x === "string")),
    )
  );
}
function checked<T>(data: unknown, valid: (data: unknown) => boolean): T {
  if (!valid(data))
    throw new Error(
      "Dữ liệu công thức từ máy chủ không đúng cấu trúc. Không thể mở hoặc sử dụng bản nháp này. Vui lòng tải lại; nếu lỗi còn xuất hiện, báo quản trị viên kiểm tra dữ liệu đã lưu.",
    );
  return data as T;
}

async function request<T>(url: string, method = "GET", body?: unknown): Promise<T> {
  const response = await fetch(url, { method, headers: { "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) });
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = typeof data?.detail === "string" ? data.detail : `Yêu cầu thất bại (HTTP ${response.status}). Vui lòng thử lại hoặc kiểm tra dữ liệu.`;
    throw new Error(
      response.status === 409 ? `${detail} Tải lại danh sách để xem phiên bản mới nhất; sao chép phần chỉnh sửa cần giữ trước khi tải lại.` : detail,
    );
  }
  if (data === null) throw new Error("Máy chủ trả dữ liệu không hợp lệ. Vui lòng thử lại.");
  return data as T;
}
export const listFormulaDrafts = async (documentId: string) =>
  checked<{ drafts: FormulaDraft[]; units: string[] }>(
    await request<unknown>(`/api/documents/${encodeURIComponent(documentId)}/formula-drafts`),
    (data) => record(data) && strings(data.units) && Array.isArray(data.drafts) && data.drafts.every(draftShape),
  );
export const generateFormulaDrafts = async (documentId: string) =>
  checked<{ created: number; candidates: number }>(
    await request<unknown>(`/api/documents/${encodeURIComponent(documentId)}/formula-drafts/generate`, "POST"),
    (data) => record(data) && Number.isInteger(data.created) && Number.isInteger(data.candidates),
  );
export const saveFormulaDraft = async (draft: FormulaDraft, proposal: FormulaProposal) =>
  checked<FormulaDraft>(await request<unknown>(`/api/formula-drafts/${draft.id}`, "PUT", { revision: draft.revision, proposal }), draftShape);
export const decideFormulaDraft = async (draft: FormulaDraft, decision: "approve" | "reject", reviewer: string, note: string, confirmed: boolean) =>
  checked<FormulaDraft>(
    await request<unknown>(`/api/formula-drafts/${draft.id}/${decision}`, "POST", { revision: draft.revision, reviewer, note, confirmed }),
    draftShape,
  );
export const calculateFormula = async (draft: FormulaDraft, inputs: Record<string, FormulaInput>, confirmations: Record<string, boolean>) =>
  checked<{ value: string; unit: string; source: string; source_hash: string; approved_by: string }>(
    await request<unknown>(`/api/formula-drafts/${draft.id}/calculate`, "POST", { revision: draft.revision, inputs, confirmations }),
    (data) => record(data) && fields(data, ["value", "unit", "source", "source_hash", "approved_by"]),
  );
