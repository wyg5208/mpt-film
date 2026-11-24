"""只读目录 + 缓存 + 预设 API 回归（迁移方案 1.8）。"""

import json
import os
import shutil
import tempfile
import unittest
from dataclasses import dataclass
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import asgi
from app.config import config
from app.controllers.v1 import catalogs as catalogs_controller


class TestCatalogEndpoints(unittest.TestCase):
    def setUp(self):
        self.original_app_config = dict(config.app)
        config.app["api_key"] = ""
        self.root = tempfile.mkdtemp(prefix="catalogs-api-")
        self.client = TestClient(asgi.app)

    def tearDown(self):
        config.app.clear()
        config.app.update(self.original_app_config)
        shutil.rmtree(self.root, True)

    def test_voices_language_filter(self):
        fake = ["zh-CN-XiaoxiaoNeural-Female", "en-US-AriaNeural-Female"]
        with patch(
            "app.services.voice.get_all_azure_voices", return_value=fake
        ) as mockvoices:
            all_voices = self.client.get("/api/v1/voices")
            zh = self.client.get("/api/v1/voices", params={"language": "zh"})
        self.assertEqual(all_voices.status_code, 200)
        self.assertEqual(all_voices.json()["data"]["voices"], fake)
        mockvoices.assert_any_call(filter_locals=None)
        mockvoices.assert_any_call(filter_locals=["zh"])
        self.assertIn("zh", zh.json()["data"]["voices"][0] or "zh")

    def test_llm_providers_metadata_has_no_secrets(self):
        response = self.client.get("/api/v1/llm-providers")
        self.assertEqual(response.status_code, 200)
        providers = response.json()["data"]["providers"]
        self.assertTrue(providers)
        first = providers[0]
        for field in ("provider_id", "requires_api_key", "default_model"):
            self.assertIn(field, first)
        # 目录只回元数据，绝不回任何已配置的密钥值。
        config.app["openai_api_key"] = "sk-secret-value"
        self.assertNotIn("sk-secret-value", self.client.get("/api/v1/llm-providers").text)

    def test_video_sources_groups_and_readiness(self):
        response = self.client.get("/api/v1/video-sources")
        self.assertEqual(response.status_code, 200)
        groups = response.json()["data"]["groups"]
        names = {group["group"] for group in groups}
        self.assertIn("stock_video", names)
        self.assertNotIn("local", names)  # 就绪度输出跳过 local 组

    def test_fonts_lists_only_font_files(self):
        with open(os.path.join(self.root, "demo.ttf"), "wb") as handle:
            handle.write(b"font")
        with open(os.path.join(self.root, "note.txt"), "w") as handle:
            handle.write("x")
        with patch("app.utils.utils.font_dir", return_value=self.root):
            response = self.client.get("/api/v1/fonts")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["name"] for item in response.json()["data"]["fonts"]], ["demo.ttf"]
        )

    def test_presets_roundtrip_and_exclusion(self):
        patcher = patch.object(
            catalogs_controller, "_preset_dir", return_value=self.root
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        created = self.client.post(
            "/api/v1/presets",
            json={
                "name": "知识科普",
                "params": {
                    "video_aspect": "9:16",
                    "video_materials": ["/local/path.mp4"],
                },
            },
        )
        self.assertEqual(created.status_code, 200)
        preset_id = created.json()["data"]["id"]
        # 本机路径类字段不入预设（跨机器无效）。
        self.assertNotIn("video_materials", created.json()["data"]["params"])

        listing = self.client.get("/api/v1/presets")
        items = [
            item for item in listing.json()["data"]["presets"] if not item["builtin"]
        ]
        self.assertEqual([item["id"] for item in items], [preset_id])
        self.assertEqual(items[0]["name"], "知识科普")

        deleted = self.client.delete(f"/api/v1/presets/{preset_id}")
        self.assertEqual(deleted.status_code, 200)
        remaining = [
            item
            for item in self.client.get("/api/v1/presets").json()["data"]["presets"]
            if not item["builtin"]
        ]
        self.assertEqual(remaining, [])

    def test_presets_validation_and_traversal(self):
        bad_name = self.client.post("/api/v1/presets", json={"name": "", "params": {}})
        self.assertEqual(bad_name.status_code, 400)
        traversal = self.client.delete("/api/v1/presets/..%5cwindows")
        self.assertEqual(traversal.status_code, 404)

    def test_cache_stats_and_clean(self):
        @dataclass
        class Stats:
            file_count: int = 3
            total_bytes: int = 100

        @dataclass
        class Clean:
            deleted_count: int = 2
            freed_bytes: int = 60

        with patch(
            "app.services.cache_manager.get_video_cache_stats",
            return_value=Stats(),
        ), patch("app.services.cache_manager.clean_video_cache", return_value=Clean()):
            stats = self.client.get("/api/v1/cache/stats")
            cleaned = self.client.delete("/api/v1/cache/video", params={"max_age_days": 7})
        self.assertEqual(stats.json()["data"]["file_count"], 3)
        self.assertEqual(cleaned.json()["data"]["deleted_count"], 2)
        unknown = self.client.delete("/api/v1/cache/other")
        self.assertEqual(unknown.status_code, 404)

    def test_service_platforms_matrix_shape(self):
        response = self.client.get("/api/v1/service-platforms")
        self.assertEqual(response.status_code, 200)
        groups = response.json()["data"]["groups"]
        self.assertTrue(groups)
        # 分组顺序与 Main.py 总览一致：国内 → 本地 → 国际 → 聚合。
        self.assertEqual(
            [g["group"] for g in groups],
            ["domestic", "local", "international", "aggregator"],
        )
        first = groups[0]["platforms"][0]
        for field in ("platform_id", "label_key", "default_label", "capabilities", "ready"):
            self.assertIn(field, first)
        self.assertIsInstance(first["ready"], bool)

    def test_presets_builtin_first_and_undeletable(self):
        response = self.client.get("/api/v1/presets").json()["data"]["presets"]
        self.assertGreaterEqual(len(response), 4)
        builtins = [p for p in response if p["builtin"]]
        self.assertEqual(len(builtins), 4)
        # 内置预设排最前且无落盘时间。
        self.assertEqual([p["id"] for p in response[:4]], [p["id"] for p in builtins])
        self.assertTrue(all(p["saved_at"] is None for p in builtins))
        # 内置预设不可通过 DELETE 接口删除。
        deleted = self.client.delete("/api/v1/presets/builtin-knowledge")
        self.assertEqual(deleted.status_code, 404)

    def test_cache_stats_includes_dir(self):
        response = self.client.get("/api/v1/cache/stats").json()["data"]
        self.assertIn("dir", response)
        self.assertTrue(response["dir"])

    def test_tts_servers_mirror_and_readiness(self):
        response = self.client.get("/api/v1/tts-servers")
        self.assertEqual(response.status_code, 200)
        servers = response.json()["data"]["servers"]
        # 服务清单与 Main.py TTS_SERVER_OPTIONS 同源（11 项，固定顺序）。
        self.assertEqual(len(servers), 11)
        self.assertEqual(servers[0]["id"], "azure-tts-v1")
        self.assertEqual(servers[-1]["id"], "voxcpm")
        for server in servers:
            for field in ("id", "label", "available"):
                self.assertIn(field, server)
            self.assertIsInstance(server["available"], bool)

    def test_llm_providers_registry_metadata_shape(self):
        providers = self.client.get("/api/v1/llm-providers").json()["data"]["providers"]
        moonshot = next(
            (item for item in providers if item["provider_id"] == "moonshot"), None
        )
        self.assertIsNotNone(moonshot)
        self.assertEqual(moonshot["label_key"], "llm_provider_label.moonshot")
        # 双区域服务商带端点选择器；端点条目含 base_url 与申请链接。
        self.assertGreaterEqual(len(moonshot["service_endpoints"]), 2)
        endpoint = moonshot["service_endpoints"][0]
        for field in (
            "endpoint_id",
            "default_label",
            "label_key",
            "base_url",
            "api_key_url",
        ):
            self.assertIn(field, endpoint)
        self.assertTrue(moonshot["endpoint_selector_label_key"])
        # 无多端点的服务商回空清单且无选择器标题。
        openai = next(
            item for item in providers if item["provider_id"] == "openai"
        )
        self.assertEqual(openai["service_endpoints"], [])
        self.assertIsNone(openai["endpoint_selector_label_key"])

    def test_llm_test_endpoint_reports_result_shape(self):
        with patch(
            "app.services.llm.test_connection", return_value=(True, "", 1.234)
        ) as mock_test:
            response = self.client.post("/api/v1/llm/test")
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertTrue(data["ok"])
        self.assertEqual(data["error"], "")
        self.assertEqual(data["elapsed"], 1.23)
        mock_test.assert_called_once()

    def test_comfy_probe_reports_engine_status(self):
        # 图片面板本地关键帧引擎探测：在线/离线都回 200，状态在 online 字段。
        with patch("app.services.comfy_local.is_online", return_value=True), patch(
            "app.services.comfy_local._base_url", return_value="http://127.0.0.1:8188"
        ):
            online = self.client.get("/api/v1/comfy/probe").json()["data"]
        with patch("app.services.comfy_local.is_online", return_value=False):
            offline = self.client.get("/api/v1/comfy/probe").json()["data"]
        self.assertTrue(online["online"])
        self.assertEqual(online["base_url"], "http://127.0.0.1:8188")
        self.assertFalse(offline["online"])


if __name__ == "__main__":
    unittest.main()
