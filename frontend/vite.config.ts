import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev và preview dùng cùng API_PORT do run.sh export; /api giữ nguyên origin
// phía trình duyệt để upload, phê duyệt công thức và streaming chat dùng chung API.
const proxy = {
  "/api": { target: `http://127.0.0.1:${process.env.API_PORT || "8080"}`, changeOrigin: true },
};

export default defineConfig({
  plugins: [react()],
  server: { port: 5173, strictPort: true, proxy },
  preview: { port: 5173, strictPort: true, proxy },
});
