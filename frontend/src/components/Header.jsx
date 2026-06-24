import { Square, Trash2, Activity } from "lucide-react";

export default function Header({ onClear, hasMessages }) {
  return (
    <header className="flex-shrink-0 h-16 bg-white border-b border-slate-200 flex items-center px-6 gap-4 shadow-sm z-10">
      {/* Logo + Title */}
      <div className="flex items-center gap-3">
        <div>
          <h1 className="text-xl font-bold text-slate-900 leading-tight">QTKĐ Chatbot</h1>
          <p className="text-xs text-slate-500 leading-tight">Tra cứu quy trình kiểm định đo lường</p>
        </div>
      </div>

      <div className="flex-1" />

      {/* Online indicator */}
      <div className="flex items-center gap-1.5 px-3 py-1.5 bg-green-50 border border-green-200 rounded-full">
        <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" aria-hidden="true" />
        <span className="text-xs font-medium text-green-700">Đang hoạt động</span>
      </div>

      {/* Clear button */}
      {hasMessages && (
        <button
          onClick={onClear}
          className="flex items-center gap-1.5 px-3 min-h-[44px] text-xs font-medium bg-white text-slate-600 hover:text-red-600 hover:bg-red-50 border border-slate-200 rounded-lg transition-colors"
        >
          <Trash2 size={13} />
          Xóa lịch sử
        </button>
      )}
    </header>
  );
}
