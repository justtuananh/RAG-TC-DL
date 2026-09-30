import type { SourceLocation } from "../../types";
import { COLOR } from "../../theme";
import { documentPreviewUrl } from "../../services/liveApi";
import XlsxExcerpt from "../docs/xlsx/XlsxExcerpt";
import HighlightedMarkdown from "./HighlightedMarkdown";
import QuoteTable from "./QuoteTable";

// "Đoạn nguyên văn" (P1) hiển thị ĐÚNG định dạng tài liệu gốc, dùng chung cho ngăn
// xuất xứ ô số và hàng đợi duyệt tri thức:
//   • QTKĐ (.docx → Markdown): mục nguồn với bảng/công thức thật, trích dẫn tô sáng;
//   • biên bản Excel: lưới ô gốc quanh dòng nguồn, ô chứa giá trị viền đậm;
//   • còn lại (biên bản Word, chưa định vị được): trích dẫn dựng lại thành bảng ô.

export interface SourceExcerptProps {
  fileStem?: string | null;
  sectionText?: string | null;
  quote?: string | null;
  quoteStart?: number | null;
  quoteEnd?: number | null;
  location?: SourceLocation | null;
  /** giá trị cần tô trong lưới ô / bảng trích dẫn */
  value?: string | null;
  maxHeight?: number;
}

const paper = {
  background: COLOR.surface,
  border: `1px solid ${COLOR.border}`,
  borderRadius: 8,
  padding: "4px 16px",
} as const;

export default function SourceExcerpt({ fileStem, sectionText, quote, quoteStart, quoteEnd, location, value, maxHeight = 340 }: SourceExcerptProps) {
  if (sectionText) {
    return (
      <div style={paper}>
        <HighlightedMarkdown text={sectionText} quote={quote} start={quoteStart} end={quoteEnd} maxHeight={maxHeight} />
      </div>
    );
  }
  const fallback = quote ? (
    <QuoteTable quote={quote} value={value} maxHeight={maxHeight} />
  ) : (
    <div style={{ fontSize: 12.5, color: COLOR.textMuted }}>Không có nguyên văn.</div>
  );
  if (location && fileStem) return <XlsxExcerpt fileUrl={documentPreviewUrl(fileStem)} location={location} fallback={fallback} />;
  return fallback;
}
