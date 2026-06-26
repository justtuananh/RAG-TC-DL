import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Mock-only app: không cần backend. Proxy /api giữ lại để sau nối backend RAG thật.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://localhost:8080", changeOrigin: true },
    },
  },
});
