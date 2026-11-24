import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// Mode A (single-origin) uses relative /api/v1 via the dev proxy below;
// Mode B points VITE_API_BASE at the own-server API origin.
// VITE_API_BASE is baked in via `define` (not import.meta.env) so the orval
// mutator graph stays esbuild-cjs-evaluable for gen:api; see src/api/env.ts.
export default defineConfig(({ mode }) => ({
  plugins: [react()],
  define: {
    __API_BASE__: JSON.stringify(loadEnv(mode, process.cwd(), "").VITE_API_BASE || ""),
  },
  build: {
    // dist is the single source of truth for both Vercel and build:embedded.
    outDir: "dist",
  },
  server: {
    port: 5173,
    // changeOrigin 必须为 false：保留原始 Host 头，后端同源 Origin 防护
    // 会把代理请求视为同源（否则 Mode A 开发态的 POST 会被 403 拦截）。
    proxy: {
      "/api": { target: "http://localhost:8080", changeOrigin: false },
      "/tasks": { target: "http://localhost:8080", changeOrigin: false },
    },
  },
  // `vite preview` mirrors the same proxy so e2e can run against the built
  // dist artifact exactly like Mode A single-origin serving.
  preview: {
    port: 4173,
    proxy: {
      "/api": { target: "http://localhost:8080", changeOrigin: false },
      "/tasks": { target: "http://localhost:8080", changeOrigin: false },
    },
  },
}));
