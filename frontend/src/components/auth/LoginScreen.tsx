import { useState, type FormEvent } from "react";
import { COLOR, SHADOW } from "../../theme";
import { IcAlert, IcBrand, IcLock } from "../common/icons";

interface Props {
  busy: boolean;
  error: string | null;
  /** Thông báo kèm theo (ví dụ: phiên đăng nhập đã hết hạn). */
  notice: string | null;
  onSubmit: (username: string, password: string) => void;
}

const inputCls =
  "h-11 border border-line-strong rounded-[10px] px-3 font-sans text-[14px] text-on-surface outline-none w-full bg-white focus:border-brand focus:shadow-focus";
const labelStyle = { fontSize: "12.5px", fontWeight: 600, color: COLOR.textSecondary } as const;

const FEATURES = [
  "Tra cứu nguyên văn quy trình kiểm định (QTKĐ)",
  "Công thức giữ đúng như tài liệu gốc, kèm trích dẫn nguồn",
  "Tải xuống tệp gốc đúng định dạng đã tải lên",
];

/**
 * Màn hình đăng nhập toàn trang. Đăng nhập là bắt buộc: chưa đăng nhập thì không thấy
 * trò chuyện hay tài liệu (mọi route dữ liệu ở backend đều yêu cầu token).
 */
export default function LoginScreen({ busy, error, notice, onSubmit }: Props) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (busy) return;
    onSubmit(username, password);
  };

  return (
    <main className="font-sans" style={{ minHeight: "100vh", display: "flex", background: COLOR.bg, color: COLOR.textPrimary }}>
      {/* cột thương hiệu - cùng tông xanh rêu với sidebar; ẩn trên màn hẹp */}
      <aside
        className="hidden md:flex"
        style={{
          flex: "0 0 42%",
          maxWidth: 560,
          flexDirection: "column",
          justifyContent: "space-between",
          padding: "44px 48px",
          background: `radial-gradient(120% 80% at 0% 0%, ${COLOR.sidebarBgAlt} 0%, ${COLOR.sidebarBg} 60%)`,
          color: COLOR.textOnDark,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span
            aria-hidden
            style={{
              width: 40,
              height: 40,
              borderRadius: 11,
              background: `linear-gradient(135deg, ${COLOR.accent}, ${COLOR.accentDark})`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              boxShadow: SHADOW.sidebar,
            }}
          >
            <IcBrand size={21} style={{ color: COLOR.star }} />
          </span>
          <div style={{ lineHeight: 1.25 }}>
            <div style={{ fontSize: "16px", fontWeight: 700 }}>Trợ lý Kiểm định</div>
            <div style={{ fontSize: "12px", color: COLOR.sidebarTextMuted }}>Tra cứu quy trình kiểm định</div>
          </div>
        </div>

        <div>
          <h1 style={{ fontSize: "30px", lineHeight: 1.2, fontWeight: 700, letterSpacing: "-0.01em", margin: "0 0 18px" }}>
            Tra cứu chính xác,
            <br />
            <span style={{ color: COLOR.accentOnDark }}>trích dẫn đúng nguồn.</span>
          </h1>
          <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 11 }}>
            {FEATURES.map((f) => (
              <li key={f} style={{ display: "flex", alignItems: "flex-start", gap: 10, fontSize: "13.5px", lineHeight: 1.5, color: COLOR.sidebarText }}>
                <span aria-hidden style={{ width: 6, height: 6, borderRadius: 9999, background: COLOR.accentOnDark, marginTop: 8, flexShrink: 0 }} />
                {f}
              </li>
            ))}
          </ul>
        </div>

        <div style={{ fontSize: "11.5px", color: COLOR.sidebarTextMuted }}>Chạy hoàn toàn nội bộ - dữ liệu không rời khỏi máy chủ.</div>
      </aside>

      {/* biểu mẫu */}
      <section style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", padding: "32px 16px" }}>
        <form onSubmit={submit} aria-labelledby="login-title" style={{ width: "100%", maxWidth: 380, display: "flex", flexDirection: "column", gap: 16 }}>
          {/* thương hiệu gọn cho màn hẹp (cột thương hiệu bên trái bị ẩn) */}
          <div className="flex md:hidden" style={{ alignItems: "center", gap: 10, marginBottom: 18 }}>
            <span
              aria-hidden
              style={{
                width: 32,
                height: 32,
                borderRadius: 9,
                background: `linear-gradient(135deg, ${COLOR.accent}, ${COLOR.accentDark})`,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <IcBrand size={17} style={{ color: COLOR.star }} />
            </span>
            <span style={{ fontSize: "14.5px", fontWeight: 700, color: COLOR.textPrimary }}>Trợ lý Kiểm định</span>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6, marginBottom: 6 }}>
            <span
              aria-hidden
              className="hidden md:flex"
              style={{
                width: 40,
                height: 40,
                borderRadius: 11,
                background: COLOR.accentSoft,
                border: `1px solid ${COLOR.accentSoftBorder}`,
                alignItems: "center",
                justifyContent: "center",
                marginBottom: 8,
              }}
            >
              <IcLock size={19} style={{ color: COLOR.accentDark }} />
            </span>
            <h2 id="login-title" style={{ margin: 0, fontSize: "22px", fontWeight: 700, color: COLOR.textPrimary }}>
              Đăng nhập
            </h2>
            <p style={{ margin: 0, fontSize: "13px", color: COLOR.textMuted, lineHeight: 1.5 }}>Dùng tài khoản do quản trị viên cấp để tiếp tục.</p>
          </div>

          {notice && !error && (
            <div
              role="status"
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
              <IcAlert size={15} strokeWidth={2.5} style={{ flexShrink: 0, marginTop: 2 }} /> {error}
            </div>
          )}

          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
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

          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
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

          <button
            type="submit"
            disabled={busy}
            className="mt-1 inline-flex items-center justify-center gap-2 h-11 px-[18px] border-none bg-brand rounded-[10px] font-sans text-[14px] font-semibold text-white cursor-pointer shadow-brand transition-colors hover:bg-brand-dark active:scale-[0.99] disabled:opacity-60 disabled:cursor-not-allowed focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
          >
            {busy && (
              <span
                className="animate-spin"
                style={{ width: 14, height: 14, border: `2px solid ${COLOR.accentSoftBorder}`, borderTopColor: COLOR.textOnDark, borderRadius: "50%" }}
              />
            )}
            {busy ? "Đang đăng nhập…" : "Đăng nhập"}
          </button>

          <p style={{ margin: 0, fontSize: "11.5px", color: COLOR.textMuted, lineHeight: 1.55 }}>
            Mọi tài khoản đều tra cứu và trò chuyện được. Chỉ <b>Kỹ thuật viên</b> và <b>Quản trị viên</b> mới tải lên, xử lý, đổi tên hoặc xoá tài liệu.
          </p>
        </form>
      </section>
    </main>
  );
}
