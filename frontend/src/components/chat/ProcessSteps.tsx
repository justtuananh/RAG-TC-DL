import type { CSSProperties } from "react";
import { PROC_DEFS } from "../../services/mockEngine";
import { IcBrand, IcCheck } from "../common/icons";

export default function ProcessSteps({ step }: { step: number }) {
  return (
    <div style={{ display: "flex", gap: 10, alignItems: "flex-start", animation: "fadeUp .25s ease-out" }}>
      <div style={{ flexShrink: 0, width: 32, height: 32, borderRadius: 9999, background: "#DCFCE7", border: "1px solid #BBF7D0", display: "flex", alignItems: "center", justifyContent: "center", marginTop: 2 }}>
        <IcBrand size={17} style={{ color: "#16A34A" }} />
      </div>
      <div style={{ minWidth: 290, maxWidth: "86%", padding: "14px 16px", borderRadius: "16px 16px 16px 5px", background: "#fff", border: "1px solid #E6EAE8", boxShadow: "0 6px 18px -10px rgba(15,23,42,.18)" }}>
        <div style={{ fontSize: "12.5px", fontWeight: 700, color: "#334155", marginBottom: 11, display: "flex", alignItems: "center", gap: 8 }}>
          <span className="animate-spin" style={{ width: 14, height: 14, border: "2px solid #BBF7D0", borderTopColor: "#16A34A", borderRadius: "50%" }} />
          Đang xử lý câu hỏi của bạn…
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {PROC_DEFS.map((d, i) => {
            const done = i < step;
            const active = i === step;
            const labelStyle: CSSProperties = done
              ? { color: "#15803D", fontWeight: 500 }
              : active
                ? { color: "#0F172A", fontWeight: 600 }
                : { color: "#94A3B8", fontWeight: 500 };
            return (
              <div key={i} style={{ display: "flex", alignItems: "center", gap: 10, fontSize: "13px" }}>
                {done && (
                  <span style={{ flexShrink: 0, width: 19, height: 19, borderRadius: 9999, background: "#16A34A", display: "flex", alignItems: "center", justifyContent: "center" }}>
                    <IcCheck size={11} strokeWidth={3} style={{ color: "#fff" }} />
                  </span>
                )}
                {active && <span className="animate-spin" style={{ flexShrink: 0, width: 19, height: 19, border: "2px solid #DCFCE7", borderTopColor: "#16A34A", borderRadius: "50%" }} />}
                {i > step && <span style={{ flexShrink: 0, width: 19, height: 19, borderRadius: 9999, border: "2px solid #E2E8F0" }} />}
                <span style={{ ...labelStyle, fontSize: "13px" }}>{done ? d.d : d.a}</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
