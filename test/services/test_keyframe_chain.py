# -*- coding: utf-8 -*-
"""本地关键帧链测试（B5）：共享边界帧复用、prompt 组装、引擎路由。

comfy_local 以桩替代（不触网不烧 GPU）；抽帧用真实 ffmpeg 夹具。
"""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.models.schema import ScriptPlan, Series
from app.services import keyframe_chain as kc
from app.services import review


def make_plan(**overrides):
    payload = {
        "title": "关键帧链",
        "episode_id": "ep1",
        "target_duration": 10,
        "status": "confirmed",
        "style": {"tone": "cinematic", "palette": "teal and orange"},
        "scenes": [
            {
                "id": "s1", "order": 1, "engine": "local_fl2v",
                "narration": "开场", "visual": "a quiet street at dawn",
                "keyframe": {"first_prompt": "street wide shot",
                             "last_prompt": "street close shot",
                             "last": "ep1-s1-l.png"},
            },
            {
                "id": "s2", "order": 2, "engine": "local_fl2v",
                "narration": "转折", "visual": "the door opens",
                "keyframe": {"first": "ep1-s1-l.png", "shared_with_prev": True,
                             "last_prompt": "door fully open"},
            },
        ],
    }
    payload.update(overrides)
    return ScriptPlan.model_validate(payload)


WINDOWS = [
    {"scene_id": "s1", "order": 1, "start": 0.0, "end": 4.0, "duration": 4.0, "cues": []},
    {"scene_id": "s2", "order": 2, "start": 4.0, "end": 10.0, "duration": 6.0, "cues": []},
]


def fake_image(prompt, **kwargs):
    return {"path": f"/fake/{kwargs['out_name']}.png", "seed": 1,
            "request_key": "k", "cached": False, "receipt": {}}


def fake_video(prompt, **kwargs):
    return {"path": f"/fake/{kwargs['out_name']}.mp4", "seed": 2,
            "request_key": "k", "cached": False, "receipt": {}}


class ChainTestCase(unittest.TestCase):
    def setUp(self):
        patches = [
            patch.object(kc.comfy_local, "is_online", return_value=True),
            patch.object(kc.comfy_local, "generate_image", side_effect=fake_image),
            patch.object(kc.comfy_local, "generate_video", side_effect=fake_video),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)


class TestPromptComposition(unittest.TestCase):
    def test_keyframe_prompt_layers_character_location_style(self):
        series = Series.model_validate({
            "id": "sr",
            "characters": [{"id": "c1", "appearance_prompt": "young woman in red coat",
                            "reference_images": ["/no/such/ref.png"]}],
            "locations": [{"id": "l1", "prompt": "old town alley"}],
        })
        plan = make_plan()
        plan.scenes[0].characters = ["c1"]
        plan.scenes[0].location = "l1"
        prompt = kc.compose_keyframe_prompt(plan.scenes[0], plan, series, which="first")
        self.assertEqual(
            prompt,
            "street wide shot, young woman in red coat, old town alley, "
            "cinematic, teal and orange",
        )

    def test_keyframe_prompt_falls_back_to_visual(self):
        plan = make_plan()
        plan.scenes[0].keyframe.first_prompt = ""
        prompt = kc.compose_keyframe_prompt(plan.scenes[0], plan, None, which="first")
        self.assertTrue(prompt.startswith("a quiet street at dawn"))

    def test_empty_description_raises(self):
        plan = make_plan()
        plan.scenes[0].keyframe.first_prompt = ""
        plan.scenes[0].visual = ""
        plan.scenes[0].narration = ""
        with self.assertRaises(kc.KeyframeChainError):
            kc.compose_keyframe_prompt(plan.scenes[0], plan, None, which="first")

    def test_motion_prompt_uses_visual_and_style(self):
        plan = make_plan()
        self.assertEqual(
            kc.compose_motion_prompt(plan.scenes[0], plan),
            "a quiet street at dawn, cinematic, teal and orange",
        )


class TestGenerateLocalSceneVideos(ChainTestCase):
    def test_no_local_scenes_is_noop(self):
        plan = make_plan()
        for scene in plan.scenes:
            scene.engine = "stock"
        with patch.object(kc.comfy_local, "is_online") as online:
            bindings, keyframes = kc.generate_local_scene_videos("t", plan, WINDOWS)
        online.assert_not_called()
        self.assertEqual((bindings, keyframes), ({}, {}))

    def test_offline_engine_raises(self):
        with patch.object(kc.comfy_local, "is_online", return_value=False):
            with self.assertRaises(kc.KeyframeChainError) as ctx:
                kc.generate_local_scene_videos("t", make_plan(), WINDOWS)
        self.assertIn("ComfyUI is not running", str(ctx.exception))

    def test_shared_boundary_frame_reuses_previous_last(self):
        plan = make_plan()
        with (
            patch.object(kc.comfy_local, "generate_image", side_effect=fake_image) as image,
            patch.object(kc.comfy_local, "generate_video", side_effect=fake_video) as video,
        ):
            bindings, keyframes = kc.generate_local_scene_videos("t", plan, WINDOWS)
        # s1 首/尾 + s2 尾 = 3 张关键帧；s2 首帧直接复用 s1 尾帧文件。
        self.assertEqual(image.call_count, 3)
        out_names = [call.kwargs["out_name"] for call in image.call_args_list]
        self.assertEqual(out_names, ["ep1-s1-f", "ep1-s1-l", "ep1-s2-l"])
        self.assertEqual(keyframes["s2"]["first"], keyframes["s1"]["last"])
        self.assertEqual(video.call_count, 2)
        s2_kwargs = video.call_args_list[1].kwargs
        self.assertEqual(s2_kwargs["first_frame"], keyframes["s1"]["last"])
        self.assertEqual(s2_kwargs["last_frame"], "/fake/ep1-s2-l.png")
        self.assertEqual(s2_kwargs["duration"], 6.0)
        self.assertEqual(bindings, {"s1": ["/fake/ep1-s1.mp4"], "s2": ["/fake/ep1-s2.mp4"]})
        # 不修改传入方案：回填是调用方的职责。
        self.assertEqual(plan.scenes[1].keyframe.first, "ep1-s1-l.png")

    def test_user_provided_keyframe_files_skip_generation(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "first.png"
            first.write_bytes(b"png")
            plan = make_plan()
            plan.scenes[0].keyframe.first = str(first)
            plan.scenes[0].keyframe.last = str(first)
            plan.scenes[1].keyframe.shared_with_prev = False
            plan.scenes[1].keyframe.first = str(first)
            plan.scenes[1].keyframe.last = str(first)
            with (
                patch.object(kc.comfy_local, "generate_image", side_effect=fake_image) as image,
                patch.object(kc.comfy_local, "generate_video", side_effect=fake_video),
            ):
                bindings, keyframes = kc.generate_local_scene_videos("t", plan, WINDOWS)
            image.assert_not_called()
            self.assertEqual(keyframes["s1"], {"first": str(first), "last": str(first)})
            self.assertEqual(len(bindings), 2)

    def test_local_i2v_skips_last_frame(self):
        plan = make_plan()
        plan.scenes[0].engine = "local_i2v"
        plan.scenes[1].engine = "local_i2v"
        plan.scenes[1].keyframe.shared_with_prev = False
        with (
            patch.object(kc.comfy_local, "generate_image", side_effect=fake_image) as image,
            patch.object(kc.comfy_local, "generate_video", side_effect=fake_video) as video,
        ):
            _, keyframes = kc.generate_local_scene_videos("t", plan, WINDOWS)
        # 每场景只生成首帧；尾帧留空由模型自由收尾。
        self.assertEqual(image.call_count, 2)
        self.assertEqual(keyframes["s1"]["last"], "")
        for call in video.call_args_list:
            self.assertEqual(call.kwargs["last_frame"], "")

    def test_shared_after_stock_scene_raises(self):
        plan = make_plan()
        plan.scenes[0].engine = "stock"
        with self.assertRaises(kc.KeyframeChainError) as ctx:
            kc.generate_local_scene_videos("t", plan, WINDOWS)
        self.assertIn("previous", str(ctx.exception))

    def test_missing_window_raises(self):
        with self.assertRaises(kc.KeyframeChainError) as ctx:
            kc.generate_local_scene_videos("t", make_plan(), WINDOWS[:1])
        self.assertIn("s2", str(ctx.exception))

    def test_quality_tier_routes_model_presets(self):
        plan = make_plan(quality_tier="final")
        with (
            patch.object(kc.comfy_local, "generate_image", side_effect=fake_image) as image,
            patch.object(kc.comfy_local, "generate_video", side_effect=fake_video) as video,
        ):
            kc.generate_local_scene_videos("t", plan, WINDOWS)
        for call in image.call_args_list:
            self.assertEqual(call.kwargs["model"], "sdxl-quality")
        for call in video.call_args_list:
            self.assertEqual(call.kwargs["model"], "minimax-final")

    def test_progress_callback_monotonic(self):
        seen = []
        kc.generate_local_scene_videos(
            "t", make_plan(), WINDOWS, progress_callback=seen.append
        )
        self.assertEqual(seen, [0.5, 1.0])


class TestExtractFrame(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ffmpeg = review._ffmpeg_binary()

    def test_first_and_last_frame_extraction(self):
        import subprocess

        with tempfile.TemporaryDirectory() as tmp:
            clip = str(Path(tmp) / "clip.mp4")
            subprocess.run(
                [self.ffmpeg, "-nostdin", "-v", "error", "-y",
                 "-f", "lavfi", "-i", "color=c=red:size=64x64:rate=10:duration=2",
                 "-c:v", "libx264", "-pix_fmt", "yuv420p", clip],
                check=True, capture_output=True, timeout=60,
            )
            first = str(Path(tmp) / "first.png")
            last = str(Path(tmp) / "last.png")
            self.assertTrue(kc.extract_frame(clip, first))
            self.assertTrue(kc.extract_frame(clip, last, at_end=True))
            self.assertGreater(Path(first).stat().st_size, 0)
            self.assertGreater(Path(last).stat().st_size, 0)

    def test_missing_input_returns_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = str(Path(tmp) / "frame.png")
            self.assertFalse(kc.extract_frame(str(Path(tmp) / "no.mp4"), out))


if __name__ == "__main__":
    unittest.main()