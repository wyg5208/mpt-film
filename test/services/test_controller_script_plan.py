"""POST /script-plans 控制器契约测试（脚本方案专业模式，B2）。

验证方案任务复用 create_task 排队链路、stop_at="plan" 正确传递，
以及 TaskVideoRequest 对新方案参数的透传。
"""

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.controllers.v1 import video as video_controller
from app.models.schema import TaskVideoRequest


class TestScriptPlanController(unittest.TestCase):
    @staticmethod
    def _request():
        return SimpleNamespace(headers={"x-task-id": "request-123"}, method="POST")

    def test_create_script_plan_queues_plan_stage_task(self):
        body = TaskVideoRequest(
            video_subject="逆袭",
            plan_target_duration=45,
            plan_scene_count=4,
        )
        with (
            patch.object(video_controller.sm.state, "update_task") as update_task,
            patch.object(video_controller.task_manager, "add_task") as add_task,
        ):
            response = video_controller.create_script_plan(
                MagicMock(), self._request(), body
            )

        update_task.assert_called_once()
        add_task.assert_called_once()
        # 队列入口是带日志捕获的 webui_task.run_api_task 包装（而非裸 tm.start）。
        self.assertIs(
            add_task.call_args.args[0], video_controller.webui_task.run_api_task
        )
        self.assertEqual(add_task.call_args.kwargs["stop_at"], "plan")
        self.assertIs(add_task.call_args.kwargs["params"], body)

        task_id = add_task.call_args.kwargs["task_id"]
        self.assertEqual(response["data"]["task_id"], task_id)

    def test_task_video_request_accepts_plan_fields(self):
        """新字段经 TaskVideoRequest 继承 VideoParams 自动进入任务参数。"""
        body = TaskVideoRequest(
            video_subject="逆袭", plan_target_duration=45, plan_scene_count=4
        )
        dumped = body.model_dump()
        self.assertEqual(dumped["plan_target_duration"], 45)
        self.assertEqual(dumped["plan_scene_count"], 4)

    def test_plan_route_registered(self):
        routes = {
            route.path
            for route in video_controller.router.routes
            if "POST" in getattr(route, "methods", set())
        }
        self.assertIn("/api/v1/script-plans", routes)


if __name__ == "__main__":
    unittest.main()