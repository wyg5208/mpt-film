"""本地关键帧链（脚本方案专业模式，B5，§5.3 主路线四步）。

① 按 scene.keyframe.first_prompt/last_prompt + 角色 appearance_prompt/
reference_images（IPAdapter）+ plan.style 生成关键帧对（t2i）；
② shared_with_prev 场景直接复用上一段尾帧文件作首帧（同一文件，像素级
衔接由模型保证）；
③ MiniMax H3 FL2V 在首尾帧间动画化；
④ 草稿档 turbo 4-step 768p，成片档完整模型 20 步。

边界连续性的承诺层级：关键帧文件级恒等（②保证）；成片切点受旁白时间窗
裁剪影响，由 review.scene_boundary_jump 实测播报（advisory，不阻断）。
所有产物经 comfy_local 的 requestKey 缓存内容寻址，重跑同方案不重复烧 GPU。
"""

import os
import subprocess

from loguru import logger

from app.models.schema import ScriptPlan, Series
from app.services import comfy_local
from app.utils import utils

# 本地引擎场景：FL2V 首尾帧动画化为主；local_i2v 仅首帧条件（尾帧留空）。
LOCAL_ENGINES = {"local_fl2v", "local_i2v"}


class KeyframeChainError(RuntimeError):
    """关键帧链的确定性失败（缺窗口/共享约束违反/引擎产物缺失）。"""


def _image_model(quality_tier: str) -> str:
    return "sdxl-quality" if quality_tier == "final" else "sdxl-lightning"


def _video_model(quality_tier: str) -> str:
    return "minimax-final" if quality_tier == "final" else "minimax-draft"


def _style_suffix(plan: ScriptPlan) -> str:
    style = plan.style
    parts = [
        part.strip()
        for part in (style.tone, style.palette, style.camera, style.consistency_subject)
        if part and part.strip()
    ]
    return ", ".join(parts)


def _character_context(scene, series: Series | None) -> tuple[str, str]:
    """场景引用角色的外貌描述与第一张存在的参考图（IPAdapter 用）。"""
    if series is None or not scene.characters:
        return "", ""
    by_id = {character.id: character for character in series.characters}
    appearances = []
    reference = ""
    for character_id in scene.characters:
        character = by_id.get(character_id)
        if character is None:
            continue
        if character.appearance_prompt.strip():
            appearances.append(character.appearance_prompt.strip())
        if not reference:
            reference = next(
                (img for img in character.reference_images if os.path.isfile(img)), ""
            )
    return ", ".join(appearances), reference


def _location_prompt(scene, series: Series | None) -> str:
    if series is None or not scene.location:
        return ""
    location = next((loc for loc in series.locations if loc.id == scene.location), None)
    return location.prompt.strip() if location else ""


def compose_keyframe_prompt(scene, plan: ScriptPlan, series: Series | None, *, which: str) -> str:
    """关键帧 prompt = 场景描述 + 角色外貌 + 场景地点 + 全局风格。"""
    keyframe = scene.keyframe
    base = (keyframe.first_prompt if which == "first" else keyframe.last_prompt).strip()
    if not base:
        base = (scene.visual or scene.narration or "").strip()
    if not base:
        raise KeyframeChainError(f"scene {scene.id} has no keyframe prompt or visual description")
    appearance, _ = _character_context(scene, series)
    parts = [base]
    if appearance:
        parts.append(appearance)
    location = _location_prompt(scene, series)
    if location:
        parts.append(location)
    style = _style_suffix(plan)
    if style:
        parts.append(style)
    return ", ".join(parts)


def compose_motion_prompt(scene, plan: ScriptPlan) -> str:
    """FL2V 的运动 prompt：场景画面描述 + 风格（首尾帧已携带外貌信息）。"""
    base = (scene.visual or scene.keyframe.first_prompt or scene.narration or "").strip()
    if not base:
        raise KeyframeChainError(f"scene {scene.id} has no visual description for motion")
    style = _style_suffix(plan)
    return f"{base}, {style}" if style else base


def extract_frame(video_path: str, out_path: str, *, at_end: bool = False) -> bool:
    """ffmpeg 抽取片段首帧/尾帧（云端关键帧链与边界审查共用）。

    尾帧用 -sseof 贴近末尾 + -update 1 逐帧覆写，落盘即最后一帧；
    失败只返回 False，由调用方决定降级路径。
    """
    if at_end:
        args = ["-sseof", "-0.5", "-i", video_path, "-update", "1", "-q:v", "2", out_path]
    else:
        args = ["-i", video_path, "-frames:v", "1", "-q:v", "2", out_path]
    command = [utils.get_ffmpeg_binary(), "-nostdin", "-v", "error", "-y", *args]
    try:
        result = subprocess.run(command, capture_output=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning(f"frame extraction failed: {video_path}, error: {exc}")
        return False
    if result.returncode != 0 or not os.path.isfile(out_path):
        logger.warning(f"frame extraction produced no picture: {video_path}")
        return False
    return True


def generate_local_scene_videos(
    task_id: str,
    plan: ScriptPlan,
    windows: list,
    *,
    aspect: str = "9:16",
    series: Series | None = None,
    on_progress=None,
    stop_event=None,
    progress_callback=None,
) -> tuple[dict, dict]:
    """为方案中的本地引擎场景逐段生成关键帧对 + FL2V 视频。

    返回 (bindings, keyframes)：bindings={scene_id: [video_path]} 直接进
    timeline 编译；keyframes={scene_id: {"first": path, "last": path}} 供
    调用方回填 plan.keyframe 并持久化（共享边界帧约束在回填后仍成立）。
    不修改传入的 plan。引擎离线/产物缺失抛 KeyframeChainError，由任务层
    翻译为 materials 阶段失败。
    """
    aspect = getattr(aspect, "value", aspect)
    local_scenes = [scene for scene in plan.scenes if scene.engine in LOCAL_ENGINES]
    if not local_scenes:
        return {}, {}
    if not comfy_local.is_online():
        raise KeyframeChainError(
            "ComfyUI is not running; local engine scenes need it online "
            "(绘世启动器 one-click start), or switch the scenes to stock."
        )
    by_id = {window["scene_id"]: window for window in windows}
    image_model = _image_model(plan.quality_tier)
    video_model = _video_model(plan.quality_tier)
    episode = plan.episode_id or plan.title or task_id
    bindings: dict = {}
    keyframes: dict = {}
    resolved: dict = {}
    previous = None
    for index, scene in enumerate(plan.scenes):
        if scene.engine not in LOCAL_ENGINES:
            previous = scene
            continue
        window = by_id.get(scene.id)
        if window is None:
            raise KeyframeChainError(f"scene {scene.id} has no time window")
        _, reference = _character_context(scene, series)

        # ① / ② 首帧：共享边界帧 > 用户指定文件 > t2i 生成。
        if scene.keyframe.shared_with_prev:
            if previous is None or previous.engine not in LOCAL_ENGINES:
                raise KeyframeChainError(
                    f"scene {scene.id} shares a boundary frame but the previous "
                    "scene is not a local engine scene"
                )
            first_path = resolved[previous.id]["last"]
        elif scene.keyframe.first and os.path.isfile(scene.keyframe.first):
            first_path = scene.keyframe.first
        else:
            first_path = comfy_local.generate_image(
                compose_keyframe_prompt(scene, plan, series, which="first"),
                model=image_model,
                aspect=aspect,
                out_name=f"{episode}-{scene.id}-f",
                reference_image=reference,
                on_progress=on_progress,
                stop_event=stop_event,
            )["path"]

        # 尾帧：用户指定文件 > t2i 生成；local_i2v 不条件化尾帧。
        last_path = ""
        if scene.keyframe.last and os.path.isfile(scene.keyframe.last):
            last_path = scene.keyframe.last
        elif scene.engine == "local_fl2v":
            last_path = comfy_local.generate_image(
                compose_keyframe_prompt(scene, plan, series, which="last"),
                model=image_model,
                aspect=aspect,
                out_name=f"{episode}-{scene.id}-l",
                reference_image=reference,
                on_progress=on_progress,
                stop_event=stop_event,
            )["path"]

        # ③ 首尾帧动画化；时长贴齐帧网格，多余部分由 timeline 裁窗。
        video = comfy_local.generate_video(
            compose_motion_prompt(scene, plan),
            model=video_model,
            aspect=aspect,
            duration=window["duration"],
            out_name=f"{episode}-{scene.id}",
            first_frame=first_path,
            last_frame=last_path,
            on_progress=on_progress,
            stop_event=stop_event,
        )
        bindings[scene.id] = [video["path"]]
        keyframes[scene.id] = {"first": first_path, "last": last_path}
        resolved[scene.id] = {"first": first_path, "last": last_path}
        logger.info(
            f"keyframe chain: task={task_id}, scene={scene.id}, "
            f"video={video['path']}, cached={video['cached']}"
        )
        if progress_callback is not None:
            progress_callback((index + 1) / len(plan.scenes))
        previous = scene
    return bindings, keyframes