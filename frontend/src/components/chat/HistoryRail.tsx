import { IcClock, IcPanelOpen, IcPlus } from "../common/icons";

export default function HistoryRail({ onToggle, onNewChat }: { onToggle: () => void; onNewChat: () => void }) {
  return (
    <aside style={{ width: 56, flexShrink: 0, display: "flex", flexDirection: "column", alignItems: "center", gap: 9, padding: "12px 0", background: "#F6F8F7", borderRight: "1px solid #E6EAE8" }}>
      <button
        onClick={onToggle}
        title="Mở lịch sử trò chuyện"
        className="w-9 h-9 rounded-[9px] border-none bg-transparent flex items-center justify-center cursor-pointer text-slate-500 hover:bg-slate-200 hover:text-slate-700"
      >
        <IcPanelOpen size={19} />
      </button>
      <button
        onClick={onNewChat}
        title="Hội thoại mới"
        className="w-9 h-9 rounded-[9px] border-none bg-brand flex items-center justify-center cursor-pointer text-white shadow-[0_2px_6px_rgba(22,163,74,.3)] hover:bg-brand-dark"
      >
        <IcPlus size={17} />
      </button>
      <div style={{ width: 26, height: 1, background: "#E2E8F0", margin: "2px 0" }} />
      <button
        onClick={onToggle}
        title="Xem lịch sử trò chuyện"
        className="w-9 h-9 rounded-[9px] border-none bg-transparent flex items-center justify-center cursor-pointer text-slate-500 hover:bg-slate-200 hover:text-slate-700"
      >
        <IcClock size={18} />
      </button>
    </aside>
  );
}
