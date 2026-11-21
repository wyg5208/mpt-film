"""方案驱动执行的任务层测试（脚本方案专业模式，B4）。

覆盖 preflight 门禁（付费场景需 confirmed、B4 仅库存源）、terms 由
keywords 编译、整篇 TTS 后 cue 切窗回填落盘、逐场景素材绑定，以及
generate_final_videos 的 plan_context 语义（单条成片 + 显式时间线 +
实测时长警告）。无方案路径的批量语义保持不变。
"""

import json
import sys
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.models.schema import ScriptPlan, VideoParams
from app.services import plan_compiler
from app.services import task as tm
from app.services.state import MemoryState


def make_plan_dict(**overrides):
    payload = {
        "title": "执行测试",
        "target_duration": 5,
        "status": "confirmed",
        "scenes": [
            {"id": "s1", "order": 1, "narration": "aaaa", "est_duration": 2,
             "keywords": ["k1"], "transition_to_next": "fade"},
            {"id": "s2", "order": 2, "narration": "bbbbbb", "est_duration": 3,
             "keywords": ["k2"]},
        ],
    }
    payload.update(overrides)
    return ScriptPlan.model_validate(payload).model_dump(by_alias=True)


def fake_sub_maker():
    return SimpleNamespace(cues=[
        SimpleNamespace(start=timedelta(seconds=0), end=timedelta(seconds=2), content="aaaa"),
        SimpleNamespace(start=timedelta(seconds=2), end=timedelta(seconds=5), content="bbbbbb"),
    ])


class PlanExecTestCase(unittest.TestCase):
    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.base_dir = Path(temp_dir.name)

        def fake_task_dir(task_id):
            task_dir = self.base_dir / str(task_id)
            task_dir.mkdir(parents=True, exist_ok=True)
            return str(task_dir)

        task_dir_patcher = patch.object(tm.utils, "task_dir", side_effect=fake_task_dir)
        task_dir_patcher.start()
        self.addCleanup(task_dir_patcher.stop)
        ffmpeg_patcher = patch.object(tm.utils, "check_ffmpeg_ready", return_value=True)
        ffmpeg_patcher.start()
        self.addCleanup(ffmpeg_patcher.stop)
        self.state = MemoryState()
        state_patcher = patch.object(tm.sm, "state", self.state)
        state_patcher.start()
        self.addCleanup(state_patcher.stop)


class TestPlanPreflightGates(PlanExecTestCase):
    def test_paid_scenes_require_confirmed_plan(self):
        plan = make_plan_dict(status="draft")
        plan["scenes"][0]["cost"] = {"tier": "paid", "estimate_cny": 1.5}
        params = VideoParams(video_subject="付费", script_plan=plan)
        result = tm.start("gate-paid", params)
        self.assertEqual(result["state"], tm.const.TASK_STATE_FAILED)
        self.assertEqual(result["failed_stage"], "preflight")
        self.assertIn("paid scenes", result["error"])
        self.assertIn("s1", result["error"])

    def test_cloud_ai_engine_counts_as_paid(self):
        plan = make_plan_dict(status="draft")
        plan["scenes"][1]["engine"] = "cloud_ai"
        params = VideoParams(video_subject="云端", script_plan=plan)
        result = tm.start("gate-cloud", params)
        self.assertEqual(result["failed_stage"], "preflight")
        self.assertIn("s2", result["error"])

    def test_local_source_requires_local_scenes(self):
        # B5 后 video_source=local 合法，但仅限全本地引擎方案；
        # 全库存方案配 local 源仍是确定性错误。
        params = VideoParams(
            video_subject="本地", script_plan=make_plan_dict(), video_source="local"
        )
        result = tm.start("gate-source", params)
        self.assertEqual(result["failed_stage"], "preflight")
        self.assertIn("local engines", result["error"])

    def test_cloud_ai_scenes_rejected_even_confirmed(self):
        plan = make_plan_dict()
        plan["scenes"][1]["engine"] = "cloud_ai"
        plan["scenes"][1]["cost"] = {"tier": "paid", "estimate_cny": 1.0}
        params = VideoParams(video_subject="云端", script_plan=plan)
        result = tm.start("gate-cloud-confirmed", params)
        self.assertEqual(result["failed_stage"], "preflight")
        self.assertIn("cloud_ai scenes", result["error"])
        self.assertIn("s2", result["error"])

    def test_local_scenes_require_comfyui_online(self):
        plan = make_plan_dict()
        for scene in plan["scenes"]:
            scene["engine"] = "local_fl2v"
            scene["visual"] = "a quiet street"
        params = VideoParams(
            video_subject="离线", script_plan=plan, video_source="local"
        )
        with patch.object(tm.comfy_local, "is_online", return_value=False):
            result = tm.start("gate-offline", params)
        self.assertEqual(result["failed_stage"], "preflight")
        self.assertIn("ComfyUI is not running", result["error"])

    def test_confirmed_free_stock_plan_passes_preflight(self):
        params = VideoParams(video_subject="放行", script_plan=make_plan_dict())
        with patch.object(tm, "generate_terms") as generate_terms:
            result = tm.start("gate-ok", params, stop_at="terms")
        self.assertEqual(result["terms"], ["k1", "k2"])
        generate_terms.assert_not_called()


class TestPlanTermsAndWindowing(PlanExecTestCase):
    def test_terms_compile_from_keywords_without_llm(self):
        params = VideoParams(video_subject="编译", script_plan=make_plan_dict())
        with (
            patch.object(tm, "generate_script") as generate_script,
            patch.object(tm, "generate_terms") as generate_terms,
        ):
            result = tm.start("terms-plan", params, stop_at="terms")
        generate_script.assert_not_called()
        generate_terms.assert_not_called()
        self.assertEqual(result["script"], "aaaa\nbbbbbb")
        self.assertEqual(result["terms"], ["k1", "k2"])
        task = self.state.get_task("terms-plan")
        self.assertEqual(task["state"], tm.const.TASK_STATE_COMPLETE)

    def test_materials_stage_binds_per_scene_and_backfills_plan(self):
        params = VideoParams(video_subject="切窗", script_plan=make_plan_dict())
        bindings = {
            "s1": [str(self.base_dir / "m1.mp4")],
            "s2": [str(self.base_dir / "m2.mp4"), str(self.base_dir / "m3.mp4")],
        }
        with (
            patch.object(tm, "generate_audio", return_value=("audio.mp3", 5.0, fake_sub_maker())) as generate_audio,
            patch.object(tm, "generate_subtitle", return_value="subtitle.srt"),
            patch.object(tm.material, "download_scene_materials", return_value=bindings) as download,
            patch.object(tm, "get_video_materials") as legacy_materials,
        ):
            result = tm.start("materials-plan", params, stop_at="materials")

        # 整篇一次 TTS：脚本是方案旁白拼接，不是逐场景独立合成。
        self.assertEqual(generate_audio.call_args.args[2], "aaaa\nbbbbbb")
        legacy_materials.assert_not_called()
        kwargs = download.call_args.kwargs
        self.assertEqual(download.call_args.args[1], {"s1": ["k1"], "s2": ["k2"]})
        self.assertEqual(download.call_args.args[2], {"s1": 2.0, "s2": 3.0})
        self.assertEqual(kwargs["source"], "pexels")
        self.assertIsInstance(kwargs["seed"], int)

        self.assertEqual(
            result["materials"],
            [bindings["s1"][0], bindings["s2"][0], bindings["s2"][1]],
        )
        # 实测时长与真实 cue 区间回填并持久化。
        plan_file = self.base_dir / "materials-plan" / "script-plan.json"
        persisted = json.loads(plan_file.read_text(encoding="utf-8"))
        self.assertEqual(persisted["scenes"][0]["measured_duration"], 2.0)
        self.assertEqual(persisted["scenes"][1]["measured_duration"], 3.0)
        self.assertEqual(
            persisted["scenes"][0]["subtitle_cues"],
            [{"start": 0.0, "end": 2.0, "text": "aaaa"}],
        )
        script_data = json.loads(
            (self.base_dir / "materials-plan" / "script.json").read_text(encoding="utf-8")
        )
        self.assertEqual(script_data["plan_revision"], 1)

    def test_missing_scene_material_fails_task(self):
        params = VideoParams(video_subject="缺素材", script_plan=make_plan_dict())
        bindings = {"s1": [str(self.base_dir / "m1.mp4")], "s2": []}
        with (
            patch.object(tm, "generate_audio", return_value=("audio.mp3", 5.0, fake_sub_maker())),
            patch.object(tm, "generate_subtitle", return_value="subtitle.srt"),
            patch.object(tm.material, "download_scene_materials", return_value=bindings),
        ):
            result = tm.start("materials-missing", params, stop_at="materials")
        self.assertEqual(result["state"], tm.const.TASK_STATE_FAILED)
        self.assertEqual(result["failed_stage"], "materials")
        self.assertIn("s2", result["error"])


class TestGenerateFinalVideosPlanContext(PlanExecTestCase):
    def _run(self, plan_dict, *, plan_context=True, video_count=1):
        plan = ScriptPlan.model_validate(plan_dict)
        windows = plan_compiler.build_scene_windows(plan, fake_sub_maker(), 5.0)
        bindings = {
            "s1": [str(self.base_dir / "m1.mp4")],
            "s2": [str(self.base_dir / "m2.mp4")],
        }
        params = VideoParams(
            video_subject="渲染", video_count=video_count, video_seed=7,
            script_plan=plan_dict,
        )
        context = (
            {"plan": plan, "windows": windows, "bindings": bindings}
            if plan_context else None
        )
        with (
            patch.object(tm.video, "combine_videos") as combine,
            patch.object(tm.video, "generate_video", return_value=True),
        ):
            finals, combined, warnings = tm.generate_final_videos(
                "render-plan", params,
                [file for files in bindings.values() for file in files],
                "audio.mp3", "subtitle.srt", 5.0,
                plan_context=context,
            )
        return finals, combined, warnings, combine, bindings, windows, plan

    def test_plan_context_renders_single_video_with_explicit_timeline(self):
        finals, combined, warnings, combine, bindings, windows, plan = self._run(
            make_plan_dict(), video_count=3
        )
        # 方案驱动恒单条成片，批量参数不适用。
        self.assertEqual(len(finals), 1)
        self.assertEqual(len(combined), 1)
        combine.assert_called_once()
        kwargs = combine.call_args.kwargs
        self.assertEqual(
            kwargs["timeline"],
            plan_compiler.compile_timeline(plan, bindings, windows),
        )
        self.assertEqual(kwargs["seed"], 7)
        self.assertEqual(warnings, [])

    def test_measured_duration_out_of_tolerance_warns(self):
        _, _, warnings, _, _, _, _ = self._run(make_plan_dict(target_duration=60))
        self.assertEqual(
            [w["code"] for w in warnings], ["plan_duration_out_of_tolerance"]
        )
        self.assertEqual(warnings[0]["measured_total"], 5.0)
        self.assertEqual(warnings[0]["target_duration"], 60)

    def test_no_plan_context_keeps_batch_semantics(self):
        finals, combined, warnings, combine, _, _, _ = self._run(
            make_plan_dict(), plan_context=False, video_count=2
        )
        self.assertEqual(len(finals), 2)
        self.assertEqual(combine.call_count, 2)
        for call in combine.call_args_list:
            self.assertIsNone(call.kwargs["timeline"])
        self.assertEqual(warnings, [])


class TestDialogueModeGates(PlanExecTestCase):
    """B6 多音色对白：preflight 路由门禁 + 独立音频装配，旁白主路径不受影响。"""

    @staticmethod
    def _dialogue_plan(**overrides):
        plan = make_plan_dict(**overrides)
        plan["series_id"] = "sr-dlg"
        plan["scenes"][1]["speaker"] = "c1"
        return plan

    @staticmethod
    def _series(voice_name="zh-CN-YunxiNeural"):
        return SimpleNamespace(
            id="sr-dlg",
            characters=[SimpleNamespace(id="c1", voice_name=voice_name)],
        )

    def test_dialogue_requires_persisted_series(self):
        plan = self._dialogue_plan()
        plan["series_id"] = None
        params = VideoParams(video_subject="对白", script_plan=plan)
        result = tm.start("dlg-no-series", params)
        self.assertEqual(result["failed_stage"], "preflight")
        self.assertIn("series", result["error"])

    def test_dialogue_character_needs_voice_binding(self):
        params = VideoParams(
            video_subject="对白", script_plan=self._dialogue_plan()
        )
        with patch.object(
            tm.series_store, "load_series", return_value=self._series(voice_name="")
        ):
            result = tm.start("dlg-no-voice", params)
        self.assertEqual(result["failed_stage"], "preflight")
        self.assertIn("voice_name", result["error"])

    def test_dialogue_rejects_custom_audio_file(self):
        params = VideoParams(
            video_subject="对白", script_plan=self._dialogue_plan(),
            custom_audio_file="voice.mp3",
        )
        result = tm.start("dlg-custom", params)
        self.assertEqual(result["failed_stage"], "preflight")
        self.assertIn("custom_audio_file", result["error"])

    def test_valid_dialogue_passes_preflight(self):
        params = VideoParams(
            video_subject="对白", script_plan=self._dialogue_plan()
        )
        with patch.object(
            tm.series_store, "load_series", return_value=self._series()
        ):
            result = tm.start("dlg-ok", params, stop_at="terms")
        self.assertEqual(result["terms"], ["k1", "k2"])

    def test_audio_stage_uses_assembler_and_backfills(self):
        plan_dict = self._dialogue_plan()
        params = VideoParams(video_subject="对白", script_plan=plan_dict)
        plan = ScriptPlan.model_validate(plan_dict)
        windows = plan_compiler.build_scene_windows(plan, fake_sub_maker(), 5.0)
        audio_file = str(self.base_dir / "dlg-audio" / "audio.mp3")
        with (
            patch.object(tm.series_store, "load_series", return_value=self._series()),
            patch.object(
                tm.dialogue_timeline, "assemble_dialogue_audio",
                return_value=(audio_file, 5.0, fake_sub_maker(), windows),
            ) as assemble,
            patch.object(tm, "generate_audio") as generate_audio,
        ):
            result = tm.start("dlg-audio", params, stop_at="audio")
        generate_audio.assert_not_called()
        assemble.assert_called_once()
        self.assertEqual(result["audio_file"], audio_file)
        self.assertEqual(result["audio_duration"], 5.0)
        persisted = json.loads(
            (self.base_dir / "dlg-audio" / "script-plan.json").read_text(encoding="utf-8")
        )
        self.assertEqual(persisted["scenes"][0]["measured_duration"], 2.0)
        self.assertEqual(persisted["scenes"][1]["measured_duration"], 3.0)

    def test_narrator_plan_never_enters_dialogue_assembler(self):
        # 旁白主路径回归守卫：全 narrator 方案仍走整篇一次 TTS。
        params = VideoParams(video_subject="旁白", script_plan=make_plan_dict())
        with (
            patch.object(
                tm, "generate_audio",
                return_value=("audio.mp3", 5.0, fake_sub_maker()),
            ) as generate_audio,
            patch.object(tm.dialogue_timeline, "assemble_dialogue_audio") as assemble,
        ):
            result = tm.start("narr-audio", params, stop_at="audio")
        assemble.assert_not_called()
        generate_audio.assert_called_once()
        self.assertEqual(result["audio_duration"], 5.0)


if __name__ == "__main__":
    unittest.main()