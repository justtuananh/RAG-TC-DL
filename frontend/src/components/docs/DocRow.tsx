import type { CSSProperties } from "react";
import type { DocItem } from "../../types";
import type { Actions } from "../../store/useAppStore";
import { extColor } from "../../services/mockEngine";
import { IcCheck, IcClock, IcEye, IcPencil, IcPlay, IcTrash } from "../common/icons";

export default function DocRow({ doc, renaming, actions }: { doc: DocItem; renaming: boolean; actions: Actions }) {
  const isReady = doc.status === "ready";
  const isProcessing = doc.status === "processing";
  const isPending = doc.status === "pending";

  const meta = `${doc.ext}  ·  ${doc.size}  ·  ${doc.pages === "—" ? "… trang" : doc.pages + " trang"}  ·  ${doc.date}`;
  const statusLabel = isReady ? "Đã sẵn sàng" : isProcessing ? `Đang xử lý ${doc.progress || 0}%` : isPending ? "Chưa xử lý" : "Lỗi xử lý";
  const statusStyle: CSSProperties = {
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    flexShrink: 0,
    padding: "5px 11px",
    borderRadius: 9999,
    fontSize: "12px",
    fontWeight: 600,
    ...(isReady
      ? { background: "#F0FDF4", color: "#15803D", border: "1px solid #BBF7D0" }
      : isProcessing
        ? { background: "#FFFBEB", color: "#B45309", border: "1px solid #FDE68A" }
        : isPending
          ? { background: "#F1F5F9", color: "#64748B", border: "1px solid #E2E8F0" }
          : { background: "#FEF2F2", color: "#DC2626", border: "1px solid #FECACA" }),
  };

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 13, background: "#fff", border: "1px solid #E6EAE8", borderRadius: 13, padding: "13px 15px", boxShadow: "0 1px 2px rgba(15,23,42,.04)" }}>
      <div style={{ flexShrink: 0, width: 40, height: 48, borderRadius: 8, display: "flex", alignItems: "flex-end", justifyContent: "center", paddingBottom: 6, background: extColor(doc.ext) }}>
        <span style={{ fontFamily: "'Be Vietnam Pro',sans-serif", fontSize: "10.5px", fontWeight: 700, color: "#fff" }}>{doc.ext}</span>
      </div>

      <div style={{ flex: 1, minWidth: 0 }}>
        {renaming ? (
          <input
            autoFocus
            value={doc.name}
            onChange={(e) => actions.renameDoc(doc.id, e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                actions.commitRenameDoc();
              }
            }}
            onBlur={actions.commitRenameDoc}
            className="w-full border border-brand outline-none rounded-[7px] px-2 py-[5px] font-sans text-[14px] font-semibold text-slate-900 shadow-[0_0_0_3px_#DCFCE7]"
          />
        ) : (
          <div style={{ fontWeight: 600, fontSize: "14px", color: "#0F172A", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{doc.name}</div>
        )}
        <div style={{ fontSize: "11.5px", color: "#94A3B8", marginTop: 3 }}>{meta}</div>
        {isProcessing && (
          <div style={{ height: 6, background: "#F1F5F9", borderRadius: 9999, overflow: "hidden", marginTop: 7, maxWidth: 270 }}>
            <div style={{ height: "100%", borderRadius: 9999, background: "#F59E0B", width: `${doc.progress || 0}%` }} />
          </div>
        )}
      </div>

      <span style={statusStyle}>
        {isReady && <IcCheck size={12} strokeWidth={2.5} />}
        {isProcessing && <span className="animate-spin" style={{ width: 11, height: 11, border: "2px solid #FDE68A", borderTopColor: "#B45309", borderRadius: "50%" }} />}
        {isPending && <IcClock size={12} />}
        {statusLabel}
      </span>

      {isPending && (
        <button
          onClick={() => actions.processDoc(doc.id)}
          title="Bắt đầu xử lý tài liệu"
          className="inline-flex items-center gap-[6px] h-8 px-[13px] border-none rounded-lg bg-brand text-white font-sans text-[12.5px] font-semibold cursor-pointer flex-shrink-0 shadow-[0_1px_3px_rgba(22,163,74,.3)] hover:bg-brand-dark"
        >
          <IcPlay size={13} /> Xử lý
        </button>
      )}

      <div style={{ display: "flex", gap: 2, flexShrink: 0 }}>
        <button onClick={() => actions.viewDoc(doc)} title="Xem tài liệu" className="w-8 h-8 rounded-lg border-none bg-transparent flex items-center justify-center cursor-pointer text-slate-400 hover:bg-green-50 hover:text-brand">
          <IcEye size={15} />
        </button>
        <button onClick={() => actions.startRenameDoc(doc.id)} title="Đổi tên" className="w-8 h-8 rounded-lg border-none bg-transparent flex items-center justify-center cursor-pointer text-slate-400 hover:bg-slate-100 hover:text-slate-700">
          <IcPencil size={14} />
        </button>
        <button onClick={() => actions.deleteDoc(doc.id)} title="Xoá tài liệu" className="w-8 h-8 rounded-lg border-none bg-transparent flex items-center justify-center cursor-pointer text-slate-400 hover:bg-red-50 hover:text-[#DC2626]">
          <IcTrash size={14} />
        </button>
      </div>
    </div>
  );
}
