// ChangoFilm brand theme — React counterpart of webui/brand_theme.py. Injects
// the brand CSS variables (mode / accent / field / glow / radius / motion /
// density / logo) onto :root and maps them onto the app's legacy design tokens
// (--bg/--panel/--border/--text/--muted/--primary). Values mirror the
// Streamlit palettes exactly so both UIs look the same.
import { useEffect, useState } from "react";

export type ThemeMode = "dark" | "light";
export type ThemeAccent = "magenta" | "violet" | "cyan";
export type ThemeField = "deep" | "black" | "aurora";
export type ThemeDensity = "cozy" | "compact";

export type ThemeState = {
  mode: ThemeMode;
  accent: ThemeAccent;
  field: ThemeField;
  glow: number;
  radius: number;
  motion: boolean;
  logo: boolean;
  density: ThemeDensity;
};

export const THEME_DEFAULTS: ThemeState = {
  mode: "dark",
  accent: "magenta",
  field: "deep",
  glow: 45,
  radius: 12,
  motion: true,
  logo: true,
  density: "cozy",
};

export const THEME_MODES: Record<ThemeMode, string> = {
  dark: "Theme Mode Dark",
  light: "Theme Mode Light",
};

export const THEME_ACCENTS: Record<
  ThemeAccent,
  { a: string; b: string; pale: string; deep: string; labelKey: string }
> = {
  magenta: { a: "#EC4899", b: "#8B5CF6", pale: "#F5D0FE", deep: "#C026D3", labelKey: "Accent Magenta" },
  violet: { a: "#8B5CF6", b: "#EC4899", pale: "#DDD6FE", deep: "#6D28D9", labelKey: "Accent Violet" },
  cyan: { a: "#22D3EE", b: "#0D9488", pale: "#CFFAFE", deep: "#0E7490", labelKey: "Accent Cyan" },
};

export const THEME_FIELDS: Record<ThemeField, string> = {
  deep: "Field Deep",
  black: "Field Black",
  aurora: "Field Aurora",
};

export const THEME_DENSITIES: Record<ThemeDensity, string> = {
  cozy: "Density Cozy",
  compact: "Density Compact",
};

// Same surface palettes as brand_theme.py: light keeps the violet tint and
// softens the shadows so dark hard shadows never sit on a light ground.
const DARK_PALETTE = {
  bg: "#0D0714",
  bg2: "#140B1F",
  surface: "#1B1029",
  surface2: "#241636",
  line: "#3A2452",
  line_soft: "#2A1A3C",
  ink: "#F7F2FA",
  muted: "#B49CC6",
  shadow_strong: "0 24px 64px rgba(0, 0, 0, 0.55)",
  shadow_bar: "0 8px 24px rgba(0, 0, 0, 0.45)",
  shadow_row: "0 4px 16px rgba(0, 0, 0, 0.4)",
};

const LIGHT_PALETTE = {
  bg: "#F4F1F8",
  bg2: "#FBF9FD",
  surface: "#FFFFFF",
  surface2: "#F7F4FB",
  line: "#DCD2EA",
  line_soft: "#E9E2F4",
  ink: "#1D1330",
  muted: "#6F5C88",
  shadow_strong: "0 24px 64px rgba(29, 19, 48, 0.22)",
  shadow_bar: "0 8px 24px rgba(29, 19, 48, 0.16)",
  shadow_row: "0 4px 16px rgba(29, 19, 48, 0.14)",
};

function fieldBg(field: ThemeField, a: string, b: string, mode: ThemeMode): string {
  if (mode === "light") {
    if (field === "black") return LIGHT_PALETTE.bg2;
    if (field === "aurora") {
      return (
        `radial-gradient(circle at 18% 12%, ${a}26, transparent 55%), ` +
        `radial-gradient(circle at 85% 88%, ${b}28, transparent 52%), ` +
        `radial-gradient(circle at 60% 40%, ${a}12, transparent 60%), ` +
        LIGHT_PALETTE.bg
      );
    }
    return `radial-gradient(circle at 50% 0%, ${b}1a, transparent 60%), ${LIGHT_PALETTE.bg}`;
  }
  if (field === "black") return "#000000";
  if (field === "aurora") {
    return (
      `radial-gradient(circle at 18% 12%, ${a}2e, transparent 55%), ` +
      `radial-gradient(circle at 85% 88%, ${b}30, transparent 52%), ` +
      `radial-gradient(circle at 60% 40%, ${a}14, transparent 60%), #0D0714`
    );
  }
  return `radial-gradient(circle at 50% 0%, ${b}1f, transparent 60%), #0D0714`;
}

const STORAGE_KEY = "cf_theme";
const listeners = new Set<() => void>();

function normalize(raw: unknown): ThemeState {
  const t = { ...THEME_DEFAULTS, ...(typeof raw === "object" && raw ? raw : {}) } as ThemeState;
  if (!(t.mode in THEME_MODES)) t.mode = THEME_DEFAULTS.mode;
  if (!(t.accent in THEME_ACCENTS)) t.accent = THEME_DEFAULTS.accent;
  if (!(t.field in THEME_FIELDS)) t.field = THEME_DEFAULTS.field;
  if (!(t.density in THEME_DENSITIES)) t.density = THEME_DEFAULTS.density;
  t.glow = Math.min(100, Math.max(0, Number(t.glow) || THEME_DEFAULTS.glow));
  t.radius = Math.min(20, Math.max(4, Number(t.radius) || THEME_DEFAULTS.radius));
  t.motion = Boolean(t.motion);
  t.logo = Boolean(t.logo);
  return t;
}

export function loadTheme(): ThemeState {
  try {
    return normalize(JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "null"));
  } catch {
    return { ...THEME_DEFAULTS };
  }
}

export function applyTheme(t: ThemeState): void {
  const root = document.documentElement;
  const c = THEME_ACCENTS[t.accent];
  const light = t.mode === "light";
  const p = light ? LIGHT_PALETTE : DARK_PALETTE;
  // Light mode swaps the pale accent for the deep one so links/hover/selected
  // text stay readable on white surfaces (same rule as brand_theme.py).
  const pale = light ? c.deep : c.pale;
  const play = t.motion ? "running" : "paused";
  const pad = t.density === "cozy" ? "0.5rem" : "0.2rem";
  const gap = t.density === "cozy" ? "1rem" : "0.55rem";
  const vars: Record<string, string> = {
    "color-scheme": light ? "light" : "dark",
    "--cf-accent": c.a,
    "--cf-accent-2": c.b,
    "--cf-accent-pale": pale,
    "--cf-accent-deep": c.deep,
    "--cf-bg": p.bg,
    "--cf-bg2": p.bg2,
    "--cf-surface": p.surface,
    "--cf-surface2": p.surface2,
    "--cf-line": p.line,
    "--cf-line-soft": p.line_soft,
    "--cf-ink": p.ink,
    "--cf-muted": p.muted,
    "--cf-link": pale,
    "--cf-glow": String(t.glow),
    "--cf-radius": `${t.radius}px`,
    "--cf-play": play,
    "--cf-pad-top": pad,
    "--cf-gap": gap,
    "--cf-mark-tri": light ? c.deep : "#F5D0FE",
    "--cf-shadow-strong": p.shadow_strong,
    "--cf-shadow-bar": p.shadow_bar,
    "--cf-shadow-row": p.shadow_row,
    "--cf-field-bg": fieldBg(t.field, c.a, c.b, t.mode),
    // Legacy app tokens follow the theme so existing CSS picks it up.
    "--bg": light ? p.bg2 : p.bg,
    "--panel": p.surface,
    "--border": p.line,
    "--text": p.ink,
    "--muted": p.muted,
    "--primary": c.a,
  };
  for (const [key, value] of Object.entries(vars)) root.style.setProperty(key, value);
  document.body.classList.toggle("cf-light", light);
  document.body.classList.toggle("cf-motion-off", !t.motion);
  document.body.classList.toggle("cf-density-compact", t.density === "compact");
  document.body.classList.toggle("cf-logo-hidden", !t.logo);
}

function commit(next: ThemeState): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  applyTheme(next);
  listeners.forEach((fn) => fn());
}

export function saveTheme(patch: Partial<ThemeState>): ThemeState {
  const next = normalize({ ...loadTheme(), ...patch });
  commit(next);
  return next;
}

export function resetTheme(): ThemeState {
  const next = { ...THEME_DEFAULTS };
  commit(next);
  return next;
}

export function subscribeTheme(fn: () => void): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function initTheme(): void {
  applyTheme(loadTheme());
}

// Reactive theme state + setter for the brand-theme settings tab.
export function useTheme(): [ThemeState, (patch: Partial<ThemeState>) => void] {
  const [theme, setTheme] = useState<ThemeState>(loadTheme);
  useEffect(() => subscribeTheme(() => setTheme(loadTheme())), []);
  return [theme, saveTheme];
}
