"""素材/成片库接口回归：清单归类、安全边界与状态+磁盘合并语义。"""

import json
import os
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest import mock

from app.controllers.v1 import video as video_controller
from app.models.exception import HttpException


def _request() -> SimpleNamespace:
    return SimpleNamespace(headers={"x-task-id": "request-123"})


class TestTaskFilesEndpoint(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._patcher = mock.patch.object(
            video_controller.utils, "task_dir", return_value=self._tmp.name
        )
        self._patcher.start()
        self.addCleanup(self._patcher.stop)

    def _make_task_dir(self, task_id: str, files: dict[str, int]) -> str:
        task_dir = os.path.join(self._tmp.name, task_id)
        os.makedirs(task_dir, exist_ok=True)
        for name, size in files.items():
            path = os.path.join(task_dir, name)
            with open(path, "wb") as handle:
                handle.write(b"x" * size)
        return task_dir

    def test_lists_files_with_categories_sizes_and_order(self):
        self._make_task_dir(
            "task-files-1",
            {
                "final-1.mp4": 1000,
                "audio.mp3": 500,
                "subtitle.srt": 100,
                "script.json": 60,
                "cover.png": 40,
                "notes.xyz": 10,
            },
        )
        # final-1.mp4 保留当前时间作为最新修改时间，验证 mtime 倒序排序。
        old = time.time() - 3600
        for name in ("audio.mp3", "subtitle.srt", "script.json", "cover.png", "notes.xyz"):
            os.utime(os.path.join(self._tmp.name, "task-files-1", name), (old, old))

        data = video_controller.get_task_files(_request(), "task-files-1")["data"]

        self.assertEqual(data["task_id"], "task-files-1")
        by_name = {item["name"]: item for item in data["files"]}
        self.assertEqual(by_name["final-1.mp4"]["category"], "video")
        self.assertEqual(by_name["audio.mp3"]["category"], "audio")
        self.assertEqual(by_name["subtitle.srt"]["category"], "subtitle")
        self.assertEqual(by_name["script.json"]["category"], "data")
        self.assertEqual(by_name["cover.png"]["category"], "image")
        self.assertEqual(by_name["notes.xyz"]["category"], "other")
        self.assertEqual(by_name["audio.mp3"]["size"], 500)
        self.assertEqual(by_name["audio.mp3"]["path"], "task-files-1/audio.mp3")
        self.assertEqual(data["files"][0]["name"], "final-1.mp4")

    def test_rejects_traversal_task_id(self):
        with self.assertRaises(HttpException) as ctx:
            video_controller.get_task_files(_request(), "../bgm")
        self.assertEqual(ctx.exception.status_code, 403)

    def test_unknown_task_returns_404(self):
        with self.assertRaises(HttpException) as ctx:
            video_controller.get_task_files(_request(), "missing-task-dir")
        self.assertEqual(ctx.exception.status_code, 404)


class TestVideosLibraryEndpoint(unittest.TestCase):
    """成片库合并语义：状态内已完成任务 + 落盘历史去重合并。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._patcher = mock.patch.object(
            video_controller.utils, "task_dir", return_value=self._tmp.name
        )
        self._patcher.start()
        self.addCleanup(self._patcher.stop)

    def _patch_state_tasks(self, tasks):
        patcher = mock.patch.object(
            video_controller.sm.state,
            "get_all_tasks",
            return_value=(tasks, len(tasks)),
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def _make_task_dir(self, task_id: str, files=(), subject=None) -> str:
        task_dir = os.path.join(self._tmp.name, task_id)
        os.makedirs(task_dir, exist_ok=True)
        for name in files:
            with open(os.path.join(task_dir, name), "wb") as handle:
                handle.write(b"x")
        if subject is not None:
            with open(os.path.join(task_dir, "script.json"), "w", encoding="utf-8") as handle:
                json.dump({"params": {"video_subject": subject}}, handle, ensure_ascii=False)
        return task_dir

    def test_merges_state_and_disk_entries_without_duplicates(self):
        self._patch_state_tasks(
            [
                {
                    "task_id": "state-task",
                    "state": video_controller.const.TASK_STATE_COMPLETE,
                    "video_subject": "状态主题",
                    "videos": ["state-task/final-1.mp4"],
                }
            ]
        )
        self._make_task_dir("state-task", files=["final-1.mp4"])
        self._make_task_dir("disk-task", files=["final-1.mp4"], subject="落盘主题")
        self._make_task_dir("audio-only", files=["audio.mp3"])

        data = video_controller.get_videos_library(_request(), 100)["data"]

        by_id = {item["task_id"]: item for item in data["items"]}
        # audio-only 目录没有 final-*.mp4，不视为成片；state-task 不重复出现。
        self.assertEqual(len(data["items"]), 2)
        self.assertEqual(
            [item["task_id"] for item in data["items"]],
            ["disk-task", "state-task"],  # mtime 倒序：后创建的目录在前
        )
        state_item = by_id["state-task"]
        self.assertEqual(state_item["subject"], "状态主题")
        self.assertEqual(state_item["source"], "state")
        self.assertTrue(state_item["videos"][0].endswith("state-task/final-1.mp4"))
        disk_item = by_id["disk-task"]
        self.assertEqual(disk_item["subject"], "落盘主题")
        self.assertEqual(disk_item["source"], "disk")
        self.assertEqual(len(disk_item["videos"]), 1)
        self.assertIn("disk-task/final-1.mp4", disk_item["videos"][0])

    def test_incomplete_state_tasks_fall_back_to_disk_scan(self):
        self._patch_state_tasks(
            [
                {
                    "task_id": "processing-task",
                    "state": 0,
                    "video_subject": "未完成",
                    "videos": ["processing-task/final-1.mp4"],
                },
                {
                    "task_id": "no-video-task",
                    "state": video_controller.const.TASK_STATE_COMPLETE,
                    "video_subject": "无成片",
                    "videos": [],
                },
            ]
        )
        self._make_task_dir("processing-task", files=["final-1.mp4"])
        self._make_task_dir("no-video-task", files=["final-1.mp4"])

        data = video_controller.get_videos_library(_request(), 100)["data"]

        by_id = {item["task_id"]: item for item in data["items"]}
        # 状态被排除（未完成/无成片）但目录里有成片的任务回落为磁盘条目。
        self.assertEqual(by_id["processing-task"]["source"], "disk")
        self.assertEqual(by_id["no-video-task"]["source"], "disk")


class TestTaskDirsEndpoint(unittest.TestCase):
    """素材库任务选择器数据源：磁盘一级子目录 + script.json 主题回退。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._patcher = mock.patch.object(
            video_controller.utils, "task_dir", return_value=self._tmp.name
        )
        self._patcher.start()
        self.addCleanup(self._patcher.stop)

    def test_lists_dirs_with_subject_and_mtime_order(self):
        for task_id, subject in (("dir-new", "新任务主题"), ("dir-old", None)):
            task_dir = os.path.join(self._tmp.name, task_id)
            os.makedirs(task_dir, exist_ok=True)
            if subject is not None:
                with open(os.path.join(task_dir, "script.json"), "w", encoding="utf-8") as handle:
                    json.dump({"params": {"video_subject": subject}}, handle, ensure_ascii=False)
        # dir-new 保留当前时间，dir-old 回退一小时，验证 mtime 倒序。
        old = time.time() - 3600
        os.utime(os.path.join(self._tmp.name, "dir-old"), (old, old))
        # 散文件不是任务目录，不应出现。
        with open(os.path.join(self._tmp.name, "loose.txt"), "wb") as handle:
            handle.write(b"x")

        data = video_controller.get_task_dirs(_request(), 100)["data"]

        by_id = {item["task_id"]: item for item in data["items"]}
        self.assertEqual(len(data["items"]), 2)
        self.assertEqual(
            [item["task_id"] for item in data["items"]],
            ["dir-new", "dir-old"],  # mtime 倒序
        )
        self.assertEqual(by_id["dir-new"]["subject"], "新任务主题")
        # 无 script.json 时回退 task_id 前 8 位。
        self.assertEqual(by_id["dir-old"]["subject"], "dir-old")
        self.assertTrue(by_id["dir-new"]["mtime"] > by_id["dir-old"]["mtime"])


if __name__ == "__main__":
    unittest.main()
