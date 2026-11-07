# MPT 确定性渲染与成片审查（Review）落地方案

> 来源：对 OpenFilm v0.2.7 的源码研读与本机部署验证（`opensources/openfilm`，全部产物在
> `opensources/` 下，已 gitignore）。本文只讨论 **MoneyPrinterTurbo 侧的可落地改动**，
> 不引入 Node/Playwright 运行时。
>
> 状态：待批准。P0 与 P1 未开始，任何 `app/`、`webui/` 下的正式代码都尚未修改。

---

## 1. 背景：从 OpenFilm 学到的、以及实测证据

上一轮在本机把 OpenFilm 跑通后，验证了四条机制，它们各自对应 MPT 的一个真实缺口：

| OpenFilm 机制 | 实测证据 | MPT 对应缺口 |
|---|---|---|
| **确定性强制**：`FILM_CLOCK` 预lude 在每个 `t` 重新播种 `Math.random`；`look` 用两遍固定种子的乱序采样重绘同一批帧，逐像素比对 | 在 `waves.html` 注入 `acc++ * 0.004` 的状态残留后，`look` 在 11/12 个采样时刻报失败并输出 `-a/-b` 差异图；撤销后转绿（exit 0） | MPT 的素材顺序、转场方向、转场类型、BGM 选择全部来自**进程级全局 `random`**，同参数重跑必然不同，且无法从任务记录复现 |
| **渲染后逐帧审查**：`look --full` 对成片按 30 fps 逐帧看，报 `white flash / jumping frame / still picture / black` 四类缺陷 | 真实抓到 `! jumping frame at 6.67s`：抽帧拼贴证实第 200 帧（t=6.6667s）除标题页外全黑，根因是片段局部时间正好落在 `out` 端点，浏览器不呈现任何帧 | MPT 生成完就结束，`final-N.mp4` 里的黑帧、冻结、拼接空洞只能靠人眼发现 |
| **响度治理**：`render --loudness=-14` 两遍 loudnorm，只动音频 | `♪ -12.8 LUFS · 0.9 dBTP → -14.0 LUFS · -2.0 dBTP`；独立 `ebur128` 复核一致；两个成片的**视频流 MD5 完全相同**（`c1494237d43571e5b53e9f0535d840f9`） | MPT 的 `bgm_volume / voice_volume` 是线性增益，成片响度完全看素材，平台（抖音/YouTube）要求 -14/-16 LUFS 时无保证 |
| **快进友好副本**：`.film/cache/seek/` 为每个源视频生成"每 0.25s 一个关键帧"的 H.264 副本 | HEVC 源被转成 `e3001de0e6c0.mp4`，关键帧间隔 `0.266667s`；而 **MPT 自己的 5 个源视频全部只有 1 个关键帧**（`keyframes=1`） | `concat_video_clips_with_ffmpeg` 与 `render_image_zoom_video` 都不传 `-g`，libx264 默认 GOP 250 帧；5s@30fps 的 zoom 缓存视频整片仅 1 个关键帧，任何随机 seek 都要从头解码 |

### 明确不借鉴的部分

- **浏览器逐帧渲染 + HTML 影片语法**：MPT 是"检索/生成素材 + FFmpeg 拼接"，不是"代码即影片"，移植页面契约没有收益。
- **`film.html` 语法与 Studio 编辑器**：MPT 已有 WebUI 与 `docs/video-projects.md` 的工程格式，不应双轨。
- **确定性追求的范围**：OpenFilm 要求全画面逐比特可复现。MPT 的上游含 LLM 脚本、第三方素材搜索与付费生成，这些**不在本方案承诺范围内**（见 §2 非目标）。本方案只承诺：**给定同一 `video_seed` 与同一批已落地素材文件，画面编排（顺序/转场/选片）逐帧一致**。

---

## 2. 目标与非目标

### 目标

- **G1**：随机决策可播种、可记录、可复现。用户传同一个 `video_seed` + 同一批素材 → 同一条片子。
- **G2**：`video_count > 1` 时，第 `k` 条视频只由 `(seed, k)` 决定，**与线程并发数、下载完成顺序无关**。
- **G3**：成片生成后自动做一次机器审查，输出结构化 findings，走现有 `warnings` 通路，绝不阻断任务。
- **G4**：拼接/图片渲染产物改为快进友好 GOP（可选开关，默认保守）。
- **G5**：以上全部有 pytest 覆盖，且 CI 上不需要网络与真实 Provider 凭据。

### 非目标

- 不改 LLM 脚本生成、不改 TTS 声学结果、不改第三方素材搜索结果的可复现性。
- 不在本方案中实现自动响度归一化（`--loudness` 等价能力）；本文只把**测量**放进 review，把**归一化**列为 P4 待定项。
- 不引入新依赖（只用 stdlib + 已有 numpy/PIL + 已有 ffmpeg 二进制）。
- 不改变现有 API 的必填字段与默认行为：`video_seed` 不传时，用户可观察到的行为与今天完全一致。

---

## 3. 现状盘点：随机源清单（逐行核实）

`app/` 下 `random.*` 的真实调用点共 **7 处**（另有 2 处 `VideoConcatMode.random.value` 是枚举比较，不是随机）：

| # | 位置 | 调用 | 决策含义 | 决策粒度 |
|---|---|---|---|---|
| R1 | `app/services/material.py:2533` | `random.shuffle(valid_video_items)` | 下载队列顺序 → 决定哪些素材被下载 | 每次 `download_videos` 一次 |
| R2 | `app/services/video.py:285` | `random.shuffle(primary_items)` | 每个源文件的"主片段"顺序 | 每次 `combine_videos` 一次 |
| R3 | `app/services/video.py:286` | `random.shuffle(overflow_items)` | 兜底片段顺序 | 同上 |
| R4 | `app/services/video.py:911` | `random.choice(files)` | 从 BGM 库随机选一首 | 每次 `generate_video` 一次 |
| R5 | `app/services/video.py:1130` | `random.choice(["left","right","top","bottom"])` | slide 转场方向 | **每片段一次** |
| R6 | `app/services/video.py:1155` | `random.choice(transition_funcs)` | shuffle 转场类型 | **每片段一次** |
| R7 | `app/services/voice.py`（无） | — | 语音侧无随机调用，已确认 | — |

### 三个必须一起解决的结构性问题

**(a) 线程共享全局 RNG。** R5/R6 位于 `combine_videos.process_one_clip`，而片段在
`ThreadPoolExecutor(max_workers=_get_clip_processing_concurrency())`（`video.py:1206`，
`config.app.video_clip_concurrency`，默认 1，上限 8）里并发执行。CPython 的 `random` 模块
对每个首次使用的线程自动播种，因此**并发数一变，结果就变**；即使并发数为 1，同一批次内
片段被 `executor.map` 派发，顺序也不受调用方控制。
→ 结论：**不能只做"入口处 seed 一次全局 random"**，必须改成"决策按索引派生独立 RNG"。

**(b) 决策没有稳定的索引。** 好消息：`process_one_clip(indexed_item)` 收到的 `index` 就是
`subclipped_items` 里的下标（`video.py:1226` 写入 `batch.append((candidate_index, ...))`），
而 `subclipped_items` 的顺序由 R2/R3 决定、在派发前已固定。
→ 结论：`(seed, video_index, "clip", index)` 是一个天然稳定键，可直接用。

**(c) 集合枚举顺序不稳定。** R4 依赖 `bgm_service.list_bgm_files()` 的返回顺序；目录遍历在
不同文件系统上顺序不同。
→ 结论：所有 `choice`/`shuffle` 的输入序列必须先显式排序，否则播种无意义。

---

## 4. P0：种子机制

### 4.1 新增 `app/services/determinism.py`（唯一的新增底层模块）

```python
"""
任务级确定性工具。

MPT 的随机决策历史上直接使用进程级 `random` 模块。该模块被所有线程共享，
CPython 还会为每个首次使用的线程自动重新播种，因此并发数、调度顺序都会
改变成片。本模块把"决策"降级为纯函数：决策的输入只有 (base_seed, role,
role_index)，与执行顺序无关。
"""

import hashlib
import random

Role = str  # "material" | "order" | "clip" | "bgm"


def derive_seed(base_seed: int, role: Role, role_index: int = 0) -> int:
    """由基础种子派生子种子。不同角色/不同下标互不干扰，改一个片段不重排其他片段。"""
    key = f"{base_seed}\0{role}\0{role_index}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(key).digest()[:8], "big")


def rng_for(base_seed: int | None, role: Role, role_index: int = 0) -> random.Random:
    """
    返回该决策专属的 RNG。

    `base_seed is None` 表示"未指定种子"，此时返回进程级 `random` 模块本身，
    保持未播种路径与历史行为完全一致（不传种子的用户不会突然变成确定性输出）。
    """
    if base_seed is None:
        return random
    return random.Random(derive_seed(base_seed, role, role_index))


def resolve_effective_seed(base_seed: int | None, task_id: str) -> int:
    """
    未指定种子时，按 task_id 派生一个"本轮种子"。

    目的不是跨运行可复现（task_id 每次都是新 UUID），而是让**单次运行内部自洽**：
    主线程与线程池、重试路径、日志与 script.json 记录的是同一个种子，
    因此把 script.json 里的 video_seed 抄回来重跑，就能得到同一条片子。
    """
    if base_seed is not None:
        return int(base_seed) & 0xFFFFFFFF
    return derive_seed(int.from_bytes(task_id.encode("utf-8"), "big", signed=True), "task")
```

设计要点：

- **不 monkey-patch 全局 `random`**，不改 `random.seed()`。全局播种在多线程下是自欺欺人。
- `base_seed is None → 返回 random 模块`：这是唯一能保证"零行为变更"的写法。
- 子种子用 sha256 而非 `seed + index`，避免角色间种子相邻导致的相关性。

### 4.2 参数与配置

| 位置 | 改动 | 说明 |
|---|---|---|
| `app/models/schema.py` `VideoParams`（第 96 行起） | 新增 `video_seed: Optional[int] = None` | 命名带 `video_` 前缀，与所有 Provider 的绘图 `seed` 区分；`None` = 未指定 |
| `app/controllers/v1/video.py` `TaskVideoRequest` | 复用 `VideoParams` 字段即自动生效；若为独立模型则同步新增 | 需带 `ge=0, le=2**32-1` 边界校验，风格对齐 `video_clip_duration` |
| `config.example.toml` `[app]` | 新增注释项 `# video_seed = ` | 只作文档说明"全局默认种子"，代码里**不**读它（避免 WebUI 与 API 行为分叉）；如后续需要再单独评审 |
| `webui/Main.py` 高级设置 | P3 再加输入框；P0 不动 WebUI | 保持 P0 的改动面只在服务层 |

### 4.3 种子的贯穿路径

```
controller / webui
  └─ task_id, params.video_seed
       └─ _run_in_thread → generate_final_videos / download_videos 入口
            effective_seed = determinism.resolve_effective_seed(params.video_seed, task_id)
            ├─ 写入 script.json（§4.5）
            ├─ material.download_videos(..., seed=effective_seed)        # R1
            ├─ video.combine_videos(..., seed=effective_seed, video_index=index)  # R2 R3 R5 R6
            └─ video.generate_video(..., seed=effective_seed)            # R4
```

- `download_videos` / `combine_videos` / `generate_video` 各新增**关键字可选参数**
  `seed: int | None = None`，默认 `None` → 走 `random` 模块（旧行为）。
- `combine_videos` 再新增 `video_index: int = 1`，用于把 `video_count` 的多条片子拆开
  （R2/R3 用 `("order", video_index)`）。
- `task.py:1051` 的 `for i in range(params.video_count)` 循环已经把 `index` 传下去，
  不需要改循环结构。

### 4.4 逐个随机点的改法（含代码）

**R1 素材下载顺序**（`material.py:2531-2533`）

```python
    concat_mode_value = getattr(video_concat_mode, "value", video_concat_mode)
    if concat_mode_value == VideoConcatMode.random.value:
        # 搜索结果顺序由 Provider 决定，这里显式排序后再打乱，
        # 否则同一批结果在不同响应顺序下会得到不同选择。
        valid_video_items.sort(key=lambda item: (item.url, item.duration))
        determinism.rng_for(seed, "material").shuffle(valid_video_items)
```

> 注意：`valid_video_items` 的去重顺序来自 `_search_terms_in_parallel` 的产出顺序，本身
> 与网络完成时序有关。排序键 `(url, duration)` 是**必须的**，不是可选优化。

**R2/R3 片段顺序**（`video.py:285-286`）

```python
    rng = determinism.rng_for(seed, "order", video_index)
    rng.shuffle(primary_items)
    rng.shuffle(overflow_items)
```

同时给 `_prioritize_unique_source_clips` 增加 `seed`、`video_index` 两个可选参数
（`video.py:234`），并在 `combine_videos` 调用处（`video.py:1080-1085`）传入。
`grouped_items` 的遍历顺序来自 dict 插入序，源头是 `video_paths` 顺序 —— 需要在
`combine_videos` 入口对 `video_paths` 做 `sorted()`（只影响 random 模式下的打乱输入，
sequential 模式保持原序，因为那是关键词轮询语义，不能动）。

**R5/R6 逐片段转场**（`video.py:1130`、`1155`）—— 本方案最关键的一处

```python
    # 转场方向与类型属于"该片段自身的属性"。用片段在编排序列里的下标派生独立 RNG，
    # 而不是共享一个序列：这样并发数、批次划分、甚至前面某片段处理失败都不会
    # 改变其他片段的随机决策。
    clip_rng = determinism.rng_for(seed, "clip", index)
    shuffle_side = clip_rng.choice(["left", "right", "top", "bottom"])
    ...
    shuffle_transition = clip_rng.choice(transition_funcs)
```

`index` 即 `process_one_clip` 收到的 `indexed_item[0]`（`video.py:1092`），已核实为
`subclipped_items` 的稳定下标。

**R4 BGM 选择**（`video.py:905-911`）

```python
    if bgm_type == "random":
        files = sorted(bgm_service.list_bgm_files())
        if not files:
            logger.warning("no background music files found")
            return ""
        return determinism.rng_for(seed, "bgm").choice(files)
```

`sorted()` 是必须的：目录枚举顺序不保证跨平台一致。

### 4.5 持久化与回显

- `task.save_script_data`（`task.py:430-436`）的 `script_data` 增加顶层字段
  `"video_seed": effective_seed`，与 `"params"` 平级，避免污染 params 快照语义。
- 任务状态里也带上：`sm.state.update_task(task_id, ..., video_seed=effective_seed)`，
  让 WebUI/API 轮询能直接读到，不必打开文件。
- 日志：在 `generate_final_videos` 开头打一条
  `logger.info(f"video seed: {effective_seed} (explicit={params.video_seed is not None})")`，
  便于从日志复现。
- **复现操作路径**（写进 §8 文档）：把 `script.json` 里的 `video_seed` 填回请求体
  `video_seed`，并保持素材源不变。

### 4.6 兼容性与风险

| 风险 | 处置 |
|---|---|
| 老任务记录没有 `video_seed` | 字段缺失 → `None` → 走 `random` 模块，与今天一致 |
| 用户以为"传了 seed 就能跨运行完全复现" | 明确边界：素材来自在线搜索/付费生成时，候选集合本身可能变化；文档写明"seed 保证编排一致，不保证素材集合一致" |
| `sorted()` 改变 random 模式下的选择分布 | 这是**预期修正**：不排序时播种毫无意义。用 P0 的测试锁定排序后的分布 |
| 新增可选参数导致调用方签名不一致 | 全部为 `keyword-only` 且带默认值；`test/services/test_video.py:1110` 等处对 `_prioritize_unique_source_clips` 的 `side_effect` 打桩需同步（该测试用 `lambda subclipped_items, concat_mode`，新增带默认值的 kwarg 不破坏它，但需实跑确认） |

---

## 5. P1：`app/services/review.py` 成片审查

### 5.1 设计原则（与 OpenFilm 的差异）

1. **只审查已渲染的产物**，不重跑页面。输入是 `final-N.mp4` 一个文件路径。
2. **advisory，不阻断**。OpenFilm 的 `look` 失败即 exit 1；MPT 是用户等待的后台任务，
   审查发现绝不能把成功变成失败。findings 一律进 `warnings`。
3. **零新依赖**。用 `ffmpeg`/`ffprobe`（已有 `utils.get_ffmpeg_binary()`、
   `utils.check_ffmpeg_ready()`）+ numpy + PIL。
   已知约束：`imageio-ffmpeg` 只带 `ffmpeg` 不带 `ffprobe`
   （`test_video_color_tags.py:14` 已记录），因此**优先用 ffmpeg 单命令完成探测与解码**，
   `ffprobe` 可用时作为加速路径，不可用时降级。
4. **成本可控**：默认只审查每条成片的**抽样帧**（`--review=sample`，约 2s 墙钟），
   全帧模式（`--review=full`）留给排障与 CI。

### 5.2 公开接口

```python
# app/services/review.py
@dataclass(frozen=True)
class Finding:
    code: str        # "black_frames" | "white_flash" | "frozen_sequence" | "abrupt_gap" | "duration_mismatch" | "too_quiet" | "clipping" | "audio_missing"
    severity: str    # "info" | "warn" | "error"
    start: float     # 秒
    end: float       # 秒；瞬时事件时 end == start
    detail: str      # 人类可读，含实测数值
    evidence: str = ""   # 相对 task_dir 的证据图路径，可空

def review_video(
    video_path: str,
    *,
    audio_path: str | None = None,
    subtitle_path: str | None = None,
    mode: str = "sample",          # "sample" | "full" | "off"
    fps_budget: int = 30,
) -> list[Finding]:
    """审查一条成片。任何内部异常都被吞成一条 info finding，绝不抛出。"""
```

返回值同时提供 `to_warnings(findings) -> list[dict]` 适配器，形状对齐现有
`warnings`（`task.py:1103-1107` 的 `{"code": ..., "video_index": ...}`）。

### 5.3 检测算法

统一先做一次 **单遍解码**：`ffmpeg -i final-N.mp4 -vf fps=N,scale=64:36 -f rawvideo -pix_fmt gray -`
得到低分辨率灰度帧序列 `frames[i]`（`sample` 模式 N=5，`full` 模式 N=原生帧率）。

> 校准说明（实现期实测，ffmpeg 7.1）：下表阈值均以**真实合成夹具**定死，与初稿
> 有两处关键修正。① 灰度而非 rgb24：所有判据都是整帧统计量，灰度把内存与解析
> 成本减半。② 黑/白阈值不能用 0/255 直觉——成片走 yuv420p 有限范围，纯黑解码后
> 整帧亮度实测为 16、纯白 235，故 `black_frames` 上界取 20、`white_flash` 下界取
> 230 才能分别包络 16/235；沿用初稿的 8/245 会让这两类缺陷在真实媒体上完全不触发。

| code | 判据（实测标定） | 依据 |
|---|---|---|
| `black_frames` | `mean(luma) < 20` 且连续 ≥ 0.2s，且至少一侧“突然”进入（邻域 diff ≥ 60） | 直接对应实测的 `jumping frame` 全黑帧；“突然”判据用来放过合法的淡入淡出转场 |
| `white_flash` | `mean(luma) > 230` 且离开白帧区间的邻接差 > 60，允许单帧 | OpenFilm 的 white flash 判据；只统计区间内部跳变，否则白色静止画面里的黑帧会被误报一次 flash |
| `frozen_sequence` | 相邻帧 `diff = mean(|a-b|)` < 1.5，连续 ≥ 0.4s | 对应 OpenFilm 的 `still picture`。整片静止在 MPT 里通常是素材读取失败后循环兜底 |
| `abrupt_gap` | 单帧 `p` 使 `diff(p-1,p)` 与 `diff(p,p+1)` **都** > 90，且两侧外邻域基线各自 < 1.5 | OpenFilm `jumping frame`。单帧异常天然产生相邻的**两个**大差值（进入+离开），硬切只有一个且两侧都在运动，据此区分；非黑非白的异常帧才走此通道，黑白瞬时事件由上两条负责 |
| `duration_mismatch` | 配音时长 − 成片时长 > 0.15s | MPT 的 `_get_required_video_duration` 本就要求画面覆盖配音；成片更长属于正常留白，不报 |
| `too_quiet` | ebur128 Summary `I < -24 LUFS` | 实测 pink noise `volume=-30dB` ≈ -50.8 LUFS 稳定触发 |
| `too_loud` | Summary `I > -9 LUFS` | 实测压缩提升链（makeup=12）≈ -3.7 LUFS 触发；平台会二次压限 |
| `clipping` | Summary `true_peak >= -0.1 dBTP` | 实测满幅 pink noise true peak ≈ 0 dBTP；留不出平台解码余量 |
| `audio_missing` | 无音频流，或 ebur128 读不出 integrated | 防“静音成片”类无声投诉。注意 `anullsrc` 数字静音仍算有声流，由 `too_quiet` 捕捉 |

每条 finding 的 `detail` 必须带实测数字（例：`black frames 0.033s–0.100s, mean luma 2.1`），
理由与 OpenFilm 一致：`! jumping frame at 6.67s` 之所以能定位，是因为报文里有时刻。

### 5.4 证据产物

- 命中视觉缺陷时在成片同目录写一张时刻拼贴图 `review-{stem}-evidence.png`（最多 8 格），
  复刻本项目里 `boundary.png`（帧 196–203 拼贴）这种一次性定位体验；命中后它的
  相对路径回填到 finding 的 `evidence` 字段随 warnings 一起返回。
- 证据写入是纯辅助：失败只记日志，**绝不改变 findings 本身**，也不影响任务。
- 本期不新增 `review-{index}.json` 产物，也不动 `task_artifacts` 白名单 / 下载 MIME
  允许列表；findings 已经走 warnings 通路对外可见，避免为辅助信息扩大攻击面。

### 5.5 编排接入

- 位置：`generate_final_videos` 中 `video.generate_video(...)` 之后、
  `sm.state.update_task(...)` 之前（`task.py:1144-1173`）。
- 每条 `final-index.mp4` 审一次，findings 追加进现有 `warnings` 列表：

```python
        # 先确认产物存在：编码失败时上游已有专属警告，审查再报一条“文件不存在”
        # 只是噪声，还会抹平调用方对 warnings 的精确断言。
        if path.isfile(final_video_path):
            findings = review.review_video(
                final_video_path,
                audio_path=audio_file,
                mode=review_mode,
            )
            for finding in findings:
                warnings.append(finding.to_warning(video_index=index))
```

- `Finding.to_warning()` 直接产出 `review_{code}` / `severity` / `start` / `end` /
  `detail` / `video_index` 的字典，形状对齐既有降级警告。
- 复用现有 `warnings` 通路 → API 响应、WebUI 提示、`partial_results` 快照全部
  自动生效，**不需要新增状态字段**。
- 开关：`config.app.video_review`（默认 `sample`）；`resolve_mode()` 允许显式参数
  > 配置 > 默认，并把 `true/false` 直觉写法映射到 `sample/off`。
- 失败隔离：`review_video` **永不抛出**，内部异常压缩成一条
  `code="review_unavailable"` 的 `info` finding。

### 5.6 风险

| 风险 | 处置 |
|---|---|
| 审查拉长任务时长 | `sample` 模式 64×36 缩放解码，12s 片子实测开销在亚秒级；文档标注 `full` 模式耗时线性 |
| 误报让用户困惑 | `severity` 三级；只有 `error` 在 WebUI 显性提示，`warn` 折叠，`info` 仅入日志与 json |
| 阈值在竖屏/横屏/低素材质量下失准 | 阈值全部集中为模块常量并带前缀注释，P1 测试用合成视频锁定行为，不做"自适应" |
| ffmpeg 缺失 | 入口先 `utils.check_ffmpeg_ready()`，缺失直接返回 `[]` 并记 `info`（此时主任务本身早已在 `task.py:1717` 失败，属防御性代码） |

---

## 6. P2：快进友好 GOP（关键帧间隔）

现状核实：`concat_video_clips_with_ffmpeg.build_command`（`video.py:653-678`）传
`-c:v codec -threads -vf _BT709_VIDEO_FILTER -pix_fmt yuv420p`，**没有 `-g`**；
`render_image_zoom_video`（`video.py:2075-2077`）传 `fps=30, ffmpeg_params=_BT709_FFMPEG_PARAMS`，
同样没有 `-g`。libx264 默认 GOP 250 帧 → 5s@30fps 的 zoom 缓存视频整片 1 个关键帧，
与实测 `keyframes=1` 一致。

改动（全部可选、默认关闭，避免无谓增大文件）：

```python
# config.app
# video_gop_seconds = 0      # 0 = 不改现状；>0 时按 fps 换算 -g
```

- `concat_video_clips_with_ffmpeg`：`-g int(gop_seconds * fps)` + 同步
  `-keyint_min` + `-sc_threshold 0`（三者必须同时设，否则场景切换会把 GOP 打散，
  等于没改）。
- `render_image_zoom_video`：追加进 `_BT709_FFMPEG_PARAMS` 的一份副本，
  **注意会改变 zoom 缓存文件名/内容**：`_ZOOM_CACHE_TAG` 必须升版
  （`video.py:2064`），否则老缓存命中新参数或反之，产生画面不一致。
- 收益场景：`combine_videos` 里每片段 `subclipped(start, end)` 的 seek、
  以及 review 的逐帧解码。
- 该项与 P0/P1 无依赖，可最后做，也可只做 concat 不动 zoom 缓存。

---

## 7. 测试方案

遵循 `test/README.md`：pytest 收集 `unittest.TestCase` 与函数式两用；一个文件一个域；
资源放 `test/resources`；不联网；`MPT_RUN_INTEGRATION_TESTS` 默认跳过真实 Provider。

### 7.1 `test/services/test_video_seed_reproducible.py`（新增）

单元层（不跑 FFmpeg，毫秒级）：

| 用例 | 断言 |
|---|---|
| `test_derive_seed_is_stable_and_role_isolated` | 同输入同输出；`("clip",0)` 与 `("bgm",0)` 不同；`("clip",0)` 与 `("clip",1)` 不同 |
| `test_unseeded_path_keeps_legacy_behavior` | `rng_for(None, ...)` 是 `random` 模块对象本身（`is` 比较），保证零行为变更 |
| `test_prioritize_unique_source_clips_is_reproducible` | 同一 `seed` 两次调用返回同一顺序；不同 `seed` 返回不同顺序（≥ 30 个片段，用集合不等断言，避免偶然相同） |
| `test_material_shuffle_sorts_before_shuffling` | 打乱输入序列后传同一 seed，两次输出顺序一致（锁定 R1 的 `sort` 修正） |
| `test_bgm_choice_is_reproducible_and_empty_safe` | monkeypatch `list_bgm_files` 返回乱序；同 seed 同结果；空列表返回 `""` 不抛 |
| `test_clip_transition_decision_depends_only_on_index` | 固定 seed，改变 `ThreadPoolExecutor` 批次划分与 `video_clip_concurrency`（1 与 4），断言每个 `index` 的 `(shuffle_side, transition)` 完全一致 —— **这是 G2 的直接证明** |
| `test_effective_seed_persisted_to_script_json` | 跑 `save_script_data`，读回 `script.json` 断言 `video_seed` 存在且等于入口解析值 |
| `test_video_count_isolates_variants` | `video_index=1` 与 `2` 的 `("order", k)` 顺序不同（批量多样性未被播种抹平） |

集成层（用 `test_video_color_tags.py` 的 ffmpeg 合成套路，小尺寸 64×64、0.4s）：

| 用例 | 断言 |
|---|---|
| `test_combine_videos_same_seed_produces_identical_file` | 两次 `combine_videos` 到不同输出，`-map 0:v -c copy -f md5 -` 的视频流 MD5 相等 |
| `test_different_seed_produces_different_file` | 同法 MD5 不等 |

### 7.2 `test/services/test_review_watch_findings.py`（新增）

全部用 ffmpeg 合成"带缺陷"与"干净"的小视频，断言检出与不误报：

| 用例 | 合成方式 | 期望 |
|---|---|---|
| `test_detects_black_frame` | 正常色帧中间插 1 帧纯黑 | 命中 `abrupt_gap`；黑段 ≥6 帧时另命中 `black_frames` |
| `test_detects_sustained_black` | 前 1s 全黑 | `black_frames`，`start≈0` |
| `test_detects_white_flash` | 中间 1 帧全白 | `white_flash` |
| `test_detects_frozen_sequence` | 同一帧重复 2s | `frozen_sequence` |
| `test_ignores_legitimate_fade` | 0.3s 淡入淡出 | **无** `black_frames`/`frozen_sequence`（防误报回归线） |
| `test_clean_video_has_no_findings` | 渐变运动 + 正弦音 | `findings == []` |
| `test_detects_too_quiet` | 音频衰减 30 dB | `too_quiet` |
| `test_detects_clipping` | 方波满幅 | `clipping` |
| `test_detects_audio_missing` | `-an` 生成 | `audio_missing` |
| `test_duration_mismatch_against_audio` | 视频 2s、旁白 5s | `duration_mismatch` |
| `test_review_never_raises` | monkeypatch `get_ffmpeg_binary` 抛 `FileNotFoundError` | 返回单条 `review_unavailable` info，不抛 |
| `test_evidence_files_written` | 命中 finding 时 | `review-{index}.json` 与 `review-{index}.png` 落在 task_dir |
| `test_review_failure_does_not_fail_task` | 编排层：monkeypatch `review.review_video` 抛异常 | 任务仍 `TASK_STATE_COMPLETE` |
| `test_findings_surface_in_warnings` | 编排层 | `update_task` 收到的 `warnings` 含 `review_*` 且带 `video_index` |

### 7.3 现有测试的影响面（需实跑确认，不预判）

- `test/services/test_video.py`：`_prioritize_unique_source_clips` 的打桩
  （`:1108-1112`）、`get_bgm_file` 的打桩（`:437`、`:499`）。
- `test/services/test_batch_material_allocation.py`：R1 加 `sort` 后顺序变化。
- `test/services/test_bgm.py` / `test_bgm_list_race.py`：R4 加 `sorted` 后。
- `test/services/test_artifact_download_mime.py`：新增 `review-*.png/json` 白名单。
- `test/services/test_video_color_tags.py`：P2 若改 `_BT709_FFMPEG_PARAMS` 复用方式。

全量命令：`uv run python -X utf8 -m pytest -q test`。

---

## 8. 分期、改动清单与验收

| 阶段 | 内容 | 新增文件 | 修改文件 | 验收 |
|---|---|---|---|---|
| **P0** | `determinism.py` + 7 个随机点改造 + `video_seed` 参数 + `script.json` 回显 | `app/services/determinism.py`、`test/services/test_video_seed_reproducible.py` | `app/models/schema.py`、`app/controllers/v1/video.py`、`app/services/video.py`（R2/R3/R4/R5/R6 + `combine_videos`/`generate_video` 签名）、`app/services/material.py`（R1 + `download_videos` 签名）、`app/services/task.py`（seed 贯穿 + `save_script_data`） | 新测试全绿；`pytest -q test` 无回归；不传 seed 时行为与今日一致 |
| **P1** | `review.py` + 编排接入 + 证据产物 | `app/services/review.py`、`test/services/test_review_watch_findings.py` | `app/services/task.py`（`generate_final_videos`）、`app/services/task_artifacts.py`（产物白名单）、`app/config/config.py`（`video_review` 默认值） | 合成缺陷全部检出、干净视频零误报、审查异常不影响任务完成 |
| **P2** | GOP 开关 | `test/services/test_video_gop_structure.py` | `app/services/video.py`（concat + zoom 渲染 + `_ZOOM_CACHE_TAG` 升版）、`config.example.toml` | 输出关键帧间隔 ≤ 配置值；老缓存不误命中新参数 |
| **P3** | WebUI：seed 输入框 + review findings 展示 | — | `webui/Main.py`、`webui/i18n/*.json`（14 个语言文件同步） | 可填种子；可看到折叠的审查提示 |
| **P4** | 待定：`--loudness` 等价（两遍 loudnorm，画面不动） | — | `app/services/video.py` | 需单独评审，不在本方案范围 |

### 落地顺序的理由

P0 先于 P1：**没有种子就没有"重跑一次做对照"的能力**，而 review 的价值恰恰在于
"同一份输入两次结果应当一致"。P1 先于 P2：review 的检出率本身就是 P2 收益的度量工具
（逐帧解码耗时是可量化指标）。

### 文档产出

- `docs/deterministic-review.md`：seed 语义与边界（尤其"seed 不保证素材集合一致"）、
  复现操作步骤、findings 码表与阈值、`sample`/`full` 成本。
- `docs/deterministic-review.md` 里保留一段"OpenFilm 对照表"，说明哪些是移植、
  哪些是重设计，避免后来者误以为存在运行时依赖。

---

## 9. 需要确认的决策点

1. `video_seed` 默认 `None`（= 不指定）是否可接受？替代方案是默认派生自 `task_id`，
   但那会让"未指定"与"已指定"难以区分。本方案选择 `None` + §4.1 的
   `resolve_effective_seed` 内部派生。
2. review 默认 `mode`：`sample`（推荐，亚秒级）还是 `full`（更准，线性耗时）。
3. review 是否默认开启（`config.app.video_review = true`）。
4. P2 是否本轮实施，还是仅 P0+P1。
