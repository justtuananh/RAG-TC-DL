import type { Conversation } from "../../types";
import { IcTrash } from "../common/icons";

interface Props {
  conv: Conversation | null;
  onYes: () => void;
  onNo: () => void;
}

export default function ConfirmDialog({ conv, onYes, onNo }: Props) {
  if (!conv) return null;
  return (
    <div
      onClick={onNo}
      style={{ position: "fixed", inset: 0, zIndex: 80, background: "rgba(15,23,42,.55)", display: "flex", alignItems: "center", justifyContent: "center", padding: 30 }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{ background: "#fff", borderRadius: 14, boxShadow: "0 24px 60px -12px rgba(0,0,0,.5)", maxWidth: 380, width: "100%", padding: 22 }}
      >
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", textAlign: "center", gap: 12 }}>
          <div style={{ width: 48, height: 48, borderRadius: 9999, background: "#FEF2F2", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <IcTrash size={22} style={{ color: "#DC2626" }} />
          </div>
          <div>
            <div style={{ fontWeight: 700, fontSize: "16px", color: "#0F172A", marginBottom: 5 }}>Xoá hội thoại này?</div>
            <div style={{ fontSize: "13.5px", color: "#64748B", lineHeight: 1.55 }}>
              “{conv.title}” sẽ bị xoá vĩnh viễn. Hành động này không thể hoàn tác.
            </div>
          </div>
        </div>
        <div style={{ display: "flex", gap: 10, marginTop: 20 }}>
          <button
            onClick={onNo}
            className="flex-1 h-[42px] border border-slate-200 bg-white rounded-[10px] font-sans text-[14px] font-semibold text-slate-600 cursor-pointer hover:bg-slate-100"
          >
            Huỷ
          </button>
          <button
            onClick={onYes}
            className="flex-1 h-[42px] border-none bg-[#DC2626] rounded-[10px] font-sans text-[14px] font-semibold text-white cursor-pointer hover:bg-[#B91C1C]"
          >
            Xoá
          </button>
        </div>
      </div>
    </div>
  );
}
