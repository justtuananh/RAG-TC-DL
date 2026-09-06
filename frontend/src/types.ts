// ── Kiểu dữ liệu dùng chung — port 1:1 từ mockup `design/kiemdinh.html` ──

export type Tab = "chat" | "docs" | "guide";

export interface CiteChip {
  n: string; // "[1]"
  index: string; // "1"
  code: string; // file_stem
}

export interface Message {
  role: "user" | "bot";
  text?: string; // user
  // ── chế độ LIVE (backend thật) ──
  markdown?: string; // câu trả lời markdown (đã fixLatex)
  summary?: string; // dòng tóm tắt tổng hợp
  citeChips?: CiteChip[]; // chip "Nguồn:" suy từ sources
  streaming?: boolean;
  error?: boolean;
  sources?: BackendSource[]; // nguồn của câu trả lời này (để lưu/khôi phục hội thoại)
}

/** Nguồn trả về từ api_server.py (_build_sources_payload) */
export interface BackendSource {
  index: number;
  file_stem: string;
  section_path: string;
  kind: string;
  snippet: string;
  rerank_score: number;
  parent_text: string;
  child_text: string;
}

/** Bảng trong "trang tài liệu" */
export interface TableData {
  head: string[];
  rows: string[][];
  highlightRow?: number;
}

/** Khối nội dung của một trang tài liệu (serif) */
export interface DocBlock {
  h?: string;
  sub?: string;
  p?: string;
  note?: string;
  formula?: string;
  highlight?: boolean;
  table?: TableData;
}

export interface Source {
  id: string;
  code: string;
  file: string;
  path: string;
  page: number;
  pages: number;
  rel: number;
  blocks: DocBlock[];
}

export type ConvGroup = "today" | "yesterday" | "week" | "older";

/** Hội thoại đã lưu (localStorage) — gồm toàn bộ tin nhắn + nguồn để khôi phục. */
export interface Conversation {
  id: string;
  title: string;
  snippet: string;
  pinned: boolean;
  createdAt: string; // ISO
  updatedAt: string; // ISO
  messages: Message[];
  liveSources: BackendSource[];
  activeCite: string;
}

export type DocExt = "PDF" | "DOCX" | "XLSX";
export type DocStatus = "ready" | "processing" | "pending" | "error";

export interface DocItem {
  id: string;
  name: string;
  ext: DocExt;
  size: string;
  pages: number | "—";
  date: string;
  status: DocStatus;
  progress?: number;
  error?: string;
}

export interface LlmConfig {
  baseUrl: string;
  apiKey: string;
  model: string;
  temperature: string;
}

export type LlmStatus = "active" | "checking" | "error" | "none";

export interface LlmTestResult {
  ok: boolean;
  msg: string;
  sample?: string;
}

export interface ViewingDoc {
  name: string;
  code: string;
  pages: number | null;
  blocks: DocBlock[];
  markdown?: string; // chế độ live: hiển thị parent_text markdown thay cho blocks
  fileUrl?: string; // tệp gốc (.docx/.pdf) thô — ưu tiên hiển thị thay cho markdown khi có
  // ── metadata thật cho panel "Thông tin tệp" — chỉ điền khi có dữ liệu ──
  ext?: DocExt;
  size?: string;
  date?: string;
  status?: DocStatus;
  sectionPath?: string; // có khi mở từ trích dẫn nguồn (openSourceDoc)
  kind?: string; // loại nội dung (đoạn văn/bảng/công thức…), có khi mở từ trích dẫn nguồn
}

export interface Proc {
  step: number;
}

export interface FaqItem {
  q: string;
  a: string;
}

export interface AppState {
  tab: Tab;
  input: string;
  proc: Proc | null;
  activeCite: string;
  pulse: number;
  pinIndex: number;
  sourceW: number;
  activeConvId: string | null;
  messages: Message[];
  histSearch: string;
  renamingConv: string | null;
  renamingDoc: string | null;
  faqOpen: number;
  toast: string | null;
  docSearch: string;
  docStatusFilter: DocStatus | "all";
  docPageSize: number;
  docPage: number;
  viewingDoc: ViewingDoc | null;
  confirmDelete: Conversation | null;
  llmConfigOpen: boolean;
  llmStatus: LlmStatus;
  llmTesting: boolean;
  llmTestResult: LlmTestResult | null;
  llm: LlmConfig;
  conversations: Conversation[];
  documents: DocItem[];
  // ── LIVE ──
  examples: string[]; // câu hỏi mẫu từ /api/examples (fallback SAMPLES)
  liveSources: BackendSource[]; // nguồn của câu trả lời hiện tại
  streaming: boolean; // đang nhận câu trả lời từ backend
}
