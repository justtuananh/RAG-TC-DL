import type { CatalogKind, CatalogRow } from "../../types";

// Nhãn và định dạng hiển thị cho bảng danh mục NAS (Pha D1).

export const CATALOG_KINDS: CatalogKind[] = [
  "lab_standard",
  "inspector",
  "procedure_catalog",
  "capability",
];

export const CATALOG_TAB_LABELS: Record<CatalogKind, string> = {
  lab_standard: "Chuẩn mẫu",
  inspector: "Kiểm định viên",
  procedure_catalog: "Danh mục tiêu chuẩn, quy trình",
  capability: "Lĩnh vực công nhận",
};

export const CATALOG_TABLE_TITLES: Record<CatalogKind, string> = {
  lab_standard: "Danh mục chuẩn mẫu, phương tiện đo, phương tiện thử nghiệm",
  inspector: "Danh sách kiểm định viên",
  procedure_catalog: "Danh mục tiêu chuẩn, quy trình áp dụng",
  capability: "Lĩnh vực kiểm định, hiệu chuẩn được công nhận",
};

export const RECOGNITION_LABELS: Record<string, string> = {
  bo_sung_moi: "Bổ sung mới",
  mo_rong: "Mở rộng",
  duy_tri: "Duy trì",
};

function pad2(value: number): string {
  return String(value).padStart(2, "0");
}

/** Hạn KĐ/HC kế tiếp dạng "MM/YYYY"; giá trị dẫn xuất nên luôn ghi "ước tính" ở UI. */
export function formatNextDue(row: CatalogRow): string {
  if (!row.next_due_derived || !row.next_due_year || !row.next_due_month) return "—";
  return `${pad2(row.next_due_month)}/${row.next_due_year}`;
}

/** Quá hạn khi hạn kế tiếp trước tháng hiện tại (so theo tháng, không theo ngày). */
export function isOverdue(row: CatalogRow, now: Date = new Date()): boolean {
  if (!row.next_due_derived || !row.next_due_year || !row.next_due_month) return false;
  const due = row.next_due_year * 12 + (row.next_due_month - 1);
  const current = now.getFullYear() * 12 + now.getMonth();
  return due < current;
}

/** Trường có được kế thừa từ dòng trên do ô ghi "nt" hay không. */
export function isInherited(row: CatalogRow, key: string): boolean {
  return (row.inherited ?? []).includes(key);
}

/** Ngày ISO (card_date) về dd/mm/yyyy, không phụ thuộc múi giờ. */
export function formatCatalogDate(value: string | null | undefined): string {
  if (!value) return "—";
  const [year, month, day] = value.slice(0, 10).split("-");
  if (!year || !month || !day) return value;
  return `${day}/${month}/${year}`;
}

export function joinList(values: string[] | null | undefined): string {
  return values && values.length ? values.join("; ") : "—";
}

export function recognitionLabel(value: string | null | undefined): string {
  if (!value) return "—";
  return RECOGNITION_LABELS[value] ?? value;
}
