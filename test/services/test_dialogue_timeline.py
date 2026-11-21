# -*- coding: utf-8 -*-
"""dialogue_timeline 契约测试（B6）：多音色路由 + 逐句拼接 + 独立时间窗。

TTS 注入假实现（真实 ffmpeg 合成正弦波 mp3），不触网；旁白主路径
（全 narrator）不进入本模块由 has_dialogue 守卫。
"""

import subprocess
import sys
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.models.schema import ScriptPlan, Series
from app.services import dialogue_timeline as dt
from app.services import review, voice


def make_plan(speakers=("narrator", "c1", "c2")) -> ScriptPlan:
    scenes = []
    for index, speaker in enumerate(speakers):
        scenes.append({
            "id": f"s{index + 1}",
            "order": index + 1,
            "speaker": speaker,
            "narration": f"台词{index + 1}号。",
            "est_duration": 1.0,
        })
    return ScriptPlan.model_validate({
        "title": "对白测试",
        "target_duration": 3,
        "voice": {"name": "zh-CN-XiaoxiaoNeural", "rate": 1.0},
        "scenes": scenes,
    })


def make_series() -> Series:
    return Series.model_validate({
        "id": "sr-dlg",
        "characters": [
            {"id": "c1", "voice_name": "zh-CN-YunxiNeural"},
            {"id": "c2", "voice_name": "zh-CN-YunyangNeural"},
            {"id": "c3", "voice_name": ""},
        ],
    })


class TestRouting(unittest.TestCase):
    def test_has_dialogue_guard(self):
        self.assertFalse(dt.has_dialogue(make_plan(("narrator", "narrator"))))
        self.assertTrue(dt.has_dialogue(make_plan(("narrator", "c1"))))

    def test_narrator_uses_plan_voice(self):
        plan = make_plan()
        self.assertEqual(
            dt.resolve_speaker_voice(plan, None, "narrator"),
            "zh-CN-XiaoxiaoNeural",
        )

    def test_character_routes_to_bible_voice(self):
        plan = make_plan()
        series = make_series()
        self.assertEqual(
            dt.resolve_speaker_voice(plan, series, "c1"), "zh-CN-YunxiNeural"
        )
        self.assertEqual(
            dt.resolve_speaker_voice(plan, series, "c2"), "zh-CN-YunyangNeural"
        )

    def test_missing_series_character_voice_rejected(self):
        plan = make_plan()
        with self.assertRaises(dt.DialogueError):
            dt.resolve_speaker_voice(plan, None, "c1")
        with self.assertRaises(dt.DialogueError):
            dt.resolve_speaker_voice(plan, make_series(), "cX")
        with self.assertRaises(dt.DialogueError):
            dt.resolve_speaker_voice(plan, make_series(), "c3")

    def test_validate_reports_first_bad_scene(self):
        plan = make_plan(("narrator", "cX"))
        error = dt.validate_dialogue_routing(plan, make_series())
        self.assertIn("s2", error)
        self.assertIsNone(dt.validate_dialogue_routing(make_plan(), make_series()))


class TestAssemble(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ffmpeg = review._ffmpeg_binary()
        if not cls.ffmpeg or not Path(cls.ffmpeg).exists():
            raise unittest.SkipTest("ffmpeg binary not available")

    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.base = Path(temp_dir.name)
        self.calls = []

        def fake_tts(*, text, voice_name, voice_rate, voice_file):
            self.calls.append({"text": text, "voice_name": voice_name})
            seconds = 0.6 if len(self.calls) % 2 else 0.9
            subprocess.run([
                self.ffmpeg, "-nostdin", "-v", "error", "-y",
                "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
                "-ar", "24000", "-ac", "1", voice_file,
            ], check=True)
            return SimpleNamespace(cues=[
                SimpleNamespace(
                    start=timedelta(seconds=0),
                    end=timedelta(seconds=seconds),
                    content=text,
                ),
            ])

        self.fake_tts = fake_tts

    def assemble(self, plan=None, series=None, **kwargs):
        plan = plan or make_plan()
        series = series if series is not None else make_series()
        out = str(self.base / "audio.mp3")
        return dt.assemble_dialogue_audio(
            plan, series, out, tts=self.fake_tts, **kwargs
        )

    def test_voice_routing_per_line(self):
        self.assemble()
        self.assertEqual(
            [c["voice_name"] for c in self.calls],
            ["zh-CN-XiaoxiaoNeural", "zh-CN-YunxiNeural", "zh-CN-YunyangNeural"],
        )

    def test_windows_contiguous_and_sum_to_duration(self):
        out, duration, sub_maker, windows = self.assemble()
        self.assertTrue(Path(out).is_file())
        self.assertEqual(len(windows), 3)
        self.assertEqual(windows[0]["start"], 0.0)
        for prev, nxt in zip(windows, windows[1:]):
            self.assertEqual(prev["end"], nxt["start"])
        self.assertAlmostEqual(windows[-1]["end"], duration, delta=0.002)
        self.assertAlmostEqual(
            sum(w["duration"] for w in windows), duration, delta=0.002
        )
        # 0.6/0.9/0.6 的正弦波：窗口时长贴近真实解码时长。
        self.assertAlmostEqual(windows[0]["duration"], 0.6, delta=0.06)
        self.assertAlmostEqual(windows[1]["duration"], 0.9, delta=0.06)

    def test_cues_shifted_to_absolute_timeline(self):
        _, duration, sub_maker, windows = self.assemble()
        self.assertEqual(len(sub_maker.cues), 3)
        for window in windows:
            for cue in window["cues"]:
                self.assertGreaterEqual(cue.start, window["start"] - 0.001)
                self.assertLessEqual(cue.end, window["end"] + 0.001)
        # 第二句 cue 的起点 == 第一窗终点（样本级偏移，无漂移）。
        self.assertAlmostEqual(
            windows[1]["cues"][0].start, windows[0]["end"], delta=0.002
        )
        self.assertAlmostEqual(sub_maker.duration, duration, delta=0.002)

    def test_empty_narration_scene_gets_silence_window(self):
        plan = make_plan(("narrator", "c1"))
        plan.scenes[1].narration = ""
        plan.scenes[1].est_duration = 0.8
        _, duration, _, windows = self.assemble(plan=plan)
        self.assertEqual(len(self.calls), 1)
        self.assertAlmostEqual(windows[1]["duration"], 0.8, delta=0.06)
        self.assertEqual(windows[1]["cues"], [])

    def test_tts_failure_fails_once_with_voice_hint(self):
        def broken_tts(**kwargs):
            self.calls.append(kwargs)
            return None

        out = str(self.base / "audio.mp3")
        with self.assertRaises(dt.DialogueError) as ctx:
            dt.assemble_dialogue_audio(
                make_plan(), make_series(), out, tts=broken_tts
            )
        self.assertEqual(len(self.calls), 1)
        self.assertIn("zh-CN-XiaoxiaoNeural", str(ctx.exception))
        self.assertIn("language", str(ctx.exception))
        self.assertFalse(Path(out).exists())

    def test_routing_error_before_any_tts(self):
        out = str(self.base / "audio.mp3")
        with self.assertRaises(dt.DialogueError):
            dt.assemble_dialogue_audio(
                make_plan(("narrator", "cX")), make_series(), out,
                tts=self.fake_tts,
            )
        self.assertEqual(self.calls, [])

    def test_progress_callback_monotonic(self):
        seen = []
        self.assemble(on_progress=seen.append)
        self.assertEqual(len(seen), 3)
        self.assertAlmostEqual(seen[-1], 1.0)
        self.assertEqual(seen, sorted(seen))


if __name__ == "__main__":
    unittest.main()