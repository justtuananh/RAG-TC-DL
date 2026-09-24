import { COLOR } from "../../theme";
import { locateQuote } from "./highlight";

/**
 * Đoạn nguyên văn của mục với trích dẫn được tô sáng — dùng lại ngôn ngữ thị giác
 * của `SourcePanel` (nền accentSoft, viền accent) nhưng tô đậm đúng `quote` bằng
 * màu highlight. Toàn bộ văn bản render dưới dạng text node nên an toàn tuyệt đối
 * với nội dung nguồn (không `dangerouslySetInnerHTML`).
 */
export default function QuoteHighlight({
  text,
  quote,
  start,
  end,
}: {
  text: string;
  quote?: string | null;
  start?: number | null;
  end?: number | null;
}) {
  const { before, match, after } = locateQuote(text, quote, start, end);
  return (
    <span style={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
      {before}
      {match && (
        <mark
          style={{
            background: COLOR.highlight,
            borderBottom: `2px solid ${COLOR.highlightBorder}`,
            color: "inherit",
            padding: "0 2px",
            borderRadius: 3,
          }}
        >
          {match}
        </mark>
      )}
      {after}
    </span>
  );
}
