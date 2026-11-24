import { useEffect, useState } from "react";
import { artifactRelativePath, signMediaPath } from "../../api/media";
import { apiBase } from "../../api/env";

// Renders a task artifact via a short-lived signed URL (migration 4.A).
// On a 401/403 playback error it re-signs once and retries.
export function VideoPreview({ path }: { path: string }) {
  const [url, setUrl] = useState("");
  const [err, setErr] = useState("");

  async function resolve() {
    try {
      // 任务列表返回的是 /tasks/... URI；签名端点要求相对 task_dir 的路径。
      const item = await signMediaPath(artifactRelativePath(path));
      setUrl(apiBase() + item.url);
    } catch {
      setErr("failed to sign media url");
    }
  }

  useEffect(() => {
    setErr("");
    resolve();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path]);

  if (err) return <div className="error">{err}</div>;
  if (!url) return <div className="muted">preparing preview…</div>;
  return (
    <video
      controls
      className="preview"
      src={url}
      onError={() => {
        // one automatic re-sign on expired/forbidden playback errors
        resolve();
      }}
    />
  );
}
