import unittest
from uuid import uuid4

from fastapi.testclient import TestClient

from app import asgi
from app.config import config
from app.models import const
from app.services import state as sm
from app.services import webui_task


class TestSSELogsStream(unittest.TestCase):
    """SSE 任务日志流（迁移方案 Phase 0.4 / 4.D）。"""

    def setUp(self):
        self.original_app_config = dict(config.app)
        config.app["api_key"] = ""
        self.client = TestClient(asgi.app)

    def tearDown(self):
        config.app.clear()
        config.app.update(self.original_app_config)

    def _seed_completed_task(self, lines):
        task_id = str(uuid4())
        for line in lines:
            webui_task._append_task_log(task_id, line)
        sm.state.update_task(
            task_id, state=const.TASK_STATE_COMPLETE, progress=100
        )
        return task_id

    def test_streams_logs_state_and_end(self):
        task_id = self._seed_completed_task(["first line", "second line"])

        response = self.client.get(f"/api/v1/tasks/{task_id}/events")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            response.headers["content-type"].startswith("text/event-stream")
        )
        self.assertEqual(response.headers.get("x-accel-buffering"), "no")
        body = response.text
        self.assertIn("event: log", body)
        self.assertIn("second line", body)
        self.assertIn("event: state", body)
        self.assertIn("event: end", body)

    def test_last_event_id_resumes_without_replaying(self):
        task_id = self._seed_completed_task(["line zero", "line one", "line two"])

        response = self.client.get(
            f"/api/v1/tasks/{task_id}/events",
            headers={"Last-Event-ID": "0"},
        )

        body = response.text
        # 从索引 0 之后续传：不应重放 id: 0 的那一行。
        self.assertNotIn("id: 0\nevent: log", body)
        self.assertIn("line one", body)
        self.assertIn("line two", body)

    def test_unknown_task_returns_404(self):
        missing_id = str(uuid4())
        response = self.client.get(f"/api/v1/tasks/{missing_id}/events")
        self.assertEqual(response.status_code, 404)

    def test_stream_requires_credentials_when_enabled(self):
        config.app["api_key"] = "sse-secret"
        task_id = self._seed_completed_task(["protected line"])

        anonymous = self.client.get(f"/api/v1/tasks/{task_id}/events")
        self.assertEqual(anonymous.status_code, 401)

        authorized = self.client.get(
            f"/api/v1/tasks/{task_id}/events",
            headers={"x-api-key": "sse-secret"},
        )
        self.assertEqual(authorized.status_code, 200)
        self.assertIn("protected line", authorized.text)

    def test_logs_rest_fallback_returns_incremental(self):
        task_id = self._seed_completed_task(["a", "b", "c", "d"])

        response = self.client.get(
            f"/api/v1/tasks/{task_id}/logs", params={"after": 1}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        # after=1 应返回序号 2、3 的行（c、d），latest_seq 为最后序号。
        seqs = [item["seq"] for item in data["items"]]
        self.assertEqual(seqs, [2, 3])
        self.assertEqual([item["line"] for item in data["items"]], ["c", "d"])
        self.assertEqual(data["latest_seq"], 3)

    def test_logs_rest_fallback_tail_limit(self):
        task_id = self._seed_completed_task(["a", "b", "c", "d"])

        response = self.client.get(
            f"/api/v1/tasks/{task_id}/logs", params={"after": -1, "tail": 2}
        )
        data = response.json()["data"]
        self.assertEqual([item["line"] for item in data["items"]], ["c", "d"])

    def test_logs_rest_requires_credentials_when_enabled(self):
        config.app["api_key"] = "sse-secret"
        task_id = self._seed_completed_task(["protected"])

        anonymous = self.client.get(f"/api/v1/tasks/{task_id}/logs")
        self.assertEqual(anonymous.status_code, 401)

        authorized = self.client.get(
            f"/api/v1/tasks/{task_id}/logs", headers={"x-api-key": "sse-secret"}
        )
        self.assertEqual(authorized.status_code, 200)


if __name__ == "__main__":
    unittest.main()
