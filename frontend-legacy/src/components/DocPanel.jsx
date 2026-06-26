import SourceCard from "./SourceCard.jsx";
import { FileText } from "lucide-react";

export default function DocPanel({ sources }) {
  return (
    <aside className="flex flex-col flex-[4] min-w-0 bg-slate-50" aria-label="Tài liệu nguồn">
      {/* Panel header */}
      <div className="flex-shrink-0 h-12 px-4 flex items-center gap-2 border-b border-slate-200 bg-white">
        <FileText size={15} className="text-slate-500" />
        <span className="text-sm font-semibold text-slate-700">Tài liệu nguồn</span>
        {sources.length > 0 && (
          <span className="ml-auto text-xs bg-blue-100 text-blue-700 font-bold px-2.5 py-0.5 rounded-full">
            {sources.length} nguồn
          </span>
        )}
      </div>

      {/* Source list */}
      <div className="flex-1 overflow-y-auto chat-scrollbar p-3 space-y-3">
        {sources.length === 0 ? (
          <EmptyDocPanel />
        ) : (
          sources.map((source) => (
            <SourceCard key={source.index} source={source} />
          ))
        )}
      </div>
    </aside>
  );
}

function EmptyDocPanel() {
  return (
    <div className="flex flex-col items-center justify-center h-full py-12 text-center">
      <div className="text-4xl mb-3 opacity-40" aria-hidden="true">📄</div>
      <p className="text-sm text-slate-500 font-medium">Kết quả tìm kiếm</p>
      <p className="text-xs text-slate-500 mt-1">sẽ hiển thị ở đây sau khi hỏi</p>
    </div>
  );
}
