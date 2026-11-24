import { defineConfig } from "vitest/config";

// Unit tests for pure frontend logic (migration Part 7: assembleVideoParams vitest).
export default defineConfig({
  test: {
    include: ["src/**/*.test.ts"],
    environment: "node",
  },
});
