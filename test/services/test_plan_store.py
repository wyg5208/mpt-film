# -*- coding: utf-8 -*-
"""plan_store 契约测试（B7）：草稿库原子持久化 + fail-closed 校验。

全部落在临时目录（patch plans_root），不触碰真实 storage/plans。
草稿库与任务目录的 script-plan.json（task_artifacts 执行产物）相互独立。
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.models.schema import ScriptPlan
from app.services import plan_store as ps


def make_plan_payload(**overrides) -> dict:
    payload = {
        "title": "测试影片",
        "target_duration": 60,
        "scenes": [
            {"id": "s1", "order": 1, "narration": "开场旁白", "est_duration": 5.0}
        ],
    }
    payload.update(overrides)
    return payload


class PlanStoreTestCase(unittest.TestCase):
    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.root = Path(temp_dir.name)
        patcher = patch.object(ps, "plans_root", return_value=self.root)
        patcher.start()
        self.addCleanup(patcher.stop)


class TestPersistence(PlanStoreTestCase):
    def test_save_load_round_trip_by_alias(self):
        plan_id = ps.save_plan(make_plan_payload())
        self.assertRegex(plan_id, r"^pl-[0-9a-f]{12}$")
        loaded = ps.load_plan(plan_id)
        expected = ScriptPlan.model_validate(make_plan_payload()).model_dump(
            mode="json", by_alias=True
        )
        self.assertEqual(loaded, expected)
        # 落盘是 by_alias JSON，可被外部工具直接消费。
        file = self.root / f"{plan_id}.json"
        self.assertEqual(json.loads(file.read_text(encoding="utf-8")), expected)

    def test_save_with_explicit_id_and_revision_preserved(self):
        payload = make_plan_payload(revision=3, status="confirmed")
        plan_id = ps.save_plan(payload, plan_id="pl-custom01")
        self.assertEqual(plan_id, "pl-custom01")
        loaded = ps.load_plan(plan_id)
        # 修订号/状态由调用方维护，store 不改写。
        self.assertEqual(loaded["revision"], 3)
        self.assertEqual(loaded["status"], "confirmed")

    def test_invalid_payload_rejected_without_write(self):
        with self.assertRaises(ps.PlanStoreError):
            ps.save_plan(make_plan_payload(mystery=1))
        with self.assertRaises(ps.PlanStoreError):
            ps.save_plan(make_plan_payload(scenes=[]))
        self.assertEqual(list(self.root.glob("*.json")), [])

    def test_load_missing_returns_none(self):
        self.assertIsNone(ps.load_plan("pl-nope"))

    def test_corrupted_draft_fails_closed(self):
        plan_id = ps.save_plan(make_plan_payload())
        file = self.root / f"{plan_id}.json"
        file.write_text("{broken", encoding="utf-8")
        with self.assertRaises(ps.PlanStoreError):
            ps.load_plan(plan_id)
        file.write_text('{"plan_version": 99}', encoding="utf-8")
        with self.assertRaises(ps.PlanStoreError):
            ps.load_plan(plan_id)

    def test_path_traversal_ids_rejected(self):
        for bad in ("../escape", "a/b", "", "x" * 65, ".hidden"):
            with self.subTest(bad=bad):
                with self.assertRaises(ps.PlanStoreError):
                    ps.load_plan(bad)
                with self.assertRaises(ps.PlanStoreError):
                    ps.delete_plan(bad)
        # save 的空串/None 走自动生成；显式非法 ID 仍须拒绝。
        for bad in ("../escape", "a/b", "x" * 65, ".hidden"):
            with self.subTest(bad=bad):
                with self.assertRaises(ps.PlanStoreError):
                    ps.save_plan(make_plan_payload(), plan_id=bad)

    def test_list_plans_skips_corrupted(self):
        first = ps.save_plan(make_plan_payload(title="第一部"))
        second = ps.save_plan(
            make_plan_payload(title="第二部", series_id="sr-x", episode_id="ep1")
        )
        (self.root / "pl-bad.json").write_text("{broken", encoding="utf-8")
        # 非 pl- 前缀文件不进入清单。
        (self.root / "other.json").write_text("{}", encoding="utf-8")
        summaries = ps.list_plans()
        self.assertEqual([s["id"] for s in summaries], sorted([first, second]))
        by_id = {s["id"]: s for s in summaries}
        self.assertEqual(by_id[first]["title"], "第一部")
        self.assertEqual(by_id[first]["scenes"], 1)
        self.assertEqual(by_id[first]["status"], "draft")
        self.assertEqual(by_id[second]["series_id"], "sr-x")
        self.assertEqual(by_id[second]["episode_id"], "ep1")

    def test_delete_plan(self):
        plan_id = ps.save_plan(make_plan_payload())
        self.assertTrue(ps.delete_plan(plan_id))
        self.assertFalse(ps.delete_plan(plan_id))
        self.assertIsNone(ps.load_plan(plan_id))


if __name__ == "__main__":
    unittest.main()