import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { AppState, AuditEntry, ExtractionData, ExtractionItem, ExtractionKind } from "../../types";
import type { Actions } from "../../store/useAppStore";
import { COLOR } from "../../theme";
import {
  IcAlert,
  IcCheck,
  IcClock,
  IcFile,
  IcFolder,
  IcLock,
  IcRefresh,
  IcSearch,
  IcShield,
  IcX,
} from "../common/icons";
import QuoteHighlight from "./QuoteHighlight";
import {
  approveExtraction,
  bulkApproveExtractions,
  editApproveExtraction,
  fetchExtraction,
  fetchExtractionAudit,
  fetchExtractionQueue,
  rejectExtraction,
} from "../../services/reviewApi";
import { AuthError } from "../../services/auth";

// ── Tab "Tri thức": hàng đợi duyệt (Sprint 6) ─────────────────────────────────
// Bố cục: danh sách chờ duyệt bên trái, giá trị đã trích bên phải, nguyên văn mục
// (đoạn trích tô sáng) ở dưới. Phím tắt: A duyệt, R từ chối, J/K (↑/↓) di chuyển.
// Chỉ approver/admin dùng được; các vai trò khác thấy thông báo quyền.

const FACT_KIND_LABEL: Record<string, string> = {
  working_range: "Phạm vi đo",
  accuracy_class: "Cấp chính xác",
  max_permissible_error: "Sai số cho phép",
  calibration_interval: "Chu kỳ kiểm định",
  env_condition: "Điều kiện môi trường",
  inspection_step: "Bước kiểm định",
  formula: "Công thức",
};

const KIND_LABEL: Record<ExtractionKind, string> = {
  fact: "Dữ kiện",
  standard: "Bảng 2",
  term: "Thuật ngữ",
};

interface FieldDef {
  key: keyof ExtractionData;
  label: string;
  numeric?: boolean;
  multiline?: boolean;
}

const FACT_FIELDS: FieldDef[] = [
  { key: "value_text", label: "Giá trị (nguyên văn)", multiline: true },
  { key: "value_min", label: "Giá trị nhỏ nhất (SI)", numeric: true },
  { key: "value_max", label: "Giá trị lớn nhất (SI)", numeric: true },
  { key: "condition_text", label: "Điều kiện kèm theo", multiline: true },
  { key: "label", label: "Nhãn" },
];
const STANDARD_FIELDS: FieldDef[] = [
  { key: "name_vi", label: "Tên phương tiện", multiline: true },
  { key: "range_text", label: "Phạm vi", multiline: true },
  { key: "accuracy_text", label: "Độ chính xác", multiline: true },
  { key: "note", label: "Ghi chú", multiline: true },
];
const TERM_FIELDS: FieldDef[] = [
  { key: "term_vi", label: "Thuật ngữ (Việt)" },
  { key: "term_en", label: "Thuật ngữ (Anh)" },
  { key: "definition", label: "Định nghĩa", multiline: true },
];

const ACTION_LABEL: Record<string, string> = {
  approve: "Duyệt",
  reject: "Từ chối",
  edit_approve: "Sửa & duyệt",
};

function fieldsFor(kind: ExtractionKind | null): FieldDef[] {
  if (kind === "standard") return STANDARD_FIELDS;
  if (kind === "term") return TERM_FIELDS;
  return FACT_FIELDS;
}

function draftFrom(item: ExtractionItem): Record<string, string> {
  const out: Record<string, string> = {};
  for (const field of fieldsFor(item.kind)) {
    const value = item.data?.[field.key];
    out[field.key] = value == null ? "" : String(value);
  }
  return out;
}

function errText(error: unknown): string {
  if (error instanceof AuthError) return "Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.";
  return error instanceof Error ? error.message : "Đã xảy ra lỗi.";
}

function confidenceColor(score: number): { color: string; bg: string } {
  if (score >= 0.85) return { color: COLOR.success, bg: COLOR.successBg };
  if (score >= 0.6) return { color: COLOR.warning, bg: COLOR.warningBg };
  return { color: COLOR.danger, bg: COLOR.dangerBg };
}

function valueText(value: unknown): string {
  if (value == null) return "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function describeChange(entry: AuditEntry): string {
  const before = (entry.before ?? {}) as Record<string, unknown>;
  const after = (entry.after ?? {}) as Record<string, unknown>;
  const beforeData = (before.data ?? null) as Record<string, unknown> | null;
  const afterData = (after.data ?? null) as Record<string, unknown> | null;
  if (beforeData && afterData) {
    const keys = new Set([...Object.keys(beforeData), ...Object.keys(afterData)]);
    const diffs: string[] = [];
    for (const key of keys) {
      if (valueText(beforeData[key]) !== valueText(afterData[key])) {
        diffs.push(`${key}: ${valueText(beforeData[key])} → ${valueText(afterData[key])}`);
      }
    }
    if (diffs.length) return diffs.join("; ");
  }
  if (entry.action === "reject") return `Lý do: ${valueText(after.reason)}`;
  if (after.note) return `Ghi chú: ${valueText(after.note)}`;
  return "";
}

function formatTime(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("vi-VN");
}

const panelStyle = { background: COLOR.surface, border: `1px solid ${COLOR.border}`, borderRadius: 13 } as const;
const buttonBase =
  "inline-flex items-center gap-[7px] h-9 px-[13px] rounded-[9px] font-sans text-[12.5px] font-semibold cursor-pointer transition-all active:scale-95 disabled:opacity-40 disabled:pointer-events-none";

export default function KnowledgeTab({ state, actions }: { state: AppState; actions: Actions }) {
  const user = state.auth.user;
  const canReview = !!user && (user.role === "approver" || user.role === "admin");

  const [items, setItems] = useState<ExtractionItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<ExtractionItem | null>(null);
  const [audit, setAudit] = useState<AuditEntry[]>([]);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [refreshKey, setRefreshKey] = useState(0);

  const [docFilter, setDocFilter] = useState("");
  const [kindFilter, setKindFilter] = useState("");
  const [confFilter, setConfFilter] = useState("");

  const [rejectOpen, setRejectOpen] = useState(false);
  const [rejectReason, setRejectReason] = useState("");

  const loadQueue = useCallback(async () => {
    if (!canReview) return;
    setLoading(true);
    setError(null);
    try {
      const page = await fetchExtractionQueue({
        document_id: docFilter || undefined,
        fact_kind: kindFilter || undefined,
        max_confidence: confFilter ? Number(confFilter) : undefined,
      });
      setItems(page.items);
      setTotal(page.total);
      setSelectedId((prev) => (page.items.some((item) => item.id === prev) ? prev : (page.items[0]?.id ?? null)));
    } catch (e) {
      setError(errText(e));
    } finally {
      setLoading(false);
    }
  }, [canReview, docFilter, kindFilter, confFilter]);

  useEffect(() => {
    void loadQueue();
  }, [loadQueue, refreshKey]);

  useEffect(() => {
    if (selectedId == null) {
      setDetail(null);
      setAudit([]);
      setDraft({});
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const [item, entries] = await Promise.all([
          fetchExtraction(selectedId),
          fetchExtractionAudit(selectedId),
        ]);
        if (cancelled) return;
        setDetail(item);
        setDraft(draftFrom(item));
        setAudit(entries);
      } catch (e) {
        if (!cancelled) setError(errText(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [selectedId, refreshKey]);

  const run = async (fn: () => Promise<unknown>, okMsg: string) => {
    if (busy) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await fn();
      setNotice(okMsg);
      setRefreshKey((key) => key + 1);
    } catch (e) {
      setError(errText(e));
    } finally {
      setBusy(false);
    }
  };

  const doApprove = () => {
    if (selectedId == null) return;
    return run(() => approveExtraction(selectedId), "Đã duyệt dòng đã chọn.");
  };

  const doBulk = () => {
    if (!detail) return;
    return run(
      () => bulkApproveExtractions({ extractor: detail.extractor, document_id: detail.document_id }),
      "Đã duyệt hàng loạt các dòng cùng luật trong tài liệu.",
    );
  };

  const doEdit = async () => {
    if (!detail) return;
    const edits: Record<string, unknown> = {};
    for (const field of fieldsFor(detail.kind)) {
      const before = detail.data?.[field.key];
      const beforeStr = before == null ? "" : String(before);
      const raw = draft[field.key] ?? "";
      if (raw.trim() === beforeStr) continue;
      if (field.numeric) {
        if (raw.trim() === "") {
          edits[field.key] = null;
          continue;
        }
        const parsed = Number(raw.trim().replace(",", "."));
        if (Number.isNaN(parsed)) {
          setError(`${field.label} phải là một số.`);
          return;
        }
        edits[field.key] = parsed;
      } else {
        edits[field.key] = raw.trim() === "" ? null : raw;
      }
    }
    if (Object.keys(edits).length === 0) {
      setError("Chưa sửa giá trị nào để duyệt.");
      return;
    }
    await run(
      () => editApproveExtraction(detail.id, edits as Partial<ExtractionData>),
      "Đã sửa giá trị và duyệt.",
    );
  };

  const confirmReject = async () => {
    const reason = rejectReason.trim();
    if (selectedId == null) return;
    if (!reason) {
      setError("Vui lòng nhập lý do từ chối.");
      return;
    }
    setRejectOpen(false);
    await run(() => rejectExtraction(selectedId, reason), "Đã từ chối dòng đã chọn.");
    setRejectReason("");
  };

  const moveSelection = (delta: number) => {
    if (items.length === 0) return;
    const index = items.findIndex((item) => item.id === selectedId);
    const next = Math.max(0, Math.min(items.length - 1, (index < 0 ? 0 : index) + delta));
    setSelectedId(items[next].id);
  };

  const keyRef = useRef({ approve: doApprove, openReject: () => setRejectOpen(true), move: moveSelection, canReview });
  useEffect(() => {
    keyRef.current = { approve: doApprove, openReject: () => setRejectOpen(true), move: moveSelection, canReview };
  });

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (!keyRef.current.canReview || rejectOpen) return;
      const target = event.target as HTMLElement | null;
      if (
        target &&
        (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.tagName === "SELECT" || target.isContentEditable)
      ) {
        return;
      }
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      const key = event.key.toLowerCase();
      if (key === "a") {
        event.preventDefault();
        void keyRef.current.approve();
      } else if (key === "r") {
        event.preventDefault();
        keyRef.current.openReject();
      } else if (key === "j" || event.key === "ArrowDown") {
        event.preventDefault();
        keyRef.current.move(1);
      } else if (key === "k" || event.key === "ArrowUp") {
        event.preventDefault();
        keyRef.current.move(-1);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [rejectOpen]);

  const documents = useMemo(
    () => [...state.documents].sort((a, b) => a.name.localeCompare(b.name)),
    [state.documents],
  );

  // ── Chưa đăng nhập / thiếu quyền ──
  if (!user) {
    return (
      <CenteredNotice
        icon={<IcLock size={26} style={{ color: COLOR.borderStrong }} />}
        title="Cần đăng nhập để duyệt tri thức"
        body="Hàng đợi duyệt chỉ dành cho vai trò Người duyệt hoặc Quản trị viên."
        action={
          <button
            className={`${buttonBase} border-none bg-brand text-white hover:bg-brand-dark`}
            onClick={() => actions.openLogin("Vui lòng đăng nhập để duyệt tri thức.")}
          >
            Đăng nhập
          </button>
        }
      />
    );
  }
  if (!canReview) {
    return (
      <CenteredNotice
        icon={<IcShield size={26} style={{ color: COLOR.borderStrong }} />}
        title="Tài khoản không có quyền duyệt"
        body={`Vai trò hiện tại là ${user.role}. Chỉ Người duyệt hoặc Quản trị viên mới xem được hàng đợi duyệt.`}
      />
    );
  }

  const currentFields = fieldsFor(detail?.kind ?? null);

  return (
    <main aria-label="Tri thức" style={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "column", background: COLOR.bg }}>
      {/* thanh lọc */}
      <div
        style={{
          flexShrink: 0,
          display: "flex",
          alignItems: "center",
          gap: 12,
          flexWrap: "wrap",
          padding: "12px 20px",
          background: COLOR.surface,
          borderBottom: `1px solid ${COLOR.border}`,
        }}
      >
        <span style={{ display: "inline-flex", alignItems: "center", gap: 7, fontWeight: 700, fontSize: "14.5px", color: COLOR.textPrimary }}>
          <IcShield size={16} style={{ color: COLOR.accent }} /> Hàng đợi duyệt
        </span>
        <span
          className="tabular-nums"
          style={{ fontSize: "11.5px", fontWeight: 700, background: COLOR.accentSoft, color: COLOR.accentDark, padding: "3px 10px", borderRadius: 9999 }}
        >
          {total} chờ duyệt
        </span>

        <div style={{ flex: 1 }} />

        <select value={docFilter} onChange={(e) => setDocFilter(e.target.value)} style={selectStyle} aria-label="Lọc theo tài liệu">
          <option value="">Tất cả tài liệu</option>
          {documents.map((doc) => (
            <option key={doc.id} value={doc.id}>
              {doc.name}
            </option>
          ))}
        </select>

        <select value={kindFilter} onChange={(e) => setKindFilter(e.target.value)} style={selectStyle} aria-label="Lọc theo loại dữ kiện">
          <option value="">Mọi loại dữ kiện</option>
          {Object.entries(FACT_KIND_LABEL).map(([key, label]) => (
            <option key={key} value={key}>
              {label}
            </option>
          ))}
        </select>

        <select value={confFilter} onChange={(e) => setConfFilter(e.target.value)} style={selectStyle} aria-label="Lọc theo điểm tin cậy">
          <option value="">Mọi độ tin cậy</option>
          <option value="0.6">Dưới 60% (khó)</option>
          <option value="0.85">Dưới 85%</option>
        </select>

        <button
          onClick={() => setRefreshKey((key) => key + 1)}
          title="Tải lại hàng đợi"
          aria-label="Tải lại hàng đợi"
          className={`${buttonBase} border border-[#DEE3EA] bg-white text-[#475467] hover:border-brand hover:text-brand`}
        >
          <IcRefresh size={14} /> Tải lại
        </button>
      </div>

      {(error || notice) && (
        <div
          role="status"
          style={{
            flexShrink: 0,
            display: "flex",
            alignItems: "center",
            gap: 8,
            padding: "9px 20px",
            fontSize: "12.5px",
            fontWeight: 600,
            background: error ? COLOR.dangerBg : COLOR.successBg,
            color: error ? COLOR.danger : COLOR.success,
            borderBottom: `1px solid ${error ? COLOR.dangerBorder : COLOR.successBorder}`,
          }}
        >
          {error ? <IcAlert size={14} /> : <IcCheck size={14} />}
          {error ?? notice}
        </div>
      )}

      <div style={{ flex: 1, minHeight: 0, display: "flex", overflow: "hidden" }}>
        {/* danh sách chờ duyệt */}
        <aside style={{ width: 360, flexShrink: 0, overflowY: "auto", borderRight: `1px solid ${COLOR.border}`, padding: 12, display: "flex", flexDirection: "column", gap: 8 }}>
          {loading && items.length === 0 ? (
            <div style={emptyStyle}>Đang tải hàng đợi…</div>
          ) : items.length === 0 ? (
            <div style={emptyStyle}>
              <IcCheck size={22} style={{ color: COLOR.success, marginBottom: 6 }} />
              <div style={{ fontWeight: 600, color: COLOR.textPrimary }}>Không còn dòng chờ duyệt</div>
              <div style={{ fontSize: "12.5px", color: COLOR.textSecondary, marginTop: 4 }}>Mọi dữ kiện đã được xử lý.</div>
            </div>
          ) : (
            items.map((item) => (
              <QueueRow
                key={item.id}
                item={item}
                active={item.id === selectedId}
                onClick={() => setSelectedId(item.id)}
              />
            ))
          )}
        </aside>

        {/* chi tiết: giá trị đã trích + nguồn tô sáng + lịch sử */}
        <section style={{ flex: 1, minWidth: 0, overflowY: "auto", padding: 18 }}>
          {!detail ? (
            <div style={emptyStyle}>Chọn một dòng ở bên trái để xem và duyệt.</div>
          ) : (
            <div style={{ maxWidth: 900, margin: "0 auto", display: "flex", flexDirection: "column", gap: 14 }}>
              {/* giá trị đã trích */}
              <div style={{ ...panelStyle, padding: "16px 18px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 9, flexWrap: "wrap", marginBottom: 12 }}>
                  <IcFile size={15} style={{ color: COLOR.accent }} />
                  <span style={{ fontWeight: 700, fontSize: "14px", color: COLOR.textPrimary }}>{detail.file_stem}</span>
                  <span style={kindBadge}>{detail.kind ? KIND_LABEL[detail.kind] : "—"}</span>
                  {detail.data?.fact_kind && <span style={kindBadge}>{FACT_KIND_LABEL[detail.data.fact_kind] ?? detail.data.fact_kind}</span>}
                  <ConfidenceBadge score={detail.confidence} />
                  <div style={{ flex: 1 }} />
                  <span style={{ fontSize: "11.5px", color: COLOR.textMuted, display: "inline-flex", alignItems: "center", gap: 5 }}>
                    <IcFolder size={12} /> {detail.section_path ?? "—"}
                  </span>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 10 }}>
                  {currentFields.map((field) => (
                    <label key={field.key} style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                      <span style={{ fontSize: "11px", fontWeight: 700, color: COLOR.textSecondary }}>{field.label}</span>
                      {field.multiline ? (
                        <textarea
                          value={draft[field.key] ?? ""}
                          onChange={(e) => setDraft((d) => ({ ...d, [field.key]: e.target.value }))}
                          rows={2}
                          style={inputStyle}
                        />
                      ) : (
                        <input
                          value={draft[field.key] ?? ""}
                          onChange={(e) => setDraft((d) => ({ ...d, [field.key]: e.target.value }))}
                          style={inputStyle}
                        />
                      )}
                    </label>
                  ))}
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", marginTop: 14 }}>
                  <button
                    onClick={() => void doApprove()}
                    disabled={busy}
                    title="Duyệt (A)"
                    className={`${buttonBase} border-none bg-brand text-white hover:bg-brand-dark`}
                  >
                    <IcCheck size={15} /> Duyệt <kbd style={kbdStyle}>A</kbd>
                  </button>
                  <button
                    onClick={() => setRejectOpen(true)}
                    disabled={busy}
                    title="Từ chối (R)"
                    className={`${buttonBase} border border-[#FECACA] bg-white text-[#DC2626] hover:bg-[#FEF2F2]`}
                  >
                    <IcX size={15} /> Từ chối <kbd style={kbdStyle}>R</kbd>
                  </button>
                  <button
                    onClick={() => void doEdit()}
                    disabled={busy}
                    title="Sửa giá trị rồi duyệt"
                    className={`${buttonBase} border border-[#DEE3EA] bg-white text-[#475467] hover:border-brand hover:text-brand`}
                  >
                    Sửa &amp; duyệt
                  </button>
                  <div style={{ flex: 1 }} />
                  <button
                    onClick={() => void doBulk()}
                    disabled={busy}
                    title="Duyệt mọi dòng cùng luật trong tài liệu này"
                    className={`${buttonBase} border border-[#C9D8FF] bg-[#E9EFFF] text-[#173CAE] hover:brightness-[0.98]`}
                  >
                    <IcCheck size={15} /> Duyệt hàng loạt cùng luật
                  </button>
                </div>
                <div style={{ marginTop: 8, fontSize: "11.5px", color: COLOR.textMuted }}>
                  Luật: <code>{detail.extractor}</code> · chunk: {detail.chunk_id ?? "—"} · tạo lúc {formatTime(detail.created_at)}
                </div>
              </div>

              {/* nguyên văn mục — đoạn trích tô sáng */}
              <div style={{ ...panelStyle, padding: "16px 18px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
                  <IcSearch size={15} style={{ color: COLOR.accent }} />
                  <span style={{ fontWeight: 700, fontSize: "13.5px", color: COLOR.textPrimary }}>Nguyên văn mục</span>
                  <span style={{ fontSize: "11.5px", color: COLOR.textMuted }}>{detail.source?.section_path ?? detail.section_path ?? "—"}</span>
                </div>
                {detail.source?.section_text ? (
                  <div
                    style={{
                      background: COLOR.accentSoft,
                      border: `2px solid ${COLOR.accent}`,
                      borderRadius: 8,
                      padding: "14px 16px",
                      position: "relative",
                      maxHeight: 320,
                      overflowY: "auto",
                      fontFamily: "'Lora', Georgia, serif",
                      fontSize: "13.5px",
                      lineHeight: 1.65,
                      color: COLOR.textPrimary,
                    }}
                  >
                    <span
                      style={{
                        position: "absolute",
                        top: -9,
                        right: 12,
                        background: COLOR.accent,
                        color: COLOR.textOnDark,
                        fontFamily: "'Be Vietnam Pro',sans-serif",
                        fontSize: "9.5px",
                        fontWeight: 700,
                        letterSpacing: ".03em",
                        padding: "2px 8px",
                        borderRadius: 9999,
                      }}
                    >
                      Đoạn trích nguồn
                    </span>
                    <QuoteHighlight
                      text={detail.source.section_text}
                      quote={detail.source.quote}
                      start={detail.source.quote_start}
                      end={detail.source.quote_end}
                    />
                  </div>
                ) : (
                  <div style={{ fontSize: "12.5px", color: COLOR.textSecondary }}>
                    Chưa dựng được nguyên văn mục. Đoạn trích đã trích: “{detail.quote}”
                  </div>
                )}
              </div>

              {/* lịch sử duyệt */}
              <div style={{ ...panelStyle, padding: "16px 18px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
                  <IcClock size={15} style={{ color: COLOR.textMuted }} />
                  <span style={{ fontWeight: 700, fontSize: "13.5px", color: COLOR.textPrimary }}>Lịch sử duyệt</span>
                  <span style={{ fontSize: "11.5px", color: COLOR.textMuted }}>{audit.length} mốc</span>
                </div>
                {audit.length === 0 ? (
                  <div style={{ fontSize: "12.5px", color: COLOR.textSecondary }}>Chưa có thao tác nào trên dòng này.</div>
                ) : (
                  <ol style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 8 }}>
                    {audit.map((entry) => (
                      <li key={entry.id} style={{ display: "flex", gap: 10, fontSize: "12.5px", color: COLOR.textSecondary }}>
                        <span
                          style={{
                            flexShrink: 0,
                            minWidth: 86,
                            fontWeight: 700,
                            color: entry.action === "reject" ? COLOR.danger : entry.action === "approve" ? COLOR.success : COLOR.accent,
                          }}
                        >
                          {ACTION_LABEL[entry.action] ?? entry.action}
                        </span>
                        <span style={{ minWidth: 0 }}>
                          <span style={{ fontWeight: 600, color: COLOR.textPrimary }}>{entry.actor_username ?? "hệ thống"}</span>{" "}
                          · {formatTime(entry.at)}
                          {describeChange(entry) && <div style={{ color: COLOR.textSecondary }}>{describeChange(entry)}</div>}
                        </span>
                      </li>
                    ))}
                  </ol>
                )}
              </div>
            </div>
          )}
        </section>
      </div>

      {/* hộp thoại lý do từ chối */}
      {rejectOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Lý do từ chối"
          style={{ position: "fixed", inset: 0, zIndex: 60, background: "rgba(16,24,40,.45)", display: "flex", alignItems: "center", justifyContent: "center", padding: 20 }}
          onClick={() => setRejectOpen(false)}
        >
          <div style={{ ...panelStyle, width: 460, maxWidth: "100%", padding: 20 }} onClick={(e) => e.stopPropagation()}>
            <div style={{ fontWeight: 700, fontSize: "15px", color: COLOR.textPrimary, marginBottom: 6 }}>Từ chối dòng đã chọn</div>
            <div style={{ fontSize: "12.5px", color: COLOR.textSecondary, marginBottom: 10 }}>
              Lý do là bắt buộc và được lưu vào lịch sử duyệt.
            </div>
            <textarea
              autoFocus
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              rows={3}
              placeholder="Ví dụ: sai đơn vị, không khớp nguyên văn…"
              style={inputStyle}
            />
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 14 }}>
              <button className={`${buttonBase} border border-[#DEE3EA] bg-white text-[#475467]`} onClick={() => setRejectOpen(false)}>
                Hủy
              </button>
              <button
                className={`${buttonBase} border-none bg-[#DC2626] text-white hover:brightness-110`}
                onClick={() => void confirmReject()}
                disabled={busy}
              >
                Xác nhận từ chối
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}

function QueueRow({ item, active, onClick }: { item: ExtractionItem; active: boolean; onClick: () => void }) {
  const label = item.data?.fact_kind ? (FACT_KIND_LABEL[item.data.fact_kind] ?? item.data.fact_kind) : item.kind ? KIND_LABEL[item.kind] : "—";
  return (
    <button
      onClick={onClick}
      aria-current={active ? "true" : undefined}
      style={{
        textAlign: "left",
        display: "flex",
        flexDirection: "column",
        gap: 5,
        padding: "10px 12px",
        borderRadius: 10,
        border: `1px solid ${active ? COLOR.accent : COLOR.border}`,
        background: active ? COLOR.accentSoft : COLOR.surface,
        cursor: "pointer",
        fontFamily: "inherit",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
        <span style={{ fontWeight: 700, fontSize: "12.5px", color: COLOR.textPrimary, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", flex: 1 }}>
          {item.file_stem}
        </span>
        <ConfidenceBadge score={item.confidence} />
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <span style={kindBadge}>{label}</span>
        <span style={{ fontSize: "11px", color: COLOR.textMuted, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
          {item.section_path ?? "—"}
        </span>
      </div>
      <div style={{ fontSize: "11.5px", color: COLOR.textSecondary, display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden" }}>
        {item.quote}
      </div>
    </button>
  );
}

function ConfidenceBadge({ score }: { score: number }) {
  const tone = confidenceColor(score);
  return (
    <span
      className="tabular-nums"
      title="Điểm tin cậy của trích xuất"
      style={{ flexShrink: 0, fontSize: "10.5px", fontWeight: 700, background: tone.bg, color: tone.color, padding: "2px 7px", borderRadius: 9999 }}
    >
      {Math.round(score * 100)}%
    </span>
  );
}

function CenteredNotice({ icon, title, body, action }: { icon: React.ReactNode; title: string; body: string; action?: React.ReactNode }) {
  return (
    <main aria-label="Tri thức" style={{ flex: 1, minHeight: 0, display: "flex", alignItems: "center", justifyContent: "center", background: COLOR.bg }}>
      <div style={{ ...panelStyle, maxWidth: 420, padding: "28px 26px", textAlign: "center", display: "flex", flexDirection: "column", alignItems: "center", gap: 8 }}>
        {icon}
        <div style={{ fontWeight: 700, fontSize: "15px", color: COLOR.textPrimary }}>{title}</div>
        <div style={{ fontSize: "13px", color: COLOR.textSecondary, lineHeight: 1.55 }}>{body}</div>
        {action}
      </div>
    </main>
  );
}

const selectStyle: React.CSSProperties = {
  height: 36,
  padding: "0 10px",
  borderRadius: 9,
  border: `1px solid ${COLOR.border}`,
  background: COLOR.surface,
  color: COLOR.textSecondary,
  fontSize: "12.5px",
  fontFamily: "inherit",
  cursor: "pointer",
};

const inputStyle: React.CSSProperties = {
  width: "100%",
  boxSizing: "border-box",
  padding: "7px 10px",
  borderRadius: 8,
  border: `1px solid ${COLOR.border}`,
  background: COLOR.surface,
  color: COLOR.textPrimary,
  fontSize: "12.5px",
  fontFamily: "inherit",
  resize: "vertical",
};

const kindBadge: React.CSSProperties = {
  flexShrink: 0,
  fontSize: "10.5px",
  fontWeight: 700,
  background: COLOR.surfaceAlt,
  color: COLOR.textSecondary,
  padding: "2px 8px",
  borderRadius: 9999,
};

const kbdStyle: React.CSSProperties = {
  fontFamily: "inherit",
  fontSize: "10px",
  fontWeight: 700,
  background: "rgba(255,255,255,.25)",
  borderRadius: 4,
  padding: "1px 5px",
};

const emptyStyle: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  textAlign: "center",
  padding: "40px 20px",
  color: COLOR.textSecondary,
  fontSize: "13px",
};
