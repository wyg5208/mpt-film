"""ScriptPlan / Series 模型校验（脚本方案专业模式，B2）。

覆盖 fail-closed 未知字段拒绝、场景顺序/唯一性、共享边界帧约束、
±10% 时长容差警告与 in/out 别名序列化往返。
"""

import sys
import unittest
from pathlib import Path

from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.models.schema import (
    PLAN_NARRATION_CHARS_PER_SECOND,
    SceneMaterial,
    ScriptPlan,
    ScriptScene,
    Series,
    SeriesCharacter,
    SeriesEpisode,
    VideoParams,
    estimate_scene_duration,
)


def make_scene(scene_id="s1", order=1, **overrides):
    payload = {
        "id": scene_id,
        "order": order,
        "narration": "开场旁白",
        "est_duration": 5.0,
    }
    payload.update(overrides)
    return payload


def make_plan(scenes=None, **overrides):
    payload = {
        "title": "测试影片",
        "target_duration": 60,
        "scenes": scenes if scenes is not None else [make_scene()],
    }
    payload.update(overrides)
    return payload


class TestScriptPlanDefaults(unittest.TestCase):
    def test_minimal_plan_fills_contract_defaults(self):
        """最小方案应补齐 v1 契约默认值：draft/stock/unknown/narrator。"""
        plan = ScriptPlan.model_validate(make_plan())

        self.assertEqual(plan.plan_version, 1)
        self.assertEqual(plan.revision, 1)
        self.assertEqual(plan.status, "draft")
        self.assertIsNone(plan.series_id)
        self.assertIsNone(plan.episode_id)
        self.assertEqual(plan.aspect, "9:16")
        self.assertEqual(plan.quality_tier, "draft")
        self.assertEqual(plan.voice.name, "zh-CN-XiaoxiaoNeural")
        self.assertEqual(plan.bgm.type, "random")
        scene = plan.scenes[0]
        self.assertEqual(scene.speaker, "narrator")
        self.assertEqual(scene.engine, "stock")
        self.assertEqual(scene.boundary_health, "unknown")
        self.assertFalse(scene.locked)
        self.assertIsNone(scene.material)
        self.assertIsNone(scene.subtitle_cues)

    def test_seed_range_is_bounded(self):
        """seed 允许 0..0xFFFFFFFF；越界必须拒绝而不是静默截断。"""
        for seed in (0, 0xFFFFFFFF):
            with self.subTest(seed=seed):
                plan = ScriptPlan.model_validate(make_plan(seed=seed))
                self.assertEqual(plan.seed, seed)
        for seed in (-1, 0x100000000):
            with self.subTest(seed=seed), self.assertRaises(ValidationError):
                ScriptPlan.model_validate(make_plan(seed=seed))

    def test_target_duration_must_be_positive(self):
        with self.assertRaises(ValidationError):
            ScriptPlan.model_validate(make_plan(target_duration=0))

    def test_aspect_rejects_unknown_ratio(self):
        with self.assertRaises(ValidationError):
            ScriptPlan.model_validate(make_plan(aspect="1:1"))

    def test_empty_scenes_rejected(self):
        with self.assertRaises(ValidationError):
            ScriptPlan.model_validate(make_plan(scenes=[]))


class TestScriptPlanFailClosed(unittest.TestCase):
    def test_unknown_field_rejected_at_every_level(self):
        """导入路径 fail-closed：plan/scene/material 未知字段一律拒绝。"""
        with self.assertRaises(ValidationError):
            ScriptPlan.model_validate(make_plan(mystery=1))
        with self.assertRaises(ValidationError):
            ScriptPlan.model_validate(
                make_plan(scenes=[make_scene(mystery=1)])
            )
        with self.assertRaises(ValidationError):
            ScriptPlan.model_validate(
                make_plan(scenes=[make_scene(material={"mystery": 1})])
            )

    def test_duplicate_scene_ids_rejected(self):
        with self.assertRaises(ValidationError):
            ScriptPlan.model_validate(
                make_plan(scenes=[make_scene("s1", 1), make_scene("s1", 2)])
            )

    def test_non_contiguous_order_rejected(self):
        """order 必须从 1 连续且与列表顺序一致。"""
        for scenes in (
            [make_scene("s1", 2)],
            [make_scene("s1", 1), make_scene("s2", 3)],
            [make_scene("s2", 2), make_scene("s1", 1)],
        ):
            with self.subTest(scenes=scenes), self.assertRaises(ValidationError):
                ScriptPlan.model_validate(make_plan(scenes=scenes))

    def test_invalid_enum_values_rejected(self):
        for overrides in (
            {"engine": "magic"},
            {"relation_to_prev": "teleport"},
            {"transition_to_next": "wipe"},
            {"boundary_health": "broken"},
        ):
            with self.subTest(overrides=overrides), self.assertRaises(ValidationError):
                ScriptPlan.model_validate(make_plan(scenes=[make_scene(**overrides)]))


class TestSharedBoundaryFrame(unittest.TestCase):
    def test_first_scene_cannot_share_boundary(self):
        with self.assertRaises(ValidationError):
            ScriptPlan.model_validate(
                make_plan(
                    scenes=[
                        make_scene("s1", 1, keyframe={"shared_with_prev": True}),
                    ]
                )
            )

    def test_shared_frame_must_reference_previous_last(self):
        """shared_with_prev=true 时首帧必须与上段尾帧同一文件。"""
        scenes = [
            make_scene("s1", 1, keyframe={"last": "frames/s1-last.png"}),
            make_scene(
                "s2",
                2,
                keyframe={"first": "frames/other.png", "shared_with_prev": True},
            ),
        ]
        with self.assertRaises(ValidationError):
            ScriptPlan.model_validate(make_plan(scenes=scenes))

    def test_shared_frame_missing_first_rejected(self):
        scenes = [
            make_scene("s1", 1, keyframe={"last": "frames/s1-last.png"}),
            make_scene("s2", 2, keyframe={"shared_with_prev": True}),
        ]
        with self.assertRaises(ValidationError):
            ScriptPlan.model_validate(make_plan(scenes=scenes))

    def test_matching_shared_frame_accepted(self):
        scenes = [
            make_scene("s1", 1, keyframe={"last": "frames/s1-last.png"}),
            make_scene(
                "s2",
                2,
                keyframe={
                    "first": "frames/s1-last.png",
                    "shared_with_prev": True,
                },
            ),
        ]
        plan = ScriptPlan.model_validate(make_plan(scenes=scenes))
        self.assertEqual(
            plan.scenes[1].keyframe.first, plan.scenes[0].keyframe.last
        )


class TestMaterialAliasRoundTrip(unittest.TestCase):
    def test_in_out_alias_round_trip(self):
        """入出点对外契约是 in/out；by_alias 序列化必须还原别名。"""
        material = SceneMaterial.model_validate(
            {"source": "pexels", "in": 1.5, "out": 6.0, "selected": "c1"}
        )
        self.assertEqual(material.in_point, 1.5)
        self.assertEqual(material.out_point, 6.0)

        dumped = material.model_dump(by_alias=True)
        self.assertEqual(dumped["in"], 1.5)
        self.assertEqual(dumped["out"], 6.0)
        self.assertNotIn("in_point", dumped)
        self.assertNotIn("out_point", dumped)

        # populate_by_name：字段名形式同样可导入（内部代码兼容）。
        by_name = SceneMaterial.model_validate({"in_point": 2.0, "out_point": 7.0})
        self.assertEqual(by_name.in_point, 2.0)

    def test_plan_dump_uses_aliases_for_nested_material(self):
        plan = ScriptPlan.model_validate(
            make_plan(
                scenes=[make_scene(material={"in": 0.5, "out": 4.0})]
            )
        )
        dumped = plan.model_dump(by_alias=True)
        material = dumped["scenes"][0]["material"]
        self.assertEqual(material["in"], 0.5)
        self.assertEqual(material["out"], 4.0)
        # 别名 dump 必须能无损重新导入。
        ScriptPlan.model_validate(dumped)

    def test_negative_in_point_rejected(self):
        with self.assertRaises(ValidationError):
            SceneMaterial.model_validate({"in": -0.1})


class TestDurationEstimation(unittest.TestCase):
    def test_estimate_scene_duration_uses_chinese_rate(self):
        text = "一" * 21
        self.assertEqual(
            estimate_scene_duration(text),
            round(21 / PLAN_NARRATION_CHARS_PER_SECOND, 1),
        )
        self.assertEqual(estimate_scene_duration(""), 0.0)
        self.assertEqual(estimate_scene_duration("   "), 0.0)
        self.assertEqual(estimate_scene_duration("  " + text + "  "), 5.0)

    def test_estimated_total_duration_sums_scenes(self):
        plan = ScriptPlan.model_validate(
            make_plan(
                scenes=[
                    make_scene("s1", 1, est_duration=5.1),
                    make_scene("s2", 2, est_duration=4.9),
                ]
            )
        )
        self.assertEqual(plan.estimated_total_duration(), 10.0)

    def test_duration_within_tolerance_has_no_warning(self):
        """偏差恰好 10% 仍在容差内（<=），不产生警告。"""
        plan = ScriptPlan.model_validate(
            make_plan(
                target_duration=100,
                scenes=[make_scene(est_duration=110.0)],
            )
        )
        self.assertEqual(plan.duration_warnings(), [])

    def test_duration_out_of_tolerance_warns_without_blocking(self):
        plan = ScriptPlan.model_validate(
            make_plan(
                target_duration=100,
                scenes=[make_scene(est_duration=110.1)],
            )
        )
        warnings = plan.duration_warnings()
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0]["code"], "plan_duration_out_of_tolerance")
        self.assertEqual(warnings[0]["estimated_total"], 110.1)
        self.assertEqual(warnings[0]["target_duration"], 100)

    def test_short_plan_also_warns(self):
        plan = ScriptPlan.model_validate(
            make_plan(
                target_duration=60,
                scenes=[make_scene(est_duration=5.0)],
            )
        )
        self.assertEqual(
            [w["code"] for w in plan.duration_warnings()],
            ["plan_duration_out_of_tolerance"],
        )


class TestSubtitleCueUnion(unittest.TestCase):
    def test_cue_count_and_cue_list_both_accepted(self):
        """生成前是预估 cue 数（int），执行后回填真实区间列表。"""
        counted = ScriptScene.model_validate(make_scene(subtitle_cues=3))
        self.assertEqual(counted.subtitle_cues, 3)

        backfilled = ScriptScene.model_validate(
            make_scene(
                subtitle_cues=[{"start": 0.0, "end": 2.5, "text": "开场"}]
            )
        )
        self.assertEqual(backfilled.subtitle_cues[0].end, 2.5)

    def test_negative_cue_start_rejected(self):
        with self.assertRaises(ValidationError):
            ScriptScene.model_validate(
                make_scene(subtitle_cues=[{"start": -1, "end": 2}])
            )


class TestSeriesValidation(unittest.TestCase):
    def test_minimal_series_defaults(self):
        series = Series.model_validate({"id": "series-1", "title": "逆袭"})
        self.assertEqual(series.series_version, 1)
        self.assertEqual(series.genre_template, "custom")
        self.assertEqual(series.characters, [])
        self.assertEqual(series.episodes, [])

    def test_character_defaults_keep_lora_unset(self):
        character = SeriesCharacter.model_validate({"id": "c1", "name": "林晚"})
        self.assertEqual(character.role, "support")
        self.assertIsNone(character.lora)
        self.assertEqual(character.seed, 0)

    def test_duplicate_asset_ids_rejected(self):
        for field, item in (
            ("characters", {"id": "c1"}),
            ("locations", {"id": "l1"}),
            ("episodes", {"id": "e1", "seq": 1}),
        ):
            payload = {"id": "series-1", field: [dict(item), dict(item)]}
            if field == "episodes":
                payload[field][1] = {"id": "e1", "seq": 2}
            with self.subTest(field=field), self.assertRaises(ValidationError):
                Series.model_validate(payload)

    def test_episode_seq_must_be_contiguous(self):
        with self.assertRaises(ValidationError):
            Series.model_validate(
                {
                    "id": "series-1",
                    "episodes": [
                        {"id": "e1", "seq": 1},
                        {"id": "e2", "seq": 3},
                    ],
                }
            )

    def test_valid_series_round_trip(self):
        series = Series.model_validate(
            {
                "id": "series-1",
                "genre_template": "urban_revenge",
                "characters": [{"id": "c1", "role": "protagonist"}],
                "episodes": [
                    {"id": "e1", "seq": 1},
                    {"id": "e2", "seq": 2, "status": "rendered"},
                ],
            }
        )
        dumped = series.model_dump(by_alias=True)
        Series.model_validate(dumped)
        self.assertEqual(dumped["episodes"][1]["status"], "rendered")

    def test_unknown_genre_template_rejected(self):
        with self.assertRaises(ValidationError):
            Series.model_validate({"id": "series-1", "genre_template": "western"})

    def test_series_episode_status_enum(self):
        with self.assertRaises(ValidationError):
            SeriesEpisode.model_validate({"id": "e1", "seq": 1, "status": "published"})


class TestVideoParamsPlanFields(unittest.TestCase):
    def test_plan_fields_default_to_none(self):
        params = VideoParams(video_subject="咖啡")
        self.assertIsNone(params.plan_target_duration)
        self.assertIsNone(params.plan_scene_count)

    def test_plan_target_duration_bounds(self):
        for value in (0, -1, 601):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                VideoParams(video_subject="咖啡", plan_target_duration=value)
        params = VideoParams(video_subject="咖啡", plan_target_duration=45)
        self.assertEqual(params.plan_target_duration, 45)

    def test_plan_scene_count_bounds(self):
        for value in (1, 21):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                VideoParams(video_subject="咖啡", plan_scene_count=value)
        params = VideoParams(video_subject="咖啡", plan_scene_count=4)
        self.assertEqual(params.plan_scene_count, 4)


if __name__ == "__main__":
    unittest.main()