// 素材库 (materials library): per-task artifact browser. The Streamlit app only
// surfaces task artifacts inside the task panel (row 播放 + bottom player); this
// page lists every file under the selected task dir grouped by category with
// inline preview (video/audio/image/text) and signed downloads.
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";
import { useI18n } from "../../i18n";
import { navigate } from "../../app/router";
import { VideoPreview } from "../tasks/VideoPreview";
import { SignedDownloadLink, useSignedUrl } from "./SignedMedia";
import { formatSize } from "../../components/ui";

type TaskSummary = {
  task_id: string;
  state: number;
  video_subject?: string;
  subjects?: string[];
};

// Disk task dir from GET /task-dirs: survives backend restarts, so history
// tasks stay selectable even when their live state was lost (memory mode).
type DirEntry = { task_id: string; subject: string; mtime: number };

type SelectorTask = { task_id: string; subject: string };

type TaskFile = {
  name: string;
  path: string;
  size: number;
  mtime: number;
  category: string;
};

// Display order mirrors what the pipeline produces: final video, narration
// audio, subtitles, covers, pipeline data files, then anything unrecognized.
const CATEGORY_ORDER = ["video", "audio", "subtitle", "image", "data", "other"];

const CATEGORY_LABEL: Record<string, string> = {
  video: "Materials Cat Video",
  audio: "Materials Cat Audio",
  subtitle: "Materials Cat Subtitle",
  image: "Materials Cat Image",
  data: "Materials Cat Data",
  other: "Materials Cat Other",
};

function subjectOf(task: TaskSummary): string {
  if (task.video_subject) return task.video_subject;
  if (task.subjects && task.subjects.length) return task.subjects[0];
  return task.task_id.slice(0, 8);
}

function AudioPreview({ path }: { path: string }) {
  const { url, err } = useSignedUrl(path);
  if (err) return <div className="error">{err}</div>;
  if (!url) return null;
  return <audio controls className="file-audio" src={url} />;
}

function ImagePreview({ path }: { path: string }) {
  const { url, err } = useSignedUrl(path);
  if (err) return <div className="error">{err}</div>;
  if (!url) return null;
  return <img className="file-img" src={url} alt={path.split("/").pop() || ""} />;
}

// Subtitle / data files: fetch the signed URL as text and render it verbatim.
function TextPreview({ path }: { path: string }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const { url, err: signErr } = useSignedUrl(open ? path : null);
  const [text, setText] = useState("");
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!open || !url) return;
    let alive = true;
    setErr("");
    setText("");
    fetch(url)
      .then((res) =>
        res.ok ? res.text() : Promise.reject(new Error(String(res.status)))
      )
      .then((body) => {
        if (alive) setText(body);
      })
      .catch(() => {
        if (alive) setErr(t("Materials Text Preview Error"));
      });
    return () => {
      alive = false;
    };
  }, [open, url, t]);

  if (!open) {
    return (
      <button className="btn ghost" onClick={() => setOpen(true)}>
        {t("Materials Text Preview")}
      </button>
    );
  }
  return (
    <div className="file-text-wrap">
      <button className="btn ghost" onClick={() => setOpen(false)}>
        {t("Hide Text Preview")}
      </button>
      {signErr || err ? (
        <div className="error">{signErr || err}</div>
      ) : (
        <pre className="file-text">{text}</pre>
      )}
    </div>
  );
}

function FileRow({ file }: { file: TaskFile }) {
  return (
    <div className="file-row" data-category={file.category}>
      <div className="file-meta">
        <span className="file-name" title={file.name}>
          {file.name}
        </span>
        <span className="file-size muted">{formatSize(file.size)}</span>
        <SignedDownloadLink path={file.path} name={file.name} />
      </div>
      {file.category === "video" && <VideoPreview path={file.path} />}
      {file.category === "audio" && <AudioPreview path={file.path} />}
      {file.category === "image" && <ImagePreview path={file.path} />}
      {(file.category === "subtitle" || file.category === "data") && (
        <TextPreview path={file.path} />
      )}
    </div>
  );
}

export function MaterialsLibraryPage() {
  const { t } = useI18n();
  const [activeId, setActiveId] = useState("");

  const { data: tasksData, isLoading: tasksLoading } = useQuery({
    queryKey: ["tasks"],
    queryFn: () => api.get<{ tasks: TaskSummary[] }>("/tasks?page_size=100"),
    refetchInterval: 10000,
  });
  const tasks = tasksData?.tasks ?? [];

  const { data: dirsData, isLoading: dirsLoading } = useQuery({
    queryKey: ["task-dirs"],
    queryFn: () => api.get<{ items: DirEntry[] }>("/task-dirs?limit=200"),
    refetchInterval: 10000,
  });

  // Selector source: live state tasks first (accurate subjects/states), then
  // disk-only history dirs so artifacts stay reachable after a restart.
  const selectorTasks: SelectorTask[] = (() => {
    const merged: SelectorTask[] = [];
    const seen = new Set<string>();
    for (const task of tasks) {
      if (seen.has(task.task_id)) continue;
      seen.add(task.task_id);
      merged.push({ task_id: task.task_id, subject: subjectOf(task) });
    }
    for (const dir of dirsData?.items ?? []) {
      if (seen.has(dir.task_id)) continue;
      seen.add(dir.task_id);
      merged.push({ task_id: dir.task_id, subject: dir.subject });
    }
    return merged;
  })();
  const current =
    selectorTasks.find((task) => task.task_id === activeId) ?? selectorTasks[0];
  const effectiveId = current?.task_id ?? "";

  const {
    data: filesData,
    isLoading: filesLoading,
    error,
  } = useQuery({
    queryKey: ["task-files", effectiveId],
    queryFn: () =>
      api.get<{ task_id: string; files: TaskFile[] }>(`/tasks/${effectiveId}/files`),
    enabled: !!effectiveId,
  });
  const files = filesData?.files ?? [];
  const groups = CATEGORY_ORDER.map((category) => ({
    category,
    files: files.filter((file) => file.category === category),
  })).filter((group) => group.files.length);

  return (
    <div className="library-page">
      <p className="muted">{t("Materials Library Hint")}</p>
      <div className="materials-select-wrap">
        <span className="muted">{t("Select Task")}</span>
        <select
          className="materials-select"
          data-testid="materials-task-select"
          value={effectiveId}
          disabled={!selectorTasks.length}
          onChange={(e) => setActiveId(e.target.value)}
        >
          {selectorTasks.map((task) => (
            <option key={task.task_id} value={task.task_id}>
              {task.subject}
            </option>
          ))}
        </select>
        {effectiveId && (
          <button
            className="btn ghost"
            onClick={() => navigate(`/jobs/${effectiveId}`)}
          >
            {t("Detail")}
          </button>
        )}
      </div>

      {(tasksLoading || dirsLoading) && <p className="muted">{t("Loading…")}</p>}
      {!selectorTasks.length && !tasksLoading && !dirsLoading && (
        <p className="muted">{t("No tasks yet.")}</p>
      )}
      {error && <div className="error">{t("Materials Load Error")}</div>}

      {effectiveId && filesLoading && <p className="muted">{t("Loading…")}</p>}
      {effectiveId && !filesLoading && !error && !files.length && (
        <p className="muted">{t("Materials Library Empty")}</p>
      )}

      {groups.map((group) => (
        <section className="file-group" key={group.category}>
          <div className="file-group-title">
            {t(CATEGORY_LABEL[group.category])}
            <span className="muted file-size"> · {group.files.length}</span>
          </div>
          <div className="file-list">
            {group.files.map((file) => (
              <FileRow key={file.path} file={file} />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
