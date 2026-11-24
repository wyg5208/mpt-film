# React SPA 部署形态：Mode A 单源 / Mode B Vercel + 自有服务器

> 迁移方案第三部分的部署操作文档。前端为 `frontend/`（Vite + React 19 + TS），
> 唯一后端为 FastAPI（`app.asgi:app`），不采用 Next.js。

## Mode A：单源自托管（默认）

FastAPI 同源伺服 SPA 构建产物，无 CORS：

1. 构建并内嵌产物：`cd frontend && npm run build:embedded`
   （`vite build` → `dist/`，`scripts/embed-dist.mjs` 拷贝到 `resource/public/`）。
2. 启动：`python main.py web [--host 0.0.0.0] [--port 8080]`
   （uvicorn `app.asgi:app`；`/` 挂载 `resource/public`，非 `/api`、非 `/tasks`
   的 GET 404 由 `spa_history_fallback` 中间件回 `index.html`，BrowserRouter 深链接可用）。
3. 前端使用相对路径 `/api/v1/...`，同源，无需任何 CORS 配置。
4. Docker：多阶段构建（`node:20-slim` 构建阶段 → `build:embedded` → python 运行时），
   `docker compose up` 即可；`api` 服务命令为 `python3 main.py web`。

## Mode B：Vercel 静态前端 + 自有服务器后端

### Vercel 侧（只托管静态产物）

| 项 | 配置 |
|---|---|
| Root Directory | `frontend` |
| Framework Preset | Vite |
| Build Command | `npm run build` |
| Output Directory | `dist` |
| SPA fallback | `frontend/vercel.json` → `{"rewrites":[{"source":"/(.*)","destination":"/index.html"}]}` |
| 环境变量 | `VITE_API_BASE=https://api.你的域名`（`VITE_*` 会内联进公开产物，绝不能放密钥） |

### 后端（自有服务器）

- 域名 + TLS（Caddy 自动签发最省事）→ 反向代理 uvicorn。
- 必须配置 `config.toml` 的 `api_key`（Mode B 公网暴露不得免认证）。
- CORS 白名单：`CORS_ALLOWED_ORIGINS=https://你的应用.vercel.app,https://app.你的域名`。
  - `parse_cors_allowed_origins` 不支持通配符：`*.vercel.app` 会被丢弃并告警；
  - Vercel Preview 域名每次部署都变 → 使用独立 staging 后端，或把 preview 域名逐个加入白名单；
  - 浏览器 Origin 防护（`asgi.py` `is_browser_origin_allowed`）与 CORS 同源策略：
    未在白名单且非同源的浏览器请求一律 403。
- 鉴权流程：前端 `POST /api/v1/auth/login` 用主密钥换 15 分钟 Bearer 令牌
  （无状态 HMAC，见迁移方案 4.B）；主密钥只出现在登录请求一次，不落 `localStorage`。

### 反向代理要点

- SSE（`GET /api/v1/tasks/{id}/events`）：
  `proxy_buffering off; proxy_cache off;`，读超时 ≥ 3600s；服务端每 15 秒发心跳
  （Cloudflare 等边缘层 100 秒空闲超时，心跳是唯一防线）。响应已带
  `X-Accel-Buffering: no`，nginx 默认可直接继承。
- 媒体：`/tasks/**` 走短时签名 URL（`POST /api/v1/media/sign`），保留 Range 206 拖动；
  反代不要缓冲/缓存该路径（`Cache-Control: private, max-age=<剩余TTL>` 由后端设置）。
- 上传：反代层与应用层同时设置体积上限（如 `client_max_body_size 512m`），
  避免大文件打满后端内存。
- 静态资源缓存：`/api/v1/*` 与 `/tasks/*` 一律 `Cache-Control: private, no-store`
  （签名媒体 URL 除外）。
- 登录端点限流：主密钥可被暴力猜测（`compare_digest` 只防时序侧信道，不限速），
  nginx 示例：

  ```nginx
  limit_req_zone $binary_remote_addr zone=login:10m rate=5r/m;
  location = /api/v1/auth/login { limit_req zone=login burst=3 nodelay; proxy_pass http://uvicorn; }
  ```

## 验证

- Mode A：`npm run e2e`（Playwright built-dist 形态，10 用例）+ `npm run e2e:dev`（dev-server 形态）。
- Mode B 冒烟：设置 `CORS_ALLOWED_ORIGINS` 为前端源后，
  `curl -H "Origin: https://你的应用.vercel.app" https://api.域名/api/v1/ping` 应返回
  `Access-Control-Allow-Origin` 回显；跨源登录 → 任务列表 → 签名媒体 → SSE 全链路
  对应 pytest：`test/services/test_asgi_cors.py`、`test_auth_tokens.py`、`test_media_sign.py`、
  `test_sse_logs_stream.py`。
