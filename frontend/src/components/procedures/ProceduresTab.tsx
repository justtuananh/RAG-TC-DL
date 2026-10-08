import { useCallback, useEffect, useRef, useState } from "react";
import type { AppState, DataCellRef, DocItem, ProcedureProfile, ProcedureSummary } from "../../types";
import type { Actions } from "../../store/useAppStore";
import { fetchProcedureProfile, fetchProcedures } from "../../services/knowledgeApi";
import { fetchExtractionQueue } from "../../services/reviewApi";
import { COLOR } from "../../theme";
import { IcBook, IcLock } from "../common/icons";
import ProvenanceDrawer from "../data/ProvenanceDrawer";
import ProcedureList from "./ProcedureList";
import ProcedureProfileView, { type ReviewInfo } from "./ProcedureProfileView";
import { PROFILE_SCROLL_ATTR, procedureCode } from "./profileFormat";

// Tab "Tri thức QTKĐ": mỗi quy trình kiểm định là một hồ sơ có cấu trúc, ghép từ tri thức
// ĐÃ DUYỆT (P3). Mọi giá trị mở được nguyên văn (P1). Cần đăng nhập (mọi vai trò đọc).

// Trang danh sách; "Tải thêm" nối trang kế (kho có thể tới hàng nghìn QTKĐ).
const PAGE_SIZE = 50;
const SEARCH_DEBOUNCE_MS = 220;

function documentItem(state: AppState, document: NonNullable<ProcedureProfile["document"]>): DocItem {
  const known = state.documents.find((doc) => doc.id === document.id);
  if (known) return known;
  const name = document.display_name ?? document.file_stem ?? document.id;
  const ext = (name.split(".").pop() ?? "DOCX").toUpperCase() as DocItem["ext"];
  return { id: document.id, name, ext, size: "", pages: "—", date: "", status: "ready" };
}

export default function ProceduresTab({ state, actions }: { state: AppState; actions: Actions }) {
  const user = state.auth.user;
  const canReview = !!user && (user.role === "approver" || user.role === "admin");

  const [query, setQuery] = useState("");
  const [items, setItems] = useState<ProcedureSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [listLoading, setListLoading] = useState(false);
  const [listError, setListError] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [loadMoreError, setLoadMoreError] = useState<string | null>(null);

  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [profile, setProfile] = useState<ProcedureProfile | null>(null);
  const [profileLoading, setProfileLoading] = useState(false);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [pendingCount, setPendingCount] = useState<number | null>(null);
  const [pendingLoading, setPendingLoading] = useState(false);
  const [provenanceRef, setProvenanceRef] = useState<DataCellRef | null>(null);

  const listSeq = useRef(0);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  // Danh sách QTKĐ: tìm kiếm debounce nhẹ. Chỉ tự chọn QTKĐ đầu tiên khi chưa chọn gì:
  // gõ tìm kiếm không được đổi hồ sơ người dùng đang đọc.
  useEffect(() => {
    if (!user) return;
    const seq = ++listSeq.current;
    // Đang chờ debounce cũng tính là đang tải: "Tải thêm" bị khoá cho tới khi trang 1 của
    // từ khoá mới về, tránh nối trang của từ khoá mới vào danh sách cũ.
    setListLoading(true);
    setLoadMoreError(null);
    const timer = setTimeout(() => {
      setListError(null);
      fetchProcedures({ q: query, limit: PAGE_SIZE })
        .then((page) => {
          if (seq !== listSeq.current) return;
          setItems(page.items);
          setTotal(page.total);
          setSelectedId((prev) => prev ?? page.items[0]?.id ?? null);
        })
        .catch((e) => {
          if (seq === listSeq.current) setListError(e instanceof Error ? e.message : "Không tải được danh sách QTKĐ.");
        })
        .finally(() => {
          if (seq === listSeq.current) setListLoading(false);
        });
    }, SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [user, query]);

  const loadMore = useCallback(() => {
    const seq = listSeq.current;
    setLoadingMore(true);
    setLoadMoreError(null);
    fetchProcedures({ q: query, limit: PAGE_SIZE, offset: items.length })
      .then((page) => {
        if (seq !== listSeq.current) return; // từ khoá đã đổi: trang này thuộc kết quả cũ
        setItems((prev) => {
          const known = new Set(prev.map((item) => item.id));
          return [...prev, ...page.items.filter((item) => !known.has(item.id))];
        });
        setTotal(page.total);
      })
      .catch((e) => {
        // Lỗi trang kế chỉ báo tại nút: phần danh sách đã tải vẫn giữ nguyên.
        if (seq === listSeq.current) setLoadMoreError(e instanceof Error ? e.message : "Không tải thêm được.");
      })
      .finally(() => setLoadingMore(false));
  }, [query, items.length]);

  // Hồ sơ của QTKĐ đang chọn.
  useEffect(() => {
    if (selectedId == null) {
      setProfile(null);
      setProfileLoading(false);
      setProfileError(null);
      return;
    }
    let cancelled = false;
    setProfileLoading(true);
    setProfileError(null);
    fetchProcedureProfile(selectedId)
      .then((result) => {
        if (cancelled) return;
        setProfile(result);
        scrollRef.current?.scrollTo({ top: 0 });
      })
      .catch((e) => {
        if (!cancelled) setProfileError(e instanceof Error ? e.message : "Không tải được hồ sơ QTKĐ.");
      })
      .finally(() => {
        if (!cancelled) setProfileLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedId]);

  // Người duyệt thấy số dòng tri thức của tài liệu đang chờ duyệt (lối tắt sang hàng đợi).
  const documentId = profile?.document?.id ?? null;
  useEffect(() => {
    setPendingCount(null);
    setPendingLoading(false);
    if (!canReview || !documentId) return;
    let cancelled = false;
    setPendingLoading(true);
    fetchExtractionQueue({ document_id: documentId, limit: 1 })
      .then((page) => {
        if (!cancelled) setPendingCount(page.total);
      })
      .catch(() => {
        if (!cancelled) setPendingCount(null);
      })
      .finally(() => {
        if (!cancelled) setPendingLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [canReview, documentId]);

  const openDocument = useCallback(() => {
    if (profile?.document) actions.viewDoc(documentItem(state, profile.document));
  }, [actions, profile, state]);

  const ask = useCallback(() => {
    if (profile) actions.composeAbout(`Theo ${procedureCode(profile.procedure)}, `);
  }, [actions, profile]);

  const review: ReviewInfo = { canReview, pending: pendingCount, loading: pendingLoading };

  // Chưa biết phiên (đang gọi /api/auth/me): giữ trống để không nháy màn "Cần đăng nhập".
  if (!user && !state.auth.restoreDone) return <main aria-label="Tri thức QTKĐ" style={centered} />;
  if (!user) {
    return (
      <main aria-label="Tri thức QTKĐ" style={centered}>
        <div style={noticeCard}>
          <IcLock size={26} style={{ color: COLOR.borderStrong }} />
          <div style={{ fontWeight: 700, fontSize: "15px", color: COLOR.textPrimary }}>Cần đăng nhập để xem tri thức QTKĐ</div>
          <div style={{ fontSize: "13px", color: COLOR.textSecondary, lineHeight: 1.55 }}>
            Hồ sơ tri thức của từng quy trình chỉ hiển thị dữ kiện đã được người duyệt đối chiếu với nguyên văn.
          </div>
          <button type="button" onClick={() => actions.openLogin("Vui lòng đăng nhập để xem tri thức QTKĐ.")} style={primaryButton}>
            Đăng nhập
          </button>
        </div>
      </main>
    );
  }

  return (
    <main aria-label="Tri thức QTKĐ" style={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "column", background: COLOR.bg }}>
      <div style={headerStyle}>
        <span style={{ display: "inline-flex", alignItems: "center", gap: 7, fontWeight: 700, fontSize: "14.5px", color: COLOR.textPrimary }}>
          <IcBook size={16} style={{ color: COLOR.accent }} /> Tri thức QTKĐ
        </span>
        <span style={{ fontSize: "12.5px", color: COLOR.textMuted }}>Hồ sơ có cấu trúc của từng quy trình kiểm định, chỉ gồm dữ kiện đã duyệt</span>
      </div>
      <div style={{ flex: 1, minHeight: 0, display: "flex" }}>
        <ProcedureList
          items={items}
          total={total}
          query={query}
          loading={listLoading}
          loadingMore={loadingMore}
          loadMoreError={loadMoreError}
          onLoadMore={loadMore}
          error={listError}
          selectedId={selectedId}
          onQuery={setQuery}
          onSelect={setSelectedId}
        />
        <div ref={scrollRef} {...{ [PROFILE_SCROLL_ATTR]: "" }} style={{ flex: 1, minWidth: 0, overflowY: "auto" }} aria-busy={profileLoading}>
          {profileError ? (
            <p role="alert" style={{ margin: 28, fontSize: "13px", color: COLOR.danger }}>
              {profileError}
            </p>
          ) : profile ? (
            <div style={{ opacity: profileLoading ? 0.6 : 1, transition: "opacity .15s ease" }}>
              <ProcedureProfileView
                key={profile.procedure.id}
                profile={profile}
                review={review}
                onOpenProvenance={setProvenanceRef}
                onOpenDocument={openDocument}
                onAsk={ask}
                onOpenDevice={actions.openDevice}
                onOpenRecords={() => actions.openProcedureRecords(profile.procedure.id)}
                onOpenReview={() => actions.openReview(documentId)}
              />
            </div>
          ) : (
            <p style={{ margin: 28, fontSize: "13px", color: COLOR.textMuted }}>
              {profileLoading || listLoading ? "Đang tải…" : "Chọn một QTKĐ ở danh sách bên trái."}
            </p>
          )}
        </div>
      </div>
      <ProvenanceDrawer cellRef={provenanceRef} onClose={() => setProvenanceRef(null)} />
    </main>
  );
}

const headerStyle: React.CSSProperties = {
  flexShrink: 0,
  display: "flex",
  alignItems: "center",
  gap: 14,
  flexWrap: "wrap",
  minHeight: 54,
  padding: "8px 20px",
  background: COLOR.surface,
  borderBottom: `1px solid ${COLOR.border}`,
};
const centered: React.CSSProperties = { flex: 1, minHeight: 0, display: "flex", alignItems: "center", justifyContent: "center", background: COLOR.bg };
const noticeCard: React.CSSProperties = {
  maxWidth: 420,
  padding: "28px 26px",
  textAlign: "center",
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  gap: 8,
  background: COLOR.surface,
  border: `1px solid ${COLOR.border}`,
  borderRadius: 13,
};
const primaryButton: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: 7,
  height: 38,
  padding: "0 16px",
  marginTop: 4,
  borderRadius: 9,
  border: "none",
  background: COLOR.accent,
  color: COLOR.textOnDark,
  fontWeight: 700,
  fontSize: "13px",
  cursor: "pointer",
};
