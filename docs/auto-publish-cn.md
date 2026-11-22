# Auto-Publishing to Domestic Platforms

ChangoFilm can automatically publish generated videos to **Douyin (抖音),
WeChat Channels (视频号), Xiaohongshu (小红书) and Bilibili (B站)** through the
free, MIT-licensed [social-auto-upload](https://github.com/dreammis/social-auto-upload)
CLI (`sau`). Kuaishou, Weibo and Baijiahao are optional extra platforms.

The existing Upload-Post integration remains available as an **optional overseas
channel** (TikTok / Instagram / YouTube). Its free plan allows 10 uploads per
month with 2 profiles and full API access.

Publishing never blocks or alters video generation: the video task completes
first, then a background cross-post job uploads the outputs. A full publish
queue degrades to a queryable `failed` publish state, not a generation failure.

For the full troubleshooting story behind these behaviors (risk control, draft
restoration, browser identity, QR login and toolchain-download pitfalls), see
[auto-publish-lessons.md](auto-publish-lessons.md) (Chinese).

## 1. Install social-auto-upload (one-time)

Install it in its own environment — ChangoFilm calls it as an external
subprocess and gains no new Python dependencies.

```bash
git clone https://github.com/dreammis/social-auto-upload
cd social-auto-upload
uv venv
uv pip install -e .
copy conf.example.py conf.py   # required: the CLI imports conf at startup
```

If GitHub is slow on your network, a working proxy clone is
`git clone https://gitclone.com/github.com/dreammis/social-auto-upload`.
Do **not** use the Gitee mirror `wanxiang-open-source/social-auto-upload`: it
is a legacy snapshot without the `sau` CLI and without Xiaohongshu/Bilibili
support. For slow PyPI access, add
`--default-index https://pypi.tuna.tsinghua.edu.cn/simple` to `uv pip install`.

Install the browser (the project uses the `patchright` Playwright fork):

```bash
patchright install chromium
```

In mainland China, first try the npmmirror host:

```bash
set PLAYWRIGHT_DOWNLOAD_HOST=https://cdn.npmmirror.com/binaries/playwright
patchright install chromium
```

If the mirror returns 404 for the required Chrome-for-Testing revision, fetch
the same asset from the npmmirror `chrome-for-testing` category
(`https://registry.npmmirror.com/-/binary/chrome-for-testing/<version>/win64/chrome-win64.zip`)
and extract it into `<browsers-dir>/chromium-<revision>/` (plus
`chrome-headless-shell-win64.zip` into `chromium_headless_shell-<revision>/`),
then create an empty `INSTALLATION_COMPLETE` file in each folder. The required
version/revision are printed by `patchright install chromium --dry-run`.

When browsers live outside the default location, either fill the **Browser
Directory (PLAYWRIGHT_BROWSERS_PATH)** field under Settings → Auto-Publish →
Advanced, or set the `PLAYWRIGHT_BROWSERS_PATH` environment variable in the
environment that starts ChangoFilm. Publishing and session checks inject
the variable into the `sau` subprocess automatically, with the priority
**UI field > system environment variable > bundled `opensources/pw-browsers`**
(used when that folder exists), so no `setx` or WebUI restart is needed for
publishing. Manual `sau ... login` commands in a terminal still rely on the
environment variable (or the default browser location).

## 2. Log in to each platform (one-time, real terminal)

QR-code login must happen in a real interactive terminal, not in the WebUI:

```bash
sau douyin login --account default
sau tencent login --account default      # WeChat Channels
sau xiaohongshu login --account default
sau bilibili login --account default
```

`default` is a local session alias; use different aliases for multiple accounts.
Verify sessions at any time:

```bash
sau douyin check --account default
```

The WebUI publish settings also provide a **Check login sessions** button that
runs these checks and shows the exact re-login command for any expired session.

## 3. Configure ChangoFilm

Open **Settings → Auto-Publish**. The domestic section is the primary area:

| Setting | Key | Default |
| --- | --- | --- |
| Enable domestic publishing | `social_publish_enabled` | `false` |
| Auto-publish after generation | `social_publish_auto_upload` | `false` |
| Account name (session alias) | `social_publish_account` | `"default"` |
| Platforms | `social_publish_platforms` | `["douyin", "tencent", "xiaohongshu", "bilibili"]` |
| Bilibili partition id (tid) | `social_publish_bilibili_tid` | `21` (Daily Life) |
| sau CLI path | `sau_cli_path` | `"sau"` |
| Browser directory | `social_publish_browsers_path` | `""` (auto) |
| Show browser window (headed) | `social_publish_headed` | `true` |

With the default `sau_cli_path = "sau"`, the service looks the executable up on
PATH and then falls back to the bundled install at
`opensources/social-auto-upload/.venv/Scripts/sau.exe` automatically. Set an
absolute path only when sau is installed elsewhere, e.g.
`D:\social-auto-upload\.venv\Scripts\sau.exe`.

Both switches are independent: `enabled` allows publishing calls, while
`auto_upload` decides whether finished videos are published automatically.

The overseas Upload-Post section is collapsed below it and keeps its previous
keys (`upload_post_*`). The two channels can run in the same task; results are
merged into one publish state.

## 4. How publishing works

1. Video generation completes and the task is marked complete.
2. A background cross-post job is queued (bounded by
   `upload_post_max_pending_tasks`, shared by both channels).
3. For each domestic platform, titles/captions/hashtags are generated with the
   platform's own length limits (e.g. Douyin title ≤ 30 chars, WeChat Channels
   title 6–16 chars, Xiaohongshu title ≤ 20 chars).
4. `sau <platform> upload-video` runs sequentially per platform with a 30-minute
   timeout; on timeout the whole browser process tree is cleaned up. Uploads
   run **headed by default** (`--headed`): a visible browser window lets you
   watch the automation and manually handle captchas/SMS checks, and domestic
   platforms are less likely to flag headless browsers. Disable the toggle only
   on servers without a desktop. Bilibili uses biliup (no browser) and is
   unaffected.
5. The task card shows the publish state plus per-platform badges
   (e.g. `Publish: complete · 抖音✅ 视频号✅ 小红书❌ B站✅`). While running it
   also shows a percentage and the current stage (queued / generating caption /
   uploading). The percentage is coarse — it advances per platform×video upload
   unit, because the `sau` subprocess exposes no fine-grained progress; the live
   log tail fills in the details.

Completed tasks can be published at any time via the **Publish Now** button in
the task manager (works even after a restart). Publishing is automatically
queued: if another publish is already running, the new job waits in line (2
concurrent workers, bounded queue). Re-triggering the same task while it is
queued or running is rejected as a duplicate.

The **Publish Queue** panel at the top of the task manager lists running and
waiting publishes with queue positions, a progress bar and an expandable live
log tail (last lines of the `sau` output); it refreshes every 2 seconds.

The task manager also shows a **zombie publish warning panel** when it finds
orphaned `sau.exe` publish trees left over from a previous WebUI session
(their parent process has exited). Each row shows the title, platform,
account, PID and how long the process has been alive, with a **Kill** button
per row and a **Kill all** button; killing removes the whole process tree
(browser included) after re-verifying the process command line, and never
touches video files. Live publishes of the current session and manual runs
in a terminal are never flagged.

The **Publish History** tab in the task manager keeps a durable record of every
publish attempt — both automatic (post-generation) and manual (Publish Now /
Republish). Each row shows the video subject and files, finish time, trigger
type, per-platform results, duration and the failure reason if any, plus a
**Republish** button that re-queues the task through the same state machine.
Records are appended to `storage/publish_history.jsonl` and survive restarts;
queue-full and scheduling failures are recorded too.

Account settings are snapshotted when the job is queued; changing the WebUI
afterwards does not affect already-queued publishes.

## 5. Troubleshooting

| Symptom | Cause / remedy |
| --- | --- |
| `sau ... exited with code ...` mentioning login | Session expired. Re-run `sau <platform> login --account <name>` in a terminal, or use the WebUI session check to get the exact command. |
| Douyin asks for an SMS code | Put the code into `verify_code.txt` in the social-auto-upload folder (upstream convention), or run the upload manually in a terminal. |
| `social-auto-upload CLI not found` | Install sau under `opensources/social-auto-upload` (auto-detected), or set the absolute `sau_cli_path` in Advanced settings. |
| Publish state `failed` with "queue is full" | Too many pending publish jobs. Generation still succeeded; retry later. |
| Publish state `failed` after a restart | Publish jobs live in the current process and are not resumed after restart; the videos are intact and can be published again. |
| Publish stuck at a low percentage, log shows upload retries | Watch the visible browser window: a captcha/SMS check may need manual handling. Also make sure only one publish runs per account — an orphaned `sau.exe` from a previous WebUI session keeps uploading in the background; the task manager's zombie publish panel detects it and offers a one-click Kill (whole process tree). |
| Platform rejects the upload or shows a captcha | Risk control. Keep a visible (headed) browser on a desktop machine, publish at low frequency, and avoid headless cloud servers. |
| Bilibili rejects the partition | Change `social_publish_bilibili_tid` to a partition that matches the content (see the biliup partition list). |

## 6. Deployment notes

- Domestic platforms expose no usable official upload API for individual
  creators; browser automation with persisted cookie sessions is the standard
  approach, so a desktop session on the publishing machine is required.
- Keep the social-auto-upload checkout pinned to a release; platform UI changes
  are fixed upstream — update via its CHANGELOG when selectors break. The
  bundled checkout carries a local Douyin robustness patch
  (`uploader/douyin_uploader/main.py`): guide-overlay dismissal, acceptance of
  the draft edit page (`enter_from=draft`) with automatic video re-injection
  when no upload progress exists, navigation back to the upload page when
  kicked out, a parsing-aware title-form wait (up to 6 minutes while Douyin
  shows "上传解析中"), and explicit deadlines instead of infinite waits.
  Uploads also run under a real-user browser identity: a persistent per-account
  profile (`browser_profiles/<account>/`, shared between manual intervention and
  automation), zh-CN locale/languages and Asia/Shanghai timezone. The same
  profile cannot be opened by two browsers at once, so concurrent publishes on
  one account fail fast by design. The Tencent (视频号) launcher likewise falls
  back to the bundled chromium instead of requiring a system Google Chrome
  install. The Xiaohongshu login QR panel is activated state-driven (visible
  img with non-empty src) instead of by text presence, so phone-login mode no
  longer leaves the QR collapsed. The biliup runtime downloader retries and
  falls back to GitHub mirrors (override with `SAU_GITHUB_MIRRORS`), verifying
  every mirror download against the official GitHub API sha256 digest;
  mirrors are only used when that digest is available. Re-check these behaviors when updating
  upstream.
- Xigua Video (西瓜视频) is intentionally not covered.