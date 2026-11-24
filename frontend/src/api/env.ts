// Single source for the API base origin. Deliberately avoids import.meta.env:
// orval evaluates the mutator import graph with esbuild in cjs format, which
// cannot parse import.meta. Vite's `define` bakes __API_BASE__ from
// VITE_API_BASE at build time (see vite.config.ts); without a bundler
// (plain node/tsc checks) it falls back to "" = same-origin relative paths.
declare const __API_BASE__: string | undefined;

export function apiBase(): string {
  return typeof __API_BASE__ === "undefined" ? "" : __API_BASE__ || "";
}
