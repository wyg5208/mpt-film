"""
随机决策的可复现性测试。

覆盖三件事：
1. 子种子派生本身的行为（角色隔离、序号隔离、未指定时的兼容语义）。
2. 每个随机点接入种子后确实可复现，且**与线程并发数无关**——这是本方案的核心
   主张，只测"同种子同结果"无法证明它。
3. 生效种子被持久化，用户能把它抄回请求体重放同一条片子。

所有用例都不联网、不调用任何 Provider；涉及编码的段落全部打桩。
"""

import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import numpy as np

# add project root to python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.models.schema import ImageMotion, MaterialInfo, VideoAspect, VideoConcatMode, VideoParams, VideoTransitionMode
from app.services import determinism, material, task, video as vd


def _make_items(count: int, sources: int = 3):
    """构造跨多个源文件的片段条目，用于验证编排打乱。"""
    items = []
    for index in range(count):
        source = f"source-{index % sources}.mp4"
        start = (index // sources) * 2.0
        items.append(
            vd.SubClippedVideoClip(
                file_path=source,
                start_time=start,
                end_time=start + 2.0,
                width=480,
                height=840,
                source_file_path=source,
            )
        )
    return items


class TestDeriveSeed(unittest.TestCase):
    def test_derive_seed_is_stable_and_isolated(self):
        self.assertEqual(
            determinism.derive_seed(7, "clip", 3),
            determinism.derive_seed(7, "clip", 3),
        )
        # 角色隔离：同一个 base_seed 与序号在不同角色下必须产出不同子种子，
        # 否则转场决策会与编排决策相关。
        self.assertNotEqual(
            determinism.derive_seed(7, "clip", 0),
            determinism.derive_seed(7, "bgm", 0),
        )
        # 序号隔离：相邻片段不能拿到相邻种子（Mersenne Twister 上高度相关）。
        self.assertNotEqual(
            determinism.derive_seed(7, "clip", 0),
            determinism.derive_seed(7, "clip", 1),
        )

    def test_unseeded_path_returns_global_module(self):
        # None 必须原样返回进程级 random 模块：未指定种子的调用方要拿到与
        # 历史完全一致的分布，而不是"按对象创建时刻熵源分布"这种新语义。
        self.assertIs(determinism.rng_for(None, "clip", 0), determinism.random)
        self.assertIsNot(determinism.rng_for(1, "clip", 0), determinism.random)

    def test_rng_for_seeded_path_is_independent_per_call(self):
        first = determinism.rng_for(11, "order", 1)
        second = determinism.rng_for(11, "order", 1)
        values = list(range(20))
        self.assertEqual(
            first.sample(values, k=5),
            second.sample(values, k=5),
        )

    def test_resolve_effective_seed(self):
        # 显式种子按 32 位归一化，与 API 校验边界一致。
        self.assertEqual(determinism.resolve_effective_seed(42, "any-task"), 42)
        self.assertEqual(
            determinism.resolve_effective_seed(2**32 + 1, "any-task"), 1
        )
        # 未指定时按 task_id 派生：稳定、落在 32 位内、不同任务不同值。
        derived = determinism.resolve_effective_seed(None, "task-a")
        self.assertEqual(derived, determinism.resolve_effective_seed(None, "task-a"))
        self.assertNotEqual(derived, determinism.resolve_effective_seed(None, "task-b"))
        self.assertGreaterEqual(derived, 0)
        self.assertLessEqual(derived, 0xFFFFFFFF)


class TestOrderingRandomPoints(unittest.TestCase):
    def test_prioritize_unique_source_clips_is_reproducible(self):
        items = _make_items(30)
        original = tuple(id(item) for item in items)
        first = tuple(
            id(item)
            for item in vd._prioritize_unique_source_clips(
                subclipped_items=list(items),
                concat_mode=VideoConcatMode.random,
                seed=1234,
                video_index=1,
            )
        )
        second = tuple(
            id(item)
            for item in vd._prioritize_unique_source_clips(
                subclipped_items=list(items),
                concat_mode=VideoConcatMode.random,
                seed=1234,
                video_index=1,
            )
        )
        # 同一批对象、同一 seed：输出序列必须逐个一致。
        self.assertEqual(first, second)
        # 输入列表本身不应被打乱（函数只返回新序列）。
        self.assertEqual(tuple(id(item) for item in items), original)
        # 顺序确实被打乱了，否则“可复现”是空话。
        self.assertNotEqual(first, original)

    def test_different_seeds_diverge(self):
        orders = set()
        for seed in range(8):
            ordered = vd._prioritize_unique_source_clips(
                subclipped_items=_make_items(30),
                concat_mode=VideoConcatMode.random,
                seed=seed,
                video_index=1,
            )
            orders.add(tuple(item.source_file_path for item in ordered))
        self.assertGreater(len(orders), 1)

    def test_video_index_isolates_batch_variants(self):
        # video_count > 1 时每条片子必须不同，否则批量生成会被播种抹平成一条。
        first = vd._prioritize_unique_source_clips(
            subclipped_items=_make_items(30),
            concat_mode=VideoConcatMode.random,
            seed=99,
            video_index=1,
        )
        second = vd._prioritize_unique_source_clips(
            subclipped_items=_make_items(30),
            concat_mode=VideoConcatMode.random,
            seed=99,
            video_index=2,
        )
        self.assertNotEqual(
            tuple(item.source_file_path for item in first),
            tuple(item.source_file_path for item in second),
        )

    def test_sequential_mode_is_not_reordered(self):
        items = _make_items(6)
        ordered = vd._prioritize_unique_source_clips(
            subclipped_items=items,
            concat_mode=VideoConcatMode.sequential,
            seed=1,
            video_index=1,
        )
        self.assertEqual([id(item) for item in ordered], [id(item) for item in items])


class TestBgmRandomPoint(unittest.TestCase):
    def test_bgm_choice_is_reproducible_regardless_of_listing_order(self):
        files = [f"/songs/{name}.mp3" for name in ("a", "b", "c", "d", "e")]
        with patch.object(vd.bgm_service, "list_bgm_files", return_value=list(reversed(files))):
            first = vd.get_bgm_file(bgm_type="random", seed=77)
        with patch.object(vd.bgm_service, "list_bgm_files", return_value=list(files)):
            second = vd.get_bgm_file(bgm_type="random", seed=77)
        # 目录枚举顺序不同也必须选到同一首：排序前置是播种生效的前提。
        self.assertEqual(first, second)

    def test_bgm_different_seeds_can_diverge(self):
        files = [f"/songs/{index:02d}.mp3" for index in range(30)]
        picks = set()
        with patch.object(vd.bgm_service, "list_bgm_files", return_value=list(files)):
            for seed in range(10):
                picks.add(vd.get_bgm_file(bgm_type="random", seed=seed))
        self.assertGreater(len(picks), 1)

    def test_empty_bgm_directory_returns_no_bgm(self):
        with patch.object(vd.bgm_service, "list_bgm_files", return_value=[]):
            self.assertEqual(vd.get_bgm_file(bgm_type="random", seed=1), "")


class TestMaterialDownloadRandomPoint(unittest.TestCase):
    @staticmethod
    def _candidates(count=10):
        return [
            MaterialInfo(url=f"https://example.com/asset-{index:02d}.mp4", duration=8)
            for index in range(count)
        ]

    def _run_download(self, seed, listing):
        """把搜索与下载打桩，只保留 download_videos 里的排序+打乱逻辑。"""

        def fake_search_videos_with_cache(**kwargs):
            # 每个关键词返回同一批候选：验证去重与稳定排序，而不是网络时序。
            return list(listing)

        def fake_download(materials, material_directory, on_downloaded=None):
            downloaded = []
            for search_term, item in materials:
                saved = f"{tempfile.gettempdir()}/{Path(item.url).name}"
                if on_downloaded is not None:
                    on_downloaded(item)
                downloaded.append((search_term, item, saved))
            return downloaded

        with ExitStack() as stack:
            stack.enter_context(
                patch.object(material, "_search_videos_with_cache", fake_search_videos_with_cache)
            )
            stack.enter_context(
                patch.object(material, "_download_materials_in_parallel", fake_download)
            )
            stack.enter_context(patch.object(material, "_persist_material_sources", lambda *a, **k: None))
            stack.enter_context(patch.object(material.config.app, "get", return_value=""))
            return material.download_videos(
                task_id="seed-test",
                search_terms=["alpha", "beta"],
                source="pexels",
                video_aspect=VideoAspect.portrait,
                video_concat_mode=VideoConcatMode.random,
                audio_duration=12.0,
                max_clip_duration=5,
                image_motion=ImageMotion.zoom,
                seed=seed,
            )

    def test_selection_is_reproducible(self):
        listing = self._candidates()
        shuffled_listing = list(reversed(listing))
        first = self._run_download(2024, listing)
        # 候选以不同到达顺序进入时，排序前置保证仍选出同一批素材。
        second = self._run_download(2024, shuffled_listing)
        self.assertEqual(first, second)

    def test_selection_actually_depends_on_seed(self):
        picks = {tuple(self._run_download(seed, self._candidates())) for seed in range(6)}
        self.assertGreater(len(picks), 1)

    def test_unseeded_call_still_works(self):
        # 未传 seed 的历史调用方（第三方集成、旧任务重跑）必须照常产出。
        self.assertTrue(self._run_download(None, self._candidates()))


class _FakeClip:
    """最小 MoviePy 接口：只实现 combine_videos 片段处理路径真正用到的成员。

    origin / span 是“这个片段到底是谁”的稳定身份，沿着 subclipped /
    with_speed_scaled 一路传递下去。测试必须按这个身份记录转场方向：
    按“调用到达顺序”记录在并发下本身就会错位——那正是本用例要排除的
    干扰，不能反过来把它当成断言依据。
    """

    def __init__(self, duration=2.0, size=(480, 840), origin=None, span=None):
        self.duration = duration
        self.size = size
        self.mask = None
        self.origin = origin
        self.span = span

    @property
    def w(self):
        return self.size[0]

    @property
    def h(self):
        return self.size[1]

    def subclipped(self, start_time, end_time):
        return _FakeClip(
            duration=end_time - start_time,
            size=self.size,
            origin=self.origin,
            span=(round(start_time, 3), round(end_time, 3)),
        )

    def with_speed_scaled(self, speed):
        return _FakeClip(
            duration=self.duration / speed,
            size=self.size,
            origin=self.origin,
            span=self.span,
        )

    def close(self):
        pass

    @property
    def identity(self):
        return (self.origin, self.span)


class TestClipTransitionIndependence(unittest.TestCase):
    """
    核心主张：逐片段转场决策只取决于片段在编排序列里的下标。

    并发数从 1 改到 4 时，线程池的批次交错方式完全不同；若沿用共享的全局
    RNG 序列，后面的片段必然拿到不同的随机值。这里用打桩把编码全部去掉，
    只观察每个片段（按素材身份识别）实际选到的转场方向。
    """

    def _collect_sides(self, seed, concurrency, paths=None, video_index=1):
        recorded = {}
        clip_count = 12
        sources = [f"source-{index}.mp4" for index in range(clip_count)]

        def fake_open(video_path, *args, **kwargs):
            # 首层 clip 的 origin 就是素材路径；subclipped 会补上 span。
            return _FakeClip(duration=2.0, origin=video_path)

        def fake_write(clip, clip_file, **kwargs):
            return clip_file

        with ExitStack() as stack:
            stack.enter_context(patch.object(vd, "_open_video_clip_quietly", fake_open))
            stack.enter_context(patch.object(vd, "close_clip", lambda clip: None))
            stack.enter_context(patch.object(vd, "AudioFileClip", lambda path: _FakeClip(duration=6.0)))
            stack.enter_context(patch.object(vd, "_write_videofile_with_codec_fallback", fake_write))
            stack.enter_context(patch.object(vd, "concat_video_clips_with_ffmpeg", lambda **kwargs: None))
            stack.enter_context(patch.object(vd, "delete_files", lambda files: None))
            stack.enter_context(patch.object(vd, "_get_clip_processing_concurrency", return_value=concurrency))
            stack.enter_context(
                patch.object(
                    vd,
                    "_fit_clip_to_canvas",
                    lambda clip, **kwargs: clip,
                )
            )

            def record_transition(clip, transition_duration, side=None):
                # 按片段身份记录：与线程到达顺序彻底无关。
                recorded[clip.identity] = side
                return clip

            stack.enter_context(
                patch.object(vd.video_effects, "slidein_transition", record_transition)
            )
            vd.combine_videos(
                combined_video_path="combined.mp4",
                video_paths=list(paths if paths is not None else reversed(sources)),
                audio_file="voice.mp3",
                video_aspect=VideoAspect.portrait,
                video_concat_mode=VideoConcatMode.random,
                video_transition_mode=VideoTransitionMode.slide_in,
                max_clip_duration=2,
                threads=1,
                seed=seed,
                video_index=video_index,
            )
        return recorded

    def test_transition_side_is_independent_of_concurrency(self):
        single = self._collect_sides(seed=31337, concurrency=1)
        parallel = self._collect_sides(seed=31337, concurrency=4)
        self.assertTrue(single, "no clip transition was recorded")
        self.assertEqual(single, parallel)

    def test_transition_side_changes_with_seed(self):
        first = self._collect_sides(seed=1, concurrency=1)
        second = self._collect_sides(seed=2, concurrency=1)
        self.assertTrue(first and second)
        self.assertNotEqual(first, second)

    def test_input_path_order_does_not_change_selection(self):
        # combine_videos 入口对 random 模式的素材列表排序：同一批素材以不同
        # 到达顺序传入时，选中的片段及其转场方向必须完全一致。
        sources = [f"source-{index}.mp4" for index in range(12)]
        forward = self._collect_sides(seed=5, concurrency=1, paths=list(sources))
        backward = self._collect_sides(seed=5, concurrency=1, paths=list(reversed(sources)))
        self.assertTrue(forward)
        self.assertEqual(forward, backward)


class TestEffectiveSeedPersistence(unittest.TestCase):
    def test_script_data_records_effective_seed(self):
        task_id = "seed-persistence-test"
        params = VideoParams(video_subject="demo", video_seed=4242)
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(vd.utils, "task_dir", return_value=temp_dir), patch.object(
                task.utils, "task_dir", return_value=temp_dir
            ):
                task.save_script_data(task_id, "script", ["term"], params)
                script_file = Path(temp_dir) / "script.json"
                self.assertTrue(script_file.is_file())
                import json

                payload = json.loads(script_file.read_text(encoding="utf-8"))
        self.assertEqual(payload["video_seed"], 4242)
        # params 快照保留用户意图：未指定就是 null，不能与生效值混为一谈。
        self.assertEqual(payload["params"]["video_seed"], 4242)

    def test_derived_seed_is_recorded_when_not_explicit(self):
        task_id = "seed-derivation-test"
        params = VideoParams(video_subject="demo")
        self.assertIsNone(params.video_seed)
        expected = determinism.resolve_effective_seed(None, task_id)
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(task.utils, "task_dir", return_value=temp_dir):
                task.save_script_data(task_id, "script", ["term"], params)
                import json

                payload = json.loads(
                    (Path(temp_dir) / "script.json").read_text(encoding="utf-8")
                )
        self.assertEqual(payload["video_seed"], expected)
        self.assertIsNone(payload["params"]["video_seed"])

    def test_resolve_video_seed_tolerates_legacy_params(self):
        # 旧任务持久化的 params 可能没有 video_seed 字段，不能抛 AttributeError。
        class LegacyParams:
            pass

        self.assertEqual(
            task._resolve_video_seed("legacy-task", LegacyParams()),
            determinism.resolve_effective_seed(None, "legacy-task"),
        )


if __name__ == "__main__":
    unittest.main()
