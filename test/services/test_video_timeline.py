"""combine_videos 显式时间线测试（脚本方案专业模式，B4）。

两层验证：
1. 打桩层：时间线条目精确决定源窗口/目标时长/转场，random 模式不再
   打乱，坏条目跳过、越界钳制；timeline=None 时旧切片逻辑保持不变。
2. 真实渲染门禁：同 seed 同 plan 两次渲染，产物 SHA-256 必须一致
   （B4 验收条款）。小尺寸 lavfi 素材，编码开销秒级。
"""

import hashlib
import subprocess
import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.models.schema import VideoAspect, VideoConcatMode, VideoTransitionMode
from app.services import plan_compiler, review, video as vd
from app.models.schema import ScriptPlan


class _RecordingClip:
    """最小 MoviePy 接口；subclipped 调用按素材身份记录源窗口。"""

    def __init__(self, recorder, origin, duration=10.0, size=(480, 840), span=None):
        self.recorder = recorder
        self.origin = origin
        self.duration = duration
        self.size = size
        self.span = span
        self.mask = None

    @property
    def w(self):
        return self.size[0]

    @property
    def h(self):
        return self.size[1]

    def subclipped(self, start_time, end_time):
        self.recorder["windows"].append(
            (self.origin, round(start_time, 3), round(end_time, 3))
        )
        return _RecordingClip(
            self.recorder, self.origin,
            duration=end_time - start_time, size=self.size,
            span=(round(start_time, 3), round(end_time, 3)),
        )

    def with_speed_scaled(self, speed):
        return _RecordingClip(
            self.recorder, self.origin,
            duration=self.duration / speed, size=self.size, span=self.span,
        )

    def close(self):
        pass


def _run_combine(timeline, *, durations=None, audio_duration=4.0,
                 concat_mode=VideoConcatMode.random,
                 transition=VideoTransitionMode.shuffle,
                 clip_speed=1.0, max_clip_duration=5, seed=7, paths=None):
    """打桩编码，只观察时间线如何落到片段窗口/时长/转场。"""
    durations = durations or {}
    recorder = {"windows": [], "writes": [], "transitions": []}

    def fake_open(video_path, *args, **kwargs):
        duration = durations.get(video_path, 10.0)
        if duration is None:
            raise OSError(f"unreadable: {video_path}")
        return _RecordingClip(recorder, video_path, duration=duration)

    def fake_write(clip, clip_file, **kwargs):
        recorder["writes"].append((clip.origin, clip.duration))
        return clip_file

    def make_transition_recorder(name):
        def record(clip, *args, **kwargs):
            recorder["transitions"].append((name, clip.origin))
            return clip
        return record

    with ExitStack() as stack:
        stack.enter_context(patch.object(vd, "_open_video_clip_quietly", fake_open))
        stack.enter_context(patch.object(vd, "close_clip", lambda clip: None))
        stack.enter_context(
            patch.object(vd, "AudioFileClip", lambda path: _RecordingClip(recorder, "audio", duration=audio_duration))
        )
        stack.enter_context(patch.object(vd, "_write_videofile_with_codec_fallback", fake_write))
        stack.enter_context(patch.object(vd, "concat_video_clips_with_ffmpeg", lambda **kwargs: None))
        stack.enter_context(patch.object(vd, "delete_files", lambda files: None))
        stack.enter_context(patch.object(vd, "_get_clip_processing_concurrency", return_value=1))
        stack.enter_context(patch.object(vd, "_fit_clip_to_canvas", lambda clip, **kwargs: clip))
        for name in ("fadein", "fadeout", "slidein", "slideout", "zoomin", "zoomout"):
            stack.enter_context(
                patch.object(vd.video_effects, f"{name}_transition", make_transition_recorder(name))
            )
        vd.combine_videos(
            combined_video_path="combined.mp4",
            video_paths=list(paths or []),
            audio_file="voice.mp3",
            video_aspect=VideoAspect.portrait,
            video_concat_mode=concat_mode,
            video_transition_mode=transition,
            max_clip_duration=max_clip_duration,
            threads=1,
            clip_speed=clip_speed,
            seed=seed,
            timeline=timeline,
        )
    return recorder


class TestTimelineMode(unittest.TestCase):
    def test_entries_define_exact_windows_durations_and_transitions(self):
        timeline = [
            {"path": "a.mp4", "in": 2.0, "out": 5.0, "duration": 3.0,
             "transition": VideoTransitionMode.fade_in.value},
            {"path": "b.mp4", "in": 0.0, "out": 4.0, "duration": 2.0,
             "transition": None},
        ]
        recorder = _run_combine(timeline, paths=["b.mp4", "a.mp4"])
        # 源窗口精确来自条目；b 的 4s 源画面按目标 2s 裁剪。
        self.assertIn(("a.mp4", 2.0, 5.0), recorder["windows"])
        self.assertIn(("b.mp4", 0.0, 4.0), recorder["windows"])
        self.assertIn(("b.mp4", 0, 2.0), recorder["windows"])
        # random 模式不得重排时间线：写出顺序即条目顺序。
        self.assertEqual([origin for origin, _ in recorder["writes"]], ["a.mp4", "b.mp4"])
        self.assertEqual([duration for _, duration in recorder["writes"]], [3.0, 2.0])
        # 转场来自条目而非全局 shuffle：a 淡入，b 硬切。
        self.assertEqual(recorder["transitions"], [("fadein", "a.mp4")])

    def test_unreadable_entries_skipped_and_windows_clamped(self):
        timeline = [
            {"path": "bad.mp4", "in": 0, "out": 3, "duration": 3, "transition": None},
            {"path": "a.mp4", "in": 1.0, "out": 10.0, "duration": 5.0, "transition": None},
        ]
        recorder = _run_combine(
            timeline, durations={"bad.mp4": None, "a.mp4": 3.0}, audio_duration=1.0
        )
        # 坏源跳过；越界 out 钳制到真实素材时长 3s。
        self.assertEqual(recorder["windows"], [("a.mp4", 1.0, 3.0)])
        self.assertEqual([origin for origin, _ in recorder["writes"]], ["a.mp4"])

    def test_non_positive_out_falls_back_to_duration_times_speed(self):
        timeline = [
            {"path": "a.mp4", "in": 0, "out": 0, "duration": 1.5, "transition": None},
        ]
        recorder = _run_combine(timeline, clip_speed=2.0, audio_duration=1.0)
        self.assertEqual(recorder["windows"], [("a.mp4", 0.0, 3.0)])
        self.assertEqual(recorder["writes"], [("a.mp4", 1.5)])

    def test_empty_window_entry_is_skipped(self):
        timeline = [
            {"path": "a.mp4", "in": 5.0, "out": 5.0, "duration": 0, "transition": None},
            {"path": "a.mp4", "in": 0, "out": 2, "duration": 2, "transition": None},
        ]
        recorder = _run_combine(timeline, durations={"a.mp4": 3.0}, audio_duration=1.0)
        self.assertEqual(recorder["windows"], [("a.mp4", 0.0, 2.0)])

    def test_none_timeline_keeps_legacy_slicing(self):
        # 无时间线：random 模式仍按 max_clip_duration 切片并应用全局转场。
        recorder = _run_combine(
            None, durations={"a.mp4": 4.0, "b.mp4": 4.0},
            max_clip_duration=2, audio_duration=7.0,
            transition=VideoTransitionMode.fade_in,
            paths=["b.mp4", "a.mp4"],
        )
        self.assertEqual(
            sorted(recorder["windows"]),
            [("a.mp4", 0, 2), ("a.mp4", 2, 4), ("b.mp4", 0, 2), ("b.mp4", 2, 4)],
        )
        self.assertEqual(len(recorder["transitions"]), 4)
        self.assertTrue(all(name == "fadein" for name, _ in recorder["transitions"]))


def _make_plan():
    return ScriptPlan.model_validate({
        "title": "渲染门禁",
        "target_duration": 2.5,
        "status": "confirmed",
        "scenes": [
            {"id": "s1", "order": 1, "narration": "开场", "est_duration": 1.0,
             "transition_to_next": "fade"},
            {"id": "s2", "order": 2, "narration": "收尾", "est_duration": 1.5},
        ],
    })


class TestRealRenderDeterminism(unittest.TestCase):
    """B4 门禁：同 seed 同 plan 两次渲染产物逐字节一致。"""

    @classmethod
    def setUpClass(cls):
        # 与 review 测试同源：优先 imageio-ffmpeg 自带二进制，不依赖 PATH。
        cls.ffmpeg = review._ffmpeg_binary()
        if not cls.ffmpeg or not Path(cls.ffmpeg).exists():
            raise unittest.SkipTest("ffmpeg binary not available")

    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.base = Path(temp_dir.name)
        base_cmd = [self.ffmpeg, "-nostdin", "-v", "error", "-y", "-threads", "1"]
        self.sources = {}
        for color in ("red", "green", "blue"):
            source = self.base / f"{color}.mp4"
            subprocess.run([
                *base_cmd, "-f", "lavfi", "-i",
                f"color=c={color}:s=64x64:r=10:d=3",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", str(source),
            ], check=True)
            self.sources[color] = str(source)
        self.audio = str(self.base / "voice.wav")
        subprocess.run([
            *base_cmd, "-f", "lavfi", "-i", "sine=frequency=220:duration=2.5",
            "-ar", "44100", self.audio,
        ], check=True)

    def _render(self, output_dir):
        output_dir.mkdir(parents=True, exist_ok=True)
        plan = _make_plan()
        windows = [
            {"scene_id": "s1", "order": 1, "start": 0.0, "end": 1.0,
             "duration": 1.0, "cues": []},
            {"scene_id": "s2", "order": 2, "start": 1.0, "end": 2.5,
             "duration": 1.5, "cues": []},
        ]
        bindings = {
            "s1": [self.sources["red"]],
            "s2": [self.sources["green"], self.sources["blue"]],
        }
        timeline = plan_compiler.compile_timeline(plan, bindings, windows)
        output = str(output_dir / "combined.mp4")
        with patch.dict(vd.config.app, {"video_codec": "libx264", "video_clip_concurrency": 1}):
            vd.combine_videos(
                combined_video_path=output,
                video_paths=[file for files in bindings.values() for file in files],
                audio_file=self.audio,
                video_aspect=VideoAspect.square,
                video_concat_mode=VideoConcatMode.random,
                video_transition_mode=VideoTransitionMode.shuffle,
                max_clip_duration=5,
                threads=1,
                seed=7,
                timeline=timeline,
            )
        return output

    def test_same_seed_same_plan_renders_identical_bytes(self):
        first = self._render(self.base / "run-1")
        second = self._render(self.base / "run-2")
        digest_first = hashlib.sha256(Path(first).read_bytes()).hexdigest()
        digest_second = hashlib.sha256(Path(second).read_bytes()).hexdigest()
        self.assertEqual(digest_first, digest_second)
        # 清理契约：临时片段与 concat 清单不残留。
        for run in ("run-1", "run-2"):
            self.assertEqual(list((self.base / run).glob("temp-clip-*.mp4")), [])
            self.assertEqual(list((self.base / run).glob("ffmpeg-concat-*.txt")), [])

    def test_rendered_duration_matches_audio(self):
        from moviepy import VideoFileClip

        output = self._render(self.base / "run-duration")
        with VideoFileClip(output, audio=False) as rendered:
            self.assertAlmostEqual(rendered.duration, 2.5, delta=0.15)


if __name__ == "__main__":
    unittest.main()