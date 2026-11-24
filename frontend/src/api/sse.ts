// fetch-stream SSE client (migration 1.2 / 4). Native EventSource cannot attach an
// Authorization header, so we stream with fetch + ReadableStream and parse SSE frames.
// Reconnects automatically and back-fills any gap via GET /tasks/{id}/logs?after=<seq>.
import { V1 } from "./client";
import { getToken } from "../app/session";

export type SseHandlers = {
  onLog?: (seq: number, line: string) => void;
  onState?: (state: number, progress: number) => void;
  onEnd?: (state: number | null) => void;
};

type Frame = { id?: string; event: string; data: string };

function parseFrame(raw: string): Frame | null {
  const lines = raw.split("\n");
  let event = "message";
  let id: string | undefined;
  const dataLines: string[] = [];
  for (const line of lines) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("id:")) id = line.slice(3).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
    else if (line.startsWith(":")) continue; // comment / heartbeat
  }
  if (!dataLines.length && event === "message") return null;
  return { id, event, data: dataLines.join("\n") };
}

export function streamTaskEvents(
  taskId: string,
  handlers: SseHandlers,
  opts: { signal?: AbortSignal } = {}
): Promise<void> {
  let lastSeq = -1;

  async function once(): Promise<boolean> {
    const headers: Record<string, string> = {
      Accept: "text/event-stream",
    };
    const token = getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
    if (lastSeq >= 0) headers["Last-Event-ID"] = String(lastSeq);

    const res = await fetch(`${V1}/tasks/${taskId}/events`, {
      headers,
      signal: opts.signal,
    });
    if (!res.ok || !res.body) throw new Error(`SSE open failed: ${res.status}`);
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let sep;
      while ((sep = buffer.indexOf("\n\n")) !== -1) {
        const rawFrame = buffer.slice(0, sep);
        buffer = buffer.slice(sep + 2);
        const frame = parseFrame(rawFrame);
        if (!frame) continue;
        if (frame.id !== undefined) lastSeq = Number(frame.id);
        if (frame.event === "log") {
          try {
            const { line } = JSON.parse(frame.data);
            handlers.onLog?.(lastSeq, line);
          } catch {
            /* ignore malformed */
          }
        } else if (frame.event === "state") {
          const s = JSON.parse(frame.data);
          handlers.onState?.(s.state, s.progress);
        } else if (frame.event === "end") {
          const s = JSON.parse(frame.data);
          handlers.onEnd?.(s.state);
          return false; // terminal, do not reconnect
        }
      }
    }
    return true; // stream closed without terminal -> reconnect
  }

  async function run() {
    while (true) {
      try {
        const shouldReconnect = await once();
        if (!shouldReconnect) return;
      } catch (err) {
        if (opts.signal?.aborted) return;
      }
      if (opts.signal?.aborted) return;
      // back-fill the gap after reconnect using the REST fallback, then retry SSE
      try {
        const q = `/tasks/${taskId}/logs?after=${lastSeq}&tail=200`;
        const res = await fetch(`${V1}${q}`, {
          headers: authHeader(),
        });
        if (res.ok) {
          const body = await res.json();
          for (const item of body.data.items) {
            if (item.seq > lastSeq) {
              lastSeq = item.seq;
              handlers.onLog?.(item.seq, item.line);
            }
          }
        }
      } catch {
        /* best-effort gap fill */
      }
      await new Promise((r) => setTimeout(r, 1500));
    }
  }

  return run();
}

function authHeader(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}
