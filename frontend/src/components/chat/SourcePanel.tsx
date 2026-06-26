import { useEffect, useRef } from "react";
import type { AppState, BackendSource } from "../../types";
import type { Actions } from "../../store/useAppStore";
import Markdown from "../common/Markdown";
import { IcExternal, IcFile, IcFolder, IcShield } from "../common/icons";

function relForScore(score: number) {
  if (score >= 0.5) return { t: "Cao", c: "#15803D", bg: "#DCFCE7" };
  if (score >= 0.2) return { t: "Trung bình", c: "#B45309", bg: "#FEF3C7" };
  return { t: "Thấp", c: "#64748B", bg: "#EEF2F0" };
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
        className="w-[6px] flex-shrink-0 cursor-col-resize bg-line flex items-center justify-center hover:bg-green-200"
      >
        <div style={{ width: 3, height: 34, borderRadius: 2, background: "#CBD5E1" }} />
      </div>

      <aside style={{ width: state.sourceW, flexShrink: 0, display: "flex", flexDirection: "column", background: "#F1F4F2" }}>
        {/* header + chips */}
        <div style={{ flexShrink: 0, padding: "12px 16px", background: "#fff", borderBottom: "1px solid #E6EAE8", display: "flex", flexDirection: "column", gap: 10 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <IcFile size={15} style={{ color: "#16A34A" }} />
            <span style={{ fontWeight: 700, fontSize: "13.5px", color: "#334155" }}>Nguồn của câu trả lời</span>
            <span
              title="Mỗi câu trả lời đều dựa trên tài liệu thật. Bấm số [1], [2]… trong câu trả lời để nhảy tới đúng đoạn được tô sáng ở đây."
              style={{ display: "inline-flex", alignItems: "center", justifyContent: "center", width: 17, height: 17, borderRadius: 9999, background: "#F1F5F9", color: "#64748B", fontSize: "10.5px", fontWeight: 700, cursor: "help" }}
            >
              ?
            </span>
            <div style={{ flex: 1 }} />
            <span style={{ fontSize: "11.5px", fontWeight: 700, background: "#DCFCE7", color: "#15803D", padding: "3px 10px", borderRadius: 9999 }}>{srcs.length} nguồn</span>
          </div>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {srcs.map((s) => {
              const active = String(s.index) === state.activeCite;
              const dot = active ? "#fff" : relForScore(s.rerank_score).c;
              return (
                <button
                  key={s.index}
                  onClick={() => actions.openCite(String(s.index))}
                  title="Xem nguồn này"
                  style={{ display: "inline-flex", alignItems: "center", gap: 7, padding: "6px 11px", borderRadius: 9999, fontSize: "12px", fontWeight: 600, cursor: "pointer", fontFamily: "inherit", whiteSpace: "nowrap", border: `1px solid ${active ? "#16A34A" : "#E2E8F0"}`, background: active ? "#16A34A" : "#fff", color: active ? "#fff" : "#475569" }}
                >
                  <span style={{ fontWeight: 700 }}>[{s.index}]</span> {s.file_stem} <span style={{ width: 7, height: 7, borderRadius: 9999, background: dot }} />
                </button>
              );
            })}
          </div>
        </div>

        {/* meta */}
        <div style={{ flexShrink: 0, padding: "11px 16px", background: "#fff", borderBottom: "1px solid #E6EAE8", display: "flex", flexDirection: "column", gap: 8 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
            <div style={{ flexShrink: 0, width: 26, height: 26, borderRadius: 7, background: "#FEE2E2", display: "flex", alignItems: "center", justifyContent: "center" }}>
              <IcFile size={13} style={{ color: "#DC2626" }} />
            </div>
            <span style={{ flex: 1, minWidth: 0, fontWeight: 700, fontSize: "13px", color: "#0F172A", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{src.file_stem}</span>
            <span title="Mức độ liên quan của đoạn trích này (điểm rerank)" style={{ display: "inline-flex", alignItems: "center", gap: 4, flexShrink: 0, background: lv.bg, color: lv.c, padding: "4px 9px", borderRadius: 9999, fontSize: "11px", fontWeight: 700, whiteSpace: "nowrap", cursor: "help" }}>
              <IcShield size={11} strokeWidth={2.2} />
              {lv.t} · {pct}%
            </span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 5, fontSize: "11px", color: "#64748B" }}>
            <IcFolder size={12} style={{ color: "#94A3B8", flexShrink: 0 }} />
            <span style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{src.section_path}</span>
          </div>
        </div>

        {/* document page: đoạn trả lời (child) tô sáng + ngữ cảnh (parent) */}
        <div ref={docRef} style={{ flex: 1, overflowY: "auto", padding: 18, position: "relative" }}>
          <div style={{ maxWidth: 600, margin: "0 auto", background: "#fff", border: "1px solid #E6EAE8", borderRadius: 6, boxShadow: "0 6px 22px -10px rgba(15,23,42,.16)", padding: "26px 30px 24px" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", paddingBottom: 11, marginBottom: 5, borderBottom: "1px dashed #E2E8F0", fontFamily: "'Be Vietnam Pro',sans-serif", fontSize: "10.5px", letterSpacing: ".08em", color: "#94A3B8", textTransform: "uppercase" }}>
              <span>{src.file_stem}</span>
              <span>{src.kind}</span>
            </div>

            {/* đoạn trả lời (child_text) — tô sáng */}
            <div ref={hlRef} style={{ position: "relative", background: "#FEF6DD", borderLeft: "4px solid #F59E0B", borderRadius: "0 8px 8px 0", padding: "14px 16px 13px", margin: "13px 0", animation: "hlGlow 2.6s ease-in-out infinite" }}>
              <span style={{ position: "absolute", top: -9, right: 12, background: "#F59E0B", color: "#fff", fontFamily: "'Be Vietnam Pro',sans-serif", fontSize: "9.5px", fontWeight: 700, letterSpacing: ".03em", padding: "2px 8px", borderRadius: 9999 }}>Đoạn trả lời</span>
              <Markdown className="md-doc">{src.child_text}</Markdown>
            </div>

            {/* ngữ cảnh đầy đủ (parent_text) */}
            <div style={{ marginTop: 14, paddingTop: 12, borderTop: "1px solid #F1F5F9" }}>
              <div style={{ fontFamily: "'Be Vietnam Pro',sans-serif", fontSize: "10.5px", letterSpacing: ".06em", color: "#94A3B8", textTransform: "uppercase", marginBottom: 6 }}>Ngữ cảnh đầy đủ</div>
              <Markdown className="md-doc">{src.parent_text}</Markdown>
            </div>
          </div>
        </div>

        {/* footer */}
        <div style={{ flexShrink: 0, padding: "10px 16px", background: "#fff", borderTop: "1px solid #E6EAE8", display: "flex", gap: 10, alignItems: "center" }}>
          <button
            onClick={actions.openSourceDoc}
            className="inline-flex items-center gap-[7px] h-9 px-[13px] border border-slate-200 bg-white rounded-[9px] font-sans text-[12.5px] font-semibold text-slate-600 cursor-pointer hover:border-brand hover:text-brand-dark hover:bg-green-50"
          >
            <IcExternal size={14} /> Mở tài liệu gốc
          </button>
          <div style={{ flex: 1 }} />
          <span style={{ fontSize: "11.5px", color: "#94A3B8" }}>{src.kind}</span>
        </div>
      </aside>
    </>
  );
}
