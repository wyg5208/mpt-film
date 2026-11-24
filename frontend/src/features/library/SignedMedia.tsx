// Shared signed-media plumbing for the library pages (migration 4.A). <video>
// and cross-origin <a download> cannot carry Bearer headers, so every artifact
// is exchanged for a short-lived HMAC URL before preview/download.
import { useEffect, useState } from "react";
import { artifactRelativePath, signMediaPath } from "../../api/media";
import { apiBase } from "../../api/env";
import { useI18n } from "../../i18n";

// Resolve one artifact path into a playable/ downloadable signed URL. Pass
// null to skip signing (e.g. a collapsed text preview); the state resets
// whenever the path changes.
export function useSignedUrl(path: string | null): { url: string; err: string } {
  const [url, setUrl] = useState("");
  const [err, setErr] = useState("");

  useEffect(() => {
    let alive = true;
    setUrl("");
    setErr("");
    if (!path) {
      return () => {
        alive = false;
      };
    }
    (async () => {
      try {
        // Callers may pass "/tasks/..." URIs (task/video lists) or already
        // task_dir-relative paths (files list); artifactRelativePath accepts both.
        const item = await signMediaPath(artifactRelativePath(path));
        if (alive) setUrl(apiBase() + item.url);
      } catch {
        if (alive) setErr("failed to sign media url");
      }
    })();
    return () => {
      alive = false;
    };
  }, [path]);

  return { url, err };
}

function fileNameOf(path: string): string {
  const raw = path.split("/").pop() || "file";
  try {
    return decodeURIComponent(raw);
  } catch {
    return raw;
  }
}

// Download anchor backed by a signed URL; `name` overrides the saved filename.
export function SignedDownloadLink({ path, name }: { path: string; name?: string }) {
  const { t } = useI18n();
  const { url, err } = useSignedUrl(path);
  if (err) return <span className="muted file-size">{err}</span>;
  if (!url) return null;
  return (
    <a className="btn ghost" href={url} download={fileNameOf(name || path)}>
      {t("Download")}
    </a>
  );
}
