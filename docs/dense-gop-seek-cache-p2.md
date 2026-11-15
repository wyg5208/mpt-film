# P2 design: dense-GOP fast seeking, ported from OpenFilm

Status: design for the deferred P2 ("快进友好 GOP") item of
[deterministic-review-plan.md](deterministic-review-plan.md) §6. The mechanism below was
traced from the local OpenFilm checkout (`opensources/openfilm/packages/openfilm/src/`) on
2026-11-09 and verified against the real-footage project `opensources/films/media`.

## 1. The problem, measured on MPT

MPT re-encodes everything with libx264 defaults and never passes `-g`. libx264's default
GOP is 250 frames with scene-cut detection on; for a near-static zoom render this means one
keyframe per file:

* `render_image_zoom_video` (app/services/video.py:2053) writes a 5 s @ 30 fps clip via
  `final_clip.write_videofile(temp_path, fps=30, ffmpeg_params=_BT709_FFMPEG_PARAMS)`.
  Measured on the audited fixtures: **`keyframes=1` on all five sources** — ffmpeg can only
  land a seek at t=0 and must then decode forward.
* `concat_video_clips_with_ffmpeg.build_command` (app/services/video.py:661) likewise passes
  `-c:v codec -threads -vf … -pix_fmt yuv420p` with no `-g`, so the combined output and the
  per-clip temp mp4s inherit the same sparse structure.
* Every source read goes through MoviePy 2.2.1's `FFMPEG_VideoReader.initialize`
  (.venv/Lib/site-packages/moviepy/video/io/ffmpeg_reader.py:113): for a start time it spawns
  `ffmpeg -ss (t-1s) -i file -ss 1s …` — the input-side `-ss` keyframe-seeks to ≤ 1 s before
  the target (or the last keyframe if the file has only one), then the output-side `-ss`
  decodes and discards forward. On a single-keyframe 5 s clip, starting the clip at t≈4 s
  decodes ~4 s of frames just to begin; on a long sparse-GOP stock video each
  `subclipped(start, end)` pays from the previous keyframe (cameras/stock: one every 1–4 s).
* `review.py` decodes whole files sequentially; its cost also grows with distance between
  keyframes whenever it restarts a decode pass.

OpenFilm solved exactly this problem for its render browser. Its design transfers cleanly.

## 2. OpenFilm's mechanism (traced)

All of it lives in `packages/openfilm/src/seekable.mjs`, consumed by `render.mjs` and served
by `host.mjs`.

### 2.1 Deciding whether a copy is needed — `copyNeed` / `slowSeeking`

Two independent triggers:

* **`unplayable`**: codec is not in the `decodedAnywhere` list (H.264 8-bit 4:2:0, VP8/VP9/AV1)
  and the render's own browser fails `firstFrame` — a real `<video>` probe, because
  `loadeddata` fires even when the decoder produces no picture (ProRes, HEVC without a chip).
* **`slow`** (`slowSeeking`): ffprobe reads (does not decode) packet flags of the first 20 s;
  if `span / keyframes > SLOW_GOP_S = 0.5 s`, the file seeks too slowly. Gates: only
  `yuv420p`/`yuvj420p` without alpha, ≤ 10 min, sides ≤ 4096.

`render.mjs:185` asks for the `slow` trigger only when the render is long enough to care
(`slow: total >= fps * 2`, i.e. ≥ 2 s); `look` passes `slow:false`, which is why a
sparse-GOP source may produce no copy until the first real render
(`films/media/sparse.out` records exactly this).

### 2.2 The key — content identity, versioned

```js
// seekable.mjs:124
join(root, '.film', 'cache', 'seek', hash(Buffer.from(`${VERSION}\0${file}\0${stat.size}\0${stat.mtimeMs}`)))
// hash = sha1, first 12 hex chars (shared.mjs)
```

`VERSION = 3` bumps whenever *how* copies are made changes (v3: an HEVC/VP9 alpha layer was
being dropped). Cache validity needs no purge: a touched file changes size/mtimeMs → new key;
a changed algorithm → new VERSION → every old key is orphaned harmlessly. An in-process map
(`found`, seekable.mjs:127) memoizes hits indefinitely and misses for 2 s, because the server
asks on every HTTP range request the playing video makes.

### 2.3 Generation — `makeCopy`

* GOP of the copy: `gop = round(fps * COPY_GOP_S)` with `COPY_GOP_S = 0.25` → 8 at 30 fps,
  i.e. four keyframes a second. Verified on `films/media/.film/cache/seek/337c7e074b54.mp4`:
  15 keyframes in ~4 s, mean spacing 0.26 s.
* `-fps_mode passthrough`, video only (`-an -sn -dn`): identical frames at identical times,
  nothing added or dropped — the copy is a pure container-bitstream change.
* Quality: `libx264 -preset superfast -crf 16` on the CPU (~"all but lossless"); the
  hardware h264 encoder when available, with the source's color tags re-stated explicitly;
  alpha sources go VP9 `yuva420p -crf 18` CPU-only (VideoToolbox silently drops alpha).
* Bitrate budget scales with pixels·fps, clamped 4–120 Mbps.
* Concurrency safety: written to a `.part-<pid>-<rand>` file, `renameSync`d when whole; a
  loser of the cross-process race keeps the winner's file (same picture); Windows
  EPERM/EACCES/EBUSY on rename retries for ~7 s; an in-process `making` map de-duplicates
  two renders wanting the same copy; a GPU encoder that writes nothing for 15 s is killed and
  the copy redone on the CPU.

### 2.4 Swap — HTTP layer, not document layer

`render.mjs:106` builds `swap = (file) => copies.get(file) ?? null` and hands it to the page
server. In `host.mjs:116` every file request becomes
`const file = (query?.has('film-facts') ? null : swap?.(asked)) ?? asked;`. Consequences:

* `film.html` never mentions a copy; the projection is per-request and vanishes with the
  render.
* `?film-facts` opts out deliberately — what a file *is* (duration, dimensions) must come
  from the original.
* The audio mix bypasses HTTP entirely: `filmSound`/`mix` (shared.mjs) read original paths
  from disk, so the copy's re-encode never touches sound.
* Before any swap exists, `madeCopy` (read-only lookup) lets a page served mid-render start
  using the copy as soon as it is whole.

## 3. Mapping onto MPT

| OpenFilm | MPT equivalent | Gap |
|---|---|---|
| Render browser frame-seeks every clip every frame | MoviePy reader seeks once per `subclipped()` start, then streams forward | Same root cause (decode-from-keyframe), lower frequency → fix the writers first, copies second |
| `-g 8 -keyint_min 8` (+ `-sc_threshold 0` via hardwareOptions/crf path) in `makeCopy` | `build_command` and `write_videofile(ffmpeg_params=…)` pass no `-g` | **default GOP 250 → keyframes=1** on 5 s clips |
| `slowSeeking` gate: copy only when keyframe spacing > 0.5 s and the render is ≥ 2 s | none — MPT never inspects source GOP | P2b probe |
| Content-keyed cache (VERSION+path+size+mtime), part-file + rename | zoom cache keyed by image **pixels**+duration+tag (`_ZOOM_CACHE_TAG`), which *does* change content | P2a must bump the tag; a source-video copy cache needs its own key |
| Swap at HTTP layer, film.html unchanged | no indirection layer; `file_path` is read directly by moviepy | P2b rewrites the path handed to `SubClippedVideoClip` instead |
| Audio mixed from originals | copies would be video-only (`-an`) — source audio is not used by MPT anyway (TTS voiceover) | benign |

## 4. P2 concrete design

Two independent shippable halves. **P2a is the plan's original minimal item (writer-side
`-g`)**; P2b is the ported OpenFilm copy cache, only if source-side seeking proves to be the
dominant cost. Neither changes any edit decision, so P0 determinism and P1 review results are
bit-identical unless GOP config itself is changed.

### 4.1 P2a — dense keyframes on everything MPT encodes

Config (default keeps current behavior, like the plan's draft):

```toml
# config.app
video_gop_seconds = 0   # 0 = leave ffmpeg defaults; >0 → keyframe at most this far apart
```

Touch points:

1. `concat_video_clips_with_ffmpeg.build_command` — when `video_gop_seconds > 0`, append for
   libx264: `["-g", str(g), "-keyint_min", str(g), "-sc_threshold", "0"]` where
   `g = max(1, round(video_gop_seconds * fps_of_output))` (the concat pass knows its fps via
   the encoded clips; use the request `fps`, default 30). All three flags or none: without
   `-sc_threshold 0` scene cuts restart the GOP irregularly and without `-keyint_min` the
   encoder may place fewer, so setting only `-g` is "等于没改".
   HW-encoders take the same `-g` (NVIDIA) / differ (AMF/QSV); route through the existing
   codec-fallback ladder — a flag set that fails belongs to `_fallback_write_videofile`,
   not to a new silent fallback per encoder.
2. `render_image_zoom_video` — same triple appended to a **copy** of `_BT709_FFMPEG_PARAMS`
   (do not mutate the shared constant; color-tag tests reuse it). This changes rendered
   content structure, so **bump `_ZOOM_CACHE_TAG`** (`"-smooth"` → e.g. `"-smooth2"`), which
   renames the cache artifact and prevents old single-keyframe files from being served to
   new reads or vice versa.
3. Suggested default for new configs: `video_gop_seconds = 2` (GOP 60 @ 30fps — 30× denser
   than today, ~1–2 % size cost on these clips). Keeping `0` as the shipped default is the
   conservative choice per plan; a non-zero default is a config.example.toml decision.

Cost model: keyframe interval affects only the *encode* flags (I-frames cost a few percent
bitrate); no extra pass, no extra process. This is the whole of "只做 concat 不动 zoom 缓存
也可" from the plan — the two touch points are independently switchable if desired.

### 4.2 P2b — source-side dense-GOP copy cache (deferred until measured)

Port of `seekable.mjs` shape onto `download_videos` / `combine_videos`:

* **Probe** (`slowSeeking` equivalent): one cheap `ffprobe -read_intervals '%+20'
  -show_entries packet=pts_time,flags -of csv` per downloaded source; keyframe spacing > 0.5 s
  and file is yuv420p h264 → candidate. Run it once, store the verdict next to the download.
* **Key**: sha1 over `VERSION + abspath + size + mtimeMs`, files under
  `storage/cache_videos/seek/<12hex>.mp4` — same properties as OpenFilm: no invalidation
  logic, a VERSION bump orphans safely, barking at algorithm changes is free.
* **Generate**: `ffmpeg -fps_mode passthrough -map 0:v:0 -an -c:v libx264 -preset superfast
  -crf 16 -g <fps/4> -keyint_min <fps/4> -pix_fmt yuv420p`, part-file + atomic rename,
  per-path in-process dedup. Video-only mirrors OpenFilm and is safe for MPT because
  `combine_videos` never uses source audio (`_open_video_clip_quietly(..., audio=False)`).
* **Swap point**: not an HTTP layer — the swap belongs where `SubClippedVideoClip.file_path`
  is built (the download path handed to `_open_video_clip_quietly` in `process_one_clip`):
  if a copy exists for this source, read the copy; kick the copy off asynchronously for
  later clips (OpenFilm's `madeCopy` "found one a moment later" pattern). `used_video_paths`
  / batch accounting keep reporting the *original* path — identity stays with the original,
  exactly as OpenFilm's `?film-facts` opt-out means.
* **Gate on demand** like `slow: total >= fps * 2`: only build copies when the task will
  subclip a source into many pieces or starts each piece late; a task reading one full-length
  download sequentially gains nothing.

Trigger to start P2b: measure per-clip open+seek time in `process_one_clip` (log timestamps
already exist around it) on real jobs; if source seeking is not a visible fraction of
combine time, ship P2a only and close P2.

### 4.3 Verification

* New `test/services/test_video_gop_structure.py` (plan §8 name): synthesize a 5 s clip with
  `video_gop_seconds=2`, assert `ffprobe -show_entries packet=flags` keyframe count ≥ 2;
  assert `=0` path still emits no `-g` (zero behavior change when off); assert the
  `_ZOOM_CACHE_TAG` bump means an old-tagged cache file is not reused.
* P1 review gains the metric the plan wanted ("review 的检出率是 P2 收益的度量工具"):
  record decode-wall-time per review run before/after on the same fixtures.
* Regression gate: full suite vs. stashed baseline, same convention as P0/P1
  (baseline-diff, failure set byte-identical).

## 5. What deliberately is *not* ported

* Browser-decodability (`unplayable`/`firstFrame`/presentsVideo/vulkanFirst) — MPT's decoder
  is ffmpeg via moviepy, which is not codec-limited like Chromium; the whole "will this play
  here" layer has no MPT counterpart.
* `madeCopy`'s 2-second miss TTL — an optimization for per-range-request server loops; MPT's
  swap point is consulted once per clip, so a plain dict without TTL is enough.
* VP9/yuva alpha copies — MPT's pipeline has no transparent-video sources; image alpha is
  resolved before mp4 rendering (`_open_image_clip_with_fallback`).
