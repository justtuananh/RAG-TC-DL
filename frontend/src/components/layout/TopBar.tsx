import type { CSSProperties } from "react";
import type { LlmStatus, Tab } from "../../types";
import { COLOR } from "../../theme";
import { IcChevronRight, IcSettings } from "../common/icons";

interface Props {
  tab: Tab;
  llmStatus: LlmStatus;
  onGo: (tab: Tab) => void;
  onOpenLlm: () => void;
  /** Tên tài liệu đang xem — thêm nhánh thứ 3 vào breadcrumb khi có */
  docName?: string;
}

const TAB_LABEL: Record<Tab, string> = {
  chat: "Trò chuyện",
  docs: "Tài liệu",
  guide: "Hướng dẫn",
};

const STATUS = {
  active: { label: "Đang hoạt động", color: COLOR.success, bg: COLOR.successBg, bd: COLOR.successBorder, dot: COLOR.success, spin: false },
  checking: { label: "Đang kiểm tra…", color: COLOR.warning, bg: COLOR.warningBg, bd: COLOR.warningBorder, dot: "#F59E0B", spin: true },
  error: { label: "Mất kết nối", color: COLOR.danger, bg: COLOR.dangerBg, bd: COLOR.dangerBorder, dot: "#EF4444", spin: false },
  none: { label: "Chưa kết nối", color: COLOR.neutral, bg: COLOR.neutralBg, bd: COLOR.neutralBorder, dot: COLOR.neutral, spin: false },
} as const;

export default function TopBar({ tab, llmStatus, onGo, onOpenLlm, docName }: Props) {
  const m = STATUS[llmStatus];
  const btnStyle: CSSProperties = {
    display: "inline-flex",
    alignItems: "center",
    gap: 7,
    padding: "7px 12px",
    background: m.bg,
    border: `1px solid ${m.bd}`,
    borderRadius: 9999,
    fontSize: "12.5px",
    fontWeight: 600,
    color: m.color,
    cursor: "pointer",
  };

  return (
    <header
      style={{
        flexShrink: 0,
        display: "flex",
        alignItems: "center",
        gap: 16,
        height: 56,
        padding: "0 20px",
        background: COLOR.surface,
        borderBottom: `1px solid ${COLOR.border}`,
        boxShadow: "0 1px 2px rgba(16,24,40,.05)",
        zIndex: 20,
      }}
    >
      {/* breadcrumb */}
      <nav aria-label="Breadcrumb" style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "13px", minWidth: 0 }}>
        <button
          onClick={() => onGo("chat")}
          className="border-none bg-transparent font-sans cursor-pointer p-0"
          style={{ color: tab === "chat" ? COLOR.textPrimary : COLOR.textMuted, fontWeight: tab === "chat" ? 700 : 500 }}
        >
          Tổng quan
        </button>
        {tab !== "chat" && (
          <>
            <IcChevronRight size={12} style={{ color: COLOR.border, flexShrink: 0 }} />
            <span style={{ color: docName ? COLOR.textMuted : COLOR.textPrimary, fontWeight: docName ? 500 : 700, whiteSpace: "nowrap" }}>
              {TAB_LABEL[tab]}
            </span>
          </>
        )}
        {docName && (
          <>
            <IcChevronRight size={12} style={{ color: COLOR.border, flexShrink: 0 }} />
            <span style={{ color: COLOR.textPrimary, fontWeight: 700, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{docName}</span>
          </>
        )}
      </nav>

      <div style={{ flex: 1 }} />

      {/* LLM status */}
      <button onClick={onOpenLlm} title="Cấu hình mô hình ngôn ngữ (LLM)" className="hover:brightness-[0.97] font-sans" style={btnStyle}>
        {m.spin ? (
          <span
            className="animate-spin"
            style={{ width: 13, height: 13, flexShrink: 0, border: `2px solid ${m.bd}`, borderTopColor: m.color, borderRadius: "50%" }}
          />
        ) : (
          <span
            className={llmStatus === "active" ? "animate-pulseDot" : ""}
            style={{ width: 8, height: 8, borderRadius: 9999, flexShrink: 0, background: m.dot }}
          />
        )}
        {m.label}
        <IcSettings size={13} strokeWidth={2} style={{ opacity: 0.55, flexShrink: 0 }} />
      </button>
    </header>
  );
}
