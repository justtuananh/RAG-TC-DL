import type { DocItem, DocStatus } from "../../types";
import { COLOR } from "../../theme";

// Kiểu dáng + nhãn trạng thái tài liệu — dùng chung giữa DocRow (thẻ) và DocTableRow (bảng).

export const STATUS_STYLE: Record<DocStatus, { bar: string; bg: string; color: string; border: string }> = {
  ready: { bar: COLOR.success, bg: COLOR.successBg, color: COLOR.success, border: COLOR.successBorder },
  processing: { bar: COLOR.warning, bg: COLOR.warningBg, color: COLOR.warning, border: COLOR.warningBorder },
  pending: { bar: COLOR.neutral, bg: COLOR.neutralBg, color: COLOR.neutral, border: COLOR.neutralBorder },
  error: { bar: COLOR.danger, bg: COLOR.dangerBg, color: COLOR.danger, border: COLOR.dangerBorder },
};

export const STATUS_TAB_LABEL: Record<DocStatus, string> = {
  ready: "Sẵn sàng",
  processing: "Đang xử lý",
  pending: "Chờ xử lý",
  error: "Lỗi",
};

export function statusLabel(doc: Pick<DocItem, "status" | "progress" | "error">): string {
  switch (doc.status) {
    case "ready":
      return "Đã sẵn sàng";
    case "processing":
      return `Đang xử lý ${doc.progress || 0}%`;
    case "pending":
      return "Chưa xử lý";
    default:
      return "Lỗi xử lý";
  }
}
