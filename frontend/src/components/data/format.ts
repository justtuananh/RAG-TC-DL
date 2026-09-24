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

export function formatRange(
  min: number | null | undefined,
  max: number | null | undefined,
  unit: string | null | undefined,
): string {
  const hasMin = min !== null && min !== undefined;
  const hasMax = max !== null && max !== undefined;
  if (!hasMin && !hasMax) return "—";
  const suffix = unit ? ` ${unit}` : "";
  if (hasMin && hasMax) return `${formatNumber(min)} – ${formatNumber(max)}${suffix}`;
  return `${formatNumber(hasMin ? min : max)}${suffix}`;
}

export interface Tone {
  label: string;
  fg: string;
  bg: string;
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
