import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "happy-dom", // cung cấp localStorage cho test persistence
    include: ["src/**/*.test.ts"],
  },
});
