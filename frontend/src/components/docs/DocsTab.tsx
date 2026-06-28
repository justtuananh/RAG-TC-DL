import type { AppState } from "../../types";
import type { Actions } from "../../store/useAppStore";
import { IcChevronLeft, IcChevronRight, IcSearch, IcUpload } from "../common/icons";
import DocRow from "./DocRow";

const navBtn = "w-8 h-8 rounded-[7px] border border-[#becabd] bg-white flex items-center justify-center text-[#3f4940] font-sans cursor-pointer";

export default function DocsTab({ state, actions }: { state: AppState; actions: Actions }) {
  const q = state.docSearch.trim().toLowerCase();
  const filtered = q ? state.documents.filter((d) => d.name.toLowerCase().indexOf(q) >= 0) : state.documents.slice();
  const size = state.docPageSize;
  const total = filtered.length;
  const pageCount = Math.max(1, Math.ceil(total / size));
  const page = Math.min(Math.max(1, state.docPage), pageCount);
  const start = (page - 1) * size;
  const items = filtered.slice(start, start + size);
  const readyCount = state.documents.filter((d) => d.status === "ready").length;

  return (
    <main aria-label="Tài liệu" style={{ flex: 1, minHeight: 0, overflowY: "auto", background: "#eaedff" }}>
      <div style={{ maxWidth: 820, margin: "0 auto", padding: "22px 24px 28px" }}>
        <h1 style={{ fontSize: "22px", fontWeight: 700, margin: "0 0 4px", color: "#131b2e" }}>Tài liệu</h1>
        <p style={{ margin: "0 0 18px", color: "#3f4940", fontSize: "14px" }}>Tải lên và quản lý các tài liệu mà trợ lý dùng để trả lời câu hỏi của bạn.</p>

        {/* upload */}
        <button
          onClick={actions.uploadDemo}
          className="w-full border-2 border-dashed border-[#becabd] bg-[#f2f3ff] rounded-[14px] p-[18px] flex flex-col items-center gap-[5px] cursor-pointer font-sans hover:border-brand hover:bg-[#eaedff]"
        >
          <div style={{ width: 42, height: 42, borderRadius: 9999, background: "#fff", border: "1px solid #becabd", display: "flex", alignItems: "center", justifyContent: "center", boxShadow: "0 2px 6px rgba(0,97,48,.15)" }}>
            <IcUpload size={24} style={{ color: "#006130" }} />
          </div>
          <div style={{ fontWeight: 700, fontSize: "15.5px", color: "#006130" }}>Kéo thả tài liệu vào đây</div>
          <div style={{ fontSize: "13px", color: "#3f4940" }}>hoặc bấm để chọn tệp — hỗ trợ PDF, Word (tối đa 50&nbsp;MB)</div>
        </button>

        {/* heading row */}
        <div style={{ display: "flex", alignItems: "center", gap: 9, margin: "24px 0 12px" }}>
          <span style={{ fontWeight: 700, fontSize: "14px", color: "#131b2e" }}>Tài liệu của bạn</span>
          <span style={{ fontSize: "11.5px", fontWeight: 700, background: "#dae2fd", color: "#006130", padding: "3px 10px", borderRadius: 9999 }}>{state.documents.length} tệp</span>
          <div style={{ flex: 1 }} />
          <span style={{ fontSize: "12.5px", color: "#3f4940" }}>{readyCount} tài liệu sẵn sàng</span>
        </div>

        {/* search + page size */}
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12, flexWrap: "wrap" }}>
          <div className="flex items-center gap-2 bg-white border border-[#becabd] rounded-[10px] px-3 h-10 flex-1 min-w-[220px] focus-within:border-brand focus-within:shadow-[0_0_0_3px_#dae2fd]">
            <IcSearch size={16} style={{ color: "#6f7a6f" }} />
            <input value={state.docSearch} onChange={(e) => actions.setDocSearch(e.target.value)} aria-label="Tìm tệp theo tên" placeholder="Tìm tệp theo tên…" className="flex-1 min-w-0 border-none outline-none font-sans text-[13.5px] text-[#131b2e] bg-transparent" />
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
            <span style={{ fontSize: "12.5px", color: "#3f4940", fontWeight: 600 }}>Hiển thị:</span>
            <div style={{ display: "flex", gap: 2, background: "#fff", border: "1px solid #becabd", borderRadius: 9, padding: 3 }}>
              {[5, 10, 100].map((n) => {
                const a = n === size;
                return (
                  <button
                    key={n}
                    onClick={() => actions.setDocPageSize(n)}
                    className="min-w-[34px] h-7 px-[9px] border-none rounded-[7px] font-sans text-[12.5px] font-semibold cursor-pointer"
                    style={{ background: a ? "#006130" : "transparent", color: a ? "#fff" : "#3f4940" }}
                  >
                    {n}
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* list (khung cao cố định, cuộn nội bộ) */}
        <div role="region" aria-label="Danh sách tài liệu" style={{ display: "flex", flexDirection: "column", gap: 9, maxHeight: "min(430px, calc(100vh - 340px))", overflowY: "auto", paddingRight: 4 }}>
          {total === 0 ? (
            <div style={{ textAlign: "center", padding: "48px 0", color: "#3f4940", fontSize: "14px", border: "1px dashed #becabd", borderRadius: 13, background: "#fff" }}>
              Không tìm thấy tệp phù hợp.
            </div>
          ) : (
            items.map((d) => <DocRow key={d.id} doc={d} renaming={state.renamingDoc === d.id} actions={actions} />)
          )}
        </div>

        {/* pagination */}
        {pageCount > 1 && (
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 14, flexWrap: "wrap", flexShrink: 0 }}>
            <span style={{ fontSize: "12.5px", color: "#3f4940" }}>
              Hiển thị {total === 0 ? 0 : start + 1}–{Math.min(start + size, total)} / {total} tệp
            </span>
            <div style={{ flex: 1 }} />
            <button onClick={() => actions.setDocPage(Math.max(1, page - 1))} disabled={page <= 1} aria-label="Trang trước" title="Trang trước" className={navBtn} style={page > 1 ? undefined : { opacity: 0.4, cursor: "default" }}>
              <IcChevronLeft size={15} />
            </button>
            {Array.from({ length: pageCount }, (_, i) => i + 1).map((n) => {
              const a = n === page;
              return (
                <button
                  key={n}
                  onClick={() => actions.setDocPage(n)}
                  className="min-w-[30px] h-[30px] px-2 rounded-[7px] font-sans text-[12.5px] font-semibold cursor-pointer"
                  style={{ border: `1px solid ${a ? "#006130" : "#becabd"}`, background: a ? "#006130" : "#fff", color: a ? "#fff" : "#3f4940" }}
                >
                  {n}
                </button>
              );
            })}
            <button onClick={() => actions.setDocPage(Math.min(pageCount, page + 1))} disabled={page >= pageCount} aria-label="Trang sau" title="Trang sau" className={navBtn} style={page < pageCount ? undefined : { opacity: 0.4, cursor: "default" }}>
              <IcChevronRight size={15} />
            </button>
          </div>
        )}
      </div>
    </main>
  );
}
