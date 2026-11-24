// Settings page — faithful port of Streamlit `_render_settings_page` (设置页):
// five tabs 通用设置 / 界面设置 / 密钥备份 / 缓存管理 / 品牌主题, each mirroring
// the Streamlit body: provider category cards, hide-log + diagnostic logging,
// key backup export/restore, cache metrics with range preview + confirm-clean,
// and the nine brand-theme controls. Credential fields render the masked view
// from the API and only send a raw value when the user actually types one.
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "../../api/client";
import { useI18n } from "../../i18n";
import { navigate } from "../../app/router";
import { FilePickButton, fmt, formatSize } from "../../components/ui";
import {
  materialLabel,
  VIDEO_SOURCE_GROUPS,
  llmProviderLabel,
  useLlmProviders,
} from "../config/catalog";
import {
  THEME_ACCENTS,
  THEME_DENSITIES,
  THEME_FIELDS,
  THEME_MODES,
  resetTheme,
  useTheme,
  type ThemeAccent,
  type ThemeDensity,
  type ThemeField,
  type ThemeMode,
} from "../../theme/brandTheme";

const LOG_LEVELS = ["TRACE", "DEBUG", "INFO", "WARNING", "ERROR"];

export type MaskedCredential = { configured: boolean; masked: string };

export function isCredential(value: unknown): value is MaskedCredential {
  return (
    typeof value === "object" &&
    value !== null &&
    "masked" in value &&
    "configured" in value
  );
}

export function useSection(section: string) {
  return useQuery({
    queryKey: ["settings", section],
    queryFn: () => api.get<Record<string, unknown>>(`/settings/${section}`),
  });
}

export function useSaveSection(section: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (changes: Record<string, unknown>) =>
      api.put<{ applied: boolean; pending: boolean }>(`/settings/${section}`, changes),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["settings", section] });
      qc.invalidateQueries({ queryKey: ["settings", "overview"] });
      qc.invalidateQueries({ queryKey: ["service-platforms"] });
    },
  });
}

type FieldSpec = {
  key: string;
  labelKey: string;
  kind: "password" | "keys" | "text" | "select" | "voices";
  options?: { value: string; labelKey?: string; label?: string }[];
  placeholder?: string;
  helpKey?: string;
};

// One declarative settings field (label + masked/plain editor) shared by the
// provider/voiceover/publish forms: password & keys render the server mask and
// only send a freshly typed raw value; text saves on blur like st.text_input
// on_change; select saves immediately.
export function SettingsField({
  spec,
  value,
  onSave,
}: {
  spec: FieldSpec;
  value: unknown;
  onSave: (key: string, raw: unknown) => void;
}) {
  const { t } = useI18n();
  const [draft, setDraft] = useState<string | null>(null);
  const masked = spec.kind === "password" || spec.kind === "keys";
  const cred = masked && isCredential(value) ? value : null;

  let display: string;
  if (spec.kind === "voices") {
    display = Array.isArray(value) ? value.join(", ") : String(value ?? "");
  } else if (masked) {
    display = "";
  } else {
    display = String(value ?? "");
  }

  // Server value changed (saved or refetched) -> drop the local draft.
  useEffect(() => setDraft(null), [display]);

  const current = draft ?? display;
  // Placeholders may be i18n keys (e.g. "VoxCPM Model ID Placeholder") or raw
  // URLs; t() falls back to the key itself so both render correctly.
  const placeholder = masked
    ? cred?.configured
      ? cred.masked
      : spec.placeholder
        ? t(spec.placeholder)
        : t("paste key")
    : spec.placeholder
      ? t(spec.placeholder)
      : undefined;

  function commitText() {
    if (draft === null) return;
    setDraft(null);
    if (spec.kind === "keys") {
      const items = draft
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean);
      if (items.length) onSave(spec.key, items);
    } else if (spec.kind === "voices") {
      onSave(
        spec.key,
        draft
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean)
      );
    } else if (draft.trim() !== display.trim()) {
      onSave(spec.key, draft.trim());
    }
  }

  return (
    <label className="field" data-testid={`settings-field-${spec.key}`}>
      <span>
        {t(spec.labelKey)}
        {masked && cred?.configured && (
          <em className="muted"> {cred.masked}</em>
        )}
      </span>
      {spec.kind === "select" ? (
        <select
          value={String(value ?? "")}
          onChange={(e) => onSave(spec.key, e.target.value)}
        >
          {(spec.options ?? []).map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.labelKey ? t(opt.labelKey) : opt.label ?? opt.value}
            </option>
          ))}
        </select>
      ) : (
        <input
          type={masked ? "password" : "text"}
          autoComplete="off"
          placeholder={placeholder ?? ""}
          value={current}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={commitText}
          onKeyDown={(e) => {
            if (e.key === "Enter") commitText();
          }}
        />
      )}
      {spec.helpKey && <span className="muted">{t(spec.helpKey)}</span>}
    </label>
  );
}

function SectionEditor({ section }: { section: string }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const query = useSection(section);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [message, setMessage] = useState("");

  const save = useMutation({
    mutationFn: (changes: Record<string, unknown>) =>
      api.put<{ applied: boolean; pending: boolean }>(`/settings/${section}`, changes),
    onSuccess: (res) => {
      setDraft({});
      setMessage(
        res.pending ? t("Saved; applies after current tasks finish") : t("Saved")
      );
      qc.invalidateQueries({ queryKey: ["settings", section] });
      qc.invalidateQueries({ queryKey: ["settings", "overview"] });
    },
    onError: (err) => setMessage(err instanceof ApiError ? err.message : String(err)),
  });

  if (query.isLoading) return <p className="muted">{t("Loading…")}</p>;
  if (query.error) return <p className="error">{String(query.error.message)}</p>;

  const data = query.data as Record<string, unknown>;
  const entries = Object.entries(data).sort(([a], [b]) => a.localeCompare(b));
  const credentialKeys = entries.filter(([, v]) => isCredential(v)).map(([k]) => k);
  const dirty = credentialKeys.filter((k) => draft[k]?.trim()).length > 0;

  function submit() {
    const changes: Record<string, unknown> = {};
    for (const [key, value] of entries) {
      if (isCredential(value)) {
        const typed = draft[key]?.trim();
        if (typed) changes[key] = typed; // raw value only, never the mask
      } else if (key in draft) {
        const raw = draft[key];
        changes[key] =
          typeof value === "number"
            ? Number(raw)
            : typeof value === "boolean"
              ? raw === "true"
              : raw;
      }
    }
    if (Object.keys(changes).length) save.mutate(changes);
  }

  return (
    <div className="card section-card" data-testid={`settings-section-${section}`}>
      <h3>{t(section)}</h3>
      {entries.map(([key, value]) => {
        if (value && typeof value === "object" && !isCredential(value)) {
          return (
            <label key={key} className="field">
              <span>{key}</span>
              <textarea
                rows={2}
                value={draft[key] ?? JSON.stringify(value)}
                onChange={(e) => setDraft((d) => ({ ...d, [key]: e.target.value }))}
              />
            </label>
          );
        }
        if (isCredential(value)) {
          return (
            <label key={key} className="field">
              <span>
                {key}{" "}
                <em className="muted">
                  {value.configured ? value.masked : t("not set")}
                </em>
              </span>
              <input
                type="password"
                autoComplete="off"
                placeholder={value.configured ? t("•••• keep unchanged") : t("paste key")}
                value={draft[key] ?? ""}
                onChange={(e) => setDraft((d) => ({ ...d, [key]: e.target.value }))}
              />
            </label>
          );
        }
        return (
          <label key={key} className="field">
            <span>{key}</span>
            {typeof value === "boolean" ? (
              <select
                value={draft[key] ?? String(value)}
                onChange={(e) => setDraft((d) => ({ ...d, [key]: e.target.value }))}
              >
                <option value="true">true</option>
                <option value="false">false</option>
              </select>
            ) : (
              <input
                type={typeof value === "number" ? "number" : "text"}
                value={draft[key] ?? String(value ?? "")}
                onChange={(e) => setDraft((d) => ({ ...d, [key]: e.target.value }))}
              />
            )}
          </label>
        );
      })}
      <div className="actions">
        <button
          className="btn primary"
          onClick={submit}
          disabled={save.isPending || (!dirty && Object.keys(draft).length === 0)}
        >
          {t("Save")}
        </button>
        {message && <span className="muted">{message}</span>}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tab 1: 通用设置 — four provider category cards (Main.py
// `_render_general_settings`): select a configured provider and activate it.
// ---------------------------------------------------------------------------

type Overview = {
  llm: { configured: string[]; oauth_status: Record<string, boolean> };
  material: Record<string, string[]>;
};

const GENERAL_CARDS = [
  { section: "llm", titleKey: "LLM Provider", target: "/config/llm" },
  { section: "ai_video", titleKey: "AI Video", target: "/config/material" },
  { section: "ai_image", titleKey: "AI Image", target: "/config/material" },
  { section: "stock_video", titleKey: "Stock Video", target: "/config/material" },
] as const;

function GeneralProviderCard({
  section,
  titleKey,
  target,
  settings,
  configured,
}: {
  section: string;
  titleKey: string;
  target: string;
  settings: Record<string, unknown>;
  configured: string[];
}) {
  const { t } = useI18n();
  const providers = useLlmProviders();
  const save = useSaveSection("app");
  const isLlm = section === "llm";
  const options = configured;
  const activeRaw = isLlm ? settings.llm_provider : settings.video_source;
  const active = String(activeRaw ?? (isLlm ? "moonshot" : "pexels"));
  const inCategory = isLlm || VIDEO_SOURCE_GROUPS[section]?.includes(active);
  const label = (id: string) => {
    if (isLlm) {
      const meta = providers.data?.providers.find((m) => m.provider_id === id);
      return meta ? llmProviderLabel(meta, t) : t(`llm_provider_label.${id}`);
    }
    return t(materialLabel(id));
  };
  const [selection, setSelection] = useState<string>(() =>
    options.includes(active) ? active : (options[0] ?? "")
  );

  return (
    <div className="card general-card">
      <h3>{t(titleKey)}</h3>
      {inCategory && options.includes(active) && (
        <p className="muted">{fmt(t("Active Provider"), { provider: label(active) })}</p>
      )}
      {options.length === 0 ? (
        <>
          <p className="muted">{t("No Configured Providers")}</p>
          <button className="btn" onClick={() => navigate(target)}>
            {t("Configure Providers")}
          </button>
        </>
      ) : (
        <>
          <label className="field">
            <span>{t("Configured Providers")}</span>
            <select value={selection} onChange={(e) => setSelection(e.target.value)}>
              {options.map((id) => (
                <option key={id} value={id}>
                  {label(id)}
                </option>
              ))}
            </select>
          </label>
          <div className="row">
            <button
              className="btn primary"
              disabled={!selection || save.isPending}
              onClick={() =>
                save.mutate(
                  isLlm ? { llm_provider: selection } : { video_source: selection }
                )
              }
            >
              {t("Use Provider")}
            </button>
            <button className="btn" onClick={() => navigate(target)}>
              {t("Configure Providers")}
            </button>
          </div>
        </>
      )}
      {save.error && <p className="error">{String(save.error.message)}</p>}
    </div>
  );
}

function GeneralSettingsTab() {
  const { t } = useI18n();
  const app = useSection("app");
  const overview = useQuery({
    queryKey: ["settings", "overview"],
    queryFn: () => api.get<Overview>("/settings/overview"),
  });

  if (app.isLoading || overview.isLoading) {
    return <p className="muted">{t("Loading…")}</p>;
  }
  const settings = (app.data ?? {}) as Record<string, unknown>;
  const data = overview.data;

  return (
    <div data-testid="settings-overview">
      <h2>{t("General Providers Title")}</h2>
      <p className="muted">{t("General Providers Help")}</p>
      <div className="grid">
        {GENERAL_CARDS.map(({ section, titleKey, target }) => (
          <GeneralProviderCard
            key={section}
            section={section}
            titleKey={titleKey}
            target={target}
            settings={settings}
            configured={
              section === "llm"
                ? (data?.llm.configured ?? [])
                : (data?.material?.[section] ?? [])
            }
          />
        ))}
      </div>
      {overview.data && <OAuthHint />}
    </div>
  );
}

// Streamlit renders the OAuth status inside the overview readiness; the SPA
// keeps the sign-in cards one click away on the provider text tab.
function OAuthHint() {
  const { t } = useI18n();
  return (
    <p className="muted">
      {t("Provider Overview Help")}{" "}
      <button className="btn ghost" onClick={() => navigate("/config/llm")}>
        {t("Configure Providers")}
      </button>
    </p>
  );
}

// ---------------------------------------------------------------------------
// Tab 2: 界面设置 — hide-log switch + diagnostic logging form (Main.py
// `_render_interface_settings_body` / `_render_logging_settings`).
// ---------------------------------------------------------------------------

function InterfaceSettingsTab() {
  const { t } = useI18n();
  const ui = useSection("ui");
  const saveUi = useSaveSection("ui");
  const logging = useQuery({
    queryKey: ["settings", "logging"],
    queryFn: () => api.get<{ level: string; log_requests: boolean }>("/settings/logging"),
  });
  const [level, setLevel] = useState("INFO");
  const [trace, setTrace] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (logging.data) {
      setLevel(logging.data.level);
      setTrace(logging.data.log_requests);
    }
  }, [logging.data]);

  const apply = useMutation({
    mutationFn: () =>
      api.post<{ applied: boolean }>("/settings/logging", {
        level,
        log_requests: trace,
      }),
    onSuccess: () => {
      setMessage(t("Logging Settings Applied"));
      logging.refetch();
    },
    onError: (err) => setMessage(err instanceof ApiError ? err.message : String(err)),
  });

  const hideLog = ui.data?.hide_log === true;

  return (
    <div data-testid="settings-logging">
      <label className="check">
        <input
          type="checkbox"
          checked={hideLog}
          onChange={(e) => saveUi.mutate({ hide_log: e.target.checked })}
        />
        {t("Hide Log")}
      </label>
      <div className="expander">
        <div className="expander-head">
          <span className="expander-title">{t("Diagnostic Logging")}</span>
        </div>
        <div className="expander-body">
          <p className="muted">{t("Diagnostic Logging Help")}</p>
          <label className="field">
            <span>{t("Log Level")}</span>
            <select value={level} onChange={(e) => setLevel(e.target.value)}>
              {LOG_LEVELS.map((l) => (
                <option key={l} value={l}>
                  {l}
                </option>
              ))}
            </select>
          </label>
          <label className="check">
            <input
              type="checkbox"
              checked={trace}
              onChange={(e) => setTrace(e.target.checked)}
            />
            {t("Trace API Requests")}
          </label>
          <div className="row">
            <button className="btn" onClick={() => apply.mutate()} disabled={apply.isPending}>
              {t("Apply Logging Settings")}
            </button>
            {message && <span className="muted">{message}</span>}
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tab 3: 密钥备份 — masked export + raw restore (Main.py
// `_render_key_backup_settings`).
// ---------------------------------------------------------------------------

function KeyBackupTab() {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [message, setMessage] = useState<{ kind: "success" | "error"; text: string } | null>(
    null
  );
  const backup = useQuery({
    queryKey: ["settings", "keys-backup"],
    queryFn: () =>
      api.get<{ count: number; keys: Record<string, Record<string, unknown>> }>(
        "/settings/keys/backup"
      ),
  });
  const count = backup.data?.count ?? 0;

  function exportKeys() {
    if (!backup.data) return;
    const blob = new Blob([JSON.stringify(backup.data, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "changofilm-keys.json";
    a.click();
    URL.revokeObjectURL(url);
  }

  async function restore(file: File) {
    setMessage(null);
    try {
      const payload = JSON.parse(await file.text());
      const res = await api.post<{ restored_count: number }>(
        "/settings/keys/restore",
        payload
      );
      setMessage({
        kind: "success",
        text: fmt(t("Keys Restored"), { count: res.restored_count }),
      });
      // Same as Streamlit's full rerun: every provider form reads restored keys.
      qc.invalidateQueries();
    } catch {
      setMessage({ kind: "error", text: t("Key Restore Failed") });
    }
  }

  return (
    <div data-testid="settings-keys">
      <p className="muted">{t("Key Backup Help")}</p>
      <p className="warning">{t("Key Backup Warning")}</p>
      <p className="muted">{fmt(t("Key Backup Summary"), { count })}</p>
      <div className="row">
        <button className="btn primary" onClick={exportKeys} disabled={count === 0}>
          {t("Export Keys")}
        </button>
        <FilePickButton
          label={t("Import Keys")}
          accept="application/json"
          onPick={(file) => void restore(file)}
        />
      </div>
      {message && <p className={message.kind === "success" ? "success" : "error"}>{message.text}</p>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tab 4: 缓存管理 — metrics, range preview, confirm-clean (Main.py
// `_render_cache_management_settings`).
// ---------------------------------------------------------------------------

type CacheStats = {
  dir: string;
  file_count: number;
  total_size: number;
  oldest_mtime: number | null;
};

const CLEANUP_RANGES: { value: number | null; labelKey: string }[] = [
  { value: 30, labelKey: "Cache Older Than 30 Days" },
  { value: 7, labelKey: "Cache Older Than 7 Days" },
  { value: 90, labelKey: "Cache Older Than 90 Days" },
  { value: null, labelKey: "All Video Cache" },
];

function CacheManagementTab() {
  const { t } = useI18n();
  const [range, setRange] = useState<number | null>(30);
  const [confirmed, setConfirmed] = useState(false);
  const [message, setMessage] = useState<{ kind: "success" | "warning"; text: string } | null>(
    null
  );
  const total = useQuery({
    queryKey: ["cache", "stats", "all"],
    queryFn: () => api.get<CacheStats>("/cache/stats"),
  });
  const preview = useQuery({
    queryKey: ["cache", "stats", "preview", range],
    queryFn: () =>
      api.get<CacheStats>(range === null ? "/cache/stats" : `/cache/stats?max_age_days=${range}`),
  });

  const clean = useMutation({
    mutationFn: () =>
      api.del<{ deleted_count: number; deleted_size: number; failed_count: number }>(
        range === null ? "/cache/video" : `/cache/video?max_age_days=${range}`
      ),
    onSuccess: (res) => {
      const params = {
        count: res.deleted_count,
        size: formatSize(res.deleted_size),
        failed: res.failed_count,
      };
      setMessage({
        kind: res.failed_count ? "warning" : "success",
        text: fmt(
          t(res.failed_count ? "Cache Cleanup Completed With Failures" : "Cache Cleanup Completed"),
          params
        ),
      });
      setConfirmed(false);
      total.refetch();
      preview.refetch();
    },
    onError: (err) =>
      setMessage({ kind: "warning", text: err instanceof ApiError ? err.message : String(err) }),
  });

  async function openDirectory() {
    const dir = total.data?.dir;
    if (!dir) return;
    try {
      await navigator.clipboard.writeText(dir);
      setMessage({ kind: "success", text: t("Cache Directory Copied") });
    } catch {
      setMessage({ kind: "warning", text: dir });
    }
  }

  const oldest =
    total.data?.oldest_mtime != null
      ? new Date(total.data.oldest_mtime * 1000).toISOString().slice(0, 10)
      : "-";

  return (
    <div data-testid="settings-cache">
      <p className="muted">{t("Video Cache Directory")}</p>
      <pre className="code-block">{total.data?.dir ?? ""}</pre>
      <div className="metric-row">
        <div className="metric">
          <span className="muted">{t("Cache File Count")}</span>
          <b>{total.data?.file_count ?? "-"}</b>
        </div>
        <div className="metric">
          <span className="muted">{t("Cache Total Size")}</span>
          <b>{total.data ? formatSize(total.data.total_size) : "-"}</b>
        </div>
        <div className="metric">
          <span className="muted">{t("Oldest Cache Date")}</span>
          <b>{oldest}</b>
        </div>
      </div>
      <p className="muted">{t("Video Cache Management Help")}</p>
      <label className="field">
        <span>{t("Cache Cleanup Range")}</span>
        <select
          value={range === null ? "all" : String(range)}
          onChange={(e) => setRange(e.target.value === "all" ? null : Number(e.target.value))}
        >
          {CLEANUP_RANGES.map(({ value, labelKey }) => (
            <option key={labelKey} value={value === null ? "all" : String(value)}>
              {t(labelKey)}
            </option>
          ))}
        </select>
      </label>
      {preview.data && (
        <p className="info-note">
          {fmt(t("Cache Cleanup Preview"), {
            count: preview.data.file_count,
            size: formatSize(preview.data.total_size),
          })}
        </p>
      )}
      <label className="check">
        <input
          type="checkbox"
          checked={confirmed}
          onChange={(e) => setConfirmed(e.target.checked)}
        />
        {t("Confirm Cache Cleanup")}
      </label>
      <div className="row">
        <button
          className="btn"
          onClick={() => {
            total.refetch();
            preview.refetch();
          }}
        >
          {t("Refresh Cache Stats")}
        </button>
        <button className="btn" onClick={() => void openDirectory()}>
          {t("Open Cache Directory")}
        </button>
        <button
          className="btn primary"
          disabled={!confirmed || (preview.data?.file_count ?? 0) === 0 || clean.isPending}
          onClick={() => clean.mutate()}
        >
          {t("Clean Cache Now")}
        </button>
      </div>
      {message && (
        <p className={message.kind === "success" ? "success" : "warning"}>{message.text}</p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tab 5: 品牌主题 — the nine brand_theme.py controls wired to the shared
// theme state (localStorage cf_theme, applied on :root).
// ---------------------------------------------------------------------------

function BrandThemeTab() {
  const { t } = useI18n();
  const [theme, update] = useTheme();
  return (
    <div className="theme-panel" data-testid="settings-theme">
      <p className="muted">{t("Theme Dialog Hint")}</p>
      <div className="cf-theme-title">{t("Theme Panel Title")}</div>
      <div className="theme-grid">
        <label className="field">
          <span>{t("Theme Mode")}</span>
          <select
            value={theme.mode}
            onChange={(e) => update({ mode: e.target.value as ThemeMode })}
          >
            {Object.entries(THEME_MODES).map(([value, labelKey]) => (
              <option key={value} value={value}>
                {t(labelKey)}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>{t("Theme Accent")}</span>
          <select
            value={theme.accent}
            onChange={(e) => update({ accent: e.target.value as ThemeAccent })}
          >
            {Object.entries(THEME_ACCENTS).map(([value, spec]) => (
              <option key={value} value={value}>
                {t(spec.labelKey)}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>{t("Theme Field")}</span>
          <select
            value={theme.field}
            onChange={(e) => update({ field: e.target.value as ThemeField })}
          >
            {Object.entries(THEME_FIELDS).map(([value, labelKey]) => (
              <option key={value} value={value}>
                {t(labelKey)}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>{t("Theme Density")}</span>
          <select
            value={theme.density}
            onChange={(e) => update({ density: e.target.value as ThemeDensity })}
          >
            {Object.entries(THEME_DENSITIES).map(([value, labelKey]) => (
              <option key={value} value={value}>
                {t(labelKey)}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>
            {t("Theme Glow")} <em className="muted">{theme.glow}</em>
          </span>
          <input
            type="range"
            min={0}
            max={100}
            value={theme.glow}
            onChange={(e) => update({ glow: Number(e.target.value) })}
          />
        </label>
        <label className="field">
          <span>
            {t("Theme Radius")} <em className="muted">{theme.radius}</em>
          </span>
          <input
            type="range"
            min={4}
            max={20}
            value={theme.radius}
            onChange={(e) => update({ radius: Number(e.target.value) })}
          />
        </label>
        <label className="check">
          <input
            type="checkbox"
            checked={theme.motion}
            onChange={(e) => update({ motion: e.target.checked })}
          />
          {t("Theme Motion")}
        </label>
        <label className="check">
          <input
            type="checkbox"
            checked={theme.logo}
            onChange={(e) => update({ logo: e.target.checked })}
          />
          {t("Theme Logo")}
        </label>
      </div>
      <button className="btn" onClick={() => resetTheme()}>
        {t("Theme Reset")}
      </button>
    </div>
  );
}

const SETTINGS_TABS = [
  { key: "general", labelKey: "General Settings Tab" },
  { key: "interface", labelKey: "Interface Settings Tab" },
  { key: "keys", labelKey: "Key Backup Tab" },
  { key: "cache", labelKey: "Cache Management Tab" },
  { key: "brand", labelKey: "Brand Theme Tab" },
];

export function SettingsPage() {
  const { t } = useI18n();
  const [tab, setTab] = useState("general");
  return (
    <div className="settings-page">
      <div className="tabs" data-testid="settings-tabs">
        {SETTINGS_TABS.map(({ key, labelKey }) => (
          <button
            key={key}
            className={key === tab ? "tab active" : "tab"}
            onClick={() => setTab(key)}
          >
            {t(labelKey)}
          </button>
        ))}
      </div>
      {tab === "general" && <GeneralSettingsTab />}
      {tab === "interface" && <InterfaceSettingsTab />}
      {tab === "keys" && <KeyBackupTab />}
      {tab === "cache" && <CacheManagementTab />}
      {tab === "brand" && <BrandThemeTab />}
    </div>
  );
}

// SectionEditor + SettingsField are reused by the provider config pages
// (服务商配置) so the split-out Streamlit nav items share the same editors.
export { SectionEditor };
export type { FieldSpec };
