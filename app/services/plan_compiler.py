"""方案→执行编译器（脚本方案专业模式，B4）。

confirmed ScriptPlan 编译为逐场景素材请求与显式时间线：
- plan_to_script：场景旁白拼回整篇文案（整篇一次 TTS，单 sub_maker 契约不变）；
- build_scene_windows：cues 时间戳按场景旁白字符边界切窗，measured_duration
  与 subtitle_cues 由此回填（§5.4：不做逐场景独立 TTS）；
- compile_timeline：场景→素材 in/out 序列 + 场景级转场，交给
  video.combine_videos 的可选 timeline 参数（缺省 None 走原逻辑）。

全部纯函数：同 plan + 同 cues + 同素材绑定 → 同时间线，重跑即同一支片子。
"""

from datetime import timedelta

from app.models.schema import ScriptPlan, SubtitleCue, VideoTransitionMode
from app.utils import utils

# 方案转场 → 既有转场枚举值。match_cut 是硬切（匹配剪辑），不加效果。
_TRANSITION_MAP = {
    "none": None,
    "fade": VideoTransitionMode.fade_in.value,
    "slide": VideoTransitionMode.slide_in.value,
    "zoom": VideoTransitionMode.zoom_in.value,
    "match_cut": None,
}


class PlanCompileError(RuntimeError):
    """表示方案无法编译为可执行时间线。"""


def plan_to_script(plan: ScriptPlan) -> str:
    """场景旁白按序拼回整篇文案；空旁白场景跳过（画面仍占时间窗）。"""
    return "\n".join(
        scene.narration.strip() for scene in plan.scenes if scene.narration.strip()
    )


def scene_search_terms(plan: ScriptPlan) -> dict[str, list[str]]:
    """逐场景素材请求：keywords 绑定场景，替代全局 terms 轮询。
    空 keywords 回退 visual 描述，再回退场景 id（绝不空手检索）。"""
    requests = {}
    for scene in plan.scenes:
        terms = [t.strip() for t in scene.keywords if (t or "").strip()]
        if not terms and scene.visual.strip():
            terms = [scene.visual.strip()]
        requests[scene.id] = terms or [scene.id]
    return requests


def _normal_chars(text: str) -> str:
    """字符边界只数可见字符：空白不参与配音，也不参与切窗。"""
    return "".join((text or "").split())


def _narration_chars(text: str) -> int:
    return len(_normal_chars(utils.remove_emoji(utils.remove_pause_tags(text or ""))))


def _seconds(value) -> float:
    if isinstance(value, timedelta):
        return value.total_seconds()
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _cue_rows(sub_maker) -> list[dict]:
    """统一两种字幕结构：edge_tts 7.x cues（timedelta）优先，
    legacy subs/offset（100ns）兜底。返回 [{start, end, text, chars}]。"""
    rows = []
    for cue in getattr(sub_maker, "cues", None) or []:
        text = str(getattr(cue, "content", "") or "")
        rows.append({
            "start": _seconds(getattr(cue, "start", 0)),
            "end": _seconds(getattr(cue, "end", 0)),
            "text": text,
            "chars": len(_normal_chars(text)),
        })
    if rows:
        return rows
    subs = getattr(sub_maker, "subs", None) or []
    offsets = getattr(sub_maker, "offset", None) or []
    for text, (start_ns, end_ns) in zip(subs, offsets):
        text = str(text or "")
        rows.append({
            "start": float(start_ns) / 10000000.0,
            "end": float(end_ns) / 10000000.0,
            "text": text,
            "chars": len(_normal_chars(text)),
        })
    return rows


def _boundary_time(position: float, spans: list[dict], total_chars: int) -> float:
    """字符位置 → 时间：落在哪条 cue 的字符区间内，就按该 cue 的
    起止时间线性插值。跨 cue 边界也能切在一条 cue 中间。"""
    if total_chars <= 0 or not spans:
        return 0.0
    position = min(max(position, 0.0), float(total_chars))
    for span in spans:
        if span["char_end"] <= 0:
            continue
        if position <= span["char_end"]:
            width = span["char_end"] - span["char_start"]
            frac = (position - span["char_start"]) / width if width > 0 else 0.0
            frac = min(max(frac, 0.0), 1.0)
            return span["start"] + frac * (span["end"] - span["start"])
    return spans[-1]["end"]


def build_scene_windows(plan: ScriptPlan, sub_maker, audio_duration: float) -> list[dict]:
    """按场景旁白字符边界把整篇 TTS 时间轴切成场景时间窗。

    cues 字符总数与旁白字符总数可能不等（TTS 规范化增删字符），按比例
    映射到 cue 字符轴再插值；拿不到 cues 时按字符数比例分配总时长。
    最后一窗吃掉剩余时长，保证窗口总和 == 音频时长。
    """
    audio_duration = max(float(audio_duration or 0), 0.0)
    counts = [_narration_chars(scene.narration) for scene in plan.scenes]
    total = sum(counts)
    rows = _cue_rows(sub_maker) if sub_maker is not None else []
    cue_chars = sum(row["chars"] for row in rows)

    boundaries = [0.0]
    if total > 0 and cue_chars > 0:
        spans = []
        cursor = 0
        for row in rows:
            spans.append({
                "char_start": cursor,
                "char_end": cursor + row["chars"],
                "start": row["start"],
                "end": row["end"],
            })
            cursor += row["chars"]
        ratio = cue_chars / total
        acc = 0
        for count in counts[:-1]:
            acc += count
            boundaries.append(
                min(max(_boundary_time(acc * ratio, spans, cue_chars), 0.0), audio_duration)
            )
    elif total > 0:
        acc = 0
        for count in counts[:-1]:
            acc += count
            boundaries.append(audio_duration * acc / total)
    else:
        # 全部空旁白：均分时间窗（画面哑剧场景）。
        step = audio_duration / len(plan.scenes)
        boundaries = [step * i for i in range(len(plan.scenes))]
    boundaries.append(audio_duration)
    # 浮点插值可能产生极小的逆序；单调化保证窗口非负。
    for i in range(1, len(boundaries)):
        boundaries[i] = max(boundaries[i], boundaries[i - 1])

    windows = []
    for index, scene in enumerate(plan.scenes):
        start, end = boundaries[index], boundaries[index + 1]
        cues = [
            SubtitleCue(start=round(row["start"], 3), end=round(row["end"], 3), text=row["text"])
            for row in rows
            if row["end"] > start and row["start"] < end
        ]
        windows.append({
            "scene_id": scene.id,
            "order": scene.order,
            "start": round(start, 3),
            "end": round(end, 3),
            "duration": round(end - start, 3),
            "cues": cues,
        })
    return windows


def backfill_plan(plan: ScriptPlan, windows: list[dict]) -> ScriptPlan:
    """实测时长与真实 SRT 区间回填（返回副本，不改原方案）。"""
    updated = plan.model_copy(deep=True)
    by_id = {window["scene_id"]: window for window in windows}
    for scene in updated.scenes:
        window = by_id.get(scene.id)
        if window is None:
            continue
        scene.measured_duration = window["duration"]
        scene.subtitle_cues = list(window["cues"])
    return updated


def compile_timeline(
    plan: ScriptPlan,
    scene_bindings: dict[str, list[str]],
    windows: list[dict],
    *,
    clip_speed: float = 1.0,
) -> list[dict]:
    """场景→素材 in/out 序列。窗口时长按绑定文件数均分（末位吃余数），
    入出点绑定只约束首个文件；转场取 scene.transition_to_next，末场景恒 none。

    返回 [{path, in, out, duration, transition}]：in/out 是源素材秒，
    duration 是目标播放秒（combine_videos 变速后按它裁剪）。
    """
    speed = float(clip_speed) if clip_speed and float(clip_speed) > 0 else 1.0
    by_id = {window["scene_id"]: window for window in windows}
    timeline = []
    for index, scene in enumerate(plan.scenes):
        window = by_id.get(scene.id)
        if window is None:
            raise PlanCompileError(f"scene {scene.id} has no time window")
        files = [f for f in (scene_bindings.get(scene.id) or []) if f]
        if not files:
            raise PlanCompileError(f"scene {scene.id} has no bound material")
        share = round(window["duration"] / len(files), 3)
        transition = (
            _TRANSITION_MAP.get(scene.transition_to_next)
            if index < len(plan.scenes) - 1
            else None
        )
        for file_index, file_path in enumerate(files):
            # 末位文件吃掉舍入余数，窗口总长精确不变。
            duration = (
                share
                if file_index < len(files) - 1
                else round(window["duration"] - share * (len(files) - 1), 3)
            )
            in_point = 0.0
            out_point = 0.0
            if file_index == 0 and scene.material is not None:
                in_point = float(scene.material.in_point or 0)
                out_point = float(scene.material.out_point or 0)
            source_end = in_point + duration * speed
            if out_point > in_point:
                source_end = min(source_end, out_point)
            timeline.append({
                "path": file_path,
                "in": round(in_point, 3),
                "out": round(source_end, 3),
                "duration": duration,
                "transition": transition,
            })
    return timeline


def build_project_request(
    plan: ScriptPlan,
    scene_media: dict[str, dict],
    *,
    project_id: str,
    bgm: str | None = None,
    fps: int = 30,
) -> dict:
    """plan → video_project 修订清单（B8 增量渲染入口）。

    scene_media：scene_id → {"footage": 路径, "audio": 路径|None}，均为已制备
    媒体（TTS/素材下载产物）。转场与 compile_timeline 同语义：取本场景
    transition_to_next，末场景恒 none；实测回填的 subtitle_cues 逐场景烧录。
    改一段后重 revise：stage_graph 指纹只失效该场景，其余阶段复用。
    """
    width, height = (1080, 1920) if plan.aspect == "9:16" else (1920, 1080)
    scenes = []
    for index, scene in enumerate(plan.scenes):
        media = scene_media.get(scene.id) or {}
        footage = media.get("footage")
        if not footage:
            raise PlanCompileError(f"scene {scene.id} has no prepared footage")
        audio = media.get("audio")
        if scene.narration.strip() and not audio:
            raise PlanCompileError(
                f"scene {scene.id} narration requires prepared audio"
            )
        cues = (
            [
                {"start": cue.start, "end": cue.end, "text": cue.text}
                for cue in scene.subtitle_cues
            ]
            if isinstance(scene.subtitle_cues, list) and scene.subtitle_cues
            else None
        )
        scenes.append(
            {
                "id": scene.id,
                "footage": footage,
                "audio": audio,
                "narration": scene.narration,
                "duration": scene.measured_duration or scene.est_duration,
                "transition": (
                    scene.transition_to_next
                    if index < len(plan.scenes) - 1
                    else "none"
                ),
                "subtitle": {"cues": cues} if cues else None,
            }
        )
    request = {
        "project_id": project_id,
        "scenes": scenes,
        "settings": {"width": width, "height": height, "fps": fps},
    }
    if bgm:
        request["bgm"] = bgm
    return request