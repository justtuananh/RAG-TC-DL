// ── Kiểu dữ liệu dùng chung — port 1:1 từ mockup `design/kiemdinh.html` ──

export type Tab = "chat" | "docs" | "knowledge" | "data" | "guide";

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
  // ── Chat lai (Sprint 9): nhánh định tuyến + khối số liệu sổ cái ──
  branch?: "text" | "data" | "mixed";
  data?: ChatDataPayload | null;
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

// ── Chat lai văn bản + số liệu (Sprint 9) ──
// Khớp `query/router.py:payload_to_dict` (api_server.py SSE event "data").
// Mỗi ô số mang tham chiếu xuất xứ (P1); bảng kèm trích dẫn sổ cái tách bạch.
export interface DataCellPayload {
  text: string;
  numeric: boolean;
  provenance: DataCellRef | null;
  device_id: number | null;
  record_id: number | null;
}

export interface DataTableColumn {
  key: string;
  label: string;
}

export interface DataTablePayload {
  title: string;
  note: string | null;
  total: number | null;
  columns: DataTableColumn[];
  rows: Record<string, DataCellPayload>[];
}

export interface LedgerCitation {
  kind: string | null;
  file_stem: string | null;
  document_id: string | null;
  display_name: string | null;
  section_path: string | null;
  chunk_id: string | null;
  quote: string | null;
  value_text: string | null;
  record_id?: number | null;
  measurement_id?: number | null;
  fact_id?: number | null;
}

export interface ChatDataPayload {
  intent: string;
  branch: string;
  title: string;
  note: string;
  empty: boolean;
  tables: DataTablePayload[];
  citations: LedgerCitation[];
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

export type DocExt = "PDF" | "DOCX" | "DOC" | "XLSX" | "XLS"; // khớp `ext` backend trả (.doc/.xls cũ vẫn là tài liệu nguồn)
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
  /** Kết quả ghi hồ sơ (StoreResult.as_dict) khi bước "Xử lý" là nạp hồ sơ. */
  result?: Record<string, unknown> | null;
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
  fileUrl?: string; // tệp gốc thô (tải xuống, PDF) - ưu tiên hiển thị thay cho markdown khi có
  previewUrl?: string; // bản xem trên trình duyệt: .doc/.xls cũ đã chuyển sang .docx/.xlsx
  // ── metadata thật cho panel "Thông tin tệp" — chỉ điền khi có dữ liệu ──
  ext?: DocExt;
  size?: string;
  date?: string;
  status?: DocStatus;
  sectionPath?: string; // có khi mở từ trích dẫn nguồn (openSourceDoc)
  kind?: string; // loại nội dung (đoạn văn/bảng/công thức…), có khi mở từ trích dẫn nguồn
}

// ── Xác thực / phân quyền (Sprint 1) ──
// Vai trò khớp enum UserRole ở backend (db/models.py).
export type UserRole = "viewer" | "technician" | "approver" | "admin";

export interface AuthUser {
  id: number;
  username: string;
  full_name: string | null;
  role: UserRole;
}

/** Trạng thái phiên đăng nhập phía client (token nằm ở localStorage, xem services/auth.ts). */
export interface AuthState {
  user: AuthUser | null;
  loginOpen: boolean; // mở màn hình đăng nhập (khi bấm thao tác ghi hoặc token hết hạn)
  loginBusy: boolean;
  loginError: string | null;
  loginNotice: string | null; // lý do mở màn hình (ví dụ "cần đăng nhập để tải lên")
  restoreDone: boolean; // đã thử khôi phục phiên từ localStorage xong chưa
}

export interface Proc {
  step: number;
}

export interface FaqItem {
  q: string;
  a: string;
}

// ── Hàng đợi duyệt tri thức (Sprint 6) ──
// Khớp response của `review/queue.py` (api_server.py /api/extractions/*).
export type ExtractionStatus = "pending" | "approved" | "rejected" | "superseded";
export type ExtractionKind = "fact" | "standard" | "term" | "catalog";

/** Dòng dữ kiện đã trích — trường nào có mặt tùy `kind`. */
export interface ExtractionData {
  fact_kind?: string | null;
  label?: string | null;
  rel_op?: string | null;
  value_min?: number | null;
  value_max?: number | null;
  unit_id?: number | null;
  value_text?: string | null;
  condition_text?: string | null;
  ord?: number | null;
  name_vi?: string | null;
  range_text?: string | null;
  accuracy_text?: string | null;
  note?: string | null;
  term_vi?: string | null;
  term_en?: string | null;
  definition?: string | null;
  // Pha D1: extraction danh mục NAS mang nhiều dòng, chỉ tóm tắt để duyệt.
  catalog_kind?: CatalogKind | null;
  catalog_label?: string | null;
  row_count?: number | null;
  sample?: CatalogSampleRow[] | null;
}

/** Vài trường nhận diện của một dòng danh mục hiển thị trong hàng đợi duyệt. */
export interface CatalogSampleRow {
  name?: string | null;
  model?: string | null;
  serial?: string | null;
  interval_text?: string | null;
  next_due?: string | null;
  birth_year?: number | null;
  rank?: string | null;
  position?: string | null;
  card_no?: string | null;
  code_text?: string | null;
  title?: string | null;
  issuer?: string | null;
  year_issued?: number | null;
  group_code?: string | null;
  group_title?: string | null;
  inspector_count?: number | null;
  recognition?: string | null;
}

/** Toạ độ ô nguồn trong tệp Excel (0-based, đúng chỉ số Excel) - backend `query/sheet_locate.py`. */
export interface SourceLocation {
  sheet: string;
  sheet_index: number;
  row: number;
  cols: number[];
  highlight_cols: number[];
}

/** Nguồn nguyên văn để tô sáng an toàn (văn bản thuần, không nhúng HTML). */
export interface ExtractionSource {
  section_path: string | null;
  chunk_id: string | null;
  quote: string;
  char_start: number | null;
  char_end: number | null;
  section_text: string | null;
  quote_start: number | null;
  quote_end: number | null;
  /** nguồn là tệp Excel (không có mục văn bản): dòng/ô sinh ra trích dẫn */
  source_location?: SourceLocation | null;
}

export interface ExtractionItem {
  id: number;
  document_id: string;
  file_stem: string;
  display_name: string | null;
  section_path: string | null;
  chunk_id: string | null;
  quote: string;
  char_start: number | null;
  char_end: number | null;
  extractor: string;
  extractor_version: string | null;
  confidence: number;
  status: ExtractionStatus;
  reviewed_by: number | null;
  reviewed_at: string | null;
  review_note: string | null;
  created_at: string | null;
  kind: ExtractionKind | null;
  data: ExtractionData | null;
  source?: ExtractionSource;
}

export interface AuditEntry {
  id: number;
  actor_id: number | null;
  actor_username: string | null;
  action: string;
  entity_type: string;
  entity_id: string | null;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  at: string | null;
}

// ── Bề mặt tra cứu dữ liệu (Sprint 8) ──
// Khớp response của `query/records.py` + `query/provenance.py` (api_server.py /api/data/*).
export type DataCellKind = "record" | "measurement" | "fact" | "extraction";

/** Tham chiếu xuất xứ của một ô số: bấm vào sẽ mở đúng đoạn nguyên văn (P1). */
export interface DataCellRef {
  field: string;
  kind: DataCellKind;
  id: number;
}

export interface DataMeasurement {
  id: number;
  record_id: number;
  ord: number | null;
  step_code: string | null;
  label: string | null;
  nominal_value: number | null;
  measured_value: number | null;
  error_value: number | null;
  unit_id: number | null;
  unit_code: string | null;
  unit_name: string | null;
  /** Đơn vị riêng của sai số/giới hạn khi khác đơn vị giá trị đo (ví dụ "%"). */
  error_unit_id: number | null;
  error_unit_code: string | null;
  limit_value: number | null;
  within_limit: boolean | null;
  note: string | null;
  quote: string | null;
  nominal_text: string | null;
  measured_text: string | null;
  error_text: string | null;
  limit_text: string | null;
  provenance: DataCellRef[];
}

export interface DataRecordRow {
  id: number;
  serial_no: string | null;
  device_id: number | null;
  device_type_id: number | null;
  device_type_name: string | null;
  quantity_id: number | null;
  quantity_name: string | null;
  model_code: string | null;
  manufacturer: string | null;
  owner_org: string | null;
  procedure_id: number | null;
  procedure_number: string | null;
  procedure_title: string | null;
  mode: string | null;
  mode_label: string | null;
  calibrated_at: string | null;
  expires_at: string | null;
  expires_from_fact_id: number | null;
  verdict: string | null;
  verdict_label: string | null;
  cert_no: string | null;
  lab_name: string | null;
  env_temp_c: number | null;
  env_humidity_pct: number | null;
  range_min: number | null;
  range_max: number | null;
  /** Giá trị phạm vi đã đổi về đơn vị gốc của dữ kiện để hiển thị (backend). */
  range_min_display: number | null;
  range_max_display: number | null;
  range_unit_code: string | null;
  range_fact_id: number | null;
  /** Pha R: trường phạm vi đo ghi trên chính biên bản (null nếu rơi về QTKĐ). */
  range_field_id?: number | null;
  /** "record": phạm vi của chính thiết bị; "procedure": phạm vi áp dụng của QTKĐ. */
  range_source?: "record" | "procedure" | null;
  /** Nguyên văn phạm vi đo, ví dụ "(50 đến 2 500) kgf/cm2;". */
  range_text?: string | null;
  accuracy_text: string | null;
  accuracy_fact_id: number | null;
  accuracy_field_id?: number | null;
  measurement_count: number | null;
  document_id: string | null;
  file_stem: string | null;
  extraction_id: number;
  extraction_section_path: string | null;
  extraction_chunk_id: string | null;
  extraction_quote: string | null;
  source_text?: string | null;
  provenance: DataCellRef[];
  measurements?: DataMeasurement[];
}

export interface DataRecordsPage {
  items: DataRecordRow[];
  total: number;
  limit: number;
  offset: number;
  sort: string;
  order: string;
}

export interface ProvenanceSource {
  kind: DataCellKind;
  field: string | null;
  document_id: string | null;
  file_stem: string | null;
  display_name: string | null;
  extractor: string | null;
  extractor_version: string | null;
  confidence: number | null;
  value_text: string | null;
  source_quote: string | null;
  section_path: string | null;
  chunk_id: string | null;
  quote: string | null;
  char_start: number | null;
  char_end: number | null;
  section_text: string | null;
  quote_start: number | null;
  quote_end: number | null;
  source_location?: SourceLocation | null;
  record_id?: number;
  measurement_id?: number;
  fact_id?: number;
  step_code?: string | null;
  label?: string | null;
  point_quote?: string | null;
}

export interface DeviceSummary {
  id: number;
  serial_no: string | null;
  model_code: string | null;
  manufacturer: string | null;
  owner_org: string | null;
  device_type_id: number | null;
  device_type_name: string | null;
  quantity_id: number | null;
  quantity_name: string | null;
  record_count: number;
  last_calibrated_at?: string | null;
  dat_count?: number;
}

export interface DeviceHistoryRecord {
  id: number;
  calibrated_at: string | null;
  expires_at: string | null;
  verdict: string | null;
  verdict_label: string | null;
  mode: string | null;
  mode_label: string | null;
  procedure_number: string | null;
  procedure_title: string | null;
  cert_no: string | null;
  document_id: string | null;
  file_stem: string | null;
  extraction_id: number;
  measurement_count: number | null;
  provenance: DataCellRef[];
}

export interface TrendPoint {
  record_id: number;
  point_id: number;
  calibrated_at: string | null;
  verdict: string | null;
  verdict_label: string | null;
  error_value: number | null;
  error_text: string | null;
  limit_value: number | null;
  limit_text: string | null;
  within_limit: boolean | null;
  unit_code: string | null;
  error_unit_code: string | null;
  provenance: DataCellRef[];
}

export interface TrendSeries {
  key: string;
  step_code: string | null;
  label: string | null;
  unit_code: string | null;
  unit_name: string | null;
  error_unit_code: string | null;
  points: TrendPoint[];
}

export interface DeviceHistory {
  device: DeviceSummary;
  records: DeviceHistoryRecord[];
  trend: TrendSeries[];
  record_count: number;
}

export interface FilterChoice {
  value: number | string;
  label: string;
  procedure_title?: string | null;
}

export interface FilterOptions {
  device_types: FilterChoice[];
  quantities: FilterChoice[];
  procedures: FilterChoice[];
  verdicts: FilterChoice[];
  sorts: string[];
}

// ── Pha D1: danh mục hồ sơ NAS (chuẩn mẫu, KĐV, quy trình, lĩnh vực) ──
// Khớp response của `query/catalogs.py` (api_server.py /api/data/catalogs/*).
export type CatalogKind = "lab_standard" | "inspector" | "procedure_catalog" | "capability";

export interface CatalogProvenance {
  document_id: string | null;
  display_name: string | null;
  file_stem: string | null;
  extraction_id: number;
  quote: string;
}

export interface CatalogProcedureLink {
  procedure_id: number;
  number: string;
  title: string | null;
  year: number | null;
  document_id: string;
}

/** Một dòng danh mục đã duyệt; trường nào có mặt tùy loại danh mục. */
export interface CatalogRow {
  id: number;
  ord: number | null;
  document_id: string;
  extraction_id: number;
  quote: string;
  display_name: string | null;
  file_stem: string | null;
  provenance: CatalogProvenance;
  // Chuẩn mẫu (Biểu 3)
  name?: string | null;
  model?: string | null;
  serial?: string | null;
  characteristics?: string | null;
  interval_text?: string | null;
  interval_months?: number | null;
  last_cal_text?: string | null;
  last_cal_year?: number | null;
  last_cal_month?: number | null;
  last_cal_place?: string | null;
  usage_text?: string | null;
  usage_refs?: [string, string][] | null;
  inherited?: string[] | null;
  next_due_year?: number | null;
  next_due_month?: number | null;
  next_due_derived?: number | null;
  // Kiểm định viên (Biểu 7)
  birth_year?: number | null;
  rank?: string | null;
  position?: string | null;
  education?: string | null;
  specialization?: string | null;
  fields?: string[] | null;
  card_no?: string | null;
  card_date?: string | null;
  // Danh mục tiêu chuẩn, quy trình (Biểu 4)
  domain?: string | null;
  group_code?: string | null;
  group_title?: string | null;
  code_text?: string | null;
  codes?: { raw: string; normalized: string }[] | null;
  title?: string | null;
  issuer?: string | null;
  year_issued?: number | null;
  procedure_number?: string | null;
  procedure_link?: CatalogProcedureLink | null;
  // Lĩnh vực công nhận (Biểu 1)
  parameters?: string[] | null;
  procedure_codes?: { raw: string; normalized: string }[] | null;
  inspector_count?: number | null;
  recognition?: string | null;
}

export interface CatalogGroup {
  code: string;
  title: string | null;
}

export interface CatalogPage {
  items: CatalogRow[];
  total: number;
  limit: number;
  offset: number;
  groups: CatalogGroup[];
}

export interface CatalogCounts {
  counts: Record<CatalogKind, number>;
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
  // ── Xác thực (Sprint 1) ──
  auth: AuthState;
  // ── LIVE ──
  examples: string[]; // câu hỏi mẫu từ /api/examples (fallback SAMPLES)
  liveSources: BackendSource[]; // nguồn của câu trả lời hiện tại
  streaming: boolean; // đang nhận câu trả lời từ backend
  // ── Chat lai (Sprint 9): mở trang thiết bị trong tab Dữ liệu từ bảng kết quả ──
  pendingDeviceId: number | null;
}
