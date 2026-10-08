// Tiền tố phạm vi mà nút "Hỏi trợ lý" của Hồ sơ QTKĐ thêm vào câu hỏi.
const SCOPE_PREFIX_RE = /^\s*Theo QTKĐ [^,]+,\s*/;

/**
 * Câu hỏi giới hạn trong một QTKĐ: `prefix` ("Theo QTKĐ 1.061:2021, ") đặt trước bản
 * nháp đang soạn. Tiền tố phạm vi cũ bị thay chứ không chồng khi chuyển sang QTKĐ khác.
 */
export function scopeQuestion(prefix: string, draft: string): string {
  return `${prefix}${draft.replace(SCOPE_PREFIX_RE, "").trim()}`;
}
