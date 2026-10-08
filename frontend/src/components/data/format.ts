import type { DataRecordRow } from "../../types";
import { COLOR } from "../../theme";

// Định dạng hiển thị dùng chung cho tab Dữ liệu.

export function formatNumber(value: number | null | undefined, digits = 3): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  if (!Number.isFinite(value)) return "—";
  const fixed = Number(value).toFixed(digits);
  // Bỏ số 0 thừa ở đuôi nhưng giữ tối thiểu 0 chữ số thập phân.
  return fixed.replace(/\.?0+$/, "") || "0";
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value.slice(0, 10);
  const day = String(date.getDate()).padStart(2, "0");
  const month = String(date.getMonth() + 1).padStart(2, "0");
  return `${day}/${month}/${date.getFullYear()}`;
}

export function formatRange(min: number | null | undefined, max: number | null | undefined, unit: string | null | undefined): string {
  const hasMin = min !== null && min !== undefined;
  const hasMax = max !== null && max !== undefined;
  if (!hasMin && !hasMax) return "—";
  const suffix = unit ? ` ${unit}` : "";
  // Hai tham số đã ở ĐƠN VỊ GỐC của dữ kiện (backend đổi từ SI và làm tròn 9 chữ
  // số có nghĩa). Dùng 9 chữ số để không nuốt mất giá trị nhỏ như 0,0015 MPa.
  if (hasMin && hasMax) return `${formatNumber(min, 9)} – ${formatNumber(max, 9)}${suffix}`;
  return `${formatNumber(hasMin ? min : max, 9)}${suffix}`;
}

export interface Tone {
  label: string;
  fg: string;
  bg: string;
}

/** Ngưỡng cảnh báo "Sắp hết hạn": còn tối đa 60 ngày. */
export const EXPIRY_WARNING_DAYS = 60;

export type ExpiryState = "valid" | "warning" | "expired" | "unknown";

export interface ExpiryStatus extends Tone {
  state: ExpiryState;
  /** Số ngày còn lại (âm khi đã hết hạn); null khi không có ngày hạn. */
  days: number | null;
}

/**
 * Trạng thái hiệu lực của một hồ sơ theo ngày hết hiệu lực:
 * "Hết hạn" khi đã qua, "Sắp hết hạn" khi còn tối đa `EXPIRY_WARNING_DAYS` ngày, còn lại "Còn hạn".
 * Ngày rỗng hoặc không hợp lệ trả "Không rõ hạn".
 */
export function expiryStatus(expiresAt: string | null | undefined, now: Date = new Date()): ExpiryStatus {
  if (!expiresAt) return { state: "unknown", label: "Không rõ hạn", days: null, fg: COLOR.textSecondary, bg: COLOR.neutralBg };
  const expiry = new Date(expiresAt);
  if (Number.isNaN(expiry.getTime())) return { state: "unknown", label: "Không rõ hạn", days: null, fg: COLOR.textSecondary, bg: COLOR.neutralBg };
  const msPerDay = 24 * 60 * 60 * 1000;
  const days = Math.ceil((expiry.getTime() - now.getTime()) / msPerDay);
  if (days < 0) return { state: "expired", label: "Hết hạn", days, fg: COLOR.danger, bg: COLOR.dangerBg };
  if (days <= EXPIRY_WARNING_DAYS) return { state: "warning", label: "Sắp hết hạn", days, fg: COLOR.warning, bg: COLOR.warningBg };
  return { state: "valid", label: "Còn hạn", days, fg: COLOR.success, bg: COLOR.successBg };
}

export function verdictTone(verdict: string | null | undefined, label?: string | null): Tone {
  if (verdict === "dat") {
    return { label: label ?? "Đạt", fg: COLOR.textOnDark, bg: COLOR.success };
  }
  if (verdict === "khong_dat") {
    return { label: label ?? "Không đạt", fg: COLOR.textOnDark, bg: COLOR.danger };
  }
  return { label: label ?? "—", fg: COLOR.textSecondary, bg: COLOR.neutralBg };
}

export function withinLimitTone(within: boolean | null | undefined): Tone {
  if (within === true) return { label: "Trong giới hạn", fg: COLOR.textOnDark, bg: COLOR.success };
  if (within === false) return { label: "Vượt giới hạn", fg: COLOR.textOnDark, bg: COLOR.danger };
  return { label: "Chưa đủ dữ liệu", fg: COLOR.textSecondary, bg: COLOR.neutralBg };
}

/** Phạm vi đo: nguyên văn biên bản khi có; phạm vi áp dụng của QTKĐ thì ghi rõ nguồn. */
export function rangeLabel(record: DataRecordRow): string {
  const text = record.range_text ?? formatRange(record.range_min_display, record.range_max_display, record.range_unit_code);
  return record.range_source === "procedure" && text !== "—" ? `${text} (theo QTKĐ)` : text;
}
