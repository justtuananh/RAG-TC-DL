import { useCallback, useEffect, useRef, useState } from "react";
import type { DragEvent } from "react";
import type { UserRole } from "../../types";
import { COLOR } from "../../theme";
import { authFetch } from "../../services/auth";
import {
  APPROVAL_COPY_ACCEPT,
  approvalCopyFileUrl,
  deleteApprovalCopy,
  listApprovalCopies,
  uploadApprovalCopy,
  type ApprovalCopy,
} from "../../services/approvalCopyApi";
import { IcEye, IcFile, IcInfo, IcTrash, IcUpload } from "../common/icons";

const UPLOADERS: (UserRole | null)[] = [null, "technician", "approver", "admin"];
const DESK_BG = COLOR.surfaceMuted;
const buttonBase =
  "inline-flex items-center justify-center gap-2 min-h-9 border rounded-lg px-3 py-2 font-sans text-[12.5px] font-semibold transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand disabled:opacity-40 disabled:cursor-not-allowed";
const primaryButton = `${buttonBase} border-brand bg-brand text-on-primary hover:bg-brand-dark hover:border-brand-dark`;

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1).replace(".", ",")} MB`;
}

function formatWhen(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleString("vi-VN");
}

const kindLabel = (copy: ApprovalCopy) => (copy.media_type === "application/pdf" ? "PDF" : "ẢNH");

/** Hiển thị một bản phê duyệt: route cần token nên tải qua authFetch rồi dùng object URL. */
function CopyViewer({ documentId, copy }: { documentId: string; copy: ApprovalCopy }) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    let objectUrl: string | null = null;
    authFetch(approvalCopyFileUrl(documentId, copy.id), { signal: controller.signal })
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.blob();
      })
      .then((blob) => {
        objectUrl = URL.createObjectURL(new Blob([blob], { type: copy.media_type }));
        setBlobUrl(objectUrl);
      })
      .catch(() => {
        if (!controller.signal.aborted) setFailed(true);
      });
    return () => {
      controller.abort();
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [documentId, copy.id, copy.media_type]);

  if (!blobUrl) {
    return (
      <div className="flex-1 flex items-center justify-center p-6 text-center text-[13px]" style={{ color: COLOR.textMuted }}>
        {failed ? "Không hiển thị được tệp. Vui lòng thử lại." : "Đang tải tệp…"}
      </div>
    );
  }
  if (copy.media_type === "application/pdf") {
    return <iframe src={blobUrl} title={copy.name} className="flex-1 w-full border-0" />;
  }
  return (
    <div className="flex-1 overflow-auto p-4 sm:p-6">
      <img src={blobUrl} alt={copy.name} className="block mx-auto max-w-full h-auto bg-white shadow-md" />
    </div>
  );
}

interface CopyRowProps {
  copy: ApprovalCopy;
  isActive: boolean;
  canDelete: boolean;
  isBusy: boolean;
  onSelect: () => void;
  onDelete: () => void;
}

function CopyRow({ copy, isActive, canDelete, isBusy, onSelect, onDelete }: CopyRowProps) {
  return (
    <li
      className={`flex items-start gap-2 rounded-[10px] border p-2.5 transition-colors ${isActive ? "border-brand bg-primary-container" : "border-line bg-surface hover:border-brand"}`}
    >
      <button
        type="button"
        onClick={onSelect}
        aria-current={isActive}
        className="flex-1 min-w-0 flex items-start gap-2.5 text-left bg-transparent border-0 p-0 cursor-pointer rounded focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
      >
        <span
          aria-hidden
          className="flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center text-[9.5px] font-bold"
          style={{ background: COLOR.accentSoft, color: COLOR.accent }}
        >
          {kindLabel(copy)}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-[12.5px] font-semibold truncate" style={{ color: COLOR.textPrimary }} title={copy.name}>
            {copy.name}
          </span>
          <span className="block text-[11px] mt-0.5" style={{ color: COLOR.textMuted }}>
            {formatSize(copy.size)} · {formatWhen(copy.uploaded_at)}
          </span>
          {copy.uploaded_by && (
            <span className="block text-[11px]" style={{ color: COLOR.textMuted }}>
              Tải lên bởi {copy.uploaded_by}
            </span>
          )}
        </span>
      </button>
      {canDelete && (
        <button
          type="button"
          onClick={onDelete}
          disabled={isBusy}
          title="Xoá bản phê duyệt"
          aria-label={`Xoá ${copy.name}`}
          className="flex-shrink-0 w-7 h-7 rounded-md flex items-center justify-center border border-transparent bg-transparent cursor-pointer transition-colors hover:border-line hover:bg-surface disabled:opacity-40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand"
          style={{ color: COLOR.danger }}
        >
          <IcTrash size={13} />
        </button>
      )}
    </li>
  );
}

interface ApprovalCopiesPanelProps {
  documentId: string;
  /** null = máy chủ tắt đăng nhập: mọi thao tác hiện, máy chủ vẫn là nơi kiểm quyền. */
  role: UserRole | null;
}

/**
 * "Tài liệu phê duyệt": bản cứng (PDF scan, ảnh chụp) của tài liệu đã ký duyệt.
 * Chỉ để xem đối chiếu - không trích xuất, không nhúng, chatbot không dùng.
 */
export default function ApprovalCopiesPanel({ documentId, role }: ApprovalCopiesPanelProps) {
  const [copies, setCopies] = useState<ApprovalCopy[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const canUpload = UPLOADERS.includes(role);
  const selected = copies.find((c) => c.id === selectedId) ?? copies[0] ?? null;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setCopies(await listApprovalCopies(documentId));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Không tải được danh sách bản phê duyệt.");
    } finally {
      setLoading(false);
    }
  }, [documentId]);

  useEffect(() => {
    void load();
  }, [load]);

  const upload = async (files: File[]) => {
    if (files.length === 0) return;
    setBusy(true);
    setError("");
    const failures: string[] = [];
    let lastId: string | null = null;
    for (const file of files) {
      try {
        lastId = (await uploadApprovalCopy(documentId, file)).id;
      } catch (e) {
        failures.push(`${file.name}: ${e instanceof Error ? e.message : "tải lên thất bại"}`);
      }
    }
    await load();
    if (lastId) setSelectedId(lastId);
    if (failures.length) setError(failures.join("\n"));
    setBusy(false);
  };

  const remove = async (copy: ApprovalCopy) => {
    if (!window.confirm(`Xoá bản phê duyệt "${copy.name}"? Thao tác này không hoàn tác được.`)) return;
    setBusy(true);
    setError("");
    try {
      await deleteApprovalCopy(documentId, copy.id);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Xoá thất bại.");
    } finally {
      setBusy(false);
    }
  };

  const handleDrop = (event: DragEvent<HTMLElement>) => {
    event.preventDefault();
    setDragging(false);
    if (canUpload && !busy) void upload(Array.from(event.dataTransfer.files));
  };

  const handleDragOver = (event: DragEvent<HTMLElement>) => {
    if (!canUpload) return;
    event.preventDefault();
    setDragging(true);
  };

  const emptyText = canUpload ? "Tải lên bản scan PDF hoặc ảnh chụp để xem tại đây." : "Chưa có bản phê duyệt để xem.";

  return (
    <div className="flex-1 min-h-0 flex flex-col md:flex-row">
      <aside
        className="flex-shrink-0 md:w-[300px] flex flex-col min-h-0 max-h-[45%] md:max-h-none border-b md:border-b-0 md:border-r border-line bg-surface"
        onDragOver={handleDragOver}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
      >
        <div className="flex-shrink-0 p-4 border-b border-line">
          <div className="flex items-center gap-1.5 text-[12px] font-bold" style={{ color: COLOR.textPrimary }}>
            <IcFile size={13} style={{ color: COLOR.accent }} /> Bản cứng đã phê duyệt
          </div>
          <p className="flex items-start gap-1.5 mt-1.5 mb-0 text-[11.5px] leading-relaxed" style={{ color: COLOR.textMuted }}>
            <IcInfo size={12} style={{ flexShrink: 0, marginTop: 3 }} />
            Chỉ để xem đối chiếu. Chatbot không đọc các tệp này.
          </p>
          {canUpload && (
            <>
              <button type="button" className={`${primaryButton} w-full mt-3`} disabled={busy} onClick={() => inputRef.current?.click()}>
                <IcUpload size={14} /> {busy ? "Đang xử lý…" : "Tải lên PDF hoặc ảnh"}
              </button>
              <input
                ref={inputRef}
                type="file"
                multiple
                accept={APPROVAL_COPY_ACCEPT}
                className="hidden"
                data-testid="approval-copy-input"
                onChange={(e) => {
                  const files = Array.from(e.target.files ?? []);
                  e.target.value = "";
                  void upload(files);
                }}
              />
              <p className="mt-2 mb-0 text-[11px] text-center" style={{ color: COLOR.textMuted }}>
                hoặc kéo thả tệp vào đây · PDF, PNG, JPG, WEBP
              </p>
            </>
          )}
        </div>
        {error && (
          <div
            role="alert"
            className="flex-shrink-0 mx-3 mt-3 border rounded-[10px] px-3 py-2 text-[12px] leading-relaxed whitespace-pre-line"
            style={{ color: COLOR.danger, background: COLOR.dangerBg, borderColor: COLOR.dangerBorder }}
          >
            {error}
          </div>
        )}
        <div className={`flex-1 min-h-0 overflow-y-auto p-3 transition-colors ${dragging ? "bg-primary-container" : ""}`}>
          {copies.length === 0 ? (
            <p className="m-0 p-2 text-[12.5px] leading-relaxed" style={{ color: COLOR.textMuted }}>
              {loading ? "Đang tải…" : "Chưa có bản phê duyệt nào cho tài liệu này."}
            </p>
          ) : (
            <ul className="flex flex-col gap-2 list-none m-0 p-0" aria-label="Danh sách bản phê duyệt">
              {copies.map((copy) => (
                <CopyRow
                  key={copy.id}
                  copy={copy}
                  isActive={selected?.id === copy.id}
                  canDelete={canUpload}
                  isBusy={busy}
                  onSelect={() => setSelectedId(copy.id)}
                  onDelete={() => void remove(copy)}
                />
              ))}
            </ul>
          )}
        </div>
      </aside>
      <section className="flex-1 min-w-0 min-h-0 flex flex-col" style={{ background: DESK_BG }} aria-label="Xem bản phê duyệt">
        {selected ? (
          <CopyViewer key={selected.id} documentId={documentId} copy={selected} />
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center gap-2 p-6 text-center" style={{ color: COLOR.textMuted }}>
            <IcEye size={22} />
            <span className="text-[13px]">{emptyText}</span>
          </div>
        )}
      </section>
    </div>
  );
}
