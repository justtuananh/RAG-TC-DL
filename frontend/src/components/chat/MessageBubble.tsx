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
      <div ref={pinnedRef} className="animate-fadeUp" style={{ display: "flex", justifyContent: "flex-end" }}>
        <div
          style={{
            maxWidth: "80%",
            padding: "11px 15px",
            borderRadius: "16px 16px 5px 16px",
            background: "#006130",
            color: "#fff",
            fontSize: "14px",
            lineHeight: 1.55,
            boxShadow: "0 2px 5px rgba(0,97,48,.22)",
          }}
        >
          {message.text}
        </div>
      </div>
    );
  }

  const md = message.markdown ?? "";
  // Đang xử lý mà chưa có chữ → KHÔNG dựng bong bóng rỗng; <ProcessSteps> là
  // chỉ báo "đang xử lý" duy nhất. Khi delta đầu về, proc=null + markdown được
  // set CÙNG một lúc → câu trả lời gen ngay trong bong bóng này (giữ nguyên box).
  if (message.streaming && !md) return null;

  const isErr = !!message.error;
  const showRegen = isLast && !proc && !message.streaming;
  const plain = md.replace(/<[^>]+>/g, "");

  const onBubbleClick = (e: React.MouseEvent) => {
    const el = (e.target as HTMLElement).closest("[data-cite]");
    if (el) actions.openCite(el.getAttribute("data-cite") || "1");
  };

  return (
    <div ref={pinnedRef} className="animate-fadeUp" style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
      <div
        style={{
          flexShrink: 0,
          width: 32,
          height: 32,
          borderRadius: 9999,
          background: "#dae2fd",
          border: "1px solid #becabd",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          marginTop: 2,
        }}
      >
        <IcBrand size={17} style={{ color: "#006130" }} />
      </div>

      <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: 9, alignItems: "flex-start" }}>
        {/* answer bubble */}
        <div
          onClick={onBubbleClick}
          style={{
            maxWidth: "100%",
            padding: "13px 16px",
            borderRadius: "16px 16px 16px 5px",
            background: isErr ? "#FEF2F2" : "#f2f3ff",
            border: `1px solid ${isErr ? "#FECACA" : "#becabd"}`,
            color: isErr ? "#B91C1C" : "#131b2e",
            fontSize: "14px",
            lineHeight: 1.65,
          }}
        >
          {message.summary && (
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                fontSize: "11.5px",
                color: "#006130",
                background: "#f2f3ff",
                border: "1px solid #dae2fd",
                padding: "4px 10px",
                borderRadius: 9999,
                marginBottom: 11,
                fontWeight: 600,
              }}
            >
              <IcCheck size={12} strokeWidth={2.5} />
              {message.summary}
            </div>
          )}

          <Markdown className="md-answer">{withCiteButtons(md)}</Markdown>

          {/* Nguồn: chips */}
          {!message.streaming && message.citeChips && message.citeChips.length > 0 && (
            <div style={{ marginTop: 11, paddingTop: 10, borderTop: "1px solid #becabd", display: "flex", flexWrap: "wrap", gap: 6, alignItems: "center" }}>
              <span style={{ fontSize: "11.5px", color: "#6f7a6f", fontWeight: 600 }}>Nguồn:</span>
              {message.citeChips.map((c) => (
                <button
                  key={c.index}
                  onClick={() => actions.openCite(c.index)}
                  title="Bấm để mở nguồn này"
                  className="inline-flex items-center gap-[5px] px-[10px] py-1 bg-white border border-[#becabd] rounded-full font-sans text-[11.5px] font-semibold text-brand-dark cursor-pointer hover:bg-[#eaedff] hover:border-brand"
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
            <button
              onClick={() => actions.copyAnswer(plain)}
              aria-label="Sao chép câu trả lời"
              title="Sao chép câu trả lời"
              className="w-7 h-7 rounded-[7px] border-none bg-transparent flex items-center justify-center cursor-pointer text-[#6f7a6f] hover:bg-[#eaedff] hover:text-[#3f4940]"
            >
              <IcCopy size={14} />
            </button>
            <button
              onClick={() => actions.feedback("up")}
              aria-label="Câu trả lời hữu ích"
              title="Câu trả lời hữu ích"
              className="w-7 h-7 rounded-[7px] border-none bg-transparent flex items-center justify-center cursor-pointer text-[#6f7a6f] hover:bg-[#f2f3ff] hover:text-brand"
            >
              <IcThumbUp size={14} />
            </button>
            <button
              onClick={() => actions.feedback("down")}
              aria-label="Câu trả lời chưa đúng"
              title="Câu trả lời chưa đúng"
              className="w-7 h-7 rounded-[7px] border-none bg-transparent flex items-center justify-center cursor-pointer text-[#6f7a6f] hover:bg-red-50 hover:text-[#DC2626]"
            >
              <IcThumbDown size={14} />
            </button>
            {showRegen && (
              <button
                onClick={() => actions.regenerate()}
                aria-label="Tạo lại câu trả lời"
                title="Tạo lại câu trả lời"
                className="w-7 h-7 rounded-[7px] border-none bg-transparent flex items-center justify-center cursor-pointer text-[#6f7a6f] hover:bg-[#eaedff] hover:text-[#3f4940]"
              >
                <IcRefresh size={14} />
              </button>
            )}
          </div>
        )}

        {/* error retry */}
        {isErr && isLast && (
          <button
            onClick={() => actions.regenerate()}
            className="inline-flex items-center gap-2 px-[11px] py-[7px] border border-line bg-white rounded-[9px] font-sans text-[12.5px] text-[#3f4940] cursor-pointer hover:border-brand hover:bg-[#eaedff] hover:text-brand-dark"
          >
            <IcRefresh size={14} style={{ color: "#006130" }} /> Thử lại
          </button>
        )}
      </div>
    </div>
  );
}
