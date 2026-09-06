import { useEffect, useState } from "react";
import type { AppState, Conversation, ConvGroup, Tab } from "../../types";
import type { Actions } from "../../store/useAppStore";
import { groupOf } from "../../store/persistence";
import { COLOR, SHADOW } from "../../theme";
import { IcBrand, IcChevronLeft, IcChevronRight, IcFile, IcHelp, IcMessage, IcPencil, IcPin, IcPlus, IcSearch, IcTrash } from "../common/icons";

const NAV_KEY = "nav_collapsed";

function loadCollapsed(): boolean {
  try {
    return localStorage.getItem(NAV_KEY) === "1";
  } catch {
    return false;
  }
}

const NAV_ITEMS: { tab: Tab; label: string; icon: (size: number) => React.ReactNode }[] = [
  { tab: "chat", label: "Trò chuyện", icon: (s) => <IcMessage size={s} /> },
  { tab: "docs", label: "Tài liệu", icon: (s) => <IcFile size={s} /> },
  { tab: "guide", label: "Hướng dẫn", icon: (s) => <IcHelp size={s} /> },
];

const GROUPS: { key: "pinned" | ConvGroup; label: string; pinned: boolean }[] = [
  { key: "pinned", label: "Đã ghim", pinned: true },
  { key: "today", label: "Hôm nay", pinned: false },
  { key: "yesterday", label: "Hôm qua", pinned: false },
  { key: "week", label: "7 ngày qua", pinned: false },
  { key: "older", label: "Cũ hơn", pinned: false },
];

/**
 * Sidebar hợp nhất — điều hướng (Trò chuyện/Tài liệu/Hướng dẫn) + lịch sử trò chuyện
 * trong CÙNG một cột (kiểu ChatGPT/Claude), thay vì hai thanh bên đặt cạnh nhau.
 */
export default function Sidebar({ state, actions }: { state: AppState; actions: Actions }) {
  const [collapsed, setCollapsed] = useState(loadCollapsed);

  useEffect(() => {
    try {
      localStorage.setItem(NAV_KEY, collapsed ? "1" : "0");
    } catch {
      /* noop */
    }
  }, [collapsed]);

  const startNewChat = () => {
    actions.newChat();
    actions.go("chat");
  };

  const showHistory = !collapsed && state.tab === "chat";

  const q = state.histSearch.trim().toLowerCase();
  const match = (c: Conversation) => !q || (c.title + " " + c.snippet).toLowerCase().indexOf(q) >= 0;
  const list = [...state.conversations].filter(match).sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
  const groups = GROUPS.map((g) => ({
    ...g,
    items: list.filter((c) => (g.key === "pinned" ? c.pinned : !c.pinned && groupOf(c.updatedAt) === g.key)),
  })).filter((g) => g.items.length > 0);
  const noneAtAll = state.conversations.length === 0;

  return (
    <aside
      style={{
        flexShrink: 0,
        width: collapsed ? 68 : 272,
        display: "flex",
        flexDirection: "column",
        background: COLOR.sidebarBg,
        borderRight: `1px solid ${COLOR.sidebarBorder}`,
        transition: "width .18s ease",
        overflow: "hidden",
      }}
    >
      {/* brand */}
      <div
        style={{
          flexShrink: 0,
          display: "flex",
          alignItems: "center",
          gap: 11,
          padding: collapsed ? "18px 0 12px" : "18px 14px 12px",
          justifyContent: collapsed ? "center" : "flex-start",
        }}
      >
        <div
          style={{
            flexShrink: 0,
            width: 34,
            height: 34,
            borderRadius: 9,
            background: `linear-gradient(135deg, ${COLOR.accent}, ${COLOR.accentDark})`,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            boxShadow: SHADOW.sidebar,
          }}
        >
          <IcBrand size={18} style={{ color: "#fff" }} />
        </div>
        {!collapsed && (
          <div style={{ display: "flex", flexDirection: "column", lineHeight: 1.2, minWidth: 0 }}>
            <span style={{ fontSize: "14.5px", fontWeight: 700, color: "#fff", whiteSpace: "nowrap" }}>Trợ lý Kiểm định</span>
            <span style={{ fontSize: "10.5px", color: COLOR.sidebarTextMuted, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
              Tra cứu quy trình kiểm định
            </span>
          </div>
        )}
      </div>

      {/* hội thoại mới */}
      <div style={{ flexShrink: 0, padding: collapsed ? "0 0 10px" : "0 12px 10px", display: "flex", justifyContent: collapsed ? "center" : "stretch" }}>
        <button
          onClick={startNewChat}
          title="Bắt đầu hội thoại mới"
          className="inline-flex items-center justify-center gap-[7px] border-none rounded-[10px] font-sans text-[13.5px] font-semibold cursor-pointer hover:brightness-110"
          style={{ width: collapsed ? 38 : "100%", height: 38, background: COLOR.accent, color: "#fff", boxShadow: "0 2px 6px rgba(36,84,224,.3)" }}
        >
          <IcPlus size={16} />
          {!collapsed && "Hội thoại mới"}
        </button>
      </div>

      {/* điều hướng */}
      <nav style={{ flexShrink: 0, display: "flex", flexDirection: "column", gap: 2, padding: "0 10px 8px" }}>
        {NAV_ITEMS.map((it) => {
          const active = state.tab === it.tab;
          return (
            <button
              key={it.tab}
              onClick={() => actions.go(it.tab)}
              title={it.label}
              aria-current={active ? "page" : undefined}
              className="relative flex items-center gap-3 h-[38px] border-none rounded-[9px] font-sans text-[13.5px] font-semibold cursor-pointer transition-colors"
              style={{
                padding: collapsed ? "0" : "0 12px",
                justifyContent: collapsed ? "center" : "flex-start",
                background: active ? COLOR.accent : "transparent",
                color: active ? "#fff" : COLOR.sidebarText,
              }}
              onMouseEnter={(e) => {
                if (!active) e.currentTarget.style.background = COLOR.sidebarHover;
              }}
              onMouseLeave={(e) => {
                if (!active) e.currentTarget.style.background = "transparent";
              }}
            >
              <span style={{ flexShrink: 0, display: "flex" }}>{it.icon(17)}</span>
              {!collapsed && <span style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{it.label}</span>}
            </button>
          );
        })}
      </nav>

      {/* lịch sử trò chuyện — chỉ hiện khi mở rộng + đang ở tab Trò chuyện, tránh 2 thanh bên cạnh nhau */}
      {showHistory ? (
        <>
          <div style={{ flexShrink: 0, margin: "2px 12px 8px", height: 1, background: COLOR.sidebarBorder }} />
          <div style={{ flexShrink: 0, padding: "0 12px 8px" }}>
            <div
              style={{
                fontSize: "10.5px",
                fontWeight: 700,
                letterSpacing: ".06em",
                textTransform: "uppercase",
                color: COLOR.sidebarTextMuted,
                marginBottom: 7,
              }}
            >
              Lịch sử trò chuyện
            </div>
            <div
              className="flex items-center gap-2 rounded-[9px] px-[10px] h-[32px] focus-within:border-brand"
              style={{ background: COLOR.sidebarBgAlt, border: `1px solid ${COLOR.sidebarBorder}` }}
            >
              <IcSearch size={14} style={{ color: COLOR.sidebarTextMuted, flexShrink: 0 }} />
              <input
                value={state.histSearch}
                onChange={(e) => actions.setHistSearch(e.target.value)}
                placeholder="Tìm hội thoại…"
                className="flex-1 min-w-0 border-none outline-none font-sans text-[12.5px] bg-transparent"
                style={{ color: "#fff" }}
              />
            </div>
          </div>

          <div style={{ flex: 1, minHeight: 0, overflowY: "auto", padding: "0 8px 14px" }}>
            {groups.map((g) => (
              <div key={g.key} style={{ marginTop: 6 }}>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                    fontSize: "9.5px",
                    fontWeight: 700,
                    letterSpacing: ".07em",
                    textTransform: "uppercase",
                    color: COLOR.sidebarTextMuted,
                    margin: "0 8px 3px",
                  }}
                >
                  {g.pinned && <IcPin size={11} strokeWidth={1.5} fill={COLOR.highlightStrong} style={{ color: COLOR.highlightStrong }} />}
                  {g.label}
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 1 }}>
                  {g.items.map((c) => (
                    <ConvRow key={c.id} conv={c} state={state} actions={actions} />
                  ))}
                </div>
              </div>
            ))}
            {groups.length === 0 && (
              <div style={{ textAlign: "center", padding: "26px 12px", color: COLOR.sidebarTextMuted, fontSize: "12.5px", lineHeight: 1.6 }}>
                {noneAtAll ? "Chưa có hội thoại. Hãy bắt đầu hỏi — cuộc trò chuyện sẽ tự lưu vào đây." : "Không tìm thấy hội thoại."}
              </div>
            )}
          </div>
        </>
      ) : (
        <div style={{ flex: 1, minHeight: 0 }} />
      )}

      {/* thu gọn / mở rộng */}
      <div style={{ flexShrink: 0, padding: 10, display: "flex", justifyContent: collapsed ? "center" : "flex-end" }}>
        <button
          onClick={() => setCollapsed((v) => !v)}
          title={collapsed ? "Mở rộng menu" : "Thu gọn menu"}
          aria-label={collapsed ? "Mở rộng menu" : "Thu gọn menu"}
          className="w-8 h-8 rounded-[8px] border flex items-center justify-center cursor-pointer transition-colors active:scale-90"
          style={{ borderColor: "rgba(255,255,255,.14)", color: COLOR.sidebarText, background: "transparent" }}
          onMouseEnter={(e) => {
            e.currentTarget.style.borderColor = COLOR.accent;
            e.currentTarget.style.color = "#fff";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.borderColor = "rgba(255,255,255,.14)";
            e.currentTarget.style.color = COLOR.sidebarText;
          }}
        >
          {collapsed ? <IcChevronRight size={14} /> : <IcChevronLeft size={14} />}
        </button>
      </div>
    </aside>
  );
}

function ConvRow({ conv, state, actions }: { conv: Conversation; state: AppState; actions: Actions }) {
  const active = state.activeConvId === conv.id;
  const renaming = state.renamingConv === conv.id;

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => actions.openConv(conv)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          actions.openConv(conv);
        }
      }}
      title={conv.title}
      className="flex items-center gap-2 px-2 py-[6px] rounded-lg cursor-pointer"
      style={{ background: active ? "rgba(36,84,224,.22)" : "transparent" }}
      onMouseEnter={(e) => {
        if (!active) e.currentTarget.style.background = COLOR.sidebarHover;
      }}
      onMouseLeave={(e) => {
        if (!active) e.currentTarget.style.background = "transparent";
      }}
    >
      <IcMessage size={14} style={{ flexShrink: 0, color: active ? COLOR.accentOnDark : COLOR.sidebarTextMuted }} />
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
            className="w-full outline-none rounded-md px-[6px] py-[2px] font-sans text-[12.5px] font-semibold"
            style={{ background: COLOR.sidebarBgAlt, border: `1px solid ${COLOR.accent}`, color: "#fff" }}
          />
        ) : (
          <div
            className="text-[12.5px] whitespace-nowrap overflow-hidden text-ellipsis"
            style={{ fontWeight: active ? 700 : 500, color: active ? "#fff" : COLOR.sidebarText }}
          >
            {conv.title}
          </div>
        )}
      </div>
      <div style={{ display: "flex", gap: 1, flexShrink: 0 }}>
        <button
          onClick={(e) => actions.togglePin(e, conv.id)}
          title={conv.pinned ? "Bỏ ghim" : "Ghim hội thoại"}
          className="w-[24px] h-[24px] rounded-md border-none bg-transparent flex items-center justify-center cursor-pointer"
          style={{ color: conv.pinned ? COLOR.highlightStrong : COLOR.sidebarTextMuted }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = COLOR.sidebarHover;
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = "transparent";
          }}
        >
          <IcPin size={13} />
        </button>
        <button
          onClick={(e) => actions.startRenameConv(e, conv.id)}
          title="Đổi tên"
          className="w-[24px] h-[24px] rounded-md border-none bg-transparent flex items-center justify-center cursor-pointer"
          style={{ color: COLOR.sidebarTextMuted }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = COLOR.sidebarHover;
            e.currentTarget.style.color = "#fff";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = "transparent";
            e.currentTarget.style.color = COLOR.sidebarTextMuted;
          }}
        >
          <IcPencil size={12} />
        </button>
        <button
          onClick={(e) => actions.requestDeleteConv(e, conv.id)}
          title="Xoá"
          className="w-[24px] h-[24px] rounded-md border-none bg-transparent flex items-center justify-center cursor-pointer"
          style={{ color: COLOR.sidebarTextMuted }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = "rgba(220,38,38,.18)";
            e.currentTarget.style.color = COLOR.dangerOnDark;
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = "transparent";
            e.currentTarget.style.color = COLOR.sidebarTextMuted;
          }}
        >
          <IcTrash size={12} />
        </button>
      </div>
    </div>
  );
}
