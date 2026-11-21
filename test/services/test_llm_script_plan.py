"""分镜方案生成链路单测（脚本方案专业模式，B2）。

覆盖 prompt 构造、语义 payload 归一化、畸形 JSON 修复重试与 None 降级、
以及 json_mode 只对 Ollama 传 response_format 的零影响约定。
"""

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from openai.types.chat import ChatCompletion

from app.services import llm


def semantic_payload(scene_count=2, **overrides):
    payload = {
        "title": "逆袭",
        "logline": "一句话故事",
        "style": {"tone": "冷峻", "palette": "青灰", "camera": "手持"},
        "scenes": [
            {
                "narration": f"第{i + 1}段旁白内容",
                "visual": f"scene {i + 1} visual",
                "keywords": ["city night", "rain"],
                "relation_to_prev": "establish" if i == 0 else "continue",
                "relation_note": "承接上一段",
                "transition_to_next": "fade",
            }
            for i in range(scene_count)
        ],
    }
    payload.update(overrides)
    return payload


def normalize(payload, **overrides):
    kwargs = {
        "target_duration": 60.0,
        "aspect": "9:16",
        "voice_name": "",
        "llm_provider": "ollama",
        "llm_model": "gemma-test",
    }
    kwargs.update(overrides)
    return llm._normalize_llm_plan(payload, **kwargs)


class TestBuildScriptPlanPrompt(unittest.TestCase):
    def test_default_scene_count_follows_duration(self):
        prompt = llm.build_script_plan_prompt("咖啡", target_duration=60)
        self.assertIn("exactly 6 scenes", prompt)
        self.assertIn("咖啡", prompt)

    def test_scene_count_clamped_to_contract_range(self):
        cases = (
            ({"target_duration": 5}, "exactly 3 scenes"),
            ({"target_duration": 600}, "exactly 12 scenes"),
            ({"scene_count": 50}, "exactly 20 scenes"),
            ({"scene_count": 1}, "exactly 2 scenes"),
        )
        for kwargs, expected in cases:
            with self.subTest(kwargs=kwargs):
                prompt = llm.build_script_plan_prompt("咖啡", **kwargs)
                self.assertIn(expected, prompt)

    def test_existing_script_block_keeps_verbatim_instruction(self):
        prompt = llm.build_script_plan_prompt(
            "咖啡", video_script="第一句。\n第二句。"
        )
        self.assertIn("keep every sentence verbatim", prompt)
        self.assertIn("第一句。\n第二句。", prompt)

    def test_series_context_injects_bible_characters_and_hook(self):
        prompt = llm.build_script_plan_prompt(
            "逆袭",
            series_context={
                "style_bible": {"tone": "冷峻", "era": "现代"},
                "characters": [
                    {"id": "c1", "name": "林晚", "appearance_prompt": "black coat"}
                ],
                "previous_hook": "她推开了那扇门",
            },
        )
        self.assertIn("Series Style Bible", prompt)
        self.assertIn("冷峻", prompt)
        self.assertIn("林晚: black coat", prompt)
        self.assertIn("她推开了那扇门", prompt)

    def test_language_and_user_requirements_appended(self):
        prompt = llm.build_script_plan_prompt(
            "咖啡", language="zh-CN", video_script_prompt="节奏更快"
        )
        self.assertIn("- language: zh-CN", prompt)
        self.assertIn("节奏更快", prompt)


class TestNormalizeLlmPlan(unittest.TestCase):
    def test_semantic_payload_becomes_full_plan(self):
        plan = normalize(semantic_payload())

        self.assertEqual(plan.plan_version, 1)
        self.assertEqual(plan.title, "逆袭")
        self.assertEqual(plan.style.tone, "冷峻")
        self.assertEqual(plan.llm.provider, "ollama")
        self.assertEqual(plan.llm.model, "gemma-test")
        self.assertEqual(plan.voice.name, "zh-CN-XiaoxiaoNeural")
        self.assertEqual([s.id for s in plan.scenes], ["s1", "s2"])
        self.assertEqual([s.order for s in plan.scenes], [1, 2])
        for scene in plan.scenes:
            self.assertEqual(scene.engine, "stock")
            self.assertEqual(scene.boundary_health, "unknown")
            self.assertGreater(scene.est_duration, 0)

    def test_unknown_keys_are_tolerated_on_llm_path(self):
        """本地模型偶发多余字段：LLM 路径宽容，导入路径才 fail-closed。"""
        payload = semantic_payload(extra_top="ignored")
        payload["scenes"][0]["extra_scene_key"] = "ignored"
        plan = normalize(payload)
        self.assertEqual(len(plan.scenes), 2)

    def test_invalid_relation_and_transition_fall_back(self):
        payload = semantic_payload()
        payload["scenes"][0]["relation_to_prev"] = "teleport"
        payload["scenes"][0]["transition_to_next"] = "wipe"
        plan = normalize(payload)
        self.assertEqual(plan.scenes[0].relation_to_prev, "unknown")
        self.assertEqual(plan.scenes[0].transition_to_next, "none")

    def test_keywords_filtered_to_non_empty_strings(self):
        payload = semantic_payload()
        payload["scenes"][0]["keywords"] = ["city night", 42, "  ", None, "rain"]
        plan = normalize(payload)
        self.assertEqual(plan.scenes[0].keywords, ["city night", "rain"])

    def test_empty_narration_rejected(self):
        payload = semantic_payload()
        payload["scenes"][1]["narration"] = "   "
        with self.assertRaises(ValueError):
            normalize(payload)

    def test_missing_or_empty_scenes_rejected(self):
        for payload in (
            semantic_payload(scenes=[]),
            {"title": "x"},
            semantic_payload(scenes="not a list"),
        ):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                normalize(payload)

    def test_non_object_payload_and_scene_rejected(self):
        with self.assertRaises(ValueError):
            normalize(["not", "an", "object"])
        payload = semantic_payload()
        payload["scenes"][0] = "not an object"
        with self.assertRaises(ValueError):
            normalize(payload)

    def test_invalid_aspect_falls_back_to_portrait(self):
        plan = normalize(semantic_payload(), aspect="1:1")
        self.assertEqual(plan.aspect, "9:16")

    def test_voice_name_forwarded(self):
        plan = normalize(semantic_payload(), voice_name="zh-CN-YunxiNeural")
        self.assertEqual(plan.voice.name, "zh-CN-YunxiNeural")


class TestGenerateScriptPlan(unittest.TestCase):
    def test_valid_json_returns_alias_dumped_plan(self):
        response = json.dumps(semantic_payload(), ensure_ascii=False)
        with patch.object(llm, "_generate_response", return_value=response) as gen:
            plan = llm.generate_script_plan("逆袭", target_duration=30)

        self.assertIsNotNone(plan)
        self.assertEqual(plan["plan_version"], 1)
        self.assertEqual(plan["target_duration"], 30)
        self.assertEqual([s["id"] for s in plan["scenes"]], ["s1", "s2"])
        self.assertTrue(gen.call_args.kwargs["json_mode"])

    def test_code_fenced_json_accepted(self):
        response = "```json\n" + json.dumps(semantic_payload()) + "\n```"
        with patch.object(llm, "_generate_response", return_value=response):
            plan = llm.generate_script_plan("逆袭")
        self.assertIsNotNone(plan)

    def test_prose_embedded_json_recovered(self):
        response = "好的，以下是方案：\n" + json.dumps(semantic_payload()) + "\n希望满意"
        with patch.object(llm, "_generate_response", return_value=response):
            plan = llm.generate_script_plan("逆袭")
        self.assertIsNotNone(plan)

    def test_repair_retry_feeds_validation_error_back(self):
        """第一次畸形输出后，重试 prompt 必须携带校验错误反馈。"""
        valid = json.dumps(semantic_payload())
        with patch.object(
            llm, "_generate_response", side_effect=["not json at all", valid]
        ) as gen:
            plan = llm.generate_script_plan("逆袭")

        self.assertIsNotNone(plan)
        self.assertEqual(gen.call_count, 2)
        retry_prompt = gen.call_args_list[1].kwargs["prompt"]
        self.assertIn("Previous attempt failed validation", retry_prompt)

    def test_persistent_malformed_json_falls_back_to_none(self):
        with patch.object(
            llm, "_generate_response", return_value="{broken"
        ) as gen:
            plan = llm.generate_script_plan("逆袭")

        self.assertIsNone(plan)
        self.assertEqual(gen.call_count, llm._max_retries)

    def test_provider_error_sentinel_falls_back_to_none(self):
        with patch.object(
            llm, "_generate_response", return_value="Error: connection refused"
        ) as gen:
            plan = llm.generate_script_plan("逆袭")
        self.assertIsNone(plan)
        self.assertEqual(gen.call_count, llm._max_retries)

    def test_empty_response_falls_back_to_none(self):
        with patch.object(llm, "_generate_response", return_value=""):
            self.assertIsNone(llm.generate_script_plan("逆袭"))

    def test_validation_failure_also_triggers_fallback(self):
        """JSON 合法但语义校验失败（空旁白）同样修复重试后降级。"""
        payload = semantic_payload()
        payload["scenes"][0]["narration"] = ""
        with patch.object(
            llm, "_generate_response", return_value=json.dumps(payload)
        ) as gen:
            plan = llm.generate_script_plan("逆袭")
        self.assertIsNone(plan)
        self.assertEqual(gen.call_count, llm._max_retries)

    def test_llm_record_follows_runtime_config(self):
        app_config = {
            "llm_provider": "ollama",
            "ollama_model_name": "gemma-test",
        }
        with patch.object(
            llm,
            "_generate_response",
            return_value=json.dumps(semantic_payload()),
        ):
            plan = llm.generate_script_plan("逆袭", app_config=app_config)
        self.assertEqual(plan["llm"], {"provider": "ollama", "model": "gemma-test"})

    def test_series_reference_forwarded(self):
        with patch.object(
            llm,
            "_generate_response",
            return_value=json.dumps(semantic_payload()),
        ):
            plan = llm.generate_script_plan(
                "逆袭", series_id="series-1", episode_id="e2"
            )
        self.assertEqual(plan["series_id"], "series-1")
        self.assertEqual(plan["episode_id"], "e2")


class TestJsonModeTransport(unittest.TestCase):
    """json_mode 只允许影响 Ollama；其它 provider 请求参数零变化。"""

    OLLAMA_CONFIG = {
        "llm_provider": "ollama",
        "ollama_model_name": "gemma-test",
        "ollama_base_url": "http://127.0.0.1:11434/v1",
    }
    MOONSHOT_CONFIG = {
        "llm_provider": "moonshot",
        "moonshot_api_key": "sk-test",
        "moonshot_model_name": "kimi-test",
        "moonshot_base_url": "https://api.moonshot.cn/v1",
    }

    def _run(self, app_config, json_mode):
        create = MagicMock(return_value=MagicMock(spec=ChatCompletion))
        client = MagicMock()
        client.chat.completions.create = create
        with (
            patch.object(llm, "OpenAI", return_value=client),
            patch.object(
                llm,
                "trace_sdk_call",
                side_effect=lambda provider, base_url, fn, **kw: fn(**kw),
            ),
            patch.object(
                llm, "_extract_chat_completion_text", return_value="OK"
            ),
        ):
            result = llm._generate_response(
                "prompt", app_config=app_config, json_mode=json_mode
            )
        self.assertEqual(result, "OK")
        return create.call_args.kwargs

    def test_ollama_json_mode_passes_response_format(self):
        kwargs = self._run(self.OLLAMA_CONFIG, json_mode=True)
        self.assertEqual(kwargs["response_format"], {"type": "json_object"})

    def test_ollama_without_json_mode_unchanged(self):
        kwargs = self._run(self.OLLAMA_CONFIG, json_mode=False)
        self.assertNotIn("response_format", kwargs)

    def test_non_ollama_provider_never_gets_response_format(self):
        kwargs = self._run(self.MOONSHOT_CONFIG, json_mode=True)
        self.assertNotIn("response_format", kwargs)


if __name__ == "__main__":
    unittest.main()