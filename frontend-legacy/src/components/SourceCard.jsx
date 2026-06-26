import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import { ChevronDown, ChevronUp } from "lucide-react";

const KIND_ICON = { formula: "∑", table: "⊞", paragraph: "¶", section: "§" };
const REMARK_PLUGINS = [remarkMath];
const REHYPE_PLUGINS = [rehypeKatex];

function ScoreBadge({ score }) {
  const color =
    score > 0.3
      ? "text-green-600 bg-green-50 border-green-200"
      : score > 0.1
      ? "text-amber-600 bg-amber-50 border-amber-200"
      : "text-slate-500 bg-slate-50 border-slate-200";

  return (
    <span className={`flex items-center gap-0.5 text-[11px] font-bold px-1.5 py-0.5 rounded border ${color}`}>
      <svg className="h-2.5 w-2.5" fill="currentColor" viewBox="0 0 20 20">
        <path
          clipRule="evenodd"
          fillRule="evenodd"
          d="M14.707 12.707a1 1 0 01-1.414 0L10 9.414l-3.293 3.293a1 1 0 01-1.414-1.414l4-4a1 1 0 011.414 0l4 4a1 1 0 010 1.414z"
        />
      </svg>
      {score.toFixed(3)}
    </span>
  );
}

function FolderIcon() {
  return (
    <svg className="h-3 w-3 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="2"
      />
    </svg>
  );
}

export default function SourceCard({ source }) {
  const [expanded, setExpanded] = useState(false);
  const { index, file_stem, section_path, kind, rerank_score, child_text, parent_text } = source;

  const hasParentContext = parent_text && parent_text !== child_text;

  return (
    <div className="border border-slate-200 rounded-xl bg-white shadow-sm hover:border-blue-300 hover:shadow-md transition-all overflow-hidden">
      <div className="p-3.5 space-y-2.5">

        {/* Row 1: index + file name + kind + score */}
        <div className="flex items-center gap-2">
          <span className="text-blue-600 font-bold text-xs w-5 flex-shrink-0">[{index}]</span>
          <code className="bg-blue-100 text-blue-800 px-2 py-0.5 rounded text-[11px] font-mono font-semibold truncate max-w-[140px]">
            {file_stem}
          </code>
          <span className="text-slate-500 text-[11px]">
            {KIND_ICON[kind] || "·"} {kind}
          </span>
          <div className="ml-auto flex-shrink-0">
            <ScoreBadge score={rerank_score} />
          </div>
        </div>

        {/* Row 2: section path */}
        <div className="flex items-center gap-1 text-[11px] text-slate-500">
          <FolderIcon />
          <span className="truncate" title={section_path}>
            {section_path.replace(/ > /g, " › ")}
          </span>
        </div>

        {/* Row 3: highlighted chunk */}
          {/* <div className="bg-teal-700 text-white rounded-lg p-3">
            <div className="text-[10px] font-bold opacity-75 mb-1.5 uppercase tracking-wider">
              Đoạn trích xuất
            </div>
            <div className="text-sm leading-relaxed text-white prose prose-xs max-w-none prose-invert prose-p:my-0.5 prose-code:bg-teal-600 prose-code:text-white">
              <ReactMarkdown remarkPlugins={REMARK_PLUGINS} rehypePlugins={REHYPE_PLUGINS}>
                {child_text}
              </ReactMarkdown>
            </div>
          </div> */}

        {/* Row 4: expand button + parent context */}
        {hasParentContext && (
          <>
            <button
              onClick={() => setExpanded(!expanded)}
              className="flex items-center gap-1 text-xs text-blue-600 font-medium hover:text-blue-800 transition-colors py-1.5"
              aria-expanded={expanded}
              aria-label={expanded ? "Thu gọn tài liệu nguồn" : "Xem tài liệu nguồn đầy đủ"}
            >
              {expanded ? <ChevronUp size={13} aria-hidden="true" /> : <ChevronDown size={13} aria-hidden="true" />}
              {expanded ? "Thu gọn" : "Xem"}
            </button>

            {expanded && (
              <div className="pt-2 border-t border-slate-100 text-[11px] text-slate-700 leading-relaxed">
                <div className="prose prose-xs max-w-none prose-slate prose-headings:text-sm prose-headings:font-semibold prose-headings:leading-snug prose-headings:mt-1 prose-headings:mb-0.5 prose-p:my-1 prose-code:bg-blue-50 prose-code:text-blue-700 prose-code:px-0.5 prose-code:rounded">
                  <ReactMarkdown remarkPlugins={REMARK_PLUGINS} rehypePlugins={REHYPE_PLUGINS}>
                    {parent_text}
                  </ReactMarkdown>
                </div>
              </div>
            )}
          </>
        )}

      </div>
    </div>
  );
}


