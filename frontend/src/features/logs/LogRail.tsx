// 右侧实时日志（Streamlit 生成日志列的 React 对应物）。
// - useTaskLogStream：SSE 订阅 + 自动重连补齐，任务切换时重置缓冲；
// - LogPanel：任务详情页内嵌的完整日志面板（/jobs/:id）；
// - LogDock：全局日志坞。默认收起为右下角悬浮胶囊（带进度角标与状态点），
//   点击后以模态框展开到页面 3/4 宽度，保证完整日志行的可读宽度；
//   新任务提交且不在任务详情页时自动展开一次（详情页已内嵌面板，不重复弹窗）。
import { useEffect, useRef, useState } from "react";
import { streamTaskEvents } from "../../api/sse";
import { useI18n } from "../../i18n";
import { getCurrentTask, onCurrentTaskChange } from "../../app/currentTask";

export type TaskLogStream = {
  lines: string[];
  state: number;
  progress: number;
  done: boolean;
};

export function useTaskLogStream(taskId: string | null): TaskLogStream {
  const [lines, setLines] = useState<string[]>([]);
  const [status, setStatus] = useState({ state: 0, progress: 0 });
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (!taskId) return;
    const controller = new AbortController();
    setLines([]);
    setStatus({ state: 0, progress: 0 });
    setDone(false);
    streamTaskEvents(
      taskId,
      {
        onLog: (_seq, line) => setLines((prev) => [...prev, line]),
        onState: (s, p) => setStatus({ state: s, progress: p }),
        onEnd: (s) => {
          setDone(true);
          if (s !== null && s !== undefined)
            setStatus((prev) => ({ ...prev, state: s }));
        },
      },
      { signal: controller.signal }
    );
    return () => controller.abort();
  }, [taskId]);

  return { lines, state: status.state, progress: status.progress, done };
}

type TFunc = (key: string, params?: Record<string, string | number>) => string;

function logStatus(t: TFunc, s: TaskLogStream): string {
  if (s.done) return t("Log Finished");
  if (s.lines.length)
    return `${t("Log Streaming")} · ${t("Log Progress", { progress: s.progress })}`;
  return t("Log Waiting");
}

function dotClass(s: TaskLogStream, hasTask: boolean): string {
  if (!hasTask) return "log-dot";
  if (s.done) return "log-dot done";
  return "log-dot running";
}

function LogLines({
  boxRef,
  lines,
  emptyText,
}: {
  boxRef: React.RefObject<HTMLDivElement | null>;
  lines: string[];
  emptyText: string;
}) {
  return (
    <div className="logbox" ref={boxRef}>
      {lines.map((l, i) => (
        <div key={i} className="logline">
          {l}
        </div>
      ))}
      {!lines.length && <div className="muted">{emptyText}</div>}
    </div>
  );
}

function useAutoScroll(lines: string[]) {
  const boxRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    if (boxRef.current)
      boxRef.current.scrollTop = boxRef.current.scrollHeight;
  }, [lines]);
  return boxRef;
}

/** 任务详情页内嵌日志面板（原 LogRail 的完整形态）。 */
export function LogPanel({ taskId }: { taskId: string }) {
  const { t } = useI18n();
  const stream = useTaskLogStream(taskId);
  const boxRef = useAutoScroll(stream.lines);

  return (
    <div className="card lograil">
      <div className="loghead">
        <h3>{t("Generation Logs Title")}</h3>
        <span className="muted">{logStatus(t, stream)}</span>
      </div>
      <LogLines boxRef={boxRef} lines={stream.lines} emptyText={t("Log Waiting")} />
    </div>
  );
}

/** 全局日志坞：右下角收起胶囊 + 3/4 宽展开模态框。 */
export function LogDock() {
  const { t } = useI18n();
  const [taskId, setTaskId] = useState(getCurrentTask());
  const [open, setOpen] = useState(false);
  // 仅响应“新任务提交”事件自动展开；页面刷新带着旧 taskId 挂载时保持收起。
  const prevTaskRef = useRef(taskId);

  useEffect(() => {
    const sync = () => {
      const next = getCurrentTask();
      if (next && next !== prevTaskRef.current && !window.location.pathname.startsWith("/jobs")) {
        setOpen(true);
      }
      prevTaskRef.current = next;
      setTaskId(next);
    };
    const off = onCurrentTaskChange(sync);
    return () => off();
  }, []);

  const stream = useTaskLogStream(taskId || null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  const boxRef = useAutoScroll(stream.lines);

  return (
    <>
      {!open && (
        <button
          className="log-launcher"
          data-testid="log-launcher"
          onClick={() => setOpen(true)}
          title={t("Expand Generation Logs")}
        >
          <span className={dotClass(stream, !!taskId)} />
          <span>{t("Generation Logs Title")}</span>
          {taskId && !stream.done && (
            <span className="log-badge">{stream.progress}%</span>
          )}
        </button>
      )}
      {open && (
        <div
          className="log-modal-backdrop"
          data-testid="log-modal"
          onClick={() => setOpen(false)}
        >
          <section
            className="log-modal"
            role="dialog"
            aria-modal="true"
            onClick={(e) => e.stopPropagation()}
          >
            <header className="log-modal-head">
              <span className={dotClass(stream, !!taskId)} />
              <h3>{t("Generation Logs Title")}</h3>
              <span className="muted log-modal-status">
                {taskId ? logStatus(t, stream) : t("Generation Logs Empty")}
              </span>
              <button
                className="btn ghost log-modal-close"
                onClick={() => setOpen(false)}
                title={t("Close Generation Logs")}
              >
                ✕
              </button>
            </header>
            <LogLines
              boxRef={boxRef}
              lines={stream.lines}
              emptyText={taskId ? t("Log Waiting") : t("Generation Logs Empty")}
            />
          </section>
        </div>
      )}
    </>
  );
}
