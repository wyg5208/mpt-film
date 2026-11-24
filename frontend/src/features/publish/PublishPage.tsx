// Publish panel (migration Part 6 发布): Streamlit `_render_publish_settings_body`
// (domestic social-auto-upload block + Upload-Post expander) on top, then the
// active cross-post queue with zombie warnings, publish history and manual
// republish via POST /publish. Polls the queue every 5s while any job is
// active (state projection lives in app/controllers/v1/publish.py).
import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api, ApiError } from "../../api/client";
import { useI18n } from "../../i18n";
import { ChipMultiSelect, Expander, fmt } from "../../components/ui";
import {
  SettingsField,
  useSection,
  useSaveSection,
} from "../settings/SettingsPage";
import {
  SAU_PLATFORMS,
  SAU_REPO_URL,
  UPLOAD_POST_API_KEYS_URL,
  UPLOAD_POST_MANAGE_USERS_URL,
} from "../config/catalog";

type QueueJob = {
  task_id: string;
  state: string;
  stage: string | null;
  progress: number | null;
  platform: string | null;
  platforms: string[] | null;
  log: { message?: string; stage?: string }[];
  video_subject: string | null;
};
type Zombie = { task_id?: string; pid?: number; message?: string };
type HistoryItem = Record<string, unknown> & {
  task_id?: string;
  platform?: string;
  state?: string;
  created_at?: string | number;
  error?: string;
};

type SessionEntry = { ok: boolean; detail?: string };

// Streamlit options are raw ids; defaults mirror social_auto_upload.
const UPLOAD_POST_PLATFORMS = ["tiktok", "instagram", "youtube"];
const DEFAULT_SAU_PLATFORMS = ["douyin", "tencent", "xiaohongshu", "bilibili"];

// 国内平台发布区 + Upload-Post 海外区（Main.py `_render_publish_settings_body`）。
// enabled 与 auto_upload 两键各自独立保存，与 Streamlit 相同。
function PublishSettingsCard() {
  const { t } = useI18n();
  const app = useSection("app");
  const save = useSaveSection("app");
  const settings = (app.data ?? {}) as Record<string, unknown>;

  const [report, setReport] = useState<Record<string, SessionEntry> | null>(null);
  const [checkMessage, setCheckMessage] = useState("");

  const enabled = settings.social_publish_enabled === true;
  const platforms = Array.isArray(settings.social_publish_platforms)
    ? (settings.social_publish_platforms as string[]).filter((p) =>
        SAU_PLATFORMS.some((option) => option.id === p)
      )
    : DEFAULT_SAU_PLATFORMS;
  const account = String(settings.social_publish_account ?? "").trim() || "default";
  const tid = Number(settings.social_publish_bilibili_tid ?? 21) || 21;
  const uploadPlatforms = Array.isArray(settings.upload_post_platforms)
    ? (settings.upload_post_platforms as string[])
    : ["tiktok", "instagram"];
  const ytAudience = settings.upload_post_youtube_made_for_kids === true;

  const check = useMutation({
    mutationFn: () =>
      api.post<{ busy: boolean; report: Record<string, SessionEntry> }>(
        "/publish/sessions/check",
        { platforms, account }
      ),
    onSuccess: (res) => {
      if (res.busy) {
        setCheckMessage(t("Session Check Busy"));
        return;
      }
      setCheckMessage("");
      setReport(res.report);
    },
    onError: (err) =>
      setCheckMessage(err instanceof ApiError ? err.message : String(err)),
  });

  function saveTid(raw: string) {
    const next = Math.min(9999, Math.max(1, Math.round(Number(raw) || 21)));
    save.mutate({ social_publish_bilibili_tid: next });
  }

  if (app.isLoading) return null;

  return (
    <div className="card" data-testid="publish-settings">
      <h3>{t("Auto-Publish Settings")}</h3>
      <p>{fmt(t("Domestic Auto-Publish Intro"), { repo_url: SAU_REPO_URL })}</p>
      <Expander title={t("Social Auto Upload Setup Guide")}>
        <p className="muted">{t("Social Auto Upload Setup Steps")}</p>
      </Expander>
      <label className="check">
        <input
          type="checkbox"
          checked={enabled}
          onChange={(e) => save.mutate({ social_publish_enabled: e.target.checked })}
        />
        {t("Enable Domestic Publishing")}
      </label>
      <label className="check">
        <input
          type="checkbox"
          checked={settings.social_publish_auto_upload === true}
          onChange={(e) =>
            save.mutate({ social_publish_auto_upload: e.target.checked })
          }
        />
        {t("Enable Domestic Auto-Publish")}
      </label>
      <SettingsField
        spec={{
          key: "social_publish_account",
          labelKey: "Publish Account Name",
          helpKey: "Publish Account Name Help",
          kind: "text",
        }}
        value={settings.social_publish_account ?? "default"}
        onSave={(_key, raw) =>
          save.mutate({ social_publish_account: String(raw).trim() || "default" })
        }
      />
      <label className="field">
        <span>{t("Domestic Platforms")}</span>
        <ChipMultiSelect
          options={SAU_PLATFORMS.map((p) => ({ value: p.id, label: p.label }))}
          value={platforms}
          onChange={(next) => save.mutate({ social_publish_platforms: next })}
        />
      </label>
      {platforms.includes("bilibili") && (
        <label className="field">
          <span>{t("Bilibili Partition ID")}</span>
          <input
            type="number"
            min={1}
            max={9999}
            value={tid}
            onChange={(e) => saveTid(e.target.value)}
          />
          <span className="muted">{t("Bilibili Partition Help")}</span>
        </label>
      )}
      <Expander title={t("Advanced Publish Settings")}>
        <SettingsField
          spec={{
            key: "sau_cli_path",
            labelKey: "SAU CLI Path",
            helpKey: "SAU CLI Path Help",
            kind: "text",
          }}
          value={settings.sau_cli_path ?? "sau"}
          onSave={(_key, raw) =>
            save.mutate({ sau_cli_path: String(raw).trim() || "sau" })
          }
        />
        <SettingsField
          spec={{
            key: "social_publish_browsers_path",
            labelKey: "Publish Browsers Path",
            helpKey: "Publish Browsers Path Help",
            kind: "text",
          }}
          value={String(settings.social_publish_browsers_path ?? "")}
          onSave={(key, raw) => save.mutate({ [key]: String(raw).trim() })}
        />
        <label className="check">
          <input
            type="checkbox"
            checked={settings.social_publish_headed !== false}
            onChange={(e) => save.mutate({ social_publish_headed: e.target.checked })}
          />
          {t("Publish Headed")}
        </label>
        <span className="muted">{t("Publish Headed Help")}</span>
      </Expander>
      <div className="row">
        <button
          className="btn"
          disabled={!enabled || platforms.length === 0 || check.isPending}
          onClick={() => check.mutate()}
        >
          {check.isPending ? t("Checking Login Sessions") : t("Check Login Sessions")}
        </button>
        {checkMessage && <span className="muted">{checkMessage}</span>}
      </div>
      {report &&
        platforms.map((platform) => {
          const entry = report[platform];
          if (!entry) return null;
          const label =
            SAU_PLATFORMS.find((p) => p.id === platform)?.label ?? platform;
          return entry.ok ? (
            <p key={platform} className="success">
              ✅ {label}
            </p>
          ) : (
            <div key={platform}>
              <p className="error">
                ❌ {label} — {entry.detail ?? ""}
              </p>
              <pre className="code-block">sau {platform} login --account {account}</pre>
            </div>
          );
        })}

      <Expander title={t("Overseas Platforms Optional UploadPost")}>
        <p className="muted">{t("Upload-Post Free Tier Note")}</p>
        <p>
          {t(
            "Automatically publish generated videos to social media using upload-post.com"
          )}
        </p>
        <p className="info-note">
          {fmt(t("Upload-Post Setup Guide"), {
            api_keys_url: UPLOAD_POST_API_KEYS_URL,
            manage_users_url: UPLOAD_POST_MANAGE_USERS_URL,
          })}
        </p>
        <label className="check">
          <input
            type="checkbox"
            checked={settings.upload_post_enabled === true}
            onChange={(e) => save.mutate({ upload_post_enabled: e.target.checked })}
          />
          {t("Enable Upload-Post Integration")}
        </label>
        <label className="check">
          <input
            type="checkbox"
            checked={settings.upload_post_auto_upload === true}
            onChange={(e) =>
              save.mutate({ upload_post_auto_upload: e.target.checked })
            }
          />
          {t("Enable Auto-Publish")}
        </label>
        <SettingsField
          spec={{
            key: "upload_post_api_key",
            labelKey: "Upload-Post API Key",
            kind: "password",
          }}
          value={settings.upload_post_api_key}
          onSave={(key, raw) => save.mutate({ [key]: raw })}
        />
        <span className="muted">
          {fmt(t("Upload-Post API Key Help"), {
            api_keys_url: UPLOAD_POST_API_KEYS_URL,
          })}
        </span>
        <SettingsField
          spec={{
            key: "upload_post_username",
            labelKey: "Upload-Post Profile Username",
            kind: "text",
          }}
          value={String(settings.upload_post_username ?? "")}
          onSave={(key, raw) => save.mutate({ [key]: raw })}
        />
        <span className="muted">
          {fmt(t("Upload-Post Profile Username Help"), {
            manage_users_url: UPLOAD_POST_MANAGE_USERS_URL,
          })}
        </span>
        <label className="field">
          <span>{t("Platforms")}</span>
          <ChipMultiSelect
            options={UPLOAD_POST_PLATFORMS.map((id) => ({ value: id, label: id }))}
            value={uploadPlatforms}
            onChange={(next) => save.mutate({ upload_post_platforms: next })}
          />
          <span className="muted">Select platforms to publish to</span>
        </label>
        {uploadPlatforms.includes("youtube") && (
          <>
            <label className="field">
              <span>{t("YouTube Privacy Status")}</span>
              <select
                value={String(settings.upload_post_youtube_privacy_status ?? "public")}
                onChange={(e) =>
                  save.mutate({ upload_post_youtube_privacy_status: e.target.value })
                }
              >
                {["public", "private", "unlisted"].map((v) => (
                  <option key={v} value={v}>
                    {v}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>{t("YouTube Audience")}</span>
              <select
                value={ytAudience ? "true" : "false"}
                onChange={(e) =>
                  save.mutate({
                    upload_post_youtube_made_for_kids: e.target.value === "true",
                  })
                }
              >
                <option value="false">{t("Not Made for Kids")}</option>
                <option value="true">{t("Made for Kids")}</option>
              </select>
              <span className="muted">{t("YouTube Audience Help")}</span>
            </label>
          </>
        )}
      </Expander>
    </div>
  );
}

export function PublishPage() {
  const { t } = useI18n();
  const [taskId, setTaskId] = useState("");
  const [message, setMessage] = useState("");

  const queue = useQuery({
    queryKey: ["publish", "queue"],
    queryFn: () => api.get<{ jobs: QueueJob[]; zombies: Zombie[] }>("/publish/queue"),
    refetchInterval: (q) =>
      (q.state.data?.jobs.length ?? 0) > 0 ? 5000 : false,
  });
  const history = useQuery({
    queryKey: ["publish", "history"],
    queryFn: () => api.get<{ history: HistoryItem[] }>("/publish/history?limit=200"),
  });

  async function republish() {
    if (!taskId.trim()) return;
    setMessage("");
    try {
      await api.post("/publish", { task_id: taskId.trim() });
      setMessage(t("Publish scheduled"));
      setTaskId("");
      queue.refetch();
      history.refetch();
    } catch (err) {
      setMessage(err instanceof ApiError ? err.message : String(err));
    }
  }

  const jobs = queue.data?.jobs ?? [];
  const zombies = queue.data?.zombies ?? [];

  return (
    <div className="publish-page">
      <PublishSettingsCard />
      <div className="card" data-testid="publish-queue">
        <h3>{t("Publish queue")}</h3>
        {zombies.length > 0 && (
          <p className="error" data-testid="zombie-warning">
            ⚠ {t("Zombie publish processes detected")}
          </p>
        )}
        {jobs.length === 0 ? (
          <p className="muted">{t("No active publish jobs")}</p>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>{t("Task")}</th>
                <th>{t("Subject")}</th>
                <th>{t("Platform")}</th>
                <th>{t("Stage")}</th>
                <th>{t("Progress")}</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((job) => (
                <tr key={job.task_id}>
                  <td>
                    <a href={`/jobs/${job.task_id}`}>{job.task_id.slice(0, 8)}</a>
                  </td>
                  <td>{job.video_subject ?? ""}</td>
                  <td>{(job.platforms ?? [job.platform]).filter(Boolean).join(", ")}</td>
                  <td>
                    {job.stage ?? ""} <em className="muted">{job.state}</em>
                  </td>
                  <td>{job.progress != null ? `${job.progress}%` : ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="card" data-testid="publish-republish">
        <h3>{t("Republish")}</h3>
        <div className="row">
          <input
            placeholder={t("Task ID of a finished video")}
            value={taskId}
            onChange={(e) => setTaskId(e.target.value)}
          />
          <button className="btn primary" disabled={!taskId.trim()} onClick={republish}>
            {t("Publish now")}
          </button>
        </div>
        {message && <p className="muted">{message}</p>}
      </div>

      <div className="card" data-testid="publish-history">
        <h3>{t("Publish history")}</h3>
        <table className="table">
          <thead>
            <tr>
              <th>{t("Task")}</th>
              <th>{t("Platform")}</th>
              <th>{t("Status")}</th>
              <th>{t("Time")}</th>
            </tr>
          </thead>
          <tbody>
            {(history.data?.history ?? []).map((item, i) => (
              <tr key={i}>
                <td>{String(item.task_id ?? "").slice(0, 8)}</td>
                <td>{String(item.platform ?? "")}</td>
                <td>
                  <span className={`badge ${String(item.state ?? "")}`}>
                    {String(item.state ?? item.status ?? "")}
                  </span>
                  {item.error ? (
                    <em className="muted"> {String(item.error)}</em>
                  ) : null}
                </td>
                <td>{String(item.created_at ?? "")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
