"""API 任务路径的任务日志捕获回归（React 实时日志栏依赖这份缓冲）。

此前 ``video.create_task`` 直接把 ``tm.start`` 提交给 TaskManager，工作线程
内没有安装任何 loguru sink，``task_logs`` 缓冲始终为空，SSE/REST 日志端点
（/tasks/{id}/events、/tasks/{id}/logs）对 API 任务没有任何进度日志可推。
``webui_task.run_api_task`` 复用 Streamlit 路径的线程作用域 sink 安装逻辑，
本模块验证捕获与清理两个契约。
"""

import unittest
from unittest.mock import patch

from loguru import logger

from app.services import task_logs, webui_task


class TestApiTaskLogCapture(unittest.TestCase):
    def test_run_api_task_captures_pipeline_logs(self):
        captured = {}

        def fake_start(task_id, params, stop_at="video"):
            logger.info(f"阶段一：合成语音 task={task_id}")
            logger.info(f"阶段二：收尾 stop_at={stop_at}")
            captured["stop_at"] = stop_at
            return {"task_id": task_id, "state": "success"}

        with patch.object(webui_task.tm, "start", side_effect=fake_start):
            result = webui_task.run_api_task(
                "t-log-capture", params=None, stop_at="audio"
            )

        self.assertEqual(result["task_id"], "t-log-capture")
        self.assertEqual(captured["stop_at"], "audio")
        logs = task_logs.get_task_logs("t-log-capture")
        self.assertTrue(any("阶段一：合成语音" in line for line in logs), logs)
        self.assertTrue(any("stop_at=audio" in line for line in logs), logs)

    def test_run_api_task_removes_sink_after_completion(self):
        # 终态后 sink 必须移除：后续同线程日志不得再写入缓冲（跨任务串流）。
        def fake_start(task_id, params, stop_at="video"):
            logger.info("in-task line")
            return {"task_id": task_id}

        with patch.object(webui_task.tm, "start", side_effect=fake_start):
            webui_task.run_api_task("t-log-clean", params=None)

        logs = task_logs.get_task_logs("t-log-clean")
        self.assertTrue(any("in-task line" in line for line in logs), logs)
        before = len(logs)

        logger.info("out-of-task line")
        after = task_logs.get_task_logs("t-log-clean")
        self.assertEqual(len(after), before)
        self.assertFalse(any("out-of-task" in line for line in after), after)

    def test_redis_func_map_resolves_api_wrapper(self):
        # Redis 模式按函数名序列化任务：FUNC_MAP 必须能解析回包装函数本身。
        from app.controllers.manager.redis_manager import FUNC_MAP

        self.assertIs(FUNC_MAP["run_api_task"], webui_task.run_api_task)


if __name__ == "__main__":
    unittest.main()
