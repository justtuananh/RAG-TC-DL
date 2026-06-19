import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8080",
        changeOrigin: true,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: (id) => {
          if (id.includes("/node_modules/react/") || id.includes("/node_modules/react-dom/")) {
            return "react-core";
          }
          if (
            id.includes("/node_modules/react-markdown/") ||
            id.includes("/node_modules/remark-math/") ||
            id.includes("/node_modules/rehype-katex/") ||
            id.includes("/node_modules/rehype-raw/")
          ) {
            return "markdown";
          }
          if (id.includes("/node_modules/katex/")) {
            return "katex";
          }
        },
      },
    },
  },
});
