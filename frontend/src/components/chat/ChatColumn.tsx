import { useEffect, useRef } from "react";
import type { AppState } from "../../types";
import type { Actions } from "../../store/useAppStore";
import { IcBrand, IcMessage, IcSend } from "../common/icons";
import MessageBubble from "./MessageBubble";
import ProcessSteps from "./ProcessSteps";

function offsetTopIn(el: HTMLElement, container: HTMLElement) {
  let y = 0;
  let n: HTMLElement | null = el;
  while (n && n !== container) {
    y += n.offsetTop || 0;
    n = n.offsetParent as HTMLElement | null;
  }
  return y;
}

export default function ChatColumn({ state, actions }: { state: AppState; actions: Actions }) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const pinRef = useRef<HTMLElement | null>(null);

  // Ghim câu hỏi lên đầu khung khi pinIndex đổi (đọc từ trên xuống)
  useEffect(() => {
    const c = scrollRef.current;
    const el = pinRef.current;
    if (c && el) c.scrollTo({ top: Math.max(0, offsetTopIn(el, c) - 14), behavior: "smooth" });
  }, [state.pinIndex, state.messages.length]);

  const firstUser = state.messages.find((m) => m.role === "user");
  const chatTitle = firstUser ? firstUser.text : "Hội thoại mới";
  const lastIdx = state.messages.length - 1;
  const canSend = !!state.input.trim() && !state.proc;

  return (
    <section style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", background: "#fff" }}>
      {/* header */}
      <div style={{ flexShrink: 0, height: 46, display: "flex", alignItems: "center", gap: 9, padding: "0 18px", borderBottom: "1px solid #F1F5F9" }}>
        <IcMessage size={15} style={{ color: "#16A34A" }} />
        <span style={{ fontWeight: 600, fontSize: "13.5px", color: "#334155", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{chatTitle}</span>
      </div>

      {/* scroll area */}
      <div ref={scrollRef} style={{ flex: 1, overflowY: "auto", padding: "18px 22px 24px", display: "flex", flexDirection: "column", gap: 15, position: "relative" }}>
        {state.messages.length === 0 ? (
          <div style={{ margin: "auto", maxWidth: 430, textAlign: "center", padding: "24px 0" }}>
            <div style={{ width: 56, height: 56, borderRadius: 9999, background: "#DCFCE7", border: "1px solid #BBF7D0", display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 15px" }}>
              <IcBrand size={28} style={{ color: "#16A34A" }} />
            </div>
            <div style={{ fontSize: "17px", fontWeight: 700, color: "#0F172A", marginBottom: 18 }}>Xin chào! Mình có thể giúp gì cho bạn?</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {state.examples.map((q, i) => (
                <button
                  key={i}
                  onClick={() => actions.askSample(q)}
                  className="text-left px-[15px] py-3 border border-slate-200 bg-[#F8FAFC] rounded-[11px] font-sans text-[13.5px] text-slate-700 cursor-pointer leading-[1.5] hover:border-brand hover:bg-green-50 hover:text-brand-dark"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        ) : (
          state.messages.map((m, i) => (
            <MessageBubble
              key={i}
              message={m}
              isLast={i === lastIdx}
              proc={!!state.proc}
              actions={actions}
              pinnedRef={i === state.pinIndex ? (el) => (pinRef.current = el) : undefined}
            />
          ))
        )}

        {state.proc && <ProcessSteps step={state.proc.step} />}
      </div>

      {/* composer */}
      <div style={{ flexShrink: 0, borderTop: "1px solid #E6EAE8", padding: "12px 18px 14px" }}>
        <div style={{ display: "flex", gap: 9, alignItems: "flex-end" }}>
          <textarea
            value={state.input}
            onChange={(e) => actions.setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                actions.send();
              }
            }}
            rows={1}
            placeholder="Nhập câu hỏi của bạn…"
            className="flex-1 resize-none border border-slate-300 rounded-[11px] px-[15px] py-3 text-[14px] font-sans leading-[1.55] h-[46px] min-h-[46px] max-h-[130px] outline-none text-slate-800 focus:border-brand focus:shadow-[0_0_0_3px_#DCFCE7]"
          />
          <button
            onClick={() => actions.send()}
            title="Gửi câu hỏi"
            style={{ flexShrink: 0, width: 46, height: 46, border: "none", borderRadius: 11, display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer", color: "#fff", boxShadow: "0 1px 2px rgba(15,23,42,.08)", background: canSend ? "#16A34A" : "#CBD5E1" }}
          >
            <IcSend size={19} />
          </button>
        </div>
        <p style={{ margin: "7px 0 0", textAlign: "center", fontSize: "11.5px", color: "#94A3B8" }}>Nhấn Enter để gửi · Shift + Enter để xuống dòng</p>
      </div>
    </section>
  );
}
