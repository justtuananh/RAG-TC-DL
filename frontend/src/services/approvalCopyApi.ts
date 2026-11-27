import { AuthError, authFetch } from "./auth";

/** Bản cứng đã phê duyệt (PDF scan / ảnh) đính kèm tài liệu - chỉ để xem, chatbot không đọc. */
export interface ApprovalCopy {
  id: string;
  name: string;
  ext: string;
  media_type: string;
  size: number;
  uploaded_at: string;
  uploaded_by: string | null;
}

/** Khớp `knowledge/approval_copies.py` (_TYPES). */
export const APPROVAL_COPY_ACCEPT = ".pdf,.png,.jpg,.jpeg,.webp,application/pdf,image/png,image/jpeg,image/webp";

const INVALID = "Máy chủ trả dữ liệu bản phê duyệt không hợp lệ. Vui lòng tải lại.";
const isRecord = (value: unknown): value is Record<string, unknown> => value !== null && typeof value === "object" && !Array.isArray(value);

export function isApprovalCopy(value: unknown): value is ApprovalCopy {
  return (
    isRecord(value) &&
    ["id", "name", "ext", "media_type", "uploaded_at"].every((key) => typeof value[key] === "string") &&
    Number.isInteger(value.size) &&
    (value.uploaded_by === null || typeof value.uploaded_by === "string")
  );
}

const base = (documentId: string) => `/api/documents/${encodeURIComponent(documentId)}/approval-copies`;

export const approvalCopyFileUrl = (documentId: string, copyId: string) => `${base(documentId)}/${encodeURIComponent(copyId)}/file`;

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

export async function listApprovalCopies(documentId: string): Promise<ApprovalCopy[]> {
  const data = await send(base(documentId));
  if (!isRecord(data) || !Array.isArray(data.copies) || !data.copies.every(isApprovalCopy)) throw new Error(INVALID);
  return data.copies;
}

export async function uploadApprovalCopy(documentId: string, file: File): Promise<ApprovalCopy> {
  const form = new FormData();
  form.append("file", file);
  const data = await send(base(documentId), { method: "POST", body: form });
  if (!isApprovalCopy(data)) throw new Error(INVALID);
  return data;
}

export async function deleteApprovalCopy(documentId: string, copyId: string): Promise<void> {
  await send(`${base(documentId)}/${encodeURIComponent(copyId)}`, { method: "DELETE" });
}
