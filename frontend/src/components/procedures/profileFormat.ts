import type { DataCellRef, InspectionMode, ProcedureFact, ProcedureProfile, ProcedureStep } from "../../types";

// Hàm thuần cho trang Hồ sơ QTKĐ: không đổi nội dung nguyên văn, chỉ trình bày.

export type ModeFilter = InspectionMode | "all";

/** "QTKĐ 1.061:2021": cách ghi số hiệu quen thuộc của văn bản ĐLVN. */
export function procedureCode(procedure: { number: string; year: number | null }): string {
  return procedure.year ? `QTKĐ ${procedure.number}:${procedure.year}` : `QTKĐ ${procedure.number}`;
}

/** Các phép áp dụng cho một chế độ kiểm định (theo dấu "+" của Bảng 1). */
export function stepsForMode(steps: ProcedureStep[], mode: ModeFilter): ProcedureStep[] {
  return mode === "all" ? steps : steps.filter((step) => step.modes[mode]);
}

/**
 * Markdown hiển thị một công thức: chuỗi đã có `$` giữ nguyên; LaTeX trần được bọc thành
 * khối `$$...$$`. Không bao giờ sửa nội dung LaTeX (công thức phải khớp ảnh trong nguồn).
 */
export function formulaMarkdown(value: string | null | undefined): string {
  const text = (value ?? "").trim();
  if (!text) return "";
  return text.includes("$") ? text : `$$\n${text}\n$$`;
}

/** Tổng số dòng tri thức đã duyệt của QTKĐ (không tính biên bản trong sổ cái). */
export function knowledgeTotal(profile: ProcedureProfile): number {
  const parameters = profile.parameters.reduce((sum, group) => sum + group.items.length, 0);
  return parameters + profile.conditions.length + profile.steps.length + profile.formulas.length + profile.standards.length + profile.terms.length;
}

/** Tham chiếu nguồn của một dữ kiện (mở theo id dữ kiện, tô đúng giá trị). */
export function factRef(fact: ProcedureFact): DataCellRef {
  return { kind: "fact", id: fact.id, field: fact.fact_kind };
}

/** Tham chiếu nguồn theo extraction (phương tiện Bảng 2, thuật ngữ). */
export function extractionRef(extractionId: number, field: string): DataCellRef {
  return { kind: "extraction", id: extractionId, field };
}

/**
 * Ô bảng nhiều dòng trong nguồn được bộ trích nối bằng " / " (có khoảng trắng hai bên).
 * Tách lại để hiển thị đúng bố cục ô gốc; "/" liền chữ (píttông/xylanh, 1/4) giữ nguyên.
 */
export function cellLines(value: string | null | undefined): string[] {
  const text = (value ?? "").trim();
  return text
    ? text
        .split(" / ")
        .map((line) => line.trim())
        .filter(Boolean)
    : [];
}
