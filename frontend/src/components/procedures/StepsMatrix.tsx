import { useState } from "react";
import type { InspectionMode, ProcedureProfile } from "../../types";
import { COLOR, SHADOW } from "../../theme";
import { IcCheck } from "../common/icons";
import { tableStyle, thStyle } from "../data/tableStyles";
import { EmptyLine, SectionCard, SourceButton, type OpenProvenance } from "./ProfileSections";
import { stepsForMode, type ModeFilter } from "./profileFormat";

// Bảng 1 "Các phép kiểm định" dưới dạng ma trận phép × chế độ. Lọc theo chế độ trả lời
// thẳng câu hỏi "kiểm định định kỳ gồm những phép nào"; mỗi dòng mở được nguyên văn.

const cell = { padding: "9px 12px", borderBottom: `1px solid ${COLOR.border}`, fontSize: "13px", verticalAlign: "middle" } as const;

function ModeFilterControl({
  options,
  value,
  onChange,
}: {
  options: { key: ModeFilter; label: string }[];
  value: ModeFilter;
  onChange: (mode: ModeFilter) => void;
}) {
  return (
    <div
      role="group"
      aria-label="Lọc theo chế độ kiểm định"
      style={{ display: "inline-flex", padding: 3, borderRadius: 10, background: COLOR.surfaceMuted, gap: 2 }}
    >
      {options.map((option) => {
        const active = option.key === value;
        return (
          <button
            key={option.key}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(option.key)}
            style={{
              height: 28,
              padding: "0 11px",
              border: "none",
              borderRadius: 8,
              background: active ? COLOR.surface : "transparent",
              boxShadow: active ? SHADOW.sm : "none",
              color: active ? COLOR.accentDark : COLOR.textSecondary,
              fontWeight: active ? 700 : 600,
              fontSize: "12px",
              fontFamily: "inherit",
              cursor: "pointer",
            }}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

export default function StepsMatrix({ profile, onOpen }: { profile: ProcedureProfile; onOpen: OpenProvenance }) {
  const [mode, setMode] = useState<ModeFilter>("all");
  const steps = stepsForMode(profile.steps, mode);
  const options: { key: ModeFilter; label: string }[] = [{ key: "all", label: "Tất cả" }, ...profile.modes];
  const filter = profile.steps.length > 0 ? <ModeFilterControl options={options} value={mode} onChange={setMode} /> : undefined;

  return (
    <SectionCard id="phep-kiem-dinh" title="Các phép kiểm định" count={profile.steps.length} aside={filter}>
      {profile.steps.length === 0 ? (
        <EmptyLine>Chưa có dòng Bảng 1 (các phép kiểm định) đã duyệt.</EmptyLine>
      ) : steps.length === 0 ? (
        <EmptyLine>Không có phép nào đánh dấu cho chế độ này trong Bảng 1.</EmptyLine>
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table style={tableStyle}>
            <thead>
              <tr>
                <th style={{ ...thStyle, width: 86 }}>Mục</th>
                <th style={thStyle}>Tên phép kiểm định</th>
                {profile.modes.map((column) => (
                  <th key={column.key} style={{ ...thStyle, width: 104, textAlign: "center", color: column.key === mode ? COLOR.accentDark : COLOR.textMuted }}>
                    {column.label}
                  </th>
                ))}
                <th style={{ ...thStyle, width: 80 }}>
                  <span className="sr-only">Nguồn</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {steps.map((step, index) => {
                const applies = (key: InspectionMode) => step.modes[key];
                return (
                  <tr key={`${step.fact_id}-${index}`}>
                    <td style={{ ...cell, color: COLOR.textSecondary }} className="tabular-nums">
                      {step.section_ref ?? ""}
                    </td>
                    <td style={{ ...cell, color: COLOR.textPrimary, fontWeight: step.depth === 0 ? 600 : 400, paddingLeft: 12 + step.depth * 20 }}>
                      {step.label}
                    </td>
                    {profile.modes.map((column) => (
                      <td key={column.key} style={{ ...cell, textAlign: "center", background: column.key === mode ? COLOR.accentSoft : undefined }}>
                        <span className="sr-only">
                          {applies(column.key) ? "Áp dụng" : "Không áp dụng"} khi kiểm định {column.label.toLowerCase()}
                        </span>
                        {applies(column.key) && (
                          <IcCheck size={16} strokeWidth={2.4} style={{ color: COLOR.accent, display: "inline-block", verticalAlign: "middle" }} />
                        )}
                      </td>
                    ))}
                    <td style={{ ...cell, textAlign: "right" }}>
                      {/* Dòng con bóc từ một ô gộp mở cùng đoạn nguồn với dòng cha. */}
                      <SourceButton cellRef={{ kind: "fact", id: step.fact_id, field: "inspection_step" }} label={step.label} onOpen={onOpen} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </SectionCard>
  );
}
