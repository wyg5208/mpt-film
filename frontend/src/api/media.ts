// Signed media URL exchange + expiry re-sign (migration 4.A). <video src> cannot
// carry auth headers, so artifact paths are exchanged for short-lived HMAC URLs.
import { api } from "./client";

export type SignedItem = { path: string; url: string; expires_at: number };

// The sign endpoint expects a path RELATIVE to task_dir ("{taskId}/file.mp4"),
// while task lists expose "/tasks/{taskId}/file.mp4" URIs (or absolute URLs when
// an endpoint is configured). Strip the mount prefix before signing; keep the
// backend's percent-encoding intact so the signature binds the same canonical
// string the static /tasks mount resolves.
export function artifactRelativePath(path: string): string {
  let raw = path;
  if (raw.startsWith("http://") || raw.startsWith("https://")) {
    try {
      raw = new URL(raw).pathname;
    } catch {
      return path;
    }
  }
  const prefix = "/tasks/";
  return raw.startsWith(prefix) ? raw.slice(prefix.length) : raw;
}

export async function signMediaPaths(paths: string[]): Promise<SignedItem[]> {
  if (!paths.length) return [];
  const data = await api.post<{ items: SignedItem[] }>("/media/sign", { paths });
  return data.items;
}

export async function signMediaPath(path: string): Promise<SignedItem> {
  const items = await signMediaPaths([path]);
  return items[0];
}
