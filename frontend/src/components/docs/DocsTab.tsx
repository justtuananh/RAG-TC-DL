import { useRef, useState } from "react";
import type { AppState, DocStatus } from "../../types";
import type { Actions } from "../../store/useAppStore";
import { COLOR } from "../../theme";
import { IcChevronLeft, IcChevronRight, IcFolder, IcGrid, IcList, IcSearch, IcUpload, IcX } from "../common/icons";
import { STATUS_TAB_LABEL } from "./docStatus";
import DocRow from "./DocRow";
import DocTableRow from "./DocTableRow";
import DocViewerPanel from "./DocViewerPanel";

type ViewMode = "table" | "cards";
type StatusFilter = AppState["docStatusFilter"];

const STATUS_TABS: { key: StatusFilter; label: string }[] = [
  { key: "all", label: "Tất cả" },
  { key: "ready", label: STATUS_TAB_LABEL.ready },
  { key: "processing", label: STATUS_TAB_LABEL.processing },
  { key: "pending", label: STATUS_TAB_LABEL.pending },
  { key: "error", label: STATUS_TAB_LABEL.error },
];

const navBtn =
  "w-8 h-8 rounded-[7px] border border-[#DEE3EA] bg-white flex items-center justify-center text-[#475467] font-sans cursor-pointer transition-all hover:border-brand hover:text-brand active:scale-90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-brand disabled:opacity-40 disabled:pointer-events-none";

const emptyBoxStyle = {
  display: "flex",
  flexDirection: "column" as const,
  alignItems: "center",
  textAlign: "center" as const,
  padding: "40px 20px",
};

const th = "text-left px-4 py-[10px] text-[11px] font-bold uppercase tracking-wide text-[#475467] border-b border-[#DEE3EA]";

/** Danh sách số trang rút gọn kiểu "1 2 … 11" khi có nhiều trang. */
function pageNumbers(page: number, pageCount: number): (number | "…")[] {
  if (pageCount <= 7) return Array.from({ length: pageCount }, (_, i) => i + 1);
  const set = new Set([1, 2, pageCount - 1, pageCount, page - 1, page, page + 1]);
  const nums = Array.from(set)
    .filter((n) => n >= 1 && n <= pageCount)
    .sort((a, b) => a - b);
  const out: (number | "…")[] = [];
  nums.forEach((n, i) => {
    if (i > 0 && n - (nums[i - 1] as number) > 1) out.push("…");
    out.push(n);
  });
  return out;
}

export default function DocsTab({ state, actions }: { state: AppState; actions: Actions }) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [dragActive, setDragActive] = useState(false);
  const [view, setView] = useState<ViewMode>("table");

  const handleFiles = (files: FileList | null) => {
    const file = files?.[0];
    if (file) actions.uploadDoc(file);
  };

  const statusFiltered = state.docStatusFilter === "all" ? state.documents : state.documents.filter((d) => d.status === state.docStatusFilter);
  const q = state.docSearch.trim().toLowerCase();
  const filtered = q ? statusFiltered.filter((d) => d.name.toLowerCase().indexOf(q) >= 0) : statusFiltered.slice();
  const size = state.docPageSize;
  const total = filtered.length;
  const pageCount = Math.max(1, Math.ceil(total / size));
  const page = Math.min(Math.max(1, state.docPage), pageCount);
  const start = (page - 1) * size;
  const items = filtered.slice(start, start + size);
  const hasNoDocsAtAll = state.documents.length === 0;
  const countOf = (s: DocStatus) => state.documents.filter((d) => d.status === s).length;
  const activeTabLabel = STATUS_TABS.find((t) => t.key === state.docStatusFilter)?.label ?? "Tất cả";

  return (
    <main
      aria-label="Tài liệu"
      style={{ flex: 1, minHeight: 0, overflowY: "auto", background: COLOR.bg }}
      onDragOver={(e) => {
        e.preventDefault();
        setDragActive(true);
      }}
      onDragLeave={() => setDragActive(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragActive(false);
        handleFiles(e.dataTransfer.files);
      }}
    >
      <div style={{ maxWidth: 1800, margin: "0 auto", padding: "20px 24px 28px" }}>
        <input
          ref={fileInputRef}
          type="file"
          accept=".docx,.pdf"
          hidden
          onChange={(e) => {
            handleFiles(e.target.files);
            e.target.value = "";
          }}
        />

        {state.viewingDoc ? (
          <DocViewerPanel viewingDoc={state.viewingDoc} onBack={actions.closeViewer} />
        ) : (
          <>
            {/* thanh lọc theo trạng thái */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 12,
                flexWrap: "wrap",
                background: COLOR.surface,
                border: `1px solid ${COLOR.border}`,
                borderRadius: 13,
                padding: "11px 16px",
                marginBottom: 14,
              }}
            >
              <span
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 7,
                  fontSize: "11.5px",
                  fontWeight: 700,
                  color: COLOR.textSecondary,
                  letterSpacing: ".04em",
                }}
              >
                <IcFolder size={14} style={{ color: COLOR.textMuted }} /> TRẠNG THÁI:
              </span>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                {STATUS_TABS.map((t) => {
                  const active = t.key === state.docStatusFilter;
                  return (
                    <button
                      key={t.key}
                      onClick={() => actions.setDocStatusFilter(t.key)}
                      className="h-8 px-[13px] border-none rounded-[9px] font-sans text-[12.5px] font-semibold cursor-pointer transition-all active:scale-95 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-brand"
                      style={{ background: active ? COLOR.accent : "transparent", color: active ? COLOR.textOnDark : COLOR.textSecondary }}
                    >
                      {t.label}
                      {t.key !== "all" && (
                        <span className="tabular-nums" style={{ marginLeft: 6, opacity: 0.75 }}>
                          {countOf(t.key)}
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* khung tài liệu: toolbar + danh sách + phân trang */}
            <div style={{ position: "relative", background: COLOR.surface, border: `1px solid ${COLOR.border}`, borderRadius: 14, overflow: "hidden" }}>
              {dragActive && (
                <div
                  style={{
                    position: "absolute",
                    inset: 0,
                    zIndex: 10,
                    background: "rgba(233,239,255,.92)",
                    border: `2px dashed ${COLOR.accent}`,
                    borderRadius: 14,
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: 6,
                    pointerEvents: "none",
                  }}
                >
                  <IcUpload size={26} style={{ color: COLOR.accent }} />
                  <div style={{ fontWeight: 700, fontSize: "14.5px", color: COLOR.accent }}>Thả tệp vào đây để tải lên</div>
                </div>
              )}

              <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", padding: "15px 16px" }}>
                <span style={{ fontWeight: 700, fontSize: "14.5px", color: COLOR.textPrimary }}>
                  {state.docStatusFilter === "all" ? "Tất cả tài liệu" : activeTabLabel}
                </span>
                <span
                  className="tabular-nums"
                  style={{
                    fontSize: "11.5px",
                    fontWeight: 700,
                    background: COLOR.accentSoft,
                    color: COLOR.accentDark,
                    padding: "3px 10px",
                    borderRadius: 9999,
                  }}
                >
                  {total} tệp
                </span>
                <div style={{ flex: 1 }} />

                <div className="flex items-center gap-2 bg-white border border-[#DEE3EA] rounded-[10px] px-3 h-9 w-[220px] transition-shadow focus-within:border-brand focus-within:shadow-[0_0_0_3px_#E9EFFF]">
                  <IcSearch size={15} style={{ color: "#7C8896", flexShrink: 0 }} />
                  <input
                    value={state.docSearch}
                    onChange={(e) => actions.setDocSearch(e.target.value)}
                    aria-label="Tìm tệp theo tên"
                    placeholder="Tìm kiếm…"
                    className="flex-1 min-w-0 border-none outline-none font-sans text-[13px] text-[#101828] bg-transparent"
                  />
                  {state.docSearch && (
                    <button
                      onClick={() => actions.setDocSearch("")}
                      aria-label="Xóa tìm kiếm"
                      title="Xóa tìm kiếm"
                      className="flex-shrink-0 w-5 h-5 rounded-full border-none bg-[#E9EFFF] text-[#475467] flex items-center justify-center cursor-pointer transition-colors hover:bg-[#C9D8FF] hover:text-brand"
                    >
                      <IcX size={11} />
                    </button>
                  )}
                </div>

                <div style={{ display: "flex", gap: 2, background: COLOR.surfaceAlt, border: `1px solid ${COLOR.border}`, borderRadius: 9, padding: 3 }}>
                  <button
                    onClick={() => setView("table")}
                    title="Xem dạng bảng"
                    aria-pressed={view === "table"}
                    className="w-8 h-[26px] border-none rounded-[7px] flex items-center justify-center cursor-pointer transition-all active:scale-90"
                    style={{ background: view === "table" ? COLOR.accent : "transparent", color: view === "table" ? COLOR.textOnDark : COLOR.textSecondary }}
                  >
                    <IcList size={14} />
                  </button>
                  <button
                    onClick={() => setView("cards")}
                    title="Xem dạng thẻ"
                    aria-pressed={view === "cards"}
                    className="w-8 h-[26px] border-none rounded-[7px] flex items-center justify-center cursor-pointer transition-all active:scale-90"
                    style={{ background: view === "cards" ? COLOR.accent : "transparent", color: view === "cards" ? COLOR.textOnDark : COLOR.textSecondary }}
                  >
                    <IcGrid size={14} />
                  </button>
                </div>

                <button
                  onClick={() => fileInputRef.current?.click()}
                  className="inline-flex items-center gap-[7px] h-9 px-[14px] border-none rounded-[10px] bg-brand text-white font-sans text-[13px] font-semibold cursor-pointer shadow-[0_1px_3px_rgba(0,97,48,.3)] transition-transform hover:bg-brand-dark active:scale-95 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-brand"
                  title="Chọn tệp Word (.docx) hoặc PDF (.pdf) để tải lên — hoặc kéo thả vào bất kỳ đâu trong khung này"
                >
                  <IcUpload size={15} /> Tải lên
                </button>
              </div>

              {hasNoDocsAtAll ? (
                <div style={emptyBoxStyle}>
                  <IcFolder size={26} style={{ color: COLOR.borderStrong, marginBottom: 8 }} />
                  <div style={{ fontWeight: 600, fontSize: "14px", color: COLOR.textPrimary, marginBottom: 4 }}>Chưa có tài liệu nào</div>
                  <div style={{ fontSize: "13px", color: COLOR.textSecondary, maxWidth: 320 }}>
                    Kéo thả tệp vào đây hoặc bấm "Tải lên" để tải tài liệu đầu tiên.
                  </div>
                </div>
              ) : total === 0 ? (
                <div style={emptyBoxStyle}>
                  <IcSearch size={26} style={{ color: COLOR.borderStrong, marginBottom: 8 }} />
                  <div style={{ fontWeight: 600, fontSize: "14px", color: COLOR.textPrimary, marginBottom: 4 }}>Không tìm thấy tệp phù hợp</div>
                  <div style={{ fontSize: "13px", color: COLOR.textSecondary, marginBottom: 12, maxWidth: 320 }}>
                    {state.docSearch ? `Không có tệp nào khớp với "${state.docSearch}".` : "Không có tệp nào ở trạng thái này."}
                  </div>
                  {(state.docSearch || state.docStatusFilter !== "all") && (
                    <button
                      onClick={() => {
                        actions.setDocSearch("");
                        actions.setDocStatusFilter("all");
                      }}
                      className="h-8 px-4 border border-[#DEE3EA] rounded-lg bg-white font-sans text-[12.5px] font-semibold text-[#475467] cursor-pointer transition-colors hover:border-brand hover:text-brand active:scale-95"
                    >
                      Xóa bộ lọc
                    </button>
                  )}
                </div>
              ) : view === "table" ? (
                <div style={{ overflowX: "auto" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse" }}>
                    <thead>
                      <tr>
                        <th className={th}>Tên</th>
                        <th className={th}>Trạng thái</th>
                        <th className={th}>Ngày</th>
                        <th className={th}>Kích thước</th>
                        <th className={th} aria-label="Hành động" />
                      </tr>
                    </thead>
                    <tbody>
                      {items.map((d) => (
                        <DocTableRow key={d.id} doc={d} renaming={state.renamingDoc === d.id} actions={actions} />
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div role="region" aria-label="Danh sách tài liệu" style={{ display: "flex", flexDirection: "column", gap: 9, padding: 16 }}>
                  {items.map((d, i) => (
                    <div key={d.id} className="animate-fadeUp" style={{ animationDelay: `${Math.min(i, 8) * 30}ms`, animationFillMode: "backwards" }}>
                      <DocRow doc={d} renaming={state.renamingDoc === d.id} actions={actions} />
                    </div>
                  ))}
                </div>
              )}

              {/* phân trang */}
              {total > 0 && (
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    flexWrap: "wrap",
                    padding: "12px 16px",
                    borderTop: `1px solid ${COLOR.border}`,
                  }}
                >
                  <span className="tabular-nums" style={{ fontSize: "12.5px", color: COLOR.textSecondary }}>
                    Hiển thị {start + 1}–{Math.min(start + size, total)} trong số {total} tài liệu
                  </span>
                  <div style={{ flex: 1 }} />
                  {pageCount > 1 && (
                    <>
                      <button
                        onClick={() => actions.setDocPage(Math.max(1, page - 1))}
                        disabled={page <= 1}
                        aria-label="Trang trước"
                        title="Trang trước"
                        className={navBtn}
                      >
                        <IcChevronLeft size={15} />
                      </button>
                      {pageNumbers(page, pageCount).map((n, i) =>
                        n === "…" ? (
                          <span key={`e${i}`} style={{ padding: "0 4px", fontSize: "12.5px", color: COLOR.textMuted }}>
                            …
                          </span>
                        ) : (
                          <button
                            key={n}
                            onClick={() => actions.setDocPage(n)}
                            className="min-w-[30px] h-[30px] px-2 rounded-[7px] font-sans text-[12.5px] font-semibold cursor-pointer tabular-nums transition-all active:scale-90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-brand"
                            style={{
                              border: `1px solid ${n === page ? COLOR.accent : COLOR.border}`,
                              background: n === page ? COLOR.accent : COLOR.surface,
                              color: n === page ? COLOR.textOnDark : COLOR.textSecondary,
                            }}
                          >
                            {n}
                          </button>
                        ),
                      )}
                      <button
                        onClick={() => actions.setDocPage(Math.min(pageCount, page + 1))}
                        disabled={page >= pageCount}
                        aria-label="Trang sau"
                        title="Trang sau"
                        className={navBtn}
                      >
                        <IcChevronRight size={15} />
                      </button>
                      <span className="tabular-nums" style={{ fontSize: "12.5px", color: COLOR.textSecondary, marginLeft: 4, whiteSpace: "nowrap" }}>
                        Trang {page}/{pageCount}
                      </span>
                    </>
                  )}
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </main>
  );
}
