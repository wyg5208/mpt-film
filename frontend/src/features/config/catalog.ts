// Shared catalog mirrors for the config-group pages — constants that Main.py
// keeps on the Streamlit side (material labels, source groups, tab label keys,
// TTS service list) so the SPA renders the same structure without importing
// Streamlit code. Display labels go through t(): the synced packs carry the
// Streamlit translations, and a missing key falls back to the English text.
import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";

// Same fixed i18n keys as Main.py `_material_provider_labels`.
export const MATERIAL_PROVIDER_LABELS: Record<string, string> = {
  pexels: "Pexels",
  pixabay: "Pixabay",
  coverr: "Coverr",
  pexels_image: "Pexels Images",
  pixabay_image: "Pixabay Images",
  metaso_minimax: "Metaso MiniMax H3",
  ofox: "OFox AI Video",
  loomloom: "Shengsuan Cloud AI Video",
  volcengine_seedance: "Volcano Engine Seedance",
  infistar: "Infistar AI Video",
  jalapeno: "Jalapeno Cloud AI Video",
  wavespeed: "WaveSpeed AI Video",
  muapi: "MuAPI AI Video",
  openai_image: "OpenAI Compatible Text-to-Image",
  codex_image: "codex.image.label",
  local: "Local file",
};

export function materialLabel(id: string): string {
  return MATERIAL_PROVIDER_LABELS[id] ?? id;
}

// Same grouping/order as app/services/provider_readiness.py VIDEO_SOURCE_GROUPS.
export const VIDEO_SOURCE_GROUPS: Record<string, string[]> = {
  ai_video: [
    "metaso_minimax",
    "ofox",
    "loomloom",
    "volcengine_seedance",
    "infistar",
    "jalapeno",
    "wavespeed",
    "muapi",
  ],
  ai_image: ["openai_image", "codex_image"],
  stock_video: ["pexels", "pixabay", "coverr"],
  stock_image: ["pexels_image", "pixabay_image"],
};

// Main.py PROVIDER_TAB_LABEL_KEYS / MATERIAL_CAPABILITY_TAB_LABEL_KEYS and the
// capability-group -> provider-tab jump table.
export const PROVIDER_TAB_LABEL_KEYS = [
  "Provider Overview Tab",
  "Provider Text Tab",
  "Provider Video Tab",
  "Provider Image Tab",
  "Provider Voiceover Tab",
  "Provider Music Tab",
  "Provider Stock Search Tab",
];

export const MATERIAL_CAPABILITY_TAB_LABEL_KEYS = [
  "Capability Group AI Video",
  "Capability Group AI Image",
  "Capability Group Stock Video",
  "Capability Group Stock Image",
];

export const MATERIAL_GROUP_PROVIDER_TAB: Record<string, string> = {
  ai_video: "Provider Video Tab",
  ai_image: "Provider Image Tab",
  stock_video: "Provider Stock Search Tab",
  stock_image: "Provider Stock Search Tab",
};

// Mirror of Main.py TTS_SERVER_OPTIONS (fixed English display labels, not
// translated on the Streamlit side either).
export const TTS_SERVERS: { id: string; label: string }[] = [
  { id: "azure-tts-v1", label: "Azure TTS V1 (Edge TTS)" },
  { id: "azure-tts-v2", label: "Azure TTS V2" },
  { id: "siliconflow", label: "SiliconFlow TTS" },
  { id: "gemini-tts", label: "Google Gemini TTS" },
  { id: "mimo-tts", label: "Xiaomi MiMo TTS" },
  { id: "minimax-tts", label: "MiniMax TTS" },
  { id: "elevenlabs", label: "ElevenLabs TTS" },
  { id: "chatterbox", label: "Chatterbox TTS" },
  { id: "kokoro", label: "Kokoro TTS" },
  { id: "fish_audio", label: "Fish Audio TTS" },
  { id: "voxcpm", label: "VoxCPM TTS" },
];

// Mirror of Main.py SOCIAL_PUBLISH_PLATFORM_LABELS / SAU_PLATFORM_ORDER:
// brand names stay untranslated in every UI language.
export const SAU_PLATFORMS: { id: string; label: string }[] = [
  { id: "douyin", label: "抖音" },
  { id: "tencent", label: "视频号" },
  { id: "xiaohongshu", label: "小红书" },
  { id: "bilibili", label: "B站" },
  { id: "kuaishou", label: "快手" },
  { id: "weibo", label: "微博" },
  { id: "baijiahao", label: "百家号" },
];

export const SAU_REPO_URL = "https://github.com/dreammis/social-auto-upload";
export const UPLOAD_POST_API_KEYS_URL = "https://app.upload-post.com/api-keys";
export const UPLOAD_POST_MANAGE_USERS_URL = "https://app.upload-post.com/manage-users";

export type LlmProviderMeta = {
  provider_id: string;
  label_key: string;
  default_label: string;
  show_api_key: boolean;
  show_base_url: boolean;
  default_model: string;
  default_base_url: string;
  service_endpoints: {
    endpoint_id: string;
    default_label: string;
    label_key: string;
    base_url: string;
    api_key_url: string;
  }[];
  endpoint_selector_label_key: string | null;
  endpoint_selector_help_key: string | null;
  extra_fields: { config_suffix: string; required: boolean; default_value: string }[];
};

export function useLlmProviders() {
  return useQuery({
    queryKey: ["llm-providers"],
    queryFn: () => api.get<{ providers: LlmProviderMeta[] }>("/llm-providers"),
  });
}

export function useTtsServers() {
  return useQuery({
    queryKey: ["tts-servers"],
    queryFn: () =>
      api.get<{ servers: { id: string; label: string; available: boolean }[] }>(
        "/tts-servers"
      ),
  });
}

// t() falls back to the en pack and then to the key itself; when even the en
// pack lacks the key, prefer the registry's default label over the raw key.
export function translateOr(
  t: (key: string) => string,
  key: string,
  fallback: string
): string {
  const translated = t(key);
  return translated === key ? fallback : translated;
}

export function llmProviderLabel(
  meta: LlmProviderMeta,
  t: (key: string) => string
): string {
  return translateOr(t, meta.label_key, meta.default_label);
}
