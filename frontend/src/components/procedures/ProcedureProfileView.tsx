import type { ProcedureProfile } from "../../types";
import { COLOR } from "../../theme";
import { IcFile, IcInfo, IcMessage, IcShield } from "../common/icons";
import { knowledgeTotal, procedureCode } from "./profileFormat";
import { ConditionsSection, FormulasSection, ParametersSection, StandardsSection, TermsSection, type OpenProvenance } from "./ProfileSections";
import RecordsSummary from "./RecordsSummary";
import StepsMatrix from "./StepsMatrix";

// Một trang Hồ sơ QTKĐ: phần đầu (số hiệu, tên, loại thiết bị, tác vụ), mục lục nhảy tới
// từng khối, rồi các khối tri thức đã duyệt và tóm tắt biên bản trong sổ cái.

export interface ProfileActions {
  onOpenProvenance: OpenProvenance;
  onOpenDocument: () => void;
  onAsk: () => void;
  onOpenDevice: (deviceId: number) => void;
  onOpenRecords: () => void;
  onOpenReview: () => void;
}

interface Props extends ProfileActions {
  profile: ProcedureProfile;
  /** Số dòng tri thức của tài liệu này đang chờ duyệt; null khi người xem không có quyền duyệt. */
  pendingCount: number | null;
}

const actionButton: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: 7,
  height: 36,
  padding: "0 14px",
  borderRadius: 10,
  fontSize: "13px",
  fontWeight: 600,
  fontFamily: "inherit",
  cursor: "pointer",
  whiteSpace: "nowrap",
};

function Chip({ children }: { children: React.ReactNode }) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        height: 24,
        padding: "0 10px",
        borderRadius: 9999,
        background: COLOR.surfaceAlt,
        border: `1px solid ${COLOR.border}`,
        fontSize: "12px",
        color: COLOR.textSecondary,
      }}
    >
      {children}
    </span>
  );
}

function Header({ profile, onOpenDocument, onAsk }: { profile: ProcedureProfile; onOpenDocument: () => void; onAsk: () => void }) {
  const { procedure, document } = profile;
  return (
    <header style={{ display: "flex", gap: 20, alignItems: "flex-start", flexWrap: "wrap" }}>
      <div style={{ flex: "1 1 420px", minWidth: 0, display: "flex", flexDirection: "column", gap: 8 }}>
        <span style={{ fontSize: "13px", fontWeight: 700, letterSpacing: ".02em", color: COLOR.accent }}>{procedureCode(procedure)}</span>
        <h1 style={{ margin: 0, fontSize: "21px", lineHeight: 1.35, fontWeight: 700, color: COLOR.textPrimary, textWrap: "balance" }}>
          {procedure.title ?? "Quy trình kiểm định"}
        </h1>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {procedure.device_type_name && <Chip>{procedure.device_type_name}</Chip>}
          {procedure.quantity_name && <Chip>Đại lượng: {procedure.quantity_name}</Chip>}
          {procedure.edition && <Chip>Bản {procedure.edition}</Chip>}
        </div>
      </div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <button
          type="button"
          onClick={onAsk}
          style={{ ...actionButton, border: "none", background: COLOR.accent, color: COLOR.textOnDark }}
          className="hover:brightness-110"
        >
          <IcMessage size={15} /> Hỏi trợ lý
        </button>
        <button
          type="button"
          onClick={onOpenDocument}
          disabled={!document}
          title={document ? (document.display_name ?? undefined) : "QTKĐ chưa gắn tài liệu gốc"}
          className="profile-chip"
          style={{
            ...actionButton,
            border: `1px solid ${COLOR.border}`,
            background: COLOR.surface,
            color: COLOR.textSecondary,
            opacity: document ? 1 : 0.55,
            cursor: document ? "pointer" : "not-allowed",
          }}
        >
          <IcFile size={15} /> Tài liệu gốc
        </button>
      </div>
    </header>
  );
}

/** Đánh dấu vùng cuộn của hồ sơ; mục lục chỉ cuộn vùng này. */
export const PROFILE_SCROLL_ATTR = "data-profile-scroll";
const SECTION_GAP_PX = 16;

/**
 * Cuộn tới một khối trong vùng cuộn của hồ sơ. Không dùng `scrollIntoView`: hàm đó cuộn
 * mọi tổ tiên (kể cả khung ứng dụng `overflow: hidden`), đẩy thanh trên ra khỏi màn hình.
 */
function scrollToSection(id: string) {
  const target = document.getElementById(id);
  const scroller = target?.closest<HTMLElement>(`[${PROFILE_SCROLL_ATTR}]`);
  if (!target || !scroller) return;
  const offset = target.getBoundingClientRect().top - scroller.getBoundingClientRect().top;
  scroller.scrollTo({ top: scroller.scrollTop + offset - SECTION_GAP_PX, behavior: "smooth" });
}

function SectionNav({ profile }: { profile: ProcedureProfile }) {
  const parameterCount = profile.parameters.reduce((sum, group) => sum + group.items.length, 0);
  const items = [
    { id: "thong-so", label: "Thông số", count: parameterCount },
    { id: "dieu-kien", label: "Điều kiện", count: profile.conditions.length },
    { id: "phep-kiem-dinh", label: "Phép kiểm định", count: profile.steps.length },
    { id: "phuong-tien", label: "Phương tiện", count: profile.standards.length },
    { id: "cong-thuc", label: "Công thức", count: profile.formulas.length },
    { id: "thuat-ngu", label: "Thuật ngữ", count: profile.terms.length },
    { id: "bien-ban", label: "Biên bản", count: profile.records.total },
  ];
  return (
    <nav aria-label="Mục của hồ sơ" style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
      {items.map((item) => (
        <a
          key={item.id}
          href={`#${item.id}`}
          className="profile-chip"
          onClick={(e) => {
            e.preventDefault();
            scrollToSection(item.id);
          }}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            height: 30,
            padding: "0 12px",
            borderRadius: 9999,
            border: `1px solid ${COLOR.border}`,
            background: COLOR.surface,
            color: item.count > 0 ? COLOR.textSecondary : COLOR.textMuted,
            fontSize: "12.5px",
            fontWeight: 600,
            textDecoration: "none",
          }}
        >
          {item.label}
          <span className="tabular-nums" style={{ fontSize: "11.5px", fontWeight: 700, color: item.count > 0 ? COLOR.accent : COLOR.textMuted }}>
            {item.count}
          </span>
        </a>
      ))}
    </nav>
  );
}

function NoKnowledgeNotice({ pendingCount, onOpenReview }: { pendingCount: number | null; onOpenReview: () => void }) {
  const canReview = pendingCount !== null;
  const hasPending = canReview && pendingCount > 0;
  return (
    <div
      role="status"
      style={{
        display: "flex",
        gap: 12,
        alignItems: "flex-start",
        padding: "14px 16px",
        borderRadius: 12,
        background: COLOR.warningBg,
        border: `1px solid ${COLOR.warningBorder}`,
      }}
    >
      <IcInfo size={18} style={{ color: COLOR.warning, flexShrink: 0, marginTop: 1 }} />
      <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 4 }}>
        <strong style={{ fontSize: "13.5px", color: COLOR.textPrimary }}>Chưa có tri thức nào của QTKĐ này được duyệt</strong>
        <span style={{ fontSize: "13px", color: COLOR.textSecondary, lineHeight: 1.55 }}>
          Hệ thống tự trích thông số, các phép kiểm định, phương tiện và thuật ngữ khi nạp tài liệu, nhưng chỉ hiển thị ở đây sau khi người duyệt đối chiếu từng
          dòng với nguyên văn.
          {hasPending && ` Tài liệu này đang có ${pendingCount} dòng chờ duyệt.`}
          {!canReview && " Hãy liên hệ người duyệt để công bố tri thức của quy trình này."}
        </span>
      </div>
      {hasPending && (
        <button
          type="button"
          onClick={onOpenReview}
          style={{ ...actionButton, height: 32, border: "none", background: COLOR.accent, color: COLOR.textOnDark }}
          className="hover:brightness-110"
        >
          <IcShield size={14} /> Mở hàng đợi duyệt
        </button>
      )}
    </div>
  );
}

export default function ProcedureProfileView({
  profile,
  pendingCount,
  onOpenProvenance,
  onOpenDocument,
  onAsk,
  onOpenDevice,
  onOpenRecords,
  onOpenReview,
}: Props) {
  const hasKnowledge = knowledgeTotal(profile) > 0;
  return (
    <article
      aria-label={procedureCode(profile.procedure)}
      style={{ maxWidth: 1080, margin: "0 auto", padding: "24px 28px 40px", display: "flex", flexDirection: "column", gap: 16 }}
    >
      <Header profile={profile} onOpenDocument={onOpenDocument} onAsk={onAsk} />
      {hasKnowledge ? <SectionNav profile={profile} /> : <NoKnowledgeNotice pendingCount={pendingCount} onOpenReview={onOpenReview} />}
      {hasKnowledge && (
        <>
          <ParametersSection parameters={profile.parameters} onOpen={onOpenProvenance} />
          <ConditionsSection conditions={profile.conditions} onOpen={onOpenProvenance} />
          <StepsMatrix profile={profile} onOpen={onOpenProvenance} />
          <StandardsSection standards={profile.standards} onOpen={onOpenProvenance} />
          <FormulasSection formulas={profile.formulas} onOpen={onOpenProvenance} />
          <TermsSection terms={profile.terms} onOpen={onOpenProvenance} />
        </>
      )}
      <RecordsSummary profile={profile} onOpenDevice={onOpenDevice} onOpenAll={onOpenRecords} />
    </article>
  );
}
