# changofilm UI Migration: Streamlit → FastAPI + React + Vite

## Summary

The FastAPI backend already exists and serves the generation path (`/api/v1/videos`, `/audio`, `/subtitle`, `/script-plans`, `/tasks`, `/musics`, `/video_materials`, `/stream`, `/download`; static mounts `/tasks` and `/`). The migration therefore has exactly three workstreams: (1) complete the API surface that only Streamlit can reach today, (2) build the React SPA against codegen'd types from `app/models/schema.py`, (3) cut over after parity. The services layer (`app/services/*`, ~20k lines) is never modified except for one log-buffer extraction.

**Locked decisions**

| Decision | Choice | Rationale |
|---|---|---|
| Real-time logs | **SSE** (not WebSocket) | One-way flow; auth via `Authorization` header works with fetch-streaming (native `EventSource` cannot send headers); trivial reconnect |
| SPA routing | `BrowserRouter` + explicit SPA fallback route in `asgi.py` | `StaticFiles(html=True)` serves `index.html` only at `/`; a small fallback handler (serve index.html for non-`/api`, non-`/tasks`, non-file paths) is required — add to `asgi.py` |
| Build output | Vite `build.outDir = ../resource/public` | `utils.public_dir()` → `resource/public`, already mounted at `/` by `asgi.py` L317. Existing public assets (favicon etc.) move into `frontend/public/` so Vite copies them |
| Frontend location | `frontend/` top-level, single package (no pnpm workspace) | Repo is Python-centric; one package keeps tooling simple |
| Server state | TanStack Query v5 | Polling + SSE invalidation + cache |
| Params state | Zustand store (`stores/params.ts`) | One explicit assembler for all ~60 `VideoParams` fields — replaces the render-coupled assembly in the four Streamlit panel renderers |
| Design system | Port `docs/ui-redesign-demo/styles.css` token system + primitives | Already IA-matched (three-column shell, collapsible rails, dark/light, zh/en), verified 28/29 by Playwright harness |
| i18n | Reuse `webui/i18n/*.json` via a sync script (flattens the `"Translation"` nesting) | 14 languages, 800–1160 lines each — no retranslation |
| Legacy UI | Keep Streamlit runnable until Phase 3 soak completes | Regression safety net |
| Rejected | WebSocket, HashRouter, shadcn/ui, sharing changovideo Studio UI | WS is bidirectional overhead; hash routing is ugly in a product; shadcn conflicts with the existing verified token system; changovideo domain differs (ad-film vs series) and its UI source is not in this workspace |

---

## Part 1 — API Endpoint Inventory (Phase 0)

New routers under `app/controllers/v1/`, registered in `app/router.py`, all wrapped with `new_router(dependencies=[Depends(base.verify_token)])` like the existing ones.

### 1.1 Existing endpoints (unchanged, the React client consumes these in Phase 1)

- `POST /api/v1/videos` · `/audio` · `/subtitle` · `/script-plans` — task creation (`stop_at` pipeline)
- `GET /api/v1/tasks` · `GET /api/v1/tasks/{task_id}` · `DELETE /api/v1/tasks/{task_id}`
- `GET/POST /api/v1/musics` · `GET/POST /api/v1/video_materials`
- `GET|HEAD /api/v1/stream/{path}` (HTTP Range 206) · `GET|HEAD /api/v1/download/{path}`
- `POST /api/v1/scripts` · `/terms` · `/social-metadata` (llm.py)
- Static: `/tasks/**` artifacts (auth via middleware), `/` SPA (after migration)

### 1.2 `app/controllers/v1/streaming.py` — SSE task logs & state (replaces 0.5 s `st.fragment` polling)

- `GET /api/v1/tasks/{task_id}/events` → SSE stream: `state` events (from `app/services/state.py` snapshot) + `log` events. Heartbeat every 15 s; close on task terminal state.
- `GET /api/v1/tasks/{task_id}/logs?after=<seq>&tail=<n>` → REST fallback (paginated tail) for reconnect gap-fill.
- **Service extraction**: move the deque log capture + `get_task_logs()` from `app/services/webui_task.py` into a new `app/services/task_logs.py`; `webui_task.py` delegates to it (only non-UI-affecting change to the Streamlit path). Log routing already flows through `app/utils/logging_utils.runtime_log_filter`.
- **SSE auth**: fetch-streaming client with `Authorization` header — no query-param token (never put credentials in URLs).

### 1.3 `app/controllers/v1/settings.py` — settings editing (replaces the 7-tab settings dialog data layer)

Config sections confirmed at `app/config/config.py` L672–679: `app`, `whisper`, `proxy`, `azure`, `siliconflow`, `elevenlabs`, `chatterbox`.

- `GET /api/v1/settings/{section}` — section snapshot; **secret redaction**: `*_api_key`-shaped fields return `{configured: bool, masked: "sk-…3f2a"}` instead of raw values.
- `PUT /api/v1/settings/{section}` — partial update; key allowlist per section (reject unknown keys 400); writes via existing `config.update_config_values_nonblocking` (pending semantics preserved so mid-generation tasks keep their confirmed config snapshot).
- `GET /api/v1/settings/overview` — provider readiness. Port `webui/settings_providers.py` (`configured_llm_providers`, `configured_material_providers`) into `app/services/provider_readiness.py` and have both Streamlit and API call it — zero logic duplication.
- `POST /api/v1/settings/logging` — wraps `config.update_logging_options`.
- Key backup: `GET /api/v1/settings/keys/backup` (export JSON, secrets excluded/masked per `_collect_key_backup` behavior), `POST /api/v1/settings/keys/restore` (validates `keys` object like Main.py `_count_backup_keys` path).

### 1.4 `app/controllers/v1/oauth.py` — provider login flows

- `POST /api/v1/oauth/{provider}/start` → `{login_url, instructions}` (provider ∈ `chatgpt` | `codex` | `kimi`)
- `GET /api/v1/oauth/{provider}/status` → `{connected, account}` (reuse `codex_oauth.account_status()` etc. from `app/services/`)
- `POST /api/v1/oauth/{provider}/complete` — server-side completion of the flow currently implemented in `webui/chatgpt_login.py`, `webui/codex_login.py`, `webui/kimi_login.py` (move flow logic into the existing `app/services/*_oauth.py` modules; webui keeps calling them — no Streamlit regression).
- `GET /api/v1/oauth/{provider}/models` — model catalog (mirrors `webui/*_models.py`).

### 1.5 `app/controllers/v1/series.py` — series/episode management (thin wrapper over `app/services/series_store.py`, all 286 lines verified)

- `GET /api/v1/series` (list summaries) · `POST /api/v1/series` · `GET/PUT/DELETE /api/v1/series/{sid}`
- Characters: `GET/POST /api/v1/series/{sid}/characters`
- Reference images: `POST /api/v1/series/{sid}/characters/{cid}/images` (multipart → `add_reference_image`), `DELETE .../images/{name}` (`remove_reference_image`; human-lock → 409), `PUT .../images/{name}/lock` + `DELETE .../lock` (lock/unlock), `GET .../images/{name}` (serve file; resolve strictly inside `series_dir` — reuse `_safe_id` + path-containment check pattern from `_resolve_path_within_directory` in video.py)
- Episodes: `POST /api/v1/series/{sid}/episodes`, `PATCH /api/v1/series/{sid}/episodes/{eid}/status` (`set_episode_status`, forward-only state machine → 409 on illegal transition), `POST .../bind-plan` (`bind_episode_plan`)
- `Series` pydantic model already in `schema.py` → response models free via codegen.

### 1.6 `app/controllers/v1/publish.py` — publish panel

- `GET /api/v1/publish/history?limit=200` → `publish_history.list_publish_history()`
- `POST /api/v1/publish` `{task_id, platforms[], youtube_privacy_status?, youtube_made_for_kids?}` → manual/re-publish via the existing `task.py` cross-post scheduler (`_schedule_cross_post` contract verified)
- Queue view: `GET /api/v1/publish/queue` → active cross-post tasks projected from `state.py` (`cross_post_state/stage/progress/platform/log` fields already on task state) + zombie warnings from `publish_zombies.py`

### 1.7 `app/controllers/v1/uploads.py` — file uploads

- `POST /api/v1/uploads/voice-reference` (multipart audio) → server path token for `VideoParams` custom-voice fields (VoxCPM reference/prompt audio)
- `POST /api/v1/uploads/material` (multipart video/image) → `material_upload` service (already exists, 325 lines)
- All uploads: `file_security` boundary checks + size caps; return opaque stored-path identifiers usable in `VideoParams` — never raw client paths (server-side `allow_server_file_input` stays `False` for API-created tasks, matching `_run_pipeline` signature).

### 1.8 `app/controllers/v1/catalogs.py` + `cache.py` — read-only reference data

- `GET /api/v1/voices?language=` (voice catalog) · `GET /api/v1/llm-providers` (`LLM_PROVIDER_REGISTRY` metadata) · `GET /api/v1/video-sources` (`VIDEO_SOURCE_GROUPS` + readiness) · `GET /api/v1/fonts` (`font_dir` listing)
- `GET /api/v1/cache/stats` · `DELETE /api/v1/cache/{kind}` → wraps `app/services/cache_manager.py`
- Presets (params preset import/export from Main.py `_render_settings_transfer` L4133): `GET /api/v1/presets` · `POST /api/v1/presets` — JSON files under `storage/presets/`.

### 1.9 OpenAPI export

- `scripts/export_openapi.py`: imports `app.asgi.app`, writes `frontend/openapi.json`. Run via `pnpm gen:api` (invokes python then `openapi-typescript` + `orval`). `app/models/schema.py` becomes the single source of truth for the TS contract.

---

## Part 2 — React + Vite + TypeScript Scaffold

```
frontend/
├── package.json              # node >= 20, react 19, vite 6, ts 5.x
├── vite.config.ts            # outDir: ../resource/public; dev proxy /api,/tasks → localhost:8080
├── tsconfig*.json
├── index.html
├── .env.development          # VITE_API_BASE
├── openapi.json              # generated, committed for review diffs
├── orval.config.ts           # generates TanStack Query hooks + fetch client
├── public/                   # favicons, brand marks (moved from resource/public)
└── src/
    ├── api/
    │   ├── generated/        # openapi-typescript types + orval hooks (DO NOT hand-edit)
    │   ├── client.ts         # fetch wrapper: base URL, Authorization, {status,message,data} envelope unwrapping
    │   └── sse.ts            # fetch-stream SSE client (state+log events, auto-reconnect, gap-fill via /logs?after=)
    ├── app/
    │   ├── router.tsx        # TanStack Router: /, /series/:id, /tasks, /publish, /settings
    │   ├── providers.tsx     # QueryClient, Theme, I18n
    │   └── spaFallback note → implemented server-side in asgi.py
    ├── stores/
    │   └── params.ts         # Zustand: ALL ~60 VideoParams fields, single assembleVideoParams() — the explicit replacement of Streamlit's four-renderer assembly
    ├── features/
    │   ├── generate/         # ScriptPanel, VideoPanel, AudioPanel, SubtitlePanel, GenerateBar, VoicePreview, quote/charge confirm dialogs
    │   ├── logs/             # LogRail (SSE), ProgressStages, ResultActions
    │   ├── tasks/            # TaskTable, TaskDetail, RestoreDialog, VideoPreview
    │   ├── publish/          # PublishQueue, PublishHistory, RepublishDialog
    │   ├── series/           # SeriesList, EpisodesTab, CharactersTab, ReferenceImages
    │   ├── settings/         # per-section panels, ProviderReadiness badges, KeyBackup, Presets, CacheManager, BrandTheme
    │   └── oauth/            # OAuthProviderCards (chatgpt/codex/kimi)
    ├── i18n/                 # sync script output (flat keys), languages lazily loaded
    ├── theme/                # ported docs/ui-redesign-demo tokens (dark/light), brand.css
    └── components/ui/        # primitives ported from demo: Button, Select, Slider, Dialog, Tabs, Table, Toast
```

**Dev loop**: `uvicorn app.asgi:app --port 8080` + `vite dev` (proxy) → HMR. **Prod**: `vite build` → `resource/public` → uvicorn serves SPA + API same-origin (no CORS needed in product; `CORS_ALLOWED_ORIGINS` only for external frontends).

---

## Part 3 — Phases 0–3

### Phase 0 — API completion (backend only; Streamlit untouched)
1. `task_logs.py` extraction + SSE/REST streaming endpoints
2. `settings.py` router + redaction + `provider_readiness.py` port
3. `oauth.py`, `series.py`, `publish.py`, `uploads.py`, `catalogs.py`, `cache.py`, presets/keys endpoints
4. `scripts/export_openapi.py`; SPA fallback in `asgi.py`
5. pytest per router (patterns: `test/services/test_api_validation_message.py`; SSE via TestClient stream; **redaction test asserts no raw secret in any response**)
**Exit**: every WebUI data need is curl-able; openapi.json complete; existing Streamlit regression suite green.

### Phase 1 — Scaffold + core generation loop (demo-critical path)
1. Scaffold, codegen pipeline, theme port, i18n sync (zh/en), three-column shell from demo
2. `stores/params.ts` + four generate panels + GenerateBar
3. LogRail over SSE, task list/detail, video preview + download
**Exit**: SPA can configure → submit → stream logs → preview/download output, matching Streamlit on the same golden task.

### Phase 2 — Full feature parity
Settings (7 sections + readiness badges), OAuth cards, key backup, presets, series pages, publish panel, cache manager, voice preview, charge/quote confirms, brand theme, remaining 12 languages.
**Exit**: parity checklist (below) 100%.

### Phase 3 — Cutover + productization
1. `main.py` launcher: `changofilm web` (uvicorn + built SPA); `changofilm streamlit` kept
2. Docker multi-stage (node build → dist into resource/public → python runtime); update Dockerfile + docker-compose
3. Playwright e2e against built dist (reuse `.ui-demo-verify` harness patterns)
4. Two-week dual-UI soak → Streamlit marked legacy/hidden; removal decision after one stable release
5. Optional follow-up: Electron shell (pattern proven by changovideo desktop)

---

## Feature-Parity Checklist (verified Main.py seams)

| Area | Main.py seam | React target | Items |
|---|---|---|---|
| Top bar | `_render_application()` | Shell header | brand lockup, language select, settings entry, task-manager entry |
| Generate panels | 4 panel renderers → one VideoParams | `features/generate` + `stores/params.ts` | **all ~60 fields mapped** (incl. charge confirmations, uploads, quotes) |
| Pages | quick tabs (wizard/plan/series fallback) L12878+, pro tabs L13123 | Router pages | wizard, plan, series, script |
| Series | episodes + characters tabs L12418 | `features/series` | episodes (status machine), characters, reference images w/ lock |
| Settings dialog | 7 panels (general/llm/ai_video/ai_image/publish/interface/keys) L7061 | `features/settings` | every section's fields, readiness badges |
| Settings page | General/Interface/Key Backup/Cache/Brand Theme L12880 | Settings sub-pages | logging options, key backup export/restore, cache mgmt, theme |
| Presets | `_render_settings_transfer` L4133 | Presets page | export/import generation-parameter presets |
| Task manager | status tabs + table + zombies L1482–1896 | `features/tasks` | task table, per-status tabs, zombie warnings, restore dialog L2569, in-browser preview L1897 |
| Publish | queue L1713, history L1782 | `features/publish` | queue, history, re-publish |
| Generation UX | progress stages + logs (0.5 s polling) | LogRail + SSE | stage labels, streaming logs, result actions, voice preview |
| i18n | 14 languages under `"Translation"` | `src/i18n` | all 14 files synced; language switch re-renders logs/drawer (demo lesson) |
| Theme | `brand_theme.py` CSS vars | `theme/` | dark/light, brand tokens |

## Test Plan

- **Golden-payload regression**: run one identical task through Streamlit and React, diff the submitted `VideoParams` JSON — must be field-identical (guards the ~60-field assembly).
- Backend pytest for each Phase 0 router + redaction + SSE.
- Frontend: vitest for `assembleVideoParams`; Playwright e2e (dev + built dist).
- Parity walkthrough per checklist row with both UIs side by side.

## Assumptions

- Single-user/local + LAN posture unchanged (existing `api_key` auth; no new multi-tenant auth in this migration).
- changovideo Studio UI is pattern reference only (source not present in this workspace).
- Windows-first development; Docker build updated but optional locally.
- `app/services/*` pipeline code untouched except `webui_task.py` log-buffer delegation.
