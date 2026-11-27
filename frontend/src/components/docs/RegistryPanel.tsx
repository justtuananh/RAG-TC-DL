import { useCallback, useEffect, useRef, useState } from "react";
import type { UserRole } from "../../types";
import { COLOR } from "../../theme";
import {
  decideRegistrySource,
  deleteRegistrySource,
  getRegistryGaps,
  getRegistrySource,
  listRegistrySources,
  uploadRegistrySource,
  type RegistryGap,
  type RegistryIssue,
  type RegistrySource,
  type RegistryStatus,
} from "../../services/registryApi";

const STATUS_LABEL: Record<RegistryStatus, string> = {
  draft: "Bản nháp",
  approved: "Đang dùng",
  rejected: "Đã từ chối",
  replaced: "Đã thay thế",
};
const STATUS_TONE: Record<RegistryStatus, { bg: string; fg: string }> = {
  draft: { bg: "#FFF4D6", fg: "#8A5A00" },
  approved: { bg: "#E3F5EA", fg: "#1D6B3A" },
  rejected: { bg: "#FDE7E7", fg: "#9B1C1C" },
  replaced: { bg: "#EEF0F3", fg: "#5B6472" },
};
const LEVEL_LABEL: Record<string, string> = { error: "Lỗi", warning: "Cần xem", info: "Ghi chú" };
const LEVEL_COLOR: Record<string, string> = { error: "#B42318", warning: "#9A6700", info: "#5B6472" };
const ERROR_COLOR = "#B42318";

const button =
  "inline-flex items-center h-8 px-3 rounded-lg border font-sans text-[12.5px] font-semibold transition-colors disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand";
const neutral = `${button} border-line bg-white text-secondary hover:border-brand hover:text-brand`;
const primary = `${button} border-brand bg-brand text-white hover:opacity-90`;
const danger = `${button} border-line bg-white text-[#B42318] hover:border-[#B42318]`;

interface Gaps {
  missing: RegistryGap[];
  total: number;
}

interface RegistryPanelProps {
  /** Vai trò người đang đăng nhập (null = máy chủ tắt đăng nhập). */
  role: UserRole | null;
  onClose: () => void;
}

const canEdit = (role: UserRole | null) => role === null || role === "technician" || role === "admin";
const canApprove = (role: UserRole | null) => role === null || role === "approver" || role === "admin";
const errorText = (error: unknown) => (error instanceof Error ? error.message : "Có lỗi xảy ra. Vui lòng thử lại.");
const formatDate = (value: string | null) => (value ? new Date(value).toLocaleString("vi-VN") : "");

function IssueList({ title, issues }: { title: string; issues: RegistryIssue[] }) {
  if (issues.length === 0) return null;
  return (
    <section className="mt-4">
      <h4 className="font-sans text-[12.5px] font-bold text-secondary mb-2">
        {title} ({issues.length})
      </h4>
      <ul className="flex flex-col gap-1">
        {issues.map((issue, index) => (
          <li key={index} className="text-[13px] leading-snug" style={{ color: COLOR.textPrimary }}>
            <span className="font-semibold" style={{ color: LEVEL_COLOR[issue.level] ?? COLOR.textSecondary }}>
              {LEVEL_LABEL[issue.level] ?? issue.level}
            </span>
            {issue.row !== null && (
              <span className="tabular-nums" style={{ color: COLOR.textMuted }}>
                {" "}
                · dòng {issue.row}
              </span>
            )}
            <span> · {issue.message}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function ChangeList({ source }: { source: RegistrySource }) {
  const changes = source.changes;
  if (!changes || changes.base_id === null) return null;
  const groups: [string, string[]][] = [
    ["Thêm mới", changes.added],
    ["Bị bỏ", changes.removed],
    ["Thay đổi nội dung", changes.changed],
  ];
  const nonEmpty = groups.filter(([, items]) => items.length > 0);
  return (
    <section className="mt-4">
      <h4 className="font-sans text-[12.5px] font-bold text-secondary mb-2">So với bản đang dùng</h4>
      {nonEmpty.length === 0 ? (
        <p className="text-[13px]" style={{ color: COLOR.textMuted }}>
          Không có dòng nào khác.
        </p>
      ) : (
        nonEmpty.map(([label, items]) => (
          <p key={label} className="text-[13px] leading-snug mb-1" style={{ color: COLOR.textPrimary }}>
            <span className="font-semibold">
              {label} ({items.length}):
            </span>{" "}
            {items.join("; ")}
          </p>
        ))
      )}
    </section>
  );
}

function SourceDetail({ source, role, onChanged }: { source: RegistrySource; role: UserRole | null; onChanged: () => void }) {
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const hasErrors = source.issues.some((issue) => issue.level === "error");
  const crossIssues = source.cross_issues ?? [];

  const run = async (action: () => Promise<unknown>) => {
    setBusy(true);
    setError(null);
    try {
      await action();
      onChanged();
    } catch (e: unknown) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="px-4 pb-4 pt-1 border-t border-line" style={{ background: COLOR.bg }}>
      {source.title && (
        <p className="mt-3 text-[13px] font-semibold" style={{ color: COLOR.textPrimary }}>
          {source.title}
        </p>
      )}
      <IssueList title="Báo cáo khi nạp file" issues={source.issues} />
      <IssueList title="Đối chiếu với danh mục quy trình" issues={crossIssues} />
      {source.issues.length === 0 && crossIssues.length === 0 && (
        <p className="mt-3 text-[13px]" style={{ color: COLOR.textMuted }}>
          Không phát hiện lỗi dữ liệu.
        </p>
      )}
      <ChangeList source={source} />
      {source.review_note && (
        <p className="mt-3 text-[13px]" style={{ color: COLOR.textSecondary }}>
          Ghi chú duyệt: {source.review_note}
        </p>
      )}
      {source.status === "draft" && canApprove(role) && (
        <div className="mt-4 flex flex-col gap-2">
          <label className="text-[12.5px] font-semibold text-secondary" htmlFor={`registry-note-${source.id}`}>
            Ghi chú khi duyệt
          </label>
          <textarea
            id={`registry-note-${source.id}`}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            maxLength={4000}
            rows={2}
            className="w-full rounded-lg border border-line bg-white p-2 font-sans text-[13px] focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand"
          />
          <div className="flex gap-2 flex-wrap">
            <button
              className={primary}
              disabled={busy || hasErrors}
              title={hasErrors ? "Còn lỗi mức nghiêm trọng, cần sửa file rồi nạp lại" : undefined}
              onClick={() => void run(() => decideRegistrySource(source.id, source.revision, true, note))}
            >
              Phê duyệt, dùng cho chatbot
            </button>
            <button className={neutral} disabled={busy} onClick={() => void run(() => decideRegistrySource(source.id, source.revision, false, note))}>
              Từ chối
            </button>
          </div>
        </div>
      )}
      {source.status !== "approved" && canEdit(role) && (
        <div className="mt-3">
          <button className={danger} disabled={busy} onClick={() => void run(() => deleteRegistrySource(source.id))}>
            Xoá bản này
          </button>
        </div>
      )}
      {error && (
        <p role="alert" className="mt-3 text-[13px] font-semibold" style={{ color: ERROR_COLOR }}>
          {error}
        </p>
      )}
    </div>
  );
}

function GapList({ gaps }: { gaps: Gaps | null }) {
  if (!gaps || gaps.total === 0) return null;
  return (
    <details className="mt-4 rounded-xl border border-line bg-white px-4 py-3">
      <summary className="cursor-pointer font-sans text-[13px] font-semibold" style={{ color: COLOR.textPrimary }}>
        Quy trình có trong danh mục nhưng kho chưa có văn bản: {gaps.missing.length}/{gaps.total}
      </summary>
      <ul className="mt-2 flex flex-col gap-1">
        {gaps.missing.map((gap) => (
          <li key={gap.code} className="text-[13px]" style={{ color: COLOR.textPrimary }}>
            <span className="font-semibold">{gap.code}</span> - {gap.title}
            <span style={{ color: COLOR.textMuted }}> (dòng {gap.row})</span>
          </li>
        ))}
      </ul>
    </details>
  );
}

/** Sổ đăng ký danh mục 877: nạp 4 file danh mục, xem báo cáo lỗi, duyệt để chatbot dùng. */
export default function RegistryPanel({ role, onClose }: RegistryPanelProps) {
  const fileInput = useRef<HTMLInputElement>(null);
  const [sources, setSources] = useState<RegistrySource[]>([]);
  const [gaps, setGaps] = useState<Gaps | null>(null);
  const [openId, setOpenId] = useState<number | null>(null);
  const [detail, setDetail] = useState<RegistrySource | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setError(null);
    try {
      const [list, missing] = await Promise.all([listRegistrySources(), getRegistryGaps()]);
      setSources(list);
      setGaps(missing);
    } catch (e: unknown) {
      setError(errorText(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // Chi tiết (báo cáo đối chiếu, thay đổi) đọc lại khi mở một bản hoặc khi danh sách đổi sau duyệt / xoá.
  useEffect(() => {
    if (openId === null) {
      setDetail(null);
      return;
    }
    let cancelled = false;
    getRegistrySource(openId)
      .then((value) => {
        if (!cancelled) setDetail(value);
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(errorText(e));
      });
    return () => {
      cancelled = true;
    };
  }, [openId, sources]);

  const upload = async (file: File | undefined) => {
    if (!file) return;
    setError(null);
    try {
      const created = await uploadRegistrySource(file);
      await refresh();
      setOpenId(created.id);
    } catch (e: unknown) {
      setError(errorText(e));
    }
  };

  return (
    <section aria-label="Danh mục 877" className="rounded-[14px] border border-line bg-white overflow-hidden">
      <header className="flex items-center gap-3 flex-wrap px-4 py-3 border-b border-line">
        <div className="flex-1 min-w-0">
          <h3 className="font-sans text-[14.5px] font-bold" style={{ color: COLOR.textPrimary }}>
            Danh mục 877 (sổ đăng ký)
          </h3>
          <p className="text-[12px]" style={{ color: COLOR.textMuted }}>
            Danh mục quy trình, năng lực kiểm định, năng lực hiệu chuẩn, chuẩn mẫu. Chatbot chỉ dùng bản đã duyệt.
          </p>
        </div>
        {canEdit(role) && (
          <>
            <input
              ref={fileInput}
              type="file"
              accept=".docx"
              hidden
              onChange={(e) => {
                void upload(e.target.files?.[0]);
                e.target.value = "";
              }}
            />
            <button className={primary} onClick={() => fileInput.current?.click()}>
              Nạp file danh mục (.docx)
            </button>
          </>
        )}
        <button className={neutral} onClick={onClose}>
          Đóng
        </button>
      </header>

      {error && (
        <p role="alert" className="px-4 pt-3 text-[13px] font-semibold" style={{ color: ERROR_COLOR }}>
          {error}
        </p>
      )}
      {loading ? (
        <p className="px-4 py-6 text-[13px]" style={{ color: COLOR.textMuted }}>
          Đang tải…
        </p>
      ) : sources.length === 0 ? (
        <p className="px-4 py-6 text-[13px]" style={{ color: COLOR.textMuted }}>
          Chưa nạp file danh mục nào.
        </p>
      ) : (
        <ul>
          {sources.map((source) => {
            const open = openId === source.id;
            const tone = STATUS_TONE[source.status] ?? STATUS_TONE.replaced;
            const attention = source.attention ?? source.issues.filter((issue) => issue.level !== "info").length;
            return (
              <li key={source.id} className="border-b border-line last:border-b-0">
                <button
                  className="w-full flex items-center gap-3 flex-wrap px-4 py-3 text-left hover:bg-[#F7F8FA] focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand"
                  aria-expanded={open}
                  onClick={() => setOpenId(open ? null : source.id)}
                >
                  <span className="rounded-md px-2 py-[2px] text-[11.5px] font-bold" style={{ background: tone.bg, color: tone.fg }}>
                    {STATUS_LABEL[source.status] ?? source.status}
                  </span>
                  <span className="font-sans text-[13px] font-semibold" style={{ color: COLOR.textPrimary }}>
                    {source.kind_label}
                  </span>
                  <span className="flex-1 min-w-0 truncate text-[12.5px]" style={{ color: COLOR.textSecondary }}>
                    {source.file_name}
                  </span>
                  <span className="tabular-nums text-[12px]" style={{ color: COLOR.textMuted }}>
                    {source.row_count} dòng · {attention} cần xem · {formatDate(source.uploaded_at)}
                  </span>
                </button>
                {open && detail?.id === source.id && <SourceDetail source={detail} role={role} onChanged={() => void refresh()} />}
              </li>
            );
          })}
        </ul>
      )}
      <div className="px-4 pb-4">
        <GapList gaps={gaps} />
      </div>
    </section>
  );
}
