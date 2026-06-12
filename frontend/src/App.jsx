import { useState, useRef, useCallback, useEffect } from "react";
import Header from "./components/Header.jsx";
import ChatPanel from "./components/ChatPanel.jsx";
import DocPanel from "./components/DocPanel.jsx";
import { streamChat, fetchExamples } from "./utils/api.js";
import { fixLatex } from "./utils/latex.js";

export default function App() {
  const [messages, setMessages]     = useState([]);
  const [sources, setSources]       = useState([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [statusText, setStatusText]  = useState("");
  const [examples, setExamples]      = useState([]);
  const abortRef = useRef(null);

  useEffect(() => {
    fetchExamples().then(setExamples).catch(() => {});
  }, []);

  const sendMessage = useCallback(async (text) => {
    if (!text.trim() || isStreaming) return;

    const userMsg = { role: "user", content: text };
    const assistantMsg = { role: "assistant", content: "", streaming: true };

    setMessages((prev) => [...prev, userMsg, assistantMsg]);
    setSources([]);
    setIsStreaming(true);
    setStatusText("");

    // history = all messages before the new pair
    const history = messages.map(({ role, content }) => ({ role, content }));

    let partial = "";
    try {
      for await (const event of streamChat(text, history)) {
        if (event.type === "status") {
          setStatusText(event.text);
        } else if (event.type === "sources") {
          setSources(event.sources);
        } else if (event.type === "delta") {
          partial += event.text;
          const fixed = fixLatex(partial);
          setMessages((prev) => {
            const next = [...prev];
            next[next.length - 1] = { ...next[next.length - 1], content: fixed };
            return next;
          });
        } else if (event.type === "done") {
          const finalAnswer = event.answer || partial;
          const finalSources = event.sources || sources;
          setMessages((prev) => {
            const next = [...prev];
            next[next.length - 1] = {
              role: "assistant",
              content: finalAnswer,
              streaming: false,
              sources: finalSources,
            };
            return next;
          });
          if (event.sources) setSources(event.sources);
        } else if (event.type === "error") {
          setMessages((prev) => {
            const next = [...prev];
            next[next.length - 1] = {
              role: "assistant",
              content: `❌ ${event.text}`,
              streaming: false,
              error: true,
            };
            return next;
          });
        }
      }
    } catch (err) {
      setMessages((prev) => {
        const next = [...prev];
        next[next.length - 1] = {
          role: "assistant",
          content: `❌ Lỗi kết nối: ${err.message}`,
          streaming: false,
          error: true,
        };
        return next;
      });
    } finally {
      setIsStreaming(false);
      setStatusText("");
    }
  }, [messages, isStreaming]);

  const clearHistory = useCallback(() => {
    setMessages([]);
    setSources([]);
    setStatusText("");
  }, []);

  return (
    <div className="flex flex-col h-screen bg-slate-50">
      <Header onClear={clearHistory} hasMessages={messages.length > 0} />

      <main className="flex flex-1 min-h-0">
        <ChatPanel
          messages={messages}
          isStreaming={isStreaming}
          statusText={statusText}
          examples={examples}
          onSend={sendMessage}
          onClear={clearHistory}
        />
        <DocPanel sources={sources} />
      </main>
    </div>
  );
}
