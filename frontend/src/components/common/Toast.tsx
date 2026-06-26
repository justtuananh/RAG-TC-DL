import { IcCheck } from "./icons";

export default function Toast({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <div
      style={{
        position: "fixed",
        right: 20,
        top: 72,
        background: "#0F172A",
        color: "#fff",
        padding: "10px 16px",
        borderRadius: 10,
        fontSize: "13px",
        fontWeight: 500,
        boxShadow: "0 10px 30px -8px rgba(0,0,0,.4)",
        zIndex: 95,
        display: "flex",
        alignItems: "center",
        gap: 8,
        animation: "fadeUp .2s ease-out",
      }}
    >
      <IcCheck size={15} strokeWidth={2.5} style={{ color: "#4ADE80", flexShrink: 0 }} />
      {message}
    </div>
  );
}
