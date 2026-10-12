import { useEffect, useState } from "react";
import type { ViewingDoc } from "../../types";
import FormulaReviewPanel from "./FormulaReviewPanel";
import { COLOR } from "../../theme";
import DocContentPane from "./DocContentPane";
import DocInfoPanel from "./DocInfoPanel";
import { IcArrowRight, IcFile, IcFolder } from "../common/icons";

/** Trang xem tài liệu - hiển thị NGAY TRONG khung Tài liệu (không phải hộp thoại nổi), cao đúng khung nhìn. */
export default function DocViewerPanel({
  viewingDoc,
  onBack,
  onDirtyChange,
}: {
  viewingDoc: ViewingDoc;
  onBack: () => void;
  onDirtyChange: (dirty: boolean) => void;
}) {
  useEffect(() => () => onDirtyChange(false), [onDirtyChange]);
  // Panel công thức chỉ mount khi mở lần đầu, rồi giữ nguyên (ẩn) để không mất phần đang sửa.
  const [formulaOpened, setFormulaOpened] = useState(false);
  const [tab, setTab] = useState<"document" | "formulas">("document");
  return (
    <div
      style={{
        flex: 1,
        minHeight: 0,
        display: "flex",
        flexDirection: "column",
        background: COLOR.surface,
        border: `1px solid ${COLOR.border}`,
        borderRadius: 14,
        overflow: "hidden",
      }}
    >
      {/* header */}
      <div style={{ flexShrink: 0, display: "flex", alignItems: "center", gap: 12, padding: "15px 18px", borderBottom: `1px solid ${COLOR.border}` }}>
        <button
          onClick={onBack}
          title="Quay lại danh sách tài liệu"
          className="flex-shrink-0 inline-flex items-center gap-[6px] h-8 px-[11px] border border-line rounded-[9px] bg-white font-sans text-[12.5px] font-semibold text-secondary cursor-pointer transition-colors hover:border-brand hover:text-brand"
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

      <div className="flex-shrink-0 flex flex-wrap gap-2 px-4 sm:px-5 py-3 border-b border-line bg-surface" role="tablist" aria-label="Nội dung tài liệu">
        <button
          role="tab"
          aria-selected={tab === "document"}
          className={`px-3 py-2 rounded-lg border font-sans text-[12.5px] font-semibold transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand ${tab === "document" ? "border-primary-container bg-primary-container text-brand" : "border-line text-secondary hover:border-brand hover:text-brand"}`}
          onClick={() => setTab("document")}
        >
          Tài liệu gốc
        </button>
        <button
          role="tab"
          aria-selected={tab === "formulas"}
          className={`px-3 py-2 rounded-lg border font-sans text-[12.5px] font-semibold transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand ${tab === "formulas" ? "border-primary-container bg-primary-container text-brand" : "border-line text-secondary hover:border-brand hover:text-brand"}`}
          onClick={() => {
            setFormulaOpened(true);
            setTab("formulas");
          }}
        >
          Công thức và phê duyệt
        </button>
      </div>
      {formulaOpened && (
        <div style={{ flex: 1, minHeight: 0, overflow: "auto", display: tab === "formulas" ? "block" : "none" }}>
          <FormulaReviewPanel
            onDirtyChange={onDirtyChange}
            key={viewingDoc.code}
            documentId={viewingDoc.code}
            isDocx={viewingDoc.ext === "DOCX" || viewingDoc.name.toLowerCase().endsWith(".docx")}
          />
        </div>
      )}
      {tab === "document" && (
        /* body - khung tài liệu tự cuộn (thanh cuộn riêng), đầu trang + panel thông tin đứng yên */
        <div style={{ flex: 1, minHeight: 0, display: "flex" }}>
          <DocContentPane viewingDoc={viewingDoc} />
          <DocInfoPanel viewingDoc={viewingDoc} />
        </div>
      )}
    </div>
  );
}
