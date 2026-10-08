import { useState } from "react";
import type { FilterChoice, FilterOptions } from "../../types";
import type { RecordFilters } from "../../services/dataApi";
import { COLOR } from "../../theme";
import { IcFilter, IcSearch, IcX } from "../common/icons";
import { formatDate } from "./format";

// Thanh lọc của tab Dữ liệu, tách khỏi <thead> của bảng.
// Hàng 1: tìm kiếm, chip kết luận, khoảng ngày. Hàng 2 (thu gọn mặc định, tự mở khi
// có bộ lọc đang bật): loại thiết bị, đại lượng, QTKĐ, phạm vi đo, cấp chính xác.
// Cuối hàng 1: tổng số hồ sơ đã duyệt. Dưới cùng: dải chip các bộ lọc đang bật (mỗi chip có nút gỡ riêng).

export interface RecordFilterBarProps {
  filters: RecordFilters;
  options: FilterOptions | null;
  total: number;
  onChange: (patch: Partial<RecordFilters>) => void;
}

const SECOND_ROW_KEYS: (keyof RecordFilters)[] = ["device_type_id", "quantity_id", "procedure_id", "range_min", "range_max", "range_unit", "accuracy"];

interface ActiveChip {
  key: string;
  label: string;
  clear: () => void;
}

function choiceLabel(choices: FilterChoice[] | undefined, value: number | string | undefined): string {
  if (value === undefined || value === "") return "";
  const found = (choices ?? []).find((choice) => String(choice.value) === String(value));
  return found?.label ?? String(value);
}

/** Dải chip các bộ lọc đang bật, mỗi chip gỡ riêng được. */
function buildChips(filters: RecordFilters, options: FilterOptions | null, onChange: (patch: Partial<RecordFilters>) => void): ActiveChip[] {
  const chips: ActiveChip[] = [];
  if (filters.search) chips.push({ key: "search", label: `Tìm: ${filters.search}`, clear: () => onChange({ search: undefined }) });
  if (filters.verdict)
    chips.push({ key: "verdict", label: `Kết luận: ${choiceLabel(options?.verdicts, filters.verdict)}`, clear: () => onChange({ verdict: undefined }) });
  if (filters.date_from) chips.push({ key: "date_from", label: `Từ ngày ${formatDate(filters.date_from)}`, clear: () => onChange({ date_from: undefined }) });
  if (filters.date_to) chips.push({ key: "date_to", label: `Đến ngày ${formatDate(filters.date_to)}`, clear: () => onChange({ date_to: undefined }) });
  if (filters.device_type_id !== undefined)
    chips.push({
      key: "device_type_id",
      label: `Thiết bị: ${choiceLabel(options?.device_types, filters.device_type_id)}`,
      clear: () => onChange({ device_type_id: undefined }),
    });
  if (filters.quantity_id !== undefined)
    chips.push({
      key: "quantity_id",
      label: `Đại lượng: ${choiceLabel(options?.quantities, filters.quantity_id)}`,
      clear: () => onChange({ quantity_id: undefined }),
    });
  if (filters.procedure_id !== undefined)
    chips.push({
      key: "procedure_id",
      label: `QTKĐ: ${choiceLabel(options?.procedures, filters.procedure_id)}`,
      clear: () => onChange({ procedure_id: undefined }),
    });
  if (filters.range_min !== undefined || filters.range_max !== undefined || filters.range_unit) {
    const min = filters.range_min ?? "";
    const max = filters.range_max ?? "";
    const unit = filters.range_unit ?? "";
    chips.push({
      key: "range",
      label: `Phạm vi ${min === "" ? "…" : min} – ${max === "" ? "…" : max}${unit ? ` ${unit}` : ""}`,
      clear: () => onChange({ range_min: undefined, range_max: undefined, range_unit: undefined }),
    });
  }
  if (filters.accuracy) chips.push({ key: "accuracy", label: `CCX: ${filters.accuracy}`, clear: () => onChange({ accuracy: undefined }) });
  return chips;
}

function VerdictChips({ choices, value, onChange }: { choices: FilterChoice[]; value: string; onChange: (patch: Partial<RecordFilters>) => void }) {
  const items = [{ value: "", label: "Tất cả" }, ...choices.map((choice) => ({ value: String(choice.value), label: choice.label }))];
  return (
    <div role="group" aria-label="Lọc theo kết luận" style={chipGroup}>
      {items.map((choice) => {
        const active = value === choice.value;
        return (
          <button
            key={choice.value || "all"}
            type="button"
            aria-pressed={active}
            onClick={() => onChange({ verdict: choice.value || undefined })}
            style={{
              ...chipButton,
              background: active ? COLOR.accent : COLOR.surface,
              color: active ? COLOR.textOnDark : COLOR.textSecondary,
              borderColor: active ? COLOR.accent : COLOR.border,
            }}
          >
            {choice.label}
          </button>
        );
      })}
    </div>
  );
}

function DateRange({ filters, onChange }: { filters: RecordFilters; onChange: (patch: Partial<RecordFilters>) => void }) {
  return (
    <div style={dateGroup}>
      <label style={dateLabel}>
        Từ
        <input
          type="date"
          value={filters.date_from ?? ""}
          onChange={(e) => onChange({ date_from: e.target.value || undefined })}
          aria-label="Lọc từ ngày kiểm định"
          style={dateInput}
        />
      </label>
      <label style={dateLabel}>
        Đến
        <input
          type="date"
          value={filters.date_to ?? ""}
          onChange={(e) => onChange({ date_to: e.target.value || undefined })}
          aria-label="Lọc đến ngày kiểm định"
          style={dateInput}
        />
      </label>
    </div>
  );
}

function MoreFilters({
  filters,
  options,
  onChange,
}: {
  filters: RecordFilters;
  options: FilterOptions | null;
  onChange: (patch: Partial<RecordFilters>) => void;
}) {
  return (
    <div style={rowStyle}>
      <label style={fieldLabel}>
        Loại thiết bị
        <select
          value={filters.device_type_id ?? ""}
          onChange={(e) => onChange({ device_type_id: e.target.value ? Number(e.target.value) : undefined })}
          aria-label="Lọc theo loại thiết bị"
          style={fieldSelect}
        >
          <option value="">Mọi loại</option>
          {(options?.device_types ?? []).map((choice) => (
            <option key={choice.value} value={choice.value}>
              {choice.label}
            </option>
          ))}
        </select>
      </label>

      <label style={fieldLabel}>
        Đại lượng
        <select
          value={filters.quantity_id ?? ""}
          onChange={(e) => onChange({ quantity_id: e.target.value ? Number(e.target.value) : undefined })}
          aria-label="Lọc theo đại lượng"
          style={{ ...fieldSelect, minWidth: 128 }}
        >
          <option value="">Mọi đại lượng</option>
          {(options?.quantities ?? []).map((choice) => (
            <option key={choice.value} value={choice.value}>
              {choice.label}
            </option>
          ))}
        </select>
      </label>

      <label style={fieldLabel}>
        QTKĐ
        <select
          value={filters.procedure_id ?? ""}
          onChange={(e) => onChange({ procedure_id: e.target.value ? Number(e.target.value) : undefined })}
          aria-label="Lọc theo QTKĐ"
          style={{ ...fieldSelect, minWidth: 128 }}
        >
          <option value="">Mọi QTKĐ</option>
          {(options?.procedures ?? []).map((choice) => (
            <option key={choice.value} value={choice.value}>
              {choice.label}
            </option>
          ))}
        </select>
      </label>

      <label style={fieldLabel}>
        Phạm vi đo
        <div style={{ display: "flex", gap: 4 }}>
          <input
            type="number"
            value={filters.range_min ?? ""}
            onChange={(e) => onChange({ range_min: e.target.value === "" ? undefined : Number(e.target.value) })}
            placeholder="Min"
            aria-label="Phạm vi đo nhỏ nhất"
            style={{ ...fieldInput, width: 84 }}
          />
          <input
            type="number"
            value={filters.range_max ?? ""}
            onChange={(e) => onChange({ range_max: e.target.value === "" ? undefined : Number(e.target.value) })}
            placeholder="Max"
            aria-label="Phạm vi đo lớn nhất"
            style={{ ...fieldInput, width: 84 }}
          />
          <input
            type="text"
            value={filters.range_unit ?? ""}
            onChange={(e) => onChange({ range_unit: e.target.value || undefined })}
            placeholder="ĐV"
            aria-label="Đơn vị phạm vi đo"
            style={{ ...fieldInput, width: 60 }}
          />
        </div>
      </label>

      <label style={fieldLabel}>
        Cấp chính xác
        <input
          type="text"
          value={filters.accuracy ?? ""}
          onChange={(e) => onChange({ accuracy: e.target.value || undefined })}
          placeholder="Cấp chính xác…"
          aria-label="Lọc theo cấp chính xác"
          style={fieldInput}
        />
      </label>
    </div>
  );
}

function ActiveChips({ chips }: { chips: ActiveChip[] }) {
  if (chips.length === 0) return null;
  return (
    <div style={chipRow}>
      {chips.map((chip) => (
        <span key={chip.key} style={activeChip}>
          {chip.label}
          <button type="button" onClick={chip.clear} aria-label={`Bỏ lọc ${chip.label}`} style={chipRemove}>
            <IcX size={11} />
          </button>
        </span>
      ))}
    </div>
  );
}

export default function RecordFilterBar({ filters, options, total, onChange }: RecordFilterBarProps) {
  const [moreOpen, setMoreOpen] = useState(false);
  const secondRowCount = SECOND_ROW_KEYS.filter((key) => filters[key] !== undefined && filters[key] !== "").length;
  const showMore = moreOpen || secondRowCount > 0;
  const chips = buildChips(filters, options, onChange);

  return (
    <div style={barStyle}>
      <div style={rowStyle}>
        <div style={searchWrap}>
          <IcSearch size={15} style={{ color: COLOR.textMuted, flexShrink: 0 }} />
          <input
            type="search"
            value={filters.search ?? ""}
            onChange={(e) => onChange({ search: e.target.value })}
            placeholder="Tìm số hiệu, model, QTKĐ…"
            aria-label="Lọc theo số hiệu, model, QTKĐ"
            style={searchInput}
          />
        </div>

        <VerdictChips choices={options?.verdicts ?? []} value={filters.verdict ?? ""} onChange={onChange} />
        <DateRange filters={filters} onChange={onChange} />

        <button type="button" aria-expanded={showMore} onClick={() => setMoreOpen((v) => !v)} style={moreButton}>
          <IcFilter size={14} /> Bộ lọc khác{secondRowCount > 0 ? ` (${secondRowCount})` : ""}
        </button>

        <span style={{ flex: 1 }} />
        <span className="tabular-nums" style={totalText}>
          {total} hồ sơ đã duyệt
        </span>
      </div>

      {showMore && <MoreFilters filters={filters} options={options} onChange={onChange} />}

      <ActiveChips chips={chips} />
    </div>
  );
}

const barStyle: React.CSSProperties = {
  flexShrink: 0,
  display: "flex",
  flexDirection: "column",
  gap: 8,
  padding: "10px 16px",
  background: COLOR.surface,
  borderBottom: `1px solid ${COLOR.border}`,
};
const rowStyle: React.CSSProperties = { display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" };
const searchWrap: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 8,
  flex: "1 1 320px",
  minWidth: 280,
  maxWidth: 420,
  height: 34,
  padding: "0 11px",
  borderRadius: 9,
  border: `1px solid ${COLOR.border}`,
  background: COLOR.surface,
};
const searchInput: React.CSSProperties = {
  flex: 1,
  minWidth: 0,
  height: "100%",
  border: "none",
  outline: "none",
  background: "transparent",
  color: COLOR.textPrimary,
  fontSize: "13px",
  fontFamily: "inherit",
};
const chipGroup: React.CSSProperties = { display: "flex", gap: 4, flexWrap: "wrap" };
const chipButton: React.CSSProperties = {
  height: 30,
  padding: "0 12px",
  borderRadius: 9999,
  border: `1px solid ${COLOR.border}`,
  fontWeight: 600,
  fontSize: "12.5px",
  fontFamily: "inherit",
  cursor: "pointer",
};
const dateGroup: React.CSSProperties = { display: "flex", gap: 10, alignItems: "center" };
// Nhãn "Từ"/"Đến" nằm cùng hàng với ô ngày để hàng lọc thứ nhất chỉ cao một dòng.
const dateLabel: React.CSSProperties = { display: "flex", alignItems: "center", gap: 6, fontSize: "12.5px", fontWeight: 600, color: COLOR.textSecondary };
const dateInput: React.CSSProperties = {
  height: 32,
  padding: "0 8px",
  borderRadius: 8,
  border: `1px solid ${COLOR.border}`,
  background: COLOR.surface,
  color: COLOR.textPrimary,
  fontSize: "12.5px",
  fontFamily: "inherit",
};
const moreButton: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: 6,
  height: 34,
  padding: "0 12px",
  borderRadius: 9,
  border: `1px solid ${COLOR.border}`,
  background: COLOR.surface,
  color: COLOR.textSecondary,
  fontWeight: 600,
  fontSize: "12.5px",
  cursor: "pointer",
};
const fieldLabel: React.CSSProperties = { display: "flex", flexDirection: "column", gap: 3, fontSize: "11px", fontWeight: 700, color: COLOR.textSecondary };
const fieldSelect: React.CSSProperties = {
  height: 32,
  padding: "0 9px",
  borderRadius: 8,
  border: `1px solid ${COLOR.border}`,
  background: COLOR.surface,
  color: COLOR.textPrimary,
  fontSize: "12.5px",
  fontFamily: "inherit",
};
const fieldInput: React.CSSProperties = { ...fieldSelect, padding: "0 8px" };
const chipRow: React.CSSProperties = { display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap", minHeight: 24 };
const activeChip: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: 5,
  height: 24,
  padding: "0 4px 0 9px",
  borderRadius: 9999,
  background: COLOR.accentSoft,
  border: `1px solid ${COLOR.accentSoftBorder}`,
  color: COLOR.accentDark,
  fontSize: "11.5px",
  fontWeight: 600,
};
const chipRemove: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  width: 17,
  height: 17,
  borderRadius: 9999,
  border: "none",
  background: "transparent",
  color: COLOR.accentDark,
  cursor: "pointer",
};
const totalText: React.CSSProperties = {
  fontSize: "11.5px",
  fontWeight: 700,
  background: COLOR.accentSoft,
  color: COLOR.accentDark,
  padding: "3px 10px",
  borderRadius: 9999,
};
