import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import rehypeRaw from "rehype-raw";

const REMARK_PLUGINS = [remarkMath];
const REHYPE_PLUGINS = [rehypeKatex, rehypeRaw];

export default function MessageBubble({ message }) {
  const isUser = message.role === "user";
  const isError = message.error;

  if (isUser) {
    return (
      <div className="flex justify-end animate-fade-in-up">
        <div className="max-w-[75%] px-4 py-3 rounded-2xl rounded-tr-md bg-primary-600 text-white text-sm leading-relaxed shadow-sm">
          {message.content}
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start animate-fade-in-up">
      {/* Avatar */}
      <div className="flex-shrink-0 w-7 h-7 rounded-full bg-primary-100 border border-primary-200 flex items-center justify-center text-sm mr-2 mt-1">
        📐
      </div>

      <div className={`max-w-[85%] px-4 py-3 rounded-2xl rounded-tl-md shadow-sm border text-sm leading-relaxed ${
        isError
          ? "bg-red-50 border-red-200 text-red-700"
          : "bg-white border-slate-200 text-slate-800"
      }`}>
        {message.streaming && !message.content ? (
          <TypingIndicator />
        ) : (
          <div className="prose prose-sm max-w-none prose-slate prose-p:my-1 prose-headings:my-2 prose-ul:my-1 prose-li:my-0.5 prose-code:bg-blue-50 prose-code:text-blue-700 prose-code:px-1 prose-code:rounded prose-blockquote:border-slate-300 prose-blockquote:text-slate-600">
            <ReactMarkdown
              remarkPlugins={REMARK_PLUGINS}
              rehypePlugins={REHYPE_PLUGINS}
            >
              {message.content || ""}
            </ReactMarkdown>
          </div>
        )}

        {/* Source chips */}
        {!message.streaming && message.sources && message.sources.length > 0 && (
          <div className="mt-2 pt-2 border-t border-slate-100 flex flex-wrap gap-1">
            {message.sources.map((s) => (
              <span
                key={s.index}
                className="inline-flex items-center gap-1 px-2 py-0.5 bg-blue-50 border border-blue-200 rounded-full text-xs font-medium text-blue-700"
              >
                [{s.index}] <span className="font-mono text-[10px]">{s.file_stem}</span>
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function TypingIndicator() {
  return (
    <div className="flex items-center gap-1 py-1">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="w-1.5 h-1.5 rounded-full bg-slate-400"
          style={{ animation: `typingDot 1.2s infinite ${i * 0.2}s` }}
        />
      ))}
      <style>{`
        @keyframes typingDot {
          0%, 60%, 100% { transform: translateY(0); opacity: 0.5; }
          30% { transform: translateY(-4px); opacity: 1; }
        }
      `}</style>
    </div>
  );
}
