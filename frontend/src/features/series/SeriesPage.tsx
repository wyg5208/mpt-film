// Series page (migration Part 6 系列): series list + detail with the episode
// forward-only state machine (draft→confirmed→rendered, invalid → 409) and
// character reference images including the human-lock semantics (locked
// delete → 409). Backs app/controllers/v1/series.py.
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "../../api/client";
import { apiBase as envBase } from "../../api/env";
import { getToken } from "../../app/session";
import { useI18n } from "../../i18n";
import { navigate } from "../../app/router";

type Character = {
  id: string;
  name: string;
  role: string;
  appearance_prompt: string;
  reference_images: string[];
  seed: number;
  voice_name: string;
  personality: string;
};
type Episode = {
  id: string;
  seq: number;
  title: string;
  logline: string;
  hook: string;
  plan_id: string | null;
  status: "draft" | "confirmed" | "rendered";
};
type Series = {
  id: string;
  title: string;
  genre_template: string;
  style_bible: Record<string, string>;
  characters: Character[];
  episodes: Episode[];
};

const NEXT_STATUS: Record<Episode["status"], Episode["status"] | null> = {
  draft: "confirmed",
  confirmed: "rendered",
  rendered: null,
};

function SeriesDetail({ sid }: { sid: string }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [tab, setTab] = useState<"episodes" | "characters">("episodes");
  const [error, setError] = useState("");
  const [newEpisode, setNewEpisode] = useState({ title: "", logline: "", hook: "" });
  const [newChar, setNewChar] = useState({ name: "", role: "support", appearance_prompt: "" });

  const query = useQuery({
    queryKey: ["series", sid],
    queryFn: () => api.get<Series>(`/series/${sid}`),
  });

  function fail(err: unknown) {
    setError(err instanceof ApiError ? err.message : String(err));
  }

  const mutate = <T,>(fn: () => Promise<T>) => () =>
    fn().then(
      () => qc.invalidateQueries({ queryKey: ["series", sid] }),
      fail
    );

  if (query.isLoading)
    return (
      <div className="series-detail" data-testid="series-detail">
        <p className="muted">{t("Loading…")}</p>
      </div>
    );
  if (query.error)
    return (
      <div className="series-detail" data-testid="series-detail">
        <p className="error">{String(query.error.message)}</p>
      </div>
    );
  const series = query.data!;

  return (
    <div className="series-detail" data-testid="series-detail">
      <div className="row">
        <button className="btn ghost" onClick={() => navigate("/series")}>
          ← {t("Back")}
        </button>
        <h2>{series.title || series.id}</h2>
        <em className="muted">{series.genre_template}</em>
      </div>
      <div className="tabs">
        <button className={tab === "episodes" ? "tab active" : "tab"} onClick={() => setTab("episodes")}>
          {t("Episodes")}
        </button>
        <button className={tab === "characters" ? "tab active" : "tab"} onClick={() => setTab("characters")}>
          {t("Characters")}
        </button>
      </div>
      {error && <p className="error">{error}</p>}

      {tab === "episodes" ? (
        <div data-testid="episodes-tab">
          <table className="table">
            <thead>
              <tr>
                <th>#</th>
                <th>{t("Title")}</th>
                <th>{t("Status")}</th>
                <th>{t("Plan")}</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {series.episodes.map((ep) => {
                const next = NEXT_STATUS[ep.status];
                return (
                  <tr key={ep.id} data-testid={`episode-${ep.seq}`}>
                    <td>{ep.seq}</td>
                    <td>{ep.title}</td>
                    <td>
                      <span className={`badge ${ep.status}`}>{ep.status}</span>
                    </td>
                    <td>{ep.plan_id ?? "—"}</td>
                    <td>
                      {next ? (
                        <button
                          className="btn"
                          onClick={mutate(() =>
                            api.patch(`/series/${sid}/episodes/${ep.id}/status`, {
                              status: next,
                            })
                          )}
                        >
                          {t("Advance")}
                        </button>
                      ) : null}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <div className="row">
            <input
              placeholder={t("Episode title")}
              value={newEpisode.title}
              onChange={(e) => setNewEpisode({ ...newEpisode, title: e.target.value })}
            />
            <button
              className="btn primary"
              disabled={!newEpisode.title.trim()}
              onClick={mutate(() => api.post(`/series/${sid}/episodes`, newEpisode))}
            >
              {t("Add episode")}
            </button>
          </div>
        </div>
      ) : (
        <div data-testid="characters-tab">
          {series.characters.map((ch) => (
            <div key={ch.id} className="card" data-testid={`character-${ch.id}`}>
              <strong>{ch.name || ch.id}</strong> <em className="muted">{ch.role}</em>
              <p>{ch.appearance_prompt}</p>
              <div className="ref-images">
                {ch.reference_images.map((img) => {
                  const name = img.split(/[\\/]/).pop()!;
                  return (
                    <span key={img} className="ref-image">
                      <AuthImage
                        url={`${apiBase()}/series/${sid}/characters/${ch.id}/images/${encodeURIComponent(name)}`}
                        alt={name}
                      />
                      <button
                        className="btn ghost"
                        title={t("Remove")}
                        onClick={mutate(() =>
                          api.del(`/series/${sid}/characters/${ch.id}/images/${encodeURIComponent(name)}`)
                        )}
                      >
                        ✕
                      </button>
                    </span>
                  );
                })}
                <UploadImage sid={sid} cid={ch.id} onDone={() => qc.invalidateQueries({ queryKey: ["series", sid] })} onError={fail} />
              </div>
            </div>
          ))}
          <div className="row">
            <input
              placeholder={t("Character name")}
              value={newChar.name}
              onChange={(e) => setNewChar({ ...newChar, name: e.target.value })}
            />
            <select value={newChar.role} onChange={(e) => setNewChar({ ...newChar, role: e.target.value })}>
              <option value="protagonist">protagonist</option>
              <option value="support">support</option>
              <option value="extra">extra</option>
            </select>
            <button
              className="btn primary"
              disabled={!newChar.name.trim()}
              onClick={mutate(() => api.post(`/series/${sid}/characters`, newChar))}
            >
              {t("Add character")}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function apiBase(): string {
  return `${envBase()}/api/v1`;
}

// Reference images live behind verify_token; <img> cannot carry the Bearer
// header, so fetch through the authenticated client as a blob object URL.
function AuthImage({ url, alt }: { url: string; alt: string }) {
  const [src, setSrc] = useState<string | null>(null);
  useEffect(() => {
    let revoked = "";
    let alive = true;
    (async () => {
      const token = getToken();
      const res = await fetch(url, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok || !alive) return;
      revoked = URL.createObjectURL(await res.blob());
      if (alive) setSrc(revoked);
    })();
    return () => {
      alive = false;
      if (revoked) URL.revokeObjectURL(revoked);
    };
  }, [url]);
  return src ? <img src={src} alt={alt} /> : null;
}

function UploadImage({
  sid,
  cid,
  onDone,
  onError,
}: {
  sid: string;
  cid: string;
  onDone: () => void;
  onError: (err: unknown) => void;
}) {
  const { t } = useI18n();
  return (
    <label className="btn ghost upload-image" data-testid={`upload-${cid}`}>
      {t("Upload image")}
      <input
        type="file"
        accept=".png,.jpg,.jpeg,.webp"
        hidden
        onChange={async (e) => {
          const file = e.target.files?.[0];
          if (!file) return;
          const form = new FormData();
          form.append("file", file);
          try {
            const token = getToken();
            await fetch(`${apiBase()}/series/${sid}/characters/${cid}/images`, {
              method: "POST",
              headers: token ? { Authorization: `Bearer ${token}` } : {},
              body: form,
            }).then(async (res) => {
              if (!res.ok) {
                const body = await res.json().catch(() => null);
                throw new ApiError(res.status, body?.message ?? res.statusText, body?.data?.code);
              }
              onDone();
            });
          } catch (err) {
            onError(err);
          }
          e.target.value = "";
        }}
      />
    </label>
  );
}

export function SeriesPage({ sid }: { sid?: string }) {
  // Split into distinct child components: when the route swaps list↔detail the
  // reconciler must see different component types, otherwise SeriesPage would
  // change its own hook count mid-life (useQuery skipped by the early return)
  // and React unmounts the whole tree on navigate(`/series/${id}`).
  return sid ? <SeriesDetail sid={sid} /> : <SeriesListView />;
}

function SeriesListView() {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [title, setTitle] = useState("");
  const [genre, setGenre] = useState("custom");
  const [error, setError] = useState("");

  const query = useQuery({
    queryKey: ["series"],
    queryFn: () =>
      api.get<{ series: { id: string; title: string; genre_template?: string }[] }>("/series"),
  });

  return (
    <div className="series-page" data-testid="series-list">
      <h2>{t("Series")}</h2>
      {error && <p className="error">{error}</p>}
      <div className="row">
        <input
          placeholder={t("Series title")}
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />
        <select value={genre} onChange={(e) => setGenre(e.target.value)}>
          {["custom", "urban_revenge", "period_romance", "suspense", "healing", "scifi"].map(
            (g) => (
              <option key={g} value={g}>
                {g}
              </option>
            )
          )}
        </select>
        <button
          className="btn primary"
          disabled={!title.trim()}
          onClick={() =>
            api
              .post<Series>("/series", { title: title.trim(), genre_template: genre })
              .then((s) => {
                setTitle("");
                qc.invalidateQueries({ queryKey: ["series"] });
                navigate(`/series/${s.id}`);
              })
              .catch((err) => setError(err instanceof ApiError ? err.message : String(err)))
          }
        >
          {t("New series")}
        </button>
      </div>
      <table className="table">
        <tbody>
          {(query.data?.series ?? []).map((s) => (
            <tr key={s.id}>
              <td>
                <a href={`/series/${s.id}`} onClick={(e) => { e.preventDefault(); navigate(`/series/${s.id}`); }}>
                  {s.title || s.id}
                </a>
              </td>
              <td className="muted">{s.genre_template ?? ""}</td>
              <td>
                <button
                  className="btn ghost"
                  onClick={() =>
                    api
                      .del(`/series/${s.id}`)
                      .then(() => qc.invalidateQueries({ queryKey: ["series"] }))
                      .catch((err) => setError(String(err)))
                  }
                >
                  {t("Delete")}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
