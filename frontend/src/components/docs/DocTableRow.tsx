import type { DocItem } from "../../types";
import type { Actions } from "../../store/useAppStore";
import { extColor } from "../../services/mockEngine";
import { COLOR } from "../../theme";
import { STATUS_STYLE, statusLabel } from "./docStatus";
import DocActionsMenu from "./DocActionsMenu";
import { IcAlert, IcCheck, IcClock, IcPlay } from "../common/icons";

const td = "px-4 py-[11px] border-b border-line align-middle";

export default function DocTableRow({ doc, renaming, actions }: { doc: DocItem; renaming: boolean; actions: Actions }) {
  const isReady = doc.status === "ready";
  const isProcessing = doc.status === "processing";
  const isPending = doc.status === "pending";
  const st = STATUS_STYLE[doc.status];
  // `error` và `superseded` đều mang câu giải thích trong `doc.error`; hiện làm chú thích của nhãn trạng thái.
  const statusNote = doc.status === "error" || doc.status === "superseded" ? doc.error : undefined;
  // Riêng `superseded`, câu lý do ("Đã có phiên bản mới hơn: …") còn hiện thành dòng phụ
  // ngay dưới tên tệp để đọc được mà không cần rê chuột vào nhãn trạng thái.
  const supersededNote = doc.status === "superseded" ? doc.error : undefined;

  return (
    <tr className="hover:bg-row-hover transition-colors">
      <td className={td} style={{ minWidth: 220 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 11 }}>
          <span
            aria-hidden
            style={{
              flexShrink: 0,
              width: 32,
              height: 38,
              borderRadius: 7,
              display: "flex",
              alignItems: "flex-end",
              justifyContent: "center",
              paddingBottom: 5,
              background: extColor(doc.ext),
              boxShadow: `0 2px 5px -1px ${COLOR.shadowStrong}`,
            }}
          >
            <span style={{ fontFamily: "'Be Vietnam Pro',sans-serif", fontSize: "9px", fontWeight: 700, color: COLOR.textOnDark }}>{doc.ext}</span>
          </span>
          <div style={{ minWidth: 0 }}>
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
                className="w-full border border-brand outline-none rounded-[7px] px-2 py-[4px] font-sans text-[13.5px] font-semibold text-on-surface shadow-focus"
              />
            ) : (
              <button
                onClick={() => actions.viewDoc(doc)}
                title="Xem tài liệu"
                className="block text-left border-none bg-transparent p-0 font-sans cursor-pointer hover:text-brand hover:underline"
                style={{
                  fontWeight: 600,
                  fontSize: "13.5px",
                  color: COLOR.textPrimary,
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  maxWidth: 560,
                }}
              >
                {doc.name}
              </button>
            )}
            {supersededNote && (
              <div
                title={supersededNote}
                style={{
                  fontSize: "12px",
                  color: COLOR.textSecondary,
                  marginTop: 2,
                  maxWidth: 560,
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                }}
              >
                {supersededNote}
              </div>
            )}
            {isProcessing && (
              <div style={{ height: 5, background: COLOR.surfaceMuted, borderRadius: 9999, overflow: "hidden", marginTop: 5, maxWidth: 160 }}>
                <div style={{ height: "100%", borderRadius: 9999, background: COLOR.warning, width: `${doc.progress || 0}%`, transition: "width .3s ease" }} />
              </div>
            )}
          </div>
        </div>
      </td>

      <td className={td}>
        <span
          title={statusNote}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 5,
            padding: "4px 10px",
            borderRadius: 9999,
            fontSize: "11.5px",
            fontWeight: 600,
            whiteSpace: "nowrap",
            background: st.bg,
            color: st.color,
            border: `1px solid ${st.border}`,
          }}
        >
          {isReady && <IcCheck size={11} strokeWidth={2.5} />}
          {isProcessing && (
            <span
              className="animate-spin"
              style={{ width: 10, height: 10, border: `2px solid ${COLOR.warningBorder}`, borderTopColor: COLOR.warning, borderRadius: "50%" }}
            />
          )}
          {isPending && <IcClock size={11} />}
          {doc.status === "error" && <IcAlert size={11} />}
          <span className="tabular-nums">{statusLabel(doc)}</span>
        </span>
      </td>

      <td className={td} style={{ color: COLOR.textSecondary, fontSize: "12.5px" }}>
        <span className="tabular-nums">{doc.date}</span>
      </td>

      <td className={td} style={{ color: COLOR.textSecondary, fontSize: "12.5px" }}>
        <span className="tabular-nums">{doc.size}</span>
      </td>

      <td className={td} style={{ textAlign: "right", width: 1 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "flex-end", gap: 6 }}>
          {isPending && (
            <button
              onClick={() => actions.processDoc(doc.id)}
              title="Bắt đầu xử lý tài liệu"
              className="inline-flex items-center gap-[5px] h-7 px-[10px] border-none rounded-md bg-brand text-white font-sans text-[11.5px] font-semibold cursor-pointer flex-shrink-0 transition-transform hover:bg-brand-dark active:scale-95"
            >
              <IcPlay size={11} /> Xử lý
            </button>
          )}
          <DocActionsMenu doc={doc} actions={actions} />
        </div>
      </td>
    </tr>
  );
}
