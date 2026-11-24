// Option sets for the generation panels, transcribed from webui/Main.py so the
// React SPA mirrors the Streamlit control enumerations exactly. Labels are i18n
// keys (fallback = English source), values are the on-wire VideoParams values.
import type { VideoAspect } from "../../stores/params";

export const SCRIPT_LOCALES: string[] = [
  "ca-ES",
  "zh-CN",
  "zh-HK",
  "zh-TW",
  "de-DE",
  "en-US",
  "es-ES",
  "fr-FR",
  "id-ID",
  "it-IT",
  "ru-RU",
  "vi-VN",
  "th-TH",
  "tr-TR",
];

export const VIDEO_CONCAT_MODES = [
  { label: "Sequential", value: "sequential" },
  { label: "Random", value: "random" },
];

// VideoTransitionMode: none is sent as null (dropped by the assembler),
// the rest use the capitalized enum values from app/models/schema.py.
export const VIDEO_TRANSITION_MODES = [
  { label: "None", value: "" },
  { label: "Shuffle", value: "Shuffle" },
  { label: "FadeIn", value: "FadeIn" },
  { label: "FadeOut", value: "FadeOut" },
  { label: "SlideIn", value: "SlideIn" },
  { label: "SlideOut", value: "SlideOut" },
  { label: "ZoomIn", value: "ZoomIn" },
  { label: "ZoomOut", value: "ZoomOut" },
];

export const VIDEO_ASPECTS: { label: string; value: VideoAspect }[] = [
  { label: "Portrait (9:16)", value: "9:16" },
  { label: "Landscape (16:9)", value: "16:9" },
  { label: "Square (1:1)", value: "1:1" },
];

export const VIDEO_FIT_MODES = [
  { label: "Fill and Crop", value: "cover" },
  { label: "Fit with Black Bars", value: "contain" },
];

export const IMAGE_MOTIONS = [
  { label: "Static Image", value: "static" },
  { label: "Slow Zoom", value: "zoom" },
];

export const CLIP_DURATIONS = [2, 3, 4, 5, 6, 7, 8, 9, 10];
export const VIDEO_COUNTS = [1, 2, 3, 4, 5];
export const CONCURRENCY_OPTIONS = [1, 2, 4, 6, 8];

export const VOICE_VOLUMES = [0.6, 0.8, 1.0, 1.2, 1.5, 2.0, 3.0, 4.0, 5.0];
export const VOICE_RATES = [0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.5, 1.8, 2.0];

export const BGM_TYPES = [
  { label: "No Background Music", value: "" },
  { label: "Random Background Music", value: "random" },
  { label: "Preset Song", value: "preset" },
  { label: "Custom Background Music", value: "custom" },
  { label: "Sonilo Background Music", value: "sonilo" },
  { label: "ElevenLabs Background Music", value: "elevenlabs" },
];
export const BGM_VOLUMES = [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0];

export const SUBTITLE_POSITIONS = [
  { label: "Top", value: "top" },
  { label: "Center", value: "center" },
  { label: "Bottom", value: "bottom" },
  { label: "2/3 from Bottom", value: "two_thirds_bottom" },
  { label: "Custom", value: "custom" },
];
export const SUBTITLE_DISPLAY_MODES = [
  { label: "Sentence by Sentence", value: "sentence" },
  { label: "Single Word (Word by Word)", value: "word_by_word" },
];
export const SUBTITLE_ANIMATIONS = [
  { label: "None", value: "none" },
  { label: "Pop Up (Spring)", value: "pop_spring" },
];

// Dubbing mode is UI-only (never a VideoParams field): it decides whether the
// voice catalog, an uploaded audio file, or no voiceover drives the task,
// matching Main.py VOICE_MODE_TTS / UPLOAD / NONE.
export const VOICE_MODES = [
  { label: "Automatic Voiceover", value: "tts" },
  { label: "Upload Voiceover", value: "upload" },
  { label: "No Voiceover", value: "none" },
];
