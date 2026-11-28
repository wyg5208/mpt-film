// 素材库文件管理器：在指定作用域（公共素材 / 任务素材）内通过 UI 直接管理
// TXT/MD 文件与空文件夹——新建/编辑/删除文件、新建/删除文件夹、进入/返回文件夹。
// 采用单层浏览 + 面包屑：cwd 为当前文件夹相对路径（"" 表示作用域根），childrenOf
// 从后端返回的扁平树里过滤出直接子项。所有写操作成功后失效并重新拉取树。
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError } from "../../api/client";
import { useI18n } from "../../i18n";
import { formatSize } from "../../components/ui";
import {
  childrenOf,
  materialDocs,
  type MaterialNode,
  type MaterialScope,
} from "./useMaterialDocs";

type Editor =
  | { mode: "new-file" }
  | { mode: "edit"; path: string; name: string }
  | null;

// A selectable destination task for the 公共素材 → 任务 引用动作。
type TaskOption = { task_id: string; subject: string };

export function FileManager({
  scope,
  taskId,
  tasks,
}: {
  scope: MaterialScope;
  taskId: string;
  tasks?: TaskOption[];
}) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [cwd, setCwd] = useState("");
  const [editor, setEditor] = useState<Editor>(null);
  const [newFolder, setNewFolder] = useState(false);
  const [folderName, setFolderName] = useState("");
  const [fileName, setFileName] = useState("");
  const [fileContent, setFileContent] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  // 引用面板：仅公共素材作用域可用——选一个目标任务，把当前 TXT/MD 复制进去。
  const [refNode, setRefNode] = useState<MaterialNode | null>(null);
  const [refTaskId, setRefTaskId] = useState("");
  const [refMsg, setRefMsg] = useState("");
  const canReference = scope === "public" && !!tasks && tasks.length > 0;

  const enabled = scope === "public" || !!taskId;
  const queryKey = ["material-tree", scope, taskId];
  const { data, isLoading } = useQuery({
    queryKey,
    queryFn: () => materialDocs.tree(scope, taskId),
    enabled,
  });
  const items = data?.items ?? [];
  const kids = childrenOf(items, cwd);

  function refresh() {
    qc.invalidateQueries({ queryKey });
  }
  function fail(err: unknown) {
    setError(err instanceof ApiError ? err.message : t("Material Op Error"));
    setBusy(false);
  }

  async function openEditor(node: MaterialNode) {
    setError("");
    try {
      const file = await materialDocs.read(scope, taskId, node.path);
      setFileName(node.name);
      setFileContent(file.content);
      setEditor({ mode: "edit", path: node.path, name: node.name });
    } catch (err) {
      fail(err);
    }
  }

  function startNewFile() {
    setError("");
    setFileName("");
    setFileContent("");
    setEditor({ mode: "new-file" });
  }

  async function saveFile() {
    if (busy || !editor) return;
    setBusy(true);
    setError("");
    try {
      if (editor.mode === "new-file") {
        await materialDocs.createFile(scope, taskId, fileName, fileContent, cwd);
      } else {
        await materialDocs.updateFile(scope, taskId, editor.path, fileContent);
      }
      setEditor(null);
      setBusy(false);
      refresh();
    } catch (err) {
      fail(err);
    }
  }

  async function createFolder() {
    if (busy || !folderName.trim()) return;
    setBusy(true);
    setError("");
    try {
      await materialDocs.createFolder(scope, taskId, folderName.trim(), cwd);
      setFolderName("");
      setNewFolder(false);
      setBusy(false);
      refresh();
    } catch (err) {
      fail(err);
    }
  }

  async function removeFile(node: MaterialNode) {
    if (!window.confirm(t("Material Delete File Confirm") + "\n" + node.name)) return;
    setBusy(true);
    setError("");
    try {
      await materialDocs.deleteFile(scope, taskId, node.path);
      setBusy(false);
      refresh();
    } catch (err) {
      fail(err);
    }
  }

  async function removeFolder(node: MaterialNode) {
    if (!window.confirm(t("Material Delete Folder Confirm") + "\n" + node.name)) return;
    setBusy(true);
    setError("");
    try {
      await materialDocs.deleteFolder(scope, taskId, node.path);
      setBusy(false);
      refresh();
    } catch (err) {
      fail(err);
    }
  }

  function startReference(node: MaterialNode) {
    setError("");
    setRefMsg("");
    setRefNode(node);
    setRefTaskId(tasks && tasks.length ? tasks[0].task_id : "");
  }

  async function confirmReference() {
    if (busy || !refNode || !refTaskId) return;
    setBusy(true);
    setError("");
    setRefMsg("");
    try {
      await materialDocs.reference({
        path: refNode.path,
        task_id: refTaskId,
        source_scope: "public",
      });
      // 目标任务树可能已缓存，失效以便下次进入该任务时拉到最新。
      qc.invalidateQueries({ queryKey: ["material-tree", "task", refTaskId] });
      setRefMsg(t("Material Reference Done"));
      setRefNode(null);
      setBusy(false);
    } catch (err) {
      fail(err);
    }
  }

  // Breadcrumb segments from cwd, e.g. "a/b" -> [{p:"a",n:"a"},{p:"a/b",n:"b"}].
  const crumbs = cwd
    ? cwd.split("/").map((seg, i, arr) => ({
        name: seg,
        path: arr.slice(0, i + 1).join("/"),
      }))
    : [];

  if (scope === "task" && !taskId) return null;

  return (
    <div className="file-manager" data-testid={`file-manager-${scope}`}>
      <div className="fm-bar">
        <nav className="fm-crumbs">
          <button
            className={cwd === "" ? "fm-crumb active" : "fm-crumb"}
            onClick={() => setCwd("")}
          >
            {scope === "public" ? t("Public Material Root") : t("Task Material Root")}
          </button>
          {crumbs.map((c) => (
            <span key={c.path} className="fm-crumb-sep">
              /
              <button
                className={cwd === c.path ? "fm-crumb active" : "fm-crumb"}
                onClick={() => setCwd(c.path)}
              >
                {c.name}
              </button>
            </span>
          ))}
        </nav>
        <div className="fm-actions">
          <button className="btn" onClick={startNewFile} disabled={busy}>
            {t("New Text File")}
          </button>
          <button
            className="btn ghost"
            onClick={() => {
              setNewFolder((v) => !v);
              setError("");
            }}
            disabled={busy}
          >
            {t("New Folder")}
          </button>
        </div>
      </div>

      {newFolder && (
        <div className="fm-inline">
          <input
            autoFocus
            value={folderName}
            placeholder={t("Folder Name Placeholder")}
            onChange={(e) => setFolderName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && createFolder()}
          />
          <button className="btn" onClick={createFolder} disabled={busy}>
            {t("Create")}
          </button>
          <button className="btn ghost" onClick={() => setNewFolder(false)}>
            {t("Cancel")}
          </button>
        </div>
      )}

      {error && <div className="error">{error}</div>}
      {refMsg && <div className="muted fm-ref-done">{refMsg}</div>}

      {refNode && canReference && (
        <div className="fm-inline" data-testid="material-reference-panel">
          <span className="fm-ref-label">
            {t("Material Reference To")} 📄 {refNode.name}
          </span>
          <select
            value={refTaskId}
            onChange={(e) => setRefTaskId(e.target.value)}
            disabled={busy}
          >
            {tasks?.map((task) => (
              <option key={task.task_id} value={task.task_id}>
                {task.subject}
              </option>
            ))}
          </select>
          <button
            className="btn"
            onClick={confirmReference}
            disabled={busy || !refTaskId}
          >
            {t("Material Reference Confirm")}
          </button>
          <button
            className="btn ghost"
            onClick={() => {
              setRefNode(null);
              setRefMsg("");
            }}
          >
            {t("Cancel")}
          </button>
        </div>
      )}

      {editor && (
        <div className="fm-editor">
          <div className="fm-editor-head">
            {editor.mode === "new-file" ? (
              <input
                autoFocus
                value={fileName}
                placeholder={t("File Name Placeholder")}
                onChange={(e) => setFileName(e.target.value)}
              />
            ) : (
              <span className="mono">{editor.name}</span>
            )}
          </div>
          <textarea
            className="fm-textarea"
            value={fileContent}
            spellCheck={false}
            onChange={(e) => setFileContent(e.target.value)}
          />
          <div className="fm-editor-foot">
            <button className="btn" onClick={saveFile} disabled={busy}>
              {t("Save")}
            </button>
            <button className="btn ghost" onClick={() => setEditor(null)}>
              {t("Cancel")}
            </button>
          </div>
        </div>
      )}

      {isLoading && <p className="muted">{t("Loading…")}</p>}
      {!isLoading && !kids.length && !editor && !newFolder && (
        <p className="muted">{t("Material Space Empty")}</p>
      )}

      <ul className="fm-list">
        {kids.map((node) => (
          <li key={node.path} className="fm-row">
            {node.type === "dir" ? (
              <>
                <button
                  className="fm-name fm-dir"
                  onClick={() => setCwd(node.path)}
                  title={node.name}
                >
                  📁 {node.name}
                </button>
                <button
                  className="btn ghost"
                  onClick={() => removeFolder(node)}
                  disabled={busy}
                >
                  {t("Delete")}
                </button>
              </>
            ) : (
              <>
                <span className="fm-name" title={node.name}>
                  📄 {node.name}
                </span>
                <span className="muted fm-size">{formatSize(node.size)}</span>
                {node.editable ? (
                  <>
                    <button className="btn ghost" onClick={() => openEditor(node)}>
                      {t("Edit")}
                    </button>
                    {canReference && (
                      <button
                        className="btn ghost"
                        onClick={() => startReference(node)}
                        disabled={busy}
                      >
                        {t("Material Reference Action")}
                      </button>
                    )}
                    <button
                      className="btn ghost"
                      onClick={() => removeFile(node)}
                      disabled={busy}
                    >
                      {t("Delete")}
                    </button>
                  </>
                ) : (
                  <span className="muted fm-size">{t("Material Not Editable")}</span>
                )}
              </>
            )}
          </li>
        ))}
      </ul>

      {data?.truncated && <p className="muted">{t("Material Tree Truncated")}</p>}
    </div>
  );
}
