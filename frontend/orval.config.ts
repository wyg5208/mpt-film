// orval codegen (migration Part 2): FastAPI OpenAPI → TanStack Query hooks.
// Single source of truth: openapi.json exported by scripts/export_openapi.py;
// generated output under src/api/generated/ must never be hand-edited.
import { defineConfig } from "orval";

export default defineConfig({
  changofilm: {
    input: {
      target: "./openapi.json",
    },
    output: {
      target: "./src/api/generated/hooks.ts",
      schemas: "./src/api/generated/models",
      client: "react-query",
      mode: "tags",
      clean: false,
      override: {
        // routes stay thin: the adapter reuses client.ts request() so Bearer
        // injection, envelope unwrap and 401→refresh remain centralized.
        mutator: {
          path: "./src/api/client.ts",
          name: "orvalRequest",
        },
      },
    },
  },
});
