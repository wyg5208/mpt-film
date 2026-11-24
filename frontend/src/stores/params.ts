// Zustand store: the single explicit assembler for all ~44 VideoParams fields
// (migration Part 2 stores/params.ts / Part 6 "全部字段逐一映射"). assembleVideoParams()
// is the ONE place that builds the POST /videos body, replacing Streamlit's
// four-panel render-coupled assembly; the golden-payload diff test asserts
// field-for-field parity against app/models/schema.py VideoParams.
import { create } from "zustand";

export type VideoAspect = "16:9" | "9:16" | "4:3" | "3:4" | "1:1";

// Mirrors schema.py MaterialInfo: local uploads are persisted as
// {provider: "local", url, duration}; bare file names are not accepted.
export interface MaterialRef {
  provider: string;
  url: string;
  duration: number;
  source_info?: Record<string, unknown> | null;
}

export interface ParamsState {
  video_subject: string;
  video_script: string;
  video_terms: string | string[] | null;
  video_aspect: VideoAspect;
  video_fit_mode: string;
  image_motion: string;
  video_concat_mode: string;
  video_transition_mode: string | null;
  video_clip_duration: number;
  video_clip_speed: number;
  match_materials_to_script: boolean;
  video_count: number;
  video_seed: number | null;
  video_source: string | null;
  video_materials: MaterialRef[] | null;
  custom_audio_file: string | null;
  video_language: string;
  voice_name: string;
  voice_volume: number;
  voice_rate: number;
  bgm_type: string;
  bgm_file: string;
  bgm_volume: number;
  video_music_prompt: string;
  sonilo_bgm_prompt: string;
  subtitle_enabled: boolean;
  subtitle_position: string;
  subtitle_display_mode: string;
  subtitle_animation: string;
  custom_position: number;
  font_name: string;
  text_fore_color: string;
  text_background_color: string | boolean;
  rounded_subtitle_background: boolean;
  font_size: number;
  stroke_color: string;
  stroke_width: number;
  n_threads: number;
  paragraph_number: number;
  video_script_prompt: string;
  custom_system_prompt: string;
  plan_target_duration: number | null;
  plan_scene_count: number | null;
  set: (patch: Partial<ParamsState>) => void;
  reset: () => void;
}

// Defaults mirror app/models/schema.py VideoParams exactly.
export const initial: Omit<ParamsState, "set" | "reset"> = {
  video_subject: "",
  video_script: "",
  video_terms: null,
  video_aspect: "9:16",
  video_fit_mode: "cover",
  image_motion: "zoom",
  video_concat_mode: "random",
  video_transition_mode: null,
  video_clip_duration: 5,
  video_clip_speed: 1.0,
  match_materials_to_script: false,
  video_count: 1,
  video_seed: null,
  video_source: "pexels",
  video_materials: null,
  custom_audio_file: null,
  video_language: "",
  voice_name: "",
  voice_volume: 1.0,
  voice_rate: 1.0,
  bgm_type: "random",
  bgm_file: "",
  bgm_volume: 0.2,
  video_music_prompt: "",
  sonilo_bgm_prompt: "",
  subtitle_enabled: true,
  subtitle_position: "bottom",
  subtitle_display_mode: "sentence",
  subtitle_animation: "none",
  custom_position: 70.0,
  font_name: "STHeitiMedium.ttc",
  text_fore_color: "#FFFFFF",
  text_background_color: false,
  rounded_subtitle_background: false,
  font_size: 60,
  stroke_color: "#000000",
  stroke_width: 1.5,
  n_threads: 2,
  paragraph_number: 1,
  video_script_prompt: "",
  custom_system_prompt: "",
  plan_target_duration: null,
  plan_scene_count: null,
};

export const useParams = create<ParamsState>((setState) => ({
  ...initial,
  set: (patch) => setState(patch),
  reset: () => setState({ ...initial }),
}));

// The VideoParams field names this assembler knows (single source of truth for
// the golden-payload test). script_plan is pipeline-internal and bound via the
// plan endpoints, so it is intentionally excluded from manual assembly.
export const VIDEO_PARAM_FIELD_NAMES = Object.keys(initial) as (keyof Omit<
  ParamsState,
  "set" | "reset"
>)[];

// Pure assembler used by GenerateBar and the golden-payload diff test
// (migration Part 7). Emits every field explicitly; nulls mean "unset" and are
// dropped so FastAPI/pydantic defaults apply, matching Streamlit behavior of
// only writing controls the user actually configured.
export function assembleVideoParams(
  state: ParamsState
): Record<string, unknown> {
  const body: Record<string, unknown> = {};
  for (const key of VIDEO_PARAM_FIELD_NAMES) {
    const value = state[key];
    if (value === null || value === undefined) continue;
    body[key] = value;
  }
  return body;
}
