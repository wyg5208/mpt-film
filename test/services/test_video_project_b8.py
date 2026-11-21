# -*- coding: utf-8 -*-
"""B8 契约：video_project 字幕/转场 + plan→spec 增量渲染。

- 离线指纹契约：旧 spec 指纹逐字节不变；改一段只失效一段；字幕/转场
  只影响所属场景的 render 阶段（audio/timing 不动）。
- 真机门禁（bundled ffmpeg，ffprobe 缺失走 -i 降级）：改一段重 revise，
  未触碰场景的 audio/timing/scene 全部 reused=True。
- 桥接：build_project_request 与 compile_timeline 同转场语义。
"""

import shutil
import subprocess
from pathlib import Path

import pytest

from app.models.schema import ScriptPlan, SubtitleCue
from app.services import plan_compiler
from app.services.video_project import (
    FFPROBE_UNAVAILABLE,
    ProjectError,
    VideoProject,
    stage_graph,
)
from app.utils import utils


def _bundled_ffmpeg() -> str:
    binary = utils.get_ffmpeg_binary()
    if binary == "ffmpeg" and not shutil.which("ffmpeg"):
        pytest.skip("no working ffmpeg binary available")
    return binary


def _media(binary, arguments):
    subprocess.run(
        [binary, "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
         "-threads", "1", *arguments],
        check=True,
    )


@pytest.fixture
def native(tmp_path):
    binary = _bundled_ffmpeg()
    for color in ("red", "blue", "green"):
        _media(
            binary,
            ["-f", "lavfi", "-i", f"color=c={color}:s=64x64:r=10:d=0.6",
             "-c:v", "libx264", "-pix_fmt", "yuv420p",
             str(tmp_path / f"{color}.mp4")],
        )
    _media(
        binary,
        ["-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=0.6",
         str(tmp_path / "voice.wav")],
    )
    return binary, tmp_path


def _frame(binary, path, second):
    return subprocess.check_output(
        [binary, "-v", "error", "-ss", str(second), "-i", str(path),
         "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
    )


def _pixel(binary, path, second, x=32, y=56):
    raw = _frame(binary, path, second)
    offset = (y * 64 + x) * 3
    return tuple(raw[offset:offset + 3])


def make_plan(**overrides) -> ScriptPlan:
    payload = {
        "title": "增量渲染",
        "target_duration": 2,
        "scenes": [
            {"id": "s1", "order": 1, "narration": "开场旁白",
             "est_duration": 0.6, "transition_to_next": "fade"},
            {"id": "s2", "order": 2, "narration": "", "est_duration": 0.6},
        ],
    }
    payload.update(overrides)
    return ScriptPlan.model_validate(payload)


def _scene_media(tmp_path, closing="blue.mp4"):
    return {
        "s1": {"footage": str(tmp_path / "red.mp4"),
               "audio": str(tmp_path / "voice.wav")},
        "s2": {"footage": str(tmp_path / closing)},
    }


def _small_request(plan, media, project_id):
    """桥接默认 1080x1920；像素探针测试统一降到 64x64@10 加快渲染。"""
    request = plan_compiler.build_project_request(
        plan, media, project_id=project_id
    )
    request["settings"] = {"width": 64, "height": 64, "fps": 10}
    return request


# ---------------------------------------------------------------------------
# 离线指纹契约（不需要 ffmpeg）
# ---------------------------------------------------------------------------


def _spec(scenes):
    return {
        "settings": {"width": 64, "height": 64, "fps": 10},
        "toolchain": {"ffmpeg": "fixture", "ffprobe": "fixture"},
        "scenes": scenes,
    }


def _scene(scene_id, **overrides):
    scene = {
        "id": scene_id,
        "narration": "",
        "audio": None,
        "duration": 0.6,
        "footage": {"sha256": scene_id * 8, "path": f"assets/{scene_id}"},
    }
    scene.update(overrides)
    return scene


def _fingerprints(spec):
    return {stage.key: stage.fingerprint for stage in stage_graph(spec)}


def test_legacy_spec_fingerprints_are_byte_compatible():
    legacy = _spec([_scene("s1"), _scene("s2")])
    explicit = _spec(
        [
            _scene("s1", transition="none", subtitle=None),
            _scene("s2", transition="none", subtitle=None),
        ]
    )
    assert _fingerprints(legacy) == _fingerprints(explicit)


def test_one_scene_change_isolates_invalidation():
    before = _fingerprints(_spec([_scene("s1"), _scene("s2"), _scene("s3")]))
    changed_scene = _scene("s2", footage={"sha256": "new", "path": "assets/new"})
    after = _fingerprints(_spec([_scene("s1"), changed_scene, _scene("s3")]))
    changed = {key for key in before if before[key] != after[key]}
    # audio/timing 不依赖画面素材：换 footage 只失效本场景 render 与汇总。
    assert changed == {"s2:scene", "assembly", "export"}


def test_subtitle_only_invalidates_scene_render():
    before = _fingerprints(_spec([_scene("s1"), _scene("s2")]))
    cues = {"cues": [{"start": 0.0, "end": 0.5, "text": "你好"}]}
    after = _fingerprints(_spec([_scene("s1"), _scene("s2", subtitle=cues)]))
    changed = {key for key in before if before[key] != after[key]}
    assert changed == {"s2:scene", "assembly", "export"}


def test_transition_only_invalidates_scene_render():
    before = _fingerprints(_spec([_scene("s1"), _scene("s2")]))
    after = _fingerprints(_spec([_scene("s1"), _scene("s2", transition="fade")]))
    changed = {key for key in before if before[key] != after[key]}
    assert changed == {"s2:scene", "assembly", "export"}


# ---------------------------------------------------------------------------
# 桥接契约（离线）
# ---------------------------------------------------------------------------


def test_bridge_maps_transitions_cues_and_settings(tmp_path):
    plan = make_plan()
    plan.scenes[0].subtitle_cues = [SubtitleCue(start=0.0, end=0.5, text="开场")]
    plan.scenes[1].measured_duration = 0.7
    request = plan_compiler.build_project_request(
        plan, _scene_media(tmp_path), project_id="episode-b8"
    )
    assert request["settings"] == {"width": 1080, "height": 1920, "fps": 30}
    first, second = request["scenes"]
    # 与 compile_timeline 同语义：转场取本场景 transition_to_next，末场景恒 none。
    assert first["transition"] == "fade"
    assert second["transition"] == "none"
    assert first["subtitle"] == {"cues": [{"start": 0.0, "end": 0.5, "text": "开场"}]}
    assert second["subtitle"] is None
    assert second["duration"] == 0.7
    assert "bgm" not in request


def test_bridge_fail_closed_on_missing_media(tmp_path):
    plan = make_plan()
    with pytest.raises(plan_compiler.PlanCompileError):
        plan_compiler.build_project_request(plan, {}, project_id="episode-b8")
    with pytest.raises(plan_compiler.PlanCompileError):
        plan_compiler.build_project_request(
            plan,
            {"s1": {"footage": str(tmp_path / "red.mp4")},
             "s2": {"footage": str(tmp_path / "blue.mp4")}},
            project_id="episode-b8",
        )


# ---------------------------------------------------------------------------
# 真机渲染门禁（bundled ffmpeg；ffprobe 缺失降级）
# ---------------------------------------------------------------------------


def test_revision_validation_rejects_bad_transition_and_cues(native):
    binary, tmp_path = native
    project = VideoProject(tmp_path / "project")
    base = {
        "project_id": "episode-b8",
        "settings": {"width": 64, "height": 64, "fps": 10},
        "scenes": [{"id": "s1", "footage": "red.mp4", "duration": 0.6}],
    }
    request = {**base, "scenes": [{**base["scenes"][0], "transition": "warp"}]}
    with pytest.raises(ProjectError):
        project.create_revision(request, relative_to=tmp_path, ffmpeg=binary)
    for cues in (
        [{"start": 0.5, "end": 0.1, "text": "倒序"}],
        [{"start": 0.0, "end": 0.5, "text": ""}],
        [{"start": 0.0, "end": 0.5, "text": "ok", "mystery": 1}],
    ):
        request = {
            **base,
            "scenes": [{**base["scenes"][0], "subtitle": {"cues": cues}}],
        }
        with pytest.raises(ProjectError):
            project.create_revision(request, relative_to=tmp_path, ffmpeg=binary)
    # ffprobe 哨兵断言必须与运行顺序无关：显式传入不存在的二进制，
    # 避免全套件中其他测试泄漏 PATH（真实 ffprobe 可见）时假失败。
    spec = project.create_revision(
        base,
        relative_to=tmp_path,
        ffmpeg=binary,
        ffprobe=str(tmp_path / "missing-ffprobe.exe"),
    )
    assert spec["toolchain"]["ffprobe"] == FFPROBE_UNAVAILABLE


def test_incremental_rerender_reuses_untouched_scenes(native):
    """B8 门禁：改一段只重渲一段（stage_graph 指纹命中证明）。"""
    binary, tmp_path = native
    project = VideoProject(tmp_path / "project")
    plan = make_plan()
    first = project.create_revision(
        _small_request(plan, _scene_media(tmp_path), "episode-b8"),
        relative_to=tmp_path,
        ffmpeg=binary,
    )
    status = project.render(ffmpeg=binary)
    assert status["state"] == "succeeded"

    # 只换 s2 的画面素材；s1 的旁白/音频/画面全部不动。
    second = project.create_revision(
        _small_request(plan, _scene_media(tmp_path, closing="green.mp4"), "episode-b8"),
        relative_to=tmp_path,
        ffmpeg=binary,
    )
    status = project.render(ffmpeg=binary)
    assert status["state"] == "succeeded"
    stages = status["stages"]
    for key in ("s1:audio", "s1:timing", "s1:scene"):
        assert stages[key]["reused"] is True, key
    assert stages["s2:scene"]["reused"] is False
    assert stages["assembly"]["reused"] is False
    assert stages["export"]["reused"] is False
    # compare 视图与渲染复用判定一致。
    comparison = {
        item["stage"]: item["change"]
        for item in project.compare(first["revision_id"], second["revision_id"])
    }
    assert comparison["s1:scene"] == "unchanged"
    assert comparison["s2:scene"] == "changed"


def test_subtitle_burn_changes_bottom_pixels(native):
    binary, tmp_path = native
    plan = make_plan(scenes=[
        {"id": "s1", "order": 1, "narration": "", "est_duration": 0.6},
    ])
    media = {"s1": {"footage": str(tmp_path / "red.mp4")}}
    project = VideoProject(tmp_path / "plain")
    project.create_revision(
        _small_request(plan, media, "plain"),
        relative_to=tmp_path, ffmpeg=binary,
    )
    plain = project.render(ffmpeg=binary)["export"]["path"]

    plan.scenes[0].subtitle_cues = [SubtitleCue(start=0.0, end=0.6, text="测试字幕")]
    titled = VideoProject(tmp_path / "titled")
    titled.create_revision(
        _small_request(plan, media, "titled"),
        relative_to=tmp_path, ffmpeg=binary,
    )
    burned = titled.render(ffmpeg=binary)["export"]["path"]
    # 字号 12、MarginV 14 → 文字底边 y=50，字形带约 y38..50；比较整条
    # 底部文字带而不是单点，避免探针落在字形间隙上。
    strip = slice(30 * 64 * 3, 56 * 64 * 3)
    assert _frame(binary, plain, 0.3)[strip] != _frame(binary, burned, 0.3)[strip]


def test_fade_slide_zoom_render(native):
    binary, tmp_path = native
    for transition in ("fade", "slide", "zoom"):
        # 双场景：s1 的 transition_to_next 生效，末场景恒 none。
        plan = make_plan()
        plan.scenes[0].transition_to_next = transition
        media = _scene_media(tmp_path)
        project = VideoProject(tmp_path / f"fx-{transition}")
        project.create_revision(
            _small_request(plan, media, f"fx-{transition}"),
            relative_to=tmp_path, ffmpeg=binary,
        )
        status = project.render(ffmpeg=binary)
        assert status["state"] == "succeeded", transition
        if transition == "fade":
            # 黑场淡入：首帧接近纯黑（与 moviepy FadeIn 观感一致）。
            assert sum(_pixel(binary, status["export"]["path"], 0.0)) < 30