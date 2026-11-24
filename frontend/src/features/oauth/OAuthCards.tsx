// Provider login cards (migration Part 6 设置页/OAuth): orchestrates the
// server-side start/complete/status flow from app/controllers/v1/oauth.py.
// Tokens never reach the browser — only connected state and account summaries.
import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "../../api/client";
import { useI18n } from "../../i18n";

type Provider = "chatgpt" | "codex" | "kimi";
const PROVIDERS: Provider[] = ["chatgpt", "codex", "kimi"];

type StartResponse = {
  login_url: string;
  instructions: string;
  flow: Record<string, unknown>;
};

type StatusResponse = {
  connected: boolean;
  account?: Record<string, unknown> | null;
};

function OAuthCard({ provider }: { provider: Provider }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [start, setStart] = useState<StartResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const timer = useRef<number | null>(null);

  const status = useQuery({
    queryKey: ["oauth", provider, "status"],
    queryFn: () => api.get<StatusResponse>(`/oauth/${provider}/status`),
  });

  useEffect(() => () => {
    if (timer.current) window.clearTimeout(timer.current);
  }, []);

  async function begin() {
    setBusy(true);
    setMessage("");
    try {
      const data = await api.post<StartResponse>(`/oauth/${provider}/start`);
      setStart(data);
      poll(data);
    } catch (err) {
      setMessage(err instanceof ApiError ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  function poll(data: StartResponse) {
    const interval = Math.max(Number(data.flow.interval ?? 0) || 0, 2) * 1000;
    timer.current = window.setTimeout(async () => {
      try {
        const done = await api.post<{ connected: boolean }>(
          `/oauth/${provider}/complete`,
          { flow: data.flow }
        );
        if (done.connected) {
          setStart(null);
          setMessage(t("Login successful"));
          qc.invalidateQueries({ queryKey: ["oauth", provider, "status"] });
          qc.invalidateQueries({ queryKey: ["settings", "overview"] });
          return;
        }
      } catch (err) {
        setStart(null);
        setMessage(err instanceof ApiError ? err.message : String(err));
        return;
      }
      poll(data);
    }, interval);
  }

  const connected = !!status.data?.connected;
  return (
    <div className="card oauth-card" data-testid={`oauth-${provider}`}>
      <div className="oauth-head">
        <strong>{provider}</strong>
        <span className={connected ? "badge ok" : "badge"}>
          {connected ? t("Connected") : t("Not connected")}
        </span>
      </div>
      {connected && status.data?.account ? (
        <pre className="account">{JSON.stringify(status.data.account, null, 2)}</pre>
      ) : null}
      {start ? (
        <div className="oauth-flow">
          <a href={start.login_url} target="_blank" rel="noreferrer noopener">
            {t("Open login page")}
          </a>
          {start.flow.user_code ? (
            <p>
              {t("Code")}: <code>{String(start.flow.user_code)}</code>
            </p>
          ) : null}
          <p className="muted">{start.instructions}</p>
        </div>
      ) : (
        <button className="btn" onClick={begin} disabled={busy}>
          {busy ? t("Starting…") : t("Sign in")}
        </button>
      )}
      {message && <p className="muted">{message}</p>}
    </div>
  );
}

export function OAuthCards() {
  return (
    <div className="oauth-grid">
      {PROVIDERS.map((p) => (
        <OAuthCard key={p} provider={p} />
      ))}
    </div>
  );
}
