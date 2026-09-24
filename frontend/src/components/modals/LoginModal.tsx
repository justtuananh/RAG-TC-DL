import { useEffect, useState, type FormEvent } from "react";
import { COLOR } from "../../theme";
import { IcAlert, IcLock, IcX } from "../common/icons";

interface Props {
  open: boolean;
  busy: boolean;
  error: string | null;
  /** Lý do màn hình được mở (ví dụ: "cần đăng nhập để tải tài liệu lên"). */
  notice: string | null;
  onClose: () => void;
  onSubmit: (username: string, password: string) => void;
}

const inputCls =
  "h-10 border border-slate-300 rounded-[9px] px-3 font-sans text-[13.5px] text-slate-800 outline-none w-full focus:border-brand focus:shadow-[0_0_0_3px_#E9EFFF]";
const labelStyle = { fontSize: "12.5px", fontWeight: 600, color: COLOR.textSecondary } as const;

/**
 * Màn hình đăng nhập (modal) — theo đúng kiểu LlmConfigModal sẵn có.
 * Route đọc/chat vẫn dùng được khi chưa đăng nhập; modal này chỉ mở khi người
 * dùng bấm thao tác ghi (upload/process/delete/rename) hoặc khi token hết hạn.
 */
export default function LoginModal({ open, busy, error, notice, onClose, onSubmit }: Props) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  // Mỗi lần mở lại thì xoá nội dung cũ (không giữ mật khẩu trong bộ nhớ).
  useEffect(() => {
    if (open) {
      setUsername("");
      setPassword("");
    }
  }, [open]);

  if (!open) return null;

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (busy) return;
    onSubmit(username, password);
  };

  return (
    <div
      onClick={busy ? undefined : onClose}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 90,
        background: "rgba(15,23,42,.55)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 24,
      }}
    >
      <form
        onClick={(e) => e.stopPropagation()}
        onSubmit={submit}
        style={{
          background: COLOR.surface,
          borderRadius: 14,
          boxShadow: "0 24px 60px -12px rgba(0,0,0,.5)",
          maxWidth: 400,
          width: "100%",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}
      >
        {/* header */}
        <div style={{ flexShrink: 0, display: "flex", alignItems: "center", gap: 11, padding: "15px 18px", borderBottom: `1px solid ${COLOR.border}` }}>
          <div
            style={{
              width: 34,
              height: 34,
              borderRadius: 9,
              background: `linear-gradient(135deg, ${COLOR.accent}, ${COLOR.accentDark})`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}
          >
            <IcLock size={18} style={{ color: COLOR.textOnDark }} />
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontWeight: 700, fontSize: "15px", color: COLOR.textPrimary }}>Đăng nhập</div>
            <div style={{ fontSize: "11.5px", color: COLOR.textMuted }}>Dành cho thao tác tài liệu</div>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={busy}
            title="Đóng"
            aria-label="Đóng"
            className="w-8 h-8 rounded-lg border-none bg-transparent flex items-center justify-center cursor-pointer text-slate-500 hover:bg-slate-100 hover:text-slate-700 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <IcX size={17} />
          </button>
        </div>

        {/* body */}
        <div style={{ padding: 18, display: "flex", flexDirection: "column", gap: 14 }}>
          {notice && !error && (
            <div
              style={{
                background: COLOR.warningBg,
                border: `1px solid ${COLOR.warningBorder}`,
                borderRadius: 10,
                padding: "10px 12px",
                fontSize: "12.5px",
                lineHeight: 1.5,
                color: COLOR.warning,
                fontWeight: 600,
              }}
            >
              {notice}
            </div>
          )}

          {error && (
            <div
              role="alert"
              style={{
                background: COLOR.dangerBg,
                border: `1px solid ${COLOR.dangerBorder}`,
                borderRadius: 10,
                padding: 12,
                display: "flex",
                alignItems: "flex-start",
                gap: 7,
                color: COLOR.danger,
                fontSize: "13px",
                fontWeight: 600,
                lineHeight: 1.5,
              }}
            >
              <IcAlert size={15} strokeWidth={2.5} style={{ flexShrink: 0, marginTop: 1 }} /> {error}
            </div>
          )}

          <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
            <label htmlFor="login-username" style={labelStyle}>
              Tên đăng nhập
            </label>
            <input
              id="login-username"
              autoFocus
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="ví dụ: kythuat"
              className={inputCls}
            />
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
            <label htmlFor="login-password" style={labelStyle}>
              Mật khẩu
            </label>
            <input
              id="login-password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              className={inputCls}
            />
          </div>

          <div style={{ fontSize: "11.5px", color: COLOR.textMuted, lineHeight: 1.5 }}>
            Chỉ tài khoản <b>Kỹ thuật viên</b> hoặc <b>Quản trị viên</b> mới tải lên/xử lý/đổi tên/xoá tài liệu. Tài khoản Người xem vẫn tra cứu và trò chuyện
            bình thường.
          </div>
        </div>

        {/* footer */}
        <div style={{ flexShrink: 0, padding: "14px 18px", borderTop: `1px solid ${COLOR.border}`, display: "flex", gap: 10, justifyContent: "flex-end" }}>
          <button
            type="button"
            onClick={onClose}
            disabled={busy}
            className="h-10 px-4 border border-slate-200 bg-white rounded-[10px] font-sans text-[14px] font-semibold text-slate-600 cursor-pointer hover:bg-slate-100 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Huỷ
          </button>
          <button
            type="submit"
            disabled={busy}
            className="inline-flex items-center justify-center gap-2 h-10 px-[18px] border-none bg-brand rounded-[10px] font-sans text-[14px] font-semibold text-white cursor-pointer shadow-[0_2px_6px_rgba(36,84,224,.3)] hover:bg-brand-dark disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {busy && (
              <span
                className="animate-spin"
                style={{ width: 14, height: 14, border: `2px solid ${COLOR.accentSoftBorder}`, borderTopColor: COLOR.textOnDark, borderRadius: "50%" }}
              />
            )}
            {busy ? "Đang đăng nhập…" : "Đăng nhập"}
          </button>
        </div>
      </form>
    </div>
  );
}
