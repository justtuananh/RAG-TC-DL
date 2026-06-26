import type { Message } from "../../types";
import type { Actions } from "../../store/useAppStore";
import Markdown from "../common/Markdown";
import { IcBrand, IcCheck, IcCopy, IcRefresh, IcThumbDown, IcThumbUp } from "../common/icons";

interface Props {
  message: Message;
  isLast: boolean;
  proc: boolean;
  actions: Actions;
  pinnedRef?: (el: HTMLElement | null) => void;
}

// Thay [n] (chữ) → nút chip bấm được (render qua rehype-raw, bắt click theo uỷ quyền).
function withCiteButtons(md: string): string {
  return md.replace(/\[(\d+)\]/g, '<button class="cite-chip" data-cite="$1">[$1]</button>');
}

export default function MessageBubble({ message, isLast, proc, actions, pinnedRef }: Props) {
  if (message.role === "user") {
    return (
      <div ref={pinnedRef} style={{ display: "flex", justifyContent: "flex-end", animation: "fadeUp .25s ease-out" }}>
        <div style={{ maxWidth: "80%", padding: "11px 15px", borderRadius: "16px 16px 5px 16px", background: "#16A34A", color: "#fff", fontSize: "14px", lineHeight: 1.55, boxShadow: "0 2px 5px rgba(22,163,74,.22)" }}>
          {message.text}
        </div>
      </div>
    );
  }

  const md = message.markdown ?? "";
  const isErr = !!message.error;
  const showRegen = isLast && !proc && !message.streaming;
  const plain = md.replace(/<[^>]+>/g, "");

  const onBubbleClick = (e: React.MouseEvent) => {
    const el = (e.target as HTMLElement).closest("[data-cite]");
    if (el) actions.openCite(el.getAttribute("data-cite") || "1");
  };

  return (
    <div ref={pinnedRef} style={{ display: "flex", gap: 10, alignItems: "flex-start", animation: "fadeUp .25s ease-out" }}>
      <div style={{ flexShrink: 0, width: 32, height: 32, borderRadius: 9999, background: "#DCFCE7", border: "1px solid #BBF7D0", display: "flex", alignItems: "center", justifyContent: "center", marginTop: 2 }}>
        <IcBrand size={17} style={{ color: "#16A34A" }} />
      </div>

      <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: 9, alignItems: "flex-start" }}>
        {/* answer bubble */}
        <div
          onClick={onBubbleClick}
          style={{
            maxWidth: "100%",
            padding: "13px 16px",
            borderRadius: "16px 16px 16px 5px",
            background: isErr ? "#FEF2F2" : "#F6F8F7",
            border: `1px solid ${isErr ? "#FECACA" : "#E6EAE8"}`,
            color: isErr ? "#B91C1C" : "#1E293B",
            fontSize: "14px",
            lineHeight: 1.65,
          }}
        >
          {message.summary && (
            <div style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: "11.5px", color: "#15803D", background: "#F0FDF4", border: "1px solid #DCFCE7", padding: "4px 10px", borderRadius: 9999, marginBottom: 11, fontWeight: 600 }}>
              <IcCheck size={12} strokeWidth={2.5} />
              {message.summary}
            </div>
          )}

          {message.streaming && !md ? (
            <TypingDots />
          ) : (
            <Markdown className="md-answer">{withCiteButtons(md)}</Markdown>
          )}

          {/* Nguồn: chips */}
          {!message.streaming && message.citeChips && message.citeChips.length > 0 && (
            <div style={{ marginTop: 11, paddingTop: 10, borderTop: "1px solid #E6EAE8", display: "flex", flexWrap: "wrap", gap: 6, alignItems: "center" }}>
              <span style={{ fontSize: "11.5px", color: "#64748B", fontWeight: 600 }}>Nguồn:</span>
              {message.citeChips.map((c) => (
                <button
                  key={c.index}
                  onClick={() => actions.openCite(c.index)}
                  title="Bấm để mở nguồn này"
                  className="inline-flex items-center gap-[5px] px-[10px] py-1 bg-white border border-green-200 rounded-full font-sans text-[11.5px] font-semibold text-brand-dark cursor-pointer hover:bg-green-50 hover:border-brand"
                >
                  <span style={{ fontWeight: 700 }}>{c.n}</span> {c.code}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* action bar (chỉ khi đã xong) */}
        {!message.streaming && !isErr && md && (
          <div style={{ display: "flex", alignItems: "center", gap: 1, marginTop: 1 }}>
            <button onClick={() => actions.copyAnswer(plain)} title="Sao chép câu trả lời" className="w-7 h-7 rounded-[7px] border-none bg-transparent flex items-center justify-center cursor-pointer text-slate-400 hover:bg-slate-100 hover:text-slate-700">
              <IcCopy size={14} />
            </button>
            <button onClick={() => actions.feedback("up")} title="Câu trả lời hữu ích" className="w-7 h-7 rounded-[7px] border-none bg-transparent flex items-center justify-center cursor-pointer text-slate-400 hover:bg-green-50 hover:text-brand">
              <IcThumbUp size={14} />
            </button>
            <button onClick={() => actions.feedback("down")} title="Câu trả lời chưa đúng" className="w-7 h-7 rounded-[7px] border-none bg-transparent flex items-center justify-center cursor-pointer text-slate-400 hover:bg-red-50 hover:text-[#DC2626]">
              <IcThumbDown size={14} />
            </button>
            {showRegen && (
              <button onClick={() => actions.regenerate()} title="Tạo lại câu trả lời" className="w-7 h-7 rounded-[7px] border-none bg-transparent flex items-center justify-center cursor-pointer text-slate-400 hover:bg-slate-100 hover:text-slate-700">
                <IcRefresh size={14} />
              </button>
            )}
          </div>
        )}

        {/* error retry */}
        {isErr && isLast && (
          <button onClick={() => actions.regenerate()} className="inline-flex items-center gap-2 px-[11px] py-[7px] border border-line bg-white rounded-[9px] font-sans text-[12.5px] text-slate-600 cursor-pointer hover:border-brand hover:bg-green-50 hover:text-brand-dark">
            <IcRefresh size={14} style={{ color: "#16A34A" }} /> Thử lại
          </button>
        )}
      </div>
    </div>
  );
}

function TypingDots() {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 4, padding: "2px 0" }}>
      {[0, 1, 2].map((i) => (
        <span key={i} style={{ width: 6, height: 6, borderRadius: "50%", background: "#94A3B8", animation: `pulseDot 1s ease-in-out ${i * 0.15}s infinite` }} />
      ))}
    </div>
  );
}
