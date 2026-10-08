import type { ExtractionUnit } from "../../types";
import { formatNumber } from "../data/format";

// Hai ô min/max của dữ kiện lưu theo SI (23 oC → 296.15 K). Người duyệt cần thấy
// đơn vị SI cạnh nhãn và giá trị đổi ngược về đơn vị gốc để đối chiếu nguyên văn.

export function siFieldLabel(label: string, unit: ExtractionUnit | null | undefined): string {
  return unit?.si_code ? `${label} (SI, ${unit.si_code})` : `${label} (SI)`;
}

/** "= 18 °C" cho giá trị SI đang nhập; null khi không có gì để đổi. */
export function originalUnitHint(raw: string, unit: ExtractionUnit | null | undefined): string | null {
  if (!unit || !unit.factor_to_si || unit.code === unit.si_code) return null;
  const text = raw.trim().replace(",", ".");
  if (text === "") return null;
  const si = Number(text);
  if (!Number.isFinite(si)) return null;
  const original = (si - unit.offset_to_si) / unit.factor_to_si;
  return `= ${formatNumber(original, 9)} ${unit.code}`;
}
