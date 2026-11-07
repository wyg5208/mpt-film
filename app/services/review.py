"""
成片机器审查（review）。

设计来自 OpenFilm 的 `look --full`：渲染完成后逐帧看一遍成片，把"人眼才看得见"
的缺陷变成结构化报文。与 OpenFilm 有三点刻意差异：

1. 只审查已渲染的产物。输入就是一个 mp4 路径，不重跑任何页面，也不引入浏览器。
2. **advisory，永不阻断任务**。MPT 的成片是用户等待已久的后台产物，审查发现只能
   提示，不能把成功变成失败。因此本模块所有入口都吞掉内部异常，调用方也不需要
   try/except。
3. 零新依赖。只用 stdlib + numpy/PIL + 仓库已有的 ffmpeg 二进制。注意
   ``imageio-ffmpeg`` 只带 ffmpeg 不带 ffprobe，因此所有探测都优先走 ffmpeg
   自身的 stderr，ffprobe 只作为可选加速路径。

报文形状对齐 OpenFilm 的实践：每条 finding 都带实测数值与时间区间。
`! jumping frame at 6.67s` 之所以能一次定位，就是因为报文里有时刻。
"""

import os
import re
import shutil
import subprocess
from dataclasses import dataclass

import numpy as np
from loguru import logger

from app.config import config
from app.utils import utils

# ---------------------------------------------------------------------------
# 阈值集中在此，便于按真实素材整体调参。不做自适应：自适应会让"同一输入两次
# 审查结论不同"，与本项目引入确定性的目标相反。
# ---------------------------------------------------------------------------

# 采样模式抽 5 fps：能覆盖多帧事件；单帧事件只有 full 模式可见（与 OpenFilm
# watch.mjs 保留原生帧率通道的原因一致）。
SAMPLE_FPS = 5
# 64x36 足够算整帧亮度统计，同时把 12s 成片的解码成本压到亚秒级。
PROBE_WIDTH = 64
PROBE_HEIGHT = 36

# 黑帧：整帧平均亮度低于该值。成片走 yuv420p 有限范围，纯黑解码后 Y=16、
# 纯白 Y=235（实测夹具的整帧均值就是这个值），因此阈值必须分别包络 16/235：
# 20 对应"接近纯黑但允许素材噪点与压黑边"，230 对应"整帧爆白"。
BLACK_LUMA = 20.0
# 白闪：整帧平均亮度高于该值。
WHITE_LUMA = 230.0
# 冻结：相邻帧平均绝对差低于该值视为同一画面。取值依据是本项目实测——确定性
# 校验里的星野噪声远低于此，而真实运动帧远高于此。
FROZEN_DIFF = 1.5
# 突变：相邻帧平均绝对差高于该值视为画面跳变。
JUMP_DIFF = 90.0
# 安静：低于 -24 LUFS 基本听不清；响于 -9 LUFS 会被平台二次压限。
QUIET_LUFS = -24.0
LOUD_LUFS = -9.0
# 削波：true peak 达到该值即认为存在采样点溢出风险。
CLIP_DBTP = -0.1
# 时长不一致：成片必须覆盖配音长度，超出该秒数差值即为异常。
DURATION_TOLERANCE = 0.15

# 连续帧数门槛与邻域窗口均以秒为单位在下面换算。
BLACK_MIN_SECONDS = 0.2
FROZEN_MIN_SECONDS = 0.4
FLASH_MIN_DIFF = 60.0

_MODES = ("off", "sample", "full")


@dataclass(frozen=True)
class Finding:
    """一条审查发现。`code` 面向程序，`detail` 面向人。"""

    code: str
    severity: str  # "info" | "warn" | "error"
    start: float
    end: float
    detail: str
    evidence: str = ""

    def to_warning(self, video_index: int | None = None) -> dict:
        """转换为任务层现有的 warnings 形状，避免为审查新增状态字段。"""
        warning = {
            "code": f"review_{self.code}",
            "severity": self.severity,
            "start": round(self.start, 3),
            "end": round(self.end, 3),
            "detail": self.detail,
        }
        if video_index is not None:
            warning["video_index"] = video_index
        return warning


def resolve_mode(explicit: str | None = None) -> str:
    """
    确定审查模式：显式参数 > 配置 > 默认 sample。

    默认值放在消费方而不是 config.py，与 ``video_clip_concurrency`` 等配置项的
    既有惯例一致：配置文件只承载用户写下的值，缺省时由服务层决定行为。
    """
    mode = explicit if explicit is not None else config.app.get("video_review", "sample")
    if isinstance(mode, bool):
        # 兼容用户写 `video_review = true/false` 的直觉写法。
        return "sample" if mode else "off"
    mode = str(mode or "sample").strip().lower()
    if mode not in _MODES:
        logger.warning(f"unknown video_review mode: {mode}, falling back to sample")
        return "sample"
    return mode


def _ffmpeg_binary() -> str:
    return utils.get_ffmpeg_binary()


def _run(args, timeout: int = 120):
    return subprocess.run(args, capture_output=True, timeout=timeout)


def _read_duration_and_fps(video_path: str) -> tuple[float | None, float | None]:
    """
    从 ffmpeg 的 stderr 横幅读取时长与帧率。

    不依赖 ffprobe：imageio-ffmpeg 只提供 ffmpeg。横幅里的
    ``Duration: 00:00:12.30`` 与 ``29.97 fps`` 精度足够（百分之一秒），
    而 review 的判据都是秒级容差。
    """
    result = _run([_ffmpeg_binary(), "-hide_banner", "-i", video_path], timeout=30)
    stderr = result.stderr.decode(errors="ignore")
    duration = None
    fps = None
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", stderr)
    if match:
        duration = int(match.group(1)) * 3600 + int(match.group(2)) * 60 + float(match.group(3))
    match = re.search(r"([\d.]+)\s*fps", stderr)
    if match:
        fps = float(match.group(1))
    return duration, fps


def _decode_frames(video_path: str, fps: int) -> np.ndarray | None:
    """
    单遍解码为灰度帧序列，形状 ``(n_frames, height, width)``，uint8。

    缩放到 64x36：所有判据都是整帧统计量，不需要像素级精度，而全分辨率原始
    数据在 1080x1920 下每帧约 6 MB，逐帧审查会先把内存吃掉。
    """
    command = [
        _ffmpeg_binary(),
        "-nostdin",
        "-v",
        "error",
        "-i",
        video_path,
        "-vf",
        f"fps={fps},scale={PROBE_WIDTH}:{PROBE_HEIGHT}:flags=area",
        "-pix_fmt",
        "gray",
        "-f",
        "rawvideo",
        "-",
    ]
    result = _run(command, timeout=600)
    if result.returncode != 0 or not result.stdout:
        logger.warning(f"review cannot decode frames: {video_path}")
        return None
    frame_bytes = PROBE_WIDTH * PROBE_HEIGHT
    count = len(result.stdout) // frame_bytes
    if count <= 0:
        return None
    frames = np.frombuffer(result.stdout[: count * frame_bytes], dtype=np.uint8)
    return frames.reshape(count, PROBE_HEIGHT, PROBE_WIDTH)


def _measure_audio(video_path: str) -> dict | None:
    """
    用 ebur128 两遍法之外的快速单遍测量，读取 integrated 与 true peak。

    返回 ``{"integrated": float, "true_peak": float}``；无音轨或解析失败返回 None。
    """
    command = [
        _ffmpeg_binary(),
        "-nostdin",
        "-v",
        "info",
        "-i",
        video_path,
        "-map",
        "0:a",
        "-af",
        "ebur128=peak=true",
        "-f",
        "null",
        "-",
    ]
    result = _run(command, timeout=600)
    stderr = result.stderr.decode(errors="ignore")
    if result.returncode != 0:
        # Input contains no stream / 无可映射音轨，ffmpeg 直接失败，这是"无音频"的可靠信号。
        if "Stream map '0:a' matches no streams" in stderr or "does not contain any stream" in stderr:
            return {"integrated": None, "true_peak": None}
        logger.warning(f"review cannot measure audio loudness: {video_path}")
        return None
    # ebur128 会先逐帧输出几十行相同格式的统计，再给出 Summary。必须在
    # Summary 区块内取值：直接搜索全文会命中第一帧的瞬时读数（开头几帧
    # 尚未积累足够样本，常为 -inf 或极低值），导致任何音频都被判为过轻。
    summary = stderr.split("Summary:")[-1]
    integrated = _parse_loudness_value(summary, r"I:\s*(-?[\d.]+|-inf)\s*LUFS")
    true_peak = _parse_loudness_value(summary, r"Peak:\s*(-?[\d.]+|\-inf)\s*dBFS")
    if integrated is None and true_peak is None:
        return None
    return {"integrated": integrated, "true_peak": true_peak}


def _parse_loudness_value(text: str, pattern: str) -> float | None:
    """读取 ebur128 数值；静音时 ffmpeg 输出 -inf，统一归一化为 -inf 浮点。"""
    match = re.search(pattern, text)
    if not match:
        return None
    raw = match.group(1)
    if raw == "-inf":
        return float("-inf")
    return float(raw)


def _segments(mask: np.ndarray) -> list[tuple[int, int]]:
    """把布尔序列压缩成 [start, end) 区间，end 为开区间。"""
    segments = []
    start = None
    for index, value in enumerate(mask):
        if value and start is None:
            start = index
        elif not value and start is not None:
            segments.append((start, index))
            start = None
    if start is not None:
        segments.append((start, len(mask)))
    return segments


def _neighbour_diffs(diff: np.ndarray, start: int, end: int, window: int) -> float:
    """区间边界的最大邻接差，用于区分"渐变进入黑场"和"突然掉进黑场"。"""
    left = diff[max(0, start - window) : start]
    right = diff[end : min(len(diff), end + window)]
    values = np.concatenate([left, right]) if len(left) or len(right) else np.array([0.0])
    return float(values.max()) if len(values) else 0.0


def _find_visual_findings(frames: np.ndarray, fps: int) -> list[Finding]:
    findings: list[Finding] = []
    luma = frames.mean(axis=(1, 2))
    # 相邻帧平均绝对差。第 i 项表示 frames[i] 与 frames[i+1] 之间的差。
    diff = np.abs(frames[1:].astype(np.int16) - frames[:-1].astype(np.int16)).mean(axis=(1, 2))
    window = max(1, int(round(fps * 0.1)))

    # --- 黑场：持续全黑，且至少一侧是"突然"进入的 ---
    # 正常淡入淡出也是全黑，但它是渐变进入的；只看"突然"才不会被转场误报，
    # 同时仍能抓到成片拼接产生的真正黑洞。
    black_min = max(1, int(round(fps * BLACK_MIN_SECONDS)))
    for start, end in _segments(luma < BLACK_LUMA):
        if end - start < black_min:
            continue
        boundary = max(
            _neighbour_diffs(diff, start, end, window),
            _neighbour_diffs(diff, end, end, window),
        )
        if boundary < FLASH_MIN_DIFF:
            # 两侧都是渐变：视为刻意转场，只在 DEBUG 记录，不作为缺陷。
            logger.debug(
                f"review ignores gradual black segment {start / fps:.2f}s-{end / fps:.2f}s"
            )
            continue
        findings.append(
            Finding(
                code="black_frames",
                severity="error",
                start=start / fps,
                end=end / fps,
                detail=(
                    f"black frames {start / fps:.2f}s-{end / fps:.2f}s "
                    f"({end - start} frames, mean luma {luma[start:end].mean():.1f})"
                ),
            )
        )

    # --- 白闪：瞬时高亮，允许单帧 ---
    for start, end in _segments(luma > WHITE_LUMA):
        # 只统计区间内部的邻接差（即"离开"白帧的跳变）；不能把"进入"白帧
        # 的跳变也算进来，否则黑帧落在白色静止画面里时，76 灰度的进入跳变
        # 会被当成白闪证据，误报一次 flash。
        jump = float(diff[start:end].max()) if end > start else 0.0
        if jump < FLASH_MIN_DIFF:
            continue
        findings.append(
            Finding(
                code="white_flash",
                severity="error",
                start=start / fps,
                end=end / fps,
                detail=(
                    f"white flash at {start / fps:.2f}s "
                    f"({end - start} frame(s), mean luma {luma[start:end].max():.1f})"
                ),
            )
        )

    # --- 冻结：连续多帧几乎不变 ---
    frozen_min = max(1, int(round(fps * FROZEN_MIN_SECONDS)))
    frozen_mask = diff < FROZEN_DIFF
    for start, end in _segments(frozen_mask):
        # diff 序列比 frames 少一帧，区间长度即"静止的相邻帧对数"。
        if end - start < frozen_min:
            continue
        # 整片静止在 MPT 里通常是素材读取失败后循环兜底，属于必须提示的问题。
        findings.append(
            Finding(
                code="frozen_sequence",
                severity="warn",
                start=start / fps,
                end=(end + 1) / fps,
                detail=(
                    f"picture frozen {start / fps:.2f}s-{(end + 1) / fps:.2f}s "
                    f"({end - start} frame pairs, max adjacent diff {diff[start:end].max():.2f})"
                ),
            )
        )

    # --- 突变空洞：单帧异常，两侧画面各自平稳 ---
    # 这是 OpenFilm 报 `jumping frame` 的数值特征。注意不能按"某个 diff 很大"
    # 来找：单帧异常天然产生**相邻的两个**大差值（进入 p、离开 p），而它们
    # 外侧的邻域才是平稳基线。硬切只有一个大差值且两侧都在运动，据此区分。
    for p in range(1, len(frames) - 1):
        if luma[p] > WHITE_LUMA or luma[p] < BLACK_LUMA:
            # 单帧爆白/掉黑已由白闪与黑场通道报告，不在这里重复。
            continue
        entering = float(diff[p - 1])
        leaving = float(diff[p])
        if entering <= JUMP_DIFF or leaving <= JUMP_DIFF:
            continue
        before_span = diff[max(0, p - 1 - window) : p - 1]
        after_span = diff[p + 1 : min(len(diff), p + 1 + window)]
        before_max = float(before_span.max()) if len(before_span) else 0.0
        after_max = float(after_span.max()) if len(after_span) else 0.0
        if before_max > FROZEN_DIFF or after_max > FROZEN_DIFF:
            # 外侧基线本身在运动：这是正常的硬切，不是空洞。
            continue
        findings.append(
            Finding(
                code="abrupt_gap",
                severity="error",
                start=p / fps,
                end=(p + 1) / fps,
                detail=(
                    f"one-frame gap at {p / fps:.2f}s "
                    f"(enter {entering:.1f}, leave {leaving:.1f}, "
                    f"baseline {before_max:.1f}/{after_max:.1f})"
                ),
            )
        )
        # 只报告第一处：单帧扫描已覆盖瞬时事件，后续同类事件大概率是
        # 拼接时序问题的副本，与黑场/白闪通道一起反复报告没有额外价值。
        break

    return findings


def _audio_findings(audio: dict | None, has_audio_stream: bool) -> list[Finding]:
    findings: list[Finding] = []
    if not has_audio_stream or audio is None or audio.get("integrated") is None:
        findings.append(
            Finding(
                code="audio_missing",
                severity="error",
                start=0.0,
                end=0.0,
                detail="no measurable audio track in the rendered video",
            )
        )
        return findings
    integrated = audio["integrated"]
    true_peak = audio["true_peak"]
    if integrated < QUIET_LUFS:
        findings.append(
            Finding(
                code="too_quiet",
                severity="warn",
                start=0.0,
                end=0.0,
                detail=f"integrated loudness {integrated:.1f} LUFS is below {QUIET_LUFS:.0f} LUFS",
            )
        )
    elif integrated > LOUD_LUFS:
        findings.append(
            Finding(
                code="too_loud",
                severity="warn",
                start=0.0,
                end=0.0,
                detail=f"integrated loudness {integrated:.1f} LUFS is above {LOUD_LUFS:.0f} LUFS",
            )
        )
    if true_peak is not None and true_peak >= CLIP_DBTP:
        findings.append(
            Finding(
                code="clipping",
                severity="warn",
                start=0.0,
                end=0.0,
                detail=f"true peak {true_peak:.1f} dBTP leaves no headroom for platform decoding",
            )
        )
    return findings


def _write_evidence(video_path: str, findings: list[Finding], frames: np.ndarray | None, fps: int) -> None:
    """
    命中视觉缺陷时输出一张时刻拼贴图，复刻人工排障体验。

    证据文件是辅助信息：写失败只记日志，绝不改变 findings 本身，也不影响任务。
    """
    if frames is None or not findings:
        return
    visual = [finding for finding in findings if finding.code in (
        "black_frames", "white_flash", "frozen_sequence", "abrupt_gap"
    )]
    if not visual:
        return
    try:
        from PIL import Image

        output_dir = os.path.dirname(os.path.abspath(video_path))
        stem = os.path.splitext(os.path.basename(video_path))[0]
        tiles = []
        for finding in visual[:8]:
            index = min(len(frames) - 1, max(0, int(finding.start * fps)))
            tiles.append(Image.fromarray(frames[index]).convert("RGB"))
        if not tiles:
            return
        sheet = Image.new("RGB", (tiles[0].width * len(tiles), tiles[0].height), (0, 0, 0))
        for position, tile in enumerate(tiles):
            sheet.paste(tile, (position * tile.width, 0))
        evidence_path = os.path.join(output_dir, f"review-{stem}-evidence.png")
        sheet.save(evidence_path)
        # 证据路径以相对 task_dir 的形式记录，与其余任务产物的写法一致；
        # 跨盘符等情况下的相对化失败不影响审查结论，回退为绝对路径即可。
        try:
            recorded = os.path.relpath(evidence_path, utils.task_dir())
        except ValueError:
            recorded = evidence_path
        replacements = {
            finding.code: Finding(
                code=finding.code,
                severity=finding.severity,
                start=finding.start,
                end=finding.end,
                detail=finding.detail,
                evidence=recorded,
            )
            for finding in visual
        }
        for index, finding in enumerate(findings):
            replacement = replacements.get(finding.code)
            if replacement is not None:
                findings[index] = replacement
    except Exception as exc:
        logger.warning(f"review evidence unavailable: {exc}")


def review_video(
    video_path: str,
    *,
    audio_path: str | None = None,
    mode: str | None = None,
) -> list[Finding]:
    """
    审查一条成片，返回结构化 findings。

    ``mode``：``"off"`` 直接返回空；``"sample"``（默认）按 5 fps 抽样，只能覆盖
    多帧事件；``"full"`` 按成片原生帧率逐帧解码，可发现单帧缺陷，成本线性增长。

    本函数**永不抛出**：任何内部异常都压缩成一条 ``review_unavailable`` 的 info
    finding。理由是调用点在任务编排末尾，此时视频、旁白、字幕都已生成，审查
    自身的环境问题不应该把成功任务变成失败任务。
    """
    resolved_mode = resolve_mode(mode)
    if resolved_mode == "off":
        return []
    findings: list[Finding] = []
    try:
        if not os.path.isfile(video_path):
            return [
                Finding(
                    code="review_unavailable",
                    severity="info",
                    start=0.0,
                    end=0.0,
                    detail=f"video file not found: {video_path}",
                )
            ]
        if not shutil.which(_ffmpeg_binary()) and not os.path.isfile(_ffmpeg_binary()):
            return [
                Finding(
                    code="review_unavailable",
                    severity="info",
                    start=0.0,
                    end=0.0,
                    detail="ffmpeg binary is unavailable, frame review skipped",
                )
            ]

        duration, source_fps = _read_duration_and_fps(video_path)
        sample_fps = int(round(source_fps or 30)) if resolved_mode == "full" else SAMPLE_FPS
        frames = _decode_frames(video_path, sample_fps)
        if frames is None:
            findings.append(
                Finding(
                    code="review_unavailable",
                    severity="info",
                    start=0.0,
                    end=0.0,
                    detail="frame decoding produced no usable picture",
                )
            )
        else:
            findings.extend(_find_visual_findings(frames, sample_fps))

        audio = _measure_audio(video_path)
        has_audio = audio is not None and audio.get("integrated") is not None
        findings.extend(_audio_findings(audio, has_audio))

        if duration is not None and audio_path and os.path.isfile(audio_path):
            narration_duration, _ = _read_duration_and_fps(audio_path)
            if narration_duration:
                # 成片必须覆盖配音。MPT 的拼接逻辑本就带安全余量，这里 shortfall
                # 超过容差说明旁白被截断，用户会听到句子在半空中结束。
                shortfall = narration_duration - duration
                if shortfall > DURATION_TOLERANCE:
                    findings.append(
                        Finding(
                            code="duration_mismatch",
                            severity="error",
                            start=duration,
                            end=narration_duration,
                            detail=(
                                f"video is {shortfall:.2f}s shorter than narration "
                                f"(video {duration:.2f}s, audio {narration_duration:.2f}s)"
                            ),
                        )
                    )

        _write_evidence(video_path, findings, frames, sample_fps)
        for finding in findings:
            logger.info(
                f"review finding: code={finding.code}, severity={finding.severity}, "
                f"window={finding.start:.2f}s-{finding.end:.2f}s, {finding.detail}"
            )
        return findings
    except Exception as exc:
        # 审查是辅助能力，包含超时与二进制缺失在内的所有故障都在这里收口。
        logger.warning(f"video review failed: {video_path}, error: {exc}")
        return [
            Finding(
                code="review_unavailable",
                severity="info",
                start=0.0,
                end=0.0,
                detail=f"review skipped due to internal failure: {exc}",
            )
        ]
