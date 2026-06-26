import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()], // transform JSX cho test component (.test.tsx)
  test: {
    environment: "happy-dom", // cung cấp localStorage cho test persistence
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
