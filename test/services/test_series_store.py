# -*- coding: utf-8 -*-
"""series_store 契约测试（B6）：原子持久化 + 内容寻址参考图 + 剧集状态机。

全部落在临时目录（patch series_root），不触碰真实 storage/series。
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.models.schema import Series
from app.services import series_store as ss


def make_series(**overrides) -> Series:
    payload = {
        "id": "sr-test01",
        "title": "测试剧",
        "style_bible": {"tone": "冷峻", "palette": "青灰"},
        "characters": [
            {"id": "c1", "name": "林晚", "role": "protagonist",
             "appearance_prompt": "黑色风衣", "seed": 900001,
             "voice_name": "zh-CN-XiaoxiaoNeural"},
            {"id": "c2", "name": "顾沉", "voice_name": "zh-CN-YunxiNeural"},
        ],
        "episodes": [
            {"id": "ep1", "seq": 1, "title": "开局", "hook": "她是谁？"},
            {"id": "ep2", "seq": 2, "title": "反转"},
        ],
    }
    payload.update(overrides)
    return Series.model_validate(payload)


class SeriesStoreTestCase(unittest.TestCase):
    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.root = Path(temp_dir.name)
        patcher = patch.object(ss, "series_root", return_value=self.root)
        patcher.start()
        self.addCleanup(patcher.stop)


class TestPersistence(SeriesStoreTestCase):
    def test_save_load_round_trip(self):
        series = make_series()
        file = ss.save_series(series)
        self.assertTrue(file.is_file())
        loaded = ss.load_series("sr-test01")
        self.assertEqual(loaded, series)
        # 落盘是 by_alias JSON，可被外部工具直接消费。
        payload = json.loads(file.read_text(encoding="utf-8"))
        self.assertEqual(payload["series_version"], 1)

    def test_load_missing_returns_none(self):
        self.assertIsNone(ss.load_series("sr-nope"))

    def test_corrupted_series_fails_closed(self):
        ss.save_series(make_series())
        file = self.root / "sr-test01" / "series.json"
        file.write_text('{"series_version": 99}', encoding="utf-8")
        with self.assertRaises(ss.SeriesStoreError):
            ss.load_series("sr-test01")
        file.write_text("{broken", encoding="utf-8")
        with self.assertRaises(ss.SeriesStoreError):
            ss.load_series("sr-test01")

    def test_path_traversal_ids_rejected(self):
        for bad in ("../escape", "a/b", "", "x" * 65, ".hidden"):
            with self.assertRaises(ss.SeriesStoreError):
                ss.series_dir(bad)

    def test_list_series_skips_corrupted(self):
        ss.save_series(make_series())
        ss.save_series(make_series(id="sr-test02", title="第二部"))
        bad = self.root / "sr-bad"
        bad.mkdir()
        (bad / "series.json").write_text("{broken", encoding="utf-8")
        summaries = ss.list_series()
        self.assertEqual([s["id"] for s in summaries], ["sr-test01", "sr-test02"])
        self.assertEqual(summaries[0]["episodes"], 2)
        self.assertEqual(summaries[0]["characters"], 2)

    def test_update_series_revalidates(self):
        ss.save_series(make_series())
        with self.assertRaises(Exception):
            ss.update_series(
                "sr-test01",
                lambda s: s.characters.append(s.characters[0]),
            )
        # 失败后档案仍是合法旧值。
        self.assertEqual(len(ss.load_series("sr-test01").characters), 2)


class TestReferenceImages(SeriesStoreTestCase):
    def test_content_addressed_and_registered(self):
        ss.save_series(make_series())
        rel = ss.add_reference_image("sr-test01", "c1", b"image-bytes-a")
        self.assertRegex(rel, r"^characters/c1/[0-9a-f]{64}\.png$")
        self.assertTrue((self.root / "sr-test01" / rel).is_file())
        series = ss.load_series("sr-test01")
        self.assertIn(rel, series.characters[0].reference_images)
        # 同字节幂等：不重复登记。
        again = ss.add_reference_image("sr-test01", "c1", b"image-bytes-a")
        self.assertEqual(again, rel)
        self.assertEqual(
            len(ss.load_series("sr-test01").characters[0].reference_images), 1
        )

    def test_reroll_keeps_old_images(self):
        ss.save_series(make_series())
        old = ss.add_reference_image("sr-test01", "c1", b"old-look")
        new = ss.add_reference_image("sr-test01", "c1", b"new-look")
        self.assertNotEqual(old, new)
        refs = ss.load_series("sr-test01").characters[0].reference_images
        self.assertEqual(refs, [old, new])
        self.assertTrue((self.root / "sr-test01" / old).is_file())

    def test_unknown_character_rejected(self):
        ss.save_series(make_series())
        with self.assertRaises(ss.SeriesStoreError):
            ss.add_reference_image("sr-test01", "cX", b"bytes")

    def test_locked_image_cannot_be_removed(self):
        ss.save_series(make_series())
        rel = ss.add_reference_image("sr-test01", "c1", b"locked-look")
        name = Path(rel).name
        self.assertFalse(ss.is_reference_locked("sr-test01", "c1", name))
        ss.lock_reference_image("sr-test01", "c1", name)
        self.assertTrue(ss.is_reference_locked("sr-test01", "c1", name))
        with self.assertRaises(ss.SeriesStoreError):
            ss.remove_reference_image("sr-test01", "c1", name)
        self.assertTrue((self.root / "sr-test01" / rel).is_file())

    def test_unlocked_image_removed_from_disk_and_bible(self):
        ss.save_series(make_series())
        rel = ss.add_reference_image("sr-test01", "c1", b"temp-look")
        ss.remove_reference_image("sr-test01", "c1", Path(rel).name)
        self.assertFalse((self.root / "sr-test01" / rel).exists())
        self.assertEqual(
            ss.load_series("sr-test01").characters[0].reference_images, []
        )


class TestEpisodeStateMachine(SeriesStoreTestCase):
    def test_forward_transitions(self):
        ss.save_series(make_series())
        ss.bind_episode_plan("sr-test01", "ep1", "plan-001")
        series = ss.set_episode_status("sr-test01", "ep1", "confirmed")
        self.assertEqual(series.episodes[0].status, "confirmed")
        self.assertEqual(series.episodes[0].plan_id, "plan-001")
        series = ss.set_episode_status("sr-test01", "ep1", "rendered")
        self.assertEqual(series.episodes[0].status, "rendered")
        # 其它集不受影响。
        self.assertEqual(series.episodes[1].status, "draft")

    def test_backward_and_skip_transitions_rejected(self):
        ss.save_series(make_series())
        with self.assertRaises(ss.SeriesStoreError):
            ss.set_episode_status("sr-test01", "ep1", "rendered")
        ss.set_episode_status("sr-test01", "ep1", "confirmed")
        with self.assertRaises(ss.SeriesStoreError):
            ss.set_episode_status("sr-test01", "ep1", "draft")
        with self.assertRaises(ss.SeriesStoreError):
            ss.set_episode_status("sr-test01", "epX", "confirmed")


if __name__ == "__main__":
    unittest.main()