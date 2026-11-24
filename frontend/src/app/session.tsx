// Session state: short-lived Bearer token kept in memory + sessionStorage
// (tab close invalidates it). The master key is NEVER persisted to localStorage
// and is dropped immediately after login (migration 4.B).
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { api, login as apiLogin } from "../api/client";

const TOKEN_KEY = "cf_token";
const EXP_KEY = "cf_exp";

// memory mirror so a hard refresh still keeps the current-tab token via sessionStorage
let memoryToken: string | null =
  typeof sessionStorage !== "undefined" ? sessionStorage.getItem(TOKEN_KEY) : null;

export function getToken(): string | null {
  return memoryToken;
}

export function setToken(token: string, expiresAt?: number) {
  memoryToken = token;
  sessionStorage.setItem(TOKEN_KEY, token);
  if (expiresAt) sessionStorage.setItem(EXP_KEY, String(expiresAt));
}

export function clearToken() {
  memoryToken = null;
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(EXP_KEY);
}

export function getMasterKeyOnce(): null {
  // Intentionally always null: we never retain the master key anywhere.
  return null;
}

export function getExpiresAt(): number | null {
  const v = sessionStorage.getItem(EXP_KEY);
  return v ? Number(v) : null;
}

type SessionState = {
  ready: boolean;
  authRequired: boolean;
  valid: boolean;
  login: (apiKey: string) => Promise<void>;
  logout: () => Promise<void>;
};

const SessionContext = createContext<SessionState | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [authRequired, setAuthRequired] = useState(true);
  const [valid, setValid] = useState(false);

  const probe = useCallback(async () => {
    try {
      const data = await api.get<{
        valid: boolean;
        auth_required: boolean;
      }>("/auth/session");
      setValid(!!data.valid);
      setAuthRequired(!!data.auth_required);
    } catch {
      setValid(false);
      setAuthRequired(true);
    } finally {
      setReady(true);
    }
  }, []);

  useEffect(() => {
    probe();
    // proactive refresh at ~80% of token lifetime (migration 4.B step 6)
    const id = setInterval(async () => {
      const exp = getExpiresAt();
      if (!exp) return;
      const now = Date.now() / 1000;
      const lifetime = 900;
      if (exp - now < lifetime * 0.2) {
        try {
          await api.post("/auth/refresh");
        } catch {
          /* handled on next 401 */
        }
      }
    }, 60_000);
    return () => clearInterval(id);
  }, [probe]);

  const login = useCallback(
    async (apiKey: string) => {
      await apiLogin(apiKey);
      setValid(true);
      setAuthRequired(true);
    },
    []
  );

  const logout = useCallback(async () => {
    try {
      await api.post("/auth/logout");
    } catch {
      /* ignore */
    }
    clearToken();
    setValid(false);
  }, []);

  return (
    <SessionContext.Provider
      value={{ ready, authRequired, valid, login, logout }}
    >
      {children}
    </SessionContext.Provider>
  );
}

export function useSession(): SessionState {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession outside provider");
  return ctx;
}
