import type { CSSProperties } from "react";
import { IcBrand, IcCheck } from "../common/icons";

const PROC_DEFS: { a: string; d: string }[] = [
  { a: "Đang tìm trong tài liệu…", d: "Đã tìm trong 24 tài liệu" },
  { a: "Đang lọc các đoạn liên quan…", d: "Tìm được 10 đoạn liên quan" },
  { a: "Đang đọc & đối chiếu nguồn…", d: "Đã đối chiếu 3 nguồn tin cậy" },
  { a: "Đang tổng hợp câu trả lời…", d: "Soạn xong câu trả lời" },
];

export default function ProcessSteps({ step }: { step: number }) {
  return (
    <div className="animate-fadeUp" style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
      <div
        style={{
          flexShrink: 0,
          width: 32,
          height: 32,
          borderRadius: 9999,
          background: "#dae2fd",
          border: "1px solid #becabd",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          marginTop: 2,
        }}
      >
        <IcBrand size={17} style={{ color: "#006130" }} />
      </div>
      <div
        style={{
          minWidth: 290,
          maxWidth: "86%",
          padding: "14px 16px",
          borderRadius: "16px 16px 16px 5px",
          background: "#fff",
          border: "1px solid #becabd",
          boxShadow: "0 6px 18px -10px rgba(19,27,46,.18)",
        }}
      >
        <div style={{ fontSize: "12.5px", fontWeight: 700, color: "#3f4940", marginBottom: 11, display: "flex", alignItems: "center", gap: 8 }}>
          <span className="animate-spin" style={{ width: 14, height: 14, border: "2px solid #becabd", borderTopColor: "#006130", borderRadius: "50%" }} />
          Đang xử lý câu hỏi của bạn…
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {PROC_DEFS.map((d, i) => {
            // Chỉ hiện bước ĐÃ XONG + đúng 1 bước ĐANG chạy; bước chưa tới thì ẩn.
            if (i > step) return null;
            const done = i < step;
            const labelStyle: CSSProperties = done ? { color: "#006130", fontWeight: 500 } : { color: "#131b2e", fontWeight: 600 };
            return (
              <div key={i} className="animate-fadeUp" style={{ display: "flex", alignItems: "center", gap: 10, fontSize: "13px" }}>
                {done ? (
                  <span
                    style={{
                      flexShrink: 0,
                      width: 19,
                      height: 19,
                      borderRadius: 9999,
                      background: "#006130",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                    }}
                  >
                    <IcCheck size={11} strokeWidth={3} style={{ color: "#fff" }} />
                  </span>
                ) : (
                  <span
                    className="animate-spin"
                    style={{ flexShrink: 0, width: 19, height: 19, border: "2px solid #dae2fd", borderTopColor: "#006130", borderRadius: "50%" }}
                  />
                )}
                <span style={{ ...labelStyle, fontSize: "13px" }}>{done ? d.d : d.a}</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
