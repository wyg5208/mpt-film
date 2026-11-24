// 专业短剧 (pro route) Wizard + Script Plan tabs. A functional port of Main.py
// `_render_wizard_page` / `_render_plan_page`. The wizard is the series-level
// entry: story idea → genre/episode plan + character sheet → POST /wizard/generate
// creates the series, the first-episode plan draft and the ep1 binding, then the
// page jumps to the plan tab with that draft selected (onPlanCreated). The plan
// tab is the pro route's main page: draft picker, AI generate/import/export,
// confirm / confirm-and-generate, plan settings and per-scene editing — every
// edit falls back to draft + revision++ on the server (plans.py), matching
// Main.py `_plan_mutate`. The local-engine dashboard is rendered above both
// tabs by ProPage when the tab is active (_pro_tab_active parity).
import { useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "../../api/client";
import { useI18n } from "../../i18n";
import { navigate } from "../../app/router";
import { setCurrentTask } from "../../app/currentTask";
import { Field, Panel, Select } from "./fields";
import { downloadJson, Expander, FilePickButton } from "../../components/ui";

type PlanTask = {
  task_id: string;
  state: number;
  progress?: number;
  video_subject?: string;
};

// Main.py WIZARD_GENRES：值与后端 WIZARD_GENRES 一致，标签走 i18n。
const WIZARD_GENRES = [
  ["urban_revenge", "Genre Urban Revenge"],
  ["period_romance", "Genre Period Romance"],
  ["suspense", "Genre Suspense"],
  ["healing", "Genre Healing"],
  ["scifi", "Genre Scifi"],
  ["custom", "Genre Custom"],
] as const;

type WizardCharacter = {
  name: string;
  voice_name: string;
  appearance_prompt: string;
};

const PLAN_ENGINE_OPTIONS = ["stock", "local_fl2v", "local_i2v"] as const;
const PLAN_ENGINE_LABEL_KEYS: Record<string, string> = {
  stock: "Plan Engine Stock",
  local_fl2v: "Plan Engine Local FL2V",
  local_i2v: "Plan Engine Local I2V",
  cloud_ai: "Plan Engine Cloud AI",
};
const PLAN_TRANSITION_OPTIONS = [
  "none",
  "fade",
  "slide",
  "zoom",
  "match_cut",
] as const;
const PLAN_TRANSITION_LABEL_KEYS: Record<string, string> = {
  none: "Transition None",
  fade: "Transition Fade",
  slide: "Transition Slide",
  zoom: "Transition Zoom",
  match_cut: "Transition Match Cut",
};

type PlanScene = {
  id: string;
  order: number;
  locked: boolean;
  narration: string;
  est_duration: number;
  visual: string;
  keywords: string[];
  engine: string;
  transition_to_next: string;
  keyframe?: { shared_with_prev?: boolean };
};

type PlanPayload = {
  revision: number;
  status: "draft" | "confirmed";
  title: string;
  logline: string;
  target_duration: number;
  aspect: string;
  quality_tier: "draft" | "final";
  voice: { name: string; rate: number };
  style: { tone: string; palette: string; camera: string };
  scenes: PlanScene[];
};

type PlanDetail = {
  plan: PlanPayload;
  estimated_duration: number;
  duration_warnings: { message: string }[];
};

type PlanSummary = {
  id: string;
  title: string;
  status: string;
  revision: number;
  scenes: number;
};

export function WizardPanel({
  onPlanCreated,
}: {
  onPlanCreated: (planId: string) => void;
}) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [idea, setIdea] = useState("");
  const [genre, setGenre] = useState("urban_revenge");
  const [duration, setDuration] = useState(60);
  const [count, setCount] = useState(3);
  const [characters, setCharacters] = useState<WizardCharacter[]>([
    { name: "", voice_name: "", appearance_prompt: "" },
  ]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");

  function updateCharacter(index: number, patch: Partial<WizardCharacter>) {
    setCharacters((rows) =>
      rows.map((row, i) => (i === index ? { ...row, ...patch } : row))
    );
  }

  async function generate() {
    if (!idea.trim()) {
      setError(t("Wizard Idea Required"));
      return;
    }
    setBusy(true);
    setError("");
    try {
      const res = await api.post<PlanDetail & { series_id: string; plan_id: string }>(
        "/wizard/generate",
        {
          story_idea: idea.trim(),
          genre,
          episode_duration: duration,
          episode_count: count,
          characters: characters.filter((c) => c.name.trim()),
        }
      );
      qc.setQueryData(["plan", res.plan_id], {
        plan: res.plan,
        estimated_duration: res.estimated_duration,
        duration_warnings: res.duration_warnings,
      });
      qc.invalidateQueries({ queryKey: ["plans"] });
      qc.invalidateQueries({ queryKey: ["series"] });
      setToast(t("Wizard Created"));
      window.setTimeout(() => setToast(""), 2600);
      onPlanCreated(res.plan_id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel title={t("Creation Wizard")}>
      <p className="muted">{t("Wizard Intro")}</p>
      {toast && <div className="toast">{toast}</div>}
      {error && <div className="error">{error}</div>}

      <div className="wizard-section">{t("Wizard Section Idea")}</div>
      <Field label="Wizard Story Idea">
        <textarea
          rows={3}
          value={idea}
          placeholder={t("Wizard Story Idea Placeholder")}
          onChange={(e) => setIdea(e.target.value)}
        />
      </Field>
      <div className="wizard-idea-row">
        <Field label="Wizard Genre">
          <Select
            value={genre}
            options={WIZARD_GENRES.map(([value, labelKey]) => ({
              value,
              label: t(labelKey),
            }))}
            onChange={setGenre}
          />
        </Field>
        <Field label="Wizard Episode Duration">
          <input
            type="number"
            min={30}
            max={300}
            step={10}
            value={duration}
            onChange={(e) => setDuration(Number(e.target.value))}
          />
        </Field>
        <Field label="Wizard Episode Count">
          <input
            type="number"
            min={1}
            max={12}
            step={1}
            value={count}
            onChange={(e) => setCount(Number(e.target.value))}
          />
        </Field>
      </div>

      <div className="wizard-section">{t("Wizard Section Characters")}</div>
      <p className="muted">{t("Wizard Characters Help")}</p>
      {characters.map((character, index) => (
        <div className="wizard-char-row" key={index}>
          <input
            value={character.name}
            placeholder={t("Wizard Character Name")}
            onChange={(e) => updateCharacter(index, { name: e.target.value })}
          />
          <input
            value={character.voice_name}
            placeholder={t("Wizard Character Voice")}
            title="zh-CN-XiaoxiaoNeural / zh-CN-YunxiNeural"
            onChange={(e) => updateCharacter(index, { voice_name: e.target.value })}
          />
          <input
            value={character.appearance_prompt}
            placeholder={t("Wizard Character Appearance")}
            onChange={(e) =>
              updateCharacter(index, { appearance_prompt: e.target.value })
            }
          />
          <button
            type="button"
            className="icon-btn"
            disabled={characters.length <= 1}
            title={t("Plan Scene Delete")}
            onClick={() =>
              setCharacters((rows) => rows.filter((_, i) => i !== index))
            }
          >
            🗑
          </button>
        </div>
      ))}
      <button
        type="button"
        className="btn ghost"
        onClick={() =>
          setCharacters((rows) => [
            ...rows,
            { name: "", voice_name: "", appearance_prompt: "" },
          ])
        }
      >
        + {t("Wizard Character Name")}
      </button>

      <div className="wizard-section">{t("Wizard Section Generate")}</div>
      <button className="btn primary" onClick={generate} disabled={busy}>
        {busy ? t("Wizard Generating") : t("Wizard Generate")}
      </button>
    </Panel>
  );
}

// Main.py `_render_local_engine_dashboard`: three readiness dots + the
// one-click local bundle preset (writer engine → ollama). Rendered above the
// wizard/plan tabs by ProPage when the tab is active.
export function LocalEngineDashboard() {
  const { t } = useI18n();
  const qc = useQueryClient();
  const { data } = useQuery({
    queryKey: ["engines", "status"],
    queryFn: () =>
      api.get<{ engines: Record<string, { online?: boolean }> }>("/engines/status"),
    refetchInterval: 15000,
    staleTime: 15000,
  });
  const [busy, setBusy] = useState(false);
  const engines = data?.engines ?? {};

  async function applyBundle() {
    setBusy(true);
    try {
      await api.post("/engines/local-bundle");
      qc.invalidateQueries({ queryKey: ["settings"] });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="engine-dashboard">
      {(
        [
          ["comfyui", "Local Video Engine"],
          ["acestep", "Local Music Engine"],
          ["ollama", "Local Writer Engine"],
        ] as const
      ).map(([key, labelKey]) => {
        const online = Boolean(engines[key]?.online);
        return (
          <div key={key} className="engine-cell">
            <strong>{online ? "🟢" : "⚪"} {t(labelKey)}</strong>
            <span className="muted">{t(online ? "Engine Online" : "Engine Offline")}</span>
          </div>
        );
      })}
      <button
        className="btn"
        onClick={applyBundle}
        disabled={busy}
        title={t("Engine Status Help")}
      >
        ⚡ {t("Local Bundle Preset")}
      </button>
    </div>
  );
}

// Settings expander body: local-state inputs remounted per revision (mirrors
// `_plan_reset_widgets`), committing on blur via PATCH /plans/{id}/settings.
function PlanSettingsEditor({
  plan,
  onCommit,
  busy,
}: {
  plan: PlanPayload;
  onCommit: (path: string, value: string | number) => void;
  busy: boolean;
}) {
  const [title, setTitle] = useState(plan.title);
  const [logline, setLogline] = useState(plan.logline);
  const [voiceName, setVoiceName] = useState(plan.voice.name);
  const [voiceRate, setVoiceRate] = useState(String(plan.voice.rate));
  const [tone, setTone] = useState(plan.style.tone);
  const [palette, setPalette] = useState(plan.style.palette);
  const [camera, setCamera] = useState(plan.style.camera);

  return (
    <div className="plan-settings-grid">
      <Field label="Plan Title Field">
        <input value={title} onChange={(e) => setTitle(e.target.value)}
          onBlur={() => title !== plan.title && onCommit("title", title)} disabled={busy} />
      </Field>
      <Field label="Plan Style Tone">
        <input value={tone} onChange={(e) => setTone(e.target.value)}
          onBlur={() => tone !== plan.style.tone && onCommit("style.tone", tone)} disabled={busy} />
      </Field>
      <Field label="Plan Logline">
        <input value={logline} onChange={(e) => setLogline(e.target.value)}
          onBlur={() => logline !== plan.logline && onCommit("logline", logline)} disabled={busy} />
      </Field>
      <Field label="Plan Style Palette">
        <input value={palette} onChange={(e) => setPalette(e.target.value)}
          onBlur={() => palette !== plan.style.palette && onCommit("style.palette", palette)} disabled={busy} />
      </Field>
      <Field label="Plan Voice Name">
        <input value={voiceName} onChange={(e) => setVoiceName(e.target.value)}
          onBlur={() => voiceName !== plan.voice.name && onCommit("voice.name", voiceName)} disabled={busy} />
      </Field>
      <Field label="Plan Style Camera">
        <input value={camera} onChange={(e) => setCamera(e.target.value)}
          onBlur={() => camera !== plan.style.camera && onCommit("style.camera", camera)} disabled={busy} />
      </Field>
      <Field label="Plan Voice Rate">
        <input type="number" min={0.5} max={2} step={0.1} value={voiceRate}
          onChange={(e) => setVoiceRate(e.target.value)}
          onBlur={() => Number(voiceRate) !== plan.voice.rate && onCommit("voice.rate", Number(voiceRate))}
          disabled={busy} />
      </Field>
    </div>
  );
}

// Scene card: local-state fields remounted per revision; selects/checkbox
// commit immediately, text/number fields commit on blur (Streamlit on_change).
function SceneCard({
  scene,
  busy,
  onPatch,
  onMove,
  onDelete,
}: {
  scene: PlanScene;
  busy: boolean;
  onPatch: (field: string, value: unknown) => void;
  onMove: (delta: number) => void;
  onDelete: () => void;
}) {
  const { t } = useI18n();
  const [narration, setNarration] = useState(scene.narration);
  const [est, setEst] = useState(String(scene.est_duration));
  const [visual, setVisual] = useState(scene.visual);
  const [keywords, setKeywords] = useState(scene.keywords.join(", "));

  const engineKnown = (PLAN_ENGINE_OPTIONS as readonly string[]).includes(scene.engine);

  return (
    <div className="plan-scene-card">
      <div className="scene-head">
        <strong>
          {scene.id} · {scene.est_duration.toFixed(1)}s
          {scene.keyframe?.shared_with_prev ? " 🔗" : ""}
        </strong>
        <label className="check">
          <input
            type="checkbox"
            checked={scene.locked}
            disabled={busy}
            onChange={(e) => onPatch("locked", e.target.checked)}
          />
          {t("Plan Scene Locked")}
        </label>
        <div className="scene-tools">
          <button className="icon-btn" disabled={busy} title={t("Plan Scene Move Up")}
            onClick={() => onMove(-1)}>↑</button>
          <button className="icon-btn" disabled={busy} title={t("Plan Scene Move Down")}
            onClick={() => onMove(1)}>↓</button>
          <button className="icon-btn" disabled={busy} title={t("Plan Scene Delete")}
            onClick={onDelete}>🗑</button>
        </div>
      </div>
      <Field label="Plan Scene Narration">
        <textarea rows={3} value={narration} disabled={busy}
          onChange={(e) => setNarration(e.target.value)}
          onBlur={() => narration !== scene.narration && onPatch("narration", narration)} />
      </Field>
      <div className="scene-row">
        <Field label="Plan Scene Est Duration">
          <input type="number" min={0.5} max={120} step={0.5} value={est} disabled={busy}
            onChange={(e) => setEst(e.target.value)}
            onBlur={() => Number(est) !== scene.est_duration && onPatch("est_duration", Number(est))} />
        </Field>
        <Field label="Plan Scene Visual">
          <input value={visual} disabled={busy}
            onChange={(e) => setVisual(e.target.value)}
            onBlur={() => visual !== scene.visual && onPatch("visual", visual)} />
        </Field>
      </div>
      <Field label="Plan Scene Keywords">
        <input value={keywords} disabled={busy}
          onChange={(e) => setKeywords(e.target.value)}
          onBlur={() => keywords !== scene.keywords.join(", ") && onPatch("keywords", keywords)} />
      </Field>
      {!engineKnown && (
        <div className="warning">
          {t("Plan Engine Cloud AI")} → {t("Plan Engine Stock")}
        </div>
      )}
      <div className="scene-row">
        <Field label="Plan Scene Engine">
          <Select
            value={engineKnown ? scene.engine : "stock"}
            disabled={busy}
            options={PLAN_ENGINE_OPTIONS.map((v) => ({ value: v, label: t(PLAN_ENGINE_LABEL_KEYS[v]) }))}
            onChange={(v) => onPatch("engine", v)}
          />
        </Field>
        <Field label="Plan Scene Transition">
          <Select
            value={scene.transition_to_next}
            disabled={busy}
            options={PLAN_TRANSITION_OPTIONS.map((v) => ({ value: v, label: t(PLAN_TRANSITION_LABEL_KEYS[v]) }))}
            onChange={(v) => onPatch("transition_to_next", v)}
          />
        </Field>
      </div>
    </div>
  );
}

export function PlanPanel({
  currentId,
  onSelectPlan,
}: {
  // Controlled selection lifted to ProPage so the wizard can jump here with
  // its fresh draft selected; falls back to internal state when uncontrolled.
  currentId?: string;
  onSelectPlan?: (id: string) => void;
}) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [internalId, setInternalId] = useState("");
  const pickPlan = onSelectPlan ?? setInternalId;
  const selectedId = currentId ?? internalId;
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [subject, setSubject] = useState("");
  const [busy, setBusy] = useState<string>("");
  const toastTimer = useRef<number | undefined>(undefined);

  function flash(message: string) {
    setToast(message);
    if (toastTimer.current) window.clearTimeout(toastTimer.current);
    toastTimer.current = window.setTimeout(() => setToast(""), 2600);
  }

  const listQuery = useQuery({
    queryKey: ["plans"],
    queryFn: () => api.get<{ plans: PlanSummary[] }>("/plans"),
  });
  const summaries = listQuery.data?.plans ?? [];
  const activeId =
    selectedId && summaries.some((s) => s.id === selectedId)
      ? selectedId
      : summaries[0]?.id ?? "";

  const detailQuery = useQuery({
    queryKey: ["plan", activeId],
    enabled: Boolean(activeId),
    queryFn: () => api.get<PlanDetail>(`/plans/${activeId}`),
  });
  const detail = detailQuery.data;
  const plan = detail?.plan;

  function done(planDetail?: PlanDetail) {
    if (planDetail) qc.setQueryData(["plan", activeId], planDetail);
    qc.invalidateQueries({ queryKey: ["plans"] });
    setBusy("");
  }
  function fail(err: unknown) {
    setError(err instanceof ApiError ? err.message : String(err));
    setBusy("");
  }
  async function run(key: string, fn: () => Promise<void>) {
    setBusy(key);
    setError("");
    try {
      await fn();
    } catch (err) {
      fail(err);
      return;
    }
    setBusy("");
  }

  async function generateDraft() {
    if (!subject.trim()) {
      setError(t("Wizard Idea Required"));
      return;
    }
    await run("generate", async () => {
      const res = await api.post<{ plan_id: string }>(
        "/plans/generate",
        { video_subject: subject.trim(), target_duration: 60 }
      );
      pickPlan(res.plan_id);
      qc.invalidateQueries({ queryKey: ["plans"] });
    });
  }

  async function importDraft(file: File) {
    await run("import", async () => {
      const parsed = JSON.parse(await file.text());
      const res = await api.post<{ plan_id: string }>("/plans", { plan: parsed });
      pickPlan(res.plan_id);
      qc.invalidateQueries({ queryKey: ["plans"] });
      flash(t("Plan Imported"));
    });
  }

  async function patchSetting(path: string, value: string | number) {
    await run("setting", async () => {
      done(await api.patch(`/plans/${activeId}/settings`, { path, value }));
    });
  }

  async function patchScene(sceneId: string, field: string, value: unknown) {
    await run("scene", async () => {
      done(await api.patch(`/plans/${activeId}/scenes/${sceneId}`, { field, value }));
    });
  }

  const moveScene = (sceneId: string, delta: number) =>
    run("scene", async () => {
      done(await api.post(`/plans/${activeId}/scenes/${sceneId}/move`, { delta }));
    });
  const addScene = () =>
    run("scene", async () => {
      done(await api.post(`/plans/${activeId}/scenes`));
    });
  const deleteScene = (sceneId: string) =>
    run("scene", async () => {
      done(await api.del(`/plans/${activeId}/scenes/${sceneId}`));
    });

  async function regenerate() {
    await run("regenerate", async () => {
      const res = await api.post(`/plans/${activeId}/regenerate`);
      done(res);
      if (plan?.scenes.some((s) => s.locked)) flash(t("Plan Locked Scenes Kept"));
    });
  }

  async function confirmPlan() {
    await run("confirm", async () => {
      done(await api.post(`/plans/${activeId}/confirm`));
      flash(t("Plan Confirmed"));
    });
  }

  async function deleteDraft() {
    await run("delete", async () => {
      await api.del(`/plans/${activeId}`);
      pickPlan("");
      setInternalId("");
      qc.invalidateQueries({ queryKey: ["plans"] });
      flash(t("Plan Draft Deleted"));
    });
  }

  async function executePlan() {
    if (!plan || !plan.scenes.some((s) => s.narration.trim())) {
      setError(t("Plan Narration Required"));
      return;
    }
    await run("execute", async () => {
      const res = await api.post<{ task_id?: string }>(`/plans/${activeId}/execute`);
      const taskId = res?.task_id;
      if (!taskId) throw new Error("no task id returned");
      setCurrentTask(taskId);
      navigate(`/jobs/${taskId}`);
    });
  }

  const estimated = detail?.estimated_duration ?? 0;
  const target = plan?.target_duration ?? 0;
  const pct = target > 0 ? Math.min((estimated / target) * 100, 100) : 0;

  return (
    <div className="route-page plan-page">
      <Panel title={t("Script Plan")}>
        {error && <div className="error">{error}</div>}
        {toast && <div className="toast">{toast}</div>}

        {summaries.length > 0 && (
          <Field label="Plan Draft Picker">
            <Select
              value={activeId}
              onChange={pickPlan}
              options={summaries.map((s) => ({
                value: s.id,
                label: `${s.title || s.id} · ${
                  t(s.status === "confirmed" ? "Plan Status Confirmed" : "Plan Status Draft")
                } · r${s.revision}`,
              }))}
            />
          </Field>
        )}

        {!plan && (
          <div>
            <p className="muted">{t("Plan Empty Hint")}</p>
            <Field label="Plan New Subject">
              <input value={subject} onChange={(e) => setSubject(e.target.value)} />
            </Field>
            <button className="btn primary" onClick={generateDraft} disabled={busy === "generate"}>
              {busy === "generate" ? t("Plan Generating") : t("Plan Generate")}
            </button>
          </div>
        )}

        {plan && (
          <>
            <div className="plan-header">
              <strong>
                {plan.status === "draft" ? "🟠" : "🟢"}{" "}
                {t(plan.status === "confirmed" ? "Plan Status Confirmed" : "Plan Status Draft")} ·{" "}
                {plan.title || activeId}
              </strong>
              <span className="muted">{t("Plan Revision")} r{plan.revision}</span>
              <span className="muted">{t("Plan Scenes Count")}: {plan.scenes.length}</span>
              <span className="muted">
                {t("Plan Target Duration")} {target.toFixed(0)}s ·{" "}
                {t("Plan Estimated Duration")} {estimated.toFixed(1)}s
              </span>
            </div>
            <div className="plan-progress">
              <div className="plan-progress-fill" style={{ width: `${pct}%` }} />
            </div>
            {detail?.duration_warnings?.map((w, i) => (
              <div key={i} className="warning">
                {t("Plan Duration Over")}: {w.message}
              </div>
            ))}

            <div className="plan-actions">
              <label className="field plan-tier">
                <span className="field-label">{t("Plan Quality Tier")}</span>
                <span className="segmented">
                  {(["draft", "final"] as const).map((tier) => (
                    <button
                      key={tier}
                      type="button"
                      className={plan.quality_tier === tier ? "seg active" : "seg"}
                      disabled={busy !== ""}
                      onClick={() => patchSetting("quality_tier", tier)}
                    >
                      {t(tier === "draft" ? "Plan Tier Draft" : "Plan Tier Final")}
                    </button>
                  ))}
                </span>
              </label>
              <button className="btn" onClick={regenerate} disabled={busy === "regenerate"}>
                {busy === "regenerate" ? t("Plan Generating") : t("Plan Regenerate")}
              </button>
              <button
                className="btn"
                onClick={() => downloadJson(`${plan.title || activeId}.json`, detail!.plan)}
              >
                {t("Plan Export JSON")}
              </button>
              <button
                className="btn"
                onClick={confirmPlan}
                disabled={plan.status === "confirmed" || busy !== ""}
              >
                {t("Plan Confirm")}
              </button>
              <button className="btn primary" onClick={executePlan} disabled={busy !== ""}>
                {busy === "execute" ? t("Submitting…") : t("Plan Confirm And Generate")}
              </button>
            </div>

            <div className="plan-import-row">
              <FilePickButton
                label={t("Plan Import JSON")}
                accept=".json,application/json"
                onPick={importDraft}
              />
              <button className="btn ghost" onClick={deleteDraft} disabled={busy !== ""}>
                {t("Plan Delete Draft")}
              </button>
            </div>

            <Expander title={t("Plan Settings")}>
              <PlanSettingsEditor
                key={`${activeId}:${plan.revision}`}
                plan={plan}
                busy={busy !== ""}
                onCommit={patchSetting}
              />
            </Expander>

            {plan.scenes.map((scene) => (
              <SceneCard
                key={`${scene.id}:${plan.revision}`}
                scene={scene}
                busy={busy !== ""}
                onPatch={(field, value) => patchScene(scene.id, field, value)}
                onMove={(delta) => moveScene(scene.id, delta)}
                onDelete={() => deleteScene(scene.id)}
              />
            ))}
            <button className="btn" onClick={addScene} disabled={busy !== ""}>
              + {t("Plan Scene Add")}
            </button>
          </>
        )}
      </Panel>
    </div>
  );
}
