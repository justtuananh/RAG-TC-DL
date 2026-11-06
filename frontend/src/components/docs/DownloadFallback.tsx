import { COLOR } from "../../theme";

/** Liên kết "Tải xuống để xem" khi không hiển thị được tệp gốc trong trình duyệt. */
export default function DownloadFallback({ onDownload }: { onDownload?: () => void }) {
  if (!onDownload) return null;
  return (
    <>
      {" "}
      <button
        type="button"
        onClick={onDownload}
        className="border-none bg-transparent p-0 font-sans cursor-pointer underline-offset-2 hover:underline"
        style={{ color: COLOR.accent, fontWeight: 600, fontSize: "inherit" }}
      >
        Tải xuống để xem
      </button>
      .
    </>
  );
}
