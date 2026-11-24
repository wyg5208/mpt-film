// Reusable creation panels shared by the two Streamlit routes (快速成片 quick /
// 专业短剧 pro). Each panel writes straight into the Zustand params store; the
// panels mirror webui/Main.py `_render_script_settings` / `_render_image_settings`
// / `_render_video_settings` / `_render_audio_settings` / `_render_subtitle_settings`
// so both routes assemble one VideoParams (quick uses script, pro uses the plan).
import { useRef, useState } from "react";
import { api, ApiError } from "../../api/client";
import { useI18n } from "../../i18n";
import { navigate } from "../../app/router";
import { useParams, assembleVideoParams, type MaterialRef } from "../../stores/params";
import { setCurrentTask } from "../../app/currentTask";
import {
  BGM_TYPES,
  BGM_VOLUMES,
  CLIP_DURATIONS,
  CONCURRENCY_OPTIONS,
  IMAGE_MOTIONS,
  SCRIPT_LOCALES,
  SUBTITLE_ANIMATIONS,
  SUBTITLE_DISPLAY_MODES,
  SUBTITLE_POSITIONS,
  VIDEO_ASPECTS,
  VIDEO_CONCAT_MODES,
  VIDEO_COUNTS,
  VIDEO_FIT_MODES,
  VIDEO_TRANSITION_MODES,
  VOICE_MODES,
  VOICE_RATES,
  VOICE_VOLUMES,
} from "./options";
import { Checkbox, Field, Panel, Segmented, Select, Slider } from "./fields";
import { useBgmFiles, useFonts, useVideoSources, useVoices } from "./useCatalogs";

type ScriptResponse = { video_script?: string };
type TermsResponse = { video_terms?: string[] };

function useRun() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const fail = (err: unknown) => setError(err instanceof ApiError ? err.message : String(err));
  return { busy, error, setError, fail, run: async (fn: () => Promise<void>) => {
    setBusy(true);
    setError("");
    try {
      await fn();
    } catch (err) {
      fail(err);
    } finally {
      setBusy(false);
    }
  } };
}

// Stock image sources drive the Image panel gating (image motion + stock picker)
// and sync the params store's video_source, exactly like Main.py's shared key.
const STOCK_IMAGE_SUFFIX = "_image";

// ---------------- Script panel (quick route only) ----------------
export function ScriptPanel() {
  const { t } = useI18n();
  const params = useParams();
  const set = params.set;
  const { busy, error, setError, fail, run } = useRun();
  const [adv, setAdv] = useState(false);
  const [notice, setNotice] = useState("");

  async function genScript() {
    if (!params.video_subject.trim()) {
      setError(t("Video Subject is required"));
      return;
    }
    await run(async () => {
      const res = await api.post<ScriptResponse>("/scripts", {
        video_subject: params.video_subject,
        video_language: params.video_language,
        paragraph_number: params.paragraph_number,
        video_script_prompt: params.video_script_prompt,
        custom_system_prompt: params.custom_system_prompt,
      });
      if (res?.video_script) set({ video_script: res.video_script });
    });
  }

  async function genTerms() {
    if (!params.video_script.trim()) {
      setNotice(t("Please enter the video script first"));
      return;
    }
    await run(async () => {
      const res = await api.post<TermsResponse>("/terms", {
        video_subject: params.video_subject,
        video_script: params.video_script,
        amount: params.match_materials_to_script ? 8 : 5,
        match_materials_to_script: params.match_materials_to_script,
      });
      if (res?.video_terms) set({ video_terms: res.video_terms.join(", ") });
    });
  }

  return (
    <Panel title={t("Tab Script")}>
      <Field label="Video Subject">
        <textarea
          rows={3}
          value={params.video_subject}
          placeholder={t("What is the video about?")}
          onChange={(e) => set({ video_subject: e.target.value })}
        />
      </Field>
      <Field label="Script Language">
        <Select
          value={params.video_language}
          options={[
            { label: t("Auto Detect"), value: "" },
            ...SCRIPT_LOCALES.map((c) => ({ label: c, value: c })),
          ]}
          onChange={(v) => set({ video_language: v })}
        />
      </Field>
      <button className="btn" onClick={genScript} disabled={busy}>
        {t("Generate Script")}
      </button>
      <Field label="Video Script" help="Video Script Help">
        <textarea
          rows={6}
          value={params.video_script}
          onChange={(e) => set({ video_script: e.target.value })}
        />
      </Field>

      <button className="btn ghost" onClick={() => setAdv((v) => !v)}>
        {adv ? t("Hide") : t("Advanced Script Settings")}
      </button>
      {adv && (
        <div className="subgroup">
          <Field label="Script Paragraph Number">
            <Slider
              value={params.paragraph_number}
              min={1}
              max={10}
              onChange={(v) => set({ paragraph_number: v })}
            />
          </Field>
          <Field label="Custom Script Requirements">
            <textarea
              rows={3}
              maxLength={2000}
              value={params.video_script_prompt}
              onChange={(e) => set({ video_script_prompt: e.target.value })}
            />
          </Field>
          <Field label="Custom System Prompt">
            <textarea
              rows={4}
              maxLength={8000}
              value={params.custom_system_prompt}
              onChange={(e) => set({ custom_system_prompt: e.target.value })}
            />
          </Field>
        </div>
      )}

      <Field label="Video Keywords" help="Video Keywords Help">
        <input
          value={
            typeof params.video_terms === "string"
              ? params.video_terms
              : (params.video_terms ?? []).join(", ")
          }
          onChange={(e) => set({ video_terms: e.target.value })}
        />
      </Field>
      <button className="btn" onClick={genTerms} disabled={busy}>
        {t("Generate Video Keywords")}
      </button>
      {notice && <p className="muted">{notice}</p>}
      {error && <div className="error">{error}</div>}
    </Panel>
  );
}

// ---------------- Image panel (both routes) ----------------
export function ImagePanel() {
  const { t } = useI18n();
  const params = useParams();
  const set = params.set;
  const sources = useVideoSources();
  const { busy, error, fail, run } = useRun();
  const [engine, setEngine] = useState<string | null>(null);

  const source = String(params.video_source ?? "");
  const stockOptions = sources.groups
    .flatMap((g) => g.options)
    .filter((o) => String(o.value).endsWith(STOCK_IMAGE_SUFFIX));
  const isStock = source.endsWith(STOCK_IMAGE_SUFFIX);
  const showMotion =
    source === "local" || source === "openai_image" || source === "codex_image" || isStock;

  async function probe() {
    await run(async () => {
      // GET /comfy/probe mirrors Main.py's comfy_local.is_online() button: the
      // envelope reports {online, base_url}; never throws for an offline engine,
      // so a false here means ComfyUI really did not answer the health check.
      const res = await api.get<{ online: boolean }>("/comfy/probe");
      setEngine(res?.online ? "online" : "offline");
    });
  }

  return (
    <Panel title={t("Image Settings")}>
      <div className="panel-section">
        <h4>{t("Image Motion Section")}</h4>
        <p className="muted">{t("Image Motion Section Help")}</p>
        {showMotion ? (
          <Field label="Image Motion">
            <Select
              value={params.image_motion}
              options={IMAGE_MOTIONS.map((o) => ({ label: t(o.label), value: o.value }))}
              onChange={(v) => set({ image_motion: v })}
            />
          </Field>
        ) : (
          <p className="muted">{t("Image Motion applies to local / AI image sources only.")}</p>
        )}
      </div>

      <div className="panel-section">
        <h4>{t("Stock Image Sources Section")}</h4>
        <p className="muted">{t("Stock Image Sources Section Help")}</p>
        <Field label="Stock Image Source" help="Stock Image Source Help">
          <Select
            value={isStock ? source : stockOptions[0]?.value ?? "pexels_image"}
            options={stockOptions}
            onChange={(v) => set({ video_source: v })}
          />
        </Field>
        <p className="muted">{t("Stock Image Keys Shared Hint")}</p>
      </div>

      {source === "openai_image" && (
        <div className="panel-section">
          <h4>{t("OpenAI Image Advanced Settings")}</h4>
          <OpenAiImageFields onFail={fail} />
        </div>
      )}

      <div className="panel-section">
        <h4>{t("Local Keyframe Engine Section")}</h4>
        <p className="muted">{t("Local Keyframe Engine Help")}</p>
        <button className="btn" onClick={probe} disabled={busy}>
          {t("Local Engine Probe")}
        </button>
        <p className="muted">
          {engine === null
            ? t("Local Engine Unknown")
            : engine === "online"
              ? t("Local Engine Online")
              : t("Local Engine Offline")}
        </p>
      </div>

      {error && <div className="error">{error}</div>}
    </Panel>
  );
}

// OpenAI image advanced params persist to the app config section (not VideoParams),
// matching Main.py `_set_runtime_config("app", ...)` for these two keys.
function OpenAiImageFields({ onFail }: { onFail: (e: unknown) => void }) {
  const { t } = useI18n();
  const q = useConfigApp();
  const [size, setSize] = useState<string | null>(null);
  const [tpl, setTpl] = useState<string | null>(null);
  const curSize = size ?? String(q.data?.openai_image_size ?? "");
  const curTpl = tpl ?? String(q.data?.openai_image_prompt_template ?? "");

  async function save(patch: Record<string, string>) {
    try {
      await api.put("/settings/app", patch);
      q.refetch();
    } catch (err) {
      onFail(err);
    }
  }

  return (
    <>
      <Field label="OpenAI Image Size" help="OpenAI Image Size Help">
        <input
          value={curSize}
          placeholder="1024x1536"
          onChange={(e) => setSize(e.target.value)}
          onBlur={() => curSize !== String(q.data?.openai_image_size ?? "") && save({ openai_image_size: curSize })}
        />
      </Field>
      <Field label="OpenAI Image Prompt Template" help="OpenAI Image Prompt Template Help">
        <input
          value={curTpl}
          placeholder="cinematic photo of {term}, photorealistic"
          onChange={(e) => setTpl(e.target.value)}
          onBlur={() => curTpl !== String(q.data?.openai_image_prompt_template ?? "") && save({ openai_image_prompt_template: curTpl })}
        />
      </Field>
    </>
  );
}

// ---------------- Video panel (both routes) ----------------
export function VideoPanel() {
  const { t } = useI18n();
  const params = useParams();
  const set = params.set;
  const sources = useVideoSources();
  const { busy, error, fail, run } = useRun();
  const materialInput = useRef<HTMLInputElement>(null);

  const isLocal = params.video_source === "local";

  async function uploadMaterial(file: File) {
    await run(async () => {
      const form = new FormData();
      form.append("file", file);
      const res = await api.postForm<{ path: string; name: string }>("/uploads/material", form);
      const ref: MaterialRef = { provider: "local", url: res.path, duration: 0 };
      set({ video_materials: [...(params.video_materials ?? []), ref] });
    });
  }

  return (
    <Panel title={t("Tab Video")}>
      <Field label="Video Source">
        <select
          value={params.video_source ?? "pexels"}
          onChange={(e) => set({ video_source: e.target.value })}
        >
          {sources.groups.map((g) => (
            <optgroup key={g.group} label={t(g.group)}>
              {g.options.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </optgroup>
          ))}
        </select>
      </Field>

      <div className="two-col">
        <Field label="Video Ratio">
          <Select
            value={params.video_aspect}
            options={VIDEO_ASPECTS.map((a) => ({ label: t(a.label), value: a.value }))}
            onChange={(v) => set({ video_aspect: v as typeof params.video_aspect })}
          />
        </Field>
        <Field label="Video Fit Mode">
          <Select
            value={params.video_fit_mode}
            options={VIDEO_FIT_MODES.map((o) => ({ label: t(o.label), value: o.value }))}
            onChange={(v) => set({ video_fit_mode: v })}
          />
        </Field>
      </div>

      <div className="two-col">
        <Field label="Video Concat Mode">
          <Select
            value={params.video_concat_mode}
            disabled={params.match_materials_to_script}
            options={VIDEO_CONCAT_MODES.map((o) => ({ label: t(o.label), value: o.value }))}
            onChange={(v) => set({ video_concat_mode: v })}
          />
        </Field>
        <Field label="Video Transition Mode">
          <Select
            value={params.video_transition_mode ?? ""}
            options={VIDEO_TRANSITION_MODES.map((o) => ({ label: t(o.label), value: o.value }))}
            onChange={(v) => set({ video_transition_mode: v || null })}
          />
        </Field>
      </div>

      <Checkbox
        label="Match Materials to Script Order"
        checked={params.match_materials_to_script}
        onChange={(c) => set({ match_materials_to_script: c })}
      />

      <div className="two-col">
        <Field label="Clip Duration">
          <Select
            value={params.video_clip_duration}
            options={CLIP_DURATIONS.map((d) => ({ label: `${d}s`, value: d }))}
            onChange={(v) => set({ video_clip_duration: Number(v) })}
          />
        </Field>
        <Field label="Clip Speed">
          <Slider
            value={params.video_clip_speed}
            min={0.5}
            max={2}
            step={0.05}
            suffix="x"
            onChange={(v) => set({ video_clip_speed: v })}
          />
        </Field>
      </div>

      <div className="two-col">
        <Field label="Number of Videos">
          <Select
            value={params.video_count}
            options={VIDEO_COUNTS.map((c) => ({ label: String(c), value: c }))}
            onChange={(v) => set({ video_count: Number(v) })}
          />
        </Field>
        <Field label="Video Seed" help="Video Seed Help">
          <input
            value={params.video_seed ?? ""}
            placeholder={t("0-4294967295 (optional)")}
            onChange={(e) => {
              const raw = e.target.value.trim();
              set({ video_seed: raw === "" ? null : Number(raw) });
            }}
          />
        </Field>
      </div>

      <Field label="Rendering Threads">
        <Select
          value={params.n_threads}
          options={CONCURRENCY_OPTIONS.map((c) => ({ label: String(c), value: c }))}
          onChange={(v) => set({ n_threads: Number(v) })}
        />
      </Field>

      {isLocal && (
        <div className="subgroup">
          <input
            ref={materialInput}
            type="file"
            accept="video/*,image/*"
            hidden
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) uploadMaterial(f);
            }}
          />
          <button className="btn" onClick={() => materialInput.current?.click()} disabled={busy}>
            {t("Upload Local Files")}
          </button>
          <ul className="chip-list">
            {(params.video_materials ?? []).map((m, i) => (
              <li key={i}>
                <span className="mono">{m.url.split(/[\\/]/).pop()}</span>
                <button
                  className="btn ghost"
                  onClick={() =>
                    set({
                      video_materials: (params.video_materials ?? []).filter((_, j) => j !== i),
                    })
                  }
                >
                  {t("Remove")}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {error && <div className="error">{error}</div>}
    </Panel>
  );
}

// ---------------- Audio panel (both routes) ----------------
export function AudioPanel() {
  const { t } = useI18n();
  const params = useParams();
  const set = params.set;
  const voices = useVoices();
  const bgms = useBgmFiles();
  const { busy, error, fail, run } = useRun();
  const [voiceMode, setVoiceMode] = useState("tts");
  const audioInput = useRef<HTMLInputElement>(null);
  const bgmInput = useRef<HTMLInputElement>(null);

  async function uploadAudio(file: File) {
    await run(async () => {
      const form = new FormData();
      form.append("file", file);
      const res = await api.postForm<{ path: string }>("/uploads/voice-reference", form);
      set({ custom_audio_file: res.path });
    });
  }

  async function uploadBgm(file: File) {
    await run(async () => {
      const form = new FormData();
      form.append("file", file);
      const res = await api.postForm<{ file: string }>("/musics", form);
      set({ bgm_file: res.file });
    });
  }

  return (
    <Panel title={t("Tab Audio")}>
      <Segmented
        value={voiceMode}
        options={VOICE_MODES}
        onChange={(mode) => {
          setVoiceMode(mode);
          if (mode === "none") set({ voice_name: "", custom_audio_file: null });
          if (mode === "tts") set({ custom_audio_file: null });
          if (mode === "upload") set({ voice_name: "" });
        }}
      />

      {voiceMode === "tts" && (
        <Field label="Voiceover Voice">
          <Select
            value={params.voice_name}
            disabled={voices.isLoading}
            options={voices.options}
            onChange={(v) => set({ voice_name: v })}
          />
        </Field>
      )}

      {voiceMode === "upload" && (
        <div className="subgroup">
          <input
            ref={audioInput}
            type="file"
            accept="audio/*"
            hidden
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) uploadAudio(f);
            }}
          />
          <button className="btn" onClick={() => audioInput.current?.click()} disabled={busy}>
            {t("Upload Voiceover File")}
          </button>
          {params.custom_audio_file && (
            <p className="muted mono">{params.custom_audio_file.split(/[\\/]/).pop()}</p>
          )}
        </div>
      )}

      {voiceMode !== "none" && (
        <div className="two-col">
          <Field label="Voiceover Volume">
            <Select
              value={params.voice_volume}
              options={VOICE_VOLUMES.map((v) => ({ label: `${Math.round(v * 100)}%`, value: v }))}
              onChange={(v) => set({ voice_volume: Number(v) })}
            />
          </Field>
          <Field label="Voiceover Speed">
            <Select
              value={params.voice_rate}
              disabled={voiceMode !== "tts"}
              options={VOICE_RATES.map((v) => ({ label: `${v}x`, value: v }))}
              onChange={(v) => set({ voice_rate: Number(v) })}
            />
          </Field>
        </div>
      )}

      <Field label="Background Music Source">
        <Select
          value={params.bgm_type}
          options={BGM_TYPES.map((o) => ({ label: t(o.label), value: o.value }))}
          onChange={(v) => set({ bgm_type: v, bgm_file: "" })}
        />
      </Field>
      <Field label="Background Music Volume">
        <Select
          value={params.bgm_volume}
          disabled={!params.bgm_type}
          options={BGM_VOLUMES.map((v) => ({ label: `${Math.round(v * 100)}%`, value: v }))}
          onChange={(v) => set({ bgm_volume: Number(v) })}
        />
      </Field>
      {params.bgm_type === "preset" && (
        <Field label="Preset Song">
          <Select
            value={params.bgm_file}
            disabled={bgms.isLoading}
            options={bgms.options}
            onChange={(v) => set({ bgm_file: v })}
          />
        </Field>
      )}
      {params.bgm_type === "custom" && (
        <div className="subgroup">
          <input
            ref={bgmInput}
            type="file"
            accept="audio/*"
            hidden
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) uploadBgm(f);
            }}
          />
          <button className="btn" onClick={() => bgmInput.current?.click()} disabled={busy}>
            {t("Upload Background Music")}
          </button>
          {params.bgm_file && <p className="muted mono">{params.bgm_file}</p>}
        </div>
      )}
      {(params.bgm_type === "sonilo" || params.bgm_type === "elevenlabs") && (
        <Field label="Music Prompt">
          <input
            value={params.video_music_prompt}
            maxLength={2000}
            onChange={(e) => set({ video_music_prompt: e.target.value })}
          />
        </Field>
      )}

      {error && <div className="error">{error}</div>}
    </Panel>
  );
}

// ---------------- Subtitle panel (both routes) ----------------
export function SubtitlePanel() {
  const { t } = useI18n();
  const params = useParams();
  const set = params.set;
  const fonts = useFonts();

  const subtitleOn = params.subtitle_enabled;
  const bgOn = typeof params.text_background_color === "string";

  return (
    <Panel title={t("Tab Subtitle")}>
      <Checkbox
        label="Enable Subtitles"
        checked={params.subtitle_enabled}
        onChange={(c) => set({ subtitle_enabled: c })}
      />
      <Field label="Font">
        <Select
          value={params.font_name}
          disabled={!subtitleOn}
          options={fonts.options}
          onChange={(v) => set({ font_name: v })}
        />
      </Field>
      <div className="two-col">
        <Field label="Position">
          <Select
            value={params.subtitle_position}
            disabled={!subtitleOn}
            options={SUBTITLE_POSITIONS.map((o) => ({ label: t(o.label), value: o.value }))}
            onChange={(v) => set({ subtitle_position: v })}
          />
        </Field>
        <Field label="Display Mode">
          <Select
            value={params.subtitle_display_mode}
            disabled={!subtitleOn}
            options={SUBTITLE_DISPLAY_MODES.map((o) => ({ label: t(o.label), value: o.value }))}
            onChange={(v) => set({ subtitle_display_mode: v })}
          />
        </Field>
      </div>
      <div className="two-col">
        <Field label="Subtitle Animation">
          <Select
            value={params.subtitle_animation}
            disabled={!subtitleOn}
            options={SUBTITLE_ANIMATIONS.map((o) => ({ label: t(o.label), value: o.value }))}
            onChange={(v) => set({ subtitle_animation: v })}
          />
        </Field>
        {params.subtitle_position === "custom" ? (
          <Field label="Custom Position (% from top)">
            <input
              type="number"
              min={0}
              max={100}
              disabled={!subtitleOn}
              value={params.custom_position}
              onChange={(e) => set({ custom_position: Number(e.target.value) })}
            />
          </Field>
        ) : (
          <Field label="Font Size">
            <Slider
              value={params.font_size}
              min={30}
              max={100}
              disabled={!subtitleOn}
              onChange={(v) => set({ font_size: v })}
            />
          </Field>
        )}
      </div>
      {params.subtitle_position === "custom" && (
        <Field label="Font Size">
          <Slider
            value={params.font_size}
            min={30}
            max={100}
            disabled={!subtitleOn}
            onChange={(v) => set({ font_size: v })}
          />
        </Field>
      )}

      <div className="two-col">
        <Field label="Font Color">
          <input
            type="color"
            disabled={!subtitleOn}
            value={params.text_fore_color}
            onChange={(e) => set({ text_fore_color: e.target.value })}
          />
        </Field>
        <Field label="Stroke Color">
          <input
            type="color"
            disabled={!subtitleOn}
            value={params.stroke_color}
            onChange={(e) => set({ stroke_color: e.target.value })}
          />
        </Field>
      </div>
      <Field label="Stroke Width">
        <Slider
          value={params.stroke_width}
          min={0}
          max={10}
          step={0.5}
          disabled={!subtitleOn}
          onChange={(v) => set({ stroke_width: v })}
        />
      </Field>

      <Checkbox
        label="Enable Subtitle Background"
        checked={bgOn}
        disabled={!subtitleOn}
        onChange={(c) =>
          set({
            text_background_color: c ? "#000000" : false,
            rounded_subtitle_background: c ? params.rounded_subtitle_background : false,
          })
        }
      />
      {bgOn && (
        <div className="two-col">
          <Field label="Subtitle Background Color">
            <input
              type="color"
              value={params.text_background_color as string}
              onChange={(e) => set({ text_background_color: e.target.value })}
            />
          </Field>
          <Checkbox
            label="Rounded Subtitle Background"
            checked={params.rounded_subtitle_background}
            onChange={(c) => set({ rounded_subtitle_background: c })}
          />
        </div>
      )}
    </Panel>
  );
}

// ---------------- Generate bar (bottom action bar) ----------------
type VideoResponse = { task_id?: string; data?: { task_id?: string } };

export function GenerateBar() {
  const { t } = useI18n();
  const params = useParams();
  const { busy, error, run } = useRun();

  async function submit() {
    await run(async () => {
      const body = assembleVideoParams(params);
      const data = await api.post<VideoResponse>("/videos", body);
      const taskId = data?.task_id || data?.data?.task_id;
      if (!taskId) throw new Error("no task id returned");
      setCurrentTask(taskId);
      navigate(`/jobs/${taskId}`);
    });
  }

  return (
    <div className="generate-bar">
      {error && <div className="error">{error}</div>}
      <button
        className="btn primary"
        onClick={submit}
        disabled={busy || !params.video_subject.trim()}
      >
        {busy ? t("Submitting…") : t("Generate Video")}
      </button>
    </div>
  );
}

// Small helper: read the app config section for the OpenAI image advanced fields.
import { useQuery } from "@tanstack/react-query";
function useConfigApp() {
  return useQuery({
    queryKey: ["settings", "app"],
    queryFn: () => api.get<Record<string, unknown>>("/settings/app"),
  });
}
