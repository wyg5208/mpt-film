"""stop_at="plan" 任务阶段与方案产物落盘测试（脚本方案专业模式，B2）。

覆盖 plan 阶段状态机、script-plan.json/script.json 落盘、失败降级
warnings 通路、FFmpeg 预检豁免与 generate_plan 参数转发。
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.models.schema import ScriptPlan, VideoAspect, VideoParams
from app.services import task as tm
from app.services import task_artifacts
from app.services.state import MemoryState
from app.utils import utils


def make_plan_dict(target_duration=60, est_duration=60.0, series_id=None):
    plan = ScriptPlan.model_validate(
        {
            "title": "测试影片",
            "target_duration": target_duration,
            "series_id": series_id,
            "scenes": [
                {
                    "id": "s1",
                    "order": 1,
                    "narration": "开场旁白",
                    "est_duration": est_duration,
                }
            ],
        }
    )
    return plan.model_dump(by_alias=True)


class PlanStageTestCase(unittest.TestCase):
    def setUp(self):
        # 产物写盘隔离：plan 阶段会真实写 script.json/script-plan.json，
        # 测试必须落在临时目录而不是真实 storage。
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
        self.state = MemoryState()

    def _start(self, task_id, plan, params=None):
        params = params or VideoParams(video_subject="逆袭", video_script="自定义文案")
        with (
            patch.object(tm, "generate_plan", return_value=plan) as generate_plan,
            patch.object(tm.sm, "state", self.state),
        ):
            result = tm.start(task_id, params, stop_at="plan")
        generate_plan.assert_called_once()
        return result


class TestPlanStage(PlanStageTestCase):
    def test_plan_stage_completes_and_persists_artifacts(self):
        plan = make_plan_dict(series_id="series-1")
        result = self._start("plan-ok", plan)

        self.assertEqual(result, {"script": "自定义文案", "plan": plan})
        task = self.state.get_task("plan-ok")
        self.assertEqual(task["state"], tm.const.TASK_STATE_COMPLETE)
        self.assertEqual(task["progress"], 100)
        self.assertEqual(task["plan"], plan)
        self.assertIsNone(task.get("warnings"))

        plan_file = self.base_dir / "plan-ok" / "script-plan.json"
        self.assertEqual(json.loads(plan_file.read_text(encoding="utf-8")), plan)

        script_data = json.loads(
            (self.base_dir / "plan-ok" / "script.json").read_text(encoding="utf-8")
        )
        self.assertEqual(script_data["script"], "自定义文案")
        self.assertEqual(script_data["plan_revision"], 1)
        self.assertEqual(script_data["series_id"], "series-1")
        self.assertIn("video_seed", script_data)

    def test_plan_failure_falls_back_with_warning(self):
        """方案生成失败不阻断任务：保留 legacy 脚本并走 warnings 通路。"""
        result = self._start("plan-fallback", None)

        self.assertEqual(result, {"script": "自定义文案", "plan": None})
        task = self.state.get_task("plan-fallback")
        self.assertEqual(task["state"], tm.const.TASK_STATE_COMPLETE)
        self.assertIsNone(task["plan"])
        self.assertEqual(
            [w["code"] for w in task["warnings"]], ["script_plan_fallback"]
        )
        self.assertFalse((self.base_dir / "plan-fallback" / "script-plan.json").exists())
        # legacy 脚本清单仍然落盘，快速模式产物不受影响。
        self.assertTrue((self.base_dir / "plan-fallback" / "script.json").exists())

    def test_duration_out_of_tolerance_surfaces_warning(self):
        plan = make_plan_dict(target_duration=60, est_duration=5.0)
        self._start("plan-duration", plan)

        task = self.state.get_task("plan-duration")
        self.assertEqual(task["state"], tm.const.TASK_STATE_COMPLETE)
        self.assertEqual(
            [w["code"] for w in task["warnings"]],
            ["plan_duration_out_of_tolerance"],
        )

    def test_plan_stage_skips_ffmpeg_preflight(self):
        """方案阶段不产音视频，缺少 FFmpeg 不应拒绝任务。"""
        params = VideoParams(video_subject="逆袭", video_script="自定义文案")
        with (
            patch.object(tm.utils, "check_ffmpeg_ready", return_value=False) as check,
            patch.object(tm, "generate_plan", return_value=make_plan_dict()),
            patch.object(tm.sm, "state", self.state),
        ):
            result = tm.start("plan-no-ffmpeg", params, stop_at="plan")

        check.assert_not_called()
        self.assertIsNotNone(result["plan"])

    def test_plan_stage_does_not_generate_terms(self):
        """plan 是独立中间产物：不得触发搜索词/素材等后续付费阶段。"""
        with (
            patch.object(tm, "generate_terms") as generate_terms,
            patch.object(tm, "get_video_materials") as get_materials,
        ):
            self._start("plan-isolated", make_plan_dict())

        generate_terms.assert_not_called()
        get_materials.assert_not_called()


class TestGeneratePlanForwarding(unittest.TestCase):
    def test_params_forwarded_to_llm_layer(self):
        params = VideoParams(
            video_subject="逆袭",
            video_language="zh-CN",
            video_aspect=VideoAspect.landscape,
            voice_name="zh-CN-YunxiNeural",
            video_script_prompt="节奏更快",
            plan_target_duration=45,
            plan_scene_count=4,
        )
        script = "第一段[pause]第二段"
        with patch.object(tm.llm, "generate_script_plan", return_value=None) as gen:
            result = tm.generate_plan("forward", params, script)

        self.assertIsNone(result)
        kwargs = gen.call_args.kwargs
        self.assertEqual(kwargs["video_subject"], "逆袭")
        self.assertEqual(kwargs["language"], "zh-CN")
        self.assertEqual(kwargs["video_script"], utils.remove_pause_tags(script))
        self.assertEqual(kwargs["target_duration"], 45)
        self.assertEqual(kwargs["scene_count"], 4)
        self.assertEqual(kwargs["aspect"], "16:9")
        self.assertEqual(kwargs["voice_name"], "zh-CN-YunxiNeural")
        self.assertEqual(kwargs["video_script_prompt"], "节奏更快")

    def test_defaults_and_square_aspect_fallback(self):
        """未指定方案参数时回落 60s；1:1 画幅回落到 9:16。"""
        params = VideoParams(video_subject="逆袭", video_aspect=VideoAspect.square)
        with patch.object(tm.llm, "generate_script_plan", return_value=None) as gen:
            tm.generate_plan("defaults", params, "文案")

        kwargs = gen.call_args.kwargs
        self.assertEqual(kwargs["target_duration"], 60.0)
        self.assertIsNone(kwargs["scene_count"])
        self.assertEqual(kwargs["aspect"], "9:16")
        self.assertEqual(kwargs["voice_name"], "")


class TestScriptPlanArtifacts(PlanStageTestCase):
    def test_write_read_round_trip(self):
        plan = make_plan_dict()
        task_artifacts.write_script_plan("artifact-ok", plan)
        self.assertEqual(task_artifacts.read_script_plan("artifact-ok"), plan)

    def test_missing_plan_returns_none(self):
        self.assertIsNone(task_artifacts.read_script_plan("artifact-missing"))

    def test_corrupted_plan_returns_none(self):
        task_dir = self.base_dir / "artifact-broken"
        task_dir.mkdir(parents=True, exist_ok=True)
        (task_dir / "script-plan.json").write_text("{broken", encoding="utf-8")
        self.assertIsNone(task_artifacts.read_script_plan("artifact-broken"))

    def test_non_object_plan_returns_none(self):
        task_dir = self.base_dir / "artifact-list"
        task_dir.mkdir(parents=True, exist_ok=True)
        (task_dir / "script-plan.json").write_text("[1, 2]", encoding="utf-8")
        self.assertIsNone(task_artifacts.read_script_plan("artifact-list"))

    def test_write_is_atomic_replace(self):
        """重复写入完整替换，不残留临时文件。"""
        first = make_plan_dict()
        second = make_plan_dict(series_id="series-2")
        task_artifacts.write_script_plan("artifact-replace", first)
        task_artifacts.write_script_plan("artifact-replace", second)

        self.assertEqual(task_artifacts.read_script_plan("artifact-replace"), second)
        leftovers = list((self.base_dir / "artifact-replace").glob("*.tmp"))
        self.assertEqual(leftovers, [])


if __name__ == "__main__":
    unittest.main()