import type { LlmConfig, LlmTestResult } from "../../types";
import { IcCheck, IcCpu, IcAlert, IcX, IcZap } from "../common/icons";
import { COLOR } from "../../theme";

interface Props {
  open: boolean;
  llm: LlmConfig;
  testing: boolean;
  result: LlmTestResult | null;
  onClose: () => void;
  onChange: (field: keyof LlmConfig, v: string) => void;
  onTest: () => void;
  onSave: () => void;
}

const inputCls =
  "h-10 border border-slate-300 rounded-[9px] px-3 font-sans text-[13.5px] text-slate-800 outline-none w-full focus:border-brand focus:shadow-[0_0_0_3px_#E9EFFF]";
const labelStyle = { fontSize: "12.5px", fontWeight: 600, color: COLOR.textSecondary } as const;

export default function LlmConfigModal({ open, llm, testing, result, onClose, onChange, onTest, onSave }: Props) {
  if (!open) return null;
  const testOk = !!(result && result.ok);
  const testErr = !!(result && !result.ok);

  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 85,
        background: "rgba(15,23,42,.55)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 24,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: COLOR.surface,
          borderRadius: 14,
          boxShadow: "0 24px 60px -12px rgba(0,0,0,.5)",
          maxWidth: 460,
          width: "100%",
          maxHeight: "90vh",
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
            <IcCpu size={18} style={{ color: COLOR.textOnDark }} />
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontWeight: 700, fontSize: "15px", color: COLOR.textPrimary }}>Cấu hình mô hình ngôn ngữ</div>
            <div style={{ fontSize: "11.5px", color: COLOR.textMuted }}>Tương thích OpenAI API</div>
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
        <div style={{ flex: 1, overflowY: "auto", padding: 18, display: "flex", flexDirection: "column", gap: 14 }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
            <label style={labelStyle}>Địa chỉ API (Base URL)</label>
            <input value={llm.baseUrl} onChange={(e) => onChange("baseUrl", e.target.value)} placeholder="https://api.openai.com/v1" className={inputCls} />
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
            <label style={labelStyle}>API Key</label>
            <input
              type="password"
              value={llm.apiKey}
              onChange={(e) => onChange("apiKey", e.target.value)}
              placeholder="sk-••••••••••••••••"
              className={inputCls}
            />
          </div>
          <div style={{ display: "flex", gap: 12 }}>
            <div style={{ flex: 2, display: "flex", flexDirection: "column", gap: 5 }}>
              <label style={labelStyle}>Tên mô hình (Model)</label>
              <input value={llm.model} onChange={(e) => onChange("model", e.target.value)} placeholder="gpt-4o-mini" className={inputCls} />
            </div>
            <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 5 }}>
              <label style={labelStyle}>Nhiệt độ</label>
              <input value={llm.temperature} onChange={(e) => onChange("temperature", e.target.value)} placeholder="0.7" className={inputCls} />
            </div>
          </div>

          <div style={{ borderTop: `1px solid ${COLOR.border}`, paddingTop: 14, display: "flex", flexDirection: "column", gap: 10 }}>
            <button
              onClick={onTest}
              className="inline-flex items-center justify-center gap-2 h-[42px] border border-brand bg-primary-container rounded-[10px] font-sans text-[14px] font-semibold text-brand-dark cursor-pointer hover:bg-brand hover:text-white"
            >
              {testing ? (
                <>
                  <span
                    className="animate-spin"
                    style={{ width: 15, height: 15, border: `2px solid ${COLOR.accentSoftBorder}`, borderTopColor: COLOR.accent, borderRadius: "50%" }}
                  />{" "}
                  Đang kiểm tra…
                </>
              ) : (
                <>
                  <IcZap size={16} /> Kiểm tra kết nối
                </>
              )}
            </button>

            {testing && (
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  fontSize: "12.5px",
                  color: COLOR.textSecondary,
                  background: COLOR.surfaceAlt,
                  border: `1px solid ${COLOR.border}`,
                  borderRadius: 9,
                  padding: "10px 12px",
                }}
              >
                <span
                  className="animate-spin"
                  style={{ width: 13, height: 13, border: `2px solid ${COLOR.border}`, borderTopColor: COLOR.textMuted, borderRadius: "50%", flexShrink: 0 }}
                />{" "}
                Đang gửi một tin nhắn thử tới mô hình…
              </div>
            )}

            {testOk && (
              <div style={{ background: COLOR.successBg, border: `1px solid ${COLOR.successBorder}`, borderRadius: 10, padding: 12 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 7, color: COLOR.success, fontWeight: 700, fontSize: "13px" }}>
                  <IcCheck size={15} strokeWidth={2.5} style={{ flexShrink: 0 }} /> {result?.msg}
                </div>
                {result?.sample && (
                  <div
                    style={{
                      marginTop: 8,
                      fontSize: "12.5px",
                      color: COLOR.textSecondary,
                      background: COLOR.surface,
                      border: `1px solid ${COLOR.successBorder}`,
                      borderRadius: 8,
                      padding: "9px 11px",
                      lineHeight: 1.5,
                    }}
                  >
                    <span style={{ color: COLOR.textMuted, fontSize: "11px", display: "block", marginBottom: 3 }}>Mô hình trả lời:</span>“{result.sample}”
                  </div>
                )}
              </div>
            )}

            {testErr && (
              <div
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
                <IcAlert size={15} strokeWidth={2.5} style={{ flexShrink: 0, marginTop: 1 }} /> {result?.msg}
              </div>
            )}
          </div>
        </div>

        {/* footer */}
        <div style={{ flexShrink: 0, padding: "14px 18px", borderTop: `1px solid ${COLOR.border}`, display: "flex", gap: 10, justifyContent: "flex-end" }}>
          <button
            onClick={onClose}
            className="h-10 px-4 border border-slate-200 bg-white rounded-[10px] font-sans text-[14px] font-semibold text-slate-600 cursor-pointer hover:bg-slate-100"
          >
            Đóng
          </button>
          <button
            onClick={onSave}
            className="h-10 px-[18px] border-none bg-brand rounded-[10px] font-sans text-[14px] font-semibold text-white cursor-pointer shadow-[0_2px_6px_rgba(36,84,224,.3)] hover:bg-brand-dark"
          >
            Lưu cấu hình
          </button>
        </div>
      </div>
    </div>
  );
}
