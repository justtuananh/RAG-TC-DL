import type { AppState, Conversation, ConvGroup } from "../../types";
import type { Actions } from "../../store/useAppStore";
import { groupOf } from "../../store/persistence";
import { IcMessage, IcPanelClose, IcPencil, IcPin, IcPlus, IcSearch, IcTrash } from "../common/icons";

const GROUPS: { key: "pinned" | ConvGroup; label: string; pinned: boolean }[] = [
  { key: "pinned", label: "Đã ghim", pinned: true },
  { key: "today", label: "Hôm nay", pinned: false },
  { key: "yesterday", label: "Hôm qua", pinned: false },
  { key: "week", label: "7 ngày qua", pinned: false },
  { key: "older", label: "Cũ hơn", pinned: false },
];

export default function HistorySidebar({ state, actions }: { state: AppState; actions: Actions }) {
  const q = state.histSearch.trim().toLowerCase();
  const match = (c: Conversation) => !q || (c.title + " " + c.snippet).toLowerCase().indexOf(q) >= 0;
  const list = [...state.conversations].filter(match).sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
  const groups = GROUPS.map((g) => ({
    ...g,
    items: list.filter((c) => (g.key === "pinned" ? c.pinned : !c.pinned && groupOf(c.updatedAt) === g.key)),
  })).filter((g) => g.items.length > 0);
  const noneAtAll = state.conversations.length === 0;

  return (
    <aside style={{ width: 278, flexShrink: 0, display: "flex", flexDirection: "column", background: "#F6F8F7", borderRight: "1px solid #E6EAE8" }}>
      <div style={{ padding: "9px 10px 6px", display: "flex", flexDirection: "column", gap: 7 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: "12.5px", fontWeight: 700, color: "#334155", flex: 1, letterSpacing: ".01em" }}>Lịch sử trò chuyện</span>
          <button
            onClick={actions.toggleSidebar}
            title="Thu gọn thanh bên"
            className="w-[30px] h-[30px] rounded-lg border-none bg-transparent flex items-center justify-center cursor-pointer text-slate-500 hover:bg-slate-200 hover:text-slate-700"
          >
            <IcPanelClose size={18} />
          </button>
        </div>

        <button
          onClick={actions.newChat}
          title="Bắt đầu hội thoại mới"
          className="inline-flex items-center justify-center gap-[7px] h-[34px] border border-brand bg-white rounded-[9px] font-sans text-[13.5px] font-semibold text-brand-dark cursor-pointer hover:bg-brand hover:text-white"
        >
          <IcPlus size={16} /> Hội thoại mới
        </button>

        <div className="flex items-center gap-2 bg-white border border-slate-200 rounded-[9px] px-[11px] h-[33px] focus-within:border-brand focus-within:shadow-[0_0_0_3px_#DCFCE7]">
          <IcSearch size={15} style={{ color: "#94A3B8" }} />
          <input
            value={state.histSearch}
            onChange={(e) => actions.setHistSearch(e.target.value)}
            placeholder="Tìm hội thoại…"
            className="flex-1 min-w-0 border-none outline-none font-sans text-[13px] text-slate-800 bg-transparent"
          />
        </div>
      </div>

      <div style={{ flex: 1, overflowY: "auto", padding: "2px 8px 14px" }}>
        {groups.map((g) => (
          <div key={g.key} style={{ marginTop: 7 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "10px", fontWeight: 700, letterSpacing: ".07em", textTransform: "uppercase", color: "#94A3B8", margin: "0 8px 3px" }}>
              {g.pinned && <IcPin size={11} strokeWidth={1.5} fill="#F59E0B" style={{ color: "#F59E0B" }} />}
              {g.label}
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 1 }}>
              {g.items.map((c) => (
                <Row key={c.id} conv={c} state={state} actions={actions} />
              ))}
            </div>
          </div>
        ))}
        {groups.length === 0 && (
          <div style={{ textAlign: "center", padding: "30px 14px", color: "#94A3B8", fontSize: "13px", lineHeight: 1.6 }}>
            {noneAtAll ? "Chưa có hội thoại. Hãy bắt đầu hỏi — cuộc trò chuyện sẽ tự lưu vào đây." : "Không tìm thấy hội thoại."}
          </div>
        )}
      </div>
    </aside>
  );
}

function Row({ conv, state, actions }: { conv: Conversation; state: AppState; actions: Actions }) {
  const active = state.activeConvId === conv.id;
  const renaming = state.renamingConv === conv.id;

  return (
    <div
      onClick={() => actions.openConv(conv)}
      title={conv.title}
      className={
        "flex items-center gap-2 px-2 py-[5px] rounded-lg cursor-pointer " + (active ? "bg-[#DCFCE7]" : "hover:bg-[#EAEFEC]")
      }
    >
      <IcMessage size={15} style={{ flexShrink: 0, color: active ? "#16A34A" : "#94A3B8" }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        {renaming ? (
          <input
            autoFocus
            value={conv.title}
            onClick={(e) => e.stopPropagation()}
            onChange={(e) => actions.renameConv(conv.id, e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                actions.commitRenameConv();
              }
            }}
            onBlur={actions.commitRenameConv}
            className="w-full border border-brand outline-none rounded-md px-[6px] py-[3px] font-sans text-[13px] font-semibold text-slate-900 shadow-[0_0_0_2px_#DCFCE7]"
          />
        ) : (
          <div
            className="text-[13px] whitespace-nowrap overflow-hidden text-ellipsis"
            style={{ fontWeight: active ? 700 : 500, color: active ? "#15803D" : "#334155" }}
          >
            {conv.title}
          </div>
        )}
      </div>
      <div style={{ display: "flex", gap: 1, flexShrink: 0 }}>
        <button
          onClick={(e) => actions.togglePin(e, conv.id)}
          title={conv.pinned ? "Bỏ ghim" : "Ghim hội thoại"}
          className="w-[26px] h-[26px] rounded-md border-none bg-transparent flex items-center justify-center cursor-pointer hover:bg-[#DCFCE7]"
          style={{ color: conv.pinned ? "#F59E0B" : "#A8B2AC" }}
        >
          <IcPin size={14} />
        </button>
        <button
          onClick={(e) => actions.startRenameConv(e, conv.id)}
          title="Đổi tên"
          className="w-[26px] h-[26px] rounded-md border-none bg-transparent flex items-center justify-center cursor-pointer text-[#A8B2AC] hover:bg-slate-200 hover:text-slate-700"
        >
          <IcPencil size={13} />
        </button>
        <button
          onClick={(e) => actions.requestDeleteConv(e, conv.id)}
          title="Xoá"
          className="w-[26px] h-[26px] rounded-md border-none bg-transparent flex items-center justify-center cursor-pointer text-[#A8B2AC] hover:bg-[#FEE2E2] hover:text-[#DC2626]"
        >
          <IcTrash size={13} />
        </button>
      </div>
    </div>
  );
}
