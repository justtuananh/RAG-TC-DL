import type { ToastState } from "../../types";
import { IcAlert, IcCheck } from "./icons";
import { COLOR } from "../../theme";

export default function Toast({ toast }: { toast: ToastState | null }) {
  if (!toast) return null;
  const isError = toast.kind === "error";
  return (
    <div
      style={{
        position: "fixed",
        right: 20,
        top: 72,
        background: COLOR.sidebarBg,
        color: COLOR.textOnDark,
        padding: "10px 16px",
        borderRadius: 10,
        fontSize: "13px",
        fontWeight: 500,
        boxShadow: `0 10px 30px -8px ${COLOR.shadowToast}`,
        zIndex: 95,
        display: "flex",
        alignItems: "center",
        gap: 8,
        animation: "fadeUp .2s ease-out",
      }}
    >
      {isError ? (
        <IcAlert size={15} strokeWidth={2.5} style={{ color: COLOR.danger, flexShrink: 0 }} />
      ) : (
        <IcCheck size={15} strokeWidth={2.5} style={{ color: COLOR.successBorder, flexShrink: 0 }} />
      )}
      {toast.message}
    </div>
  );
}
