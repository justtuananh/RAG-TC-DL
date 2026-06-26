import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import rehypeRaw from "rehype-raw";

// rehype-raw TRƯỚC rehype-katex: parse HTML thô (chip [n]) rồi mới render math.
const REMARK = [remarkMath];
const REHYPE = [rehypeRaw, rehypeKatex];

export default function Markdown({ children, className }: { children: string; className?: string }) {
  return (
    <div className={className}>
      <ReactMarkdown remarkPlugins={REMARK} rehypePlugins={REHYPE}>
        {children}
      </ReactMarkdown>
    </div>
  );
}
