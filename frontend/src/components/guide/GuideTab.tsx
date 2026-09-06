import type { ReactNode } from "react";
import type { AppState } from "../../types";
import type { Actions } from "../../store/useAppStore";
import { FAQS } from "../../store/seed";
import { IcArrowDown, IcArrowRight, IcChevronDown, IcChevronUp, IcMessage, IcShield, IcSparkles, IcUpload } from "../common/icons";
import { COLOR, SHADOW } from "../../theme";

const sectionTitle = { fontSize: "16.5px", fontWeight: 700, color: COLOR.textPrimary, margin: "28px 0 13px" } as const;
const card = { background: COLOR.surface, border: `1px solid ${COLOR.border}`, borderRadius: 13, padding: 18, boxShadow: SHADOW.sm } as const;

function Step({ n, icon, title, desc }: { n: number; icon: ReactNode; title: string; desc: string }) {
  return (
    <div style={card}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 11 }}>
        <span
          style={{
            width: 28,
            height: 28,
            borderRadius: 9999,
            background: COLOR.accent,
            color: COLOR.textOnDark,
            fontWeight: 700,
            fontSize: "14px",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          {n}
        </span>
        {icon}
      </div>
      <div style={{ fontWeight: 700, fontSize: "14.5px", color: COLOR.textPrimary, marginBottom: 5 }}>{title}</div>
      <div style={{ fontSize: "13px", color: COLOR.textSecondary, lineHeight: 1.6 }}>{desc}</div>
    </div>
  );
}

function UploadStep({ n, children }: { n: number; children: ReactNode }) {
  return (
    <div style={{ display: "flex", gap: 11, alignItems: "flex-start" }}>
      <span
        style={{
          flexShrink: 0,
          width: 25,
          height: 25,
          borderRadius: 9999,
          background: COLOR.accentSoft,
          color: COLOR.accentDark,
          fontWeight: 700,
          fontSize: "12.5px",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        {n}
      </span>
      <div style={{ fontSize: "13.5px", color: COLOR.textSecondary, lineHeight: 1.6, paddingTop: 2 }}>{children}</div>
    </div>
  );
}

export default function GuideTab({ state, actions }: { state: AppState; actions: Actions }) {
  return (
    <main style={{ flex: 1, minHeight: 0, overflowY: "auto", background: COLOR.bg }}>
      <div style={{ maxWidth: 840, margin: "0 auto", padding: "28px 24px 56px" }}>
        {/* hero */}
        <div
          style={{
            background: `linear-gradient(135deg, ${COLOR.accent}, ${COLOR.accentDark})`,
            borderRadius: 16,
            padding: "26px 28px",
            color: COLOR.textOnDark,
            boxShadow: "0 10px 26px -12px rgba(36,84,224,.5)",
          }}
        >
          <div style={{ fontSize: "22px", fontWeight: 700, marginBottom: 6 }}>Hướng dẫn sử dụng</div>
          <div style={{ fontSize: "14.5px", lineHeight: 1.6, opacity: 0.95, maxWidth: 560 }}>
            Trợ lý giúp bạn tra cứu nhanh các quy trình kiểm định — không cần nhớ tài liệu nằm ở đâu, chỉ cần hỏi bằng tiếng Việt.
          </div>
        </div>

        {/* 3 steps */}
        <div style={sectionTitle}>Bắt đầu trong 3 bước</div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 13 }}>
          <Step
            n={1}
            icon={<IcMessage size={19} style={{ color: COLOR.accent }} />}
            title="Đặt câu hỏi"
            desc="Gõ câu hỏi như đang hỏi đồng nghiệp, rồi nhấn Gửi. Không cần dùng từ khóa kỹ thuật."
          />
          <Step
            n={2}
            icon={<IcSparkles size={19} style={{ color: COLOR.accent }} />}
            title="Đọc câu trả lời"
            desc="Trợ lý tổng hợp từ tài liệu và trả lời ngắn gọn, kèm số trích dẫn [1], [2]…"
          />
          <Step
            n={3}
            icon={<IcShield size={19} style={{ color: COLOR.accent }} />}
            title="Kiểm chứng nguồn"
            desc="Bấm số [1] để mở tài liệu gốc và xem đúng đoạn được tô sáng. Luôn biết câu trả lời từ đâu."
          />
        </div>

        {/* sample questions */}
        <div style={sectionTitle}>Câu hỏi mẫu — bấm để hỏi ngay</div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 9 }}>
          {state.examples.map((q, i) => (
            <button
              key={i}
              onClick={() => actions.askSample(q)}
              className="inline-flex items-center gap-2 px-[15px] py-[10px] bg-white border border-slate-200 rounded-[11px] font-sans text-[13.5px] text-slate-700 cursor-pointer text-left hover:border-brand hover:bg-primary-container hover:text-brand-dark"
            >
              <IcArrowRight size={15} style={{ flexShrink: 0, color: COLOR.accent }} />
              {q}
            </button>
          ))}
        </div>

        {/* how to read sources */}
        <div style={sectionTitle}>Cách đọc &amp; kiểm chứng nguồn</div>
        <div style={{ display: "flex", gap: 18, ...card, borderRadius: 15, padding: 20, flexWrap: "wrap" }}>
          <div style={{ flex: 1, minWidth: 250, fontSize: "13.5px", color: COLOR.textSecondary, lineHeight: 1.7 }}>
            <p style={{ margin: "0 0 10px" }}>Mỗi con số màu xanh trong câu trả lời tương ứng với một đoạn trong tài liệu gốc.</p>
            <p style={{ margin: 0 }}>
              Khi bạn <strong style={{ color: COLOR.accentDark }}>bấm vào số [1]</strong>, hệ thống sẽ mở đúng trang tài liệu và{" "}
              <strong style={{ color: COLOR.warning }}>tô sáng đoạn được dùng để trả lời</strong>, kèm độ tin cậy — để bạn yên tâm kiểm chứng.
            </p>
          </div>
          <div style={{ flex: 1, minWidth: 250, background: COLOR.surfaceAlt, border: `1px solid ${COLOR.border}`, borderRadius: 12, padding: 15 }}>
            <div style={{ fontSize: "13px", color: COLOR.textPrimary, lineHeight: 1.6, marginBottom: 6 }}>
              …phải đạt <strong>≥ 3 phút</strong> ở 20&nbsp;°C{" "}
              <span
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  minWidth: 21,
                  height: 21,
                  padding: "0 5px",
                  background: COLOR.accentSoft,
                  border: `1px solid ${COLOR.accentSoftBorder}`,
                  color: COLOR.accentDark,
                  borderRadius: 6,
                  fontSize: "11.5px",
                  fontWeight: 700,
                  verticalAlign: -3,
                }}
              >
                [1]
              </span>
            </div>
            <div style={{ display: "flex", justifyContent: "center", margin: "7px 0" }}>
              <IcArrowDown size={19} style={{ color: COLOR.textMuted }} />
            </div>
            <div
              style={{
                position: "relative",
                background: COLOR.highlight,
                borderLeft: `4px solid ${COLOR.highlightStrong}`,
                borderRadius: "0 8px 8px 0",
                padding: "11px 13px",
                fontFamily: "'Lora',serif",
                fontSize: "13px",
                color: COLOR.textPrimary,
                lineHeight: 1.55,
              }}
            >
              <span
                style={{
                  position: "absolute",
                  top: -9,
                  right: 11,
                  background: COLOR.highlightStrong,
                  color: COLOR.textOnDark,
                  fontFamily: "'Be Vietnam Pro',sans-serif",
                  fontSize: "9px",
                  fontWeight: 700,
                  padding: "2px 8px",
                  borderRadius: 9999,
                }}
              >
                Đoạn trả lời
              </span>
              Thời gian quay tự do tối thiểu của pít tông áp kế chuẩn phải đạt ≥ 3 phút trong điều kiện chuẩn (20&nbsp;°C).
            </div>
          </div>
        </div>

        {/* upload guide */}
        <div style={sectionTitle}>Tải tài liệu mới lên</div>
        <div style={{ ...card, borderRadius: 15, padding: 20 }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 11, marginBottom: 15 }}>
            <UploadStep n={1}>
              Mở tab <strong style={{ color: COLOR.accentDark }}>Tài liệu</strong>, kéo thả tệp PDF/Word vào khung tải lên hoặc bấm để chọn tệp.
            </UploadStep>
            <UploadStep n={2}>
              Bấm nút <strong style={{ color: COLOR.accentDark }}>Xử lý</strong> trên tài liệu vừa tải; chờ trạng thái chuyển sang{" "}
              <strong style={{ color: COLOR.accentDark }}>Đã sẵn sàng</strong> (chỉ vài giây).
            </UploadStep>
            <UploadStep n={3}>Quay lại tab Trò chuyện và hỏi về nội dung tài liệu vừa tải lên.</UploadStep>
          </div>
          <button
            onClick={() => actions.go("docs")}
            className="inline-flex items-center gap-2 h-10 px-[17px] border-none rounded-[10px] bg-brand text-white font-sans text-[13.5px] font-semibold cursor-pointer shadow-[0_2px_6px_rgba(36,84,224,.3)] hover:bg-brand-dark"
          >
            <IcUpload size={16} /> Mở mục Tài liệu
          </button>
        </div>

        {/* FAQ */}
        <div style={sectionTitle}>Câu hỏi thường gặp</div>
        <div style={{ display: "flex", flexDirection: "column", gap: 9 }}>
          {FAQS.map((f, i) => {
            const open = state.faqOpen === i;
            return (
              <div key={i} style={{ background: COLOR.surface, border: `1px solid ${COLOR.border}`, borderRadius: 12, overflow: "hidden" }}>
                <button
                  onClick={() => actions.toggleFaq(i)}
                  className="w-full flex items-center justify-between gap-3 px-4 py-[14px] bg-transparent border-none cursor-pointer font-sans text-left"
                >
                  <span style={{ fontWeight: 600, fontSize: "14px", color: COLOR.textPrimary }}>{f.q}</span>
                  {open ? (
                    <IcChevronUp size={17} strokeWidth={2.5} style={{ flexShrink: 0, color: COLOR.accent }} />
                  ) : (
                    <IcChevronDown size={17} strokeWidth={2.5} style={{ flexShrink: 0, color: COLOR.textMuted }} />
                  )}
                </button>
                {open && <div style={{ padding: "0 16px 15px", fontSize: "13.5px", color: COLOR.textSecondary, lineHeight: 1.7 }}>{f.a}</div>}
              </div>
            );
          })}
        </div>
      </div>
    </main>
  );
}
