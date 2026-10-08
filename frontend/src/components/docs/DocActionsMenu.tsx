import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type { DocItem } from "../../types";
import type { Actions } from "../../store/useAppStore";
import { COLOR, SHADOW } from "../../theme";
import { IcEye, IcMoreHorizontal, IcPencil, IcPlay, IcTrash } from "../common/icons";

// Menu nổi phải thoát khỏi khung bảng (overflow: hidden / auto) nên render qua portal với
// position: fixed, tính vị trí từ nút bấm; thiếu chỗ phía dưới thì lật lên trên.
const MENU_GAP = 4;
const MENU_MIN_WIDTH = 168;
const VIEWPORT_MARGIN = 8;

interface MenuPosition {
  top: number;
  left: number;
}

function placeMenu(anchor: DOMRect, menu: { width: number; height: number }): MenuPosition {
  const below = anchor.bottom + MENU_GAP;
  const fitsBelow = below + menu.height <= window.innerHeight - VIEWPORT_MARGIN;
  const top = fitsBelow ? below : Math.max(VIEWPORT_MARGIN, anchor.top - MENU_GAP - menu.height);
  const left = Math.min(Math.max(VIEWPORT_MARGIN, anchor.right - menu.width), window.innerWidth - menu.width - VIEWPORT_MARGIN);
  return { top, left };
}

const item =
  "w-full flex items-center gap-2 px-3 h-9 border-none bg-transparent font-sans text-[13px] text-left cursor-pointer whitespace-nowrap hover:bg-row-hover";

export default function DocActionsMenu({ doc, actions }: { doc: DocItem; actions: Actions }) {
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState<MenuPosition | null>(null);
  const ref = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {
    if (!open) {
      setPosition(null);
      return;
    }
    const anchor = ref.current?.getBoundingClientRect();
    const menu = menuRef.current;
    if (!anchor || !menu) return;
    setPosition(placeMenu(anchor, { width: menu.offsetWidth, height: menu.offsetHeight }));
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const inside = (target: EventTarget | null) => target instanceof Node && (ref.current?.contains(target) || menuRef.current?.contains(target));
    const onDown = (e: MouseEvent) => {
      if (!inside(e.target)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    // Vị trí fixed không đi theo khi cuộn hay đổi kích thước: đóng menu thay vì để nó trôi lệch.
    const close = (e: Event) => {
      if (!inside(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    window.addEventListener("scroll", close, true);
    window.addEventListener("resize", close);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
      window.removeEventListener("scroll", close, true);
      window.removeEventListener("resize", close);
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
        className="w-8 h-8 rounded-lg border-none bg-transparent flex items-center justify-center cursor-pointer text-icon-muted transition-colors hover:bg-row-hover hover:text-on-surface active:scale-90"
      >
        <IcMoreHorizontal size={16} />
      </button>
      {open &&
        createPortal(
          <div
            ref={menuRef}
            role="menu"
            style={{
              position: "fixed",
              top: position?.top ?? 0,
              left: position?.left ?? 0,
              // Đo kích thước ở lượt đầu khi chưa có vị trí, tránh nháy menu ở góc trên trái.
              visibility: position ? "visible" : "hidden",
              zIndex: 60,
              minWidth: MENU_MIN_WIDTH,
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
              className={`${item} rounded-md text-on-surface`}
            >
              <IcEye size={14} style={{ color: COLOR.textMuted }} /> Xem tài liệu
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
              className={`${item} rounded-md text-on-surface`}
            >
              <IcPencil size={13} style={{ color: COLOR.textMuted }} /> Đổi tên
            </button>
            <button
              role="menuitem"
              onClick={() => {
                setOpen(false);
                actions.deleteDoc(doc.id);
              }}
              className={`${item} rounded-md text-error`}
            >
              <IcTrash size={13} /> Xoá tài liệu
            </button>
          </div>,
          document.body,
        )}
    </div>
  );
}
