// Tracks the most recent submitted task so the shell's right-hand log rail can
// stream it across navigation (the Streamlit generation-log column is persistent
// chrome, not part of any single page). Persisted in sessionStorage and broadcast
// via a window event so the rail picks it up without a router-level store.
const KEY = "cf_current_task";
const EVENT = "cf-current-task";

export function setCurrentTask(taskId: string) {
  sessionStorage.setItem(KEY, taskId);
  window.dispatchEvent(new Event(EVENT));
}

export function getCurrentTask(): string {
  return sessionStorage.getItem(KEY) ?? "";
}

export function onCurrentTaskChange(cb: (id: string) => void): () => void {
  const handler = () => cb(getCurrentTask());
  window.addEventListener(EVENT, handler);
  return () => window.removeEventListener(EVENT, handler);
}
