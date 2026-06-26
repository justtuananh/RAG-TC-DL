import type { CSSProperties } from "react";
import type { DocBlock } from "../../types";
import { IcInfo } from "./icons";

// "Trang tài liệu" mô phỏng (serif Lora) — dùng chung cho Cột nguồn & Trình xem tài liệu.

const paper: CSSProperties = {
  maxWidth: 600,
  margin: "0 auto",
  background: "#fff",
  border: "1px solid #E6EAE8",
  borderRadius: 6,
  boxShadow: "0 6px 22px -10px rgba(15,23,42,.16)",
  fontFamily: "'Lora',Georgia,serif",
  color: "#1E293B",
  lineHeight: 1.65,
  fontSize: "13.5px",
};
const headerRow: CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  paddingBottom: 11,
  marginBottom: 5,
  borderBottom: "1px dashed #E2E8F0",
  fontFamily: "'Be Vietnam Pro',sans-serif",
  fontSize: "10.5px",
  letterSpacing: ".08em",
  color: "#94A3B8",
  textTransform: "uppercase",
};
const hStyle: CSSProperties = { fontFamily: "'Be Vietnam Pro',sans-serif", fontWeight: 700, fontSize: "14px", letterSpacing: ".03em", color: "#0F172A", margin: "18px 0 7px" };
const subStyle: CSSProperties = { fontFamily: "'Be Vietnam Pro',sans-serif", fontWeight: 700, fontSize: "13px", color: "#15803D", margin: "14px 0 5px" };
const noteStyle: CSSProperties = { display: "flex", gap: 8, alignItems: "flex-start", background: "#F1F5F9", borderRadius: 9, padding: "11px 13px", margin: "13px 0", fontFamily: "'Be Vietnam Pro',sans-serif", fontSize: "12.5px", color: "#475569", lineHeight: 1.55 };
const formulaPlain: CSSProperties = { background: "#F8FAFC", border: "1px solid #E2E8F0", borderRadius: 8, padding: "11px 15px", margin: "9px 0", textAlign: "center", fontFamily: "'Be Vietnam Pro',sans-serif", fontSize: "16px", color: "#0F172A" };
const tableStyle: CSSProperties = { width: "100%", borderCollapse: "collapse", margin: "13px 0", fontFamily: "'Be Vietnam Pro',sans-serif", fontSize: "12.5px" };
const thStyle: CSSProperties = { textAlign: "left", padding: "8px 11px", background: "#F1F5F9", border: "1px solid #E2E8F0", fontWeight: 700, color: "#334155" };
const footStyle: CSSProperties = { background: "#6E8B78", color: "#fff", textAlign: "center", letterSpacing: ".18em", fontFamily: "'Be Vietnam Pro',sans-serif", fontSize: "10.5px", fontWeight: 700, padding: 8, borderRadius: 4, marginTop: 24 };

export interface DocPageProps {
  code: string;
  topRight: string;
  footLabel: string;
  blocks: DocBlock[];
  withHighlight?: boolean;
  /** gắn vào đoạn được tô sáng để cuộn tới */
  setHlEl?: (el: HTMLElement | null) => void;
  paperPadding?: string;
}

export default function DocPage({ code, topRight, footLabel, blocks, withHighlight = false, setHlEl, paperPadding = "28px 34px 26px" }: DocPageProps) {
  return (
    <div style={{ ...paper, padding: paperPadding }}>
      <div style={headerRow}>
        <span>{code}</span>
        <span>{topRight}</span>
      </div>

      {blocks.map((b, i) => {
        if (b.h) return <div key={i} style={hStyle}>{b.h}</div>;
        if (b.sub) return <div key={i} style={subStyle}>{b.sub}</div>;
        if (b.note)
          return (
            <div key={i} style={noteStyle}>
              <IcInfo size={14} style={{ color: "#94A3B8", flexShrink: 0, marginTop: 1 }} />
              {b.note}
            </div>
          );
        if (b.formula && !b.p) return <div key={i} style={formulaPlain}>{b.formula}</div>;
        if (b.table) {
          const t = b.table;
          return (
            <table key={i} style={tableStyle}>
              <thead>
                <tr>
                  {t.head.map((h, hi) => (
                    <th key={hi} style={thStyle}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {t.rows.map((row, ri) => {
                  const hl = withHighlight && t.highlightRow === ri;
                  return (
                    <tr
                      key={ri}
                      ref={hl && setHlEl ? (el) => setHlEl(el) : undefined}
                      style={hl ? { background: "#FEF6DD", animation: "hlGlow 2.6s ease-in-out infinite" } : undefined}
                    >
                      {row.map((c, ci) => (
                        <td
                          key={ci}
                          style={
                            hl
                              ? { padding: "8px 11px", border: "1px solid #FCD34D", fontWeight: 700, color: "#92400E" }
                              : { padding: "8px 11px", border: "1px solid #E2E8F0", color: "#475569" }
                          }
                        >
                          {c}
                        </td>
                      ))}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          );
        }
        // paragraph
        if (withHighlight && b.highlight) {
          return (
            <div
              key={i}
              ref={setHlEl ? (el) => setHlEl(el) : undefined}
              style={{ position: "relative", background: "#FEF6DD", borderLeft: "4px solid #F59E0B", borderRadius: "0 8px 8px 0", padding: "14px 16px 13px", margin: "13px 0", animation: "hlGlow 2.6s ease-in-out infinite" }}
            >
              <span style={{ position: "absolute", top: -9, right: 12, background: "#F59E0B", color: "#fff", fontFamily: "'Be Vietnam Pro',sans-serif", fontSize: "9.5px", fontWeight: 700, letterSpacing: ".03em", padding: "2px 8px", borderRadius: 9999 }}>
                Đoạn trả lời
              </span>
              <p style={{ margin: 0 }}>{b.p}</p>
              {b.formula && (
                <div style={{ background: "#fff", border: "1px solid #FCD34D", borderRadius: 8, padding: "11px 15px", margin: "11px 0 2px", textAlign: "center", fontFamily: "'Be Vietnam Pro',sans-serif", fontSize: "16px", letterSpacing: ".02em", color: "#0F172A" }}>
                  {b.formula}
                </div>
              )}
            </div>
          );
        }
        return (
          <div key={i}>
            <p style={{ margin: "11px 0" }}>{b.p}</p>
            {b.formula && <div style={formulaPlain}>{b.formula}</div>}
          </div>
        );
      })}

      <div style={footStyle}>{footLabel}</div>
    </div>
  );
}
