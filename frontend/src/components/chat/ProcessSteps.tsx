import type { CSSProperties } from "react";
import type { Proc } from "../../types";
import { COLOR } from "../../theme";
import { IcBrand, IcCheck } from "../common/icons";

// Các pha xử lý theo đúng thứ tự backend thực hiện; pha sau chỉ bắt đầu khi pha trước xong.
function phases(proc: Proc): { a: string; d: string }[] {
  const found = proc.passages !== undefined ? `Tìm được ${proc.passages} đoạn liên quan trong ${proc.docs ?? 0} tài liệu` : "Đã tìm và lọc nguồn";
  return [
    { a: "Đang tìm và lọc các đoạn liên quan…", d: found },
    { a: "Đang soạn câu trả lời…", d: "Đã soạn câu trả lời" },
    { a: "Đang kiểm tra số liệu và trích dẫn nguồn…", d: "Đã kiểm tra số liệu và trích dẫn" },
  ];
}

/** Danh sách pha: chỉ hiện pha ĐÃ XONG và đúng 1 pha ĐANG chạy, lần lượt từ trên xuống. */
export function StepList({ proc }: { proc: Proc }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {phases(proc).map((d, i) => {
        if (i > proc.step) return null;
        const done = i < proc.step;
        const labelStyle: CSSProperties = done ? { color: COLOR.accent, fontWeight: 500 } : { color: COLOR.textPrimary, fontWeight: 600 };
        return (
          <div key={i} className="animate-fadeUp" data-phase={i} data-done={done} style={{ display: "flex", alignItems: "center", gap: 10, fontSize: "13px" }}>
            {done ? (
              <span
                style={{
                  flexShrink: 0,
                  width: 19,
                  height: 19,
                  borderRadius: 9999,
                  background: COLOR.accent,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <IcCheck size={11} strokeWidth={3} style={{ color: COLOR.textOnDark }} />
              </span>
            ) : (
              <span
                className="animate-spin"
                style={{ flexShrink: 0, width: 19, height: 19, border: `2px solid ${COLOR.accentSoft}`, borderTopColor: COLOR.accent, borderRadius: "50%" }}
              />
            )}
            <span style={{ ...labelStyle, fontSize: "13px" }}>{done ? d.d : d.a}</span>
          </div>
        );
      })}
    </div>
  );
}

/** Khung "đang xử lý" khi câu trả lời chưa có chữ nào. */
export default function ProcessSteps({ proc }: { proc: Proc }) {
  return (
    <div className="animate-fadeUp" style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
      <div
        style={{
          flexShrink: 0,
          width: 32,
          height: 32,
          borderRadius: 9999,
          background: COLOR.accentSoft,
          border: `1px solid ${COLOR.border}`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          marginTop: 2,
        }}
      >
        <IcBrand size={17} style={{ color: COLOR.accent }} />
      </div>
      <div
        style={{
          minWidth: 290,
          maxWidth: "86%",
          padding: "14px 16px",
          borderRadius: "16px 16px 16px 5px",
          background: COLOR.surface,
          border: `1px solid ${COLOR.border}`,
          boxShadow: `0 6px 18px -10px ${COLOR.shadowPageSoft}`,
        }}
      >
        <div style={{ fontSize: "12.5px", fontWeight: 700, color: COLOR.textSecondary, marginBottom: 11, display: "flex", alignItems: "center", gap: 8 }}>
          <span
            className="animate-spin"
            style={{ width: 14, height: 14, border: `2px solid ${COLOR.border}`, borderTopColor: COLOR.accent, borderRadius: "50%" }}
          />
          Đang xử lý câu hỏi của bạn…
        </div>
        <StepList proc={proc} />
      </div>
    </div>
  );
}
