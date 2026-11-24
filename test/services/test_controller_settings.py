"""设置编辑 API 回归（迁移方案 1.3 / 4.D 脱敏红线）。

范式对齐 test_api_validation_message.py：TestClient(asgi.app)、
monkeypatch config.app、断言状态码 + {status,message,data} 信封。
所有写入路径都被打桩，测试绝不落盘真实 config.toml。
"""

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import asgi
from app.config import config

SECRET = "sk-supers…1234"


class TestSettingsEndpoints(unittest.TestCase):
    def setUp(self):
        self.original_app_config = dict(config.app)
        self.original_azure = dict(config.azure)
        self.original_ui = dict(config.ui)
        self.updates = []
        # 打桩非阻塞写入：pending 语义由 config.py 自身测试覆盖，这里断言调用。
        patcher = patch(
            "app.config.config.update_config_values_nonblocking",
            side_effect=lambda section, changes: (
                self.updates.append((section, dict(changes))) or True
            ),
        )
        self.mock_update = patcher.start()
        self.addCleanup(patcher.stop)
        logging_patcher = patch(
            "app.config.config.update_logging_options", return_value=True
        )
        self.mock_logging = logging_patcher.start()
        self.addCleanup(logging_patcher.stop)
        config.app["api_key"] = ""
        self.client = TestClient(asgi.app)

    def tearDown(self):
        config.app.clear()
        config.app.update(self.original_app_config)
        config.azure.clear()
        config.azure.update(self.original_azure)
        config.ui.clear()
        config.ui.update(self.original_ui)

    # ── 分区快照与脱敏 ────────────────────────────────────────────────

    def test_section_snapshot_masks_credentials(self):
        config.app["openai_api_key"] = SECRET
        config.app["video_aspect"] = "16:9"
        response = self.client.get("/api/v1/settings/app")
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["video_aspect"], "16:9")
        self.assertEqual(
            data["openai_api_key"], {"configured": True, "masked": "sk-…1234"}
        )
        # 脱敏红线：任何设置类响应不出现密钥原文。
        self.assertNotIn(SECRET, response.text)

    def test_unknown_section_is_404(self):
        response = self.client.get("/api/v1/settings/nonexistent-section")
        self.assertEqual(response.status_code, 404)

    def test_settings_require_credentials_when_enabled(self):
        config.app["api_key"] = "settings-secret"
        anonymous = self.client.get("/api/v1/settings/app")
        self.assertEqual(anonymous.status_code, 401)
        authorized = self.client.get(
            "/api/v1/settings/app", headers={"x-api-key": "settings-secret"}
        )
        self.assertEqual(authorized.status_code, 200)

    # ── 部分更新与键白名单 ────────────────────────────────────────────

    def test_put_rejects_unknown_key(self):
        response = self.client.put(
            "/api/v1/settings/app", json={"definitely_not_a_key": 1}
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("unknown key", response.json()["message"])

    def test_put_accepts_known_and_new_credential_keys(self):
        config.app["video_aspect"] = "16:9"
        response = self.client.put(
            "/api/v1/settings/app",
            json={"video_aspect": "9:16", "deepseek_api_key": "sk-new"},
        )
        self.assertEqual(response.status_code, 200)
        section, changes = self.updates[-1]
        self.assertIs(section, config.app)
        self.assertEqual(changes["video_aspect"], "9:16")

    def test_put_rejects_masked_object_writeback(self):
        config.app["openai_api_key"] = SECRET
        response = self.client.put(
            "/api/v1/settings/app",
            json={"openai_api_key": {"configured": True, "masked": "sk-…1234"}},
        )
        self.assertEqual(response.status_code, 400)

    # ── 就绪度概览 ────────────────────────────────────────────────────

    def test_overview_shape(self):
        with patch(
            "app.controllers.v1.settings._codex_connected", return_value=False
        ), patch(
            "app.controllers.v1.settings._chatgpt_connected", return_value=False
        ), patch(
            "app.controllers.v1.settings._kimi_connected", return_value=False
        ):
            response = self.client.get("/api/v1/settings/overview")
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertIn("configured", data["llm"])
        self.assertIn("stock_video", data["material"])

    # ── 日志选项 ──────────────────────────────────────────────────────

    def test_logging_update_and_validation(self):
        ok = self.client.post(
            "/api/v1/settings/logging",
            json={"level": "info", "log_requests": True},
        )
        self.assertEqual(ok.status_code, 200)
        self.mock_logging.assert_called_once_with("INFO", True)
        bad = self.client.post(
            "/api/v1/settings/logging", json={"level": "NOTICE"}
        )
        self.assertEqual(bad.status_code, 400)

    # ── Key 备份 / 恢复 ───────────────────────────────────────────────

    def test_keys_backup_masks_credentials(self):
        config.app["openai_api_key"] = SECRET
        config.app["pexels_api_keys"] = ["abc…defg"]
        config.azure["speech_key"] = "azure-secret-key"
        config.azure["speech_region"] = "eastasia"
        config.ui["language"] = "zh"
        response = self.client.get("/api/v1/settings/keys/backup")
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertTrue(data["masked"])
        # 备份范围：凭据 + 配套项；ui 分区跳过。
        self.assertEqual(data["keys"]["azure"]["speech_region"], "eastasia")
        self.assertNotIn("ui", data["keys"])
        self.assertNotIn("language", str(data["keys"]))
        for entry in (
            data["keys"]["app"]["openai_api_key"],
            data["keys"]["azure"]["speech_key"],
        ):
            self.assertIsInstance(entry, dict)
            self.assertTrue(entry["configured"])
        self.assertNotIn(SECRET, response.text)
        self.assertNotIn("azure-secret-key", response.text)

    def test_keys_restore_rejects_masked_values(self):
        response = self.client.post(
            "/api/v1/settings/keys/restore",
            json={"keys": {"app": {"openai_api_key": {"configured": True, "masked": "sk-…1234"}}}},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("masked", response.json()["message"])

    def test_keys_restore_applies_raw_values_in_scope(self):
        response = self.client.post(
            "/api/v1/settings/keys/restore",
            json={
                "keys": {
                    "app": {"openai_api_key": SECRET, "not_a_key_scope": "x"},
                    "nonexistent-section": {"openai_api_key": SECRET},
                }
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertTrue(data["applied"])
        self.assertEqual(data["restored_count"], 1)

    def test_keys_restore_rejects_empty(self):
        response = self.client.post("/api/v1/settings/keys/restore", json={"keys": {}})
        self.assertEqual(response.status_code, 400)
        self.assertIn("no restorable keys", response.json()["message"])


if __name__ == "__main__":
    unittest.main()
