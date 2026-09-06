import { useEffect, useRef } from "react";
import type { AppState, BackendSource } from "../../types";
import type { Actions } from "../../store/useAppStore";
import Markdown from "../common/Markdown";
import { COLOR } from "../../theme";
import { IcExternal, IcFile, IcFolder, IcShield } from "../common/icons";

function relForScore(score: number) {
  if (score >= 0.5) return { t: "Cao", c: COLOR.success, bg: COLOR.successBg };
  if (score >= 0.2) return { t: "Trung bình", c: COLOR.warning, bg: COLOR.warningBg };
  return { t: "Thấp", c: COLOR.neutral, bg: COLOR.neutralBg };
}
const pctOf = (score: number) => Math.max(0, Math.min(100, Math.round(score * 100)));

export default function SourcePanel({ state, actions }: { state: AppState; actions: Actions }) {
  const docRef = useRef<HTMLDivElement>(null);
  const hlRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const c = docRef.current;
    const el = hlRef.current;
    if (c && el) c.scrollTo({ top: Math.max(0, el.offsetTop - 60), behavior: "smooth" });
  }, [state.activeCite, state.pulse]);

  const srcs: BackendSource[] = state.liveSources;
  const src = srcs.find((x) => String(x.index) === state.activeCite) || srcs[0];
  if (!src) return null;
  const lv = relForScore(src.rerank_score);
  const pct = pctOf(src.rerank_score);

  return (
    <>
      <div
        onMouseDown={actions.startResize}
        title="Kéo để thay đổi độ rộng"
        className="layout-resize-handle w-[6px] flex-shrink-0 cursor-col-resize bg-line flex items-center justify-center hover:bg-[#E9EFFF]"
      >
        <div style={{ width: 3, height: 34, borderRadius: 2, background: COLOR.borderStrong }} />
      </div>

      <aside
        className="layout-source-panel"
        style={{ width: state.sourceW, flexShrink: 0, display: "flex", flexDirection: "column", background: COLOR.surfaceAlt }}
      >
        {/* header + chips */}
        <div
          style={{
            flexShrink: 0,
            padding: "12px 16px",
            background: COLOR.surface,
            borderBottom: `1px solid ${COLOR.border}`,
            display: "flex",
            flexDirection: "column",
            gap: 10,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <IcFile size={15} style={{ color: COLOR.accent }} />
            <span style={{ fontWeight: 700, fontSize: "13.5px", color: COLOR.textSecondary }}>Nguồn của câu trả lời</span>
            <span
              title="Mỗi câu trả lời đều dựa trên tài liệu thật. Bấm số [1], [2]… trong câu trả lời để nhảy tới đúng đoạn được tô sáng ở đây."
              style={{
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                width: 17,
                height: 17,
                borderRadius: 9999,
                background: COLOR.accentSoft,
                color: COLOR.textMuted,
                fontSize: "10.5px",
                fontWeight: 700,
                cursor: "help",
              }}
            >
              ?
            </span>
            <div style={{ flex: 1 }} />
            <span style={{ fontSize: "11.5px", fontWeight: 700, background: COLOR.accentSoft, color: COLOR.accent, padding: "3px 10px", borderRadius: 9999 }}>
              {srcs.length} nguồn
            </span>
          </div>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {srcs.map((s) => {
              const active = String(s.index) === state.activeCite;
              const dot = active ? COLOR.textOnDark : relForScore(s.rerank_score).c;
              return (
                <button
                  key={s.index}
                  onClick={() => actions.openCite(String(s.index))}
                  title="Xem nguồn này"
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 7,
                    padding: "6px 11px",
                    borderRadius: 9999,
                    fontSize: "12px",
                    fontWeight: 600,
                    cursor: "pointer",
                    fontFamily: "inherit",
                    whiteSpace: "nowrap",
                    border: `1px solid ${active ? COLOR.accent : COLOR.border}`,
                    background: active ? COLOR.accent : COLOR.surface,
                    color: active ? COLOR.textOnDark : COLOR.textSecondary,
                  }}
                >
                  <span style={{ fontWeight: 700 }}>[{s.index}]</span> {s.file_stem}{" "}
                  <span style={{ width: 7, height: 7, borderRadius: 9999, background: dot }} />
                </button>
              );
            })}
          </div>
        </div>

        {/* meta */}
        <div
          style={{
            flexShrink: 0,
            padding: "11px 16px",
            background: COLOR.surface,
            borderBottom: `1px solid ${COLOR.border}`,
            display: "flex",
            flexDirection: "column",
            gap: 8,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
            <div
              style={{
                flexShrink: 0,
                width: 26,
                height: 26,
                borderRadius: 7,
                background: COLOR.accentSoft,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <IcFile size={13} style={{ color: COLOR.accent }} />
            </div>
            <span
              style={{
                flex: 1,
                minWidth: 0,
                fontWeight: 700,
                fontSize: "13px",
                color: COLOR.textPrimary,
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
              }}
            >
              {src.file_stem}
            </span>
            <span
              title="Mức độ liên quan của đoạn trích này (điểm rerank)"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 4,
                flexShrink: 0,
                background: lv.bg,
                color: lv.c,
                padding: "4px 9px",
                borderRadius: 9999,
                fontSize: "11px",
                fontWeight: 700,
                whiteSpace: "nowrap",
                cursor: "help",
              }}
            >
              <IcShield size={11} strokeWidth={2.2} />
              {lv.t} · {pct}%
            </span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 5, fontSize: "11px", color: COLOR.textMuted }}>
            <IcFolder size={12} style={{ color: COLOR.textMuted, flexShrink: 0 }} />
            <span style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{src.section_path}</span>
          </div>
        </div>

        {/* document page: đoạn trả lời (child) tô sáng + ngữ cảnh (parent) */}
        <div ref={docRef} style={{ flex: 1, overflowY: "auto", padding: 18, position: "relative" }}>
          <div
            style={{
              maxWidth: 600,
              margin: "0 auto",
              background: COLOR.surface,
              border: `1px solid ${COLOR.border}`,
              borderRadius: 6,
              boxShadow: "0 6px 22px -10px rgba(16,24,40,.16)",
              padding: "26px 30px 24px",
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                paddingBottom: 11,
                marginBottom: 5,
                borderBottom: `1px dashed ${COLOR.border}`,
                fontFamily: "'Be Vietnam Pro',sans-serif",
                fontSize: "11px",
                fontWeight: 500,
                color: COLOR.textMuted,
              }}
            >
              <span>{src.file_stem}</span>
              <span>{src.kind}</span>
            </div>

            {/* đoạn trả lời (child_text) — tô sáng */}
            <div
              ref={hlRef}
              className="animate-hlGlow"
              style={{
                position: "relative",
                background: COLOR.accentSoft,
                border: `2px solid ${COLOR.accent}`,
                borderRadius: 8,
                padding: "14px 16px 13px",
                margin: "13px 0",
              }}
            >
              <span
                style={{
                  position: "absolute",
                  top: -9,
                  right: 12,
                  background: COLOR.accent,
                  color: COLOR.textOnDark,
                  fontFamily: "'Be Vietnam Pro',sans-serif",
                  fontSize: "9.5px",
                  fontWeight: 700,
                  letterSpacing: ".03em",
                  padding: "2px 8px",
                  borderRadius: 9999,
                }}
              >
                Đoạn trả lời
              </span>
              <Markdown className="md-doc">{src.child_text}</Markdown>
            </div>

            {/* ngữ cảnh đầy đủ (parent_text) */}
            <div style={{ marginTop: 14, paddingTop: 12, borderTop: `1px solid ${COLOR.border}` }}>
              <div style={{ fontFamily: "'Be Vietnam Pro',sans-serif", fontSize: "11px", fontWeight: 600, color: COLOR.textMuted, marginBottom: 6 }}>
                Ngữ cảnh đầy đủ
              </div>
              <Markdown className="md-doc">{src.parent_text}</Markdown>
            </div>
          </div>
        </div>

        {/* footer */}
        <div
          style={{
            flexShrink: 0,
            padding: "10px 16px",
            background: COLOR.surface,
            borderTop: `1px solid ${COLOR.border}`,
            display: "flex",
            gap: 10,
            alignItems: "center",
          }}
        >
          <button
            onClick={actions.openSourceDoc}
            className="inline-flex items-center gap-[7px] h-9 px-[13px] border border-line bg-white rounded-[9px] font-sans text-[12.5px] font-semibold text-[#475467] cursor-pointer hover:border-brand hover:text-brand-dark hover:bg-[#E9EFFF]"
          >
            <IcExternal size={14} /> Mở tài liệu gốc
          </button>
          <div style={{ flex: 1 }} />
          <span style={{ fontSize: "11.5px", color: COLOR.textMuted }}>{src.kind}</span>
        </div>
      </aside>
    </>
  );
}
