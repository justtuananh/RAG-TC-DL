import { useEffect, useRef, useState } from "react";
import type { DocItem } from "../../types";
import type { Actions } from "../../store/useAppStore";
import { COLOR, SHADOW } from "../../theme";
import { IcEye, IcMoreHorizontal, IcPencil, IcPlay, IcTrash } from "../common/icons";

const item =
  "w-full flex items-center gap-2 px-3 h-9 border-none bg-transparent font-sans text-[13px] text-left cursor-pointer whitespace-nowrap hover:bg-[#E9EFFF]";

export default function DocActionsMenu({ doc, actions }: { doc: DocItem; actions: Actions }) {
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
    <div ref={ref} style={{ position: "relative" }}>
      <button
        onClick={() => setOpen((v) => !v)}
        aria-label="Thao tác khác"
        aria-haspopup="menu"
        aria-expanded={open}
        title="Thao tác khác"
        className="w-8 h-8 rounded-lg border-none bg-transparent flex items-center justify-center cursor-pointer text-[#7C8896] transition-colors hover:bg-[#E9EFFF] hover:text-[#101828] active:scale-90"
      >
        <IcMoreHorizontal size={16} />
      </button>
      {open && (
        <div
          role="menu"
          style={{
            position: "absolute",
            right: 0,
            top: "calc(100% + 4px)",
            zIndex: 30,
            minWidth: 168,
            background: COLOR.surface,
            border: `1px solid ${COLOR.border}`,
            borderRadius: 10,
            boxShadow: SHADOW.lg,
            padding: 4,
            overflow: "hidden",
          }}
        >
          <button
            role="menuitem"
            onClick={() => {
              setOpen(false);
              actions.viewDoc(doc);
            }}
            className={`${item} rounded-md text-[#101828]`}
          >
            <IcEye size={14} style={{ color: "#7C8896" }} /> Xem tài liệu
          </button>
          {doc.status === "pending" && (
            <button
              role="menuitem"
              onClick={() => {
                setOpen(false);
                actions.processDoc(doc.id);
              }}
              className={`${item} rounded-md text-brand font-semibold`}
            >
              <IcPlay size={13} style={{ color: COLOR.accent }} /> Xử lý ngay
            </button>
          )}
          <button
            role="menuitem"
            onClick={() => {
              setOpen(false);
              actions.startRenameDoc(doc.id);
            }}
            className={`${item} rounded-md text-[#101828]`}
          >
            <IcPencil size={13} style={{ color: "#7C8896" }} /> Đổi tên
          </button>
          <button
            role="menuitem"
            onClick={() => {
              setOpen(false);
              actions.deleteDoc(doc.id);
            }}
            className={`${item} rounded-md text-[#DC2626]`}
          >
            <IcTrash size={13} /> Xoá tài liệu
          </button>
        </div>
      )}
    </div>
  );
}
