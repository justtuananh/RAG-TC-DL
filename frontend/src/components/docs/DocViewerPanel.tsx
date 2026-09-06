import type { ViewingDoc } from "../../types";
import { COLOR } from "../../theme";
import DocContentPane from "./DocContentPane";
import DocInfoPanel from "./DocInfoPanel";
import { IcArrowRight, IcFile, IcFolder } from "../common/icons";

/** Trang xem tài liệu — hiển thị NGAY TRONG khung Tài liệu (không phải hộp thoại nổi), giống ảnh mẫu. */
export default function DocViewerPanel({ viewingDoc, onBack }: { viewingDoc: ViewingDoc; onBack: () => void }) {
  return (
    <div style={{ background: COLOR.surface, border: `1px solid ${COLOR.border}`, borderRadius: 14, overflow: "hidden" }}>
      {/* header */}
      <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "15px 18px", borderBottom: `1px solid ${COLOR.border}` }}>
        <button
          onClick={onBack}
          title="Quay lại danh sách tài liệu"
          className="flex-shrink-0 inline-flex items-center gap-[6px] h-8 px-[11px] border border-[#DEE3EA] rounded-[9px] bg-white font-sans text-[12.5px] font-semibold text-[#475467] cursor-pointer transition-colors hover:border-brand hover:text-brand"
        >
          <IcArrowRight size={13} style={{ transform: "rotate(180deg)" }} /> Tài liệu
        </button>
        <span
          aria-hidden
          style={{
            flexShrink: 0,
            width: 34,
            height: 34,
            borderRadius: 10,
            background: COLOR.accentSoft,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <IcFile size={16} style={{ color: COLOR.accent }} />
        </span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 700, fontSize: "15px", color: COLOR.textPrimary, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
            {viewingDoc.name}
          </div>
          <div style={{ fontSize: "11.5px", color: COLOR.textMuted, display: "flex", alignItems: "center", gap: 6, minWidth: 0 }}>
            <span style={{ flexShrink: 0 }}>Bản xem tài liệu</span>
            {viewingDoc.sectionPath && (
              <>
                <IcFolder size={11} style={{ flexShrink: 0 }} />
                <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{viewingDoc.sectionPath}</span>
              </>
            )}
          </div>
        </div>
      </div>

      {/* body */}
      <div style={{ display: "flex", minHeight: "calc(100vh - 230px)" }}>
        <DocContentPane viewingDoc={viewingDoc} />
        <DocInfoPanel viewingDoc={viewingDoc} />
      </div>
    </div>
  );
}
