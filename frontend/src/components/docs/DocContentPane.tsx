import { useEffect, useRef, useState } from "react";
import { renderAsync } from "docx-preview";
import type { ViewingDoc } from "../../types";
import { COLOR } from "../../theme";
import DocPage from "../common/DocPage";
import Markdown from "../common/Markdown";

/** Render tệp .docx gốc thẳng trong trình duyệt (offline, không gọi dịch vụ ngoài) qua docx-preview. */
function DocxFilePreview({ fileUrl, name }: { fileUrl: string; name: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const controller = new AbortController();
    setStatus("loading");
    container.innerHTML = "";
    fetch(fileUrl, { signal: controller.signal })
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.blob();
      })
      .then((blob) => renderAsync(blob, container))
      .then(() => setStatus("ready"))
      .catch((e) => {
        if (controller.signal.aborted) return;
        setStatus("error");
        console.error("Không render được tệp .docx gốc:", e);
      });
    return () => controller.abort();
  }, [fileUrl]);

  return (
    <div style={{ maxWidth: 900, margin: "0 auto" }}>
      {status === "loading" && <div style={{ padding: 20, textAlign: "center", color: COLOR.textMuted, fontSize: 13 }}>Đang tải tệp gốc…</div>}
      {status === "error" && (
        <div style={{ padding: 20, textAlign: "center", color: COLOR.textMuted, fontSize: 13 }}>
          Không hiển thị được tệp gốc.{" "}
          <a href={fileUrl} download={name} style={{ color: COLOR.accent, fontWeight: 600 }}>
            Tải xuống để xem
          </a>
          .
        </div>
      )}
      <div ref={containerRef} style={{ display: status === "ready" ? "block" : "none" }} />
    </div>
  );
}

/** Nội dung tài liệu — ưu tiên hiển thị tệp gốc (.docx/.pdf) thô; Markdown đã trích xuất/embed chỉ là phương án dự phòng. */
export default function DocContentPane({ viewingDoc }: { viewingDoc: ViewingDoc }) {
  const pageLabel = viewingDoc.pages ? `TRANG 01 / ${String(viewingDoc.pages).padStart(2, "0")}` : "TRANG 01";

  if (viewingDoc.fileUrl && viewingDoc.ext === "PDF") {
    return (
      <div style={{ flex: 1, minWidth: 0, display: "flex" }}>
        <iframe src={viewingDoc.fileUrl} title={viewingDoc.name} style={{ flex: 1, border: "none" }} />
      </div>
    );
  }

  if (viewingDoc.fileUrl && viewingDoc.ext === "DOCX") {
    return (
      <div style={{ flex: 1, minWidth: 0, overflow: "auto", padding: 20 }}>
        <DocxFilePreview fileUrl={viewingDoc.fileUrl} name={viewingDoc.name} />
      </div>
    );
  }

  return (
    <div style={{ flex: 1, minWidth: 0, overflowY: "auto", padding: 20 }}>
      {viewingDoc.markdown != null ? (
        <div
          style={{
            maxWidth: 900,
            margin: "0 auto",
            background: COLOR.surface,
            border: `1px solid ${COLOR.border}`,
            borderRadius: 6,
            boxShadow: "0 6px 22px -10px rgba(16,24,40,.18)",
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
