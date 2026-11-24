// 成片库 (finished-videos library): the React counterpart of Main.py's disk-scan
// task history (storage/tasks/*/final-*.mp4 rendered as st.video rows). One
// GET /videos-library merges in-memory state entries with on-disk history so
// videos survive backend restarts; playback reuses VideoPreview (signed URLs).
import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";
import { useI18n } from "../../i18n";
import { navigate } from "../../app/router";
import { VideoPreview } from "../tasks/VideoPreview";
import { SignedDownloadLink } from "./SignedMedia";

type LibraryVideo = {
  task_id: string;
  subject: string;
  videos: string[];
  source: string;
  mtime: number;
};

export function VideosLibraryPage() {
  const { t } = useI18n();
  const { data, isLoading, error } = useQuery({
    queryKey: ["videos-library"],
    queryFn: () => api.get<{ items: LibraryVideo[] }>("/videos-library?limit=100"),
    refetchInterval: 10000,
  });
  const items = data?.items ?? [];

  return (
    <div className="library-page">
      <p className="muted">{t("Videos Library Hint")}</p>
      {isLoading && <p className="muted">{t("Loading…")}</p>}
      {error && <div className="error">{t("Videos Library Load Error")}</div>}
      {items.map((item) => (
        <section className="lib-card" key={item.task_id}>
          <header className="lib-head">
            <div>
              <div className="lib-title">{item.subject}</div>
              <div className="lib-sub muted">
                {item.task_id}
                {item.mtime
                  ? ` · ${new Date(item.mtime * 1000).toLocaleString()}`
                  : ""}
              </div>
            </div>
            <button
              className="btn ghost"
              onClick={() => navigate(`/jobs/${item.task_id}`)}
            >
              {t("Detail")}
            </button>
          </header>
          <div className="library-grid">
            {item.videos.map((video) => (
              <div className="lib-video" key={video}>
                <VideoPreview path={video} />
                <SignedDownloadLink path={video} />
              </div>
            ))}
          </div>
        </section>
      ))}
      {!items.length && !isLoading && !error && (
        <p className="muted">{t("Videos Library Empty")}</p>
      )}
    </div>
  );
}
