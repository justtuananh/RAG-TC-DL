import type { ReactNode } from "react";
import type { DataCellRef, ProcedureFact, ProcedureProfile, ProcedureStandard, ProcedureTerm } from "../../types";
import { COLOR } from "../../theme";
import { IcLink } from "../common/icons";
import Markdown from "../common/Markdown";
import { PROV_CELL_CLASS, tableStyle, thStyle } from "../data/tableStyles";
import { cellLines, extractionRef, factRef, formulaMarkdown } from "./profileFormat";

// Các khối nội dung của trang Hồ sơ QTKĐ. Mọi giá trị hiển thị NGUYÊN VĂN (P2) và bấm
// được để mở đoạn nguồn (P1): dữ kiện mở theo `id` (kind "fact"), phương tiện và thuật
// ngữ mở theo `extraction_id`.

export type OpenProvenance = (ref: DataCellRef) => void;

export function SectionCard({ id, title, count, children, aside }: { id: string; title: string; count?: number; children: ReactNode; aside?: ReactNode }) {
  return (
    <section
      id={id}
      aria-labelledby={`${id}-title`}
      style={{ scrollMarginTop: 64, background: COLOR.surface, border: `1px solid ${COLOR.border}`, borderRadius: 14, padding: "18px 20px" }}
    >
      <header style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14, flexWrap: "wrap" }}>
        <h2 id={`${id}-title`} style={{ margin: 0, fontSize: "15px", fontWeight: 700, color: COLOR.textPrimary }}>
          {title}
        </h2>
        {count !== undefined && (
          <span className="tabular-nums" style={{ fontSize: "12px", fontWeight: 600, color: COLOR.textMuted }}>
            {count}
          </span>
        )}
        <div style={{ flex: 1 }} />
        {aside}
      </header>
      {children}
    </section>
  );
}

export function EmptyLine({ children }: { children: ReactNode }) {
  return <p style={{ margin: 0, fontSize: "13px", color: COLOR.textMuted, lineHeight: 1.55 }}>{children}</p>;
}

export function SourceButton({ cellRef, label, onOpen }: { cellRef: DataCellRef; label: string; onOpen: OpenProvenance }) {
  return (
    <button
      type="button"
      className="profile-chip"
      onClick={() => onOpen(cellRef)}
      aria-label={`Xem nguyên văn: ${label}`}
      title="Xem nguyên văn trong tài liệu"
      style={{
        flexShrink: 0,
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        height: 26,
        padding: "0 9px",
        border: `1px solid ${COLOR.border}`,
        borderRadius: 9999,
        background: COLOR.surface,
        color: COLOR.textSecondary,
        fontSize: "11.5px",
        fontWeight: 600,
        fontFamily: "inherit",
        cursor: "pointer",
      }}
    >
      <IcLink size={11} /> Nguồn
    </button>
  );
}

/** Giá trị nguyên văn bấm được để mở nguồn; cùng kiểu ô số của tab Dữ liệu. */
function FactValue({ fact, onOpen }: { fact: ProcedureFact; onOpen: OpenProvenance }) {
  const ref = factRef(fact);
  return (
    <button
      type="button"
      className={PROV_CELL_CLASS}
      data-prov-kind={ref.kind}
      data-prov-id={ref.id}
      onClick={() => onOpen(ref)}
      aria-label={`Xem nguồn ${fact.label ?? ""}: ${fact.value_text ?? ""}`}
      style={{ fontSize: "15px", fontWeight: 600, color: COLOR.textPrimary }}
    >
      {fact.value_text ?? "(không ghi giá trị)"}
      <IcLink size={11} />
    </button>
  );
}

function Condition({ text }: { text: string | null }) {
  return text ? <span style={{ fontSize: "12px", color: COLOR.textSecondary, lineHeight: 1.5 }}>{text}</span> : null;
}

export function ParametersSection({ parameters, onOpen }: { parameters: ProcedureProfile["parameters"]; onOpen: OpenProvenance }) {
  const count = parameters.reduce((sum, group) => sum + group.items.length, 0);
  return (
    <SectionCard id="thong-so" title="Thông số kỹ thuật" count={count}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 10 }}>
        {parameters.map((group) => (
          <div key={group.kind} style={{ border: `1px solid ${COLOR.border}`, borderRadius: 11, padding: "12px 14px", background: COLOR.surfaceAlt }}>
            <div style={{ fontSize: "12px", fontWeight: 600, color: COLOR.textMuted, marginBottom: 6 }}>{group.label}</div>
            {group.items.length === 0 ? (
              <span style={{ fontSize: "13px", color: COLOR.textMuted }}>Chưa có dữ kiện đã duyệt</span>
            ) : (
              <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 6 }}>
                {group.items.map((fact) => (
                  <li key={fact.id} style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                    {group.items.length > 1 && fact.label && fact.label !== group.label && (
                      <span style={{ fontSize: "12px", color: COLOR.textSecondary }}>{fact.label}</span>
                    )}
                    <FactValue fact={fact} onOpen={onOpen} />
                    <Condition text={fact.condition_text} />
                  </li>
                ))}
              </ul>
            )}
          </div>
        ))}
      </div>
    </SectionCard>
  );
}

export function ConditionsSection({ conditions, onOpen }: { conditions: ProcedureFact[]; onOpen: OpenProvenance }) {
  return (
    <SectionCard id="dieu-kien" title="Điều kiện kiểm định" count={conditions.length}>
      {conditions.length === 0 ? (
        <EmptyLine>Chưa có điều kiện môi trường đã duyệt.</EmptyLine>
      ) : (
        <dl style={{ margin: 0, display: "grid", gridTemplateColumns: "minmax(160px, max-content) 1fr", columnGap: 18, rowGap: 10 }}>
          {conditions.map((fact) => (
            <div key={fact.id} style={{ display: "contents" }}>
              <dt style={{ fontSize: "13px", color: COLOR.textSecondary, paddingTop: 2 }}>{fact.label ?? "Điều kiện"}</dt>
              <dd style={{ margin: 0, display: "flex", flexDirection: "column", gap: 2 }}>
                <FactValue fact={fact} onOpen={onOpen} />
                <Condition text={fact.condition_text} />
              </dd>
            </div>
          ))}
        </dl>
      )}
    </SectionCard>
  );
}

const cellStyle = {
  padding: "10px 12px",
  borderBottom: `1px solid ${COLOR.border}`,
  fontSize: "13px",
  color: COLOR.textPrimary,
  verticalAlign: "top",
} as const;

/** Ô bảng nguồn nhiều dòng: mỗi dòng gốc một dòng hiển thị. */
function CellText({ value }: { value: string | null }) {
  return (
    <>
      {cellLines(value).map((line, index) => (
        <div key={index}>{line}</div>
      ))}
    </>
  );
}

export function StandardsSection({ standards, onOpen }: { standards: ProcedureStandard[]; onOpen: OpenProvenance }) {
  return (
    <SectionCard id="phuong-tien" title="Phương tiện kiểm định" count={standards.length}>
      {standards.length === 0 ? (
        <EmptyLine>Chưa có dòng Bảng 2 (phương tiện kiểm định) đã duyệt.</EmptyLine>
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table style={tableStyle}>
            <thead>
              <tr>
                <th style={{ ...thStyle, width: 44 }}>TT</th>
                <th style={thStyle}>Tên phương tiện</th>
                <th style={thStyle}>Phạm vi đo</th>
                <th style={thStyle}>Đặc trưng kỹ thuật đo lường</th>
                <th style={{ ...thStyle, width: 80 }}>
                  <span className="sr-only">Nguồn</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {standards.map((row, index) => (
                <tr key={row.id}>
                  <td style={{ ...cellStyle, color: COLOR.textMuted }} className="tabular-nums">
                    {row.ord ?? index + 1}
                  </td>
                  <td style={{ ...cellStyle, fontWeight: 600 }}>
                    <CellText value={row.name_vi} />
                  </td>
                  <td style={cellStyle}>
                    <CellText value={row.range_text} />
                  </td>
                  <td style={cellStyle}>
                    <CellText value={row.accuracy_text} />
                    {row.note && (
                      <div style={{ fontSize: "12px", color: COLOR.textSecondary, marginTop: 3 }}>
                        <CellText value={row.note} />
                      </div>
                    )}
                  </td>
                  <td style={{ ...cellStyle, textAlign: "right" }}>
                    <SourceButton cellRef={extractionRef(row.extraction_id, "standard")} label={row.name_vi} onOpen={onOpen} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </SectionCard>
  );
}

export function FormulasSection({ formulas, onOpen }: { formulas: ProcedureFact[]; onOpen: OpenProvenance }) {
  return (
    <SectionCard id="cong-thuc" title="Công thức" count={formulas.length}>
      {formulas.length === 0 ? (
        <EmptyLine>Chưa có công thức đã duyệt. Công thức ở mục Tiến hành kiểm định do mô hình ngôn ngữ trích và cần người duyệt.</EmptyLine>
      ) : (
        <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 10 }}>
          {formulas.map((fact) => (
            <li key={fact.id} style={{ border: `1px solid ${COLOR.border}`, borderRadius: 11, padding: "10px 14px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <span style={{ flex: 1, fontSize: "13px", fontWeight: 600, color: COLOR.textSecondary }}>{fact.label ?? "Công thức"}</span>
                <SourceButton cellRef={factRef(fact)} label={fact.label ?? "công thức"} onOpen={onOpen} />
              </div>
              <Markdown className="md-answer">{formulaMarkdown(fact.value_text)}</Markdown>
            </li>
          ))}
        </ul>
      )}
    </SectionCard>
  );
}

export function TermsSection({ terms, onOpen }: { terms: ProcedureTerm[]; onOpen: OpenProvenance }) {
  return (
    <SectionCard id="thuat-ngu" title="Thuật ngữ và định nghĩa" count={terms.length}>
      {terms.length === 0 ? (
        <EmptyLine>Chưa có thuật ngữ đã duyệt. Một số QTKĐ không có mục Thuật ngữ.</EmptyLine>
      ) : (
        <dl style={{ margin: 0, display: "flex", flexDirection: "column" }}>
          {terms.map((term, index) => (
            <div key={term.id} style={{ display: "flex", gap: 14, padding: "12px 0", borderTop: index === 0 ? "none" : `1px solid ${COLOR.border}` }}>
              <dt style={{ width: 220, flexShrink: 0, display: "flex", flexDirection: "column", gap: 2 }}>
                <span style={{ fontSize: "13.5px", fontWeight: 700, color: COLOR.textPrimary }}>{term.term_vi}</span>
                {term.term_en && <span style={{ fontSize: "12px", fontStyle: "italic", color: COLOR.textMuted }}>{term.term_en}</span>}
              </dt>
              <dd style={{ margin: 0, flex: 1, fontSize: "13px", lineHeight: 1.6, color: COLOR.textSecondary }}>{term.definition ?? ""}</dd>
              <div style={{ flexShrink: 0 }}>
                <SourceButton cellRef={extractionRef(term.extraction_id, "term")} label={term.term_vi} onOpen={onOpen} />
              </div>
            </div>
          ))}
        </dl>
      )}
    </SectionCard>
  );
}
