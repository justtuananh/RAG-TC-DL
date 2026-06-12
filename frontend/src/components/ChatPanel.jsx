import { useRef, useEffect, useState, useCallback } from "react";
import { Send, Loader2 } from "lucide-react";
import MessageBubble from "./MessageBubble.jsx";

export default function ChatPanel({ messages, isStreaming, statusText, examples, onSend, onClear }) {
  const [input, setInput] = useState("");
  const bottomRef = useRef(null);
  const textareaRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, statusText]);

  const handleSend = useCallback(() => {
    const text = input.trim();
    if (!text || isStreaming) return;
    setInput("");
    onSend(text);
  }, [input, isStreaming, onSend]);

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const isEmpty = messages.length === 0;

  return (
    <div className="flex flex-col flex-[6] min-w-0 border-r border-slate-200 bg-white">
      {/* Message list */}
      <div className="flex-1 overflow-y-auto chat-scrollbar px-4 py-4 space-y-4">
        {isEmpty ? (
          <EmptyState examples={examples} onExample={(q) => onSend(q)} />
        ) : (
          messages.map((msg, i) => (
            <MessageBubble key={i} message={msg} />
          ))
        )}

        {/* Status bar */}
        {statusText && (
          <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-primary-50 border border-primary-100 w-fit animate-fade-in-up">
            <Loader2 size={13} className="animate-spin text-primary-500 flex-shrink-0" />
            <span className="text-xs text-primary-700 font-medium">{statusText}</span>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input area */}
      <div className="flex-shrink-0 border-t border-slate-200 p-4">
        <div className="flex gap-2 items-end">
          <textarea
            ref={textareaRef}
            className="flex-1 resize-none rounded-xl border border-slate-300 focus:border-primary-400 focus:ring-2 focus:ring-primary-100 outline-none px-4 py-3 text-sm text-slate-800 placeholder-slate-400 bg-white min-h-[44px] max-h-32 leading-relaxed transition-shadow"
            placeholder="Nhập câu hỏi về quy trình kiểm định đo lường…"
            rows={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isStreaming}
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || isStreaming}
            className="flex-shrink-0 w-11 h-11 rounded-xl bg-primary-600 hover:bg-primary-700 disabled:bg-slate-200 disabled:cursor-not-allowed text-white flex items-center justify-center transition-colors shadow-sm"
          >
            {isStreaming
              ? <Loader2 size={18} className="animate-spin" />
              : <Send size={18} />
            }
          </button>
        </div>
        <p className="mt-1.5 text-xs text-slate-400 text-center">
          Enter để gửi · Shift+Enter xuống dòng
        </p>
      </div>
    </div>
  );
}

function EmptyState({ examples, onExample }) {
  return (
    <div className="flex flex-col items-center justify-center h-full py-12 gap-6">
      <div className="text-center">
        <div className="text-5xl mb-3">📐</div>
        <h2 className="text-lg font-bold text-slate-800 mb-1">Hỏi về quy trình kiểm định</h2>
        <p className="text-sm text-slate-500 max-w-xs">
          Nguồn: QTKĐ 1.061 / 1.062 / 1.063 / 1.071 / 1.159 / 1.160 / 1.190
        </p>
      </div>

      {examples.length > 0 && (
        <div className="w-full max-w-md space-y-2">
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide text-center">Câu hỏi mẫu</p>
          {examples.map((q, i) => (
            <button
              key={i}
              onClick={() => onExample(q)}
              className="w-full text-left px-4 py-3 rounded-xl border border-slate-200 bg-slate-50 hover:bg-primary-50 hover:border-primary-200 text-sm text-slate-700 hover:text-primary-700 transition-colors leading-relaxed"
            >
              {q}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
