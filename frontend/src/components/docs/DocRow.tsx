import type { CSSProperties } from "react";
import type { DocItem } from "../../types";
import type { Actions } from "../../store/useAppStore";
import { extColor } from "../../services/mockEngine";
import { COLOR } from "../../theme";
import { STATUS_STYLE, statusLabel } from "./docStatus";
import { IcAlert, IcCheck, IcClock, IcEye, IcPencil, IcPlay, IcTrash } from "../common/icons";

const actionBtn =
  "w-8 h-8 rounded-lg border-none bg-transparent flex items-center justify-center cursor-pointer transition-transform active:scale-90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-brand";

export default function DocRow({ doc, renaming, actions }: { doc: DocItem; renaming: boolean; actions: Actions }) {
  const isReady = doc.status === "ready";
  const isProcessing = doc.status === "processing";
  const isPending = doc.status === "pending";
  const st = STATUS_STYLE[doc.status];

  const meta = `${doc.ext}  ·  ${doc.size}  ·  ${doc.pages === "—" ? "… trang" : doc.pages + " trang"}  ·  ${doc.date}`;
  const statusStyle: CSSProperties = {
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    flexShrink: 0,
    padding: "5px 11px",
    borderRadius: 9999,
    fontSize: "12px",
    fontWeight: 600,
    background: st.bg,
    color: st.color,
    border: `1px solid ${st.border}`,
  };

  return (
    <div
      style={{
        position: "relative",
        display: "flex",
        alignItems: "center",
        gap: 13,
        background: COLOR.surface,
        border: `1px solid ${COLOR.border}`,
        borderRadius: 13,
        padding: "13px 15px 13px 19px",
        boxShadow: "0 1px 2px rgba(16,24,40,.06)",
        transition: "box-shadow .18s ease, transform .18s ease",
      }}
      className="hover:shadow-[0_6px_18px_-8px_rgba(36,84,224,.24)] hover:-translate-y-[1px]"
    >
      <span aria-hidden style={{ position: "absolute", left: 0, top: 8, bottom: 8, width: 3, borderRadius: 9999, background: st.bar }} />

      <div
        style={{
          flexShrink: 0,
          width: 40,
          height: 48,
          borderRadius: 8,
          display: "flex",
          alignItems: "flex-end",
          justifyContent: "center",
          paddingBottom: 6,
          background: extColor(doc.ext),
          boxShadow: "0 2px 5px -1px rgba(19,27,46,.25)",
        }}
      >
        <span style={{ fontFamily: "'Be Vietnam Pro',sans-serif", fontSize: "10.5px", fontWeight: 700, color: COLOR.textOnDark }}>{doc.ext}</span>
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
            className="w-full border border-brand outline-none rounded-[7px] px-2 py-[5px] font-sans text-[14px] font-semibold text-[#101828] shadow-[0_0_0_3px_#E9EFFF]"
          />
        ) : (
          <div style={{ fontWeight: 600, fontSize: "14px", color: COLOR.textPrimary, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
            {doc.name}
          </div>
        )}
        <div className="tabular-nums" style={{ fontSize: "11.5px", color: COLOR.textSecondary, marginTop: 3 }}>
          {meta}
        </div>
        {isProcessing && (
          <div style={{ height: 6, background: COLOR.surfaceMuted, borderRadius: 9999, overflow: "hidden", marginTop: 7, maxWidth: 270 }}>
            <div style={{ height: "100%", borderRadius: 9999, background: COLOR.warning, width: `${doc.progress || 0}%`, transition: "width .3s ease" }} />
          </div>
        )}
      </div>

      <span style={statusStyle} title={doc.status === "error" ? doc.error : undefined}>
        {isReady && <IcCheck size={12} strokeWidth={2.5} />}
        {isProcessing && (
          <span
            className="animate-spin"
            style={{ width: 11, height: 11, border: `2px solid ${COLOR.warningBorder}`, borderTopColor: COLOR.warning, borderRadius: "50%" }}
          />
        )}
        {isPending && <IcClock size={12} />}
        {doc.status === "error" && <IcAlert size={12} />}
        <span className="tabular-nums">{statusLabel(doc)}</span>
      </span>

      {isPending && (
        <button
          onClick={() => actions.processDoc(doc.id)}
          title="Bắt đầu xử lý tài liệu"
          className="inline-flex items-center gap-[6px] h-8 px-[13px] border-none rounded-lg bg-brand text-white font-sans text-[12.5px] font-semibold cursor-pointer flex-shrink-0 shadow-[0_1px_3px_rgba(0,97,48,.3)] transition-transform hover:bg-brand-dark active:scale-95 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-brand"
        >
          <IcPlay size={13} /> Xử lý
        </button>
      )}

      <div style={{ display: "flex", gap: 2, flexShrink: 0 }}>
        <button
          onClick={() => actions.viewDoc(doc)}
          aria-label="Xem tài liệu"
          title="Xem tài liệu"
          className={`${actionBtn} text-[#7C8896] hover:bg-[#E9EFFF] hover:text-brand`}
        >
          <IcEye size={15} />
        </button>
        <button
          onClick={() => actions.startRenameDoc(doc.id)}
          aria-label="Đổi tên"
          title="Đổi tên"
          className={`${actionBtn} text-[#7C8896] hover:bg-[#E8ECF2] hover:text-[#101828]`}
        >
          <IcPencil size={14} />
        </button>
        <button
          onClick={() => actions.deleteDoc(doc.id)}
          aria-label="Xoá tài liệu"
          title="Xoá tài liệu"
          className={`${actionBtn} text-[#7C8896] hover:bg-red-50 hover:text-[#DC2626]`}
        >
          <IcTrash size={14} />
        </button>
      </div>
    </div>
  );
}
