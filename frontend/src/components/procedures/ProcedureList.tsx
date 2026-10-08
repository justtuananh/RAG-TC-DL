import { memo } from "react";
import type { ProcedureSummary } from "../../types";
import { COLOR } from "../../theme";
import { IcSearch } from "../common/icons";
import { procedureCode } from "./profileFormat";

// Cột trái của trang Hồ sơ QTKĐ: tìm không dấu theo số hiệu / tên / loại thiết bị,
// mỗi dòng cho biết QTKĐ đã có bao nhiêu tri thức được duyệt.

interface Props {
  items: ProcedureSummary[];
  total: number;
  query: string;
  loading: boolean;
  loadingMore: boolean;
  error: string | null;
  selectedId: number | null;
  onQuery: (value: string) => void;
  onSelect: (id: number) => void;
  onLoadMore: () => void;
}

function knowledgeCount(item: ProcedureSummary): number {
  return item.counts.facts + item.counts.standards + item.counts.terms;
}

// memo: đổi trạng thái hồ sơ bên phải không vẽ lại cả danh sách (onSelect ổn định).
const Row = memo(function Row({ item, active, onSelect }: { item: ProcedureSummary; active: boolean; onSelect: (id: number) => void }) {
  const knowledge = knowledgeCount(item);
  return (
    <li>
      <button
        type="button"
        onClick={() => onSelect(item.id)}
        aria-current={active ? "true" : undefined}
        className="procedure-row"
        style={{
          width: "100%",
          textAlign: "left",
          display: "flex",
          flexDirection: "column",
          gap: 3,
          padding: "10px 12px",
          border: "none",
          borderRadius: 10,
          background: active ? COLOR.accentSoft : "transparent",
          cursor: "pointer",
          fontFamily: "inherit",
        }}
      >
        <span style={{ fontWeight: 700, fontSize: "13.5px", color: active ? COLOR.accentDark : COLOR.textPrimary }}>{procedureCode(item)}</span>
        {item.title && (
          <span
            style={{
              fontSize: "12px",
              lineHeight: 1.45,
              color: COLOR.textSecondary,
              display: "-webkit-box",
              WebkitLineClamp: 2,
              WebkitBoxOrient: "vertical",
              overflow: "hidden",
            }}
          >
            {item.title}
          </span>
        )}
        <span style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "11.5px", color: COLOR.textMuted }}>
          <span
            aria-hidden
            style={{ width: 6, height: 6, borderRadius: 9999, flexShrink: 0, background: knowledge > 0 ? COLOR.success : COLOR.borderStrong }}
          />
          <span className="tabular-nums">{knowledge > 0 ? `${knowledge} tri thức đã duyệt` : "Chưa có tri thức đã duyệt"}</span>
          {item.counts.records > 0 && <span className="tabular-nums">· {item.counts.records} biên bản</span>}
        </span>
      </button>
    </li>
  );
});

export default function ProcedureList({ items, total, query, loading, loadingMore, error, selectedId, onQuery, onSelect, onLoadMore }: Props) {
  const hasMore = items.length < total;
  return (
    <nav
      aria-label="Danh sách QTKĐ"
      style={{
        width: 300,
        flexShrink: 0,
        display: "flex",
        flexDirection: "column",
        minHeight: 0,
        borderRight: `1px solid ${COLOR.border}`,
        background: COLOR.surface,
      }}
    >
      <div style={{ padding: "14px 14px 10px", display: "flex", flexDirection: "column", gap: 8 }}>
        <label
          className="flex items-center gap-2 rounded-[10px] px-[11px] h-[36px] focus-within:border-brand"
          style={{ border: `1px solid ${COLOR.border}`, background: COLOR.surfaceAlt }}
        >
          <IcSearch size={15} style={{ color: COLOR.textMuted, flexShrink: 0 }} />
          <input
            value={query}
            onChange={(e) => onQuery(e.target.value)}
            placeholder="Số hiệu, tên hoặc loại thiết bị"
            aria-label="Tìm QTKĐ"
            className="flex-1 min-w-0 border-none outline-none bg-transparent font-sans text-[13px]"
            style={{ color: COLOR.textPrimary }}
          />
        </label>
        <span className="tabular-nums" style={{ fontSize: "11.5px", color: COLOR.textMuted }}>
          {loading ? "Đang tải…" : hasMore ? `Hiển thị ${items.length} / ${total} quy trình` : `${total} quy trình`}
        </span>
      </div>
      <div style={{ flex: 1, minHeight: 0, overflowY: "auto", padding: "0 8px 12px" }}>
        {error ? (
          <p role="alert" style={{ margin: "8px 6px", fontSize: "12.5px", color: COLOR.danger }}>
            {error}
          </p>
        ) : !loading && items.length === 0 ? (
          <p style={{ margin: "8px 6px", fontSize: "12.5px", color: COLOR.textMuted, lineHeight: 1.55 }}>
            {query.trim() ? "Không có QTKĐ khớp từ khoá." : "Chưa có QTKĐ nào trong kho tài liệu."}
          </p>
        ) : (
          <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 2 }}>
            {items.map((item) => (
              <Row key={item.id} item={item} active={item.id === selectedId} onSelect={onSelect} />
            ))}
          </ul>
        )}
        {hasMore && !error && (
          <button
            type="button"
            className="profile-chip"
            onClick={onLoadMore}
            disabled={loadingMore}
            style={{
              width: "100%",
              height: 34,
              marginTop: 8,
              border: `1px solid ${COLOR.border}`,
              borderRadius: 10,
              background: COLOR.surface,
              color: COLOR.textSecondary,
              fontSize: "12.5px",
              fontWeight: 600,
              fontFamily: "inherit",
              cursor: loadingMore ? "progress" : "pointer",
            }}
          >
            {loadingMore ? "Đang tải…" : `Tải thêm (còn ${total - items.length})`}
          </button>
        )}
      </div>
    </nav>
  );
}
