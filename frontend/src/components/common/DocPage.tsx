import type { CSSProperties } from "react";
import type { DocBlock } from "../../types";
import { IcInfo } from "./icons";
import { COLOR } from "../../theme";

// "Trang tài liệu" mô phỏng (serif Lora) — dùng chung cho Cột nguồn & Trình xem tài liệu.

const paper: CSSProperties = {
  maxWidth: 900,
  margin: "0 auto",
  background: COLOR.surface,
  border: `1px solid ${COLOR.border}`,
  borderRadius: 6,
  boxShadow: "0 6px 22px -10px rgba(15,23,42,.16)",
  fontFamily: "'Lora',Georgia,serif",
  color: COLOR.textPrimary,
  lineHeight: 1.65,
  fontSize: "13.5px",
};
const headerRow: CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  paddingBottom: 11,
  marginBottom: 5,
  borderBottom: `1px dashed ${COLOR.border}`,
  fontFamily: "'Be Vietnam Pro',sans-serif",
  fontSize: "10.5px",
  letterSpacing: ".08em",
  color: COLOR.textMuted,
  textTransform: "uppercase",
};
const hStyle: CSSProperties = {
  fontFamily: "'Be Vietnam Pro',sans-serif",
  fontWeight: 700,
  fontSize: "14px",
  letterSpacing: ".03em",
  color: COLOR.textPrimary,
  margin: "18px 0 7px",
};
const subStyle: CSSProperties = { fontFamily: "'Be Vietnam Pro',sans-serif", fontWeight: 700, fontSize: "13px", color: COLOR.accentDark, margin: "14px 0 5px" };
const noteStyle: CSSProperties = {
  display: "flex",
  gap: 8,
  alignItems: "flex-start",
  background: COLOR.surfaceAlt,
  borderRadius: 9,
  padding: "11px 13px",
  margin: "13px 0",
  fontFamily: "'Be Vietnam Pro',sans-serif",
  fontSize: "12.5px",
  color: COLOR.textSecondary,
  lineHeight: 1.55,
};
const formulaPlain: CSSProperties = {
  background: COLOR.surfaceAlt,
  border: `1px solid ${COLOR.border}`,
  borderRadius: 8,
  padding: "11px 15px",
  margin: "9px 0",
  textAlign: "center",
  fontFamily: "'Be Vietnam Pro',sans-serif",
  fontSize: "16px",
  color: COLOR.textPrimary,
};
const tableStyle: CSSProperties = {
  width: "100%",
  borderCollapse: "collapse",
  margin: "13px 0",
  fontFamily: "'Be Vietnam Pro',sans-serif",
  fontSize: "12.5px",
};
const thStyle: CSSProperties = {
  textAlign: "left",
  padding: "8px 11px",
  background: COLOR.surfaceAlt,
  border: `1px solid ${COLOR.border}`,
  fontWeight: 700,
  color: COLOR.textSecondary,
};
const footStyle: CSSProperties = {
  background: COLOR.sidebarBg,
  color: COLOR.textOnDark,
  textAlign: "center",
  letterSpacing: ".18em",
  fontFamily: "'Be Vietnam Pro',sans-serif",
  fontSize: "10.5px",
  fontWeight: 700,
  padding: 8,
  borderRadius: 4,
  marginTop: 24,
};

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
        if (b.h)
          return (
            <div key={i} style={hStyle}>
              {b.h}
            </div>
          );
        if (b.sub)
          return (
            <div key={i} style={subStyle}>
              {b.sub}
            </div>
          );
        if (b.note)
          return (
            <div key={i} style={noteStyle}>
              <IcInfo size={14} style={{ color: COLOR.textMuted, flexShrink: 0, marginTop: 1 }} />
              {b.note}
            </div>
          );
        if (b.formula && !b.p)
          return (
            <div key={i} style={formulaPlain}>
              {b.formula}
            </div>
          );
        if (b.table) {
          const t = b.table;
          return (
            <table key={i} style={tableStyle}>
              <thead>
                <tr>
                  {t.head.map((h, hi) => (
                    <th key={hi} style={thStyle}>
                      {h}
                    </th>
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
                      style={hl ? { background: COLOR.highlight, animation: "hlGlow 2.6s ease-in-out infinite" } : undefined}
                    >
                      {row.map((c, ci) => (
                        <td
                          key={ci}
                          style={
                            hl
                              ? { padding: "8px 11px", border: `1px solid ${COLOR.highlightBorder}`, fontWeight: 700, color: COLOR.warning }
                              : { padding: "8px 11px", border: `1px solid ${COLOR.border}`, color: COLOR.textSecondary }
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
              style={{
                position: "relative",
                background: COLOR.highlight,
                borderLeft: `4px solid ${COLOR.highlightStrong}`,
                borderRadius: "0 8px 8px 0",
                padding: "14px 16px 13px",
                margin: "13px 0",
                animation: "hlGlow 2.6s ease-in-out infinite",
              }}
            >
              <span
                style={{
                  position: "absolute",
                  top: -9,
                  right: 12,
                  background: COLOR.highlightStrong,
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
              <p style={{ margin: 0 }}>{b.p}</p>
              {b.formula && (
                <div
                  style={{
                    background: COLOR.surface,
                    border: `1px solid ${COLOR.highlightBorder}`,
                    borderRadius: 8,
                    padding: "11px 15px",
                    margin: "11px 0 2px",
                    textAlign: "center",
                    fontFamily: "'Be Vietnam Pro',sans-serif",
                    fontSize: "16px",
                    letterSpacing: ".02em",
                    color: COLOR.textPrimary,
                  }}
                >
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
