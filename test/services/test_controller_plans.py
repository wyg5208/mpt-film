"""脚本方案草稿库控制器测试（专业短剧「脚本方案」页 REST 层）。

验证草稿 CRUD、编辑语义（draft 回退 + revision++）、confirm 语义、
镜头结构操作（调序/增删）以及 execute 的方案对齐规则（与 Main.py 一致）。
"""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.controllers.v1 import plans
from app.models.exception import HttpException
from app.services import plan_store, series_store


def _payload(**overrides):
    payload = {
        "title": "逆袭",
        "target_duration": 12,
        "scenes": [
            {"id": "s1", "order": 1, "est_duration": 5.0, "narration": "第一幕"},
            {"id": "s2", "order": 2, "est_duration": 7.0, "narration": ""},
        ],
    }
    payload.update(overrides)
    return payload


class TestPlansController(unittest.TestCase):
    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp(prefix="plans-controller-"))
        self._tmp_series = Path(tempfile.mkdtemp(prefix="wizard-series-"))
        patcher = patch.object(plan_store, "plans_root", return_value=self._tmp)
        patcher.start()
        self.addCleanup(patcher.stop)
        series_patcher = patch.object(series_store, "series_root", return_value=self._tmp_series)
        series_patcher.start()
        self.addCleanup(series_patcher.stop)
        self.addCleanup(lambda: shutil.rmtree(self._tmp, ignore_errors=True))
        self.addCleanup(lambda: shutil.rmtree(self._tmp_series, ignore_errors=True))
        self._request = SimpleNamespace(
            headers={"x-task-id": "request-123"}, method="POST"
        )

    def _save(self, payload=None):
        return plan_store.save_plan(payload or _payload())

    def test_generate_creates_and_lists_draft(self):
        generated = _payload(title="AI 生成")
        with patch.object(plans.llm, "generate_script_plan", return_value=generated):
            response = plans.generate_plan(
                self._request, plans.PlanGenerateRequest(video_subject=" 逆袭 ")
            )
        plan_id = response["data"]["plan_id"]
        self.assertTrue(str(plan_id).startswith("pl-"))
        self.assertEqual(response["data"]["plan"]["title"], "AI 生成")
        summaries = {item["id"] for item in plans.list_plans(self._request)["data"]["plans"]}
        self.assertIn(plan_id, summaries)

    def test_generate_requires_subject(self):
        with self.assertRaises(HttpException):
            plans.generate_plan(
                self._request, plans.PlanGenerateRequest(video_subject="   ")
            )

    def test_scene_patch_edit_semantics(self):
        plan_id = self._save()
        response = plans.patch_plan_scene(
            self._request, plan_id, "s1",
            plans.PlanScenePatchRequest(field="narration", value="改写"),
        )
        data = response["data"]
        self.assertEqual(data["plan"]["status"], "draft")
        self.assertEqual(data["plan"]["revision"], 2)
        self.assertEqual(data["plan"]["scenes"][0]["narration"], "改写")

        # keywords 以逗号切分；engine 白名单外的值拒绝。
        data = plans.patch_plan_scene(
            self._request, plan_id, "s1",
            plans.PlanScenePatchRequest(field="keywords", value=" 夜色, 天台 "),
        )["data"]
        self.assertEqual(data["plan"]["scenes"][0]["keywords"], ["夜色", "天台"])
        data = plans.patch_plan_scene(
            self._request, plan_id, "s1",
            plans.PlanScenePatchRequest(field="engine", value="local_fl2v"),
        )["data"]
        self.assertEqual(data["plan"]["scenes"][0]["engine"], "local_fl2v")
        with self.assertRaises(HttpException):
            plans.patch_plan_scene(
                self._request, plan_id, "s1",
                plans.PlanScenePatchRequest(field="engine", value="cloud"),
            )

    def test_confirm_keeps_revision(self):
        plan_id = self._save()
        data = plans.confirm_plan(self._request, plan_id)["data"]
        self.assertEqual(data["plan"]["status"], "confirmed")
        self.assertEqual(data["plan"]["revision"], 1)

    def test_execute_aligns_params_and_confirms(self):
        payload = _payload(
            scenes=[
                {
                    "id": "s1", "order": 1, "est_duration": 5.0,
                    "narration": "第一幕", "engine": "local_fl2v",
                },
                {
                    "id": "s2", "order": 2, "est_duration": 7.0,
                    "narration": "", "engine": "local_i2v",
                },
            ]
        )
        plan_id = self._save(payload)
        with patch.object(plans.video_controller, "create_task") as create_task:
            create_task.return_value = {"status": 200, "data": {"task_id": "t-1"}}
            response = plans.execute_plan(self._request, plan_id)
        self.assertEqual(response["data"]["task_id"], "t-1")
        body = create_task.call_args.args[1]
        self.assertEqual(create_task.call_args.kwargs["stop_at"], "video")
        # 与 Main.py 对齐规则：本地引擎镜头全选 → video_source=local。
        self.assertEqual(body.video_source, "local")
        self.assertEqual(body.plan_target_duration, 12)
        self.assertEqual(body.voice_name, "zh-CN-XiaoxiaoNeural")
        self.assertEqual(body.video_subject, "逆袭")
        self.assertEqual(body.script_plan.model_dump()["status"], "confirmed")
        # execute 幂等确认：确认落盘。
        stored = plan_store.load_plan(plan_id)
        self.assertEqual(stored["status"], "confirmed")

    def test_execute_requires_narration(self):
        plan_id = self._save(
            _payload(
                scenes=[{"id": "s1", "order": 1, "est_duration": 5.0, "narration": ""}]
            )
        )
        with self.assertRaises(HttpException):
            plans.execute_plan(self._request, plan_id)

    def test_move_delete_add_scene(self):
        plan_id = self._save()
        data = plans.move_plan_scene(
            self._request, plan_id, "s2", plans.PlanSceneMoveRequest(delta=-1)
        )["data"]
        self.assertEqual([s["id"] for s in data["plan"]["scenes"]], ["s2", "s1"])
        self.assertEqual(data["plan"]["scenes"][0]["order"], 1)
        self.assertEqual(data["plan"]["scenes"][0]["relation_to_prev"], "establish")
        self.assertFalse(data["plan"]["scenes"][1]["keyframe"]["shared_with_prev"])
        self.assertEqual(data["plan"]["status"], "draft")
        self.assertEqual(data["plan"]["revision"], 2)

        # 越界移动是无操作，不产生 revision 噪音。
        data = plans.move_plan_scene(
            self._request, plan_id, "s2", plans.PlanSceneMoveRequest(delta=-1)
        )["data"]
        self.assertEqual(data["plan"]["revision"], 2)

        data = plans.add_plan_scene(self._request, plan_id)["data"]
        self.assertEqual(data["plan"]["scenes"][-1]["id"], "s3")
        self.assertEqual(data["plan"]["scenes"][-1]["est_duration"], 5.0)
        self.assertEqual(data["plan"]["revision"], 3)

        data = plans.delete_plan_scene(self._request, plan_id, "s1")["data"]
        self.assertEqual([s["id"] for s in data["plan"]["scenes"]], ["s2", "s3"])
        self.assertEqual(data["plan"]["revision"], 4)

        # 只剩一个镜头时拒绝删除。
        plans.delete_plan_scene(self._request, plan_id, "s2")
        with self.assertRaises(HttpException):
            plans.delete_plan_scene(self._request, plan_id, "s3")

    def test_settings_patch_paths(self):
        plan_id = self._save()
        data = plans.patch_plan_setting(
            self._request, plan_id,
            plans.PlanSettingPatchRequest(path="voice.rate", value="1.3"),
        )["data"]
        self.assertEqual(data["plan"]["voice"]["rate"], 1.3)
        self.assertEqual(data["plan"]["status"], "draft")
        with self.assertRaises(HttpException):
            plans.patch_plan_setting(
                self._request, plan_id,
                plans.PlanSettingPatchRequest(path="scenes", value=[]),
            )

    def test_regenerate_keeps_locked_scenes(self):
        plan_id = self._save(
            _payload(
                scenes=[
                    {"id": "s1", "order": 1, "est_duration": 5.0,
                     "narration": "锁定旁白", "locked": True},
                    {"id": "s2", "order": 2, "est_duration": 7.0, "narration": ""},
                ]
            )
        )
        regenerated = _payload(
            title="新标题",
            scenes=[
                {"id": "s1", "order": 1, "est_duration": 3.0, "narration": "重写"},
                {"id": "s2", "order": 2, "est_duration": 9.0, "narration": "重写二"},
            ],
        )
        with patch.object(plans.llm, "generate_script_plan", return_value=regenerated):
            data = plans.regenerate_plan(self._request, plan_id)["data"]
        locked = data["plan"]["scenes"][0]
        self.assertTrue(locked["locked"])
        self.assertEqual(locked["narration"], "锁定旁白")
        self.assertEqual(locked["est_duration"], 5.0)
        self.assertEqual(data["plan"]["scenes"][1]["narration"], "重写二")
        self.assertEqual(data["plan"]["revision"], 2)
        self.assertEqual(data["plan"]["status"], "draft")

    def test_import_forces_draft_and_bumps_revision(self):
        imported = _payload(status="confirmed", revision=3)
        data = plans.import_plan(
            self._request, plans.PlanImportRequest(plan=imported)
        )["data"]
        self.assertEqual(data["plan"]["status"], "draft")
        self.assertEqual(data["plan"]["revision"], 4)

    def test_local_bundle_switches_writer_engine(self):
        fake_config = MagicMock()
        fake_config.app = {"ollama_model_name": ""}
        fake_config.update_config_values_nonblocking.return_value = True
        with patch.object(plans, "config", fake_config):
            response = plans.apply_local_bundle(self._request)
        changes = fake_config.update_config_values_nonblocking.call_args.args[1]
        self.assertEqual(changes, {"llm_provider": "ollama", "ollama_model_name": "gemma4:26b"})
        self.assertTrue(response["data"]["applied"])
        # 已配置模型名时不覆盖默认值。
        fake_config.app = {"ollama_model_name": "qwen3:32b"}
        with patch.object(plans, "config", fake_config):
            plans.apply_local_bundle(self._request)
        changes = fake_config.update_config_values_nonblocking.call_args.args[1]
        self.assertEqual(changes, {"llm_provider": "ollama"})

    def test_engines_status_shape(self):
        with patch("app.services.comfy_local.local_engines_status") as probe:
            probe.return_value = {"comfyui": {"online": True}}
            data = plans.engines_status(self._request)["data"]
        self.assertTrue(data["engines"]["comfyui"]["online"])
        probe.assert_called_once_with()

    def test_wizard_generate_links_series_and_plan(self):
        """向导 → 系列草稿 + ep1 绑定的方案草稿（联动关系核心契约）。"""
        generated = _payload(title="逆袭")
        idea = "被裁员的女生靠一份贷款方案逆袭"
        with patch.object(plans.llm, "generate_script_plan", return_value=generated) as gen:
            response = plans.wizard_generate(
                self._request,
                plans.WizardGenerateRequest(
                    story_idea=idea,
                    genre="urban_revenge",
                    episode_duration=90,
                    episode_count=2,
                    characters=[
                        plans.WizardCharacterInput(
                            name="林总",
                            voice_name="zh-CN-XiaoxiaoNeural",
                            appearance_prompt="西装",
                        ),
                        plans.WizardCharacterInput(name="  "),
                    ],
                ),
            )
        data = response["data"]
        self.assertTrue(data["series_id"].startswith("sr-"))
        self.assertTrue(data["plan_id"].startswith("pl-"))
        gen.assert_called_once()
        kwargs = gen.call_args.kwargs
        self.assertEqual(kwargs["video_subject"], idea)
        self.assertEqual(kwargs["target_duration"], 90)
        self.assertEqual(kwargs["aspect"], "9:16")

        series = series_store.load_series(data["series_id"])
        self.assertEqual(series.genre_template, "urban_revenge")
        # 空名角色剔除；剧集数与请求一致。
        self.assertEqual(len(series.characters), 1)
        self.assertEqual(series.characters[0].name, "林总")
        self.assertEqual(len(series.episodes), 2)
        self.assertEqual(series.episodes[0].plan_id, data["plan_id"])
        self.assertIsNone(series.episodes[1].plan_id)

        # 方案草稿进入草稿库，脚本方案页选择器可见。
        summaries = {item["id"] for item in plans.list_plans(self._request)["data"]["plans"]}
        self.assertIn(data["plan_id"], summaries)

    def test_wizard_generate_validations(self):
        with self.assertRaises(HttpException):
            plans.wizard_generate(
                self._request, plans.WizardGenerateRequest(story_idea="   ")
            )
        with self.assertRaises(HttpException):
            plans.wizard_generate(
                self._request,
                plans.WizardGenerateRequest(story_idea="逆袭", genre="western"),
            )

    def test_narration_patch_re_estimates_duration(self):
        """旁白编辑后按语速经验值回填预估时长（Main.py 同语义）。"""
        plan_id = self._save()
        text = "她站在天台俯瞰整座城市，眼里的火没有灭"
        data = plans.patch_plan_scene(
            self._request, plan_id, "s1",
            plans.PlanScenePatchRequest(field="narration", value=text),
        )["data"]
        self.assertEqual(data["plan"]["scenes"][0]["est_duration"], round(len(text) / 4.2, 1))


if __name__ == "__main__":
    unittest.main()
