# Deterministic rendering and machine review

Two related, opt-in capabilities for the short-video pipeline:

- **`video_seed`** makes the *random editing decisions* reproducible, so the same
  inputs can be replayed into the same cut.
- **Machine review** scans each finished `final-N.mp4` for the defects people
  otherwise file bug reports about — black frames, white flashes, frozen
  picture, one-frame gaps, wrong loudness, truncated narration — and reports
  them as ordinary task warnings.

Both ideas were ported from a study of OpenFilm v0.2.7. Where the port was
direct and where it was redesigned is called out explicitly in the
[OpenFilm comparison](#openfilm-comparison) section; there is **no runtime
dependency** on OpenFilm and no Node/Playwright anywhere in this code path.

Nothing here changes the default behavior for callers who do not use it: an
unseeded request behaves exactly as it did before, and review is advisory and
never fails a completed task.

---

## 1. `video_seed`

### 1.1 What is randomized, and what the seed fixes

Before this feature, four kinds of decision were driven by Python's
process-global `random` module:

| Role | Decision | Where |
|---|---|---|
| `material` | order of the download queue (which landed materials get used) | `material.download_videos` |
| `order` | clip sequencing for each output video | `video.combine_videos` |
| `clip` | per-clip transition direction and shuffle-transition type | `video.combine_videos` |
| `bgm` | which background-music track is picked | `video.get_bgm_file` |

A global `random` is unseedable in practice here: clip processing runs in a
`ThreadPoolExecutor` (`video_clip_concurrency`, 1–8) and CPython re-seeds the
module per thread, so the *concurrency level*, the *batch split*, and even
*whether one clip happened to fail* all shifted the random stream for later
clips. Calling `random.seed()` once at the entry point does not fix that.

The seed replaces "shared random stream" with a **pure function of
`(base_seed, role, role_index)`**. Each decision derives its own
`random.Random` from a SHA-256 of that triple (see
`app/services/determinism.py`), so:

- changing one clip's transition does not reshuffle any other clip;
- batch generation gives each output `k` a distinct edit, determined only by
  `(seed, k)`;
- the result is independent of thread count and scheduling order.

Sub-seeds are hashed rather than `seed + index` because adjacent integer seeds
stay highly correlated under the Mersenne Twister, which would show up as
transitions that "look like they repeat".

### 1.2 How to set it

The field is `video_seed` on `VideoParams` (`app/models/schema.py`), bounded to
a 32-bit unsigned integer (`0 … 4294967295`), default `None`.

- **API**: `TaskVideoRequest` inherits `VideoParams`, so add `"video_seed": 12345`
  to the `POST /api/v1/videos` body.
- **Programmatic / CLI pipeline**: set `params.video_seed` on a `VideoParams`.
- **`None` (default) means "not specified"**, and the code path then uses the
  process-global `random` exactly as before. This is deliberate: an unseeded
  caller must keep today's distribution, not silently become deterministic.

> The WebUI seed input box and a dedicated CLI flag are **not** part of this
> change (they are the deferred P3 step). Today you set the seed through the API
> body or a `VideoParams` object.

### 1.3 The effective seed, and how a run records itself

Even when you pass `None`, the task computes an **effective seed** by deriving
one from the `task_id`. This is *not* to make separate runs reproducible
(`task_id` is a fresh UUID every time); it is so that one run is internally
consistent — main thread, worker threads, retries, logs and the recorded
manifest all use the same number. That recorded number is what you copy back to
replay.

`save_script_data` writes it into the task's `script.json` under `video_seed`.
`params.video_seed` is kept unchanged alongside it, because it records "did the
user actually specify one" — a different fact that must not be collapsed into
the effective value.

### 1.4 What the seed does **not** guarantee

This is the most important limit, so it is stated plainly. `video_seed`
reproduces the **editing decisions applied to a given set of already-landed
material files**. It does **not** pin down *which* material files exist, because
those come from sources this feature deliberately does not touch:

- **Third-party material search is not seeded.** Pexels/Pixabay/Coverr and the
  paid generation providers return whatever their API returns that day. The
  code sorts each candidate list by a stable key `(url, duration)` before
  shuffling so that a *given* set shuffles reproducibly — but if the provider's
  result set changes, the material set changes with it and the cut changes.
- **Download failures change the usable set.** A material that fails to fetch
  or fails FFmpeg validation is dropped before the seed is applied, so the
  inputs to the decision are different.
- **Script, voice and search terms are not covered.** LLM script generation,
  TTS acoustics, and auto-generated search terms are outside the determinism
  promise. Feed the same `video_script` / `video_terms` if you need those fixed.

Practical rule: to reproduce a cut, reuse the **same local material set** (e.g.
`video_source: "local"` with `video_materials`, or an unchanged cache) **and**
the same script/terms, then vary only `video_seed`. Given those, the clip order,
transition directions, transition types and BGM pick reproduce. Cross-run
"same provider search = same footage" is explicitly not promised.

---

## 2. Reproduce a video, step by step

1. **Generate once.** Submit a request (or run the pipeline). You do not need to
   pass a seed.
2. **Read back the effective seed.** Open the task's `script.json` artifact and
   note the top-level `video_seed` value. (It is also logged as
   `video seed: <n>, explicit=…, count=…`.)
3. **Fix the non-seeded inputs.** Reuse the same `video_script` and
   `video_terms`, and point at the *same* material files — the reliable way is
   `video_source: "local"` with an explicit `video_materials` list, so the
   candidate set cannot drift with a provider response.
4. **Re-submit with the seed.** Put the value from step 2 into `video_seed`.
5. **Compare.** Clip ordering, per-clip transition direction, shuffle-transition
   choice, and the random BGM track should match. If they do not, the difference
   is coming from step 3 (materials/script drifted), not from the seed.

Because `video_index` also feeds the derivation, batch mode stays reproducible
per output: with one seed, output *k* is always the same cut regardless of
`video_count` or thread concurrency.

---

## 3. Machine review

`app/services/review.py` scans a finished video and returns structured
findings. It is wired into `generate_final_videos` right after the final encode
and before the task status is written, so findings ride the **existing
`warnings` channel** — the API response, WebUI notices and `partial_results`
snapshots all pick them up without any new state field.

### 3.1 Enabling and configuring

Set `video_review` under `[app]` in `config.toml` (documented in
`config.example.toml`):

| Value | Meaning |
|---|---|
| `"sample"` | **default** — 5 fps grayscale scan. Catches multi-frame defects. |
| `"full"` | native-frame-rate scan. Can additionally catch single-frame defects. |
| `"off"` | skip review. |
| `true` / `false` | convenience mapping to `sample` / `off`. |

Resolution precedence is **explicit `mode=` argument > `config.app.video_review`
> `sample`**. An unrecognized value logs a warning and falls back to `sample`.

### 3.2 What a finding looks like

Every finding is appended as a warning dict:

```json
{
  "code": "review_black_frames",
  "severity": "error",
  "start": 6.60,
  "end": 6.80,
  "detail": "black frames 6.60s-6.80s (6 frames, mean luma 2.1)",
  "video_index": 1
}
```

- `code` is namespaced `review_*` for the program.
- `severity` is `error` | `warn` | `info`, so a client can tier display. (The
  richer folded/expanded WebUI treatment is part of the deferred P3 step; today
  every finding surfaces as a warning carrying its own `severity`.)
- `detail` always embeds measured numbers and a timestamp — the same reason
  OpenFilm's `! jumping frame at 6.67s` is actionable at a glance.
- Visual findings additionally carry `evidence`, a relative path to a timestamp
  contact sheet written next to the video (see §3.4).

### 3.3 Detection algorithm and calibrated thresholds

Review does a single grayscale decode (`fps=N, scale=64:36, pix_fmt=gray`) to a
NumPy array, plus one `ebur128` audio pass. All visual criteria are whole-frame
statistics, so the low-resolution grayscale stream is enough and keeps a 12 s
clip's memory tiny.

| Code | Severity | Criterion (calibrated) | Threshold constant |
|---|---|---|---|
| `black_frames` | error | mean luma `< 20`, sustained `>= 0.2 s`, and entered *suddenly* (neighbouring diff `>= 60` on at least one side) | `BLACK_LUMA`, `BLACK_MIN_SECONDS`, `FLASH_MIN_DIFF` |
| `white_flash` | error | mean luma `> 230`, with an intra-segment jump `> 60` (single frames allowed) | `WHITE_LUMA`, `FLASH_MIN_DIFF` |
| `frozen_sequence` | warn | adjacent-frame mean-abs diff `< 1.5`, sustained `>= 0.4 s` | `FROZEN_DIFF`, `FROZEN_MIN_SECONDS` |
| `abrupt_gap` | error | a non-black/non-white frame `p` where **both** `diff(p-1,p)` and `diff(p,p+1)` exceed `90`, while both outer baselines stay `< 1.5` | `JUMP_DIFF`, `FROZEN_DIFF` |
| `duration_mismatch` | error | `narration_duration − video_duration > 0.15 s` (video longer than narration is normal padding, not reported) | `DURATION_TOLERANCE` |
| `too_quiet` | warn | ebur128 integrated `I < −24 LUFS` | `QUIET_LUFS` |
| `too_loud` | warn | ebur128 integrated `I > −9 LUFS` | `LOUD_LUFS` |
| `clipping` | warn | ebur128 true peak `>= −0.1 dBTP` | `CLIP_DBTP` |
| `audio_missing` | error | no audio stream, or no measurable integrated loudness | — |
| `review_unavailable` | info | file missing, ffmpeg unavailable, decode produced no frames, or any internal error | — |

Every threshold lives as a named module constant with a leading comment; there
is no "adaptive" tuning on purpose, because adaptivity would make two reviews of
the same file disagree — the opposite of what this feature is for.

#### Why the black/white thresholds are 20 and 230, not 0 and 255

This is a real calibration correction, not a guess. Final videos are encoded
**yuv420p limited (video) range**, so after decoding to grayscale, a *pure
black* frame does **not** measure luma 0 — it measures about **16**, and pure
white measures about **235**, not 255. Those are the values the FFmpeg decoder
produces for BT.601/BT.709 limited-range content.

If the thresholds used the naïve 0/255 intuition (`< 8` for black, `> 245` for
white), neither defect would ever fire on real media, because real black sits at
16 (above 8) and real white sits at 235 (below 245). The working thresholds must
therefore *envelope the limited-range values*:

- `BLACK_LUMA = 20` — just above the measured 16, still low enough to allow
  material noise and crushed letterbox edges.
- `WHITE_LUMA = 230` — just below the measured 235, so only genuine full-frame
  blowout trips it.

Two more subtleties that the fixtures lock down:

- **`white_flash` counts only intra-segment jumps** (`diff[start:end]`). If the
  *entering* jump were included, a black frame sitting inside an otherwise white
  static scene would register a spurious flash on the way in.
- **`abrupt_gap` needs two consecutive large diffs with quiet outer baselines.**
  A genuine one-frame anomaly inherently produces *two* adjacent large
  differences — into frame `p` and out of it — whereas a normal hard cut between
  two moving shots produces one large diff with motion on both outer sides.
  That asymmetry is what distinguishes a defect from an intentional cut.
  Black/white single frames are skipped here because they belong to the
  `black_frames` / `white_flash` channels.

The audio band was calibrated the same way, against synthetic fixtures: full-scale
pink noise measures ≈ 0 dBTP (trips `clipping`); a −30 dB tone measures
≈ −50 LUFS (trips `too_quiet`); a compressed+madeup track measures ≈ −3.7 LUFS
(trips `too_loud`); a `anullsrc` digital-silence track still counts as "audio
present" and is caught by `too_quiet`, not `audio_missing`.

### 3.4 Evidence contact sheet

When a visual defect is found, review writes one timestamp contact sheet
`review-{stem}-evidence.png` (up to 8 tiles) next to the video, recreating the
one-glance triage of manually pulling frames. The relative path is back-filled
into the finding's `evidence` field. Writing evidence is purely auxiliary: a
failure to write it is logged and changes nothing about the findings or the
task.

This cycle adds **no** new `review-{index}.json` artifact and does **not** touch
the `task_artifacts` download whitelist or the MIME allow-list — findings already
reach the user through the warnings channel, so there is no reason to widen the
attack surface for auxiliary data.

### 3.5 Failure isolation

`review_video` **never raises**. Missing ffmpeg, an unreadable file, an
undecodable stream, or an internal exception each collapse into a single
`review_unavailable` info finding. The call site in `task.py` additionally wraps
the loop and gates it on `os.path.isfile(final_video_path)` — so a genuinely
absent output (an earlier encode failure that already emitted its own warning)
produces no noisy "file not found" review line and does not disturb exact
`warnings` assertions. Review problems can never turn a successful task into a
failed one.

---

## 4. `sample` vs `full`: measured cost

Both modes run three short FFmpeg subprocesses (a duration/fps probe, the
grayscale frame decode, and the `ebur128` audio pass). Measured on this
workspace's bundled `imageio-ffmpeg` binary against synthetic 1080×1920 clips
(median of repeated runs, wall-clock):

| Clip | `sample` (5 fps) | `full` (native 30 fps) |
|---|---|---|
| 12 s | ≈ 0.24 s (~60 frames analysed) | ≈ 0.26 s (~360 frames analysed) |
| 60 s | ≈ 0.67 s (~300 frames analysed) | ≈ 0.74 s (~1800 frames analysed) |

The numbers are close, and it is worth being honest about why: FFmpeg's `fps`
filter must **fully decode the source in order to drop frames**, so the
expensive part (decoding the H.264 stream) is identical in both modes. `sample`
saves on the raw-video pipe volume and the NumPy analysis over it, not on
decoding. The fixed subprocess overhead dominates for short clips; the gap grows
slowly with duration but does not explode.

Choose the mode on **detection need**, not cost:

- `sample` (default) is fine for routine runs and only misses genuine
  **single-frame** events (a one-frame black/flash/gap), which it can thin out.
- `full` decodes at native frame rate so single-frame defects are visible. Use it
  for acceptance testing of a finished piece, or when a `sample` pass is clean
  but you still suspect a flash.

Both scale roughly linearly with clip duration; there is no benefit to `full`
for content that is already sampled at a similar effective rate.

---

## 5. OpenFilm comparison

The concept, the four visual defect families, and the "every message carries a
timestamp and a measured number" convention are ported. Several mechanisms had
to be redesigned because MoneyPrinterTurbo is a "fetch/generate footage +
FFmpeg-concat" pipeline, not OpenFilm's "code-is-the-film, browser-rendered"
pipeline.

**Ported directly**

- The four review defect families map one-to-one from OpenFilm's
  `look --full` report: `white flash → white_flash`,
  `jumping frame → abrupt_gap`, `still picture → frozen_sequence`,
  `black → black_frames`.
- Loudness/true-peak reporting via `ebur128`, and the practice of embedding
  measured values (LUFS, dBTP, timestamps) in the message text.
- Keeping every detection threshold explicit rather than adaptive.

**Redesigned for MPT**

- **Determinism mechanism.** OpenFilm forces determinism by re-seeding
  `Math.random` at every rendered timestamp inside a browser render loop
  (`FILM_CLOCK`). MPT has no such loop; instead each decision is a pure function
  of `(seed, role, role_index)` with its own `random.Random`, specifically so it
  is correct under `ThreadPoolExecutor` without monkey-patching global state.
- **Review input.** OpenFilm `look` re-renders pages in a browser at 30 fps and
  pixel-diffs two seeded passes. MPT reviews the *already-rendered mp4* by
  decoding low-resolution grayscale frames with FFmpeg — no browser, no
  re-render, zero new dependencies (stdlib + the already-present NumPy/PIL + the
  repo's FFmpeg binary; note `imageio-ffmpeg` ships FFmpeg but not ffprobe, so
  probing reads FFmpeg's own stderr).
- **Advisory only.** OpenFilm's `look` gates the render. MPT's review never
  fails a completed task; it can only add warnings.
- **Limited-range thresholds.** OpenFilm works from a browser RGBA canvas
  (full 0–255); MPT works from yuv420p limited range, which is exactly why the
  black/white luma thresholds had to be recalibrated to 20/230 (§3.3). This
  constraint does not exist upstream.
- **Single-frame formulation.** `abrupt_gap`'s "two consecutive large diffs with
  quiet outer baselines" is an MPT formulation suited to a sampled grayscale
  stream, not a port of OpenFilm's pixel-diff equality test.

**Explicitly not borrowed**

- Browser frame rendering and the HTML film syntax.
- `film.html` grammar and the Studio editor (MPT already has WebUI and
  `docs/video-projects.md`).
- OpenFilm's full bit-exact reproducibility goal. MPT's upstream includes LLM
  scripts, third-party material search and paid generation that are out of scope
  (see §1.4); MPT only promises frame-identical *editing* for a *given* landed
  material set.

---

## 6. Related tests

- `test/services/test_video_seed_reproducible.py` — 20 cases: same seed /
  different thread concurrency yields identical per-clip decisions (identified by
  clip origin+span, not arrival order), different roles don't interfere, and
  unseeded callers still get the process-global `random`.
- `test/services/test_review_watch_findings.py` — 24 cases: every code fires on
  real FFmpeg-synthesized fixtures, a clean video yields zero findings, and
  review never raises on missing/broken inputs.
