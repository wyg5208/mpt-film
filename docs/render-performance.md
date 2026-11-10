# 渲染性能调优指南

一份 58.6 秒的 1080x1920 成片在 i9-14900HX + RTX 5090 Laptop 上渲染了 17 分钟以上，
而同机调优后预期 3–5 分钟。差距全部来自**配置**而非代码能力。本文拆解渲染管线的耗时
结构，并给出可调项。

---

## 1. 渲染管线 anatomy：同样的素材要编码三次

| 阶段 | 实现 | 耗时占比（调优前实测） |
|---|---|---|
| ① 分段预处理 | `video.process_one_clip`：MoviePy 逐段裁剪/变速/转场/裁边后各自编码为临时 mp4 | ~5 分 48 秒（30 段 × ~7 秒，**串行**） |
| ② 拼接 | `concat_video_clips_with_ffmpeg`：concat demuxer 读入全部片段，**整段重编码**（BT709 色彩滤镜 + yuv420p + 时长裁剪） | ~3 分 46 秒 |
| ③ 成片合成 | `video.generate_video`：MoviePy 合成字幕（含动画）与旁白，**再编码一次** | 13 分钟以上，且这是 MoviePy 的 **Python 逐帧管线**（单线程生成帧），只有编码侧吃得到多线程/GPU |
| 素材下载 | Pexels 网络下载 | 4 分 24 秒（与硬件无关） |

三次编码默认全部落在 `libx264`（纯 CPU 软编）。

---

## 2. 三个旋钮

### 2.1 `video_codec`（[app]，默认 `libx264`）

- 白名单：`libx264` / `h264_nvenc`（NVIDIA）/ `h264_amf`（AMD）/ `h264_qsv`（Intel 核显）/ `h264_mf` / `h264_videotoolbox`（macOS），见 `video.py` `_SUPPORTED_VIDEO_CODECS`。
- 选择非 libx264 时先检测 bundled ffmpeg 是否含该 encoder，再在运行时失败时**自动回退 libx264**并禁用该编码器（单任务内不重复失败），不会让任务挂掉。
- **推荐**：有 NVIDIA 显卡即设 `h264_nvenc`。实测 RTX 5090 Laptop 通过（bundled ffmpeg 自带 `h264_nvenc` / `av1_nvenc`）。
- 注意：NVENC 默认恒定码率策略与 libx264 的 CRF 不同，画质观感需以实测成片为准；如不满意需在编码路径补显式 bitrate/QP。

### 2.2 `video_clip_concurrency`（[app]，默认 1，上限 8）

- 阶段 ① 的并行度（`ThreadPoolExecutor`）。默认 1 = 30 段素材逐个编码。
- **并发不影响成片内容**：每个片段的转场随机决策用 `(seed, "clip", index)` 派生的独立 RNG（见 [deterministic-review.md](deterministic-review.md)），与线程数、调度顺序、批次划分无关——这是并行化能安全开启的前提。
- **推荐**：4–6。多路 MoviePy 编码同时读写磁盘，过高收益递减。

### 2.3 `n_threads`（VideoParams，默认 2，上限 16）

- 控制阶段 ② 拼接（ffmpeg `-threads`）与阶段 ③ 成片（MoviePy `write_videofile(threads=...)`）的**编码线程数**。
- 默认 2 出自历史保守值；在 CPU 编码（libx264）时这是最大的单点瓶颈——24 核机器只跑 2 线程。
- WebUI 目前没有该参数的输入项，API 调用方可在请求体显式传入。若启用 `h264_nvenc`，编码已卸载到 GPU，该值影响变小。
- schema 中无配置文件回退：`params.n_threads or 2`。

---

## 3. 推荐配置与预期收益

```toml
# config.toml [app]
video_codec = "h264_nvenc"
video_clip_concurrency = 5
```

1 分钟竖屏成片（i9-14900HX + RTX 5090 Laptop，实测/推算）：

| 阶段 | 调优前 | 调优后（预期） |
|---|---|---|
| ① 分段 | 5 min 48 s（串行 CPU） | ~1–2 min（5 并发 + NVENC） |
| ② 拼接 | 3 min 46 s（libx264 2 线程） | ~10–20 s（NVENC） |
| ③ 成片 | 13 min+（MoviePy 逐帧 + 2 线程编码） | ~2–4 min（编码走 GPU；**字幕逐帧合成仍是 Python 单线程**，此阶段无法被 GPU 完全覆盖） |
| 合计 | **17.5 min+** | **~3–5 min** |

---

## 4. 注意事项

1. **改配置后必须重启 WebUI**：进程持有启动时的配置快照。
2. **`[app]` 是应用运行时会回写的表**（`video_clip_concurrency`、`material_concurrency`、`upload_post_*` 等由程序持久化）：手工加键前先全文搜索同名键，重复键会让整个配置解析失败。
3. 阶段 ② 拼接期间无进度日志，只有 30 秒间隔的心跳（`ffmpeg concat still running`）；阶段 ③ 同理（`final video render still running`）——这是存活心跳，不是卡死。
4. 拼接阶段设了 3600 秒超时（`_DEFAULT_FFMPEG_CONCAT_TIMEOUT_SECONDS`），编码器挂死会显式失败而不是无限等待。
5. 排查渲染慢的第一步：看任务日志里三个阶段各自的时间戳，先分清是编码慢、逐帧合成慢，还是下载慢。

相关文档：[v1.3.9_2026-11-09_tts与渲染稳定性.md](迭代记录文档/v1.3.9_2026-11-09_tts与渲染稳定性.md) · [deterministic-review.md](deterministic-review.md)
