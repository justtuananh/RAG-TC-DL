import type { ViewingDoc } from "../../types";
import DocPage from "../common/DocPage";
import Markdown from "../common/Markdown";
import { IcFile, IcX } from "../common/icons";

interface Props {
  viewingDoc: ViewingDoc | null;
  onClose: () => void;
}

export default function DocViewerModal({ viewingDoc, onClose }: Props) {
  if (!viewingDoc) return null;
  const pageLabel = viewingDoc.pages ? `TRANG 01 / ${String(viewingDoc.pages).padStart(2, "0")}` : "TRANG 01";

  return (
    <div
      onClick={onClose}
      style={{ position: "fixed", inset: 0, zIndex: 70, background: "rgba(15,23,42,.55)", display: "flex", alignItems: "center", justifyContent: "center", padding: 30 }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{ width: "100%", maxWidth: 720, maxHeight: "88vh", background: "#F1F4F2", borderRadius: 14, boxShadow: "0 24px 60px -12px rgba(0,0,0,.5)", display: "flex", flexDirection: "column", overflow: "hidden" }}
      >
        {/* header */}
        <div style={{ flexShrink: 0, display: "flex", alignItems: "center", gap: 11, padding: "13px 16px", background: "#fff", borderBottom: "1px solid #E6EAE8" }}>
          <IcFile size={17} style={{ color: "#16A34A" }} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontWeight: 700, fontSize: "13.5px", color: "#0F172A", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{viewingDoc.name}</div>
            <div style={{ fontSize: "11.5px", color: "#94A3B8" }}>Bản xem tài liệu</div>
          </div>
          <button
            onClick={onClose}
            title="Đóng"
            className="w-8 h-8 rounded-lg border-none bg-transparent flex items-center justify-center cursor-pointer text-slate-500 hover:bg-slate-100 hover:text-slate-700"
          >
            <IcX size={17} />
          </button>
        </div>

        {/* body */}
        <div style={{ flex: 1, overflowY: "auto", padding: 20 }}>
          {viewingDoc.markdown != null ? (
            <div style={{ maxWidth: 600, margin: "0 auto", background: "#fff", border: "1px solid #E6EAE8", borderRadius: 6, boxShadow: "0 6px 22px -10px rgba(15,23,42,.16)", padding: "30px 36px 26px" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", paddingBottom: 11, marginBottom: 5, borderBottom: "1px dashed #E2E8F0", fontFamily: "'Be Vietnam Pro',sans-serif", fontSize: "10.5px", letterSpacing: ".08em", color: "#94A3B8", textTransform: "uppercase" }}>
                <span>{viewingDoc.code}</span>
                <span>Tài liệu nguồn</span>
              </div>
              <Markdown className="md-doc">{viewingDoc.markdown}</Markdown>
            </div>
          ) : (
            <DocPage code={viewingDoc.code} topRight={pageLabel} footLabel={pageLabel} blocks={viewingDoc.blocks} withHighlight={false} paperPadding="30px 36px 26px" />
          )}
        </div>
      </div>
    </div>
  );
}
