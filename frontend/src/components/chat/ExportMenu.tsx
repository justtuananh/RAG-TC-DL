import { useEffect, useRef, useState } from "react";
import type { ExportFormat } from "../../services/exportConversation";
import { COLOR, SHADOW } from "../../theme";
import { IcChevronDown, IcDownload } from "../common/icons";

interface Props {
  onExport: (format: ExportFormat) => void;
}

const OPTIONS: { format: ExportFormat; label: string; hint: string }[] = [
  { format: "docx", label: "Word (.docx)", hint: "Văn bản trình bày sẵn để in, gửi" },
  { format: "json", label: "JSON (.json)", hint: "Dữ liệu thô: câu hỏi, trả lời, nguồn" },
];

/** Nút "Xuất" ở đầu khung chat: chọn định dạng rồi tải hội thoại hiện tại. */
export default function ExportMenu({ onExport }: Props) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div ref={ref} style={{ position: "relative", flexShrink: 0, marginLeft: "auto" }}>
      <button
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        title="Xuất hội thoại ra file"
        className="inline-flex items-center gap-[6px] h-[30px] px-[10px] rounded-lg border border-line bg-transparent font-sans text-[12.5px] font-semibold text-secondary cursor-pointer hover:border-brand hover:text-brand-dark"
      >
        <IcDownload size={14} /> Xuất
        <IcChevronDown size={12} style={{ opacity: 0.7 }} />
      </button>
      {open && (
        <div
          role="menu"
          style={{
            position: "absolute",
            right: 0,
            top: "calc(100% + 6px)",
            zIndex: 60,
            minWidth: 250,
            background: COLOR.surface,
            border: `1px solid ${COLOR.border}`,
            borderRadius: 11,
            boxShadow: SHADOW.lg,
            padding: 6,
          }}
        >
          {OPTIONS.map((o) => (
            <button
              key={o.format}
              role="menuitem"
              onClick={() => {
                setOpen(false);
                onExport(o.format);
              }}
              className="w-full flex flex-col items-start gap-[2px] px-3 py-2 border-none bg-transparent rounded-lg font-sans text-left cursor-pointer hover:bg-row-hover"
            >
              <span style={{ fontSize: "13px", fontWeight: 600, color: COLOR.textPrimary }}>{o.label}</span>
              <span style={{ fontSize: "11.5px", color: COLOR.textMuted }}>{o.hint}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
