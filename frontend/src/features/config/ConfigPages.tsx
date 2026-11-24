// Config-group primary pages — faithful ports of the Streamlit 服务商配置 /
// 素材API / 预设库 primary pages: the seven provider tabs (总览矩阵 / 文本 /
// 视频 / 图片 / 配音 / 音乐 / 素材搜索) with three-slot chains and per-provider
// credential expanders, the four material capability tabs with source chains,
// and the preset library with save / import / export / apply / delete.
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "../../api/client";
import { useI18n } from "../../i18n";
import { navigate } from "../../app/router";
import { useParams, assembleVideoParams } from "../../stores/params";
import { OAuthCards } from "../oauth/OAuthCards";
import {
  Expander,
  FilePickButton,
  fmt,
  truncate,
  downloadJson,
} from "../../components/ui";
import {
  SectionEditor,
  SettingsField,
  useSection,
  useSaveSection,
  type FieldSpec,
} from "../settings/SettingsPage";
import {
  MATERIAL_CAPABILITY_TAB_LABEL_KEYS,
  PROVIDER_TAB_LABEL_KEYS,
  TTS_SERVERS,
  VIDEO_SOURCE_GROUPS,
  llmProviderLabel,
  materialLabel,
  translateOr,
  useLlmProviders,
  useTtsServers,
  type LlmProviderMeta,
} from "./catalog";

type Overview = {
  llm: { configured: string[]; oauth_status: Record<string, boolean> };
  material: Record<string, string[]>;
};

function useOverview() {
  return useQuery({
    queryKey: ["settings", "overview"],
    queryFn: () => api.get<Overview>("/settings/overview"),
  });
}

// ---------------------------------------------------------------------------
// Provider tab 1: 总览矩阵 (Main.py `_render_service_provider_overview`).
// ---------------------------------------------------------------------------

type PlatformGroup = {
  group: string;
  label_key: string;
  platforms: {
    platform_id: string;
    label_key: string;
    default_label: string;
    capabilities: string[];
    ready: boolean;
  }[];
};

function ProviderOverviewTab() {
  const { t } = useI18n();
  const { data, isLoading } = useQuery({
    queryKey: ["service-platforms"],
    queryFn: () => api.get<{ groups: PlatformGroup[] }>("/service-platforms"),
  });
  if (isLoading) return <p className="muted">{t("Loading…")}</p>;
  return (
    <div data-testid="provider-overview">
      <p className="muted">{t("Provider Overview Help")}</p>
      {(data?.groups ?? []).map((group) => (
        <div key={group.group} className="platform-group">
          <h3>{t(group.label_key)}</h3>
          {group.platforms.map((platform) => (
            <div className="platform-row" key={platform.platform_id}>
              <div className="platform-info">
                <strong>{translateOr(t, platform.label_key, platform.default_label)}</strong>
                {platform.capabilities.length > 0 && (
                  <span className="muted">
                    {platform.capabilities.map((c) => t(c)).join(" · ")}
                  </span>
                )}
              </div>
              <span className={platform.ready ? "badge ok" : "badge"}>
                {platform.ready
                  ? t("Provider Configured Badge")
                  : t("Provider Not Configured Badge")}
              </span>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Provider tab 2: 文本生成 — LLM 三槽链 + 当前 Provider 表单 (Main.py
// `_render_llm_chain_settings` / `_render_llm_provider_form`).
// ---------------------------------------------------------------------------

// Only keep real user overrides, never the registry defaults (same rule as
// Main.py normalize_provider_override): defaults stay unfixed in config.toml
// so registry updates flow through.
function normalizeOverride(value: string, defaultValue: string): string {
  const next = value.trim();
  return next && next !== defaultValue.trim() ? next : "";
}

function BaseUrlField({
  meta,
  selectedEndpoint,
  savedBase,
  onSave,
}: {
  meta: LlmProviderMeta;
  selectedEndpoint: LlmProviderMeta["service_endpoints"][number] | null;
  savedBase: string;
  onSave: (raw: string) => void;
}) {
  const { t } = useI18n();
  const [draft, setDraft] = useState<string | null>(null);
  useEffect(() => setDraft(null), [savedBase, selectedEndpoint?.endpoint_id]);
  const display = selectedEndpoint ? selectedEndpoint.base_url : savedBase;
  const value = draft ?? display;

  function commit() {
    if (draft === null) return;
    setDraft(null);
    if (selectedEndpoint) return; // standard region URLs are fixed
    const next = normalizeOverride(draft, meta.default_base_url);
    if (next !== savedBase) onSave(next);
  }

  return (
    <label className="field">
      <span>{t("Base Url")}</span>
      <input
        value={value}
        disabled={Boolean(selectedEndpoint)}
        placeholder={meta.default_base_url}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === "Enter") commit();
        }}
      />
    </label>
  );
}

function TestConnectionButton({ meta, modelName }: { meta: LlmProviderMeta; modelName: string }) {
  const { t } = useI18n();
  const test = useMutation({
    mutationFn: () =>
      api.post<{ ok: boolean; error: string; elapsed: number }>("/llm/test"),
  });
  return (
    <div>
      <button className="btn" onClick={() => test.mutate()} disabled={test.isPending}>
        {test.isPending ? t("Testing LLM Connection") : t("Test LLM Connection")}
      </button>
      {test.data?.ok && (
        <p className="success">
          {fmt(t("LLM Connection Test Succeeded"), {
            provider: llmProviderLabel(meta, t),
            model: modelName || "-",
            elapsed: test.data.elapsed,
          })}
        </p>
      )}
      {test.data && !test.data.ok && (
        <p className="error">
          {fmt(t("LLM Connection Test Failed"), { error: test.data.error })}
        </p>
      )}
    </div>
  );
}

function LlmProviderForm({ meta }: { meta: LlmProviderMeta }) {
  const { t } = useI18n();
  const app = useSection("app");
  const save = useSaveSection("app");
  const settings = (app.data ?? {}) as Record<string, unknown>;
  const id = meta.provider_id;
  const endpoints = meta.service_endpoints;
  const savedBase = String(settings[`${id}_base_url`] ?? "").trim();
  // Mirror Main.py select_service_endpoint: a saved standard URL wins, empty
  // config falls back to the first region, unknown URLs stay custom.
  const matched = endpoints.find(
    (e) => e.base_url.replace(/\/$/, "") === savedBase.replace(/\/$/, "")
  );
  const [endpointId, setEndpointId] = useState<string>(() => {
    if (!endpoints.length) return "custom";
    if (!savedBase) return endpoints[0].endpoint_id;
    return matched?.endpoint_id ?? "custom";
  });
  const selectedEndpoint =
    endpoints.find((e) => e.endpoint_id === endpointId) ?? null;

  const modelName = String(settings[`${id}_model_name`] ?? "").trim() || meta.default_model;

  function saveKey(key: string, raw: unknown) {
    save.mutate({ [key]: raw });
  }

  return (
    <div className="card" data-testid={`llm-form-${id}`}>
      {endpoints.length > 0 && (
        <label className="field">
          <span>{translateOr(t, meta.endpoint_selector_label_key ?? "", "API Platform")}</span>
          <select
            value={endpointId}
            onChange={(e) => {
              const nextId = e.target.value;
              setEndpointId(nextId);
              const endpoint = endpoints.find((x) => x.endpoint_id === nextId);
              if (endpoint) saveKey(`${id}_base_url`, endpoint.base_url);
            }}
          >
            {endpoints.map((endpoint) => (
              <option key={endpoint.endpoint_id} value={endpoint.endpoint_id}>
                {translateOr(t, endpoint.label_key, endpoint.default_label)}
              </option>
            ))}
            <option value="custom">{t("Custom API Endpoint")}</option>
          </select>
          {meta.endpoint_selector_help_key && (
            <span className="muted">{t(meta.endpoint_selector_help_key)}</span>
          )}
        </label>
      )}
      {meta.show_api_key && (
        <SettingsField
          spec={{ key: `${id}_api_key`, labelKey: "API Key", kind: "password" }}
          value={settings[`${id}_api_key`]}
          onSave={saveKey}
        />
      )}
      {meta.show_base_url && (
        <BaseUrlField
          meta={meta}
          selectedEndpoint={selectedEndpoint}
          savedBase={savedBase}
          onSave={(raw) => saveKey(`${id}_base_url`, raw)}
        />
      )}
      <label className="field">
        <span>{t("Model Name")}</span>
        <input
          value={modelName}
          placeholder={meta.default_model}
          onChange={(e) => saveKey(`${id}_model_name`, normalizeOverride(e.target.value, meta.default_model))}
        />
      </label>
      {meta.extra_fields.map((field) => (
        <SettingsField
          key={field.config_suffix}
          spec={{
            key: `${id}_${field.config_suffix}`,
            labelKey: "Model Name", // generic label; registry defaults below
            kind: "text",
            placeholder: field.default_value,
          }}
          value={settings[`${id}_${field.config_suffix}`]}
          onSave={saveKey}
        />
      ))}
      <TestConnectionButton meta={meta} modelName={modelName} />
    </div>
  );
}

function LlmChainTab() {
  const { t } = useI18n();
  const providers = useLlmProviders();
  const app = useSection("app");
  const save = useSaveSection("app");
  const overview = useOverview();
  const metaList = providers.data?.providers ?? [];
  const settings = (app.data ?? {}) as Record<string, unknown>;
  const ids = metaList.map((m) => m.provider_id);
  const saved = String(settings.llm_provider ?? "").toLowerCase();
  const primary = ids.includes(saved) ? saved : (ids[0] ?? "moonshot");
  const configuredLlm = new Set(overview.data?.llm.configured ?? []);
  const meta = metaList.find((m) => m.provider_id === primary);

  if (providers.isLoading || app.isLoading) {
    return <p className="muted">{t("Loading…")}</p>;
  }
  return (
    <div data-testid="provider-llm-chain">
      <label className="field">
        <span>{t("LLM Provider")}</span>
        <select
          value={primary}
          onChange={(e) => save.mutate({ llm_provider: e.target.value })}
        >
          {metaList.map((m) => (
            <option key={m.provider_id} value={m.provider_id}>
              {llmProviderLabel(m, t)}
            </option>
          ))}
        </select>
      </label>
      {[1, 2].map((slot) => {
        const key = `llm_provider_backup${slot}`;
        const savedBackup = String(settings[key] ?? "").toLowerCase();
        const value = ids.includes(savedBackup) ? savedBackup : "";
        return (
          <label className="field" key={key}>
            <span>{t(`Backup LLM Provider ${slot}`)}</span>
            <select
              value={value}
              onChange={(e) => save.mutate({ [key]: e.target.value })}
            >
              <option value="">{t("Backup Slot Disabled")}</option>
              {metaList.map((m) => (
                <option key={m.provider_id} value={m.provider_id}>
                  {llmProviderLabel(m, t) +
                    (configuredLlm.has(m.provider_id)
                      ? ""
                      : t("Provider Not Configured Suffix"))}
                </option>
              ))}
            </select>
          </label>
        );
      })}
      <p className="muted">{t("LLM Chain Help")}</p>
      {meta && <LlmProviderForm meta={meta} />}
      {["openai_codex", "openai_chatgpt", "kimi_code"].includes(primary) && (
        <OAuthCards />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Provider tabs 3/4/7 + material pages: per-provider credential expanders.
// Field specs mirror Main.py `_render_material_provider_settings`.
// ---------------------------------------------------------------------------

const MATERIAL_PROVIDER_CAPTIONS: Record<string, string> = {
  ofox: "OFox AI Video Help",
  muapi: "MuAPI AI Video Help",
  codex_image: "codex.image.help",
};

const MATERIAL_PROVIDER_FIELDS: Record<string, FieldSpec[]> = {
  pexels: [{ key: "pexels_api_keys", labelKey: "Pexels API Key", kind: "keys" }],
  pixabay: [{ key: "pixabay_api_keys", labelKey: "Pixabay API Key", kind: "keys" }],
  coverr: [{ key: "coverr_api_keys", labelKey: "Coverr API Key", kind: "keys" }],
  metaso_minimax: [
    {
      key: "metaso_minimax_api_key",
      labelKey: "Metaso MiniMax API Key",
      kind: "password",
      helpKey: "Metaso MiniMax API Key Help",
    },
    {
      key: "metaso_minimax_base_url",
      labelKey: "Metaso MiniMax Base URL",
      kind: "text",
      placeholder: "https://metaso.cn/api/minimax",
    },
    {
      key: "metaso_minimax_resolution",
      labelKey: "Metaso MiniMax Resolution",
      kind: "select",
      options: [{ value: "768P" }, { value: "2K" }],
      helpKey: "Metaso MiniMax Resolution Help",
    },
  ],
  ofox: [
    { key: "ofox_api_key", labelKey: "OFox API Key", kind: "password" },
    {
      key: "ofox_text_to_video_model",
      labelKey: "OFox Text-to-Video Model",
      kind: "text",
      placeholder: "bytedance/seedance-2.0-fast",
    },
    { key: "ofox_base_url", labelKey: "OFox Base URL", kind: "text", placeholder: "https://api.ofox.ai/v1" },
    {
      key: "ofox_provider",
      labelKey: "OFox Upstream Vendor",
      kind: "select",
      options: [
        { value: "byteplus", labelKey: "OFox Vendor BytePlus" },
        { value: "volcengine", labelKey: "OFox Vendor Volcengine" },
        { value: "", labelKey: "OFox Vendor Auto" },
      ],
      helpKey: "OFox Upstream Vendor Help",
    },
  ],
  loomloom: [
    {
      key: "loomloom_api_token",
      labelKey: "Shengsuan Cloud API Key",
      kind: "password",
      helpKey: "Shengsuan Cloud API Key Help",
    },
  ],
  volcengine_seedance: [
    {
      key: "volcengine_seedance_api_key",
      labelKey: "Volcano Engine Ark API Key",
      kind: "password",
      helpKey: "Volcano Engine Ark API Key Help",
    },
    {
      key: "volcengine_seedance_model",
      labelKey: "Volcano Engine Seedance Model",
      kind: "text",
      placeholder: "doubao-seedance-1-0-pro-250528",
    },
    {
      key: "volcengine_seedance_base_url",
      labelKey: "Volcano Engine Ark Base URL",
      kind: "text",
      placeholder: "https://ark.cn-beijing.volces.com/api/v3",
    },
  ],
  infistar: [
    {
      key: "infistar_video_api_key",
      labelKey: "Infistar Video API Key",
      kind: "password",
      helpKey: "Infistar Video Key Help",
    },
    {
      key: "infistar_video_base_url",
      labelKey: "Infistar Video Base URL",
      kind: "text",
      placeholder: "https://infistar.cc/v1",
    },
  ],
  jalapeno: [
    { key: "jalapeno_api_key", labelKey: "Jalapeno Cloud API Key", kind: "password" },
  ],
  wavespeed: [{ key: "wavespeed_api_keys", labelKey: "WaveSpeed API Key", kind: "keys" }],
  muapi: [
    { key: "muapi_api_key", labelKey: "MuAPI API Key", kind: "password", helpKey: "MuAPI API Key Help" },
    {
      key: "muapi_base_url",
      labelKey: "MuAPI Base URL",
      kind: "text",
      placeholder: "https://api.muapi.ai/api/v1",
      helpKey: "MuAPI Base URL Help",
    },
    {
      key: "muapi_video_endpoint",
      labelKey: "MuAPI Video Endpoint",
      kind: "text",
      placeholder: "seedance-lite-t2v",
      helpKey: "MuAPI Video Endpoint Help",
    },
    {
      key: "muapi_resolution",
      labelKey: "MuAPI Resolution",
      kind: "text",
      placeholder: "480p",
      helpKey: "MuAPI Resolution Help",
    },
  ],
  openai_image: [
    { key: "openai_image_base_url", labelKey: "OpenAI Image Base URL", kind: "text", placeholder: "https://api.openai.com/v1" },
    { key: "openai_image_api_keys", labelKey: "OpenAI Image API Key", kind: "keys", helpKey: "OpenAI Image API Key Help" },
    { key: "openai_image_model", labelKey: "OpenAI Image Model", kind: "text", placeholder: "gpt-image-2" },
  ],
  codex_image: [
    { key: "codex_image_model_name", labelKey: "Model Name", kind: "text" },
    { key: "codex_image_timeout", labelKey: "codex.image.timeout", kind: "text", placeholder: "300" },
  ],
};

function ProviderExpander({ provider, ready }: { provider: string; ready: boolean }) {
  const { t } = useI18n();
  const app = useSection("app");
  const save = useSaveSection("app");
  const settings = (app.data ?? {}) as Record<string, unknown>;
  const specs = MATERIAL_PROVIDER_FIELDS[provider] ?? [];
  const captionKey = MATERIAL_PROVIDER_CAPTIONS[provider];
  return (
    <Expander title={t(materialLabel(provider))} ready={ready}>
      {captionKey && <p className="muted">{t(captionKey)}</p>}
      {specs.map((spec) => (
        <SettingsField
          key={spec.key}
          spec={spec}
          value={settings[spec.key]}
          onSave={(key, raw) => save.mutate({ [key]: raw })}
        />
      ))}
    </Expander>
  );
}

function MaterialProvidersTab({ group, helpKey }: { group: string; helpKey: string }) {
  const { t } = useI18n();
  const overview = useOverview();
  const configured = new Set(Object.values(overview.data?.material ?? {}).flat());
  return (
    <div>
      <p className="muted">{t(helpKey)}</p>
      {(VIDEO_SOURCE_GROUPS[group] ?? []).map((id) => (
        <ProviderExpander key={id} provider={id} ready={configured.has(id)} />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Provider tab 5: 配音 — TTS 三槽链 + 各服务凭证 (Main.py
// `_render_voiceover_provider_settings` / `_render_tts_provider_settings`).
// ---------------------------------------------------------------------------

// section omitted -> fields live in the app section (shared keys).
const TTS_FORMS: Record<string, { section?: string; fields: FieldSpec[] }> = {
  "azure-tts-v2": {
    section: "azure",
    fields: [
      { key: "speech_region", labelKey: "Speech Region", kind: "text" },
      { key: "speech_key", labelKey: "Speech Key", kind: "password" },
    ],
  },
  siliconflow: {
    section: "siliconflow",
    fields: [{ key: "api_key", labelKey: "SiliconFlow API Key", kind: "password" }],
  },
  "gemini-tts": {
    fields: [{ key: "gemini_api_key", labelKey: "Gemini API Key", kind: "password" }],
  },
  "mimo-tts": {
    fields: [{ key: "mimo_api_key", labelKey: "MiMo API Key", kind: "password" }],
  },
  elevenlabs: {
    section: "elevenlabs",
    fields: [
      { key: "api_key", labelKey: "ElevenLabs API Key", kind: "password" },
      {
        key: "model_id",
        labelKey: "ElevenLabs Model",
        kind: "select",
        options: [
          { value: "eleven_multilingual_v2" },
          { value: "eleven_flash_v2_5" },
          { value: "eleven_v3" },
        ],
      },
    ],
  },
  fish_audio: {
    section: "fish_audio",
    fields: [
      { key: "api_key", labelKey: "Fish Audio API Key", kind: "password" },
      {
        key: "model",
        labelKey: "Fish Audio Model",
        kind: "select",
        options: [
          { value: "s2.1-pro-free" },
          { value: "s2.1-pro" },
          { value: "s2-pro" },
        ],
      },
    ],
  },
  voxcpm: {
    section: "voxcpm",
    fields: [
      { key: "api_key", labelKey: "VoxCPM API Key", kind: "password" },
      { key: "model_id", labelKey: "VoxCPM Model ID", kind: "text", placeholder: "VoxCPM Model ID Placeholder" },
      { key: "base_url", labelKey: "VoxCPM Base URL", kind: "text" },
    ],
  },
  chatterbox: {
    section: "chatterbox",
    fields: [
      { key: "base_url", labelKey: "Chatterbox Base URL", kind: "text", placeholder: "Chatterbox Base URL Placeholder" },
      { key: "api_key", labelKey: "Chatterbox API Key", kind: "password" },
      { key: "model_id", labelKey: "Chatterbox Model", kind: "text" },
      { key: "voices", labelKey: "Chatterbox Voices", kind: "voices", placeholder: "Chatterbox Voices Placeholder" },
    ],
  },
  kokoro: {
    section: "kokoro",
    fields: [
      { key: "base_url", labelKey: "Kokoro Base URL", kind: "text", placeholder: "Kokoro Base URL Placeholder" },
      { key: "api_key", labelKey: "Kokoro API Key", kind: "password" },
      { key: "model_id", labelKey: "Kokoro Model", kind: "text" },
      { key: "voices", labelKey: "Kokoro Voices", kind: "voices", placeholder: "Kokoro Voices Placeholder" },
    ],
  },
};

function TtsServerForm({ serverId }: { serverId: string }) {
  const { t } = useI18n();
  const form = TTS_FORMS[serverId];
  const sectionName = form?.section ?? "app";
  const section = useSection(sectionName);
  const save = useSaveSection(sectionName);
  const settings = (section.data ?? {}) as Record<string, unknown>;
  if (serverId === "azure-tts-v1") {
    return <p className="muted">{t("Azure Edge TTS Free Hint")}</p>;
  }
  if (serverId === "minimax-tts") {
    return <SectionEditor section="minimax_tts" />;
  }
  if (!form) return null;
  return (
    <>
      {form.fields.map((spec) => (
        <SettingsField
          key={`${sectionName}-${spec.key}`}
          spec={spec}
          value={settings[spec.key]}
          onSave={(key, raw) => save.mutate({ [key]: raw })}
        />
      ))}
      {(serverId === "voxcpm") && (
        <p className="muted">{t("VoxCPM Reference Audio Notice")}</p>
      )}
    </>
  );
}

function VoiceoverTab() {
  const { t } = useI18n();
  const ui = useSection("ui");
  const save = useSaveSection("ui");
  const servers = useTtsServers();
  const settings = (ui.data ?? {}) as Record<string, unknown>;
  const ids = TTS_SERVERS.map((s) => s.id);
  const saved = String(settings.tts_server ?? "azure-tts-v1");
  const primary = ids.includes(saved) ? saved : "azure-tts-v1";
  const availability = new Map(
    (servers.data?.servers ?? []).map((s) => [s.id, s.available])
  );
  if (ui.isLoading) return <p className="muted">{t("Loading…")}</p>;
  return (
    <div data-testid="provider-voiceover">
      <label className="field">
        <span>{t("Voiceover Service")}</span>
        <select
          value={primary}
          onChange={(e) => save.mutate({ tts_server: e.target.value })}
        >
          {TTS_SERVERS.map((s) => (
            <option key={s.id} value={s.id}>
              {s.label}
            </option>
          ))}
        </select>
      </label>
      {[1, 2].map((slot) => {
        const key = `tts_server_backup${slot}`;
        const savedBackup = String(settings[key] ?? "");
        const value = ids.includes(savedBackup) ? savedBackup : "";
        return (
          <label className="field" key={key}>
            <span>{t(`Backup Voiceover Service ${slot}`)}</span>
            <select
              value={value}
              onChange={(e) => save.mutate({ [key]: e.target.value })}
            >
              <option value="">{t("Backup Slot Disabled")}</option>
              {TTS_SERVERS.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.label}
                </option>
              ))}
            </select>
          </label>
        );
      })}
      <p className="muted">{t("TTS Chain Help")}</p>
      {TTS_SERVERS.map((server) => (
        <Expander key={server.id} title={server.label} ready={availability.get(server.id)}>
          <TtsServerForm serverId={server.id} />
        </Expander>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Provider tab 6: 音乐 — Sonilo / ElevenLabs (Main.py
// `_render_music_provider_settings`).
// ---------------------------------------------------------------------------

function MusicTab() {
  const { t } = useI18n();
  const app = useSection("app");
  const saveApp = useSaveSection("app");
  const eleven = useSection("elevenlabs");
  const saveEleven = useSaveSection("elevenlabs");
  const appSettings = (app.data ?? {}) as Record<string, unknown>;
  const elSettings = (eleven.data ?? {}) as Record<string, unknown>;
  return (
    <div data-testid="provider-music">
      <p className="muted">{t("Provider Music Tab Help")}</p>
      <div className="card">
        <h3>{t("Sonilo Background Music")}</h3>
        <SettingsField
          spec={{ key: "sonilo_api_key", labelKey: "Sonilo API Key", kind: "password" }}
          value={appSettings.sonilo_api_key}
          onSave={(key, raw) => saveApp.mutate({ [key]: raw })}
        />
      </div>
      <div className="card">
        <h3>{t("ElevenLabs Background Music")}</h3>
        <SettingsField
          spec={{ key: "elevenlabs_music_api_key", labelKey: "ElevenLabs Music API Key", kind: "password" }}
          value={elSettings.api_key}
          onSave={(_key, raw) => saveEleven.mutate({ api_key: raw })}
        />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// 服务商配置 page — seven keyed tabs (Main.py `_render_llm_settings_body`).
// ---------------------------------------------------------------------------

const PROVIDER_TABS = PROVIDER_TAB_LABEL_KEYS.map((labelKey, index) => ({
  key: ["overview", "text", "video", "image", "voiceover", "music", "stock"][index],
  labelKey,
  group: (["video", "image", "stock"] as const).includes(
    ["overview", "text", "video", "image", "voiceover", "music", "stock"][index] as never
  )
    ? ({ video: "ai_video", image: "ai_image", stock: "stock_video" } as Record<string, string>)[
        ["overview", "text", "video", "image", "voiceover", "music", "stock"][index]
      ]
    : undefined,
  helpKey:
    {
      video: "Provider Video Tab Help",
      image: "Provider Image Tab Help",
      stock: "Provider Stock Tab Help",
    }[["overview", "text", "video", "image", "voiceover", "music", "stock"][index]] ?? undefined,
}));

export function ProvidersPage() {
  const { t } = useI18n();
  const [tab, setTab] = useState("overview");
  const active = PROVIDER_TABS.find((item) => item.key === tab);
  return (
    <div className="config-page">
      <div className="tabs" data-testid="provider-tabs">
        {PROVIDER_TABS.map((item) => (
          <button
            key={item.key}
            className={item.key === tab ? "tab active" : "tab"}
            onClick={() => setTab(item.key)}
          >
            {t(item.labelKey)}
          </button>
        ))}
      </div>
      {tab === "overview" && <ProviderOverviewTab />}
      {tab === "text" && <LlmChainTab />}
      {tab === "voiceover" && <VoiceoverTab />}
      {tab === "music" && <MusicTab />}
      {active?.group && (
        <>
          <MaterialProvidersTab group={active.group} helpKey={active.helpKey!} />
          {active.group === "stock_video" && (
            <p className="muted">{t("Stock Image Keys Shared Hint")}</p>
          )}
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// 素材API page — four capability tabs with three-slot source chains (Main.py
// `_render_material_capability_tab`). No key inputs here: keys live on the
// provider page, same as Streamlit.
// ---------------------------------------------------------------------------

const MATERIAL_TABS = [
  { key: "ai_video", labelKey: "Capability Group AI Video" },
  { key: "ai_image", labelKey: "Capability Group AI Image" },
  { key: "stock_video", labelKey: "Capability Group Stock Video" },
  { key: "stock_image", labelKey: "Capability Group Stock Image" },
];

function MaterialCapabilityTab({ group }: { group: string }) {
  const { t } = useI18n();
  const app = useSection("app");
  const save = useSaveSection("app");
  const overview = useOverview();
  const providers = VIDEO_SOURCE_GROUPS[group] ?? [];
  const settings = (app.data ?? {}) as Record<string, unknown>;
  const savedSource = String(settings.video_source ?? "");
  const [primary, setPrimary] = useState(
    providers.includes(savedSource) ? savedSource : providers[0]
  );
  const configured = new Set(Object.values(overview.data?.material ?? {}).flat());
  if (app.isLoading) return <p className="muted">{t("Loading…")}</p>;
  return (
    <div data-testid={`material-tab-${group}`}>
      <label className="field">
        <span>{t("Priority Source")}</span>
        <select
          value={primary}
          onChange={(e) => {
            setPrimary(e.target.value);
            save.mutate({ video_source: e.target.value });
          }}
        >
          {providers.map((id) => (
            <option key={id} value={id}>
              {t(materialLabel(id))}
            </option>
          ))}
        </select>
      </label>
      <p className="muted">{t("Material Primary Source Help")}</p>
      {[1, 2].map((slot) => {
        const key = `video_source_backups_${group}_${slot}`;
        const savedBackup = String(settings[key] ?? "");
        const value = providers.includes(savedBackup) ? savedBackup : "";
        return (
          <label className="field" key={key}>
            <span>{t(`Backup Source ${slot}`)}</span>
            <select
              value={value}
              onChange={(e) => save.mutate({ [key]: e.target.value })}
            >
              <option value="">{t("Backup Slot Disabled")}</option>
              {providers.map((id) => (
                <option key={id} value={id}>
                  {t(materialLabel(id))}
                </option>
              ))}
            </select>
          </label>
        );
      })}
      <p className="muted">{t("Material Chain Help")}</p>
      <div className="card">
        <h3>{t("Source Status Section")}</h3>
        {providers.map((id) => {
          const ready = configured.has(id);
          return (
            <p key={id} className="source-status">
              <span className={ready ? "ok-mark" : "off-mark"}>{ready ? "✓" : "○"}</span>{" "}
              {t(materialLabel(id))} ·{" "}
              {ready
                ? t("Provider Configured Badge")
                : t("Provider Not Configured Badge")}
            </p>
          );
        })}
      </div>
      <p className="muted">{t("Material Keys In Provider Page Hint")}</p>
      <button className="btn" onClick={() => navigate("/config/llm")}>
        {t("Open Provider Settings")}
      </button>
    </div>
  );
}

export function MaterialPage() {
  const { t } = useI18n();
  const [tab, setTab] = useState(MATERIAL_TABS[0].key);
  return (
    <div className="config-page">
      <div className="tabs" data-testid="material-tabs">
        {MATERIAL_TABS.map((item) => (
          <button
            key={item.key}
            className={item.key === tab ? "tab active" : "tab"}
            onClick={() => setTab(item.key)}
          >
            {t(item.labelKey)}
          </button>
        ))}
      </div>
      <MaterialCapabilityTab group={tab} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// 预设库 page — faithful port of Main.py `_render_presets_page`: save bar,
// importer, builtin + library rows with apply / export / delete.
// ---------------------------------------------------------------------------

type Preset = {
  id: string;
  name: string;
  params: Record<string, unknown>;
  builtin?: boolean;
  saved_at?: string | null;
};

const PRESET_SCHEMA = "changofilm.settings-preset";
const PRESET_VERSION = 1;

export function PresetsConfigPage() {
  const { t } = useI18n();
  const qc = useQueryClient();
  const params = useParams();
  const [name, setName] = useState("");
  const [message, setMessage] = useState<{ kind: string; text: string } | null>(null);
  const query = useQuery({
    queryKey: ["presets"],
    queryFn: () => api.get<{ presets: Preset[] }>("/presets"),
  });
  const presets = query.data?.presets ?? [];
  const libraryCount = presets.filter((p) => !p.builtin).length;

  function show(kind: string, text: string) {
    setMessage({ kind, text });
  }

  async function savePreset() {
    if (!name.trim()) {
      show("warning", t("Preset Name Missing"));
      return;
    }
    try {
      await api.post("/presets", {
        name: name.trim(),
        params: assembleVideoParams(params),
      });
      show("success", fmt(t("Preset Saved"), { name: name.trim() }));
      setName("");
      qc.invalidateQueries({ queryKey: ["presets"] });
    } catch (err) {
      show("error", err instanceof ApiError ? err.message : t("Preset Save Failed"));
    }
  }

  async function importPreset(file: File) {
    try {
      const payload = JSON.parse(await file.text());
      const importedName =
        String(payload.name ?? file.name.replace(/\.json$/i, ""))
          .trim()
          .slice(0, 60) || t("Preset Library");
      await api.post("/presets", {
        name: importedName,
        params: payload.params ?? {},
      });
      show("success", fmt(t("Preset Import Saved"), { name: importedName }));
      qc.invalidateQueries({ queryKey: ["presets"] });
    } catch {
      show("error", t("Settings Preset Import Failed"));
    }
  }

  function apply(preset: Preset) {
    params.set(preset.params as never);
    show("success", t("Preset applied"));
  }

  function exportPreset(preset: Preset) {
    downloadJson(`changofilm-preset-${preset.id}.json`, {
      schema: PRESET_SCHEMA,
      version: PRESET_VERSION,
      name: preset.name,
      params: preset.params,
    });
  }

  function remove(preset: Preset) {
    api
      .del(`/presets/${preset.id}`)
      .then(() => qc.invalidateQueries({ queryKey: ["presets"] }))
      .catch((err) =>
        show("error", err instanceof ApiError ? err.message : String(err))
      );
  }

  return (
    <div className="config-page" data-testid="presets-page">
      <p className="muted">{t("Preset Library Help")}</p>
      <div className="row preset-save-bar">
        <input
          value={name}
          maxLength={60}
          placeholder={t("Preset Name Placeholder")}
          onChange={(e) => setName(e.target.value)}
        />
        <button className="btn primary" onClick={() => void savePreset()}>
          {t("Save Current As Preset")}
        </button>
      </div>
      {message && (
        <p className={message.kind === "success" ? "success" : message.kind === "error" ? "error" : "warning"}>
          {message.text}
        </p>
      )}
      <FilePickButton
        label={t("Import Preset To Library")}
        accept="application/json"
        onPick={(file) => void importPreset(file)}
      />
      <hr />
      {presets.map((preset) => {
        const subject = String(preset.params.video_subject ?? "");
        const captionBits = [
          subject ? truncate(subject, 30) : "",
          preset.saved_at ? preset.saved_at.replace("T", " ") : "",
          preset.builtin ? t("Builtin Preset Tag") : "",
        ].filter(Boolean);
        return (
          <div className="card preset-row" key={preset.id}>
            <strong>{truncate(preset.name, 60)}</strong>
            {captionBits.length > 0 && <p className="muted">{captionBits.join(" · ")}</p>}
            <div className="row">
              <button className="btn primary" onClick={() => apply(preset)}>
                {t("Apply Preset")}
              </button>
              <button className="btn" onClick={() => exportPreset(preset)}>
                {t("Export Preset")}
              </button>
              {!preset.builtin && (
                <button className="btn ghost" onClick={() => remove(preset)}>
                  {t("Delete Preset")}
                </button>
              )}
            </div>
          </div>
        );
      })}
      {libraryCount === 0 && <p className="muted">{t("Preset Empty")}</p>}
    </div>
  );
}
