// Material-docs API surface for the 素材库 file manager (public shared space +
// per-task TXT/MD + folder CRUD). Thin wrappers over the shared `api` client;
// every call carries scope ("public" | "task") and, for task scope, the task_id.
import { api } from "../../api/client";

export type MaterialScope = "public" | "task";

export type MaterialNode = {
  name: string;
  path: string;
  type: "dir" | "file";
  size: number;
  mtime: number;
  editable: boolean;
  depth: number;
};

export type MaterialTree = {
  scope: MaterialScope;
  root: string;
  items: MaterialNode[];
  truncated: boolean;
};

export type MaterialFile = { scope: MaterialScope; path: string; content: string };

function qs(scope: MaterialScope, taskId: string, extra = ""): string {
  const base = `scope=${encodeURIComponent(scope)}`;
  const task = scope === "task" ? `&task_id=${encodeURIComponent(taskId)}` : "";
  return `?${base}${task}${extra}`;
}

export const materialDocs = {
  tree: (scope: MaterialScope, taskId: string) =>
    api.get<MaterialTree>(`/materials/tree${qs(scope, taskId)}`),

  read: (scope: MaterialScope, taskId: string, path: string) =>
    api.get<MaterialFile>(
      `/materials/file${qs(scope, taskId, `&path=${encodeURIComponent(path)}`)}`
    ),

  createFile: (
    scope: MaterialScope,
    taskId: string,
    name: string,
    content: string,
    parent: string
  ) =>
    api.post<{ name: string; path: string; created: boolean }>("/materials/file", {
      scope,
      task_id: taskId,
      name,
      content,
      parent,
    }),

  updateFile: (scope: MaterialScope, taskId: string, path: string, content: string) =>
    api.put<{ name: string; path: string; created: boolean }>("/materials/file", {
      scope,
      task_id: taskId,
      path,
      content,
    }),

  deleteFile: (scope: MaterialScope, taskId: string, path: string) =>
    api.del<{ path: string; deleted: boolean }>(
      `/materials/file${qs(scope, taskId, `&path=${encodeURIComponent(path)}`)}`
    ),

  createFolder: (scope: MaterialScope, taskId: string, name: string, parent: string) =>
    api.post<{ name: string; path: string }>("/materials/folder", {
      scope,
      task_id: taskId,
      name,
      parent,
    }),

  deleteFolder: (scope: MaterialScope, taskId: string, path: string) =>
    api.del<{ path: string; deleted: boolean }>(
      `/materials/folder${qs(scope, taskId, `&path=${encodeURIComponent(path)}`)}`
    ),

  // Copy (reference) a file from a source scope (default public) into a task.
  reference: (body: {
    path: string;
    task_id: string;
    source_scope?: MaterialScope;
    source_task_id?: string;
    parent?: string;
    name?: string;
  }) =>
    api.post<{ source: string; name: string; path: string; created: boolean }>(
      "/materials/reference",
      body
    ),
};

// Direct children of `cwd` within a flat tree list, folders first then files,
// each case-folded for stable ordering (mirrors the backend listing intent).
export function childrenOf(items: MaterialNode[], cwd: string): MaterialNode[] {
  const prefix = cwd ? `${cwd}/` : "";
  const kids = items.filter((item) => {
    if (cwd === "") return !item.path.includes("/");
    return item.path.startsWith(prefix) && !item.path.slice(prefix.length).includes("/");
  });
  return kids.sort((a, b) => {
    if (a.type !== b.type) return a.type === "dir" ? -1 : 1;
    return a.name.localeCompare(b.name, undefined, { sensitivity: "base" });
  });
}
