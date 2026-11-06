import { IcDownload } from "../common/icons";

/** Nút "Tải xuống" ở đầu khung xem tài liệu: lưu tệp gốc đúng định dạng đã tải lên. */
export default function DownloadButton({ onDownload, ext }: { onDownload: () => void; ext?: string }) {
  const label = ext ? `Tải xuống tệp gốc (.${ext.toLowerCase()})` : "Tải xuống tệp gốc";
  return (
    <button
      type="button"
      onClick={onDownload}
      title={label}
      aria-label={label}
      className="flex-shrink-0 inline-flex items-center gap-[6px] h-8 px-[11px] border border-line rounded-[9px] bg-white font-sans text-[12.5px] font-semibold text-secondary cursor-pointer transition-colors hover:border-brand hover:text-brand active:scale-[0.97] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
    >
      <IcDownload size={13} /> Tải xuống
    </button>
  );
}
