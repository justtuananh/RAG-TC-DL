import { useCallback, useEffect, useState } from "react";
import type { UserRole } from "../../types";
import { COLOR, RADIUS, SHADOW } from "../../theme";
import Markdown from "../common/Markdown";
import { decideSummary, editSummary, generateSummary, getSummary, type DocSummary, type SummaryStatus } from "../../services/summaryApi";

const POLL_MS = 4000;
const field =
  "block min-w-0 w-full mt-1 border border-line rounded-lg px-3 py-2 text-[13px] font-sans font-normal text-on-surface bg-surface outline-none transition-colors placeholder:text-icon-muted focus:border-brand focus:ring-2 focus:ring-primary-container disabled:bg-surface-container-low disabled:text-icon-muted";
const buttonBase =
  "inline-flex items-center justify-center gap-2 min-h-9 border rounded-lg px-3 py-2 font-sans text-[12.5px] font-semibold transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand disabled:opacity-40 disabled:cursor-not-allowed";
const button = `${buttonBase} border-line text-secondary bg-surface hover:border-brand hover:text-brand hover:bg-primary-container`;
const primaryButton = `${buttonBase} border-brand bg-brand text-on-primary hover:bg-brand-dark hover:border-brand-dark`;
const dangerButton = `${buttonBase} bg-surface hover:opacity-80`;
const card = "min-w-0 border border-line bg-surface rounded-[14px] p-4 sm:p-5";
const notice = "border rounded-[10px] px-3 py-2.5 text-[12.5px] leading-relaxed";

const tone = {
  warning: { color: COLOR.warning, background: COLOR.warningBg, borderColor: COLOR.warningBorder },
  success: { color: COLOR.success, background: COLOR.successBg, borderColor: COLOR.successBorder },
  danger: { color: COLOR.danger, background: COLOR.dangerBg, borderColor: COLOR.dangerBorder },
  neutral: { color: COLOR.neutral, background: COLOR.neutralBg, borderColor: COLOR.neutralBorder },
};
const STATUS: Record<SummaryStatus, { label: string; tone: keyof typeof tone }> = {
  generating: { label: "Đang sinh", tone: "neutral" },
  draft: { label: "Chờ phê duyệt", tone: "warning" },
  approved: { label: "Đã phê duyệt", tone: "success" },
  rejected: { label: "Đã từ chối", tone: "danger" },
  error: { label: "Sinh lỗi", tone: "danger" },
};

const EDITORS: (UserRole | null)[] = [null, "technician", "admin"];
const APPROVERS: (UserRole | null)[] = [null, "approver", "admin"];

/** Máy chủ trả giờ UTC không kèm múi giờ ("2026-11-20T10:00:00"). */
function when(iso: string | null): string {
  if (!iso) return "";
  const date = new Date(`${iso}Z`);
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleString("vi-VN");
}

function StatusBadge({ status }: { status: SummaryStatus }) {
  return (
    <span
      className="inline-flex items-center border px-2 py-0.5 text-[11px] font-semibold whitespace-nowrap"
      style={{ ...tone[STATUS[status].tone], borderRadius: RADIUS.pill }}
    >
      {STATUS[status].label}
    </span>
  );
}

interface SummaryReviewPanelProps {
  documentId: string;
  /** null = máy chủ tắt đăng nhập: mọi thao tác hiện, máy chủ vẫn là nơi kiểm quyền. */
  role: UserRole | null;
  onDirtyChange?: (dirty: boolean) => void;
}

/**
 * Bản tóm tắt tài liệu do LLM viết lúc nạp. Kỹ thuật viên sinh lại / sửa, người duyệt phê duyệt
 * hoặc từ chối; chat chỉ dùng bản đã phê duyệt cho câu hỏi "tóm tắt / nói về gì".
 */
export default function SummaryReviewPanel({ documentId, role, onDirtyChange }: SummaryReviewPanelProps) {
  const [summary, setSummary] = useState<DocSummary | null>(null);
  const [draft, setDraft] = useState("");
  const [note, setNote] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  // waiting: đã bấm sinh, chưa có phản hồi hỏi lại nào; queued: máy chủ báo tài liệu còn trong hàng đợi.
  const [waiting, setWaiting] = useState(false);
  const [queued, setQueued] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const canEdit = EDITORS.includes(role);
  const canApprove = APPROVERS.includes(role);
  const dirty = summary !== null && draft !== summary.text;

  useEffect(() => onDirtyChange?.(dirty), [dirty, onDirtyChange]);

  const show = useCallback((value: DocSummary | null) => {
    setSummary(value);
    setDraft(value?.text ?? "");
  }, []);

  useEffect(() => {
    let live = true;
    getSummary(documentId)
      .then((state) => {
        if (!live) return;
        show(state.summary);
        setQueued(state.queued);
      })
      .catch((e) => {
        if (live) setError(e instanceof Error ? e.message : "Không tải được bản tóm tắt.");
      })
      .finally(() => {
        if (live) setLoading(false);
      });
    return () => {
      live = false;
    };
  }, [documentId, show]);

  // Đang sinh trên luồng nền: hỏi lại định kỳ tới khi máy chủ báo tài liệu đã ra khỏi hàng đợi.
  const generating = waiting || queued;
  useEffect(() => {
    if (!generating) return;
    const timer = window.setInterval(() => {
      getSummary(documentId)
        .then((state) => {
          setWaiting(false);
          setQueued(state.queued);
          if (state.queued) {
            setSummary(state.summary);
            return;
          }
          show(state.summary);
          if (state.summary === null) setError("Không sinh được bản tóm tắt. Vui lòng thử lại hoặc báo quản trị viên xem nhật ký máy chủ.");
        })
        .catch((e) => {
          setWaiting(false);
          setQueued(false);
          setError(e instanceof Error ? e.message : "Không tải được bản tóm tắt.");
        });
    }, POLL_MS);
    return () => window.clearInterval(timer);
  }, [generating, documentId, show]);

  async function run(action: () => Promise<DocSummary | null>, done: string) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const value = await action();
      if (value) show(value);
      setNote("");
      setMessage(done);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Thao tác thất bại.");
    } finally {
      setBusy(false);
    }
  }

  async function regenerate() {
    if (dirty && !window.confirm("Có chỉnh sửa chưa lưu. Sinh lại sẽ thay nội dung này. Tiếp tục?")) return;
    if (summary?.status === "approved" && !window.confirm("Bản tóm tắt đã được phê duyệt. Sinh lại sẽ cần phê duyệt lại. Tiếp tục?")) return;
    setDraft(summary?.text ?? "");
    await run(async () => {
      await generateSummary(documentId);
      setWaiting(true);
      return null;
    }, "Đã xếp hàng sinh bản tóm tắt. Kết quả hiện ở đây khi LLM viết xong (thường dưới 1 phút).");
  }

  const status = summary?.status;
  const settled = !generating && (status === "draft" || status === "approved" || status === "rejected");
  // Dòng "đang sinh" mà máy chủ không còn xếp hàng: lần sinh bị gián đoạn (máy chủ khởi động lại giữa chừng).
  const interrupted = status === "generating" && !generating;
  const edited = summary !== null && summary.generated_text !== "" && summary.text !== summary.generated_text;

  return (
    <section aria-label="Tóm tắt tài liệu" className="p-4 sm:p-5 font-sans text-[13px] leading-relaxed text-on-surface bg-background [overflow-wrap:anywhere]">
      <div className={`${card} mb-4`} style={{ boxShadow: SHADOW.sm }}>
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="text-[15px] font-bold">Tóm tắt tài liệu</h2>
          {status && <StatusBadge status={generating ? "generating" : status} />}
          <span className="flex-1" />
          {canEdit && (
            <button className={summary ? button : primaryButton} disabled={busy || loading || generating} onClick={regenerate}>
              {generating ? "Đang sinh…" : summary ? "Sinh lại bằng LLM" : "Sinh bản tóm tắt"}
            </button>
          )}
        </div>
        <p className="text-secondary mt-2 mb-0">
          LLM viết bản tóm tắt từ chính tài liệu khi nạp. Chatbot chỉ dùng bản đã được người duyệt phê duyệt để trả lời câu hỏi "tóm tắt / tài liệu nói về gì";
          câu hỏi "dùng để làm gì" vẫn trích nguyên văn mục Phạm vi áp dụng.
        </p>
      </div>

      {error && (
        <p role="alert" className={`${notice} mb-3 whitespace-pre-wrap`} style={tone.danger}>
          {error}
        </p>
      )}
      {message && (
        <p role="status" className={`${notice} mb-3`} style={tone.success}>
          {message}
        </p>
      )}
      {loading && <p role="status">Đang tải bản tóm tắt…</p>}
      {!loading && !summary && !generating && !error && (
        <p className="py-6 text-secondary">Tài liệu chưa có bản tóm tắt.{canEdit ? ' Dùng nút "Sinh bản tóm tắt" phía trên.' : ""}</p>
      )}

      {summary && (
        <div className="grid gap-4 xl:grid-cols-2 items-start">
          <div className={card} style={{ boxShadow: SHADOW.sm }}>
            <h3 className="text-[13.5px] font-bold mb-2">Nội dung</h3>
            {summary.stale && (
              <p className={`${notice} mb-3`} style={tone.warning} role="status">
                Tài liệu đã được xử lý lại sau khi sinh bản tóm tắt này. Nên sinh lại để khớp nội dung mới.
              </p>
            )}
            {interrupted && (
              <p className={`${notice} mb-3`} style={tone.warning} role="status">
                Lần sinh trước bị gián đoạn (máy chủ khởi động lại giữa chừng). {canEdit ? 'Bấm "Sinh lại bằng LLM" để sinh lại.' : ""}
              </p>
            )}
            {status === "error" && (
              <p className={`${notice} mb-3`} style={tone.danger} role="alert">
                Sinh bản tóm tắt thất bại: {summary.error}
              </p>
            )}
            {summary.warnings.length > 0 && (
              <div className={`${notice} mb-3`} style={tone.warning} role="status">
                <strong>Cần đối chiếu với tài liệu gốc trước khi phê duyệt:</strong>
                <ul className="list-disc pl-5 mt-1 mb-0">
                  {summary.warnings.map((w) => (
                    <li key={w}>{w}</li>
                  ))}
                </ul>
              </div>
            )}
            {canEdit && settled ? (
              <label className="block font-semibold text-secondary text-[12px]">
                Nội dung tóm tắt (Markdown)
                <textarea
                  className={`${field} min-h-[240px] font-mono text-[12.5px] leading-relaxed`}
                  value={draft}
                  disabled={busy}
                  onChange={(e) => setDraft(e.target.value)}
                />
              </label>
            ) : (
              summary.text && <Markdown className="md-doc">{summary.text}</Markdown>
            )}
            {canEdit && settled && (
              <div className="flex flex-wrap gap-2 mt-3">
                <button
                  className={primaryButton}
                  disabled={busy || !dirty || !draft.trim()}
                  onClick={() => run(() => editSummary(documentId, summary.revision, draft), "Đã lưu. Bản tóm tắt chờ phê duyệt lại.")}
                >
                  Lưu chỉnh sửa
                </button>
                <button className={button} disabled={busy || !dirty} onClick={() => setDraft(summary.text)}>
                  Bỏ chỉnh sửa
                </button>
              </div>
            )}
            <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 mt-4 mb-0 text-[12px] text-secondary">
              {summary.generated_at && (
                <>
                  <dt>Sinh lúc</dt>
                  <dd className="m-0">
                    {when(summary.generated_at)}
                    {summary.model ? ` · ${summary.model}` : ""}
                  </dd>
                </>
              )}
              {summary.edited_by && (
                <>
                  <dt>Sửa bởi</dt>
                  <dd className="m-0">
                    {summary.edited_by} · {when(summary.edited_at)}
                  </dd>
                </>
              )}
              {summary.reviewed_by && (
                <>
                  <dt>{status === "approved" ? "Phê duyệt bởi" : "Từ chối bởi"}</dt>
                  <dd className="m-0">
                    {summary.reviewed_by} · {when(summary.reviewed_at)}
                    {summary.review_note ? ` - ${summary.review_note}` : ""}
                  </dd>
                </>
              )}
            </dl>
          </div>

          <div className="grid gap-4">
            {canEdit && settled && draft.trim() && (
              <div className={card} style={{ boxShadow: SHADOW.sm }}>
                <h3 className="text-[13.5px] font-bold mb-2">Xem trước</h3>
                <Markdown className="md-doc">{draft}</Markdown>
              </div>
            )}
            {canApprove && settled && status !== "rejected" && (
              <div className={card} style={{ boxShadow: SHADOW.sm }}>
                <h3 className="text-[13.5px] font-bold mb-2">Phê duyệt</h3>
                {dirty && <p className="text-secondary mt-0">Lưu chỉnh sửa trước khi phê duyệt.</p>}
                <label className="block font-semibold text-secondary text-[12px]">
                  Ghi chú {status === "approved" ? "(bắt buộc khi thu hồi)" : "(bắt buộc khi từ chối)"}
                  <textarea className={`${field} min-h-[72px]`} value={note} disabled={busy} onChange={(e) => setNote(e.target.value)} />
                </label>
                <div className="flex flex-wrap gap-2 mt-3">
                  {status === "draft" && (
                    <button
                      className={primaryButton}
                      disabled={busy || dirty || summary.stale}
                      title={summary.stale ? "Tài liệu đã được xử lý lại: cần sinh lại trước khi phê duyệt." : undefined}
                      onClick={() =>
                        run(() => decideSummary(documentId, "approve", summary.revision, note), "Đã phê duyệt. Chatbot dùng bản tóm tắt này từ bây giờ.")
                      }
                    >
                      Phê duyệt
                    </button>
                  )}
                  <button
                    className={dangerButton}
                    style={{ color: COLOR.danger, borderColor: COLOR.dangerBorder }}
                    disabled={busy || dirty || !note.trim()}
                    onClick={() =>
                      run(
                        () => decideSummary(documentId, "reject", summary.revision, note),
                        status === "approved" ? "Đã thu hồi phê duyệt." : "Đã từ chối bản tóm tắt.",
                      )
                    }
                  >
                    {status === "approved" ? "Thu hồi phê duyệt" : "Từ chối"}
                  </button>
                </div>
              </div>
            )}
            {edited && (
              <details className={card} style={{ boxShadow: SHADOW.sm }}>
                <summary className="cursor-pointer font-semibold text-secondary">Bản LLM viết ban đầu</summary>
                <Markdown className="md-doc mt-2">{summary.generated_text}</Markdown>
              </details>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
