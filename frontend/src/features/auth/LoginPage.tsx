import { useState, type FormEvent } from "react";
import { useSession } from "../../app/session";
import { ApiError } from "../../api/client";
import { navigate } from "../../app/router";

export function LoginPage() {
  const { login } = useSession();
  const [apiKey, setApiKey] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await login(apiKey);
      navigate("/");
    } catch (err) {
      setError(
        err instanceof ApiError && err.code === "invalid_api_key"
          ? "Invalid master key"
          : "Login failed"
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-wrap">
      <form className="card login" onSubmit={onSubmit}>
        <h1>Sign in</h1>
        <p className="muted">
          Enter the master key to exchange it for a short-lived session token.
        </p>
        <label>
          Master key
          <input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            autoFocus
          />
        </label>
        {error && <div className="error">{error}</div>}
        <button className="btn primary" disabled={busy || !apiKey}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
