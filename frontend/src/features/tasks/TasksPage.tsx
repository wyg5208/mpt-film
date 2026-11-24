// Task management page (migration Part 6 "任务管理"): the React counterpart of
// the Streamlit task-manager popover. Loads the paginated task list, filters it
// by lifecycle state through tabs, and offers per-row actions (open detail /
// delete). State numbers mirror app task states: 0 processing, 1 complete,
// -1 failed, 4 pending/ready.
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "../../api/client";
import { useI18n } from "../../i18n";
import { navigate } from "../../app/router";

type Task = {
  task_id: string;
  state: number;
  progress?: number;
  video_subject?: string;
  subjects?: string[];
  videos?: string[];
  error?: string | null;
};

const FILTERS = [
  { key: "all", label: "All" },
  { key: "processing", label: "Processing" },
  { key: "pending", label: "Pending" },
  { key: "complete", label: "Complete" },
  { key: "failed", label: "Failed" },
];

function matchesFilter(state: number, filter: string): boolean {
  if (filter === "all") return true;
  if (filter === "processing") return state === 0;
  if (filter === "pending") return state === 4;
  if (filter === "complete") return state === 1;
  if (filter === "failed") return state === -1;
  return true;
}

function subjectOf(task: Task): string {
  if (task.video_subject) return task.video_subject;
  if (task.subjects && task.subjects.length) return task.subjects[0];
  return task.task_id.slice(0, 8);
}

export function TasksPage() {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [filter, setFilter] = useState("all");
  const [message, setMessage] = useState("");

  const { data, isLoading, error } = useQuery({
    queryKey: ["tasks"],
    queryFn: () => api.get<{ tasks: Task[] }>("/tasks?page_size=100"),
    refetchInterval: 5000,
  });

  const remove = useMutation({
    mutationFn: (taskId: string) => api.del(`/tasks/${taskId}`),
    onSuccess: () => {
      setMessage(t("Task deleted"));
      qc.invalidateQueries({ queryKey: ["tasks"] });
    },
    onError: (err) => setMessage(err instanceof ApiError ? err.message : String(err)),
  });

  const tasks = (data?.tasks ?? []).filter((task) => matchesFilter(task.state, filter));

  return (
    <div className="tasks-page">
      <div className="tabs" data-testid="task-filters">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            className={f.key === filter ? "tab active" : "tab"}
            onClick={() => setFilter(f.key)}
          >
            {t(f.label)}
          </button>
        ))}
      </div>

      {message && <p className="muted">{message}</p>}
      {isLoading && <p className="muted">{t("Loading…")}</p>}
      {error && <div className="error">{t("Failed to load tasks")}</div>}

      <table className="table">
        <thead>
          <tr>
            <th>{t("Subject")}</th>
            <th>{t("State")}</th>
            <th>{t("Progress")}</th>
            <th>{t("Actions")}</th>
          </tr>
        </thead>
        <tbody>
          {tasks.map((task) => (
            <tr key={task.task_id}>
              <td title={task.task_id}>{subjectOf(task)}</td>
              <td>
                <span className={`state-badge state-${stateKey(task.state)}`}>
                  {t(stateLabel(task.state))}
                </span>
              </td>
              <td>
                <div className="progress">
                  <div
                    className="progress-bar"
                    style={{ width: `${task.progress ?? 0}%` }}
                  />
                </div>
                <span className="progress-text">{task.progress ?? 0}%</span>
              </td>
              <td className="row-actions">
                <button className="btn ghost" onClick={() => navigate(`/jobs/${task.task_id}`)}>
                  {t("Detail")}
                </button>
                <button
                  className="btn ghost"
                  disabled={remove.isPending}
                  onClick={() => remove.mutate(task.task_id)}
                >
                  {t("Delete")}
                </button>
              </td>
            </tr>
          ))}
          {!tasks.length && !isLoading && (
            <tr>
              <td colSpan={4} className="muted">
                {t("No tasks yet.")}
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function stateKey(state: number): string {
  if (state === 1) return "complete";
  if (state === -1) return "failed";
  if (state === 0) return "processing";
  if (state === 4) return "pending";
  return "unknown";
}

function stateLabel(state: number): string {
  return {
    1: "Complete",
    "-1": "Failed",
    0: "Processing",
    4: "Pending",
  }[state] ?? "Unknown";
}
