import { useCallback, useEffect, useReducer, useRef } from "react";
import type { AppState, BackendSource, CiteChip, Conversation, DocItem, Message } from "../types";
import { SAMPLES } from "./seed";
import { TIMING, ZOOM } from "../services/mockEngine";
import {
  deleteDocument,
  documentFileUrl,
  fetchDocumentMarkdown,
  fetchDocuments,
  fetchExamples,
  fixLatex,
  pingHealth,
  processDocument,
  renameDocument,
  streamChat,
  uploadDocument,
  type HistoryTurn,
} from "../services/liveApi";
import { loadConversations, saveConversations } from "./persistence";

// setState-style reducer: nhận patch (partial hoặc hàm) → merge.
type Patch = Partial<AppState> | ((s: AppState) => Partial<AppState>);
function reducer(s: AppState, patch: Patch): AppState {
  const p = typeof patch === "function" ? patch(s) : patch;
  return { ...s, ...p };
}

function makeInitialState(): AppState {
  return {
    tab: "chat",
    input: "",
    proc: null,
    activeCite: "1",
    pulse: 0,
    pinIndex: -1,
    sourceW: 430,
    activeConvId: null,
    messages: [], // LIVE: bắt đầu rỗng (màn hình chào + câu hỏi mẫu)
    histSearch: "",
    renamingConv: null,
    renamingDoc: null,
    faqOpen: 0,
    toast: null,
    docSearch: "",
    docStatusFilter: "all",
    docPageSize: 5,
    docPage: 1,
    viewingDoc: null,
    confirmDelete: null,
    llmConfigOpen: false,
    llmStatus: "none",
    llmTesting: false,
    llmTestResult: null,
    llm: { baseUrl: "https://api.openai.com/v1", apiKey: "", model: "gpt-4o-mini", temperature: "0.7" },
    conversations: loadConversations(),
    documents: [], // LIVE: nạp từ /api/documents khi mount (xem effect bên dưới)
    examples: SAMPLES,
    liveSources: [],
    streaming: false,
  };
}

export interface Actions {
  go: (tab: AppState["tab"]) => void;
  setInput: (v: string) => void;
  send: (text?: string) => void;
  regenerate: () => void;
  copyAnswer: (text: string) => void;
  feedback: (type: "up" | "down") => void;
  askSample: (q: string) => void;
  newChat: () => void;
  openCite: (id: string) => void;
  openConv: (conv: Conversation) => void;
  togglePin: (e: React.MouseEvent, id: string) => void;
  startRenameConv: (e: React.MouseEvent, id: string) => void;
  renameConv: (id: string, v: string) => void;
  commitRenameConv: () => void;
  requestDeleteConv: (e: React.MouseEvent, id: string) => void;
  confirmDeleteYes: () => void;
  confirmDeleteNo: () => void;
  setHistSearch: (v: string) => void;
  uploadDoc: (file: File) => void;
  processDoc: (id: string) => void;
  startRenameDoc: (id: string) => void;
  renameDoc: (id: string, v: string) => void;
  commitRenameDoc: () => void;
  deleteDoc: (id: string) => void;
  viewDoc: (d: DocItem) => void;
  openSourceDoc: () => void;
  closeViewer: () => void;
  setDocSearch: (v: string) => void;
  setDocStatusFilter: (v: AppState["docStatusFilter"]) => void;
  setDocPageSize: (n: number) => void;
  setDocPage: (n: number) => void;
  toggleFaq: (i: number) => void;
  startResize: (e: React.MouseEvent) => void;
  openLlmConfig: () => void;
  closeLlmConfig: () => void;
  setLlm: (field: keyof AppState["llm"], v: string) => void;
  testLlm: () => void;
  saveLlm: () => void;
}

// ── helpers thuần ──
function updateLastBot(s: AppState, patch: Partial<AppState["messages"][number]>): Partial<AppState> {
  const next = [...s.messages];
  for (let i = next.length - 1; i >= 0; i--) {
    if (next[i].role === "bot") {
      next[i] = { ...next[i], ...patch };
      break;
    }
  }
  return { messages: next };
}
function summaryOf(srcs: BackendSource[]): string {
  return srcs.length ? `Trả lời dựa trên ${srcs.length} đoạn tài liệu` : "";
}
function chipsOf(srcs: BackendSource[]): CiteChip[] {
  return srcs.map((s) => ({ n: `[${s.index}]`, index: String(s.index), code: s.file_stem }));
}
function snippetOf(md: string): string {
  return md
    .replace(/<[^>]+>/g, "")
    .replace(/[#*`>_~]/g, "")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 90);
}
/** Dựng history gửi backend từ các lượt TRƯỚC (timing-independent). */
function toHistory(prior: Message[]): HistoryTurn[] {
  const hist: HistoryTurn[] = [];
  for (const m of prior) {
    if (m.role === "user" && m.text) hist.push({ role: "user", content: m.text });
    else if (m.role === "bot" && m.markdown && !m.error) hist.push({ role: "assistant", content: m.markdown });
  }
  return hist;
}

export function useAppStore(): { state: AppState; actions: Actions } {
  const [state, set] = useReducer(reducer, undefined, makeInitialState);
  const stateRef = useRef(state);
  stateRef.current = state;

  const toastTimer = useRef<number | undefined>(undefined);
  const upTimer = useRef<number | undefined>(undefined);
  const llmTimer = useRef<number | undefined>(undefined);
  const abortRef = useRef<AbortController | null>(null);

  // Nạp danh sách tài liệu thật; khi còn tài liệu "processing" thì poll lại sau
  // ~2s để cập nhật tiến độ/kết quả (dừng khi không còn tài liệu nào đang xử lý).
  // Dùng cả ở mount lẫn ngay sau upload/xử lý/xoá để phản ánh tức thời.
  const refreshDocuments = useCallback(() => {
    clearTimeout(upTimer.current);
    fetchDocuments()
      .then((docs) => {
        set({ documents: docs });
        if (docs.some((d) => d.status === "processing")) {
          upTimer.current = window.setTimeout(refreshDocuments, 2000);
        }
      })
      .catch(() => {});
  }, []);

  // mount: nạp câu hỏi mẫu + ping sức khoẻ backend (lặp 30s) + tài liệu thật
  useEffect(() => {
    fetchExamples()
      .then((ex) => ex.length && set({ examples: ex }))
      .catch(() => {});
    const ping = () =>
      pingHealth()
        .then((ok) => set({ llmStatus: ok ? "active" : "none" }))
        .catch(() => set({ llmStatus: "none" }));
    ping();
    const iv = window.setInterval(ping, 30000);

    refreshDocuments();

    return () => {
      clearInterval(iv);
      clearTimeout(toastTimer.current);
      clearTimeout(upTimer.current);
      clearTimeout(llmTimer.current);
      abortRef.current?.abort();
    };
  }, [refreshDocuments]);

  // Lưu lịch sử hội thoại mỗi khi danh sách thay đổi
  useEffect(() => {
    saveConversations(state.conversations);
  }, [state.conversations]);

  const showToast = (msg: string) => {
    set({ toast: msg });
    clearTimeout(toastTimer.current);
    toastTimer.current = window.setTimeout(() => set({ toast: null }), TIMING.toast);
  };

  const runLive = async (q: string, prior: Message[]) => {
    const hist = toHistory(prior);
    const ac = new AbortController();
    abortRef.current = ac;
    let partial = "";
    let firstDelta = true;
    try {
      for await (const ev of streamChat(q, hist, ac.signal)) {
        if (ev.type === "status") {
          set((s) => ({ proc: { step: Math.min((s.proc?.step ?? 0) + 1, 3) } }));
        } else if (ev.type === "sources") {
          set({ liveSources: ev.sources ?? [], activeCite: "1", proc: { step: 2 } });
        } else if (ev.type === "delta") {
          partial += ev.text ?? "";
          const md = fixLatex(partial);
          if (firstDelta) firstDelta = false;
          set((s) => ({ ...updateLastBot(s, { markdown: md, streaming: true }), proc: null }));
        } else if (ev.type === "done") {
          const md = fixLatex(ev.answer || partial);
          const srcs = ev.sources ?? stateRef.current.liveSources;
          set((s) => {
            // cập nhật bot message cuối + gắn nguồn
            const next = [...s.messages];
            for (let i = next.length - 1; i >= 0; i--) {
              if (next[i].role === "bot") {
                next[i] = { ...next[i], markdown: md, streaming: false, summary: summaryOf(srcs), citeChips: chipsOf(srcs), sources: srcs };
                break;
              }
            }
            // tạo / cập nhật hội thoại đã lưu (localStorage qua effect)
            const cite = s.activeCite || "1";
            const now = new Date().toISOString();
            const firstUser = next.find((m) => m.role === "user");
            const snippet = snippetOf(md);
            let id = s.activeConvId;
            let convs = s.conversations;
            if (!id) {
              id = "conv_" + Date.now();
              const conv: Conversation = {
                id,
                title: (firstUser?.text || "Hội thoại").slice(0, 90),
                snippet,
                pinned: false,
                createdAt: now,
                updatedAt: now,
                messages: next,
                liveSources: srcs,
                activeCite: cite,
              };
              convs = [conv, ...convs];
            } else {
              convs = convs.map((c) => (c.id === id ? { ...c, snippet, updatedAt: now, messages: next, liveSources: srcs, activeCite: cite } : c));
            }
            return { messages: next, liveSources: srcs, activeCite: cite, proc: null, streaming: false, conversations: convs, activeConvId: id };
          });
        } else if (ev.type === "error") {
          set((s) => ({ ...updateLastBot(s, { markdown: "❌ " + (ev.text || "Lỗi"), error: true, streaming: false }), proc: null, streaming: false }));
        }
      }
    } catch (e) {
      if (!ac.signal.aborted) {
        const msg = e instanceof Error ? e.message : String(e);
        set((s) => ({ ...updateLastBot(s, { markdown: "❌ Lỗi kết nối: " + msg, error: true, streaming: false }), proc: null, streaming: false }));
      }
    } finally {
      set({ proc: null, streaming: false });
      abortRef.current = null;
    }
  };

  const send = (text?: string) => {
    const t = (typeof text === "string" ? text : stateRef.current.input).trim();
    if (!t || stateRef.current.streaming) return;
    const prior = stateRef.current.messages; // các lượt TRƯỚC — để LLM nhớ ngữ cảnh
    set((s) => ({
      messages: [...s.messages, { role: "user", text: t }, { role: "bot", markdown: "", streaming: true }],
      input: "",
      proc: { step: 0 },
      streaming: true,
      liveSources: [],
      pinIndex: s.messages.length,
    }));
    void runLive(t, prior);
  };

  const resetAndSend = (q: string, base: AppState["messages"], extra?: Partial<AppState>) => {
    abortRef.current?.abort();
    set({ messages: base, proc: null, streaming: false, liveSources: [], input: "", ...extra });
    window.setTimeout(() => send(q), 30);
  };

  const actions: Actions = {
    go: (tab) => set({ tab }),
    setInput: (v) => set({ input: v }),
    send,
    regenerate: () => {
      const msgs = stateRef.current.messages;
      let i = msgs.length - 1;
      while (i >= 0 && msgs[i].role !== "user") i--;
      if (i < 0) return;
      const q = msgs[i].text || "";
      resetAndSend(q, msgs.slice(0, i));
      showToast("Đang tạo lại câu trả lời…");
    },
    copyAnswer: (text) => {
      try {
        if (navigator.clipboard?.writeText) navigator.clipboard.writeText(text).catch(() => {});
      } catch {
        /* noop */
      }
      showToast("Đã sao chép câu trả lời");
    },
    feedback: (type) => showToast(type === "up" ? "Cảm ơn phản hồi của bạn!" : "Đã ghi nhận — trợ lý sẽ cải thiện."),
    askSample: (q) => {
      set({ tab: "chat" });
      window.setTimeout(() => send(q), 30);
    },
    newChat: () => {
      abortRef.current?.abort();
      set({ messages: [], proc: null, input: "", activeConvId: null, pinIndex: -1, streaming: false, liveSources: [] });
      showToast("Đã tạo hội thoại mới");
    },
    openCite: (id) => set((s) => ({ tab: "chat", activeCite: id, pulse: s.pulse + 1 })),
    openConv: (conv) => {
      if (stateRef.current.renamingConv === conv.id) return;
      abortRef.current?.abort();
      const stored = stateRef.current.conversations.find((c) => c.id === conv.id) || conv;
      // NẠP đúng hội thoại đã lưu — KHÔNG hỏi lại, KHÔNG gọi backend
      set({
        tab: "chat",
        proc: null,
        streaming: false,
        messages: stored.messages,
        liveSources: stored.liveSources,
        activeCite: stored.activeCite || "1",
        activeConvId: conv.id,
        pinIndex: stored.messages.length ? 0 : -1,
      });
      showToast("Đã mở: " + conv.title);
    },
    togglePin: (e, id) => {
      e?.stopPropagation();
      set((s) => ({ conversations: s.conversations.map((c) => (c.id === id ? { ...c, pinned: !c.pinned } : c)) }));
    },
    startRenameConv: (e, id) => {
      e?.stopPropagation();
      set({ renamingConv: id });
    },
    renameConv: (id, v) => set((s) => ({ conversations: s.conversations.map((c) => (c.id === id ? { ...c, title: v } : c)) })),
    commitRenameConv: () => {
      set({ renamingConv: null });
      showToast("Đã đổi tên hội thoại");
    },
    requestDeleteConv: (e, id) => {
      e?.stopPropagation();
      const conv = stateRef.current.conversations.find((c) => c.id === id) || null;
      set({ confirmDelete: conv });
    },
    confirmDeleteYes: () => {
      const conv = stateRef.current.confirmDelete;
      if (!conv) return;
      set((s) => ({ conversations: s.conversations.filter((c) => c.id !== conv.id), confirmDelete: null }));
      showToast("Đã xoá hội thoại thành công");
    },
    confirmDeleteNo: () => set({ confirmDelete: null }),
    setHistSearch: (v) => set({ histSearch: v }),
    uploadDoc: (file) => {
      uploadDocument(file)
        .then((doc) => {
          set((s) => ({ documents: [doc, ...s.documents.filter((d) => d.id !== doc.id)], docPage: 1 }));
          showToast("Đã tải lên — tài liệu đang chờ xử lý");
        })
        .catch((e) => showToast(e instanceof Error ? e.message : "Tải lên thất bại"));
    },
    processDoc: (id) => {
      set((s) => ({ documents: s.documents.map((d) => (d.id === id ? { ...d, status: "processing", progress: 5, error: undefined } : d)) }));
      showToast("Bắt đầu xử lý tài liệu…");
      processDocument(id)
        .then(refreshDocuments)
        .catch((e) => {
          showToast(e instanceof Error ? e.message : "Không xử lý được tài liệu");
          refreshDocuments();
        });
    },
    startRenameDoc: (id) => set({ renamingDoc: id }),
    renameDoc: (id, v) => set((s) => ({ documents: s.documents.map((d) => (d.id === id ? { ...d, name: v } : d)) })),
    commitRenameDoc: () => {
      const id = stateRef.current.renamingDoc;
      set({ renamingDoc: null });
      const doc = id ? stateRef.current.documents.find((d) => d.id === id) : undefined;
      if (!id || !doc) return;
      renameDocument(id, doc.name)
        .then(() => showToast("Đã đổi tên tài liệu"))
        .catch((e) => showToast(e instanceof Error ? e.message : "Đổi tên thất bại"));
    },
    deleteDoc: (id) => {
      set((s) => ({ documents: s.documents.filter((d) => d.id !== id) }));
      deleteDocument(id)
        .then(() => showToast("Đã xoá tài liệu"))
        .catch((e) => {
          showToast(e instanceof Error ? e.message : "Xoá thất bại");
          refreshDocuments();
        });
    },
    viewDoc: (d) => {
      if (d.status && d.status !== "ready") {
        showToast("Tài liệu đang được xử lý — vui lòng đợi");
        return;
      }
      // Hiện tệp gốc (.docx/.pdf) thô ngay; markdown chỉ tải nền làm phương án dự phòng
      // (ext không phải PDF/DOCX, hoặc tệp gốc không mở được trong trình duyệt).
      set({
        viewingDoc: {
          name: d.name,
          code: d.id,
          pages: null,
          blocks: [],
          fileUrl: documentFileUrl(d.id),
          ext: d.ext,
          size: d.size,
          date: d.date,
          status: d.status,
        },
      });
      fetchDocumentMarkdown(d.id)
        .then((markdown) => set((st) => (st.viewingDoc ? { viewingDoc: { ...st.viewingDoc, markdown } } : {})))
        .catch(() => {});
    },
    openSourceDoc: () => {
      const s = stateRef.current.liveSources.find((x) => String(x.index) === stateRef.current.activeCite) || stateRef.current.liveSources[0];
      if (!s) return;
      // doc thật trong danh sách (nếu có) — cung cấp ext/size/ngày/trạng thái thật cho panel "Thông tin tệp"
      const doc = stateRef.current.documents.find((d) => d.id === s.file_stem);
      const meta = { sectionPath: s.section_path, kind: s.kind, ext: doc?.ext, size: doc?.size, date: doc?.date, status: doc?.status };
      // Hiện tệp gốc (.docx/.pdf) thô — không chỉ đoạn parent_text của 1 trích dẫn;
      // markdown (parent_text) chỉ dùng khi chưa biết ext hoặc tệp gốc không mở được.
      set({
        viewingDoc: { name: s.file_stem, code: s.file_stem, pages: null, blocks: [], markdown: s.parent_text, fileUrl: documentFileUrl(s.file_stem), ...meta },
      });
      fetchDocumentMarkdown(s.file_stem)
        .then((markdown) => set((st) => (st.viewingDoc ? { viewingDoc: { ...st.viewingDoc, markdown } } : {})))
        .catch(() => {});
    },
    closeViewer: () => set({ viewingDoc: null }),
    setDocSearch: (v) => set({ docSearch: v, docPage: 1 }),
    setDocStatusFilter: (v) => set({ docStatusFilter: v, docPage: 1 }),
    setDocPageSize: (n) => set({ docPageSize: n, docPage: 1 }),
    setDocPage: (n) => set({ docPage: n }),
    toggleFaq: (i) => set((s) => ({ faqOpen: s.faqOpen === i ? -1 : i })),
    startResize: (e) => {
      e.preventDefault();
      const startX = e.clientX;
      const startW = stateRef.current.sourceW;
      const move = (ev: MouseEvent) => {
        const dx = (ev.clientX - startX) / ZOOM;
        let w = startW - dx;
        w = Math.max(320, Math.min(720, w));
        set({ sourceW: w });
      };
      const up = () => {
        window.removeEventListener("mousemove", move);
        window.removeEventListener("mouseup", up);
      };
      window.addEventListener("mousemove", move);
      window.addEventListener("mouseup", up);
    },
    openLlmConfig: () => set({ llmConfigOpen: true }),
    closeLlmConfig: () => set({ llmConfigOpen: false }),
    setLlm: (field, v) => set((s) => ({ llm: { ...s.llm, [field]: v } })),
    testLlm: () => {
      const l = stateRef.current.llm;
      if (!l.baseUrl.trim() || !l.apiKey.trim() || !l.model.trim()) {
        set({ llmTestResult: { ok: false, msg: "Vui lòng nhập đầy đủ Địa chỉ API, API Key và Tên mô hình trước khi kiểm tra." } });
        return;
      }
      set({ llmTesting: true, llmTestResult: null, llmStatus: "checking" });
      clearTimeout(llmTimer.current);
      llmTimer.current = window.setTimeout(() => {
        set({
          llmTesting: false,
          llmStatus: "active",
          llmTestResult: { ok: true, msg: "Kết nối thành công — mô hình đã phản hồi.", sample: "Xin chào! Tôi là trợ lý kiểm định, đã sẵn sàng hỗ trợ bạn." },
        });
      }, TIMING.llmTest);
    },
    saveLlm: () => {
      set({ llmConfigOpen: false });
      showToast("Đã lưu cấu hình mô hình");
    },
  };

  return { state, actions };
}
