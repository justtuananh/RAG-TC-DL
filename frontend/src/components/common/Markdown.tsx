import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import rehypeRaw from "rehype-raw";

// remark-gfm: bảng `| … |`, danh sách, ~~gạch~~ (nguồn QTKĐ có bảng pipe).
// rehype-raw TRƯỚC rehype-katex: parse HTML thô (chip [n]) rồi mới render math.
// KaTeX khoan dung: công thức lỗi → tô đỏ tại chỗ thay vì vỡ cả khối.
const REMARK = [remarkGfm, remarkMath];
const REHYPE: NonNullable<Parameters<typeof ReactMarkdown>[0]["rehypePlugins"]> = [
  rehypeRaw,
  [rehypeKatex, { throwOnError: false, strict: false, errorColor: "#DC2626" }],
];

export default function Markdown({ children, className }: { children: string; className?: string }) {
  return (
    <div className={className}>
      <ReactMarkdown remarkPlugins={REMARK} rehypePlugins={REHYPE}>
        {children}
      </ReactMarkdown>
    </div>
  );
}
