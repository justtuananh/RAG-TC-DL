import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()], // transform JSX cho test component (.test.tsx)
  test: {
    environment: "happy-dom", // cung cấp DOM cho test component
    // Node 26 định nghĩa `localStorage` global (trả về undefined nếu thiếu
    // --localstorage-file) và che mất bản của happy-dom → setup cài lại Storage thật.
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
