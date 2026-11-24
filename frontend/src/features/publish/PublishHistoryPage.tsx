// 发布历史 (publish history) primary page: the Streamlit publish_history nav item.
// A focused read-only list over GET /publish/history (the operational queue and
// republish live on the 自动发布 config page / PublishPage).
import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";
import { useI18n } from "../../i18n";
import { navigate } from "../../app/router";

type HistoryItem = Record<string, unknown> & {
  task_id?: string;
  platform?: string;
  state?: string;
  status?: string;
  created_at?: string | number;
  error?: string;
};

export function PublishHistoryPage() {
  const { t } = useI18n();
  const { data, isLoading } = useQuery({
    queryKey: ["publish", "history"],
    queryFn: () => api.get<{ history: HistoryItem[] }>("/publish/history?limit=200"),
  });

  return (
    <div className="config-page">
      <div className="card" data-testid="publish-history">
        <h3>{t("Publish History Tab")}</h3>
        {isLoading && <p className="muted">{t("Loading…")}</p>}
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
            {(data?.history ?? []).map((item, i) => (
              <tr key={i}>
                <td>
                  <a href={`/jobs/${String(item.task_id ?? "")}`}>{String(item.task_id ?? "").slice(0, 8)}</a>
                </td>
                <td>{String(item.platform ?? "")}</td>
                <td>
                  <span className={`badge ${String(item.state ?? "")}`}>
                    {String(item.state ?? item.status ?? "")}
                  </span>
                  {item.error ? <em className="muted"> {String(item.error)}</em> : null}
                </td>
                <td>{String(item.created_at ?? "")}</td>
              </tr>
            ))}
            {!data?.history?.length && !isLoading && (
              <tr>
                <td colSpan={4} className="muted">
                  {t("No tasks yet.")}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
