"""方案→执行编译器单元测试（脚本方案专业模式，B4）。

覆盖 plan_to_script / scene_search_terms / build_scene_windows（cues 与
legacy 双结构、比例映射、跨 cue 插值、无 cues 兜底）/ backfill_plan 副本
语义 / compile_timeline（均分余数、入出点、变速、转场映射、失败路径）。
全部纯函数断言：不联网、不落盘、不编码。
"""

import sys
import unittest
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.models.schema import ScriptPlan, SubtitleCue
from app.services import plan_compiler
from app.services.plan_compiler import PlanCompileError


def make_plan(scenes=None, **overrides):
    payload = {
        "title": "编译测试",
        "target_duration": 10,
        "scenes": scenes or [
            {"id": "s1", "order": 1, "narration": "aaaa", "est_duration": 4},
            {"id": "s2", "order": 2, "narration": "bbbbbb", "est_duration": 6},
        ],
    }
    payload.update(overrides)
    return ScriptPlan.model_validate(payload)


def cue(start, end, content):
    return SimpleNamespace(
        start=timedelta(seconds=start), end=timedelta(seconds=end), content=content
    )


class TestPlanToScript(unittest.TestCase):
    def test_joins_non_empty_narrations_in_order(self):
        plan = make_plan([
            {"id": "s1", "order": 1, "narration": "  第一段  "},
            {"id": "s2", "order": 2, "narration": ""},
            {"id": "s3", "order": 3, "narration": "第三段"},
        ])
        self.assertEqual(plan_compiler.plan_to_script(plan), "第一段\n第三段")

    def test_all_empty_narration_yields_empty_script(self):
        plan = make_plan([{"id": "s1", "order": 1, "narration": "  "}])
        self.assertEqual(plan_compiler.plan_to_script(plan), "")


class TestSceneSearchTerms(unittest.TestCase):
    def test_keywords_bound_per_scene(self):
        plan = make_plan([
            {"id": "s1", "order": 1, "keywords": [" city ", "", "night"]},
            {"id": "s2", "order": 2, "keywords": ["forest"]},
        ])
        self.assertEqual(
            plan_compiler.scene_search_terms(plan),
            {"s1": ["city", "night"], "s2": ["forest"]},
        )

    def test_falls_back_to_visual_then_scene_id(self):
        plan = make_plan([
            {"id": "s1", "order": 1, "visual": " 雨后街道 "},
            {"id": "s2", "order": 2},
        ])
        self.assertEqual(
            plan_compiler.scene_search_terms(plan),
            {"s1": ["雨后街道"], "s2": ["s2"]},
        )


class TestBuildSceneWindows(unittest.TestCase):
    def test_cue_aligned_boundaries(self):
        plan = make_plan()
        sub_maker = SimpleNamespace(cues=[
            cue(0, 2, "aaaa"), cue(2, 5, "bbbbbb"),
        ])
        windows = plan_compiler.build_scene_windows(plan, sub_maker, 5.0)
        self.assertEqual([w["scene_id"] for w in windows], ["s1", "s2"])
        self.assertEqual([w["start"] for w in windows], [0.0, 2.0])
        self.assertEqual([w["end"] for w in windows], [2.0, 5.0])
        self.assertEqual([w["duration"] for w in windows], [2.0, 3.0])
        self.assertEqual([c.text for c in windows[0]["cues"]], ["aaaa"])
        self.assertEqual([c.text for c in windows[1]["cues"]], ["bbbbbb"])

    def test_boundary_interpolates_inside_straddling_cue(self):
        # 单条 cue 覆盖两个场景：字符 4/10 处应切在 cue 时间轴 2s。
        plan = make_plan()
        sub_maker = SimpleNamespace(cues=[cue(0, 5, "aaaabbbbbb")])
        windows = plan_compiler.build_scene_windows(plan, sub_maker, 5.0)
        self.assertEqual(windows[0]["end"], 2.0)
        self.assertEqual(windows[1]["start"], 2.0)
        # 跨窗 cue 两侧都保留（SRT 区间与窗口相交即归属）。
        self.assertEqual(len(windows[0]["cues"]), 1)
        self.assertEqual(len(windows[1]["cues"]), 1)

    def test_cue_char_axis_maps_proportionally(self):
        # TTS 规范化后 cue 字符数(20)是旁白字符数(10)的两倍：按比例映射。
        plan = make_plan()
        sub_maker = SimpleNamespace(cues=[
            cue(0, 2, "aaaaaaaa"), cue(2, 5, "bbbbbbbbbbbb"),
        ])
        windows = plan_compiler.build_scene_windows(plan, sub_maker, 5.0)
        self.assertEqual(windows[0]["end"], 2.0)

    def test_legacy_subs_offset_fallback(self):
        plan = make_plan()
        sub_maker = SimpleNamespace(
            cues=[],
            subs=["aaaa", "bbbbbb"],
            offset=[(0, 20000000), (20000000, 50000000)],
        )
        windows = plan_compiler.build_scene_windows(plan, sub_maker, 5.0)
        self.assertEqual([w["duration"] for w in windows], [2.0, 3.0])
        self.assertEqual(windows[1]["cues"][0].start, 2.0)

    def test_no_cues_splits_by_char_proportion(self):
        plan = make_plan()
        windows = plan_compiler.build_scene_windows(plan, None, 10.0)
        self.assertEqual([w["duration"] for w in windows], [4.0, 6.0])
        self.assertEqual(windows[0]["cues"], [])

    def test_all_empty_narration_splits_equally(self):
        plan = make_plan([
            {"id": "s1", "order": 1}, {"id": "s2", "order": 2},
        ])
        sub_maker = SimpleNamespace(cues=[cue(0, 10, "ignored")])
        windows = plan_compiler.build_scene_windows(plan, sub_maker, 10.0)
        self.assertEqual([w["duration"] for w in windows], [5.0, 5.0])

    def test_windows_sum_to_audio_duration_and_stay_monotonic(self):
        plan = make_plan([
            {"id": f"s{i}", "order": i, "narration": "x" * (i + 1)}
            for i in range(1, 6)
        ])
        sub_maker = SimpleNamespace(cues=[cue(0, 7, "y" * 23)])
        windows = plan_compiler.build_scene_windows(plan, sub_maker, 7.0)
        self.assertEqual(windows[-1]["end"], 7.0)
        self.assertAlmostEqual(sum(w["duration"] for w in windows), 7.0, places=2)
        for previous, current in zip(windows, windows[1:]):
            self.assertGreaterEqual(current["start"], previous["start"])
            self.assertGreaterEqual(current["duration"], 0)

    def test_whitespace_and_pause_tags_do_not_shift_boundaries(self):
        # 空白与 [pause] 不配音：字符边界只数可见字符。
        plan = make_plan([
            {"id": "s1", "order": 1, "narration": "a a a a[pause]"},
            {"id": "s2", "order": 2, "narration": "bbbbbb"},
        ])
        sub_maker = SimpleNamespace(cues=[cue(0, 2, "aaaa"), cue(2, 5, "bbbbbb")])
        windows = plan_compiler.build_scene_windows(plan, sub_maker, 5.0)
        self.assertEqual(windows[0]["end"], 2.0)


class TestBackfillPlan(unittest.TestCase):
    def test_backfill_returns_copy_with_measured_fields(self):
        plan = make_plan()
        sub_maker = SimpleNamespace(cues=[cue(0, 2, "aaaa"), cue(2, 5, "bbbbbb")])
        windows = plan_compiler.build_scene_windows(plan, sub_maker, 5.0)
        updated = plan_compiler.backfill_plan(plan, windows)

        self.assertIsNot(updated, plan)
        self.assertIsNone(plan.scenes[0].measured_duration)
        self.assertIsNone(plan.scenes[0].subtitle_cues)
        self.assertEqual(updated.scenes[0].measured_duration, 2.0)
        self.assertEqual(updated.scenes[1].measured_duration, 3.0)
        self.assertIsInstance(updated.scenes[0].subtitle_cues[0], SubtitleCue)
        # by_alias 导出可直接回写 script-plan.json。
        dumped = updated.model_dump(by_alias=True)
        self.assertEqual(dumped["scenes"][0]["measured_duration"], 2.0)

    def test_unknown_window_leaves_scene_untouched(self):
        plan = make_plan()
        updated = plan_compiler.backfill_plan(plan, [])
        self.assertIsNone(updated.scenes[0].measured_duration)


class TestCompileTimeline(unittest.TestCase):
    def _windows(self, durations):
        windows = []
        cursor = 0.0
        for index, duration in enumerate(durations, start=1):
            windows.append({
                "scene_id": f"s{index}", "order": index,
                "start": cursor, "end": cursor + duration,
                "duration": duration, "cues": [],
            })
            cursor += duration
        return windows

    def test_distribution_remainder_and_transitions(self):
        plan = make_plan([
            {"id": "s1", "order": 1, "narration": "a",
             "transition_to_next": "fade"},
            {"id": "s2", "order": 2, "narration": "b"},
        ])
        windows = self._windows([1.0, 1.5])
        bindings = {"s1": ["a.mp4"], "s2": ["b.mp4", "c.mp4"]}
        timeline = plan_compiler.compile_timeline(plan, bindings, windows)

        self.assertEqual([t["path"] for t in timeline], ["a.mp4", "b.mp4", "c.mp4"])
        self.assertEqual([t["duration"] for t in timeline], [1.0, 0.75, 0.75])
        self.assertEqual(timeline[0]["transition"], "FadeIn")
        # 末场景恒硬切，即使方案里写了转场。
        self.assertIsNone(timeline[1]["transition"])
        self.assertIsNone(timeline[2]["transition"])
        self.assertEqual([t["in"] for t in timeline], [0.0, 0.0, 0.0])
        self.assertEqual([t["out"] for t in timeline], [1.0, 0.75, 0.75])

    def test_last_file_eats_rounding_remainder(self):
        plan = make_plan([{"id": "s1", "order": 1, "narration": "a"}])
        windows = self._windows([1.0])
        bindings = {"s1": ["a.mp4", "b.mp4", "c.mp4"]}
        timeline = plan_compiler.compile_timeline(plan, bindings, windows)
        self.assertEqual([t["duration"] for t in timeline], [0.333, 0.333, 0.334])
        self.assertAlmostEqual(sum(t["duration"] for t in timeline), 1.0, places=6)

    def test_material_in_out_constrains_first_file_only(self):
        plan = make_plan([
            {"id": "s1", "order": 1, "narration": "a",
             "material": {"in": 2.0, "out": 2.5}},
        ])
        windows = self._windows([1.0])
        bindings = {"s1": ["a.mp4", "b.mp4"]}
        timeline = plan_compiler.compile_timeline(plan, bindings, windows)
        # 首文件 out 被素材出点钳制；第二文件不受入出点约束。
        self.assertEqual(timeline[0]["in"], 2.0)
        self.assertEqual(timeline[0]["out"], 2.5)
        self.assertEqual(timeline[1]["in"], 0.0)
        self.assertEqual(timeline[1]["out"], 0.5)

    def test_clip_speed_scales_source_window(self):
        plan = make_plan([{"id": "s1", "order": 1, "narration": "a"}])
        windows = self._windows([1.0])
        timeline = plan_compiler.compile_timeline(
            plan, {"s1": ["a.mp4"]}, windows, clip_speed=2.0
        )
        self.assertEqual(timeline[0]["duration"], 1.0)
        self.assertEqual(timeline[0]["out"], 2.0)

    def test_transition_map(self):
        scenes = [
            {"id": f"s{i}", "order": i, "narration": "a", "transition_to_next": t}
            for i, t in enumerate(["fade", "slide", "zoom", "match_cut", "none"], 1)
        ]
        plan = make_plan(scenes)
        windows = self._windows([1.0] * 5)
        bindings = {f"s{i}": [f"{i}.mp4"] for i in range(1, 6)}
        timeline = plan_compiler.compile_timeline(plan, bindings, windows)
        self.assertEqual(
            [t["transition"] for t in timeline],
            ["FadeIn", "SlideIn", "ZoomIn", None, None],
        )

    def test_missing_material_or_window_raises(self):
        plan = make_plan()
        windows = self._windows([1.0, 1.0])
        with self.assertRaisesRegex(PlanCompileError, "no bound material"):
            plan_compiler.compile_timeline(plan, {"s1": ["a.mp4"]}, windows)
        with self.assertRaisesRegex(PlanCompileError, "no time window"):
            plan_compiler.compile_timeline(
                plan, {"s1": ["a.mp4"], "s2": ["b.mp4"]}, windows[:1]
            )

    def test_blank_binding_entries_are_filtered(self):
        plan = make_plan([{"id": "s1", "order": 1, "narration": "a"}])
        windows = self._windows([1.0])
        timeline = plan_compiler.compile_timeline(
            plan, {"s1": ["", "a.mp4", None]}, windows
        )
        self.assertEqual([t["path"] for t in timeline], ["a.mp4"])

    def test_same_inputs_compile_identical_timeline(self):
        plan = make_plan()
        windows = self._windows([2.0, 3.0])
        bindings = {"s1": ["a.mp4"], "s2": ["b.mp4", "c.mp4"]}
        first = plan_compiler.compile_timeline(plan, bindings, windows)
        second = plan_compiler.compile_timeline(plan, bindings, windows)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()