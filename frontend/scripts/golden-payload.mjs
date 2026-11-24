// Golden payload emitter (migration Part 7): bundles the REAL frontend
// assembler (src/stores/params.ts) with esbuild, assembles a default payload
// and a fully-populated sample payload, and prints them as JSON on stdout.
// test/services/test_golden_payload.py diffs this against pydantic VideoParams
// so the ~44-field assembly stays field-for-field identical to the backend contract.
import { build } from "esbuild";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const paramsTsu = resolve(here, "..", "src", "stores", "params.ts");

const result = await build({
  entryPoints: [paramsTsu],
  bundle: true,
  format: "esm",
  platform: "node",
  write: false,
});

const dir = mkdtempSync(resolve(tmpdir(), "changofilm-golden-"));
const bundlePath = resolve(dir, "params.mjs");
writeFileSync(bundlePath, result.outputFiles[0].text, "utf8");

const mod = await import(pathToFileURL(bundlePath).href);
const { assembleVideoParams, initial, VIDEO_PARAM_FIELD_NAMES } = mod;

const defaultState = { ...initial, set: (p) => p, reset: () => {} };
const sampleState = {
  ...initial,
  video_subject: "deep sea creatures",
  video_script: "a script about the abyss",
  video_terms: ["whale", "anglerfish"],
  video_aspect: "16:9",
  video_fit_mode: "contain",
  image_motion: "static",
  video_concat_mode: "sequential",
  video_transition_mode: "FadeIn",
  video_clip_duration: 7,
  video_clip_speed: 1.25,
  match_materials_to_script: true,
  video_count: 2,
  video_seed: 42,
  video_source: "coverr",
  video_materials: [
    { provider: "local", url: "changofilmmaterials/sample.mp4", duration: 12 },
  ],
  custom_audio_file: "voice/ref-1.wav",
  video_language: "zh-CN",
  voice_name: "zh-CN-XiaoxiaoNeural",
  voice_volume: 0.9,
  voice_rate: 1.1,
  bgm_type: "custom",
  bgm_file: "bgm/track.mp3",
  bgm_volume: 0.35,
  video_music_prompt: "calm piano",
  sonilo_bgm_prompt: "cinematic underscore",
  subtitle_enabled: true,
  subtitle_position: "custom",
  subtitle_display_mode: "word_by_word",
  subtitle_animation: "pop_spring",
  custom_position: 82.5,
  font_name: "STHeitiMedium.ttc",
  text_fore_color: "#F7D723",
  text_background_color: "#1A1A1A",
  rounded_subtitle_background: true,
  font_size: 48,
  stroke_color: "#000000",
  stroke_width: 2,
  n_threads: 4,
  paragraph_number: 3,
  video_script_prompt: "documentary tone",
  custom_system_prompt: "you are a scriptwriter",
  plan_target_duration: 60,
  plan_scene_count: 8,
  set: (p) => p,
  reset: () => {},
};

console.log(
  JSON.stringify({
    field_names: VIDEO_PARAM_FIELD_NAMES,
    default_payload: assembleVideoParams(defaultState),
    sample_payload: assembleVideoParams(sampleState),
  })
);
