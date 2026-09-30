import { useEffect, useMemo, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import { locateQuote } from "../knowledge/highlight";
import rehypeHighlightRange, { HIGHLIGHT_CLASS, type HighlightRange } from "./rehypeHighlightRange";

// Mục nguồn (Markdown đã trích từ .docx) render đúng định dạng: bảng pipe thành
// bảng thật, `$LaTeX$` qua KaTeX - kèm đoạn trích được tô sáng và tự cuộn tới.
// KHÔNG bật rehype-raw: HTML thô trong nguồn bị bỏ qua, không bao giờ được chèn.

const REMARK = [remarkGfm, remarkMath];

type RehypePlugins = NonNullable<Parameters<typeof ReactMarkdown>[0]["rehypePlugins"]>;

interface Props {
  text: string;
  quote?: string | null;
  start?: number | null;
  end?: number | null;
  maxHeight?: number;
}

export default function HighlightedMarkdown({ text, quote, start, end, maxHeight = 340 }: Props) {
  const boxRef = useRef<HTMLDivElement>(null);
  const range = useMemo<HighlightRange | null>(() => {
    const parts = locateQuote(text, quote, start, end);
    return parts.match ? { start: parts.before.length, end: parts.before.length + parts.match.length } : null;
  }, [text, quote, start, end]);
  const rehype = useMemo<RehypePlugins>(
    () => [
      [rehypeHighlightRange, { source: text, range }],
      [rehypeKatex, { throwOnError: false, strict: false, errorColor: "#DC2626" }],
    ],
    [text, range],
  );

  useEffect(() => {
    const box = boxRef.current;
    const first = box?.querySelector(`mark.${HIGHLIGHT_CLASS}`);
    if (!box || !first) return;
    const offset = first.getBoundingClientRect().top - box.getBoundingClientRect().top;
    box.scrollTop += offset - box.clientHeight / 3;
  }, [rehype]);

  return (
    <div ref={boxRef} className="md-doc md-source" style={{ maxHeight, overflowY: "auto" }}>
      <ReactMarkdown remarkPlugins={REMARK} rehypePlugins={rehype}>
        {text}
      </ReactMarkdown>
    </div>
  );
}
