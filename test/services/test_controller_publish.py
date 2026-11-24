"""发布面板 API 回归（迁移方案 1.6）。"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import asgi
from app.config import config
from app.services import publish_history


class TestPublishEndpoints(unittest.TestCase):
    def setUp(self):
        self.original_app_config = dict(config.app)
        config.app["api_key"] = ""
        self.client = TestClient(asgi.app)

    def tearDown(self):
        config.app.clear()
        config.app.update(self.original_app_config)

    def test_history_sorted_newest_first(self):
        with tempfile.TemporaryDirectory(prefix="publish-history-") as directory:
            history_path = Path(directory) / "publish_history.jsonl"
            with patch(
                "app.services.publish_history.history_file",
                return_value=str(history_path),
            ):
                publish_history.record_publish(
                    {"task_id": "task-abc", "platform": "douyin", "finished_at": 2}
                )
                publish_history.record_publish(
                    {"task_id": "task-def", "platform": "bilibili", "finished_at": 5}
                )
                response = self.client.get("/api/v1/publish/history")
        self.assertEqual(response.status_code, 200)
        history = response.json()["data"]["history"]
        self.assertEqual(history[0]["task_id"], "task-def")

    def test_publish_dispatches_manual_scheduler(self):
        with patch(
            "app.services.task.publish_task_now", return_value=None
        ) as mock_publish:
            response = self.client.post(
                "/api/v1/publish", json={"task_id": "task-1", "platforms": ["douyin"]}
            )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["data"]["scheduled"])
        mock_publish.assert_called_once_with("task-1")

    def test_publish_surfaces_scheduler_error_as_400(self):
        with patch(
            "app.services.task.publish_task_now",
            return_value="task is not complete; only finished videos can be published",
        ):
            response = self.client.post("/api/v1/publish", json={"task_id": "task-1"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("not complete", response.json()["message"])

    def test_queue_projects_active_jobs_and_zombies(self):
        fake_tasks = [
            {
                "task_id": "live-1",
                "cross_post_state": "processing",
                "cross_post_stage": "uploading",
                "cross_post_progress": 40,
                "cross_post_platform": "douyin",
                "cross_post_platforms": ["douyin"],
                "cross_post_log": ["uploaded 40%"],
                "video_subject": "demo",
            },
            {"task_id": "done-1", "cross_post_state": "succeeded"},
        ]
        with patch(
            "app.controllers.v1.publish.sm.state"
        ) as mock_state, patch(
            "app.services.publish_zombies.detect_zombies",
            return_value=[{"pid": 4242, "name": "sau.exe"}],
        ):
            mock_state.get_all_tasks.return_value = (fake_tasks, len(fake_tasks))
            response = self.client.get("/api/v1/publish/queue")
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual([job["task_id"] for job in data["jobs"]], ["live-1"])
        self.assertEqual(data["jobs"][0]["stage"], "uploading")
        self.assertEqual(data["zombies"][0]["pid"], 4242)

    def test_session_check_reports_busy_and_report(self):
        # 与 Streamlit「检查登录状态」同源：占用中回 busy，正常回逐平台报告。
        with patch(
            "app.services.social_auto_upload.social_auto_upload_service.check_sessions",
            return_value=None,
        ):
            busy = self.client.post(
                "/api/v1/publish/sessions/check",
                json={"platforms": ["douyin"], "account": "default"},
            )
        self.assertEqual(busy.status_code, 200)
        self.assertTrue(busy.json()["data"]["busy"])

        with patch(
            "app.services.social_auto_upload.social_auto_upload_service.check_sessions",
            return_value={"douyin": {"ok": False, "detail": "not logged in"}},
        ) as mock_check:
            report = self.client.post(
                "/api/v1/publish/sessions/check",
                json={"platforms": ["douyin"], "account": "default"},
            )
        self.assertEqual(report.status_code, 200)
        self.assertFalse(report.json()["data"]["busy"])
        self.assertFalse(report.json()["data"]["report"]["douyin"]["ok"])
        mock_check.assert_called_once_with(["douyin"], "default")

    def test_requires_credentials_when_enabled(self):
        config.app["api_key"] = "publish-secret"
        anonymous = self.client.get("/api/v1/publish/queue")
        self.assertEqual(anonymous.status_code, 401)
        authorized = self.client.get(
            "/api/v1/publish/queue", headers={"x-api-key": "publish-secret"}
        )
        self.assertEqual(authorized.status_code, 200)


if __name__ == "__main__":
    unittest.main()
