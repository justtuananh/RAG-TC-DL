import { useEffect, useRef, useState } from "react";
import type { DataCellRef, ProvenanceSource } from "../../types";
import { COLOR } from "../../theme";
import { IcAlert, IcExternal, IcFile, IcLink, IcSearch, IcX } from "../common/icons";
import QuoteHighlight from "../knowledge/QuoteHighlight";
import { fetchProvenance } from "../../services/dataApi";

// Ngăn kéo xuất xứ: mở đúng tài liệu/mục/chunk/trích dẫn sinh ra một ô số (P1).
// Văn bản nguồn render bằng text node qua QuoteHighlight — không nhúng HTML.

const FIELD_LABEL: Record<string, string> = {
  nominal: "Giá trị danh nghĩa",
  measured: "Giá trị đo",
  error: "Sai số",
  limit: "Giới hạn",
  calibrated_at: "Ngày kiểm định",
  expires_at: "Hạn hiệu lực",
  env_temp_c: "Nhiệt độ môi trường",
  env_humidity_pct: "Độ ẩm môi trường",
  range_min: "Phạm vi đo – nhỏ nhất",
  range_max: "Phạm vi đo – lớn nhất",
  accuracy_text: "Cấp chính xác",
  measurement_count: "Số điểm đo",
  working_range: "Phạm vi đo",
  accuracy_class: "Cấp chính xác",
};

function fieldLabel(field: string | null | undefined): string {
  if (!field) return "—";
  return FIELD_LABEL[field] ?? field;
}

export default function ProvenanceDrawer({
  cellRef,
  onClose,
}: {
  cellRef: DataCellRef | null;
  onClose: () => void;
}) {
  const [source, setSource] = useState<ProvenanceSource | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const closeRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    if (!cellRef) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    setSource(null);
    (async () => {
      try {
        const result = await fetchProvenance(cellRef);
        if (!cancelled) setSource(result);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Không đọc được xuất xứ.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [cellRef]);

  useEffect(() => {
    if (!cellRef) return;
    closeRef.current?.focus();
    const handler = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [cellRef, onClose]);

  if (!cellRef) return null;

  const documentId = source?.file_stem ?? source?.document_id ?? null;

  return (
    <div
      style={{ position: "fixed", inset: 0, zIndex: 70, display: "flex", justifyContent: "flex-end", background: "rgba(16,24,40,.35)" }}
      onClick={onClose}
    >
      <aside
        role="dialog"
        aria-modal="true"
        aria-label="Xuất xứ ô số"
        style={{
          width: 520,
          maxWidth: "100%",
          background: COLOR.surface,
          borderLeft: `1px solid ${COLOR.border}`,
          boxShadow: "0 10px 28px rgba(16,24,40,.18)",
          display: "flex",
          flexDirection: "column",
          minHeight: 0,
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <header style={{ display: "flex", alignItems: "center", gap: 9, padding: "14px 18px", borderBottom: `1px solid ${COLOR.border}` }}>
          <IcLink size={17} style={{ color: COLOR.accent }} />
          <span style={{ fontWeight: 700, fontSize: "14.5px", color: COLOR.textPrimary }}>Xuất xứ ô số</span>
          <span style={{ fontSize: "11.5px", color: COLOR.textMuted }}>{fieldLabel(cellRef.field)}</span>
          <div style={{ flex: 1 }} />
          {documentId && (
            <a
              href={`/api/documents/${encodeURIComponent(documentId)}/file`}
              target="_blank"
              rel="noreferrer"
              title="Mở tài liệu gốc"
              style={linkButton}
            >
              <IcExternal size={13} /> Tài liệu gốc
            </a>
          )}
          <button ref={closeRef} onClick={onClose} aria-label="Đóng xuất xứ" style={iconButton}>
            <IcX size={16} />
          </button>
        </header>

        <div style={{ flex: 1, minHeight: 0, overflowY: "auto", padding: "14px 18px", display: "flex", flexDirection: "column", gap: 12 }}>
          {loading && <div style={{ fontSize: "13px", color: COLOR.textSecondary }}>Đang dựng xuất xứ…</div>}
          {error && (
            <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: "13px", color: COLOR.danger }}>
              <IcAlert size={15} /> {error}
            </div>
          )}

          {source && (
            <>
              <dl style={{ display: "grid", gridTemplateColumns: "130px 1fr", gap: "6px 12px", margin: 0, fontSize: "12.5px" }}>
                <dt style={dtStyle}>Giá trị nguyên văn</dt>
                <dd style={ddStyle}>
                  <code style={{ background: COLOR.surfaceAlt, padding: "1px 6px", borderRadius: 5 }}>
                    {source.value_text ?? source.quote ?? "—"}
                  </code>
                </dd>
                <dt style={dtStyle}>Tài liệu</dt>
                <dd style={ddStyle}>{source.display_name ?? source.file_stem ?? source.document_id ?? "—"}</dd>
                <dt style={dtStyle}>Mục</dt>
                <dd style={ddStyle}>{source.section_path ?? "—"}</dd>
                <dt style={dtStyle}>Chunk</dt>
                <dd style={ddStyle}>{source.chunk_id ?? "—"}</dd>
                <dt style={dtStyle}>Luật trích xuất</dt>
                <dd style={ddStyle}>
                  {source.extractor ?? "—"}
                  {source.extractor_version ? ` (${source.extractor_version})` : ""}
                </dd>
                <dt style={dtStyle}>Độ tin cậy</dt>
                <dd style={ddStyle}>{source.confidence == null ? "—" : `${Math.round(source.confidence * 100)}%`}</dd>
              </dl>

              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <IcSearch size={14} style={{ color: COLOR.accent }} />
                <span style={{ fontWeight: 700, fontSize: "13px", color: COLOR.textPrimary }}>Đoạn nguyên văn</span>
              </div>
              <div
                style={{
                  background: COLOR.accentSoft,
                  border: `2px solid ${COLOR.accent}`,
                  borderRadius: 8,
                  padding: "14px 16px",
                  fontFamily: "'Lora', Georgia, serif",
                  fontSize: "13px",
                  lineHeight: 1.65,
                  color: COLOR.textPrimary,
                  whiteSpace: "pre-wrap",
                }}
              >
                {source.section_text ? (
                  <QuoteHighlight
                    text={source.section_text}
                    quote={source.quote}
                    start={source.quote_start}
                    end={source.quote_end}
                  />
                ) : (
                  source.quote ?? "—"
                )}
              </div>

              {source.point_quote && source.point_quote !== source.quote && (
                <div style={{ fontSize: "12px", color: COLOR.textSecondary }}>
                  Dòng số liệu nguồn: <span style={{ color: COLOR.textPrimary }}>{source.point_quote}</span>
                </div>
              )}
              <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "11.5px", color: COLOR.textMuted }}>
                <IcFile size={12} /> Mọi ô số đều truy ngược được về nguyên văn (nguyên tắc P1).
              </div>
            </>
          )}
        </div>
      </aside>
    </div>
  );
}

const dtStyle: React.CSSProperties = { fontWeight: 700, color: COLOR.textSecondary };
const ddStyle: React.CSSProperties = { margin: 0, color: COLOR.textPrimary, wordBreak: "break-word" };
const linkButton: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: 5,
  height: 30,
  padding: "0 10px",
  borderRadius: 8,
  border: `1px solid ${COLOR.border}`,
  color: COLOR.accentDark,
  fontSize: "12px",
  fontWeight: 600,
  textDecoration: "none",
  background: COLOR.surface,
};
const iconButton: React.CSSProperties = {
  width: 30,
  height: 30,
  borderRadius: 8,
  border: `1px solid ${COLOR.border}`,
  background: COLOR.surface,
  color: COLOR.textSecondary,
  cursor: "pointer",
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
};
