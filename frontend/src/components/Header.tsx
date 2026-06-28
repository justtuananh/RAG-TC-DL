import type { CSSProperties } from "react";
import type { LlmStatus, Tab } from "../types";
import { IcBrand, IcFile, IcHelp, IcMessage, IcSettings } from "./common/icons";

interface Props {
  tab: Tab;
  llmStatus: LlmStatus;
  onGo: (tab: Tab) => void;
  onOpenLlm: () => void;
}

const STATUS = {
  active: { label: "Đang hoạt động", color: "#006130", bg: "#f2f3ff", bd: "#dae2fd", dot: "#006130", spin: false },
  checking: { label: "Đang kiểm tra…", color: "#B45309", bg: "#FFFBEB", bd: "#FDE68A", dot: "#F59E0B", spin: true },
  error: { label: "Mất kết nối", color: "#DC2626", bg: "#FEF2F2", bd: "#FECACA", dot: "#EF4444", spin: false },
  none: { label: "Chưa kết nối", color: "#6f7a6f", bg: "#eaedff", bd: "#becabd", dot: "#6f7a6f", spin: false },
} as const;

function Tab_({ active, icon, label, title, onClick }: { active: boolean; icon: React.ReactNode; label: string; title: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      title={title}
      className="relative inline-flex items-center gap-[7px] h-[42px] px-[14px] border-none bg-transparent rounded-[9px] font-sans text-[14px] font-semibold cursor-pointer hover:bg-[#eaedff]"
      style={{ color: active ? "#006130" : "#3f4940" }}
    >
      {icon}
      {label}
      {active && <span style={{ position: "absolute", left: 12, right: 12, bottom: -9, height: 3, borderRadius: "3px 3px 0 0", background: "#006130" }} />}
    </button>
  );
}

export default function Header({ tab, llmStatus, onGo, onOpenLlm }: Props) {
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
        height: 62,
        padding: "0 20px",
        background: "#fff",
        borderBottom: "1px solid #becabd",
        boxShadow: "0 1px 2px rgba(29,45,35,.04)",
        zIndex: 20,
      }}
    >
      {/* logo + title */}
      <div style={{ display: "flex", alignItems: "center", gap: 11 }}>
        <div
          style={{
            width: 37,
            height: 37,
            borderRadius: 10,
            background: "linear-gradient(135deg,#107c41,#006130)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            boxShadow: "0 3px 8px rgba(0,97,48,.35)",
          }}
        >
          <IcBrand size={20} style={{ color: "#fff" }} />
        </div>
        <div style={{ display: "flex", flexDirection: "column", lineHeight: 1.2 }}>
          <span style={{ fontSize: "15.5px", fontWeight: 700, color: "#131b2e" }}>Trợ lý Kiểm định</span>
          <span style={{ fontSize: "11.5px", color: "#6f7a6f" }}>Tra cứu quy trình kiểm định đo lường</span>
        </div>
      </div>

      {/* tabs */}
      <nav style={{ display: "flex", alignItems: "center", gap: 2, marginLeft: 12 }}>
        <Tab_ active={tab === "chat"} onClick={() => onGo("chat")} title="Hỏi đáp với trợ lý" label="Trò chuyện" icon={<IcMessage size={17} />} />
        <Tab_ active={tab === "docs"} onClick={() => onGo("docs")} title="Tải lên & quản lý tài liệu" label="Tài liệu" icon={<IcFile size={17} />} />
        <Tab_ active={tab === "guide"} onClick={() => onGo("guide")} title="Hướng dẫn sử dụng" label="Hướng dẫn" icon={<IcHelp size={17} />} />
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
