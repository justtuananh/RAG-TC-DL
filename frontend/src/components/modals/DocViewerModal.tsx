import type { ViewingDoc } from "../../types";
import DocContentPane from "../docs/DocContentPane";
import DocInfoPanel from "../docs/DocInfoPanel";
import { IcFile, IcFolder, IcX } from "../common/icons";
import { COLOR } from "../../theme";

interface Props {
  viewingDoc: ViewingDoc | null;
  onClose: () => void;
}

/** Hộp thoại xem tài liệu — dùng khi mở tài liệu gốc từ trích dẫn trong Trò chuyện (không có "danh sách" để quay lại). */
export default function DocViewerModal({ viewingDoc, onClose }: Props) {
  if (!viewingDoc) return null;

  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 70,
        background: "rgba(15,23,42,.55)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 26,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: "100%",
          maxWidth: 1080,
          maxHeight: "90vh",
          background: COLOR.surface,
          borderRadius: 16,
          boxShadow: "0 24px 60px -12px rgba(0,0,0,.5)",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}
      >
        {/* header */}
        <div style={{ flexShrink: 0, display: "flex", alignItems: "center", gap: 12, padding: "15px 18px", borderBottom: `1px solid ${COLOR.border}` }}>
          <span
            aria-hidden
            style={{
              flexShrink: 0,
              width: 36,
              height: 36,
              borderRadius: 10,
              background: COLOR.accentSoft,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <IcFile size={17} style={{ color: COLOR.accentDark }} />
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
          <button
            onClick={onClose}
            title="Đóng"
            style={{ color: COLOR.textMuted }}
            className="w-9 h-9 rounded-lg border-none bg-transparent flex items-center justify-center cursor-pointer hover:bg-primary-container hover:text-on-primary-container"
          >
            <IcX size={18} />
          </button>
        </div>

        {/* body */}
        <div style={{ flex: 1, minHeight: 0, display: "flex" }}>
          <DocContentPane viewingDoc={viewingDoc} />
          <DocInfoPanel viewingDoc={viewingDoc} />
        </div>
      </div>
    </div>
  );
}
