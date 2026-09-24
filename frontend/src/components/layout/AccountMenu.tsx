import { useEffect, useRef, useState } from "react";
import type { AuthState } from "../../types";
import { COLOR, SHADOW } from "../../theme";
import { ROLE_LABEL } from "../../services/auth";
import { IcChevronDown, IcLogOut, IcUser } from "../common/icons";

interface Props {
  auth: AuthState;
  onLogin: () => void;
  onLogout: () => void;
}

const pill = "inline-flex items-center gap-[7px] h-[34px] px-3 rounded-full border font-sans text-[12.5px] font-semibold cursor-pointer transition-colors";

/**
 * Nút tài khoản trên thanh trên cùng: chưa đăng nhập → "Đăng nhập";
 * đã đăng nhập → tên + menu vai trò/đăng xuất. Không ép đăng nhập để đọc/chat.
 */
export default function AccountMenu({ auth, onLogin, onLogout }: Props) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const user = auth.user;

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

  // Đang khôi phục phiên từ localStorage — giữ chỗ để tránh nhấp nháy nút "Đăng nhập".
  if (!user && !auth.restoreDone) {
    return <span aria-hidden style={{ display: "inline-block", width: 104, height: 34 }} />;
  }

  if (!user) {
    return (
      <button
        onClick={onLogin}
        title="Đăng nhập để tải lên/xử lý tài liệu"
        className={`${pill} border-[#DEE3EA] bg-white text-[#475467] hover:border-brand hover:text-brand`}
      >
        <IcUser size={15} /> Đăng nhập
      </button>
    );
  }

  const displayName = user.full_name || user.username;

  return (
    <div ref={ref} style={{ position: "relative" }}>
      <button
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        title={displayName}
        className={`${pill} border-[#C9D8FF] bg-[#E9EFFF] text-[#173CAE] hover:brightness-[0.98]`}
      >
        <IcUser size={15} />
        <span style={{ maxWidth: 150, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{displayName}</span>
        <IcChevronDown size={13} style={{ opacity: 0.7 }} />
      </button>

      {open && (
        <div
          role="menu"
          style={{
            position: "absolute",
            right: 0,
            top: "calc(100% + 6px)",
            zIndex: 60,
            minWidth: 220,
            background: COLOR.surface,
            border: `1px solid ${COLOR.border}`,
            borderRadius: 11,
            boxShadow: SHADOW.lg,
            padding: 6,
          }}
        >
          <div style={{ padding: "8px 10px 9px", borderBottom: `1px solid ${COLOR.border}`, marginBottom: 4 }}>
            <div style={{ fontSize: "13px", fontWeight: 700, color: COLOR.textPrimary, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
              {displayName}
            </div>
            <div style={{ fontSize: "11.5px", color: COLOR.textMuted, marginTop: 2 }}>
              {user.username} · {ROLE_LABEL[user.role]}
            </div>
          </div>
          <button
            role="menuitem"
            onClick={() => {
              setOpen(false);
              onLogout();
            }}
            className="w-full flex items-center gap-2 px-3 h-9 border-none bg-transparent rounded-lg font-sans text-[13px] text-left text-[#DC2626] cursor-pointer hover:bg-red-50"
          >
            <IcLogOut size={14} /> Đăng xuất
          </button>
        </div>
      )}
    </div>
  );
}
