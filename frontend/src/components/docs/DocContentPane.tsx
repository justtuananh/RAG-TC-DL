import { useEffect, useRef, useState } from "react";
import { renderAsync } from "docx-preview";
import type { ViewingDoc } from "../../types";
import { COLOR } from "../../theme";
import { authFetch } from "../../services/auth";
import DocPage from "../common/DocPage";
import Markdown from "../common/Markdown";
import DownloadFallback from "./DownloadFallback";
import XlsxFilePreview from "./xlsx/XlsxFilePreview";

/** Nền "bàn làm việc" quanh trang giấy, khớp token giao diện (thay nền xám của docx-preview). */
const DESK_BG = COLOR.surfaceMuted;

/** Lề ngang của "bàn làm việc" quanh trang (khớp padding .docx-wrapper trong index.css). */
const DESK_GUTTER = 48;

/**
 * Thu nhỏ (không phóng to) từng trang rộng hơn khung, như "Vừa chiều rộng trang" của Word:
 * tài liệu lẫn trang dọc và trang ngang thì trang dọc vẫn giữ nguyên 100%.
 */
function fitPagesToWidth(scroller: HTMLElement, wrapper: HTMLElement | null) {
  if (!wrapper) return;
  const available = scroller.clientWidth - DESK_GUTTER;
  for (const page of Array.from(wrapper.querySelectorAll<HTMLElement>("section.docx"))) {
    page.style.zoom = "";
    const width = page.offsetWidth;
    page.style.zoom = width > available && available > 0 ? String(available / width) : "";
  }
}

/**
 * Render tệp Word gốc thẳng trong trình duyệt (offline) qua docx-preview. Tệp .doc cũ
 * đi qua cùng đường này: backend trả bản .docx đã chuyển bằng LibreOffice nên giữ đúng
 * khổ giấy, lề, font, bảng của tài liệu gốc. Khung có thanh cuộn riêng.
 */
/**
 * PDF gốc trong iframe. Route tệp cần token nên không gán thẳng URL cho iframe:
 * tải qua authFetch rồi hiển thị bằng object URL (thu hồi khi đổi tài liệu).
 */
function PdfFilePreview({ fileUrl, name, onDownload }: { fileUrl: string; name: string; onDownload?: () => void }) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    let objectUrl: string | null = null;
    setBlobUrl(null);
    setFailed(false);
    authFetch(fileUrl, { signal: controller.signal })
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.blob();
      })
      .then((blob) => {
        objectUrl = URL.createObjectURL(blob.type ? blob : new Blob([blob], { type: "application/pdf" }));
        setBlobUrl(objectUrl);
      })
      .catch(() => {
        if (!controller.signal.aborted) setFailed(true);
      });
    return () => {
      controller.abort();
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [fileUrl]);

  return (
    <div style={{ flex: 1, minWidth: 0, display: "flex", background: DESK_BG }}>
      {blobUrl ? (
        <iframe src={blobUrl} title={name} style={{ flex: 1, border: "none" }} />
      ) : (
        <div style={{ flex: 1, padding: 24, textAlign: "center", color: COLOR.textMuted, fontSize: 13 }}>
          {failed ? (
            <>
              Không hiển thị được tệp gốc.
              <DownloadFallback onDownload={onDownload} />
            </>
          ) : (
            "Đang tải tệp gốc…"
          )}
        </div>
      )}
    </div>
  );
}

function DocxFilePreview({ previewUrl, onDownload }: { previewUrl: string; onDownload?: () => void }) {
  const scrollerRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const controller = new AbortController();
    setStatus("loading");
    container.innerHTML = "";
    authFetch(previewUrl, { signal: controller.signal })
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.blob();
      })
      .then((blob) => renderAsync(blob, container))
      .then(() => setStatus("ready"))
      .catch((e) => {
        if (controller.signal.aborted) return;
        setStatus("error");
        console.error("Không render được tệp Word gốc:", e);
      });
    return () => controller.abort();
  }, [previewUrl]);

  useEffect(() => {
    const scroller = scrollerRef.current;
    if (status !== "ready" || !scroller) return;
    const fit = () => fitPagesToWidth(scroller, containerRef.current?.querySelector<HTMLElement>(".docx-wrapper") ?? null);
    fit();
    const observer = new ResizeObserver(fit);
    observer.observe(scroller);
    return () => observer.disconnect();
  }, [status]);

  return (
    <div ref={scrollerRef} style={{ flex: 1, minWidth: 0, minHeight: 0, overflow: "auto", background: DESK_BG }}>
      {status === "loading" && <div style={{ padding: 24, textAlign: "center", color: COLOR.textMuted, fontSize: 13 }}>Đang tải tệp gốc…</div>}
      {status === "error" && (
        <div style={{ padding: 24, textAlign: "center", color: COLOR.textMuted, fontSize: 13 }}>
          Không hiển thị được tệp gốc.
          <DownloadFallback onDownload={onDownload} />
        </div>
      )}
      <div ref={containerRef} className="docx-host" style={{ display: status === "ready" ? "block" : "none" }} />
    </div>
  );
}

/** Nội dung tài liệu: ưu tiên tệp gốc (Word, Excel, PDF); Markdown đã trích xuất chỉ là phương án dự phòng. */
export default function DocContentPane({ viewingDoc, onDownload }: { viewingDoc: ViewingDoc; onDownload?: () => void }) {
  const { ext, fileUrl, previewUrl, name } = viewingDoc;
  const pageLabel = viewingDoc.pages ? `TRANG 01 / ${String(viewingDoc.pages).padStart(2, "0")}` : "TRANG 01";

  if (fileUrl && ext === "PDF") {
    return <PdfFilePreview fileUrl={fileUrl} name={name} onDownload={onDownload} />;
  }

  if (fileUrl && previewUrl && (ext === "DOCX" || ext === "DOC")) {
    return <DocxFilePreview previewUrl={previewUrl} onDownload={onDownload} />;
  }

  if (fileUrl && previewUrl && (ext === "XLSX" || ext === "XLS")) {
    return (
      <div style={{ flex: 1, minWidth: 0, minHeight: 0, display: "flex" }}>
        <XlsxFilePreview fileUrl={previewUrl} onDownload={onDownload} />
      </div>
    );
  }

  return (
    <div style={{ flex: 1, minWidth: 0, minHeight: 0, overflowY: "auto", padding: 20, background: DESK_BG }}>
      {viewingDoc.markdown != null ? (
        <div
          style={{
            maxWidth: 900,
            margin: "0 auto",
            background: COLOR.surface,
            border: `1px solid ${COLOR.border}`,
            borderRadius: 6,
            boxShadow: `0 6px 22px -10px ${COLOR.shadowPageSoft}`,
            padding: "30px 36px 26px",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              paddingBottom: 11,
              marginBottom: 5,
              borderBottom: `1px dashed ${COLOR.border}`,
              fontFamily: "'Be Vietnam Pro',sans-serif",
              fontSize: "10.5px",
              letterSpacing: ".08em",
              color: COLOR.textMuted,
              textTransform: "uppercase",
            }}
          >
            <span>{viewingDoc.code}</span>
            <span>Tài liệu nguồn</span>
          </div>
          <Markdown className="md-doc">{viewingDoc.markdown}</Markdown>
        </div>
      ) : (
        <DocPage
          code={viewingDoc.code}
          topRight={pageLabel}
          footLabel={pageLabel}
          blocks={viewingDoc.blocks}
          withHighlight={false}
          paperPadding="30px 36px 26px"
        />
      )}
    </div>
  );
}
